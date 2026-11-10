"""EDA-01 checks: key numbers and the wording claims in eda_initial.md, recomputed with pandas from DWD.
usage: .venv/bin/python evidence/EDA-01/verify_eda.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
from runtime import open_current  # noqa: E402

R = json.loads((ROOT / 'reports/analysis/eda_initial.json').read_text(encoding='utf-8'))
md = (ROOT / 'reports/analysis/eda_initial.md').read_text(encoding='utf-8')
con, ptr = open_current()
O = con.execute("""SELECT o.order_id, o.customer_id, o.purchase_ts::VARCHAR p, o.approved_ts::VARCHAR a, o.merch_usd::DOUBLE m,
                          o.late_by_days, o.review_score, c.customer_region FROM dwd.fact_order o JOIN dwd.dim_customer c USING (customer_id)""").df()
L = con.execute("SELECT l.order_id, l.item_price_usd::DOUBLE price, p.product_category cat FROM dwd.fact_order_line l JOIN dwd.dim_product p USING (product_id)").df()
con.close()
O['p'] = pd.to_datetime(O.p, utc=True)
O['a'] = pd.to_datetime(O.a, utc=True)
V = O[O.a < pd.Timestamp('2026-11-08', tz='UTC')].copy()
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


check('scope states synthetic and not live operations', '完全合成' in md and '不代表 2026 年实时经营' in md and R['release'] == ptr['version'])
mon = V.groupby(V.p.dt.strftime('%Y-%m')).size()
check('monthly valid orders equal pandas for all months', all(mon[m['month']] == m['valid_orders'] for m in R['monthly']))
cust = V.groupby('customer_id').m.sum().sort_values(ascending=False)
top10 = cust.iloc[:int(np.ceil(len(cust) * 0.1))].sum() / cust.sum()
check('top-10% customer share close to pandas (ntile vs ceil boundary)', abs(top10 - R['concentration']['top10pct_customers_share']) < 0.003, f'{top10:.4f}')
n = V.groupby('customer_id').size()
check('repeat share equals pandas', abs((n >= 2).mean() - R['customers']['repeat']['repeat_share']) < 1e-12, f'{(n >= 2).mean():.4f}')
g = V.sort_values('p').groupby('customer_id').p.diff().dt.total_seconds().dropna() / 86400
check('share of gaps within 30 days equals pandas', abs((g < 30).mean() - R['customers']['gap_days']['share_within_30d']) < 1e-12, f'{(g < 30).mean():.4f}')
first = V.groupby('customer_id').p.min()
check('new buyers by half-year sum to all buyers', sum(x['new_buyers'] for x in R['customers']['new_buyers_by_half_year']) == first.size == R['volume']['buyers'])
check('claim: mean order value above median (right skew)', V.m.mean() > V.m.median() and '平均值高于中位数' in md, f'{V.m.mean():.2f} > {V.m.median():.2f}')
lv = L[L.order_id.isin(V.order_id)]
share = lv.groupby('cat').price.sum() / lv.price.sum()
lines = lv.groupby('cat').size()
avg = lv.groupby('cat').price.mean()
check('claim: category shares differ mainly through average line amount (line counts similar)',
      lines.max() / lines.min() < 1.6 and avg.max() / avg.min() > 5 and f'{share.max():.1%}' in md and f'{share.min():.1%}' in md,
      f'lines {lines.min()}..{lines.max()}, avg {avg.min():.1f}..{avg.max():.1f}, share {share.min():.3f}..{share.max():.3f}')
rb = V.groupby('customer_region').customer_id.nunique()
aov = V.groupby('customer_region').m.mean()
check('claim: region differences come mainly from buyer counts (AOV similar)', aov.max() / aov.min() < 1.15 and rb.max() / rb.min() > 1.5,
      f'aov {aov.min():.1f}..{aov.max():.1f}, buyers {rb.min()}..{rb.max()}')
d = V[V.review_score.notna() & V.late_by_days.notna()]
s = d.groupby('late_by_days').review_score.mean()
rep = {x['late_by_days']: x['avg_score'] for x in R['delivery_review']['score_by_late']}
check('review score by lateness equals pandas', all(abs(s[k] - rep[k]) < 1e-9 for k in s.index), s.round(3).to_dict())
check('association wording, not causation', '相关，不是因果' in md)
reg = V.groupby('customer_region').m.sum()
check('region merchandise equals pandas', all(abs(reg[x['customer_region']] - x['merch_usd']) < 1e-6 for x in R['region']))
check('closed-population caveat for new buyers stated', '合成人口封闭' in md and '不能解读为获客能力下降' in md)
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
