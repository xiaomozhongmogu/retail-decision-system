"""UI-02 check: render the data page with AppTest and compare what it shows with the reports and the release.
usage: .venv/bin/python evidence/UI-02/check.py"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


def alltext(at):
    parts = [m.value for m in at.markdown] + [h.value for h in at.subheader] + [c.value for c in at.caption] + [str(m.label) + ' ' + str(m.value) for m in at.metric] + \
            [x.value for x in at.info] + [x.value for x in at.warning] + [x.value for x in at.error] + [x.value for x in at.success] + \
            [str(e.label) for e in at.expander] + [d.value.to_csv() for d in at.dataframe]
    return '\n'.join(parts)


def run(env=None):
    if env:
        os.environ.update(env)
    at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=90)
    at.run()
    return at


prof = json.loads((ROOT / 'reports/data/profile_after.json').read_text())
qc = json.loads((ROOT / 'reports/data/quality_checks.json').read_text())
rec = json.loads((ROOT / 'reports/data/transaction_reconciliation.json').read_text())
iss = json.loads((ROOT / 'reports/ui/data_issue_samples.json').read_text())
at = run()
t = alltext(at)
check('page renders without exception', not at.exception, [str(e.value) for e in at.exception])
check('seven tabs: source, coverage, quality, reconciliation, missing/duplicates, metric explanation, issue samples',
      [x.label for x in at.tabs] == ['来源与版本', '规模与覆盖', '质量检查', '有效购买对账', '缺失与重复', '指标解释', '问题样本'])
mets = {m.label: m.value for m in at.metric}
check('valid orders and amounts equal profile_after.json', mets.get('有效订单') == f"{prof['valid_orders_at_cutoff']['orders']:,}"
      and mets.get('商品金额（USD，不含运费）') == f"{float(prof['valid_orders_at_cutoff']['merch_usd']):,.2f}", mets)
check('release cross-check (ads.kpi_monthly) agrees with the report', any('与质量报告一致' in s.value for s in at.success))
check('table row counts equal the report', all(f'{n}' in t for n in prof['rows'].values()) and '15639' in t)
check('quality gate 10/10 and the 2026-Q4 warning shown', f"{qc['passed']}/{qc['total']}" in t and any('2026-Q4' in w.value for w in at.warning))
check('reconciliation rows: raw 9311 = cancelled 194 + pending 4 + valid 9113', all(str(x) in t for x in (9311, 194, 4, 9113)) and
      rec['raw_all_orders']['orders'] == rec['cancelled_orders']['orders'] + rec['pending_approval_at_cutoff']['orders'] + rec['valid_orders_at_cutoff']['orders'])
check('model sample rows shown separately and labelled as not raw data', '模型样本（不是原始数据量）' in t and f"{prof['label_30d_with_frozen_rule']['rows']:,}" in t)
sb = at.selectbox[0]
sb.set_value('aov_usd').run()
t2 = alltext(at)
check('metric explanation opens: picking aov_usd shows its definition, numerator and denominator', at.selectbox[0].value == 'aov_usd'
      and '**定义**：有效订单商品金额 / 有效订单数' in t2 and '**分子**：merchandise_sales_usd' in t2 and '**分母**：valid_orders' in t2)
check('issue samples open: four types with counts and 5 rows each', len(at.expander) == 4 and [len(d.value) for d in at.dataframe[-4:]] == [min(5, v['count']) for v in iss['issues'].values()]
      and '194 单' in t2 and '4 单' in t2, [e.label for e in at.expander])
check('no customer ids, keys or personal attributes on the page', not re.search(r'customer_\d{4,}|sk-[A-Za-z0-9]|LLM_API_KEY|zip_prefix|customer_city', t2))
with tempfile.TemporaryDirectory() as empty:
    at3 = run({'RETAIL_BI_RELEASES_DIR': empty})
    t3 = alltext(at3)
    check('without a release: banner empty state, report tabs still render, cross-check shows empty state', not at3.exception and '尚无已发布的数据版本' in t3
          and any('发布版本中没有月度指标' in i.value for i in at3.info))
    del os.environ['RETAIL_BI_RELEASES_DIR']
print(f'{sum(ok)}/{len(ok)} checks passed')
sys.exit(0 if all(ok) else 1)
