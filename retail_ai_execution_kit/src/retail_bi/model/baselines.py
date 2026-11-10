"""ML-06: rule baselines and logistic regression on target-v1 / split-v1 / features-v1.

Everything that is fitted (medians for missing values, scaler, model) is fitted on the training set only and
its parameters are saved. Results on train and validation are reported; the test set is not touched.

usage: .venv/bin/python src/retail_bi/model/baselines.py   (writes reports/model/baselines.json and baselines.md)
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LogisticRegression

from common import FEATURES, LOG_FEATURES, ROOT, data_identity, load_frame, metrics

SEED = 20261110


class Prep:
    """Train-only preprocessing: median imputation, log1p on skewed columns, standardisation."""

    def fit(self, X: pd.DataFrame):
        Z = X.copy()
        self.medians = {c: float(Z[c].median()) for c in Z.columns}
        Z = Z.fillna(self.medians)
        for c in LOG_FEATURES:
            Z[c] = np.log1p(Z[c].clip(lower=0))
        self.mean = Z.mean().to_dict()
        self.std = {c: (float(v) if v > 0 else 1.0) for c, v in Z.std(ddof=0).items()}
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        Z = X.fillna(self.medians).copy()
        for c in LOG_FEATURES:
            Z[c] = np.log1p(Z[c].clip(lower=0))
        return ((Z - pd.Series(self.mean)) / pd.Series(self.std))[list(X.columns)].to_numpy()

    def params(self):
        return {'medians': self.medians, 'log1p_columns': LOG_FEATURES, 'mean': self.mean, 'std': self.std}


def run():
    df = load_frame()
    tr, va = df[df.set == 'train'], df[df.set == 'validation']
    res = {'task_id': 'ML-06', 'run_at': datetime.now(timezone.utc).isoformat(), 'data': data_identity(), 'seed': SEED,
           'library': {'scikit-learn': sklearn.__version__, 'numpy': np.__version__, 'pandas': pd.__version__},
           'sets': {'train': {'rows': len(tr), 'positives': int(tr.y.sum())}, 'validation': {'rows': len(va), 'positives': int(va.y.sum())}},
           'test_set_used': False, 'models': {}}
    # rule baselines (no fitting except the constant base rate, which comes from train)
    base = float(tr.y.mean())
    rules = {
        'base_rate': (np.full(len(va), base), np.full(len(tr), base), True, f'常数 = 训练期正例比例 {base:.4f}'),
        'rule_recency': (-va.recency_days.to_numpy(), -tr.recency_days.to_numpy(), False, '越近期购买分数越高（−recency_days）'),
        'rule_frequency_90d': (va.orders_90d + va.merch_90d / 1e6, tr.orders_90d + tr.merch_90d / 1e6, False, '近 90 天订单数，金额作次序打破平局'),
    }
    for name, (sv, st, prob, desc) in rules.items():
        res['models'][name] = {'type': 'rule', 'description': desc, 'train': metrics(tr.y, st, prob) if name != 'base_rate' else None,
                               'validation': metrics(va.y, sv, prob) if name != 'base_rate' else
                               {'n': len(va), 'positive_rate': round(float(va.y.mean()), 6), 'roc_auc': 0.5,
                                'pr_auc': round(float(va.y.mean()), 6),
                                'brier': round(float(np.mean((base - va.y) ** 2)), 6)}}
    # logistic regression, two imbalance settings; both fitted on train only
    prep = Prep().fit(tr[FEATURES])
    Xtr, Xva = prep.transform(tr[FEATURES]), prep.transform(va[FEATURES])
    for name, cw in [('logreg', None), ('logreg_balanced', 'balanced')]:
        t0 = time.perf_counter()
        m = LogisticRegression(C=1.0, class_weight=cw, max_iter=2000, random_state=SEED)
        m.fit(Xtr, tr.y)
        ptr, pva = m.predict_proba(Xtr)[:, 1], m.predict_proba(Xva)[:, 1]
        res['models'][name] = {
            'type': 'logistic_regression', 'class_weight': cw, 'C': 1.0, 'seconds': round(time.perf_counter() - t0, 3),
            'probabilities_calibrated': cw is None,
            'train': metrics(tr.y, ptr), 'validation': metrics(va.y, pva),
            'coefficients': dict(zip(FEATURES, [round(float(c), 6) for c in m.coef_[0]])), 'intercept': round(float(m.intercept_[0]), 6),
        }
    res['preprocessing'] = prep.params()
    res['feature_order'] = FEATURES
    ranked = sorted(((k, v['validation']['pr_auc']) for k, v in res['models'].items()), key=lambda kv: -kv[1])
    res['validation_ranking_by_pr_auc'] = ranked
    res['notes'] = ['类别加权会把预测概率整体抬高，不能直接当作校准概率；排序指标可比',
                    '规则分数不是概率，只报告排序指标', '测试集未使用（ML-09 才使用一次）']
    return res


def render(r):
    L = ['# 规则与逻辑回归基线（ML-06）', '',
         f'- 运行时间 {r["run_at"]}；数据 {r["data"]["release"]} / {r["data"]["feature_version"]} / {r["data"]["split_version"]}；随机种子 {r["seed"]}；'
         f'scikit-learn {r["library"]["scikit-learn"]}。',
         f'- 训练 {r["sets"]["train"]["rows"]:,} 行（正例 {r["sets"]["train"]["positives"]:,}），验证 {r["sets"]["validation"]["rows"]:,} 行（正例 {r["sets"]["validation"]["positives"]:,}）。测试集未使用。',
         '- 填补中位数、log1p、标准化参数只在训练集拟合，保存在 baselines.json 的 preprocessing。', '',
         '| 模型 | 验证 ROC-AUC | 验证 PR-AUC | KS | Lift@10% | Recall@10% | Brier | 训练 ROC-AUC |', '|---|---:|---:|---:|---:|---:|---:|---:|']
    for k, v in r['models'].items():
        va, tr = v['validation'], v.get('train') or {}
        L.append(f'| {k} | {va.get("roc_auc", "")} | {va.get("pr_auc", "")} | {va.get("ks", "")} | {va.get("lift@10%", "")} | '
                 f'{va.get("recall@10%", "")} | {va.get("brier", "")} | {tr.get("roc_auc", "")} |')
    best = r['validation_ranking_by_pr_auc'][0]
    lr = r['models']['logreg']['validation']
    L += ['', f'验证集 PR-AUC 最高的是 `{best[0]}`（{best[1]:.4f}），验证集正例比例为 {r["models"]["base_rate"]["validation"]["positive_rate"]:.4f}。'
          f'逻辑回归 ROC-AUC {lr["roc_auc"]:.4f}、PR-AUC {lr["pr_auc"]:.4f}：区分能力有限，与 ML-01 预期一致（30 天窗口内复购信号弱，母体内外复购率接近）。', '',
          '逻辑回归系数（标准化后，前 8 个绝对值最大）：', '']
    coef = sorted(r['models']['logreg']['coefficients'].items(), key=lambda kv: -abs(kv[1]))[:8]
    L += [f'- {k}: {v:+.4f}' for k, v in coef]
    L += ['', '系数是相关性的描述，不是因果效果。', '', '说明：' + '；'.join(r['notes']) + '。', '']
    return '\n'.join(L)


def main():
    r = run()
    (ROOT / 'reports/model/baselines.json').write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'reports/model/baselines.md').write_text(render(r), encoding='utf-8')
    print(json.dumps({k: (v['validation'].get('roc_auc'), v['validation'].get('pr_auc')) for k, v in r['models'].items()}, ensure_ascii=False))


if __name__ == '__main__':
    main()
