-- Daily simple returns from adjusted close. Return is NULL (not bridged) when the
-- gap to the previous observation exceeds {{max_gap_days}} calendar days.
CREATE OR REPLACE TABLE {{schema}}.returns AS
WITH base AS (
  SELECT ticker, trade_date, adj_close,
         LAG(adj_close) OVER (PARTITION BY ticker ORDER BY trade_date) AS prev_close,
         LAG(trade_date) OVER (PARTITION BY ticker ORDER BY trade_date) AS prev_date
  FROM {{schema}}.raw_prices
  WHERE adj_close > 0
)
SELECT ticker, trade_date, adj_close,
       CASE WHEN prev_close IS NOT NULL
             AND DATEDIFF('day', prev_date, trade_date) <= {{max_gap_days}}
            THEN adj_close / prev_close - 1
       END AS ret_1d
FROM base;
