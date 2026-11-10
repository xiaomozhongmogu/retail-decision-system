"""DATA-10: deterministic transforms, time features, and a train-only fitting guard.

Two kinds of transforms are kept apart:

1. Deterministic, row-wise transforms (no parameters learned from data):
   time parts from purchase_ts, approval lag, delivery days recomputed from
   timestamps (two lateness definitions), log1p of amounts. Safe to apply to
   any period. Written to data/processed/transformed/<key>/orders.parquet.
2. Fitted transforms (scaling, quantile bins, clipping thresholds, K-Means):
   only through TrainOnlyFit, which refuses rows at or after the training
   cutoff. ML-03/ML-05 use it; this module tests it.

usage: .venv/bin/python src/retail_bi/data/transform.py --integrated-dir <dir> \
         --out-root data/processed/transformed --audit reports/data/transform_audit.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

TRANSFORM_VERSION = 'transform-v1'
LOG_COLUMNS = ['merch_usd', 'shipping_usd', 'order_value_usd']


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def deterministic(orders: pd.DataFrame) -> pd.DataFrame:
    """Row-wise features; every output depends only on the same row."""
    o = orders.copy()
    p = o['purchase_ts']
    o['purchase_date'] = p.dt.date
    o['purchase_week_start'] = (p.dt.normalize() - pd.to_timedelta(p.dt.day_of_week, unit='D')).dt.date
    o['purchase_month'] = p.dt.strftime('%Y-%m')
    o['purchase_dow'] = p.dt.day_of_week            # Monday = 0
    o['purchase_hour_utc'] = p.dt.hour
    o['approval_lag_hours'] = (o['approved_ts'] - p).dt.total_seconds() / 3600
    # delivery recomputed from timestamps; two lateness definitions kept apart (DATA-06)
    o['delivery_days_floor'] = np.floor((o['delivered_ts'] - p).dt.total_seconds() / 86400)
    o['late_by_days'] = (o['delivery_days_floor'] > o['estimated_delivery_days']).where(o['delivered_ts'].notna())
    est = pd.to_datetime(o['estimated_delivery_date']).dt.tz_localize('UTC')
    o['late_by_date'] = (o['delivered_ts'].dt.normalize() > est).where(o['delivered_ts'].notna())
    for c in LOG_COLUMNS:
        o[f'log1p_{c}'] = np.log1p(o[c].astype(float))
    o['multi_payment'] = o['payment_rows'] > 1
    o['has_review'] = o['review_score'].notna()
    return o


class TrainOnlyFit:
    """Fit parameters only on rows strictly before train_end.

    fit() raises if any row at or after train_end is passed, so a full-period
    frame cannot be used by mistake. transform() can be applied to any period.
    Supported: 'standard' (mean/std), 'quantile_bins' (edges), 'clip' (upper quantile).
    """

    def __init__(self, kind: str, column: str, time_column: str, train_end, **kw):
        self.kind, self.column, self.time_column = kind, column, time_column
        self.train_end = pd.Timestamp(train_end)
        self.kw, self.params = kw, None

    def fit(self, df: pd.DataFrame):
        t = pd.to_datetime(df[self.time_column])
        if (t >= self.train_end).any():
            raise ValueError(f'fit data reaches {t.max()} >= train_end {self.train_end}; fitted transforms use training rows only')
        x = df[self.column].astype(float).dropna()
        if self.kind == 'standard':
            self.params = {'mean': float(x.mean()), 'std': float(x.std(ddof=0)) or 1.0}
        elif self.kind == 'quantile_bins':
            q = self.kw.get('q', 5)
            self.params = {'edges': [float(v) for v in np.unique(x.quantile(np.linspace(0, 1, q + 1)).values)]}
        elif self.kind == 'clip':
            self.params = {'upper': float(x.quantile(self.kw.get('upper_q', 0.99)))}
        else:
            raise ValueError(self.kind)
        self.params.update({'fitted_rows': int(len(x)), 'train_end': str(self.train_end),
                            'fit_time_max': str(t.max())})
        return self

    def transform(self, df: pd.DataFrame) -> pd.Series:
        if self.params is None:
            raise ValueError('not fitted')
        x = df[self.column].astype(float)
        if self.kind == 'standard':
            return (x - self.params['mean']) / self.params['std']
        if self.kind == 'quantile_bins':
            e = self.params['edges']
            return pd.Series(np.clip(np.searchsorted(e[1:-1], x, side='right') + 1, 1, len(e) - 1), index=df.index)
        return x.clip(upper=self.params['upper'])


def skew(x: pd.Series) -> float:
    return round(float(pd.Series(x).astype(float).skew()), 4)


def build(integrated_dir: Path, out_root: Path) -> dict:
    integrated_dir, out_root = integrated_dir.resolve(), out_root.resolve()
    man = json.loads((integrated_dir / 'manifest.json').read_text(encoding='utf-8'))
    for o in man['outputs']:
        if sha(integrated_dir / o['path']) != o['sha256']:
            raise ValueError(f'integrated output changed: {o["path"]}')
    orders = pd.read_parquet(integrated_dir / 'orders.parquet')
    out = deterministic(orders)
    key = f'{sha(integrated_dir / "manifest.json")[:16]}-{TRANSFORM_VERSION}'

    # before/after comparisons
    delivered = out[out['delivered_ts'].notna()]
    audit = {
        'task_id': 'DATA-10', 'version': TRANSFORM_VERSION, 'key': key,
        'integrated_manifest_sha256': sha(integrated_dir / 'manifest.json'),
        'rows_in': len(orders), 'rows_out': len(out),
        'new_columns': [c for c in out.columns if c not in orders.columns],
        'deterministic_transforms': {
            'time_parts': '下单日期、周起始日（周一）、月份、星期、UTC 小时：由 purchase_ts 逐行拆出，不学习参数',
            'approval_lag_hours': {'min': float(out.approval_lag_hours.min()), 'max': float(out.approval_lag_hours.max()),
                                   'nulls_equal_cancelled': int(out.approval_lag_hours.isna().sum()) == int((out.order_status == 'cancelled').sum())},
            'delivery_days_floor': {'delivered_orders': int(len(delivered)),
                                    'rule': '向下取整的（送达 - 下单）天数；DATA-06 实测与源 actual_delivery_days 完全一致'},
            'late_rates_on_delivered': {'late_by_days(generator definition)': round(float(delivered.late_by_days.astype(bool).mean()), 4),
                                        'late_by_date': round(float(delivered.late_by_date.astype(bool).mean()), 4)},
            'log1p_amounts': {c: {'skew_before': skew(out[c]), 'skew_after': skew(out[f'log1p_{c}'])} for c in LOG_COLUMNS},
        },
        'availability': '派生列只用同一订单已有字段；送达类特征在 as_of 使用前必须按 delivered_ts < as_of 截断（ML-03），审批类按 approved_ts < as_of',
    }
    # train-only fitting guard demonstration (no model is trained here)
    train_end = pd.Timestamp('2025-07-01', tz='UTC')
    train = out[out.purchase_ts < train_end]
    full_fit_refused = False
    try:
        TrainOnlyFit('standard', 'log1p_merch_usd', 'purchase_ts', train_end).fit(out)
    except ValueError:
        full_fit_refused = True
    fits = {k: TrainOnlyFit(k, 'merch_usd', 'purchase_ts', train_end, **kw).fit(train).params
            for k, kw in [('standard', {}), ('quantile_bins', {'q': 5}), ('clip', {'upper_q': 0.99})]}
    full_mean = float(out.merch_usd.astype(float).mean())
    audit['train_only_fitting'] = {
        'example_train_end': str(train_end), 'train_rows': int(len(train)),
        'fit_on_full_period_refused': full_fit_refused,
        'fitted_params_on_training_rows': fits,
        'full_period_mean_for_comparison': round(full_mean, 4),
        'note': '示例切分只用于测试防护；正式切分由 ML-04 冻结。拟合参数随训练期变化，验证/测试期只调用 transform',
    }
    audit['checks'] = {
        'row_count_preserved': len(out) == len(orders),
        'approval_lag_nulls_are_cancelled': audit['deterministic_transforms']['approval_lag_hours']['nulls_equal_cancelled'],
        'approval_lag_max_24h': bool(out.approval_lag_hours.max() <= 24),
        'log1p_reduces_skew': all(v['skew_after'] < v['skew_before'] for v in audit['deterministic_transforms']['log1p_amounts'].values()),
        'fit_on_full_period_refused': full_fit_refused,
        'train_fit_uses_only_train_rows': all(pd.Timestamp(p['fit_time_max']) < train_end for p in fits.values()),
    }

    out_root.mkdir(parents=True, exist_ok=True)
    target = out_root / key
    rel = 'orders.parquet'
    stage = Path(tempfile.mkdtemp(dir=out_root, prefix=f'{key}.partial-'))
    try:
        out.to_parquet(stage / rel, index=False)
        h = sha(stage / rel)
        if target.exists():
            old = json.loads((target / 'manifest.json').read_text(encoding='utf-8'))
            audit['rerun_identical_to_existing'] = old['outputs'][0]['sha256'] == h and sha(target / rel) == h
            audit['checks']['rerun_reproducible'] = audit['rerun_identical_to_existing']
            if not audit['rerun_identical_to_existing']:
                raise ValueError('rerun produced a different file for the same version; bump TRANSFORM_VERSION')
        else:
            (stage / 'manifest.json').write_text(json.dumps({'key': key, 'outputs': [{'path': rel, 'sha256': h, 'rows': len(out)}]}, indent=2) + '\n')
            stage.rename(target)
            stage = None
            audit['rerun_identical_to_existing'] = None
        audit['outputs'] = [{'path': rel, 'sha256': h, 'rows': len(out)}]
    finally:
        if stage is not None:
            shutil.rmtree(stage)
    audit['all_checks_passed'] = all(bool(v) for v in audit['checks'].values())
    return audit


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--integrated-dir', type=Path, required=True)
    ap.add_argument('--out-root', type=Path, required=True)
    ap.add_argument('--audit', type=Path, required=True)
    a = ap.parse_args()
    audit = build(a.integrated_dir, a.out_root)
    a.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps(audit['checks'], ensure_ascii=False, default=str))
    raise SystemExit(0 if audit['all_checks_passed'] else 1)


if __name__ == '__main__':
    main()
