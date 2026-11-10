"""ML-11 checks on the published release and the scoring functions."""
import copy
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for p in ('src/retail_bi/model', 'src/retail_bi/warehouse', 'src/retail_bi/features'):
    sys.path.insert(0, str(ROOT / p))
from scoring import FEATURES, ScoringError, get_risk_score, load_model, score_frame  # noqa: E402
from evaluate import score_frozen  # noqa: E402
from common import load_frame  # noqa: E402
from runtime import open_current, query_view  # noqa: E402

ok, res = [], []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    res.append({'check': name, 'status': 'passed' if cond else 'failed', 'detail': str(detail)})
    print('PASS' if cond else 'FAIL', name, detail)


model = load_model()
con, ptr = open_current()
S = con.execute("SELECT customer_id, as_of::VARCHAR a, applicability, p_repurchase_30d p, p_non_repurchase_30d q, model_version FROM ads.model_scores").df()
allowed = [r[0] for r in con.execute('SELECT view_name FROM meta.allowed_view').fetchall()]
con.close()
inp, outp = S[S.applicability == 'in_population'], S[S.applicability == 'out_of_population']
check('ADS score table: one row per snapshot customer at the latest as_of, with model version', len(S) == S.customer_id.nunique() and (S.model_version == model['model_version']).all(), len(S))
check('probabilities in [0,1] and complementary', inp.p.between(0, 1).all() and np.allclose(inp.p + inp.q, 1.0, atol=1e-12))
check('out-of-population rows have no probability', outp.p.isna().all() and outp.q.isna().all(), len(outp))
c_in, c_out = inp.customer_id.iloc[0], outp.customer_id.iloc[0]
r1 = get_risk_score(c_in, inp.a.iloc[0])
check('service result for an in-population customer equals the ADS table and carries version/explanation',
      r1['status'] == 'ok' and abs(r1['data']['p_repurchase_30d'] - inp.p.iloc[0]) < 1e-12 and r1['model_version'] == model['model_version']
      and r1['data']['top_factors'] and abs(r1['data']['p_non_repurchase_30d'] + r1['data']['p_repurchase_30d'] - 1) < 1e-12)
r2 = get_risk_score(c_out, outp.a.iloc[0])
check('out-of-population customer -> unsupported / out_of_population, no probability', r2['status'] == 'unsupported'
      and r2['error']['code'] == 'out_of_population' and 'p_repurchase_30d' not in r2['data'])
df = load_frame()
te = df[df.set == 'test'].head(500)
p_service, _ = score_frame(model, te[FEATURES])
check('scoring service equals the evaluated frozen scorer (ML-09) on 500 test rows', np.allclose(p_service, score_frozen(model, te), atol=1e-12))


def raises(fn):
    try:
        fn()
    except ScoringError:
        return True
    return False


check('feature order mismatch fails', raises(lambda: score_frame(model, te[list(reversed(FEATURES))])))
check('missing feature fails', raises(lambda: score_frame(model, te[FEATURES[:-1]])))
bad = te[FEATURES].copy()
bad['recency_days'] = bad['recency_days'].astype(str)
check('wrong type (text feature) fails', raises(lambda: score_frame(model, bad)))
check('unexpected model version fails', raises(lambda: load_model(expected='repurchase-logreg-v2')))
m2 = copy.deepcopy(model)
m2['feature_version'] = 'features-v0'
tmp = ROOT / 'evidence/ML-11/_wrong_feature_version.json'
tmp.write_text(json.dumps(m2))
check('model trained on another feature version fails', raises(lambda: load_model(tmp)))
tmp.unlink()
check('customer-level scores are not open to the AI query layer; summary view is', 'ads.model_scores' not in allowed and 'ads.risk_summary_latest' in allowed)
r3 = query_view('ads.risk_summary_latest')
check('summary view answers through the read-only runtime', r3['status'] == 'ok' and r3['dataset_version'] == ptr['version'], r3['rows'])
out = {'task_id': 'ML-11', 'release': ptr['version'], 'model_version': model['model_version'], 'rows': len(S), 'in_population': len(inp),
       'out_of_population': len(outp), 'mean_p_repurchase_in_population': round(float(inp.p.mean()), 4), 'checks': res, 'all_passed': all(ok)}
(ROOT / 'reports/model/scoring_checks.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
