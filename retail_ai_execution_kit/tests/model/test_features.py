"""ML-03 tests on the real release.
1. Point-in-time: features at an as_of recomputed on a copy of DWD where everything at/after that as_of is
   removed or blanked must equal the original features (no future information used).
2. Forbidden columns are absent; null policy for single-purchase customers holds.
run: .venv/bin/python -m pytest tests/model/test_features.py -q
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in ('src/retail_bi/warehouse', 'src/retail_bi/features'):
    sys.path.insert(0, str(ROOT / p))
from db import connect  # noqa: E402
from runtime import pointer  # noqa: E402
from customer_features import FEATURES, compute  # noqa: E402

META = json.loads((ROOT / 'reports/model/feature_build.json').read_text(encoding='utf-8'))
FEAT = pd.read_parquet(ROOT / META['file'])
RELEASE = ROOT / 'warehouse/releases' / pointer()['file']
FORBIDDEN = {'customer_id', 'order_status', 'customer_segment', 'customer_lifecycle_stage', 'lifecycle_state', 'review_sentiment_label',
             'seller_quality_score', 'cluster', 'y', 'label_matured_at', 'payment_value_usd', 'cancelled'}


@pytest.mark.parametrize('as_of', ['2024-09-02 00:00:00+00', '2025-08-04 00:00:00+00', '2026-06-01 00:00:00+00'])
def test_features_do_not_change_when_the_future_is_removed(tmp_path, as_of):
    db = tmp_path / 'cut.duckdb'
    con = connect(db)
    con.execute(f"ATTACH '{RELEASE}' AS r (READ_ONLY)")
    con.execute('CREATE SCHEMA dwd')
    t = f"TIMESTAMPTZ '{as_of}'"
    con.execute(f"""CREATE TABLE dwd.fact_order AS SELECT order_id, customer_id, purchase_ts,
                       CASE WHEN approved_ts < {t} THEN approved_ts END AS approved_ts,
                       CASE WHEN delivered_ts < {t} THEN delivered_ts END AS delivered_ts,
                       CASE WHEN delivered_ts < {t} THEN late_by_date END AS late_by_date,
                       CASE WHEN review_created_date < CAST({t} AS DATE) THEN review_score END AS review_score,
                       CASE WHEN review_created_date < CAST({t} AS DATE) THEN review_created_date END AS review_created_date,
                       merch_usd, item_lines
                    FROM r.dwd.fact_order WHERE purchase_ts < {t}""")
    con.execute('CREATE TABLE dwd.fact_order_line AS SELECT * FROM r.dwd.fact_order_line WHERE order_id IN (SELECT order_id FROM dwd.fact_order)')
    con.execute('CREATE TABLE dwd.fact_payment AS SELECT * FROM r.dwd.fact_payment WHERE order_id IN (SELECT order_id FROM dwd.fact_order)')
    con.execute('CREATE TABLE dwd.dim_product AS SELECT * FROM r.dwd.dim_product')
    con.execute('CREATE TABLE dwd.dim_customer AS SELECT * FROM r.dwd.dim_customer')
    con.execute('DETACH r')
    orig = FEAT[FEAT.as_of == as_of].sort_values('customer_id').reset_index(drop=True)
    assert len(orig) > 500
    again = compute(con, orig[['customer_id', 'as_of', 'y']]).sort_values('customer_id').reset_index(drop=True)
    con.close()
    assert list(again.customer_id) == list(orig.customer_id)
    for c in FEATURES:
        a, b = orig[c].astype(float).to_numpy(), again[c].astype(float).to_numpy()
        assert np.allclose(a, b, equal_nan=True, atol=1e-9), c


def test_forbidden_columns_absent_from_feature_list():
    assert not (set(FEATURES) & FORBIDDEN)
    assert not any('segment' in f or 'status' in f or 'cluster' in f for f in FEATURES)


def test_single_purchase_gap_is_null_with_indicator():
    one = FEAT[FEAT.orders_all_time == 1]
    assert len(one) > 0 and one.gap_mean_days.isna().all() and (one.has_gap == 0).all()
    many = FEAT[FEAT.orders_all_time >= 2]
    assert many.gap_mean_days.notna().all() and (many.has_gap == 1).all()


def test_review_and_delivery_nulls_have_indicators():
    assert ((FEAT.last_review_score.isna()) == (FEAT.has_review == 0)).all()
    assert ((FEAT.late_by_date_share.isna()) == (FEAT.delivered_count == 0)).all()


def test_one_feature_row_per_sample_and_windows_nested():
    assert len(FEAT) == META['rows'] and not FEAT.duplicated(['customer_id', 'as_of']).any()
    assert (FEAT.orders_7d <= FEAT.orders_30d).all() and (FEAT.orders_30d <= FEAT.orders_90d).all()
    assert (FEAT.orders_90d <= FEAT.orders_all_time).all() and (FEAT.orders_90d >= 1).all()   # population: bought in last 90 days
