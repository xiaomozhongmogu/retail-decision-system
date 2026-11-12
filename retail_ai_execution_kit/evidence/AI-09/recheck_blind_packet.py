"""Re-run our report checker (after the AI-10 fixes) on the 24 blind-review reports and compare with the answer key
and the reviewer's real new findings. usage: .venv/bin/python evidence/AI-09/recheck_blind_packet.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'eval'))
sys.path.insert(0, str(ROOT / 'src/retail_bi/ai'))
import make_blind_packet as M  # noqa: E402
import report_generator as G  # noqa: E402

key = {k['report']: k for k in json.loads((ROOT / 'eval/blind_key/answer_key.json').read_text(encoding='utf-8'))['reports']}
facts = {sid: M.facts_for(sid) for sid in M.SCEN}
rows, ok = [], True
for rid, k in sorted(key.items()):
    text = (ROOT / f'eval/blind_packet/reports/{rid}.md').read_text(encoding='utf-8')
    f = facts[k['scenario']]
    flags = M.our_check(text, G.pick_facts(f), f)
    should = bool(k['planted_errors']) or rid in ('R22', 'R24')
    good = bool(flags) == should
    ok &= good
    rows.append({'report': rid, 'planted': [p['type'] for p in k['planted_errors']], 'real_new_issue': rid in ('R22', 'R24'), 'flags_before': len(k['our_checker_flags']),
                 'flags_now': flags, 'match': good})
    print('PASS' if good else 'FAIL', rid, k['scenario'], [p['type'] for p in k['planted_errors']], 'R22/24' if rid in ('R22', 'R24') else '', flags[:2])
caught = sum(bool(r['flags_now']) for r in rows if r['planted'] or r['real_new_issue'])
print(f'flagged {caught}/10 known problem reports; clean reports flagged: {sum(bool(r["flags_now"]) for r in rows if not (r["planted"] or r["real_new_issue"]))}/14')
(ROOT / 'evidence/AI-09/recheck_blind_packet.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
sys.exit(0 if ok else 1)
