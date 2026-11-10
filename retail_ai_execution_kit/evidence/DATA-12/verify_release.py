"""DATA-12 checks: the release register matches the files, the readme matches the register.
usage: .venv/bin/python evidence/DATA-12/verify_release.py
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R = json.loads((ROOT / 'reports/data/dataset_release.json').read_text(encoding='utf-8'))
doc = (ROOT / 'docs/data_readme.md').read_text(encoding='utf-8')
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


f = R['formal_data']
check('source ZIP hash and size', sha(ROOT.parent / f['path']) == f['sha256'] == 'd50ee64a0478d8ae8df1b8b66521671a4911e19f911ae86196452a668f917a16'
      and f['bytes'] == 1310750 and f['git_tracked'])
check('derived dirs ignored by git', all(f['derived_dirs_git_ignored'].values()))
for lay in R['layers']:
    d = ROOT / lay['path']
    check(f"layer files match register: {lay['kind']}", sha(d / 'manifest.json') == lay['manifest_sha256']
          and all(sha(d / x['path']) == x['sha256'] for x in lay['files']), f"{len(lay['files'])} files")
for p, h in R['documents'].items():
    if p != 'docs/data_readme.md':
        check(f'document hash {p}', sha(ROOT / p) == h)
check('readme names every layer directory', all(v in doc for k, v in R['versions'].items() if k in ('clean', 'integrated', 'transformed')))
check('readme one-click chain present and ends with the gate', 'quality_gate.py' in doc and doc.count('&&') >= 4 and R['versions']['clean'] in doc)
t = R['course_thresholds']
check('records threshold', t['records']['measured_order_items_rows'] >= 10000 and '15,639' in doc)
check('fields threshold', t['fields']['measured'] >= 8 and '17 个' in doc)
check('time field and coverage', t['time']['months'] >= 24 and '35 个月' in doc)
check('freshness stated as user-authorized, not teacher', '教师未答复' in t['freshness']['status'] and '没有教师确认' in doc)
check('gate passed with warning disclosed', R['quality_gate']['result'] == 'passed' and R['quality_gate']['warnings'] and '1 条警告' in doc)
check('full scope, not sample', '未抽样' in R['scope']['full_or_sample'] and '没有抽样' in doc)
check('no public release', '不公开' in R['delivery']['public_release'] and '不公开发布' in doc)
check('unknowns listed in both', len(R['unknowns']) >= 4 and all(u.split('（')[0][:8] in doc for u in R['unknowns']))
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
