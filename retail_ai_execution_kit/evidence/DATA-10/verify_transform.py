"""DATA-10 checks: document coverage, independent recompute of transforms,
train-only guard, reproducibility.
usage: .venv/bin/python evidence/DATA-10/verify_transform.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/data'))
from transform import TrainOnlyFit  # noqa: E402

A = json.loads((ROOT / 'reports/data/transform_audit.json').read_text(encoding='utf-8'))
P = json.loads((ROOT / 'reports/data/profile_before.json').read_text(encoding='utf-8'))
doc = (ROOT / 'docs/preprocessing_methods.md').read_text(encoding='utf-8')
out = pd.read_parquet(ROOT / 'data/processed/transformed' / A['key'] / 'orders.parquet')
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


check('doc covers four categories with handling', all(f'## {i}. {h}' in doc for i, h in [(1, '清理'), (2, '集成'), (3, '归约'), (4, '转换')]))
check('doc gives not-applicable reasons (PCA) rather than only method names', '维度归约（PCA 等） | 不适用 |' in doc)
check('doc states sampling and dev-sample rule', '不抽样' in doc and '开发样本' in doc and '不取文件前 N 行' in doc)
check('doc before/after numbers match reports',
      f'{P["money"]["order_items.item_price_usd"]["extreme_above_q3_plus_3iqr"]} 行' in doc
      and f'{A["deterministic_transforms"]["late_rates_on_delivered"]["late_by_date"]:.2%}' in doc
      and f'{A["deterministic_transforms"]["late_rates_on_delivered"]["late_by_days(generator definition)"]:.2%}' in doc
      and f'{A["train_only_fitting"]["train_rows"]:,} 单' in doc)
# independent recompute
p = out.purchase_ts
check('time parts recomputed', (out.purchase_dow == p.dt.day_of_week).all() and (out.purchase_month == p.dt.strftime('%Y-%m')).all()
      and (pd.to_datetime(out.purchase_week_start) == (p.dt.tz_localize(None).dt.normalize() - pd.to_timedelta(p.dt.day_of_week, 'D'))).all())
d = out[out.delivered_ts.notna()]
days = ((d.delivered_ts - d.purchase_ts).dt.total_seconds() // 86400)
check('delivery days recomputed', (days == d.delivery_days_floor).all())
lbd = d.delivered_ts.dt.tz_localize(None).dt.normalize() > pd.to_datetime(d.estimated_delivery_date)
check('late_by_date recomputed', (lbd == d.late_by_date.astype(bool)).all() and round(lbd.mean(), 4) == A['deterministic_transforms']['late_rates_on_delivered']['late_by_date'])
check('log1p recomputed', np.allclose(out.log1p_merch_usd, np.log1p(out.merch_usd.astype(float))))
check('undelivered rows have null lateness', out[out.delivered_ts.isna()].late_by_date.isna().all())
# guard
te = pd.Timestamp('2025-07-01', tz='UTC')
refused = False
try:
    TrainOnlyFit('standard', 'merch_usd', 'purchase_ts', te).fit(pd.concat([out[out.purchase_ts < te], out[out.purchase_ts >= te].head(1)]))
except ValueError:
    refused = True
check('guard refuses training rows plus a single row after train_end', refused)
f = TrainOnlyFit('standard', 'merch_usd', 'purchase_ts', te).fit(out[out.purchase_ts < te])
tr = out[out.purchase_ts < te].merch_usd.astype(float)
check('fitted params equal training-only stats', abs(f.params['mean'] - tr.mean()) < 1e-9 and abs(f.params['std'] - tr.std(ddof=0)) < 1e-9)
check('audit records rerun reproducible', A['checks'].get('rerun_reproducible') is True and A['all_checks_passed'])
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
