-- Market proxy = equal-weight mean return of the universe (includes the stock itself).
-- Dates with fewer than {{min_universe}} valid returns are dropped.
CREATE OR REPLACE TABLE {{schema}}.market AS
SELECT trade_date, AVG(ret_1d) AS mkt_ret, COUNT(ret_1d) AS n_names
FROM {{schema}}.returns
WHERE ret_1d IS NOT NULL
GROUP BY trade_date
HAVING COUNT(ret_1d) >= {{min_universe}};

-- Rebalance date = last market date in each COMPLETE calendar month. The latest calendar month in
-- the data is excluded: it may be partial, and a return to a partial month-end would be a stub
-- period averaged and annualised as if it were a full month.
CREATE OR REPLACE TABLE {{schema}}.rebalance_dates AS
SELECT MAX(trade_date) AS rebalance_date,
       EXTRACT(year FROM MAX(trade_date)) * 12 + EXTRACT(month FROM MAX(trade_date)) AS month_idx
FROM {{schema}}.market
WHERE EXTRACT(year FROM trade_date) * 12 + EXTRACT(month FROM trade_date) <
      (SELECT MAX(EXTRACT(year FROM trade_date) * 12 + EXTRACT(month FROM trade_date)) FROM {{schema}}.market)
GROUP BY EXTRACT(year FROM trade_date), EXTRACT(month FROM trade_date);
