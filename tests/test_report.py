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


def test_results_block_is_data_driven_and_readme_update_preserves_surroundings(tmp_path):
    from factor_mart.report import RESULTS_END, RESULTS_START, results_block

    summary = pd.DataFrame({
        "factor": ["mom_12_1", "vol_63d", "rev_21d"], "n_months": [80, 89, 91],
        "ann_ls_return": [0.04, -0.21, 0.01], "ann_ls_vol": [0.17, 0.22, 0.15], "ls_sharpe": [0.2547, -0.9474, 0.07],
        "hit_rate": [0.53, 0.37, 0.50], "mean_ic": [0.01, -0.04, 0.03], "icir": [0.07, -0.14, 0.25]})
    labels = {"mom_12_1": "Momentum", "vol_63d": "Low vol", "rev_21d": "Reversal"}
    blk = results_block(summary, labels, ["mom_12_1", "rev_21d", "vol_63d"], "2019-02-28", "2026-07-31")
    assert "Quintile spread distinguishable from zero at naive |t| >= 2: Low vol (t = -2.58" in blk
    assert "IC (but not the spread) distinguishable" in blk and "Reversal (t = 2.38)" in blk   # 0.25*sqrt(91)
    assert "Indistinguishable from zero on both" in blk and "Momentum" in blk.split("Indistinguishable")[1]
    assert blk.startswith(RESULTS_START) and blk.endswith(RESULTS_END)

    readme = tmp_path / "README.md"
    readme.write_text(f"intro\n{RESULTS_START}\nOLD\n{RESULTS_END}\noutro\n", encoding="utf-8")
    generate(_built(), tmp_path / "r", readme=readme)
    new = readme.read_text(encoding="utf-8")
    assert new.startswith("intro\n") and new.endswith("\noutro\n") and "OLD" not in new
    assert new.count("| Momentum") == 1 and new.count(RESULTS_START) == 1
