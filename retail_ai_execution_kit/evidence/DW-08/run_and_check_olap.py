"""DW-08: run the OLAP query set against the published build and check that totals reconcile.
usage: .venv/bin/python evidence/DW-08/run_and_check_olap.py   (writes reports/warehouse/olap_checks.json)
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
from db import connect, sql_blocks  # noqa: E402

latest = json.loads((ROOT / 'warehouse/builds/latest.json').read_text(encoding='utf-8'))
con = connect(ROOT / 'warehouse/builds' / latest['file'], read_only=True)
Q = sql_blocks(ROOT / 'sql/olap_examples.sql')
V = "approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'"
ok, checks, outputs = [], [], {}


def check(name, cond, expected, got):
    ok.append(bool(cond))
    checks.append({'check': name, 'status': 'passed' if cond else 'failed', 'expected': str(expected), 'got': str(got)})
    print('PASS' if cond else 'FAIL', name, '| expected', expected, '| got', got)


def run(name):
    cur = con.execute(Q[name])
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    question = [ln[3:].strip() for ln in Q[name].splitlines() if ln.startswith('-- Question')][0]
    outputs[name] = {'question': question, 'columns': cols, 'rows': len(rows),
                     'sample': [[str(v) for v in r] for r in rows[:5]]}
    return cols, rows


def one(sql):
    return con.execute(sql).fetchone()


cols, rows = run('q1_slice_year_by_region')
tot = one(f"SELECT count(*), sum(merch_usd) FROM dwd.fact_order o JOIN dwd.dim_date d ON d.date_key = o.purchase_date_key WHERE d.year = 2025 AND {V}")
check('q1 slice: regions add up to the 2025 total (orders, merchandise)', (sum(r[1] for r in rows), sum(r[2] for r in rows)) == tot, tot, (sum(r[1] for r in rows), sum(r[2] for r in rows)))
cols, rows = run('q2_dice_q4_2025_two_regions_three_categories')
check('q2 dice: 2 regions x 3 categories = 6 cells', len(rows) == 6 and {r[0] for r in rows} == {'West', 'South'}, 6, len(rows))
cols, rows = run('q3_rollup_year_quarter_month')
lvl = {}
for r in rows:
    lvl.setdefault(r[5], []).append(r)
grand = lvl[7][0][3]
check('q3 roll-up: months, quarter subtotals, year subtotals and grand total all equal the same total',
      sum(r[3] for r in lvl[0]) == sum(r[3] for r in lvl[1]) == sum(r[3] for r in lvl[3]) == grand == Decimal('1380161.23'), '1380161.23',
      (sum(r[3] for r in lvl[0]), sum(r[3] for r in lvl[1]), sum(r[3] for r in lvl[3]), grand))
mon = one(f"SELECT count(*), sum(merch_usd) FROM dwd.fact_order o JOIN dwd.dim_date d ON d.date_key = o.purchase_date_key WHERE d.year = 2025 AND d.month = 11 AND {V}")
_, days = run('q4a_drill_month_to_day')
check('q4a drill month->day: days add up to the month', (sum(r[1] for r in days), sum(r[2] for r in days)) == mon, mon, (sum(r[1] for r in days), sum(r[2] for r in days)))
day = next(r for r in days if str(r[0]) == '2025-11-28')
_, orders = run('q4b_drill_day_to_order')
check('q4b drill day->order: orders add up to the day', (len(orders), sum(r[3] for r in orders)) == (day[1], day[2]), (day[1], day[2]), (len(orders), sum(r[3] for r in orders)))
_, lines = run('q4c_drill_order_to_line')
check('q4c drill order->line: lines add up to the orders, line count = sum of item_lines',
      sum(r[4] for r in lines) == sum(r[3] for r in orders) and len(lines) == sum(r[2] for r in orders), (sum(r[3] for r in orders), sum(r[2] for r in orders)), (sum(r[4] for r in lines), len(lines)))
cols, rows = run('q5_pivot_month_by_region_2026h1')
h1 = one(f"SELECT sum(merch_usd) FROM dwd.fact_order o JOIN dwd.dim_date d ON d.date_key = o.purchase_date_key WHERE d.year = 2026 AND d.month <= 6 AND {V}")[0]
cells = sum(v for r in rows for v in r[1:] if v is not None)
check('q5 pivot: 6 months x 4 region columns, cells add up to the unpivoted total', len(rows) == 6 and len(cols) == 5 and cells == h1, h1, cells)
cols, rows = run('q6_geo_drill_region_state_city')
by = {}
for r in rows:
    by.setdefault(r[4], []).append(r)
check('q6 geo drill: cities = state subtotals = region total', sum(r[3] for r in by[0]) == sum(r[3] for r in by[1]) == by[3][0][3], by[3][0][3],
      (sum(r[3] for r in by[0]), sum(r[3] for r in by[1])))
cols, rows = run('q7_category_share_within_region')
shares = {}
for r in rows:
    shares[r[0]] = shares.get(r[0], 0) + r[3]
check('q7 shares sum to 1 within each region', all(abs(s - 1) < 1e-12 for s in shares.values()), 1.0, {k: round(v, 12) for k, v in shares.items()})
cols, rows = run('q8_payment_type_mix')
paid = one(f"SELECT sum(payment_value_usd) FROM dwd.fact_order o JOIN dwd.dim_date d ON d.date_key = o.purchase_date_key WHERE d.year = 2025 AND {V}")[0]
n_orders = one(f"SELECT count(*) FROM dwd.fact_order o JOIN dwd.dim_date d ON d.date_key = o.purchase_date_key WHERE d.year = 2025 AND {V}")[0]
check('q8 payment mix: paid amount adds up to order-level payments; orders_using_type is not additive (two-payment orders)',
      sum(r[3] for r in rows) == paid and sum(r[1] for r in rows) >= n_orders, (paid, f'>= {n_orders}'), (sum(r[3] for r in rows), sum(r[1] for r in rows)))
naive = one(f"""SELECT sum(l.item_price_usd) FROM dwd.fact_order_line l JOIN dwd.fact_payment pm USING (order_id) JOIN dwd.fact_order o USING (order_id)
               WHERE {V.replace('approved_ts', 'o.approved_ts')}""")[0]
check('joining lines to payments would double count (why the set never does it)', naive > Decimal('1380161.23'), '> 1380161.23', naive)
con.close()
out = {'task_id': 'DW-08', 'build': latest, 'operations': {'slice': ['q1'], 'dice': ['q2'], 'roll_up': ['q3', 'q6'], 'drill_down': ['q4a', 'q4b', 'q4c', 'q6'],
       'pivot': ['q5'], 'ranking_share': ['q7'], 'other_grain': ['q8']},
       'route_note': '交易路线有订单号，下钻到订单与明细；不涉及行为事件层', 'queries': outputs, 'checks': checks, 'all_checks_passed': all(ok)}
(ROOT / 'reports/warehouse/olap_checks.json').write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
