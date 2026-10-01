-- Rolling signals per ticker. All rolling stats use plain SUM/COUNT window sums
-- (no STDDEV/COVAR window functions) so the file runs unchanged on DuckDB and Snowflake.
-- A signal is NULL unless its window is complete and calendar spans are sane.
CREATE OR REPLACE TABLE {{schema}}.signals AS
WITH j AS (
  SELECT r.ticker, r.trade_date, r.adj_close, r.ret_1d,
         CASE WHEN m.mkt_ret IS NOT NULL THEN r.ret_1d END AS ret_b,
         CASE WHEN r.ret_1d IS NOT NULL THEN m.mkt_ret END AS mkt_b
  FROM {{schema}}.returns r
  LEFT JOIN {{schema}}.market m ON m.trade_date = r.trade_date
),
w AS (
  SELECT ticker, trade_date, adj_close,
    LAG(adj_close, 21)  OVER (PARTITION BY ticker ORDER BY trade_date) AS px_21,
    LAG(trade_date, 21) OVER (PARTITION BY ticker ORDER BY trade_date) AS dt_21,
    LAG(adj_close, 252)  OVER (PARTITION BY ticker ORDER BY trade_date) AS px_252,
    LAG(trade_date, 252) OVER (PARTITION BY ticker ORDER BY trade_date) AS dt_252,
    COUNT(ret_1d) OVER (PARTITION BY ticker ORDER BY trade_date ROWS BETWEEN 62 PRECEDING AND CURRENT ROW) AS v_n,
    SUM(ret_1d) OVER (PARTITION BY ticker ORDER BY trade_date ROWS BETWEEN 62 PRECEDING AND CURRENT ROW) AS v_s,
    SUM(ret_1d * ret_1d) OVER (PARTITION BY ticker ORDER BY trade_date ROWS BETWEEN 62 PRECEDING AND CURRENT ROW) AS v_ss,
    COUNT(ret_b) OVER (PARTITION BY ticker ORDER BY trade_date ROWS BETWEEN 251 PRECEDING AND CURRENT ROW) AS b_n,
    SUM(ret_b) OVER (PARTITION BY ticker ORDER BY trade_date ROWS BETWEEN 251 PRECEDING AND CURRENT ROW) AS b_sr,
    SUM(mkt_b) OVER (PARTITION BY ticker ORDER BY trade_date ROWS BETWEEN 251 PRECEDING AND CURRENT ROW) AS b_sm,
    SUM(ret_b * mkt_b) OVER (PARTITION BY ticker ORDER BY trade_date ROWS BETWEEN 251 PRECEDING AND CURRENT ROW) AS b_srm,
    SUM(mkt_b * mkt_b) OVER (PARTITION BY ticker ORDER BY trade_date ROWS BETWEEN 251 PRECEDING AND CURRENT ROW) AS b_smm
  FROM j
)
SELECT ticker, trade_date,
  CASE WHEN px_21 IS NOT NULL AND px_252 IS NOT NULL
        AND DATEDIFF('day', dt_21, trade_date) BETWEEN 26 AND 40
        AND DATEDIFF('day', dt_252, trade_date) BETWEEN 340 AND 400
       THEN px_21 / px_252 - 1
  END AS mom_12_1,
  CASE WHEN px_21 IS NOT NULL
        AND DATEDIFF('day', dt_21, trade_date) BETWEEN 26 AND 40
       THEN adj_close / px_21 - 1
  END AS rev_21d,
  CASE WHEN v_n = 63
       THEN SQRT(GREATEST((v_ss - v_s * v_s / v_n) / (v_n - 1), 0)) * SQRT(252)
  END AS vol_63d,
  CASE WHEN b_n = 252
       THEN ((b_srm / b_n) - (b_sr / b_n) * (b_sm / b_n))
            / NULLIF((b_smm / b_n) - (b_sm / b_n) * (b_sm / b_n), 0)
  END AS beta_252d
FROM w;
