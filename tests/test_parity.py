import numpy as np

from conftest import make_prices
from factor_mart.backends import DuckDBBackend
from factor_mart.config import Params
from factor_mart.contract import validate_prices
from factor_mart.parity import compare
from factor_mart.runner import run_models


def _built():
    params = Params(schema="core", min_universe=5, max_gap_days=5)
    b = DuckDBBackend(":memory:")
    b.load_prices(validate_prices(make_prices(np.linspace(0.4, 1.6, 20), n_days=700, noise=0.006)), "core")
    run_models(b, params)
    return b


def test_identical_runs_have_parity():
    ok, lines = compare(_built(), _built())
    assert ok, "\n".join(lines)


def test_row_count_difference_is_caught():
    a, b = _built(), _built()
    b.execute("DELETE FROM core.mart_ic WHERE rebalance_date = (SELECT MIN(rebalance_date) FROM core.mart_ic)")
    ok, lines = compare(a, b)
    assert not ok and any("MISMATCH" in l for l in lines)


def test_quintile_and_score_differences_are_caught():
    a, b = _built(), _built()
    b.execute("UPDATE core.mart_scores_monthly SET quintile = 6 - quintile "
              "WHERE ticker = (SELECT MIN(ticker) FROM core.mart_scores_monthly)")
    ok, lines = compare(a, b)
    assert not ok and any("quintile disagreements" in l and not l.strip().endswith(": 0 of") for l in lines)

    a, b = _built(), _built()
    b.execute("UPDATE core.mart_scores_monthly SET score = score + 0.001 WHERE factor = 'mom_12_1'")
    ok, _ = compare(a, b)
    assert not ok
