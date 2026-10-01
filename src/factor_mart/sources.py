from __future__ import annotations

import pandas as pd


def read_prices(parquet: str | None = None, csv: str | None = None,
                postgres_url: str | None = None, query: str | None = None) -> pd.DataFrame:
    """Read the lakehouse gold prices. The result must expose ticker, trade_date, adj_close
    (alias columns in --query if your gold table names them differently)."""
    given = [x for x in (parquet, csv, postgres_url) if x]
    if len(given) != 1:
        raise ValueError("Provide exactly one of: parquet, csv, postgres_url")
    if parquet:
        return pd.read_parquet(parquet)
    if csv:
        return pd.read_csv(csv)
    if not query:
        raise ValueError("--query is required with --postgres-url")
    from sqlalchemy import create_engine
    return pd.read_sql(query, create_engine(postgres_url))
