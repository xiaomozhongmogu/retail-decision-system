"""DATA-03 route facts: read-only statistics behind the main-dataset decision.

Reads the DATA-05 engineering layer (history_source, all values as strings)
and writes one JSON with the facts quoted in reports/data/dataset_selection.md.
It does not define "valid purchase"; that belongs to DATA-08. Repurchase base
rates are reported twice (all orders / non-canceled orders) only to show the
route can support the 30-day target, not to freeze the label.

usage: .venv/bin/python evidence/DATA-03/route_facts.py --layer <dir> --out <json>
"""
import argparse
import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

TABLES = ['orders', 'order_items', 'payments', 'customers', 'products',
          'sellers', 'shipping', 'reviews']


def read(layer, name):
    with open(layer / 'history_source' / f'{name}.csv', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def ts(value):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc) if value else None


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def field_profile(rows, col):
    vals = [r[col] for r in rows]
    non_null = [v for v in vals if v != '']
    top = Counter(non_null).most_common(6)
    return {'rows': len(vals), 'non_null': len(non_null), 'distinct': len(set(non_null)),
            'top_values': top if len(set(non_null)) <= 20 else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--layer', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    layer = Path(args.layer)
    data = {t: read(layer, t) for t in TABLES}
    manifest = json.loads((layer / 'manifest.json').read_text(encoding='utf-8'))
    cutoff = datetime.fromisoformat(manifest['as_of_exclusive'])

    orders = data['orders']
    status = Counter(o['order_status'] for o in orders)

    # Business fields checked from source columns (no date splits, no generator labels).
    checked = {
        'orders.order_id': ('orders', 'order_id'),
        'orders.customer_id': ('orders', 'customer_id'),
        'orders.order_status': ('orders', 'order_status'),
        'orders.order_purchase_timestamp': ('orders', 'order_purchase_timestamp'),
        'orders.order_delivered_customer_date': ('orders', 'order_delivered_customer_date'),
        'order_items.product_id': ('order_items', 'product_id'),
        'order_items.seller_id': ('order_items', 'seller_id'),
        'order_items.item_price_usd': ('order_items', 'item_price_usd'),
        'order_items.shipping_cost_usd': ('order_items', 'shipping_cost_usd'),
        'products.product_category': ('products', 'product_category'),
        'payments.payment_type': ('payments', 'payment_type'),
        'payments.payment_installments': ('payments', 'payment_installments'),
        'payments.payment_value_usd': ('payments', 'payment_value_usd'),
        'customers.customer_state': ('customers', 'customer_state'),
        'customers.customer_region': ('customers', 'customer_region'),
        'shipping.estimated_delivery_days': ('shipping', 'estimated_delivery_days'),
        'reviews.review_score': ('reviews', 'review_score'),
    }
    fields = {k: field_profile(data[t], c) for k, (t, c) in checked.items()}

    # Join integrity inside the one package (no cross-source IDs).
    ids = {t: set(r[k] for r in data[t]) for t, k in
           [('orders', 'order_id'), ('customers', 'customer_id'),
            ('products', 'product_id'), ('sellers', 'seller_id')]}
    joins = {
        'orders.customer_id->customers': sum(o['customer_id'] not in ids['customers'] for o in orders),
        'order_items.order_id->orders': sum(r['order_id'] not in ids['orders'] for r in data['order_items']),
        'order_items.product_id->products': sum(r['product_id'] not in ids['products'] for r in data['order_items']),
        'order_items.seller_id->sellers': sum(r['seller_id'] not in ids['sellers'] for r in data['order_items']),
        'payments.order_id->orders': sum(r['order_id'] not in ids['orders'] for r in data['payments']),
        'shipping.order_id->orders': sum(r['order_id'] not in ids['orders'] for r in data['shipping']),
        'reviews.order_id->orders': sum(r['order_id'] not in ids['orders'] for r in data['reviews']),
    }

    # Amounts (USD), by status, from item rows.
    status_of = {o['order_id']: o['order_status'] for o in orders}
    item_amount = defaultdict(Decimal)
    for r in data['order_items']:
        item_amount[status_of[r['order_id']]] += Decimal(r['item_price_usd'])

    # Customer purchase sequences.
    def sequences(keep):
        seq = defaultdict(list)
        for o in orders:
            if keep(o):
                seq[o['customer_id']].append(ts(o['order_purchase_timestamp']))
        for v in seq.values():
            v.sort()
        return seq

    variants = {'all_orders': lambda o: True,
                'non_cancelled_orders': lambda o: o['order_status'] != 'cancelled'}
    repurchase = {}
    for name, keep in variants.items():
        seq = sequences(keep)
        counts = Counter(len(v) for v in seq.values())
        gaps = [(b - a).total_seconds() / 86400 for v in seq.values() for a, b in zip(v, v[1:])]
        q = statistics.quantiles(gaps, n=20) if len(gaps) > 20 else []
        base = []
        for as_of in ['2025-01-01', '2025-04-01', '2025-07-01', '2025-10-01',
                      '2026-01-01', '2026-04-01', '2026-07-01', '2026-09-01']:
            t = datetime.fromisoformat(as_of).replace(tzinfo=timezone.utc)
            if t + timedelta(days=30) > cutoff:
                continue
            pop = [c for c, v in seq.items() if any(t - timedelta(days=90) <= x < t for x in v)]
            pos = [c for c in pop if any(t <= x < t + timedelta(days=30) for x in seq[c])]
            base.append({'as_of': as_of, 'population_90d_buyers': len(pop),
                         'repurchased_next_30d': len(pos),
                         'rate': round(len(pos) / len(pop), 4) if pop else None})
        repurchase[name] = {
            'customers_with_orders': len(seq),
            'customers_with_2plus_orders': sum(n for k, n in counts.items() if k >= 2),
            'orders_per_customer_distribution': dict(sorted(counts.items())),
            'inter_order_gap_days': {
                'n': len(gaps),
                'median': round(statistics.median(gaps), 1) if gaps else None,
                'p05_p25_p75_p95': [round(q[0], 1), round(q[4], 1), round(q[14], 1), round(q[18], 1)] if q else None,
            },
            'base_rate_30d_examples': base,
        }

    months = Counter(o['order_purchase_timestamp'][:7] for o in orders)
    out = {
        'task_id': 'DATA-03',
        'generated_by': 'evidence/DATA-03/route_facts.py',
        'layer': str(layer),
        'layer_manifest_sha256': sha(layer / 'manifest.json'),
        'engineering_version': manifest.get('version'),
        'as_of_exclusive': manifest['as_of_exclusive'],
        'row_counts': {t: len(v) for t, v in data.items()},
        'size_rule_check': {'rule': 'min_records 10000 (contracts/data_contract.json size_rule)',
                            'largest_fact_rows': {'order_items': len(data['order_items']),
                                                  'payments': len(data['payments']),
                                                  'orders': len(orders)}},
        'order_status': dict(status),
        'item_price_usd_by_status': {k: str(v) for k, v in item_amount.items()},
        'purchase_month_range': [min(months), max(months)],
        'purchase_months': len(months),
        'orders_per_month_min_max': [min(months.values()), max(months.values())],
        'checked_business_fields': fields,
        'join_orphans': joins,
        'repurchase_feasibility': repurchase,
        'notes': [
            'order_status is the final generator state, not a status history; it is not available at purchase time.',
            'Valid purchase / refund / pending definitions are not frozen here (DATA-08).',
            'Base rates are feasibility descriptions only; not model labels.',
        ],
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': out['order_status'], 'rows': out['row_counts'],
                      'orphans': joins, 'checked_fields': len(fields)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
