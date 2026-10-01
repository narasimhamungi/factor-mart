import numpy as np
import pandas as pd

from conftest import make_prices
from factor_mart.checks import run_checks
from factor_mart.contract import validate_prices
from factor_mart.runner import run_models, split_statements, render


def build(backend, params, prices, only=None):
    backend.load_prices(validate_prices(prices), params.schema)
    return run_models(backend, params, only)


def test_templates_fully_resolved(params):
    from factor_mart.runner import model_files
    for _, text in model_files():
        assert "{{" not in render(text, params)
        assert all(s for s in split_statements(render(text, params)))


def test_returns_null_across_gap(backend, params):
    px = make_prices([1.0] * 6, n_days=40)
    drop = px[(px.ticker == "T00")].iloc[10:20].index  # remove 10 consecutive bdays for one ticker
    px = px.drop(drop)
    build(backend, params, px, only=["00", "01"])
    r = backend.query_df("SELECT ticker, trade_date, ret_1d FROM core.returns "
                         "WHERE ticker='T00' ORDER BY trade_date")
    first_after_gap = r.iloc[10]
    assert pd.isna(first_after_gap.ret_1d)          # not bridged
    assert r.iloc[11].ret_1d is not None and not pd.isna(r.iloc[11].ret_1d)


def test_beta_exact_on_noise_free_factor_data(backend, params):
    betas = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4]
    build(backend, params, make_prices(betas, n_days=600), only=["00", "01", "02", "03"])
    last = backend.query_df("SELECT ticker, beta_252d FROM core.signals "
                            "WHERE trade_date = (SELECT MAX(trade_date) FROM core.signals) ORDER BY ticker")
    expected = np.array(betas) / np.mean(betas)
    np.testing.assert_allclose(last.beta_252d.to_numpy(), expected, atol=1e-6)


def test_vol_zero_for_constant_return_and_gated_early(backend, params):
    dates = pd.bdate_range("2022-01-03", periods=120)
    frames = [pd.DataFrame({"ticker": f"C{i}", "trade_date": dates,
                            "adj_close": 100 * (1.001 ** np.arange(120)) * (1 + 0.0 * i)}) for i in range(6)]
    build(backend, params, pd.concat(frames, ignore_index=True), only=["00", "01", "02", "03"])
    s = backend.query_df("SELECT trade_date, vol_63d FROM core.signals WHERE ticker='C0' ORDER BY trade_date")
    assert s.vol_63d.iloc[:62].isna().all()          # needs 63 valid returns => first valid at row index 63
    assert s.vol_63d.dropna().abs().max() < 1e-5


def test_momentum_matches_python_reference(backend, params):
    px = make_prices([0.8, 0.9, 1.0, 1.1, 1.2, 1.3], n_days=400, noise=0.004)
    build(backend, params, px, only=["00", "01", "02", "03"])
    sig = backend.query_df("SELECT ticker, trade_date, mom_12_1, rev_21d FROM core.signals "
                           "WHERE ticker='T03' ORDER BY trade_date").reset_index(drop=True)
    p = px[px.ticker == "T03"].sort_values("trade_date").reset_index(drop=True)
    ref_mom = p.adj_close.shift(21) / p.adj_close.shift(252) - 1
    ref_rev = p.adj_close / p.adj_close.shift(21) - 1
    np.testing.assert_allclose(sig.mom_12_1.to_numpy(float), ref_mom.to_numpy(float), atol=1e-10, equal_nan=True)
    np.testing.assert_allclose(sig.rev_21d.to_numpy(float), ref_rev.to_numpy(float), atol=1e-10, equal_nan=True)


def test_full_pipeline_checks_pass(backend, params):
    betas = np.linspace(0.4, 1.6, 20)
    ran = build(backend, params, make_prices(betas, n_days=900, noise=0.006))
    assert ran[0] == "00_dims.sql" and ran[-1] == "06_marts.sql"
    fails, _warns = run_checks(backend, params)
    assert fails == []
    summ = backend.query_df("SELECT factor FROM core.mart_factor_summary ORDER BY factor")
    assert list(summ.factor) == ["beta_252d", "mom_12_1", "rev_21d", "vol_63d"]


def test_low_beta_direction_puts_low_beta_names_in_top_quintile(backend, params):
    # Noisy data => estimated betas of neighbours can swap, so assert the sign convention,
    # not exact membership (exact beta arithmetic is covered by the noise-free test).
    betas = np.linspace(0.4, 1.6, 20)
    build(backend, params, make_prices(betas, n_days=700, noise=0.006))
    q = backend.query_df("""SELECT ticker, quintile FROM core.mart_scores_monthly
        WHERE factor='beta_252d'
          AND rebalance_date = (SELECT MAX(rebalance_date) FROM core.mart_scores_monthly WHERE factor='beta_252d')""")
    true_beta = {f"T{i:02d}": b for i, b in enumerate(betas)}
    q["true_beta"] = q.ticker.map(true_beta)
    top, bot = q[q.quintile == 5], q[q.quintile == 1]
    assert top.true_beta.max() < np.median(betas)          # top quintile drawn from the low-beta half
    assert top.true_beta.mean() < bot.true_beta.mean()


def _seed_marts_inputs(backend, sign):
    backend.execute("CREATE SCHEMA IF NOT EXISTS core")
    rows = []
    for m, d in enumerate(pd.date_range("2022-01-31", periods=8, freq="ME")):
        for k in range(20):
            score = (k - 9.5) / 5
            rows.append(("X%02d" % k, d.date(), "mom_12_1", score, score, 1, 20, sign * score * 0.01))
    df = pd.DataFrame(rows, columns=["ticker", "rebalance_date", "factor", "raw_value", "score",
                                     "direction", "n_names", "fwd"])
    backend.con.register("_s", df)
    backend.execute("CREATE TABLE core.scores AS SELECT ticker, CAST(rebalance_date AS DATE) AS rebalance_date, "
                    "factor, raw_value, n_names, direction, score FROM _s")
    backend.execute("CREATE TABLE core.fwd_returns AS SELECT ticker, CAST(rebalance_date AS DATE) AS rebalance_date, "
                    "fwd AS fwd_ret_1m FROM _s")


def test_marts_perfect_positive_relationship(backend, params):
    _seed_marts_inputs(backend, +1)
    run_models(backend, params, only=["06"])
    fr = backend.query_df("SELECT * FROM core.mart_factor_returns ORDER BY rebalance_date")
    assert (fr.ls_ret > 0).all()
    assert ((fr.q1_ret < fr.q2_ret) & (fr.q2_ret < fr.q3_ret) & (fr.q3_ret < fr.q4_ret) & (fr.q4_ret < fr.q5_ret)).all()
    ic = backend.query_df("SELECT ic FROM core.mart_ic")
    np.testing.assert_allclose(ic.ic.to_numpy(float), 1.0, atol=1e-12)


def test_marts_perfect_negative_relationship(backend, params):
    _seed_marts_inputs(backend, -1)
    run_models(backend, params, only=["06"])
    assert (backend.query_df("SELECT ls_ret FROM core.mart_factor_returns").ls_ret < 0).all()
    np.testing.assert_allclose(backend.query_df("SELECT ic FROM core.mart_ic").ic.to_numpy(float), -1.0, atol=1e-12)


def test_checks_catch_injected_duplicate(backend, params):
    betas = np.linspace(0.4, 1.6, 20)
    build(backend, params, make_prices(betas, n_days=700, noise=0.006))
    backend.execute("INSERT INTO core.mart_scores_monthly SELECT * FROM core.mart_scores_monthly LIMIT 1")
    fails, _ = run_checks(backend, params)
    assert any("duplicate" in f for f in fails)


def test_splitter_respects_semicolons_in_string_literals():
    stmts = split_statements("SELECT 'a;b' AS x;\n-- comment; ignored\nSELECT 'it''s; ok' AS y;")
    assert stmts == ["SELECT 'a;b' AS x", "SELECT 'it''s; ok' AS y"]


def test_checks_warn_when_most_months_unscored(backend, params):
    # 6 tickers (>= min_universe) only from month ~19 of a 36-month raw range => thin coverage
    import pandas as pd
    px = make_prices([1.0] * 6, n_days=300, noise=0.01)
    early = make_prices([1.0], n_days=900, noise=0.01, seed=3)
    early["ticker"] = "EARLY"
    build(backend, params, pd.concat([px, early], ignore_index=True))
    _fails, warns = run_checks(backend, params)
    assert any("calendar months" in w for w in warns)
