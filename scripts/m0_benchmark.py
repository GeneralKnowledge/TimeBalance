"""M0 benchmark: Timestral sizes x devices x context lengths x horizons.

    uv run python scripts/m0_benchmark.py [--sizes 5M 28M 123M 209M] [--devices cpu cuda] [--runs 10]

Each (size, device) runs in a fresh subprocess so cold-load time and memory are not polluted by
earlier models. Then one extra subprocess cycles load -> forecast -> unload through every size in
sequence, as production will, and records RSS/VRAM after each unload.

Measured: cold load time; warm latency p50/p95 over --runs calls (after one warm-up call); peak
process RSS (psutil, sampled every 2 ms) and peak VRAM (torch.cuda.max_memory_allocated) per
configuration; output validity; repeat determinism; GPU-vs-CPU difference; memory after unload.
OOM and other failures are caught and recorded as results.

Writes benchmarks/m0_<hostname>_<date>.json and benchmarks/m0_<hostname>_<date>.md.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CONTEXTS = (512, 2048, 8192)
HORIZONS = (1, 20, 96)


class PeakRSS:
    """Samples this process's RSS in a background thread; ``peak_mb`` since the last reset."""

    def __init__(self, interval: float = 0.002) -> None:
        import psutil

        self._p = psutil.Process()
        self._interval = interval
        self._peak = 0
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            rss = self._p.memory_info().rss
            self._peak = max(self._peak, rss)
            time.sleep(self._interval)

    def reset(self) -> None:
        self._peak = self._p.memory_info().rss

    @property
    def now_mb(self) -> float:
        return self._p.memory_info().rss / 2**20

    @property
    def peak_mb(self) -> float:
        return max(self._peak, self._p.memory_info().rss) / 2**20

    def stop(self) -> None:
        self._stop.set()


def _is_oom(e: BaseException) -> bool:
    import torch

    return isinstance(e, (MemoryError, torch.OutOfMemoryError)) or "out of memory" in str(e).lower()


def _series(n: int):
    import numpy as np

    rng = np.random.default_rng(0)
    t = np.arange(n)
    return (np.sin(2 * np.pi * t / 24) + 0.3 * rng.standard_normal(n).cumsum() / 10).astype(np.float64)


def worker(size: str, device: str, runs: int) -> dict:
    import numpy as np
    import torch

    from mpe.fixtures import make_input, synthetic_index
    from mpe.models.base import validate_output
    from mpe.models.timestral import TimestralModel

    torch.set_num_threads(os.cpu_count() or 1)
    mon = PeakRSS()
    cuda = device.startswith("cuda")
    res: dict = {"size": size, "device": device, "configs": []}
    rss_before = mon.now_mb
    if cuda:
        torch.cuda.init()
        torch.cuda.reset_peak_memory_stats()
        res["cuda_context_rss_mb"] = round(mon.now_mb - rss_before, 1)
        rss_before = mon.now_mb
    res["rss_before_load_mb"] = round(rss_before, 1)

    model = TimestralModel(size, clip_nonnegative=False)
    mon.reset()
    t0 = time.perf_counter()
    try:
        model.load(device)
    except Exception as e:  # noqa: BLE001
        res["load_error"] = f"{type(e).__name__}: {e}"[:500]
        res["load_oom"] = _is_oom(e)
        return res
    res["cold_load_s"] = round(time.perf_counter() - t0, 3)
    res["load_peak_rss_mb"] = round(mon.peak_mb, 1)
    res["rss_after_load_mb"] = round(mon.now_mb, 1)
    if cuda:
        res["vram_after_load_mb"] = round(torch.cuda.memory_allocated() / 2**20, 1)

    full = _series(max(CONTEXTS))
    idx = synthetic_index(len(full))
    for ctx in CONTEXTS:
        for h in HORIZONS:
            cfg: dict = {"context": ctx, "horizon": h}
            inp = make_input(full[-ctx:], idx[-ctx:], h)
            try:
                if cuda:
                    torch.cuda.reset_peak_memory_stats()
                mon.reset()
                first = model.forecast(inp)  # warm-up, also the determinism reference
                validate_output(first, 1, h)
                times = []
                max_repeat_diff = 0.0
                for _ in range(runs):
                    out = model.forecast(inp)
                    times.append(out.inference_ms)
                    max_repeat_diff = max(
                        max_repeat_diff, float(np.abs(out.quantiles - first.quantiles).max())
                    )
                cfg.update(
                    ok=True,
                    p50_ms=round(float(np.percentile(times, 50)), 2),
                    p95_ms=round(float(np.percentile(times, 95)), 2),
                    first_call_ms=round(first.inference_ms, 2),
                    peak_rss_mb=round(mon.peak_mb, 1),
                    max_repeat_abs_diff=max_repeat_diff,
                    median_last=float(first.values[0, -1]),
                    quantiles_sha=_sha(first.quantiles),
                )
                if cuda:
                    cfg["peak_vram_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
                if ctx == 2048 and h == 20:
                    res["reference_quantiles_2048_20"] = first.quantiles.tolist()
            except Exception as e:  # noqa: BLE001
                cfg.update(ok=False, oom=_is_oom(e), error=f"{type(e).__name__}: {e}"[:500])
                if cuda:
                    torch.cuda.empty_cache()
            res["configs"].append(cfg)
            print(
                f"  {size} {device} ctx={ctx} h={h}: {cfg.get('p50_ms', cfg.get('error'))}", file=sys.stderr
            )

    model.unload()
    time.sleep(0.2)
    res["rss_after_unload_mb"] = round(mon.now_mb, 1)
    if cuda:
        res["vram_after_unload_mb"] = round(torch.cuda.memory_allocated() / 2**20, 2)
        res["vram_reserved_after_unload_mb"] = round(torch.cuda.memory_reserved() / 2**20, 2)
    mon.stop()
    return res


def sequence_worker(sizes: list[str], device: str) -> dict:
    """One process: load -> forecast -> unload each size in turn, as the ModelManager will."""
    import torch

    from mpe.fixtures import make_input, synthetic_index
    from mpe.models.base import validate_output
    from mpe.models.registry import ModelManager

    mon = PeakRSS()
    cuda = device.startswith("cuda")
    if cuda:
        torch.cuda.init()
    start = mon.now_mb
    full = _series(2048)
    inp = make_input(full, synthetic_index(len(full)), 20)
    mgr = ModelManager(max_resident=1, device=device)
    steps = []
    for size in sizes:
        mon.reset()
        m = mgr.get(f"timestral-{size.lower()}")
        validate_output(m.forecast(inp), 1, 20)
        peak = mon.peak_mb
        mgr.release_all()
        time.sleep(0.2)
        step = {"size": size, "peak_rss_mb": round(peak, 1), "rss_after_unload_mb": round(mon.now_mb, 1)}
        if cuda:
            step["vram_after_unload_mb"] = round(torch.cuda.memory_allocated() / 2**20, 2)
        steps.append(step)
        print(f"  sequence {device} {size}: {step}", file=sys.stderr)
    mon.stop()
    return {"device": device, "rss_start_mb": round(start, 1), "steps": steps,
            "max_peak_rss_mb": max(s["peak_rss_mb"] for s in steps)}  # fmt: skip


def _sha(a) -> str:
    import hashlib

    return hashlib.sha256(a.astype("float64").tobytes()).hexdigest()[:16]


def env_info() -> dict:
    import psutil
    import torch

    from mpe.models.timestral import cuda_usable

    ok, why = cuda_usable()
    info = {
        "hostname": socket.gethostname(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "cuda_usable": ok,
        "cuda_reason": why,
        "arch_list": torch.cuda.get_arch_list() if torch.cuda.is_available() else [],
        "cpu": platform.processor() or platform.machine(),
        "cpu_threads": os.cpu_count(),
        "torch_threads": torch.get_num_threads(),
        "ram_total_mb": round(psutil.virtual_memory().total / 2**20),
    }
    if torch.cuda.is_available():
        info["gpu"] = torch.cuda.get_device_name(0)
        info["gpu_capability"] = ".".join(map(str, torch.cuda.get_device_capability(0)))
        info["vram_total_mb"] = round(torch.cuda.get_device_properties(0).total_memory / 2**20)
    try:
        info["cpu"] = next(
            line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines()
            if line.startswith("model name")
        )
    except (OSError, StopIteration):
        pass
    return info


def _run_sub(args: list[str]) -> dict:
    p = subprocess.run([sys.executable, __file__, *args], capture_output=True, text=True, check=False)
    sys.stderr.write(p.stderr[-4000:])
    if p.returncode != 0:
        return {"process_error": f"exit {p.returncode}", "stderr_tail": p.stderr[-1500:]}
    return json.loads(p.stdout.strip().splitlines()[-1])


def summarise(report: dict) -> str:
    lines = [
        f"# M0 benchmark: {report['env']['hostname']} {report['date']}",
        "",
        (
            f"torch {report['env']['torch']} (CUDA {report['env']['torch_cuda']}), "
            f"CUDA usable: {report['env']['cuda_usable']} ({report['env']['cuda_reason']}); "
            f"CPU {report['env']['cpu']}, {report['env']['cpu_threads']} threads; "
            f"RAM {report['env']['ram_total_mb']} MB. Batch 1, univariate, symmetric averaging on "
            f"(2 passes per forecast), {report['runs']} warm runs per cell."
        ),
        "",
        "| size | device | cold load s | ctx | h | p50 ms | p95 ms | peak RSS MB | peak VRAM MB | repeat diff |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in report["results"]:
        if "configs" not in r:
            lines.append(
                f"| {r.get('size')} | {r.get('device')} | failed: {r.get('process_error') or r.get('load_error')} |"
            )
            continue
        for c in r["configs"]:
            if c.get("ok"):
                lines.append(
                    f"| {r['size']} | {r['device']} | {r.get('cold_load_s', '')} | {c['context']} | {c['horizon']} | "
                    f"{c['p50_ms']} | {c['p95_ms']} | {c['peak_rss_mb']} | {c.get('peak_vram_mb', '-')} | "
                    f"{c['max_repeat_abs_diff']:.1e} |"
                )
            else:
                kind = "OOM" if c.get("oom") else "error"
                lines.append(
                    f"| {r['size']} | {r['device']} | | {c['context']} | {c['horizon']} | {kind}: {c['error'][:80]} | | | | |"
                )
    lines += ["", "Memory around load/unload (fresh process per row):", "",
              "| size | device | RSS before load | RSS after load | RSS after unload | VRAM after load | VRAM after unload |",
              "|---|---|---|---|---|---|---|"]  # fmt: skip
    for r in report["results"]:
        if "configs" in r:
            lines.append(
                f"| {r['size']} | {r['device']} | {r['rss_before_load_mb']} | {r.get('rss_after_load_mb')} | "
                f"{r.get('rss_after_unload_mb')} | {r.get('vram_after_load_mb', '-')} | {r.get('vram_after_unload_mb', '-')} |"
            )
    if report.get("gpu_vs_cpu"):
        lines += ["", "GPU vs CPU, max |difference| over all quantiles (ctx 2048, h 20):", ""]
        lines += [f"- {k}: {v:.2e}" for k, v in report["gpu_vs_cpu"].items()]
    for seq in report.get("sequences", []):
        lines += ["", (f"Sequential load/forecast/unload in one process ({seq.get('device')}): "
                  f"max peak RSS {seq.get('max_peak_rss_mb')} MB"), ""]  # fmt: skip
        for s in seq.get("steps", []):
            lines.append(f"- {s}")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", nargs="+", default=["5M", "28M", "123M", "209M"])
    ap.add_argument("--devices", nargs="+", default=None)
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--worker", nargs=2, metavar=("SIZE", "DEVICE"))
    ap.add_argument("--sequence", metavar="DEVICE")
    args = ap.parse_args()

    if args.worker:
        print(json.dumps(worker(args.worker[0], args.worker[1], args.runs)))
        return 0
    if args.sequence:
        print(json.dumps(sequence_worker(args.sizes, args.sequence)))
        return 0

    import numpy as np

    env = env_info()
    devices = args.devices or (["cpu", "cuda"] if env["cuda_usable"] else ["cpu"])
    report = {"date": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "env": env,
              "runs": args.runs, "contexts": CONTEXTS, "horizons": HORIZONS, "results": []}  # fmt: skip
    for size in args.sizes:
        for dev in devices:
            print(f"[{size} on {dev}]", file=sys.stderr)
            report["results"].append(_run_sub(["--worker", size, dev, "--runs", str(args.runs)]))
    report["gpu_vs_cpu"] = {}
    for size in args.sizes:
        ref = {
            r.get("device"): r.get("reference_quantiles_2048_20")
            for r in report["results"]
            if r.get("size") == size
        }
        if ref.get("cpu") and ref.get("cuda"):
            report["gpu_vs_cpu"][size] = float(np.abs(np.array(ref["cpu"]) - np.array(ref["cuda"])).max())
    for r in report["results"]:
        r.pop("reference_quantiles_2048_20", None)
    report["sequences"] = [_run_sub(["--sequence", d, "--sizes", *args.sizes]) for d in devices]

    out_dir = ROOT / "benchmarks"
    out_dir.mkdir(exist_ok=True)
    stem = f"m0_{env['hostname']}_{report['date'][:10]}"
    (out_dir / f"{stem}.json").write_text(json.dumps(report, indent=2) + "\n")
    (out_dir / f"{stem}.md").write_text(summarise(report))
    print(summarise(report))
    print(f"wrote benchmarks/{stem}.json and .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
