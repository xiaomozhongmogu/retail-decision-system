"""DATA-09 independent checks with pandas merge(validate=...).
usage: .venv/bin/python evidence/DATA-09/verify_integration.py
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
A = json.loads((ROOT / 'reports/data/integration_audit.json').read_text(encoding='utf-8'))
clean = next((ROOT / 'data/processed/clean').glob('*-clean-v2'))
integ = ROOT / 'data/processed/integrated' / A['key']
T = {t: pd.read_parquet(clean / f'{t}.parquet') for t in ['orders', 'order_items', 'payments', 'products', 'sellers', 'seller_products', 'shipping', 'reviews', 'customers']}
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


def dsum(s):
    return sum((Decimal(str(x)) for x in s), Decimal(0))


it = T['order_items']
base_rows, base_amt = len(it), dsum(it.item_price_usd)
df = it
for t, k, how in [('orders', 'order_id', 'inner'), ('products', 'product_id', 'inner'), ('sellers', 'seller_id', 'inner'),
                  ('seller_products', 'seller_product_id', 'inner'), ('shipping', 'order_id', 'inner'), ('reviews', 'order_id', 'left')]:
    right = T[t][[k] + [c for c in T[t].columns if c not in df.columns]]
    df = df.merge(right, on=k, how=how, validate='many_to_one')   # raises if the right side is not unique
    check(f'join {t}: many-to-one validated, rows and amount unchanged', len(df) == base_rows and dsum(df.item_price_usd) == base_amt)
lines = pd.read_parquet(integ / 'order_lines.parquet')
orders = pd.read_parquet(integ / 'orders.parquet')
check('integrated order_lines rows/amount = items', len(lines) == base_rows and dsum(lines.item_price_usd) == base_amt)
check('integrated orders rows = orders, merch = items', len(orders) == len(T['orders']) and dsum(orders.merch_usd) == base_amt)
check('integrated orders payment = order value (exact)', all(Decimal(str(a)) == Decimal(str(b)) for a, b in zip(orders.payment_value_usd, orders.order_value_usd)))
naive = it.merge(T['payments'], on='order_id')
check('naive payments join inflates as reported', len(naive) - base_rows == A['order_level']['naive_items_join_payments']['inflated_rows']
      and dsum(naive.item_price_usd) - base_amt == Decimal(A['order_level']['naive_items_join_payments']['inflated_merch_usd']))
check('review coverage as reported', round(it.order_id.isin(T['reviews'].order_id).mean(), 6) == next(j['coverage'] for j in A['joins'] if ' reviews ' in j['join']))
check('every order line customer in master', lines.customer_id.isin(T['customers'].customer_id).all())
check('audit all checks true', A['all_checks_passed'])
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
