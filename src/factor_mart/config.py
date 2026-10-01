from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Params:
    schema: str = "core"
    min_universe: int = 30      # min names with a valid value on a date / per factor-month
    max_gap_days: int = 5       # a daily return is NULL if the gap to the prior obs is larger

    def as_template_vars(self) -> dict[str, str]:
        return {
            "schema": self.schema,
            "min_universe": str(int(self.min_universe)),
            "max_gap_days": str(int(self.max_gap_days)),
        }


@dataclass
class SnowflakeSettings:
    account: str
    user: str
    warehouse: str
    database: str
    schema: str
    role: str | None = None
    password: str | None = None
    private_key_file: str | None = None
    private_key_passphrase: str | None = None

    @classmethod
    def from_env(cls) -> "SnowflakeSettings":
        env = os.environ
        missing = [k for k in ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_WAREHOUSE",
                               "SNOWFLAKE_DATABASE", "SNOWFLAKE_SCHEMA") if not env.get(k)]
        if missing:
            raise RuntimeError(f"Missing Snowflake env vars: {', '.join(missing)}")
        key_file = env.get("SNOWFLAKE_PRIVATE_KEY_FILE") or env.get("SNOWFLAKE_PRIVATE_KEY_PATH")
        if not (env.get("SNOWFLAKE_PASSWORD") or key_file):
            raise RuntimeError("Set SNOWFLAKE_PRIVATE_KEY_FILE (or _PATH), or SNOWFLAKE_PASSWORD")
        return cls(
            account=env["SNOWFLAKE_ACCOUNT"], user=env["SNOWFLAKE_USER"],
            warehouse=env["SNOWFLAKE_WAREHOUSE"], database=env["SNOWFLAKE_DATABASE"],
            schema=env["SNOWFLAKE_SCHEMA"], role=env.get("SNOWFLAKE_ROLE"),
            password=env.get("SNOWFLAKE_PASSWORD"),
            private_key_file=key_file,
            private_key_passphrase=env.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE") or None,
        )
