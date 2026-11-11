"""UI-02: offline extraction of data-issue samples for the data page (run by the build owner, not the app).

The app reads only allowed ADS views, which hold no order-level rows. This script opens the published
release read-only and writes a few example orders per issue type to reports/ui/data_issue_samples.json,
with the release version so the page can tell when the samples are out of date. No customer ids, names,
cities or zip codes are written; order ids are synthetic.

usage: .venv/bin/python src/retail_bi/ui/issue_samples.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
from runtime import open_current  # noqa: E402

CUT = "TIMESTAMPTZ '2026-11-08 00:00:00+00'"
COLS = """order_id, order_status, CAST(purchase_ts AS VARCHAR) AS purchase_ts, CAST(approved_ts AS VARCHAR) AS approved_ts,
          CAST(delivered_ts AS VARCHAR) AS delivered_ts, CAST(merch_usd AS VARCHAR) AS merch_usd, item_lines"""
ISSUES = {
    'cancelled_no_approval': ('已取消：没有审批时间，不计入有效购买', f"approved_ts IS NULL"),
    'pending_at_cutoff': ('截止前下单、截止后才审批：截止时不计入有效购买', f"approved_ts >= {CUT}"),
    'not_delivered_yet': ('已审批但截止前未送达：送达时间为空（不插补）', f"approved_ts < {CUT} AND delivered_ts IS NULL"),
    'repeated_product_lines': ('同一订单重复商品：保留为独立明细（每行价格不同），不合并为数量',
                               "order_id IN (SELECT order_id FROM dwd.fact_order_line GROUP BY order_id, product_id HAVING count(*) > 1)"),
}


def main():
    con, ptr = open_current()
    out = {'release': ptr['version'], 'generated_by': 'src/retail_bi/ui/issue_samples.py', 'columns_excluded': 'customer_id 与客户属性（不必要的个人信息）', 'issues': {}}
    for k, (label, where) in ISSUES.items():
        n = con.execute(f'SELECT count(*) FROM dwd.fact_order WHERE {where}').fetchone()[0]
        cur = con.execute(f'SELECT {COLS} FROM dwd.fact_order WHERE {where} ORDER BY purchase_ts, order_id LIMIT 5')
        names = [d[0] for d in cur.description]
        out['issues'][k] = {'label': label, 'count': int(n), 'samples': [dict(zip(names, r)) for r in cur.fetchall()]}
    extra, groups = con.execute('SELECT sum(c - 1), count(*) FROM (SELECT order_id, product_id, count(*) c FROM dwd.fact_order_line GROUP BY 1, 2 HAVING count(*) > 1)').fetchone()
    out['issues']['repeated_product_lines'].update({'count_unit': 'orders', 'extra_lines': int(extra), 'groups': int(groups)})
    con.close()
    p = ROOT / 'reports/ui/data_issue_samples.json'
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(p, {k: v['count'] for k, v in out['issues'].items()})


if __name__ == '__main__':
    main()
