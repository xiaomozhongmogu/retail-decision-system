"""AI-01 smoke: real configuration status (redacted) + fixture tests of the boundaries.
usage: .venv/bin/python evidence/AI-01/client_smoke.py   (writes reports/ai/client_smoke.json)"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/ai'))
from client import Config, LLMClient, TransportError, fixture_transport  # noqa: E402

ok, res = [], []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    res.append({'check': name, 'status': 'passed' if cond else 'failed', 'detail': detail})
    print('PASS' if cond else 'FAIL', name, detail)


live_cfg = Config.from_env()
live = LLMClient(cfg=live_cfg, log_path=None).chat([{'role': 'user', 'content': 'ping'}], purpose='smoke')
real = {'config': live_cfg.redacted(), 'result': live,
        'online_integration_done': live['status'] == 'ok'}
print('real call:', json.dumps(live, ensure_ascii=False))

tmp = Path(tempfile.mkdtemp())
CFG = Config(api_key='sk-test-SECRET123456', base_url='https://example.invalid/v1', model='fixture-model', allow_paid=True,
             max_calls=5, max_cost_usd=0.01, price_in_per_1k=0.001, price_out_per_1k=0.002, max_retries=2)
OKR = {'model': 'fixture-model', 'choices': [{'message': {'content': '{"answer": "ok", "confidence": 0.9}'}}], 'usage': {'prompt_tokens': 100, 'completion_tokens': 20}}
mk = lambda resp, cfg=CFG: LLMClient(cfg=Config(**vars(cfg)), transport=fixture_transport(resp), mode='fixture', log_path=tmp / 'calls.jsonl', sleep=lambda s: None)  # noqa: E731

r = mk([OKR]).chat([{'role': 'user', 'content': 'hi'}], json_schema={'required': ['answer']})
check('fixture success: text, structured JSON, usage and cost recorded', r['status'] == 'ok' and r['json']['answer'] == 'ok' and abs(r['usage']['cost_usd'] - (0.1 * 0.001 + 0.02 * 0.002)) < 1e-12, r['usage'])
bad = {**OKR, 'choices': [{'message': {'content': 'not json'}}]}
r = mk([bad]).chat([{'role': 'user', 'content': 'hi'}], json_schema={'required': ['answer']})
check('invalid structured output is rejected', r['status'] == 'error' and r['error']['code'] == 'invalid_output')
c = mk([TransportError('HTTP 503', True, 503), OKR])
r = c.chat([{'role': 'user', 'content': 'hi'}])
check('retryable error (503) retried once then succeeds', r['status'] == 'ok' and r['attempts'] == 2 and c.calls == 2)
r = mk([TransportError('HTTP 401', False, 401)]).chat([{'role': 'user', 'content': 'hi'}])
check('non-retryable error (401) fails immediately', r['status'] == 'error' and r['error']['retryable'] is False)
c = mk([TransportError('HTTP 429', True, 429)] * 5)
r = c.chat([{'role': 'user', 'content': 'hi'}])
check('retries are limited (max_retries=2 -> 3 attempts) and rate limit reported', r['status'] == 'error' and c.calls == 3 and r['error']['code'] == 'rate_limited', c.calls)
c = mk([TransportError('network: TimeoutError', True)] * 5)
r = c.chat([{'role': 'user', 'content': 'hi'}])
check('timeout reported as timeout', r['error']['code'] == 'timeout')
c = mk([OKR] * 10, Config(**{**vars(CFG), 'max_calls': 2}))
rs = [c.chat([{'role': 'user', 'content': 'hi'}]) for _ in range(3)]
check('call budget: third call refused without calling', [x['status'] for x in rs] == ['ok', 'ok', 'error'] and rs[2]['error']['code'] == 'budget_denied' and c.calls == 2)
c = mk([OKR], Config(**{**vars(CFG), 'max_cost_usd': 0.0005}))
r = c.chat([{'role': 'user', 'content': 'x' * 4000}], max_tokens=400)
check('cost budget: expected cost over the limit is refused before calling', r['error']['code'] == 'budget_denied' and c.calls == 0)
r = LLMClient(cfg=Config(**{**vars(CFG), 'allow_paid': False}), transport=fixture_transport([OKR]), log_path=None).chat([{'role': 'user', 'content': 'hi'}])
check('live mode without paid permission does not call', r['error']['code'] == 'budget_denied')
r = LLMClient(cfg=Config(**{**vars(CFG), 'price_in_per_1k': 0, 'price_out_per_1k': 0}), transport=fixture_transport([OKR]), log_path=None).chat([{'role': 'user', 'content': 'hi'}])
check('live mode with unknown price does not call', r['error']['code'] == 'budget_denied')
r = LLMClient(cfg=Config(), log_path=None).chat([{'role': 'user', 'content': 'hi'}])
check('no key -> llm_unavailable, no network call', r['error']['code'] == 'llm_unavailable')
log = (tmp / 'calls.jsonl').read_text()
check('call log has model, tokens, cost, timing; never the key or the prompt text', 'SECRET' not in log and '"tokens_in"' in log and '"seconds"' in log and 'hi"' not in log)
check('config summary redacts the key', 'SECRET' not in json.dumps(CFG.redacted()))
out = {'task_id': 'AI-01', 'real_call': real, 'fixture_checks': res, 'fixture_checks_passed': all(ok),
       'online_integration': 'done' if real['online_integration_done'] else 'not done: no credentials configured (status in_review)',
       'note': '已安装的 openai SDK 在设置了 SOCKS 代理变量时无法创建客户端（缺 socksio），适配层改用标准库 urllib'}
(ROOT / 'reports/ai/client_smoke.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'{sum(ok)}/{len(ok)} fixture checks passed; online integration done: {real["online_integration_done"]}')
sys.exit(0 if all(ok) else 1)
