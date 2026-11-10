"""DATA-07 checks: real output against the source layer, plus failure paths on
fixtures built in a temporary directory (physically separate from real data).
usage: .venv/bin/python evidence/DATA-07/verify_clean.py
"""
import csv
import hashlib
import json
import shutil
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/data'))
from clean import build, parse  # noqa: E402

LAYER = ROOT / 'data/processed/engineering/d50ee64a0478d8ae-20261108T000000Z-engineering-import-v1'
CONTRACT = ROOT / 'contracts/data_contract.json'
C = json.loads(CONTRACT.read_text(encoding='utf-8'))
REPORT = json.loads((ROOT / 'reports/data/cleaning_missing_duplicates.json').read_text(encoding='utf-8'))
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rows(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


# ---------- real output
target = ROOT / 'data/processed/clean' / REPORT['clean_key']
m = json.loads((target / 'manifest.json').read_text(encoding='utf-8'))
for t, spec in C['tables'].items():
    src = rows(LAYER / 'history_source' / f'{t}.csv')
    tbl = pq.read_table(target / f'{t}.parquet')
    df = tbl.to_pandas()
    std = {c['raw_name']: c['standard_name'] for c in spec['columns']}
    same_rows = len(src) == tbl.num_rows == m['tables'][t]['rows_out']
    same_nulls = all(int(df[c['standard_name']].isna().sum()) == c['profile']['null_count'] for c in spec['columns'])
    ids_full = all(df[c['standard_name']].notna().all() for c in spec['columns'] if c['role'] in ('pk', 'fk'))
    money = all(sum(Decimal(r[c['raw_name']]) for r in src) == sum(df[c['standard_name']])
                for c in spec['columns'] if c['type'] == 'decimal(12,2)')
    typ = {c['raw_name']: c['type'] for c in spec['columns']}
    keys_equal = [tuple(parse(typ[k], r[k]) for k in spec['primary_key']) for r in src] == \
        [tuple(v) for v in tbl.select([std[k] for k in spec['primary_key']]).to_pylist() for v in [v.values()]]
    check(f'{t}: rows, nulls (no imputation), IDs, money sums, keys equal source', same_rows and same_nulls and ids_full and money and keys_equal)
ts = pq.read_table(target / 'orders.parquet').schema.field('purchase_ts').type
check('timestamps typed as UTC (engineering assumption)', str(ts) == 'timestamp[ms, tz=UTC]', str(ts))
check('nothing quarantined in real data and counts reconcile',
      m['quarantine']['dir'] is None and all(v['rows_in'] == v['rows_out'] + v['rows_quarantined'] for v in m['tables'].values()))
cov = REPORT['customer_coverage']
check('summary and customer-model coverage reported separately',
      cov['summary_scope_orders'] == 9311 and cov['customer_model_scope_orders'] == 9311 and cov['unknown_customer_orders'] == 0)
check('repeated product lines kept with reason', REPORT['duplicates']['same_product_repeated_lines_kept'] == 779
      and '不假定订单+商品唯一' in REPORT['duplicates']['same_product_rule'])

# ---------- fixtures (temporary directory)


def make_fixture(root):
    fx = root / 'layer'
    shutil.copytree(LAYER, fx)
    o = fx / 'history_source/orders.csv'
    lines = o.read_text(encoding='utf-8-sig').splitlines()
    parts = lines[5].split(',')
    parts[3] = '2025-13-45T99:00:00'          # unparseable purchase time on CSV line 6
    lines[5] = ','.join(parts)
    o.write_text('﻿' + '\n'.join(lines) + '\n', encoding='utf-8')
    cu = fx / 'history_source/customers.csv'
    lines = cu.read_text(encoding='utf-8-sig').splitlines()
    lines.append(lines[1])                    # duplicate primary key
    cu.write_text('﻿' + '\n'.join(lines) + '\n', encoding='utf-8')
    man = json.loads((fx / 'manifest.json').read_text(encoding='utf-8'))
    for item in man['outputs']:
        item['sha256'] = sha(fx / item['path'])
    (fx / 'manifest.json').write_text(json.dumps(man, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return fx, rows(o)[4]['order_id']


def reject(fn, word):
    try:
        fn()
    except (ValueError, FileExistsError) as exc:
        return word in str(exc) or word == ''
    return False


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    fx, bad_order = make_fixture(root)
    out, qr = root / 'out', root / 'quarantine'
    tgt, man, reused = build(fx, CONTRACT, out, qr)
    q_orders = rows(Path(man['quarantine']['dir']) / 'orders.csv')
    q_cust = rows(Path(man['quarantine']['dir']) / 'customers.csv')
    check('fixture: bad timestamp quarantined with source line and reason',
          any(r['source_line'] == '6' and r['column'] == 'order_purchase_timestamp' and 'timestamp' in r['reason'] for r in q_orders))
    check('fixture: duplicate primary key quarantined', any('duplicate primary key' in r['reason'] for r in q_cust))
    check('fixture: dependent rows of the bad order quarantined as orphans, not silently dropped',
          any(r['value'] == bad_order and 'orphan' in r['reason'] for r in rows(Path(man['quarantine']['dir']) / 'order_items.csv')))
    check('fixture: every input row is either output or quarantined',
          all(v['rows_in'] == v['rows_out'] + v['rows_quarantined'] for v in man['tables'].values())
          and man['tables']['orders']['rows_out'] == 9310 and man['tables']['customers']['rows_out'] == 3647)
    before = {p.name: sha(p) for p in tgt.iterdir()}
    _, _, reused = build(fx, CONTRACT, out, qr)
    check('fixture: rerun reuses output without rewriting', reused and before == {p.name: sha(p) for p in tgt.iterdir()})
    (tgt / 'orders.parquet').write_bytes(b'corrupt')
    check('fixture: tampered output refused, not overwritten',
          reject(lambda: build(fx, CONTRACT, out, qr), 'changed') and (tgt / 'orders.parquet').read_bytes() == b'corrupt')
    c2 = root / 'contract.json'
    c2.write_text(CONTRACT.read_text(encoding='utf-8').replace('"meaning": "订单标识"', '"meaning": "订单号"'), encoding='utf-8')
    out2 = root / 'out2'
    build(fx, CONTRACT, out2, root / 'q2')
    check('fixture: same version key with a different contract is refused', reject(lambda: build(fx, c2, out2, root / 'q2'), 'different inputs'))
    (fx / 'history_source/payments.csv').write_text('changed', encoding='utf-8')
    check('fixture: input layer file changed after import is refused', reject(lambda: build(fx, CONTRACT, root / 'out3', root / 'q3'), 'changed after import'))
    fx2, _ = make_fixture(root / 'b') if (root / 'b').mkdir() is None else (None, None)
    key_dir = root / 'out4'
    key_dir.mkdir()
    lay_sha = sha(fx2 / 'manifest.json')
    (key_dir / f'{lay_sha[:16]}-{C["contract_version"]}-clean-v1.lock').mkdir()
    check('fixture: active lock refused', reject(lambda: build(fx2, CONTRACT, key_dir, root / 'q4'), ''))
    check('fixture: lock left in place for a person to inspect', (key_dir / f'{lay_sha[:16]}-{C["contract_version"]}-clean-v1.lock').is_dir())

check('real data untouched by fixture tests', sha(LAYER / 'manifest.json') == REPORT['identity']['layer_manifest_sha256'])
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
