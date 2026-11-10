"""EDA-03: cohort retention report from ads.cohort_retention (read through the runtime), with independent checks.
usage: .venv/bin/python evidence/EDA-03/cohort_report.py   (writes reports/analysis/cohort.md and cohort_checks.json)"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
from runtime import open_current, query_view  # noqa: E402

r = query_view('ads.cohort_retention', ['cohort_month', 'months_since_first', 'cohort_customers', 'active_customers', 'retention_rate', 'immature'])
C = pd.DataFrame(r['rows'], columns=r['columns'])
for c in ('months_since_first', 'cohort_customers'):
    C[c] = C[c].astype(int)
C['active_customers'] = pd.to_numeric(C.active_customers)
C['retention_rate'] = pd.to_numeric(C.retention_rate)
C['immature'] = C.immature == 'True'
con, ptr = open_current()
O = con.execute("SELECT customer_id, purchase_ts::VARCHAR p FROM dwd.fact_order WHERE approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'").df()
con.close()
O['m'] = pd.to_datetime(O.p, utc=True).dt.tz_localize(None).dt.to_period('M')
first = O.groupby('customer_id').m.min().rename('cohort')
A = O.join(first, on='customer_id')
A['k'] = (A.m - A.cohort).apply(lambda x: x.n)
checks, ok = [], []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    checks.append({'check': name, 'status': 'passed' if cond else 'failed', 'detail': str(detail)})


for coh, k in [('2024-01', 1), ('2024-03', 6), ('2024-09', 12), ('2025-06', 3), ('2026-02', 1)]:
    p = pd.Period(coh, 'M')
    size = int((first == p).sum())
    act = int(A[(A.cohort == p) & (A.k == k)].customer_id.nunique())
    row = C[(C.cohort_month == coh) & (C.months_since_first == k)].iloc[0]
    check(f'cell {coh} +{k}: cohort size and active customers equal pandas recount', (row.cohort_customers, int(row.active_customers)) == (size, act), (size, act))
k0 = C[(C.months_since_first == 0) & ~C.immature]
check('k = 0 retention is 100% for every mature cohort (definition check)', (k0.retention_rate == 1.0).all(), len(k0))
imm = C[C.immature]
check('immature cells (month not finished at cutoff) are missing, not 0', imm.active_customers.isna().all() and imm.retention_rate.isna().all() and len(imm) > 0, len(imm))
check('no cell beyond the data month exists', (pd.PeriodIndex(C.cohort_month, freq='M') + C.months_since_first).max() <= pd.Period('2026-11', 'M'))
check('cohort sizes add up to all buyers', C[C.months_since_first == 0].cohort_customers.sum() == first.size, first.size)
# comparison table on mature windows only: +1, +3, +6, +12 for cohorts where the cell is mature
mature = C[~C.immature]
pivot = mature.pivot(index='cohort_month', columns='months_since_first', values='retention_rate')
sizes = C[C.months_since_first == 0].set_index('cohort_month').cohort_customers
half = lambda m: m[:4] + ('-H1' if int(m[5:]) <= 6 else '-H2')  # noqa: E731
rows = []
for k in (1, 3, 6, 12):
    s = mature[mature.months_since_first == k]
    g = s.assign(h=s.cohort_month.map(half)).groupby('h')
    for h, x in g:
        rows.append({'k': k, 'half': h, 'cohorts': int(len(x)), 'customers': int(x.cohort_customers.sum()),
                     'weighted_retention': round(float(x.active_customers.sum() / x.cohort_customers.sum()), 4)})
out = {'task_id': 'EDA-03', 'release': ptr['version'], 'definition': {
    'cohort': '首次可观测有效购买（已审批）的自然月；不是终身首次购买',
    'age': '距首购月的月数 k（k=0 为首购月）',
    'retention': '第 k 个月有至少一次有效购买的客户数 / cohort 客户数',
    'maturity': '第 k 个月在截止（2026-11-08）前已完整结束才算成熟；2026-11 及以后为缺失',
    'left_truncation': '客户 2024-01-01 至 2024-06-29 建档，数据起点之前没有交易，本数据不存在左截断；若换用有历史的真实数据，2024 年初的 cohort 会混入老客户，需要预热期'},
    'summary_mature_by_half_year': rows, 'cohorts': int(len(sizes)), 'checks': checks, 'all_passed': all(ok)}
(ROOT / 'reports/analysis/cohort_checks.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
L = ['# 首次可观测购买 cohort 与留存（EDA-03）', '', f'- 数据：只读发布 `{ptr["version"]}` 的视图 `ads.cohort_retention`（SQL 见 `sql/ads.sql`）；完全合成数据。', '',
     '## 1. 口径', ''] + [f'- **{k}**：{v}' for k, v in out['definition'].items()] + [
     '', '## 2. 成熟窗口比较（按首购半年加权）', '', '| 距首购月数 | cohort 半年 | cohort 数 | 客户 | 留存率 |', '|---:|---|---:|---:|---:|']
L += [f'| +{x["k"]} | {x["half"]} | {x["cohorts"]} | {x["customers"]:,} | {x["weighted_retention"]:.1%} |' for x in rows]
L += ['', '只比较已成熟的格子；后期 cohort 的 +6、+12 尚未观察到，所以不出现在表中，而不是 0。', '',
      '## 3. 留存矩阵（成熟格子；空白 = 尚未观察到）', '', '| cohort | 客户 | ' + ' | '.join(f'+{k}' for k in range(0, 13)) + ' |', '|---|---:|' + '---:|' * 13]
for coh in pivot.index:
    L.append(f'| {coh} | {sizes[coh]} | ' + ' | '.join('' if pd.isna(pivot.loc[coh].get(k)) else f'{pivot.loc[coh][k]:.0%}' for k in range(0, 13)) + ' |')
w1 = {x['half']: x['weighted_retention'] for x in rows if x['k'] == 1}
L += ['', '## 4. 发现', '',
      f'- 首购后第 1 个月的留存率在各半年 cohort 之间为 {min(w1.values()):.1%}–{max(w1.values()):.1%}，没有持续变好或变差的趋势。',
      f'- 在客户数不少于 100 的半年组合里，第 1、3、6、12 个月的加权留存率都在 {min(x["weighted_retention"] for x in rows if x["customers"] >= 100):.1%}–{max(x["weighted_retention"] for x in rows if x["customers"] >= 100):.1%} 之间，'
       '没有常见电商“首月高、随后快速下降”的形状，这与合成生成器中复购几乎不依赖时间间隔一致（EDA-05）。客户数少于 100 的组合（如 2026-H2）波动大，不作解读。',
      '- 新 cohort 规模逐期变小，因为 2024 年中之后没有新建档客户（EDA-01），后期 cohort 小、留存率波动大，不宜单独解读。', '']
(ROOT / 'reports/analysis/cohort.md').write_text('\n'.join(L), encoding='utf-8')
print(json.dumps({'checks': [c['status'] for c in checks], 'summary': rows[:4]}, ensure_ascii=False))
sys.exit(0 if all(ok) else 1)
