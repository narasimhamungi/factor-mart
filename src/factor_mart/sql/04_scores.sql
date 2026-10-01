-- Cross-sectional z-score per (rebalance_date, factor), winsorised at +/-3,
-- then multiplied by factor direction so that a HIGHER score is always "better".
CREATE OR REPLACE TABLE {{schema}}.scores AS
WITH long_raw AS (
  SELECT s.ticker, d.rebalance_date, 'mom_12_1' AS factor, s.mom_12_1 AS raw_value
  FROM {{schema}}.signals s JOIN {{schema}}.rebalance_dates d ON d.rebalance_date = s.trade_date
  WHERE s.mom_12_1 IS NOT NULL
  UNION ALL
  SELECT s.ticker, d.rebalance_date, 'rev_21d', s.rev_21d
  FROM {{schema}}.signals s JOIN {{schema}}.rebalance_dates d ON d.rebalance_date = s.trade_date
  WHERE s.rev_21d IS NOT NULL
  UNION ALL
  SELECT s.ticker, d.rebalance_date, 'vol_63d', s.vol_63d
  FROM {{schema}}.signals s JOIN {{schema}}.rebalance_dates d ON d.rebalance_date = s.trade_date
  WHERE s.vol_63d IS NOT NULL
  UNION ALL
  SELECT s.ticker, d.rebalance_date, 'beta_252d', s.beta_252d
  FROM {{schema}}.signals s JOIN {{schema}}.rebalance_dates d ON d.rebalance_date = s.trade_date
  WHERE s.beta_252d IS NOT NULL
),
z AS (
  SELECT ticker, rebalance_date, factor, raw_value,
         COUNT(*) OVER (PARTITION BY rebalance_date, factor) AS n_names,
         (raw_value - AVG(raw_value) OVER (PARTITION BY rebalance_date, factor))
           / NULLIF(STDDEV_SAMP(raw_value) OVER (PARTITION BY rebalance_date, factor), 0) AS z_raw
  FROM long_raw
)
SELECT z.ticker, z.rebalance_date, z.factor, z.raw_value, z.n_names, g.direction,
       CASE WHEN z.z_raw > 3 THEN 3 WHEN z.z_raw < -3 THEN -3 ELSE z.z_raw END * g.direction AS score
FROM z JOIN {{schema}}.dim_factor g ON g.factor = z.factor
WHERE z.z_raw IS NOT NULL AND z.n_names >= {{min_universe}};
