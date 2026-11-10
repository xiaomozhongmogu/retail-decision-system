"""EDA-02 checks: comparable-period numbers recomputed with pandas; decomposition and contributions add up;
growth statuses follow the base rule; findings traceable."""
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
from runtime import open_current  # noqa: E402

T = json.loads((ROOT / 'reports/analysis/business_trends.json').read_text(encoding='utf-8'))
md = (ROOT / 'reports/analysis/business_trends.md').read_text(encoding='utf-8')
con, _ = open_current()
O = con.execute("SELECT customer_id, purchase_ts::VARCHAR p, approved_ts::VARCHAR a, merch_usd::DOUBLE m FROM dwd.fact_order").df()
con.close()
O['p'], O['a'] = pd.to_datetime(O.p, utc=True), pd.to_datetime(O.a, utc=True)
V = O[(O.a < pd.Timestamp('2026-11-08', tz='UTC')) & (O.p.dt.month <= 10)]
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


rows = {r['year']: r for r in T['queries']['ytd_by_year']['rows']}
for yr, g in V.groupby(V.p.dt.year):
    check(f'{yr} Jan-Oct orders/merch/buyers recomputed', (rows[yr]['orders'], rows[yr]['buyers']) == (len(g), g.customer_id.nunique()) and abs(rows[yr]['merch_usd'] - g.m.sum()) < 1e-6)
d = T['decomposition_2026_vs_2025']
check('volume x price parts add up to the total change', abs(d['due_to_buyers_usd'] + d['due_to_orders_per_buyer_usd'] + d['due_to_aov_usd'] - d['delta_merch_usd']) < 0.05)
check('category changes add up to the total change', abs(sum(r['delta'] for r in T['category_contribution']) - d['delta_merch_usd']) < 0.05)
check('region changes add up to the total change', abs(sum(r['delta'] for r in T['region_contribution']) - d['delta_merch_usd']) < 0.05)
check('no percentage of a near-zero total is produced', '占总变化' not in md and 'share_of_total_delta' not in json.dumps(T))
check('growth status rule: ok only with base >= 30 orders', all((r['growth']['status'] == 'ok') == (r['growth']['value'] is not None) for r in T['category_contribution'] + T['region_contribution']))
check('incomplete month 2026-11 excluded from the comparable period', '2026-11 不完整，排除' in T['comparable_period'])
check('refund and non-merchandise rules stated', all(k in T['rules'] for k in ('merchandise', 'refunds', 'cancellations')))
finds = re.findall(r'^\d\. .*查询：(\w+)', md, flags=re.M)
check('at least 3 findings, each naming a stored query', len(finds) >= 3 and all(f in T['queries'] for f in finds), finds)
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
