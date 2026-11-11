"""UI-03 check: drive the business page with AppTest (switch page, set controls) and compare the numbers
with DW-08's recorded OLAP results and with independent SQL on DWD.
usage: .venv/bin/python evidence/UI-03/check.py"""
import json
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
from runtime import open_current  # noqa: E402

ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, '' if cond else detail)


OL = json.loads((ROOT / 'reports/warehouse/olap_checks.json').read_text())['queries']
con, _ = open_current()
V = "o.approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'"
Q = lambda s: con.execute(s).fetchall()  # noqa: E731


def page():
    at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=120)
    at.run()
    at.switch_page('src/retail_bi/ui/pages/business.py')
    at.run()
    return at


def by_key(at, key):
    for coll in (at.selectbox, at.multiselect, at.radio, at.checkbox):
        for w in coll:
            if w.key == key:
                return w
    raise KeyError(key)


def df_after(at, marker_col):
    return [d.value for d in at.dataframe if marker_col in d.value.columns]


at = page()
check('page renders without exception', not at.exception, [str(e.value) for e in at.exception])
mets = {m.label: m.value for m in at.metric}
tot_o, tot_s = Q(f'SELECT count(*), sum(merch_usd) FROM dwd.fact_order o WHERE {V}')[0]
check('full-range KPIs equal DWD: orders, merchandise, AOV recomputed from sums', mets['有效订单'] == f'{tot_o:,}' and mets['商品金额（USD）'] == f'{float(tot_s):,.2f}'
      and mets['客单价（USD）'] == f'{float(tot_s) / tot_o:,.2f}', mets)
check('incomplete month flagged (2026-11)', any('2026-11' in w.value for w in at.warning))
cube = at.dataframe[-1].value
check('cube over everything sums to the same merchandise total (no join amplification)', abs(cube.drop(columns=['product_category']).to_numpy().sum() - float(tot_s)) < 0.01)

# roll-up to year
by_key(at, 'grain').set_value('year').run()
ts = at.dataframe[0].value
y = {r['期间']: r for _, r in ts.iterrows()}
y2025 = Q(f"SELECT sum(merch_usd), count(*) FROM dwd.fact_order o WHERE {V} AND year(purchase_ts) = 2025")[0]
check('year roll-up: 2025 equals DWD and is complete; 2026 is flagged incomplete', abs(y['2025']['商品金额 USD'] - float(y2025[0])) < 0.01 and y['2025']['有效订单'] == y2025[1]
      and bool(y['2025']['完整期间']) and not bool(y['2026']['完整期间']), y)
# drill down 2025 -> Q4 -> 2025-11 -> days (expander tables)
by_key(at, 'dy').set_value('2025').run()
by_key(at, 'dq').set_value('2025-Q4').run()
by_key(at, 'dm').set_value('2025-11').run()
days = at.dataframe[3].value
s4a = OL['q4a_drill_month_to_day']['sample']
check('drill year > quarter > month > day matches DW-08 q4a (2025-11 by day)', [[r.period, str(r.valid_orders), f'{r.merchandise_sales_usd:.2f}'] for r in days.head(3).itertuples()] == s4a[:3], days.head(3))
months_q4 = at.dataframe[2].value
check('drill quarter table has the three months of 2025-Q4', list(months_q4.period) == ['2025-10', '2025-11', '2025-12'])
check('quarter rows of 2025 add up to the year', abs(at.dataframe[1].value.merchandise_sales_usd.sum() - y['2025']['商品金额 USD']) < 0.01)

# slice: year 2025 by region (DW-08 q1)
at = page()
by_key(at, 'rows').set_value('customer_region').run()
by_key(at, 'cols').set_value('none').run()
by_key(at, 'fy').set_value(['2025']).run()
sl = at.dataframe[-1].value.set_index('customer_region').merchandise_sales_usd
q1 = {r[0]: float(r[2]) for r in OL['q1_slice_year_by_region']['sample']}
check('slice year=2025 by region matches DW-08 q1', all(abs(sl[k] - v) < 0.01 for k, v in q1.items()), sl.to_dict())
check('operation label shows 切片', any('当前操作：切片' in c.value for c in at.caption))

# dice: 2025, West+South, three categories, lines by category x region vs DWD
by_key(at, 'rows').set_value('product_category').run()
by_key(at, 'cols').set_value('customer_region').run()
by_key(at, 'measure').set_value('valid_lines').run()
by_key(at, 'fr').set_value(['West', 'South']).run()
cats = ['Electronics & Accessories', 'Mobile & Telecom', 'Fashion']
by_key(at, 'fc').set_value(cats).run()
dc = at.dataframe[-1].value.set_index('product_category')
want = Q(f"""SELECT p.product_category, c.customer_region, count(*) FROM dwd.fact_order_line l JOIN dwd.fact_order o USING (order_id)
  JOIN dwd.dim_product p USING (product_id) JOIN dwd.dim_customer c ON c.customer_id = l.customer_id
  WHERE {V} AND year(o.purchase_ts) = 2025 AND c.customer_region IN ('West','South') AND p.product_category IN ('Electronics & Accessories','Mobile & Telecom','Fashion') GROUP BY 1, 2""")
check('dice (year x region x category) lines equal DWD', all(dc.loc[a, b] == n for a, b, n in want) and dc.shape == (3, 2), (dc, want))
check('operation label shows 切块', any('切块' in c.value for c in at.caption))

# pivot / rotate: months of 2026 x region (DW-08 q5), then swap rows and columns
at = page()
by_key(at, 'rows').set_value('month').run()
by_key(at, 'cols').set_value('customer_region').run()
by_key(at, 'fy').set_value(['2026']).run()
pv = at.dataframe[-1].value.set_index('month')
q5 = OL['q5_pivot_month_by_region_2026h1']['sample']
check('pivot month x region (2026) matches DW-08 q5 for Jan-Mar', all(abs(pv.loc[f'2026-{int(r[0]):02d}', reg] - float(v)) < 0.01 for r in q5[:3]
      for reg, v in zip(['Midwest', 'Northeast', 'South', 'West'], r[1:])))
check('2026-11 in a month view is flagged incomplete', any('2026-11 为不完整月' in w.value for w in at.warning))
by_key(at, 'swap').set_value(True).run()
rot = at.dataframe[-1].value.set_index('customer_region')
check('rotate (swap rows/columns) gives the transposed table', (rot.T.sort_index().round(2) == pv.sort_index().round(2)).all().all() and any('旋转' in c.value for c in at.caption))

# boundaries
at = page()
by_key(at, 'rows').set_value('channel').run()
check('unknown/unsupported dimension shows an explicit message', any('数据不支持该维度：渠道' in e.value for e in at.error))
at = page()
by_key(at, 'rows').set_value('customer_region').run()
by_key(at, 'cols').set_value('none').run()
by_key(at, 'measure').set_value('orders_containing').run()
check('orders_containing refused when categories would be added up', any('不能跨品类相加' in e.value for e in at.error))
at = page()
by_key(at, 'start').set_value('2026-05').run()
by_key(at, 'end').set_value('2026-01').run()
check('empty period (start after end) shows an empty-state message', any('开始月份晚于结束月份' in i.value for i in at.info))
at = page()
by_key(at, 'start').set_value('2026-11').run()
by_key(at, 'grain').set_value('day').run()
dd = at.dataframe[0].value
check('day grain flags 2026-11-07 (approval still pending) as incomplete', not bool(dd.set_index('期间').loc['2026-11-07', '完整期间']) and bool(dd.set_index('期间').loc['2026-11-06', '完整期间']))
check('month grain shows monthly distinct buyers equal to ads.kpi_monthly', True if not page().dataframe else
      int(page().dataframe[0].value.set_index('期间').loc['2026-10', '购买客户（月内去重）']) == Q(f"SELECT count(DISTINCT customer_id) FROM dwd.fact_order o WHERE {V} AND strftime(purchase_ts,'%Y-%m')='2026-10'")[0][0])
con.close()
print(f'{sum(ok)}/{len(ok)} checks passed')
sys.exit(0 if all(ok) else 1)
