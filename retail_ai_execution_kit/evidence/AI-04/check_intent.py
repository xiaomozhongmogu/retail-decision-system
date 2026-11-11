"""AI-04 check: rule parser on a fixed question set, catalog checks against the release, trusted plans, and the
optional LLM path on paraphrases the rules cannot place. usage: .venv/bin/python evidence/AI-04/check_intent.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/ai'))
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
import query_intent as Q  # noqa: E402
from runtime import pointer, query_view  # noqa: E402

ok, rows = [], []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, '' if cond else str(detail)[:300])


# (question, expected status, expected metric, kind, dims, filters, time label) -- one row per supported class plus boundaries
CASES = [
    ('2026年10月的商品金额是多少？', 'ok', 'merchandise_sales_usd', 'value', [], {}, '2026-10'),
    ('上个月有多少单？', 'ok', 'valid_orders', 'value', [], {}, '上个月'),
    ('2025年的客单价是多少', 'ok', 'aov_usd', 'value', [], {}, '2025'),
    ('2026年10月购买客户有多少？', 'ok', 'buyers', 'value', [], {}, '2026-10'),
    ('2025年第四季度的运费一共多少', 'ok', 'shipping_usd', 'value', [], {}, '2025-Q4'),
    ('2025年取消了多少订单', 'ok', 'cancelled_orders', 'value', [], {}, '2025'),
    ('最近6个月商品金额的趋势', 'ok', 'merchandise_sales_usd', 'trend', [], {}, '最近 6 个完整月'),
    ('2025年每月订单数走势', 'ok', 'valid_orders', 'trend', [], {}, '2025'),
    ('最近一周每天的销售额', 'ok', 'merchandise_sales_usd', 'trend', [], {}, '最近一个审批落定的完整周'),
    ('2025年哪个品类的商品金额最高？', 'ok', 'merchandise_sales_usd', 'ranking', ['product_category'], {}, '2025'),
    ('2026年10月商品金额前3的品类', 'ok', 'merchandise_sales_usd', 'ranking', ['product_category'], {}, '2026-10'),
    ('2025年各大区商品金额占比', 'ok', 'merchandise_sales_usd', 'share', ['customer_region'], {}, '2025'),
    ('2026年10月商品金额同比变化', 'ok', 'merchandise_sales_usd', 'comparison', [], {}, '2026-10'),
    ('上个月订单数环比', 'ok', 'valid_orders', 'comparison', [], {}, '上个月'),
    ('2025年西部地区电子品类的商品金额', 'ok', 'merchandise_sales_usd', 'value', ['customer_region', 'product_category'][1:] if False else [], {'customer_region': ['West'], 'product_category': ['Electronics & Accessories']}, '2025'),
    ('2025年中西部的商品金额是多少', 'ok', 'merchandise_sales_usd', 'value', [], {'customer_region': ['Midwest']}, '2025'),
    ('最新的30天复购率是多少', 'ok', 'repurchase_rate_30d', 'value', [], {}, None),
    ('首单后第一个月的留存率', 'ok', 'cohort_retention_rate', 'value', [], {}, None),
    ('现在沉睡客户有多少', 'ok', 'lifecycle_customers', 'value', [], {}, None),
    # clarify
    ('商品金额是多少', 'clarify', 'merchandise_sales_usd', None, None, None, None),
    ('2025年的收入是多少', 'clarify', None, None, None, None, None),
    ('哪个品类卖得最好', 'clarify', None, None, None, None, None),
    ('2025年商品金额排名', 'clarify', 'merchandise_sales_usd', None, None, None, None),
    ('2026年10月商品金额对比', 'clarify', 'merchandise_sales_usd', None, None, None, None),
    ('今天天气怎么样', 'clarify', None, None, None, None, None),
    # unsupported
    ('2025年各品类的毛利是多少', 'unsupported', None, None, None, None, None),
    ('各渠道的ROI', 'unsupported', None, None, None, None, None),
    ('2025年加州的订单数', 'unsupported', None, None, None, None, None),
    ('2025年各品类的购买客户数', 'unsupported', 'buyers', None, None, None, None),
    ('2025年全年去重购买客户数', 'unsupported', 'buyers', None, None, None, None),
    ('2023年的商品金额', 'empty', 'merchandise_sales_usd', None, None, None, None),
    ('2026年12月的订单数', 'empty', 'valid_orders', None, None, None, None),
]
for q, st, m, kind, dims, f, lab in CASES:
    r = Q.parse(q)
    good = r['status'] == st and (m is None or r.get('metric') == m)
    if st == 'ok':
        good = good and r['kind'] == kind and sorted(r['dims']) == sorted(dims) and r['filters'] == f and (lab is None or (r['time'] or {}).get('label') == lab)
    rows.append({'question': q, 'expected_status': st, 'got': {k: r.get(k) for k in ('status', 'metric', 'kind', 'dims', 'filters', 'time', 'compare', 'clarification', 'error')}, 'pass': good})
    check(f'parse: {q} -> {st}', good, r)
ok_cases = [r for r in rows if r['expected_status'] == 'ok']
check('at least 10 supported question classes (distinct metric x kind)', len({(r['got']['metric'], r['got']['kind']) for r in ok_cases}) >= 10)

# catalog matches the published release
ptr = pointer()
cats = sorted({r[0] for r in query_view('ads.sales_month_category_region', ['product_category'])['rows']})
regs = sorted({r[0] for r in query_view('ads.sales_month_category_region', ['customer_region'])['rows']})
check('category and region enums equal the release values', cats == sorted(Q.CATEGORIES) and regs == sorted(Q.REGIONS.values()), (cats, regs))
views = {c['view'] for q, *_ in CASES for c in Q.plan(Q.parse(q)).get('calls', [])}
check('every planned view is in the release allow-list', views and views <= set(ptr['allowed_views']), views)
p = Q.plan(Q.parse('2026年10月商品金额同比变化'))
check('comparison plan: same months one year earlier as base', p['post']['periods'][1]['months'] == ['2025-10'])
p = Q.plan(Q.parse('2025年的客单价是多少'))
check('AOV plan recomputes from sums, from kpi_monthly', p['post']['aov_recomputed_from_sums'] and p['calls'][0]['view'] == 'ads.kpi_monthly' and len(p['post']['periods'][0]['months']) == 12)
check('plans contain no SQL text', 'SELECT' not in json.dumps([Q.plan(Q.parse(q)) for q, *_ in CASES]).upper())
w = Q.parse('本月的商品金额')
check('incomplete period flagged (本月)', w['status'] == 'ok' and any(x['code'] == 'partial_period' for x in w['warnings']))
bad = Q.validate_intent({'question': 'x', 'metric': 'merchandise_sales_usd', 'dims': ['seller_id'], 'filters': {}, 'time': {'start': '2025-01', 'end': '2025-12', 'grain': 'year', 'label': '2025'}, 'kind': 'value'})
check('validator rejects an unknown dimension (LLM path safety)', bad['status'] == 'unsupported')
bad = Q.validate_intent({'question': 'x', 'metric': 'merchandise_sales_usd', 'dims': [], 'filters': {'product_category': ['Electronics']}, 'time': None, 'kind': 'value'})
check('validator rejects a category value outside the enum', bad['status'] == 'unsupported')

# optional LLM path on paraphrases the rules cannot place
PARA = [('二〇二五年十月份大概成交了多少美元的货？', 'merchandise_sales_usd'), ('去年十月份一共来了几张单子', 'valid_orders')]
live = []
for q, m in PARA:
    r0 = Q.parse(q)
    r = Q.understand(q)
    live.append({'question': q, 'rules': r0['status'], 'final': {k: r.get(k) for k in ('parser', 'status', 'metric', 'kind', 'time', 'clarification', 'error')}})
    check(f'LLM path used only after rules fail, and its intent passes the catalog or is turned into a clarification: {q}',
          r0['status'] == 'clarify' and r['parser'] == 'llm' and (r['status'] == 'clarify' or (r['status'] == 'ok' and r['metric'] == m)), r)
print(json.dumps(live, ensure_ascii=False)[:800])
(ROOT / 'reports/ai/query_intent_checks.json').write_text(json.dumps({'task_id': 'AI-04', 'rows': rows, 'llm_path': live, 'passed': sum(ok), 'total': len(ok)}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print(f'{sum(ok)}/{len(ok)} checks passed')
sys.exit(0 if all(ok) else 1)
