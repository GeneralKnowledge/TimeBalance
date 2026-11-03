"""Experiment execution: prepare origins once, then run one model at a time over all of them.

Order of work for ``run``:

1. Load the saved configuration (its hash is re-checked).
2. Prepare every origin's context through the replay accessor and read realised targets. The
   first preparation is stored (``research_origins`` / ``research_targets``); later runs rebuild
   the contexts and refuse to continue if any input hash differs (the data changed underneath).
3. For each model in configuration order: load it through ``ModelManager`` (one resident model),
   forecast every pending origin, validate each output with ``validate_output``, store it (or the
   failure), then unload. Forecasts already stored are skipped, so an interrupted run resumes
   without duplicating anything.
"""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import psutil
from sqlalchemy.orm import Session, sessionmaker

from mpe.clock import Clock, to_iso
from mpe.models.base import ForecastInput, ForecastModel, validate_output
from mpe.models.baselines import BASELINES
from mpe.models.registry import ModelManager
from mpe.research.config import ExperimentConfig, ModelSpec
from mpe.research.data import OriginBuilder, PreparedOrigin, json_ts, make_grid, resolve_assets
from mpe.research.store import ResearchStore, code_version, pack

log = logging.getLogger(__name__)

ModelFactory = Callable[[ModelSpec], ForecastModel]
Progress = Callable[[str, int, int, float], None]


class DataChanged(RuntimeError):
    """A rebuilt input differs from the stored one: the experiment's data is no longer the same."""


class VersionChanged(RuntimeError):
    pass


def default_model_factory(spec: ModelSpec) -> ForecastModel:
    if spec.family == "timestral":
        from mpe.models.timestral import TimestralModel  # lazy: keeps torch out of baseline-only runs

        return TimestralModel(spec.name.split("-", 1)[1].upper(), **spec.params)
    return BASELINES[spec.name](**spec.params)


@dataclass
class Prepared:
    cfg: ExperimentConfig
    ok: list[PreparedOrigin]
    summary: dict = field(default_factory=dict)


def _grid_start(cfg: ExperimentConfig) -> pd.Timestamp:
    start = pd.Timestamp(cfg.origin_start)
    if cfg.domain == "stocks":  # (context + 1) sessions back, with generous room for holidays
        return start - pd.Timedelta(days=int((cfg.context_length + 1) * 7 / 5 * 1.15) + 30)
    return start - pd.Timedelta(hours=cfg.context_length + 2)


class ExperimentRunner:
    def __init__(
        self,
        market_factory: sessionmaker[Session],
        store: ResearchStore,
        clock: Clock,
        model_factory: ModelFactory = default_model_factory,
        progress: Progress | None = None,
        commit_every: int = 100,
    ):
        self.market = market_factory
        self.store = store
        self.clock = clock
        self.model_factory = model_factory
        self.progress = progress
        self.commit_every = commit_every

    # -- preparation ----------------------------------------------------------------
    def prepare(self, eid: str) -> Prepared:
        row = self.store.get(eid)
        cfg = row.config
        stored = self.store.origin_hashes(eid)
        stored_by_asset: dict[str, list[str]] = {}
        for a, t in stored:
            stored_by_asset.setdefault(a, []).append(t)
        ok: list[PreparedOrigin] = []
        summary: dict = {"assets": {}, "excluded_assets": [e.model_dump() for e in cfg.excluded_assets]}
        with self.market() as s:
            assets, excluded = resolve_assets(s, cfg)
            summary["excluded_assets"] += [e.model_dump() for e in excluded]
            grid = make_grid(cfg, _grid_start(cfg).to_pydatetime())
            b = OriginBuilder(s, cfg, grid)
            for a in assets:
                info: dict = {"label": a.label, **({"meta": a.meta} if a.meta else {})}
                if a.key in stored_by_asset:  # resume: exactly the stored origins, rebuilt and verified
                    cand = sorted(pd.Timestamp(t) for t in stored_by_asset[a.key])
                    skipped = (row.prepare or {}).get("assets", {}).get(a.key, {}).get("skipped", {})
                    span = None
                else:
                    span = b.data_span(a)
                    cand, skipped = b.candidate_origins(a, span)
                pos = [b.prepare_origin(a, t) for t in cand]
                reasons: dict[str, int] = {}
                for po in pos:
                    if po.status != "ok":
                        reasons[po.reason] = reasons.get(po.reason, 0) + 1
                info.update(skipped=skipped, candidate_origins=len(cand), ok_origins=sum(p.status == "ok" for p in pos),
                            excluded_origins=reasons)  # fmt: skip
                if span is not None:
                    info["data_span"] = [to_iso(span[0].to_pydatetime()), to_iso(span[1].to_pydatetime())]
                if a.key in stored_by_asset:
                    self._verify(a.key, pos, stored)
                else:
                    self._store_asset(eid, cfg, b, a, pos)
                if a.key in stored_by_asset and row.prepare:
                    info = (row.prepare.get("assets") or {}).get(a.key, info)
                summary["assets"][a.key] = info
                ok += [p for p in pos if p.status == "ok"]
                log.info("prepared %s: %d origins, %d usable", a.key, len(pos), info.get("ok_origins", 0))
        if row.prepare is None:
            self.store.set_prepare(eid, summary)
        if row.status == "created":
            self.store.set_status(eid, "prepared", self.clock.now())
        return Prepared(cfg, ok, summary)

    def _verify(self, asset: str, pos: list[PreparedOrigin], stored: dict) -> None:
        for po in pos:
            key = (asset, to_iso(po.origin_ts.to_pydatetime()))
            st, h = stored[key]
            if st != po.status or h != po.input_hash:
                raise DataChanged(f"{asset} origin {key[1]}: stored {st}/{h}, rebuilt {po.status}/{po.input_hash}; "
                                  "the market data seen by this experiment has changed")  # fmt: skip

    def _store_asset(
        self, eid: str, cfg: ExperimentConfig, b: OriginBuilder, a, pos: list[PreparedOrigin]
    ) -> None:
        orow = [{
            "experiment_id": eid, "asset": a.key, "origin_ts": to_iso(p.origin_ts.to_pydatetime()),
            "cutoff_ts": to_iso(p.cutoff), "status": p.status, "reason": p.reason,
            "target_timestamps_json": json_ts(p.target_timestamps), "context_start": p.context_start,
            "context_end": p.context_end, "context_points": None if p.values is None else len(p.values),
            "missing_points": p.missing_points, "last_level": p.last_level, "last_value": p.last_value,
            "input_hash": p.input_hash, "provenance_json": _dumps(p.provenance),
        } for p in pos]  # fmt: skip
        trows: list[dict] = []
        ok = [p for p in pos if p.status == "ok"]
        if ok:
            first = min(p.target_timestamps[0] for p in ok)
            last = max(p.target_timestamps[-1] for p in ok)
            prev = b.grid.upto(first - pd.Timedelta(seconds=1), 1)  # one point earlier, for returns
            start = prev[0] if len(prev) else first
            needed = {t for p in ok for t in p.target_timestamps}
            real = b.realised(a, start, last)
            for r in real.itertuples(index=False):
                if r.target_ts not in needed:
                    continue
                trows.append({
                    "experiment_id": eid, "asset": a.key, "target_ts": to_iso(r.target_ts.to_pydatetime()),
                    "value": None if np.isnan(r.value) else float(r.value),
                    "level": None if np.isnan(r.level) else float(r.level), "status": r.status,
                    "available_at": None if r.available_at is None or pd.isna(r.available_at)
                    else to_iso(pd.Timestamp(r.available_at).to_pydatetime()),
                    "version": None if r.version is None or pd.isna(r.version) else int(r.version),
                    "knowledge": r.knowledge,
                })  # fmt: skip
        with self.store.tx() as c:  # one asset = one transaction: never half-stored
            self.store.insert_origins(c, orow)
            self.store.insert_targets(c, trows)

    # -- execution ------------------------------------------------------------------
    def run(self, eid: str, models: list[str] | None = None, max_forecasts: int | None = None,
            allow_code_change: bool = False) -> dict:  # fmt: skip
        row = self.store.get(eid)
        cfg = row.config
        code = code_version()
        if code != row.code_version and not allow_code_change:
            log.warning("code version %s differs from experiment creation %s (recorded per model run)",
                        code, row.code_version)  # fmt: skip
        prep = self.prepare(eid)
        specs = [m for m in cfg.models if models is None or m.name in models]
        unknown = set(models or []) - {m.name for m in cfg.models}
        if unknown:
            raise ValueError(f"models not in this experiment: {sorted(unknown)}")
        self.store.set_status(eid, "running", self.clock.now())
        budget = max_forecasts
        result: dict = {"experiment_id": eid, "models": {}}
        any_failed = False
        try:
            for spec in specs:
                r = self._run_model(eid, cfg, spec, prep.ok, budget, code)
                result["models"][spec.name] = r
                any_failed |= r["status"] == "failed"
                if budget is not None:
                    budget -= r["new"] + r["failed"]
                    if budget <= 0:
                        break
        except KeyboardInterrupt:
            self.store.set_status(
                eid, "interrupted", self.clock.now(), "interrupted by user; re-run to resume"
            )
            raise
        complete = self.is_complete(eid, cfg, prep)
        status = "completed" if complete else ("failed" if any_failed else "partial")
        self.store.set_status(eid, status, self.clock.now(), None if complete else "re-run to continue")
        result["status"] = status
        return result

    def is_complete(self, eid: str, cfg: ExperimentConfig, prep: Prepared) -> bool:
        need = {(p.asset, to_iso(p.origin_ts.to_pydatetime())) for p in prep.ok}
        return all(need <= self.store.done_forecasts(eid, m.name) for m in cfg.models)

    def _run_model(self, eid: str, cfg: ExperimentConfig, spec: ModelSpec, ok: list[PreparedOrigin],
                   budget: int | None, code: str) -> dict:  # fmt: skip
        done = self.store.done_forecasts(eid, spec.name)
        pending = [p for p in ok if (p.asset, to_iso(p.origin_ts.to_pydatetime())) not in done]
        if budget is not None:
            pending = pending[: max(budget, 0)]
        if not pending:
            return {"status": "complete", "new": 0, "failed": 0}
        run_id = self.store.start_model_run(eid, spec, cfg.device, code, self.clock.now())
        manager = ModelManager(
            {spec.name: lambda: self.model_factory(spec)}, max_resident=1, device=cfg.device
        )
        proc = psutil.Process()
        peak_rss = proc.memory_info().rss
        vram = False
        idx = [h - 1 for h in cfg.horizons]
        levels = tuple(cfg.quantile_levels)
        buf: list[dict] = []
        n_new = n_failed = 0
        infer_ms = 0.0
        device = None
        status, error, version = "running", None, None
        t0 = time.perf_counter()
        try:
            model = manager.get(spec.name)
            vram = _vram_reset()  # after loading: the peak covers this model's weights and inference only
            version = model.metadata().version
            prev = self.store.get(eid).model_versions.get(spec.name)
            if prev is not None and prev != version:
                raise VersionChanged(
                    f"{spec.name} version {version} differs from {prev} used earlier in {eid}"
                )
            self.store.set_model_version(eid, spec.name, version)
            for i, p in enumerate(pending):
                rec = {"experiment_id": eid, "model_name": spec.name, "asset": p.asset,
                       "origin_ts": to_iso(p.origin_ts.to_pydatetime()), "model_run_id": run_id,
                       "input_hash": p.input_hash, "created_at": to_iso(self.clock.now()),
                       "status": "failed", "error": None, "median": None, "quantiles": None, "device": None,
                       "inference_ms": None, "input_window_json": None}  # every row binds every column  # fmt: skip
                try:
                    inp = ForecastInput(values=p.values, timestamps=p.timestamps, series_names=(p.asset,),
                                        horizon=cfg.max_horizon, input_cutoff=p.cutoff,
                                        future_timestamps=p.future_timestamps, quantile_levels=levels,
                                        seed=cfg.seed)  # fmt: skip
                    out = model.forecast(inp)
                    validate_output(out, 1, cfg.max_horizon)
                    if tuple(out.quantile_levels) != levels or out.quantiles is None:
                        raise AssertionError(f"quantile levels {out.quantile_levels} != requested")
                    if not np.array_equal(out.timestamps.astype("datetime64[ns]"), p.future_timestamps):
                        raise AssertionError("output timestamps differ from the requested target timestamps")
                    rec.update(status="ok", median=pack(out.values[0, idx]), quantiles=pack(out.quantiles[0, idx, :]),
                               device=out.device, inference_ms=out.inference_ms,
                               input_window_json=_dumps(out.input_window))  # fmt: skip
                    device = out.device
                    infer_ms += out.inference_ms
                    n_new += 1
                except (KeyboardInterrupt, MemoryError):
                    raise
                except Exception as e:  # noqa: BLE001 - invalid output or a model error: recorded, never hidden
                    rec.update(status="failed", error=f"{type(e).__name__}: {e}"[:2000])
                    n_failed += 1
                buf.append(rec)
                if len(buf) >= self.commit_every:
                    self.store.insert_forecasts(buf)
                    buf = []
                    peak_rss = max(peak_rss, proc.memory_info().rss)
                if self.progress and (i + 1) % 50 == 0:
                    self.progress(spec.name, i + 1, len(pending), time.perf_counter() - t0)
            status = "completed" if len(pending) + len(done) >= len(ok) else "partial"
        except KeyboardInterrupt:
            status, error = "interrupted", "KeyboardInterrupt"
            raise
        except Exception as e:
            status, error = "failed", f"{type(e).__name__}: {e}"[:2000]
            log.exception("model %s failed in %s", spec.name, eid)
        finally:
            self.store.insert_forecasts(buf)
            peak_rss = max(peak_rss, proc.memory_info().rss)
            manager.release_all()
            self.store.finish_model_run(
                run_id, self.clock.now(), status=status, error=error, device=device, n_new_forecasts=n_new,
                n_failed=n_failed, inference_ms_total=infer_ms, wall_seconds=time.perf_counter() - t0,
                model_version=version,
                peak_rss_mb=peak_rss / 2**20, peak_vram_mb=_vram_peak(vram),
            )  # fmt: skip
            if self.progress:
                self.progress(spec.name, n_new + n_failed, len(pending), time.perf_counter() - t0)
        return {"status": status, "new": n_new, "failed": n_failed, "error": error, "device": device}


def _vram_reset() -> bool:
    torch = sys.modules.get("torch")
    if torch is None or not torch.cuda.is_available() or not torch.cuda.is_initialized():
        return False
    torch.cuda.reset_peak_memory_stats()
    return True


def _vram_peak(was_reset: bool) -> float | None:
    torch = sys.modules.get("torch")
    if torch is None or not torch.cuda.is_available() or not torch.cuda.is_initialized():
        return None
    return torch.cuda.max_memory_allocated() / 2**20


def _dumps(d: dict) -> str:
    import json

    return json.dumps(d, sort_keys=True, default=str)
