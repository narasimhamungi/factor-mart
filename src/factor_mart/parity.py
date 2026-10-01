"""Parity check: the same pipeline run on DuckDB and on Snowflake must produce the same marts.

    python -m factor_mart.parity [--duckdb-path factor_mart.duckdb] [--schema core]

Compares row counts of every model table, the factor summary, and per-row score / quintile /
forward return in mart_scores_monthly. Exit 0 = identical within tolerance, 1 = differences.
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from factor_mart.backends import Backend

TABLES = ["raw_prices", "returns", "market", "rebalance_dates", "signals", "scores",
          "fwd_returns", "mart_scores_monthly", "mart_factor_returns", "mart_ic", "mart_factor_summary"]
KEYS = ["ticker", "rebalance_date", "factor"]


def _float(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if c in KEYS or c == "factor":
            continue
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def compare(a: Backend, b: Backend, schema: str = "core", tol: float = 1e-9) -> tuple[bool, list[str]]:
    ok, lines = True, []

    lines.append("row counts")
    for t in TABLES:
        na = int(a.query_df(f"SELECT COUNT(*) FROM {schema}.{t}").iloc[0, 0])
        nb = int(b.query_df(f"SELECT COUNT(*) FROM {schema}.{t}").iloc[0, 0])
        same = na == nb
        ok &= same
        lines.append(f"  {t:22s} A={na:>10,}  B={nb:>10,}  {'OK' if same else 'MISMATCH'}")

    lines.append("factor summary (max abs difference per column)")
    sa = _float(a.query_df(f"SELECT * FROM {schema}.mart_factor_summary ORDER BY factor"))
    sb = _float(b.query_df(f"SELECT * FROM {schema}.mart_factor_summary ORDER BY factor"))
    if list(sa["factor"]) != list(sb["factor"]):
        ok = False
        lines.append("  factor lists differ")
    else:
        for c in [c for c in sa.columns if c != "factor"]:
            d = float(np.nanmax(np.abs(sa[c].to_numpy(float) - sb[c].to_numpy(float))))
            good = d <= max(tol, tol * float(np.nanmax(np.abs(sa[c].to_numpy(float)))))
            ok &= good
            lines.append(f"  {c:16s} {d:.3e}  {'OK' if good else 'DIFF'}")

    lines.append("row-level mart_scores_monthly")
    cols = "ticker, rebalance_date, factor, score, quintile, fwd_ret_1m"
    ra = _float(a.query_df(f"SELECT {cols} FROM {schema}.mart_scores_monthly"))
    rb = _float(b.query_df(f"SELECT {cols} FROM {schema}.mart_scores_monthly"))
    for df in (ra, rb):
        df["rebalance_date"] = pd.to_datetime(df["rebalance_date"])
    m = ra.merge(rb, on=KEYS, how="outer", suffixes=("_a", "_b"), indicator=True)
    only = int((m["_merge"] != "both").sum())
    both = m[m["_merge"] == "both"]
    q_bad = int((both["quintile_a"] != both["quintile_b"]).sum())
    s_max = float(np.nanmax(np.abs(both["score_a"] - both["score_b"]))) if len(both) else float("nan")
    f_max = float(np.nanmax(np.abs(both["fwd_ret_1m_a"] - both["fwd_ret_1m_b"]))) if len(both) else float("nan")
    ok &= (only == 0 and q_bad == 0 and s_max <= tol and f_max <= tol)
    lines.append(f"  keys present in only one engine : {only}")
    lines.append(f"  quintile disagreements          : {q_bad} of {len(both):,}")
    lines.append(f"  max |score diff|                : {s_max:.3e}")
    lines.append(f"  max |fwd_ret diff|              : {f_max:.3e}")
    return bool(ok), lines


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="factor_mart.parity")
    p.add_argument("--duckdb-path", default="factor_mart.duckdb")
    p.add_argument("--schema", default="core")
    args = p.parse_args(argv)

    from dotenv import load_dotenv
    load_dotenv(override=True)
    from factor_mart.backends import DuckDBBackend, SnowflakeBackend
    from factor_mart.config import SnowflakeSettings

    ok, lines = compare(DuckDBBackend(args.duckdb_path), SnowflakeBackend(SnowflakeSettings.from_env()),
                        args.schema)
    print("A = DuckDB, B = Snowflake")
    print("\n".join(lines))
    print("\nPARITY OK" if ok else "\nPARITY FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
