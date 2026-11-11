"""AI-10: build the blind-review packet described in eval/blind_test_plan.md.

Writes eval/blind_packet/ (give to the reviewer: README, knowledge.md, facts_S*.json, reports/R01..R24.md) and
eval/blind_key/answer_key.json (keep: scenario, generation mode, planted errors, our checker's result per report).
usage: .venv/bin/python eval/make_blind_packet.py
"""
import json
import random
import re
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/retail_bi/ai'))
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
import report_facts as RF  # noqa: E402
import report_generator as G  # noqa: E402
from runtime import pointer, query_view  # noqa: E402

PK, KEY = ROOT / 'eval/blind_packet', ROOT / 'eval/blind_key'
rows = lambda v: [dict(zip(r['columns'], x)) for x in r['rows']] if (r := query_view(v))['status'] == 'ok' else []  # noqa: E731
BASE = {k: rows(v) for k, v in [('daily', 'ads.kpi_daily'), ('monthly', 'ads.kpi_monthly'), ('catreg', 'ads.sales_month_category_region'),
                                 ('lifecycle', 'ads.lifecycle_mix_weekly'), ('repurchase', 'ads.repurchase_rate_weekly')]}
PTR = pointer()


def envelope(data, label):
    return {'status': 'ok', 'data': {'facts_version': RF.FACTS_VERSION, **{k: v for k, v in data.items() if k != 'warnings'}},
            'window': data['periods']['report_week'], 'dataset_version': f'src=synthetic;rel={PTR["version"]};scenario={label}',
            'metric_version': RF.metric_version(), 'mode': 'fixture' if label != 'S01' else 'live', 'warnings': data['warnings']}


def scale_days(daily, start, end, f):
    out = []
    for r in daily:
        d = date.fromisoformat(r['day'])
        if start <= d < end:
            o = int(round(int(r['valid_orders']) * f))
            if o == 0:
                continue
            k = Decimal(o) / Decimal(r['valid_orders'])
            r = {**r, 'valid_orders': str(o), 'merchandise_sales_usd': str((Decimal(r['merchandise_sales_usd']) * k).quantize(Decimal('0.01'))),
                 'shipping_usd': str((Decimal(r['shipping_usd']) * k).quantize(Decimal('0.01')))}
        out.append(r)
    return out


W0, W1, P0 = date(2026, 10, 31), date(2026, 11, 7), date(2026, 10, 24)
SCEN = {
    'S01': ('正常周（真实发布数据）', None),
    'S02': ('环比下降（报告周订单按 0.55 倍缩小）', lambda b: {**b, 'daily': scale_days(b['daily'], W0, W1, 0.55)}),
    'S03': ('分母为 0（上一周没有有效订单）', lambda b: {**b, 'daily': [r for r in b['daily'] if not (P0 <= date.fromisoformat(r['day']) < W0)]}),
    'S04': ('小样本（每天只有 1–2 单）', lambda b: {**b, 'daily': scale_days(b['daily'], date(2024, 1, 1), date(2026, 11, 8), 0.15)}),
    'S05': ('不完整周期（as_of = 2026-10-15，10 月未结束）', 'as_of'),
}


def facts_for(sid):
    label, f = SCEN[sid]
    if f is None:
        return RF.build_weekly_facts()
    if f == 'as_of':
        a = date(2026, 10, 15)
        daily = [r for r in BASE['daily'] if date.fromisoformat(r['day']) < a]
        oct_ = [r for r in daily if r['day'].startswith('2026-10')]
        mon = [r for r in BASE['monthly'] if r['month'] < '2026-10'] + [{'month': '2026-10', 'valid_orders': str(sum(int(r['valid_orders']) for r in oct_)),
               'merchandise_sales_usd': str(sum(Decimal(r['merchandise_sales_usd']) for r in oct_)), 'buyers': str(sum(int(r['valid_orders']) for r in oct_)),
               'aov_usd': '0', 'partial_period': 'True'}]
        data = RF.compute(daily, mon, [r for r in BASE['catreg'] if r['month'] < '2026-10'],
                          [r for r in BASE['lifecycle'] if r['as_of_date'] < '2026-10-15'], [r for r in BASE['repurchase'] if r['as_of_date'] < '2026-09-14'],
                          as_of=a, dataset_version=PTR['version'], mversion=RF.metric_version())
        return envelope(data, sid)
    b = f(dict(BASE))
    return envelope(RF.compute(**b, dataset_version=PTR['version'], mversion=RF.metric_version()), sid)


def compact(facts):
    keep = ('evidence_id', 'metric', 'label', 'value', 'unit', 'window', 'compare_window', 'status', 'sample_size', 'total_change')
    return {'scenario_note': '完全合成的模拟数据；本文件是该场景周报唯一的数字依据', 'periods': facts['data']['periods'], 'warnings': facts['warnings'],
            'facts': [{k: f[k] for k in keep if k in f} for f in facts['data']['facts'] if not isinstance(f['value'], (list, dict)) or f['metric'].startswith('split')]}


def our_check(text, sel, facts):
    """Our deterministic checks on a final report text (as the system would run them)."""
    errs = G.final_check(text, sel, facts)
    expl = text.split('## 解释', 1)[-1].split('## 行动建议', 1)[0]
    errs += [f'解释中的原因推测未标待验证：{s[:20]}' for s in re.split(r'[。；\n]', expl) if G.CAUSE.search(s) and '待验证' not in s]
    body = text.split('## 解释', 1)[-1].split('## 提示', 1)[0]
    if G.UNAVAILABLE.search(body):
        errs.append('提到数据中没有的字段')
    ids = {x['evidence_id'] for x in sel}
    errs += [f'未知 evidence_id {e}' for e in re.findall(r'fact:[0-9a-f]{8}', text) if e not in ids and e not in {f['evidence_id'] for f in facts['data']['facts']}]
    return errs


PLANTS = [  # (type, scenario, function(text, sel) -> new text, description)
    ('数字', 'S01', lambda t, s: t.replace(s[0]['text'].split()[0], s[0]['text'].split()[0].replace('3', '6', 1), 1), '本周商品金额的一个数字被改动'),
    ('单位', 'S01', lambda t, s: t.replace(' USD', ' 元', 1), '第一个 USD 改为“元”'),
    ('窗口', 'S02', lambda t, s: t.replace('2026-10-31 至', '2026-10-30 至', 1), '标题中报告周起始日改早一天'),
    ('引用', 'S02', lambda t, s: t.replace(s[1]['evidence_id'], 'fact:0badc0de', 1), '关键数字表中一个 evidence_id 换成不存在的编号'),
    ('因果', 'S01', lambda t, s: t.replace('## 行动建议', '本周金额上升是因为促销活动效果显著。\n\n## 行动建议', 1), '解释末尾加入未标待验证的因果结论'),
    ('不存在字段', 'S02', lambda t, s: t.replace('## 待验证假设', '- 建议按渠道拆分本周订单，找出贡献最大的投放渠道。\n\n## 待验证假设', 1), '行动建议中加入按渠道拆分'),
    ('不完整周期', 'S05', lambda t, s: t.replace('## 行动建议', '本月商品金额已经低于上月全月，月度业绩明显下滑。\n\n## 行动建议', 1), '把未结束的 10 月与 9 月全月直接比较'),
    ('特殊情况处理', 'S03', lambda t, s: t.replace('## 行动建议', '商品金额环比增长 0%，与上周持平。\n\n## 行动建议', 1), '分母为 0 时写成“环比增长 0%，与上周持平”'),
]


def main():
    (PK / 'reports').mkdir(parents=True, exist_ok=True)
    KEY.mkdir(parents=True, exist_ok=True)
    items = []
    for sid in SCEN:
        facts = facts_for(sid)
        (PK / f'facts_{sid}.json').write_text(json.dumps(compact(facts), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        modes = ['live', 'live', 'template'] + (['live'] if sid == 'S01' else [])
        for m in modes:
            r = G.generate_weekly_report(facts, mode=m)
            sel = G.pick_facts(facts)
            items.append({'scenario': sid, 'mode_requested': m, 'mode_used': r['mode'], 'text': r['text'], 'sel': sel, 'facts': facts,
                          'generator_status': r['status'], 'attempts': len(r['attempts']), 'planted': []})
    base = {sid: next(i for i in items if i['scenario'] == sid and i['mode_used'] == 'live' and i['generator_status'] == 'ok')
            for sid in SCEN if any(i['scenario'] == sid and i['mode_used'] == 'live' for i in items)}
    for typ, sid, fn, desc in PLANTS:
        src = base.get(sid) or next(i for i in items if i['scenario'] == sid)
        new = fn(src['text'], src['sel'])
        assert new != src['text'], (typ, sid)
        items.append({**src, 'text': new, 'planted': [{'type': typ, 'description': desc}], 'mode_used': src['mode_used'] + '+planted'})
    random.Random(20261111).shuffle(items)
    key = []
    for n, it in enumerate(items, 1):
        rid = f'R{n:02d}'
        text = it['text'].replace('\n- 数据：', f"\n- 对应事实表：facts_{it['scenario']}.json\n- 数据：", 1)
        text = re.sub(r'\n- 生成模式：[^\n]*', '', text, count=1)      # hide the generation mode from the reviewer
        (PK / 'reports' / f'{rid}.md').write_text(text, encoding='utf-8')
        key.append({'report': rid, 'scenario': it['scenario'], 'scenario_label': SCEN[it['scenario']][0], 'generation': it['mode_used'],
                    'generator_status': it['generator_status'], 'llm_attempts': it['attempts'], 'planted_errors': it['planted'],
                    'our_checker_flags': our_check(text, it['sel'], it['facts'])})
    kn = ['# 口径规则摘录（审查依据）', '', '数据是完全合成的模拟电商数据，截止 2026-11-08（不含），金额单位 USD。', '',
          '1. 有效购买 = 截止前已审批的订单（approved_ts < as_of）；已取消订单没有审批，不计入；下单到审批最长 24 小时，所以截止前最后一天的订单可能尚未审批，该日单独列出，不参与比较。（docs/transaction_rules.md §1–§2）',
          '2. 商品金额 = 有效订单的商品金额，不含运费；运费单列。客单价 = 商品金额合计 ÷ 有效订单数，不对各期客单价取平均。（contracts/metrics.json）',
          '3. 比较期间：环比 = 上一个 7 天；同比 = 52 周前的同星期；分母为 0 时比率为空并标 zero_denominator，基期订单少于 30 单时增长率不给出（small_sample）；不完整期间（partial_period / incomplete_period）不与完整期间直接比较。（AI-08 事实规则）',
          '4. 数据中没有的字段：渠道与营销投放、毛利与成本、库存、优惠券、广告、浏览与加购、客户年龄与性别。涉及这些的分析或建议都没有依据。（docs/data_dictionary.md §4、docs/business_scope.md §4）',
          '5. 原因推测必须标为“待验证”，数据只支持相关与分解，不支持因果结论。（docs/business_scope.md）', '',
          '每份周报头部写明对应的事实表文件；周报中的每个数字都应能在该事实表中找到（允许千分位与两位小数的格式差异，比例以百分数显示）。']
    (PK / 'knowledge.md').write_text('\n'.join(kn) + '\n', encoding='utf-8')
    plan = (ROOT / 'eval/blind_test_plan.md').read_text(encoding='utf-8')
    instr = plan.split('## 3. 交给 GPT 的指令（直接复制）', 1)[1].split('## 4.', 1)[0].strip()
    instr = '\n'.join(l[2:] if l.startswith('> ') else ('' if l == '>' else l) for l in instr.splitlines())
    (PK / 'README_给审查者.md').write_text('# 审查任务说明\n\n' + instr + '\n\n文件清单：knowledge.md、facts_S01.json 至 facts_S05.json、reports/R01.md 至 R24.md。\n', encoding='utf-8')
    one = ['# 周报盲测材料（合并版，便于一次上传）', '', (PK / 'README_给审查者.md').read_text(encoding='utf-8'), '', (PK / 'knowledge.md').read_text(encoding='utf-8')]
    for sid in SCEN:
        one += ['', f'## facts_{sid}.json', '', '```json', (PK / f'facts_{sid}.json').read_text(encoding='utf-8').strip(), '```']
    for n in range(1, len(items) + 1):
        one += ['', f'## 周报 R{n:02d}', '', (PK / 'reports' / f'R{n:02d}.md').read_text(encoding='utf-8').strip()]
    (PK / 'ALL_IN_ONE.md').write_text('\n'.join(one) + '\n', encoding='utf-8')
    (KEY / 'answer_key.json').write_text(json.dumps({'note': '不要交给审查者', 'reports': key}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(len(items), 'reports;', sum(bool(k['planted_errors']) for k in key), 'planted;',
          {m: sum(k['generation'].startswith(m) for k in key) for m in ('live', 'template', 'replay')})
    for k in key:
        print(k['report'], k['scenario'], k['generation'], k['generator_status'], [p['type'] for p in k['planted_errors']], len(k['our_checker_flags']))


if __name__ == '__main__':
    main()
