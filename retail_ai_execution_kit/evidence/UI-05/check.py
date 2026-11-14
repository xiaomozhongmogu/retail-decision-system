"""UI-05 check: render the prediction page with AppTest, compare with the frozen model reports and the release,
drive the K / threshold what-if, and confirm nothing frozen is written.
usage: .venv/bin/python evidence/UI-05/check.py"""
import hashlib
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


FROZEN = sorted((ROOT / 'reports/model').glob('*.json')) + [ROOT / 'models/repurchase-logreg-v1.json', ROOT / 'warehouse/releases/current.json']
before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in FROZEN}


def page():
    at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=120)
    at.run()
    at.switch_page('src/retail_bi/ui/pages/prediction.py')
    at.run()
    return at


def text(at):
    return '\n'.join([m.value for m in at.markdown] + [c.value for c in at.caption] + [str(m.label) + ' ' + str(m.value) for m in at.metric]
                     + [x.value for x in at.info] + [x.value for x in at.warning] + [d.value.to_csv() for d in at.dataframe])


tm = json.loads((ROOT / 'reports/model/test_metrics.json').read_text())
sp = json.loads((ROOT / 'reports/model/split_manifest.json').read_text())
at = page()
t = text(at)
check('page renders without exception; five tabs', not at.exception and [x.label for x in at.tabs] == ['样本与切分', '基线与选模', '测试结果（冻结）', '误差分析', '名单试算'],
      [str(e.value) for e in at.exception])
split = next(d.value for d in at.dataframe if '集合' in d.value.columns).set_index('集合')
check('sample ranges equal split_manifest (train/validation/test rows and positives)', all(int(split.loc[z, '样本行（客户×周）']) == sp['sets'][k]['rows'] and int(split.loc[z, '正例']) == sp['sets'][k]['positives']
      for k, z in (('train', '训练'), ('validation', '验证'), ('test', '测试'))))
check('sample rows labelled customer x week, not raw orders', '样本行是客户×周' in t and '不是原始订单数' in t)
tt = next(d.value for d in at.dataframe if '方法' in d.value.columns).set_index('方法')
ci = tm['scores']['p_model']['roc_auc_95ci']      # headers are readable names since UI-07; CI shown as "a–b"
check('frozen test metrics with CI, rule baselines and base rate shown', abs(float(tt.loc['冻结模型', 'ROC-AUC']) - tm['scores']['p_model']['roc_auc']) <= 5e-5 and tt.loc['冻结模型', 'ROC-AUC 95% 区间'] == f'{ci[0]:.3f}–{ci[1]:.3f}'
      and '规则：近 90 天订单数' in tt.index and '基率' in tt.index)
check('calibration (reliability) chart and ECE shown', len([c for c in at.get('vega_lite_chart')]) >= 1 and f"ECE {tm['scores']['p_model']['ece']}" in t)
check('error analysis: weekly top-10% confusion matrix shown', 'TP 107、FP 1695、FN 1171、TN 15029' in t)
check('feature effects stated as non-causal', '模型关联，不是因果' in t and '因素是模型解释，不是因果效果' in t)

con, _ = open_current()
rank = [r[0] for r in con.execute("""SELECT s.customer_id FROM ads.model_scores s JOIN ads.customer_profile_latest p USING (customer_id)
    WHERE s.as_of = (SELECT max(as_of) FROM ads.model_scores) AND s.applicability = 'in_population'
    ORDER BY p.frequency_90d DESC, p.monetary_90d_usd DESC, s.customer_id""").fetchall()]
oop = con.execute("SELECT count(*) FROM ads.model_scores WHERE applicability = 'out_of_population' AND as_of = (SELECT max(as_of) FROM ads.model_scores)").fetchone()[0]
p_of = dict(con.execute("SELECT customer_id, p_repurchase_30d FROM ads.model_scores WHERE as_of = (SELECT max(as_of) FROM ads.model_scores)").fetchall())
con.close()
lst = next(d.value for d in at.dataframe if '客户编号' in d.value.columns)
check('default what-if = frozen K 10%: 70 of 704, ordered by 90-day orders then amount (independent SQL)', len(lst) == round(len(rank) * 0.10) == 70 and list(lst['客户编号']) == rank[:70])
check('out-of-population customers counted as not applicable and absent from the list', f'母体外 {oop:,} 人不适用模型' in t and not set(lst['客户编号']) & {c for c, p in p_of.items() if p is None})
[s for s in at.slider if s.key == 'k'][0].set_value(0.2).run()
lst2 = next(d.value for d in at.dataframe if '客户编号' in d.value.columns)
check('K = 20% gives the top 141 of the same ranking', len(lst2) == round(704 * 0.2) and list(lst2['客户编号']) == rank[:len(lst2)])
[s for s in at.slider if s.key == 'pmin'][0].set_value(0.08).run()
lst3 = next(d.value for d in at.dataframe if '客户编号' in d.value.columns)
want = [c for c in rank[:141] if p_of[c] >= 0.08]
check('probability floor 0.08 keeps exactly those top-K customers with p >= 0.08', list(lst3['客户编号']) == want and len(want) < 141, (len(lst3), len(want)))
check('what-if labelled as trial, frozen rule restated', '上面的滑块只是试算，不修改冻结记录或测试结果' in text(at))
check('no city, zip or personal attributes in the list', not re.search(r'city|zip|customer_state', ' '.join(lst3.columns)))
after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in FROZEN}
check('frozen reports, model file and release pointer unchanged after the what-if', before == after, [k for k in before if before[k] != after[k]])
print(f'{sum(ok)}/{len(ok)} checks passed')
sys.exit(0 if all(ok) else 1)
