"""The research results database.

Research results live in their own SQLite file (``research_database_path``, default
``data/research.sqlite3``), not in the market-data database. The market-data database is opened
read-only by the research commands, so an experiment cannot modify observations, and the
operational ``forecasts`` / ``evaluations`` tables stay reserved for live forecasting (M3).

Tables (schema version 1):

``research_experiments``  one row per configuration (id = domain + config hash); status mutable
``research_origins``      one row per (experiment, asset, origin): cutoff, target timestamps,
                          input hash, provenance, or the exclusion reason. Immutable.
``research_targets``      realised target values per (experiment, asset, target timestamp), or
                          why there is none. Immutable.
``research_model_runs``   one row per model execution attempt (device, versions, timing, memory)
``research_forecasts``    one row per (experiment, model, asset, origin): median and quantiles at
                          the configured horizons (little-endian float64 blobs), or the failure.
                          Immutable; the primary key makes a duplicate forecast impossible.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from sqlalchemy import (
    Column,
    Engine,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    create_engine,
    event,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.engine import Connection

from mpe.clock import to_iso
from mpe.config import ROOT
from mpe.research.config import ExperimentConfig

SCHEMA_VERSION = "1"
IMMUTABLE = ("research_origins", "research_targets", "research_forecasts")

meta = MetaData()

research_meta = Table("research_meta", meta, Column("key", Text, primary_key=True), Column("value", Text))

experiments = Table(
    "research_experiments", meta,
    Column("experiment_id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("domain", Text, nullable=False),
    Column("knowledge_mode", Text, nullable=False),
    Column("config_hash", Text, nullable=False, unique=True),
    Column("config_version", Text, nullable=False),
    Column("config_json", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("code_version", Text, nullable=False),
    Column("status", Text, nullable=False),  # created | prepared | running | interrupted | completed | failed
    Column("status_detail", Text),
    Column("updated_at", Text, nullable=False),
    Column("prepare_json", Text),  # data summary from preparation (exclusion counts, data span)
    Column("model_versions_json", Text),
)  # fmt: skip

origins = Table(
    "research_origins", meta,
    Column("experiment_id", Text, ForeignKey("research_experiments.experiment_id"), nullable=False),
    Column("asset", Text, nullable=False),
    Column("origin_ts", Text, nullable=False),
    Column("cutoff_ts", Text, nullable=False),
    Column("status", Text, nullable=False),  # ok | excluded
    Column("reason", Text),
    Column("target_timestamps_json", Text, nullable=False),
    Column("context_start", Text),
    Column("context_end", Text),
    Column("context_points", Integer),
    Column("missing_points", Integer),
    Column("last_level", Float),
    Column("last_value", Float),
    Column("input_hash", Text),
    Column("provenance_json", Text),
    PrimaryKeyConstraint("experiment_id", "asset", "origin_ts"),
)  # fmt: skip

targets = Table(
    "research_targets", meta,
    Column("experiment_id", Text, ForeignKey("research_experiments.experiment_id"), nullable=False),
    Column("asset", Text, nullable=False),
    Column("target_ts", Text, nullable=False),
    Column("value", Float),  # realised target (log return / logit); NULL when not observed
    Column("level", Float),  # realised price / probability
    Column("status", Text, nullable=False),  # observed | target_missing | target_not_yet_available | after_market_close
    Column("available_at", Text),
    Column("version", Integer),
    Column("knowledge", Text),  # captured | reconstructed
    PrimaryKeyConstraint("experiment_id", "asset", "target_ts"),
)  # fmt: skip

model_runs = Table(
    "research_model_runs", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("experiment_id", Text, ForeignKey("research_experiments.experiment_id"), nullable=False),
    Column("model_name", Text, nullable=False),
    Column("family", Text, nullable=False),
    Column("model_version", Text),
    Column("params_json", Text, nullable=False),
    Column("code_version", Text, nullable=False),
    Column("requested_device", Text, nullable=False),
    Column("device", Text),
    Column("status", Text, nullable=False),  # running | completed | partial | interrupted | failed
    Column("started_at", Text, nullable=False),
    Column("finished_at", Text),
    Column("n_new_forecasts", Integer, nullable=False, default=0),
    Column("n_failed", Integer, nullable=False, default=0),
    Column("inference_ms_total", Float),
    Column("wall_seconds", Float),
    Column("peak_rss_mb", Float),
    Column("peak_vram_mb", Float),
    Column("error", Text),
)  # fmt: skip

forecasts = Table(
    "research_forecasts", meta,
    Column("experiment_id", Text, ForeignKey("research_experiments.experiment_id"), nullable=False),
    Column("model_name", Text, nullable=False),
    Column("asset", Text, nullable=False),
    Column("origin_ts", Text, nullable=False),
    Column("model_run_id", Integer, ForeignKey("research_model_runs.id"), nullable=False),
    Column("status", Text, nullable=False),  # ok | failed
    Column("error", Text),
    Column("input_hash", Text, nullable=False),
    Column("median", LargeBinary),  # float64 (n_horizons,)
    Column("quantiles", LargeBinary),  # float64 (n_horizons, n_levels)
    Column("device", Text),
    Column("inference_ms", Float),
    Column("input_window_json", Text),
    Column("created_at", Text, nullable=False),
    PrimaryKeyConstraint("experiment_id", "model_name", "asset", "origin_ts"),
)  # fmt: skip


def code_version(root: Path = ROOT) -> str:
    """Git commit of this checkout, with ``+dirty`` if tracked files are modified; 'unknown' otherwise."""
    try:
        sha = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True,
                             timeout=10, check=True).stdout.strip()  # fmt: skip
        dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True, timeout=10, check=True).stdout.strip()  # fmt: skip
        return sha + ("+dirty" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def make_research_engine(path: str | Path) -> Engine:
    url = str(path)
    if "://" not in url:
        Path(url).parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{url}"
    engine = create_engine(url, future=True)

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _record):  # pragma: no cover
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        if ":memory:" not in url:
            cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

    return engine


def make_readonly_market_engine(path: str | Path) -> Engine:
    """The market-data database opened read-only (SQLite ``mode=ro``, plus ``query_only``)."""
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"market database not found: {p}")
    engine = create_engine(f"sqlite:///file:{p}?mode=ro&uri=true", future=True)

    @event.listens_for(engine, "connect")
    def _ro(dbapi_conn, _record):  # pragma: no cover
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA query_only=ON")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

    return engine


def pack(a: np.ndarray) -> bytes:
    return np.ascontiguousarray(a, dtype="<f8").tobytes()


def unpack(b: bytes | None, shape: tuple[int, ...]) -> np.ndarray | None:
    return None if b is None else np.frombuffer(b, dtype="<f8").reshape(shape).copy()


class ExperimentExists(RuntimeError):
    pass


class UnknownExperiment(KeyError):
    pass


@dataclass
class ExperimentRow:
    experiment_id: str
    config: ExperimentConfig
    status: str
    created_at: str
    code_version: str
    status_detail: str | None
    prepare: dict | None
    model_versions: dict


class ResearchStore:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.init_schema()

    def init_schema(self) -> None:
        meta.create_all(self.engine)
        with self.engine.begin() as c:
            v = c.execute(
                select(research_meta.c.value).where(research_meta.c.key == "schema_version")
            ).scalar()
            if v is None:
                c.execute(insert(research_meta).values(key="schema_version", value=SCHEMA_VERSION))
            elif v != SCHEMA_VERSION:
                raise RuntimeError(f"research database schema {v}, code expects {SCHEMA_VERSION}")
            for t in IMMUTABLE:
                for op in ("UPDATE", "DELETE"):
                    c.execute(text(
                        f"CREATE TRIGGER IF NOT EXISTS {t}_no_{op.lower()} BEFORE {op} ON {t} "
                        f"BEGIN SELECT RAISE(ABORT, '{t} is immutable'); END"
                    ))  # fmt: skip

    @contextmanager
    def tx(self) -> Iterator[Connection]:
        with self.engine.begin() as c:
            yield c

    # -- experiments ------------------------------------------------------------------
    def create(self, cfg: ExperimentConfig, now: datetime, code: str | None = None) -> str:
        eid = cfg.experiment_id
        with self.tx() as c:
            row = c.execute(
                select(experiments.c.config_hash).where(experiments.c.experiment_id == eid)
            ).first()
            if row is not None:
                if row.config_hash != cfg.config_hash():  # 48-bit prefix collision: refuse
                    raise RuntimeError(f"experiment id collision for {eid}")
                raise ExperimentExists(eid)
            c.execute(insert(experiments).values(
                experiment_id=eid, name=cfg.name, domain=cfg.domain, knowledge_mode=cfg.knowledge_mode.value,
                config_hash=cfg.config_hash(), config_version=cfg.config_version, config_json=cfg.to_json(),
                created_at=to_iso(now), code_version=code or code_version(), status="created",
                updated_at=to_iso(now), model_versions_json="{}",
            ))  # fmt: skip
        return eid

    def get(self, eid: str) -> ExperimentRow:
        with self.tx() as c:
            r = c.execute(select(experiments).where(experiments.c.experiment_id == eid)).first()
        if r is None:
            raise UnknownExperiment(eid)
        cfg = ExperimentConfig.from_json(r.config_json)
        if cfg.config_hash() != r.config_hash:
            raise RuntimeError(f"{eid}: stored configuration does not match its hash")
        return ExperimentRow(eid, cfg, r.status, r.created_at, r.code_version, r.status_detail,
                             json.loads(r.prepare_json) if r.prepare_json else None,
                             json.loads(r.model_versions_json or "{}"))  # fmt: skip

    def list(self) -> list[dict]:
        with self.tx() as c:
            rows = c.execute(select(experiments.c.experiment_id, experiments.c.name, experiments.c.domain,
                                    experiments.c.knowledge_mode, experiments.c.status, experiments.c.created_at,
                                    experiments.c.updated_at).order_by(experiments.c.created_at)).all()  # fmt: skip
        return [dict(r._mapping) for r in rows]

    def set_status(self, eid: str, status: str, now: datetime, detail: str | None = None) -> None:
        with self.tx() as c:
            c.execute(update(experiments).where(experiments.c.experiment_id == eid)
                      .values(status=status, status_detail=detail, updated_at=to_iso(now)))  # fmt: skip

    def set_prepare(self, eid: str, summary: dict) -> None:
        with self.tx() as c:
            c.execute(update(experiments).where(experiments.c.experiment_id == eid)
                      .values(prepare_json=json.dumps(summary, sort_keys=True, default=str)))  # fmt: skip

    def set_model_version(self, eid: str, model: str, version: str) -> None:
        with self.tx() as c:
            r = c.execute(
                select(experiments.c.model_versions_json).where(experiments.c.experiment_id == eid)
            ).scalar()
            d = json.loads(r or "{}")
            d[model] = version
            c.execute(update(experiments).where(experiments.c.experiment_id == eid)
                      .values(model_versions_json=json.dumps(d, sort_keys=True)))  # fmt: skip

    # -- origins and targets ----------------------------------------------------------
    def origin_hashes(self, eid: str) -> dict[tuple[str, str], tuple[str, str | None]]:
        with self.tx() as c:
            rows = c.execute(select(origins.c.asset, origins.c.origin_ts, origins.c.status, origins.c.input_hash)
                             .where(origins.c.experiment_id == eid)).all()  # fmt: skip
        return {(r.asset, r.origin_ts): (r.status, r.input_hash) for r in rows}

    def insert_origins(self, c: Connection, rows: list[dict]) -> None:
        if rows:
            c.execute(insert(origins), rows)

    def insert_targets(self, c: Connection, rows: list[dict]) -> None:
        if rows:
            c.execute(insert(targets), rows)

    def has_targets(self, eid: str, asset: str) -> bool:
        with self.tx() as c:
            return c.execute(select(targets.c.asset).where(targets.c.experiment_id == eid,
                                                           targets.c.asset == asset).limit(1)).first() is not None  # fmt: skip

    # -- model runs and forecasts -----------------------------------------------------
    def start_model_run(self, eid: str, spec, requested_device: str, code: str, now: datetime) -> int:
        with self.tx() as c:
            r = c.execute(insert(model_runs).values(
                experiment_id=eid, model_name=spec.name, family=spec.family,
                params_json=json.dumps(spec.params, sort_keys=True), code_version=code,
                requested_device=requested_device, status="running", started_at=to_iso(now),
                n_new_forecasts=0, n_failed=0,
            ))  # fmt: skip
            return int(r.inserted_primary_key[0])

    def finish_model_run(self, run_id: int, now: datetime, **values) -> None:
        with self.tx() as c:
            c.execute(
                update(model_runs).where(model_runs.c.id == run_id).values(finished_at=to_iso(now), **values)
            )

    def done_forecasts(self, eid: str, model: str) -> set[tuple[str, str]]:
        with self.tx() as c:
            rows = c.execute(select(forecasts.c.asset, forecasts.c.origin_ts)
                             .where(forecasts.c.experiment_id == eid, forecasts.c.model_name == model)).all()  # fmt: skip
        return {(r.asset, r.origin_ts) for r in rows}

    def insert_forecasts(self, rows: list[dict]) -> None:
        if rows:
            with self.tx() as c:
                c.execute(insert(forecasts), rows)

    def model_runs(self, eid: str) -> list[dict]:
        with self.tx() as c:
            rows = c.execute(select(model_runs).where(model_runs.c.experiment_id == eid)
                             .order_by(model_runs.c.id)).all()  # fmt: skip
        return [dict(r._mapping) for r in rows]
