# Experiment `polymarket-39b8a053a14d`: polymarket strict (historical cutoffs)

> **STRICT POINT-IN-TIME: only data the system had actually retrieved by each cutoff.**

Status: **completed**. Created 2026-11-03T12:08:41.430067Z at code version `749a6f6bf8dc0a7543459ab8231711820ce78ffb`. This is forecasting research. It is not a trading signal and says nothing about profitability.

## Configuration

| field | value |
|---|---|
| domain | polymarket |
| knowledge mode | strict_point_in_time |
| source / interval | polymarket_clob_history / 1h |
| calendar | UTC hours |
| target | logit of the YES token price (eps 0.0001); probabilities via inverse logit |
| price field | close |
| assets requested | 47 |
| origins | 2025-06-01 00:00 to 2026-11-01 10:00 UTC, every 24 hours |
| cutoff | origin timestamp + 300 s; extra replay latency 0 s |
| targets read as of | 2026-11-03 12:00 UTC |
| context | 336 points (min 168 valid, max 25% missing) |
| horizons | 1, 6, 24 hours |
| quantile levels | 21 in [0.01, 0.99] |
| reference baseline | persistence |
| seed / device requested | 0 / auto |
| availability rule | hourly price sample: filed under its hour, known at its own sample time source_ts; available_at = source_ts + availability.polymarket_history_latency_seconds |
| model versions |  |

## Data and exclusions

- Assets prepared: 47; usable origins: 0; scored cases in the common sample: 0 per model.
- Grid origins skipped (after_market_close): 17.
- Grid origins skipped (outside_data_span): 13,350.
- Origins excluded (origin_observation_missing): 11,026.

**No scored cases.** Nothing below can be interpreted.
