"""ML-02 boundary tests: events exactly on window edges are assigned to the right side.
A tiny warehouse is built from hand-made fixture orders (tmp_path only).
run: .venv/bin/python -m pytest tests/model -q
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in ('src/retail_bi/warehouse', 'src/retail_bi/features', 'tests/data'):
    sys.path.insert(0, str(ROOT / p))
from db import connect  # noqa: E402
import ods  # noqa: E402
import dwd  # noqa: E402
import snapshot  # noqa: E402
from build_samples import build_samples  # noqa: E402
from conftest import ORDER_DEFAULTS, ITEM_DEFAULTS, write_layer  # noqa: E402

AS_OF = '2025-01-27 00:00:00+00'      # a Monday on the fixture grid (first_as_of 2025-01-13, weekly)


def order(oid, cust, purchase, approved):
    return {'order_id': oid, 'customer_id': cust, 'order_status': 'processing', 'order_purchase_timestamp': purchase,
            'order_approved_at': approved, 'order_estimated_delivery_date': '2025-06-30T00:00:00',
            'order_delivered_carrier_date': '', 'order_delivered_customer_date': '', **ORDER_DEFAULTS}


def add_boundary_orders(t):
    t['customers'].append({**t['customers'][0], 'customer_id': 'c3', 'customer_unique_id': 'u3'})
    t['customers'].append({**t['customers'][0], 'customer_id': 'c4', 'customer_unique_id': 'u4'})
    t['customers'].append({**t['customers'][0], 'customer_id': 'c5', 'customer_unique_id': 'u5'})
    new = [
        # c3: bought 2025-01-15 (in population at AS_OF); next purchase exactly at AS_OF -> label 1, not a feature
        order('b1', 'c3', '2025-01-15T09:00:00', '2025-01-15T10:00:00'),
        order('b2', 'c3', '2025-01-27T00:00:00', '2025-01-27T01:00:00'),
        # c4: bought 2025-01-14; purchase placed before AS_OF but approved exactly at AS_OF -> not visible at AS_OF
        order('b3', 'c4', '2025-01-14T09:00:00', '2025-01-14T10:00:00'),
        order('b4', 'c4', '2025-01-26T20:00:00', '2025-01-27T00:00:00'),
        # c1 (bought 2025-01-10/20): purchase exactly at AS_OF + 30 days -> outside the label window
        order('b5', 'c1', '2025-02-26T00:00:00', '2025-02-26T01:00:00'),
        # c5: bought 2025-01-16 (in population); next purchase inside the window but approved exactly at AS_OF + 31 days -> not counted
        order('b7', 'c5', '2025-01-16T09:00:00', '2025-01-16T10:00:00'),
        order('b6', 'c5', '2025-02-20T10:00:00', '2025-02-27T00:00:00'),
    ]
    for o in new:
        t['orders'].append(o)
        t['order_items'].append({'order_id': o['order_id'], 'order_item_id': '1', 'item_price_usd': '10.00', 'shipping_cost_usd': '1.00',
                                 'item_total_usd': '11.00', **ITEM_DEFAULTS})
        t['payments'].append({'order_id': o['order_id'], 'payment_sequential': '1', 'payment_type': 'credit_card', 'payment_installments': '1',
                              'payment_value_usd': '11.00', 'scenario_name': 'baseline'})
    from conftest import _shipping
    t['shipping'] = [_shipping(o) for o in t['orders']]
    from datetime import date, timedelta            # extend the fixture calendar to cover the boundary orders
    cal, d = [], date(2025, 1, 1)
    while d < date(2025, 4, 1):
        cal.append({'date': f'{d.isoformat()}T00:00:00', 'year': str(d.year), 'quarter': '1', 'month': str(d.month), 'month_name': 'x',
                    'week': '1', 'day_of_week': str(d.weekday()), 'day_name': 'x', 'is_weekend': str(d.weekday() >= 5),
                    'is_holiday_period': 'False', 'is_promotion_period': 'False', 'season': 'winter'})
        d += timedelta(days=1)
    t['calendar'] = cal


@pytest.fixture(scope='module')
def wh(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('ml02')
    lay = write_layer(tmp, add_boundary_orders)
    man = json.loads((lay / 'manifest.json').read_text(encoding='utf-8'))
    for o in man['outputs']:
        o['rows'] = sum(1 for _ in open(lay / o['path'], encoding='utf-8-sig')) - 1
    man['version'] = 'fixture-v1'
    (lay / 'manifest.json').write_text(json.dumps(man), encoding='utf-8')
    db = tmp / 'w.duckdb'
    ods.load(lay, db)
    dwd.build(db)
    params = dict(snapshot.PARAMS, first_as_of='2025-01-13 00:00:00', cutoff='2025-04-01 00:00:00')
    snapshot.build(db, params)
    con = connect(db, read_only=True)
    df, funnel = build_samples(con)
    snap = con.execute("SELECT customer_id, as_of::VARCHAR a, frequency_90d, orders_all_time FROM dws.customer_snapshot").df()
    con.close()
    return df, funnel, snap


def row(df, cust, as_of=AS_OF):
    r = df[(df.customer_id == cust) & (df.as_of == as_of)]
    assert len(r) == 1, f'{cust} at {as_of}: {len(r)} rows'
    return r.iloc[0]


def test_key_unique(wh):
    df, _, _ = wh
    assert not df.duplicated(['customer_id', 'as_of']).any()


def test_purchase_exactly_at_as_of_is_label_not_feature(wh):
    df, _, _ = wh
    r = row(df, 'c3')
    assert r.orders_all_time == 1 and r.frequency_90d == 1      # only b1 is visible at AS_OF
    assert r.y == 1                                             # b2 at AS_OF belongs to [AS_OF, AS_OF+30d)


def test_approval_exactly_at_as_of_is_not_visible(wh):
    df, _, snap = wh
    r = row(df, 'c4')
    assert r.orders_all_time == 1                               # b4 approved at AS_OF is not yet visible
    nxt = snap[(snap.customer_id == 'c4') & (snap.a == '2025-02-03 00:00:00+00')].iloc[0]
    assert nxt.orders_all_time == 2                             # visible one week later


def test_purchase_exactly_at_window_end_is_outside(wh):
    df, _, _ = wh
    r = row(df, 'c1')
    assert r.y == 0                                             # b5 at AS_OF + 30d is outside [AS_OF, AS_OF+30d)


def test_approval_exactly_at_maturity_is_not_counted(wh):
    df, _, _ = wh
    r = row(df, 'c5')
    assert r.y == 0                                             # b6 approved at AS_OF + 31d (not < maturity)
    later = row(df, 'c5', '2025-02-03 00:00:00+00')              # window [02-03, 03-05) holds b6; approved 02-27 < maturity 03-06
    assert later.y == 1


def test_right_censored_as_of_excluded(wh):
    df, funnel, _ = wh
    # cutoff 2025-04-01: last as_of with mature label is 2025-02-24 (2025-02-24 + 31d = 2025-03-27 <= cutoff)
    assert df.as_of.max() == '2025-02-24 00:00:00+00'
    assert funnel['as_of_points_right_censored'] > 0
