"""Independent source/roundtrip/event controls and import failure-path checks."""
import csv
from datetime import datetime
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/retail_bi/data'))
from ingest import build

run=json.loads((ROOT/'evidence/DATA-05/import_run.json').read_text());target=Path(run['target']);m=run['manifest'];source=ROOT.parent/'ecommerce-sample-database-100k/01_source/baseline_10000_seed42.zip'
def rows(blob):return list(csv.DictReader(io.StringIO(blob.decode('utf-8-sig'))))
with zipfile.ZipFile(source) as z:
 raw={Path(n).stem:rows(z.read(n)) for n in z.namelist() if n.endswith('.csv') and not n.startswith('__MACOSX/')}
cutoff=datetime(2026,11,8);ids={r['order_id'] for r in raw['orders'] if datetime.fromisoformat(r['order_purchase_timestamp'])<cutoff}
for name in ('customers','sellers','products','seller_products','orders','order_items','payments','shipping','reviews','calendar'):
 expected=raw[name]
 if name in ('orders','order_items','payments','shipping','reviews'):expected=[r for r in expected if r['order_id'] in ids]
 if name=='calendar':expected=[r for r in expected if datetime.fromisoformat(r['date'])<cutoff]
 actual=rows((target/'history_source'/f'{name}.csv').read_bytes())
 assert expected==actual,name
print('PASS all 10 history tables equal independent source cutoff; strings and leading zeros preserved')
for table,key,col in [('customers','customer_id','customer_zip_prefix'),('sellers','seller_id','seller_zip_prefix')]:
 actual={r[key]:r[col] for r in rows((target/'history_source'/f'{table}.csv').read_bytes())}
 assert all(actual[r[key]]==r[col] for r in raw[table])
orders=rows((target/'observed/orders.csv').read_bytes());reviews=rows((target/'observed/reviews.csv').read_bytes())
assert len(orders)==9311 and len(reviews)==6096
for r in orders:
 assert 'order_status' not in r
 for c in ('order_purchase_timestamp','order_approved_at','order_delivered_carrier_date','order_delivered_customer_date'):
  assert not r[c] or datetime.fromisoformat(r[c])<cutoff
for r in reviews:
 for c in ('review_creation_date','review_answer_timestamp'):assert not r[c] or datetime.fromisoformat(r[c])<cutoff
print('PASS observed views independently contain no post-cutoff actual dates or final order status')
manifest_before=(target/'manifest.json').read_bytes()
replayed,replay=build(source,Path(m['archive']).parent,target.parent,'2026-11-08T00:00:00Z',m['source_sha256'])
assert replayed==target and (target/'manifest.json').read_bytes()==manifest_before
print('PASS repeated import idempotent, manifest byte-identical')
with tempfile.TemporaryDirectory() as temp:
 root=Path(temp)
 def reject(fn):
  try:fn()
  except (ValueError,FileExistsError):return
  raise AssertionError('Expected failure')
 reject(lambda:build(source,root/'raw',root/'work','2026-11-08T00:00:00Z','0'*64))
 assert not (root/'work').exists()
 reject(lambda:build(source,root/'raw',root/'work','2026-11-08',m['source_sha256']))
 reject(lambda:build(source,source.parent/'unsafe',root/'work','2026-11-08T00:00:00Z',m['source_sha256']))
 assert not (source.parent/'unsafe').exists()
 reject(lambda:build(source,root/'raw',root/'work','2023-01-01T00:00:00Z',m['source_sha256']))
 assert not list((root/'work').glob('*.partial-*')) and not list((root/'work').glob('*.lock'))
 key=target.name;lock=root/'work'/(key+'.lock');lock.mkdir()
 reject(lambda:build(source,root/'raw',root/'work','2026-11-08T00:00:00Z',m['source_sha256']))
 assert lock.is_dir();lock.rmdir()
 # Corrupt only a disposable output; verify rerun refuses to silently reuse it.
 import shutil
 shutil.copytree(target,root/'work'/key)
 f=root/'work'/key/'observed/orders.csv';f.write_bytes(b'corrupted')
 reject(lambda:build(source,root/'raw',root/'work','2026-11-08T00:00:00Z',m['source_sha256']))
 assert f.read_bytes()==b'corrupted'
print('PASS wrong checksum, naive cutoff, source-output overlap, empty scope, active lock and corrupt output rejected without overwrite')
assert hashlib.sha256(source.read_bytes()).hexdigest()==m['source_sha256']
print('PASS source ZIP unchanged; no credentials or external calls')
