-- Single source of truth for factor definitions and sign convention.
-- direction = +1: higher raw value => higher score. -1: lower raw value => higher score.
CREATE SCHEMA IF NOT EXISTS {{schema}};

CREATE OR REPLACE TABLE {{schema}}.dim_factor AS
SELECT 'mom_12_1' AS factor, 'Momentum (12-1)' AS label, 1 AS direction,
       'Price(t-21d) / Price(t-252d) - 1; skips most recent month' AS definition
UNION ALL
SELECT 'rev_21d', 'Short-term reversal (1M)', -1,
       'Price(t) / Price(t-21d) - 1; losers score high'
UNION ALL
SELECT 'vol_63d', 'Low volatility (63d)', -1,
       'Annualised stdev of daily returns over 63 obs; low vol scores high'
UNION ALL
SELECT 'beta_252d', 'Low beta (252d)', -1,
       'Beta vs equal-weight universe return over 252 obs; low beta scores high';
