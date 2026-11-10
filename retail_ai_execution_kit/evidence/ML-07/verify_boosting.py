"""ML-07 checks: best trial reproduces exactly (deterministic), trial budget respected, test set untouched,
run record complete. usage: .venv/bin/python evidence/ML-07/verify_boosting.py"""
import json
import sys
from pathlib import Path

import lightgbm as lgb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/model'))
from common import FEATURES, load_frame, metrics  # noqa: E402

R = json.loads((ROOT / 'reports/model/training_runs.json').read_text(encoding='utf-8'))
C = json.loads((ROOT / 'reports/model/boosting_validation.json').read_text(encoding='utf-8'))
src = (ROOT / 'src/retail_bi/model/boosting.py').read_text(encoding='utf-8')
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


df = load_frame()
tr, va = df[df.set == 'train'], df[df.set == 'validation']
best = next(t for t in R['trials'] if t['trial'] == C['best_trial'])
b = lgb.train(best['params'], lgb.Dataset(tr[FEATURES].astype(float), tr.y), num_boost_round=best['best_iteration'])
m = metrics(va.y, b.predict(va[FEATURES].astype(float)))
check('best trial retrained with saved params and iteration gives identical validation metrics',
      m['roc_auc'] == best['validation']['roc_auc'] and m['pr_auc'] == best['validation']['pr_auc'], f"{m['roc_auc']}/{m['pr_auc']}")
check('trial budget: at most 8 trials, fixed grid', len(R['trials']) == 8)
check('test set never loaded or scored', R['test_set_used'] is False and "set == 'test'" not in src and 'test' not in R['sets'])
check('run record: seed, features, params, library versions, data identity, timings',
      R['seed'] and R['features'] == FEATURES and R['environment']['lightgbm'] == lgb.__version__ and R['data']['feature_sha256']
      and all('seconds' in t and 'params' in t for t in R['trials']))
check('comparison with logistic regression recorded honestly', C['delta_pr_auc_vs_logreg'] < 0 and 'ML-09' in C['note'],
      C['delta_pr_auc_vs_logreg'])
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
