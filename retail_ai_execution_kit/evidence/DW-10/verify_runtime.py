"""DW-10 checks: read-only access, allowed views, identity check, cache invalidation on a new release,
interrupted publish keeps the previous release, rollback, and ETL running while the app holds a reader.
Temporary release directories are used for the publish/rollback scenarios; the real release is only read.
usage: .venv/bin/python evidence/DW-10/verify_runtime.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
import release  # noqa: E402
import runtime  # noqa: E402

ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


real = runtime.pointer()
con, ptr = runtime.open_current()
try:
    con.execute('CREATE TABLE ads.x (a INT)')
    wrote = True
except Exception as exc:
    wrote = False
    err = type(exc).__name__
check('runtime connection is read-only (write refused)', not wrote, err)
check('release file is read-only on disk (0444)', oct((release.RELEASES / ptr['file']).stat().st_mode & 0o777) == '0o444')
r = runtime.query_view('ads.kpi_monthly', ['month', 'valid_orders'], {'month': '2025-07'})
check('allowed view answers with dataset_version and live mode', r['status'] == 'ok' and r['rows'] == [['2025-07', '272']] and r['dataset_version'] == real['version'], r['rows'])
r = runtime.query_view('dwd.fact_order')
check('non-allowed table refused as unsupported', r['status'] == 'unsupported', r['error']['code'])
r = runtime.query_view('ads.kpi_monthly', ['month; DROP TABLE x'])
check('bad column text refused (no SQL injection path)', r['status'] == 'error', r['error']['code'])
r = runtime.query_view('ads.kpi_monthly', where={'month': '1999-01'})
check('valid query with no rows returns status empty', r['status'] == 'empty')

# ETL keeps running while the app holds a reader; the release file is not touched
before = release.sha(release.RELEASES / ptr['file'])
p = subprocess.run([str(ROOT / '.venv/bin/python'), 'src/retail_bi/pipeline.py', 'build', '--force', '--report', str(ROOT / 'evidence/DW-10/etl_while_reading.json')],
                   cwd=ROOT, capture_output=True, text=True)
still = con.execute('SELECT count(*) FROM ads.kpi_monthly').fetchone()[0]
con.close()
check('offline build succeeds while a reader is open; reader unaffected; release unchanged',
      p.returncode == 0 and still == 35 and release.sha(release.RELEASES / ptr['file']) == before, p.stdout.strip()[-120:])

build = ROOT / 'warehouse/builds' / json.loads((ROOT / 'warehouse/builds/latest.json').read_text())['file']
with tempfile.TemporaryDirectory() as tmp:
    rel = Path(tmp) / 'releases'
    p1 = release.publish(build, 'v1', rel)
    release._record_history(rel, p1)
    runtime._cached.cache_clear()
    a = runtime.query_view('ads.kpi_monthly', ['month'], {'month': '2025-07'}, releases=rel)
    b = runtime.query_view('ads.kpi_monthly', ['month'], {'month': '2025-07'}, releases=rel)
    i1 = runtime.cache_info()
    check('repeat query served from cache within one release', a == b and i1.hits == 1 and i1.misses == 1, i1)
    p2 = release.publish(build, 'v2', rel)
    release._record_history(rel, p2)
    c = runtime.query_view('ads.kpi_monthly', ['month'], {'month': '2025-07'}, releases=rel)
    i2 = runtime.cache_info()
    check('new release invalidates cached results (version in cache key)', c['dataset_version'] == 'v2' and i2.misses == 2, i2)
    try:
        release.publish(build, 'v3', rel, _fail_before_pointer=True)
        failed = False
    except RuntimeError:
        failed = True
    cur = release.current(rel)
    d = runtime.query_view('ads.kpi_monthly', ['month'], {'month': '2025-07'}, releases=rel)
    check('interrupted publish: pointer still on v2, queries still work, no temp copy left',
          failed and cur['version'] == 'v2' and d['status'] == 'ok' and not list(rel.glob('.*.copy')), cur['version'])
    cur_obj = json.loads((rel / 'current.json').read_text())
    cur_obj['sha256'] = '0' * 64
    (rel / 'current.json').write_text(json.dumps(cur_obj))
    try:
        runtime._identity_cache.clear()
        runtime.open_current(rel)
        refused = False
    except runtime.ReleaseError:
        refused = True
    check('identity check: a release whose hash does not match the pointer is refused', refused)
    cur_obj['sha256'] = p2['sha256']
    (rel / 'current.json').write_text(json.dumps(cur_obj))
    rb = release.rollback(rel)
    e = runtime.query_view('ads.kpi_monthly', ['month'], {'month': '2025-07'}, releases=rel)
    check('rollback switches readers back to the previous release', rb['version'] == 'v1' and e['dataset_version'] == 'v1')
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
