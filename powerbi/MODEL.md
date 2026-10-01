# Power BI model

Connect: Get data > Snowflake > server `<account>.snowflakecomputing.com`, warehouse `FACTOR_MART_WH`,
database `FACTOR_MART`, schema `CORE`. **Import mode** (month-end marts are small; DirectQuery would burn credits).

Load only these tables: `dim_factor`, `dim_month`, `mart_factor_returns`, `mart_ic`,
`mart_scores_monthly`, `mart_factor_summary`. Do not load `signals`, `scores`, `returns` (daily grain).

## Relationships (all many-to-one, single direction, from fact to dim)
| From | To |
|---|---|
| mart_factor_returns[factor] | dim_factor[factor] |
| mart_ic[factor] | dim_factor[factor] |
| mart_scores_monthly[factor] | dim_factor[factor] |
| mart_factor_returns[rebalance_date] | dim_month[month_end] |
| mart_ic[rebalance_date] | dim_month[month_end] |
| mart_scores_monthly[rebalance_date] | dim_month[month_end] |

`mart_factor_summary` stays disconnected (cross-check only; filter it with the Factor slicer via a
`TREATAS` measure or compare visually on a card).

## Report pages
1. **Overview** - slicer on `dim_factor[label]`; cards: Ann. LS Return, Ann. LS Vol, LS Sharpe, Hit Rate, Mean IC, ICIR; line: Cumulative LS by month_end.
2. **Quintiles** - clustered column of q1..q5 mean forward return (unpivot q1_ret..q5_ret in Power Query); IC by month bar chart.
3. **Reconciliation** - cards for `Ann. LS Return`, `SQL Summary Ann. LS`, `DAX vs SQL Diff`; diff must be ~0 with no date filter.

Apply `theme.json` (View > Themes > Browse for themes).

## Not verified
The .pbix has not been built from this repo. DAX is written but unrun; the reconciliation page exists
precisely so the first load proves or disproves it.
