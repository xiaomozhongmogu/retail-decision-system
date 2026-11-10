"""Independent pandas recount of key numbers in reports/data/profile_before.json.
usage: .venv/bin/python evidence/DATA-06/verify_profile.py
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
L = ROOT / 'data/processed/engineering/d50ee64a0478d8ae-20261108T000000Z-engineering-import-v1/history_source'
P = json.loads((ROOT / 'reports/data/profile_before.json').read_text(encoding='utf-8'))
md = (ROOT / 'reports/data/profile_before.md').read_text(encoding='utf-8')
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


T = {t: pd.read_csv(L / f'{t}.csv', dtype=str, keep_default_na=False, encoding='utf-8-sig')
     for t in ['customers', 'sellers', 'products', 'seller_products', 'orders', 'order_items', 'payments', 'shipping', 'reviews', 'calendar']}
o, it = T['orders'], T['order_items']

check('volume', all(P['volume'][t] == len(df) for t, df in T.items()))
check('customers with orders', P['entities']['customers_with_orders'] == o.customer_id.nunique())
check('products sold', P['entities']['products_sold'] == it.product_id.nunique())
miss = {f'{t}.{c}': int((df[c] == '').sum()) for t, df in T.items() for c in df.columns if (df[c] == '').any()}
check('missing counts', miss == {k: v['nulls'] for k, v in P['missing'].items()}, str(miss))
check('no exact duplicate rows', all(not df.duplicated().any() for df in T.values())
      and all(v == 0 for k, v in P['duplicates'].items() if k.startswith('exact_')))
check('same product repeated rows', P['duplicates']['order_items_same_product_repeated_in_order']
      == int(it.duplicated(['order_id', 'product_id']).sum()))
check('status counts', P['cancellation_and_negatives']['status_counts'] == o.order_status.value_counts().to_dict())
for t, c in [('order_items', 'item_price_usd'), ('payments', 'payment_value_usd')]:
    v = pd.to_numeric(T[t][c])
    m = P['money'][f'{t}.{c}']
    check(f'{t}.{c} negatives/zeros/max', m['negative'] == int((v < 0).sum()) and m['zero'] == int((v == 0).sum())
          and abs(float(m['quantiles']['p100']) - v.max()) < 1e-9)

d = o[o.order_delivered_customer_date != ''].merge(T['shipping'], on='order_id')
late_by_date = (pd.to_datetime(d.order_delivered_customer_date).dt.normalize() > pd.to_datetime(d.order_estimated_delivery_date)) & (d.late_delivery_flag == 'False')
check('late-by-date-not-flagged', P['validity']['counts']['delivered after estimated DATE but late_flag False'] == int(late_by_date.sum()), str(int(late_by_date.sum())))

# 30-day positives over weekly snapshots, provisional rule (not cancelled)
b = o[o.order_status != 'cancelled'][['customer_id', 'order_purchase_timestamp']].copy()
b['t'] = pd.to_datetime(b.order_purchase_timestamp)
cutoff = pd.Timestamp('2026-11-08')
rows = pos = 0
t = pd.Timestamp('2024-04-01')
while t + pd.Timedelta(days=30) <= cutoff:
    pop = set(b[(b.t >= t - pd.Timedelta(days=90)) & (b.t < t)].customer_id)
    fut = set(b[(b.t >= t) & (b.t < t + pd.Timedelta(days=30))].customer_id)
    rows += len(pop)
    pos += len(pop & fut)
    t += pd.Timedelta(days=7)
p30 = P['customer_coverage']['positive_class_potential']['30d']
check('30d snapshot rows and positives', p30['customer_snapshot_rows'] == rows and p30['positive_rows'] == pos, f'{rows} {pos}')
check('report quotes the 30d numbers', f'{rows:,}' in md and f'{pos:,}' in md)
check('no zip/city in report samples', 'zip' not in json.dumps(P['duplicate_samples']) and 'customer_city' not in md)
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
