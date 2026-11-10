-- DWS business aggregates (DW-04). Valid purchase = approved_ts < $as_of (transaction-rules-v1);
-- for the published warehouse $as_of is the data cutoff 2026-11-08T00:00:00Z. Day = purchase date (UTC).
-- Additivity (also in sql/ddl.sql comments):
--   additive: valid_orders (across days and regions), valid_lines, merch_usd, shipping_usd
--   NOT additive: buyers (distinct customers per day), orders_containing (an order can contain several
--   categories/products). Monthly or yearly distinct counts must be recomputed from DWD, never summed.

-- name: build
DELETE FROM dws.orders_daily_region; DELETE FROM dws.sales_daily_category_region;
DELETE FROM dws.customer_daily; DELETE FROM dws.product_daily;
INSERT INTO dws.orders_daily_region
SELECT o.purchase_date_key, c.customer_region, count(*), sum(o.merch_usd), sum(o.shipping_usd), count(DISTINCT o.customer_id)
FROM dwd.fact_order o JOIN dwd.dim_customer c USING (customer_id)
WHERE o.approved_ts < $as_of GROUP BY ALL;
INSERT INTO dws.sales_daily_category_region
SELECT l.purchase_date_key, p.product_category, c.customer_region, count(*), sum(l.item_price_usd), sum(l.item_shipping_usd),
       count(DISTINCT l.order_id)
FROM dwd.fact_order_line l JOIN dwd.fact_order o USING (order_id) JOIN dwd.dim_product p USING (product_id)
JOIN dwd.dim_customer c ON c.customer_id = l.customer_id
WHERE o.approved_ts < $as_of GROUP BY ALL;
INSERT INTO dws.customer_daily
SELECT customer_id, purchase_date_key, count(*), sum(merch_usd)
FROM dwd.fact_order WHERE approved_ts < $as_of GROUP BY ALL;
INSERT INTO dws.product_daily
SELECT l.product_id, l.purchase_date_key, count(*), sum(l.item_price_usd), count(DISTINCT l.order_id)
FROM dwd.fact_order_line l JOIN dwd.fact_order o USING (order_id)
WHERE o.approved_ts < $as_of GROUP BY ALL;

-- name: audit
SELECT 'orders_daily_region' t, count(*) n, sum(valid_orders) orders_or_lines, sum(merch_usd)::VARCHAR merch FROM dws.orders_daily_region
UNION ALL SELECT 'sales_daily_category_region', count(*), sum(valid_lines), sum(merch_usd)::VARCHAR FROM dws.sales_daily_category_region
UNION ALL SELECT 'customer_daily', count(*), sum(valid_orders), sum(merch_usd)::VARCHAR FROM dws.customer_daily
UNION ALL SELECT 'product_daily', count(*), sum(valid_lines), sum(merch_usd)::VARCHAR FROM dws.product_daily;

-- name: dwd_totals
SELECT count(*) FILTER (WHERE approved_ts < $as_of) AS valid_orders,
       sum(merch_usd) FILTER (WHERE approved_ts < $as_of)::VARCHAR AS merch,
       (SELECT count(*) FROM dwd.fact_order_line l JOIN dwd.fact_order o USING (order_id) WHERE o.approved_ts < $as_of) AS valid_lines
FROM dwd.fact_order;

-- name: additivity_demo
-- monthly distinct buyers: correct (from DWD) vs wrong (sum of daily distinct counts)
WITH m AS (SELECT purchase_date_key // 100 AS ym, count(DISTINCT customer_id) AS buyers_correct
           FROM dwd.fact_order WHERE approved_ts < $as_of GROUP BY 1),
     d AS (SELECT date_key // 100 AS ym, sum(buyers) AS buyers_summed_wrong FROM dws.orders_daily_region GROUP BY 1)
SELECT ym, buyers_correct, buyers_summed_wrong FROM m JOIN d USING (ym) ORDER BY ym;
