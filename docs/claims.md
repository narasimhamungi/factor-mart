# Claims ledger

Generated 2026-11-04. This repo already ships its own "Verification status" table in the README (as of 2026-10-01) —
this ledger confirms that table is accurate and current rather than re-deriving it.

| Claim | Tag | Evidence |
|---|---|---|
| SQL logic correct: 28 DuckDB tests (exact beta recovery, momentum/reversal vs pandas reference, etc.) | Demonstrated | README verification table |
| Pipeline runs on real lakehouse data: 957,361 rows, 503 tickers after de-duplication | Demonstrated | README verification table |
| Pipeline runs on Snowflake (trial account, key-pair auth) | Demonstrated | README verification table |
| DuckDB and Snowflake agree: identical row counts, zero quintile disagreements, scores equal to float precision; one real engine difference found and fixed (decimal AVG rounding) | Demonstrated | README verification table, `factor_mart.parity` |
| CI: DuckDB suite on every push; Snowflake load/parity run manually (needs credentials) | Demonstrated — correctly scoped, not claimed as CI-automated | README verification table |
| Power BI model / DAX | Unsupported — explicitly marked "Not built," spec only | README verification table |
| Factor performance is investable | Unsupported — explicitly marked "No" in the README's own table | README verification table |
| Six tickers carry duplicate security_keys in the lakehouse's `dim_security` (root cause flagged as lakehouse-side, not factor-mart's) | Demonstrated | README, `--dup-tol` handling |

## Action
No overclaim found — this repo's self-reported verification table is itself a model claims ledger: it states "Not built" and "No" as plainly as it states "Demonstrated." Nothing to fix.
