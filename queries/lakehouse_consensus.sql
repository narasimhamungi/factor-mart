-- Input query for marketdata-lakehouse (Postgres). Cross-source consensus adj_close, one row per
-- (security_key, date_key). ticker comes from dim_security, the date from dim_date.
-- dim_security is slowly-changing, so a ticker can map to several security_keys and yield
-- several rows per (ticker, date). Run with --dup-tol 1e-5: duplicates are collapsed only if
-- their relative price spread is within tolerance, otherwise the run aborts.
SELECT s.ticker, d.date AS trade_date, c.adj_close
FROM fact_price_daily_consensus c
JOIN dim_security s ON s.security_key = c.security_key
JOIN dim_date d ON d.date_key = c.date_key
WHERE d.is_trading_day
