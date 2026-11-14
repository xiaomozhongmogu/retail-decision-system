"""Small shared helpers for the warehouse stages (DuckDB).

- named SQL blocks: a .sql file is split on lines "-- name: <block>"
- connect(): opens a DuckDB file with UTC session time zone
Timestamps with time zone are never fetched into Python objects (that needs pytz,
which is not installed); queries cast them to VARCHAR when returning values.
"""
from __future__ import annotations

import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[3]


def connect(path: Path | str, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(path), read_only=read_only)
    con.execute("SET timezone = 'UTC'")
    return con


def sql_blocks(path: Path) -> dict[str, str]:
    text = Path(path).read_text(encoding='utf-8')
    parts = re.split(r'^-- name: (\S+)\s*$', text, flags=re.M)
    blocks = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}
    if not blocks:
        raise ValueError(f'no "-- name:" blocks in {path}')
    return blocks


def run_script(con, sql: str) -> None:
    """Execute a block that may hold several statements."""
    con.execute(sql)
