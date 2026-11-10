"""DW-04: build DWS from DWD (sql/dws.sql) and check it.
Checks: grains, totals equal DWD, several time x dimension slices recomputed independently
from DWD lines with pandas, additive vs non-additive behaviour.
usage: .venv/bin/python evidence/DW-04/run_and_verify_dws.py
writes reports/warehouse/dws_audit.json
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
from db import connect, sql_blocks  # noqa: E402

DB = ROOT / 'warehouse/build/dev.duckdb'
AS_OF = '2026-11-08 00:00:00+00'
SQL = sql_blocks(ROOT / 'sql/dws.sql')
ok, results = [], []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    results.append({'check': name, 'status': 'passed' if cond else 'failed', 'detail': str(detail)})
    print('PASS' if cond else 'FAIL', name, detail)


con = connect(DB)
con.execute((ROOT / 'sql/ddl.sql').read_text(encoding='utf-8'))      # creates dws.orders_daily_region if missing
con.execute('BEGIN TRANSACTION')
for stmt in [x.strip() for x in SQL['build'].split(';') if x.strip()]:   # parameters work one statement at a time
    con.execute(stmt, {'as_of': AS_OF}) if '$as_of' in stmt else con.execute(stmt)
con.execute('COMMIT')
audit = {r[0]: {'rows': r[1], 'sum_count': int(r[2]), 'merch_usd': r[3]} for r in con.execute(SQL['audit']).fetchall()}
dwd = dict(zip(['valid_orders', 'merch', 'valid_lines'], con.execute(SQL['dwd_totals'], {'as_of': AS_OF}).fetchone()))
for t in audit:
    pk = {'orders_daily_region': 'date_key, customer_region', 'sales_daily_category_region': 'date_key, product_category, customer_region',
          'customer_daily': 'customer_id, date_key', 'product_daily': 'product_id, date_key'}[t]
    dup = con.execute(f'SELECT count(*) - count(DISTINCT ({pk})) FROM dws.{t}').fetchone()[0]
    check(f'dws.{t} one row per ({pk})', dup == 0, f"{audit[t]['rows']} rows")
    check(f'dws.{t} merch total equals DWD valid merch', audit[t]['merch_usd'] == dwd['merch'], audit[t]['merch_usd'])
check('orders_daily_region and customer_daily order counts = DWD valid orders',
      audit['orders_daily_region']['sum_count'] == audit['customer_daily']['sum_count'] == dwd['valid_orders'], dwd['valid_orders'])
check('line-level tables line counts = DWD valid lines',
      audit['sales_daily_category_region']['sum_count'] == audit['product_daily']['sum_count'] == dwd['valid_lines'], dwd['valid_lines'])

# independent recomputation from DWD lines with pandas
L = con.execute(f"""SELECT l.order_id, l.customer_id, l.product_id, CAST(l.purchase_date_key AS INTEGER) AS date_key,
                           l.item_price_usd::VARCHAR AS price, p.product_category AS cat, c.customer_region AS region
                    FROM dwd.fact_order_line l JOIN dwd.fact_order o USING (order_id) JOIN dwd.dim_product p USING (product_id)
                    JOIN dwd.dim_customer c ON c.customer_id = l.customer_id WHERE o.approved_ts < TIMESTAMPTZ '{AS_OF}'""").df()
L['price'] = L['price'].map(Decimal)
L['month'] = L.date_key // 100
slices = [('2025-03', 'Books & Media', 'South'), ('2024-12', 'Fashion', 'West'), ('2026-06', 'Pet Supplies', 'Northeast'),
          ('2025-11', None, 'Midwest'), ('2026-01', 'Automotive', None)]
for month, cat, region in slices:
    m = int(month.replace('-', ''))
    f = L[(L.month == m) & ((L.cat == cat) if cat else True) & ((L.region == region) if region else True)]
    where = [f'date_key // 100 = {m}'] + ([f"product_category = '{cat}'"] if cat else []) + ([f"customer_region = '{region}'"] if region else [])
    s = con.execute(f"SELECT coalesce(sum(valid_lines),0), coalesce(sum(merch_usd),0)::VARCHAR FROM dws.sales_daily_category_region WHERE {' AND '.join(where)}").fetchone()
    exp_orders = f.order_id.nunique()
    got_orders_summed = con.execute(f"SELECT coalesce(sum(orders_containing),0) FROM dws.sales_daily_category_region WHERE {' AND '.join(where)}").fetchone()[0]
    check(f'slice {month} / {cat or "all categories"} / {region or "all regions"}: lines and merch equal DWD recount',
          s[0] == len(f) and Decimal(s[1]) == sum(f.price, Decimal(0)), f'{len(f)} lines, {s[1]} USD')
    if cat is None:
        check(f'slice {month} / all categories: summing orders_containing over categories over-counts distinct orders',
              got_orders_summed >= exp_orders, f'summed {got_orders_summed} vs distinct {exp_orders}')
demo = con.execute(SQL['additivity_demo'], {'as_of': AS_OF}).fetchall()
over = [(mo, c, w) for mo, c, w in demo if w > c]
check('monthly distinct buyers differ from the sum of daily distinct buyers in some months (non-additive)', len(over) > 0,
      f'{len(over)} of {len(demo)} months, e.g. {over[0] if over else None}')
check('orders_daily_region: daily orders are additive to the DWD total', audit['orders_daily_region']['sum_count'] == dwd['valid_orders'])
con.close()
out = {'task_id': 'DW-04', 'as_of': AS_OF, 'tables': audit, 'dwd_totals': dwd,
       'grains': {'orders_daily_region': '日期×客户大区', 'sales_daily_category_region': '日期×品类×客户大区',
                  'customer_daily': '客户×日期', 'product_daily': '商品×日期'},
       'additive': ['valid_orders', 'valid_lines', 'merch_usd', 'shipping_usd'],
       'non_additive': {'buyers': '按天去重客户数，跨天相加会重复计算同一客户；月度去重须从 DWD 重算',
                        'orders_containing': '包含该品类/商品的订单数，一单可含多个品类，跨品类相加会重复'},
       'additivity_demo_months_overcounted': len(over), 'checks': results, 'all_checks_passed': all(ok)}
(ROOT / 'reports/warehouse/dws_audit.json').write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
