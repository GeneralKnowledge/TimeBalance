"""Optional M0 sanity check (report only, draw no conclusions): rolling one-step-ahead forecasts of
SPY daily log returns over the last 250 days of the fixture.

    uv run python scripts/m0_sanity.py [--device auto] [--models timestral-5m zero ...]

Metrics per model: MAE of the median, directional accuracy (sign of median vs sign of actual,
zero medians count as wrong), and mean pinball loss over the 21 quantile levels.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mpe.features.transforms import stock_log_returns
from mpe.fixtures import make_input, spy_daily
from mpe.models.registry import REGISTRY, ModelManager

N_TEST = 250


def pinball(q: np.ndarray, levels: tuple[float, ...], y: float) -> float:
    lv = np.asarray(levels)
    d = y - q
    return float(np.mean(np.maximum(lv * d, (lv - 1) * d)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="auto")
    ap.add_argument(
        "--models",
        nargs="+",
        default=["timestral-5m", "timestral-209m", "zero", "persistence"],
        choices=sorted(REGISTRY),
    )
    args = ap.parse_args()
    spy = spy_daily()
    r = stock_log_returns(spy).to_numpy()  # close, not adj_close
    ts = spy["timestamp"].iloc[1:].reset_index(drop=True)
    mgr = ModelManager(max_resident=1, device=args.device)
    print(
        f"SPY daily log returns, rolling 1-step, last {N_TEST} days "
        f"({ts.iloc[-N_TEST]:%Y-%m-%d} to {ts.iloc[-1]:%Y-%m-%d})"
    )
    print(f"{'model':16s} {'MAE':>9s} {'dir acc':>8s} {'pinball':>9s}")
    for name in args.models:
        m = mgr.get(name)
        errs, hits, pins = [], [], []
        for i in range(len(r) - N_TEST, len(r)):
            out = m.forecast(make_input(r[:i], ts[:i], 1))
            med, y = out.values[0, 0], r[i]
            errs.append(abs(med - y))
            hits.append(np.sign(med) == np.sign(y) and med != 0)
            pins.append(pinball(out.quantiles[0, 0], out.quantile_levels, y))
        print(f"{name:16s} {np.mean(errs):9.5f} {np.mean(hits):8.3f} {np.mean(pins):9.6f}")
        mgr.release(name)
    print("n = 250 daily points; no significance testing; not evidence either way.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
