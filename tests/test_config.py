import pytest

from factor_mart.config import SnowflakeSettings

BASE = {"SNOWFLAKE_ACCOUNT": "ORG-ACCT", "SNOWFLAKE_USER": "U", "SNOWFLAKE_WAREHOUSE": "W",
        "SNOWFLAKE_DATABASE": "D", "SNOWFLAKE_SCHEMA": "S"}


def _set(monkeypatch, **extra):
    for k in list(__import__("os").environ):
        if k.startswith("SNOWFLAKE_"):
            monkeypatch.delenv(k)
    for k, v in {**BASE, **extra}.items():
        monkeypatch.setenv(k, v)


def test_key_path_alias_and_passphrase(monkeypatch):
    _set(monkeypatch, SNOWFLAKE_PRIVATE_KEY_PATH="C:/k.p8", SNOWFLAKE_PRIVATE_KEY_PASSPHRASE="pw")
    s = SnowflakeSettings.from_env()
    assert s.private_key_file == "C:/k.p8" and s.private_key_passphrase == "pw"


def test_file_name_wins_and_passphrase_optional(monkeypatch):
    _set(monkeypatch, SNOWFLAKE_PRIVATE_KEY_FILE="a.p8", SNOWFLAKE_PRIVATE_KEY_PATH="b.p8")
    s = SnowflakeSettings.from_env()
    assert s.private_key_file == "a.p8" and s.private_key_passphrase is None


def test_requires_some_credential(monkeypatch):
    _set(monkeypatch)
    with pytest.raises(RuntimeError, match="PRIVATE_KEY"):
        SnowflakeSettings.from_env()
