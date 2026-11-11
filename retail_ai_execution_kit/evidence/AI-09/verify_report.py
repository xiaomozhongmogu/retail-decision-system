"""AI-09 verification: fixtures for validation, repair limit and fallback (no network), then one live run.
usage: .venv/bin/python evidence/AI-09/verify_report.py"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/ai'))
import report_generator as G  # noqa: E402
from report_facts import build_weekly_facts  # noqa: E402

ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, '' if cond else str(detail)[:300])


class Fake:
    def __init__(self, texts):
        self.texts, self.calls = list(texts), 0

    def chat(self, msgs, **kw):
        self.calls += 1
        t = self.texts.pop(0) if self.texts else ''
        return {'status': 'ok', 'text': t, 'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'cost_usd': 0}}


facts = build_weekly_facts()
sel = G.pick_facts(facts)
good = json.dumps({'explanation': '本周商品金额为 {{F01}}，环比 {{F04}}。', 'actions': ['分开跟踪订单与客单价'], 'hypotheses': ['待验证：变化与订单数增加有关']}, ensure_ascii=False)
r = G.generate_weekly_report(facts, client=Fake([good]), mode='live')
check('valid LLM text accepted; numbers substituted from facts; mode live', r['mode'] == 'live' and r['status'] == 'ok' and sel[0]['text'] in r['text'] and '{{' not in r['text'])
bad_digit = json.dumps({'explanation': '本周商品金额增长 50%。', 'actions': ['a'], 'hypotheses': ['待验证：x']}, ensure_ascii=False)
bad_cn = json.dumps({'explanation': '相对前八周偏高 {{F08}}。', 'actions': ['a'], 'hypotheses': ['待验证：x']}, ensure_ascii=False)
bad_ph = json.dumps({'explanation': '本周 {{F99}}。', 'actions': ['a'], 'hypotheses': ['待验证：x']}, ensure_ascii=False)
bad_cause = json.dumps({'explanation': '本周金额上升是由于促销 {{F01}}。', 'actions': ['a'], 'hypotheses': ['促销有效']}, ensure_ascii=False)
check('digits outside placeholders rejected', any('数字' in e for e in G.validate_llm(json.loads(bad_digit), sel)))
check('Chinese numerals with a unit rejected', any('中文数字' in e for e in G.validate_llm(json.loads(bad_cn), sel)))
check('unknown placeholder rejected', any('未知占位符' in e for e in G.validate_llm(json.loads(bad_ph), sel)))
check('unmarked cause in explanation and hypothesis without 待验证 rejected', len(G.validate_llm(json.loads(bad_cause), sel)) == 2)
bad_use = json.dumps({'explanation': '同比（{{F07}} 对应周前同星期）为 {{F07}}，相对前 {{F08}} 周偏高。', 'actions': ['a'], 'hypotheses': ['待验证：x']}, ensure_ascii=False)
e = G.validate_llm(json.loads(bad_use), sel)
check('placeholder misused as another quantity (unit after it, repeated) rejected — seen in live run 2', any('单位或量词' in x for x in e) and any('重复' in x for x in e), e)
bad_sem = json.dumps({'explanation': '相对前 {{F08}} 的基期偏高。', 'actions': ['按渠道拆分订单'], 'hypotheses': ['待验证：x']}, ensure_ascii=False)
e = G.validate_llm(json.loads(bad_sem), sel)
check('placeholder used as a period count and unavailable field (渠道) rejected — seen in live run 4', any('计数或期数' in x for x in e) and any('数据中没有的字段' in x for x in e), e)
f = Fake([bad_digit, good])
r = G.generate_weekly_report(facts, client=f, mode='live')
check('one repair then accepted', r['mode'] == 'live' and [a['result'] for a in r['attempts']] == ['validation_failed', 'ok'] and f.calls == 2)
f = Fake([bad_digit] * 10)
r = G.generate_weekly_report(facts, client=f, mode='live')
check(f'repairs capped at {G.MAX_REPAIRS}: {G.MAX_REPAIRS + 1} calls, then trusted template', f.calls == G.MAX_REPAIRS + 1 and r['mode'] == 'template' and '已回退为可信模板' in r['text'] and r['status'] == 'ok')
r = G.generate_weekly_report(facts, client=Fake(['not json']), mode='live')
check('non-JSON output falls back after the cap', r['mode'] == 'template')
r = G.generate_weekly_report(facts, mode='replay', replay_text=good)
check('replay mode labelled as replay', r['mode'] == 'replay' and '回放（离线记录的 LLM 文本）' in r['text'])
r = G.generate_weekly_report(facts, mode='template')
check('template mode passes the final number check', r['mode'] == 'template' and r['final_check_errors'] == [])
check('final check catches a number not in the facts', G.final_check(r['text'] + '\n本周新增 777 单', sel, facts) == ['最终文本含未知数字 777'])
check('every key number cites its evidence id', all(f"`{x['evidence_id']}`" in r['text'] for x in sel))
from client import LLMClient, Config  # noqa: E402
r = G.generate_weekly_report(facts, client=LLMClient(cfg=Config(), log_path=None), mode='live')
check('LLM unavailable -> template with note, not an error', r['mode'] == 'template' and r['attempts'][0]['result'] == 'llm_error')
live = G.generate_weekly_report(facts, mode='live')
print('live attempts:', json.dumps(live['attempts'], ensure_ascii=False)[:600])
check('live run: real LLM text accepted within the repair cap, final check clean', live['mode'] == 'live' and live['status'] == 'ok' and live['final_check_errors'] == [], live['attempts'])
(ROOT / 'reports/ai/weekly_report_example.md').write_text(live['text'], encoding='utf-8')
(ROOT / 'reports/ai/weekly_report_replay.json').write_text(json.dumps({k: live[k] for k in ('status', 'mode', 'attempts', 'final_check_errors', 'evidence_ids', 'llm_body')}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
r = G.generate_weekly_report(facts, mode='replay', replay_text=json.dumps(live['llm_body'], ensure_ascii=False))
check('the recorded live text replays identically (offline demo)', r['mode'] == 'replay' and r['text'].split('## 关键数字')[1] == live['text'].split('## 关键数字')[1])
print(f'{sum(ok)}/{len(ok)} checks passed')
sys.exit(0 if all(ok) else 1)
