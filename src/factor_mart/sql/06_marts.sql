-- Power BI-facing marts: month-end grain only (daily tables stay in Snowflake).
-- rebalance_date = formation date; fwd_ret_1m / ls_ret are earned over the FOLLOWING month.
CREATE OR REPLACE TABLE {{schema}}.mart_scores_monthly AS
WITH q AS (
  SELECT ticker, rebalance_date, factor, raw_value, score,
         NTILE(5) OVER (PARTITION BY rebalance_date, factor ORDER BY score, ticker) AS quintile
  FROM {{schema}}.scores
)
SELECT q.ticker, q.rebalance_date, q.factor, q.raw_value, q.score, q.quintile, f.fwd_ret_1m
FROM q LEFT JOIN {{schema}}.fwd_returns f
  ON f.ticker = q.ticker AND f.rebalance_date = q.rebalance_date;

CREATE OR REPLACE TABLE {{schema}}.mart_factor_returns AS
SELECT rebalance_date, factor,
       AVG(CASE WHEN quintile = 1 THEN fwd_ret_1m END) AS q1_ret,
       AVG(CASE WHEN quintile = 2 THEN fwd_ret_1m END) AS q2_ret,
       AVG(CASE WHEN quintile = 3 THEN fwd_ret_1m END) AS q3_ret,
       AVG(CASE WHEN quintile = 4 THEN fwd_ret_1m END) AS q4_ret,
       AVG(CASE WHEN quintile = 5 THEN fwd_ret_1m END) AS q5_ret,
       AVG(CASE WHEN quintile = 5 THEN fwd_ret_1m END)
         - AVG(CASE WHEN quintile = 1 THEN fwd_ret_1m END) AS ls_ret,
       COUNT(fwd_ret_1m) AS n_names
FROM {{schema}}.mart_scores_monthly
WHERE fwd_ret_1m IS NOT NULL
GROUP BY rebalance_date, factor;

-- Information coefficient = rank correlation of score vs forward return (RANK, ties share min rank).
CREATE OR REPLACE TABLE {{schema}}.mart_ic AS
WITH r AS (
  SELECT rebalance_date, factor,
         RANK() OVER (PARTITION BY rebalance_date, factor ORDER BY score) AS rk_score,
         RANK() OVER (PARTITION BY rebalance_date, factor ORDER BY fwd_ret_1m) AS rk_fwd
  FROM {{schema}}.mart_scores_monthly
  WHERE fwd_ret_1m IS NOT NULL
)
SELECT rebalance_date, factor, CORR(rk_score, rk_fwd) AS ic, COUNT(*) AS n_names
FROM r
GROUP BY rebalance_date, factor;

-- Cross-check table: Power BI DAX measures should reproduce these numbers.
-- hit_rate is cast to DOUBLE on purpose: Snowflake AVG over fixed-point literals (1.0 / 0.0) rounds to 6 decimals.
-- Annualisation = arithmetic mean x 12 and stdev x sqrt(12) (simplification, stated in README).
CREATE OR REPLACE TABLE {{schema}}.mart_factor_summary AS
WITH f AS (
  SELECT factor, COUNT(*) AS n_months, AVG(ls_ret) AS mean_ls, STDDEV_SAMP(ls_ret) AS sd_ls,
         AVG(CAST(CASE WHEN ls_ret > 0 THEN 1 ELSE 0 END AS DOUBLE)) AS hit_rate
  FROM {{schema}}.mart_factor_returns GROUP BY factor
),
i AS (
  SELECT factor, AVG(ic) AS mean_ic, STDDEV_SAMP(ic) AS sd_ic
  FROM {{schema}}.mart_ic GROUP BY factor
)
SELECT f.factor, f.n_months,
       f.mean_ls * 12 AS ann_ls_return,
       f.sd_ls * SQRT(12) AS ann_ls_vol,
       (f.mean_ls * 12) / NULLIF(f.sd_ls * SQRT(12), 0) AS ls_sharpe,
       f.hit_rate, i.mean_ic, i.mean_ic / NULLIF(i.sd_ic, 0) AS icir
FROM f JOIN i ON i.factor = f.factor;

CREATE OR REPLACE TABLE {{schema}}.dim_month AS
SELECT DISTINCT rebalance_date AS month_end,
       EXTRACT(year FROM rebalance_date) AS yr,
       EXTRACT(month FROM rebalance_date) AS mth
FROM {{schema}}.mart_scores_monthly;
