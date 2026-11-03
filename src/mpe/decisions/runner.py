"""Run a decision model over stored snapshots, persisting every input and output before scoring."""

from __future__ import annotations

import hashlib
import json
import logging
import platform
import resource
import time
from dataclasses import asdict

from mpe.clock import Clock
from mpe.decisions.base import DecisionModel, DecisionRequest
from mpe.decisions.snapshot import SNAPSHOT_SCHEMA, STATE_TEMPLATE, iso, render_state
from mpe.decisions.store import DecisionStore
from mpe.decisions.tasks import load_questions
from mpe.research.store import code_version

log = logging.getLogger(__name__)


def hardware_info() -> dict:
    info = {"platform": platform.platform(), "python": platform.python_version(),
            "cpu": platform.processor() or platform.machine()}  # fmt: skip
    try:
        import psutil

        info["ram_total_gb"] = round(psutil.virtual_memory().total / 2**30, 1)
        info["cpu_count"] = psutil.cpu_count()
    except ImportError:
        pass
    try:
        import torch

        info["torch"] = torch.__version__
        if torch.cuda.is_available():
            p = torch.cuda.get_device_properties(0)
            info["gpu"] = p.name
            info["gpu_capability"] = f"{p.major}.{p.minor}"
            info["vram_total_gb"] = round(p.total_memory / 2**30, 2)
    except ImportError:
        pass
    return info


def peak_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # Linux: KiB


def _cuda():
    try:
        import torch

        return torch if torch.cuda.is_available() else None
    except ImportError:
        return None


def run_decisions(
    store: DecisionStore, model: DecisionModel, clock: Clock, *, device: str = "auto",
    tasks_path=None, max_snapshots: int | None = None, chunk: int = 32, resume_run: str | None = None,
) -> str:  # fmt: skip
    qversion, qhash, questions = load_questions(tasks_path)
    snaps = store.snapshots()
    if max_snapshots:
        snaps = snaps[:max_snapshots]
    torch = _cuda()
    if torch is not None:
        torch.cuda.reset_peak_memory_stats()
    rss_before = peak_rss_mb()
    t0 = time.perf_counter()
    model.load(device)
    load_s = time.perf_counter() - t0
    meta = model.metadata()
    if resume_run:
        run_id = resume_run
        if store.run(run_id)["question_hash"] != qhash:
            raise ValueError("question set changed since this run started; start a new run")
    else:
        now = clock.now()
        run_id = f"{meta.name}-{now:%Y%m%dT%H%M%S}-" + hashlib.sha256(
            f"{meta.version}{qhash}{len(snaps)}".encode()).hexdigest()[:6]  # fmt: skip
        store.create_run({
            "run_id": run_id, "created_at": iso(now), "status": "running", "model_name": meta.name,
            "provider": meta.provider, "checkpoint": meta.checkpoint, "model_version": meta.version,
            "library_version": meta.library_version, "question_version": qversion, "question_hash": qhash,
            "questions_json": json.dumps([q.to_dict() for q in questions]), "state_template": STATE_TEMPLATE,
            "snapshot_schema": SNAPSHOT_SCHEMA,
            "config_json": json.dumps({"device": device, "max_snapshots": max_snapshots, "chunk": chunk,
                                       "model": meta.to_dict()}),
            "hardware_json": json.dumps(hardware_info()), "code_version": code_version(),
        })  # fmt: skip
    done = store.done_snapshots(run_id)
    todo = [s for s in snaps if s["snapshot_id"] not in done]
    log.info("run %s: %d snapshots to score (%d already done)", run_id, len(todo), len(done))
    n_err = 0
    latencies = []
    t_inf = time.perf_counter()
    for start in range(0, len(todo), chunk):
        batch = todo[start : start + chunk]
        reqs = []
        for s in batch:
            snap = json.loads(s["snapshot_json"])
            state = render_state(snap)
            rid = hashlib.sha256((s["snapshot_id"] + qhash + STATE_TEMPLATE).encode()).hexdigest()[:16]
            reqs.append(DecisionRequest(rid, state, questions, s["decision_ts"], SNAPSHOT_SCHEMA))
        results = model.decide_batch(reqs)
        now = iso(clock.now())
        rows = []
        for s, req, res in zip(batch, reqs, results, strict=True):
            n_err += res.error is not None
            latencies.append(res.latency_ms)
            rows.append({
                "run_id": run_id, "snapshot_id": s["snapshot_id"], "request_id": req.request_id,
                "state_json": json.dumps(req.state, sort_keys=True),
                "raw_json": None if res.raw is None else json.dumps(res.raw),
                "normalised_json": json.dumps({k: asdict(a) for k, a in res.answers.items()}),
                "latency_ms": res.latency_ms, "device": res.device, "error": res.error, "created_at": now,
            })  # fmt: skip
        store.insert_outputs(rows)
        log.info("run %s: %d/%d", run_id, start + len(batch), len(todo))
    wall = time.perf_counter() - t_inf
    bench = {
        "load_seconds": round(getattr(model, "load_seconds", None) or load_s, 2),
        "peak_rss_mb": round(peak_rss_mb(), 0), "rss_before_load_mb": round(rss_before, 0),
        "peak_vram_allocated_mb": None if torch is None else round(torch.cuda.max_memory_allocated() / 2**20, 0),
        "peak_vram_reserved_mb": None if torch is None else round(torch.cuda.max_memory_reserved() / 2**20, 0),
        "snapshots": len(todo), "questions_per_snapshot": len(questions), "errors": n_err,
        "failure_rate": round(n_err / len(todo), 4) if todo else None,
        "latency_ms_per_snapshot_mean": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "latency_ms_per_snapshot_p95": (round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 1)
                                        if latencies else None),
        "snapshots_per_second": round(len(todo) / wall, 2) if wall > 0 and todo else None,
        "decisions_per_second": round(len(todo) * len(questions) / wall, 1) if wall > 0 and todo else None,
        "device": meta.extra.get("device"),
    }  # fmt: skip
    model.unload()
    store.update_run(run_id, status="done", finished_at=iso(clock.now()), benchmark_json=json.dumps(bench))
    return run_id
