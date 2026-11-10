"""ML-09 checks: test metrics recomputed independently; frozen model unchanged since ML-08; report complete."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/model'))
from common import load_frame  # noqa: E402
from evaluate import score_frozen  # noqa: E402

T = json.loads((ROOT / 'reports/model/test_metrics.json').read_text(encoding='utf-8'))
S = json.loads((ROOT / 'reports/model/model_selection.json').read_text(encoding='utf-8'))
md = (ROOT / 'reports/model/evaluation.md').read_text(encoding='utf-8')
ML08_SHA = '01b2b335e07bd51bd7f3da1bac0219089e04438aa8beb655e54f1dab3b0855d2'   # printed at freeze time (evidence/ML-08/verification_run.log)
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


mp = ROOT / S['model_file']
check('model file unchanged since freeze', hashlib.sha256(mp.read_bytes()).hexdigest() == ML08_SHA == T['model_file_sha256'])
df = load_frame()
te = df[df.set == 'test']
p = score_frozen(json.loads(mp.read_text()), te)
check('test ROC-AUC / PR-AUC / Brier recomputed', abs(roc_auc_score(te.y, p) - T['scores']['p_model']['roc_auc']) < 1e-6
      and abs(average_precision_score(te.y, p) - T['scores']['p_model']['pr_auc']) < 1e-6 and abs(brier_score_loss(te.y, p) - T['scores']['p_model']['brier']) < 1e-6)
check('test set size, customers, class ratio, time range reported', T['test_set']['rows'] == len(te) and T['test_set']['customers'] == te.customer_id.nunique()
      and T['test_set']['positives'] == int(te.y.sum()) and T['test_set']['as_of_range'][0] and T['test_set']['as_of_range'][1])
need = ['roc_auc', 'pr_auc', 'ks', 'f1_at_weekly_top10%', 'recall_at_weekly_top10%', 'weekly_lift@10%', 'lift@10%', 'brier', 'ece', 'roc_auc_95ci']
check('required metrics present for the model, plus baselines', all(k in T['scores']['p_model'] for k in need) and {'rule_frequency_90d', 'rule_recency', 'base_rate'} <= set(T['scores']))
ci = T['scores']['p_model']['roc_auc_95ci']
check('customer-block interval brackets the estimate and is reported', ci[0] <= T['scores']['p_model']['roc_auc'] <= ci[1] and '客户分块' in md)
check('evaluated after freeze; no promised score; weak result stated', T['evaluated_at'] > S['frozen_at'] and '没有承诺任何分数' in md and '负结果' in md)
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
