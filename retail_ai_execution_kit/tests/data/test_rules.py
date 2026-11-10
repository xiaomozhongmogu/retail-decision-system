"""Key data rules: each test states its input and expected output.
run: .venv/bin/python -m pytest tests/data -q
"""
import csv
import json
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from conftest import CONTRACT, write_layer
from clean import build as clean_build, parse
from transactions import connect, metric, reconcile

CUTOFF = '2025-02-05 00:00:00+00'


def run_clean(tmp_path, layer):
    target, manifest, reused = clean_build(layer, CONTRACT, tmp_path / 'clean', tmp_path / 'quarantine')
    return target, manifest, reused


def qrows(manifest, table):
    p = Path(manifest['quarantine']['dir']) / f'{table}.csv'
    with open(p, encoding='utf-8') as f:
        return list(csv.DictReader(f))


# ---------------- abnormal rows are quarantined, not dropped
def test_unparseable_timestamp_goes_to_quarantine_with_line_and_reason(tmp_path):
    # input: order o2 has purchase time "2025-13-01T99:00:00"
    layer = write_layer(tmp_path, lambda t: t['orders'][1].update(order_purchase_timestamp='2025-13-01T99:00:00'))
    _, m, _ = run_clean(tmp_path, layer)
    rows = qrows(m, 'orders')
    # expected: one quarantine row for CSV line 3 (header=1, o1=2, o2=3); o2's item/payment/shipping become orphans
    assert [(r['source_line'], r['column']) for r in rows] == [('3', 'order_purchase_timestamp')]
    assert m['tables']['orders'] == {'rows_in': 4, 'rows_after_type_and_pk': 3, 'rows_out': 3, 'rows_quarantined': 1}
    assert any(r['value'] == 'o2' and 'orphan' in r['reason'] for r in qrows(m, 'order_items'))
    assert all(v['rows_in'] == v['rows_out'] + v['rows_quarantined'] for v in m['tables'].values())


def test_duplicate_primary_key_is_quarantined(tmp_path):
    layer = write_layer(tmp_path, lambda t: t['customers'].append(dict(t['customers'][0])))
    _, m, _ = run_clean(tmp_path, layer)
    assert [r['reason'] for r in qrows(m, 'customers')] == ['duplicate primary key']
    assert m['tables']['customers']['rows_out'] == 2


def test_clean_fixture_has_no_quarantine(tmp_path, layer):
    _, m, _ = run_clean(tmp_path, layer)
    assert m['quarantine']['dir'] is None


# ---------------- duplicate import
def test_rerun_reuses_output_and_tampering_is_refused(tmp_path, layer):
    target, _, reused1 = run_clean(tmp_path, layer)
    before = (target / 'orders.parquet').read_bytes()
    _, _, reused2 = run_clean(tmp_path, layer)
    assert (reused1, reused2) == (False, True)
    assert (target / 'orders.parquet').read_bytes() == before
    (target / 'orders.parquet').write_bytes(b'x')
    with pytest.raises(ValueError, match='changed'):
        run_clean(tmp_path, layer)


def test_changed_input_file_is_refused(tmp_path, layer):
    (layer / 'history_source' / 'payments.csv').write_text('tampered', encoding='utf-8')
    with pytest.raises(ValueError, match='changed after import'):
        run_clean(tmp_path, layer)


# ---------------- cancellation / pending / refund classification and amounts
@pytest.fixture
def con(tmp_path, layer):
    target, _, _ = run_clean(tmp_path, layer)
    return connect(target), target


def test_valid_cancelled_pending_classification(con):
    c, _ = con
    w = ('2025-01-01 00:00:00+00', '2025-02-01 00:00:00+00')
    # as_of 2025-02-01: o1, o2 approved before -> valid; o3 no approval -> cancelled; o4 approved 02-01 08:00 -> not yet
    assert metric(c, 'valid_orders', *w, '2025-02-01 00:00:00+00') == 2
    assert metric(c, 'cancelled_orders', *w, '2025-02-01 00:00:00+00') == 1
    # as_of 2025-02-05: o4 is now approved and counts
    assert metric(c, 'valid_orders', *w, CUTOFF) == 3
    assert metric(c, 'merchandise_sales_usd', *w, '2025-02-01 00:00:00+00') == '160.50'   # 100 + 20.50 + 40
    assert metric(c, 'shipping_usd', *w, '2025-02-01 00:00:00+00') == '11.25'             # shipping kept separate
    assert metric(c, 'cancelled_merchandise_usd', *w, CUTOFF) == '30.00'


def test_zero_denominator_returns_null(con):
    c, _ = con
    assert metric(c, 'aov_usd', '2023-01-01 00:00:00+00', '2023-02-01 00:00:00+00', CUTOFF) is None


def test_reconciliation_differences_are_exact(con):
    _, target = con
    r = reconcile(target, '2025-02-01 00:00:00+00')
    # raw 4 orders = valid 2 + cancelled 1 + pending 1 ; amounts exact to the cent
    assert (r['raw_all_orders']['orders'], r['valid_orders_at_cutoff']['orders'], r['cancelled_orders']['orders'],
            r['pending_approval_at_cutoff']['orders']) == (4, 2, 1, 1)
    assert Decimal(r['raw_all_orders']['merch_usd']) == Decimal('200.49')
    assert Decimal(r['raw_minus_valid']['merch_usd']) == Decimal('39.99')     # 30.00 cancelled + 9.99 pending
    assert r['checks']['raw_minus_valid_equals_cancelled_plus_pending']
    assert r['checks']['payments_equal_order_value_all_orders']


def test_negative_amount_is_flagged_by_reconciliation(tmp_path):
    # input: a refund-like negative line; the rules do not net it silently
    layer = write_layer(tmp_path, lambda t: t['order_items'].append(
        {'order_id': 'o1', 'order_item_id': '3', 'item_price_usd': '-20.50', 'shipping_cost_usd': '0.00', 'item_total_usd': '-20.50',
         'seller_product_id': 'sp1', 'product_id': 'p1', 'seller_id': 's1', 'scenario_name': 'baseline'}))
    target, _, _ = clean_build(layer, CONTRACT, tmp_path / 'clean', tmp_path / 'q')
    r = reconcile(target, CUTOFF)
    assert r['checks']['no_negative_or_refund_amounts'] is False
    assert r['all_checks_passed'] is False


# ---------------- time parsing
@pytest.mark.parametrize('typ,value,expected', [
    ('timestamp', '2025-01-10T10:00:00', '2025-01-10T10:00:00+00:00'),   # naive -> UTC (engineering assumption)
    ('timestamp', '2025-01-10 10:00:00', '2025-01-10T10:00:00+00:00'),
    ('date', '2025-01-15T00:00:00', '2025-01-15'),
    ('timestamp', '', None),
])
def test_time_parsing(typ, value, expected):
    v = parse(typ, value)
    assert (v.isoformat() if v is not None else None) == expected


@pytest.mark.parametrize('typ,value', [('date', '2025-01-15T08:00:00'), ('timestamp', '2025-13-01T00:00:00'),
                                       ('integer', '5.5'), ('decimal(12,2)', '1.234'), ('boolean', 'yes')])
def test_invalid_values_raise(typ, value):
    with pytest.raises(ValueError):
        parse(typ, value)


def test_output_types(tmp_path, layer):
    target, _, _ = run_clean(tmp_path, layer)
    s = pq.read_schema(target / 'orders.parquet')
    assert str(s.field('purchase_ts').type) == 'timestamp[ms, tz=UTC]'
    assert str(pq.read_schema(target / 'order_items.parquet').field('item_price_usd').type) == 'decimal128(12, 2)'
