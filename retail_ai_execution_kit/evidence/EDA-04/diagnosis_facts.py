"""EDA-04 facts: customer-structure and AOV mix decomposition (2026 vs 2025, Jan-Oct). Writes reports/analysis/diagnosis_facts.json."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
from runtime import open_current  # noqa: E402

V = "o.approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00' AND month(o.purchase_ts) <= 10"
con, ptr = open_current()
cust = con.execute(f"""WITH f AS (SELECT customer_id, min(purchase_ts) first FROM dwd.fact_order WHERE approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00' GROUP BY 1)
  SELECT year(o.purchase_ts) y, CASE WHEN year(f.first) = year(o.purchase_ts) THEN 'new_this_year' ELSE 'returning' END t,
         count(DISTINCT o.customer_id) buyers, count(*) orders, sum(o.merch_usd)::DOUBLE merch
  FROM dwd.fact_order o JOIN f USING (customer_id) WHERE {V} AND year(o.purchase_ts) IN (2025, 2026) GROUP BY 1, 2 ORDER BY 1, 2""").fetchall()
mix = con.execute(f"""SELECT year(o.purchase_ts) y, p.product_category c, count(*) lines, sum(l.item_price_usd)::DOUBLE m
  FROM dwd.fact_order_line l JOIN dwd.fact_order o USING (order_id) JOIN dwd.dim_product p USING (product_id)
  WHERE {V} AND year(o.purchase_ts) IN (2025, 2026) GROUP BY 1, 2""").fetchall()
lines_per_order = con.execute(f"SELECT year(o.purchase_ts), avg(o.item_lines) FROM dwd.fact_order o WHERE {V} AND year(o.purchase_ts) IN (2025, 2026) GROUP BY 1 ORDER BY 1").fetchall()
late = con.execute(f"""SELECT year(o.purchase_ts), avg(o.late_by_date::INT), avg(o.review_score) FROM dwd.fact_order o WHERE {V} AND year(o.purchase_ts) IN (2025, 2026)
  AND o.delivered_ts IS NOT NULL GROUP BY 1 ORDER BY 1""").fetchall()
con.close()
L = {}
for y, c, n, m in mix:
    L.setdefault(c, {})[y] = (n, m)
tot = {y: sum(v[y][0] for v in L.values()) for y in (2025, 2026)}
# line-value change = mix effect (share shift at 2025 price) + price effect (price change at 2026 share)
mix_eff = sum((L[c][2026][0] / tot[2026] - L[c][2025][0] / tot[2025]) * (L[c][2025][1] / L[c][2025][0]) for c in L)
price_eff = sum((L[c][2026][0] / tot[2026]) * (L[c][2026][1] / L[c][2026][0] - L[c][2025][1] / L[c][2025][0]) for c in L)
avg_line = {y: sum(v[y][1] for v in L.values()) / tot[y] for y in (2025, 2026)}
out = {'task_id': 'EDA-04', 'release': ptr['version'], 'period': 'Jan-Oct, 2026 vs 2025',
       'customer_structure': [dict(zip(['year', 'type', 'buyers', 'orders', 'merch_usd'], r)) for r in cust],
       'avg_line_value': {str(k): round(v, 4) for k, v in avg_line.items()},
       'avg_line_change': round(avg_line[2026] - avg_line[2025], 4), 'mix_effect': round(mix_eff, 4), 'within_category_price_effect': round(price_eff, 4),
       'lines_per_order': {str(y): round(v, 4) for y, v in lines_per_order},
       'delivery_and_review': {str(y): {'late_by_date_rate': round(a, 4), 'avg_review_score': round(b, 4)} for y, a, b in late}}
(ROOT / 'reports/analysis/diagnosis_facts.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(out, ensure_ascii=False))
