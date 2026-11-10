"""DW-03 checks: SQL-built DWD equals the independent Python cleaning (DATA-07) value by value,
keys are unique, semantics match DATA-08/DATA-10 reports, rebuild is idempotent.
usage: .venv/bin/python evidence/DW-03/verify_dwd.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
from dwd import build  # noqa: E402
from db import connect  # noqa: E402

DB = ROOT / 'warehouse/build/dev.duckdb'
CLEAN = next((ROOT / 'data/processed/clean').glob('*-clean-v2'))
REC = json.loads((ROOT / 'reports/data/transaction_reconciliation.json').read_text(encoding='utf-8'))
TR = json.loads((ROOT / 'reports/data/transform_audit.json').read_text(encoding='utf-8'))
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


before = build(DB)            # rebuild once more: must give the same result
con = connect(DB, read_only=True)


def same(dwd_sql, clean_sql, label):
    a = con.execute(f'SELECT count(*) FROM (({dwd_sql}) EXCEPT ALL ({clean_sql}))').fetchone()[0]
    b = con.execute(f'SELECT count(*) FROM (({clean_sql}) EXCEPT ALL ({dwd_sql}))').fetchone()[0]
    n = con.execute(f'SELECT count(*) FROM ({dwd_sql})').fetchone()[0]
    check(f'{label}: DWD (SQL) equals DATA-07 clean (Python) row for row', a == 0 and b == 0, f'{n} rows, diff {a}/{b}')


P = lambda t: f"read_parquet('{(CLEAN / f'{t}.parquet').as_posix()}')"  # noqa: E731
same('SELECT customer_id, customer_state, customer_region, customer_city, customer_created_date FROM dwd.dim_customer',
     f'SELECT customer_id, customer_state, customer_region, customer_city, customer_created_date FROM {P("customers")}', 'dim_customer')
same('SELECT product_id, product_category, product_name, product_weight_g, product_length_cm, product_height_cm, product_width_cm, product_price_base_usd FROM dwd.dim_product',
     f'SELECT product_id, product_category, product_name, product_weight_g, product_length_cm, product_height_cm, product_width_cm, product_price_base_usd FROM {P("products")}', 'dim_product')
same('SELECT seller_id, seller_state, seller_region, seller_city FROM dwd.dim_seller',
     f'SELECT seller_id, seller_state, seller_region, seller_city FROM {P("sellers")}', 'dim_seller')
same('SELECT calendar_date, year, quarter, month, week, day_of_week, is_weekend, season FROM dwd.dim_date',
     f'SELECT date, year, quarter, month, week, day_of_week, is_weekend, season FROM {P("calendar")}', 'dim_date')
same('SELECT order_id, customer_id, purchase_ts, approved_ts, carrier_handoff_ts, delivered_ts, estimated_delivery_date, order_status FROM dwd.fact_order',
     f'SELECT order_id, customer_id, purchase_ts, approved_ts, carrier_handoff_ts, delivered_ts, estimated_delivery_date, order_status FROM {P("orders")}', 'fact_order')
same('SELECT order_id, order_item_seq, product_id, seller_id, seller_product_id, item_price_usd, item_shipping_usd, item_total_usd FROM dwd.fact_order_line',
     f'SELECT order_id, order_item_seq, product_id, seller_id, seller_product_id, item_price_usd, item_shipping_usd, item_total_usd FROM {P("order_items")}', 'fact_order_line')
same('SELECT order_id, payment_seq, payment_type, payment_installments, payment_value_usd FROM dwd.fact_payment',
     f'SELECT order_id, payment_seq, payment_type, payment_installments, payment_value_usd FROM {P("payments")}', 'fact_payment')
same('SELECT order_id, shipping_distance_band, shipping_zone, estimated_delivery_days, order_shipping_usd FROM dwd.fact_fulfillment',
     f'SELECT order_id, shipping_distance_band, shipping_zone, estimated_delivery_days, order_shipping_usd FROM {P("shipping")}', 'fact_fulfillment')
same('SELECT order_id, review_score, review_created_date FROM dwd.fact_order WHERE review_score IS NOT NULL',
     f'SELECT order_id, review_score, review_created_date FROM {P("reviews")}', 'reviews merged into fact_order')
for t, k in [('dim_date', 'date_key'), ('dim_geo', 'geo_key'), ('dim_customer', 'customer_id'), ('dim_product', 'product_id'),
             ('dim_seller', 'seller_id'), ('fact_order', 'order_id')]:
    dup = con.execute(f'SELECT count(*) - count(DISTINCT {k}) FROM dwd.{t}').fetchone()[0]
    check(f'dwd.{t} key {k} unique', dup == 0)
orph = con.execute("""SELECT (SELECT count(*) FROM dwd.fact_order_line l LEFT JOIN dwd.dim_product p USING (product_id) WHERE p.product_id IS NULL)
                           + (SELECT count(*) FROM dwd.fact_order o LEFT JOIN dwd.dim_customer c USING (customer_id) WHERE c.customer_id IS NULL)
                           + (SELECT count(*) FROM dwd.dim_customer c LEFT JOIN dwd.dim_geo g USING (geo_key) WHERE g.geo_key IS NULL)""").fetchone()[0]
check('no orphan keys', orph == 0)
grain = con.execute("""SELECT count(*), sum(item_price_usd)::VARCHAR FROM dwd.fact_order_line l JOIN dwd.fact_order USING (order_id)
                       JOIN dwd.dim_product USING (product_id) JOIN dwd.dim_seller USING (seller_id) JOIN dwd.dim_customer c ON c.customer_id = l.customer_id
                       JOIN dwd.dim_date d ON d.date_key = l.purchase_date_key""").fetchone()
check('star join keeps line grain and amount', grain == (15639, '1408601.73'), str(grain))
v = REC['valid_orders_at_cutoff']
sem = before['semantics_at_cutoff']
check('valid/cancelled/pending match DATA-08 reconciliation', sem['valid_at_cutoff'] == v['orders'] and sem['merch_valid_at_cutoff'] == v['merch_usd']
      and sem['no_approval'] == REC['cancelled_orders']['orders'] and sem['approved_after_cutoff'] == REC['pending_approval_at_cutoff']['orders'])
lr = TR['deterministic_transforms']['late_rates_on_delivered']
check('late flags match DATA-10 rates', round(sem['late_by_date'] / 8655, 4) == lr['late_by_date'] and round(sem['late_by_days'] / 8655, 4) == lr['late_by_days(generator definition)'])
con.close()
again = build(DB)
check('rebuild is idempotent (same counts, all checks)', again['row_counts'] == before['row_counts'] and again['all_checks_passed'])
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
