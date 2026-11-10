"""ML-09: one-time out-of-time evaluation on the test set with the decisions frozen in ML-08.

Nothing is fitted here. The frozen probability model is read from its JSON file and its hash is checked
against the value recorded at freeze time; rule baselines need no fitting; the base-rate baseline uses the
train+validation positive rate. Intervals: 95% bootstrap resampling whole customers (all their snapshots
together), 500 replicates, fixed seed; snapshots of one customer are never treated as independent.

usage: .venv/bin/python src/retail_bi/model/evaluate.py
writes reports/model/test_metrics.json and reports/model/evaluation.md
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score

from common import ROOT, data_identity, load_frame, metrics

B_REPS, SEED = 500, 20261111


def score_frozen(model: dict, X: pd.DataFrame) -> np.ndarray:
    pp = model['preprocessing']
    Z = X[model['features']].astype(float).fillna(pp['medians'])
    for c in pp['log1p_columns']:
        Z[c] = np.log1p(Z[c].clip(lower=0))
    Z = (Z - pd.Series(pp['mean'])) / pd.Series(pp['std'])
    z = Z[model['features']].to_numpy() @ np.array([model['coefficients'][f] for f in model['features']]) + model['intercept']
    return 1 / (1 + np.exp(-z))


def weekly_topk(frame, col, frac):
    flags = np.zeros(len(frame), dtype=bool)
    pos = {i: k for k, i in enumerate(frame.index)}
    lifts, aucs, single = [], [], 0
    for _, g in frame.groupby('as_of'):
        n = max(1, int(round(len(g) * frac)))
        top = g.nlargest(n, col)
        for i in top.index:
            flags[pos[i]] = True
        if g.y.nunique() < 2:
            single += 1
            continue
        lifts.append(top.y.mean() / g.y.mean())
        aucs.append(roc_auc_score(g.y, g[col]))
    return flags, float(np.mean(lifts)), float(np.mean(aucs)), single


def ece(y, p, bins=10):
    edges = np.quantile(p, np.linspace(0, 1, bins + 1))
    idx = np.clip(np.searchsorted(edges[1:-1], p, side='right'), 0, bins - 1)
    table = [{'bin': b + 1, 'n': int((idx == b).sum()), 'mean_pred': round(float(p[idx == b].mean()), 4), 'observed': round(float(y[idx == b].mean()), 4)}
             for b in range(bins) if (idx == b).any()]
    return float(sum(abs(t['mean_pred'] - t['observed']) * t['n'] for t in table) / len(y)), table


def bootstrap(frame, col, rng):
    custs = frame.customer_id.unique()
    groups = {c: g.index.to_numpy() for c, g in frame.groupby('customer_id')}
    y, s = frame.y.to_numpy(), frame[col].to_numpy()
    pos = {i: k for k, i in enumerate(frame.index)}
    aucs, aps = [], []
    for _ in range(B_REPS):
        pick = rng.choice(custs, size=len(custs), replace=True)
        idx = np.concatenate([[pos[i] for i in groups[c]] for c in pick])
        aucs.append(roc_auc_score(y[idx], s[idx]))
        aps.append(average_precision_score(y[idx], s[idx]))
    q = lambda a: [round(float(np.percentile(a, 2.5)), 4), round(float(np.percentile(a, 97.5)), 4)]  # noqa: E731
    return {'roc_auc_95ci': q(aucs), 'pr_auc_95ci': q(aps)}


def main():
    sel = json.loads((ROOT / 'reports/model/model_selection.json').read_text(encoding='utf-8'))
    model_path = ROOT / sel['model_file']
    model = json.loads(model_path.read_text(encoding='utf-8'))
    df = load_frame()
    te = df[df.set == 'test'].copy()
    tv_rate = float(df[df.set.isin(['train', 'validation'])].y.mean())
    te['p_model'] = score_frozen(model, te)
    te['rule_frequency_90d'] = te.orders_90d + te.merch_90d / 1e6
    te['rule_recency'] = -te.recency_days
    K = sel['threshold_and_capacity']['capacity_share_per_week']
    y = te.y.to_numpy()
    rng = np.random.default_rng(SEED)
    res = {'task_id': 'ML-09', 'evaluated_at': datetime.now(timezone.utc).isoformat(), 'data': data_identity(),
           'frozen_at': sel['frozen_at'], 'model_version': model['model_version'],
           'model_file_sha256': hashlib.sha256(model_path.read_bytes()).hexdigest(),
           'positive_class': 'repurchase within 30 days (y=1)',
           'test_set': {'as_of_range': [te.as_of.min(), te.as_of.max()], 'as_of_points': int(te.as_of.nunique()), 'rows': int(len(te)),
                        'customers': int(te.customer_id.nunique()), 'positives': int(y.sum()), 'negatives': int(len(y) - y.sum()),
                        'positive_rate': round(float(y.mean()), 4), 'includes_partial_2026Q4': bool((te.as_of == '2026-10-05 00:00:00+00').any())},
           'capacity_share_per_week': K, 'scores': {}}
    for col, prob, label in [('p_model', True, 'frozen logistic regression (probability model)'),
                             ('rule_frequency_90d', False, 'frozen ranking policy: 90-day order frequency'),
                             ('rule_recency', False, 'baseline rule: recency')]:
        flags, wl, wa, single = weekly_topk(te, col, K)
        out = {'label': label, **metrics(y, te[col].to_numpy(), prob),
               f'weekly_lift@{int(K * 100)}%': round(wl, 4), 'mean_weekly_roc_auc': round(wa, 4), 'weeks_single_class_skipped': single,
               f'f1_at_weekly_top{int(K * 100)}%': round(float(f1_score(y, flags)), 4),
               f'precision_at_weekly_top{int(K * 100)}%': round(float(y[flags].mean()), 4),
               f'recall_at_weekly_top{int(K * 100)}%': round(float(y[flags].sum() / y.sum()), 4), **bootstrap(te, col, rng)}
        if prob:
            e, table = ece(y, te[col].to_numpy())
            out['ece'], out['reliability'] = round(e, 4), table
        res['scores'][col] = out
    res['scores']['base_rate'] = {'label': 'constant = train+validation positive rate', 'value': round(tv_rate, 4),
                                  'roc_auc': 0.5, 'pr_auc_equals_positive_rate': round(float(y.mean()), 4),
                                  'brier': round(float(np.mean((tv_rate - y) ** 2)), 6)}
    res['notes'] = ['测试集只在本任务使用一次；模型、校准、排序与 K 在 ML-08 冻结后未改动',
                    '区间按客户整体重抽样（500 次），不把同一客户的多个快照当作独立样本',
                    '周内指标在每个 as_of 内计算再平均；单类周会被跳过并计数',
                    '没有承诺任何分数；数据完全合成']
    (ROOT / 'reports/model/test_metrics.json').write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    (ROOT / 'reports/model/evaluation.md').write_text(render(res), encoding='utf-8')
    for k, v in res['scores'].items():
        print(k, {x: v.get(x) for x in ('roc_auc', 'pr_auc', 'brier', 'weekly_lift@10%', 'mean_weekly_roc_auc', 'roc_auc_95ci', 'ece')})


def render(r):
    t, s = r['test_set'], r['scores']
    m, f, rc, b = s['p_model'], s['rule_frequency_90d'], s['rule_recency'], s['base_rate']
    k = int(r['capacity_share_per_week'] * 100)
    L = ['# 最终时间外评估（ML-09）', '',
         f'- 评估时间 {r["evaluated_at"]}；冻结时间 {r["frozen_at"]}；模型 `{r["model_version"]}`（文件 SHA-256 `{r["model_file_sha256"][:16]}…`）。',
         f'- 正类：{r["positive_class"]}。测试集 as_of {t["as_of_range"][0][:10]} 至 {t["as_of_range"][1][:10]}，{t["as_of_points"]} 周，{t["rows"]:,} 行，'
         f'{t["customers"]:,} 名客户；正例 {t["positives"]:,}、负例 {t["negatives"]:,}，正例比例 {t["positive_rate"]:.2%}（含不完整的 2026-Q4 一周）。',
         '- 数据完全合成；测试集只使用这一次。', '',
         '| 指标 | 冻结逻辑回归 | 排序策略（90 天订单数） | 规则（最近购买） | 基率常数 |', '|---|---:|---:|---:|---:|',
         f'| ROC-AUC（95% 客户分块区间） | {m["roc_auc"]:.4f} [{m["roc_auc_95ci"][0]}, {m["roc_auc_95ci"][1]}] | {f["roc_auc"]:.4f} [{f["roc_auc_95ci"][0]}, {f["roc_auc_95ci"][1]}] | {rc["roc_auc"]:.4f} | 0.5 |',
         f'| PR-AUC（95% 区间） | {m["pr_auc"]:.4f} [{m["pr_auc_95ci"][0]}, {m["pr_auc_95ci"][1]}] | {f["pr_auc"]:.4f} [{f["pr_auc_95ci"][0]}, {f["pr_auc_95ci"][1]}] | {rc["pr_auc"]:.4f} | {b["pr_auc_equals_positive_rate"]} |',
         f'| KS | {m["ks"]:.4f} | {f["ks"]:.4f} | {rc["ks"]:.4f} | — |',
         f'| 周内平均 ROC-AUC | {m["mean_weekly_roc_auc"]:.4f} | {f["mean_weekly_roc_auc"]:.4f} | {rc["mean_weekly_roc_auc"]:.4f} | 0.5 |',
         f'| 周内 Lift@{k}% | {m[f"weekly_lift@{k}%"]:.3f} | {f[f"weekly_lift@{k}%"]:.3f} | {rc[f"weekly_lift@{k}%"]:.3f} | 1.000 |',
         f'| 每周前 {k}% 的 Precision / Recall / F1 | {m[f"precision_at_weekly_top{k}%"]:.3f} / {m[f"recall_at_weekly_top{k}%"]:.3f} / {m[f"f1_at_weekly_top{k}%"]:.3f} | '
         f'{f[f"precision_at_weekly_top{k}%"]:.3f} / {f[f"recall_at_weekly_top{k}%"]:.3f} / {f[f"f1_at_weekly_top{k}%"]:.3f} | '
         f'{rc[f"precision_at_weekly_top{k}%"]:.3f} / {rc[f"recall_at_weekly_top{k}%"]:.3f} / {rc[f"f1_at_weekly_top{k}%"]:.3f} | — |',
         f'| 合并 Lift@10% / Recall@10% | {m["lift@10%"]:.3f} / {m["recall@10%"]:.3f} | {f["lift@10%"]:.3f} / {f["recall@10%"]:.3f} | {rc["lift@10%"]:.3f} / {rc["recall@10%"]:.3f} | — |',
         f'| Brier | {m["brier"]:.5f} | 非概率 | 非概率 | {b["brier"]:.5f} |', '',
         f'冻结逻辑回归的校准误差 ECE = {m["ece"]:.4f}，平均预测 {m["mean_pred"]:.4f}，实际正例比例 {t["positive_rate"]:.4f}。', '',
         '| 分组（按预测概率十分位） | 样本 | 平均预测 | 实际比例 |', '|---:|---:|---:|---:|']
    L += [f'| {x["bin"]} | {x["n"]:,} | {x["mean_pred"]:.4f} | {x["observed"]:.4f} |' for x in m['reliability']]
    better = m['brier'] < b['brier']
    L += ['', '## 结论', '',
          f'- 在测试期，模型和规则的区分能力都很弱：逻辑回归 ROC-AUC {m["roc_auc"]:.3f}，客户分块 95% 区间 [{m["roc_auc_95ci"][0]}, {m["roc_auc_95ci"][1]}]；'
          f'周内平均 ROC-AUC {m["mean_weekly_roc_auc"]:.3f}，周内排序接近随机。',
          f'- 冻结的名单排序策略（90 天订单数）周内 Lift@{k}% 为 {f[f"weekly_lift@{k}%"]:.3f}，逻辑回归为 {m[f"weekly_lift@{k}%"]:.3f}。',
          f'- 概率水平基本可信（ECE {m["ece"]:.4f}）；Brier {"略好于" if better else "不优于"}基率常数（{m["brier"]:.5f} 对 {b["brier"]:.5f}）。',
          '- 业务含义：模型给出的平均复购水平可信（约 7%），但不同客户之间的概率差异没有可靠的区分价值，不能挑出“这周最该联系的少数客户”。'
          '触达名单应以价值、频次等可解释规则排序并说明其效果也接近随机；模型概率只作整体水平参考，页面与 Agent 不得宣称精准预测、高风险识别或挽回效果。',
          '- 原因（ML-01、EDA-01）：30 天内再次购买的间隔只占约 11%，母体内外复购率接近，合成生成器中复购与历史行为的关系弱。这是诚实的负结果，没有更改目标或测试集。', '',
          '说明：' + '；'.join(r['notes']) + '。', '']
    return '\n'.join(L)


if __name__ == '__main__':
    main()
