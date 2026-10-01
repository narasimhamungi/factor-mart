from __future__ import annotations

from typing import Protocol

import pandas as pd

from factor_mart.config import SnowflakeSettings


class Backend(Protocol):
    name: str

    def execute(self, sql: str) -> None: ...
    def query_df(self, sql: str) -> pd.DataFrame: ...
    def load_prices(self, df: pd.DataFrame, schema: str) -> None: ...


class DuckDBBackend:
    """Local engine used for tests and offline development. Same SQL files as Snowflake."""
    name = "duckdb"

    def __init__(self, path: str = ":memory:"):
        import duckdb
        self.con = duckdb.connect(path)

    def execute(self, sql: str) -> None:
        self.con.execute(sql)

    def query_df(self, sql: str) -> pd.DataFrame:
        return self.con.execute(sql).df()

    def load_prices(self, df: pd.DataFrame, schema: str) -> None:
        self.con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        self.con.register("_prices_df", df)
        self.con.execute(
            f"CREATE OR REPLACE TABLE {schema}.raw_prices AS "
            "SELECT ticker, CAST(trade_date AS DATE) AS trade_date, "
            "CAST(adj_close AS DOUBLE) AS adj_close FROM _prices_df"
        )
        self.con.unregister("_prices_df")


class SnowflakeBackend:
    """NOT yet exercised against a live account - see README 'Verification status'."""
    name = "snowflake"

    def __init__(self, settings: SnowflakeSettings):
        import snowflake.connector
        kwargs = dict(account=settings.account, user=settings.user,
                      warehouse=settings.warehouse, database=settings.database,
                      schema=settings.schema)
        if settings.role:
            kwargs["role"] = settings.role
        if settings.private_key_file:
            kwargs["private_key_file"] = settings.private_key_file
            if settings.private_key_passphrase:
                kwargs["private_key_file_pwd"] = settings.private_key_passphrase
        else:
            kwargs["password"] = settings.password
        self.con = snowflake.connector.connect(**kwargs)

    def execute(self, sql: str) -> None:
        cur = self.con.cursor()
        try:
            cur.execute(sql)
        finally:
            cur.close()

    def query_df(self, sql: str) -> pd.DataFrame:
        cur = self.con.cursor()
        try:
            cur.execute(sql)
            df = cur.fetch_pandas_all()
        finally:
            cur.close()
        df.columns = [c.lower() for c in df.columns]
        return df

    def load_prices(self, df: pd.DataFrame, schema: str) -> None:
        from snowflake.connector.pandas_tools import write_pandas
        self.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        self.execute(f"CREATE OR REPLACE TABLE {schema}.raw_prices "
                     "(ticker VARCHAR, trade_date DATE, adj_close DOUBLE)")
        out = df[["ticker", "trade_date", "adj_close"]].copy()
        out.columns = [c.upper() for c in out.columns]  # unquoted DDL => UPPERCASE identifiers
        ok, _chunks, nrows, _ = write_pandas(self.con, out, "RAW_PRICES", schema=schema.upper())
        if not ok or nrows != len(out):
            raise RuntimeError(f"Snowflake load mismatch: sent {len(out)} rows, loaded {nrows}")
