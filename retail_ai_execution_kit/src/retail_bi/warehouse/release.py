"""DW-10: publish a checked warehouse build as a read-only release.

The offline pipeline is the only writer and writes only under warehouse/builds/. Publishing copies a
build into warehouse/releases/<version>.duckdb (temp file + fsync + os.replace), records its identity
(SHA-256, size) and then atomically replaces warehouse/releases/current.json. Earlier releases are
kept, so `rollback` can point back to the previous one. If publishing stops at any point before the
pointer is replaced, readers still see the previous release unchanged.

usage:
  .venv/bin/python src/retail_bi/warehouse/release.py publish      # publishes warehouse/builds/latest.json
  .venv/bin/python src/retail_bi/warehouse/release.py rollback
  .venv/bin/python src/retail_bi/warehouse/release.py status
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import ROOT, connect  # noqa: E402

BUILDS = ROOT / 'warehouse/builds'
RELEASES = ROOT / 'warehouse/releases'
REQUIRED_ALLOWED_VIEWS = 6


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _write_json_atomic(path: Path, data: dict) -> None:
    tmp = path.with_name(f'.{path.name}.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def verify_build(path: Path) -> dict:
    con = connect(path, read_only=True)
    try:
        allowed = [r[0] for r in con.execute('SELECT view_name FROM meta.allowed_view ORDER BY 1').fetchall()]
        for v in allowed:
            con.execute(f'SELECT * FROM {v} LIMIT 1').fetchall()
        n_orders = con.execute('SELECT count(*) FROM dwd.fact_order').fetchone()[0]
        loaded = con.execute("SELECT count(*) FROM meta.load_batch WHERE status = 'loaded'").fetchone()[0]
    finally:
        con.close()
    if len(allowed) < REQUIRED_ALLOWED_VIEWS or n_orders == 0 or loaded != 1:   # 6 ADS views, plus ads.risk_summary_latest once scores exist
        raise ValueError(f'build {path.name} is not publishable: allowed views {len(allowed)}, orders {n_orders}, loaded batches {loaded}')
    return {'allowed_views': allowed, 'orders': n_orders}


def current(releases: Path = RELEASES) -> dict | None:
    p = releases / 'current.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None


def publish(build_file: Path | None = None, version: str | None = None, releases: Path = RELEASES, _fail_before_pointer: bool = False) -> dict:
    if build_file is None:
        latest = json.loads((BUILDS / 'latest.json').read_text(encoding='utf-8'))
        build_file, version = BUILDS / latest['file'], latest['version']
    version = version or build_file.stem
    releases.mkdir(parents=True, exist_ok=True)
    info = verify_build(build_file)
    target = releases / f'{version}.duckdb'
    prev = current(releases)
    if target.exists() and prev and prev['version'] == version and sha(target) == prev['sha256']:
        return {**prev, 'reused': True}
    tmp = releases / f'.{version}.{os.getpid()}.copy'
    try:
        shutil.copyfile(build_file, tmp)
        with open(tmp, 'rb') as f:
            os.fsync(f.fileno())
        digest = sha(tmp)
        if digest != sha(build_file):
            raise ValueError('copy differs from the build')
        os.replace(tmp, target)
        os.chmod(target, 0o444)                     # read-only on disk as well
        if _fail_before_pointer:
            raise RuntimeError('injected failure before the pointer switch (test)')
        pointer = {'version': version, 'file': target.name, 'sha256': digest, 'bytes': target.stat().st_size,
                   'published_at': datetime.now(timezone.utc).isoformat(), 'source_build': build_file.name,
                   'previous': prev['version'] if prev else None, 'allowed_views': info['allowed_views']}
        _write_json_atomic(releases / 'current.json', pointer)
        return pointer
    finally:
        if tmp.exists():
            tmp.unlink()


def rollback(releases: Path = RELEASES) -> dict:
    cur = current(releases)
    if not cur or not cur.get('previous'):
        raise ValueError('no previous release to roll back to')
    prev_file = releases / f"{cur['previous']}.duckdb"
    hist = json.loads((releases / 'history.json').read_text(encoding='utf-8')) if (releases / 'history.json').exists() else {}
    pointer = {'version': cur['previous'], 'file': prev_file.name, 'sha256': sha(prev_file), 'bytes': prev_file.stat().st_size,
               'published_at': datetime.now(timezone.utc).isoformat(), 'rolled_back_from': cur['version'],
               'previous': hist.get(cur['previous']), 'allowed_views': cur['allowed_views']}
    _write_json_atomic(releases / 'current.json', pointer)
    return pointer


def _record_history(releases: Path, pointer: dict) -> None:
    p = releases / 'history.json'
    hist = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    hist.setdefault(pointer['version'], pointer.get('previous'))
    _write_json_atomic(p, hist)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['publish', 'rollback', 'status'])
    a = ap.parse_args()
    if a.command == 'publish':
        r = publish()
        _record_history(RELEASES, r)
    elif a.command == 'rollback':
        r = rollback()
    else:
        r = current()
    print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
