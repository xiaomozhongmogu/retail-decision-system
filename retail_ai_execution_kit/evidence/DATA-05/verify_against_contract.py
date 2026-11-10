"""DATA-05 review: check the engineering import against the approved contract (DATA-04)
and the frozen research scope (DATA-03).
usage: .venv/bin/python evidence/DATA-05/verify_against_contract.py
"""
import csv
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
contract = json.loads((ROOT / 'contracts/data_contract.json').read_text(encoding='utf-8'))
manifest_report = ROOT / 'reports/data/source_manifest.json'
key = 'd50ee64a0478d8ae-20261108T000000Z-engineering-import-v1'
layer = ROOT / 'data/processed/engineering' / key
src_zip = ROOT.parent / 'ecommerce-sample-database-100k/01_source/baseline_10000_seed42.zip'
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


m = json.loads(manifest_report.read_text(encoding='utf-8'))
want = contract['selected_dataset']['source_archive_sha256']
check('reports/data/source_manifest.json is byte-identical to layer manifest',
      manifest_report.read_bytes() == (layer / 'manifest.json').read_bytes())
check('manifest source hash = contract source hash', m['source_sha256'] == want)
check('source ZIP hash unchanged', sha(src_zip) == want)
check('read-only archive copy has same hash', sha(ROOT / 'data/raw/archives' / f'{want}.zip') == want)
check('cutoff = contract as_of', m['as_of_exclusive'] == contract['as_of_exclusive'])
check('layer version = contract engineering version', m['version'] == contract['selected_dataset']['engineering_layer_version'])

with zipfile.ZipFile(src_zip) as z:
    members = {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()
               if n.endswith('.csv') and not n.startswith('__MACOSX/')}
recorded = {x['member']: x['sha256'] for x in m['source_members']}
check('all 12 ZIP CSV members recorded with matching hash', members == recorded and len(members) == 12, f'{len(members)} members')

outs = {x['path']: x for x in m['outputs']}
for p, x in outs.items():
    if sha(layer / p) != x['sha256']:
        check(f'output hash {p}', False)
check('all layer outputs match manifest hashes', all(sha(layer / p) == x['sha256'] for p, x in outs.items()), f'{len(outs)} files')
for t, spec in contract['tables'].items():
    o = outs.get(f'history_source/{t}.csv')
    with open(layer / 'history_source' / f'{t}.csv', encoding='utf-8-sig', newline='') as f:
        header = next(csv.reader(f))
    check(f'{t}: in scope, rows and columns match contract',
          o is not None and o['rows'] == spec['rows'] and o['columns'] == header == [c['raw_name'] for c in spec['columns']])

code = (ROOT / 'src/retail_bi/data/ingest.py').read_text(encoding='utf-8')
check('import code reads no credentials or network', not re.search(r'environ|getenv|dotenv|requests|urllib|http', code))
check('no .env file in project', not (ROOT / '.env').exists())
check('raw and processed data are git-ignored',
      all(x in (ROOT / '.gitignore').read_text(encoding='utf-8') for x in ('data/raw/', 'data/processed/')))
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
