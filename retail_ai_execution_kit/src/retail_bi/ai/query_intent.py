"""AI-04: question -> structured intent -> trusted query plan over allowed ADS views (no model-written SQL).

parse(question)      deterministic rule parser -> intent dict with status ok | clarify | unsupported
parse_llm(question)  optional: LLM fills the same intent JSON; validate_intent() checks every field against the
                     catalog (metrics, dimensions, enums, time) before it is used; rejected intents fall back to clarify
plan(intent)         trusted constructor: a list of runtime.query_view calls (view, columns, equality filters) plus a
                     post-processing spec (month range, group by, sums, AOV recomputed). The executor is AI-05.
Time semantics: as_of 2026-11-08 (exclusive); "上个月" = 2026-10; "本月" = 2026-11 (incomplete); "本周/最近一周" = the
settled report week 2026-10-31..2026-11-06 (AI-08); "今年" = 2026 (incomplete); "去年" = 2025.
"""
from __future__ import annotations

import json
import re

AS_OF_MONTH = '2026-11'
LAST_FULL_MONTH = '2026-10'
SETTLED_WEEK = ('2026-10-31', '2026-11-07')       # [start, end) as in AI-08
DATA_START = '2024-01'
CATEGORIES = ['Automotive', 'Baby Products', 'Books & Media', 'Electronics & Accessories', 'Fashion', 'Furniture & Decor', 'Garden & Outdoor',
              'Health & Beauty', 'Home & Bedding', 'Home Goods', 'Mobile & Telecom', 'Office Supplies', 'Pet Supplies', 'Sports & Outdoors',
              'Toys & Games', 'Watches & Gifts']
CAT_ALIAS = {'汽车': 'Automotive', '母婴': 'Baby Products', '图书': 'Books & Media', '电子': 'Electronics & Accessories', '服装': 'Fashion', '时尚': 'Fashion',
             '家具': 'Furniture & Decor', '园艺': 'Garden & Outdoor', '美妆': 'Health & Beauty', '健康': 'Health & Beauty', '家纺': 'Home & Bedding',
             '家居': 'Home Goods', '手机': 'Mobile & Telecom', '通讯': 'Mobile & Telecom', '办公': 'Office Supplies', '宠物': 'Pet Supplies',
             '运动': 'Sports & Outdoors', '玩具': 'Toys & Games', '手表': 'Watches & Gifts', '礼品': 'Watches & Gifts'}
REGIONS = {'中西部': 'Midwest', '东北': 'Northeast', '南部': 'South', '西部': 'West'}
METRICS = {   # id: (zh, unit, keywords)
    'merchandise_sales_usd': ('商品金额', 'USD', r'商品金额|销售总?额|销售金额|总销售额|销售总金额|成交额|成交金额|销量金额|卖了多少钱|金额'),
    'valid_orders': ('有效订单数', 'orders', r'订单数|订单量|单量|多少单|订单'),
    'aov_usd': ('客单价', 'USD', r'客单价|平均每[笔单]|每[笔单].{0,8}平均|平均订单金额|订单平均金额|笔均|单均|AOV'),
    'buyers': ('购买客户数（月内去重）', 'customers', r'购买客户|买家|客户数|多少客户|多少人买'),
    'shipping_usd': ('运费', 'USD', r'运费'),
    'cancelled_orders': ('取消订单数', 'orders', r'取消'),
    'repurchase_rate_30d': ('30 天经验复购率', 'ratio', r'复购率|复购'),
    'cohort_retention_rate': ('cohort 留存率', 'ratio', r'留存'),
    'lifecycle_customers': ('生命周期状态人数', 'customers', r'生命周期|沉睡|活跃客户|预警客户|新客'),
    'valid_lines': ('有效明细行', 'lines', r'明细|件数|行数'),
}
UNSUPPORTED = {r'毛利|利润': '毛利与利润（数据中没有成本）', r'退款|退货': '退款与退货（数据中没有）', r'渠道|广告|投放|ROI': '渠道与营销投放（数据中没有）',
               r'库存': '库存（数据中没有）', r'年龄|性别': '客户年龄或性别（数据中没有）', r'浏览|加购|点击|转化率': '浏览与转化漏斗（数据中没有）',
               r'城市|州|邮编': '州、城市与邮编（不在允许视图中）', r'卖家|商家': '卖家维度（不在允许视图中）', r'评分|评价': '评价（不在允许视图中）'}
AMBIGUOUS = {r'收入|营收|业绩|GMV|流水': '“收入/业绩”可以指商品金额（不含运费）或订单金额（含运费），本系统默认口径是商品金额。请确认要看哪一个。',
             r'卖得最好|最好卖|最受欢迎|表现最好': '“卖得最好”可以按商品金额或按明细件数排名，请确认用哪个指标。'}
CN_NUM = {'一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '十二': 12}


def _months(a: str, b: str) -> list[str]:
    y, m = map(int, a.split('-'))
    out = []
    while f'{y}-{m:02d}' <= b:
        out.append(f'{y}-{m:02d}')
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _shift(month: str, k: int) -> str:
    y, m = map(int, month.split('-'))
    t = y * 12 + (m - 1) + k
    return f'{t // 12}-{t % 12 + 1:02d}'


def _next_day(d: str) -> str:
    from datetime import date, timedelta
    return (date.fromisoformat(d) + timedelta(days=1)).isoformat()


def parse_time(q: str) -> dict | None:
    m = re.search(r'(20\d\d)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]', q) or re.search(r'(20\d\d)-(\d{1,2})-(\d{1,2})', q)
    if m:                                                        # a single day (external test G-002: was silently read as the month)
        try:
            d = f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
            return {'start': d, 'end': _next_day(d), 'grain': 'day', 'label': d, 'closed': 'left', 'single_day': True}
        except ValueError:
            return {'start': None, 'end': None, 'grain': 'invalid', 'label': m.group(0)}
    m = re.search(r'(20\d\d)\s*年\s*(\d{1,2})\s*月\s*(?:到|至|~|～|-|—|－)\s*(?:(20\d\d)\s*年\s*)?(\d{1,2})\s*月', q)
    if m:                                                        # a month range (G-003: was truncated to the first month)
        a, b = f'{m.group(1)}-{int(m.group(2)):02d}', f'{m.group(3) or m.group(1)}-{int(m.group(4)):02d}'
        return {'start': a, 'end': b, 'grain': 'month', 'label': f'{a} 至 {b}'}
    m = re.search(r'(20\d\d)\s*年\s*(\d{1,2})\s*月', q) or re.search(r'(20\d\d)-(\d{1,2})(?!\d)', q)
    if m:
        mo = f'{m.group(1)}-{int(m.group(2)):02d}'
        return {'start': mo, 'end': mo, 'grain': 'month', 'label': mo}
    m = re.search(r'(20\d\d\s*年?|去年|今年)\s*(?:的\s*)?(?:第\s*([一二三四1-4])\s*季度|Q([1-4]))', q, re.I)
    if m:
        y = {'去年': '2025', '今年': '2026'}.get(m.group(1), m.group(1)[:4])
        qn = int(m.group(3) or (CN_NUM.get(m.group(2)) or m.group(2)))
        return {'start': f'{y}-{3 * qn - 2:02d}', 'end': f'{y}-{3 * qn:02d}', 'grain': 'quarter', 'label': f'{y}-Q{qn}'}
    m = re.search(r'(?:最近|近|过去)\s*(\d{1,2}|[一二两三四五六七八九十]|十二)\s*个?月', q)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else CN_NUM[m.group(1)]
        return {'start': _shift(LAST_FULL_MONTH, -(n - 1)), 'end': LAST_FULL_MONTH, 'grain': 'month', 'label': f'最近 {n} 个完整月'}
    if re.search(r'上个?月', q):
        return {'start': LAST_FULL_MONTH, 'end': LAST_FULL_MONTH, 'grain': 'month', 'label': '上个月'}
    if '本月' in q or '这个月' in q:
        return {'start': AS_OF_MONTH, 'end': AS_OF_MONTH, 'grain': 'month', 'label': '本月（不完整）', 'incomplete': True}
    if re.search(r'本周|这周|最近一周|上周', q):
        return {'start': SETTLED_WEEK[0], 'end': SETTLED_WEEK[1], 'grain': 'day', 'label': '最近一个审批落定的完整周', 'closed': 'left'}
    m = re.search(r'(20\d\d)\s*年', q)
    if m:
        y = m.group(1)
        return {'start': f'{y}-01', 'end': f'{y}-12' if y < '2026' else AS_OF_MONTH, 'grain': 'year', 'label': y, 'incomplete': y == '2026'}
    if '今年' in q:
        return {'start': '2026-01', 'end': AS_OF_MONTH, 'grain': 'year', 'label': '2026（不完整）', 'incomplete': True}
    if '去年' in q:
        return {'start': '2025-01', 'end': '2025-12', 'grain': 'year', 'label': '2025'}
    if re.search(r'全部|所有时间|历史|累计', q):
        return {'start': DATA_START, 'end': AS_OF_MONTH, 'grain': 'all', 'label': '全部历史'}
    return None


def parse(question: str) -> dict:
    q = question.strip()
    base = {'question': q, 'parser': 'rules', 'metric': None, 'dims': [], 'filters': {}, 'time': None, 'compare': None, 'top_n': None, 'grain': None}
    if not q:
        return {**base, 'status': 'clarify', 'clarification': '请输入一个经营问题。'}
    if re.search(r'删除|修改|更新|插入|清空|写入|导出|下载|备份|drop|delete|update|insert|truncate|alter|^\s*select\b', q, re.I):
        return {**base, 'status': 'unsupported', 'error': {'code': 'query_rejected', 'message': '只支持只读的经营指标查询，不能修改、删除、导出数据或直接执行 SQL'}}
    for pat, why in UNSUPPORTED.items():
        if re.search(pat, q):
            return {**base, 'status': 'unsupported', 'error': {'code': 'capability_not_supported', 'message': f'不支持：{why}'}}
    for pat, ask in AMBIGUOUS.items():
        if re.search(pat, q):
            return {**base, 'status': 'clarify', 'clarification': ask}
    order = ['cancelled_orders', 'aov_usd', 'shipping_usd', 'repurchase_rate_30d', 'cohort_retention_rate', 'lifecycle_customers', 'buyers',
             'valid_lines', 'merchandise_sales_usd', 'valid_orders']     # specific terms before generic ones (取消订单 before 订单)
    metric = next((k for k in order if re.search(METRICS[k][2], q)), None)
    if metric == 'merchandise_sales_usd' and re.search(METRICS['aov_usd'][2], q):
        metric = 'aov_usd'
    if metric is None:
        return {**base, 'status': 'clarify', 'clarification': '没有识别出指标。可以问商品金额、订单数、客单价、购买客户数、运费、取消订单、复购率、留存率或生命周期人数。'}
    grp = r'(?:各个?|按|每个|分|哪个|哪一个?|哪些|前\s*\S{1,2}的?)\s*'
    dims = (['product_category'] if re.search(grp + r'(?:品类|类目|类别)', q) or re.search(r'(?:品类|类目|类别)\s*(?:排名|排行|占比|分布)', q) else []) + \
           (['customer_region'] if re.search(grp + r'(?:地区|大区|区域)', q) or re.search(r'(?:地区|大区|区域)\s*(?:排名|排行|占比|分布)', q) else [])
    filters = {}
    cats = sorted({v for k, v in CAT_ALIAS.items() if k in q} | {c for c in CATEGORIES if c.lower() in q.lower()})
    rest = q.replace('中西部', '')
    regs = sorted({'Midwest'} if '中西部' in q else set()) + sorted({v for k, v in REGIONS.items() if k != '中西部' and k in rest} | {r for r in REGIONS.values() if r.lower() in q.lower()})
    regs = sorted(set(regs))
    if cats:
        filters['product_category'] = cats
    if regs:
        filters['customer_region'] = regs
    kind = 'value'
    if re.search(r'趋势|走势|每个?月|按月|逐月|变化情况', q):
        kind, grain = 'trend', 'month'
    elif re.search(r'每天|按天|逐日|每日', q):
        kind, grain = 'trend', 'day'
    else:
        grain = None
    top = re.search(r'(?:前|top\s*)(\d{1,2}|[一二两三四五六七八九十])', q, re.I)
    top = top or re.search(r'(\d{1,2}|[一二两三四五六七八九十])\s*个\s*(?:品类|类目|类别|大区|地区|区域)', q)    # “最低的3个品类” (G-007)
    if re.search(r'哪个|哪一|最高|最多|最低|最少|排名|排行|排在?第一|第一名|冠军|居首', q) or top:
        kind = 'ranking'
    if re.search(r'同比|环比|相比|对比|比去年|比上', q):
        kind = 'comparison'
    if re.search(r'占比|比例|份额|贡献', q):
        kind = 'share'
    if kind in ('ranking', 'share'):
        if not dims and re.search(r'品类|类目|类别', q) and not cats:
            dims.append('product_category')
        if not dims and re.search(r'地区|大区|区域', q) and not regs:
            dims.append('customer_region')
    t = parse_time(q)
    state = next((v for k, v in {'沉睡': 'dormant', '活跃': 'active', '预警': 'at_risk', '新客': 'new'}.items() if k in q), None) if metric == 'lifecycle_customers' else None
    intent = {**base, 'metric': metric, 'dims': dims, 'filters': filters, 'time': t, 'kind': kind, 'grain': grain,
              'top_n': (int(top.group(1)) if top.group(1).isdigit() else CN_NUM[top.group(1)]) if top else (1 if kind == 'ranking' and re.search(r'最|哪个|哪一|第一|冠军|居首', q) else None),
              'descending': not re.search(r'最低|最少', q), 'lifecycle_state': state}
    if kind == 'comparison':
        intent['compare'] = 'yoy' if re.search(r'同比|去年', q) else 'mom' if re.search(r'环比|上个?月|上周', q) else None
        if intent['compare'] is None:
            return {**intent, 'status': 'clarify', 'clarification': '请说明对比对象：同比（去年同期）还是环比（上一期）。'}
    if kind in ('ranking', 'share') and not dims:
        return {**intent, 'status': 'clarify', 'clarification': '排名或占比需要一个维度：按品类还是按客户大区？'}
    why = uncovered(q, intent)
    if why:
        return {**intent, 'status': 'clarify', 'clarification': why}
    return validate_intent(intent)


def uncovered(q: str, intent: dict) -> str | None:
    """Constraints the question states but the intent would not apply. Answering anyway would return a number for a
    different question (external tests 2026-11-13: G-001..G-007, U-001, U-002), so the assistant asks instead."""
    t, dims, f = intent.get('time') or {}, intent.get('dims') or [], intent.get('filters') or {}
    if t.get('grain') == 'invalid':
        return f"日期“{t['label']}”无效，请检查年月日。"
    if re.search(r'品类|类目|类别', q) and 'product_category' not in dims and 'product_category' not in f:
        return '没有识别出问题中的品类名称。可选品类：' + '、'.join(f'{k}（{v}）' for k, v in CAT_ALIAS.items()) + '。也可以问“各品类……”。'
    if re.search(r'地区|大区|区域', q) and 'customer_region' not in dims and 'customer_region' not in f:
        return '没有识别出问题中的大区。可选：中西部、东北、南部、西部；也可以问“各大区……”。'
    if re.search(r'季度|(?<![A-Za-z])Q[1-4]', q, re.I) and t.get('grain') != 'quarter':
        return '没有识别出季度所在的年份，请写成“2025年第3季度”或“去年第3季度”。'
    if re.search(r'\d\s*[日号]', q) and not t.get('single_day'):
        return '没有识别出具体日期，请写成“2026年10月5日”。'
    if re.search(r'(?<!生命)周(?!期)', q) and t.get('grain') != 'day':
        return '按周只支持“上周/本周/最近一周”（最近一个审批落定的完整周），其他周请写成具体日期或改问月份。'
    years = set(re.findall(r'20\d\d', q))
    if len(years) > 1 and not (t.get('start') and t.get('end') and {t['start'][:4], t['end'][:4]} == years):
        return '一次只能问一个时间范围；比较两个年份请用“同比”，或写成“2025年11月到2026年2月”。'
    if '平均' in q and intent.get('metric') != 'aov_usd':
        return '“平均”可以指客单价（每笔有效订单的平均商品金额）或月均值；本系统只提供客单价，请确认。'
    if intent.get('metric') == 'cancelled_orders' and re.search(r'金额|销售额|多少钱|美元|USD', q, re.I):
        return '取消订单只提供订单数，不提供取消订单的金额。'
    if intent.get('compare') and dims:
        return '暂不支持按品类或大区分组的同比/环比。可以指定一个品类或大区，例如“2026年10月西部商品金额同比”。'
    if intent.get('compare') == 'yoy' and t.get('grain') == 'day':
        return '按周的同比请使用“经营周报”（按去年同期同星期对齐）；这里可以问按周环比或按月同比。'
    return None


def validate_intent(intent: dict) -> dict:
    """Catalog check shared by the rule parser and the LLM path. Returns the intent with status set."""
    m, dims, f, t = intent.get('metric'), intent.get('dims') or [], intent.get('filters') or {}, intent.get('time')
    bad = lambda msg: {**intent, 'status': 'unsupported', 'error': {'code': 'unknown_field', 'message': msg}}  # noqa: E731
    if m not in METRICS:
        return bad(f'未知指标：{m}')
    if any(d not in ('product_category', 'customer_region') for d in dims):
        return bad(f'未知维度：{dims}')
    if any(v not in CATEGORIES for v in f.get('product_category', [])) or any(v not in REGIONS.values() for v in f.get('customer_region', [])) \
            or any(k not in ('product_category', 'customer_region') for k in f):
        return bad(f'筛选值不在枚举中：{f}')
    if intent.get('kind') not in ('value', 'trend', 'ranking', 'comparison', 'share'):
        return bad(f"未知问题类型：{intent.get('kind')}")
    sliced = bool(dims or f)
    if intent.get('compare') and dims:
        return {**intent, 'status': 'clarify', 'clarification': '暂不支持按品类或大区分组的同比/环比。可以指定一个品类或大区，例如“2026年10月西部商品金额同比”。'}
    if sliced and m in ('valid_orders', 'buyers', 'aov_usd', 'shipping_usd', 'cancelled_orders'):
        return bad(f'{METRICS[m][0]}没有按品类或地区的允许视图（品类×地区视图只有商品金额、明细行和含该品类订单数）')
    if sliced and m in ('repurchase_rate_30d', 'cohort_retention_rate', 'lifecycle_customers'):
        return bad(f'{METRICS[m][0]}没有按品类或地区的视图')
    if m in ('repurchase_rate_30d', 'cohort_retention_rate', 'lifecycle_customers'):
        return {**intent, 'status': 'ok', 'warnings': ([{'code': 'time_ignored', 'message': '该指标按其视图的快照时间返回，时间条件仅作展示'}] if t else [])}
    if t is None:
        return {**intent, 'status': 'clarify', 'clarification': '请指定时间范围，例如“2026年10月”“2025年”“最近3个月”或“上周”。'}
    if t['grain'] == 'invalid':
        return bad(f"时间范围无效：{t['label']}")
    if t['start'] < (DATA_START + '-01' if t['grain'] == 'day' else DATA_START):
        return {**intent, 'status': 'empty', 'error': {'code': 'out_of_range', 'message': f"数据从 2024-01 开始，所问时间 {t['label']} 没有数据"}}
    if (t['grain'] != 'day' and t['end'] > AS_OF_MONTH) or t['start'] > AS_OF_MONTH or (t['grain'] == 'day' and t['start'] >= '2026-11-08'):
        return {**intent, 'status': 'empty', 'error': {'code': 'out_of_range', 'message': f"数据截止 2026-11-08（不含），所问时间 {t['label']} 没有数据"}}
    if t['start'] > t['end']:
        return bad(f"时间范围无效：{t['label']}（开始晚于结束）")
    if m == 'buyers' and t['grain'] != 'month' or (m == 'buyers' and t['start'] != t['end']):
        if intent.get('kind') != 'trend':
            return bad('购买客户按月去重，跨月不能相加：请问单个月份，或用“每月购买客户趋势”')
    if t['grain'] == 'day' and sliced:
        return bad('品类×地区视图只有月粒度，不能按周或按天切分')
    w = [{'code': 'partial_period', 'message': f"{t['label']} 是不完整期间，不能与完整期间直接比较"}] if t.get('incomplete') else []
    return {**intent, 'status': 'ok', 'warnings': w}


def plan(intent: dict) -> dict:
    """Trusted constructor: query_view calls + post-processing. No SQL text is produced from the question."""
    if intent.get('status') != 'ok':
        return {'status': intent.get('status'), 'calls': []}
    m, t, sliced = intent['metric'], intent.get('time'), bool(intent['dims'] or intent['filters'])
    if m == 'lifecycle_customers':
        return {'status': 'ok', 'calls': [{'view': 'ads.lifecycle_mix_weekly', 'columns': ['as_of_date', 'lifecycle_state', 'customers'], 'where': {}}],
                'post': {'latest_snapshot': True, 'state': intent.get('lifecycle_state')}}
    if m == 'repurchase_rate_30d':
        return {'status': 'ok', 'calls': [{'view': 'ads.repurchase_rate_weekly', 'columns': ['as_of_date', 'population', 'repurchasers', 'repurchase_rate_30d'], 'where': {}}],
                'post': {'latest_matured': True}}
    if m == 'cohort_retention_rate':
        return {'status': 'ok', 'calls': [{'view': 'ads.cohort_retention', 'columns': ['cohort_month', 'months_since_first', 'cohort_customers', 'active_customers', 'retention_rate', 'immature'], 'where': {}}],
                'post': {'months_since_first': 1, 'exclude_immature': True}}
    months = _months(t['start'], t['end']) if t['grain'] != 'day' else None
    periods = [{'label': 'current', 'months': months, 'days': None if months else list(t and (t['start'], t['end']))}]
    if intent.get('compare') and months:
        k = 12 if intent['compare'] == 'yoy' else len(months)
        periods.append({'label': 'base', 'months': [_shift(x, -k) for x in months], 'days': None})
    elif intent.get('compare') == 'mom' and t['grain'] == 'day':            # week (or day) on the previous span of equal length
        from datetime import date
        a, b = date.fromisoformat(t['start']), date.fromisoformat(t['end'])
        periods.append({'label': 'base', 'months': None, 'days': [(a - (b - a)).isoformat(), t['start']]})
    if sliced:
        cols = ['month', 'product_category', 'customer_region', 'valid_lines', 'merchandise_sales_usd'] + (['orders_containing'] if m == 'valid_lines' else [])
        call = {'view': 'ads.sales_month_category_region', 'columns': cols, 'where': {}}
        group = intent['dims'] or []
    elif t['grain'] == 'day':
        call = {'view': 'ads.kpi_daily', 'columns': ['day', 'valid_orders', 'merchandise_sales_usd', 'shipping_usd'], 'where': {}}
        group = []
    else:
        call = {'view': 'ads.kpi_monthly', 'columns': ['month', 'valid_orders', 'merchandise_sales_usd', 'shipping_usd', 'buyers', 'cancelled_orders', 'partial_period'], 'where': {}}
        group = []
    return {'status': 'ok', 'calls': [call], 'post': {'periods': periods, 'filters': intent['filters'], 'group_by': group,
            'by_month': intent['kind'] == 'trend' and intent.get('grain') == 'month', 'by_day': intent.get('grain') == 'day',
            'measure': m, 'aov_recomputed_from_sums': m == 'aov_usd', 'rank': {'top_n': intent.get('top_n'), 'descending': intent.get('descending', True)} if intent['kind'] == 'ranking' else None,
            'share': intent['kind'] == 'share', 'compare': intent.get('compare')}}


LLM_SCHEMA_HELP = ('只输出 JSON：{"metric": 指标id, "dims": [维度id], "filters": {"product_category": [品类英文名], "customer_region": [大区英文名]}, '
                   '"time": {"start": "YYYY-MM", "end": "YYYY-MM", "grain": "month|quarter|year|all", "label": 文本} 或 null, '
                   '"kind": "value|trend|ranking|comparison|share", "compare": "yoy|mom|null", "top_n": 整数或 null}。')


def parse_llm(question: str, client=None) -> dict:
    """Optional LLM path: the model fills the intent JSON; validate_intent() decides whether it can be used."""
    from client import LLMClient
    client = client or LLMClient()
    catalog = {'metrics': {k: v[0] for k, v in METRICS.items()}, 'dims': {'product_category': '品类', 'customer_region': '客户大区'},
               'product_category': CATEGORIES, 'customer_region': list(REGIONS.values()),
               'time_rules': f'数据 2024-01 至 2026-11-07；as_of 2026-11-08；上个月={LAST_FULL_MONTH}；去年=2025'}
    msgs = [{'role': 'system', 'content': '把经营问题解析为结构化意图，只能使用目录中的指标、维度和枚举值；无法判断时 metric 写 null。' + LLM_SCHEMA_HELP},
            {'role': 'user', 'content': '目录：' + json.dumps(catalog, ensure_ascii=False) + '\n问题：' + question}]
    r = client.chat(msgs, json_schema={'required': ['metric', 'kind']}, max_tokens=250, purpose='query_intent')
    if r['status'] != 'ok':
        return {'question': question, 'parser': 'llm', 'status': 'clarify', 'clarification': '暂时无法解析该问题，请换一种说法或使用示例问题。', 'llm_error': r.get('error')}
    j = r['json']
    intent = {'question': question, 'parser': 'llm', 'metric': j.get('metric'), 'dims': j.get('dims') or [], 'filters': j.get('filters') or {},
              'time': j.get('time'), 'kind': j.get('kind'), 'compare': j.get('compare') if j.get('compare') not in ('null', '') else None,
              'top_n': j.get('top_n'), 'grain': 'month' if j.get('kind') == 'trend' else None, 'descending': True}
    if intent['metric'] is None:
        return {**intent, 'status': 'clarify', 'clarification': '没有识别出指标，请换一种说法。'}
    v = validate_intent(intent)
    if v['status'] == 'unsupported':
        v['status'], v['clarification'] = 'clarify', f"模型给出的意图未通过目录校验（{v['error']['message']}），请换一种说法。"
    return v


def understand(question: str, use_llm: bool = True, client=None) -> dict:
    """Rules first; only questions the rules cannot place (no metric found) go to the LLM path."""
    r = parse(question)
    if use_llm and r['status'] == 'clarify' and r.get('metric') is None and not any(re.search(p, question) for p in AMBIGUOUS):
        return parse_llm(question, client)
    return r
