"""REL-04: measure resources, query/page/AI latency and cost, and check the degraded modes.

Measures on the current machine and the published release (read only):
- hardware and data scale;
- view queries: cold (new process: open the release, check its SHA-256, query), uncached (connection reopened, identity
  already checked) and hot (result cache hit);
- page render: each of the five pages in a new process (first run) and a rerun in the same session;
- LLM: latency, tokens and estimated cost per purpose from logs/ai/llm_calls.jsonl (successful live calls only);
- degraded modes through integration.Hub: no key, network down (unreachable endpoint), call budget exhausted, replay.
Writes reports/release/performance_probe.json. Makes at most 2 real LLM calls (budget probe), only when a key is configured.

usage: .venv/bin/python src/retail_bi/perf_probe.py
"""
from __future__ import annotations

import json
import os
import platform
import statistics as stx
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
for p in ('src/retail_bi/warehouse', 'src/retail_bi/ai'):
    sys.path.insert(0, str(ROOT / p))
OUT = ROOT / 'reports/release/performance_probe.json'
VIEW = ('ads.sales_month_category_region', ['month', 'product_category', 'merchandise_sales_usd'], {'customer_region': 'West'})


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def hardware():
    return {'cpu': sh(['sysctl', '-n', 'machdep.cpu.brand_string']), 'cores': int(sh(['sysctl', '-n', 'hw.ncpu']) or 0),
            'memory_gb': round(int(sh(['sysctl', '-n', 'hw.memsize']) or 0) / 2**30, 1), 'os': f"macOS {sh(['sw_vers', '-productVersion'])}",
            'arch': platform.machine(), 'python': platform.python_version()}


def scale():
    import runtime
    con, ptr = runtime.open_current()
    try:
        q = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
        return {'release': ptr['version'], 'release_bytes': ptr.get('bytes'),
                'orders': q('SELECT count(*) FROM dwd.fact_order'), 'order_lines': q('SELECT count(*) FROM dwd.fact_order_line'),
                'customers': q('SELECT count(*) FROM dwd.dim_customer'), 'customer_snapshots': q('SELECT count(*) FROM dws.customer_snapshot'),
                'model_scores': q('SELECT count(*) FROM ads.model_scores')}
    finally:
        con.close()


COLD = """
import sys, time, json; sys.path.insert(0, 'src/retail_bi/warehouse')
t0 = time.perf_counter(); import runtime; t1 = time.perf_counter()
r = runtime.query_view(%r, %r, %r); t2 = time.perf_counter()
print(json.dumps({'import_s': t1 - t0, 'first_query_s': t2 - t1, 'status': r['status'], 'rows': len(r['rows'])}))
""" % VIEW


def queries():
    cold = [json.loads(subprocess.run([PY, '-c', COLD], cwd=ROOT, capture_output=True, text=True).stdout) for _ in range(3)]
    import runtime
    runtime.query_view(*VIEW)
    unc = []
    for _ in range(20):
        runtime._cached.cache_clear()
        t = time.perf_counter(); runtime.query_view(*VIEW); unc.append(time.perf_counter() - t)
    hot = []
    for _ in range(200):
        t = time.perf_counter(); runtime.query_view(*VIEW); hot.append(time.perf_counter() - t)
    ms = lambda xs: round(stx.median(xs) * 1000, 2)  # noqa: E731
    return {'view': VIEW[0], 'rows': cold[0]['rows'], 'cold_first_query_ms': [round(c['first_query_s'] * 1000, 1) for c in cold],
            'cold_import_ms': [round(c['import_s'] * 1000, 1) for c in cold],
            'uncached_median_ms': ms(unc), 'uncached_max_ms': round(max(unc) * 1000, 2), 'hot_median_ms': ms(hot), 'hot_max_ms': round(max(hot) * 1000, 3),
            'note': 'cold = new process: open release, verify SHA-256 of the file, query; uncached = connection reopened per query; hot = result cache hit'}


PAGE = """
import json, sys, time
from streamlit.testing.v1 import AppTest
at = AppTest.from_file('app.py', default_timeout=240)
t0 = time.perf_counter(); at.run()
if %r != 'data':
    at.switch_page('src/retail_bi/ui/pages/%s.py'); at.run()
t1 = time.perf_counter(); at.run(); t2 = time.perf_counter()
print(json.dumps({'first_s': t1 - t0, 'rerun_s': t2 - t1, 'exceptions': len(at.exception)}))
"""


def pages():
    out = {}
    env = {**os.environ, 'LLM_ALLOW_PAID': '0'}       # page timing without model calls (the AI page makes none on load anyway)
    for p in ('data', 'business', 'customers', 'prediction', 'ai'):
        r = subprocess.run([PY, '-c', PAGE % (p, p)], cwd=ROOT, capture_output=True, text=True, env=env)
        line = [l for l in r.stdout.splitlines() if l.startswith('{')]
        out[p] = json.loads(line[-1]) if line else {'error': r.stderr[-300:]}
        if line:
            out[p] = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in out[p].items()}
    return out


def llm_stats():
    rows = [json.loads(l) for l in open(ROOT / 'logs/ai/llm_calls.jsonl', encoding='utf-8') if l.strip()] if (ROOT / 'logs/ai/llm_calls.jsonl').exists() else []
    ok = [r for r in rows if r.get('status') == 'ok' and r.get('mode') == 'live']
    by = {}
    for r in ok:
        by.setdefault(r['purpose'], []).append(r)
    q = lambda xs, f: round(sorted(xs)[min(len(xs) - 1, int(f * len(xs)))], 2)  # noqa: E731
    stats = {p: {'calls': len(v), 'median_s': round(stx.median([x['seconds'] for x in v]), 2), 'p90_s': q([x['seconds'] for x in v], 0.9),
                 'median_tokens_in': int(stx.median([x.get('tokens_in') or 0 for x in v])), 'median_tokens_out': int(stx.median([x.get('tokens_out') or 0 for x in v])),
                 'median_cost_usd': round(stx.median([x.get('cost_usd') or 0 for x in v]), 6)} for p, v in sorted(by.items())}
    errs = {}
    for r in rows:
        if r.get('status') != 'ok':
            errs[(r.get('error') or 'unknown').split(':')[0]] = errs.get((r.get('error') or 'unknown').split(':')[0], 0) + 1
    return {'log_rows': len(rows), 'live_ok_calls': len(ok), 'total_cost_usd_logged': round(sum(r.get('cost_usd') or 0 for r in ok), 4),
            'first_call': rows[0]['at'] if rows else None, 'last_call': rows[-1]['at'] if rows else None, 'by_purpose': stats, 'non_ok_by_kind': errs}


def degraded():
    import client as C
    import integration as I
    import drafts
    base = C.Config.from_env()
    tmp = Path(tempfile.mkdtemp())
    q = '2026年10月的商品金额是多少？'
    res = {}
    hub = I.Hub(C.LLMClient(C.Config(api_key='', base_url='', model='')), events=tmp / 'e.jsonl')
    a, ev = hub.run_query(q)                       # Hub methods return (result, event)
    res['no_key'] = {'mode': ev['mode'], 'answer_ok': a['status'] == 'ok', 'llm_calls': ev['llm']['calls']}
    down = C.Config(api_key='sk-probe-not-a-real-key', base_url='http://127.0.0.1:9/v1', model=base.model or 'deepseek-chat', allow_paid=True,
                    allow_unknown_price=True, max_retries=0, timeout_s=3)
    hub = I.Hub(C.LLMClient(down), events=tmp / 'e.jsonl')
    t = time.perf_counter(); a, e1 = hub.run_query(q); rr, e2 = hub.run_report('live')
    ra, e3 = hub.run_agent({'request_id': 'probe-down', 'customer_id': 'customer_001045', 'context': {'consent': True, 'gross_margin': 0.3}, 'spent_usd': 0},
                       store=drafts.DraftStore(tmp / 'd.sqlite'))
    res['network_down'] = {'modes': [e1['mode'], e2['mode'], e3['mode']], 'answer_ok': a['status'] == 'ok',
                           'report_generator_mode': e2.get('generator_mode'), 'agent_outcome': e3['outcome'], 'draft_sent': (ra.get('draft') or {}).get('sent'), 'seconds_all_three': round(time.perf_counter() - t, 2),
                           'key_in_events': 'sk-probe-not-a-real-key' in (tmp / 'e.jsonl').read_text(encoding='utf-8')}
    if base.api_key and base.allow_paid:
        tight = C.Config(**{**base.__dict__, 'max_calls': 1})
        hub = I.Hub(C.LLMClient(tight), events=tmp / 'e.jsonl')
        a1, b1 = hub.run_query(q); a2, b2 = hub.run_query('2025年的商品金额是多少？')
        res['budget_exhausted'] = {'first_mode': b1['mode'], 'second_mode': b2['mode'], 'second_answer_ok': a2['status'] == 'ok',
                                   'calls_used': hub.client.budget()['calls'], 'max_calls': 1}
    else:
        res['budget_exhausted'] = {'skipped': 'no key or paid calls not allowed'}
    body = json.loads((ROOT / 'reports/ai/weekly_report_replay.json').read_text(encoding='utf-8')).get('llm_body')   # same source as the AI page
    rp, ep = I.Hub(C.LLMClient(C.Config(api_key='', base_url='', model='')), events=tmp / 'e.jsonl').run_report(
        'replay', replay_text=json.dumps(body, ensure_ascii=False))
    res['replay'] = {'mode': ep['mode'], 'generator_mode': ep.get('generator_mode'), 'llm_calls': ep['llm']['calls']}
    return res


ALLPAGES = """
from streamlit.testing.v1 import AppTest
for p in ('data', 'business', 'customers', 'prediction', 'ai'):
    at = AppTest.from_file('app.py', default_timeout=240); at.run()
    if p != 'data':
        at.switch_page(f'src/retail_bi/ui/pages/{p}.py'); at.run()
"""


def memory_and_concurrency():
    """Peak memory of one process rendering all five pages; latency of uncached view queries from 8 threads at once."""
    r = subprocess.run(['/usr/bin/time', '-l', PY, '-c', ALLPAGES], cwd=ROOT, capture_output=True, text=True, env={**os.environ, 'LLM_ALLOW_PAID': '0'})
    rss = next((int(l.split()[0]) for l in r.stderr.splitlines() if 'maximum resident set size' in l), None)
    import threading
    import runtime
    lat, errs = [], []

    def worker(region):
        for _ in range(10):
            try:
                runtime._cached.cache_clear()
                t = time.perf_counter(); runtime.query_view(VIEW[0], VIEW[1], {'customer_region': region}); lat.append(time.perf_counter() - t)
            except Exception as e:  # noqa: BLE001
                errs.append(repr(e))
    th = [threading.Thread(target=worker, args=(g,)) for g in ('West', 'Northeast', 'South', 'Midwest') * 2]
    t0 = time.perf_counter(); [t.start() for t in th]; [t.join() for t in th]; wall = time.perf_counter() - t0
    lat.sort()
    return {'all_pages_peak_rss_mb': round(rss / 2**20, 1) if rss else None,
            'concurrent_threads': 8, 'queries': len(lat), 'errors': len(errs), 'median_ms': round(stx.median(lat) * 1000, 1),
            'p90_ms': round(lat[int(0.9 * len(lat))] * 1000, 1), 'max_ms': round(lat[-1] * 1000, 1), 'wall_s': round(wall, 2)}


def main():
    t0 = time.time()
    out = {'task_id': 'REL-04', 'run_at': datetime.now(timezone.utc).isoformat(), 'hardware': hardware(), 'scale': scale(), 'queries': queries(),
           'pages': pages(), 'etl': json.loads((ROOT / 'reports/warehouse/etl_run.json').read_text(encoding='utf-8')).get('stages'),
           'llm': llm_stats(), 'degraded': degraded(), 'memory_and_concurrency': memory_and_concurrency()}
    out['probe_seconds'] = round(time.time() - t0, 1)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False)[:3000])


if __name__ == '__main__':
    main()
