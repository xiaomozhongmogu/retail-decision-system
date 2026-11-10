"""ML-08 checks: freeze record complete and made without the test set; the frozen JSON model scores exactly like
an sklearn refit; decisions follow the recorded validation numbers.
usage: .venv/bin/python evidence/ML-08/verify_selection.py"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/model'))
from common import FEATURES, load_frame  # noqa: E402
from model_select import fit_lr  # noqa: E402

S = json.loads((ROOT / 'reports/model/model_selection.json').read_text(encoding='utf-8'))
M = json.loads((ROOT / S['model_file']).read_text(encoding='utf-8'))
src = (ROOT / 'src/retail_bi/model/model_select.py').read_text(encoding='utf-8')
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


def score_json(model, X: pd.DataFrame):
    pp = model['preprocessing']
    Z = X[model['features']].astype(float).fillna(pp['medians'])
    for c in pp['log1p_columns']:
        Z[c] = np.log1p(Z[c].clip(lower=0))
    Z = (Z - pd.Series(pp['mean'])) / pd.Series(pp['std'])
    z = Z[model['features']].to_numpy() @ np.array([model['coefficients'][f] for f in model['features']]) + model['intercept']
    return 1 / (1 + np.exp(-z))


df = load_frame()
tv = df[df.set.isin(['train', 'validation'])]
prep, lr = fit_lr(tv)
ref = lr.predict_proba(prep.transform(tv[FEATURES]))[:, 1]
mine = score_json(M, tv)
check('frozen JSON model reproduces sklearn refit probabilities', np.allclose(mine, ref, atol=1e-10), f'max diff {np.abs(mine - ref).max():.2e}')
check('frozen model fitted on train + validation only', M['fitted_rows'] == len(tv) and M['features'] == FEATURES)
check('test set not loaded during selection', S['test_set_used'] is False and "'test'" not in src)
check('freeze time recorded and no-switch rule stated', S['frozen_at'] and '不得因测试结果' in S['no_switch_after_test'])
cm = S['calibration']['cross_fitted_brier_by_method']
check('calibration choice follows cross-fitted Brier', S['calibration']['choice'] == ('none' if cm['none'] - min(cm.values()) < 1e-4 else min(cm, key=cm.get)), cm)
rk = S['ranking_policy']['validation_within_week']
check('ranking policy = best validation within-week lift@10%', S['ranking_policy']['choice'] == max(rk, key=lambda c: rk[c]['weekly_lift@10%']), S['ranking_policy']['choice'])
check('no fixed 0.5 threshold; capacity K recorded', S['threshold_and_capacity']['probability_threshold'] is None and S['threshold_and_capacity']['capacity_share_per_week'] == 0.10)
print('model file sha256', hashlib.sha256((ROOT / S['model_file']).read_bytes()).hexdigest())
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
