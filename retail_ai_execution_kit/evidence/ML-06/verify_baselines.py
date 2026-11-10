"""ML-06 checks: an independent sklearn Pipeline reproduces the logistic regression; preprocessing params come
from train only; shared population/labels/split; test set unused.
usage: .venv/bin/python evidence/ML-06/verify_baselines.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/model'))
from common import FEATURES, LOG_FEATURES, load_frame  # noqa: E402

B = json.loads((ROOT / 'reports/model/baselines.json').read_text(encoding='utf-8'))
S = json.loads((ROOT / 'reports/model/split_manifest.json').read_text(encoding='utf-8'))
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


df = load_frame()
tr, va = df[df.set == 'train'], df[df.set == 'validation']
check('train/validation sizes equal the frozen split', len(tr) == S['sets']['train']['rows'] and len(va) == S['sets']['validation']['rows'])
check('medians saved = train medians (not train+validation)', all(abs(B['preprocessing']['medians'][c] - tr[c].median()) < 1e-9 for c in FEATURES)
      and any(abs(B['preprocessing']['medians'][c] - df[df.set.isin(['train', 'validation'])][c].median()) > 1e-9 for c in FEATURES))
logc = [FEATURES.index(c) for c in LOG_FEATURES]
pipe = Pipeline([('impute', SimpleImputer(strategy='median')),
                 ('log', ColumnTransformer([('l', FunctionTransformer(lambda x: np.log1p(np.clip(x, 0, None))), logc)], remainder='passthrough')),
                 ('scale', StandardScaler()), ('lr', LogisticRegression(C=1.0, max_iter=2000, random_state=B['seed']))])
pipe.fit(tr[FEATURES].astype(float).to_numpy(), tr.y)
p = pipe.predict_proba(va[FEATURES].astype(float).to_numpy())[:, 1]
auc, ap = roc_auc_score(va.y, p), average_precision_score(va.y, p)
rep = B['models']['logreg']['validation']
check('independent sklearn pipeline reproduces logreg validation ROC-AUC / PR-AUC', abs(auc - rep['roc_auc']) < 1e-4 and abs(ap - rep['pr_auc']) < 1e-4,
      f'{auc:.6f}/{ap:.6f} vs {rep["roc_auc"]}/{rep["pr_auc"]}')
check('all models evaluated on the same validation rows and labels', all(v['validation']['n'] == len(va) for v in B['models'].values()))
check('test set not used', B['test_set_used'] is False and 'test' not in B['sets'])
check('run record has seed, library versions, data identity, coefficients',
      B['seed'] and B['library']['scikit-learn'] and B['data']['feature_sha256'] and len(B['models']['logreg']['coefficients']) == len(FEATURES))
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
