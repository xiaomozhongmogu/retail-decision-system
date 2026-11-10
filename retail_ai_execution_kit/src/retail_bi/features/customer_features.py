"""ML-03: point-in-time customer features for the target-v1 samples.

Every feature at (customer, as_of) uses only information knowable before as_of:
  orders     purchase_ts < as_of AND approved_ts < as_of           (valid purchase visible at as_of)
  delivery   delivered_ts < as_of                                  (outcome known)
  reviews    review_created_date < as_of (day granularity)         (review existed)
  payments   type/installments of visible orders (no payment time; assumed known at purchase, D011)
  static     customer region, product category (master data created 2024-01-01, before every as_of)
Never used: customer_id as a feature, final order_status, cancellations (no cancellation time), any amount
or event at/after as_of, generator labels (segment, lifecycle stage, sentiment, seller parameters), clusters.
There are no returns/refunds in the data, so no return features exist.

FEATURES (order matters for models) and their dictionary are in docs/feature_dictionary.md.
usage: .venv/bin/python src/retail_bi/features/customer_features.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'warehouse'))
from db import ROOT  # noqa: E402

FEATURE_VERSION = 'features-v1'
FEATURES = [
    'recency_days', 'tenure_days', 'orders_7d', 'orders_30d', 'orders_90d', 'merch_7d', 'merch_30d', 'merch_90d',
    'orders_all_time', 'merch_all_time', 'aov_all_time', 'lines_per_order', 'active_days_90d',
    'gap_mean_days', 'gap_last_days', 'has_gap', 'categories_all_time', 'categories_90d', 'products_90d',
    'installment_share', 'credit_card_share', 'delivered_count', 'late_by_date_share', 'last_review_score', 'has_review',
    'region_midwest', 'region_northeast', 'region_south', 'region_west', 'as_of_month',
]

FEATURE_SQL = """
WITH keys AS (SELECT DISTINCT customer_id, CAST(as_of AS TIMESTAMPTZ) AS as_of FROM samples),
vis AS (     -- orders visible at as_of
    SELECT k.customer_id, k.as_of, o.order_id, o.purchase_ts, o.merch_usd, o.item_lines, o.delivered_ts, o.late_by_date,
           o.review_score, o.review_created_date
    FROM keys k JOIN dwd.fact_order o ON o.customer_id = k.customer_id AND o.purchase_ts < k.as_of AND o.approved_ts < k.as_of),
gaps AS (
    SELECT customer_id, as_of, epoch(purchase_ts - lag(purchase_ts) OVER (PARTITION BY customer_id, as_of ORDER BY purchase_ts)) / 86400.0 AS gap,
           row_number() OVER (PARTITION BY customer_id, as_of ORDER BY purchase_ts DESC) AS rn
    FROM vis),
base AS (
    SELECT customer_id, as_of,
        epoch(as_of - max(purchase_ts)) / 86400.0 AS recency_days,
        epoch(as_of - min(purchase_ts)) / 86400.0 AS tenure_days,
        count(*) FILTER (WHERE purchase_ts >= as_of - INTERVAL 7 DAY) AS orders_7d,
        count(*) FILTER (WHERE purchase_ts >= as_of - INTERVAL 30 DAY) AS orders_30d,
        count(*) FILTER (WHERE purchase_ts >= as_of - INTERVAL 90 DAY) AS orders_90d,
        coalesce(sum(merch_usd) FILTER (WHERE purchase_ts >= as_of - INTERVAL 7 DAY), 0)::DOUBLE AS merch_7d,
        coalesce(sum(merch_usd) FILTER (WHERE purchase_ts >= as_of - INTERVAL 30 DAY), 0)::DOUBLE AS merch_30d,
        coalesce(sum(merch_usd) FILTER (WHERE purchase_ts >= as_of - INTERVAL 90 DAY), 0)::DOUBLE AS merch_90d,
        count(*) AS orders_all_time, sum(merch_usd)::DOUBLE AS merch_all_time,
        (sum(merch_usd) / count(*))::DOUBLE AS aov_all_time, avg(item_lines)::DOUBLE AS lines_per_order,
        count(DISTINCT CAST(purchase_ts AS DATE)) FILTER (WHERE purchase_ts >= as_of - INTERVAL 90 DAY) AS active_days_90d,
        count(*) FILTER (WHERE delivered_ts < as_of) AS delivered_count,
        avg(late_by_date::INT) FILTER (WHERE delivered_ts < as_of) AS late_by_date_share,
        arg_max(review_score, review_created_date) FILTER (WHERE review_created_date < CAST(as_of AS DATE)) AS last_review_score
    FROM vis GROUP BY customer_id, as_of),
g AS (SELECT customer_id, as_of, avg(gap) AS gap_mean_days, max(gap) FILTER (WHERE rn = 1) AS gap_last_days FROM gaps GROUP BY 1, 2),
lines AS (
    SELECT v.customer_id, v.as_of, count(DISTINCT p.product_category) AS categories_all_time,
           count(DISTINCT p.product_category) FILTER (WHERE v.purchase_ts >= v.as_of - INTERVAL 90 DAY) AS categories_90d,
           count(DISTINCT l.product_id) FILTER (WHERE v.purchase_ts >= v.as_of - INTERVAL 90 DAY) AS products_90d
    FROM vis v JOIN dwd.fact_order_line l USING (order_id) JOIN dwd.dim_product p USING (product_id) GROUP BY 1, 2),
pay AS (
    SELECT v.customer_id, v.as_of, avg((pm.max_inst > 1)::INT) AS installment_share, avg(pm.cc::INT) AS credit_card_share
    FROM vis v JOIN (SELECT order_id, max(payment_installments) AS max_inst, bool_or(payment_type = 'credit_card') AS cc
                     FROM dwd.fact_payment GROUP BY 1) pm USING (order_id) GROUP BY 1, 2)
SELECT s.customer_id, s.as_of, s.y,
       b.recency_days, b.tenure_days, b.orders_7d, b.orders_30d, b.orders_90d, b.merch_7d, b.merch_30d, b.merch_90d,
       b.orders_all_time, b.merch_all_time, b.aov_all_time, b.lines_per_order, b.active_days_90d,
       g.gap_mean_days, g.gap_last_days, (g.gap_mean_days IS NOT NULL)::INT AS has_gap,
       ln.categories_all_time, ln.categories_90d, ln.products_90d,
       pay.installment_share, pay.credit_card_share,
       b.delivered_count, b.late_by_date_share, b.last_review_score, (b.last_review_score IS NOT NULL)::INT AS has_review,
       (c.customer_region = 'Midwest')::INT AS region_midwest, (c.customer_region = 'Northeast')::INT AS region_northeast,
       (c.customer_region = 'South')::INT AS region_south, (c.customer_region = 'West')::INT AS region_west,
       month(CAST(s.as_of AS TIMESTAMPTZ)) AS as_of_month
FROM samples s
JOIN base b ON b.customer_id = s.customer_id AND b.as_of = CAST(s.as_of AS TIMESTAMPTZ)
LEFT JOIN g ON g.customer_id = s.customer_id AND g.as_of = CAST(s.as_of AS TIMESTAMPTZ)
JOIN lines ln ON ln.customer_id = s.customer_id AND ln.as_of = CAST(s.as_of AS TIMESTAMPTZ)
JOIN pay ON pay.customer_id = s.customer_id AND pay.as_of = CAST(s.as_of AS TIMESTAMPTZ)
JOIN dwd.dim_customer c ON c.customer_id = s.customer_id
ORDER BY s.as_of, s.customer_id
"""


def compute(con, samples_df):
    con.register('samples', samples_df[['customer_id', 'as_of', 'y']])
    df = con.execute(FEATURE_SQL).df()
    con.unregister('samples')
    return df


def main():
    import pandas as pd
    from runtime import open_current
    audit = json.loads((ROOT / 'reports/model/sample_audit.json').read_text(encoding='utf-8'))
    samples = pd.read_parquet(ROOT / audit['sample_file'])
    con, ptr = open_current()
    df = compute(con, samples)
    con.close()
    assert len(df) == len(samples), 'every sample must get one feature row'
    path = ROOT / f'data/processed/model/features-{ptr["version"]}-target-v1-{FEATURE_VERSION}.parquet'
    df.to_parquet(path, index=False)
    nulls = {c: int(df[c].isna().sum()) for c in FEATURES if df[c].isna().any()}
    meta = {'task_id': 'ML-03', 'feature_version': FEATURE_VERSION, 'release': ptr['version'], 'features': FEATURES,
            'file': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'rows': len(df),
            'null_counts': nulls, 'positives': int(df.y.sum())}
    (ROOT / 'reports/model/feature_build.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: meta[k] for k in ('rows', 'null_counts', 'positives')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
