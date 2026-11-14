# Polymarket data export

Snapshot of the Polymarket data collected by the `mpe-ingest-polymarket` timer
into `data/mpe.sqlite3`, taken 2026-11-14 ~22:50 UTC (collection started 2026-11-03).

One CSV (with header) per table, zstd-compressed, split into <50 MB parts.
Reassemble and decompress:

    cat observations.csv.zst.part* | zstd -d > observations.csv

| file | source |
|---|---|
| markets | `markets` (all rows, provider = polymarket) |
| assets | `assets` where provider = polymarket (pm_token, YES/NO sides) |
| resolutions | `resolutions` |
| observations | `observations` joined to polymarket assets (1h bars + snapshots) |
| order_book_snapshots | `order_book_snapshots` (bids_json / asks_json) |

Columns match the SQLite schema (`src/mpe/db`). yfinance rows are not included.
