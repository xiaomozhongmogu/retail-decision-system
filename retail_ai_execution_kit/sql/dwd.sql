-- DWD build (DW-03): typed star schema from one ODS batch. Executed by src/retail_bi/warehouse/dwd.py
-- inside one transaction. Casting rules follow contracts/data_contract.json (synthetic-transaction-v1):
-- empty text -> NULL; naive timestamps read as UTC (session time zone is UTC, D011);
-- integers stored as "8.0" are checked to be whole numbers by the audit block.
-- Transaction semantics (transaction-rules-v1): nothing is dropped here; cancelled orders and
-- orders approved after a given as_of stay in the facts and are filtered by approved_ts in DWS/ADS.

-- name: clear
-- Drop child tables before parents, then dwd.py re-runs sql/ddl.sql to recreate them empty.
-- (Row DELETEs cannot be used: DuckDB checks foreign keys against rows deleted earlier in the same transaction.)
DROP TABLE IF EXISTS dwd.fact_fulfillment; DROP TABLE IF EXISTS dwd.fact_payment; DROP TABLE IF EXISTS dwd.fact_order_line;
DROP TABLE IF EXISTS dwd.fact_order; DROP TABLE IF EXISTS dwd.dim_customer; DROP TABLE IF EXISTS dwd.dim_seller;
DROP TABLE IF EXISTS dwd.dim_product; DROP TABLE IF EXISTS dwd.dim_geo; DROP TABLE IF EXISTS dwd.dim_date;

-- name: dim_date
INSERT INTO dwd.dim_date
SELECT CAST(strftime(CAST(CAST("date" AS TIMESTAMP) AS DATE), '%Y%m%d') AS INTEGER), CAST(CAST("date" AS TIMESTAMP) AS DATE),
       CAST("year" AS INTEGER), CAST(quarter AS INTEGER), CAST("month" AS INTEGER), month_name, CAST(week AS INTEGER),
       CAST(day_of_week AS INTEGER), day_name, is_weekend = 'True', is_holiday_period = 'True', is_promotion_period = 'True', season
FROM ods.calendar WHERE _batch_id = $batch_id;

-- name: dim_geo
INSERT INTO dwd.dim_geo
SELECT DISTINCT region || '|' || state || '|' || city, region, state, city FROM (
    SELECT customer_region AS region, customer_state AS state, customer_city AS city FROM ods.customers WHERE _batch_id = $batch_id
    UNION SELECT seller_region, seller_state, seller_city FROM ods.sellers WHERE _batch_id = $batch_id);

-- name: dim_customer
INSERT INTO dwd.dim_customer
SELECT customer_id, customer_region || '|' || customer_state || '|' || customer_city, customer_state, customer_region, customer_city,
       CAST(CAST(created_at AS TIMESTAMP) AS DATE)
FROM ods.customers WHERE _batch_id = $batch_id;

-- name: dim_product
INSERT INTO dwd.dim_product
SELECT product_id, product_category, product_name, CAST(CAST(product_weight_g AS DOUBLE) AS BIGINT),
       CAST(product_length_cm AS DOUBLE), CAST(product_height_cm AS DOUBLE), CAST(product_width_cm AS DOUBLE),
       CAST(product_price_base_usd AS DECIMAL(12,2))
FROM ods.products WHERE _batch_id = $batch_id;

-- name: dim_seller
INSERT INTO dwd.dim_seller
SELECT seller_id, seller_region || '|' || seller_state || '|' || seller_city, seller_state, seller_region, seller_city
FROM ods.sellers WHERE _batch_id = $batch_id;

-- name: fact_order
INSERT INTO dwd.fact_order
WITH o AS (
    SELECT order_id, customer_id, order_status,
           CAST(order_purchase_timestamp AS TIMESTAMP)::TIMESTAMPTZ AS purchase_ts,
           CAST(NULLIF(order_approved_at, '') AS TIMESTAMP)::TIMESTAMPTZ AS approved_ts,
           CAST(NULLIF(order_delivered_carrier_date, '') AS TIMESTAMP)::TIMESTAMPTZ AS carrier_handoff_ts,
           CAST(NULLIF(order_delivered_customer_date, '') AS TIMESTAMP)::TIMESTAMPTZ AS delivered_ts,
           CAST(CAST(order_estimated_delivery_date AS TIMESTAMP) AS DATE) AS estimated_delivery_date
    FROM ods.orders WHERE _batch_id = $batch_id),
i AS (SELECT order_id, sum(CAST(item_price_usd AS DECIMAL(12,2))) AS merch, sum(CAST(shipping_cost_usd AS DECIMAL(12,2))) AS ship,
             sum(CAST(item_total_usd AS DECIMAL(12,2))) AS total, count(*) AS n
      FROM ods.order_items WHERE _batch_id = $batch_id GROUP BY order_id),
p AS (SELECT order_id, sum(CAST(payment_value_usd AS DECIMAL(12,2))) AS paid, count(*) AS n
      FROM ods.payments WHERE _batch_id = $batch_id GROUP BY order_id),
r AS (SELECT order_id, CAST(review_score AS INTEGER) AS score, CAST(CAST(review_creation_date AS TIMESTAMP) AS DATE) AS created
      FROM ods.reviews WHERE _batch_id = $batch_id),
s AS (SELECT order_id, CAST(CAST(estimated_delivery_days AS DOUBLE) AS BIGINT) AS est_days FROM ods.shipping WHERE _batch_id = $batch_id)
SELECT o.order_id, o.customer_id, CAST(strftime(CAST(o.purchase_ts AS DATE), '%Y%m%d') AS INTEGER),
       o.purchase_ts, o.approved_ts, o.carrier_handoff_ts, o.delivered_ts, o.estimated_delivery_date, o.order_status,
       i.merch, i.ship, i.total, i.n, p.paid, p.n, r.score, r.created,
       CASE WHEN o.delivered_ts IS NULL THEN NULL ELSE CAST(o.delivered_ts AS DATE) > o.estimated_delivery_date END,
       CASE WHEN o.delivered_ts IS NULL THEN NULL ELSE floor(epoch(o.delivered_ts - o.purchase_ts) / 86400) > s.est_days END
FROM o JOIN i USING (order_id) JOIN p USING (order_id) JOIN s USING (order_id) LEFT JOIN r USING (order_id);

-- name: fact_order_line
INSERT INTO dwd.fact_order_line
SELECT l.order_id, CAST(l.order_item_id AS BIGINT), f.customer_id, f.purchase_date_key, l.product_id, l.seller_id, l.seller_product_id,
       CAST(l.item_price_usd AS DECIMAL(12,2)), CAST(l.shipping_cost_usd AS DECIMAL(12,2)), CAST(l.item_total_usd AS DECIMAL(12,2))
FROM ods.order_items l JOIN dwd.fact_order f USING (order_id) WHERE l._batch_id = $batch_id;

-- name: fact_payment
INSERT INTO dwd.fact_payment
SELECT order_id, CAST(payment_sequential AS BIGINT), payment_type, CAST(payment_installments AS BIGINT), CAST(payment_value_usd AS DECIMAL(12,2))
FROM ods.payments WHERE _batch_id = $batch_id;

-- name: fact_fulfillment
INSERT INTO dwd.fact_fulfillment
SELECT s.order_id, s.shipping_distance_band, s.shipping_zone, CAST(CAST(s.estimated_delivery_days AS DOUBLE) AS BIGINT),
       CAST(s.shipping_cost_usd AS DECIMAL(12,2)),
       CAST(floor(epoch(f.delivered_ts - f.purchase_ts) / 86400) AS INTEGER)
FROM ods.shipping s JOIN dwd.fact_order f USING (order_id) WHERE s._batch_id = $batch_id;

-- name: audit_counts
SELECT 'dim_date' t, count(*) n FROM dwd.dim_date UNION ALL SELECT 'dim_geo', count(*) FROM dwd.dim_geo
UNION ALL SELECT 'dim_customer', count(*) FROM dwd.dim_customer UNION ALL SELECT 'dim_product', count(*) FROM dwd.dim_product
UNION ALL SELECT 'dim_seller', count(*) FROM dwd.dim_seller UNION ALL SELECT 'fact_order', count(*) FROM dwd.fact_order
UNION ALL SELECT 'fact_order_line', count(*) FROM dwd.fact_order_line UNION ALL SELECT 'fact_payment', count(*) FROM dwd.fact_payment
UNION ALL SELECT 'fact_fulfillment', count(*) FROM dwd.fact_fulfillment;

-- name: audit_cast_checks
SELECT
  (SELECT count(*) FROM ods.orders WHERE _batch_id = $batch_id AND order_estimated_delivery_date NOT LIKE '%T00:00:00') AS est_date_with_time,
  (SELECT count(*) FROM ods.calendar WHERE _batch_id = $batch_id AND "date" NOT LIKE '%T00:00:00') AS calendar_with_time,
  (SELECT count(*) FROM ods.shipping WHERE _batch_id = $batch_id AND estimated_delivery_days <> ''
          AND CAST(estimated_delivery_days AS DOUBLE) <> floor(CAST(estimated_delivery_days AS DOUBLE))) AS non_integer_days,
  (SELECT count(*) FROM ods.order_items WHERE _batch_id = $batch_id
          AND (item_price_usd LIKE '%.___%' OR shipping_cost_usd LIKE '%.___%' OR item_total_usd LIKE '%.___%')) AS money_over_2dp,
  (SELECT count(*) FROM (SELECT state FROM dwd.dim_geo GROUP BY state HAVING count(DISTINCT region) > 1)) AS state_in_two_regions,
  (SELECT count(*) FROM dwd.fact_order_line l JOIN ods.order_items o ON o.order_id = l.order_id
          AND CAST(o.order_item_id AS BIGINT) = l.order_item_seq AND o._batch_id = $batch_id
          WHERE o.product_id <> l.product_id) AS line_mismatch;

-- name: audit_semantics
SELECT
  (SELECT count(*) FROM dwd.fact_order WHERE approved_ts IS NULL) AS no_approval,
  (SELECT count(*) FROM dwd.fact_order WHERE order_status = 'cancelled') AS status_cancelled,
  (SELECT count(*) FROM dwd.fact_order WHERE approved_ts >= TIMESTAMPTZ '2026-11-08 00:00:00+00') AS approved_after_cutoff,
  (SELECT count(*) FROM dwd.fact_order WHERE approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00') AS valid_at_cutoff,
  (SELECT count(*) FROM dwd.fact_order WHERE customer_id IS NULL) AS anonymous_orders,
  (SELECT sum(merch_usd)::VARCHAR FROM dwd.fact_order) AS merch_all,
  (SELECT sum(merch_usd)::VARCHAR FROM dwd.fact_order WHERE approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00') AS merch_valid_at_cutoff,
  (SELECT sum(item_price_usd)::VARCHAR FROM dwd.fact_order_line) AS merch_lines,
  (SELECT count(*) FROM dwd.fact_order WHERE payment_value_usd <> order_value_usd) AS payment_mismatch,
  (SELECT count(*) FROM dwd.fact_order WHERE late_by_date) AS late_by_date,
  (SELECT count(*) FROM dwd.fact_order WHERE late_by_days) AS late_by_days;
