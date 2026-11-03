# Experiment `stocks-d35cd4ace9ec`: CPU check: SPY, Timestral sizes on CPU

> **RECONSTRUCTED RESEARCH: inputs are backfilled data replayed under documented availability assumptions. This is not what the system genuinely knew at the time.**

Status: **completed**. Created 2026-11-03T12:17:00.500021Z at code version `c40b2067347ae1891da4bd953a1167f48248b13a+dirty`. This is forecasting research. It is not a trading signal and says nothing about profitability.

## Configuration

| field | value |
|---|---|
| domain | stocks |
| knowledge mode | reconstructed_history |
| source / interval | yfinance / 1d |
| calendar | XNYS |
| target | daily log return of `close` |
| price field | close |
| assets requested | 1 |
| origins | 2026-06-01 00:00 to 2026-09-29 00:00 UTC, every 1 sessions |
| cutoff | origin timestamp + 1800 s; extra replay latency 0 s |
| targets read as of | 2026-11-03 00:00 UTC |
| context | 512 points (min 480 valid, max 5% missing) |
| horizons | 1, 5, 20 trading sessions |
| quantile levels | 21 in [0.01, 0.99] |
| reference baseline | zero |
| seed / device requested | 0 / cpu |
| availability rule | daily bar: timestamp is the session close (XNYS calendar; 00:00 Europe/London for FX); available_at = close + availability.stock_close_delay_minutes / fx_close_delay_minutes |
| model versions | timestral-123m=5a147287addd, timestral-209m=9874d252ab0a, timestral-28m=49b26409ac87, timestral-5m=bdd20cfc15a3, zero=baselines-0.1 |

## Data and exclusions

- Assets prepared: 1; usable origins: 83; scored cases in the common sample: 249 per model.

## Leaderboard

Pooled over all scored cases (every case equal weight); `macro MAE` is the mean of per-asset MAEs. Relative columns are `1 - metric / metric(zero)`: positive is better than `zero`. `asset skill` is the same ratio computed within each asset and then averaged over assets, so high-volatility assets do not dominate it. CRPS_q is the quantile CRPS over levels [{min(cfg.quantile_levels)}, {max(cfg.quantile_levels)}] (no tail extrapolation). Directional accuracy excludes zero changes.

### h = 1 trading sessions

| model | n | assets | MAE | RMSE | mean err | pinball | CRPS_q | cov 90% | width 90% | dir acc | ΔMAE | ΔCRPS | macro MAE | asset skill MAE | asset skill CRPS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| timestral-5m | 83 | 1 | 0.0065 | 0.0083 | 0.0010 | 0.0022 | 0.0046 | 0.8554 | 0.0277 | 0.4458 | -0.4% | -0.2% | 0.0065 | -0.4% | -0.2% |
| timestral-28m | 83 | 1 | 0.0064 | 0.0082 | 0.0012 | 0.0022 | 0.0045 | 0.8554 | 0.0265 | 0.4458 | +0.5% | +0.9% | 0.0064 | +0.5% | +0.9% |
| timestral-123m | 83 | 1 | 0.0065 | 0.0082 | 0.0011 | 0.0022 | 0.0046 | 0.8916 | 0.0269 | 0.4458 | -0.6% | +0.1% | 0.0065 | -0.6% | +0.1% |
| timestral-209m | 83 | 1 | 0.0064 | 0.0082 | 0.0011 | 0.0022 | 0.0046 | 0.8795 | 0.0265 | 0.4458 | +0.5% | +0.2% | 0.0064 | +0.5% | +0.2% |
| zero | 83 | 1 | 0.0064 | 0.0082 | 0.0011 | 0.0022 | 0.0046 | 0.8675 | 0.0268 | 0.4458 | +0.0% | +0.0% | 0.0064 | +0.0% | +0.0% |

### h = 5 trading sessions

| model | n | assets | MAE | RMSE | mean err | pinball | CRPS_q | cov 90% | width 90% | dir acc | ΔMAE | ΔCRPS | macro MAE | asset skill MAE | asset skill CRPS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| timestral-5m | 83 | 1 | 0.0061 | 0.0077 | 5.791e-04 | 0.0021 | 0.0043 | 0.8916 | 0.0287 | 0.4578 | +0.5% | +0.3% | 0.0061 | +0.5% | +0.3% |
| timestral-28m | 83 | 1 | 0.0062 | 0.0077 | 6.181e-04 | 0.0021 | 0.0043 | 0.8916 | 0.0270 | 0.4578 | +0.0% | +0.4% | 0.0062 | +0.0% | +0.4% |
| timestral-123m | 83 | 1 | 0.0062 | 0.0077 | 5.425e-04 | 0.0021 | 0.0043 | 0.8916 | 0.0273 | 0.4578 | +0.4% | +0.3% | 0.0062 | +0.4% | +0.3% |
| timestral-209m | 83 | 1 | 0.0062 | 0.0076 | 6.079e-04 | 0.0021 | 0.0043 | 0.8916 | 0.0273 | 0.4578 | +0.1% | -0.0% | 0.0062 | +0.1% | -0.0% |
| zero | 83 | 1 | 0.0062 | 0.0077 | 5.886e-04 | 0.0021 | 0.0043 | 0.8795 | 0.0269 | 0.4578 | +0.0% | +0.0% | 0.0062 | +0.0% | +0.0% |

### h = 20 trading sessions

| model | n | assets | MAE | RMSE | mean err | pinball | CRPS_q | cov 90% | width 90% | dir acc | ΔMAE | ΔCRPS | macro MAE | asset skill MAE | asset skill CRPS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| timestral-5m | 83 | 1 | 0.0055 | 0.0068 | 7.395e-04 | 0.0019 | 0.0039 | 0.9639 | 0.0305 | 0.4578 | +0.4% | -0.8% | 0.0055 | +0.4% | -0.8% |
| timestral-28m | 83 | 1 | 0.0056 | 0.0068 | 7.802e-04 | 0.0019 | 0.0038 | 0.9398 | 0.0280 | 0.4578 | -0.1% | -0.4% | 0.0056 | -0.1% | -0.4% |
| timestral-123m | 83 | 1 | 0.0055 | 0.0068 | 7.596e-04 | 0.0019 | 0.0038 | 0.9518 | 0.0283 | 0.4578 | +0.5% | -0.2% | 0.0055 | +0.5% | -0.2% |
| timestral-209m | 83 | 1 | 0.0056 | 0.0068 | 8.062e-04 | 0.0019 | 0.0038 | 0.9518 | 0.0294 | 0.4578 | +0.1% | -0.2% | 0.0056 | +0.1% | -0.2% |
| zero | 83 | 1 | 0.0056 | 0.0068 | 7.701e-04 | 0.0018 | 0.0038 | 0.9398 | 0.0275 | 0.4578 | +0.0% | +0.0% | 0.0056 | +0.0% | +0.0% |

## Paired comparisons

Mean loss difference (model − comparator) over identical cases; negative is better. 95% CI from a moving-block bootstrap over origin dates (2000 resamples, block ≥ horizon/stride). `insufficient data` when there are fewer than 30 origin dates or fewer than 10 blocks. 24 comparisons are shown, so about 1 could exclude zero by chance alone. `DM p` is the Diebold-Mariano test (Newey-West variance, Harvey-Leybourne-Newbold correction) on the per-date mean differential; `Holm p` adjusts it for every comparison in this table.

| h | loss | model | vs | comparator | mean diff | 95% CI | rel. improvement | pairs | assets | dates | DM p | Holm p | conclusion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | mae | timestral-5m | zero | reference | 2.871e-05 | [-5.079e-05, 1.107e-04] | -0.4% | 83 | 1 | 83 | 0.5844 | 1 | no demonstrated difference |
| 1 | mae | timestral-28m | zero | reference | -3.488e-05 | [-9.959e-05, 2.536e-05] | +0.5% | 83 | 1 | 83 | 0.3756 | 1 | no demonstrated difference |
| 1 | mae | timestral-123m | zero | reference | 3.554e-05 | [-3.319e-05, 1.066e-04] | -0.6% | 83 | 1 | 83 | 0.4384 | 1 | no demonstrated difference |
| 1 | mae | timestral-209m | zero | reference | -3.133e-05 | [-9.684e-05, 1.703e-05] | +0.5% | 83 | 1 | 83 | 0.2842 | 1 | no demonstrated difference |
| 1 | crps | timestral-5m | zero | reference | 8.827e-06 | [-6.649e-05, 8.128e-05] | -0.2% | 83 | 1 | 83 | 0.8452 | 1 | no demonstrated difference |
| 1 | crps | timestral-28m | zero | reference | -3.975e-05 | [-9.356e-05, 1.629e-05] | +0.9% | 83 | 1 | 83 | 0.3022 | 1 | no demonstrated difference |
| 1 | crps | timestral-123m | zero | reference | -3.405e-06 | [-6.284e-05, 6.243e-05] | +0.1% | 83 | 1 | 83 | 0.9297 | 1 | no demonstrated difference |
| 1 | crps | timestral-209m | zero | reference | -1.123e-05 | [-8.167e-05, 5.490e-05] | +0.2% | 83 | 1 | 83 | 0.7786 | 1 | no demonstrated difference |
| 5 | mae | timestral-5m | zero | reference | -3.293e-05 | [-7.222e-05, 2.492e-05] | +0.5% | 83 | 1 | 83 | 0.2537 | 1 | no demonstrated difference |
| 5 | mae | timestral-28m | zero | reference | -1.009e-06 | [-3.404e-05, 4.134e-05] | +0.0% | 83 | 1 | 83 | 0.9625 | 1 | no demonstrated difference |
| 5 | mae | timestral-123m | zero | reference | -2.496e-05 | [-5.028e-05, 1.118e-05] | +0.4% | 83 | 1 | 83 | 0.1692 | 1 | no demonstrated difference |
| 5 | mae | timestral-209m | zero | reference | -9.236e-06 | [-4.176e-05, 3.897e-05] | +0.1% | 83 | 1 | 83 | 0.7060 | 1 | no demonstrated difference |
| 5 | crps | timestral-5m | zero | reference | -1.202e-05 | [-6.554e-05, 3.985e-05] | +0.3% | 83 | 1 | 83 | 0.6571 | 1 | no demonstrated difference |
| 5 | crps | timestral-28m | zero | reference | -1.690e-05 | [-5.080e-05, 1.696e-05] | +0.4% | 83 | 1 | 83 | 0.3315 | 1 | no demonstrated difference |
| 5 | crps | timestral-123m | zero | reference | -1.224e-05 | [-5.379e-05, 3.082e-05] | +0.3% | 83 | 1 | 83 | 0.5627 | 1 | no demonstrated difference |
| 5 | crps | timestral-209m | zero | reference | 1.499e-06 | [-3.725e-05, 4.613e-05] | -0.0% | 83 | 1 | 83 | 0.9442 | 1 | no demonstrated difference |
| 20 | mae | timestral-5m | zero | reference | -2.462e-05 | [–, –] | +0.4% | 83 | 1 | 83 | – | – | insufficient data |
| 20 | mae | timestral-28m | zero | reference | 5.367e-06 | [–, –] | -0.1% | 83 | 1 | 83 | – | – | insufficient data |
| 20 | mae | timestral-123m | zero | reference | -2.544e-05 | [–, –] | +0.5% | 83 | 1 | 83 | – | – | insufficient data |
| 20 | mae | timestral-209m | zero | reference | -3.865e-06 | [–, –] | +0.1% | 83 | 1 | 83 | – | – | insufficient data |
| 20 | crps | timestral-5m | zero | reference | 2.986e-05 | [–, –] | -0.8% | 83 | 1 | 83 | – | – | insufficient data |
| 20 | crps | timestral-28m | zero | reference | 1.520e-05 | [–, –] | -0.4% | 83 | 1 | 83 | – | – | insufficient data |
| 20 | crps | timestral-123m | zero | reference | 6.971e-06 | [–, –] | -0.2% | 83 | 1 | 83 | – | – | insufficient data |
| 20 | crps | timestral-209m | zero | reference | 7.825e-06 | [–, –] | -0.2% | 83 | 1 | 83 | – | – | insufficient data |

## Per-asset results (CRPS_q vs zero)

Counts of assets by conclusion, then the detail.

| h | model | better | worse | no demonstrated difference | insufficient data |
|---|---|---|---|---|---|
| 1 | timestral-123m | 0 | 0 | 1 | 0 |
| 1 | timestral-209m | 0 | 0 | 1 | 0 |
| 1 | timestral-28m | 0 | 0 | 1 | 0 |
| 1 | timestral-5m | 0 | 0 | 1 | 0 |
| 5 | timestral-123m | 0 | 0 | 1 | 0 |
| 5 | timestral-209m | 0 | 0 | 1 | 0 |
| 5 | timestral-28m | 0 | 0 | 1 | 0 |
| 5 | timestral-5m | 0 | 0 | 1 | 0 |
| 20 | timestral-123m | 0 | 0 | 0 | 1 |
| 20 | timestral-209m | 0 | 0 | 0 | 1 |
| 20 | timestral-28m | 0 | 0 | 0 | 1 |
| 20 | timestral-5m | 0 | 0 | 0 | 1 |

<details><summary>Per-asset detail</summary>

| asset | label | h | model | n | rel. improvement | CI low | CI high | conclusion |
|---|---|---|---|---|---|---|---|---|
| SPY | SPY | 1 | timestral-5m | 83 | -0.2% | -6.649e-05 | 8.128e-05 | no demonstrated difference |
| SPY | SPY | 1 | timestral-28m | 83 | +0.9% | -9.356e-05 | 1.629e-05 | no demonstrated difference |
| SPY | SPY | 1 | timestral-123m | 83 | +0.1% | -6.284e-05 | 6.243e-05 | no demonstrated difference |
| SPY | SPY | 1 | timestral-209m | 83 | +0.2% | -8.167e-05 | 5.490e-05 | no demonstrated difference |
| SPY | SPY | 5 | timestral-5m | 83 | +0.3% | -6.554e-05 | 3.985e-05 | no demonstrated difference |
| SPY | SPY | 5 | timestral-28m | 83 | +0.4% | -5.080e-05 | 1.696e-05 | no demonstrated difference |
| SPY | SPY | 5 | timestral-123m | 83 | +0.3% | -5.379e-05 | 3.082e-05 | no demonstrated difference |
| SPY | SPY | 5 | timestral-209m | 83 | -0.0% | -3.725e-05 | 4.613e-05 | no demonstrated difference |
| SPY | SPY | 20 | timestral-5m | 83 | -0.8% | – | – | insufficient data |
| SPY | SPY | 20 | timestral-28m | 83 | -0.4% | – | – | insufficient data |
| SPY | SPY | 20 | timestral-123m | 83 | -0.2% | – | – | insufficient data |
| SPY | SPY | 20 | timestral-209m | 83 | -0.2% | – | – | insufficient data |

</details>

## Calibration

Empirical coverage of central prediction intervals (nominal in the header) and the quantile calibration error (mean |share of outcomes ≤ q_τ − τ| over all levels), the PIT total-variation distance (0 = outcomes fall in each quantile bin as often as its width predicts) and the interval (Winkler) score of the 90% interval, which charges width and misses together. Coverage is only meaningful with a large n; a narrow interval is good only if its coverage holds.

| h | model | n | cov 50% | width 50% | cov 80% | width 80% | cov 90% | width 90% | cov 98% | width 98% | QCE | PIT TV | IS 90% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | timestral-123m | 83 | 0.4699 | 0.0100 | 0.7952 | 0.0202 | 0.8916 | 0.0269 | 0.9880 | 0.0437 | 0.0508 | 0.1886 | 0.0347 |
| 1 | timestral-209m | 83 | 0.4458 | 0.0095 | 0.7711 | 0.0196 | 0.8795 | 0.0265 | 0.9880 | 0.0444 | 0.0493 | 0.1904 | 0.0346 |
| 1 | timestral-28m | 83 | 0.4578 | 0.0098 | 0.7952 | 0.0197 | 0.8554 | 0.0265 | 0.9880 | 0.0438 | 0.0500 | 0.2070 | 0.0351 |
| 1 | timestral-5m | 83 | 0.4578 | 0.0102 | 0.8072 | 0.0206 | 0.8554 | 0.0277 | 0.9880 | 0.0451 | 0.0477 | 0.2245 | 0.0352 |
| 1 | zero | 83 | 0.4578 | 0.0089 | 0.8072 | 0.0190 | 0.8675 | 0.0268 | 0.9880 | 0.0374 | 0.0501 | 0.1940 | 0.0383 |
| 5 | timestral-123m | 83 | 0.4578 | 0.0097 | 0.8193 | 0.0200 | 0.8916 | 0.0273 | 1 | 0.0462 | 0.0379 | 0.2124 | 0.0337 |
| 5 | timestral-209m | 83 | 0.4337 | 0.0095 | 0.8072 | 0.0198 | 0.8916 | 0.0273 | 1 | 0.0471 | 0.0371 | 0.1986 | 0.0335 |
| 5 | timestral-28m | 83 | 0.4699 | 0.0097 | 0.8193 | 0.0197 | 0.8916 | 0.0270 | 1 | 0.0468 | 0.0385 | 0.2190 | 0.0336 |
| 5 | timestral-5m | 83 | 0.4699 | 0.0102 | 0.8193 | 0.0210 | 0.8916 | 0.0287 | 1 | 0.0481 | 0.0389 | 0.2383 | 0.0342 |
| 5 | zero | 83 | 0.4458 | 0.0089 | 0.8193 | 0.0191 | 0.8795 | 0.0269 | 0.9880 | 0.0376 | 0.0395 | 0.1922 | 0.0356 |
| 20 | timestral-123m | 83 | 0.4819 | 0.0098 | 0.8795 | 0.0203 | 0.9518 | 0.0283 | 1 | 0.0510 | 0.0425 | 0.2042 | 0.0305 |
| 20 | timestral-209m | 83 | 0.4940 | 0.0096 | 0.8795 | 0.0208 | 0.9518 | 0.0294 | 1 | 0.0521 | 0.0420 | 0.2006 | 0.0305 |
| 20 | timestral-28m | 83 | 0.4819 | 0.0096 | 0.8795 | 0.0200 | 0.9398 | 0.0280 | 1 | 0.0521 | 0.0391 | 0.1865 | 0.0304 |
| 20 | timestral-5m | 83 | 0.5301 | 0.0104 | 0.8795 | 0.0218 | 0.9639 | 0.0305 | 1 | 0.0554 | 0.0443 | 0.2006 | 0.0316 |
| 20 | zero | 83 | 0.4819 | 0.0091 | 0.8554 | 0.0197 | 0.9398 | 0.0275 | 1 | 0.0380 | 0.0373 | 0.1986 | 0.0304 |

## Performance over time

CRPS_q improvement over `zero` per year of origin (positive = better). A model that only wins in one period has not shown a stable advantage.


**h = 1**

| period | n | timestral-5m | timestral-28m | timestral-123m | timestral-209m |
|---|---|---|---|---|---|
| 2026 | 83 | -0.2% | +0.9% | +0.1% | +0.2% |

**h = 5**

| period | n | timestral-5m | timestral-28m | timestral-123m | timestral-209m |
|---|---|---|---|---|---|
| 2026 | 83 | +0.3% | +0.4% | +0.3% | -0.0% |

**h = 20**

| period | n | timestral-5m | timestral-28m | timestral-123m | timestral-209m |
|---|---|---|---|---|---|
| 2026 | 83 | -0.8% | -0.4% | -0.2% | -0.2% |

## Model runs

| run | model | version | device | status | forecasts | failed | ms/forecast | wall s | peak RSS MB | peak VRAM MB | code |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | timestral-5m | bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f | cpu | completed | 83 | 0 | 15.66 | 3.152 | 615.2 | – | c40b2067347ae1891da4bd953a1167f48248b13a+dirty |
| 3 | timestral-28m | 49b26409ac87b5935539a5d8ffe7f397b720db47 | cpu | completed | 83 | 0 | 35.44 | 3.421 | 702.2 | – | c40b2067347ae1891da4bd953a1167f48248b13a+dirty |
| 4 | timestral-123m | 5a147287addda85f6acd8da3fb8858fe9af7e8f7 | cpu | completed | 83 | 0 | 106.5 | 10.21 | 1065 | – | c40b2067347ae1891da4bd953a1167f48248b13a+dirty |
| 5 | timestral-209m | 9874d252ab0aae16f7f7c999f98f98d6ad7d8365 | cpu | completed | 83 | 0 | 170.5 | 16.49 | 1396 | – | c40b2067347ae1891da4bd953a1167f48248b13a+dirty |
| 6 | zero | baselines-0.1 | cpu | completed | 83 | 0 | 4.278 | 0.4675 | 596.2 | – | c40b2067347ae1891da4bd953a1167f48248b13a+dirty |

## Figures

- [calibration_h1.svg](calibration_h1.svg)
- [pit_h1.svg](pit_h1.svg)
- [over_time_h1.svg](over_time_h1.svg)
- [calibration_h5.svg](calibration_h5.svg)
- [pit_h5.svg](pit_h5.svg)
- [over_time_h5.svg](over_time_h5.svg)
- [calibration_h20.svg](calibration_h20.svg)
- [pit_h20.svg](pit_h20.svg)
- [over_time_h20.svg](over_time_h20.svg)

## Reading these results

- `better` / `worse` mean the 95% interval of the paired loss difference excludes zero. `no demonstrated difference` means it does not: the model has not shown an advantage (this is not proof of equality). `insufficient data` means the sample is too small to tell.
- Directional accuracy is not profitability, and no result here accounts for costs.
- See docs/M2_RESEARCH_METHODOLOGY.md and docs/KNOWN_LIMITATIONS.md.
