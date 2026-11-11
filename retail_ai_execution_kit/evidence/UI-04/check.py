"""UI-04 check: render the customer page with AppTest and compare with views, DWD and reports; exercise the
customer lookup for in-population, dormant, no-purchase, unknown and malformed ids.
usage: .venv/bin/python evidence/UI-04/check.py"""
import json
import re
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
from runtime import open_current  # noqa: E402

ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, '' if cond else detail)


def page():
    at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=120)
    at.run()
    at.switch_page('src/retail_bi/ui/pages/customers.py')
    at.run()
    return at


def text(at):
    return '\n'.join([m.value for m in at.markdown] + [c.value for c in at.caption] + [str(m.label) + ' ' + str(m.value) for m in at.metric]
                     + [x.value for x in at.info] + [x.value for x in at.warning] + [x.value for x in at.error] + [d.value.to_csv() for d in at.dataframe])


con, _ = open_current()
Q = lambda s, p=None: con.execute(s, p or []).fetchall()  # noqa: E731
at = page()
t = text(at)
check('page renders without exception; five tabs', not at.exception and [x.label for x in at.tabs] == ['生命周期阶段', '价值群', '复购风险', 'cohort 留存', '查看客户'],
      [str(e.value) for e in at.exception])
mets = {m.label: m.value for m in at.metric}
st_ = dict(Q("SELECT lifecycle_state, count(*) FROM ads.customer_profile_latest GROUP BY 1"))
check('stage counts equal the latest snapshot', all(mets[z] == f'{st_[s]:,}' for s, z in [('new', '新客'), ('active', '活跃'), ('at_risk', '沉默预警'), ('dormant', '沉睡')]), mets)
tot = Q('SELECT count(*) FROM dwd.dim_customer')[0][0]
check('no-visible-purchase customers = all customers - snapshot customers; anonymous = 0', f'**{tot - sum(st_.values()):,}**' in t and '匿名 **0**' in t)
dorm = Q("SELECT count(*) FILTER (WHERE recency_days >= 730), max(recency_days) FROM ads.customer_profile_latest WHERE lifecycle_state = 'dormant'")[0]
bk = next(d.value for d in at.dataframe if '距上次购买' in d.value.columns)
check('long-dormant customers (>= 730 days) shown as dormant with correct count', int(bk.set_index('距上次购买').loc['730 天以上', '客户']) == dorm[0] and '不标为已流失' in t, bk)
seg = json.loads((ROOT / 'reports/model/cluster_metrics.json').read_text())
rs = next(d.value for d in at.dataframe if '规则分群' in d.value.columns)
check('value segments equal the ML-05 report (4 groups, 704 customers)', int(rs['客户'].sum()) == sum(p['customers'] for p in seg['rule_segments']['apply_as_of_profile']) == 704 and len(rs) == 4)
inpop = Q("SELECT count(*) FROM ads.customer_profile_latest WHERE frequency_90d >= 1")[0][0]
check('segment population equals in-population customers of the current release', inpop == 704, inpop)
rk = Q("SELECT customers_scored, mean_p_repurchase_30d, out_of_population_customers FROM ads.risk_summary_latest")[0]
check('risk shown as average only, with weak-model warning, from risk_summary_latest', mets['已评分客户'] == f'{rk[0] - rk[2]:,}' and mets['平均 30 天复购概率'] == f'{rk[1]:.1%}'
      and any('接近随机' in w.value for w in at.warning) and '高风险名单' in t, (mets, rk))
co = Q("SELECT count(*) FROM ads.cohort_retention WHERE immature AND months_since_first BETWEEN 1 AND 12")[0][0]
check('cohort immature cells counted and labelled 未成熟 (not 0%)', f'未成熟格子（月份未结束，{co} 格）' in t and co > 0, co)
check('no age, channel, city, zip or generator labels on the page', not re.search(r'年龄：|渠道：|customer_city|zip|customer_segment|customer_lifecycle_stage', t))

def look(cid):
    a = page()
    [w for w in a.text_input if w.key == 'cid'][0].set_value(cid).run()
    return a, text(a)
cid_active = Q("SELECT customer_id FROM ads.customer_profile_latest WHERE lifecycle_state = 'active' AND frequency_90d >= 2 ORDER BY customer_id LIMIT 1")[0][0]
a, ta = look(cid_active)
p = Q("SELECT recency_days, frequency_90d, monetary_90d_usd FROM ads.customer_profile_latest WHERE customer_id = ?", [cid_active])[0]
check('lookup in-population customer: stage with rule basis, value segment, model reference, observable fields', '活跃 — 最近一次购买距 as_of' in ta and f'{p[0]:.1f} 天' in ta
      and '高价值' in ta and '适用性 in_population' in ta and 'customer_region' in ta and not a.exception, ta[:300])
cid_dorm = Q("SELECT customer_id FROM ads.customer_profile_latest WHERE lifecycle_state = 'dormant' ORDER BY recency_days DESC LIMIT 1")[0][0]
a, td = look(cid_dorm)
check('lookup longest-dormant customer: dormant, not lost; out of model population', '沉睡 — ' in td and '不表示已流失' in td and '不在 RFM 分群母体' in td and '无（母体外）' in td)
cid_none = Q("SELECT customer_id FROM dwd.dim_customer WHERE customer_id NOT IN (SELECT customer_id FROM ads.customer_profile_latest) ORDER BY 1 LIMIT 1")[0][0]
a, tn = look(cid_none)
check('lookup customer with no visible purchase: unknown_no_purchase', '未知：尚无购买' in tn and '不进入快照' in tn)
a, tu = look('customer_999999')
check('unknown id: empty state', any('没有这个客户编号' in i.value for i in a.info))
a, tb = look("customer_1' OR 1=1 --")
check('malformed id rejected before querying', any('格式应为' in e.value for e in a.error))
check('all real customer ids match the accepted format', Q("SELECT count(*) FROM dwd.dim_customer WHERE NOT regexp_matches(customer_id, '^customer_[0-9]{6}$')")[0][0] == 0)
con.close()
print(f'{sum(ok)}/{len(ok)} checks passed')
sys.exit(0 if all(ok) else 1)
