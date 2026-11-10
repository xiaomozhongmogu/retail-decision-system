"""DW-02 checks: every ODS value equals the source text; failures leave no false success.
usage: .venv/bin/python evidence/DW-02/verify_ods.py
"""
import csv
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
sys.path.insert(0, str(ROOT / 'tests/data'))
from ods import load  # noqa: E402
from db import connect  # noqa: E402
from conftest import write_layer  # noqa: E402

LAYER = ROOT / 'data/processed/engineering/d50ee64a0478d8ae-20261108T000000Z-engineering-import-v1'
DB = ROOT / 'warehouse/build/dev.duckdb'
C = json.loads((ROOT / 'contracts/data_contract.json').read_text(encoding='utf-8'))
A = json.loads((ROOT / 'reports/warehouse/ods_audit.json').read_text(encoding='utf-8'))
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


con = connect(DB, read_only=True)
for t, spec in C['tables'].items():
    raw = [c['raw_name'] for c in spec['columns']]
    with open(LAYER / 'history_source' / f'{t}.csv', encoding='utf-8-sig', newline='') as f:
        src = [tuple(r) for r in list(csv.reader(f))[1:]]
    q = ', '.join(f'"{c}"' for c in raw)
    ods = [tuple(r) for r in con.execute(f'SELECT {q} FROM ods.{t} WHERE _batch_id = ? ORDER BY _row_no', [A['batch_id']]).fetchall()]
    meta = con.execute(f"""SELECT count(DISTINCT _source_sha256), min(_row_no), max(_row_no), count(*) FILTER (WHERE _loaded_at IS NULL),
                                  any_value(_source_file) FROM ods.{t}""").fetchone()
    check(f'ods.{t}: every value equals source text in row order; metadata present', ods == src and meta[0] == 1 and meta[1] == 1
          and meta[2] == len(src) and meta[3] == 0 and meta[4] == f'history_source/{t}.csv', f'{len(src)} rows')
empties = con.execute("SELECT count(*) FROM ods.orders WHERE order_approved_at = ''").fetchone()[0]
check('empty source fields kept as empty text (not NULL)', empties == 194, str(empties))
check('one loaded batch, counts match manifest', A['all_counts_match'] and A['batches_in_db'] == [[A['batch_id'], 'loaded']])
log = (ROOT / 'evidence/DW-02/ods_run.log').read_text(encoding='utf-8')
check('rerun skipped the already-loaded batch', '"skipped_already_loaded": true' in log)
con.close()


def fixture(root, mutate_manifest=None, drop=None):
    lay = write_layer(root)
    man = json.loads((lay / 'manifest.json').read_text(encoding='utf-8'))
    for o in man['outputs']:
        with open(lay / o['path'], encoding='utf-8-sig', newline='') as f:
            o['rows'] = sum(1 for _ in csv.reader(f)) - 1
    man['version'] = 'fixture-v1'
    if mutate_manifest:
        mutate_manifest(man)
    (lay / 'manifest.json').write_text(json.dumps(man), encoding='utf-8')
    if drop:
        (lay / drop).unlink()
    return lay


def state(db):
    c = connect(db, read_only=True)
    r = (c.execute('SELECT count(*) FROM meta.load_batch').fetchone()[0], c.execute('SELECT count(*) FROM ods.orders').fetchone()[0],
         c.execute('SELECT count(*) FROM meta.load_file').fetchone()[0])
    c.close()
    return r


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    lay = fixture(tmp / 'a', drop='history_source/reviews.csv')
    try:
        load(lay, tmp / 'a.duckdb')
        raised = None
    except FileNotFoundError as exc:
        raised = str(exc)
    check('missing file: clear error naming the file', raised is not None and 'reviews.csv' in raised, raised or '')
    check('missing file: no batch, no rows left behind', state(tmp / 'a.duckdb') == (0, 0, 0), str(state(tmp / 'a.duckdb')))

    lay = fixture(tmp / 'b')
    (lay / 'history_source/payments.csv').write_text('tampered', encoding='utf-8')
    try:
        load(lay, tmp / 'b.duckdb')
        raised = None
    except ValueError as exc:
        raised = str(exc)
    check('hash mismatch: refused, nothing committed', raised and 'payments.csv' in raised and state(tmp / 'b.duckdb') == (0, 0, 0))

    lay = fixture(tmp / 'c', mutate_manifest=lambda m: [o.update(rows=o['rows'] + 1) for o in m['outputs'] if o['path'].endswith('reviews.csv')])
    try:
        load(lay, tmp / 'c.duckdb')
        raised = None
    except ValueError as exc:
        raised = str(exc)
    check('row-count mismatch midway (after orders loaded): rolled back, no false loaded status',
          raised and 'reviews' in raised and state(tmp / 'c.duckdb') == (0, 0, 0), str(state(tmp / 'c.duckdb')))

    lay = fixture(tmp / 'd')
    r1, r2 = load(lay, tmp / 'd.duckdb'), load(lay, tmp / 'd.duckdb')
    check('fixture: load then rerun skips without duplicating rows',
          not r1['skipped_already_loaded'] and r2['skipped_already_loaded'] and state(tmp / 'd.duckdb') == (1, 4, 10))
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
