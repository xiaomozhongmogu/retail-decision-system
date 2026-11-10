"""DATA-09: in-source integration with join audits.

There is one source (one synthetic package), so integration means joining its
tables on verified keys. Every join is checked for key coverage and for
row/amount changes before and after (no fact inflation). Payments (1-2 rows per
order) are aggregated to order level before joining; the naive join is also run
to show the inflation it would cause.

Outputs (git-ignored): data/processed/integrated/<key>/order_lines.parquet and
orders.parquet, plus the audit JSON.

usage: .venv/bin/python src/retail_bi/data/integrate.py --clean-dir <clean dir> \
         --out-root data/processed/integrated --audit reports/data/integration_audit.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

import duckdb

INTEGRATE_VERSION = 'integrate-v1'


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def stats(con, rel, amount='item_price_usd'):
    r = con.execute(f'SELECT count(*), coalesce(sum({amount}), 0) FROM ({rel})').fetchone()
    return {'rows': r[0], 'amount': str(r[1])}


def build(clean_dir: Path, out_root: Path):
    clean_dir, out_root = clean_dir.resolve(), out_root.resolve()
    cman = json.loads((clean_dir / 'manifest.json').read_text(encoding='utf-8'))
    for item in cman['outputs']:
        if sha(clean_dir / item['path']) != item['sha256']:
            raise ValueError(f'clean output changed: {item["path"]}')
    key = f'{sha(clean_dir / "manifest.json")[:16]}-{INTEGRATE_VERSION}'
    con = duckdb.connect()
    con.execute("SET timezone = 'UTC'")
    for t in ['customers', 'sellers', 'products', 'seller_products', 'orders', 'order_items', 'payments', 'shipping', 'reviews', 'calendar']:
        con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{(clean_dir / f'{t}.parquet').as_posix()}')")

    audit = {'task_id': 'DATA-09', 'version': INTEGRATE_VERSION, 'key': key,
             'clean_manifest_sha256': sha(clean_dir / 'manifest.json'), 'source_count': 1}

    # 1. same-source naming/types: every table came through the contract (DATA-07)
    audit['naming_and_types'] = {
        'rule': '10 张表全部经契约统一为标准列名与类型（DATA-07）；同一概念在不同表中名称一致',
        'shared_columns': {}}
    cols = {t: [r[0] for r in con.execute(f'DESCRIBE {t}').fetchall()] for t in ['customers', 'sellers', 'products', 'seller_products', 'orders', 'order_items', 'payments', 'shipping', 'reviews']}
    types = {t: {r[0]: r[1] for r in con.execute(f'DESCRIBE {t}').fetchall()} for t in cols}
    for c in ['order_id', 'customer_id', 'product_id', 'seller_id', 'seller_product_id']:
        where = [t for t in cols if c in cols[t]]
        audit['naming_and_types']['shared_columns'][c] = {'tables': where, 'types': sorted({types[t][c] for t in where})}
    audit['naming_and_types']['consistent'] = all(len(v['types']) == 1 for v in audit['naming_and_types']['shared_columns'].values())

    # 2. time overlap and duplicates across files of the one source
    audit['time_and_duplicates'] = {
        'files_per_table': 1,
        'calendar_covers_purchase_days': con.execute(
            'SELECT count(*) FROM (SELECT DISTINCT CAST(purchase_ts AS DATE) d FROM orders) x WHERE d NOT IN (SELECT date FROM calendar)').fetchone()[0] == 0,
        'orders_purchase_range': [str(x) for x in con.execute('SELECT min(purchase_ts)::VARCHAR, max(purchase_ts)::VARCHAR FROM orders').fetchone()],
        'calendar_range': [str(x) for x in con.execute('SELECT min(date), max(date) FROM calendar').fetchone()],
        'reviews_after_purchase': con.execute('SELECT count(*) FROM reviews r JOIN orders o USING (order_id) WHERE r.review_created_date < CAST(o.purchase_ts AS DATE)').fetchone()[0] == 0,
        'duplicate_keys_after_clean': {t: con.execute(f'SELECT count(*) - count(DISTINCT {k}) FROM {t}').fetchone()[0]
                                       for t, k in [('orders', 'order_id'), ('shipping', 'order_id'), ('reviews', 'order_id'), ('customers', 'customer_id'), ('products', 'product_id')]},
    }

    # 3. joins: coverage + rows/amount before and after
    base = 'SELECT * FROM order_items'
    steps = [
        ('orders', 'order_id', 'm:1'), ('products', 'product_id', 'm:1'), ('sellers', 'seller_id', 'm:1'),
        ('seller_products', 'seller_product_id', 'm:1'), ('shipping', 'order_id', 'm:1 (1:1 with orders)'),
        ('reviews', 'order_id', 'm:0..1'),
    ]
    joins = []
    rel = base
    before = stats(con, rel)
    keep = {'orders': 'customer_id, purchase_ts, approved_ts, carrier_handoff_ts, delivered_ts, estimated_delivery_date, order_status',
            'products': 'product_category, product_weight_g',
            'sellers': 'seller_state, seller_region',
            'seller_products': 'seller_price_usd',
            'shipping': 'shipping_distance_band, shipping_zone, estimated_delivery_days, order_shipping_usd',
            'reviews': 'review_score, review_created_date'}
    for table, k, card in steps:
        how = 'LEFT JOIN' if table == 'reviews' else 'JOIN'
        dup = con.execute(f'SELECT count(*) - count(DISTINCT {k}) FROM {table}').fetchone()[0]
        cover = con.execute(f'SELECT count(*) FILTER (WHERE {k} IN (SELECT {k} FROM {table})), count(*) FROM ({rel})').fetchone()
        new = f'SELECT b.*, {", ".join("j." + c.strip() for c in keep[table].split(","))} FROM ({rel}) b {how} {table} j USING ({k})'
        after = stats(con, new)
        joins.append({'join': f'order_items ⨝ {table} ON {k}', 'cardinality': card, 'type': how,
                      'right_key_duplicates': dup, 'left_rows_matched': cover[0], 'left_rows': cover[1],
                      'coverage': round(cover[0] / cover[1], 6), 'before': before, 'after': after,
                      'no_fact_inflation': after == before})
        rel, before = new, after
    con.execute(f'CREATE VIEW order_lines AS {rel}')
    cust_cover = con.execute('SELECT count(*) FILTER (WHERE customer_id IN (SELECT customer_id FROM customers)), count(*) FROM order_lines').fetchone()
    joins.append({'join': 'order_lines ⨝ customers ON customer_id (coverage only; customer attributes join in the warehouse)',
                  'left_rows_matched': cust_cover[0], 'left_rows': cust_cover[1], 'coverage': round(cust_cover[0] / cust_cover[1], 6)})

    # 4. order level: payments pre-aggregated vs naive join
    naive = con.execute('''SELECT count(*), sum(i.item_price_usd) FROM order_items i JOIN payments p USING (order_id)''').fetchone()
    con.execute('''CREATE VIEW pay_by_order AS SELECT order_id, sum(payment_value_usd) AS payment_value_usd,
                   count(*) AS payment_rows, string_agg(DISTINCT payment_type, '+' ORDER BY payment_type) AS payment_types,
                   max(payment_installments) AS max_installments FROM payments GROUP BY order_id''')
    con.execute('''CREATE VIEW orders_enriched AS
        SELECT o.*, a.merch_usd, a.shipping_usd, a.order_value_usd, a.item_lines, p.payment_value_usd, p.payment_rows,
               p.payment_types, p.max_installments, s.shipping_distance_band, s.estimated_delivery_days, r.review_score
        FROM orders o
        JOIN (SELECT order_id, sum(item_price_usd) merch_usd, sum(item_shipping_usd) shipping_usd,
                     sum(item_total_usd) order_value_usd, count(*) item_lines FROM order_items GROUP BY 1) a USING (order_id)
        JOIN pay_by_order p USING (order_id) JOIN shipping s USING (order_id) LEFT JOIN reviews r USING (order_id)''')
    oe = con.execute('SELECT count(*), sum(merch_usd), sum(payment_value_usd), sum(order_value_usd) FROM orders_enriched').fetchone()
    items_total = con.execute('SELECT count(*), sum(item_price_usd) FROM order_items').fetchone()
    audit['order_level'] = {
        'orders_rows': con.execute('SELECT count(*) FROM orders').fetchone()[0], 'orders_enriched_rows': oe[0],
        'merch_usd_items': str(items_total[1]), 'merch_usd_orders_enriched': str(oe[1]),
        'payment_equals_order_value': oe[2] == oe[3],
        'naive_items_join_payments': {'rows': naive[0], 'merch_usd': str(naive[1]),
                                      'inflated_rows': naive[0] - items_total[0], 'inflated_merch_usd': str(naive[1] - items_total[1]),
                                      'note': '直接把明细与支付连接，699 个两次支付订单的明细会翻倍；因此支付先按订单汇总再连接'},
    }
    audit['joins'] = joins
    audit['checks'] = {
        'naming_types_consistent': audit['naming_and_types']['consistent'],
        'calendar_covers_purchase_days': audit['time_and_duplicates']['calendar_covers_purchase_days'],
        'no_duplicate_keys': all(v == 0 for v in audit['time_and_duplicates']['duplicate_keys_after_clean'].values()),
        'all_joins_full_coverage': all(j['coverage'] == 1.0 for j in joins if j['join'].split(' ')[2] != 'reviews'),
        'no_fact_inflation_on_any_join': all(j.get('no_fact_inflation', True) for j in joins),
        'order_level_rows_and_amount_preserved': oe[0] == audit['order_level']['orders_rows'] and oe[1] == items_total[1],
        'naive_payment_join_would_inflate': naive[0] > items_total[0],
    }
    audit['cross_source'] = '只有一个来源，不需要跨来源集成；没有拼接任何外部用户 ID（D013）。来源内整合方式：按契约主外键连接，支付先按订单汇总，评价左连接（只有部分订单有评价）。'
    audit['all_checks_passed'] = all(audit['checks'].values())

    out_root.mkdir(parents=True, exist_ok=True)
    target = out_root / key
    if target.exists():
        m = json.loads((target / 'manifest.json').read_text(encoding='utf-8'))
        for o in m['outputs']:
            if sha(target / o['path']) != o['sha256']:
                raise ValueError(f'existing integrated output changed: {o["path"]}')
        audit['reused_existing_output'] = True
        audit['outputs'] = m['outputs']
        return audit
    stage = Path(tempfile.mkdtemp(dir=out_root, prefix=f'{key}.partial-'))
    try:
        outputs = []
        for name, view in [('order_lines', 'order_lines'), ('orders', 'orders_enriched')]:
            p = stage / f'{name}.parquet'
            con.execute(f"COPY (SELECT * FROM {view} ORDER BY order_id{', order_item_seq' if name == 'order_lines' else ''}) TO '{p.as_posix()}' (FORMAT parquet, COMPRESSION zstd)")
            outputs.append({'path': p.name, 'sha256': sha(p), 'rows': con.execute(f"SELECT count(*) FROM read_parquet('{p.as_posix()}')").fetchone()[0]})
        (stage / 'manifest.json').write_text(json.dumps({'key': key, 'clean_manifest_sha256': audit['clean_manifest_sha256'],
                                                         'outputs': outputs}, indent=2) + '\n', encoding='utf-8')
        stage.rename(target)
        stage = None
    finally:
        if stage is not None:
            shutil.rmtree(stage)
    audit['reused_existing_output'] = False
    audit['outputs'] = outputs
    return audit


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--clean-dir', type=Path, required=True)
    ap.add_argument('--out-root', type=Path, required=True)
    ap.add_argument('--audit', type=Path, required=True)
    a = ap.parse_args()
    audit = build(a.clean_dir, a.out_root)
    a.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps(audit['checks'], ensure_ascii=False))
    raise SystemExit(0 if audit['all_checks_passed'] else 1)


if __name__ == '__main__':
    main()
