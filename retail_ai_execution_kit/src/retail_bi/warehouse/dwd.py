"""DW-03: build DWD dimensions and facts from one ODS batch (sql/dwd.sql), in one transaction.

usage: .venv/bin/python src/retail_bi/warehouse/dwd.py --db warehouse/build/dev.duckdb \
         --audit reports/warehouse/dwd_audit.json
The batch is the single 'loaded' batch in meta.load_batch (error if none or several).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import ROOT, connect, sql_blocks  # noqa: E402

SQL = sql_blocks(ROOT / 'sql/dwd.sql')
DDL = (ROOT / 'sql/ddl.sql').read_text(encoding='utf-8')
BUILD_ORDER = ['clear', 'dim_date', 'dim_geo', 'dim_customer', 'dim_product', 'dim_seller',
               'fact_order', 'fact_order_line', 'fact_payment', 'fact_fulfillment']


def build(db: Path) -> dict:
    con = connect(db)
    batches = con.execute("SELECT batch_id FROM meta.load_batch WHERE status = 'loaded'").fetchall()
    if len(batches) != 1:
        raise ValueError(f'expected exactly one loaded ODS batch, found {len(batches)}')
    batch_id = batches[0][0]
    con.execute('BEGIN TRANSACTION')
    try:
        for step in BUILD_ORDER:
            if step == 'dim_date':
                con.execute(DDL)          # recreate the dropped DWD tables (CREATE ... IF NOT EXISTS)
            params = {'batch_id': batch_id} if '$batch_id' in SQL[step] else None
            con.execute(SQL[step], params) if params else con.execute(SQL[step])
        con.execute('COMMIT')
    except BaseException:
        con.execute('ROLLBACK')
        con.close()
        raise
    counts = dict(con.execute(SQL['audit_counts']).fetchall())
    cur = con.execute(SQL['audit_cast_checks'], {'batch_id': batch_id})
    cast_checks = dict(zip([d[0] for d in cur.description], cur.fetchone()))
    cur = con.execute(SQL['audit_semantics'])
    semantics = dict(zip([d[0] for d in cur.description], cur.fetchone()))
    ods_counts = {t: con.execute(f'SELECT count(*) FROM ods.{t} WHERE _batch_id = ?', [batch_id]).fetchone()[0]
                  for t in ['customers', 'sellers', 'products', 'orders', 'order_items', 'payments', 'shipping', 'calendar']}
    con.close()
    checks = {
        'grain_orders_equal_ods': counts['fact_order'] == ods_counts['orders'],
        'grain_lines_equal_ods': counts['fact_order_line'] == ods_counts['order_items'],
        'grain_payments_equal_ods': counts['fact_payment'] == ods_counts['payments'],
        'grain_fulfillment_equal_ods': counts['fact_fulfillment'] == ods_counts['shipping'],
        'dims_equal_ods': counts['dim_customer'] == ods_counts['customers'] and counts['dim_product'] == ods_counts['products']
                          and counts['dim_seller'] == ods_counts['sellers'] and counts['dim_date'] == ods_counts['calendar'],
        'cast_checks_zero': all(v == 0 for v in cast_checks.values()),
        'order_merch_equals_line_merch': semantics['merch_all'] == semantics['merch_lines'],
        'payments_reconcile': semantics['payment_mismatch'] == 0,
        'no_approval_equals_cancelled': semantics['no_approval'] == semantics['status_cancelled'],
        'no_anonymous_orders': semantics['anonymous_orders'] == 0,
    }
    return {'task_id': 'DW-03', 'db': str(db), 'batch_id': batch_id, 'row_counts': counts, 'ods_counts': ods_counts,
            'cast_checks': cast_checks, 'semantics_at_cutoff': semantics, 'checks': checks, 'all_checks_passed': all(checks.values()),
            'notes': ['取消订单与截止后才审批的订单保留在事实表中，由 approved_ts 在 DWS/ADS 过滤（transaction-rules-v1）',
                      '没有匿名客户、退款或隔离记录（DATA-07、DATA-08）；如出现，ODS 加载前的清洗规则会将其隔离']}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--db', type=Path, required=True)
    ap.add_argument('--audit', type=Path)
    a = ap.parse_args()
    r = build(a.db)
    if a.audit:
        a.audit.write_text(json.dumps(r, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps({'counts': r['row_counts'], 'checks': r['checks']}, ensure_ascii=False))
    raise SystemExit(0 if r['all_checks_passed'] else 1)


if __name__ == '__main__':
    main()
