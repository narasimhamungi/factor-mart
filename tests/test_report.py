import datetime as dt

import numpy as np
import pandas as pd

from conftest import make_prices
from factor_mart.backends import DuckDBBackend
from factor_mart.config import Params
from factor_mart.contract import validate_prices
from factor_mart.report import generate
from factor_mart.runner import run_models


def _built():
    b = DuckDBBackend(":memory:")
    b.load_prices(validate_prices(make_prices(np.linspace(0.4, 1.6, 20), n_days=900, noise=0.006)), "core")
    run_models(b, Params(schema="core", min_universe=5, max_gap_days=5))
    return b


def test_report_writes_csvs_charts_and_manifest(tmp_path):
    b = _built()
    paths = generate(b, tmp_path / "results", now=dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc))
    names = {p.name for p in paths}
    assert names == {"mart_factor_summary.csv", "mart_factor_returns.csv", "mart_ic.csv", "dim_factor.csv",
                     "cumulative_ls_spread.png", "ic_by_month.png", "MANIFEST.txt"}
    for p in paths:
        assert p.stat().st_size > 0
        if p.suffix == ".png":
            assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" and p.stat().st_size > 10_000

    n_db = int(b.query_df("SELECT COUNT(*) FROM core.mart_factor_returns").iloc[0, 0])
    assert len(pd.read_csv(tmp_path / "results" / "mart_factor_returns.csv")) == n_db
    summ = pd.read_csv(tmp_path / "results" / "mart_factor_summary.csv")
    assert set(summ["factor"]) == {"mom_12_1", "rev_21d", "vol_63d", "beta_252d"}

    manifest = (tmp_path / "results" / "MANIFEST.txt").read_text()
    assert "generated: 2026-10-01 00:00 UTC" in manifest and "engine: duckdb" in manifest
