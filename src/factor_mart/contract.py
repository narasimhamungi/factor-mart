"""Input data contract. The lakehouse gold layer must satisfy this or the run aborts loudly."""
from __future__ import annotations

import pandas as pd

REQUIRED = ("ticker", "trade_date", "adj_close")


class ContractError(ValueError):
    pass


def validate_prices(df: pd.DataFrame, dup_rel_tol: float | None = None) -> pd.DataFrame:
    """Return a cleaned copy (ticker upper-cased/stripped, trade_date as date, adj_close float)
    or raise ContractError listing *every* violation found.

    Duplicate (ticker, trade_date) rows are an error by default. With dup_rel_tol set, a duplicate
    group is collapsed only if its relative price spread (max-min)/min is <= dup_rel_tol; any group
    beyond tolerance still aborts, so a real conflict can never be resolved silently.
    The number of collapsed groups is recorded in result.attrs["deduped_groups"]."""
    problems: list[str] = []
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ContractError(f"Missing required columns: {missing}; got {list(df.columns)}")

    out = df[list(REQUIRED)].copy()
    out["ticker"] = out["ticker"].astype("string").str.strip().str.upper()
    out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce").dt.date
    out["adj_close"] = pd.to_numeric(out["adj_close"], errors="coerce")

    for col in REQUIRED:
        n = int(out[col].isna().sum())
        if n:
            problems.append(f"{n} null/unparseable values in {col}")
    out = out.dropna(subset=list(REQUIRED))

    nonpos = int((out["adj_close"] <= 0).sum())
    if nonpos:
        problems.append(f"{nonpos} rows with adj_close <= 0")

    dedup_groups = 0
    dup_mask = out.duplicated(subset=["ticker", "trade_date"], keep=False)
    if dup_mask.any():
        g = out.loc[dup_mask].groupby(["ticker", "trade_date"])["adj_close"]
        denom = g.min().abs().where(lambda x: x > 0)
        spread = (g.max() - g.min()) / denom
        worst = float(spread.max()) if spread.notna().any() else float("inf")
        n_groups = int(len(spread))
        if dup_rel_tol is None or not worst <= dup_rel_tol:
            tol_txt = "" if dup_rel_tol is None else f" (exceeds tolerance {dup_rel_tol:.0e})"
            problems.append(f"{n_groups} duplicate (ticker, trade_date) groups; "
                            f"max relative price spread {worst:.2e}{tol_txt}")
        else:
            out = out.drop_duplicates(subset=["ticker", "trade_date"], keep="first")
            dedup_groups = n_groups

    if out.empty:
        problems.append("no rows left after null removal")

    if problems:
        raise ContractError("; ".join(problems))
    out["adj_close"] = out["adj_close"].astype(float)
    out["ticker"] = out["ticker"].astype(str)
    out = out.reset_index(drop=True)
    out.attrs["deduped_groups"] = dedup_groups
    return out
