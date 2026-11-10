"""ML-08: freeze the model, calibration, ranking policy and capacity on validation only (before any test use).

Decisions (recorded in reports/model/model_selection.json with the freeze time):
- probability model: logistic regression (unweighted), the best validation PR-AUC (ML-06/07); LightGBM did not beat it.
- calibration: compared on validation with time-blocked cross-fitting (fit on one half of the validation weeks,
  score the other half); the method with the lowest mean Brier is kept ('none' unless a method is clearly better).
- ranking policy for weekly contact lists: chosen by mean *within-week* lift@10% on validation, because lists are
  built per week; pooled metrics mostly reflect month-to-month base-rate changes.
- no fixed 0.5 threshold: lists take the top K of the weekly population; K is a business capacity setting.
- the frozen probability model is refit on train + validation with the same hyper-parameters and preprocessing
  rules; the test set is not loaded here.

usage: .venv/bin/python src/retail_bi/model/model_select.py
writes reports/model/model_selection.json and models/repurchase-logreg-v1.json (git-ignored copy; ML-12 publishes)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

from baselines import Prep, SEED
from common import FEATURES, ROOT, data_identity, load_frame, metrics

MODEL_VERSION = 'repurchase-logreg-v1'
CAPACITY_SHARE = 0.10        # default weekly contact capacity (demo business setting, AI-11 may override)


def ece(y, p, bins=10):
    edges = np.quantile(p, np.linspace(0, 1, bins + 1))
    idx = np.clip(np.searchsorted(edges[1:-1], p, side='right'), 0, bins - 1)
    return float(sum(abs(p[idx == b].mean() - y[idx == b].mean()) * (idx == b).mean() for b in range(bins) if (idx == b).any()))


def weekly(frame, col, frac):
    lifts, aucs = [], []
    for _, g in frame.groupby('as_of'):
        n = max(1, int(round(len(g) * frac)))
        lifts.append(g.nlargest(n, col).y.mean() / g.y.mean())
        aucs.append(roc_auc_score(g.y, g[col]))
    return float(np.mean(lifts)), float(np.mean(aucs))


def fit_lr(frame):
    prep = Prep().fit(frame[FEATURES])
    m = LogisticRegression(C=1.0, max_iter=2000, random_state=SEED).fit(prep.transform(frame[FEATURES]), frame.y)
    return prep, m


def main():
    df = load_frame()
    tr, va = df[df.set == 'train'], df[df.set == 'validation'].copy()
    prep, lr = fit_lr(tr)
    va['p_logreg'] = lr.predict_proba(prep.transform(va[FEATURES]))[:, 1]
    va['rule_frequency_90d'] = va.orders_90d + va.merch_90d / 1e6
    va['rule_recency'] = -va.recency_days
    y, p = va.y.to_numpy(), va.p_logreg.to_numpy()

    # calibration: time-blocked cross-fitting inside validation
    weeks = sorted(va.as_of.unique())
    halves = [set(weeks[:len(weeks) // 2]), set(weeks[len(weeks) // 2:])]
    cal = {'none': [], 'platt': [], 'isotonic': []}
    for fit_w, eval_w in [(halves[0], halves[1]), (halves[1], halves[0])]:
        f, e = va[va.as_of.isin(fit_w)], va[va.as_of.isin(eval_w)]
        cal['none'].append(brier_score_loss(e.y, e.p_logreg))
        platt = LogisticRegression().fit(np.log(f.p_logreg / (1 - f.p_logreg)).to_numpy()[:, None], f.y)
        cal['platt'].append(brier_score_loss(e.y, platt.predict_proba(np.log(e.p_logreg / (1 - e.p_logreg)).to_numpy()[:, None])[:, 1]))
        iso = IsotonicRegression(out_of_bounds='clip').fit(f.p_logreg, f.y)
        cal['isotonic'].append(brier_score_loss(e.y, iso.predict(e.p_logreg)))
    cal_mean = {k: round(float(np.mean(v)), 7) for k, v in cal.items()}
    best_cal = min(cal_mean, key=cal_mean.get)
    calibration = 'none' if cal_mean['none'] - cal_mean[best_cal] < 1e-4 else best_cal

    # ranking policy by within-week lift on validation
    rank = {}
    for c in ('p_logreg', 'rule_frequency_90d', 'rule_recency'):
        l10, auc = weekly(va, c, CAPACITY_SHARE)
        l20, _ = weekly(va, c, 0.20)
        rank[c] = {'weekly_lift@10%': round(l10, 4), 'weekly_lift@20%': round(l20, 4), 'mean_weekly_roc_auc': round(auc, 4)}
    ranking_policy = max(rank, key=lambda c: rank[c]['weekly_lift@10%'])

    # refit the probability model on train + validation for the frozen version (test not loaded)
    tv = df[df.set.isin(['train', 'validation'])]
    prep_f, lr_f = fit_lr(tv)
    model = {'model_version': MODEL_VERSION, 'type': 'logistic_regression', 'features': FEATURES, 'feature_version': 'features-v1',
             'target': 'target-v1', 'positive_class': 'repurchase within 30 days', 'fitted_on': 'train + validation (split-v1)',
             'fitted_rows': int(len(tv)), 'hyperparameters': {'C': 1.0, 'class_weight': None, 'max_iter': 2000, 'random_state': SEED},
             'preprocessing': prep_f.params(), 'coefficients': dict(zip(FEATURES, [float(c) for c in lr_f.coef_[0]])),
             'intercept': float(lr_f.intercept_[0]), 'calibration': calibration, 'data': data_identity()}
    (ROOT / 'models').mkdir(exist_ok=True)
    (ROOT / f'models/{MODEL_VERSION}.json').write_text(json.dumps(model, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    base = json.loads((ROOT / 'reports/model/baselines.json').read_text(encoding='utf-8'))
    boost = json.loads((ROOT / 'reports/model/boosting_validation.json').read_text(encoding='utf-8'))
    sel = {
        'task_id': 'ML-08', 'frozen_at': datetime.now(timezone.utc).isoformat(), 'test_set_used': False, 'data': data_identity(),
        'candidates_validation': {'logreg': base['models']['logreg']['validation'], 'logreg_balanced': base['models']['logreg_balanced']['validation'],
                                  'lightgbm_best': boost['lightgbm_validation'], 'rule_frequency_90d': base['models']['rule_frequency_90d']['validation'],
                                  'rule_recency': base['models']['rule_recency']['validation']},
        'probability_model': {'choice': MODEL_VERSION, 'why': '验证 PR-AUC 最高（0.0897），优于 LightGBM（0.0882）且更简单；类别加权版本概率偏高、排序不更好',
                              'validation_metrics_train_only_fit': metrics(y, p), 'expected_calibration_error_validation': round(ece(y, p), 5),
                              'refit': 'train + validation，相同超参数与预处理规则；测试集评估使用这个冻结版本'},
        'calibration': {'cross_fitted_brier_by_method': cal_mean, 'choice': calibration,
                        'why': '验证周按时间分两半交叉拟合，校准后的 Brier 改善不到 0.0001 时保留原始概率'},
        'ranking_policy': {'choice': ranking_policy, 'validation_within_week': rank,
                           'why': '名单按周生成，按验证期“周内”Lift@10% 选择排序方式；所有候选的周内 ROC-AUC 都在 0.50–0.52，周内排序能力接近随机'},
        'threshold_and_capacity': {'probability_threshold': None, 'capacity_share_per_week': CAPACITY_SHARE,
                                   'rule': '不使用固定 0.5 阈值：每周对母体按排序策略取前 K（默认 10%，业务可配置）；概率只作展示和汇总，未复购风险 = 1 − 概率',
                                   'expected_weekly_lift_at_K_validation': rank[ranking_policy]['weekly_lift@10%']},
        'selection_criterion_change': 'ML-07 以合并验证集的 PR-AUC 比较模型；ML-08 发现合并指标主要反映各月基率差异，名单场景改用周内 Lift@K 选择排序方式。该改变发生在任何测试集使用之前，概率模型仍按 PR-AUC 选择。',
        'no_switch_after_test': '冻结后不得因测试结果更换模型、校准、排序策略或 K；任何改变须作为新实验并采用新的评估方案。',
        'model_file': f'models/{MODEL_VERSION}.json',
    }
    (ROOT / 'reports/model/model_selection.json').write_text(json.dumps(sel, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'calibration': cal_mean, 'choice': calibration, 'ece': sel['probability_model']['expected_calibration_error_validation'],
                      'ranking': rank, 'ranking_policy': ranking_policy}, ensure_ascii=False))


if __name__ == '__main__':
    main()
