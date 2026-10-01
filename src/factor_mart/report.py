"""Export the marts to CSV and draw the two README charts.

    python -m factor_mart.report [--backend duckdb|snowflake] [--duckdb-path factor_mart.duckdb] [--out results]

Writes into --out: the four small mart tables as CSV, cumulative_ls_spread.png, ic_by_month.png and
MANIFEST.txt (engine, row counts, window, generation time). The CSVs make the numbers in the README
reproducible without a live warehouse.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from factor_mart.backends import Backend

CSV_TABLES = {
    "mart_factor_summary": ["factor"],
    "mart_factor_returns": ["factor", "rebalance_date"],
    "mart_ic": ["factor", "rebalance_date"],
    "dim_factor": ["factor"],
}
PALETTE = ["#1F3A5F", "#C8553D", "#4F772D", "#8D6A9F", "#D9A441"]
TEXT_COLS = {"factor", "label", "definition"}
CANONICAL = ["mom_12_1", "rev_21d", "vol_63d", "beta_252d"]


def _ordered(factors: list[str]) -> list[str]:
    return [f for f in CANONICAL if f in factors] + sorted(f for f in factors if f not in CANONICAL)


def _read(backend: Backend, schema: str, table: str, sort: list[str]) -> pd.DataFrame:
    df = backend.query_df(f"SELECT * FROM {schema}.{table}")
    for c in df.columns:
        if c == "rebalance_date":
            df[c] = pd.to_datetime(df[c]).dt.date
        elif c not in TEXT_COLS:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values(sort).reset_index(drop=True)


def _footer(first, last) -> str:
    return (f"Formation dates {first} to {last}. Equal-weight quintiles, gross of costs, no neutralisation.\n"
            "Universe taken from the lakehouse (survivorship-biased). Not evidence of factor premia.")


def _cumulative_chart(returns: pd.DataFrame, order: list[str], labels: dict, path: Path, footer: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 5.4), dpi=150)
    for f, color in zip(order, PALETTE):
        g = returns[returns["factor"] == f].sort_values("rebalance_date")
        if g.empty:
            continue
        cum = ((1 + g["ls_ret"]).cumprod() - 1) * 100
        ax.plot(pd.to_datetime(g["rebalance_date"]), cum, label=labels.get(f, f), color=color, lw=1.8)
    ax.axhline(0, color="#444444", lw=0.8)
    ax.set_ylabel("Cumulative top-minus-bottom spread, % (compounded monthly)")
    ax.set_title("Quintile spread by factor: a spread, not a tradable portfolio return", fontsize=11, loc="left")
    ax.legend(frameon=False, loc="best")
    ax.grid(alpha=0.2)
    fig.text(0.01, 0.012, footer, fontsize=7.5, color="#555555", ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(path)
    plt.close(fig)


def _ic_chart(ic: pd.DataFrame, order: list[str], labels: dict, path: Path, footer: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(10, 6.2), dpi=150, sharex=True)
    for ax, f, color in zip(axes.ravel(), order, PALETTE):
        g = ic[ic["factor"] == f].sort_values("rebalance_date")
        x = pd.to_datetime(g["rebalance_date"])
        ax.bar(x, g["ic"], width=20, color=color, alpha=0.35)
        ax.plot(x, g["ic"].rolling(12, min_periods=12).mean(), color=color, lw=1.8)
        ax.axhline(0, color="#444444", lw=0.8)
        n, mean, sd = len(g), float(g["ic"].mean()), float(g["ic"].std(ddof=1))
        t = mean / sd * np.sqrt(n) if sd else float("nan")
        ax.set_title(f"{labels.get(f, f)}   mean IC {mean:+.3f}, naive t {t:+.2f}", fontsize=9, loc="left")
        ax.grid(alpha=0.2)
    fig.suptitle("Monthly rank IC (bars) and trailing 12-month mean (line)", fontsize=11, x=0.01, ha="left")
    fig.text(0.01, 0.012, footer, fontsize=7.5, color="#555555", ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.06, 1, 0.96))
    fig.savefig(path)
    plt.close(fig)


def generate(backend: Backend, out_dir: Path | str, schema: str = "core",
             now: dt.datetime | None = None) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    frames = {t: _read(backend, schema, t, s) for t, s in CSV_TABLES.items()}
    for t, df in frames.items():
        p = out / f"{t}.csv"
        df.to_csv(p, index=False, float_format="%.10g", lineterminator="\n")
        written.append(p)

    dim = frames["dim_factor"]
    order = _ordered(list(dim["factor"]))
    labels = dict(zip(dim["factor"], dim["label"]))
    returns, ic = frames["mart_factor_returns"], frames["mart_ic"]
    first, last = returns["rebalance_date"].min(), returns["rebalance_date"].max()
    footer = _footer(first, last)

    p = out / "cumulative_ls_spread.png"
    _cumulative_chart(returns, order, labels, p, footer)
    written.append(p)
    p = out / "ic_by_month.png"
    _ic_chart(ic, order, labels, p, footer)
    written.append(p)

    raw = backend.query_df(f"SELECT COUNT(*) AS n, COUNT(DISTINCT ticker) AS t, MIN(trade_date) AS a, "
                           f"MAX(trade_date) AS b FROM {schema}.raw_prices").iloc[0]
    stamp = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"generated: {stamp}",
        f"engine: {backend.name}",
        f"raw_prices: {int(raw['n']):,} rows, {int(raw['t']):,} tickers, {raw['a']} to {raw['b']}",
        f"scored window (formation dates): {first} to {last}, {ic['rebalance_date'].nunique()} months",
        "rows: " + ", ".join(f"{t}={len(df)}" for t, df in frames.items()),
        "reproduce: python -m factor_mart.report",
    ]
    p = out / "MANIFEST.txt"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    written.append(p)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="factor_mart.report")
    ap.add_argument("--backend", choices=["duckdb", "snowflake"], default="duckdb")
    ap.add_argument("--duckdb-path", default="factor_mart.duckdb")
    ap.add_argument("--schema", default="core")
    ap.add_argument("--out", default="results")
    args = ap.parse_args(argv)

    if args.backend == "duckdb":
        from factor_mart.backends import DuckDBBackend
        backend: Backend = DuckDBBackend(args.duckdb_path)
    else:
        from dotenv import load_dotenv
        load_dotenv(override=True)
        from factor_mart.backends import SnowflakeBackend
        from factor_mart.config import SnowflakeSettings
        backend = SnowflakeBackend(SnowflakeSettings.from_env())

    for p in generate(backend, args.out, args.schema):
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
