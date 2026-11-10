"""ML-05 checks: R/F/M recomputed from orders; scaler fitted on the fit as_of only; k choice follows its rule;
segments cover the population; naming follows measured medians."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
sys.path.insert(0, str(ROOT / 'src/retail_bi/model'))
from runtime import open_current  # noqa: E402
from segments import FIT_AS_OF, APPLY_AS_OF, rfm  # noqa: E402

C = json.loads((ROOT / 'reports/model/cluster_metrics.json').read_text(encoding='utf-8'))
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


con, _ = open_current()
O = con.execute("SELECT customer_id, purchase_ts::VARCHAR p, approved_ts::VARCHAR a, merch_usd::DOUBLE m FROM dwd.fact_order").df()
fit, app = rfm(con, FIT_AS_OF), rfm(con, APPLY_AS_OF)
con.close()
O['p'], O['a'] = pd.to_datetime(O.p, utc=True), pd.to_datetime(O.a, utc=True)
t = pd.Timestamp(APPLY_AS_OF)
v = O[(O.p < t) & (O.a < t)]
w = v[v.p >= t - pd.Timedelta(days=90)]
g = w.groupby('customer_id').agg(f=('m', 'size'), m=('m', 'sum'))
g['r'] = (t - v.groupby('customer_id').p.max()).dt.total_seconds() / 86400
chk = app.set_index('customer_id').join(g, rsuffix='_x', how='left')
check('R/F/M at apply as_of recomputed from orders (same as_of, same 90-day window)',
      np.allclose(chk.r, chk.r_x) and (chk.f == chk.f_x).all() and np.allclose(chk.m, chk.m_x) and len(g) == len(app), f'{len(app)} customers')
z = np.log1p(fit[['r', 'f', 'm']].to_numpy(float))
check('scaler parameters come from the fit as_of only', np.allclose(z.mean(0), C['kmeans']['mu'], atol=1e-5) and np.allclose(z.std(0), C['kmeans']['sd'], atol=1e-5))
ks = C['kmeans']['k_comparison']
okk = [int(k) for k, v in ks.items() if v['min_cluster_share'] >= 0.05 and v['bootstrap_ari_mean'] >= 0.8]
check('k choice follows the stated rule (k = 3..6 compared)', set(ks) == {'3', '4', '5', '6'} and C['kmeans']['k_chosen'] == max(okk, key=lambda k: ks[str(k)]['silhouette']), okk)
check('rule segments and clusters cover the whole population', sum(p['customers'] for p in C['rule_segments']['apply_as_of_profile']) == len(app)
      and sum(p['customers'] for p in C['kmeans']['apply_as_of_profile']) == len(app) and sum(p['customers'] for p in C['kmeans']['fit_as_of_profile']) == len(fit))
med_r, med_m = fit.r.median(), fit.m.median()
check('cluster names follow measured medians', all(p['name'].startswith('近期' if p['r_median_days'] < med_r else '较早')
      and p['name'].endswith('高金额' if p['m_median_usd'] >= med_m else '低金额') for p in C['kmeans']['fit_as_of_profile']))
check('M not called profit or CLV', '不是利润' in (ROOT / 'reports/model/rfm_segments.md').read_text(encoding='utf-8'))
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
