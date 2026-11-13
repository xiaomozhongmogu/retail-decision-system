"""AI-06 check: answers come from executed queries (vs DWD), envelope shows query/definition/as_of/version, explicit
states for empty/cancel/out-of-range/error, multi-turn follow-ups and session isolation, LLM note has no numbers.
usage: .venv/bin/python evidence/AI-06/check_assistant.py   (writes reports/ai/query_examples.json)"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/ai'))
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
import query_assistant as QA  # noqa: E402
import sql_executor as X  # noqa: E402
from runtime import open_current  # noqa: E402

ok, examples = [], []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, '' if cond else str(detail)[:300])


def keep(o):
    examples.append({k: o.get(k) for k in ('session_id', 'question', 'status', 'answer', 'note', 'intent', 'query', 'metric_definition', 'as_of', 'dataset_version', 'evidence_ids', 'warnings', 'result', 'error')})
    return o


con, _ = open_current()
V = "approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'"
q1 = lambda s: con.execute(s).fetchone()  # noqa: E731
s = QA.Session('A')
a = keep(s.ask('2026年10月的商品金额是多少？'))
want = float(q1(f"SELECT sum(merch_usd) FROM dwd.fact_order WHERE {V} AND strftime(purchase_ts,'%Y-%m')='2026-10'")[0])
check('answer value comes from the executed query and equals DWD', a['status'] == 'ok' and abs(a['result']['value'] - want) < 0.005 and f'{want:,.2f} USD' in a['answer'], a['answer'])
check('envelope shows view, columns, SQL text, metric definition, as_of, dataset version, evidence ids',
      a['query']['view'] == 'ads.kpi_monthly' and a['query']['sql'].startswith('SELECT') and a['metric_definition']['definition'] and a['as_of'].startswith('2026-11-08')
      and a['dataset_version'] == 'wh-d3aaa559048c' and a['evidence_ids'], a.get('query'))
b = keep(s.ask('那西部呢'))
wb = float(q1(f"""SELECT sum(l.item_price_usd) FROM dwd.fact_order_line l JOIN dwd.fact_order o USING (order_id) JOIN dwd.dim_customer c ON c.customer_id=l.customer_id
                  WHERE o.{V} AND strftime(o.purchase_ts,'%Y-%m')='2026-10' AND c.customer_region='West'""")[0])
check('follow-up “那西部呢” reuses time and metric, adds the region filter, value = DWD', b['status'] == 'ok' and b['intent']['parser'] == 'follow_up'
      and b['intent']['filters'] == {'customer_region': ['West']} and abs(b['result']['value'] - wb) < 0.005, b)
c = keep(s.ask('换成订单数'))
check('follow-up to a metric that has no region view is refused, not guessed', c['status'] == 'unsupported', c)
d = keep(s.ask('去年呢'))
w25 = float(q1(f"""SELECT sum(l.item_price_usd) FROM dwd.fact_order_line l JOIN dwd.fact_order o USING (order_id) JOIN dwd.dim_customer c ON c.customer_id=l.customer_id
                   WHERE o.{V} AND strftime(o.purchase_ts,'%Y-%m')='2025-10' AND c.customer_region='West'""")[0])
# since the external test (G-026) “去年呢 / 上个月呢” shift the previous turn's period (2026-10 -> 2025-10), not as_of
check('follow-up “去年呢” keeps the last valid intent (West, merchandise) and shifts its month back a year', d['status'] == 'ok'
      and d['intent']['time']['start'] == '2025-10' and abs(d['result']['value'] - w25) < 0.005, d)
s2 = QA.Session('B')
e = keep(s2.ask('那西部呢'))
check('session isolation: the same follow-up in a new session is not answered from session A', e['status'] in ('clarify', 'unsupported') and s2.last_intent is None, e)
f = keep(QA.Session('C').ask('2023年的商品金额'))
check('time not covered -> empty with explanation, no numbers made up', f['status'] == 'empty' and '没有数据' in f['answer'] and not re.search(r'\d+\.\d\d', f['answer']), f)
g = keep(QA.Session('D').ask('各品类的毛利是多少'))
check('unsupported field -> unsupported state', g['status'] == 'unsupported', g)
h = keep(QA.Session('E').ask('2025年的收入是多少'))
check('ambiguous -> clarify', h['status'] == 'clarify', h)
s3 = QA.Session('F')
s3.cancel()
i = keep(s3.ask('2026年10月的商品金额是多少？'))
check('cancelled before execution -> cancelled, no query run', i['status'] == 'cancelled' and 'query' not in i, i)
j = s3.ask('2026年10月的商品金额是多少？')
check('cancel applies only once; next question runs', j['status'] == 'ok')
orig = X.run_plan
X.run_plan = lambda plan: (_ for _ in ()).throw(RuntimeError('db down'))
k = keep(QA.Session('G').ask('2026年10月的商品金额是多少？'))
X.run_plan = orig
check('execution error -> error state with no answer numbers', k['status'] == 'error' and not re.search(r'\d', k['answer']), k)
l = keep(QA.Session('H').ask('2026年10月商品金额同比变化'))
b25 = float(q1(f"SELECT sum(merch_usd) FROM dwd.fact_order WHERE {V} AND strftime(purchase_ts,'%Y-%m')='2025-10'")[0])
check('comparison answer states base period and change from executed values', l['status'] == 'ok' and abs(l['result']['base_value'] - b25) < 0.005 and '2025-10' in l['answer'], l['answer'])
m = keep(QA.Session('I').ask('现在沉睡客户有多少'))
check('lifecycle answer from the latest snapshot (named state -> its count, since AI-07)', m['status'] == 'ok' and '沉睡客户 2,098 人' in m['answer'] and '不表示流失' in m['answer'], m['answer'])
n = keep(QA.Session('J').ask('2025年各大区商品金额占比'))
check('share answer lists four regions with percentages', n['status'] == 'ok' and n['answer'].count('%') == 4, n['answer'])
notes = [x.get('note') for x in examples if x.get('note')]
check('LLM notes (when present) contain no digits', all(not re.search(r'[0-9%]', x) for x in notes), notes)
check('every ok answer carries evidence ids and a dataset version', all(x['evidence_ids'] and x['dataset_version'] for x in examples if x['status'] == 'ok'))
con.close()
(ROOT / 'reports/ai/query_examples.json').write_text(json.dumps({'task_id': 'AI-06', 'examples': examples}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print(f'{sum(ok)}/{len(ok)} checks passed; {len(notes)} LLM notes kept')
sys.exit(0 if all(ok) else 1)
