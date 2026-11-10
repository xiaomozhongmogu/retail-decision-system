"""Check that reports/data/dataset_selection.md matches the computed facts.

usage: .venv/bin/python evidence/DATA-03/verify_selection.py
Exit 0 only if every assertion passes. Prints one line per check.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
facts = json.loads((ROOT / 'reports/data/dataset_selection_facts.json').read_text(encoding='utf-8'))
md = (ROOT / 'reports/data/dataset_selection.md').read_text(encoding='utf-8')
SOURCE_SHA = 'd50ee64a0478d8ae8df1b8b66521671a4911e19f911ae86196452a668f917a16'
EXCLUDED = {'customer_segment', 'customer_lifecycle_stage', 'review_sentiment_label',
            'satisfaction_risk_flag', 'seller_segment', 'seller_quality_score',
            'seller_fulfillment_capacity', 'scenario_name', 'order_year', 'order_quarter',
            'order_month', 'order_week', 'order_day_of_week', 'is_weekend',
            'is_holiday_period', 'is_promotion_period'}
results = []


def check(name, ok, detail=''):
    results.append(ok)
    print(('PASS' if ok else 'FAIL'), name, detail)


def n(x):
    return f'{x:,}'


layer = Path(facts['layer'])
layer = layer if layer.is_absolute() else ROOT / layer
manifest_path = layer / 'manifest.json'
check('layer manifest unchanged since facts run',
      hashlib.sha256(manifest_path.read_bytes()).hexdigest() == facts['layer_manifest_sha256'])
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
check('layer built from frozen source ZIP', manifest.get('source_sha256') == SOURCE_SHA and SOURCE_SHA in md)
check('cutoff in report', facts['as_of_exclusive'].startswith('2026-11-08T00:00:00') and '2026-11-08T00:00:00Z' in md)

fields = facts['checked_business_fields']
meaningful = [k for k, v in fields.items() if v['non_null'] > 0 and k.split('.')[1] not in EXCLUDED]
check('>=8 meaningful source fields, none excluded', len(meaningful) >= 8 and len(meaningful) == len(fields),
      f'{len(meaningful)} fields')
for k, v in fields.items():
    check(f'field row in report: {k}', f'| {k} |' in md and f'{n(v["non_null"])} / {n(v["rows"])}' in md
          and f'| {n(v["distinct"])} |' in md)

check('all internal joins have zero orphans', all(v == 0 for v in facts['join_orphans'].values())
      and len(facts['join_orphans']) == 7)
for k in facts['join_orphans']:
    a, b = k.split('->')
    check(f'join row in report: {k}', f'{a} → {b} | 0 |' in md)

rows = facts['row_counts']
for t, label in [('orders', '订单'), ('order_items', '订单明细'), ('payments', '支付'),
                 ('customers', '客户'), ('products', '商品'), ('sellers', '卖家'),
                 ('shipping', '物流'), ('reviews', '评价')]:
    check(f'row count {t}', f'{label} {n(rows[t])}' in md)

st = facts['order_status']
check('status counts', all(f'{n(st[s])}' in md for s in st) and set(st) == {'delivered', 'processing', 'cancelled', 'shipped'})
check('size rule uses order_items >= 10000', rows['order_items'] >= 10000 and n(rows['order_items']) in md)
check('month span', facts['purchase_months'] == 35 and f'共 {facts["purchase_months"]} 个月' in md)
mn, mx = facts['orders_per_month_min_max']
check('orders per month range', f'{mn} 至 {mx} 单' in md)

rep = facts['repurchase_feasibility']['non_cancelled_orders']
check('repurchase customers', f'{n(rep["customers_with_orders"])} 名' in md and f'{n(rep["customers_with_2plus_orders"])} 人' in md)
g = rep['inter_order_gap_days']
check('gap quantiles', f'{g["median"]} 天' in md and f'{g["p05_p25_p75_p95"][1]} 天' in md
      and f'{g["p05_p25_p75_p95"][2]} 天' in md)
for b in rep['base_rate_30d_examples']:
    pct = f'{b["rate"] * 100:.1f}%'
    check(f'base rate {b["as_of"]}',
          f'| {b["as_of"]} | {n(b["population_90d_buyers"])} | {b["repurchased_next_30d"]} | {pct} |' in md)

check('authorization wording: D012 user, no teacher reply',
      'D012' in md and '没有收到教师' in md and '不能写成“教师已确认”' in md)
check('route decision stated', '走交易路线' in md and '选交易路线' in md)
check('adjusted/deleted items listed', '**删除**' in md and '**调整**' in md and '### 页面' in md and '### 模型' in md)

print(f'{sum(results)}/{len(results)} passed')
sys.exit(0 if all(results) else 1)
