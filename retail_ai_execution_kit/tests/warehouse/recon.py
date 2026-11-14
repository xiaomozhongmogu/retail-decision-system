"""DW-09: warehouse constraint checks and raw-to-ADS reconciliation.

Checks run as queries, so they also catch problems in a copy without database constraints.
run_checks(con) -> {name: {'passed': bool, 'value': ...}}
reconcile(con, zip_path) -> step-by-step order counts and amounts from the source ZIP to ADS.

usage: .venv/bin/python tests/warehouse/recon.py     (writes reports/warehouse/reconciliation.json)
"""
from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
from db import connect  # noqa: E402

AS_OF = "TIMESTAMPTZ '2026-11-08 00:00:00+00'"
CUTOFF = datetime(2026, 11, 8)
DIM_KEYS = {'dim_date': 'date_key', 'dim_geo': 'geo_key', 'dim_customer': 'customer_id', 'dim_product': 'product_id', 'dim_seller': 'seller_id'}
FACT_KEYS = {'fact_order': 'order_id', 'fact_order_line': 'order_id, order_item_seq', 'fact_payment': 'order_id, payment_seq',
             'fact_fulfillment': 'order_id'}
FKS = [('fact_order', 'customer_id', 'dim_customer', 'customer_id'), ('fact_order', 'purchase_date_key', 'dim_date', 'date_key'),
       ('fact_order_line', 'order_id', 'fact_order', 'order_id'), ('fact_order_line', 'product_id', 'dim_product', 'product_id'),
       ('fact_order_line', 'seller_id', 'dim_seller', 'seller_id'), ('fact_order_line', 'purchase_date_key', 'dim_date', 'date_key'),
       ('fact_payment', 'order_id', 'fact_order', 'order_id'), ('fact_fulfillment', 'order_id', 'fact_order', 'order_id'),
       ('dim_customer', 'geo_key', 'dim_geo', 'geo_key'), ('dim_seller', 'geo_key', 'dim_geo', 'geo_key')]
NOT_NULL = [('fact_order', 'purchase_date_key'), ('fact_order', 'customer_id'), ('fact_order', 'purchase_ts'),
            ('fact_order_line', 'purchase_date_key'), ('fact_order_line', 'item_price_usd'), ('dim_date', 'calendar_date')]


def q(con, sql):
    return con.execute(sql).fetchone()[0]


def run_checks(con) -> dict:
    r = {}

    def add(name, passed, value):
        r[name] = {'passed': bool(passed), 'value': value}

    for t, k in DIM_KEYS.items():
        d = q(con, f'SELECT count(*) - count(DISTINCT ({k})) FROM dwd.{t}')
        add(f'unique_key:{t}', d == 0, d)
    for t, k in FACT_KEYS.items():
        d = q(con, f'SELECT count(*) - count(DISTINCT ({k})) FROM dwd.{t}')
        add(f'unique_key:{t}', d == 0, d)
    for ct, cc, pt, pc in FKS:   # policy: orphans are quarantined before DWD, so any orphan here is an error
        n = q(con, f'SELECT count(*) FROM dwd.{ct} c LEFT JOIN dwd.{pt} p ON c.{cc} = p.{pc} WHERE p.{pc} IS NULL')
        add(f'no_orphans:{ct}.{cc}->{pt}', n == 0, n)
    for t, c in NOT_NULL:
        n = q(con, f'SELECT count(*) FROM dwd.{t} WHERE {c} IS NULL')
        add(f'not_null:{t}.{c}', n == 0, n)
    base = con.execute('SELECT count(*), sum(item_price_usd) FROM dwd.fact_order_line').fetchone()
    joined = con.execute("""SELECT count(*), sum(l.item_price_usd) FROM dwd.fact_order_line l JOIN dwd.fact_order o USING (order_id)
                            JOIN dwd.dim_product p USING (product_id) JOIN dwd.dim_seller s USING (seller_id)
                            JOIN dwd.dim_customer c ON c.customer_id = l.customer_id JOIN dwd.dim_date d ON d.date_key = l.purchase_date_key
                            JOIN dwd.fact_fulfillment f USING (order_id)""").fetchone()
    add('star_join_no_inflation', joined == base, {'lines': [base[0], joined[0]], 'amount': [str(base[1]), str(joined[1])]})
    g = con.execute("""SELECT (SELECT count(*) FROM dwd.fact_order),
                              (SELECT count(DISTINCT order_id) FROM dwd.fact_order_line),
                              (SELECT count(*) FROM dwd.fact_order o WHERE o.item_lines <> (SELECT count(*) FROM dwd.fact_order_line l WHERE l.order_id = o.order_id)),
                              (SELECT count(*) FROM dwd.fact_order o WHERE o.merch_usd <> (SELECT sum(item_price_usd) FROM dwd.fact_order_line l WHERE l.order_id = o.order_id))""").fetchone()
    add('grain:order_header_matches_lines', g[0] == g[1] and g[2] == 0 and g[3] == 0, {'orders': g[0], 'orders_in_lines': g[1], 'item_lines_mismatch': g[2], 'merch_mismatch': g[3]})
    for t, k in [('orders_daily_region', 'date_key, customer_region'), ('sales_daily_category_region', 'date_key, product_category, customer_region'),
                 ('customer_daily', 'customer_id, date_key'), ('product_daily', 'product_id, date_key')]:
        d = q(con, f'SELECT count(*) - count(DISTINCT ({k})) FROM dws.{t}')
        add(f'grain:dws.{t}', d == 0, d)
    valid = con.execute(f'SELECT count(*), sum(merch_usd) FROM dwd.fact_order WHERE approved_ts < {AS_OF}').fetchone()
    dws = con.execute('SELECT sum(valid_orders), sum(merch_usd) FROM dws.orders_daily_region').fetchone()
    add('dws_equals_dwd_valid', dws == valid, {'dwd': [valid[0], str(valid[1])], 'dws': [dws[0], str(dws[1])]})
    return r


def reconcile(con, zip_path: Path) -> list[dict]:
    with zipfile.ZipFile(zip_path) as z:
        def rows(name):
            return list(csv.DictReader(io.StringIO(z.read(f'baseline_10000_seed42/{name}.csv').decode('utf-8-sig'))))
        orders, items = rows('orders'), rows('order_items')
    merch = {}
    for i in items:
        merch[i['order_id']] = merch.get(i['order_id'], Decimal(0)) + Decimal(i['item_price_usd'])
    raw_n, raw_m = len(orders), sum(merch.values())
    hist = [o for o in orders if datetime.fromisoformat(o['order_purchase_timestamp']) < CUTOFF]
    hist_m = sum(merch[o['order_id']] for o in hist)
    dwd = con.execute('SELECT count(*), sum(merch_usd) FROM dwd.fact_order').fetchone()
    canc = con.execute('SELECT count(*), sum(merch_usd) FROM dwd.fact_order WHERE approved_ts IS NULL').fetchone()
    pend = con.execute(f'SELECT count(*), sum(merch_usd) FROM dwd.fact_order WHERE approved_ts >= {AS_OF}').fetchone()
    valid = con.execute(f'SELECT count(*), sum(merch_usd) FROM dwd.fact_order WHERE approved_ts < {AS_OF}').fetchone()
    dws = con.execute('SELECT sum(valid_orders), sum(merch_usd) FROM dws.orders_daily_region').fetchone()
    ads = con.execute('SELECT sum(valid_orders), sum(merchandise_sales_usd) FROM ads.kpi_monthly').fetchone()
    clean_report = json.loads((ROOT / 'reports/data/cleaning_missing_duplicates.json').read_text(encoding='utf-8'))
    quarantined = clean_report['row_counts']['orders']['rows_quarantined']   # DATA-07 quarantine for the orders table
    steps = [
        {'step': '1 raw ZIP orders', 'orders': raw_n, 'merch_usd': str(raw_m)},
        {'step': '2 minus orders placed at/after the 2026-11-08 cutoff', 'orders': raw_n - len(hist), 'merch_usd': str(raw_m - hist_m), 'kind': 'excluded'},
        {'step': '3 historical scope (DATA-05)', 'orders': len(hist), 'merch_usd': str(hist_m)},
        {'step': '4 minus quarantined in cleaning (DATA-07)', 'orders': quarantined, 'merch_usd': '0', 'kind': 'quarantined'},
        {'step': '5 DWD fact_order', 'orders': dwd[0], 'merch_usd': str(dwd[1])},
        {'step': '6 minus cancelled (no approval)', 'orders': canc[0], 'merch_usd': str(canc[1]), 'kind': 'excluded from valid'},
        {'step': '7 minus approved only after the cutoff', 'orders': pend[0], 'merch_usd': str(pend[1]), 'kind': 'excluded from valid at cutoff'},
        {'step': '8 valid purchases at cutoff (DWD)', 'orders': valid[0], 'merch_usd': str(valid[1])},
        {'step': '9 DWS orders_daily_region', 'orders': dws[0], 'merch_usd': str(dws[1])},
        {'step': '10 ADS kpi_monthly', 'orders': ads[0], 'merch_usd': str(ads[1])},
    ]
    ok = (len(hist) == raw_n - (raw_n - len(hist)) and dwd[0] == len(hist) - quarantined and dwd[1] == hist_m
          and valid[0] == dwd[0] - canc[0] - pend[0] and valid[1] == dwd[1] - canc[1] - pend[1]
          and tuple(dws) == tuple(valid) and tuple(ads) == tuple(valid))
    return steps, ok


def main():
    latest = json.loads((ROOT / 'warehouse/builds/latest.json').read_text(encoding='utf-8'))
    con = connect(ROOT / 'warehouse/builds' / latest['file'], read_only=True)
    checks = run_checks(con)
    steps, chain_ok = reconcile(con, ROOT.parent / 'ecommerce-sample-database-100k/01_source/baseline_10000_seed42.zip')
    con.close()
    out = {'task_id': 'DW-09', 'build': latest, 'checks': checks, 'chain': steps, 'chain_reconciles': chain_ok,
           'orphan_policy': '外键孤儿在清洗阶段进入隔离区（DATA-07），DWD 中出现任何孤儿都视为失败',
           'all_passed': chain_ok and all(c['passed'] for c in checks.values())}
    (ROOT / 'reports/warehouse/reconciliation.json').write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    for s in steps:
        print(s)
    print('checks', sum(c['passed'] for c in checks.values()), '/', len(checks), 'chain', chain_ok)
    raise SystemExit(0 if out['all_passed'] else 1)


if __name__ == '__main__':
    main()
