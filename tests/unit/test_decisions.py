"""Offline tests for the decision-model interface, Laya adapter, snapshots, store and evaluation."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from mpe.clock import FixedClock
from mpe.decisions.base import DecisionModel, DecisionModelError, DecisionQuestion, DecisionRequest
from mpe.decisions.dataset import history_points, make_snapshots
from mpe.decisions.evaluate import EvalConfig, evaluate, fit_logistic
from mpe.decisions.laya_model import LayaDecisionModel, from_laya_answer, to_laya_question
from mpe.decisions.report import write_report
from mpe.decisions.runner import run_decisions
from mpe.decisions.snapshot import LeakageError, PricePoint, build_snapshot, iso, render_state
from mpe.decisions.store import DecisionStore
from mpe.decisions.tasks import load_questions

T0 = datetime(2026, 6, 1, tzinfo=UTC)


class FakeAgent:
    """Mimics laya.Agent.predict_batch output (laya 0.4.22 answer shapes)."""

    revision = "fakesha"
    device = "cpu"

    def __init__(self, fail_every: int = 0):
        self.calls = 0
        self.fail_every = fail_every

    def predict_batch(self, states, questions, batch_size=None):
        self.calls += 1
        if self.fail_every and self.calls % self.fail_every == 0:
            raise RuntimeError("boom")
        out = []
        for s in states:
            yes = float(s["current YES price"].split("%")[0]) / 100
            ans = {}
            for qid, q in questions.items():
                if q["type"] == "choice":
                    keys = list(q["criteria"])
                    p = np.full(len(keys), 0.5 / max(len(keys) - 1, 1))
                    p[0] = 0.5
                    if qid == "resolves_yes":
                        p = np.array([0.5 * yes + 0.25, 0.75 - 0.5 * yes])
                    ans[qid] = {
                        "type": "choice",
                        "choice": keys[int(p.argmax())],
                        "probabilities": dict(zip(keys, p.tolist(), strict=True)),
                        "confidence": 0.3,
                        "answer_confidence": float(p.max()),
                        "action": {},
                    }
                elif q["type"] == "score":
                    k = len(q["criteria"])
                    ans[qid] = {
                        "type": "score",
                        "score": 2.0,
                        "probabilities": {str(i): 1 / k for i in range(k)},
                        "confidence": 0.1,
                        "answer_confidence": 0.2,
                        "action": {},
                    }
                else:
                    ans[qid] = {"type": "noul", "noul": 0.7, "confidence": 0.7, "answer_confidence": 0.7}
            out.append({"answers": ans})
        return out


def test_question_validation():
    with pytest.raises(ValueError):
        DecisionQuestion("q", "binary", "x?", ("a", "b", "c"), positive="a")
    with pytest.raises(ValueError):
        DecisionQuestion("q", "choice", "x?", ("a", "a"))


def test_task_file_loads_and_hashes():
    version, digest, qs = load_questions()
    assert version.startswith("pm-questions/")
    assert len(digest) == 12
    assert {q.id for q in qs} >= {
        "resolves_yes",
        "direction_6h",
        "direction_24h",
        "regime",
        "opportunity",
        "enough_information",
    }


def test_laya_mapping_roundtrip():
    q = DecisionQuestion("p", "binary", "Resolves YES?", ("yes", "no"), positive="yes")
    assert to_laya_question(q)["type"] == "choice"
    assert to_laya_question(q, "noul")["type"] == "noul"
    a = from_laya_answer(
        q, {"type": "choice", "probabilities": {"yes": 0.6, "no": 0.2}, "answer_confidence": 0.75}
    )
    assert a.positive_probability == pytest.approx(0.75)  # renormalised
    n = from_laya_answer(q, {"type": "noul", "noul": 0.3, "answer_confidence": 0.7}, "noul")
    assert n.positive_probability == pytest.approx(0.3)
    o = DecisionQuestion("o", "ordinal", "level?", ("lo", "mid", "hi"))
    oa = from_laya_answer(o, {"type": "score", "probabilities": {"0": 0.0, "1": 0.0, "2": 1.0}})
    assert oa.expected_level == pytest.approx(2.0) and oa.choice == "hi"
    with pytest.raises(DecisionModelError):
        from_laya_answer(q, {"type": "score", "probabilities": {}})


def test_abstain_rule():
    q = DecisionQuestion("p", "binary", "Resolves YES?", ("yes", "no"), positive="yes", abstain_below=0.8)
    a = from_laya_answer(
        q, {"type": "choice", "probabilities": {"yes": 0.6, "no": 0.4}, "answer_confidence": 0.6}
    )
    assert a.abstained and a.choice is None and a.positive_probability == pytest.approx(0.6)


def test_adapter_is_a_decision_model_and_records_errors():
    m = LayaDecisionModel(agent=FakeAgent(fail_every=2), batch_size=1)
    assert isinstance(m, DecisionModel)
    qs = [DecisionQuestion("resolves_yes", "binary", "Resolves YES?", ("yes", "no"), positive="yes")]
    reqs = [DecisionRequest(str(i), {"current YES price": "40.0%"}, qs, iso(T0), "x") for i in range(2)]
    res = m.decide_batch(reqs)
    assert res[0].ok and res[0].answers["resolves_yes"].positive_probability == pytest.approx(0.45)
    assert not res[1].ok and res[1].answers["resolves_yes"].abstained
    assert m.metadata().version == "fakesha"


def _hist(start: datetime, n: int, f) -> list[PricePoint]:
    return [
        PricePoint(start + timedelta(hours=i), f(i), start + timedelta(hours=i, seconds=60)) for i in range(n)
    ]


def test_snapshot_excludes_future_and_unknowns():
    hist = _hist(T0, 100, lambda i: 0.3 + 0.002 * i)
    t = T0 + timedelta(hours=50)
    snap = build_snapshot(
        {"condition_id": "c", "question": "Q?", "scheduled_end": iso(T0 + timedelta(hours=99))}, hist, t
    )
    assert snap["price"]["yes"] == pytest.approx(0.3 + 0.002 * 49)  # hour 50 not yet available (latency)
    assert snap["price"]["observations"] == 50
    assert snap["reconstructed"] is True
    assert "volume" in snap["unavailable"] and "news" in snap["unavailable"]
    assert "market question" in render_state(snap)
    bad = [PricePoint(T0, 0.5, T0 + timedelta(hours=1))]
    with pytest.raises(ValueError):
        build_snapshot({"condition_id": "c", "question": "Q?"}, bad, T0)
    assert LeakageError  # exported for callers


def _seed_store(store: DecisionStore, n_markets: int = 90) -> None:
    rng = np.random.default_rng(0)
    for k in range(n_markets):
        end = T0 + timedelta(days=k)
        start = end - timedelta(days=17)
        p_true = rng.uniform(0.1, 0.9)
        y = "YES" if rng.uniform() < p_true else "NO"
        hist = _hist(
            start, 17 * 24 + 1, lambda i, p=p_true: float(np.clip(p + 0.01 * np.sin(i / 7), 0.01, 0.99))
        )
        store.insert_market(
            {
                "condition_id": f"c{k}",
                "question": f"Market {k}?",
                "description": "rules",
                "category": "x",
                "opening_time": iso(start),
                "scheduled_end": iso(end),
                "closed_time": iso(end),
                "resolved_at": iso(end),
                "outcome": y,
                "yes_token_id": f"t{k}",
                "fee_rate": 0.0,
                "neg_risk": 0,
                "final_volume": 1e6,
                "retrieved_at": iso(end + timedelta(days=200)),
                "raw_json": "{}",
            },
            [
                {
                    "condition_id": f"c{k}",
                    "ts": iso(p.ts),
                    "price": p.price,
                    "source_ts": None,
                    "available_at": iso(p.available_at),
                    "retrieved_at": iso(end + timedelta(days=200)),
                }
                for p in hist
            ],
        )


def test_end_to_end_append_only(tmp_path):
    store = DecisionStore(tmp_path / "d.sqlite3")
    _seed_store(store)
    stats = make_snapshots(store, (168, 24, 6))
    assert stats["created"] == 90 * 3
    make_snapshots(store, (168, 24, 6))  # idempotent
    assert len(store.snapshots()) == 270
    clock = FixedClock(datetime(2026, 11, 3, tzinfo=UTC))
    run_id = run_decisions(store, LayaDecisionModel(agent=FakeAgent(), batch_size=16), clock)
    assert len(store.outputs(run_id)) == 270
    bench = json.loads(store.run(run_id)["benchmark_json"])
    assert bench["errors"] == 0 and bench["snapshots"] == 270
    # a second run never touches the first
    run2 = run_decisions(
        store,
        LayaDecisionModel(agent=FakeAgent(), batch_size=16),
        FixedClock(datetime(2026, 11, 4, tzinfo=UTC)),
        max_snapshots=10,
    )
    assert run2 != run_id and len(store.outputs(run_id)) == 270

    markets = {m["condition_id"]: m for m in store.markets()}
    hist = {c: history_points(store, c) for c in markets}
    res = evaluate(store.outputs(run_id), markets, hist, EvalConfig(min_train=30, bootstrap_samples=100))
    p = res["probability"].set_index("forecaster")
    assert {"market", "laya_raw", "laya_recal", "market_plus_laya", "market_recal", "base_rate"} <= set(
        p.index
    )
    assert p.loc["market", "brier_minus_market"] == 0
    assert not res["direction"].empty
    assert any(t["trades"] > 0 for t in res["trading"])
    out = write_report(
        store.run(run_id),
        res,
        "eval-1",
        {"half_spread": 0.01, "slippage": 0.005, "default_fee_rate": 0.0, "stake_usd": 10},
        root=tmp_path,
    )
    assert (out / "report.md").read_text().startswith("# Decision-model evaluation")
    with pytest.raises(FileExistsError):
        write_report(store.run(run_id), res, "eval-1", {}, root=tmp_path)


def test_walk_forward_uses_only_resolved_past():
    """A forecaster fitted walk-forward has no forecast before min_train markets have resolved."""
    import pandas as pd

    from mpe.decisions.evaluate import walk_forward

    n = 50
    df = pd.DataFrame(
        {
            "decision_ts": pd.date_range("2026-01-01", periods=n, freq="D", tz="UTC"),
            "resolved_at": pd.date_range("2026-01-03", periods=n, freq="D", tz="UTC"),
            "x": np.linspace(-1, 1, n),
            "y": np.tile([0.0, 1.0], n // 2),
        }
    )
    out = walk_forward(df, ["x"], EvalConfig(min_train=10))
    # point i sees markets resolved strictly before its decision: i - 2 of them
    assert np.isnan(out[:12]).all() and not np.isnan(out[12:]).any()


def test_logistic_recovers_signal():
    rng = np.random.default_rng(1)
    x = rng.normal(size=4000)
    y = (rng.uniform(size=4000) < 1 / (1 + np.exp(-(0.5 + 2 * x)))).astype(float)
    w = fit_logistic(x[:, None], y, ridge=0.0)
    assert w[0] == pytest.approx(0.5, abs=0.15) and w[1] == pytest.approx(2.0, abs=0.2)
