"""AI-08 verification: live facts vs an independent SQL recompute on DWD, envelope fields, exact splits,
same metric definition as the business page, fixture boundaries, and no LLM in the computation.
usage: .venv/bin/python evidence/AI-08/verify_facts.py"""
import json
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/ai'))
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
import report_facts as RF  # noqa: E402
from runtime import open_current  # noqa: E402

ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


out = RF.build_weekly_facts()
out2 = RF.build_weekly_facts()
F = {f['metric']: f for f in out['data']['facts']}
check('live run ok, mode live, computed by code', out['status'] == 'ok' and out['mode'] == 'live' and out['computed_by'].startswith('deterministic'))
check('deterministic: two runs identical', json.dumps(out, sort_keys=True) == json.dumps(out2, sort_keys=True))
need = ('evidence_id', 'unit', 'window', 'status', 'query', 'dataset_version', 'metric_version', 'sample_size')
check('every fact has evidence_id, unit, window, status, query, versions, sample size',
      all(all(k in f for k in need) and f['query']['sql_id'].startswith('sql:') and f['window']['closed'] == 'left' for f in F.values()), len(F))
check('evidence ids unique', len({f['evidence_id'] for f in F.values()}) == len(F))
check('null values always carry a non-ok status', all(f['status'] != 'ok' for f in F.values() if f['value'] is None))

# independent recompute straight from DWD (read-only), not through the ADS views
con, ptr = open_current()
V = "o.approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'"
def q(sql): return con.execute(sql).fetchall()
w = out['data']['periods']['report_week']
o, s = q(f"SELECT count(*), sum(merch_usd) FROM dwd.fact_order o WHERE {V} AND CAST(purchase_ts AS DATE) >= DATE '{w['start']}' AND CAST(purchase_ts AS DATE) < DATE '{w['end']}'")[0]
check('report week orders and sales equal an independent DWD recompute', F['report_week.orders']['value'] == o and F['report_week.sales']['value'] == float(s), (o, float(s)))
p = out['data']['periods']['previous_week']
o2, s2 = q(f"SELECT count(*), sum(merch_usd) FROM dwd.fact_order o WHERE {V} AND CAST(purchase_ts AS DATE) >= DATE '{p['start']}' AND CAST(purchase_ts AS DATE) < DATE '{p['end']}'")[0]
check('previous week and week-on-week change equal the recompute', F['previous_week.orders']['value'] == o2 and
      F['change_vs_previous_week.sales']['value'] == round(float(s - s2) / float(s2), 4), (o2, float(s2)))
mo, mb, ms = q(f"SELECT count(*), count(DISTINCT customer_id), sum(merch_usd) FROM dwd.fact_order o WHERE {V} AND strftime(purchase_ts, '%Y-%m') = '2026-10'")[0]
check('report month orders, distinct buyers, sales equal the recompute', (F['report_month.orders']['value'], F['report_month.buyers']['value'], F['report_month.sales']['value']) == (mo, mb, float(ms)))
cat = dict(q(f"""SELECT p.product_category, sum(CASE WHEN strftime(o.purchase_ts,'%Y-%m')='2026-10' THEN l.item_price_usd ELSE 0 END)
  - sum(CASE WHEN strftime(o.purchase_ts,'%Y-%m')='2026-09' THEN l.item_price_usd ELSE 0 END) FROM dwd.fact_order_line l
  JOIN dwd.fact_order o USING (order_id) JOIN dwd.dim_product p USING (product_id) WHERE {V} GROUP BY 1"""))
parts = {x['key']: x['change'] for x in F['month_contribution_vs_previous_month.product_category']['value']}
check('category contributions equal the recompute', all(abs(parts[k] - float(v)) < 0.005 for k, v in cat.items()) and set(parts) == set(cat))
tail = q(f"SELECT count(*) FROM dwd.fact_order o WHERE {V} AND CAST(purchase_ts AS DATE) = DATE '2026-11-07'")[0][0]
pend = q("SELECT count(*) FROM dwd.fact_order WHERE CAST(purchase_ts AS DATE) = DATE '2026-11-07' AND approved_ts >= TIMESTAMPTZ '2026-11-08 00:00:00+00'")[0][0]
check('open tail day reported separately as partial_period (orders still awaiting approval)', F['open_tail.orders']['status'] == 'partial_period' and F['open_tail.orders']['value'] == tail and pend > 0, f'valid {tail}, approved after cutoff {pend}')
con.close()

# exact splits
for k in ('split_vs_previous_week', 'split_vs_same_week_last_year', 'month_split_vs_previous_month', 'month_split_vs_same_month_last_year'):
    f = F[k]
    check(f'{k}: parts add up to the total change exactly', abs(sum(f['value'].values()) - f['total_change']) < 0.005, (f['value'], f['total_change']))
for k in ('month_contribution_vs_previous_month.product_category', 'month_contribution_vs_previous_month.customer_region',
          'month_contribution_vs_same_month_last_year.product_category', 'month_contribution_vs_same_month_last_year.customer_region'):
    base = k.split('.')[0].replace('month_contribution', 'month_split')
    check(f'{k}: contributions sum to the month change', abs(F[k]['sum_of_changes'] - F[base]['total_change']) < 0.005)

# same metric definition as the business page (it shows ads.kpi_monthly)
import report_facts  # noqa: E402,F401
from runtime import query_view  # noqa: E402
m = {r[0]: r for r in query_view('ads.kpi_monthly', ['month', 'valid_orders', 'merchandise_sales_usd'])['rows']}
d = [r for r in query_view('ads.kpi_daily', ['day', 'valid_orders', 'merchandise_sales_usd'])['rows'] if r[0].startswith('2026-10')]
check('kpi_daily summed over 2026-10 equals kpi_monthly 2026-10 shown on the business page',
      sum(int(r[1]) for r in d) == int(m['2026-10'][1]) and sum(Decimal(r[2]) for r in d) == Decimal(m['2026-10'][2]) == Decimal(str(F['report_month.sales']['value'])))
check('report month is the latest complete month (2026-11 partial is not used)', out['data']['periods']['report_month']['start'] == '2026-10-01'
      and any(x['code'] == 'partial_period' and '2026-11' in x['message'] for x in out['warnings']))

# no LLM in the fact computation
src = (ROOT / 'src/retail_bi/ai/report_facts.py').read_text(encoding='utf-8')
check('fact module does not import the LLM client', 'import client' not in src and 'from client' not in src and 'LLMClient' not in src)

# ---------- fixtures ----------
def day_rows(start, end, orders_fn, sales_per_order='100.00'):
    rows, x = [], start
    while x < end:
        n = orders_fn(x)
        if n:
            rows.append({'day': x.isoformat(), 'valid_orders': str(n), 'merchandise_sales_usd': str(Decimal(sales_per_order) * n), 'shipping_usd': str(n * 10)})
        x += timedelta(days=1)
    return rows
A = date(2026, 11, 8)
# (a) previous week has zero orders
rows = day_rows(date(2024, 1, 1), A, lambda x: 0 if date(2026, 10, 24) <= x < date(2026, 10, 31) else 10)
r = RF.compute(rows, [], [], [], [], as_of=A)
G = {f['metric']: f for f in r['facts']}
check('fixture zero base week: aov and change get zero_denominator, value null', G['previous_week.aov']['status'] == 'zero_denominator' and G['previous_week.aov']['value'] is None
      and G['change_vs_previous_week.sales']['status'] == 'zero_denominator' and G['split_vs_previous_week']['status'] == 'zero_denominator')
# (b) data start 100 days before as_of -> last-year windows incomplete
rows = day_rows(A - timedelta(days=100), A, lambda x: 10)
mon = [{'month': '2026-10', 'valid_orders': '310', 'merchandise_sales_usd': '31000.00', 'buyers': '300', 'aov_usd': '100', 'partial_period': 'False'},
       {'month': '2026-09', 'valid_orders': '300', 'merchandise_sales_usd': '30000.00', 'buyers': '290', 'aov_usd': '100', 'partial_period': 'False'}]
r = RF.compute(rows, mon, [], [], [], as_of=A)
G = {f['metric']: f for f in r['facts']}
check('fixture short history: same-week-last-year and its change are incomplete_period',
      G['same_week_last_year.sales']['status'] == 'incomplete_period' and G['change_vs_same_week_last_year.sales']['status'] == 'incomplete_period')
check('fixture short history: same-month-last-year split is incomplete_period, previous month split ok',
      G['month_split_vs_same_month_last_year']['status'] == 'incomplete_period' and G['month_split_vs_previous_month']['status'] == 'ok')
# (c) small base
rows = day_rows(date(2024, 1, 1), A, lambda x: 2)
r = RF.compute(rows, [], [], [], [], as_of=A)
G = {f['metric']: f for f in r['facts']}
check('fixture small base (14 orders < 30): growth withheld as small_sample', G['change_vs_previous_week.sales']['status'] == 'small_sample' and G['change_vs_previous_week.sales']['value'] is None)
# (d) tail-day drop flagged as candidate with the approval explanation, not as a business change
rows = day_rows(date(2024, 1, 1), A, lambda x: 1 if x == date(2026, 11, 7) else (10 + x.day % 3))
r = RF.compute(rows, [], [], [], [], as_of=A)
c = [x for x in r['anomaly_candidates'] if x.get('day') == '2026-11-07']
check('fixture tail-day drop: candidate notes pending approval', c and '尚未全部审批' in c[0]['note'], c[:1])
# (e) a spike day inside the report week is a daily candidate
rows = day_rows(date(2024, 1, 1), A, lambda x: 60 if x == date(2026, 11, 3) else (10 + x.day % 3))
r = RF.compute(rows, [], [], [], [], as_of=A)
check('fixture spike day: daily candidate raised', any(x.get('day') == '2026-11-03' and x['type'] == 'daily' for x in r['anomaly_candidates']))
print(f'{sum(ok)}/{len(ok)} checks passed')
sys.exit(0 if all(ok) else 1)
