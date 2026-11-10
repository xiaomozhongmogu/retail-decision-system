"""Independent checks of contracts/data_contract.json and docs/data_dictionary.md.

Recounts nulls and keys straight from the DATA-05 layer CSV files (not from the
builder's profile) and checks the DATA-04 acceptance items.
usage: .venv/bin/python evidence/DATA-04/verify_contract.py
"""
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAYER = ROOT / 'data/processed/engineering/d50ee64a0478d8ae-20261108T000000Z-engineering-import-v1'
c = json.loads((ROOT / 'contracts/data_contract.json').read_text(encoding='utf-8'))
md = (ROOT / 'docs/data_dictionary.md').read_text(encoding='utf-8')
ledger = json.loads((ROOT / 'project/tasks.json').read_text(encoding='utf-8'))
facts3 = json.loads((ROOT / 'reports/data/dataset_selection_facts.json').read_text(encoding='utf-8'))
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


REQUIRED = ['raw_name', 'standard_name', 'type', 'meaning', 'nullable', 'unit', 'source', 'role',
            'time_semantics', 'feature_policy', 'effective_business_field']
TIME_TYPES = {'date', 'timestamp'}
BAD_NAMES = ('channel', 'margin', 'profit', 'cogs', 'quantity', 'qty', 'inventory', 'consent', 'age', 'gender')

# --- approval tied to DATA-03 evidence
d3 = next(t for t in ledger['tasks'] if t['id'] == 'DATA-03')
check('status approved with DATA-03 evidence', c['status'] == 'approved'
      and c['approval_basis']['route_evidence'] in d3['evidence'] and d3['status'] == 'done')
check('approval states user authorization, not teacher', '不是教师确认' in c['approval_basis']['nature'] and '不是教师确认' in md)
check('layer manifest unchanged', hashlib.sha256((LAYER / 'manifest.json').read_bytes()).hexdigest() == c['layer_manifest_sha256'])
check('builder recorded no failures', c['check_failures'] == [])
check('currency USD, synthetic', c['business_currency'] == 'USD' and c['selected_dataset']['nature'] == 'fully_synthetic')

# --- every column of every layer table documented, with required keys
all_cols = 0
for table, spec in c['tables'].items():
    with open(LAYER / 'history_source' / f'{table}.csv', encoding='utf-8-sig', newline='') as f:
        r = csv.DictReader(f)
        header, rows = r.fieldnames, list(r)
    cols = spec['columns']
    check(f'{table}: columns match file header in order', [x['raw_name'] for x in cols] == header)
    check(f'{table}: row count', spec['rows'] == len(rows), f'{len(rows)}')
    for col in cols:
        all_cols += 1
        missing = [k for k in REQUIRED if k not in col]
        nulls = sum(row[col['raw_name']] == '' for row in rows)
        good = (not missing and col['meaning'] and col['standard_name'] and col['source']
                and col['nullable'] == (nulls > 0) and col['profile']['null_count'] == nulls
                and (col['type'] not in TIME_TYPES or col['time_semantics'])
                and (col['role'] not in ('pk', 'fk') or col['feature_policy'] == 'key')
                and f'| {col["raw_name"]} | {col["standard_name"]} | {col["type"]} |' in md)
        if not good:
            check(f'{table}.{col["raw_name"]} documented', False, f'missing={missing} nulls={nulls}')
    pk = spec['primary_key']
    seen = set()
    dup = 0
    for row in rows:
        k = tuple(row[x] for x in pk)
        dup += k in seen
        seen.add(k)
    check(f'{table}: primary key {pk} unique (recounted)', dup == 0)
check('all columns passed field checks', all(ok), f'{all_cols} columns')
check('101 columns across 10 tables', all_cols == 101 and len(c['tables']) == 10)

# --- foreign keys recorded for every fk column
fk_cols = {(t, x['raw_name']) for t, s in c['tables'].items() for x in s['columns'] if x['role'] == 'fk'}
fk_keys = {(k.split(':')[1].split('->')[0].split('.')[0], k.split(':')[1].split('->')[0].split('.')[1]) for k in c['keys'] if k.startswith('fk:')}
check('every fk column has a key check', fk_cols <= fk_keys, f'{sorted(fk_cols - fk_keys)}')
check('all key checks zero', all(v.get('orphans', 0) == 0 and v.get('duplicates', 0) == 0 and v.get('nulls', 0) == 0 for v in c['keys'].values()))
check('consistency checks zero', all(v == 0 for v in c['consistency_checks'].values()))

# --- effective fields
eff = c['effective_business_fields']
roles = {f'{t}.{x["raw_name"]}': x['role'] for t, s in c['tables'].items() for x in s['columns']}
check('>= 8 effective fields', len(eff) >= 8 and c['effective_business_field_count'] == len(eff), f'{len(eff)}')
check('effective fields exclude labels/calendar/derived/scenario/denormalized',
      all(roles[f] not in ('generator_label', 'calendar', 'derived', 'scenario', 'denormalized') for f in eff))
check('effective fields equal DATA-03 checked fields', set(eff) == set(facts3['checked_business_fields']))
check('related fields listed separately with full key coverage (listing does not add to the count)',
      all(r['coverage_rows'] == r['child_rows'] for r in c['verified_related_fields'] if 'note' not in r)
      and len(set(eff)) == len(eff) == c['effective_business_field_count'])

# --- no invented fields
names = [x['standard_name'] for s in c['tables'].values() for x in s['columns']]
check('no channel/margin/quantity-like column invented', not any(b in n.split('_') for n in names for b in BAD_NAMES))
check('not_available lists channel, margin, quantity', all(x in ''.join(c['not_available']) for x in ('渠道', '毛利', '购买数量')))
check('UCI candidate superseded', 'UCI' in c['superseded'] and 'GBP' not in json.dumps(c['tables']))

print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
