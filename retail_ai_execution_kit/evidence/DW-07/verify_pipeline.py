"""DW-07 checks: rerun is a no-op, an injected failure is located and leaves nothing behind,
the run report has rows/amounts/durations/versions.
usage: .venv/bin/python evidence/DW-07/verify_pipeline.py
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = str(ROOT / '.venv/bin/python')
B = ROOT / 'warehouse/builds'
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


def run(*args, report):
    p = subprocess.run([PY, 'src/retail_bi/pipeline.py', 'build', '--report', str(report), *args], cwd=ROOT, capture_output=True, text=True)
    return p.returncode, json.loads(Path(report).read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


first = json.loads((ROOT / 'reports/warehouse/etl_run.json').read_text(encoding='utf-8'))
check('first run: all stages ok, ending with publish', first['status'] == 'ok' and [s['stage'] for s in first['stages']][-1] == 'publish'
      and all(s['status'] == 'ok' for s in first['stages']))
st = {s['stage']: s for s in first['stages']}
check('report records rows per layer, amounts, durations, input versions',
      st['checks']['rows']['dwd.fact_order'] == 9311 and st['checks']['values']['valid_merch_usd'] == '1380161.23'
      and all('seconds' in s for s in first['stages']) and len(first['inputs']['files']) >= 9 and first['inputs']['source_sha256'])
latest_before = (B / 'latest.json').read_bytes()
final = B / f"{first['version']}.duckdb"
final_sha = sha(final)
tmp_report = ROOT / 'evidence/DW-07/rerun_report.json'
code, r2 = run(report=tmp_report)
check('rerun with same inputs is a no-op: same version, existing build verified, not rebuilt',
      code == 0 and r2['version'] == first['version'] and [s['stage'] for s in r2['stages']][-1] == 'verify_existing'
      and sha(final) == final_sha, [s['stage'] for s in r2['stages']])
fail_report = ROOT / 'evidence/DW-07/injected_failure_report.json'
code, r3 = run('--force', '--fail-at', 'dws', report=fail_report)
check('injected failure at dws: exit 1, failed stage named with error', code == 1 and r3['status'] == 'failed' and r3['failed_stage'] == 'dws'
      and 'injected failure' in next(s for s in r3['stages'] if s['stage'] == 'dws')['error'])
check('failed run leaves no half-built file', not list(B.glob('.*building*')), [p.name for p in B.glob('.*')])
check('failed run does not touch the published build or latest.json', sha(final) == final_sha and (B / 'latest.json').read_bytes() == latest_before)
code, r4 = run('--force', report=ROOT / 'evidence/DW-07/forced_rebuild_report.json')
s4 = {s['stage']: s for s in r4['stages']}
check('forced full rebuild succeeds with identical checked values and row counts',
      code == 0 and s4['checks']['values'] == st['checks']['values'] and s4['checks']['rows'] == st['checks']['rows'])
latest = json.loads((B / 'latest.json').read_text(encoding='utf-8'))
check('latest.json points to the published version', latest['version'] == first['version'] and (B / latest['file']).is_file())
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
