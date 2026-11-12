"""AI-07: fixed NL2SQL benchmark for the query assistant (AI-06), scored by result semantics against gold SQL on DWD.
Gold answers come from independent SQL on the detail tables (not the ADS views the assistant uses).
usage: .venv/bin/python eval/nl2sql_eval.py [--tag NAME]   (writes reports/ai/nl2sql_evaluation.json)"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/retail_bi/ai'))
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
import query_assistant as QA  # noqa: E402
from runtime import open_current  # noqa: E402

TOL = 0.006


def close(a, b):
    return a is not None and b is not None and abs(float(a) - float(b)) <= max(TOL, abs(float(b)) * 1e-9)


def judge(case, ans, gold):
    c = case['compare']
    if ans['status'] != 'ok':
        return False, f"status {ans['status']}"
    r = ans['result']
    if c == 'value':
        return close(r.get('value'), gold[0][0]), f"{r.get('value')} vs {gold[0][0]}"
    if c == 'series':
        got = [(str(k), v) for k, v in r.get('rows', [])]
        return len(got) == len(gold) and all(str(a) == str(g[0]) and close(b, g[1]) for (a, b), g in zip(got, gold)), f'{got[:3]} vs {gold[:3]}'
    if c == 'top1':
        return bool(r.get('rows')) and r['rows'][0][0] == gold[0][0] and close(r['rows'][0][-1], gold[0][1]), f"{r.get('rows', [])[:1]} vs {gold[0]}"
    if c == 'rows':
        got = r.get('rows', [])
        return len(got) == len(gold) and all(a[0] == g[0] and close(a[-1], g[1]) for a, g in zip(got, gold)), f'{got[:2]} vs {gold[:2]}'
    if c == 'share':
        tot = sum(float(g[1]) for g in gold)
        want = {g[0]: float(g[1]) / tot for g in gold}
        got = {x[0]: x[-1] for x in r.get('rows', [])}
        return set(got) == set(want) and all(abs(got[k] - want[k]) < 1e-9 for k in want), f'{len(got)} vs {len(want)}'
    if c == 'compare':
        v, b = gold[0]
        return close(r.get('value'), v) and close(r.get('base_value'), b) and abs(r['change'] - (float(v) - float(b)) / float(b)) < 1e-9, f"{r.get('value')},{r.get('base_value')} vs {v},{b}"
    return False, 'unknown compare'


def main():
    tag = sys.argv[sys.argv.index('--tag') + 1] if '--tag' in sys.argv else 'run'
    cases = [json.loads(l) for l in (ROOT / 'eval/nl2sql_cases.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    con, _ = open_current()
    rows = []
    for c in cases:
        s = QA.Session(c['id'], use_llm=True)
        a = s.ask(c['question'])
        if c['type'] == 'answerable':
            gold = [list(x) for x in con.execute(c['gold_sql_on_dwd']).fetchall()]
            ok, why = judge(c, a, gold)
        elif c['type'] == 'ambiguous':
            ok, why = a['status'] == 'clarify', a['status']
        elif c['type'] == 'no_data':
            ok, why = a['status'] == 'empty', a['status']
        else:
            ok, why = a['status'] in ('unsupported', 'clarify', 'empty') and 'query' not in a, a['status']
        rows.append({'id': c['id'], 'type': c['type'], 'question': c['question'], 'status': a['status'], 'pass': ok, 'detail': why[:200] if isinstance(why, str) else why,
                     'answer': (a.get('answer') or '')[:200], 'parser': (a.get('intent') or {}).get('parser'), 'executed': 'query' in a})
        print('PASS' if ok else 'FAIL', c['id'], c['question'], '|', a['status'], '|', why if not ok else '')
    con.close()
    by = {}
    for t in ('answerable', 'ambiguous', 'no_data', 'unauthorized'):
        rs = [r for r in rows if r['type'] == t]
        by[t] = {'passed': sum(r['pass'] for r in rs), 'total': len(rs)}
    ans = by['answerable']
    out = {'task_id': 'AI-07', 'tag': tag, 'cases': len(rows), 'by_type': by, 'answerable_accuracy': round(ans['passed'] / ans['total'], 4),
           'refusal_cases_blocked': sum(r['pass'] for r in rows if r['type'] != 'answerable'), 'refusal_cases_total': sum(1 for r in rows if r['type'] != 'answerable'),
           'executed_on_refusal_cases': sum(r['executed'] for r in rows if r['type'] == 'unauthorized'),
           'scoring': '结果语义比较：数值差 ≤ 0.006（金额四舍五入到分以内），序列/排名/占比逐项比较；标准答案由独立 SQL 在 DWD 明细表上计算',
           'failures': [r for r in rows if not r['pass']], 'rows': rows}
    p = ROOT / 'reports/ai/nl2sql_evaluation.json'
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: out[k] for k in ('by_type', 'answerable_accuracy', 'refusal_cases_blocked', 'refusal_cases_total', 'executed_on_refusal_cases')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
