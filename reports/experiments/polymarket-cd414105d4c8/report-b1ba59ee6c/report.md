# Experiment `polymarket-cd414105d4c8`: polymarket reconstructed 47-market panel

> **RECONSTRUCTED RESEARCH: inputs are backfilled data replayed under documented availability assumptions. This is not what the system genuinely knew at the time.**

Status: **completed**. Created 2026-11-03T13:50:35.421372Z at code version `2f0caf39abfff31a8723c81320ef1bdc2d5e55a6`. This is forecasting research. It is not a trading signal and says nothing about profitability.

## Configuration

| field | value |
|---|---|
| domain | polymarket |
| knowledge mode | reconstructed_history |
| source / interval | polymarket_clob_history / 1h |
| calendar | UTC hours |
| target | logit of the YES token price (eps 0.0001); probabilities via inverse logit |
| price field | close |
| assets requested | 47 |
| origins | 2025-06-01 00:00 to 2026-11-01 10:00 UTC, every 6 hours |
| cutoff | origin timestamp + 300 s; extra replay latency 0 s |
| targets read as of | 2026-11-03 10:00 UTC |
| context | 336 points (min 168 valid, max 25% missing) |
| horizons | 1, 6, 24 hours |
| quantile levels | 21 in [0.01, 0.99] |
| reference baseline | persistence |
| seed / device requested | 0 / auto |
| availability rule | hourly price sample: filed under its hour, known at its own sample time source_ts; available_at = source_ts + availability.polymarket_history_latency_seconds |
| model versions | linear_trend=baselines-0.1, momentum=baselines-0.1, moving_average=baselines-0.1, persistence=baselines-0.1, timestral-123m=5a147287addd, timestral-209m=9874d252ab0a, timestral-28m=49b26409ac87, timestral-5m=bdd20cfc15a3, zero=baselines-0.1 |

## Data and exclusions

- Assets prepared: 47; usable origins: 38,623; scored cases in the common sample: 113,072 per model.
- Grid origins skipped (after_market_close): 66.
- Grid origins skipped (outside_data_span): 53,356.
- Origins excluded (insufficient_context): 1,648.
- Origins excluded (origin_observation_missing): 3,105.
- Origins excluded (too_many_missing_context): 680.
- Origin-horizon cases without a realised target (h1:target_missing): 516.
- Origin-horizon cases without a realised target (h24:after_market_close): 27.
- Origin-horizon cases without a realised target (h24:target_missing): 1,159.
- Origin-horizon cases without a realised target (h6:after_market_close): 2.
- Origin-horizon cases without a realised target (h6:target_missing): 1,093.

## Leaderboard

Pooled over all scored cases (every case equal weight); `macro MAE` is the mean of per-asset MAEs. Relative columns are `1 - metric / metric(persistence)`: positive is better than `persistence`. `asset skill` is the same ratio computed within each asset and then averaged over assets, so high-volatility assets do not dominate it. CRPS_q is the quantile CRPS over levels [{min(cfg.quantile_levels)}, {max(cfg.quantile_levels)}] (no tail extrapolation). Directional accuracy excludes zero changes.

### h = 1 hours

| model | n | assets | MAE (prob) | RMSE (prob) | MAE | RMSE | mean err | pinball | CRPS_q | cov 90% | width 90% | dir acc | ΔMAE | ΔCRPS | macro MAE | asset skill MAE | asset skill CRPS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| timestral-5m | 38,107 | 46 | 0.0016 | 0.0062 | 0.0119 | 0.0434 | 1.143e-04 | 0.0050 | 0.0102 | 0.9074 | 0.0627 | 0.5594 | -11.6% | -4.9% | 0.0264 | -12.7% | -6.0% |
| timestral-28m | 38,107 | 46 | 0.0016 | 0.0062 | 0.0114 | 0.0421 | 1.354e-04 | 0.0048 | 0.0099 | 0.9120 | 0.0615 | 0.5489 | -6.8% | -1.7% | 0.0254 | -7.3% | -2.4% |
| timestral-123m | 38,107 | 46 | 0.0015 | 0.0061 | 0.0113 | 0.0421 | 9.535e-05 | 0.0048 | 0.0098 | 0.9171 | 0.0640 | 0.5462 | -5.6% | -0.7% | 0.0252 | -6.1% | -1.6% |
| timestral-209m | 38,107 | 46 | 0.0015 | 0.0061 | 0.0112 | 0.0417 | 5.853e-05 | 0.0048 | 0.0097 | 0.9094 | 0.0592 | 0.5353 | -4.8% | -0.3% | 0.0249 | -5.6% | -1.2% |
| zero | 38,107 | 46 | 0.0179 | 0.0383 | 0.1361 | 0.2551 | 0.0350 | 0.0454 | 0.0944 | 0.8562 | 0.3495 | 0.5387 | -1173.6% | -873.1% | 0.2366 | -1286.1% | -952.0% |
| persistence | 38,107 | 46 | 0.0015 | 0.0061 | 0.0107 | 0.0419 | 1.996e-04 | 0.0048 | 0.0097 | 0.9138 | 0.0592 | 0.5625 | +0.0% | +0.0% | 0.0243 | +0.0% | +0.0% |
| moving_average | 38,107 | 46 | 0.0052 | 0.0136 | 0.0399 | 0.1012 | 7.817e-04 | 0.0155 | 0.0320 | 0.8832 | 0.1973 | 0.5678 | -273.4% | -229.3% | 0.0762 | -297.4% | -251.4% |
| momentum | 38,107 | 46 | 0.0018 | 0.0062 | 0.0131 | 0.0433 | 9.046e-05 | 0.0055 | 0.0114 | 0.8906 | 0.0666 | 0.4473 | -22.9% | -17.1% | 0.0278 | -25.0% | -19.1% |
| linear_trend | 38,107 | 46 | 0.0063 | 0.0145 | 0.0486 | 0.1048 | -4.635e-04 | 0.0181 | 0.0375 | 0.8795 | 0.2216 | 0.5473 | -354.9% | -286.4% | 0.0862 | -391.6% | -316.2% |

### h = 6 hours

| model | n | assets | MAE (prob) | RMSE (prob) | MAE | RMSE | mean err | pinball | CRPS_q | cov 90% | width 90% | dir acc | ΔMAE | ΔCRPS | macro MAE | asset skill MAE | asset skill CRPS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| timestral-5m | 37,528 | 46 | 0.0048 | 0.0134 | 0.0354 | 0.0890 | 0.0016 | 0.0140 | 0.0288 | 0.8915 | 0.1904 | 0.5566 | -2.9% | +1.5% | 0.0603 | -2.2% | +1.5% |
| timestral-28m | 37,528 | 46 | 0.0047 | 0.0134 | 0.0349 | 0.0893 | 0.0017 | 0.0138 | 0.0285 | 0.8921 | 0.1938 | 0.5618 | -1.3% | +2.6% | 0.0598 | -0.5% | +2.5% |
| timestral-123m | 37,528 | 46 | 0.0047 | 0.0133 | 0.0347 | 0.0890 | 0.0017 | 0.0138 | 0.0284 | 0.8933 | 0.1926 | 0.5549 | -1.0% | +2.8% | 0.0595 | -0.2% | +2.6% |
| timestral-209m | 37,528 | 46 | 0.0047 | 0.0134 | 0.0347 | 0.0891 | 0.0017 | 0.0138 | 0.0284 | 0.8903 | 0.1913 | 0.5462 | -0.8% | +2.8% | 0.0592 | -0.0% | +2.6% |
| zero | 37,528 | 46 | 0.0183 | 0.0386 | 0.1386 | 0.2538 | 0.0363 | 0.0468 | 0.0972 | 0.8341 | 0.3464 | 0.5503 | -303.0% | -232.1% | 0.2345 | -319.7% | -247.6% |
| persistence | 37,528 | 46 | 0.0046 | 0.0134 | 0.0344 | 0.0908 | 0.0019 | 0.0142 | 0.0293 | 0.8858 | 0.1873 | 0.5419 | +0.0% | +0.0% | 0.0602 | +0.0% | +0.0% |
| moving_average | 37,528 | 46 | 0.0069 | 0.0171 | 0.0527 | 0.1201 | 0.0016 | 0.0204 | 0.0420 | 0.8662 | 0.2542 | 0.5725 | -53.2% | -43.7% | 0.0936 | -59.9% | -51.6% |
| momentum | 37,528 | 46 | 0.0061 | 0.0154 | 0.0467 | 0.1092 | 5.577e-04 | 0.0183 | 0.0377 | 0.8783 | 0.2321 | 0.4388 | -35.8% | -29.0% | 0.0810 | -38.5% | -33.3% |
| linear_trend | 37,528 | 46 | 0.0085 | 0.0188 | 0.0654 | 0.1286 | -1.955e-05 | 0.0244 | 0.0504 | 0.8641 | 0.2962 | 0.5386 | -90.0% | -72.4% | 0.1085 | -97.8% | -80.1% |

### h = 24 hours

| model | n | assets | MAE (prob) | RMSE (prob) | MAE | RMSE | mean err | pinball | CRPS_q | cov 90% | width 90% | dir acc | ΔMAE | ΔCRPS | macro MAE | asset skill MAE | asset skill CRPS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| timestral-5m | 37,437 | 46 | 0.0100 | 0.0240 | 0.0763 | 0.1746 | 0.0063 | 0.0289 | 0.0596 | 0.8642 | 0.3601 | 0.5486 | +0.2% | +3.5% | 0.1472 | +0.3% | +3.1% |
| timestral-28m | 37,437 | 46 | 0.0098 | 0.0239 | 0.0749 | 0.1733 | 0.0065 | 0.0286 | 0.0590 | 0.8797 | 0.3864 | 0.5584 | +2.0% | +4.4% | 0.1454 | +1.8% | +3.7% |
| timestral-123m | 37,437 | 46 | 0.0098 | 0.0239 | 0.0751 | 0.1736 | 0.0071 | 0.0286 | 0.0590 | 0.8844 | 0.3906 | 0.5500 | +1.9% | +4.5% | 0.1464 | +1.5% | +3.7% |
| timestral-209m | 37,437 | 46 | 0.0098 | 0.0239 | 0.0750 | 0.1733 | 0.0068 | 0.0286 | 0.0590 | 0.8880 | 0.4032 | 0.5498 | +1.9% | +4.4% | 0.1457 | +1.6% | +3.6% |
| zero | 37,437 | 46 | 0.0195 | 0.0407 | 0.1481 | 0.2698 | 0.0389 | 0.0522 | 0.1076 | 0.7654 | 0.3318 | 0.5526 | -93.6% | -74.2% | 0.2601 | -95.1% | -76.0% |
| persistence | 37,437 | 46 | 0.0101 | 0.0244 | 0.0765 | 0.1758 | 0.0032 | 0.0300 | 0.0617 | 0.8427 | 0.3465 | 0.4936 | +0.0% | +0.0% | 0.1479 | +0.0% | +0.0% |
| moving_average | 37,437 | 46 | 0.0115 | 0.0264 | 0.0877 | 0.1861 | 0.0027 | 0.0336 | 0.0691 | 0.8093 | 0.3528 | 0.5463 | -14.6% | -12.0% | 0.1633 | -14.4% | -12.1% |
| momentum | 37,437 | 46 | 0.0162 | 0.0351 | 0.1252 | 0.2519 | -6.996e-04 | 0.0478 | 0.0985 | 0.8585 | 0.5917 | 0.4459 | -63.7% | -59.6% | 0.2203 | -61.6% | -57.7% |
| linear_trend | 37,437 | 46 | 0.0157 | 0.0328 | 0.1209 | 0.2243 | 8.277e-04 | 0.0452 | 0.0932 | 0.8200 | 0.5036 | 0.5011 | -58.0% | -50.9% | 0.2101 | -57.2% | -50.0% |

## Paired comparisons

Mean loss difference (model − comparator) over identical cases; negative is better. 95% CI from a moving-block bootstrap over origin dates (2000 resamples, block ≥ horizon/stride). `insufficient data` when there are fewer than 30 origin dates or fewer than 10 blocks. 24 comparisons are shown, so about 1 could exclude zero by chance alone. `DM p` is the Diebold-Mariano test (Newey-West variance, Harvey-Leybourne-Newbold correction) on the per-date mean differential; `Holm p` adjusts it for every comparison in this table.

| h | loss | model | vs | comparator | mean diff | 95% CI | rel. improvement | pairs | assets | dates | DM p | Holm p | conclusion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | mae | timestral-5m | persistence | reference | 0.0012 | [0.0011, 0.0014] | -11.6% | 38,107 | 46 | 1,960 | 1.458e-46 | 3.499e-45 | worse |
| 1 | mae | timestral-28m | persistence | reference | 7.267e-04 | [6.644e-04, 8.055e-04] | -6.8% | 38,107 | 46 | 1,960 | 2.114e-40 | 4.863e-39 | worse |
| 1 | mae | timestral-123m | persistence | reference | 5.965e-04 | [5.299e-04, 6.845e-04] | -5.6% | 38,107 | 46 | 1,960 | 8.790e-23 | 1.846e-21 | worse |
| 1 | mae | timestral-209m | persistence | reference | 5.107e-04 | [4.703e-04, 5.544e-04] | -4.8% | 38,107 | 46 | 1,960 | 1.773e-32 | 3.900e-31 | worse |
| 1 | crps | timestral-5m | persistence | reference | 4.779e-04 | [3.709e-04, 5.943e-04] | -4.9% | 38,107 | 46 | 1,960 | 9.747e-08 | 1.267e-06 | worse |
| 1 | crps | timestral-28m | persistence | reference | 1.603e-04 | [8.017e-05, 2.325e-04] | -1.7% | 38,107 | 46 | 1,960 | 0.1984 | 1 | worse |
| 1 | crps | timestral-123m | persistence | reference | 6.866e-05 | [-2.230e-05, 1.611e-04] | -0.7% | 38,107 | 46 | 1,960 | 0.7697 | 1 | no demonstrated difference |
| 1 | crps | timestral-209m | persistence | reference | 3.169e-05 | [-4.443e-05, 1.038e-04] | -0.3% | 38,107 | 46 | 1,960 | 0.3644 | 1 | no demonstrated difference |
| 6 | mae | timestral-5m | persistence | reference | 9.858e-04 | [7.755e-04, 0.0012] | -2.9% | 37,528 | 46 | 1,959 | 0.0020 | 0.0221 | worse |
| 6 | mae | timestral-28m | persistence | reference | 4.516e-04 | [3.173e-04, 5.744e-04] | -1.3% | 37,528 | 46 | 1,959 | 0.2189 | 1 | worse |
| 6 | mae | timestral-123m | persistence | reference | 3.442e-04 | [1.721e-04, 4.852e-04] | -1.0% | 37,528 | 46 | 1,959 | 0.6749 | 1 | worse |
| 6 | mae | timestral-209m | persistence | reference | 2.653e-04 | [6.925e-05, 4.186e-04] | -0.8% | 37,528 | 46 | 1,959 | 0.7182 | 1 | worse |
| 6 | crps | timestral-5m | persistence | reference | -4.514e-04 | [-6.585e-04, -2.508e-04] | +1.5% | 37,528 | 46 | 1,959 | 3.671e-05 | 4.405e-04 | better |
| 6 | crps | timestral-28m | persistence | reference | -7.553e-04 | [-9.355e-04, -5.839e-04] | +2.6% | 37,528 | 46 | 1,959 | 3.025e-09 | 4.537e-08 | better |
| 6 | crps | timestral-123m | persistence | reference | -8.144e-04 | [-0.0010, -6.300e-04] | +2.8% | 37,528 | 46 | 1,959 | 1.054e-11 | 1.686e-10 | better |
| 6 | crps | timestral-209m | persistence | reference | -8.273e-04 | [-0.0010, -6.546e-04] | +2.8% | 37,528 | 46 | 1,959 | 1.397e-13 | 2.794e-12 | better |
| 24 | mae | timestral-5m | persistence | reference | -1.414e-04 | [-9.862e-04, 6.784e-04] | +0.2% | 37,437 | 46 | 1,962 | 0.8552 | 1 | no demonstrated difference |
| 24 | mae | timestral-28m | persistence | reference | -0.0015 | [-0.0023, -8.314e-04] | +2.0% | 37,437 | 46 | 1,962 | 0.0056 | 0.0448 | better |
| 24 | mae | timestral-123m | persistence | reference | -0.0014 | [-0.0022, -6.654e-04] | +1.9% | 37,437 | 46 | 1,962 | 0.0036 | 0.0328 | better |
| 24 | mae | timestral-209m | persistence | reference | -0.0015 | [-0.0022, -7.947e-04] | +1.9% | 37,437 | 46 | 1,962 | 0.0026 | 0.0261 | better |
| 24 | crps | timestral-5m | persistence | reference | -0.0021 | [-0.0028, -0.0015] | +3.5% | 37,437 | 46 | 1,962 | 6.214e-08 | 8.700e-07 | better |
| 24 | crps | timestral-28m | persistence | reference | -0.0027 | [-0.0033, -0.0022] | +4.4% | 37,437 | 46 | 1,962 | 4.184e-12 | 7.113e-11 | better |
| 24 | crps | timestral-123m | persistence | reference | -0.0028 | [-0.0034, -0.0022] | +4.5% | 37,437 | 46 | 1,962 | 8.859e-13 | 1.595e-11 | better |
| 24 | crps | timestral-209m | persistence | reference | -0.0027 | [-0.0033, -0.0022] | +4.4% | 37,437 | 46 | 1,962 | 2.711e-13 | 5.151e-12 | better |

## Per-asset results (CRPS_q vs persistence)

Counts of assets by conclusion, then the detail.

| h | model | better | worse | no demonstrated difference | insufficient data |
|---|---|---|---|---|---|
| 1 | timestral-123m | 1 | 10 | 32 | 3 |
| 1 | timestral-209m | 2 | 10 | 31 | 3 |
| 1 | timestral-28m | 1 | 15 | 27 | 3 |
| 1 | timestral-5m | 0 | 28 | 15 | 3 |
| 6 | timestral-123m | 23 | 0 | 20 | 3 |
| 6 | timestral-209m | 20 | 1 | 22 | 3 |
| 6 | timestral-28m | 18 | 0 | 25 | 3 |
| 6 | timestral-5m | 6 | 1 | 36 | 3 |
| 24 | timestral-123m | 18 | 0 | 25 | 3 |
| 24 | timestral-209m | 18 | 0 | 25 | 3 |
| 24 | timestral-28m | 18 | 0 | 25 | 3 |
| 24 | timestral-5m | 11 | 0 | 32 | 3 |

<details><summary>Per-asset detail</summary>

| asset | label | h | model | n | rel. improvement | CI low | CI high | conclusion |
|---|---|---|---|---|---|---|---|---|
| 0x024b68f77bfc019341ee3db8f57c103334e4b9430bba4746d8c94aafd8b36fee | Will Bitcoin dip to $45,000 by December 31, 2026? | 1 | timestral-5m | 1,091 | -3.7% | 1.242e-04 | 8.969e-04 | worse |
| 0x024b68f77bfc019341ee3db8f57c103334e4b9430bba4746d8c94aafd8b36fee | Will Bitcoin dip to $45,000 by December 31, 2026? | 1 | timestral-28m | 1,091 | -1.3% | -1.506e-04 | 4.931e-04 | no demonstrated difference |
| 0x024b68f77bfc019341ee3db8f57c103334e4b9430bba4746d8c94aafd8b36fee | Will Bitcoin dip to $45,000 by December 31, 2026? | 1 | timestral-123m | 1,091 | -0.8% | -1.929e-04 | 4.496e-04 | no demonstrated difference |
| 0x024b68f77bfc019341ee3db8f57c103334e4b9430bba4746d8c94aafd8b36fee | Will Bitcoin dip to $45,000 by December 31, 2026? | 1 | timestral-209m | 1,091 | -0.3% | -2.504e-04 | 3.291e-04 | no demonstrated difference |
| 0x024b68f77bfc019341ee3db8f57c103334e4b9430bba4746d8c94aafd8b36fee | Will Bitcoin dip to $45,000 by December 31, 2026? | 6 | timestral-5m | 1,049 | +1.9% | -0.0014 | 1.250e-05 | no demonstrated difference |
| 0x024b68f77bfc019341ee3db8f57c103334e4b9430bba4746d8c94aafd8b36fee | Will Bitcoin dip to $45,000 by December 31, 2026? | 6 | timestral-28m | 1,049 | +2.6% | -0.0016 | -3.420e-04 | better |
| 0x024b68f77bfc019341ee3db8f57c103334e4b9430bba4746d8c94aafd8b36fee | Will Bitcoin dip to $45,000 by December 31, 2026? | 6 | timestral-123m | 1,049 | +2.0% | -0.0013 | -1.640e-04 | better |
| 0x024b68f77bfc019341ee3db8f57c103334e4b9430bba4746d8c94aafd8b36fee | Will Bitcoin dip to $45,000 by December 31, 2026? | 6 | timestral-209m | 1,049 | +2.6% | -0.0016 | -3.755e-04 | better |
| 0x024b68f77bfc019341ee3db8f57c103334e4b9430bba4746d8c94aafd8b36fee | Will Bitcoin dip to $45,000 by December 31, 2026? | 24 | timestral-5m | 1,048 | +2.9% | -0.0051 | 0.0013 | no demonstrated difference |
| 0x024b68f77bfc019341ee3db8f57c103334e4b9430bba4746d8c94aafd8b36fee | Will Bitcoin dip to $45,000 by December 31, 2026? | 24 | timestral-28m | 1,048 | +3.9% | -0.0055 | 2.500e-04 | no demonstrated difference |
| 0x024b68f77bfc019341ee3db8f57c103334e4b9430bba4746d8c94aafd8b36fee | Will Bitcoin dip to $45,000 by December 31, 2026? | 24 | timestral-123m | 1,048 | +3.3% | -0.0052 | 8.854e-04 | no demonstrated difference |
| 0x024b68f77bfc019341ee3db8f57c103334e4b9430bba4746d8c94aafd8b36fee | Will Bitcoin dip to $45,000 by December 31, 2026? | 24 | timestral-209m | 1,048 | +3.4% | -0.0051 | 4.894e-04 | no demonstrated difference |
| 0x0b4cc3b739e1dfe5d73274740e7308b6fb389c5af040c3a174923d928d134bee | Will Jesus Christ return before 2027? | 1 | timestral-5m | 1,231 | -4.6% | 3.499e-05 | 3.899e-04 | worse |
| 0x0b4cc3b739e1dfe5d73274740e7308b6fb389c5af040c3a174923d928d134bee | Will Jesus Christ return before 2027? | 1 | timestral-28m | 1,231 | -0.7% | -8.487e-05 | 1.903e-04 | no demonstrated difference |
| 0x0b4cc3b739e1dfe5d73274740e7308b6fb389c5af040c3a174923d928d134bee | Will Jesus Christ return before 2027? | 1 | timestral-123m | 1,231 | -0.3% | -1.123e-04 | 1.843e-04 | no demonstrated difference |
| 0x0b4cc3b739e1dfe5d73274740e7308b6fb389c5af040c3a174923d928d134bee | Will Jesus Christ return before 2027? | 1 | timestral-209m | 1,231 | +1.2% | -1.716e-04 | 1.045e-04 | no demonstrated difference |
| 0x0b4cc3b739e1dfe5d73274740e7308b6fb389c5af040c3a174923d928d134bee | Will Jesus Christ return before 2027? | 6 | timestral-5m | 1,219 | +2.2% | -6.898e-04 | 1.389e-04 | no demonstrated difference |
| 0x0b4cc3b739e1dfe5d73274740e7308b6fb389c5af040c3a174923d928d134bee | Will Jesus Christ return before 2027? | 6 | timestral-28m | 1,219 | +3.4% | -7.553e-04 | -1.420e-04 | better |
| 0x0b4cc3b739e1dfe5d73274740e7308b6fb389c5af040c3a174923d928d134bee | Will Jesus Christ return before 2027? | 6 | timestral-123m | 1,219 | +2.9% | -7.656e-04 | -3.097e-05 | better |
| 0x0b4cc3b739e1dfe5d73274740e7308b6fb389c5af040c3a174923d928d134bee | Will Jesus Christ return before 2027? | 6 | timestral-209m | 1,219 | +3.7% | -8.409e-04 | -1.664e-04 | better |
| 0x0b4cc3b739e1dfe5d73274740e7308b6fb389c5af040c3a174923d928d134bee | Will Jesus Christ return before 2027? | 24 | timestral-5m | 1,217 | +6.7% | -0.0037 | -5.005e-04 | better |
| 0x0b4cc3b739e1dfe5d73274740e7308b6fb389c5af040c3a174923d928d134bee | Will Jesus Christ return before 2027? | 24 | timestral-28m | 1,217 | +7.6% | -0.0038 | -0.0010 | better |
| 0x0b4cc3b739e1dfe5d73274740e7308b6fb389c5af040c3a174923d928d134bee | Will Jesus Christ return before 2027? | 24 | timestral-123m | 1,217 | +7.8% | -0.0040 | -0.0010 | better |
| 0x0b4cc3b739e1dfe5d73274740e7308b6fb389c5af040c3a174923d928d134bee | Will Jesus Christ return before 2027? | 24 | timestral-209m | 1,217 | +6.7% | -0.0035 | -7.764e-04 | better |
| 0x0e4a0c937b8934c2475613b6322b3f8edc8dedc24762e01e42b0e6f87424a089 | US x Iran permanent peace deal by May 31, 2026? | 1 | timestral-5m | 130 | +0.7% | -0.0039 | 0.0024 | no demonstrated difference |
| 0x0e4a0c937b8934c2475613b6322b3f8edc8dedc24762e01e42b0e6f87424a089 | US x Iran permanent peace deal by May 31, 2026? | 1 | timestral-28m | 130 | +2.3% | -0.0046 | 0.0013 | no demonstrated difference |
| 0x0e4a0c937b8934c2475613b6322b3f8edc8dedc24762e01e42b0e6f87424a089 | US x Iran permanent peace deal by May 31, 2026? | 1 | timestral-123m | 130 | +2.8% | -0.0054 | 9.443e-04 | no demonstrated difference |
| 0x0e4a0c937b8934c2475613b6322b3f8edc8dedc24762e01e42b0e6f87424a089 | US x Iran permanent peace deal by May 31, 2026? | 1 | timestral-209m | 130 | +2.6% | -0.0043 | 0.0010 | no demonstrated difference |
| 0x0e4a0c937b8934c2475613b6322b3f8edc8dedc24762e01e42b0e6f87424a089 | US x Iran permanent peace deal by May 31, 2026? | 6 | timestral-5m | 129 | +2.5% | -0.0155 | 0.0031 | no demonstrated difference |
| 0x0e4a0c937b8934c2475613b6322b3f8edc8dedc24762e01e42b0e6f87424a089 | US x Iran permanent peace deal by May 31, 2026? | 6 | timestral-28m | 129 | +2.5% | -0.0122 | 0.0020 | no demonstrated difference |
| 0x0e4a0c937b8934c2475613b6322b3f8edc8dedc24762e01e42b0e6f87424a089 | US x Iran permanent peace deal by May 31, 2026? | 6 | timestral-123m | 129 | +2.8% | -0.0135 | 0.0017 | no demonstrated difference |
| 0x0e4a0c937b8934c2475613b6322b3f8edc8dedc24762e01e42b0e6f87424a089 | US x Iran permanent peace deal by May 31, 2026? | 6 | timestral-209m | 129 | +2.9% | -0.0143 | 0.0021 | no demonstrated difference |
| 0x0e4a0c937b8934c2475613b6322b3f8edc8dedc24762e01e42b0e6f87424a089 | US x Iran permanent peace deal by May 31, 2026? | 24 | timestral-5m | 126 | +5.7% | -0.0538 | 0.0097 | no demonstrated difference |
| 0x0e4a0c937b8934c2475613b6322b3f8edc8dedc24762e01e42b0e6f87424a089 | US x Iran permanent peace deal by May 31, 2026? | 24 | timestral-28m | 126 | +4.9% | -0.0470 | 0.0100 | no demonstrated difference |
| 0x0e4a0c937b8934c2475613b6322b3f8edc8dedc24762e01e42b0e6f87424a089 | US x Iran permanent peace deal by May 31, 2026? | 24 | timestral-123m | 126 | +5.8% | -0.0530 | 0.0097 | no demonstrated difference |
| 0x0e4a0c937b8934c2475613b6322b3f8edc8dedc24762e01e42b0e6f87424a089 | US x Iran permanent peace deal by May 31, 2026? | 24 | timestral-209m | 126 | +4.8% | -0.0496 | 0.0136 | no demonstrated difference |
| 0x2745c38ff0617cb345c1d2df19b4f74ea777508e07411e88eeb6ab3affcda2a2 | Will Bitcoin dip to $35,000 by December 31, 2026? | 1 | timestral-5m | 1,194 | -4.8% | -1.857e-04 | 9.470e-04 | no demonstrated difference |
| 0x2745c38ff0617cb345c1d2df19b4f74ea777508e07411e88eeb6ab3affcda2a2 | Will Bitcoin dip to $35,000 by December 31, 2026? | 1 | timestral-28m | 1,194 | -1.4% | -4.410e-04 | 5.205e-04 | no demonstrated difference |
| 0x2745c38ff0617cb345c1d2df19b4f74ea777508e07411e88eeb6ab3affcda2a2 | Will Bitcoin dip to $35,000 by December 31, 2026? | 1 | timestral-123m | 1,194 | +0.2% | -7.102e-04 | 4.279e-04 | no demonstrated difference |
| 0x2745c38ff0617cb345c1d2df19b4f74ea777508e07411e88eeb6ab3affcda2a2 | Will Bitcoin dip to $35,000 by December 31, 2026? | 1 | timestral-209m | 1,194 | -0.3% | -4.475e-04 | 3.841e-04 | no demonstrated difference |
| 0x2745c38ff0617cb345c1d2df19b4f74ea777508e07411e88eeb6ab3affcda2a2 | Will Bitcoin dip to $35,000 by December 31, 2026? | 6 | timestral-5m | 1,184 | +1.0% | -0.0012 | 5.548e-04 | no demonstrated difference |
| 0x2745c38ff0617cb345c1d2df19b4f74ea777508e07411e88eeb6ab3affcda2a2 | Will Bitcoin dip to $35,000 by December 31, 2026? | 6 | timestral-28m | 1,184 | +2.1% | -0.0014 | 2.010e-05 | no demonstrated difference |
| 0x2745c38ff0617cb345c1d2df19b4f74ea777508e07411e88eeb6ab3affcda2a2 | Will Bitcoin dip to $35,000 by December 31, 2026? | 6 | timestral-123m | 1,184 | +2.8% | -0.0016 | -2.168e-04 | better |
| 0x2745c38ff0617cb345c1d2df19b4f74ea777508e07411e88eeb6ab3affcda2a2 | Will Bitcoin dip to $35,000 by December 31, 2026? | 6 | timestral-209m | 1,184 | +2.3% | -0.0014 | -5.434e-05 | better |
| 0x2745c38ff0617cb345c1d2df19b4f74ea777508e07411e88eeb6ab3affcda2a2 | Will Bitcoin dip to $35,000 by December 31, 2026? | 24 | timestral-5m | 1,181 | +5.0% | -0.0065 | 2.584e-04 | no demonstrated difference |
| 0x2745c38ff0617cb345c1d2df19b4f74ea777508e07411e88eeb6ab3affcda2a2 | Will Bitcoin dip to $35,000 by December 31, 2026? | 24 | timestral-28m | 1,181 | +5.0% | -0.0061 | -1.344e-05 | better |
| 0x2745c38ff0617cb345c1d2df19b4f74ea777508e07411e88eeb6ab3affcda2a2 | Will Bitcoin dip to $35,000 by December 31, 2026? | 24 | timestral-123m | 1,181 | +6.0% | -0.0070 | -5.571e-04 | better |
| 0x2745c38ff0617cb345c1d2df19b4f74ea777508e07411e88eeb6ab3affcda2a2 | Will Bitcoin dip to $35,000 by December 31, 2026? | 24 | timestral-209m | 1,181 | +5.3% | -0.0064 | -2.027e-04 | better |
| 0x32707ae194389a70f25314ec934851daba12d893da616c492ffe8b655b7759a9 | Will Eleven die in "Stranger Things: Season 5"? | 1 | timestral-5m | 78 | +3.3% | -0.0050 | 9.177e-04 | no demonstrated difference |
| 0x32707ae194389a70f25314ec934851daba12d893da616c492ffe8b655b7759a9 | Will Eleven die in "Stranger Things: Season 5"? | 1 | timestral-28m | 78 | +2.1% | -0.0044 | 0.0012 | no demonstrated difference |
| 0x32707ae194389a70f25314ec934851daba12d893da616c492ffe8b655b7759a9 | Will Eleven die in "Stranger Things: Season 5"? | 1 | timestral-123m | 78 | +3.2% | -0.0053 | 8.857e-04 | no demonstrated difference |
| 0x32707ae194389a70f25314ec934851daba12d893da616c492ffe8b655b7759a9 | Will Eleven die in "Stranger Things: Season 5"? | 1 | timestral-209m | 78 | +4.0% | -0.0064 | 8.979e-04 | no demonstrated difference |
| 0x32707ae194389a70f25314ec934851daba12d893da616c492ffe8b655b7759a9 | Will Eleven die in "Stranger Things: Season 5"? | 6 | timestral-5m | 80 | +4.9% | -0.0166 | 0.0022 | no demonstrated difference |
| 0x32707ae194389a70f25314ec934851daba12d893da616c492ffe8b655b7759a9 | Will Eleven die in "Stranger Things: Season 5"? | 6 | timestral-28m | 80 | +4.1% | -0.0143 | 0.0019 | no demonstrated difference |
| 0x32707ae194389a70f25314ec934851daba12d893da616c492ffe8b655b7759a9 | Will Eleven die in "Stranger Things: Season 5"? | 6 | timestral-123m | 80 | +4.3% | -0.0154 | 0.0032 | no demonstrated difference |
| 0x32707ae194389a70f25314ec934851daba12d893da616c492ffe8b655b7759a9 | Will Eleven die in "Stranger Things: Season 5"? | 6 | timestral-209m | 80 | +5.4% | -0.0180 | 0.0015 | no demonstrated difference |
| 0x32707ae194389a70f25314ec934851daba12d893da616c492ffe8b655b7759a9 | Will Eleven die in "Stranger Things: Season 5"? | 24 | timestral-5m | 77 | +2.5% | -0.0499 | 0.0363 | no demonstrated difference |
| 0x32707ae194389a70f25314ec934851daba12d893da616c492ffe8b655b7759a9 | Will Eleven die in "Stranger Things: Season 5"? | 24 | timestral-28m | 77 | +1.0% | -0.0437 | 0.0385 | no demonstrated difference |
| 0x32707ae194389a70f25314ec934851daba12d893da616c492ffe8b655b7759a9 | Will Eleven die in "Stranger Things: Season 5"? | 24 | timestral-123m | 77 | +1.4% | -0.0477 | 0.0395 | no demonstrated difference |
| 0x32707ae194389a70f25314ec934851daba12d893da616c492ffe8b655b7759a9 | Will Eleven die in "Stranger Things: Season 5"? | 24 | timestral-209m | 77 | +3.5% | -0.0493 | 0.0312 | no demonstrated difference |
| 0x32e869cb0f7316273417ec79aa94c8a139f8c390ebff8a24150a18753d257f8e | Will GameStop acquire eBay? | 1 | timestral-5m | 643 | -38.7% | 5.204e-04 | 0.0011 | worse |
| 0x32e869cb0f7316273417ec79aa94c8a139f8c390ebff8a24150a18753d257f8e | Will GameStop acquire eBay? | 1 | timestral-28m | 643 | -28.0% | 3.489e-04 | 8.229e-04 | worse |
| 0x32e869cb0f7316273417ec79aa94c8a139f8c390ebff8a24150a18753d257f8e | Will GameStop acquire eBay? | 1 | timestral-123m | 643 | -28.5% | 3.631e-04 | 8.638e-04 | worse |
| 0x32e869cb0f7316273417ec79aa94c8a139f8c390ebff8a24150a18753d257f8e | Will GameStop acquire eBay? | 1 | timestral-209m | 643 | -28.1% | 3.507e-04 | 8.376e-04 | worse |
| 0x32e869cb0f7316273417ec79aa94c8a139f8c390ebff8a24150a18753d257f8e | Will GameStop acquire eBay? | 6 | timestral-5m | 624 | -3.3% | -1.553e-05 | 0.0013 | no demonstrated difference |
| 0x32e869cb0f7316273417ec79aa94c8a139f8c390ebff8a24150a18753d257f8e | Will GameStop acquire eBay? | 6 | timestral-28m | 624 | +0.9% | -5.031e-04 | 6.346e-04 | no demonstrated difference |
| 0x32e869cb0f7316273417ec79aa94c8a139f8c390ebff8a24150a18753d257f8e | Will GameStop acquire eBay? | 6 | timestral-123m | 624 | +0.0% | -4.644e-04 | 8.330e-04 | no demonstrated difference |
| 0x32e869cb0f7316273417ec79aa94c8a139f8c390ebff8a24150a18753d257f8e | Will GameStop acquire eBay? | 6 | timestral-209m | 624 | +0.8% | -5.716e-04 | 7.294e-04 | no demonstrated difference |
| 0x32e869cb0f7316273417ec79aa94c8a139f8c390ebff8a24150a18753d257f8e | Will GameStop acquire eBay? | 24 | timestral-5m | 625 | +1.0% | -0.0022 | 0.0024 | no demonstrated difference |
| 0x32e869cb0f7316273417ec79aa94c8a139f8c390ebff8a24150a18753d257f8e | Will GameStop acquire eBay? | 24 | timestral-28m | 625 | +3.7% | -0.0031 | 0.0012 | no demonstrated difference |
| 0x32e869cb0f7316273417ec79aa94c8a139f8c390ebff8a24150a18753d257f8e | Will GameStop acquire eBay? | 24 | timestral-123m | 625 | +3.3% | -0.0031 | 0.0015 | no demonstrated difference |
| 0x32e869cb0f7316273417ec79aa94c8a139f8c390ebff8a24150a18753d257f8e | Will GameStop acquire eBay? | 24 | timestral-209m | 625 | +3.6% | -0.0033 | 0.0013 | no demonstrated difference |
| 0x3488f31e6449f9803f99a8b5dd232c7ad883637f1c86e6953305a2ef19c77f20 | US strikes Iran by February 28, 2026? | 1 | timestral-5m | 16 | +2.1% | – | – | insufficient data |
| 0x3488f31e6449f9803f99a8b5dd232c7ad883637f1c86e6953305a2ef19c77f20 | US strikes Iran by February 28, 2026? | 1 | timestral-28m | 16 | +3.8% | – | – | insufficient data |
| 0x3488f31e6449f9803f99a8b5dd232c7ad883637f1c86e6953305a2ef19c77f20 | US strikes Iran by February 28, 2026? | 1 | timestral-123m | 16 | +3.8% | – | – | insufficient data |
| 0x3488f31e6449f9803f99a8b5dd232c7ad883637f1c86e6953305a2ef19c77f20 | US strikes Iran by February 28, 2026? | 1 | timestral-209m | 16 | +4.3% | – | – | insufficient data |
| 0x3488f31e6449f9803f99a8b5dd232c7ad883637f1c86e6953305a2ef19c77f20 | US strikes Iran by February 28, 2026? | 6 | timestral-5m | 16 | +9.7% | – | – | insufficient data |
| 0x3488f31e6449f9803f99a8b5dd232c7ad883637f1c86e6953305a2ef19c77f20 | US strikes Iran by February 28, 2026? | 6 | timestral-28m | 16 | +3.5% | – | – | insufficient data |
| 0x3488f31e6449f9803f99a8b5dd232c7ad883637f1c86e6953305a2ef19c77f20 | US strikes Iran by February 28, 2026? | 6 | timestral-123m | 16 | +4.1% | – | – | insufficient data |
| 0x3488f31e6449f9803f99a8b5dd232c7ad883637f1c86e6953305a2ef19c77f20 | US strikes Iran by February 28, 2026? | 6 | timestral-209m | 16 | +2.6% | – | – | insufficient data |
| 0x3488f31e6449f9803f99a8b5dd232c7ad883637f1c86e6953305a2ef19c77f20 | US strikes Iran by February 28, 2026? | 24 | timestral-5m | 13 | +9.1% | – | – | insufficient data |
| 0x3488f31e6449f9803f99a8b5dd232c7ad883637f1c86e6953305a2ef19c77f20 | US strikes Iran by February 28, 2026? | 24 | timestral-28m | 13 | -4.5% | – | – | insufficient data |
| 0x3488f31e6449f9803f99a8b5dd232c7ad883637f1c86e6953305a2ef19c77f20 | US strikes Iran by February 28, 2026? | 24 | timestral-123m | 13 | -6.4% | – | – | insufficient data |
| 0x3488f31e6449f9803f99a8b5dd232c7ad883637f1c86e6953305a2ef19c77f20 | US strikes Iran by February 28, 2026? | 24 | timestral-209m | 13 | -5.7% | – | – | insufficient data |
| 0x3733a1b647e7364095736ab0966465d896a84cf3b6bc1695ca1f26c3239b3868 | MicroStrategy sells any Bitcoin by May 31, 2026? | 1 | timestral-5m | 87 | -16.5% | 6.498e-04 | 0.0572 | worse |
| 0x3733a1b647e7364095736ab0966465d896a84cf3b6bc1695ca1f26c3239b3868 | MicroStrategy sells any Bitcoin by May 31, 2026? | 1 | timestral-28m | 87 | -6.8% | -0.0011 | 0.0245 | no demonstrated difference |
| 0x3733a1b647e7364095736ab0966465d896a84cf3b6bc1695ca1f26c3239b3868 | MicroStrategy sells any Bitcoin by May 31, 2026? | 1 | timestral-123m | 87 | -10.5% | 2.131e-05 | 0.0373 | worse |
| 0x3733a1b647e7364095736ab0966465d896a84cf3b6bc1695ca1f26c3239b3868 | MicroStrategy sells any Bitcoin by May 31, 2026? | 1 | timestral-209m | 87 | -6.5% | -0.0027 | 0.0251 | no demonstrated difference |
| 0x3733a1b647e7364095736ab0966465d896a84cf3b6bc1695ca1f26c3239b3868 | MicroStrategy sells any Bitcoin by May 31, 2026? | 6 | timestral-5m | 86 | +4.9% | -0.0611 | 0.0131 | no demonstrated difference |
| 0x3733a1b647e7364095736ab0966465d896a84cf3b6bc1695ca1f26c3239b3868 | MicroStrategy sells any Bitcoin by May 31, 2026? | 6 | timestral-28m | 86 | +4.2% | -0.0463 | 0.0094 | no demonstrated difference |
| 0x3733a1b647e7364095736ab0966465d896a84cf3b6bc1695ca1f26c3239b3868 | MicroStrategy sells any Bitcoin by May 31, 2026? | 6 | timestral-123m | 86 | +3.1% | -0.0434 | 0.0137 | no demonstrated difference |
| 0x3733a1b647e7364095736ab0966465d896a84cf3b6bc1695ca1f26c3239b3868 | MicroStrategy sells any Bitcoin by May 31, 2026? | 6 | timestral-209m | 86 | +3.9% | -0.0458 | 0.0110 | no demonstrated difference |
| 0x3733a1b647e7364095736ab0966465d896a84cf3b6bc1695ca1f26c3239b3868 | MicroStrategy sells any Bitcoin by May 31, 2026? | 24 | timestral-5m | 83 | -1.8% | -0.0824 | 0.0730 | no demonstrated difference |
| 0x3733a1b647e7364095736ab0966465d896a84cf3b6bc1695ca1f26c3239b3868 | MicroStrategy sells any Bitcoin by May 31, 2026? | 24 | timestral-28m | 83 | +0.7% | -0.0799 | 0.0526 | no demonstrated difference |
| 0x3733a1b647e7364095736ab0966465d896a84cf3b6bc1695ca1f26c3239b3868 | MicroStrategy sells any Bitcoin by May 31, 2026? | 24 | timestral-123m | 83 | -1.2% | -0.0777 | 0.0687 | no demonstrated difference |
| 0x3733a1b647e7364095736ab0966465d896a84cf3b6bc1695ca1f26c3239b3868 | MicroStrategy sells any Bitcoin by May 31, 2026? | 24 | timestral-209m | 83 | +0.2% | -0.0782 | 0.0539 | no demonstrated difference |
| 0x377e7fe65cf198a7fc4fdae3f2136b74729279267858daaf96718b23bc2a5607 | Iran leadership change by December 31? | 1 | timestral-5m | 745 | -12.7% | 6.205e-04 | 0.0012 | worse |
| 0x377e7fe65cf198a7fc4fdae3f2136b74729279267858daaf96718b23bc2a5607 | Iran leadership change by December 31? | 1 | timestral-28m | 745 | -7.5% | 3.300e-04 | 7.547e-04 | worse |
| 0x377e7fe65cf198a7fc4fdae3f2136b74729279267858daaf96718b23bc2a5607 | Iran leadership change by December 31? | 1 | timestral-123m | 745 | -6.3% | 2.559e-04 | 6.386e-04 | worse |
| 0x377e7fe65cf198a7fc4fdae3f2136b74729279267858daaf96718b23bc2a5607 | Iran leadership change by December 31? | 1 | timestral-209m | 745 | -5.3% | 1.761e-04 | 5.671e-04 | worse |
| 0x377e7fe65cf198a7fc4fdae3f2136b74729279267858daaf96718b23bc2a5607 | Iran leadership change by December 31? | 6 | timestral-5m | 724 | -0.3% | -5.426e-04 | 0.0010 | no demonstrated difference |
| 0x377e7fe65cf198a7fc4fdae3f2136b74729279267858daaf96718b23bc2a5607 | Iran leadership change by December 31? | 6 | timestral-28m | 724 | +1.7% | -0.0010 | 4.105e-04 | no demonstrated difference |
| 0x377e7fe65cf198a7fc4fdae3f2136b74729279267858daaf96718b23bc2a5607 | Iran leadership change by December 31? | 6 | timestral-123m | 724 | +1.0% | -9.192e-04 | 6.357e-04 | no demonstrated difference |
| 0x377e7fe65cf198a7fc4fdae3f2136b74729279267858daaf96718b23bc2a5607 | Iran leadership change by December 31? | 6 | timestral-209m | 724 | +1.2% | -8.428e-04 | 5.770e-04 | no demonstrated difference |
| 0x377e7fe65cf198a7fc4fdae3f2136b74729279267858daaf96718b23bc2a5607 | Iran leadership change by December 31? | 24 | timestral-5m | 718 | +2.4% | -0.0053 | 0.0025 | no demonstrated difference |
| 0x377e7fe65cf198a7fc4fdae3f2136b74729279267858daaf96718b23bc2a5607 | Iran leadership change by December 31? | 24 | timestral-28m | 718 | +3.4% | -0.0056 | 0.0016 | no demonstrated difference |
| 0x377e7fe65cf198a7fc4fdae3f2136b74729279267858daaf96718b23bc2a5607 | Iran leadership change by December 31? | 24 | timestral-123m | 718 | +3.1% | -0.0054 | 0.0018 | no demonstrated difference |
| 0x377e7fe65cf198a7fc4fdae3f2136b74729279267858daaf96718b23bc2a5607 | Iran leadership change by December 31? | 24 | timestral-209m | 718 | +3.4% | -0.0054 | 0.0015 | no demonstrated difference |
| 0x3b0107a80edd066fe987784d7ab5963c177888433efbec10689951c17320606c | Will Satoshi move any Bitcoin in 2026? | 1 | timestral-5m | 989 | -5.1% | 7.206e-05 | 3.568e-04 | worse |
| 0x3b0107a80edd066fe987784d7ab5963c177888433efbec10689951c17320606c | Will Satoshi move any Bitcoin in 2026? | 1 | timestral-28m | 989 | -2.4% | -1.048e-05 | 2.067e-04 | no demonstrated difference |
| 0x3b0107a80edd066fe987784d7ab5963c177888433efbec10689951c17320606c | Will Satoshi move any Bitcoin in 2026? | 1 | timestral-123m | 989 | -2.5% | -1.651e-05 | 2.211e-04 | no demonstrated difference |
| 0x3b0107a80edd066fe987784d7ab5963c177888433efbec10689951c17320606c | Will Satoshi move any Bitcoin in 2026? | 1 | timestral-209m | 989 | -1.4% | -1.288e-05 | 1.291e-04 | no demonstrated difference |
| 0x3b0107a80edd066fe987784d7ab5963c177888433efbec10689951c17320606c | Will Satoshi move any Bitcoin in 2026? | 6 | timestral-5m | 980 | +4.6% | -0.0013 | -1.549e-04 | better |
| 0x3b0107a80edd066fe987784d7ab5963c177888433efbec10689951c17320606c | Will Satoshi move any Bitcoin in 2026? | 6 | timestral-28m | 980 | +4.2% | -0.0010 | -2.061e-04 | better |
| 0x3b0107a80edd066fe987784d7ab5963c177888433efbec10689951c17320606c | Will Satoshi move any Bitcoin in 2026? | 6 | timestral-123m | 980 | +4.5% | -0.0011 | -2.129e-04 | better |
| 0x3b0107a80edd066fe987784d7ab5963c177888433efbec10689951c17320606c | Will Satoshi move any Bitcoin in 2026? | 6 | timestral-209m | 980 | +4.8% | -0.0011 | -2.493e-04 | better |
| 0x3b0107a80edd066fe987784d7ab5963c177888433efbec10689951c17320606c | Will Satoshi move any Bitcoin in 2026? | 24 | timestral-5m | 975 | +9.2% | -0.0051 | -9.287e-04 | better |
| 0x3b0107a80edd066fe987784d7ab5963c177888433efbec10689951c17320606c | Will Satoshi move any Bitcoin in 2026? | 24 | timestral-28m | 975 | +8.7% | -0.0045 | -0.0011 | better |
| 0x3b0107a80edd066fe987784d7ab5963c177888433efbec10689951c17320606c | Will Satoshi move any Bitcoin in 2026? | 24 | timestral-123m | 975 | +10.2% | -0.0052 | -0.0014 | better |
| 0x3b0107a80edd066fe987784d7ab5963c177888433efbec10689951c17320606c | Will Satoshi move any Bitcoin in 2026? | 24 | timestral-209m | 975 | +8.6% | -0.0044 | -9.646e-04 | better |
| 0x3de0f3d7d7efb40cde68e814d40a0b232832083653c8e78260eb999baa967de0 | US strike on Cuba by December 31? | 1 | timestral-5m | 1,020 | -6.5% | 2.550e-04 | 7.442e-04 | worse |
| 0x3de0f3d7d7efb40cde68e814d40a0b232832083653c8e78260eb999baa967de0 | US strike on Cuba by December 31? | 1 | timestral-28m | 1,020 | -4.9% | 2.023e-04 | 5.578e-04 | worse |
| 0x3de0f3d7d7efb40cde68e814d40a0b232832083653c8e78260eb999baa967de0 | US strike on Cuba by December 31? | 1 | timestral-123m | 1,020 | -2.2% | -7.541e-05 | 4.228e-04 | no demonstrated difference |
| 0x3de0f3d7d7efb40cde68e814d40a0b232832083653c8e78260eb999baa967de0 | US strike on Cuba by December 31? | 1 | timestral-209m | 1,020 | -1.8% | -7.464e-05 | 3.264e-04 | no demonstrated difference |
| 0x3de0f3d7d7efb40cde68e814d40a0b232832083653c8e78260eb999baa967de0 | US strike on Cuba by December 31? | 6 | timestral-5m | 1,015 | -0.5% | -4.667e-04 | 7.413e-04 | no demonstrated difference |
| 0x3de0f3d7d7efb40cde68e814d40a0b232832083653c8e78260eb999baa967de0 | US strike on Cuba by December 31? | 6 | timestral-28m | 1,015 | +1.1% | -8.572e-04 | 3.468e-04 | no demonstrated difference |
| 0x3de0f3d7d7efb40cde68e814d40a0b232832083653c8e78260eb999baa967de0 | US strike on Cuba by December 31? | 6 | timestral-123m | 1,015 | +1.1% | -8.995e-04 | 3.871e-04 | no demonstrated difference |
| 0x3de0f3d7d7efb40cde68e814d40a0b232832083653c8e78260eb999baa967de0 | US strike on Cuba by December 31? | 6 | timestral-209m | 1,015 | +1.9% | -0.0010 | 1.302e-04 | no demonstrated difference |
| 0x3de0f3d7d7efb40cde68e814d40a0b232832083653c8e78260eb999baa967de0 | US strike on Cuba by December 31? | 24 | timestral-5m | 1,014 | +2.9% | -0.0043 | 0.0013 | no demonstrated difference |
| 0x3de0f3d7d7efb40cde68e814d40a0b232832083653c8e78260eb999baa967de0 | US strike on Cuba by December 31? | 24 | timestral-28m | 1,014 | +4.4% | -0.0050 | 2.398e-04 | no demonstrated difference |
| 0x3de0f3d7d7efb40cde68e814d40a0b232832083653c8e78260eb999baa967de0 | US strike on Cuba by December 31? | 24 | timestral-123m | 1,014 | +4.2% | -0.0050 | 5.931e-04 | no demonstrated difference |
| 0x3de0f3d7d7efb40cde68e814d40a0b232832083653c8e78260eb999baa967de0 | US strike on Cuba by December 31? | 24 | timestral-209m | 1,014 | +4.3% | -0.0050 | 3.519e-04 | no demonstrated difference |
| 0x405b56fc75f56d7635a94df9836d6cb6f9b9571d1fd33eb165c1e59d1d11801f | Strait of Hormuz traffic returns to normal by October 31? | 1 | timestral-5m | 265 | -8.7% | 8.841e-04 | 0.0035 | worse |
| 0x405b56fc75f56d7635a94df9836d6cb6f9b9571d1fd33eb165c1e59d1d11801f | Strait of Hormuz traffic returns to normal by October 31? | 1 | timestral-28m | 265 | -3.9% | -2.612e-04 | 0.0020 | no demonstrated difference |
| 0x405b56fc75f56d7635a94df9836d6cb6f9b9571d1fd33eb165c1e59d1d11801f | Strait of Hormuz traffic returns to normal by October 31? | 1 | timestral-123m | 265 | -2.6% | -5.227e-04 | 0.0018 | no demonstrated difference |
| 0x405b56fc75f56d7635a94df9836d6cb6f9b9571d1fd33eb165c1e59d1d11801f | Strait of Hormuz traffic returns to normal by October 31? | 1 | timestral-209m | 265 | -1.3% | -6.253e-04 | 0.0012 | no demonstrated difference |
| 0x405b56fc75f56d7635a94df9836d6cb6f9b9571d1fd33eb165c1e59d1d11801f | Strait of Hormuz traffic returns to normal by October 31? | 6 | timestral-5m | 254 | -1.1% | -0.0027 | 0.0037 | no demonstrated difference |
| 0x405b56fc75f56d7635a94df9836d6cb6f9b9571d1fd33eb165c1e59d1d11801f | Strait of Hormuz traffic returns to normal by October 31? | 6 | timestral-28m | 254 | -0.9% | -0.0027 | 0.0033 | no demonstrated difference |
| 0x405b56fc75f56d7635a94df9836d6cb6f9b9571d1fd33eb165c1e59d1d11801f | Strait of Hormuz traffic returns to normal by October 31? | 6 | timestral-123m | 254 | -0.9% | -0.0029 | 0.0035 | no demonstrated difference |
| 0x405b56fc75f56d7635a94df9836d6cb6f9b9571d1fd33eb165c1e59d1d11801f | Strait of Hormuz traffic returns to normal by October 31? | 6 | timestral-209m | 254 | -1.0% | -0.0029 | 0.0036 | no demonstrated difference |
| 0x405b56fc75f56d7635a94df9836d6cb6f9b9571d1fd33eb165c1e59d1d11801f | Strait of Hormuz traffic returns to normal by October 31? | 24 | timestral-5m | 252 | -2.5% | -0.0110 | 0.0147 | no demonstrated difference |
| 0x405b56fc75f56d7635a94df9836d6cb6f9b9571d1fd33eb165c1e59d1d11801f | Strait of Hormuz traffic returns to normal by October 31? | 24 | timestral-28m | 252 | -0.1% | -0.0139 | 0.0117 | no demonstrated difference |
| 0x405b56fc75f56d7635a94df9836d6cb6f9b9571d1fd33eb165c1e59d1d11801f | Strait of Hormuz traffic returns to normal by October 31? | 24 | timestral-123m | 252 | -2.5% | -0.0123 | 0.0159 | no demonstrated difference |
| 0x405b56fc75f56d7635a94df9836d6cb6f9b9571d1fd33eb165c1e59d1d11801f | Strait of Hormuz traffic returns to normal by October 31? | 24 | timestral-209m | 252 | -1.3% | -0.0126 | 0.0123 | no demonstrated difference |
| 0x43ec78527bd98a0588dd9455685b2cc82f5743140cb3a154603dc03c02b57de5 | US government shutdown Saturday? | 1 | timestral-5m | 280 | -4.5% | -9.853e-05 | 0.0017 | no demonstrated difference |
| 0x43ec78527bd98a0588dd9455685b2cc82f5743140cb3a154603dc03c02b57de5 | US government shutdown Saturday? | 1 | timestral-28m | 280 | -1.8% | -9.381e-04 | 0.0012 | no demonstrated difference |
| 0x43ec78527bd98a0588dd9455685b2cc82f5743140cb3a154603dc03c02b57de5 | US government shutdown Saturday? | 1 | timestral-123m | 280 | -0.4% | -0.0011 | 9.995e-04 | no demonstrated difference |
| 0x43ec78527bd98a0588dd9455685b2cc82f5743140cb3a154603dc03c02b57de5 | US government shutdown Saturday? | 1 | timestral-209m | 280 | -2.1% | -6.784e-04 | 0.0011 | no demonstrated difference |
| 0x43ec78527bd98a0588dd9455685b2cc82f5743140cb3a154603dc03c02b57de5 | US government shutdown Saturday? | 6 | timestral-5m | 285 | +2.6% | -0.0057 | 0.0014 | no demonstrated difference |
| 0x43ec78527bd98a0588dd9455685b2cc82f5743140cb3a154603dc03c02b57de5 | US government shutdown Saturday? | 6 | timestral-28m | 285 | +4.0% | -0.0064 | 6.156e-04 | no demonstrated difference |
| 0x43ec78527bd98a0588dd9455685b2cc82f5743140cb3a154603dc03c02b57de5 | US government shutdown Saturday? | 6 | timestral-123m | 285 | +4.2% | -0.0066 | 3.370e-04 | no demonstrated difference |
| 0x43ec78527bd98a0588dd9455685b2cc82f5743140cb3a154603dc03c02b57de5 | US government shutdown Saturday? | 6 | timestral-209m | 285 | +2.8% | -0.0051 | 7.224e-04 | no demonstrated difference |
| 0x43ec78527bd98a0588dd9455685b2cc82f5743140cb3a154603dc03c02b57de5 | US government shutdown Saturday? | 24 | timestral-5m | 282 | +4.6% | -0.0171 | 0.0043 | no demonstrated difference |
| 0x43ec78527bd98a0588dd9455685b2cc82f5743140cb3a154603dc03c02b57de5 | US government shutdown Saturday? | 24 | timestral-28m | 282 | +4.6% | -0.0168 | 0.0041 | no demonstrated difference |
| 0x43ec78527bd98a0588dd9455685b2cc82f5743140cb3a154603dc03c02b57de5 | US government shutdown Saturday? | 24 | timestral-123m | 282 | +5.2% | -0.0178 | 0.0032 | no demonstrated difference |
| 0x43ec78527bd98a0588dd9455685b2cc82f5743140cb3a154603dc03c02b57de5 | US government shutdown Saturday? | 24 | timestral-209m | 282 | +4.2% | -0.0170 | 0.0042 | no demonstrated difference |
| 0x46ca741da4abd7ffa993f59ac65bfe83de43ae027accac71d263a493e44064e7 | US announces end of Iranian blockade by December 31, 2026? | 1 | timestral-5m | 340 | +2.1% | -8.953e-04 | 2.063e-04 | no demonstrated difference |
| 0x46ca741da4abd7ffa993f59ac65bfe83de43ae027accac71d263a493e44064e7 | US announces end of Iranian blockade by December 31, 2026? | 1 | timestral-28m | 340 | +4.3% | -0.0013 | -1.976e-04 | better |
| 0x46ca741da4abd7ffa993f59ac65bfe83de43ae027accac71d263a493e44064e7 | US announces end of Iranian blockade by December 31, 2026? | 1 | timestral-123m | 340 | +4.2% | -0.0013 | -2.171e-04 | better |
| 0x46ca741da4abd7ffa993f59ac65bfe83de43ae027accac71d263a493e44064e7 | US announces end of Iranian blockade by December 31, 2026? | 1 | timestral-209m | 340 | +4.7% | -0.0014 | -2.657e-04 | better |
| 0x46ca741da4abd7ffa993f59ac65bfe83de43ae027accac71d263a493e44064e7 | US announces end of Iranian blockade by December 31, 2026? | 6 | timestral-5m | 336 | +2.5% | -0.0027 | 1.537e-04 | no demonstrated difference |
| 0x46ca741da4abd7ffa993f59ac65bfe83de43ae027accac71d263a493e44064e7 | US announces end of Iranian blockade by December 31, 2026? | 6 | timestral-28m | 336 | +3.3% | -0.0031 | -3.567e-04 | better |
| 0x46ca741da4abd7ffa993f59ac65bfe83de43ae027accac71d263a493e44064e7 | US announces end of Iranian blockade by December 31, 2026? | 6 | timestral-123m | 336 | +3.1% | -0.0033 | 2.211e-04 | no demonstrated difference |
| 0x46ca741da4abd7ffa993f59ac65bfe83de43ae027accac71d263a493e44064e7 | US announces end of Iranian blockade by December 31, 2026? | 6 | timestral-209m | 336 | +2.6% | -0.0029 | 4.913e-04 | no demonstrated difference |
| 0x46ca741da4abd7ffa993f59ac65bfe83de43ae027accac71d263a493e44064e7 | US announces end of Iranian blockade by December 31, 2026? | 24 | timestral-5m | 336 | +1.5% | -0.0115 | 0.0052 | no demonstrated difference |
| 0x46ca741da4abd7ffa993f59ac65bfe83de43ae027accac71d263a493e44064e7 | US announces end of Iranian blockade by December 31, 2026? | 24 | timestral-28m | 336 | +2.9% | -0.0108 | 0.0025 | no demonstrated difference |
| 0x46ca741da4abd7ffa993f59ac65bfe83de43ae027accac71d263a493e44064e7 | US announces end of Iranian blockade by December 31, 2026? | 24 | timestral-123m | 336 | +2.4% | -0.0102 | 0.0032 | no demonstrated difference |
| 0x46ca741da4abd7ffa993f59ac65bfe83de43ae027accac71d263a493e44064e7 | US announces end of Iranian blockade by December 31, 2026? | 24 | timestral-209m | 336 | +2.7% | -0.0104 | 0.0033 | no demonstrated difference |
| 0x48b0b0bca515f68fccf95af4793dbd0edbfec1f8ec6e8df2c0f69ba74f8c4722 | Trump out as President before 2027? | 1 | timestral-5m | 1,313 | -5.9% | 2.197e-04 | 6.331e-04 | worse |
| 0x48b0b0bca515f68fccf95af4793dbd0edbfec1f8ec6e8df2c0f69ba74f8c4722 | Trump out as President before 2027? | 1 | timestral-28m | 1,313 | -2.8% | -2.316e-05 | 3.991e-04 | no demonstrated difference |
| 0x48b0b0bca515f68fccf95af4793dbd0edbfec1f8ec6e8df2c0f69ba74f8c4722 | Trump out as President before 2027? | 1 | timestral-123m | 1,313 | -2.4% | -3.479e-05 | 3.469e-04 | no demonstrated difference |
| 0x48b0b0bca515f68fccf95af4793dbd0edbfec1f8ec6e8df2c0f69ba74f8c4722 | Trump out as President before 2027? | 1 | timestral-209m | 1,313 | -2.4% | -2.454e-05 | 3.600e-04 | no demonstrated difference |
| 0x48b0b0bca515f68fccf95af4793dbd0edbfec1f8ec6e8df2c0f69ba74f8c4722 | Trump out as President before 2027? | 6 | timestral-5m | 1,286 | +1.8% | -0.0013 | 3.371e-04 | no demonstrated difference |
| 0x48b0b0bca515f68fccf95af4793dbd0edbfec1f8ec6e8df2c0f69ba74f8c4722 | Trump out as President before 2027? | 6 | timestral-28m | 1,286 | +2.8% | -0.0014 | 1.384e-05 | no demonstrated difference |
| 0x48b0b0bca515f68fccf95af4793dbd0edbfec1f8ec6e8df2c0f69ba74f8c4722 | Trump out as President before 2027? | 6 | timestral-123m | 1,286 | +3.2% | -0.0015 | -1.067e-04 | better |
| 0x48b0b0bca515f68fccf95af4793dbd0edbfec1f8ec6e8df2c0f69ba74f8c4722 | Trump out as President before 2027? | 6 | timestral-209m | 1,286 | +3.6% | -0.0015 | -1.275e-04 | better |
| 0x48b0b0bca515f68fccf95af4793dbd0edbfec1f8ec6e8df2c0f69ba74f8c4722 | Trump out as President before 2027? | 24 | timestral-5m | 1,282 | +4.8% | -0.0041 | -3.890e-04 | better |
| 0x48b0b0bca515f68fccf95af4793dbd0edbfec1f8ec6e8df2c0f69ba74f8c4722 | Trump out as President before 2027? | 24 | timestral-28m | 1,282 | +6.3% | -0.0046 | -0.0011 | better |
| 0x48b0b0bca515f68fccf95af4793dbd0edbfec1f8ec6e8df2c0f69ba74f8c4722 | Trump out as President before 2027? | 24 | timestral-123m | 1,282 | +6.4% | -0.0047 | -0.0011 | better |
| 0x48b0b0bca515f68fccf95af4793dbd0edbfec1f8ec6e8df2c0f69ba74f8c4722 | Trump out as President before 2027? | 24 | timestral-209m | 1,282 | +6.2% | -0.0045 | -0.0010 | better |
| 0x4c80df6f557bb0b9de08c0301ebdce500dd9bdc58400d9269fb8fab1709ed584 | China x Taiwan military clash before 2027? | 1 | timestral-5m | 1,160 | -6.8% | 9.748e-05 | 8.468e-04 | worse |
| 0x4c80df6f557bb0b9de08c0301ebdce500dd9bdc58400d9269fb8fab1709ed584 | China x Taiwan military clash before 2027? | 1 | timestral-28m | 1,160 | -2.2% | -1.902e-04 | 4.511e-04 | no demonstrated difference |
| 0x4c80df6f557bb0b9de08c0301ebdce500dd9bdc58400d9269fb8fab1709ed584 | China x Taiwan military clash before 2027? | 1 | timestral-123m | 1,160 | -0.4% | -3.891e-04 | 3.730e-04 | no demonstrated difference |
| 0x4c80df6f557bb0b9de08c0301ebdce500dd9bdc58400d9269fb8fab1709ed584 | China x Taiwan military clash before 2027? | 1 | timestral-209m | 1,160 | -1.7% | -2.018e-04 | 4.172e-04 | no demonstrated difference |
| 0x4c80df6f557bb0b9de08c0301ebdce500dd9bdc58400d9269fb8fab1709ed584 | China x Taiwan military clash before 2027? | 6 | timestral-5m | 1,123 | +3.3% | -0.0021 | -6.640e-05 | better |
| 0x4c80df6f557bb0b9de08c0301ebdce500dd9bdc58400d9269fb8fab1709ed584 | China x Taiwan military clash before 2027? | 6 | timestral-28m | 1,123 | +4.0% | -0.0021 | -4.038e-04 | better |
| 0x4c80df6f557bb0b9de08c0301ebdce500dd9bdc58400d9269fb8fab1709ed584 | China x Taiwan military clash before 2027? | 6 | timestral-123m | 1,123 | +4.4% | -0.0024 | -4.540e-04 | better |
| 0x4c80df6f557bb0b9de08c0301ebdce500dd9bdc58400d9269fb8fab1709ed584 | China x Taiwan military clash before 2027? | 6 | timestral-209m | 1,123 | +3.5% | -0.0019 | -3.383e-04 | better |
| 0x4c80df6f557bb0b9de08c0301ebdce500dd9bdc58400d9269fb8fab1709ed584 | China x Taiwan military clash before 2027? | 24 | timestral-5m | 1,120 | +9.3% | -0.0081 | -0.0029 | better |
| 0x4c80df6f557bb0b9de08c0301ebdce500dd9bdc58400d9269fb8fab1709ed584 | China x Taiwan military clash before 2027? | 24 | timestral-28m | 1,120 | +9.3% | -0.0079 | -0.0032 | better |
| 0x4c80df6f557bb0b9de08c0301ebdce500dd9bdc58400d9269fb8fab1709ed584 | China x Taiwan military clash before 2027? | 24 | timestral-123m | 1,120 | +10.0% | -0.0083 | -0.0036 | better |
| 0x4c80df6f557bb0b9de08c0301ebdce500dd9bdc58400d9269fb8fab1709ed584 | China x Taiwan military clash before 2027? | 24 | timestral-209m | 1,120 | +8.9% | -0.0077 | -0.0030 | better |
| 0x51f624dbbf14f9edb575fef1be6f7a303751de70783fa144fce27b957452c803 | Zelenskyy out as Ukraine president by end of 2026? | 1 | timestral-5m | 1,660 | -9.5% | 4.721e-04 | 7.682e-04 | worse |
| 0x51f624dbbf14f9edb575fef1be6f7a303751de70783fa144fce27b957452c803 | Zelenskyy out as Ukraine president by end of 2026? | 1 | timestral-28m | 1,660 | -5.3% | 2.350e-04 | 4.513e-04 | worse |
| 0x51f624dbbf14f9edb575fef1be6f7a303751de70783fa144fce27b957452c803 | Zelenskyy out as Ukraine president by end of 2026? | 1 | timestral-123m | 1,660 | -4.9% | 1.772e-04 | 4.555e-04 | worse |
| 0x51f624dbbf14f9edb575fef1be6f7a303751de70783fa144fce27b957452c803 | Zelenskyy out as Ukraine president by end of 2026? | 1 | timestral-209m | 1,660 | -4.2% | 1.579e-04 | 3.980e-04 | worse |
| 0x51f624dbbf14f9edb575fef1be6f7a303751de70783fa144fce27b957452c803 | Zelenskyy out as Ukraine president by end of 2026? | 6 | timestral-5m | 1,645 | +0.3% | -5.446e-04 | 3.718e-04 | no demonstrated difference |
| 0x51f624dbbf14f9edb575fef1be6f7a303751de70783fa144fce27b957452c803 | Zelenskyy out as Ukraine president by end of 2026? | 6 | timestral-28m | 1,645 | +1.4% | -7.700e-04 | 9.540e-05 | no demonstrated difference |
| 0x51f624dbbf14f9edb575fef1be6f7a303751de70783fa144fce27b957452c803 | Zelenskyy out as Ukraine president by end of 2026? | 6 | timestral-123m | 1,645 | +2.2% | -9.481e-04 | -6.028e-05 | better |
| 0x51f624dbbf14f9edb575fef1be6f7a303751de70783fa144fce27b957452c803 | Zelenskyy out as Ukraine president by end of 2026? | 6 | timestral-209m | 1,645 | +1.9% | -8.456e-04 | -3.431e-05 | better |
| 0x51f624dbbf14f9edb575fef1be6f7a303751de70783fa144fce27b957452c803 | Zelenskyy out as Ukraine president by end of 2026? | 24 | timestral-5m | 1,646 | +3.5% | -0.0036 | 1.520e-04 | no demonstrated difference |
| 0x51f624dbbf14f9edb575fef1be6f7a303751de70783fa144fce27b957452c803 | Zelenskyy out as Ukraine president by end of 2026? | 24 | timestral-28m | 1,646 | +4.4% | -0.0039 | -3.361e-04 | better |
| 0x51f624dbbf14f9edb575fef1be6f7a303751de70783fa144fce27b957452c803 | Zelenskyy out as Ukraine president by end of 2026? | 24 | timestral-123m | 1,646 | +4.5% | -0.0042 | -1.481e-04 | better |
| 0x51f624dbbf14f9edb575fef1be6f7a303751de70783fa144fce27b957452c803 | Zelenskyy out as Ukraine president by end of 2026? | 24 | timestral-209m | 1,646 | +4.7% | -0.0042 | -4.077e-04 | better |
| 0x5c79dfde05559b79a9cb9f7c4187e4d49632dd042572ae676952f812732591cc | Strait of Hormuz traffic returns to normal by December 31? | 1 | timestral-5m | 645 | -3.5% | -6.258e-05 | 9.857e-04 | no demonstrated difference |
| 0x5c79dfde05559b79a9cb9f7c4187e4d49632dd042572ae676952f812732591cc | Strait of Hormuz traffic returns to normal by December 31? | 1 | timestral-28m | 645 | -1.5% | -2.420e-04 | 6.292e-04 | no demonstrated difference |
| 0x5c79dfde05559b79a9cb9f7c4187e4d49632dd042572ae676952f812732591cc | Strait of Hormuz traffic returns to normal by December 31? | 1 | timestral-123m | 645 | +0.8% | -5.950e-04 | 3.380e-04 | no demonstrated difference |
| 0x5c79dfde05559b79a9cb9f7c4187e4d49632dd042572ae676952f812732591cc | Strait of Hormuz traffic returns to normal by December 31? | 1 | timestral-209m | 645 | +0.5% | -4.741e-04 | 3.089e-04 | no demonstrated difference |
| 0x5c79dfde05559b79a9cb9f7c4187e4d49632dd042572ae676952f812732591cc | Strait of Hormuz traffic returns to normal by December 31? | 6 | timestral-5m | 638 | -0.3% | -8.481e-04 | 0.0010 | no demonstrated difference |
| 0x5c79dfde05559b79a9cb9f7c4187e4d49632dd042572ae676952f812732591cc | Strait of Hormuz traffic returns to normal by December 31? | 6 | timestral-28m | 638 | +1.7% | -0.0016 | 1.332e-04 | no demonstrated difference |
| 0x5c79dfde05559b79a9cb9f7c4187e4d49632dd042572ae676952f812732591cc | Strait of Hormuz traffic returns to normal by December 31? | 6 | timestral-123m | 638 | +2.1% | -0.0017 | 3.809e-06 | no demonstrated difference |
| 0x5c79dfde05559b79a9cb9f7c4187e4d49632dd042572ae676952f812732591cc | Strait of Hormuz traffic returns to normal by December 31? | 6 | timestral-209m | 638 | +1.8% | -0.0015 | 7.273e-05 | no demonstrated difference |
| 0x5c79dfde05559b79a9cb9f7c4187e4d49632dd042572ae676952f812732591cc | Strait of Hormuz traffic returns to normal by December 31? | 24 | timestral-5m | 638 | -3.1% | -0.0029 | 0.0083 | no demonstrated difference |
| 0x5c79dfde05559b79a9cb9f7c4187e4d49632dd042572ae676952f812732591cc | Strait of Hormuz traffic returns to normal by December 31? | 24 | timestral-28m | 638 | +0.6% | -0.0053 | 0.0043 | no demonstrated difference |
| 0x5c79dfde05559b79a9cb9f7c4187e4d49632dd042572ae676952f812732591cc | Strait of Hormuz traffic returns to normal by December 31? | 24 | timestral-123m | 638 | +0.6% | -0.0055 | 0.0047 | no demonstrated difference |
| 0x5c79dfde05559b79a9cb9f7c4187e4d49632dd042572ae676952f812732591cc | Strait of Hormuz traffic returns to normal by December 31? | 24 | timestral-209m | 638 | +0.7% | -0.0051 | 0.0040 | no demonstrated difference |
| 0x5db999fad322cea2914535aae5517060c3f80ad6d8c0231cde2124a434d16846 | Will the U.S. invade Iran before 2027? | 1 | timestral-5m | 1,373 | -3.9% | 8.130e-05 | 8.656e-04 | worse |
| 0x5db999fad322cea2914535aae5517060c3f80ad6d8c0231cde2124a434d16846 | Will the U.S. invade Iran before 2027? | 1 | timestral-28m | 1,373 | -1.0% | -2.132e-04 | 4.441e-04 | no demonstrated difference |
| 0x5db999fad322cea2914535aae5517060c3f80ad6d8c0231cde2124a434d16846 | Will the U.S. invade Iran before 2027? | 1 | timestral-123m | 1,373 | +0.2% | -3.654e-04 | 3.040e-04 | no demonstrated difference |
| 0x5db999fad322cea2914535aae5517060c3f80ad6d8c0231cde2124a434d16846 | Will the U.S. invade Iran before 2027? | 1 | timestral-209m | 1,373 | +0.4% | -3.016e-04 | 2.150e-04 | no demonstrated difference |
| 0x5db999fad322cea2914535aae5517060c3f80ad6d8c0231cde2124a434d16846 | Will the U.S. invade Iran before 2027? | 6 | timestral-5m | 1,372 | +1.1% | -0.0014 | 4.866e-04 | no demonstrated difference |
| 0x5db999fad322cea2914535aae5517060c3f80ad6d8c0231cde2124a434d16846 | Will the U.S. invade Iran before 2027? | 6 | timestral-28m | 1,372 | +1.9% | -0.0015 | 2.861e-05 | no demonstrated difference |
| 0x5db999fad322cea2914535aae5517060c3f80ad6d8c0231cde2124a434d16846 | Will the U.S. invade Iran before 2027? | 6 | timestral-123m | 1,372 | +2.6% | -0.0017 | -3.054e-04 | better |
| 0x5db999fad322cea2914535aae5517060c3f80ad6d8c0231cde2124a434d16846 | Will the U.S. invade Iran before 2027? | 6 | timestral-209m | 1,372 | +2.6% | -0.0016 | -3.399e-04 | better |
| 0x5db999fad322cea2914535aae5517060c3f80ad6d8c0231cde2124a434d16846 | Will the U.S. invade Iran before 2027? | 24 | timestral-5m | 1,371 | +2.8% | -0.0048 | 8.054e-04 | no demonstrated difference |
| 0x5db999fad322cea2914535aae5517060c3f80ad6d8c0231cde2124a434d16846 | Will the U.S. invade Iran before 2027? | 24 | timestral-28m | 1,371 | +3.9% | -0.0053 | -5.544e-04 | better |
| 0x5db999fad322cea2914535aae5517060c3f80ad6d8c0231cde2124a434d16846 | Will the U.S. invade Iran before 2027? | 24 | timestral-123m | 1,371 | +4.6% | -0.0059 | -9.994e-04 | better |
| 0x5db999fad322cea2914535aae5517060c3f80ad6d8c0231cde2124a434d16846 | Will the U.S. invade Iran before 2027? | 24 | timestral-209m | 1,371 | +4.1% | -0.0053 | -8.462e-04 | better |
| 0x6bd56627aa21311850825edb27e53434a0e17a4f782be0086bc07f71eee00d0d | Putin out as President of Russia by December 31, 2026? | 1 | timestral-5m | 1,844 | -4.3% | -2.763e-06 | 4.972e-04 | no demonstrated difference |
| 0x6bd56627aa21311850825edb27e53434a0e17a4f782be0086bc07f71eee00d0d | Putin out as President of Russia by December 31, 2026? | 1 | timestral-28m | 1,844 | -1.4% | -1.578e-04 | 2.723e-04 | no demonstrated difference |
| 0x6bd56627aa21311850825edb27e53434a0e17a4f782be0086bc07f71eee00d0d | Putin out as President of Russia by December 31, 2026? | 1 | timestral-123m | 1,844 | -0.0% | -3.097e-04 | 2.292e-04 | no demonstrated difference |
| 0x6bd56627aa21311850825edb27e53434a0e17a4f782be0086bc07f71eee00d0d | Putin out as President of Russia by December 31, 2026? | 1 | timestral-209m | 1,844 | -0.5% | -2.096e-04 | 2.106e-04 | no demonstrated difference |
| 0x6bd56627aa21311850825edb27e53434a0e17a4f782be0086bc07f71eee00d0d | Putin out as President of Russia by December 31, 2026? | 6 | timestral-5m | 1,835 | +3.4% | -0.0013 | 4.191e-06 | no demonstrated difference |
| 0x6bd56627aa21311850825edb27e53434a0e17a4f782be0086bc07f71eee00d0d | Putin out as President of Russia by December 31, 2026? | 6 | timestral-28m | 1,835 | +4.4% | -0.0014 | -3.153e-04 | better |
| 0x6bd56627aa21311850825edb27e53434a0e17a4f782be0086bc07f71eee00d0d | Putin out as President of Russia by December 31, 2026? | 6 | timestral-123m | 1,835 | +5.3% | -0.0017 | -4.402e-04 | better |
| 0x6bd56627aa21311850825edb27e53434a0e17a4f782be0086bc07f71eee00d0d | Putin out as President of Russia by December 31, 2026? | 6 | timestral-209m | 1,835 | +4.9% | -0.0015 | -4.113e-04 | better |
| 0x6bd56627aa21311850825edb27e53434a0e17a4f782be0086bc07f71eee00d0d | Putin out as President of Russia by December 31, 2026? | 24 | timestral-5m | 1,832 | +7.0% | -0.0045 | -9.032e-04 | better |
| 0x6bd56627aa21311850825edb27e53434a0e17a4f782be0086bc07f71eee00d0d | Putin out as President of Russia by December 31, 2026? | 24 | timestral-28m | 1,832 | +7.5% | -0.0044 | -0.0014 | better |
| 0x6bd56627aa21311850825edb27e53434a0e17a4f782be0086bc07f71eee00d0d | Putin out as President of Russia by December 31, 2026? | 24 | timestral-123m | 1,832 | +8.1% | -0.0048 | -0.0016 | better |
| 0x6bd56627aa21311850825edb27e53434a0e17a4f782be0086bc07f71eee00d0d | Putin out as President of Russia by December 31, 2026? | 24 | timestral-209m | 1,832 | +7.6% | -0.0046 | -0.0014 | better |
| 0x6d0e09d0f04572d9b1adad84703458b0297bc5603b69dccbde93147ee4443246 | US forces enter Iran by April 30? | 1 | timestral-5m | 12 | -6.1% | – | – | insufficient data |
| 0x6d0e09d0f04572d9b1adad84703458b0297bc5603b69dccbde93147ee4443246 | US forces enter Iran by April 30? | 1 | timestral-28m | 12 | +5.1% | – | – | insufficient data |
| 0x6d0e09d0f04572d9b1adad84703458b0297bc5603b69dccbde93147ee4443246 | US forces enter Iran by April 30? | 1 | timestral-123m | 12 | +1.8% | – | – | insufficient data |
| 0x6d0e09d0f04572d9b1adad84703458b0297bc5603b69dccbde93147ee4443246 | US forces enter Iran by April 30? | 1 | timestral-209m | 12 | -0.9% | – | – | insufficient data |
| 0x6d0e09d0f04572d9b1adad84703458b0297bc5603b69dccbde93147ee4443246 | US forces enter Iran by April 30? | 6 | timestral-5m | 8 | +4.1% | – | – | insufficient data |
| 0x6d0e09d0f04572d9b1adad84703458b0297bc5603b69dccbde93147ee4443246 | US forces enter Iran by April 30? | 6 | timestral-28m | 8 | +7.1% | – | – | insufficient data |
| 0x6d0e09d0f04572d9b1adad84703458b0297bc5603b69dccbde93147ee4443246 | US forces enter Iran by April 30? | 6 | timestral-123m | 8 | +6.7% | – | – | insufficient data |
| 0x6d0e09d0f04572d9b1adad84703458b0297bc5603b69dccbde93147ee4443246 | US forces enter Iran by April 30? | 6 | timestral-209m | 8 | +11.0% | – | – | insufficient data |
| 0x6d0e09d0f04572d9b1adad84703458b0297bc5603b69dccbde93147ee4443246 | US forces enter Iran by April 30? | 24 | timestral-5m | 7 | +4.7% | – | – | insufficient data |
| 0x6d0e09d0f04572d9b1adad84703458b0297bc5603b69dccbde93147ee4443246 | US forces enter Iran by April 30? | 24 | timestral-28m | 7 | +7.7% | – | – | insufficient data |
| 0x6d0e09d0f04572d9b1adad84703458b0297bc5603b69dccbde93147ee4443246 | US forces enter Iran by April 30? | 24 | timestral-123m | 7 | +6.2% | – | – | insufficient data |
| 0x6d0e09d0f04572d9b1adad84703458b0297bc5603b69dccbde93147ee4443246 | US forces enter Iran by April 30? | 24 | timestral-209m | 7 | +7.3% | – | – | insufficient data |
| 0x6fefc0438c7598b23531457c8c60541990d0786bd4bd9dfc3eabc8d95c291092 | Will Bitcoin reach $250,000 by December 31, 2026? | 1 | timestral-5m | 1,008 | -11.5% | 1.475e-04 | 7.344e-04 | worse |
| 0x6fefc0438c7598b23531457c8c60541990d0786bd4bd9dfc3eabc8d95c291092 | Will Bitcoin reach $250,000 by December 31, 2026? | 1 | timestral-28m | 1,008 | -8.1% | 8.010e-06 | 5.572e-04 | worse |
| 0x6fefc0438c7598b23531457c8c60541990d0786bd4bd9dfc3eabc8d95c291092 | Will Bitcoin reach $250,000 by December 31, 2026? | 1 | timestral-123m | 1,008 | -5.4% | -7.929e-05 | 4.122e-04 | no demonstrated difference |
| 0x6fefc0438c7598b23531457c8c60541990d0786bd4bd9dfc3eabc8d95c291092 | Will Bitcoin reach $250,000 by December 31, 2026? | 1 | timestral-209m | 1,008 | -6.6% | -3.536e-05 | 4.763e-04 | no demonstrated difference |
| 0x6fefc0438c7598b23531457c8c60541990d0786bd4bd9dfc3eabc8d95c291092 | Will Bitcoin reach $250,000 by December 31, 2026? | 6 | timestral-5m | 990 | +2.3% | -8.440e-04 | 1.118e-04 | no demonstrated difference |
| 0x6fefc0438c7598b23531457c8c60541990d0786bd4bd9dfc3eabc8d95c291092 | Will Bitcoin reach $250,000 by December 31, 2026? | 6 | timestral-28m | 990 | +3.5% | -0.0010 | -3.175e-05 | better |
| 0x6fefc0438c7598b23531457c8c60541990d0786bd4bd9dfc3eabc8d95c291092 | Will Bitcoin reach $250,000 by December 31, 2026? | 6 | timestral-123m | 990 | +4.2% | -0.0011 | -1.773e-04 | better |
| 0x6fefc0438c7598b23531457c8c60541990d0786bd4bd9dfc3eabc8d95c291092 | Will Bitcoin reach $250,000 by December 31, 2026? | 6 | timestral-209m | 990 | +4.0% | -0.0011 | -1.501e-04 | better |
| 0x6fefc0438c7598b23531457c8c60541990d0786bd4bd9dfc3eabc8d95c291092 | Will Bitcoin reach $250,000 by December 31, 2026? | 24 | timestral-5m | 988 | +1.0% | -0.0024 | 9.917e-04 | no demonstrated difference |
| 0x6fefc0438c7598b23531457c8c60541990d0786bd4bd9dfc3eabc8d95c291092 | Will Bitcoin reach $250,000 by December 31, 2026? | 24 | timestral-28m | 988 | +0.3% | -0.0023 | 0.0012 | no demonstrated difference |
| 0x6fefc0438c7598b23531457c8c60541990d0786bd4bd9dfc3eabc8d95c291092 | Will Bitcoin reach $250,000 by December 31, 2026? | 24 | timestral-123m | 988 | +2.9% | -0.0029 | 2.107e-04 | no demonstrated difference |
| 0x6fefc0438c7598b23531457c8c60541990d0786bd4bd9dfc3eabc8d95c291092 | Will Bitcoin reach $250,000 by December 31, 2026? | 24 | timestral-209m | 988 | +1.2% | -0.0021 | 8.683e-04 | no demonstrated difference |
| 0x747dc809fb79e1b05be09c42d6179459a58de2ef3e40f02484a4e1260f741f75 | Will the US confirm that aliens exist before 2027? | 1 | timestral-5m | 1,163 | -14.2% | 4.060e-04 | 8.934e-04 | worse |
| 0x747dc809fb79e1b05be09c42d6179459a58de2ef3e40f02484a4e1260f741f75 | Will the US confirm that aliens exist before 2027? | 1 | timestral-28m | 1,163 | -8.4% | 2.006e-04 | 5.818e-04 | worse |
| 0x747dc809fb79e1b05be09c42d6179459a58de2ef3e40f02484a4e1260f741f75 | Will the US confirm that aliens exist before 2027? | 1 | timestral-123m | 1,163 | -7.9% | 1.501e-04 | 5.732e-04 | worse |
| 0x747dc809fb79e1b05be09c42d6179459a58de2ef3e40f02484a4e1260f741f75 | Will the US confirm that aliens exist before 2027? | 1 | timestral-209m | 1,163 | -7.1% | 1.322e-04 | 5.181e-04 | worse |
| 0x747dc809fb79e1b05be09c42d6179459a58de2ef3e40f02484a4e1260f741f75 | Will the US confirm that aliens exist before 2027? | 6 | timestral-5m | 1,157 | +1.8% | -0.0011 | 2.247e-04 | no demonstrated difference |
| 0x747dc809fb79e1b05be09c42d6179459a58de2ef3e40f02484a4e1260f741f75 | Will the US confirm that aliens exist before 2027? | 6 | timestral-28m | 1,157 | +3.4% | -0.0014 | -1.021e-04 | better |
| 0x747dc809fb79e1b05be09c42d6179459a58de2ef3e40f02484a4e1260f741f75 | Will the US confirm that aliens exist before 2027? | 6 | timestral-123m | 1,157 | +3.7% | -0.0015 | -1.506e-04 | better |
| 0x747dc809fb79e1b05be09c42d6179459a58de2ef3e40f02484a4e1260f741f75 | Will the US confirm that aliens exist before 2027? | 6 | timestral-209m | 1,157 | +3.9% | -0.0015 | -2.258e-04 | better |
| 0x747dc809fb79e1b05be09c42d6179459a58de2ef3e40f02484a4e1260f741f75 | Will the US confirm that aliens exist before 2027? | 24 | timestral-5m | 1,153 | +2.2% | -0.0033 | 0.0012 | no demonstrated difference |
| 0x747dc809fb79e1b05be09c42d6179459a58de2ef3e40f02484a4e1260f741f75 | Will the US confirm that aliens exist before 2027? | 24 | timestral-28m | 1,153 | +2.0% | -0.0031 | 0.0011 | no demonstrated difference |
| 0x747dc809fb79e1b05be09c42d6179459a58de2ef3e40f02484a4e1260f741f75 | Will the US confirm that aliens exist before 2027? | 24 | timestral-123m | 1,153 | +2.4% | -0.0034 | 0.0011 | no demonstrated difference |
| 0x747dc809fb79e1b05be09c42d6179459a58de2ef3e40f02484a4e1260f741f75 | Will the US confirm that aliens exist before 2027? | 24 | timestral-209m | 1,153 | +2.5% | -0.0033 | 0.0010 | no demonstrated difference |
| 0x752fa61c93f16c4b15e85b0bd438d9c684176b0ea7b319a84c8aca34616e8a8c | Will Bitcoin dip to $55,000 by December 31, 2026? | 1 | timestral-5m | 1,234 | -2.1% | -1.331e-04 | 7.766e-04 | no demonstrated difference |
| 0x752fa61c93f16c4b15e85b0bd438d9c684176b0ea7b319a84c8aca34616e8a8c | Will Bitcoin dip to $55,000 by December 31, 2026? | 1 | timestral-28m | 1,234 | +0.4% | -4.447e-04 | 2.960e-04 | no demonstrated difference |
| 0x752fa61c93f16c4b15e85b0bd438d9c684176b0ea7b319a84c8aca34616e8a8c | Will Bitcoin dip to $55,000 by December 31, 2026? | 1 | timestral-123m | 1,234 | +0.8% | -4.976e-04 | 2.450e-04 | no demonstrated difference |
| 0x752fa61c93f16c4b15e85b0bd438d9c684176b0ea7b319a84c8aca34616e8a8c | Will Bitcoin dip to $55,000 by December 31, 2026? | 1 | timestral-209m | 1,234 | +1.7% | -6.059e-04 | 7.214e-05 | no demonstrated difference |
| 0x752fa61c93f16c4b15e85b0bd438d9c684176b0ea7b319a84c8aca34616e8a8c | Will Bitcoin dip to $55,000 by December 31, 2026? | 6 | timestral-5m | 1,222 | +2.3% | -0.0020 | -8.633e-05 | better |
| 0x752fa61c93f16c4b15e85b0bd438d9c684176b0ea7b319a84c8aca34616e8a8c | Will Bitcoin dip to $55,000 by December 31, 2026? | 6 | timestral-28m | 1,222 | +3.2% | -0.0022 | -5.852e-04 | better |
| 0x752fa61c93f16c4b15e85b0bd438d9c684176b0ea7b319a84c8aca34616e8a8c | Will Bitcoin dip to $55,000 by December 31, 2026? | 6 | timestral-123m | 1,222 | +3.2% | -0.0022 | -6.092e-04 | better |
| 0x752fa61c93f16c4b15e85b0bd438d9c684176b0ea7b319a84c8aca34616e8a8c | Will Bitcoin dip to $55,000 by December 31, 2026? | 6 | timestral-209m | 1,222 | +3.7% | -0.0024 | -7.743e-04 | better |
| 0x752fa61c93f16c4b15e85b0bd438d9c684176b0ea7b319a84c8aca34616e8a8c | Will Bitcoin dip to $55,000 by December 31, 2026? | 24 | timestral-5m | 1,220 | +2.2% | -0.0057 | 0.0021 | no demonstrated difference |
| 0x752fa61c93f16c4b15e85b0bd438d9c684176b0ea7b319a84c8aca34616e8a8c | Will Bitcoin dip to $55,000 by December 31, 2026? | 24 | timestral-28m | 1,220 | +3.8% | -0.0067 | 3.949e-04 | no demonstrated difference |
| 0x752fa61c93f16c4b15e85b0bd438d9c684176b0ea7b319a84c8aca34616e8a8c | Will Bitcoin dip to $55,000 by December 31, 2026? | 24 | timestral-123m | 1,220 | +3.5% | -0.0070 | 0.0012 | no demonstrated difference |
| 0x752fa61c93f16c4b15e85b0bd438d9c684176b0ea7b319a84c8aca34616e8a8c | Will Bitcoin dip to $55,000 by December 31, 2026? | 24 | timestral-209m | 1,220 | +4.4% | -0.0073 | -1.219e-04 | better |
| 0x79b7408f02df2eba4034ca4c06ddf17b8dbeacc5adbe8595969e7573912c4e3b | US-Iran Final Nuclear Deal by December 31, 2026? | 1 | timestral-5m | 456 | -14.7% | 5.829e-04 | 0.0012 | worse |
| 0x79b7408f02df2eba4034ca4c06ddf17b8dbeacc5adbe8595969e7573912c4e3b | US-Iran Final Nuclear Deal by December 31, 2026? | 1 | timestral-28m | 456 | -7.2% | 2.290e-04 | 6.430e-04 | worse |
| 0x79b7408f02df2eba4034ca4c06ddf17b8dbeacc5adbe8595969e7573912c4e3b | US-Iran Final Nuclear Deal by December 31, 2026? | 1 | timestral-123m | 456 | -8.1% | 2.594e-04 | 7.147e-04 | worse |
| 0x79b7408f02df2eba4034ca4c06ddf17b8dbeacc5adbe8595969e7573912c4e3b | US-Iran Final Nuclear Deal by December 31, 2026? | 1 | timestral-209m | 456 | -7.1% | 2.436e-04 | 6.075e-04 | worse |
| 0x79b7408f02df2eba4034ca4c06ddf17b8dbeacc5adbe8595969e7573912c4e3b | US-Iran Final Nuclear Deal by December 31, 2026? | 6 | timestral-5m | 449 | -4.8% | 4.512e-04 | 0.0022 | worse |
| 0x79b7408f02df2eba4034ca4c06ddf17b8dbeacc5adbe8595969e7573912c4e3b | US-Iran Final Nuclear Deal by December 31, 2026? | 6 | timestral-28m | 449 | -1.6% | -2.690e-04 | 0.0011 | no demonstrated difference |
| 0x79b7408f02df2eba4034ca4c06ddf17b8dbeacc5adbe8595969e7573912c4e3b | US-Iran Final Nuclear Deal by December 31, 2026? | 6 | timestral-123m | 449 | -2.6% | -6.317e-05 | 0.0016 | no demonstrated difference |
| 0x79b7408f02df2eba4034ca4c06ddf17b8dbeacc5adbe8595969e7573912c4e3b | US-Iran Final Nuclear Deal by December 31, 2026? | 6 | timestral-209m | 449 | -2.8% | 8.741e-05 | 0.0015 | worse |
| 0x79b7408f02df2eba4034ca4c06ddf17b8dbeacc5adbe8595969e7573912c4e3b | US-Iran Final Nuclear Deal by December 31, 2026? | 24 | timestral-5m | 448 | -0.6% | -0.0040 | 0.0054 | no demonstrated difference |
| 0x79b7408f02df2eba4034ca4c06ddf17b8dbeacc5adbe8595969e7573912c4e3b | US-Iran Final Nuclear Deal by December 31, 2026? | 24 | timestral-28m | 448 | +1.9% | -0.0057 | 0.0038 | no demonstrated difference |
| 0x79b7408f02df2eba4034ca4c06ddf17b8dbeacc5adbe8595969e7573912c4e3b | US-Iran Final Nuclear Deal by December 31, 2026? | 24 | timestral-123m | 448 | +2.0% | -0.0060 | 0.0038 | no demonstrated difference |
| 0x79b7408f02df2eba4034ca4c06ddf17b8dbeacc5adbe8595969e7573912c4e3b | US-Iran Final Nuclear Deal by December 31, 2026? | 24 | timestral-209m | 448 | +0.8% | -0.0046 | 0.0041 | no demonstrated difference |
| 0x7cb525e831729325d651017f81cbcb6f1adde5011c7b2283babea00b4ae93ae7 | Netanyahu out by March 31? | 1 | timestral-5m | 83 | -2.8% | -0.0023 | 0.0047 | no demonstrated difference |
| 0x7cb525e831729325d651017f81cbcb6f1adde5011c7b2283babea00b4ae93ae7 | Netanyahu out by March 31? | 1 | timestral-28m | 83 | -0.7% | -0.0024 | 0.0028 | no demonstrated difference |
| 0x7cb525e831729325d651017f81cbcb6f1adde5011c7b2283babea00b4ae93ae7 | Netanyahu out by March 31? | 1 | timestral-123m | 83 | +0.6% | -0.0031 | 0.0022 | no demonstrated difference |
| 0x7cb525e831729325d651017f81cbcb6f1adde5011c7b2283babea00b4ae93ae7 | Netanyahu out by March 31? | 1 | timestral-209m | 83 | +0.2% | -0.0034 | 0.0025 | no demonstrated difference |
| 0x7cb525e831729325d651017f81cbcb6f1adde5011c7b2283babea00b4ae93ae7 | Netanyahu out by March 31? | 6 | timestral-5m | 81 | -1.8% | -0.0037 | 0.0112 | no demonstrated difference |
| 0x7cb525e831729325d651017f81cbcb6f1adde5011c7b2283babea00b4ae93ae7 | Netanyahu out by March 31? | 6 | timestral-28m | 81 | -0.0% | -0.0045 | 0.0068 | no demonstrated difference |
| 0x7cb525e831729325d651017f81cbcb6f1adde5011c7b2283babea00b4ae93ae7 | Netanyahu out by March 31? | 6 | timestral-123m | 81 | +0.7% | -0.0054 | 0.0062 | no demonstrated difference |
| 0x7cb525e831729325d651017f81cbcb6f1adde5011c7b2283babea00b4ae93ae7 | Netanyahu out by March 31? | 6 | timestral-209m | 81 | -1.2% | -0.0044 | 0.0104 | no demonstrated difference |
| 0x7cb525e831729325d651017f81cbcb6f1adde5011c7b2283babea00b4ae93ae7 | Netanyahu out by March 31? | 24 | timestral-5m | 77 | -9.7% | -0.0093 | 0.0463 | no demonstrated difference |
| 0x7cb525e831729325d651017f81cbcb6f1adde5011c7b2283babea00b4ae93ae7 | Netanyahu out by March 31? | 24 | timestral-28m | 77 | -14.0% | -3.064e-04 | 0.0581 | no demonstrated difference |
| 0x7cb525e831729325d651017f81cbcb6f1adde5011c7b2283babea00b4ae93ae7 | Netanyahu out by March 31? | 24 | timestral-123m | 77 | -13.0% | -0.0053 | 0.0596 | no demonstrated difference |
| 0x7cb525e831729325d651017f81cbcb6f1adde5011c7b2283babea00b4ae93ae7 | Netanyahu out by March 31? | 24 | timestral-209m | 77 | -16.8% | -0.0012 | 0.0747 | no demonstrated difference |
| 0x80ebf0a88a44bf737d4047b3accd7108285c69b84257e5c684bdc4c715c81139 | Will the U.S. invade Cuba in 2026? | 1 | timestral-5m | 1,014 | -1.2% | -2.578e-04 | 5.235e-04 | no demonstrated difference |
| 0x80ebf0a88a44bf737d4047b3accd7108285c69b84257e5c684bdc4c715c81139 | Will the U.S. invade Cuba in 2026? | 1 | timestral-28m | 1,014 | +1.1% | -5.238e-04 | 2.773e-04 | no demonstrated difference |
| 0x80ebf0a88a44bf737d4047b3accd7108285c69b84257e5c684bdc4c715c81139 | Will the U.S. invade Cuba in 2026? | 1 | timestral-123m | 1,014 | +4.0% | -8.672e-04 | 4.053e-05 | no demonstrated difference |
| 0x80ebf0a88a44bf737d4047b3accd7108285c69b84257e5c684bdc4c715c81139 | Will the U.S. invade Cuba in 2026? | 1 | timestral-209m | 1,014 | +3.5% | -7.126e-04 | 5.406e-06 | no demonstrated difference |
| 0x80ebf0a88a44bf737d4047b3accd7108285c69b84257e5c684bdc4c715c81139 | Will the U.S. invade Cuba in 2026? | 6 | timestral-5m | 989 | +1.3% | -0.0012 | 5.354e-04 | no demonstrated difference |
| 0x80ebf0a88a44bf737d4047b3accd7108285c69b84257e5c684bdc4c715c81139 | Will the U.S. invade Cuba in 2026? | 6 | timestral-28m | 989 | +2.5% | -0.0014 | 1.108e-04 | no demonstrated difference |
| 0x80ebf0a88a44bf737d4047b3accd7108285c69b84257e5c684bdc4c715c81139 | Will the U.S. invade Cuba in 2026? | 6 | timestral-123m | 989 | +3.7% | -0.0018 | -2.417e-04 | better |
| 0x80ebf0a88a44bf737d4047b3accd7108285c69b84257e5c684bdc4c715c81139 | Will the U.S. invade Cuba in 2026? | 6 | timestral-209m | 989 | +3.6% | -0.0017 | -1.967e-04 | better |
| 0x80ebf0a88a44bf737d4047b3accd7108285c69b84257e5c684bdc4c715c81139 | Will the U.S. invade Cuba in 2026? | 24 | timestral-5m | 988 | +2.8% | -0.0039 | 9.766e-04 | no demonstrated difference |
| 0x80ebf0a88a44bf737d4047b3accd7108285c69b84257e5c684bdc4c715c81139 | Will the U.S. invade Cuba in 2026? | 24 | timestral-28m | 988 | +4.2% | -0.0045 | -6.965e-05 | better |
| 0x80ebf0a88a44bf737d4047b3accd7108285c69b84257e5c684bdc4c715c81139 | Will the U.S. invade Cuba in 2026? | 24 | timestral-123m | 988 | +4.6% | -0.0048 | -2.765e-04 | better |
| 0x80ebf0a88a44bf737d4047b3accd7108285c69b84257e5c684bdc4c715c81139 | Will the U.S. invade Cuba in 2026? | 24 | timestral-209m | 988 | +4.6% | -0.0047 | -2.757e-04 | better |
| 0x890fc3ba40458db0b67560691aa1597344c2a0560d18e80f586a4b35f510b4ce | Will the US acquire part of Greenland in 2026? | 1 | timestral-5m | 1,082 | -11.0% | 2.901e-04 | 0.0011 | worse |
| 0x890fc3ba40458db0b67560691aa1597344c2a0560d18e80f586a4b35f510b4ce | Will the US acquire part of Greenland in 2026? | 1 | timestral-28m | 1,082 | -6.2% | 1.709e-05 | 7.152e-04 | worse |
| 0x890fc3ba40458db0b67560691aa1597344c2a0560d18e80f586a4b35f510b4ce | Will the US acquire part of Greenland in 2026? | 1 | timestral-123m | 1,082 | -4.2% | -1.368e-04 | 5.951e-04 | no demonstrated difference |
| 0x890fc3ba40458db0b67560691aa1597344c2a0560d18e80f586a4b35f510b4ce | Will the US acquire part of Greenland in 2026? | 1 | timestral-209m | 1,082 | -5.6% | 6.117e-05 | 6.209e-04 | worse |
| 0x890fc3ba40458db0b67560691aa1597344c2a0560d18e80f586a4b35f510b4ce | Will the US acquire part of Greenland in 2026? | 6 | timestral-5m | 1,072 | +2.0% | -0.0015 | 2.478e-04 | no demonstrated difference |
| 0x890fc3ba40458db0b67560691aa1597344c2a0560d18e80f586a4b35f510b4ce | Will the US acquire part of Greenland in 2026? | 6 | timestral-28m | 1,072 | +3.1% | -0.0018 | -1.136e-04 | better |
| 0x890fc3ba40458db0b67560691aa1597344c2a0560d18e80f586a4b35f510b4ce | Will the US acquire part of Greenland in 2026? | 6 | timestral-123m | 1,072 | +3.9% | -0.0021 | -2.262e-04 | better |
| 0x890fc3ba40458db0b67560691aa1597344c2a0560d18e80f586a4b35f510b4ce | Will the US acquire part of Greenland in 2026? | 6 | timestral-209m | 1,072 | +2.8% | -0.0017 | 1.159e-05 | no demonstrated difference |
| 0x890fc3ba40458db0b67560691aa1597344c2a0560d18e80f586a4b35f510b4ce | Will the US acquire part of Greenland in 2026? | 24 | timestral-5m | 1,070 | +5.2% | -0.0058 | -5.635e-04 | better |
| 0x890fc3ba40458db0b67560691aa1597344c2a0560d18e80f586a4b35f510b4ce | Will the US acquire part of Greenland in 2026? | 24 | timestral-28m | 1,070 | +6.2% | -0.0061 | -0.0015 | better |
| 0x890fc3ba40458db0b67560691aa1597344c2a0560d18e80f586a4b35f510b4ce | Will the US acquire part of Greenland in 2026? | 24 | timestral-123m | 1,070 | +6.5% | -0.0064 | -0.0015 | better |
| 0x890fc3ba40458db0b67560691aa1597344c2a0560d18e80f586a4b35f510b4ce | Will the US acquire part of Greenland in 2026? | 24 | timestral-209m | 1,070 | +5.2% | -0.0056 | -6.292e-04 | better |
| 0x9345d5142a67f5541264c96515496affee02580f1c572680759eac9fd2a1588a | Billionaire one-time wealth tax passes in California election 2026? | 1 | timestral-5m | 1,368 | +0.8% | -7.093e-04 | 4.254e-04 | no demonstrated difference |
| 0x9345d5142a67f5541264c96515496affee02580f1c572680759eac9fd2a1588a | Billionaire one-time wealth tax passes in California election 2026? | 1 | timestral-28m | 1,368 | +2.6% | -6.807e-04 | 1.478e-04 | no demonstrated difference |
| 0x9345d5142a67f5541264c96515496affee02580f1c572680759eac9fd2a1588a | Billionaire one-time wealth tax passes in California election 2026? | 1 | timestral-123m | 1,368 | +3.8% | -9.284e-04 | 1.004e-04 | no demonstrated difference |
| 0x9345d5142a67f5541264c96515496affee02580f1c572680759eac9fd2a1588a | Billionaire one-time wealth tax passes in California election 2026? | 1 | timestral-209m | 1,368 | +4.9% | -0.0013 | 8.214e-05 | no demonstrated difference |
| 0x9345d5142a67f5541264c96515496affee02580f1c572680759eac9fd2a1588a | Billionaire one-time wealth tax passes in California election 2026? | 6 | timestral-5m | 1,345 | +1.0% | -0.0012 | 7.660e-04 | no demonstrated difference |
| 0x9345d5142a67f5541264c96515496affee02580f1c572680759eac9fd2a1588a | Billionaire one-time wealth tax passes in California election 2026? | 6 | timestral-28m | 1,345 | +2.1% | -0.0014 | 2.139e-04 | no demonstrated difference |
| 0x9345d5142a67f5541264c96515496affee02580f1c572680759eac9fd2a1588a | Billionaire one-time wealth tax passes in California election 2026? | 6 | timestral-123m | 1,345 | +3.2% | -0.0018 | -3.009e-05 | better |
| 0x9345d5142a67f5541264c96515496affee02580f1c572680759eac9fd2a1588a | Billionaire one-time wealth tax passes in California election 2026? | 6 | timestral-209m | 1,345 | +2.7% | -0.0016 | 1.509e-04 | no demonstrated difference |
| 0x9345d5142a67f5541264c96515496affee02580f1c572680759eac9fd2a1588a | Billionaire one-time wealth tax passes in California election 2026? | 24 | timestral-5m | 1,338 | +4.0% | -0.0053 | 8.576e-04 | no demonstrated difference |
| 0x9345d5142a67f5541264c96515496affee02580f1c572680759eac9fd2a1588a | Billionaire one-time wealth tax passes in California election 2026? | 24 | timestral-28m | 1,338 | +5.5% | -0.0060 | -7.056e-04 | better |
| 0x9345d5142a67f5541264c96515496affee02580f1c572680759eac9fd2a1588a | Billionaire one-time wealth tax passes in California election 2026? | 24 | timestral-123m | 1,338 | +6.2% | -0.0063 | -0.0011 | better |
| 0x9345d5142a67f5541264c96515496affee02580f1c572680759eac9fd2a1588a | Billionaire one-time wealth tax passes in California election 2026? | 24 | timestral-209m | 1,338 | +5.7% | -0.0060 | -8.668e-04 | better |
| 0x9cb23d04b2ded06147482076688b69b487a8d982c63ebdda2ab3678cf27cf390 | Clarity Act (H.R.3633) signed into law in 2026? | 1 | timestral-5m | 964 | -2.3% | -6.809e-05 | 0.0011 | no demonstrated difference |
| 0x9cb23d04b2ded06147482076688b69b487a8d982c63ebdda2ab3678cf27cf390 | Clarity Act (H.R.3633) signed into law in 2026? | 1 | timestral-28m | 964 | +1.0% | -7.185e-04 | 2.943e-04 | no demonstrated difference |
| 0x9cb23d04b2ded06147482076688b69b487a8d982c63ebdda2ab3678cf27cf390 | Clarity Act (H.R.3633) signed into law in 2026? | 1 | timestral-123m | 964 | +0.9% | -6.383e-04 | 3.313e-04 | no demonstrated difference |
| 0x9cb23d04b2ded06147482076688b69b487a8d982c63ebdda2ab3678cf27cf390 | Clarity Act (H.R.3633) signed into law in 2026? | 1 | timestral-209m | 964 | +1.7% | -7.836e-04 | 1.485e-04 | no demonstrated difference |
| 0x9cb23d04b2ded06147482076688b69b487a8d982c63ebdda2ab3678cf27cf390 | Clarity Act (H.R.3633) signed into law in 2026? | 6 | timestral-5m | 945 | +3.7% | -0.0040 | -4.729e-04 | better |
| 0x9cb23d04b2ded06147482076688b69b487a8d982c63ebdda2ab3678cf27cf390 | Clarity Act (H.R.3633) signed into law in 2026? | 6 | timestral-28m | 945 | +3.9% | -0.0037 | -8.655e-04 | better |
| 0x9cb23d04b2ded06147482076688b69b487a8d982c63ebdda2ab3678cf27cf390 | Clarity Act (H.R.3633) signed into law in 2026? | 6 | timestral-123m | 945 | +4.2% | -0.0040 | -9.777e-04 | better |
| 0x9cb23d04b2ded06147482076688b69b487a8d982c63ebdda2ab3678cf27cf390 | Clarity Act (H.R.3633) signed into law in 2026? | 6 | timestral-209m | 945 | +4.6% | -0.0041 | -0.0013 | better |
| 0x9cb23d04b2ded06147482076688b69b487a8d982c63ebdda2ab3678cf27cf390 | Clarity Act (H.R.3633) signed into law in 2026? | 24 | timestral-5m | 943 | +8.4% | -0.0162 | -0.0050 | better |
| 0x9cb23d04b2ded06147482076688b69b487a8d982c63ebdda2ab3678cf27cf390 | Clarity Act (H.R.3633) signed into law in 2026? | 24 | timestral-28m | 943 | +8.7% | -0.0161 | -0.0064 | better |
| 0x9cb23d04b2ded06147482076688b69b487a8d982c63ebdda2ab3678cf27cf390 | Clarity Act (H.R.3633) signed into law in 2026? | 24 | timestral-123m | 943 | +8.6% | -0.0165 | -0.0056 | better |
| 0x9cb23d04b2ded06147482076688b69b487a8d982c63ebdda2ab3678cf27cf390 | Clarity Act (H.R.3633) signed into law in 2026? | 24 | timestral-209m | 943 | +9.5% | -0.0174 | -0.0070 | better |
| 0xa467b14d51f01b957109d9cbb1d6c124fab2a089d52ed8f471d23c2812e743b7 | Xi Jinping out before 2027? | 1 | timestral-5m | 1,705 | -5.8% | 7.040e-05 | 4.610e-04 | worse |
| 0xa467b14d51f01b957109d9cbb1d6c124fab2a089d52ed8f471d23c2812e743b7 | Xi Jinping out before 2027? | 1 | timestral-28m | 1,705 | -1.8% | -8.597e-05 | 2.287e-04 | no demonstrated difference |
| 0xa467b14d51f01b957109d9cbb1d6c124fab2a089d52ed8f471d23c2812e743b7 | Xi Jinping out before 2027? | 1 | timestral-123m | 1,705 | -1.4% | -1.110e-04 | 2.012e-04 | no demonstrated difference |
| 0xa467b14d51f01b957109d9cbb1d6c124fab2a089d52ed8f471d23c2812e743b7 | Xi Jinping out before 2027? | 1 | timestral-209m | 1,705 | -0.5% | -1.549e-04 | 1.597e-04 | no demonstrated difference |
| 0xa467b14d51f01b957109d9cbb1d6c124fab2a089d52ed8f471d23c2812e743b7 | Xi Jinping out before 2027? | 6 | timestral-5m | 1,677 | +1.4% | -7.603e-04 | 2.057e-04 | no demonstrated difference |
| 0xa467b14d51f01b957109d9cbb1d6c124fab2a089d52ed8f471d23c2812e743b7 | Xi Jinping out before 2027? | 6 | timestral-28m | 1,677 | +2.7% | -8.850e-04 | -5.477e-05 | better |
| 0xa467b14d51f01b957109d9cbb1d6c124fab2a089d52ed8f471d23c2812e743b7 | Xi Jinping out before 2027? | 6 | timestral-123m | 1,677 | +2.4% | -8.643e-04 | -2.943e-05 | better |
| 0xa467b14d51f01b957109d9cbb1d6c124fab2a089d52ed8f471d23c2812e743b7 | Xi Jinping out before 2027? | 6 | timestral-209m | 1,677 | +2.9% | -9.139e-04 | -1.116e-04 | better |
| 0xa467b14d51f01b957109d9cbb1d6c124fab2a089d52ed8f471d23c2812e743b7 | Xi Jinping out before 2027? | 24 | timestral-5m | 1,673 | +4.2% | -0.0030 | -2.519e-04 | better |
| 0xa467b14d51f01b957109d9cbb1d6c124fab2a089d52ed8f471d23c2812e743b7 | Xi Jinping out before 2027? | 24 | timestral-28m | 1,673 | +4.8% | -0.0031 | -5.522e-04 | better |
| 0xa467b14d51f01b957109d9cbb1d6c124fab2a089d52ed8f471d23c2812e743b7 | Xi Jinping out before 2027? | 24 | timestral-123m | 1,673 | +5.0% | -0.0033 | -5.377e-04 | better |
| 0xa467b14d51f01b957109d9cbb1d6c124fab2a089d52ed8f471d23c2812e743b7 | Xi Jinping out before 2027? | 24 | timestral-209m | 1,673 | +4.8% | -0.0031 | -5.375e-04 | better |
| 0xa4ddc18895cc7b14810283ef8f113939abffd3969c6a0e37f1897110c67e6f73 | Hantavirus pandemic in 2026? | 1 | timestral-5m | 642 | -16.7% | 4.692e-04 | 9.560e-04 | worse |
| 0xa4ddc18895cc7b14810283ef8f113939abffd3969c6a0e37f1897110c67e6f73 | Hantavirus pandemic in 2026? | 1 | timestral-28m | 642 | -10.2% | 2.216e-04 | 6.201e-04 | worse |
| 0xa4ddc18895cc7b14810283ef8f113939abffd3969c6a0e37f1897110c67e6f73 | Hantavirus pandemic in 2026? | 1 | timestral-123m | 642 | -9.3% | 1.638e-04 | 5.892e-04 | worse |
| 0xa4ddc18895cc7b14810283ef8f113939abffd3969c6a0e37f1897110c67e6f73 | Hantavirus pandemic in 2026? | 1 | timestral-209m | 642 | -7.2% | 1.211e-04 | 4.677e-04 | worse |
| 0xa4ddc18895cc7b14810283ef8f113939abffd3969c6a0e37f1897110c67e6f73 | Hantavirus pandemic in 2026? | 6 | timestral-5m | 624 | -1.0% | -3.083e-04 | 8.074e-04 | no demonstrated difference |
| 0xa4ddc18895cc7b14810283ef8f113939abffd3969c6a0e37f1897110c67e6f73 | Hantavirus pandemic in 2026? | 6 | timestral-28m | 624 | +0.6% | -5.122e-04 | 3.707e-04 | no demonstrated difference |
| 0xa4ddc18895cc7b14810283ef8f113939abffd3969c6a0e37f1897110c67e6f73 | Hantavirus pandemic in 2026? | 6 | timestral-123m | 624 | -0.4% | -5.507e-04 | 6.190e-04 | no demonstrated difference |
| 0xa4ddc18895cc7b14810283ef8f113939abffd3969c6a0e37f1897110c67e6f73 | Hantavirus pandemic in 2026? | 6 | timestral-209m | 624 | +0.1% | -5.928e-04 | 5.062e-04 | no demonstrated difference |
| 0xa4ddc18895cc7b14810283ef8f113939abffd3969c6a0e37f1897110c67e6f73 | Hantavirus pandemic in 2026? | 24 | timestral-5m | 625 | +3.2% | -0.0041 | 0.0012 | no demonstrated difference |
| 0xa4ddc18895cc7b14810283ef8f113939abffd3969c6a0e37f1897110c67e6f73 | Hantavirus pandemic in 2026? | 24 | timestral-28m | 625 | +5.4% | -0.0051 | -1.578e-04 | better |
| 0xa4ddc18895cc7b14810283ef8f113939abffd3969c6a0e37f1897110c67e6f73 | Hantavirus pandemic in 2026? | 24 | timestral-123m | 625 | +5.5% | -0.0050 | -6.466e-05 | better |
| 0xa4ddc18895cc7b14810283ef8f113939abffd3969c6a0e37f1897110c67e6f73 | Hantavirus pandemic in 2026? | 24 | timestral-209m | 625 | +5.9% | -0.0051 | -4.410e-04 | better |
| 0xa885bfe10688056a9d0f4e9a1523bfa18f66fda065f0400d714ba54776083713 | Will Bitcoin dip to $15,000 by December 31, 2026? | 1 | timestral-5m | 1,065 | -4.2% | 1.339e-04 | 7.320e-04 | worse |
| 0xa885bfe10688056a9d0f4e9a1523bfa18f66fda065f0400d714ba54776083713 | Will Bitcoin dip to $15,000 by December 31, 2026? | 1 | timestral-28m | 1,065 | -1.8% | -8.637e-05 | 4.931e-04 | no demonstrated difference |
| 0xa885bfe10688056a9d0f4e9a1523bfa18f66fda065f0400d714ba54776083713 | Will Bitcoin dip to $15,000 by December 31, 2026? | 1 | timestral-123m | 1,065 | -0.5% | -2.503e-04 | 3.812e-04 | no demonstrated difference |
| 0xa885bfe10688056a9d0f4e9a1523bfa18f66fda065f0400d714ba54776083713 | Will Bitcoin dip to $15,000 by December 31, 2026? | 1 | timestral-209m | 1,065 | +0.2% | -2.870e-04 | 2.562e-04 | no demonstrated difference |
| 0xa885bfe10688056a9d0f4e9a1523bfa18f66fda065f0400d714ba54776083713 | Will Bitcoin dip to $15,000 by December 31, 2026? | 6 | timestral-5m | 1,055 | +0.9% | -0.0012 | 7.517e-04 | no demonstrated difference |
| 0xa885bfe10688056a9d0f4e9a1523bfa18f66fda065f0400d714ba54776083713 | Will Bitcoin dip to $15,000 by December 31, 2026? | 6 | timestral-28m | 1,055 | +2.0% | -0.0014 | 2.716e-04 | no demonstrated difference |
| 0xa885bfe10688056a9d0f4e9a1523bfa18f66fda065f0400d714ba54776083713 | Will Bitcoin dip to $15,000 by December 31, 2026? | 6 | timestral-123m | 1,055 | +1.3% | -0.0013 | 5.771e-04 | no demonstrated difference |
| 0xa885bfe10688056a9d0f4e9a1523bfa18f66fda065f0400d714ba54776083713 | Will Bitcoin dip to $15,000 by December 31, 2026? | 6 | timestral-209m | 1,055 | +2.3% | -0.0015 | 2.501e-04 | no demonstrated difference |
| 0xa885bfe10688056a9d0f4e9a1523bfa18f66fda065f0400d714ba54776083713 | Will Bitcoin dip to $15,000 by December 31, 2026? | 24 | timestral-5m | 1,053 | +7.1% | -0.0070 | -0.0019 | better |
| 0xa885bfe10688056a9d0f4e9a1523bfa18f66fda065f0400d714ba54776083713 | Will Bitcoin dip to $15,000 by December 31, 2026? | 24 | timestral-28m | 1,053 | +7.8% | -0.0071 | -0.0025 | better |
| 0xa885bfe10688056a9d0f4e9a1523bfa18f66fda065f0400d714ba54776083713 | Will Bitcoin dip to $15,000 by December 31, 2026? | 24 | timestral-123m | 1,053 | +7.6% | -0.0071 | -0.0024 | better |
| 0xa885bfe10688056a9d0f4e9a1523bfa18f66fda065f0400d714ba54776083713 | Will Bitcoin dip to $15,000 by December 31, 2026? | 24 | timestral-209m | 1,053 | +7.4% | -0.0068 | -0.0024 | better |
| 0xa93b28a6384aefff4e7d5adb2061c444e4a0e95b8ad17755f9cee123c7099b35 | Russia x Ukraine ceasefire by May 31, 2026? | 1 | timestral-5m | 36 | +10.4% | – | – | insufficient data |
| 0xa93b28a6384aefff4e7d5adb2061c444e4a0e95b8ad17755f9cee123c7099b35 | Russia x Ukraine ceasefire by May 31, 2026? | 1 | timestral-28m | 36 | +8.7% | – | – | insufficient data |
| 0xa93b28a6384aefff4e7d5adb2061c444e4a0e95b8ad17755f9cee123c7099b35 | Russia x Ukraine ceasefire by May 31, 2026? | 1 | timestral-123m | 36 | +13.4% | – | – | insufficient data |
| 0xa93b28a6384aefff4e7d5adb2061c444e4a0e95b8ad17755f9cee123c7099b35 | Russia x Ukraine ceasefire by May 31, 2026? | 1 | timestral-209m | 36 | +12.3% | – | – | insufficient data |
| 0xa93b28a6384aefff4e7d5adb2061c444e4a0e95b8ad17755f9cee123c7099b35 | Russia x Ukraine ceasefire by May 31, 2026? | 6 | timestral-5m | 34 | -1.7% | – | – | insufficient data |
| 0xa93b28a6384aefff4e7d5adb2061c444e4a0e95b8ad17755f9cee123c7099b35 | Russia x Ukraine ceasefire by May 31, 2026? | 6 | timestral-28m | 34 | +2.6% | – | – | insufficient data |
| 0xa93b28a6384aefff4e7d5adb2061c444e4a0e95b8ad17755f9cee123c7099b35 | Russia x Ukraine ceasefire by May 31, 2026? | 6 | timestral-123m | 34 | -0.4% | – | – | insufficient data |
| 0xa93b28a6384aefff4e7d5adb2061c444e4a0e95b8ad17755f9cee123c7099b35 | Russia x Ukraine ceasefire by May 31, 2026? | 6 | timestral-209m | 34 | -7.5% | – | – | insufficient data |
| 0xa93b28a6384aefff4e7d5adb2061c444e4a0e95b8ad17755f9cee123c7099b35 | Russia x Ukraine ceasefire by May 31, 2026? | 24 | timestral-5m | 32 | +2.0% | – | – | insufficient data |
| 0xa93b28a6384aefff4e7d5adb2061c444e4a0e95b8ad17755f9cee123c7099b35 | Russia x Ukraine ceasefire by May 31, 2026? | 24 | timestral-28m | 32 | +1.3% | – | – | insufficient data |
| 0xa93b28a6384aefff4e7d5adb2061c444e4a0e95b8ad17755f9cee123c7099b35 | Russia x Ukraine ceasefire by May 31, 2026? | 24 | timestral-123m | 32 | +2.1% | – | – | insufficient data |
| 0xa93b28a6384aefff4e7d5adb2061c444e4a0e95b8ad17755f9cee123c7099b35 | Russia x Ukraine ceasefire by May 31, 2026? | 24 | timestral-209m | 32 | +1.4% | – | – | insufficient data |
| 0xaa5cdb6830cbfa2ca711b7cf93bd42cf4f8e062d44ea188c0b8ec1fb2924c083 | Will Reza Pahlavi lead Iran in 2026? | 1 | timestral-5m | 779 | -10.7% | 1.876e-04 | 5.317e-04 | worse |
| 0xaa5cdb6830cbfa2ca711b7cf93bd42cf4f8e062d44ea188c0b8ec1fb2924c083 | Will Reza Pahlavi lead Iran in 2026? | 1 | timestral-28m | 779 | -7.0% | 1.018e-04 | 3.594e-04 | worse |
| 0xaa5cdb6830cbfa2ca711b7cf93bd42cf4f8e062d44ea188c0b8ec1fb2924c083 | Will Reza Pahlavi lead Iran in 2026? | 1 | timestral-123m | 779 | -5.1% | 2.305e-05 | 2.872e-04 | worse |
| 0xaa5cdb6830cbfa2ca711b7cf93bd42cf4f8e062d44ea188c0b8ec1fb2924c083 | Will Reza Pahlavi lead Iran in 2026? | 1 | timestral-209m | 779 | -2.1% | -6.487e-05 | 1.631e-04 | no demonstrated difference |
| 0xaa5cdb6830cbfa2ca711b7cf93bd42cf4f8e062d44ea188c0b8ec1fb2924c083 | Will Reza Pahlavi lead Iran in 2026? | 6 | timestral-5m | 756 | +0.5% | -6.372e-04 | 5.117e-04 | no demonstrated difference |
| 0xaa5cdb6830cbfa2ca711b7cf93bd42cf4f8e062d44ea188c0b8ec1fb2924c083 | Will Reza Pahlavi lead Iran in 2026? | 6 | timestral-28m | 756 | +1.1% | -4.982e-04 | 2.334e-04 | no demonstrated difference |
| 0xaa5cdb6830cbfa2ca711b7cf93bd42cf4f8e062d44ea188c0b8ec1fb2924c083 | Will Reza Pahlavi lead Iran in 2026? | 6 | timestral-123m | 756 | +1.9% | -7.735e-04 | 1.921e-04 | no demonstrated difference |
| 0xaa5cdb6830cbfa2ca711b7cf93bd42cf4f8e062d44ea188c0b8ec1fb2924c083 | Will Reza Pahlavi lead Iran in 2026? | 6 | timestral-209m | 756 | +2.4% | -8.424e-04 | 1.193e-04 | no demonstrated difference |
| 0xaa5cdb6830cbfa2ca711b7cf93bd42cf4f8e062d44ea188c0b8ec1fb2924c083 | Will Reza Pahlavi lead Iran in 2026? | 24 | timestral-5m | 753 | +1.6% | -0.0024 | 0.0015 | no demonstrated difference |
| 0xaa5cdb6830cbfa2ca711b7cf93bd42cf4f8e062d44ea188c0b8ec1fb2924c083 | Will Reza Pahlavi lead Iran in 2026? | 24 | timestral-28m | 753 | +2.0% | -0.0020 | 8.934e-04 | no demonstrated difference |
| 0xaa5cdb6830cbfa2ca711b7cf93bd42cf4f8e062d44ea188c0b8ec1fb2924c083 | Will Reza Pahlavi lead Iran in 2026? | 24 | timestral-123m | 753 | +2.7% | -0.0025 | 8.113e-04 | no demonstrated difference |
| 0xaa5cdb6830cbfa2ca711b7cf93bd42cf4f8e062d44ea188c0b8ec1fb2924c083 | Will Reza Pahlavi lead Iran in 2026? | 24 | timestral-209m | 753 | +2.7% | -0.0024 | 7.588e-04 | no demonstrated difference |
| 0xbb4d51e6364066d92eb6f9b8413dd7193de70966736044463b205834805a1f3b | Will the Iranian regime fall before 2027? | 1 | timestral-5m | 1,202 | -5.4% | 2.297e-04 | 7.719e-04 | worse |
| 0xbb4d51e6364066d92eb6f9b8413dd7193de70966736044463b205834805a1f3b | Will the Iranian regime fall before 2027? | 1 | timestral-28m | 1,202 | -1.8% | -7.874e-05 | 4.371e-04 | no demonstrated difference |
| 0xbb4d51e6364066d92eb6f9b8413dd7193de70966736044463b205834805a1f3b | Will the Iranian regime fall before 2027? | 1 | timestral-123m | 1,202 | -0.1% | -2.885e-04 | 3.205e-04 | no demonstrated difference |
| 0xbb4d51e6364066d92eb6f9b8413dd7193de70966736044463b205834805a1f3b | Will the Iranian regime fall before 2027? | 1 | timestral-209m | 1,202 | -0.2% | -2.561e-04 | 3.202e-04 | no demonstrated difference |
| 0xbb4d51e6364066d92eb6f9b8413dd7193de70966736044463b205834805a1f3b | Will the Iranian regime fall before 2027? | 6 | timestral-5m | 1,163 | +1.2% | -0.0010 | 3.892e-04 | no demonstrated difference |
| 0xbb4d51e6364066d92eb6f9b8413dd7193de70966736044463b205834805a1f3b | Will the Iranian regime fall before 2027? | 6 | timestral-28m | 1,163 | +1.5% | -0.0011 | 2.259e-04 | no demonstrated difference |
| 0xbb4d51e6364066d92eb6f9b8413dd7193de70966736044463b205834805a1f3b | Will the Iranian regime fall before 2027? | 6 | timestral-123m | 1,163 | +1.6% | -0.0011 | 2.000e-04 | no demonstrated difference |
| 0xbb4d51e6364066d92eb6f9b8413dd7193de70966736044463b205834805a1f3b | Will the Iranian regime fall before 2027? | 6 | timestral-209m | 1,163 | +2.2% | -0.0013 | 5.524e-05 | no demonstrated difference |
| 0xbb4d51e6364066d92eb6f9b8413dd7193de70966736044463b205834805a1f3b | Will the Iranian regime fall before 2027? | 24 | timestral-5m | 1,165 | +1.1% | -0.0031 | 0.0017 | no demonstrated difference |
| 0xbb4d51e6364066d92eb6f9b8413dd7193de70966736044463b205834805a1f3b | Will the Iranian regime fall before 2027? | 24 | timestral-28m | 1,165 | +1.9% | -0.0036 | 0.0012 | no demonstrated difference |
| 0xbb4d51e6364066d92eb6f9b8413dd7193de70966736044463b205834805a1f3b | Will the Iranian regime fall before 2027? | 24 | timestral-123m | 1,165 | +1.2% | -0.0033 | 0.0020 | no demonstrated difference |
| 0xbb4d51e6364066d92eb6f9b8413dd7193de70966736044463b205834805a1f3b | Will the Iranian regime fall before 2027? | 24 | timestral-209m | 1,165 | +1.2% | -0.0031 | 0.0017 | no demonstrated difference |
| 0xbe9d61d80c767264a0adc8a16453fbcaf0413e673e665cc7c14701691143fac0 | Will Ukraine recapture Crimean territory by December 31, 2026? | 1 | timestral-5m | 581 | -8.4% | 2.701e-04 | 0.0011 | worse |
| 0xbe9d61d80c767264a0adc8a16453fbcaf0413e673e665cc7c14701691143fac0 | Will Ukraine recapture Crimean territory by December 31, 2026? | 1 | timestral-28m | 581 | -4.1% | 1.053e-04 | 5.689e-04 | worse |
| 0xbe9d61d80c767264a0adc8a16453fbcaf0413e673e665cc7c14701691143fac0 | Will Ukraine recapture Crimean territory by December 31, 2026? | 1 | timestral-123m | 581 | -4.0% | -4.437e-05 | 6.694e-04 | no demonstrated difference |
| 0xbe9d61d80c767264a0adc8a16453fbcaf0413e673e665cc7c14701691143fac0 | Will Ukraine recapture Crimean territory by December 31, 2026? | 1 | timestral-209m | 581 | -3.7% | 6.193e-05 | 5.264e-04 | worse |
| 0xbe9d61d80c767264a0adc8a16453fbcaf0413e673e665cc7c14701691143fac0 | Will Ukraine recapture Crimean territory by December 31, 2026? | 6 | timestral-5m | 575 | +1.2% | -0.0013 | 0.0011 | no demonstrated difference |
| 0xbe9d61d80c767264a0adc8a16453fbcaf0413e673e665cc7c14701691143fac0 | Will Ukraine recapture Crimean territory by December 31, 2026? | 6 | timestral-28m | 575 | +3.1% | -0.0016 | 5.249e-04 | no demonstrated difference |
| 0xbe9d61d80c767264a0adc8a16453fbcaf0413e673e665cc7c14701691143fac0 | Will Ukraine recapture Crimean territory by December 31, 2026? | 6 | timestral-123m | 575 | +2.2% | -0.0016 | 9.173e-04 | no demonstrated difference |
| 0xbe9d61d80c767264a0adc8a16453fbcaf0413e673e665cc7c14701691143fac0 | Will Ukraine recapture Crimean territory by December 31, 2026? | 6 | timestral-209m | 575 | +3.3% | -0.0017 | 4.692e-04 | no demonstrated difference |
| 0xbe9d61d80c767264a0adc8a16453fbcaf0413e673e665cc7c14701691143fac0 | Will Ukraine recapture Crimean territory by December 31, 2026? | 24 | timestral-5m | 575 | +4.4% | -0.0055 | 0.0019 | no demonstrated difference |
| 0xbe9d61d80c767264a0adc8a16453fbcaf0413e673e665cc7c14701691143fac0 | Will Ukraine recapture Crimean territory by December 31, 2026? | 24 | timestral-28m | 575 | +5.6% | -0.0061 | 9.234e-04 | no demonstrated difference |
| 0xbe9d61d80c767264a0adc8a16453fbcaf0413e673e665cc7c14701691143fac0 | Will Ukraine recapture Crimean territory by December 31, 2026? | 24 | timestral-123m | 575 | +5.8% | -0.0062 | 8.874e-04 | no demonstrated difference |
| 0xbe9d61d80c767264a0adc8a16453fbcaf0413e673e665cc7c14701691143fac0 | Will Ukraine recapture Crimean territory by December 31, 2026? | 24 | timestral-209m | 575 | +6.3% | -0.0064 | 4.699e-04 | no demonstrated difference |
| 0xce3c54c3e773e8b3bf73e4c12af93205b21195d03b9c386e22f274b9acfc2c56 | Will Bitcoin dip to $50,000 by December 31, 2026? | 1 | timestral-5m | 901 | -7.0% | 4.713e-04 | 0.0013 | worse |
| 0xce3c54c3e773e8b3bf73e4c12af93205b21195d03b9c386e22f274b9acfc2c56 | Will Bitcoin dip to $50,000 by December 31, 2026? | 1 | timestral-28m | 901 | -4.1% | 2.288e-04 | 7.977e-04 | worse |
| 0xce3c54c3e773e8b3bf73e4c12af93205b21195d03b9c386e22f274b9acfc2c56 | Will Bitcoin dip to $50,000 by December 31, 2026? | 1 | timestral-123m | 901 | -2.7% | 4.846e-05 | 6.313e-04 | worse |
| 0xce3c54c3e773e8b3bf73e4c12af93205b21195d03b9c386e22f274b9acfc2c56 | Will Bitcoin dip to $50,000 by December 31, 2026? | 1 | timestral-209m | 901 | -2.2% | 2.363e-05 | 5.358e-04 | worse |
| 0xce3c54c3e773e8b3bf73e4c12af93205b21195d03b9c386e22f274b9acfc2c56 | Will Bitcoin dip to $50,000 by December 31, 2026? | 6 | timestral-5m | 868 | +1.4% | -0.0014 | 3.408e-04 | no demonstrated difference |
| 0xce3c54c3e773e8b3bf73e4c12af93205b21195d03b9c386e22f274b9acfc2c56 | Will Bitcoin dip to $50,000 by December 31, 2026? | 6 | timestral-28m | 868 | +2.8% | -0.0018 | -3.807e-04 | better |
| 0xce3c54c3e773e8b3bf73e4c12af93205b21195d03b9c386e22f274b9acfc2c56 | Will Bitcoin dip to $50,000 by December 31, 2026? | 6 | timestral-123m | 868 | +2.9% | -0.0018 | -4.105e-04 | better |
| 0xce3c54c3e773e8b3bf73e4c12af93205b21195d03b9c386e22f274b9acfc2c56 | Will Bitcoin dip to $50,000 by December 31, 2026? | 6 | timestral-209m | 868 | +2.9% | -0.0018 | -4.378e-04 | better |
| 0xce3c54c3e773e8b3bf73e4c12af93205b21195d03b9c386e22f274b9acfc2c56 | Will Bitcoin dip to $50,000 by December 31, 2026? | 24 | timestral-5m | 868 | +3.5% | -0.0067 | 0.0015 | no demonstrated difference |
| 0xce3c54c3e773e8b3bf73e4c12af93205b21195d03b9c386e22f274b9acfc2c56 | Will Bitcoin dip to $50,000 by December 31, 2026? | 24 | timestral-28m | 868 | +5.9% | -0.0080 | -0.0011 | better |
| 0xce3c54c3e773e8b3bf73e4c12af93205b21195d03b9c386e22f274b9acfc2c56 | Will Bitcoin dip to $50,000 by December 31, 2026? | 24 | timestral-123m | 868 | +5.3% | -0.0076 | -2.123e-04 | better |
| 0xce3c54c3e773e8b3bf73e4c12af93205b21195d03b9c386e22f274b9acfc2c56 | Will Bitcoin dip to $50,000 by December 31, 2026? | 24 | timestral-209m | 868 | +5.4% | -0.0075 | -6.548e-04 | better |
| 0xd4bbf7f6707c67beb736135ad32a41f6db41f8ae52d3ac4919650de9eeb94ed8 | Khamenei out as Supreme Leader of Iran by February 28? | 1 | timestral-5m | 148 | -0.3% | -0.0016 | 0.0016 | no demonstrated difference |
| 0xd4bbf7f6707c67beb736135ad32a41f6db41f8ae52d3ac4919650de9eeb94ed8 | Khamenei out as Supreme Leader of Iran by February 28? | 1 | timestral-28m | 148 | +2.6% | -0.0023 | 6.250e-04 | no demonstrated difference |
| 0xd4bbf7f6707c67beb736135ad32a41f6db41f8ae52d3ac4919650de9eeb94ed8 | Khamenei out as Supreme Leader of Iran by February 28? | 1 | timestral-123m | 148 | +1.6% | -0.0020 | 0.0011 | no demonstrated difference |
| 0xd4bbf7f6707c67beb736135ad32a41f6db41f8ae52d3ac4919650de9eeb94ed8 | Khamenei out as Supreme Leader of Iran by February 28? | 1 | timestral-209m | 148 | +2.9% | -0.0020 | 4.886e-04 | no demonstrated difference |
| 0xd4bbf7f6707c67beb736135ad32a41f6db41f8ae52d3ac4919650de9eeb94ed8 | Khamenei out as Supreme Leader of Iran by February 28? | 6 | timestral-5m | 151 | +3.5% | -0.0070 | 0.0019 | no demonstrated difference |
| 0xd4bbf7f6707c67beb736135ad32a41f6db41f8ae52d3ac4919650de9eeb94ed8 | Khamenei out as Supreme Leader of Iran by February 28? | 6 | timestral-28m | 151 | +3.1% | -0.0058 | 0.0017 | no demonstrated difference |
| 0xd4bbf7f6707c67beb736135ad32a41f6db41f8ae52d3ac4919650de9eeb94ed8 | Khamenei out as Supreme Leader of Iran by February 28? | 6 | timestral-123m | 151 | +2.2% | -0.0058 | 0.0035 | no demonstrated difference |
| 0xd4bbf7f6707c67beb736135ad32a41f6db41f8ae52d3ac4919650de9eeb94ed8 | Khamenei out as Supreme Leader of Iran by February 28? | 6 | timestral-209m | 151 | +2.6% | -0.0056 | 0.0028 | no demonstrated difference |
| 0xd4bbf7f6707c67beb736135ad32a41f6db41f8ae52d3ac4919650de9eeb94ed8 | Khamenei out as Supreme Leader of Iran by February 28? | 24 | timestral-5m | 148 | -0.3% | -0.0165 | 0.0190 | no demonstrated difference |
| 0xd4bbf7f6707c67beb736135ad32a41f6db41f8ae52d3ac4919650de9eeb94ed8 | Khamenei out as Supreme Leader of Iran by February 28? | 24 | timestral-28m | 148 | +0.4% | -0.0151 | 0.0158 | no demonstrated difference |
| 0xd4bbf7f6707c67beb736135ad32a41f6db41f8ae52d3ac4919650de9eeb94ed8 | Khamenei out as Supreme Leader of Iran by February 28? | 24 | timestral-123m | 148 | -2.3% | -0.0135 | 0.0216 | no demonstrated difference |
| 0xd4bbf7f6707c67beb736135ad32a41f6db41f8ae52d3ac4919650de9eeb94ed8 | Khamenei out as Supreme Leader of Iran by February 28? | 24 | timestral-209m | 148 | -0.3% | -0.0149 | 0.0169 | no demonstrated difference |
| 0xd595eb9b81885ff018738300c79047e3ec89e87294424f57a29a7fa9162bf116 | Will Trump acquire Greenland before 2027? | 1 | timestral-5m | 1,074 | -3.7% | 2.847e-05 | 3.710e-04 | worse |
| 0xd595eb9b81885ff018738300c79047e3ec89e87294424f57a29a7fa9162bf116 | Will Trump acquire Greenland before 2027? | 1 | timestral-28m | 1,074 | -1.5% | -6.654e-05 | 2.245e-04 | no demonstrated difference |
| 0xd595eb9b81885ff018738300c79047e3ec89e87294424f57a29a7fa9162bf116 | Will Trump acquire Greenland before 2027? | 1 | timestral-123m | 1,074 | -0.7% | -1.089e-04 | 1.958e-04 | no demonstrated difference |
| 0xd595eb9b81885ff018738300c79047e3ec89e87294424f57a29a7fa9162bf116 | Will Trump acquire Greenland before 2027? | 1 | timestral-209m | 1,074 | -0.3% | -1.310e-04 | 1.575e-04 | no demonstrated difference |
| 0xd595eb9b81885ff018738300c79047e3ec89e87294424f57a29a7fa9162bf116 | Will Trump acquire Greenland before 2027? | 6 | timestral-5m | 1,055 | +3.6% | -9.942e-04 | -7.757e-05 | better |
| 0xd595eb9b81885ff018738300c79047e3ec89e87294424f57a29a7fa9162bf116 | Will Trump acquire Greenland before 2027? | 6 | timestral-28m | 1,055 | +4.0% | -0.0010 | -2.017e-04 | better |
| 0xd595eb9b81885ff018738300c79047e3ec89e87294424f57a29a7fa9162bf116 | Will Trump acquire Greenland before 2027? | 6 | timestral-123m | 1,055 | +4.4% | -0.0011 | -2.574e-04 | better |
| 0xd595eb9b81885ff018738300c79047e3ec89e87294424f57a29a7fa9162bf116 | Will Trump acquire Greenland before 2027? | 6 | timestral-209m | 1,055 | +4.2% | -0.0011 | -2.472e-04 | better |
| 0xd595eb9b81885ff018738300c79047e3ec89e87294424f57a29a7fa9162bf116 | Will Trump acquire Greenland before 2027? | 24 | timestral-5m | 1,053 | +3.4% | -0.0023 | 3.664e-04 | no demonstrated difference |
| 0xd595eb9b81885ff018738300c79047e3ec89e87294424f57a29a7fa9162bf116 | Will Trump acquire Greenland before 2027? | 24 | timestral-28m | 1,053 | +4.1% | -0.0025 | 2.033e-04 | no demonstrated difference |
| 0xd595eb9b81885ff018738300c79047e3ec89e87294424f57a29a7fa9162bf116 | Will Trump acquire Greenland before 2027? | 24 | timestral-123m | 1,053 | +3.5% | -0.0025 | 6.325e-04 | no demonstrated difference |
| 0xd595eb9b81885ff018738300c79047e3ec89e87294424f57a29a7fa9162bf116 | Will Trump acquire Greenland before 2027? | 24 | timestral-209m | 1,053 | +3.2% | -0.0022 | 4.622e-04 | no demonstrated difference |
| 0xd86a816093fcd0a0e1ca440bc5ce199bd3c5a8d6139e044b076958164f8c5423 | US x Iran permanent peace deal by June 15, 2026? | 1 | timestral-5m | 91 | +6.8% | -0.0145 | 0.0017 | no demonstrated difference |
| 0xd86a816093fcd0a0e1ca440bc5ce199bd3c5a8d6139e044b076958164f8c5423 | US x Iran permanent peace deal by June 15, 2026? | 1 | timestral-28m | 91 | +7.1% | -0.0137 | 0.0010 | no demonstrated difference |
| 0xd86a816093fcd0a0e1ca440bc5ce199bd3c5a8d6139e044b076958164f8c5423 | US x Iran permanent peace deal by June 15, 2026? | 1 | timestral-123m | 91 | +6.9% | -0.0128 | 5.932e-04 | no demonstrated difference |
| 0xd86a816093fcd0a0e1ca440bc5ce199bd3c5a8d6139e044b076958164f8c5423 | US x Iran permanent peace deal by June 15, 2026? | 1 | timestral-209m | 91 | +6.8% | -0.0109 | -2.723e-04 | better |
| 0xd86a816093fcd0a0e1ca440bc5ce199bd3c5a8d6139e044b076958164f8c5423 | US x Iran permanent peace deal by June 15, 2026? | 6 | timestral-5m | 90 | -3.0% | -0.0044 | 0.0171 | no demonstrated difference |
| 0xd86a816093fcd0a0e1ca440bc5ce199bd3c5a8d6139e044b076958164f8c5423 | US x Iran permanent peace deal by June 15, 2026? | 6 | timestral-28m | 90 | -1.8% | -0.0043 | 0.0127 | no demonstrated difference |
| 0xd86a816093fcd0a0e1ca440bc5ce199bd3c5a8d6139e044b076958164f8c5423 | US x Iran permanent peace deal by June 15, 2026? | 6 | timestral-123m | 90 | -0.6% | -0.0066 | 0.0108 | no demonstrated difference |
| 0xd86a816093fcd0a0e1ca440bc5ce199bd3c5a8d6139e044b076958164f8c5423 | US x Iran permanent peace deal by June 15, 2026? | 6 | timestral-209m | 90 | -0.1% | -0.0094 | 0.0104 | no demonstrated difference |
| 0xd86a816093fcd0a0e1ca440bc5ce199bd3c5a8d6139e044b076958164f8c5423 | US x Iran permanent peace deal by June 15, 2026? | 24 | timestral-5m | 87 | +0.2% | -0.0311 | 0.0279 | no demonstrated difference |
| 0xd86a816093fcd0a0e1ca440bc5ce199bd3c5a8d6139e044b076958164f8c5423 | US x Iran permanent peace deal by June 15, 2026? | 24 | timestral-28m | 87 | +2.0% | -0.0398 | 0.0254 | no demonstrated difference |
| 0xd86a816093fcd0a0e1ca440bc5ce199bd3c5a8d6139e044b076958164f8c5423 | US x Iran permanent peace deal by June 15, 2026? | 24 | timestral-123m | 87 | +2.9% | -0.0457 | 0.0254 | no demonstrated difference |
| 0xd86a816093fcd0a0e1ca440bc5ce199bd3c5a8d6139e044b076958164f8c5423 | US x Iran permanent peace deal by June 15, 2026? | 24 | timestral-209m | 87 | +2.7% | -0.0430 | 0.0248 | no demonstrated difference |
| 0xd9fb1184af0064e5e34b129f5b79afa5a17b7e32f2953ab05efed82315fee6d4 | Will China invade Taiwan by end of 2026? | 1 | timestral-5m | 1,684 | -6.6% | 1.691e-04 | 4.429e-04 | worse |
| 0xd9fb1184af0064e5e34b129f5b79afa5a17b7e32f2953ab05efed82315fee6d4 | Will China invade Taiwan by end of 2026? | 1 | timestral-28m | 1,684 | -3.7% | 6.224e-05 | 2.801e-04 | worse |
| 0xd9fb1184af0064e5e34b129f5b79afa5a17b7e32f2953ab05efed82315fee6d4 | Will China invade Taiwan by end of 2026? | 1 | timestral-123m | 1,684 | -2.4% | -2.070e-05 | 2.165e-04 | no demonstrated difference |
| 0xd9fb1184af0064e5e34b129f5b79afa5a17b7e32f2953ab05efed82315fee6d4 | Will China invade Taiwan by end of 2026? | 1 | timestral-209m | 1,684 | -1.9% | -1.642e-05 | 1.787e-04 | no demonstrated difference |
| 0xd9fb1184af0064e5e34b129f5b79afa5a17b7e32f2953ab05efed82315fee6d4 | Will China invade Taiwan by end of 2026? | 6 | timestral-5m | 1,681 | +0.8% | -4.330e-04 | 1.949e-04 | no demonstrated difference |
| 0xd9fb1184af0064e5e34b129f5b79afa5a17b7e32f2953ab05efed82315fee6d4 | Will China invade Taiwan by end of 2026? | 6 | timestral-28m | 1,681 | +2.0% | -5.582e-04 | -3.330e-05 | better |
| 0xd9fb1184af0064e5e34b129f5b79afa5a17b7e32f2953ab05efed82315fee6d4 | Will China invade Taiwan by end of 2026? | 6 | timestral-123m | 1,681 | +2.4% | -6.641e-04 | -5.908e-05 | better |
| 0xd9fb1184af0064e5e34b129f5b79afa5a17b7e32f2953ab05efed82315fee6d4 | Will China invade Taiwan by end of 2026? | 6 | timestral-209m | 1,681 | +2.3% | -6.243e-04 | -6.534e-05 | better |
| 0xd9fb1184af0064e5e34b129f5b79afa5a17b7e32f2953ab05efed82315fee6d4 | Will China invade Taiwan by end of 2026? | 24 | timestral-5m | 1,682 | +7.1% | -0.0035 | -0.0012 | better |
| 0xd9fb1184af0064e5e34b129f5b79afa5a17b7e32f2953ab05efed82315fee6d4 | Will China invade Taiwan by end of 2026? | 24 | timestral-28m | 1,682 | +7.0% | -0.0034 | -0.0012 | better |
| 0xd9fb1184af0064e5e34b129f5b79afa5a17b7e32f2953ab05efed82315fee6d4 | Will China invade Taiwan by end of 2026? | 24 | timestral-123m | 1,682 | +8.2% | -0.0039 | -0.0015 | better |
| 0xd9fb1184af0064e5e34b129f5b79afa5a17b7e32f2953ab05efed82315fee6d4 | Will China invade Taiwan by end of 2026? | 24 | timestral-209m | 1,682 | +7.2% | -0.0034 | -0.0012 | better |
| 0xdaa4866bae18be58c5a79d2aeeffd035ec78f1bb49dbd88f72993997778a990f | Will Bitcoin reach $100,000 by December 31, 2026? | 1 | timestral-5m | 1,181 | -6.4% | 4.875e-04 | 0.0011 | worse |
| 0xdaa4866bae18be58c5a79d2aeeffd035ec78f1bb49dbd88f72993997778a990f | Will Bitcoin reach $100,000 by December 31, 2026? | 1 | timestral-28m | 1,181 | -2.2% | 1.213e-05 | 5.212e-04 | worse |
| 0xdaa4866bae18be58c5a79d2aeeffd035ec78f1bb49dbd88f72993997778a990f | Will Bitcoin reach $100,000 by December 31, 2026? | 1 | timestral-123m | 1,181 | -1.1% | -1.058e-04 | 3.741e-04 | no demonstrated difference |
| 0xdaa4866bae18be58c5a79d2aeeffd035ec78f1bb49dbd88f72993997778a990f | Will Bitcoin reach $100,000 by December 31, 2026? | 1 | timestral-209m | 1,181 | -1.0% | -1.109e-04 | 3.395e-04 | no demonstrated difference |
| 0xdaa4866bae18be58c5a79d2aeeffd035ec78f1bb49dbd88f72993997778a990f | Will Bitcoin reach $100,000 by December 31, 2026? | 6 | timestral-5m | 1,179 | -0.0% | -8.806e-04 | 7.083e-04 | no demonstrated difference |
| 0xdaa4866bae18be58c5a79d2aeeffd035ec78f1bb49dbd88f72993997778a990f | Will Bitcoin reach $100,000 by December 31, 2026? | 6 | timestral-28m | 1,179 | +2.0% | -0.0016 | -9.302e-05 | better |
| 0xdaa4866bae18be58c5a79d2aeeffd035ec78f1bb49dbd88f72993997778a990f | Will Bitcoin reach $100,000 by December 31, 2026? | 6 | timestral-123m | 1,179 | +1.6% | -0.0014 | -3.919e-05 | better |
| 0xdaa4866bae18be58c5a79d2aeeffd035ec78f1bb49dbd88f72993997778a990f | Will Bitcoin reach $100,000 by December 31, 2026? | 6 | timestral-209m | 1,179 | +1.4% | -0.0013 | 7.758e-05 | no demonstrated difference |
| 0xdaa4866bae18be58c5a79d2aeeffd035ec78f1bb49dbd88f72993997778a990f | Will Bitcoin reach $100,000 by December 31, 2026? | 24 | timestral-5m | 1,178 | +1.0% | -0.0046 | 0.0026 | no demonstrated difference |
| 0xdaa4866bae18be58c5a79d2aeeffd035ec78f1bb49dbd88f72993997778a990f | Will Bitcoin reach $100,000 by December 31, 2026? | 24 | timestral-28m | 1,178 | +3.6% | -0.0064 | 3.480e-04 | no demonstrated difference |
| 0xdaa4866bae18be58c5a79d2aeeffd035ec78f1bb49dbd88f72993997778a990f | Will Bitcoin reach $100,000 by December 31, 2026? | 24 | timestral-123m | 1,178 | +2.9% | -0.0057 | 7.466e-04 | no demonstrated difference |
| 0xdaa4866bae18be58c5a79d2aeeffd035ec78f1bb49dbd88f72993997778a990f | Will Bitcoin reach $100,000 by December 31, 2026? | 24 | timestral-209m | 1,178 | +3.0% | -0.0057 | 4.042e-04 | no demonstrated difference |
| 0xe6d5e5da83874cd82c9b651a8a5d4fc541a800a295fb62e85124b4f5a04a4b7d | Will China invade Taiwan by December 31, 2027? | 1 | timestral-5m | 744 | -14.2% | 1.705e-04 | 6.225e-04 | worse |
| 0xe6d5e5da83874cd82c9b651a8a5d4fc541a800a295fb62e85124b4f5a04a4b7d | Will China invade Taiwan by December 31, 2027? | 1 | timestral-28m | 744 | -8.2% | 8.372e-05 | 3.585e-04 | worse |
| 0xe6d5e5da83874cd82c9b651a8a5d4fc541a800a295fb62e85124b4f5a04a4b7d | Will China invade Taiwan by December 31, 2027? | 1 | timestral-123m | 744 | -7.9% | 5.803e-05 | 3.793e-04 | worse |
| 0xe6d5e5da83874cd82c9b651a8a5d4fc541a800a295fb62e85124b4f5a04a4b7d | Will China invade Taiwan by December 31, 2027? | 1 | timestral-209m | 744 | -8.0% | 6.504e-05 | 3.827e-04 | worse |
| 0xe6d5e5da83874cd82c9b651a8a5d4fc541a800a295fb62e85124b4f5a04a4b7d | Will China invade Taiwan by December 31, 2027? | 6 | timestral-5m | 722 | -0.3% | -4.683e-04 | 5.187e-04 | no demonstrated difference |
| 0xe6d5e5da83874cd82c9b651a8a5d4fc541a800a295fb62e85124b4f5a04a4b7d | Will China invade Taiwan by December 31, 2027? | 6 | timestral-28m | 722 | +1.4% | -5.882e-04 | 3.087e-04 | no demonstrated difference |
| 0xe6d5e5da83874cd82c9b651a8a5d4fc541a800a295fb62e85124b4f5a04a4b7d | Will China invade Taiwan by December 31, 2027? | 6 | timestral-123m | 722 | +2.7% | -7.175e-04 | 1.980e-04 | no demonstrated difference |
| 0xe6d5e5da83874cd82c9b651a8a5d4fc541a800a295fb62e85124b4f5a04a4b7d | Will China invade Taiwan by December 31, 2027? | 6 | timestral-209m | 722 | +2.2% | -6.650e-04 | 2.576e-04 | no demonstrated difference |
| 0xe6d5e5da83874cd82c9b651a8a5d4fc541a800a295fb62e85124b4f5a04a4b7d | Will China invade Taiwan by December 31, 2027? | 24 | timestral-5m | 721 | +7.2% | -0.0033 | -4.727e-05 | better |
| 0xe6d5e5da83874cd82c9b651a8a5d4fc541a800a295fb62e85124b4f5a04a4b7d | Will China invade Taiwan by December 31, 2027? | 24 | timestral-28m | 721 | +7.1% | -0.0032 | -2.581e-05 | better |
| 0xe6d5e5da83874cd82c9b651a8a5d4fc541a800a295fb62e85124b4f5a04a4b7d | Will China invade Taiwan by December 31, 2027? | 24 | timestral-123m | 721 | +7.8% | -0.0034 | -3.871e-06 | better |
| 0xe6d5e5da83874cd82c9b651a8a5d4fc541a800a295fb62e85124b4f5a04a4b7d | Will China invade Taiwan by December 31, 2027? | 24 | timestral-209m | 721 | +7.4% | -0.0033 | 3.216e-05 | no demonstrated difference |
| 0xf2bf04609e7458df56c9bb4b1e051286dea11da1c944bbc1dafbcc6b76904e52 | NATO x Russia military clash by December 31, 2026? | 1 | timestral-5m | 1,010 | -5.6% | 4.192e-04 | 0.0010 | worse |
| 0xf2bf04609e7458df56c9bb4b1e051286dea11da1c944bbc1dafbcc6b76904e52 | NATO x Russia military clash by December 31, 2026? | 1 | timestral-28m | 1,010 | -1.1% | -1.936e-04 | 5.198e-04 | no demonstrated difference |
| 0xf2bf04609e7458df56c9bb4b1e051286dea11da1c944bbc1dafbcc6b76904e52 | NATO x Russia military clash by December 31, 2026? | 1 | timestral-123m | 1,010 | +0.5% | -4.824e-04 | 3.966e-04 | no demonstrated difference |
| 0xf2bf04609e7458df56c9bb4b1e051286dea11da1c944bbc1dafbcc6b76904e52 | NATO x Russia military clash by December 31, 2026? | 1 | timestral-209m | 1,010 | +0.7% | -4.825e-04 | 3.025e-04 | no demonstrated difference |
| 0xf2bf04609e7458df56c9bb4b1e051286dea11da1c944bbc1dafbcc6b76904e52 | NATO x Russia military clash by December 31, 2026? | 6 | timestral-5m | 985 | +1.8% | -0.0021 | 4.380e-04 | no demonstrated difference |
| 0xf2bf04609e7458df56c9bb4b1e051286dea11da1c944bbc1dafbcc6b76904e52 | NATO x Russia military clash by December 31, 2026? | 6 | timestral-28m | 985 | +2.9% | -0.0024 | -4.031e-05 | better |
| 0xf2bf04609e7458df56c9bb4b1e051286dea11da1c944bbc1dafbcc6b76904e52 | NATO x Russia military clash by December 31, 2026? | 6 | timestral-123m | 985 | +3.4% | -0.0027 | -8.794e-05 | better |
| 0xf2bf04609e7458df56c9bb4b1e051286dea11da1c944bbc1dafbcc6b76904e52 | NATO x Russia military clash by December 31, 2026? | 6 | timestral-209m | 985 | +3.7% | -0.0027 | -3.166e-04 | better |
| 0xf2bf04609e7458df56c9bb4b1e051286dea11da1c944bbc1dafbcc6b76904e52 | NATO x Russia military clash by December 31, 2026? | 24 | timestral-5m | 984 | +1.2% | -0.0050 | 0.0034 | no demonstrated difference |
| 0xf2bf04609e7458df56c9bb4b1e051286dea11da1c944bbc1dafbcc6b76904e52 | NATO x Russia military clash by December 31, 2026? | 24 | timestral-28m | 984 | +3.1% | -0.0060 | 0.0010 | no demonstrated difference |
| 0xf2bf04609e7458df56c9bb4b1e051286dea11da1c944bbc1dafbcc6b76904e52 | NATO x Russia military clash by December 31, 2026? | 24 | timestral-123m | 984 | +2.4% | -0.0059 | 0.0019 | no demonstrated difference |
| 0xf2bf04609e7458df56c9bb4b1e051286dea11da1c944bbc1dafbcc6b76904e52 | NATO x Russia military clash by December 31, 2026? | 24 | timestral-209m | 984 | +3.0% | -0.0059 | 0.0013 | no demonstrated difference |
| 0xf2ce8d3897ac5009a131637d3575f1f91c579bd08eecce6ae2b2da0f32bbe6f1 | Xi Jinping out in 2025? | 1 | timestral-5m | 776 | -2.6% | -2.133e-04 | 9.415e-04 | no demonstrated difference |
| 0xf2ce8d3897ac5009a131637d3575f1f91c579bd08eecce6ae2b2da0f32bbe6f1 | Xi Jinping out in 2025? | 1 | timestral-28m | 776 | +0.1% | -4.585e-04 | 4.736e-04 | no demonstrated difference |
| 0xf2ce8d3897ac5009a131637d3575f1f91c579bd08eecce6ae2b2da0f32bbe6f1 | Xi Jinping out in 2025? | 1 | timestral-123m | 776 | +1.2% | -7.438e-04 | 3.697e-04 | no demonstrated difference |
| 0xf2ce8d3897ac5009a131637d3575f1f91c579bd08eecce6ae2b2da0f32bbe6f1 | Xi Jinping out in 2025? | 1 | timestral-209m | 776 | +1.5% | -7.571e-04 | 2.735e-04 | no demonstrated difference |
| 0xf2ce8d3897ac5009a131637d3575f1f91c579bd08eecce6ae2b2da0f32bbe6f1 | Xi Jinping out in 2025? | 6 | timestral-5m | 775 | +4.0% | -0.0028 | -2.698e-04 | better |
| 0xf2ce8d3897ac5009a131637d3575f1f91c579bd08eecce6ae2b2da0f32bbe6f1 | Xi Jinping out in 2025? | 6 | timestral-28m | 775 | +5.6% | -0.0032 | -9.955e-04 | better |
| 0xf2ce8d3897ac5009a131637d3575f1f91c579bd08eecce6ae2b2da0f32bbe6f1 | Xi Jinping out in 2025? | 6 | timestral-123m | 775 | +5.8% | -0.0034 | -0.0011 | better |
| 0xf2ce8d3897ac5009a131637d3575f1f91c579bd08eecce6ae2b2da0f32bbe6f1 | Xi Jinping out in 2025? | 6 | timestral-209m | 775 | +6.2% | -0.0035 | -0.0013 | better |
| 0xf2ce8d3897ac5009a131637d3575f1f91c579bd08eecce6ae2b2da0f32bbe6f1 | Xi Jinping out in 2025? | 24 | timestral-5m | 772 | +3.1% | -0.0068 | 0.0016 | no demonstrated difference |
| 0xf2ce8d3897ac5009a131637d3575f1f91c579bd08eecce6ae2b2da0f32bbe6f1 | Xi Jinping out in 2025? | 24 | timestral-28m | 772 | +3.6% | -0.0068 | 9.078e-04 | no demonstrated difference |
| 0xf2ce8d3897ac5009a131637d3575f1f91c579bd08eecce6ae2b2da0f32bbe6f1 | Xi Jinping out in 2025? | 24 | timestral-123m | 772 | +3.5% | -0.0068 | 0.0012 | no demonstrated difference |
| 0xf2ce8d3897ac5009a131637d3575f1f91c579bd08eecce6ae2b2da0f32bbe6f1 | Xi Jinping out in 2025? | 24 | timestral-209m | 772 | +3.4% | -0.0068 | 0.0010 | no demonstrated difference |

</details>

## Calibration

Empirical coverage of central prediction intervals (nominal in the header) and the quantile calibration error (mean |share of outcomes ≤ q_τ − τ| over all levels), the PIT total-variation distance (0 = outcomes fall in each quantile bin as often as its width predicts) and the interval (Winkler) score of the 90% interval, which charges width and misses together. Coverage is only meaningful with a large n; a narrow interval is good only if its coverage holds.

| h | model | n | cov 50% | width 50% | cov 80% | width 80% | cov 90% | width 90% | cov 98% | width 98% | QCE | PIT TV | IS 90% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | linear_trend | 38,107 | 0.5168 | 0.0659 | 0.7861 | 0.1538 | 0.8795 | 0.2216 | 0.9560 | 0.3573 | 0.0238 | 0.0569 | 0.3722 |
| 1 | momentum | 38,107 | 0.5660 | 0.0079 | 0.8003 | 0.0329 | 0.8906 | 0.0666 | 0.9696 | 0.1848 | 0.0925 | 0.2110 | 0.1595 |
| 1 | moving_average | 38,107 | 0.5381 | 0.0454 | 0.7927 | 0.1264 | 0.8832 | 0.1973 | 0.9594 | 0.3370 | 0.0425 | 0.0924 | 0.3500 |
| 1 | persistence | 38,107 | 0.8209 | 0.0024 | 0.8704 | 0.0242 | 0.9138 | 0.0592 | 0.9721 | 0.1786 | 0.3268 | 0.6420 | 0.1516 |
| 1 | timestral-123m | 38,107 | 0.6989 | 0.0097 | 0.8700 | 0.0339 | 0.9171 | 0.0640 | 0.9708 | 0.1895 | 0.0563 | 0.2082 | 0.1369 |
| 1 | timestral-209m | 38,107 | 0.6421 | 0.0087 | 0.8533 | 0.0297 | 0.9094 | 0.0592 | 0.9699 | 0.1886 | 0.0481 | 0.1725 | 0.1374 |
| 1 | timestral-28m | 38,107 | 0.6394 | 0.0099 | 0.8516 | 0.0310 | 0.9120 | 0.0615 | 0.9726 | 0.2009 | 0.0492 | 0.2223 | 0.1377 |
| 1 | timestral-5m | 38,107 | 0.6431 | 0.0127 | 0.8638 | 0.0347 | 0.9074 | 0.0627 | 0.9682 | 0.1806 | 0.0443 | 0.2075 | 0.1382 |
| 1 | zero | 38,107 | 0.5484 | 0.1638 | 0.7709 | 0.2887 | 0.8562 | 0.3495 | 0.9435 | 0.4320 | 0.1733 | 0.3067 | 0.6566 |
| 6 | linear_trend | 37,528 | 0.5120 | 0.0912 | 0.7718 | 0.2084 | 0.8641 | 0.2962 | 0.9372 | 0.4512 | 0.0260 | 0.0671 | 0.5014 |
| 6 | momentum | 37,528 | 0.5448 | 0.0539 | 0.7894 | 0.1485 | 0.8783 | 0.2321 | 0.9548 | 0.4330 | 0.0732 | 0.1763 | 0.4195 |
| 6 | moving_average | 37,528 | 0.5216 | 0.0638 | 0.7754 | 0.1666 | 0.8662 | 0.2542 | 0.9396 | 0.3937 | 0.0405 | 0.0920 | 0.4569 |
| 6 | persistence | 37,528 | 0.6450 | 0.0287 | 0.8099 | 0.1115 | 0.8858 | 0.1873 | 0.9561 | 0.3742 | 0.1858 | 0.3916 | 0.3588 |
| 6 | timestral-123m | 37,528 | 0.6162 | 0.0378 | 0.8167 | 0.1180 | 0.8933 | 0.1926 | 0.9664 | 0.4251 | 0.0365 | 0.1591 | 0.3292 |
| 6 | timestral-209m | 37,528 | 0.6145 | 0.0369 | 0.8142 | 0.1168 | 0.8903 | 0.1913 | 0.9659 | 0.4216 | 0.0361 | 0.1552 | 0.3295 |
| 6 | timestral-28m | 37,528 | 0.5717 | 0.0368 | 0.8130 | 0.1179 | 0.8921 | 0.1938 | 0.9671 | 0.4250 | 0.0283 | 0.1268 | 0.3313 |
| 6 | timestral-5m | 37,528 | 0.6051 | 0.0420 | 0.8148 | 0.1198 | 0.8915 | 0.1904 | 0.9606 | 0.3867 | 0.0298 | 0.1377 | 0.3311 |
| 6 | zero | 37,528 | 0.5354 | 0.1627 | 0.7495 | 0.2867 | 0.8341 | 0.3464 | 0.9169 | 0.4280 | 0.1732 | 0.3160 | 0.7186 |
| 24 | linear_trend | 37,437 | 0.4896 | 0.1790 | 0.7534 | 0.3950 | 0.8200 | 0.5036 | 0.8749 | 0.6538 | 0.0309 | 0.1182 | 0.9417 |
| 24 | momentum | 37,437 | 0.5248 | 0.1808 | 0.7741 | 0.4137 | 0.8585 | 0.5917 | 0.9152 | 0.8490 | 0.0524 | 0.1424 | 1.024 |
| 24 | moving_average | 37,437 | 0.4823 | 0.1166 | 0.7361 | 0.2765 | 0.8093 | 0.3528 | 0.8685 | 0.4494 | 0.0425 | 0.1346 | 0.7436 |
| 24 | persistence | 37,437 | 0.5532 | 0.0983 | 0.7749 | 0.2596 | 0.8427 | 0.3465 | 0.8974 | 0.4651 | 0.1001 | 0.2324 | 0.6779 |
| 24 | timestral-123m | 37,437 | 0.5444 | 0.1062 | 0.7924 | 0.2601 | 0.8844 | 0.3906 | 0.9622 | 0.8591 | 0.0343 | 0.0944 | 0.6156 |
| 24 | timestral-209m | 37,437 | 0.5531 | 0.1067 | 0.7994 | 0.2650 | 0.8880 | 0.4032 | 0.9642 | 0.9051 | 0.0294 | 0.1075 | 0.6220 |
| 24 | timestral-28m | 37,437 | 0.5288 | 0.1085 | 0.7984 | 0.2629 | 0.8797 | 0.3864 | 0.9584 | 0.8019 | 0.0329 | 0.0787 | 0.6177 |
| 24 | timestral-5m | 37,437 | 0.5339 | 0.1051 | 0.7839 | 0.2507 | 0.8642 | 0.3601 | 0.9520 | 0.7140 | 0.0221 | 0.0947 | 0.6196 |
| 24 | zero | 37,437 | 0.4947 | 0.1551 | 0.6897 | 0.2748 | 0.7654 | 0.3318 | 0.8402 | 0.4076 | 0.1734 | 0.3485 | 0.9637 |

## Performance over time

CRPS_q improvement over `persistence` per month of origin (positive = better). A model that only wins in one period has not shown a stable advantage.


**h = 1**

| period | n | timestral-5m | timestral-28m | timestral-123m | timestral-209m | zero | moving_average | momentum | linear_trend |
|---|---|---|---|---|---|---|---|---|---|
| 2025-06 | 44 | +1.8% | +4.2% | +5.5% | +5.1% | -59.0% | -42.7% | -4.5% | -64.1% |
| 2025-07 | 280 | +1.9% | +4.5% | +4.5% | +4.3% | -710.6% | -198.5% | -18.3% | -215.8% |
| 2025-08 | 620 | -11.9% | -6.1% | -4.8% | -4.2% | -1286.4% | -312.6% | -26.3% | -395.1% |
| 2025-09 | 596 | -13.8% | -8.3% | -7.6% | -6.0% | -1218.1% | -410.0% | -36.3% | -509.8% |
| 2025-10 | 615 | -3.3% | -0.8% | +0.6% | +1.1% | -725.4% | -206.5% | -20.0% | -252.3% |
| 2025-11 | 1,022 | -2.5% | +0.2% | +1.4% | +0.6% | -832.0% | -199.6% | -17.1% | -261.8% |
| 2025-12 | 2,129 | -1.1% | +0.7% | +2.1% | +1.6% | -599.7% | -166.7% | -14.8% | -212.7% |
| 2026-01 | 2,653 | -1.1% | +1.2% | +2.6% | +2.5% | -744.8% | -198.7% | -14.5% | -249.5% |
| 2026-02 | 2,650 | -1.2% | +1.2% | +2.0% | +1.8% | -713.9% | -196.6% | -11.1% | -240.5% |
| 2026-03 | 2,943 | -2.4% | -0.4% | +0.9% | +0.9% | -667.6% | -173.7% | -11.7% | -223.7% |
| 2026-04 | 814 | -6.0% | -5.1% | -5.1% | -3.7% | -719.4% | -225.1% | -15.3% | -281.6% |
| 2026-05 | 3,920 | -3.0% | -0.3% | +0.9% | +1.3% | -735.3% | -202.1% | -13.1% | -244.4% |
| 2026-06 | 3,896 | -5.7% | -1.4% | -1.2% | -0.4% | -860.1% | -206.3% | -15.0% | -251.4% |
| 2026-07 | 3,943 | -11.0% | -5.7% | -5.0% | -4.1% | -1263.1% | -303.9% | -24.5% | -381.6% |
| 2026-08 | 4,259 | -9.2% | -4.7% | -4.4% | -3.0% | -1476.6% | -326.7% | -26.4% | -422.1% |
| 2026-09 | 4,174 | -7.1% | -2.9% | -1.6% | -1.6% | -980.1% | -274.2% | -22.0% | -351.6% |
| 2026-10 | 3,491 | -11.6% | -7.0% | -6.1% | -4.7% | -1051.5% | -314.9% | -23.9% | -382.2% |
| 2026-11 | 58 | -11.8% | -9.5% | -11.5% | -10.4% | -1146.5% | -344.0% | -26.5% | -428.9% |

**h = 6**

| period | n | timestral-5m | timestral-28m | timestral-123m | timestral-209m | zero | moving_average | momentum | linear_trend |
|---|---|---|---|---|---|---|---|---|---|
| 2025-06 | 44 | +10.4% | +10.3% | +12.6% | +11.5% | -2.3% | +11.1% | -20.1% | -9.1% |
| 2025-07 | 280 | +8.1% | +8.1% | +9.0% | +9.4% | -162.1% | -12.6% | -26.2% | -23.9% |
| 2025-08 | 620 | -2.1% | +0.5% | +1.1% | +1.5% | -324.7% | -58.6% | -40.2% | -100.5% |
| 2025-09 | 592 | +2.4% | +4.2% | +3.5% | +4.4% | -212.1% | -56.3% | -39.9% | -88.0% |
| 2025-10 | 610 | +1.2% | +2.9% | +3.6% | +4.0% | -186.4% | -40.9% | -30.2% | -67.0% |
| 2025-11 | 1,018 | -0.3% | +1.0% | +2.0% | +1.7% | -256.7% | -48.7% | -30.8% | -82.7% |
| 2025-12 | 2,164 | +2.7% | +3.5% | +3.7% | +3.9% | -162.8% | -28.8% | -28.3% | -52.9% |
| 2026-01 | 2,717 | +3.9% | +4.7% | +4.9% | +4.4% | -196.7% | -33.0% | -25.4% | -59.2% |
| 2026-02 | 2,615 | +2.9% | +3.7% | +3.8% | +3.8% | -205.0% | -39.7% | -24.9% | -66.8% |
| 2026-03 | 2,817 | +3.3% | +3.7% | +4.1% | +3.9% | -194.9% | -31.3% | -22.1% | -59.6% |
| 2026-04 | 663 | +1.4% | +1.6% | +2.3% | +2.4% | -184.4% | -43.6% | -25.6% | -76.0% |
| 2026-05 | 3,884 | +1.9% | +2.7% | +2.9% | +2.8% | -224.2% | -46.5% | -30.4% | -71.3% |
| 2026-06 | 3,896 | +2.4% | +3.3% | +3.6% | +3.7% | -245.9% | -40.2% | -27.3% | -63.7% |
| 2026-07 | 3,886 | -0.9% | +0.5% | +0.5% | +0.7% | -298.0% | -55.5% | -31.3% | -89.3% |
| 2026-08 | 4,259 | -1.2% | +0.9% | +0.8% | +1.2% | -341.2% | -59.4% | -33.9% | -95.1% |
| 2026-09 | 4,200 | +0.1% | +1.7% | +1.8% | +1.7% | -242.9% | -54.0% | -33.9% | -89.7% |
| 2026-10 | 3,205 | -0.0% | +0.9% | +1.1% | +1.3% | -216.6% | -46.6% | -30.9% | -75.0% |
| 2026-11 | 58 | -7.5% | -3.8% | -6.4% | -4.7% | -133.1% | -30.4% | -11.7% | -38.3% |

**h = 24**

| period | n | timestral-5m | timestral-28m | timestral-123m | timestral-209m | zero | moving_average | momentum | linear_trend |
|---|---|---|---|---|---|---|---|---|---|
| 2025-06 | 44 | +13.0% | +11.8% | +13.4% | +11.4% | +7.4% | +3.9% | -69.7% | -58.1% |
| 2025-07 | 280 | -0.5% | -0.1% | +0.8% | +2.3% | -84.3% | -12.9% | -55.5% | -25.3% |
| 2025-08 | 620 | +2.5% | +4.5% | +4.3% | +4.7% | -100.4% | -9.0% | -71.4% | -65.5% |
| 2025-09 | 592 | +7.5% | +7.9% | +8.5% | +8.2% | -54.8% | -11.7% | -72.6% | -48.1% |
| 2025-10 | 610 | +3.1% | +5.4% | +6.8% | +5.9% | -51.4% | -4.4% | -69.4% | -41.1% |
| 2025-11 | 1,018 | +2.0% | +2.7% | +3.5% | +3.3% | -80.3% | -14.2% | -59.9% | -54.4% |
| 2025-12 | 2,158 | +4.3% | +4.7% | +4.7% | +4.4% | -54.4% | -7.8% | -65.0% | -45.0% |
| 2026-01 | 2,711 | +5.6% | +6.0% | +6.1% | +5.5% | -67.3% | -13.0% | -57.8% | -51.8% |
| 2026-02 | 2,624 | +6.3% | +6.5% | +6.4% | +6.7% | -65.0% | -9.7% | -61.7% | -53.1% |
| 2026-03 | 2,748 | +3.8% | +4.3% | +4.2% | +3.6% | -74.3% | -12.8% | -60.7% | -55.8% |
| 2026-04 | 670 | +6.0% | +5.0% | +5.4% | +5.6% | -57.6% | -3.6% | -76.7% | -50.4% |
| 2026-05 | 3,879 | +4.8% | +5.3% | +5.3% | +5.2% | -59.8% | -10.2% | -52.0% | -42.6% |
| 2026-06 | 3,890 | +2.4% | +4.2% | +4.5% | +4.8% | -88.2% | -14.0% | -58.4% | -46.4% |
| 2026-07 | 3,864 | +1.6% | +3.0% | +2.8% | +2.8% | -92.9% | -14.4% | -56.5% | -55.6% |
| 2026-08 | 4,259 | +0.9% | +3.0% | +2.6% | +2.9% | -102.8% | -17.4% | -56.6% | -56.0% |
| 2026-09 | 4,200 | +3.1% | +4.6% | +4.4% | +4.0% | -67.3% | -11.4% | -60.2% | -54.8% |
| 2026-10 | 3,212 | +2.1% | +2.9% | +3.5% | +3.6% | -69.4% | -9.8% | -66.2% | -51.5% |
| 2026-11 | 58 | -17.3% | -13.0% | -15.0% | -12.7% | -95.8% | -8.4% | -54.2% | -30.6% |

## Resolution analysis (secondary, Polymarket)

Resolved markets with a YES/NO outcome: 12 ({'YES': 7, 'NO': 5}); scored: 11. Only origins whose cutoff is before both the scheduled close and the recorded resolution time count. The Brier columns treat a price as a probability of YES: `market price` is the price at the origin, `forecast price` is the model's median forecast of the price h hours later. A price forecast is not an event-probability model and origins of one market are strongly dependent, so with this few markets these numbers support **no calibration claim**; they are reported for completeness and kept apart from the price-forecast metrics above.

| h | model | n | markets | Brier market price | Brier forecast price |
|---|---|---|---|---|---|
| 1 | linear_trend | 1,734 | 11 | 0.2252 | 0.2258 |
| 1 | momentum | 1,734 | 11 | 0.2252 | 0.2253 |
| 1 | moving_average | 1,734 | 11 | 0.2252 | 0.2260 |
| 1 | persistence | 1,734 | 11 | 0.2252 | 0.2252 |
| 1 | timestral-123m | 1,734 | 11 | 0.2252 | 0.2252 |
| 1 | timestral-209m | 1,734 | 11 | 0.2252 | 0.2252 |
| 1 | timestral-28m | 1,734 | 11 | 0.2252 | 0.2252 |
| 1 | timestral-5m | 1,734 | 11 | 0.2252 | 0.2252 |
| 1 | zero | 1,734 | 11 | 0.2252 | 0.2226 |
| 6 | linear_trend | 1,733 | 11 | 0.2275 | 0.2287 |
| 6 | momentum | 1,733 | 11 | 0.2275 | 0.2283 |
| 6 | moving_average | 1,733 | 11 | 0.2275 | 0.2291 |
| 6 | persistence | 1,733 | 11 | 0.2275 | 0.2277 |
| 6 | timestral-123m | 1,733 | 11 | 0.2275 | 0.2273 |
| 6 | timestral-209m | 1,733 | 11 | 0.2275 | 0.2274 |
| 6 | timestral-28m | 1,733 | 11 | 0.2275 | 0.2274 |
| 6 | timestral-5m | 1,733 | 11 | 0.2275 | 0.2274 |
| 6 | zero | 1,733 | 11 | 0.2275 | 0.2248 |
| 24 | linear_trend | 1,704 | 11 | 0.2278 | 0.2317 |
| 24 | momentum | 1,704 | 11 | 0.2278 | 0.2322 |
| 24 | moving_average | 1,704 | 11 | 0.2278 | 0.2315 |
| 24 | persistence | 1,704 | 11 | 0.2278 | 0.2307 |
| 24 | timestral-123m | 1,704 | 11 | 0.2278 | 0.2271 |
| 24 | timestral-209m | 1,704 | 11 | 0.2278 | 0.2273 |
| 24 | timestral-28m | 1,704 | 11 | 0.2278 | 0.2273 |
| 24 | timestral-5m | 1,704 | 11 | 0.2278 | 0.2274 |
| 24 | zero | 1,704 | 11 | 0.2278 | 0.2240 |

## Model runs

| run | model | version | device | status | forecasts | failed | ms/forecast | wall s | peak RSS MB | peak VRAM MB | code |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 15 | timestral-5m | bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f | cuda:0 | completed | 38,623 | 0 | 20.13 | 816.9 | 1652 | 28.16 | 2f0caf39abfff31a8723c81320ef1bdc2d5e55a6 |
| 16 | timestral-28m | 49b26409ac87b5935539a5d8ffe7f397b720db47 | cuda:0 | completed | 38,623 | 0 | 27.08 | 1084 | 1712 | 115.2 | 2f0caf39abfff31a8723c81320ef1bdc2d5e55a6 |
| 17 | timestral-123m | 5a147287addda85f6acd8da3fb8858fe9af7e8f7 | cuda:0 | completed | 38,623 | 0 | 41.63 | 1647 | 1731 | 481.1 | 2f0caf39abfff31a8723c81320ef1bdc2d5e55a6 |
| 18 | timestral-209m | 9874d252ab0aae16f7f7c999f98f98d6ad7d8365 | cuda:0 | completed | 38,623 | 0 | 49.41 | 1949 | 2143 | 812.7 | 2f0caf39abfff31a8723c81320ef1bdc2d5e55a6 |
| 19 | zero | baselines-0.1 | cpu | completed | 38,623 | 0 | 3.508 | 161.4 | 1651 | 0.0000 | 2f0caf39abfff31a8723c81320ef1bdc2d5e55a6 |
| 20 | persistence | baselines-0.1 | cpu | completed | 38,623 | 0 | 3.636 | 165.4 | 1651 | 0.0000 | 2f0caf39abfff31a8723c81320ef1bdc2d5e55a6 |
| 21 | moving_average | baselines-0.1 | cpu | completed | 38,623 | 0 | 4.401 | 194.9 | 1651 | 0.0000 | 2f0caf39abfff31a8723c81320ef1bdc2d5e55a6 |
| 22 | momentum | baselines-0.1 | cpu | completed | 38,623 | 0 | 5.891 | 252.4 | 1651 | 0.0000 | 2f0caf39abfff31a8723c81320ef1bdc2d5e55a6 |
| 23 | linear_trend | baselines-0.1 | cpu | completed | 38,623 | 0 | 17.36 | 695.5 | 1652 | 0.0000 | 2f0caf39abfff31a8723c81320ef1bdc2d5e55a6 |

## Figures

- [calibration_h1.svg](calibration_h1.svg)
- [pit_h1.svg](pit_h1.svg)
- [over_time_h1.svg](over_time_h1.svg)
- [calibration_h6.svg](calibration_h6.svg)
- [pit_h6.svg](pit_h6.svg)
- [over_time_h6.svg](over_time_h6.svg)
- [calibration_h24.svg](calibration_h24.svg)
- [pit_h24.svg](pit_h24.svg)
- [over_time_h24.svg](over_time_h24.svg)

## Reading these results

- `better` / `worse` mean the 95% interval of the paired loss difference excludes zero. `no demonstrated difference` means it does not: the model has not shown an advantage (this is not proof of equality). `insufficient data` means the sample is too small to tell.
- Directional accuracy is not profitability, and no result here accounts for costs.
- See docs/M2_RESEARCH_METHODOLOGY.md and docs/KNOWN_LIMITATIONS.md.
