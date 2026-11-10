"""Hand-made fixtures for the data rules. They are written to pytest's tmp_path
and never touch data/ (fixtures are physically separate from formal data)."""
import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/data'))
CONTRACT = ROOT / 'contracts/data_contract.json'

# One small, readable scenario. Values are invented for tests only.
BASE = {
    'customers': [
        {'customer_id': 'c1', 'customer_unique_id': 'u1', 'customer_state': 'NY', 'customer_city': 'X', 'customer_region': 'Northeast',
         'customer_zip_prefix': '01234', 'customer_segment': 'a', 'customer_lifecycle_stage': 'new', 'created_at': '2024-01-01T00:00:00'},
        {'customer_id': 'c2', 'customer_unique_id': 'u2', 'customer_state': 'CA', 'customer_city': 'Y', 'customer_region': 'West',
         'customer_zip_prefix': '90001', 'customer_segment': 'a', 'customer_lifecycle_stage': 'new', 'created_at': '2024-01-01T00:00:00'},
    ],
    'sellers': [{'seller_id': 's1', 'seller_state': 'TX', 'seller_city': 'Z', 'seller_region': 'South', 'seller_zip_prefix': '73301',
                 'seller_segment': 'x', 'seller_quality_score': '0.5', 'seller_fulfillment_capacity': '0.5', 'seller_active_flag': 'True',
                 'created_at': '2024-01-01T00:00:00', 'deactivated_at': ''}],
    'products': [{'product_id': 'p1', 'product_category': 'Books', 'product_name': 'B1', 'product_weight_g': '100', 'product_length_cm': '1.0',
                  'product_height_cm': '1.0', 'product_width_cm': '1.0', 'product_price_base_usd': '10.00', 'created_at': '2024-01-01T00:00:00'}],
    'seller_products': [{'seller_product_id': 'sp1', 'seller_id': 's1', 'product_id': 'p1', 'seller_price_usd': '10.00',
                         'listing_created_at': '2024-01-01T00:00:00', 'listing_active_flag': 'True', 'scenario_name': 'baseline'}],
    # o1 delivered, o2 processing (approved), o3 cancelled (no approval), o4 approved only after the as_of used in tests
    'orders': [
        {'order_id': 'o1', 'customer_id': 'c1', 'order_status': 'delivered', 'order_purchase_timestamp': '2025-01-10T10:00:00',
         'order_approved_at': '2025-01-10T12:00:00', 'order_estimated_delivery_date': '2025-01-15T00:00:00',
         'order_delivered_carrier_date': '2025-01-11T09:00:00', 'order_delivered_customer_date': '2025-01-16T08:00:00'},
        {'order_id': 'o2', 'customer_id': 'c1', 'order_status': 'processing', 'order_purchase_timestamp': '2025-01-20T10:00:00',
         'order_approved_at': '2025-01-20T11:00:00', 'order_estimated_delivery_date': '2025-01-27T00:00:00',
         'order_delivered_carrier_date': '', 'order_delivered_customer_date': ''},
        {'order_id': 'o3', 'customer_id': 'c2', 'order_status': 'cancelled', 'order_purchase_timestamp': '2025-01-21T10:00:00',
         'order_approved_at': '', 'order_estimated_delivery_date': '2025-01-28T00:00:00',
         'order_delivered_carrier_date': '', 'order_delivered_customer_date': ''},
        {'order_id': 'o4', 'customer_id': 'c2', 'order_status': 'processing', 'order_purchase_timestamp': '2025-01-31T20:00:00',
         'order_approved_at': '2025-02-01T08:00:00', 'order_estimated_delivery_date': '2025-02-07T00:00:00',
         'order_delivered_carrier_date': '', 'order_delivered_customer_date': ''},
    ],
    'order_items': [
        {'order_id': 'o1', 'order_item_id': '1', 'item_price_usd': '100.00', 'shipping_cost_usd': '5.00', 'item_total_usd': '105.00'},
        {'order_id': 'o1', 'order_item_id': '2', 'item_price_usd': '20.50', 'shipping_cost_usd': '2.25', 'item_total_usd': '22.75'},
        {'order_id': 'o2', 'order_item_id': '1', 'item_price_usd': '40.00', 'shipping_cost_usd': '4.00', 'item_total_usd': '44.00'},
        {'order_id': 'o3', 'order_item_id': '1', 'item_price_usd': '30.00', 'shipping_cost_usd': '3.00', 'item_total_usd': '33.00'},
        {'order_id': 'o4', 'order_item_id': '1', 'item_price_usd': '9.99', 'shipping_cost_usd': '1.01', 'item_total_usd': '11.00'},
    ],
    'payments': [
        {'order_id': 'o1', 'payment_sequential': '1', 'payment_type': 'credit_card', 'payment_installments': '1', 'payment_value_usd': '100.00'},
        {'order_id': 'o1', 'payment_sequential': '2', 'payment_type': 'gift_card', 'payment_installments': '1', 'payment_value_usd': '27.75'},
        {'order_id': 'o2', 'payment_sequential': '1', 'payment_type': 'credit_card', 'payment_installments': '2', 'payment_value_usd': '44.00'},
        {'order_id': 'o3', 'payment_sequential': '1', 'payment_type': 'debit_card', 'payment_installments': '1', 'payment_value_usd': '33.00'},
        {'order_id': 'o4', 'payment_sequential': '1', 'payment_type': 'credit_card', 'payment_installments': '1', 'payment_value_usd': '11.00'},
    ],
    'reviews': [{'review_id': 'r1', 'order_id': 'o1', 'review_score': '4', 'review_creation_date': '2025-01-17T00:00:00',
                 'review_answer_timestamp': '2025-01-18T10:00:00', 'review_sentiment_label': 'positive', 'satisfaction_risk_flag': 'False',
                 'scenario_name': 'baseline'}],
}
ORDER_DEFAULTS = {'order_year': '2025', 'order_quarter': '1', 'order_month': '1', 'order_week': '3', 'order_day_of_week': '4',
                  'is_weekend': 'False', 'is_holiday_period': 'False', 'is_promotion_period': 'False', 'scenario_name': 'baseline'}
ITEM_DEFAULTS = {'seller_product_id': 'sp1', 'product_id': 'p1', 'seller_id': 's1', 'scenario_name': 'baseline'}


def _shipping(o):
    return {'order_id': o['order_id'], 'seller_state': 'TX', 'customer_state': 'NY', 'seller_region': 'South', 'customer_region': 'Northeast',
            'shipping_distance_band': 'cross_region', 'shipping_zone': 'zone_3', 'estimated_delivery_days': '5',
            'actual_delivery_days': '5.0' if o['order_delivered_customer_date'] else '',
            'delivery_delay_days': '0.0' if o['order_delivered_customer_date'] else '', 'late_delivery_flag': 'False',
            'shipping_cost_usd': '1.00', 'scenario_name': 'baseline'}


def _calendar():
    from datetime import date, timedelta
    out, d = [], date(2025, 1, 1)
    while d < date(2025, 2, 10):
        out.append({'date': f'{d.isoformat()}T00:00:00', 'year': str(d.year), 'quarter': '1', 'month': str(d.month), 'month_name': 'x',
                    'week': '1', 'day_of_week': str(d.weekday()), 'day_name': 'x', 'is_weekend': str(d.weekday() >= 5),
                    'is_holiday_period': 'False', 'is_promotion_period': 'False', 'season': 'winter'})
        d += timedelta(days=1)
    return out


def write_layer(root: Path, mutate=None) -> Path:
    """Write a fixture engineering layer; mutate(tables) can edit rows first."""
    contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
    tables = {k: [dict(r) for r in v] for k, v in BASE.items()}
    tables['orders'] = [{**r, **ORDER_DEFAULTS} for r in tables['orders']]
    tables['order_items'] = [{**r, **ITEM_DEFAULTS} for r in tables['order_items']]
    tables['payments'] = [{**r, 'scenario_name': 'baseline'} for r in tables['payments']]
    tables['shipping'] = [_shipping(o) for o in tables['orders']]
    tables['calendar'] = _calendar()
    if mutate:
        mutate(tables)
    layer = root / 'layer'
    (layer / 'history_source').mkdir(parents=True)
    outputs = []
    for t, spec in contract['tables'].items():
        cols = [c['raw_name'] for c in spec['columns']]
        p = layer / 'history_source' / f'{t}.csv'
        with open(p, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows({c: r.get(c, '') for c in cols} for r in tables[t])
        outputs.append({'path': f'history_source/{t}.csv', 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
    (layer / 'manifest.json').write_text(json.dumps({'outputs': outputs, 'fixture': True}), encoding='utf-8')
    return layer


@pytest.fixture
def layer(tmp_path):
    return write_layer(tmp_path)
