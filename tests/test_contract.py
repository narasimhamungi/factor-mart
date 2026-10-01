import pandas as pd
import pytest

from factor_mart.contract import ContractError, validate_prices


def _ok():
    return pd.DataFrame({"ticker": [" aapl", "AAPL"], "trade_date": ["2024-01-02", "2024-01-03"],
                         "adj_close": [10.0, 10.5]})


def test_clean_passes_and_normalises():
    out = validate_prices(_ok())
    assert list(out["ticker"]) == ["AAPL", "AAPL"]


def test_missing_column():
    with pytest.raises(ContractError, match="Missing required columns"):
        validate_prices(_ok().drop(columns=["adj_close"]))


def test_reports_all_violations_at_once():
    df = pd.DataFrame({"ticker": ["A", "A", "B"], "trade_date": ["2024-01-02", "2024-01-02", "2024-01-02"],
                       "adj_close": [1.0, 1.0, -3.0]})
    with pytest.raises(ContractError) as e:
        validate_prices(df)
    msg = str(e.value)
    assert "adj_close <= 0" in msg and "duplicate" in msg


def _dups(spread):
    return pd.DataFrame({"ticker": ["A", "A", "B"], "trade_date": ["2024-01-02"] * 3,
                         "adj_close": [100.0, 100.0 * (1 + spread), 50.0]})


def test_duplicates_within_tolerance_are_collapsed_and_counted():
    out = validate_prices(_dups(1e-7), dup_rel_tol=1e-5)
    assert len(out) == 2 and out.attrs["deduped_groups"] == 1


def test_duplicates_beyond_tolerance_still_abort():
    with pytest.raises(ContractError, match="exceeds tolerance"):
        validate_prices(_dups(0.01), dup_rel_tol=1e-5)


def test_duplicates_abort_by_default_even_if_identical():
    with pytest.raises(ContractError, match="duplicate"):
        validate_prices(_dups(0.0))
