"""DW-10: read-only query runtime used by the app and the AI tools.

- open_current(): opens the release named in warehouse/releases/current.json with read_only=True after
  checking the file's SHA-256 against the pointer (identity check, cached per file size/mtime).
- query_view(view, columns, where, params, limit): the only query entry for the app/AI; the view must be
  in the release's allowed list, and only a plain SELECT over that view is built.
- results are cached with the release version in the key, so a new release invalidates them.
The runtime never writes: the connection is read-only and the release file itself is mode 0444.
"""
from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import ROOT, connect  # noqa: E402
from release import RELEASES, sha  # noqa: E402

IDENT = re.compile(r'^[a-z_][a-z0-9_]*$')
_identity_cache: dict = {}


class ReleaseError(RuntimeError):
    pass


def pointer(releases: Path = RELEASES) -> dict:
    p = releases / 'current.json'
    if not p.exists():
        raise ReleaseError('snapshot_unavailable: no published release')
    return json.loads(p.read_text(encoding='utf-8'))


def open_current(releases: Path = RELEASES):
    ptr = pointer(releases)
    f = releases / ptr['file']
    st = f.stat()
    key = (str(f), st.st_size, st.st_mtime_ns)
    if _identity_cache.get(key) != ptr['sha256']:
        if sha(f) != ptr['sha256']:
            raise ReleaseError(f'release file {f.name} does not match its recorded SHA-256')
        _identity_cache[key] = ptr['sha256']
    return connect(f, read_only=True), ptr


@lru_cache(maxsize=256)
def _cached(version: str, releases: str, sql: str, params: tuple):
    con, ptr = open_current(Path(releases))
    try:
        if ptr['version'] != version:
            raise ReleaseError('release changed while querying')
        cur = con.execute(sql, list(params))
        return tuple(d[0] for d in cur.description), tuple(tuple(str(v) if v is not None else None for v in r) for r in cur.fetchall())
    finally:
        con.close()


def query_view(view: str, columns: list[str] | None = None, where: dict | None = None, limit: int = 5000,
               releases: Path = RELEASES) -> dict:
    ptr = pointer(releases)
    if view not in ptr['allowed_views']:
        return {'status': 'unsupported', 'error': {'code': 'unknown_field', 'message': f'view {view} is not allowed'}}
    cols = columns or ['*']
    if any(c != '*' and not IDENT.match(c) for c in cols) or any(not IDENT.match(k) for k in (where or {})):
        return {'status': 'error', 'error': {'code': 'invalid_argument', 'message': 'bad column name'}}
    limit = max(1, min(int(limit), 5000))
    sql = f'SELECT {", ".join(cols)} FROM {view}'
    params = []
    if where:
        sql += ' WHERE ' + ' AND '.join(f'{k} = ?' for k in where)
        params = list(where.values())
    sql += f' LIMIT {limit}'
    names, rows = _cached(ptr['version'], str(releases), sql, tuple(params))
    return {'status': 'ok' if rows else 'empty', 'dataset_version': ptr['version'], 'columns': list(names), 'rows': [list(r) for r in rows],
            'mode': 'live'}


def cache_info():
    return _cached.cache_info()
