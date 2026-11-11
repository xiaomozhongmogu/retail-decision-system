"""UI-01 smoke: render every page with streamlit.testing AppTest, with and without a release; then the real
server is started separately (see navigation_smoke.md). usage: .venv/bin/python evidence/UI-01/smoke.py"""
import json
import sys
from pathlib import Path
from unittest import mock

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
PAGES = {'data': '数据口径与质量', 'business': '经营总览', 'customers': '客户生命周期与分群', 'prediction': '复购预测', 'ai': 'AI 工作台'}
res, ok = [], []


def text(at):
    parts = [m.value for m in at.markdown] + [t.value for t in at.title] + [c.value for c in at.caption] + \
            [str(m.label) + str(m.value) for m in at.metric] + [i.value for i in at.info] + [w.value for w in at.warning] + [e.value for e in at.error]
    return '\n'.join(parts)


for page, title in PAGES.items():
    at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=60)
    at.run()
    if page != 'data':
        at.switch_page(f'src/retail_bi/ui/pages/{page}.py')
        at.run()
    t = text(at)
    good = not at.exception and title in t and '数据版本' in t and '2026-11-08' in t and '完全合成数据' in t and '不是 2026 年实时经营' in t
    ok.append(good)
    res.append({'page': page, 'title_found': title in t, 'banner': '数据版本' in t, 'exception': [str(e.value) for e in at.exception],
                'dataframes': len(at.dataframe)})
import os
import tempfile
with tempfile.TemporaryDirectory() as empty:
    os.environ['RETAIL_BI_RELEASES_DIR'] = empty
    for page in PAGES:
        at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=60)
        at.run()
        if page != 'data':
            at.switch_page(f'src/retail_bi/ui/pages/{page}.py')
            at.run()
        t = text(at)
        good = not at.exception and '尚无已发布的数据版本' in t and len(at.dataframe) == 0
        ok.append(good)
        res.append({'page': page, 'no_release': True, 'empty_state_shown': '尚无已发布的数据版本' in t, 'exception': [str(e.value) for e in at.exception]})
    del os.environ['RETAIL_BI_RELEASES_DIR']
print(json.dumps(res, ensure_ascii=False))
print(f'{sum(ok)}/{len(ok)} pages ok')
sys.exit(0 if all(ok) else 1)
