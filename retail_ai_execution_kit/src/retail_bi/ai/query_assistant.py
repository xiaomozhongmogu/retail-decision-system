"""AI-06: query assistant — answer = query first, then explain the bounded result (answer_business_question).

Session.ask(question):
  1. understand (AI-04 rules, LLM fallback) — follow-ups ("那西部呢" / "换成订单数" / "去年呢" / "按品类") are merged
     into this session's previous intent; every Session keeps its own state, nothing is global or shared.
  2. plan + run_plan (AI-05, query_view only) -> bounded result.
  3. the answer sentence and table are rendered by code from the result; an optional LLM note (one sentence, no digits,
     no causes, no unavailable fields) is validated and dropped if it fails.
  4. the envelope shows the query (view, columns, filter, SQL text and hash), metric definition, as_of, dataset version,
     status and warnings. Statuses: ok | clarify | unsupported | empty | error | cancelled.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src/retail_bi/ai'))
import query_intent as QI  # noqa: E402
import sql_executor as X  # noqa: E402

AS_OF = '2026-11-08T00:00:00+00:00'
METRIC_DEFS = {m['id']: m for m in json.loads((ROOT / 'contracts/metrics.json').read_text(encoding='utf-8'))['metrics']}
DEF_ID = {'merchandise_sales_usd': 'merchandise_sales_usd', 'valid_orders': 'valid_orders', 'aov_usd': 'aov_usd', 'buyers': 'buyers', 'shipping_usd': 'shipping_usd',
          'cancelled_orders': 'cancelled_orders', 'repurchase_rate_30d': 'repurchase_rate_30d_observed', 'cohort_retention_rate': 'cohort_retention_rate'}
FOLLOW = re.compile(r'^(?:那|那么|换成|改成|如果是|再看|看看)?(.{0,20}?)(?:呢|的呢|怎么样|如何)?[？?。]?$')


def fmt(v, unit):
    if v is None:
        return '—'
    if unit == 'USD':
        return f'{v:,.2f} USD'
    if unit == 'ratio':
        return f'{v * 100:.1f}%'
    return f'{int(round(v)):,}'


class Session:
    def __init__(self, session_id: str, use_llm: bool = True, client=None):
        self.id, self.use_llm, self.client = session_id, use_llm, client
        self.last_intent, self.history, self._cancel = None, [], False

    def cancel(self):
        """Mark the next question as cancelled (e.g. the user pressed stop before execution)."""
        self._cancel = True

    def _follow_up(self, q: str) -> dict | None:
        """Merge a short follow-up into this session's previous intent; None when it is a new question."""
        if self.last_intent is None or self.last_intent.get('status') != 'ok':
            return None
        fresh = QI.parse(q)
        if fresh['status'] == 'ok' and fresh.get('time') and fresh.get('metric'):
            return None                                       # a complete new question
        if not (FOLLOW.match(q.strip()) and len(q.strip()) <= 24):
            return None
        it = copy.deepcopy(self.last_intent)
        it['question'], it['parser'], it['follow_up_of'] = q, 'follow_up', self.last_intent['question']
        m = next((k for k in ('cancelled_orders', 'aov_usd', 'shipping_usd', 'buyers', 'valid_lines', 'merchandise_sales_usd', 'valid_orders')
                  if re.search(QI.METRICS[k][2], q)), None)
        if m:
            it['metric'] = m
        t = QI.parse_time(q)
        if t:
            it['time'] = t
        probe = QI.parse('2025年商品金额' + q)                  # reuse the rule parser for filters and dims in the fragment
        if probe.get('filters'):
            it['filters'] = {**{k: v for k, v in it['filters'].items() if k not in probe['filters']}, **probe['filters']}
        if probe.get('dims'):
            it['dims'] = probe['dims']
        if not (m or t or probe.get('filters') or probe.get('dims')):
            return None
        return QI.validate_intent({k: v for k, v in it.items() if k not in ('status', 'warnings', 'error', 'clarification')})

    def ask(self, question: str) -> dict:
        env = {'session_id': self.id, 'question': question, 'as_of': AS_OF, 'mode': 'live'}
        if self._cancel:
            self._cancel = False
            out = {**env, 'status': 'cancelled', 'answer': '已取消，本次没有执行查询。'}
            self.history.append(out)
            return out
        intent = self._follow_up(question) or QI.understand(question, use_llm=self.use_llm, client=self.client)
        env['intent'] = {k: intent.get(k) for k in ('parser', 'metric', 'kind', 'dims', 'filters', 'time', 'compare', 'top_n', 'follow_up_of')}
        if intent['status'] in ('clarify', 'unsupported', 'empty'):
            msg = intent.get('clarification') or (intent.get('error') or {}).get('message')
            out = {**env, 'status': intent['status'], 'answer': msg, 'error': intent.get('error')}
            if intent['status'] == 'empty':
                out['answer'] = f'没有数据：{msg}'
            self.history.append(out)
            return out
        plan = QI.plan(intent)
        try:
            res = X.run_plan(plan)
        except Exception as e:                                  # execution failure is a state, never a made-up answer
            out = {**env, 'status': 'error', 'answer': '查询执行失败，没有结果可以解释。', 'error': {'code': 'error', 'message': type(e).__name__, 'retryable': True}}
            self.history.append(out)
            return out
        call = plan['calls'][0]
        import report_facts as RF
        env['query'] = {'view': call['view'], 'columns': call['columns'], 'where': call['where'], 'sql': RF.view_sql(call['view'], call['columns'], call['where'] or None),
                        'post_processing': {k: v for k, v in plan.get('post', {}).items() if k != 'periods'},
                        'periods': [p.get('months') or p.get('days') for p in plan.get('post', {}).get('periods', [])]}
        d = METRIC_DEFS.get(DEF_ID.get(intent['metric'], ''), {})
        env['metric_definition'] = {'id': intent['metric'], 'name': QI.METRICS[intent['metric']][0], 'unit': QI.METRICS[intent['metric']][1], 'definition': d.get('definition')}
        env['dataset_version'], env['evidence_ids'] = res.get('dataset_version'), res.get('evidence_ids', [])
        env['warnings'] = (intent.get('warnings') or []) + (res.get('warnings') or [])
        if res.get('status') != 'ok':
            out = {**env, 'status': res.get('status', 'error'), 'answer': '所选条件没有数据。' if res.get('status') == 'empty' else '查询没有返回结果。', 'result': res}
            self.history.append(out)
            return out
        env.update({'status': 'ok', 'result': {k: res[k] for k in res if k in ('kind', 'value', 'columns', 'rows', 'base_value', 'base_months', 'change', 'change_status', 'n', 'as_of', 'cohorts', 'note')},
                    'answer': self._sentence(intent, res)})
        note = self._llm_note(intent, env['answer']) if self.use_llm else None
        if note:
            env['note'] = note
        self.last_intent = intent
        self.history.append(env)
        return env

    @staticmethod
    def _sentence(intent, res) -> str:
        name, unit = QI.METRICS[intent['metric']][:2]
        t = (intent.get('time') or {}).get('label', '最新快照')
        flt = '、'.join(v for vs in intent['filters'].values() for v in vs)
        scope = f'{t}{"（" + flt + "）" if flt else ""}'
        k = res['kind']
        if k == 'value' and 'change' in res:
            ch = '无法计算（基期为 0）' if res['change_status'] == 'zero_denominator' else fmt(res['change'], 'ratio') if res['change'] is not None else '无法计算'
            cmp = '同比' if intent.get('compare') == 'yoy' else '环比'
            return f"{scope}{name}为 {fmt(res['value'], unit)}；{cmp}基期（{'、'.join(res['base_months'])}）为 {fmt(res['base_value'], unit)}，变化 {ch}。"
        if k == 'value':
            extra = f"（样本 {res['n']:,} 人，as_of {res['as_of']}）" if res.get('n') and res.get('as_of') else (f"（{res['cohorts']} 个成熟 cohort，共 {res['n']:,} 人）" if res.get('cohorts') else '')
            return f"{scope}{name}为 {fmt(res['value'], unit)}{extra}。"
        if k == 'series':
            pts = '；'.join(f'{a} {fmt(b, unit)}' for a, b in res['rows'][:12])
            return f"{scope}{name}：{pts}{'……' if len(res['rows']) > 12 else ''}。"
        if 'lifecycle_state' in res.get('columns', []):
            zh = {'new': '新客', 'active': '活跃', 'at_risk': '沉默预警', 'dormant': '沉睡'}
            return f"最新快照（{res.get('as_of')}）生命周期人数：" + '，'.join(f"{zh.get(a, a)} {b:,}" for a, b in res['rows']) + '。'
        if res.get('columns', [])[-1] == 'share':
            return f"{scope}{name}占比：" + '；'.join(f"{r[0]} {fmt(r[-2], unit)}（{fmt(r[-1], 'ratio')}）" for r in res['rows']) + '。'
        lab = '、'.join(intent['dims'])
        return f"{scope}按{'品类' if lab == 'product_category' else '客户大区' if lab == 'customer_region' else lab}的{name}" + \
               ('排名' if intent['kind'] == 'ranking' else '') + '：' + '；'.join(f"{' / '.join(map(str, r[:-1]))} {fmt(r[-1], unit)}" for r in res['rows']) + '。'

    def _llm_note(self, intent, answer):
        """One explanatory sentence with no digits; validated, dropped on failure (never blocks the answer)."""
        try:
            from client import LLMClient
            import report_generator as G
            c = self.client or LLMClient()
            r = c.chat([{'role': 'system', 'content': '你给经营查询结果补一句口径提示。只输出 JSON {"note": 字符串}。不写任何数字，不推测原因，'
                         '不提数据中没有的字段（渠道、毛利、库存、广告），数据是完全合成的模拟数据。'},
                        {'role': 'user', 'content': f'问题：{intent["question"]}\n已给出的答案：{answer}\n指标口径：{QI.METRICS[intent["metric"]][0]}，单位 {QI.METRICS[intent["metric"]][1]}'}],
                       json_schema={'required': ['note']}, max_tokens=120, purpose='query_note')
            if r['status'] != 'ok':
                return None
            n = str(r['json']['note'])
            if re.search(r'[0-9%％]', n) or G.CN_NUM.search(n) or G.CAUSE.search(n) or G.UNAVAILABLE.search(n) or G.semantic_flags(n) or len(n) > 120:
                return None
            return n
        except Exception:
            return None


if __name__ == '__main__':
    s = Session('demo')
    out = [s.ask(q) for q in ['2026年10月的商品金额是多少？', '那西部呢', '换成订单数', '2025年哪个品类的商品金额最高？']]
    print(json.dumps([{k: o.get(k) for k in ('status', 'answer', 'note')} for o in out], ensure_ascii=False, indent=1))
