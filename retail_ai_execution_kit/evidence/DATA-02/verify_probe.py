"""Independent CSV/Decimal/date controls and failure-path checks for DATA-02."""
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

root=Path(__file__).resolve().parents[2]
source=root.parent/'ecommerce-sample-database-100k'
report=json.loads((root/'reports/data/candidate_probe.json').read_text())

def rows(blob):return list(csv.DictReader(io.StringIO(blob.decode('utf-8-sig'))))
with zipfile.ZipFile(source/'01_source/baseline_10000_seed42.zip') as z:
    raw={Path(n).stem:rows(z.read(n)) for n in z.namelist() if n.endswith('.csv') and not n.startswith('__MACOSX/')}
hist={p.stem:rows(p.read_bytes()) for p in (source/'02_historical_utf8').glob('*.csv')}
for name,r in raw.items():assert len(r)==report['profiles']['raw:'+name]['rows']
for name,r in hist.items():assert len(r)==report['profiles']['historical:'+name]['rows']
assert sum(map(len,hist.values()))==77916
cutoff=datetime(2026,11,8)
ids={r['order_id'] for r in raw['orders'] if datetime.fromisoformat(r['order_purchase_timestamp'])<cutoff}
assert len(ids)==9311 and len(raw['orders'])-len(ids)==689
for name in ('orders','order_items','payments','shipping','reviews'):
    expected=[r for r in raw[name] if r['order_id'] in ids]
    assert Counter(tuple(sorted(r.items())) for r in expected)==Counter(tuple(sorted(r.items())) for r in hist[name]),name
for table,key,col,count in [('customers','customer_id','customer_zip_prefix',334),('sellers','seller_id','seller_zip_prefix',75)]:
    a={r[key]:r for r in raw[table]};changed=[(a[r[key]][col],r[col]) for r in hist[table] if a[r[key]][col]!=r[col]]
    assert len(changed)==count
    assert all(x.startswith('0') and x.lstrip('0')==y.lstrip('0') for x,y in changed)
    assert report['historical_source_differences'][table][col]['changed_rows']==count
for dataset in (raw,hist):
    totals=defaultdict(Decimal);paid=defaultdict(Decimal)
    for row in dataset['order_items']:
        assert Decimal(row['item_price_usd'])+Decimal(row['shipping_cost_usd'])==Decimal(row['item_total_usd'])
        totals[row['order_id']]+=Decimal(row['item_total_usd'])
    for row in dataset['payments']:paid[row['order_id']]+=Decimal(row['payment_value_usd'])
    assert totals==paid
assert 'quantity' not in raw['order_items'][0]
assert report['assertions']['history_matches_declared_order_cutoff'] is False
assert report['assertions']['source_unchanged'] is True
print('PASS independent counts, cutoff, fact-table equality, postal-loss detection, exact Decimal reconciliation, quantity absence')
for table in ('orders','reviews'):
    for col in hist[table][0]:
        if not any(x['name']==col and x['declared_type'] in ('date','datetime') for x in report['profiles']['historical:'+table]['columns']):continue
        future=sum(bool(r[col]) and datetime.fromisoformat(r[col])>=cutoff for r in hist[table])
        measured=next(x['at_or_after_cutoff'] for x in report['profiles']['historical:'+table]['columns'] if x['name']==col)
        assert future==measured
print('PASS independent post-cutoff date controls')
spec=importlib.util.spec_from_file_location('probe',root/'src/retail_bi/data/candidate_probe.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
df,_=module.read_csv(b'id,when,price\n001,bad,1.23\n')
profile=module.profile(df,b'test','fixture',{'when':{'data_type':'datetime'},'price':{'data_type':'float'}})
assert df.id.iloc[0]=='001'
assert next(c for c in profile['columns'] if c['name']=='when')['invalid_declared_type_count']==1
print('PASS identifier preservation and invalid datetime detection (fixture only)')
with tempfile.TemporaryDirectory() as temp:
    command=[sys.executable,str(root/'src/retail_bi/data/candidate_probe.py'),'--source',str(source),'--out',temp,'--strict']
    run=subprocess.run(command,capture_output=True,text=True)
    assert run.returncode==1,run.stderr
    strict=json.loads((Path(temp)/'candidate_probe.json').read_text())
    assert strict['assertions']['history_matches_declared_order_cutoff'] is False
    missing=subprocess.run(command[:3]+[str(Path(temp)/'missing'),'--out',temp],capture_output=True,text=True)
    assert missing.returncode!=0
    inside=subprocess.run(command[:4]+['--out',str(source/'should-not-exist')],capture_output=True,text=True)
    assert inside.returncode!=0 and not (source/'should-not-exist').exists()
print('PASS strict detects real data issues; missing input fails; source-directory writes rejected')
