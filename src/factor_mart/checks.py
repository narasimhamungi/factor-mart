"""Post-run invariants. Failures abort the CLI with a non-zero exit; warnings are reported only."""
from __future__ import annotations

import pandas as pd

from factor_mart.backends import Backend
from factor_mart.config import Params


def _scalar(backend: Backend, sql: str):
    return backend.query_df(sql).iloc[0, 0]


def run_checks(backend: Backend, params: Params) -> tuple[list[str], list[str]]:
    s = params.schema
    fails: list[str] = []
    warns: list[str] = []

    n = _scalar(backend, f"SELECT COUNT(*) FROM {s}.mart_scores_monthly")
    if n == 0:
        return ["mart_scores_monthly is empty - universe/min_universe/history likely insufficient"], warns

    dup = _scalar(backend, f"""SELECT COUNT(*) FROM (
        SELECT ticker, rebalance_date, factor FROM {s}.mart_scores_monthly
        GROUP BY ticker, rebalance_date, factor HAVING COUNT(*) > 1) t""")
    if dup:
        fails.append(f"{dup} duplicate (ticker, rebalance_date, factor) rows in mart_scores_monthly")

    n_dim = _scalar(backend, f"SELECT COUNT(*) FROM {s}.dim_factor")
    n_sum = _scalar(backend, f"SELECT COUNT(*) FROM {s}.mart_factor_summary")
    if n_sum != n_dim:
        fails.append(f"mart_factor_summary has {n_sum} factors, dim_factor has {n_dim}")

    oob = _scalar(backend, f"SELECT COUNT(*) FROM {s}.mart_scores_monthly "
                           "WHERE score > 3.000001 OR score < -3.000001")
    if oob:
        fails.append(f"{oob} scores outside the +/-3 winsor band")

    imbalance = _scalar(backend, f"""SELECT COUNT(*) FROM (
        SELECT rebalance_date, factor, MAX(c) - MIN(c) AS spread FROM (
          SELECT rebalance_date, factor, quintile, COUNT(*) AS c
          FROM {s}.mart_scores_monthly GROUP BY rebalance_date, factor, quintile) x
        GROUP BY rebalance_date, factor HAVING MAX(c) - MIN(c) > 1) y""")
    if imbalance:
        fails.append(f"{imbalance} factor-months with quintile sizes differing by more than 1")

    misordered = _scalar(backend, f"""SELECT COUNT(*) FROM (
        SELECT rebalance_date, factor,
               AVG(CASE WHEN quintile = 5 THEN score END) AS top,
               AVG(CASE WHEN quintile = 1 THEN score END) AS bot
        FROM {s}.mart_scores_monthly GROUP BY rebalance_date, factor) t
        WHERE top <= bot""")
    if misordered:
        fails.append(f"{misordered} factor-months where top-quintile mean score <= bottom-quintile")

    extreme = _scalar(backend, f"""SELECT COUNT(*) FROM (
        SELECT DISTINCT ticker, rebalance_date FROM {s}.mart_scores_monthly
        WHERE ABS(fwd_ret_1m) > 0.8) t""")
    if extreme:
        warns.append(f"{extreme} distinct ticker-months with forward return beyond +/-80% "
                     "- real crashes/squeezes or unadjusted splits; inspect before trusting results")

    rng = backend.query_df(f"SELECT MIN(trade_date) AS a, MAX(trade_date) AS b FROM {s}.raw_prices").iloc[0]
    cov = backend.query_df(f"SELECT MIN(rebalance_date) AS a, COUNT(DISTINCT rebalance_date) AS n "
                           f"FROM {s}.mart_scores_monthly").iloc[0]
    a, b = pd.Timestamp(rng.iloc[0]), pd.Timestamp(rng.iloc[1])
    span = (b.year - a.year) * 12 + (b.month - a.month) + 1
    if cov.iloc[1] < 0.75 * span:
        warns.append(f"only {int(cov.iloc[1])} of {span} calendar months in the raw price range are scored "
                     f"(first scored month {pd.Timestamp(cov.iloc[0]).date()}): most tickers have shorter "
                     "history than the headline range - state the effective window in the README")

    thin = _scalar(backend, f"SELECT COUNT(*) FROM {s}.mart_factor_summary WHERE n_months < 24")
    if thin:
        warns.append(f"{thin} factor(s) with fewer than 24 monthly observations - summary stats unreliable")

    return fails, warns
