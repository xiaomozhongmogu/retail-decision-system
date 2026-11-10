"""Shared model inputs and metric definitions (ML-06 onward). Every model uses the same population
(target-v1), labels, split (split-v1), feature order (features-v1) and these metric functions.

Positive class = repurchase within 30 days (y = 1). Scores are P(y = 1).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score

ROOT = Path(__file__).resolve().parents[3]
import sys
sys.path.insert(0, str(ROOT / 'src/retail_bi/features'))
sys.path.insert(0, str(ROOT / 'src/retail_bi/model'))
from customer_features import FEATURES  # noqa: E402
from split import assign, SETS  # noqa: E402

LOG_FEATURES = ['recency_days', 'tenure_days', 'merch_7d', 'merch_30d', 'merch_90d', 'merch_all_time', 'aov_all_time',
                'orders_all_time', 'gap_mean_days', 'gap_last_days', 'products_90d', 'delivered_count']


def load_frame() -> pd.DataFrame:
    meta = json.loads((ROOT / 'reports/model/feature_build.json').read_text(encoding='utf-8'))
    df = pd.read_parquet(ROOT / meta['file'])
    df['set'] = assign(df.as_of)
    return df


def data_identity() -> dict:
    meta = json.loads((ROOT / 'reports/model/feature_build.json').read_text(encoding='utf-8'))
    split = json.loads((ROOT / 'reports/model/split_manifest.json').read_text(encoding='utf-8'))
    return {'feature_file': meta['file'], 'feature_sha256': meta['sha256'], 'feature_version': meta['feature_version'],
            'release': meta['release'], 'split_version': split['split_version'], 'target': 'target-v1'}


def lift_at(y, s, frac):
    n = max(1, int(round(len(y) * frac)))
    idx = np.argsort(-np.asarray(s), kind='stable')[:n]
    yk = np.asarray(y)[idx]
    return float(yk.mean() / np.mean(y)), float(yk.sum() / np.sum(y))      # lift, recall


def ks(y, s):
    y, s = np.asarray(y), np.asarray(s)
    order = np.argsort(-s, kind='stable')
    yp = np.cumsum(y[order]) / y.sum()
    yn = np.cumsum(1 - y[order]) / (1 - y).sum()
    return float(np.max(np.abs(yp - yn)))


def metrics(y, s, prob=True) -> dict:
    """Ranking metrics for any score; probability metrics only when s is a probability."""
    y, s = np.asarray(y).astype(int), np.asarray(s, dtype=float)
    out = {'n': int(len(y)), 'positives': int(y.sum()), 'positive_rate': round(float(y.mean()), 6),
           'roc_auc': round(float(roc_auc_score(y, s)), 6), 'pr_auc': round(float(average_precision_score(y, s)), 6),
           'ks': round(ks(y, s), 6)}
    for frac in (0.05, 0.10, 0.20):
        lift, rec = lift_at(y, s, frac)
        out[f'lift@{int(frac * 100)}%'] = round(lift, 4)
        out[f'recall@{int(frac * 100)}%'] = round(rec, 4)
    if prob:
        p = np.clip(s, 1e-6, 1 - 1e-6)
        out['brier'] = round(float(brier_score_loss(y, p)), 6)
        out['log_loss'] = round(float(log_loss(y, p)), 6)
        out['mean_pred'] = round(float(p.mean()), 6)
    return out
