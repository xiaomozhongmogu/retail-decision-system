"""DATA-08: purchase, cancellation and amount rules, as executable DuckDB SQL.

One place defines the rules; contracts/metrics.json quotes the same SQL and the
reconciliation below executes it. Rules (docs/transaction_rules.md):

- valid purchase = an order whose payment approval happened (approved_ts not
  null). In this data that is exactly "status != cancelled" (checked below);
  approval is used because it is observable at the time, final status is not.
- event time of a purchase = purchase_ts (order time). At an as_of point an
  order counts only if approved_ts < as_of (approval lag is at most 24 hours).
- cancelled orders are excluded from sales and order counts and reported on
  their own, attributed to purchase_ts (the cancellation time is unknown).
- merchandise amount = item_price_usd; shipping is reported separately; payment
  rows are used only for reconciliation, never as "paid GMV" or revenue.
- there are no refunds, returns or negative amounts in this data; if any
  appeared they would be quarantined, not netted silently.

usage: .venv/bin/python src/retail_bi/data/transactions.py --clean-dir <clean dir> \
         --out reports/data/transaction_reconciliation.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import duckdb

RULE_VERSION = 'transaction-rules-v1'
APPROVAL_MAX_LAG_HOURS = 24          # measured: max(approved_ts - purchase_ts) = 24 h
LABEL_MATURITY_DAYS = 1              # a label window [t, t+h) is complete once t+h+1 day <= cutoff

VIEWS = {
    'orders_all': "SELECT * FROM read_parquet('{d}/orders.parquet')",
    'items_all': "SELECT * FROM read_parquet('{d}/order_items.parquet')",
    'payments_all': "SELECT * FROM read_parquet('{d}/payments.parquet')",
    # valid purchase: approval observed (as of the data cutoff)
    'orders_valid': "SELECT * FROM orders_all WHERE approved_ts IS NOT NULL",
    'orders_cancelled': "SELECT * FROM orders_all WHERE approved_ts IS NULL",
    'order_amounts': """
        SELECT o.order_id, o.customer_id, o.purchase_ts, o.approved_ts, o.order_status,
               o.approved_ts IS NOT NULL AS is_valid,
               sum(i.item_price_usd) AS merch_usd, sum(i.item_shipping_usd) AS shipping_usd,
               sum(i.item_total_usd) AS order_value_usd, count(*) AS item_lines
        FROM orders_all o JOIN items_all i USING (order_id)
        GROUP BY ALL""",
}

# Metric SQL over a window [:start, :end) on purchase_ts. :as_of applies the
# observability rule (approval before as_of); for complete past periods as_of = cutoff.
METRIC_SQL = {
    'valid_orders': "SELECT count(*) FROM order_amounts WHERE is_valid AND approved_ts < $as_of AND purchase_ts >= $start AND purchase_ts < $end",
    'merchandise_sales_usd': "SELECT coalesce(sum(merch_usd), 0) FROM order_amounts WHERE is_valid AND approved_ts < $as_of AND purchase_ts >= $start AND purchase_ts < $end",
    'shipping_usd': "SELECT coalesce(sum(shipping_usd), 0) FROM order_amounts WHERE is_valid AND approved_ts < $as_of AND purchase_ts >= $start AND purchase_ts < $end",
    'order_value_usd': "SELECT coalesce(sum(order_value_usd), 0) FROM order_amounts WHERE is_valid AND approved_ts < $as_of AND purchase_ts >= $start AND purchase_ts < $end",
    'buyers': "SELECT count(DISTINCT customer_id) FROM order_amounts WHERE is_valid AND approved_ts < $as_of AND customer_id IS NOT NULL AND purchase_ts >= $start AND purchase_ts < $end",
    'aov_usd': "SELECT sum(merch_usd) / nullif(count(*), 0) FROM order_amounts WHERE is_valid AND approved_ts < $as_of AND purchase_ts >= $start AND purchase_ts < $end",
    'cancelled_orders': "SELECT count(*) FROM order_amounts WHERE NOT is_valid AND purchase_ts >= $start AND purchase_ts < $end AND purchase_ts < $as_of",
    'cancelled_merchandise_usd': "SELECT coalesce(sum(merch_usd), 0) FROM order_amounts WHERE NOT is_valid AND purchase_ts >= $start AND purchase_ts < $end AND purchase_ts < $as_of",
}


def connect(clean_dir: Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET timezone = 'UTC'")
    for name, sql in VIEWS.items():
        con.execute(f'CREATE VIEW {name} AS {sql.format(d=clean_dir.as_posix())}')
    return con


def metric(con, name, start, end, as_of):
    v = con.execute(METRIC_SQL[name], {'start': start, 'end': end, 'as_of': as_of}).fetchone()[0]
    return str(v) if isinstance(v, Decimal) else v


def totals(con, where):
    r = con.execute(f"""SELECT count(*), coalesce(sum(item_lines),0), coalesce(sum(merch_usd),0),
                               coalesce(sum(shipping_usd),0), coalesce(sum(order_value_usd),0)
                        FROM order_amounts WHERE {where}""").fetchone()
    return {'orders': r[0], 'item_lines': int(r[1]), 'merch_usd': r[2], 'shipping_usd': r[3], 'order_value_usd': r[4]}


def reconcile(clean_dir: Path, cutoff: str) -> dict:
    con = connect(clean_dir)
    c = f"TIMESTAMPTZ '{cutoff}'"
    # state as seen at the cutoff: the clean layer keeps source approvals that happen after the cutoff
    raw = totals(con, 'TRUE')
    valid = totals(con, f'approved_ts < {c}')
    canc = totals(con, 'approved_ts IS NULL')
    pending = totals(con, f'approved_ts >= {c}')
    by_status = {s: totals(con, f"order_status = '{s}'") for s in ('delivered', 'shipped', 'processing', 'cancelled')}
    pay_total = con.execute('SELECT sum(payment_value_usd) FROM payments_all').fetchone()[0]
    pay_by_valid = dict(con.execute(f"""SELECT a.approved_ts < {c}, sum(p.payment_value_usd) FROM payments_all p
                                       JOIN order_amounts a USING (order_id) WHERE a.approved_ts IS NOT NULL GROUP BY 1""").fetchall())
    lag = con.execute("SELECT max(epoch(approved_ts - purchase_ts)) / 3600 FROM orders_all").fetchone()[0]
    rule_vs_status = con.execute("""SELECT count(*) FROM orders_all
                                    WHERE (approved_ts IS NOT NULL) <> (order_status <> 'cancelled')""").fetchone()[0]
    negatives = con.execute("""SELECT count(*) FROM items_all WHERE item_price_usd < 0 OR item_shipping_usd < 0 OR item_total_usd < 0""").fetchone()[0]
    monthly = con.execute("""SELECT strftime(purchase_ts, '%Y-%m') m,
                                    count(*) FILTER (WHERE is_valid), sum(merch_usd) FILTER (WHERE is_valid),
                                    count(*) FILTER (WHERE NOT is_valid), coalesce(sum(merch_usd) FILTER (WHERE NOT is_valid), 0)
                             FROM order_amounts GROUP BY 1 ORDER BY 1""").fetchall()

    def s(d):
        return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in d.items()}

    diff = {k: raw[k] - valid[k] for k in raw}
    checks = {
        'raw_minus_valid_equals_cancelled_plus_pending': all(diff[k] == canc[k] + pending[k] for k in raw),
        'valid_plus_pending_equals_delivered_shipped_processing': all(
            valid[k] + pending[k] == by_status['delivered'][k] + by_status['shipped'][k] + by_status['processing'][k] for k in raw),
        'payments_equal_order_value_all_orders': pay_total == raw['order_value_usd'],
        'payments_equal_order_value_valid_orders': pay_by_valid.get(True) == valid['order_value_usd'],
        'merch_plus_shipping_equals_order_value': raw['merch_usd'] + raw['shipping_usd'] == raw['order_value_usd'],
        'approval_rule_matches_non_cancelled_status_exactly': rule_vs_status == 0,
        'approval_lag_within_declared_max': lag <= APPROVAL_MAX_LAG_HOURS,
        'no_negative_or_refund_amounts': negatives == 0,
    }
    # metric SQL executed on example windows (as_of = cutoff for complete periods)
    examples = {}
    for label, start, end, as_of in [
        ('2026-Q3 (complete period)', '2026-07-01 00:00:00+00', '2026-10-01 00:00:00+00', cutoff),
        ('full history', '2024-01-01 00:00:00+00', cutoff, cutoff),
        ('2026-11-01..cutoff seen at 2026-11-05 (observability)', '2026-11-01 00:00:00+00', cutoff, '2026-11-05 00:00:00+00'),
        ('empty window 2023-01 (zero denominator)', '2023-01-01 00:00:00+00', '2023-02-01 00:00:00+00', cutoff),
    ]:
        examples[label] = {k: metric(con, k, start, end, as_of) for k in METRIC_SQL}
    full = examples['full history']
    checks['metric_sql_full_history_matches_reconciliation'] = (
        full['valid_orders'] == valid['orders'] and Decimal(full['merchandise_sales_usd']) == valid['merch_usd']
        and full['cancelled_orders'] == canc['orders'])
    checks['aov_is_sales_over_orders'] = abs(Decimal(str(full['aov_usd'])) - valid['merch_usd'] / valid['orders']) < Decimal('1e-9')
    checks['zero_denominator_returns_null'] = examples['empty window 2023-01 (zero denominator)']['aov_usd'] is None
    return {
        'task_id': 'DATA-08', 'rule_version': RULE_VERSION, 'generated_by': 'src/retail_bi/data/transactions.py',
        'clean_dir_manifest_sha256': hashlib.sha256((clean_dir / 'manifest.json').read_bytes()).hexdigest(),
        'cutoff_exclusive': cutoff,
        'raw_all_orders': s(raw), 'valid_orders_at_cutoff': s(valid), 'cancelled_orders': s(canc),
        'pending_approval_at_cutoff': s(pending),
        'raw_minus_valid': s(diff),
        'difference_explained': '原始与有效之间的差额逐项等于“已取消”加“截止时尚未审批”两部分（订单数、明细行、商品金额、运费、订单金额）。后者是截止前下单、源数据中截止后才审批的订单，按可观察规则截止时不计入；没有退款、冲销、负金额或隔离行',
        'by_status': {k: s(v) for k, v in by_status.items()},
        'delivered_only_sensitivity': {
            'orders': by_status['delivered']['orders'], 'merch_usd': str(by_status['delivered']['merch_usd']),
            'share_of_valid_merch': round(float(by_status['delivered']['merch_usd'] / valid['merch_usd']), 4),
            'note': '若只算已送达，商品金额少 shipped+processing 部分；本项目采用“已审批”口径'},
        'payments': {'total_usd': str(pay_total), 'valid_orders_usd': str(pay_by_valid.get(True)),
                     'pending_orders_usd': str(pay_by_valid.get(False)),
                     'cancelled_orders_usd': str(pay_total - pay_by_valid.get(True, 0) - pay_by_valid.get(False, 0)),
                     'note': '取消单也有支付记录，但没有退款记录；支付只用于对账，不据此命名“已支付 GMV”或推断退款'},
        'approval_lag_hours_max': lag, 'label_maturity_days': LABEL_MATURITY_DAYS,
        'monthly': [{'month': m, 'valid_orders': a, 'valid_merch_usd': str(b), 'cancelled_orders': c, 'cancelled_merch_usd': str(d)}
                    for m, a, b, c, d in monthly],
        'metric_examples': examples,
        'checks': checks,
        'all_checks_passed': all(checks.values()),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--clean-dir', type=Path, required=True)
    ap.add_argument('--cutoff', default='2026-11-08 00:00:00+00')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    r = reconcile(a.clean_dir.resolve(), a.cutoff)
    a.out.write_text(json.dumps(r, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps({'checks': r['checks'], 'raw': r['raw_all_orders'], 'valid': r['valid_orders_at_cutoff']}, ensure_ascii=False, default=str))
    raise SystemExit(0 if r['all_checks_passed'] else 1)


if __name__ == '__main__':
    main()
