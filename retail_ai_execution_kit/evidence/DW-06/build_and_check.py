"""DW-06: create ADS views + allowed-view list, add grain/ADS mapping to contracts/metrics.json,
and check metric samples against hand calculation / independent implementations.
usage: .venv/bin/python evidence/DW-06/build_and_check.py
writes reports/warehouse/metric_checks.json and updates contracts/metrics.json (ads fields only)
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
sys.path.insert(0, str(ROOT / 'src/retail_bi/data'))
from db import connect, sql_blocks  # noqa: E402
from transactions import connect as rules_connect, metric  # noqa: E402

DB = ROOT / 'warehouse/build/dev.duckdb'
S = sql_blocks(ROOT / 'sql/ads.sql')
con = connect(DB)
con.execute('BEGIN TRANSACTION')
con.execute(S['views'])
con.execute(S['allowed'])
con.execute('COMMIT')
allowed = con.execute(S['list']).fetchall()
ok, results = [], []


def check(name, cond, expected, got):
    ok.append(bool(cond))
    results.append({'check': name, 'status': 'passed' if cond else 'failed', 'expected': str(expected), 'got': str(got)})
    print('PASS' if cond else 'FAIL', name, '| expected', expected, '| got', got)


# ---- independent data (pandas) straight from DWD facts
O = con.execute("SELECT order_id, customer_id, purchase_ts::VARCHAR p, approved_ts::VARCHAR a, merch_usd::VARCHAR m FROM dwd.fact_order").df()
O['p'] = pd.to_datetime(O.p, utc=True)
O['a'] = pd.to_datetime(O.a, utc=True)
O['m'] = O.m.map(Decimal)
cut = pd.Timestamp('2026-11-08', tz='UTC')
V = O[O.a < cut].copy()
V['month'] = V.p.dt.strftime('%Y-%m')

# 1. monthly orders, buyers, merch (2025-07) vs pandas
r = con.execute("SELECT valid_orders, buyers, merchandise_sales_usd::VARCHAR, aov_usd FROM ads.kpi_monthly WHERE month = '2025-07'").fetchone()
mv = V[V.month == '2025-07']
check('kpi_monthly 2025-07 orders / buyers / merch vs pandas', (r[0], r[1], Decimal(r[2])) == (len(mv), mv.customer_id.nunique(), sum(mv.m)),
      (len(mv), mv.customer_id.nunique(), sum(mv.m)), r[:3])
# 2. AOV hand calculation
check('kpi_monthly 2025-07 AOV = merch / orders (hand)', abs(Decimal(str(r[3])) - sum(mv.m) / len(mv)) < Decimal('1e-9'), round(sum(mv.m) / len(mv), 4), round(r[3], 4))
# 3. quarter totals vs DATA-08 rule SQL on the Python-cleaned parquet (independent implementation)
clean = next((ROOT / 'data/processed/clean').glob('*-clean-v2'))
rc = rules_connect(clean)
q3 = ('2026-07-01 00:00:00+00', '2026-10-01 00:00:00+00', '2026-11-08 00:00:00+00')
r = con.execute("SELECT sum(valid_orders), sum(merchandise_sales_usd)::VARCHAR FROM ads.kpi_monthly WHERE month IN ('2026-07','2026-08','2026-09')").fetchone()
check('2026-Q3 orders and merchandise (net of cancellations; no refunds exist) vs DATA-08 rule SQL on clean parquet',
      (r[0], Decimal(r[1])) == (metric(rc, 'valid_orders', *q3), Decimal(metric(rc, 'merchandise_sales_usd', *q3))),
      (metric(rc, 'valid_orders', *q3), metric(rc, 'merchandise_sales_usd', *q3)), r)
r = con.execute("SELECT sum(cancelled_orders), sum(cancelled_merchandise_usd)::VARCHAR FROM ads.kpi_monthly").fetchone()
check('cancelled orders / merchandise (all months) vs DATA-08 reconciliation', (r[0], r[1]) == (194, '27778.26'), (194, '27778.26'), r)
# 4. daily view sums to monthly
r = con.execute("""SELECT (SELECT sum(valid_orders) FROM ads.kpi_daily WHERE strftime(day, '%Y-%m') = '2026-03'),
                          (SELECT valid_orders FROM ads.kpi_monthly WHERE month = '2026-03')""").fetchone()
check('kpi_daily orders add up to kpi_monthly (2026-03)', r[0] == r[1], r[1], r[0])
# 5. repurchase rate (2025-03-03) vs pandas from orders, not from the label table
t = pd.Timestamp('2025-03-03', tz='UTC')
pop = set(V[(V.p >= t - pd.Timedelta(days=90)) & (V.p < t) & (V.a < t)].customer_id)
buy = set(O[(O.p >= t) & (O.p < t + pd.Timedelta(days=30)) & (O.a < t + pd.Timedelta(days=31))].customer_id)
r = con.execute("SELECT population, repurchasers, repurchase_rate_30d FROM ads.repurchase_rate_weekly WHERE as_of_date = DATE '2025-03-03'").fetchone()
check('repurchase_rate_weekly 2025-03-03 vs pandas from orders', (r[0], r[1]) == (len(pop), len(pop & buy)) and abs(r[2] - len(pop & buy) / len(pop)) < 1e-12,
      (len(pop), len(pop & buy)), r[:2])
# 6. cohort retention cell vs pandas
first = V.groupby('customer_id').p.min().dt.strftime('%Y-%m')
coh = first[first == '2025-02'].index
act = V[V.customer_id.isin(coh) & (V.month == '2025-05')].customer_id.nunique()
r = con.execute("SELECT cohort_customers, active_customers, retention_rate FROM ads.cohort_retention WHERE cohort_month = '2025-02' AND months_since_first = 3").fetchone()
check('cohort 2025-02, month +3 retention vs pandas', (r[0], r[1]) == (len(coh), act), (len(coh), act), r[:2])
r = con.execute("SELECT count(*) FILTER (WHERE immature AND active_customers IS NOT NULL), count(*) FILTER (WHERE immature) FROM ads.cohort_retention").fetchone()
check('immature cohort cells are NULL, not 0', r[0] == 0 and r[1] > 0, 'all immature cells NULL', r)
r = con.execute("SELECT partial_period FROM ads.kpi_monthly WHERE month = '2026-11'").fetchone()[0]
check('partial month 2026-11 flagged', r is True, True, r)
check('allowed views registered and exclude customer-level profile', len(allowed) == 6 and all(v.startswith('ads.') for v, _ in allowed)
      and 'ads.customer_profile_latest' not in [v for v, _ in allowed], 6, [v for v, _ in allowed])
con.close()

# ---- metrics.json: add grain + ADS mapping (existing SQL untouched), add ADS-level metrics
M = json.loads((ROOT / 'contracts/metrics.json').read_text(encoding='utf-8'))
ads_map = {
    'valid_orders': ('日 / 月（按下单日）；可跨日、跨大区相加', 'ads.kpi_daily.valid_orders, ads.kpi_monthly.valid_orders'),
    'merchandise_sales_usd': ('日 / 月 / 月×品类×大区；可加', 'ads.kpi_daily.merchandise_sales_usd, ads.kpi_monthly.merchandise_sales_usd, ads.sales_month_category_region.merchandise_sales_usd'),
    'shipping_usd': ('日 / 月；可加', 'ads.kpi_daily.shipping_usd, ads.kpi_monthly.shipping_usd'),
    'order_value_usd': ('订单', 'dwd.fact_order.order_value_usd（不在 ADS 暴露）'),
    'buyers': ('日 / 月；不可跨期相加，月度按月重算', 'ads.kpi_daily.buyers, ads.kpi_monthly.buyers'),
    'aov_usd': ('日 / 月；比率，不可相加', 'ads.kpi_daily.aov_usd, ads.kpi_monthly.aov_usd'),
    'cancelled_orders': ('月（按下单月）', 'ads.kpi_monthly.cancelled_orders'),
    'cancelled_merchandise_usd': ('月（按下单月）', 'ads.kpi_monthly.cancelled_merchandise_usd'),
    'repurchase_30d': ('客户×as_of', 'ML-11 输出；经验值见 ads.repurchase_rate_weekly'),
    'non_repurchase_30d': ('客户×as_of', 'ML-11 输出'),
    'rfm': ('客户×as_of', 'dws.customer_snapshot（recency_days, frequency_90d, monetary_90d_usd）'),
}
model_sql = {
    'repurchase_30d': ('sql/customer_snapshot.sql block labels（目标定义；概率由 ML-11 模型输出）',
                       '标签与 DATA-11 门槛一致见 evidence/DW-05；模型概率样例待 ML-11'),
    'non_repurchase_30d': ('1 - repurchase_30d（ML-11 评分服务输出）', '待 ML-11'),
    'rfm': ('sql/customer_snapshot.sql block snapshot（recency_days, frequency_90d, monetary_90d_usd）',
            'evidence/DW-05/verify_snapshot.py：3 个 as_of 由截断订单独立重算一致'),
}
for x in [m for m in M['metrics'] if m['id'] in ads_map]:
    g, v = ads_map[x['id']]
    x['grain'], x['ads_view'] = g, v
    if x['id'] in model_sql:
        x['sql_mapping'], x['examples_and_checks'] = model_sql[x['id']]
new = [
    {'id': 'repurchase_rate_30d_observed', 'name': '30天经验复购率', 'unit': 'ratio 0-1',
     'definition': 'as_of 时 90 天母体中，[as_of, as_of+30d) 内有有效购买（as_of+31d 前已审批）的客户占比；是已发生的比例，不是模型概率',
     'population': 'as_of 前 90 天有有效购买的已知客户', 'inclusions': '标签已成熟的 as_of', 'exclusions': '未成熟 as_of', 'numerator': 'repurchasers',
     'denominator': 'population', 'windows': 'as_of 每周一；标签窗 [as_of, as_of+30d)', 'zero_null_policy': '母体为 0 时为 null',
     'supported_dimensions': ['as_of week'], 'grain': 'as_of（周）', 'ads_view': 'ads.repurchase_rate_weekly',
     'sql_mapping': 'sql/ads.sql view ads.repurchase_rate_weekly', 'examples_and_checks': 'reports/warehouse/metric_checks.json'},
    {'id': 'cohort_retention_rate', 'name': 'cohort 留存率', 'unit': 'ratio 0-1',
     'definition': '首次可观测有效购买月为 cohort，第 k 个月有有效购买的客户 / cohort 客户数；未成熟（含不完整的截止月）为 null',
     'population': '至少一次有效购买的客户', 'inclusions': '有效购买', 'exclusions': '取消订单', 'numerator': 'active_customers',
     'denominator': 'cohort_customers', 'windows': '自然月，按下单时间', 'zero_null_policy': '未成熟格子为 null，不当作 0',
     'supported_dimensions': ['cohort_month', 'months_since_first'], 'grain': 'cohort 月×距首购月数', 'ads_view': 'ads.cohort_retention',
     'sql_mapping': 'sql/ads.sql view ads.cohort_retention', 'examples_and_checks': 'reports/warehouse/metric_checks.json'},
]
M['metrics'] = [x for x in M['metrics'] if x['id'] not in {n['id'] for n in new}] + new
M['ads'] = {'views_sql': 'sql/ads.sql', 'allowed_views': [v for v, _ in allowed], 'as_of': '2026-11-08T00:00:00Z'}
M['required_for_approval'] = sorted(set(M['required_for_approval']) | {'grain', 'ads_view'})
(ROOT / 'contracts/metrics.json').write_text(json.dumps(M, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
missing = [(x['id'], k) for x in M['metrics'] for k in M['required_for_approval'] if k not in x]
check('every metric has unit, numerator/denominator, window, inclusions/exclusions, null policy, grain and SQL/ADS mapping', not missing, [], missing)
out = {'task_id': 'DW-06', 'as_of': '2026-11-08T00:00:00Z', 'allowed_views': [{'view': v, 'purpose': p} for v, p in allowed],
       'view_duties': {'经营总览': ['ads.kpi_daily', 'ads.kpi_monthly', 'ads.sales_month_category_region'], 'cohort': ['ads.cohort_retention'],
                       '分群/生命周期': ['ads.lifecycle_mix_weekly', 'ads.customer_profile_latest（客户级，不对 AI 开放）'],
                       '风险': ['ads.repurchase_rate_weekly（经验比例）；模型风险分由 ML-11 加入']},
       'checks': results, 'all_checks_passed': all(ok)}
(ROOT / 'reports/warehouse/metric_checks.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
