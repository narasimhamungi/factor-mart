-- One-month forward return from each rebalance date to the NEXT rebalance date.
-- NULL if the ticker has no price on the next consecutive month's rebalance date
-- (delisting / data gap) - never bridged across a missing month.
CREATE OR REPLACE TABLE {{schema}}.fwd_returns AS
WITH px AS (
  SELECT r.ticker, d.rebalance_date, d.month_idx, r.adj_close
  FROM {{schema}}.returns r JOIN {{schema}}.rebalance_dates d ON d.rebalance_date = r.trade_date
),
nx AS (
  SELECT ticker, rebalance_date, month_idx, adj_close,
         LEAD(adj_close) OVER (PARTITION BY ticker ORDER BY rebalance_date) AS next_close,
         LEAD(month_idx) OVER (PARTITION BY ticker ORDER BY rebalance_date) AS next_month_idx
  FROM px
)
SELECT ticker, rebalance_date,
       CASE WHEN next_month_idx = month_idx + 1 THEN next_close / adj_close - 1 END AS fwd_ret_1m
FROM nx;
