"""ML-07: LightGBM with a small, fixed search on train/validation only.

Every trial trains on the training set and early-stops on the validation set (allowed: validation is part of
model development). The test set is never loaded. Eight configurations at most; seed, features, parameters,
library versions, data identity and timing are saved for every trial.

usage: .venv/bin/python src/retail_bi/model/boosting.py
writes reports/model/training_runs.json (all trials) and reports/model/boosting_validation.json (comparison)
"""
from __future__ import annotations

import itertools
import json
import platform
import time
from datetime import datetime, timezone

import lightgbm as lgb
import numpy as np
import pandas as pd
import sklearn

from common import FEATURES, ROOT, data_identity, load_frame, metrics

SEED = 20261110
BASE = {'objective': 'binary', 'metric': 'average_precision', 'learning_rate': 0.03, 'feature_fraction': 0.8,
        'bagging_fraction': 0.8, 'bagging_freq': 1, 'seed': SEED, 'deterministic': True, 'force_row_wise': True,
        'num_threads': 4, 'verbose': -1}
GRID = {'num_leaves': [15, 31], 'min_child_samples': [50, 200], 'lambda_l2': [0.0, 5.0]}   # 8 trials
MAX_ROUNDS, EARLY_STOP = 2000, 100


def run():
    df = load_frame()
    tr, va = df[df.set == 'train'], df[df.set == 'validation']
    Xtr, Xva = tr[FEATURES].astype(float), va[FEATURES].astype(float)
    dtr = lgb.Dataset(Xtr, tr.y, feature_name=FEATURES, free_raw_data=False)
    dva = lgb.Dataset(Xva, va.y, reference=dtr, free_raw_data=False)
    trials = []
    for i, combo in enumerate(itertools.product(*GRID.values()), start=1):
        params = {**BASE, **dict(zip(GRID, combo))}
        t0 = time.perf_counter()
        booster = lgb.train(params, dtr, num_boost_round=MAX_ROUNDS, valid_sets=[dva], valid_names=['validation'],
                            callbacks=[lgb.early_stopping(EARLY_STOP, verbose=False)])
        secs = time.perf_counter() - t0
        p_tr = booster.predict(Xtr, num_iteration=booster.best_iteration)
        p_va = booster.predict(Xva, num_iteration=booster.best_iteration)
        gain = booster.feature_importance('gain')
        trials.append({'trial': i, 'params': params, 'best_iteration': int(booster.best_iteration), 'seconds': round(secs, 2),
                       'train': metrics(tr.y, p_tr), 'validation': metrics(va.y, p_va),
                       'top_gain_features': [f for _, f in sorted(zip(gain, FEATURES), reverse=True)[:8]]})
    base = json.loads((ROOT / 'reports/model/baselines.json').read_text(encoding='utf-8'))
    best = max(trials, key=lambda t: t['validation']['pr_auc'])
    lr = base['models']['logreg']['validation']
    comparison = {
        'task_id': 'ML-07', 'selection_metric': 'validation PR-AUC (positive class = repurchase)',
        'best_trial': best['trial'], 'best_params': {k: best['params'][k] for k in GRID}, 'best_iteration': best['best_iteration'],
        'lightgbm_validation': best['validation'], 'logreg_validation': lr,
        'delta_pr_auc_vs_logreg': round(best['validation']['pr_auc'] - lr['pr_auc'], 6),
        'delta_roc_auc_vs_logreg': round(best['validation']['roc_auc'] - lr['roc_auc'], 6),
        'validation_spread': {'pr_auc_min': min(t['validation']['pr_auc'] for t in trials), 'pr_auc_max': max(t['validation']['pr_auc'] for t in trials)},
        'train_validation_gap_roc_auc': round(best['train']['roc_auc'] - best['validation']['roc_auc'], 6),
        'note': '只用训练与验证集；测试集未加载。验证集同时用于早停和挑选试验，因此验证分数略偏乐观，最终以 ML-09 测试为准。',
    }
    runs = {'task_id': 'ML-07', 'run_at': datetime.now(timezone.utc).isoformat(), 'data': data_identity(), 'seed': SEED,
            'features': FEATURES, 'grid': GRID, 'base_params': BASE, 'max_rounds': MAX_ROUNDS, 'early_stopping_rounds': EARLY_STOP,
            'environment': {'python': platform.python_version(), 'lightgbm': lgb.__version__, 'scikit-learn': sklearn.__version__,
                            'numpy': np.__version__, 'pandas': pd.__version__, 'machine': platform.machine()},
            'sets': {'train_rows': len(tr), 'validation_rows': len(va)}, 'test_set_used': False, 'trials': trials}
    return runs, comparison


def main():
    runs, comp = run()
    (ROOT / 'reports/model/training_runs.json').write_text(json.dumps(runs, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'reports/model/boosting_validation.json').write_text(json.dumps(comp, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for t in runs['trials']:
        print(t['trial'], {k: t['params'][k] for k in GRID}, t['best_iteration'], t['validation']['roc_auc'], t['validation']['pr_auc'], t['seconds'])
    print(json.dumps({k: comp[k] for k in ('best_trial', 'delta_pr_auc_vs_logreg', 'delta_roc_auc_vs_logreg', 'train_validation_gap_roc_auc')}))


if __name__ == '__main__':
    main()
