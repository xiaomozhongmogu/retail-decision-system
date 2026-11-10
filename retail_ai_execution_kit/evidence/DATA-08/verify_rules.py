"""DATA-08 independent checks (pandas, not the DuckDB rule SQL).
usage: .venv/bin/python evidence/DATA-08/verify_rules.py
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/data'))
from transactions import METRIC_SQL  # noqa: E402

R = json.loads((ROOT / 'reports/data/transaction_reconciliation.json').read_text(encoding='utf-8'))
M = json.loads((ROOT / 'contracts/metrics.json').read_text(encoding='utf-8'))
doc = (ROOT / 'docs/transaction_rules.md').read_text(encoding='utf-8')
clean = next((ROOT / 'data/processed/clean').glob('*-clean-v1'))
o = pd.read_parquet(clean / 'orders.parquet')
it = pd.read_parquet(clean / 'order_items.parquet')
pay = pd.read_parquet(clean / 'payments.parquet')
cut = pd.Timestamp('2026-11-08', tz='UTC')
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


def n(x):
    return f'{x:,}'


amt = it.groupby('order_id').agg(merch=('item_price_usd', 'sum'), ship=('item_shipping_usd', 'sum'),
                                 total=('item_total_usd', 'sum'), lines=('order_id', 'size')).reset_index()
a = o.merge(amt, on='order_id')
valid = a[a.approved_ts.notna() & (a.approved_ts < cut)]
canc = a[a.approved_ts.isna()]
pend = a[a.approved_ts.notna() & (a.approved_ts >= cut)]
for label, df, key in [('valid', valid, 'valid_orders_at_cutoff'), ('cancelled', canc, 'cancelled_orders'), ('pending', pend, 'pending_approval_at_cutoff')]:
    r = R[key]
    check(f'{label} recount', len(df) == r['orders'] and int(df.lines.sum()) == r['item_lines']
          and Decimal(str(sum(df.merch))) == Decimal(r['merch_usd']) and Decimal(str(sum(df.ship))) == Decimal(r['shipping_usd']),
          f'{len(df)} orders')
    check(f'{label} row quoted in docs', n(r['orders']) in doc and n(Decimal(r['merch_usd'])) in doc)
check('valid + cancelled + pending = all', len(valid) + len(canc) + len(pend) == len(o))
check('approval == not cancelled (pandas)', ((o.approved_ts.notna()) == (o.order_status != 'cancelled')).all())
check('approval lag <= 24h', ((o.approved_ts - o.purchase_ts).dt.total_seconds().max() / 3600) <= 24)
check('all reconciliation checks true', R['all_checks_passed'] and all(R['checks'].values()))
check('payments total = order value', Decimal(str(sum(pay.payment_value_usd))) == Decimal(R['raw_all_orders']['order_value_usd']))
q3 = valid[(valid.purchase_ts >= pd.Timestamp('2026-07-01', tz='UTC')) & (valid.purchase_ts < pd.Timestamp('2026-10-01', tz='UTC'))]
ex = R['metric_examples']['2026-Q3 (complete period)']
check('Q3 orders/sales/buyers recount', len(q3) == ex['valid_orders'] and Decimal(str(sum(q3.merch))) == Decimal(ex['merchandise_sales_usd'])
      and q3.customer_id.nunique() == ex['buyers'])
seen = a[a.approved_ts.notna() & (a.approved_ts < pd.Timestamp('2026-11-05', tz='UTC')) & (a.purchase_ts >= pd.Timestamp('2026-11-01', tz='UTC'))]
check('observability example recount (as_of 2026-11-05)', len(seen) == R['metric_examples']['2026-11-01..cutoff seen at 2026-11-05 (observability)']['valid_orders'], str(len(seen)))
check('doc quotes Q3 and full-history examples', all(s in doc for s in ['| 734 |', '112,870.30', '| 663 |', '153.77', '151.45', '| 3,339 |']))
check('metrics.json SQL identical to rule module', all(x.get('sql') == METRIC_SQL[x['id']] for x in M['metrics'] if x['id'] in METRIC_SQL))
req = M['required_for_approval']
check('every SQL metric has all approval fields', all(all(k in x for k in req) for x in M['metrics'] if x['id'] in METRIC_SQL))
check('no GBP / UCI semantics left in metrics', 'GBP' not in json.dumps(M['metrics']) and 'invoice' not in json.dumps(M['metrics']))
check('forbidden names listed', all(w in M['forbidden_names'] for w in ['已支付 GMV', '净收入', '退款金额']))
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
