"""UI-07 check: caching, connection boundaries, no ETL/training in pages, and recoverable errors without secrets.

Readability (fonts, contrast, axes, units, layout at the projector size) is checked in the browser and written up in
reports/ui/full_ui_review.md; this script covers what can be asserted in code.
usage: .venv/bin/python evidence/UI-07/check.py
"""
import os
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ('src/retail_bi/ui', 'src/retail_bi/warehouse', 'src/retail_bi/ai'):
    sys.path.insert(0, str(ROOT / p))

import streamlit as st  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

import customer_data  # noqa: E402
import drafts  # noqa: E402
import model_data  # noqa: E402
import runtime  # noqa: E402

PAGES = ['data', 'business', 'customers', 'prediction', 'ai']
FAKE_KEY = 'sk-uitest-LEAKCHECK7f3a91'
ok = []
TMP = Path(tempfile.mkdtemp())
drafts.DraftStore.__init__.__defaults__ = (TMP / 'ui07_drafts.sqlite',)   # keep test drafts out of the real store


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, '' if cond else str(detail)[:400])


def text(at):
    parts = []
    for kind in ('markdown', 'caption', 'info', 'warning', 'error', 'success', 'title', 'code'):
        parts += [str(x.value) for x in at.get(kind)]
    parts += [str(e.value) for e in at.exception]
    for d in at.dataframe:
        parts.append(d.value.to_string())
    return '\n'.join(parts)


def open_page(name, run=True):
    at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=240)
    at.run()
    if name != 'data':
        at.switch_page(f'src/retail_bi/ui/pages/{name}.py')
        if run:
            at.run()
    return at


def tabs_text(at):
    return text(at)


# ---- 1. pages never run ETL or training ----------------------------------------------------------------------------
sessions = {p: open_page(p) for p in PAGES}
check('all five pages render without exceptions', all(not at.exception for at in sessions.values()),
      {p: [str(e.value) for e in at.exception] for p, at in sessions.items() if at.exception})
heavy = {'ingest', 'clean', 'integrate', 'transform', 'transactions', 'profile', 'candidate_probe', 'ods', 'dwd', 'pipeline',
         'baselines', 'boosting', 'model_select', 'segments', 'evaluate', 'split', 'samples', 'features', 'sklearn', 'lightgbm'}
loaded = {m.split('.')[0] for m in sys.modules}   # everything in the process, including what was imported before
check('rendering every page loads no ETL, warehouse-build or training module (nor sklearn/lightgbm)', not (loaded & heavy), sorted(loaded & heavy))

# ---- 2. caches ----------------------------------------------------------------------------------------------------
code = runtime._cached.__wrapped__.__code__
check('view-query cache key = (release version, releases dir, SQL with columns and filters, bound filter values)',
      code.co_varnames[:4] == ('version', 'releases', 'sql', 'params'))
runtime._cached.cache_clear()
runtime.query_view('ads.sales_month_category_region', ['month', 'merchandise_sales_usd'], {'customer_region': 'West'})
h0 = runtime.cache_info()
runtime.query_view('ads.sales_month_category_region', ['month', 'merchandise_sales_usd'], {'customer_region': 'West'})
h1 = runtime.cache_info()
r_east = runtime.query_view('ads.sales_month_category_region', ['month', 'merchandise_sales_usd'], {'customer_region': 'South'})
h2 = runtime.cache_info()
check('same query and filter is a cache hit; a different filter is a separate entry',
      h1.hits == h0.hits + 1 and h2.misses == h1.misses + 1 and r_east['status'] == 'ok', (h0, h1, h2))

calls = {'score_list': 0, 'aggregates': 0}
_sl, _ag = model_data.score_list, customer_data.aggregates
model_data.score_list = lambda *a, **k: (calls.__setitem__('score_list', calls['score_list'] + 1), _sl(*a, **k))[1]
customer_data.aggregates = lambda *a, **k: (calls.__setitem__('aggregates', calls['aggregates'] + 1), _ag(*a, **k))[1]
st.cache_data.clear()
a1, a2 = open_page('prediction'), open_page('prediction')
a1.run(); a1.run()
c1, c2 = open_page('customers'), open_page('customers')
c1.run()
check('scoring list and lifecycle aggregates are read once per release version across reruns and sessions',
      calls == {'score_list': 1, 'aggregates': 1} and not (a1.exception or a2.exception or c1.exception or c2.exception), calls)
model_data.score_list, customer_data.aggregates = _sl, _ag

errors = []


def worker(region):
    try:
        for _ in range(5):
            r = runtime.query_view('ads.sales_month_category_region', ['month'], {'customer_region': region}, releases=runtime.RELEASES)
            assert r['status'] == 'ok'
            runtime._cached.cache_clear()          # force real connections, not cache hits
    except Exception as e:  # noqa: BLE001
        errors.append(repr(e))


th = [threading.Thread(target=worker, args=(r,)) for r in ('West', 'Northeast', 'South', 'Midwest') * 2]
[t.start() for t in th]
[t.join() for t in th]
check('8 threads querying at once: each query opens and closes its own read-only connection, no errors', not errors, errors[:3])

# ---- 3. recoverable errors ------------------------------------------------------------------------------------------
empty = TMP / 'no_releases'
empty.mkdir()
os.environ['RETAIL_BI_RELEASES_DIR'] = str(empty)
st.cache_data.clear()
res = {p: open_page(p) for p in PAGES}
check('no published release: every page shows the empty state, no exception',
      all(not at.exception and '尚无已发布的数据版本' in text(at) for at in res.values()),
      {p: [str(e.value) for e in at.exception] for p, at in res.items()})
del os.environ['RETAIL_BI_RELEASES_DIR']

_rep = model_data.REPORTS
model_data.REPORTS = TMP / 'no_reports'
st.cache_data.clear()
pr, cu = open_page('prediction'), open_page('customers')
model_data.REPORTS = _rep
check('frozen model records missing: prediction page explains and stops instead of crashing',
      not pr.exception and '模型评估记录缺失或无法读取' in text(pr), [str(e.value) for e in pr.exception])
check('segment record missing: customer page shows an error in that tab, other tabs still render',
      not cu.exception and '分群记录 reports/model/cluster_metrics.json 缺失' in text(cu) and '沉睡' in text(cu), [str(e.value) for e in cu.exception])

model_data.score_list = lambda *a, **k: {**_sl(*a, **k), 'model_version': 'repurchase-logreg-v0'}
st.cache_data.clear()
mv = open_page('prediction')
model_data.score_list = _sl
st.cache_data.clear()
t = text(mv)
check('scoring table from another model version: list is withheld with an explanation',
      not mv.exception and '与冻结版本 `repurchase-logreg-v1` 不一致' in t and '入选人数' not in t, [str(e.value) for e in mv.exception])

# LLM endpoint down, with a fake key in the environment: modules fall back, nothing on the page shows the key
env = {'LLM_API_KEY': FAKE_KEY, 'LLM_BASE_URL': 'http://127.0.0.1:9/v1', 'LLM_MODEL': 'deepseek-chat', 'LLM_ALLOW_PAID': '1',
       'LLM_ALLOW_UNKNOWN_PRICE': '1', 'LLM_MAX_RETRIES': '0', 'LLM_TIMEOUT_S': '3'}
saved = {k: os.environ.get(k) for k in env}
os.environ.update(env)
try:
    ai = open_page('ai')
    toggles = [x for x in ai.toggle if x.key == 'use_llm']
    check('with a (fake) key configured the LLM switch is on', toggles and toggles[0].value, [x.key for x in ai.toggle])
    ai.chat_input[0].set_value('2026年10月的商品金额是多少？').run()
    [b for b in ai.button if b.key == 'qa_run'][0].click().run()
    ai.radio[[r.key for r in ai.radio].index('wr_mode')].set_value('live').run()
    [b for b in ai.button if b.key == 'wr_go'][0].click().run()
    [b for b in ai.button if b.key == 'ag_go'][0].click().run()
    t = text(ai)
    check('API unreachable: query still answers from the executed query (47,590.59 USD)', '47,590.59 USD' in t, t[:300])
    import re
    m = re.search(r'生成模式 \*\*(\S+)\*\*（请求 (\S+)） · LLM 尝试 (\d+) 次 · 最终数字复核 \*\*(\S+)\*\*', t)
    check('API unreachable: live weekly report request falls back to the template, final number check passed',
          m and m.group(1).startswith('template') and m.group(2) == 'live' and m.group(4) == '通过', m.groups() if m else t[:600])
    check('API unreachable: agent still ends with a pending draft, not sent', '**未发送**' in t, t[-400:])
    check('no exception, and the key never appears on the page (text, tables, code, errors)',
          not ai.exception and FAKE_KEY not in t and FAKE_KEY[:12] not in t, [str(e.value) for e in ai.exception])
finally:
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

print(f'{sum(ok)}/{len(ok)} checks passed')
sys.exit(0 if all(ok) else 1)
