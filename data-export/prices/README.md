# Price bars (yfinance 1.7.0, pulled 2026-11-14 ~23:05 UTC)

`{ticker}_{1h|1d}.csv.gz` (^VIX -> VIX). Index column `timestamp_utc` (UTC, bar open time),
then Open, High, Low, Close, Adj Close, Volume, Dividends, Stock Splits (auto_adjust=False).
1h = period 730d (stocks: regular session only; VIX includes extended hours; crypto 24/7).
1d = period max. Daily stock bars are stamped at New York midnight converted to UTC (04:00/05:00Z);
crypto daily bars at 00:00Z.

Already in data/mpe.sqlite3 (not re-exported): yfinance daily bars 2010-01-04 -> 2026-11-13 for
SPY, QQQ, IWM, GLD, TLT, NVDA, MSFT, AAPL, AMZN, ^VIX, GBPUSD=X.
