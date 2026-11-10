"""ML-10: error analysis of the frozen model on the test set (aggregates only, no customer identities).
usage: .venv/bin/python evidence/ML-10/error_analysis.py   (writes reports/model/error_analysis.md and error_analysis.json)"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/model'))
sys.path.insert(0, str(ROOT / 'src/retail_bi/analysis'))
from common import FEATURES, load_frame  # noqa: E402
from evaluate import score_frozen  # noqa: E402

sel = json.loads((ROOT / 'reports/model/model_selection.json').read_text(encoding='utf-8'))
model = json.loads((ROOT / sel['model_file']).read_text(encoding='utf-8'))
seg = json.loads((ROOT / 'reports/model/cluster_metrics.json').read_text(encoding='utf-8'))
df = load_frame()
te = df[df.set == 'test'].copy()
te['p'] = score_frozen(model, te)
K = sel['threshold_and_capacity']['capacity_share_per_week']
te['flag'] = False
for _, g in te.groupby('as_of'):
    te.loc[g.nlargest(max(1, int(round(len(g) * K))), 'p').index, 'flag'] = True
te['outcome'] = np.select([te.flag & (te.y == 1), te.flag & (te.y == 0), ~te.flag & (te.y == 1)], ['TP', 'FP', 'FN'], 'TN')
cuts = seg['rule_segments']['cut_points_fitted_on_fit_as_of']
te['value_segment'] = np.select([(te.recency_days < cuts['r_recent_days']) & ((te.orders_90d >= 2) | (te.merch_90d >= cuts['m_high_usd'])),
                                 te.recency_days < cuts['r_recent_days'], (te.orders_90d >= 2) | (te.merch_90d >= cuts['m_high_usd'])],
                                ['近期高价值', '近期一般', '较早高价值'], '较早一般')
te['lifecycle'] = np.where(te.tenure_days <= 30, 'new', 'active')       # population = bought in last 90 days -> new or active
te['region'] = np.select([te.region_midwest == 1, te.region_northeast == 1, te.region_south == 1], ['Midwest', 'Northeast', 'South'], 'West')
te['month'] = pd.to_datetime(te.as_of, utc=True).dt.strftime('%Y-%m')


def group(col):
    rows = []
    for k, g in te.groupby(col):
        auc = roc_auc_score(g.y, g.p) if g.y.nunique() == 2 else None
        rows.append({col: k, 'rows': int(len(g)), 'positive_rate': round(float(g.y.mean()), 4), 'mean_pred': round(float(g.p.mean()), 4),
                     'roc_auc': round(float(auc), 4) if auc is not None else 'single class', 'flagged_share': round(float(g.flag.mean()), 4),
                     'precision_flagged': round(float(g[g.flag].y.mean()), 4) if g.flag.any() else None})
    return rows


comp = te.groupby('outcome')[['recency_days', 'orders_90d', 'merch_90d', 'orders_all_time', 'tenure_days', 'gap_mean_days', 'as_of_month']].median().round(2)
coef = sorted(model['coefficients'].items(), key=lambda kv: -abs(kv[1]))
out = {'task_id': 'ML-10', 'model_version': model['model_version'], 'capacity_share': K,
       'confusion_at_weekly_top_k': te.outcome.value_counts().to_dict(),
       'median_features_by_outcome': comp.to_dict('index'),
       'by_month': group('month'), 'by_region': group('region'), 'by_value_segment': group('value_segment'), 'by_lifecycle': group('lifecycle'),
       'coefficients_top10': coef[:10]}
(ROOT / 'reports/model/error_analysis.json').write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')


def table(rows, key, title):
    L = [f'| {title} | 样本 | 实际比例 | 平均预测 | ROC-AUC | 入选比例 | 入选者命中率 |', '|---|---:|---:|---:|---:|---:|---:|']
    L += [f'| {r[key]} | {r["rows"]:,} | {r["positive_rate"]:.2%} | {r["mean_pred"]:.2%} | {r["roc_auc"]} | {r["flagged_share"]:.1%} | '
          f'{"" if r["precision_flagged"] is None else format(r["precision_flagged"], ".2%")} |' for r in rows]
    return L


cm = out['confusion_at_weekly_top_k']
L = ['# 误差分析与适用限制（ML-10）', '',
     f'- 模型 `{model["model_version"]}`，测试集（2026-03-30 至 2026-10-05），每周取预测概率最高的 {int(K * 100)}% 作为“入选”。只报告汇总，不列出任何客户。数据完全合成。', '',
     f'## 1. 误报与漏报', '', f'入选并复购（TP）{cm.get("TP", 0):,}，入选未复购（误报 FP）{cm.get("FP", 0):,}，未入选但复购（漏报 FN）{cm.get("FN", 0):,}，未入选未复购（TN）{cm.get("TN", 0):,}。'
     f'误报约为命中的 {cm.get("FP", 0) / max(1, cm.get("TP", 0)):.0f} 倍；漏报占全部复购的 {cm.get("FN", 0) / max(1, cm.get("FN", 0) + cm.get("TP", 0)):.1%}。', '',
     '| 结果 | 最近购买天数 | 近 90 天订单 | 近 90 天金额 | 累计订单 | 客龄天数 | 平均间隔 | as_of 月份 |', '|---|---:|---:|---:|---:|---:|---:|---:|']
L += [f'| {k} | {v["recency_days"]} | {v["orders_90d"]} | {v["merch_90d"]} | {v["orders_all_time"]} | {v["tenure_days"]} | {v["gap_mean_days"]} | {v["as_of_month"]} |'
      for k, v in out['median_features_by_outcome'].items()]
L += ['', '四类结果的特征中位数几乎相同：模型没有学到能可靠区分“这次会回来”与“不会回来”的信号。', '',
      '## 2. 分组表现', ''] + table(out['by_month'], 'month', '月份') + [''] + table(out['by_region'], 'region', '大区') + [''] + \
    table(out['by_value_segment'], 'value_segment', '价值分群（ML-05 规则）') + [''] + table(out['by_lifecycle'], 'lifecycle', '生命周期（母体内只有新客与活跃）')
L += ['', '各组 ROC-AUC 都在 0.5 附近波动，没有哪一组表现稳定地更好；小组的 AUC 波动大，不应据此下结论。', '',
      '## 3. 模型解释（不是因果）', '', '标准化后绝对值最大的 10 个系数：', ''] + [f'- {k}: {v:+.4f}' for k, v in out['coefficients_top10']]
L += ['', '系数只说明在这份数据里模型如何组合特征，**不表示改变某个特征就会改变复购**（例如“让客户多买几种商品”不会因此提高复购）。系数在特征相关时也不稳定。', '',
      '## 4. 适用限制', '',
      '- 测试期 74% 的客户也在训练期出现：结果只说明“已知客户在未来时点”的表现，不证明能推广到全新客户。',
      '- 数据是一个合成生成器产生的美国式电商记录，生成器中复购与历史行为关系很弱；结论不能推广到真实企业，更不能推广到当代中国市场。',
      '- 模型不估计营销触达的增量效果；没有实验数据，不能用风险分数代替“联系后能否挽回”。',
      '- 由于个体区分力接近随机，页面与 Agent 只能展示平均复购水平和规则名单，并明确说明模型的这一限制。', '']
(ROOT / 'reports/model/error_analysis.md').write_text('\n'.join(L), encoding='utf-8')
print(cm, [(r['month'], r['roc_auc']) for r in out['by_month']])
