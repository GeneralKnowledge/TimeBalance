# Experiment `stocks-4daa0990200b`: stocks reconstructed 2012-2026 daily origins

> **RECONSTRUCTED RESEARCH: inputs are backfilled data replayed under documented availability assumptions. This is not what the system genuinely knew at the time.**

Status: **completed**. Created 2026-11-03T11:55:26.089906Z at code version `d3632d2c43f229eae54253a686269a14c8ecf43e`. This is forecasting research. It is not a trading signal and says nothing about profitability.

## Configuration

| field | value |
|---|---|
| domain | stocks |
| knowledge mode | reconstructed_history |
| source / interval | yfinance / 1d |
| calendar | XNYS |
| target | daily log return of `close` |
| price field | close |
| assets requested | 10 |
| origins | 2012-03-01 00:00 to 2026-09-29 00:00 UTC, every 1 sessions |
| cutoff | origin timestamp + 1800 s; extra replay latency 0 s |
| targets read as of | 2026-11-03 00:00 UTC |
| context | 512 points (min 480 valid, max 5% missing) |
| horizons | 1, 5, 20 trading sessions |
| quantile levels | 21 in [0.01, 0.99] |
| reference baseline | zero |
| seed / device requested | 0 / auto |
| availability rule | daily bar: timestamp is the session close (XNYS calendar; 00:00 Europe/London for FX); available_at = close + availability.stock_close_delay_minutes / fx_close_delay_minutes |
| model versions | linear_trend=baselines-0.1, momentum=baselines-0.1, moving_average=baselines-0.1, persistence=baselines-0.1, timestral-123m=5a147287addd, timestral-209m=9874d252ab0a, timestral-28m=49b26409ac87, timestral-5m=bdd20cfc15a3, zero=baselines-0.1 |

## Data and exclusions

- Assets prepared: 10; usable origins: 36,650; scored cases in the common sample: 109,950 per model.

## Leaderboard

Pooled over all scored cases (every case equal weight); `macro MAE` is the mean of per-asset MAEs. Relative columns are `1 - metric / metric(zero)`: positive is better than `zero`. `asset skill` is the same ratio computed within each asset and then averaged over assets, so high-volatility assets do not dominate it. CRPS_q is the quantile CRPS over levels [{min(cfg.quantile_levels)}, {max(cfg.quantile_levels)}] (no tail extrapolation). Directional accuracy excludes zero changes.

### h = 1 trading sessions

| model | n | assets | MAE | RMSE | mean err | pinball | CRPS_q | cov 90% | width 90% | dir acc | ΔMAE | ΔCRPS | macro MAE | asset skill MAE | asset skill CRPS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| timestral-5m | 36,650 | 10 | 0.0153 | 0.0297 | -3.432e-04 | 0.0054 | 0.0111 | 0.8951 | 0.0637 | 0.5211 | -0.4% | +0.9% | 0.0153 | -0.5% | +0.9% |
| timestral-28m | 36,650 | 10 | 0.0152 | 0.0295 | -3.311e-04 | 0.0053 | 0.0111 | 0.9011 | 0.0649 | 0.5217 | -0.1% | +1.2% | 0.0152 | -0.2% | +1.3% |
| timestral-123m | 36,650 | 10 | 0.0152 | 0.0294 | -3.175e-04 | 0.0053 | 0.0110 | 0.8996 | 0.0641 | 0.5211 | -0.1% | +1.4% | 0.0152 | -0.3% | +1.5% |
| timestral-209m | 36,650 | 10 | 0.0152 | 0.0294 | -3.689e-04 | 0.0053 | 0.0110 | 0.8949 | 0.0635 | 0.5266 | +0.2% | +1.7% | 0.0152 | -0.0% | +1.7% |
| zero | 36,650 | 10 | 0.0152 | 0.0294 | -4.703e-04 | 0.0054 | 0.0112 | 0.8925 | 0.0650 | 0.5299 | +0.0% | +0.0% | 0.0152 | +0.0% | +0.0% |
| persistence | 36,650 | 10 | 0.0223 | 0.0429 | 1.717e-04 | 0.0079 | 0.0164 | 0.8921 | 0.0941 | 0.4867 | -47.0% | -46.1% | 0.0223 | -46.4% | -45.4% |
| moving_average | 36,650 | 10 | 0.0157 | 0.0301 | -4.678e-04 | 0.0056 | 0.0116 | 0.8941 | 0.0669 | 0.4997 | -3.4% | -3.2% | 0.0157 | -3.2% | -3.0% |
| momentum | 36,650 | 10 | 0.0229 | 0.0440 | 1.986e-04 | 0.0081 | 0.0168 | 0.8920 | 0.0965 | 0.4870 | -50.8% | -50.0% | 0.0229 | -50.2% | -49.2% |
| linear_trend | 36,650 | 10 | 0.0159 | 0.0304 | -5.239e-04 | 0.0056 | 0.0117 | 0.8931 | 0.0675 | 0.4973 | -4.5% | -4.3% | 0.0159 | -4.4% | -4.0% |

### h = 5 trading sessions

| model | n | assets | MAE | RMSE | mean err | pinball | CRPS_q | cov 90% | width 90% | dir acc | ΔMAE | ΔCRPS | macro MAE | asset skill MAE | asset skill CRPS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| timestral-5m | 36,650 | 10 | 0.0152 | 0.0295 | -2.980e-04 | 0.0054 | 0.0111 | 0.8962 | 0.0650 | 0.5282 | -0.2% | +0.5% | 0.0152 | -0.2% | +0.8% |
| timestral-28m | 36,650 | 10 | 0.0152 | 0.0293 | -2.989e-04 | 0.0054 | 0.0111 | 0.9005 | 0.0658 | 0.5288 | -0.0% | +0.7% | 0.0152 | -0.0% | +1.0% |
| timestral-123m | 36,650 | 10 | 0.0152 | 0.0293 | -2.369e-04 | 0.0054 | 0.0111 | 0.8979 | 0.0650 | 0.5296 | +0.1% | +0.9% | 0.0152 | +0.0% | +1.1% |
| timestral-209m | 36,650 | 10 | 0.0152 | 0.0293 | -2.735e-04 | 0.0054 | 0.0111 | 0.8972 | 0.0650 | 0.5312 | +0.1% | +0.9% | 0.0152 | +0.1% | +1.2% |
| zero | 36,650 | 10 | 0.0152 | 0.0294 | -4.735e-04 | 0.0054 | 0.0112 | 0.8921 | 0.0650 | 0.5309 | +0.0% | +0.0% | 0.0152 | +0.0% | +0.0% |
| persistence | 36,650 | 10 | 0.0221 | 0.0416 | 2.426e-04 | 0.0078 | 0.0162 | 0.8930 | 0.0940 | 0.4998 | -45.7% | -44.5% | 0.0221 | -44.8% | -43.7% |
| moving_average | 36,650 | 10 | 0.0156 | 0.0299 | -4.437e-04 | 0.0056 | 0.0115 | 0.8926 | 0.0666 | 0.5052 | -3.0% | -2.8% | 0.0156 | -3.0% | -2.7% |
| momentum | 36,650 | 10 | 0.0253 | 0.0475 | 3.232e-04 | 0.0089 | 0.0185 | 0.8928 | 0.1078 | 0.5012 | -66.7% | -65.2% | 0.0253 | -65.6% | -64.3% |
| linear_trend | 36,650 | 10 | 0.0159 | 0.0304 | -4.596e-04 | 0.0056 | 0.0117 | 0.8920 | 0.0675 | 0.4986 | -4.9% | -4.5% | 0.0159 | -4.9% | -4.4% |

### h = 20 trading sessions

| model | n | assets | MAE | RMSE | mean err | pinball | CRPS_q | cov 90% | width 90% | dir acc | ΔMAE | ΔCRPS | macro MAE | asset skill MAE | asset skill CRPS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| timestral-5m | 36,650 | 10 | 0.0152 | 0.0294 | -2.704e-04 | 0.0054 | 0.0112 | 0.9024 | 0.0679 | 0.5287 | -0.0% | +0.2% | 0.0152 | -0.1% | +0.3% |
| timestral-28m | 36,650 | 10 | 0.0152 | 0.0293 | -2.655e-04 | 0.0054 | 0.0112 | 0.9010 | 0.0670 | 0.5291 | +0.1% | +0.4% | 0.0152 | +0.0% | +0.4% |
| timestral-123m | 36,650 | 10 | 0.0152 | 0.0293 | -2.074e-04 | 0.0054 | 0.0112 | 0.8979 | 0.0661 | 0.5301 | +0.1% | +0.4% | 0.0152 | +0.0% | +0.5% |
| timestral-209m | 36,650 | 10 | 0.0152 | 0.0293 | -2.380e-04 | 0.0054 | 0.0112 | 0.9017 | 0.0671 | 0.5306 | +0.1% | +0.5% | 0.0152 | +0.0% | +0.6% |
| zero | 36,650 | 10 | 0.0152 | 0.0294 | -4.716e-04 | 0.0054 | 0.0112 | 0.8893 | 0.0649 | 0.5305 | +0.0% | +0.0% | 0.0152 | +0.0% | +0.0% |
| persistence | 36,650 | 10 | 0.0222 | 0.0414 | 1.251e-04 | 0.0078 | 0.0162 | 0.8889 | 0.0935 | 0.5099 | -45.7% | -44.3% | 0.0222 | -44.8% | -43.6% |
| moving_average | 36,650 | 10 | 0.0156 | 0.0300 | -4.856e-04 | 0.0056 | 0.0115 | 0.8889 | 0.0665 | 0.5103 | -2.9% | -2.6% | 0.0156 | -2.9% | -2.7% |
| momentum | 36,650 | 10 | 0.0386 | 0.0718 | 3.702e-04 | 0.0136 | 0.0281 | 0.8891 | 0.1632 | 0.5074 | -153.7% | -150.6% | 0.0386 | -151.7% | -149.1% |
| linear_trend | 36,650 | 10 | 0.0165 | 0.0310 | -5.292e-04 | 0.0058 | 0.0121 | 0.8883 | 0.0692 | 0.5079 | -8.2% | -7.5% | 0.0165 | -8.5% | -8.0% |

## Paired comparisons

Mean loss difference (model − comparator) over identical cases; negative is better. 95% CI from a moving-block bootstrap over origin dates (2000 resamples, block ≥ horizon/stride). `insufficient data` when there are fewer than 30 origin dates or fewer than 10 blocks. 24 comparisons are shown, so about 1 could exclude zero by chance alone. `DM p` is the Diebold-Mariano test (Newey-West variance, Harvey-Leybourne-Newbold correction) on the per-date mean differential; `Holm p` adjusts it for every comparison in this table.

| h | loss | model | vs | comparator | mean diff | 95% CI | rel. improvement | pairs | assets | dates | DM p | Holm p | conclusion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | mae | timestral-5m | zero | reference | 5.323e-05 | [1.034e-05, 1.059e-04] | -0.4% | 36,650 | 10 | 3,665 | 0.0346 | 0.4152 | worse |
| 1 | mae | timestral-28m | zero | reference | 1.735e-05 | [-1.777e-05, 5.420e-05] | -0.1% | 36,650 | 10 | 3,665 | 0.3298 | 0.9893 | no demonstrated difference |
| 1 | mae | timestral-123m | zero | reference | 1.943e-05 | [-2.266e-06, 4.217e-05] | -0.1% | 36,650 | 10 | 3,665 | 0.1358 | 0.8145 | no demonstrated difference |
| 1 | mae | timestral-209m | zero | reference | -2.529e-05 | [-4.923e-05, -1.916e-07] | +0.2% | 36,650 | 10 | 3,665 | 0.0613 | 0.6446 | better |
| 1 | crps | timestral-5m | zero | reference | -9.816e-05 | [-1.591e-04, -5.147e-05] | +0.9% | 36,650 | 10 | 3,665 | 4.812e-06 | 8.662e-05 | better |
| 1 | crps | timestral-28m | zero | reference | -1.389e-04 | [-2.221e-04, -8.502e-05] | +1.2% | 36,650 | 10 | 3,665 | 1.027e-13 | 2.260e-12 | better |
| 1 | crps | timestral-123m | zero | reference | -1.607e-04 | [-2.374e-04, -1.081e-04] | +1.4% | 36,650 | 10 | 3,665 | 6.001e-21 | 1.380e-19 | better |
| 1 | crps | timestral-209m | zero | reference | -1.886e-04 | [-2.741e-04, -1.321e-04] | +1.7% | 36,650 | 10 | 3,665 | 1.589e-23 | 3.813e-22 | better |
| 5 | mae | timestral-5m | zero | reference | 2.844e-05 | [-5.928e-06, 7.013e-05] | -0.2% | 36,650 | 10 | 3,665 | 0.1120 | 0.7956 | no demonstrated difference |
| 5 | mae | timestral-28m | zero | reference | 4.556e-07 | [-1.464e-05, 1.567e-05] | -0.0% | 36,650 | 10 | 3,665 | 0.9545 | 1 | no demonstrated difference |
| 5 | mae | timestral-123m | zero | reference | -1.167e-05 | [-2.448e-05, 1.560e-06] | +0.1% | 36,650 | 10 | 3,665 | 0.0995 | 0.7956 | no demonstrated difference |
| 5 | mae | timestral-209m | zero | reference | -1.883e-05 | [-3.243e-05, -5.924e-06] | +0.1% | 36,650 | 10 | 3,665 | 0.0083 | 0.1078 | better |
| 5 | crps | timestral-5m | zero | reference | -5.933e-05 | [-1.093e-04, -1.603e-05] | +0.5% | 36,650 | 10 | 3,665 | 7.493e-04 | 0.0105 | better |
| 5 | crps | timestral-28m | zero | reference | -8.039e-05 | [-1.303e-04, -4.331e-05] | +0.7% | 36,650 | 10 | 3,665 | 6.043e-07 | 1.148e-05 | better |
| 5 | crps | timestral-123m | zero | reference | -1.008e-04 | [-1.528e-04, -6.138e-05] | +0.9% | 36,650 | 10 | 3,665 | 3.401e-09 | 6.801e-08 | better |
| 5 | crps | timestral-209m | zero | reference | -1.047e-04 | [-1.584e-04, -6.505e-05] | +0.9% | 36,650 | 10 | 3,665 | 1.886e-09 | 3.960e-08 | better |
| 20 | mae | timestral-5m | zero | reference | 3.507e-06 | [-1.915e-05, 3.321e-05] | -0.0% | 36,650 | 10 | 3,665 | 0.7934 | 1 | no demonstrated difference |
| 20 | mae | timestral-28m | zero | reference | -8.632e-06 | [-2.196e-05, 6.064e-06] | +0.1% | 36,650 | 10 | 3,665 | 0.2235 | 0.8941 | no demonstrated difference |
| 20 | mae | timestral-123m | zero | reference | -1.193e-05 | [-2.407e-05, 1.073e-06] | +0.1% | 36,650 | 10 | 3,665 | 0.0631 | 0.6446 | no demonstrated difference |
| 20 | mae | timestral-209m | zero | reference | -1.154e-05 | [-2.304e-05, 1.721e-06] | +0.1% | 36,650 | 10 | 3,665 | 0.0586 | 0.6446 | no demonstrated difference |
| 20 | crps | timestral-5m | zero | reference | -2.088e-05 | [-5.024e-05, 9.075e-06] | +0.2% | 36,650 | 10 | 3,665 | 0.1533 | 0.8145 | no demonstrated difference |
| 20 | crps | timestral-28m | zero | reference | -4.002e-05 | [-6.370e-05, -1.875e-05] | +0.4% | 36,650 | 10 | 3,665 | 5.370e-04 | 0.0081 | better |
| 20 | crps | timestral-123m | zero | reference | -4.793e-05 | [-7.164e-05, -2.610e-05] | +0.4% | 36,650 | 10 | 3,665 | 4.307e-05 | 6.891e-04 | better |
| 20 | crps | timestral-209m | zero | reference | -5.121e-05 | [-7.404e-05, -3.128e-05] | +0.5% | 36,650 | 10 | 3,665 | 5.017e-06 | 8.662e-05 | better |

## Per-asset results (CRPS_q vs zero)

Counts of assets by conclusion, then the detail.

| h | model | better | worse | no demonstrated difference | insufficient data |
|---|---|---|---|---|---|
| 1 | timestral-123m | 10 | 0 | 0 | 0 |
| 1 | timestral-209m | 10 | 0 | 0 | 0 |
| 1 | timestral-28m | 9 | 0 | 1 | 0 |
| 1 | timestral-5m | 8 | 0 | 2 | 0 |
| 5 | timestral-123m | 9 | 0 | 1 | 0 |
| 5 | timestral-209m | 9 | 0 | 1 | 0 |
| 5 | timestral-28m | 8 | 0 | 2 | 0 |
| 5 | timestral-5m | 7 | 0 | 3 | 0 |
| 20 | timestral-123m | 7 | 0 | 3 | 0 |
| 20 | timestral-209m | 8 | 0 | 2 | 0 |
| 20 | timestral-28m | 6 | 0 | 4 | 0 |
| 20 | timestral-5m | 3 | 0 | 7 | 0 |

<details><summary>Per-asset detail</summary>

| asset | label | h | model | n | rel. improvement | CI low | CI high | conclusion |
|---|---|---|---|---|---|---|---|---|
| AAPL | AAPL | 1 | timestral-5m | 3,665 | +0.7% | -1.393e-04 | -9.330e-06 | better |
| AAPL | AAPL | 1 | timestral-28m | 3,665 | +1.1% | -1.878e-04 | -3.325e-05 | better |
| AAPL | AAPL | 1 | timestral-123m | 3,665 | +1.2% | -1.919e-04 | -5.565e-05 | better |
| AAPL | AAPL | 1 | timestral-209m | 3,665 | +1.3% | -2.074e-04 | -6.140e-05 | better |
| AAPL | AAPL | 5 | timestral-5m | 3,665 | +0.7% | -1.350e-04 | -1.288e-05 | better |
| AAPL | AAPL | 5 | timestral-28m | 3,665 | +0.9% | -1.467e-04 | -3.130e-05 | better |
| AAPL | AAPL | 5 | timestral-123m | 3,665 | +1.0% | -1.578e-04 | -4.639e-05 | better |
| AAPL | AAPL | 5 | timestral-209m | 3,665 | +1.1% | -1.675e-04 | -5.219e-05 | better |
| AAPL | AAPL | 20 | timestral-5m | 3,665 | +0.2% | -5.856e-05 | 1.205e-05 | no demonstrated difference |
| AAPL | AAPL | 20 | timestral-28m | 3,665 | +0.2% | -5.768e-05 | 1.387e-05 | no demonstrated difference |
| AAPL | AAPL | 20 | timestral-123m | 3,665 | +0.4% | -7.418e-05 | -3.069e-06 | better |
| AAPL | AAPL | 20 | timestral-209m | 3,665 | +0.5% | -7.992e-05 | -1.616e-05 | better |
| AMZN | AMZN | 1 | timestral-5m | 3,665 | +0.8% | -1.462e-04 | -3.536e-05 | better |
| AMZN | AMZN | 1 | timestral-28m | 3,665 | +1.0% | -1.711e-04 | -4.996e-05 | better |
| AMZN | AMZN | 1 | timestral-123m | 3,665 | +1.2% | -1.931e-04 | -7.470e-05 | better |
| AMZN | AMZN | 1 | timestral-209m | 3,665 | +1.4% | -2.082e-04 | -8.554e-05 | better |
| AMZN | AMZN | 5 | timestral-5m | 3,665 | +0.7% | -1.204e-04 | -4.151e-05 | better |
| AMZN | AMZN | 5 | timestral-28m | 3,665 | +0.9% | -1.409e-04 | -5.255e-05 | better |
| AMZN | AMZN | 5 | timestral-123m | 3,665 | +1.1% | -1.607e-04 | -6.590e-05 | better |
| AMZN | AMZN | 5 | timestral-209m | 3,665 | +1.1% | -1.622e-04 | -6.697e-05 | better |
| AMZN | AMZN | 20 | timestral-5m | 3,665 | +0.5% | -1.014e-04 | -1.936e-05 | better |
| AMZN | AMZN | 20 | timestral-28m | 3,665 | +0.6% | -1.115e-04 | -2.513e-05 | better |
| AMZN | AMZN | 20 | timestral-123m | 3,665 | +0.7% | -1.261e-04 | -3.820e-05 | better |
| AMZN | AMZN | 20 | timestral-209m | 3,665 | +0.7% | -1.213e-04 | -3.607e-05 | better |
| GLD | GLD | 1 | timestral-5m | 3,665 | +0.1% | -2.735e-05 | 1.889e-05 | no demonstrated difference |
| GLD | GLD | 1 | timestral-28m | 3,665 | +0.4% | -4.683e-05 | -4.376e-06 | better |
| GLD | GLD | 1 | timestral-123m | 3,665 | +0.5% | -6.098e-05 | -5.231e-06 | better |
| GLD | GLD | 1 | timestral-209m | 3,665 | +0.7% | -6.597e-05 | -1.437e-05 | better |
| GLD | GLD | 5 | timestral-5m | 3,665 | +0.3% | -3.362e-05 | 4.015e-06 | no demonstrated difference |
| GLD | GLD | 5 | timestral-28m | 3,665 | +0.6% | -5.176e-05 | -1.599e-05 | better |
| GLD | GLD | 5 | timestral-123m | 3,665 | +0.8% | -6.714e-05 | -2.323e-05 | better |
| GLD | GLD | 5 | timestral-209m | 3,665 | +0.8% | -6.413e-05 | -2.400e-05 | better |
| GLD | GLD | 20 | timestral-5m | 3,665 | +0.2% | -2.696e-05 | 9.060e-06 | no demonstrated difference |
| GLD | GLD | 20 | timestral-28m | 3,665 | +0.3% | -3.507e-05 | 2.864e-06 | no demonstrated difference |
| GLD | GLD | 20 | timestral-123m | 3,665 | +0.4% | -3.818e-05 | 4.390e-07 | no demonstrated difference |
| GLD | GLD | 20 | timestral-209m | 3,665 | +0.4% | -3.702e-05 | -7.823e-07 | better |
| IWM | IWM | 1 | timestral-5m | 3,665 | +0.8% | -1.322e-04 | -2.961e-06 | better |
| IWM | IWM | 1 | timestral-28m | 3,665 | +1.5% | -1.928e-04 | -4.213e-05 | better |
| IWM | IWM | 1 | timestral-123m | 3,665 | +1.7% | -2.068e-04 | -5.833e-05 | better |
| IWM | IWM | 1 | timestral-209m | 3,665 | +1.8% | -2.172e-04 | -6.187e-05 | better |
| IWM | IWM | 5 | timestral-5m | 3,665 | +0.9% | -1.291e-04 | -3.414e-06 | better |
| IWM | IWM | 5 | timestral-28m | 3,665 | +1.2% | -1.473e-04 | -3.427e-05 | better |
| IWM | IWM | 5 | timestral-123m | 3,665 | +1.4% | -1.645e-04 | -4.492e-05 | better |
| IWM | IWM | 5 | timestral-209m | 3,665 | +1.4% | -1.668e-04 | -4.517e-05 | better |
| IWM | IWM | 20 | timestral-5m | 3,665 | +0.5% | -7.008e-05 | 1.592e-06 | no demonstrated difference |
| IWM | IWM | 20 | timestral-28m | 3,665 | +0.6% | -7.137e-05 | -1.537e-05 | better |
| IWM | IWM | 20 | timestral-123m | 3,665 | +0.7% | -7.924e-05 | -2.075e-05 | better |
| IWM | IWM | 20 | timestral-209m | 3,665 | +0.8% | -9.059e-05 | -2.188e-05 | better |
| MSFT | MSFT | 1 | timestral-5m | 3,665 | +1.3% | -2.180e-04 | -3.935e-05 | better |
| MSFT | MSFT | 1 | timestral-28m | 3,665 | +1.7% | -2.773e-04 | -5.676e-05 | better |
| MSFT | MSFT | 1 | timestral-123m | 3,665 | +1.8% | -2.790e-04 | -6.915e-05 | better |
| MSFT | MSFT | 1 | timestral-209m | 3,665 | +1.9% | -2.880e-04 | -7.673e-05 | better |
| MSFT | MSFT | 5 | timestral-5m | 3,665 | +1.0% | -1.665e-04 | -2.880e-05 | better |
| MSFT | MSFT | 5 | timestral-28m | 3,665 | +1.0% | -1.560e-04 | -3.407e-05 | better |
| MSFT | MSFT | 5 | timestral-123m | 3,665 | +1.2% | -1.762e-04 | -5.183e-05 | better |
| MSFT | MSFT | 5 | timestral-209m | 3,665 | +1.2% | -1.763e-04 | -4.907e-05 | better |
| MSFT | MSFT | 20 | timestral-5m | 3,665 | +0.5% | -7.371e-05 | -8.824e-06 | better |
| MSFT | MSFT | 20 | timestral-28m | 3,665 | +0.6% | -8.417e-05 | -1.441e-05 | better |
| MSFT | MSFT | 20 | timestral-123m | 3,665 | +0.6% | -8.413e-05 | -1.239e-05 | better |
| MSFT | MSFT | 20 | timestral-209m | 3,665 | +0.6% | -9.052e-05 | -2.223e-05 | better |
| NVDA | NVDA | 1 | timestral-5m | 3,665 | +0.7% | -2.130e-04 | -1.076e-05 | better |
| NVDA | NVDA | 1 | timestral-28m | 3,665 | +1.0% | -2.613e-04 | -5.084e-05 | better |
| NVDA | NVDA | 1 | timestral-123m | 3,665 | +0.9% | -2.283e-04 | -5.640e-05 | better |
| NVDA | NVDA | 1 | timestral-209m | 3,665 | +1.2% | -2.777e-04 | -8.967e-05 | better |
| NVDA | NVDA | 5 | timestral-5m | 3,665 | +0.6% | -1.566e-04 | -2.346e-05 | better |
| NVDA | NVDA | 5 | timestral-28m | 3,665 | +0.8% | -1.876e-04 | -4.093e-05 | better |
| NVDA | NVDA | 5 | timestral-123m | 3,665 | +0.9% | -2.084e-04 | -6.597e-05 | better |
| NVDA | NVDA | 5 | timestral-209m | 3,665 | +0.9% | -2.036e-04 | -5.678e-05 | better |
| NVDA | NVDA | 20 | timestral-5m | 3,665 | +0.5% | -1.237e-04 | -2.359e-05 | better |
| NVDA | NVDA | 20 | timestral-28m | 3,665 | +0.5% | -1.287e-04 | -2.947e-05 | better |
| NVDA | NVDA | 20 | timestral-123m | 3,665 | +0.7% | -1.514e-04 | -4.790e-05 | better |
| NVDA | NVDA | 20 | timestral-209m | 3,665 | +0.7% | -1.471e-04 | -4.744e-05 | better |
| QQQ | QQQ | 1 | timestral-5m | 3,665 | +1.5% | -1.865e-04 | -3.004e-05 | better |
| QQQ | QQQ | 1 | timestral-28m | 3,665 | +2.2% | -2.482e-04 | -7.391e-05 | better |
| QQQ | QQQ | 1 | timestral-123m | 3,665 | +2.3% | -2.373e-04 | -8.422e-05 | better |
| QQQ | QQQ | 1 | timestral-209m | 3,665 | +2.4% | -2.513e-04 | -9.280e-05 | better |
| QQQ | QQQ | 5 | timestral-5m | 3,665 | +1.4% | -1.617e-04 | -2.706e-05 | better |
| QQQ | QQQ | 5 | timestral-28m | 3,665 | +1.8% | -1.792e-04 | -6.540e-05 | better |
| QQQ | QQQ | 5 | timestral-123m | 3,665 | +1.9% | -1.885e-04 | -7.397e-05 | better |
| QQQ | QQQ | 5 | timestral-209m | 3,665 | +2.0% | -1.984e-04 | -8.046e-05 | better |
| QQQ | QQQ | 20 | timestral-5m | 3,665 | +0.4% | -6.860e-05 | 1.917e-05 | no demonstrated difference |
| QQQ | QQQ | 20 | timestral-28m | 3,665 | +0.6% | -7.821e-05 | -9.771e-06 | better |
| QQQ | QQQ | 20 | timestral-123m | 3,665 | +0.7% | -8.143e-05 | -1.018e-05 | better |
| QQQ | QQQ | 20 | timestral-209m | 3,665 | +0.7% | -8.517e-05 | -1.586e-05 | better |
| SPY | SPY | 1 | timestral-5m | 3,665 | +2.0% | -1.981e-04 | -3.327e-05 | better |
| SPY | SPY | 1 | timestral-28m | 3,665 | +2.9% | -2.623e-04 | -7.408e-05 | better |
| SPY | SPY | 1 | timestral-123m | 3,665 | +2.9% | -2.565e-04 | -8.151e-05 | better |
| SPY | SPY | 1 | timestral-209m | 3,665 | +3.3% | -2.797e-04 | -9.631e-05 | better |
| SPY | SPY | 5 | timestral-5m | 3,665 | +1.6% | -1.708e-04 | -2.032e-05 | better |
| SPY | SPY | 5 | timestral-28m | 3,665 | +2.1% | -1.855e-04 | -5.396e-05 | better |
| SPY | SPY | 5 | timestral-123m | 3,665 | +2.2% | -1.972e-04 | -5.601e-05 | better |
| SPY | SPY | 5 | timestral-209m | 3,665 | +2.4% | -2.106e-04 | -6.436e-05 | better |
| SPY | SPY | 20 | timestral-5m | 3,665 | +0.2% | -5.488e-05 | 3.932e-05 | no demonstrated difference |
| SPY | SPY | 20 | timestral-28m | 3,665 | +0.7% | -6.744e-05 | -1.101e-05 | better |
| SPY | SPY | 20 | timestral-123m | 3,665 | +0.7% | -7.032e-05 | -1.171e-05 | better |
| SPY | SPY | 20 | timestral-209m | 3,665 | +0.9% | -8.073e-05 | -1.871e-05 | better |
| TLT | TLT | 1 | timestral-5m | 3,665 | +0.2% | -4.618e-05 | 1.616e-05 | no demonstrated difference |
| TLT | TLT | 1 | timestral-28m | 3,665 | +0.3% | -5.614e-05 | 9.867e-06 | no demonstrated difference |
| TLT | TLT | 1 | timestral-123m | 3,665 | +0.6% | -7.955e-05 | -5.078e-07 | better |
| TLT | TLT | 1 | timestral-209m | 3,665 | +0.8% | -8.977e-05 | -8.579e-06 | better |
| TLT | TLT | 5 | timestral-5m | 3,665 | +0.5% | -7.201e-05 | 3.144e-06 | no demonstrated difference |
| TLT | TLT | 5 | timestral-28m | 3,665 | +0.3% | -4.620e-05 | 1.238e-05 | no demonstrated difference |
| TLT | TLT | 5 | timestral-123m | 3,665 | +0.5% | -5.648e-05 | 4.747e-06 | no demonstrated difference |
| TLT | TLT | 5 | timestral-209m | 3,665 | +0.5% | -5.656e-05 | 1.155e-06 | no demonstrated difference |
| TLT | TLT | 20 | timestral-5m | 3,665 | -0.1% | -1.334e-05 | 2.839e-05 | no demonstrated difference |
| TLT | TLT | 20 | timestral-28m | 3,665 | -0.1% | -1.448e-05 | 2.460e-05 | no demonstrated difference |
| TLT | TLT | 20 | timestral-123m | 3,665 | -0.0% | -1.928e-05 | 2.640e-05 | no demonstrated difference |
| TLT | TLT | 20 | timestral-209m | 3,665 | +0.2% | -2.546e-05 | 5.649e-06 | no demonstrated difference |
| ^VIX | ^VIX | 1 | timestral-5m | 3,665 | +0.8% | -5.207e-04 | -1.517e-04 | better |
| ^VIX | ^VIX | 1 | timestral-28m | 3,665 | +1.1% | -6.143e-04 | -3.184e-04 | better |
| ^VIX | ^VIX | 1 | timestral-123m | 3,665 | +1.5% | -7.847e-04 | -4.245e-04 | better |
| ^VIX | ^VIX | 1 | timestral-209m | 3,665 | +1.9% | -9.747e-04 | -5.658e-04 | better |
| ^VIX | ^VIX | 5 | timestral-5m | 3,665 | -0.0% | -1.462e-04 | 1.949e-04 | no demonstrated difference |
| ^VIX | ^VIX | 5 | timestral-28m | 3,665 | +0.2% | -1.689e-04 | 9.038e-06 | no demonstrated difference |
| ^VIX | ^VIX | 5 | timestral-123m | 3,665 | +0.4% | -2.757e-04 | -7.104e-05 | better |
| ^VIX | ^VIX | 5 | timestral-209m | 3,665 | +0.5% | -3.085e-04 | -7.499e-05 | better |
| ^VIX | ^VIX | 20 | timestral-5m | 3,665 | -0.1% | -6.339e-05 | 2.109e-04 | no demonstrated difference |
| ^VIX | ^VIX | 20 | timestral-28m | 3,665 | +0.1% | -1.606e-04 | 3.255e-05 | no demonstrated difference |
| ^VIX | ^VIX | 20 | timestral-123m | 3,665 | +0.2% | -1.493e-04 | 1.219e-05 | no demonstrated difference |
| ^VIX | ^VIX | 20 | timestral-209m | 3,665 | +0.2% | -1.465e-04 | 1.375e-05 | no demonstrated difference |

</details>

## Calibration

Empirical coverage of central prediction intervals (nominal in the header) and the quantile calibration error (mean |share of outcomes ≤ q_τ − τ| over all levels), the PIT total-variation distance (0 = outcomes fall in each quantile bin as often as its width predicts) and the interval (Winkler) score of the 90% interval, which charges width and misses together. Coverage is only meaningful with a large n; a narrow interval is good only if its coverage holds.

| h | model | n | cov 50% | width 50% | cov 80% | width 80% | cov 90% | width 90% | cov 98% | width 98% | QCE | PIT TV | IS 90% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | linear_trend | 36,650 | 0.5015 | 0.0237 | 0.7961 | 0.0491 | 0.8931 | 0.0675 | 0.9708 | 0.1127 | 0.0015 | 0.0149 | 0.1026 |
| 1 | momentum | 36,650 | 0.5008 | 0.0343 | 0.7974 | 0.0708 | 0.8920 | 0.0965 | 0.9710 | 0.1624 | 0.0016 | 0.0127 | 0.1472 |
| 1 | moving_average | 36,650 | 0.5010 | 0.0234 | 0.7960 | 0.0486 | 0.8941 | 0.0669 | 0.9708 | 0.1119 | 0.0016 | 0.0163 | 0.1017 |
| 1 | persistence | 36,650 | 0.5008 | 0.0334 | 0.7964 | 0.0690 | 0.8921 | 0.0941 | 0.9706 | 0.1583 | 0.0016 | 0.0126 | 0.1435 |
| 1 | timestral-123m | 36,650 | 0.5101 | 0.0239 | 0.8047 | 0.0481 | 0.8996 | 0.0641 | 0.9776 | 0.1016 | 0.0039 | 0.0162 | 0.0920 |
| 1 | timestral-209m | 36,650 | 0.4930 | 0.0231 | 0.7934 | 0.0471 | 0.8949 | 0.0635 | 0.9797 | 0.1045 | 0.0033 | 0.0160 | 0.0919 |
| 1 | timestral-28m | 36,650 | 0.5111 | 0.0237 | 0.8068 | 0.0480 | 0.9011 | 0.0649 | 0.9787 | 0.1049 | 0.0037 | 0.0177 | 0.0928 |
| 1 | timestral-5m | 36,650 | 0.5071 | 0.0234 | 0.8009 | 0.0476 | 0.8951 | 0.0637 | 0.9767 | 0.1039 | 0.0040 | 0.0288 | 0.0935 |
| 1 | zero | 36,650 | 0.5023 | 0.0225 | 0.7951 | 0.0471 | 0.8925 | 0.0650 | 0.9708 | 0.1089 | 0.0017 | 0.0140 | 0.0991 |
| 5 | linear_trend | 36,650 | 0.5010 | 0.0237 | 0.7962 | 0.0494 | 0.8920 | 0.0675 | 0.9692 | 0.1122 | 0.0017 | 0.0145 | 0.1028 |
| 5 | momentum | 36,650 | 0.5034 | 0.0383 | 0.7959 | 0.0791 | 0.8928 | 0.1078 | 0.9701 | 0.1754 | 0.0019 | 0.0153 | 0.1595 |
| 5 | moving_average | 36,650 | 0.5018 | 0.0233 | 0.7948 | 0.0486 | 0.8926 | 0.0666 | 0.9691 | 0.1111 | 0.0018 | 0.0167 | 0.1015 |
| 5 | persistence | 36,650 | 0.5014 | 0.0336 | 0.7960 | 0.0689 | 0.8930 | 0.0940 | 0.9695 | 0.1543 | 0.0018 | 0.0157 | 0.1399 |
| 5 | timestral-123m | 36,650 | 0.5076 | 0.0232 | 0.8049 | 0.0480 | 0.8979 | 0.0650 | 0.9769 | 0.1065 | 0.0031 | 0.0197 | 0.0957 |
| 5 | timestral-209m | 36,650 | 0.4968 | 0.0227 | 0.7982 | 0.0474 | 0.8972 | 0.0650 | 0.9784 | 0.1097 | 0.0029 | 0.0203 | 0.0956 |
| 5 | timestral-28m | 36,650 | 0.5101 | 0.0233 | 0.8063 | 0.0481 | 0.9005 | 0.0658 | 0.9782 | 0.1096 | 0.0033 | 0.0160 | 0.0961 |
| 5 | timestral-5m | 36,650 | 0.5130 | 0.0235 | 0.8052 | 0.0481 | 0.8962 | 0.0650 | 0.9762 | 0.1079 | 0.0045 | 0.0238 | 0.0963 |
| 5 | zero | 36,650 | 0.5026 | 0.0225 | 0.7953 | 0.0471 | 0.8921 | 0.0650 | 0.9698 | 0.1088 | 0.0019 | 0.0162 | 0.0994 |
| 20 | linear_trend | 36,650 | 0.4998 | 0.0248 | 0.7902 | 0.0505 | 0.8883 | 0.0692 | 0.9652 | 0.1132 | 0.0026 | 0.0205 | 0.1065 |
| 20 | momentum | 36,650 | 0.5030 | 0.0594 | 0.7942 | 0.1197 | 0.8891 | 0.1632 | 0.9649 | 0.2604 | 0.0023 | 0.0203 | 0.2430 |
| 20 | moving_average | 36,650 | 0.5023 | 0.0234 | 0.7919 | 0.0481 | 0.8889 | 0.0665 | 0.9658 | 0.1100 | 0.0024 | 0.0199 | 0.1026 |
| 20 | persistence | 36,650 | 0.5025 | 0.0342 | 0.7930 | 0.0688 | 0.8889 | 0.0935 | 0.9663 | 0.1523 | 0.0024 | 0.0203 | 0.1406 |
| 20 | timestral-123m | 36,650 | 0.5116 | 0.0231 | 0.8038 | 0.0480 | 0.8979 | 0.0661 | 0.9773 | 0.1146 | 0.0040 | 0.0227 | 0.0987 |
| 20 | timestral-209m | 36,650 | 0.4958 | 0.0223 | 0.8008 | 0.0478 | 0.9017 | 0.0671 | 0.9786 | 0.1161 | 0.0026 | 0.0174 | 0.0985 |
| 20 | timestral-28m | 36,650 | 0.5098 | 0.0229 | 0.8049 | 0.0482 | 0.9010 | 0.0670 | 0.9785 | 0.1167 | 0.0030 | 0.0220 | 0.0989 |
| 20 | timestral-5m | 36,650 | 0.5236 | 0.0239 | 0.8108 | 0.0493 | 0.9024 | 0.0679 | 0.9783 | 0.1207 | 0.0072 | 0.0283 | 0.0993 |
| 20 | zero | 36,650 | 0.5029 | 0.0225 | 0.7935 | 0.0471 | 0.8893 | 0.0649 | 0.9668 | 0.1083 | 0.0023 | 0.0183 | 0.1003 |

## Performance over time

CRPS_q improvement over `zero` per year of origin (positive = better). A model that only wins in one period has not shown a stable advantage.


**h = 1**

| period | n | timestral-5m | timestral-28m | timestral-123m | timestral-209m | persistence | moving_average | momentum | linear_trend |
|---|---|---|---|---|---|---|---|---|---|
| 2012 | 2,100 | +0.7% | +0.8% | +0.7% | +0.9% | -42.4% | -2.7% | -46.0% | -3.0% |
| 2013 | 2,520 | +0.2% | +0.5% | +0.6% | +1.0% | -49.5% | -3.6% | -53.5% | -4.2% |
| 2014 | 2,520 | +0.9% | +0.7% | +1.1% | +1.6% | -45.6% | -3.6% | -49.3% | -4.4% |
| 2015 | 2,520 | +0.3% | -0.1% | +0.7% | +1.1% | -40.8% | -3.5% | -44.3% | -5.5% |
| 2016 | 2,520 | +0.7% | +1.1% | +1.4% | +1.6% | -46.5% | -3.0% | -50.1% | -4.8% |
| 2017 | 2,510 | +0.4% | +0.3% | +0.4% | +0.6% | -49.4% | -3.4% | -53.1% | -5.1% |
| 2018 | 2,510 | +0.8% | +1.6% | +1.8% | +2.0% | -45.7% | -3.5% | -49.6% | -4.0% |
| 2019 | 2,520 | +1.3% | +1.2% | +1.3% | +1.7% | -46.4% | -3.1% | -50.1% | -4.7% |
| 2020 | 2,530 | +3.9% | +5.0% | +4.7% | +5.2% | -55.5% | -3.1% | -60.1% | -4.2% |
| 2021 | 2,520 | +1.0% | +1.8% | +2.2% | +2.5% | -45.5% | -3.4% | -49.4% | -4.2% |
| 2022 | 2,510 | +0.5% | +1.0% | +0.9% | +0.9% | -41.3% | -2.9% | -45.1% | -3.6% |
| 2023 | 2,500 | +0.9% | +0.9% | +1.2% | +1.5% | -43.8% | -3.2% | -47.6% | -4.1% |
| 2024 | 2,520 | -0.9% | -0.2% | +0.5% | +0.5% | -42.8% | -3.1% | -46.3% | -4.3% |
| 2025 | 2,500 | +0.2% | +0.9% | +0.9% | +1.2% | -48.5% | -3.3% | -52.1% | -4.0% |
| 2026 | 1,850 | +0.9% | +1.0% | +1.0% | +1.0% | -46.7% | -2.7% | -50.6% | -4.1% |

**h = 5**

| period | n | timestral-5m | timestral-28m | timestral-123m | timestral-209m | persistence | moving_average | momentum | linear_trend |
|---|---|---|---|---|---|---|---|---|---|
| 2012 | 2,100 | +0.6% | +0.6% | +0.8% | +0.8% | -46.1% | -2.2% | -66.4% | -2.9% |
| 2013 | 2,520 | -0.1% | -0.0% | +0.3% | +0.2% | -50.9% | -3.3% | -73.7% | -4.1% |
| 2014 | 2,520 | +0.3% | +0.3% | +0.4% | +0.6% | -42.5% | -3.5% | -63.7% | -5.0% |
| 2015 | 2,520 | -0.4% | -0.2% | -0.0% | -0.0% | -46.5% | -1.9% | -66.3% | -4.7% |
| 2016 | 2,520 | +0.6% | +0.7% | +0.9% | +1.0% | -49.7% | -3.0% | -70.6% | -6.1% |
| 2017 | 2,510 | -0.1% | -0.2% | +0.2% | +0.2% | -44.7% | -3.0% | -65.4% | -5.4% |
| 2018 | 2,510 | +0.8% | +1.1% | +1.4% | +1.3% | -47.2% | -3.1% | -68.8% | -4.5% |
| 2019 | 2,520 | +0.5% | +0.5% | +0.6% | +0.7% | -44.9% | -3.0% | -66.5% | -4.6% |
| 2020 | 2,530 | +3.3% | +3.2% | +3.2% | +3.3% | -36.8% | -2.5% | -57.5% | -4.1% |
| 2021 | 2,520 | +0.3% | +0.4% | +0.5% | +0.6% | -45.6% | -2.1% | -65.9% | -3.4% |
| 2022 | 2,510 | +1.1% | +1.4% | +1.5% | +1.5% | -38.8% | -3.0% | -58.9% | -4.3% |
| 2023 | 2,500 | +0.8% | +0.8% | +1.2% | +1.3% | -41.5% | -3.0% | -61.5% | -4.8% |
| 2024 | 2,520 | -1.4% | -0.6% | -0.2% | -0.2% | -53.2% | -2.6% | -73.5% | -5.0% |
| 2025 | 2,500 | -0.1% | +0.6% | +0.6% | +0.8% | -45.0% | -3.1% | -65.1% | -4.2% |
| 2026 | 1,850 | +0.0% | +0.3% | +0.4% | +0.2% | -39.7% | -2.3% | -59.9% | -4.4% |

**h = 20**

| period | n | timestral-5m | timestral-28m | timestral-123m | timestral-209m | persistence | moving_average | momentum | linear_trend |
|---|---|---|---|---|---|---|---|---|---|
| 2012 | 2,100 | +0.2% | +0.4% | +0.6% | +0.7% | -42.1% | -1.6% | -143.6% | -5.8% |
| 2013 | 2,520 | -0.1% | +0.1% | +0.2% | +0.1% | -45.8% | -2.3% | -155.1% | -5.6% |
| 2014 | 2,520 | +0.1% | +0.0% | -0.0% | +0.0% | -41.4% | -2.8% | -141.7% | -6.3% |
| 2015 | 2,520 | -1.2% | -0.2% | -0.1% | -0.1% | -41.7% | -3.1% | -144.3% | -9.3% |
| 2016 | 2,520 | +0.1% | +0.4% | +0.4% | +0.6% | -44.2% | -3.3% | -154.3% | -10.9% |
| 2017 | 2,510 | -0.4% | -0.3% | -0.1% | -0.0% | -47.7% | -3.1% | -158.3% | -8.3% |
| 2018 | 2,510 | +0.1% | +0.4% | +0.6% | +0.5% | -48.4% | -2.2% | -156.5% | -5.6% |
| 2019 | 2,520 | -0.2% | -0.1% | -0.1% | -0.1% | -50.6% | -3.6% | -167.5% | -8.3% |
| 2020 | 2,530 | +1.1% | +0.8% | +0.6% | +1.0% | -48.2% | -2.9% | -160.9% | -10.4% |
| 2021 | 2,520 | +0.1% | +0.4% | +0.5% | +0.4% | -49.3% | -2.3% | -157.9% | -5.1% |
| 2022 | 2,510 | +1.1% | +1.2% | +1.5% | +1.3% | -38.6% | -2.6% | -140.8% | -8.6% |
| 2023 | 2,500 | +0.6% | +0.7% | +1.2% | +1.1% | -42.1% | -3.1% | -144.4% | -6.8% |
| 2024 | 2,520 | +0.3% | +0.5% | +0.3% | +0.2% | -41.8% | -2.6% | -137.4% | -7.4% |
| 2025 | 2,500 | -0.2% | +0.1% | +0.2% | +0.3% | -41.0% | -1.7% | -147.1% | -5.6% |
| 2026 | 1,850 | +0.2% | +0.2% | +0.2% | +0.1% | -42.1% | -2.6% | -147.7% | -7.3% |

## Model runs

| run | model | version | device | status | forecasts | failed | ms/forecast | wall s | peak RSS MB | peak VRAM MB | code |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | timestral-5m | – | cuda:0 | completed | 36,650 | 0 | 20.12 | 776.5 | 1699 | 28.22 | d3632d2c43f229eae54253a686269a14c8ecf43e |
| 7 | timestral-28m | – | cuda:0 | completed | 36,650 | 0 | 25.47 | 969 | 1760 | 115.4 | d3632d2c43f229eae54253a686269a14c8ecf43e |
| 8 | timestral-123m | – | cuda:0 | completed | 36,650 | 0 | 38.01 | 1430 | 1780 | 481.3 | d3632d2c43f229eae54253a686269a14c8ecf43e |
| 9 | timestral-209m | – | cuda:0 | completed | 36,650 | 0 | 44.76 | 1678 | 2225 | 812.9 | d3632d2c43f229eae54253a686269a14c8ecf43e |
| 10 | zero | – | cpu | completed | 36,650 | 0 | 3.004 | 134.9 | 1700 | 0.0000 | d3632d2c43f229eae54253a686269a14c8ecf43e |
| 11 | persistence | – | cpu | completed | 36,650 | 0 | 3.097 | 139.7 | 1700 | 0.0000 | d3632d2c43f229eae54253a686269a14c8ecf43e |
| 12 | moving_average | – | cpu | completed | 36,650 | 0 | 3.978 | 169.8 | 1700 | 0.0000 | d3632d2c43f229eae54253a686269a14c8ecf43e |
| 13 | momentum | – | cpu | completed | 36,650 | 0 | 5.482 | 224.1 | 1700 | 0.0000 | d3632d2c43f229eae54253a686269a14c8ecf43e |
| 14 | linear_trend | – | cpu | completed | 36,650 | 0 | 16.72 | 636.4 | 1701 | 0.0000 | d3632d2c43f229eae54253a686269a14c8ecf43e |

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
