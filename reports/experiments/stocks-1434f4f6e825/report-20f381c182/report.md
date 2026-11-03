# Experiment `stocks-1434f4f6e825`: stocks strict 2012-2026 (historical cutoffs)

> **STRICT POINT-IN-TIME: only data the system had actually retrieved by each cutoff.**

Status: **completed**. Created 2026-11-03T12:08:31.676982Z at code version `749a6f6bf8dc0a7543459ab8231711820ce78ffb`. This is forecasting research. It is not a trading signal and says nothing about profitability.

## Configuration

| field | value |
|---|---|
| domain | stocks |
| knowledge mode | strict_point_in_time |
| source / interval | yfinance / 1d |
| calendar | XNYS |
| target | daily log return of `close` |
| price field | close |
| assets requested | 10 |
| origins | 2012-03-01 00:00 to 2026-09-29 00:00 UTC, every 20 sessions |
| cutoff | origin timestamp + 1800 s; extra replay latency 0 s |
| targets read as of | 2026-11-03 12:00 UTC |
| context | 512 points (min 480 valid, max 5% missing) |
| horizons | 1, 5, 20 trading sessions |
| quantile levels | 21 in [0.01, 0.99] |
| reference baseline | zero |
| seed / device requested | 0 / auto |
| availability rule | daily bar: timestamp is the session close (XNYS calendar; 00:00 Europe/London for FX); available_at = close + availability.stock_close_delay_minutes / fx_close_delay_minutes |
| model versions |  |

## Data and exclusions

- Assets prepared: 10; usable origins: 0; scored cases in the common sample: 0 per model.
- Origins excluded (origin_observation_missing): 1,840.

**No scored cases.** Nothing below can be interpreted.
