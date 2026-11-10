"""ML-12: model manifest + fixed-sample fixture, and a fresh-process reproduction check.
usage: .venv/bin/python evidence/ML-12/publish_model.py         (writes reports/model/model_manifest.json, reports/model/model_fixture.json)
       .venv/bin/python evidence/ML-12/publish_model.py reproduce   (new process: load model, recompute features, compare)"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for p in ('src/retail_bi/model', 'src/retail_bi/warehouse', 'src/retail_bi/features'):
    sys.path.insert(0, str(ROOT / p))
TOL = 1e-9


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


if sys.argv[1:] == ['reproduce']:
    import pandas as pd
    from scoring import FEATURES, load_model, score_frame
    from customer_features import compute
    from runtime import open_current
    fx = json.loads((ROOT / 'reports/model/model_fixture.json').read_text(encoding='utf-8'))
    man = json.loads((ROOT / 'reports/model/model_manifest.json').read_text(encoding='utf-8'))
    assert sha(ROOT / man['model_file']) == man['model_sha256'], 'model file hash differs from manifest'
    model = load_model()
    con, ptr = open_current()
    keys = pd.DataFrame({'customer_id': [r['customer_id'] for r in fx['rows']], 'as_of': [r['as_of'] for r in fx['rows']],
                         'y': pd.array([pd.NA] * len(fx['rows']), dtype='Int64')})
    f = compute(con, keys).set_index(['customer_id', 'as_of']).loc[list(zip(keys.customer_id, keys.as_of))].reset_index()
    con.close()
    p, _ = score_frame(model, f[FEATURES])
    exp = np.array([r['p_repurchase_30d'] for r in fx['rows']])
    diff = float(np.abs(p - exp).max())
    print(json.dumps({'rows': len(exp), 'max_abs_diff': diff, 'tolerance': TOL, 'release': ptr['version'], 'passed': diff <= TOL}))
    sys.exit(0 if diff <= TOL else 1)

from common import load_frame  # noqa: E402
from evaluate import score_frozen  # noqa: E402
sel = json.loads((ROOT / 'reports/model/model_selection.json').read_text(encoding='utf-8'))
runs = json.loads((ROOT / 'reports/model/training_runs.json').read_text(encoding='utf-8'))
mpath = ROOT / sel['model_file']
model = json.loads(mpath.read_text(encoding='utf-8'))
df = load_frame()
te = df[df.set == 'test'].sample(20, random_state=7).sort_values(['as_of', 'customer_id'])
p = score_frozen(model, te)
fixture = {'model_version': model['model_version'], 'tolerance': TOL,
           'rows': [{'customer_id': c, 'as_of': a, 'p_repurchase_30d': float(x)} for c, a, x in zip(te.customer_id, te.as_of, p)]}
(ROOT / 'reports/model/model_fixture.json').write_text(json.dumps(fixture, indent=2) + '\n', encoding='utf-8')
manifest = {'task_id': 'ML-12', 'model_version': model['model_version'], 'model_file': sel['model_file'], 'model_sha256': sha(mpath),
            'bytes': mpath.stat().st_size, 'type': model['type'], 'contents': ['features (order)', 'preprocessing: medians, log1p columns, mean, std',
            'coefficients', 'intercept', 'hyperparameters', 'calibration', 'data identity'],
            'feature_version': model['feature_version'], 'feature_order': model['features'], 'target': model['target'],
            'trained_on': model['fitted_on'], 'fitted_rows': model['fitted_rows'], 'hyperparameters': model['hyperparameters'], 'calibration': model['calibration'],
            'data': model['data'], 'training_records': {'selection': 'reports/model/model_selection.json', 'selection_frozen_at': sel['frozen_at'],
            'baselines': 'reports/model/baselines.json', 'boosting_trials': 'reports/model/training_runs.json',
            'library': runs['environment']}, 'test_report': 'reports/model/test_metrics.json', 'fixture': 'reports/model/model_fixture.json',
            'reproduction_tolerance': TOL, 'storage': '模型是几 KB 的 JSON（参数而非二进制对象），虽然 models/ 默认被 Git 忽略，此文件按课程交付要求强制加入私有仓库',
            'loading': 'src/retail_bi/model/scoring.py load_model() 校验版本与特征版本后用 score_frame() 打分'}
(ROOT / 'reports/model/model_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(manifest['model_sha256'], len(fixture['rows']))
