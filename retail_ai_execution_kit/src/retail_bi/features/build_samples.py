"""ML-02: build supervised samples (customer x as_of) from the point-in-time snapshot and the label table.

A sample exists when the customer is in the target-v1 population at as_of (frequency_90d >= 1, i.e. a valid
purchase in [as_of - 90d, as_of)) AND the 30-day label is mature (label_matured_at <= data cutoff). Later as_of
points are right-censored and excluded. Windows are left-closed, right-open:
  features  [.., as_of)          purchase_ts < as_of and approved_ts < as_of        (DW-05 snapshot)
  label     [as_of, as_of+30d)   purchase in window and approved_ts < as_of + 31d   (DW-05 labels)

usage: .venv/bin/python src/retail_bi/features/build_samples.py
writes data/processed/model/samples-<release>-target-v1.parquet (git-ignored) and reports/model/sample_audit.json
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'warehouse'))
from db import ROOT  # noqa: E402

TARGET = 'target-v1'
SNAPSHOT_VERSION, LABEL_VERSION, HORIZON = 'snapshot-v1', 'label-repurchase-v1', 30

SAMPLE_SQL = f"""
SELECT s.customer_id, s.as_of::VARCHAR AS as_of, s.feature_window_start::VARCHAR AS feature_window_start,
       l.label_matured_at::VARCHAR AS label_matured_at, l.y::INT AS y,
       s.recency_days, s.frequency_90d, s.monetary_90d_usd::DOUBLE AS monetary_90d_usd, s.orders_all_time,
       s.merch_all_time_usd::DOUBLE AS merch_all_time_usd, s.tenure_days, s.lifecycle_state
FROM dws.customer_snapshot s
JOIN dws.label_repurchase l USING (customer_id, as_of)
WHERE s.snapshot_version = '{SNAPSHOT_VERSION}' AND l.label_version = '{LABEL_VERSION}' AND l.horizon_days = {HORIZON}
  AND s.frequency_90d >= 1
ORDER BY s.as_of, s.customer_id
"""


def build_samples(con):
    df = con.execute(SAMPLE_SQL).df()
    funnel = {
        'snapshot_rows': con.execute(f"SELECT count(*) FROM dws.customer_snapshot WHERE snapshot_version = '{SNAPSHOT_VERSION}'").fetchone()[0],
        'snapshot_rows_in_population': con.execute(f"SELECT count(*) FROM dws.customer_snapshot WHERE snapshot_version = '{SNAPSHOT_VERSION}' AND frequency_90d >= 1").fetchone()[0],
        'as_of_points_snapshot': con.execute(f"SELECT count(DISTINCT as_of) FROM dws.customer_snapshot WHERE snapshot_version = '{SNAPSHOT_VERSION}'").fetchone()[0],
        'as_of_points_with_mature_labels': con.execute(f"SELECT count(DISTINCT as_of) FROM dws.label_repurchase WHERE label_version = '{LABEL_VERSION}'").fetchone()[0],
    }
    funnel['as_of_points_right_censored'] = funnel['as_of_points_snapshot'] - funnel['as_of_points_with_mature_labels']
    return df, funnel


def main():
    from runtime import open_current
    con, ptr = open_current()
    df, funnel = build_samples(con)
    con.close()
    out_dir = ROOT / 'data/processed/model'
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f'samples-{ptr["version"]}-{TARGET}.parquet'
    df.to_parquet(path, index=False)
    audit = {
        'task_id': 'ML-02', 'target': TARGET, 'release': ptr['version'], 'release_sha256': ptr['sha256'],
        'sample_file': str(path.relative_to(ROOT)), 'sample_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'key': ['customer_id', 'as_of'], 'key_unique': bool(not df.duplicated(['customer_id', 'as_of']).any()),
        'windows': {'features': '[.., as_of)：purchase_ts < as_of 且 approved_ts < as_of；近 90 天特征窗 [as_of-90d, as_of)',
                    'label': '[as_of, as_of+30d)：窗口内下单且 approved_ts < as_of+31d', 'as_of_grid': '每周一 00:00 UTC'},
        'population_filter': 'frequency_90d >= 1（过去 90 天有有效购买的已知客户）',
        'funnel': funnel,
        'samples': {'rows': int(len(df)), 'as_of_points': int(df.as_of.nunique()), 'customers': int(df.customer_id.nunique()),
                    'positives': int(df.y.sum()), 'positive_rate': round(float(df.y.mean()), 6),
                    'first_as_of': df.as_of.min(), 'last_as_of': df.as_of.max(),
                    'max_label_matured_at': df.label_matured_at.max()},
        'right_censoring': '成熟时间晚于截止 2026-11-08 的 as_of 不生成标签，因此不进入样本',
        'columns': list(df.columns),
    }
    (ROOT / 'reports/model').mkdir(parents=True, exist_ok=True)
    (ROOT / 'reports/model/sample_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps(audit['samples'], ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
