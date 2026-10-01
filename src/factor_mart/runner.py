from __future__ import annotations

from importlib import resources

from factor_mart.backends import Backend
from factor_mart.config import Params


def split_statements(sql: str) -> list[str]:
    """Split on ';' outside single-quoted string literals; drop whole-line '--' comments."""
    text = "\n".join(ln for ln in sql.splitlines() if not ln.strip().startswith("--"))
    stmts, buf, in_quote, i = [], [], False, 0
    while i < len(text):
        ch = text[i]
        if ch == "'":
            if in_quote and text[i + 1:i + 2] == "'":   # escaped '' inside a literal
                buf.append("''")
                i += 2
                continue
            in_quote = not in_quote
        if ch == ";" and not in_quote:
            stmts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    if in_quote:
        raise ValueError("Unterminated string literal in SQL")
    stmts.append("".join(buf).strip())
    return [s for s in stmts if s]


def render(sql: str, params: Params) -> str:
    for key, val in params.as_template_vars().items():
        sql = sql.replace("{{" + key + "}}", val)
    if "{{" in sql:
        raise ValueError("Unresolved template variable in SQL")
    return sql


def model_files() -> list[tuple[str, str]]:
    root = resources.files("factor_mart").joinpath("sql")
    files = sorted((p for p in root.iterdir() if p.name.endswith(".sql")), key=lambda p: p.name)
    return [(p.name, p.read_text(encoding="utf-8")) for p in files]


def run_models(backend: Backend, params: Params, only: list[str] | None = None) -> list[str]:
    """Execute SQL models in filename order. `only` = list of file-name prefixes, e.g. ['06']."""
    ran = []
    for name, text in model_files():
        if only and not any(name.startswith(p) for p in only):
            continue
        for stmt in split_statements(render(text, params)):
            backend.execute(stmt)
        ran.append(name)
    return ran
