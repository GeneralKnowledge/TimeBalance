"""Append-only store for decision-model experiments (``data/decisions.sqlite3``).

Separate from the market database and the M2 research database so nothing here can overwrite
existing results. Rows are only ever inserted: a rerun creates a new run id, an evaluation a new
evaluation id. Raw provider output and normalised answers are stored in separate columns.
No credentials are stored: runs record model and hardware facts only.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
create table if not exists pm_markets (
  condition_id text primary key, question text not null, description text, category text,
  opening_time text, scheduled_end text, closed_time text, resolved_at text, outcome text not null,
  yes_token_id text not null, fee_rate real, neg_risk integer, final_volume real,
  retrieved_at text not null, raw_json text
);
create table if not exists pm_history (
  condition_id text not null, ts text not null, price real not null, source_ts text,
  available_at text not null, retrieved_at text not null,
  primary key (condition_id, ts)
);
create table if not exists snapshots (
  snapshot_id text primary key, condition_id text not null, decision_ts text not null,
  lead_hours integer, schema text not null, reconstructed integer not null, snapshot_json text not null
);
create table if not exists runs (
  run_id text primary key, created_at text not null, finished_at text, status text not null,
  model_name text not null, provider text not null, checkpoint text not null, model_version text,
  library_version text, question_version text not null, question_hash text not null,
  questions_json text not null, state_template text not null, snapshot_schema text not null,
  config_json text not null, hardware_json text, benchmark_json text, code_version text
);
create table if not exists outputs (
  run_id text not null, snapshot_id text not null, request_id text not null,
  state_json text not null, raw_json text, normalised_json text not null,
  latency_ms real, device text, error text, created_at text not null,
  primary key (run_id, snapshot_id)
);
create table if not exists evaluations (
  eval_id text primary key, run_id text not null, created_at text not null,
  config_json text not null, results_json text not null, report_dir text
);
"""


class DecisionStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("pragma journal_mode=wal")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self.conn:
            yield self.conn

    # ------------------------------------------------------------------ dataset
    def has_market(self, cid: str) -> bool:
        return (
            self.conn.execute("select 1 from pm_markets where condition_id=?", (cid,)).fetchone() is not None
        )

    def insert_market(self, row: dict, history: Iterable[dict]) -> None:
        with self.tx() as c:
            c.execute(
                f"insert or ignore into pm_markets ({','.join(row)}) values ({','.join('?' * len(row))})",
                list(row.values()),
            )
            c.executemany(
                "insert or ignore into pm_history (condition_id, ts, price, source_ts, available_at, retrieved_at)"
                " values (:condition_id, :ts, :price, :source_ts, :available_at, :retrieved_at)",
                list(history),
            )

    def markets(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("select * from pm_markets order by scheduled_end")]

    def history(self, cid: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "select ts, price, available_at from pm_history where condition_id=? order by ts", (cid,))]  # fmt: skip

    def insert_snapshots(self, rows: list[dict]) -> None:
        with self.tx() as c:
            c.executemany(
                "insert or ignore into snapshots values (:snapshot_id, :condition_id, :decision_ts, :lead_hours,"
                " :schema, :reconstructed, :snapshot_json)",
                rows,
            )

    def snapshots(self) -> list[dict]:
        return [
            dict(r) for r in self.conn.execute("select * from snapshots order by decision_ts, condition_id")
        ]

    # ------------------------------------------------------------------ runs
    def create_run(self, row: dict) -> None:
        with self.tx() as c:
            c.execute(
                f"insert into runs ({','.join(row)}) values ({','.join('?' * len(row))})", list(row.values())
            )

    def update_run(self, run_id: str, **values) -> None:
        sets = ",".join(f"{k}=?" for k in values)
        with self.tx() as c:
            c.execute(f"update runs set {sets} where run_id=?", [*values.values(), run_id])

    def run(self, run_id: str) -> dict:
        r = self.conn.execute("select * from runs where run_id=?", (run_id,)).fetchone()
        if r is None:
            raise KeyError(f"unknown run {run_id}")
        return dict(r)

    def runs(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "select run_id, created_at, status, model_name, model_version, question_version from runs"
            " order by created_at")]  # fmt: skip

    def done_snapshots(self, run_id: str) -> set[str]:
        return {r[0] for r in self.conn.execute("select snapshot_id from outputs where run_id=?", (run_id,))}

    def insert_outputs(self, rows: list[dict]) -> None:
        with self.tx() as c:
            c.executemany(
                "insert into outputs values (:run_id, :snapshot_id, :request_id, :state_json, :raw_json,"
                " :normalised_json, :latency_ms, :device, :error, :created_at)",
                rows,
            )

    def outputs(self, run_id: str) -> list[dict]:
        rows = self.conn.execute(
            "select o.snapshot_id, o.normalised_json, o.latency_ms, o.error, s.condition_id, s.decision_ts,"
            " s.lead_hours, s.snapshot_json from outputs o join snapshots s using (snapshot_id)"
            " where o.run_id=? order by s.decision_ts", (run_id,))  # fmt: skip
        out = []
        for r in rows:
            d = dict(r)
            d["answers"] = json.loads(d.pop("normalised_json"))
            d["snapshot"] = json.loads(d.pop("snapshot_json"))
            out.append(d)
        return out

    def insert_evaluation(self, row: dict) -> None:
        with self.tx() as c:
            c.execute("insert into evaluations values (:eval_id, :run_id, :created_at, :config_json,"
                      " :results_json, :report_dir)", row)  # fmt: skip
