-- Standard OLAP query set (DW-08). Run against a published build (warehouse/builds/latest.json).
-- All money is USD merchandise amount of valid purchases (approved before the 2026-11-08 cutoff), data are synthetic.
-- Order-level counts use dwd.fact_order (one row per order); line-level amounts use dwd.fact_order_line.
-- Payment rows are never joined to lines (that would double amounts for two-payment orders).

-- name: q1_slice_year_by_region
-- Question: In 2025, how much merchandise did each customer region buy, and how many orders?  (slice: year = 2025)
SELECT c.customer_region, count(*) AS valid_orders, sum(o.merch_usd) AS merchandise_usd,
       sum(o.merch_usd) / count(*) AS aov_usd
FROM dwd.fact_order o JOIN dwd.dim_customer c USING (customer_id) JOIN dwd.dim_date d ON d.date_key = o.purchase_date_key
WHERE d.year = 2025 AND o.approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'
GROUP BY 1 ORDER BY merchandise_usd DESC;

-- name: q2_dice_q4_2025_two_regions_three_categories
-- Question: In 2025 Q4, for the West and South regions, how did Electronics, Mobile and Fashion sell?  (dice: 3 dimensions restricted)
SELECT c.customer_region, p.product_category, count(*) AS valid_lines, sum(l.item_price_usd) AS merchandise_usd,
       count(DISTINCT l.order_id) AS orders_containing
FROM dwd.fact_order_line l JOIN dwd.fact_order o USING (order_id) JOIN dwd.dim_product p USING (product_id)
JOIN dwd.dim_customer c ON c.customer_id = l.customer_id JOIN dwd.dim_date d ON d.date_key = l.purchase_date_key
WHERE d.year = 2025 AND d.quarter = 4 AND c.customer_region IN ('West', 'South')
  AND p.product_category IN ('Electronics & Accessories', 'Mobile & Telecom', 'Fashion')
  AND o.approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'
GROUP BY 1, 2 ORDER BY 1, 2;

-- name: q3_rollup_year_quarter_month
-- Question: Merchandise by month, with quarter and year subtotals and a grand total.  (roll-up along the date hierarchy)
SELECT d.year, d.quarter, d.month, sum(o.merch_usd) AS merchandise_usd, count(*) AS valid_orders,
       grouping(d.year, d.quarter, d.month) AS level   -- 0 month, 1 quarter subtotal, 3 year subtotal, 7 grand total
FROM dwd.fact_order o JOIN dwd.dim_date d ON d.date_key = o.purchase_date_key
WHERE o.approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'
GROUP BY ROLLUP (d.year, d.quarter, d.month) ORDER BY d.year NULLS LAST, d.quarter NULLS LAST, d.month NULLS LAST;

-- name: q4a_drill_month_to_day
-- Question: November 2025 by day (drill down from month to day).
SELECT d.calendar_date, count(*) AS valid_orders, sum(o.merch_usd) AS merchandise_usd
FROM dwd.fact_order o JOIN dwd.dim_date d ON d.date_key = o.purchase_date_key
WHERE d.year = 2025 AND d.month = 11 AND o.approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'
GROUP BY 1 ORDER BY 1;

-- name: q4b_drill_day_to_order
-- Question: The orders of 2025-11-28 (drill down from day to order).
SELECT o.order_id, o.customer_id, o.item_lines, o.merch_usd
FROM dwd.fact_order o WHERE o.purchase_date_key = 20251128 AND o.approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'
ORDER BY 1;

-- name: q4c_drill_order_to_line
-- Question: The lines of every order on 2025-11-28 (drill down from order to line).
SELECT l.order_id, l.order_item_seq, l.product_id, p.product_category, l.item_price_usd
FROM dwd.fact_order_line l JOIN dwd.fact_order o USING (order_id) JOIN dwd.dim_product p USING (product_id)
WHERE l.purchase_date_key = 20251128 AND o.approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'
ORDER BY 1, 2;

-- name: q5_pivot_month_by_region_2026h1
-- Question: 2026 first half, merchandise per month as rows and regions as columns.  (pivot / rotate)
PIVOT (SELECT d.month, c.customer_region, o.merch_usd
       FROM dwd.fact_order o JOIN dwd.dim_customer c USING (customer_id) JOIN dwd.dim_date d ON d.date_key = o.purchase_date_key
       WHERE d.year = 2026 AND d.month <= 6 AND o.approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00')
ON customer_region USING sum(merch_usd) GROUP BY month ORDER BY month;

-- name: q6_geo_drill_region_state_city
-- Question: In the West region in 2026, which states and cities buy most?  (drill along region > state > city)
SELECT c.customer_state, c.customer_city, count(*) AS valid_orders, sum(o.merch_usd) AS merchandise_usd,
       grouping(c.customer_state, c.customer_city) AS level   -- 0 city, 1 state subtotal, 3 region total
FROM dwd.fact_order o JOIN dwd.dim_customer c USING (customer_id) JOIN dwd.dim_date d ON d.date_key = o.purchase_date_key
WHERE c.customer_region = 'West' AND d.year = 2026 AND o.approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'
GROUP BY ROLLUP (c.customer_state, c.customer_city) ORDER BY c.customer_state NULLS LAST, merchandise_usd DESC;

-- name: q7_category_share_within_region
-- Question: Within each region, what share of 2025 merchandise does each category take, and its rank?
SELECT c.customer_region, p.product_category, sum(l.item_price_usd) AS merchandise_usd,
       sum(l.item_price_usd) / sum(sum(l.item_price_usd)) OVER (PARTITION BY c.customer_region) AS share_in_region,
       rank() OVER (PARTITION BY c.customer_region ORDER BY sum(l.item_price_usd) DESC) AS rank_in_region
FROM dwd.fact_order_line l JOIN dwd.fact_order o USING (order_id) JOIN dwd.dim_product p USING (product_id)
JOIN dwd.dim_customer c ON c.customer_id = l.customer_id JOIN dwd.dim_date d ON d.date_key = l.purchase_date_key
WHERE d.year = 2025 AND o.approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'
GROUP BY 1, 2 ORDER BY 1, rank_in_region;

-- name: q8_payment_type_mix
-- Question: How many 2025 orders used each payment type, and how much was paid with it?  (payment grain kept apart from lines)
SELECT pm.payment_type, count(DISTINCT pm.order_id) AS orders_using_type, count(*) AS payment_rows, sum(pm.payment_value_usd) AS paid_usd
FROM dwd.fact_payment pm JOIN dwd.fact_order o USING (order_id) JOIN dwd.dim_date d ON d.date_key = o.purchase_date_key
WHERE d.year = 2025 AND o.approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'
GROUP BY 1 ORDER BY paid_usd DESC;
