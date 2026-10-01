import numpy as np
import pandas as pd
import pytest

from factor_mart.backends import DuckDBBackend
from factor_mart.config import Params


def make_prices(betas, n_days=900, noise=0.0, seed=7, start="2021-01-04"):
    """ret_i,t = beta_i * f_t + noise. With noise=0 the equal-weight market return is
    mean(beta) * f_t, so true beta_i vs that proxy is exactly beta_i / mean(beta)."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=n_days)
    f = rng.normal(0.0004, 0.01, n_days)
    rows = []
    for i, b in enumerate(betas):
        eps = rng.normal(0, noise, n_days) if noise else 0.0
        r = b * f + eps
        r[0] = 0.0
        px = 100 * np.cumprod(1 + r)
        rows.append(pd.DataFrame({"ticker": f"T{i:02d}", "trade_date": dates, "adj_close": px}))
    return pd.concat(rows, ignore_index=True)


@pytest.fixture
def params():
    return Params(schema="core", min_universe=5, max_gap_days=5)


@pytest.fixture
def backend():
    return DuckDBBackend(":memory:")
