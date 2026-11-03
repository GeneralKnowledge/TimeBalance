"""M0 working demonstration: every model forecasts SPY log returns and a Polymarket logit YES price.

    uv run python scripts/m0_demo.py [--device cpu|cuda|auto] [--models timestral-5m persistence ...]

SPY: target = daily log return of adj_close; h = 1, 5, 20 trading days. Implied price = last close
times exp(cumulative median returns), i.e. the median-path price.
Polymarket: target = logit(YES price), eps 1e-4; h = 1, 6, 24 hours; context ends 2024-11-05 00:00Z
(before the result was known). Implied value = inverse-logit of the step-h quantiles.
Shown per row: the step-h median, q0.1 and q0.9.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mpe.features.transforms import inv_logit, log_returns, logit, reconstruct_prices
from mpe.fixtures import make_input, pm_yes_hourly, spy_daily
from mpe.models.base import validate_output
from mpe.models.registry import REGISTRY, ModelManager

DEFAULT_MODELS = [
    "timestral-5m", "timestral-28m", "timestral-123m", "timestral-209m",
    "zero", "persistence", "moving_average", "momentum", "linear_trend",
]  # fmt: skip


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="auto")
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS, choices=sorted(REGISTRY))
    args = ap.parse_args()

    spy = spy_daily()
    r = log_returns(spy["adj_close"].to_numpy())
    r_ts = spy["timestamp"].iloc[1:]
    last_price = float(spy["adj_close"].iloc[-1])

    pm = pm_yes_hourly()
    pm = pm[pm["timestamp"] < pd.Timestamp("2024-11-05T00:00:00Z")]
    z = logit(pm["yes_price"].to_numpy())

    mgr = ModelManager(max_resident=1, device=args.device)
    rows = []
    for name in args.models:
        model = mgr.get(name)
        for target, values, ts, horizons in (
            ("SPY log_return", r, r_ts, (1, 5, 20)),
            ("PM logit_yes", z, pm["timestamp"], (1, 6, 24)),
        ):
            for h in horizons:
                step = pd.Timedelta(days=1) if target.startswith("SPY") else pd.Timedelta(hours=1)
                inp = make_input(values, ts, h, names=(target,), step=step, quantile_levels=(0.1, 0.5, 0.9))
                out = model.forecast(inp)
                validate_output(out, 1, h)
                med, lo, hi = out.values[0, -1], out.quantile(0.1)[0, -1], out.quantile(0.9)[0, -1]
                if target.startswith("SPY"):
                    implied = f"{reconstruct_prices(last_price, out.values[0])[-1]:.2f} (price)"
                else:
                    p = inv_logit(np.array([lo, med, hi]))
                    assert ((p > 0) & (p < 1)).all()
                    implied = f"{p[1]:.4f} [{p[0]:.4f}, {p[2]:.4f}] (P)"
                rows.append({
                    "model": name, "target": target, "h": h,
                    "median": f"{med:+.5f}", "q0.1": f"{lo:+.5f}", "q0.9": f"{hi:+.5f}",
                    "implied": implied, "ms": f"{out.inference_ms:.1f}", "device": out.device,
                })  # fmt: skip
        mgr.release(name)
    mgr.release_all()

    df = pd.DataFrame(rows)
    with pd.option_context("display.max_rows", None, "display.width", 200):
        print(df.to_string(index=False))
    print(
        f"\nSPY context: {len(r)} daily returns to {r_ts.iloc[-1]:%Y-%m-%d}, last adj close {last_price:.2f}"
    )
    print(
        f"PM context: {len(z)} hourly logits to {pm['timestamp'].iloc[-1]:%Y-%m-%d %H:%M}Z, "
        f"last YES price {pm['yes_price'].iloc[-1]:.4f}"
    )
    print("All outputs validated: shapes, finite values, non-decreasing quantiles, probabilities in (0, 1).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
