from __future__ import annotations

import argparse
import os
import sys

from factor_mart.backends import DuckDBBackend, SnowflakeBackend
from factor_mart.checks import run_checks
from factor_mart.config import Params, SnowflakeSettings
from factor_mart.contract import validate_prices
from factor_mart.runner import run_models
from factor_mart.sources import read_prices


def _backend(args):
    if args.backend == "duckdb":
        return DuckDBBackend(args.duckdb_path)
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except ImportError:
        pass
    return SnowflakeBackend(SnowflakeSettings.from_env())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="factor-mart")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--backend", choices=["duckdb", "snowflake"], default="duckdb")
        sp.add_argument("--duckdb-path", default="factor_mart.duckdb")
        sp.add_argument("--schema", default=None)
        sp.add_argument("--min-universe", type=int, default=30)
        sp.add_argument("--max-gap-days", type=int, default=5)

    r = sub.add_parser("run", help="validate -> load -> build models -> checks")
    common(r)
    r.add_argument("--parquet"); r.add_argument("--csv")
    r.add_argument("--postgres-url"); r.add_argument("--query")
    r.add_argument("--query-file", help="path to a .sql file used instead of --query")
    r.add_argument("--dup-tol", type=float, default=None,
                   help="collapse duplicate (ticker, date) groups only if relative price spread <= this (e.g. 1e-5)")
    c = sub.add_parser("check", help="re-run invariants on existing marts")
    common(c)

    args = p.parse_args(argv)
    schema = args.schema or (os.environ.get("SNOWFLAKE_SCHEMA", "core")
                             if args.backend == "snowflake" else "core")
    params = Params(schema=schema, min_universe=args.min_universe, max_gap_days=args.max_gap_days)
    backend = _backend(args)

    if args.cmd == "run":
        query = args.query
        if args.query_file:
            if query:
                p.error("use either --query or --query-file, not both")
            with open(args.query_file, encoding="utf-8") as fh:
                query = fh.read()
        df = validate_prices(read_prices(args.parquet, args.csv, args.postgres_url, query),
                             dup_rel_tol=args.dup_tol)
        if df.attrs.get("deduped_groups"):
            print(f"collapsed {df.attrs['deduped_groups']:,} duplicate (ticker, date) groups "
                  f"within tolerance {args.dup_tol:.0e}")
        print(f"contract OK: {len(df):,} rows, {df['ticker'].nunique():,} tickers, "
              f"{df['trade_date'].min()} -> {df['trade_date'].max()}")
        backend.load_prices(df, params.schema)
        for name in run_models(backend, params):
            print(f"ran {name}")

    win = backend.query_df(f"SELECT MIN(rebalance_date) AS a, MAX(rebalance_date) AS b, "
                           f"COUNT(DISTINCT rebalance_date) AS n FROM {params.schema}.mart_scores_monthly")
    print(f"mart window: {win.iloc[0, 0]} -> {win.iloc[0, 1]} ({int(win.iloc[0, 2])} scored months)")
    fails, warns = run_checks(backend, params)
    for w in warns:
        print(f"WARN: {w}")
    for f in fails:
        print(f"FAIL: {f}")
    if fails:
        return 1
    print("checks OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
