"""AI-10: score the blind reviewer's output against eval/blind_key/answer_key.json.
usage: .venv/bin/python eval/score_blind_review.py   (reads eval/blind_packet/gpt_review.jsonl, writes reports/ai/report_evaluation.json)"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
key = {k['report']: k for k in json.loads((ROOT / 'eval/blind_key/answer_key.json').read_text(encoding='utf-8'))['reports']}
gpt = {r['report']: r for r in (json.loads(l) for l in (ROOT / 'eval/blind_packet/gpt_review.jsonl').read_text(encoding='utf-8').splitlines() if l.strip())}
TYPE_MATCH = {'数字': {'数字'}, '单位': {'单位'}, '窗口': {'窗口'}, '引用': {'引用'}, '因果': {'因果'}, '不存在字段': {'不存在字段'},
              '不完整周期': {'特殊情况处理', '窗口', '语义'}, '特殊情况处理': {'特殊情况处理', '语义'}}
# Manual classification (claude-opus-5-5, checked against the report text and facts) of reviewer findings that are not planted errors
ROUNDING = 'ratio shown with one decimal (e.g. 0.4416 -> +44.2%): packet knowledge.md did not say whether one-decimal percentages are allowed; values are correct when rounded -> spec ambiguity, not a report error'
TEMPLATE_HYP = 'template hypothesis says causes need price/promotion/contact records that the data lacks; it is labelled 待验证 and states the fields are missing -> wording to improve, not a false claim'
REAL_NEW = {'R22': 'LLM hypothesis says the excluded last day will raise the report-week amount; that day is outside the report week -> real semantic error missed by our checker',
            'R24': 'LLM hypothesis says the excluded last day can change the report-week result; same error -> real, missed by our checker'}
rows, planted_total, planted_found, ours_found = [], 0, 0, 0
for rid, k in sorted(key.items()):
    g = gpt.get(rid, {'issues': [], 'publishable': None})
    high = [i for i in g['issues'] if i['severity'] == '高']
    found = []
    for p in k['planted_errors']:
        planted_total += 1
        hit = any(i['type'] in TYPE_MATCH[p['type']] for i in high)
        planted_found += hit
        ours_found += bool(k['our_checker_flags'])
        found.append({'planted': p['type'], 'reviewer_found': hit, 'our_checker_found': bool(k['our_checker_flags'])})
    other = []
    for i in g['issues']:
        if any(i['type'] in TYPE_MATCH[p['type']] for p in k['planted_errors']) and i['severity'] == '高':
            continue
        if i['type'] == '数字' and i['severity'] == '低' and '一位小数' in i['evidence']:
            cls = ('spec_ambiguity', ROUNDING)
        elif i['type'] == '不存在字段' and '价格、促销与触达' in i['quote']:
            cls = ('wording', TEMPLATE_HYP)
        elif rid in REAL_NEW and i['severity'] == '高':
            cls = ('real_new_issue', REAL_NEW[rid])
        elif rid == 'R17' and i['type'] == '不存在字段':
            cls = ('planted_related', 'second finding on the same planted sentence (促销 is not in the data) -> correct')
        elif rid == 'R20' and i['type'] == '语义':
            cls = ('planted_related', 'second finding on the same planted sentence -> correct')
        else:
            cls = ('unclassified', 'needs review')
        other.append({'type': i['type'], 'severity': i['severity'], 'class': cls[0], 'note': cls[1], 'quote': i['quote'][:80]})
    rows.append({'report': rid, 'scenario': k['scenario'], 'generation': k['generation'], 'reviewer_publishable': g['publishable'],
                 'planted': found, 'other_findings': other, 'our_checker_flags': k['our_checker_flags']})
clean = [r for r in rows if not r['planted']]
cls = lambda c: sum(1 for r in rows for o in r['other_findings'] if o['class'] == c)  # noqa: E731
out = {'task_id': 'AI-10', 'reviewer': 'GPT（用户提供的盲测结果，型号未告知）', 'review_mode': 'independent AI review, blind (answer key withheld)', 'reports': len(rows),
       'scenarios': sorted({r['scenario'] for r in rows}),
       'planted': {'total': planted_total, 'found_by_reviewer': planted_found, 'found_by_our_checker': ours_found},
       'clean_reports': {'total': len(clean), 'with_high_severity_findings': sum(any(o['severity'] == '高' for o in r['other_findings']) for r in clean),
                         'high_severity_real_new_issues': cls('real_new_issue'), 'false_positive_high': sum(1 for r in clean for o in r['other_findings'] if o['severity'] == '高' and o['class'] not in ('real_new_issue',))},
       'low_severity': {'spec_ambiguity_rounding': cls('spec_ambiguity'), 'template_wording': cls('wording'), 'unclassified': cls('unclassified')},
       'checker_gaps': ['单位被改为“元”未被最终复核发现', '未结束月份与上月全月的直接比较未被发现', '假设中把截止前最后一天算进报告周（R22、R24，真实 LLM 输出）未被发现'],
       'human_spot_check': '未完成：需要真人从 24 份中任选至少 5 份按同样检查项复核',
       'scope': '结论只针对这 24 份报告，不代表所有输入都不会出错', 'rows': rows}
(ROOT / 'reports/ai/report_evaluation.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print(json.dumps({k: out[k] for k in ('planted', 'clean_reports', 'low_severity', 'checker_gaps')}, ensure_ascii=False, indent=1))
