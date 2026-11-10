-- ADS semantic views (DW-06). Views only; no data copied. As-of for all views = data cutoff
-- 2026-11-08T00:00:00Z (exclusive): valid purchase = approved_ts < cutoff (transaction-rules-v1).
-- Money is USD merchandise amount (shipping separate); data are fully synthetic.
-- The AI query layer may read only the views registered in meta.allowed_view.

-- name: views
CREATE OR REPLACE VIEW ads.params AS
SELECT TIMESTAMPTZ '2026-11-08 00:00:00+00' AS as_of, 'transaction-rules-v1' AS rule_version, 'USD' AS currency, TRUE AS synthetic;

CREATE OR REPLACE VIEW ads.kpi_daily AS
SELECT d.calendar_date AS day, sum(r.valid_orders) AS valid_orders, sum(r.merch_usd) AS merchandise_sales_usd,
       sum(r.shipping_usd) AS shipping_usd, sum(r.buyers) AS buyers,            -- one region per customer, so summing regions within a day is exact
       sum(r.merch_usd) / nullif(sum(r.valid_orders), 0) AS aov_usd
FROM dws.orders_daily_region r JOIN dwd.dim_date d ON d.date_key = r.date_key GROUP BY 1;

CREATE OR REPLACE VIEW ads.kpi_monthly AS
WITH o AS (SELECT strftime(CAST(purchase_ts AS DATE), '%Y-%m') AS month, * FROM dwd.fact_order),
v AS (SELECT month, count(*) AS valid_orders, sum(merch_usd) AS merchandise_sales_usd, sum(shipping_usd) AS shipping_usd,
             count(DISTINCT customer_id) AS buyers FROM o, ads.params p WHERE approved_ts < p.as_of GROUP BY 1),
c AS (SELECT month, count(*) AS cancelled_orders, sum(merch_usd) AS cancelled_merchandise_usd FROM o WHERE approved_ts IS NULL GROUP BY 1)
SELECT v.month, v.valid_orders, v.merchandise_sales_usd, v.shipping_usd, v.buyers,
       v.merchandise_sales_usd / nullif(v.valid_orders, 0) AS aov_usd,
       coalesce(c.cancelled_orders, 0) AS cancelled_orders, coalesce(c.cancelled_merchandise_usd, 0) AS cancelled_merchandise_usd,
       v.month = '2026-11' AS partial_period
FROM v LEFT JOIN c USING (month);

CREATE OR REPLACE VIEW ads.sales_month_category_region AS
SELECT strftime(CAST(o.purchase_ts AS DATE), '%Y-%m') AS month, p.product_category, c.customer_region,
       count(*) AS valid_lines, sum(l.item_price_usd) AS merchandise_sales_usd, count(DISTINCT l.order_id) AS orders_containing
FROM dwd.fact_order_line l JOIN dwd.fact_order o USING (order_id) JOIN dwd.dim_product p USING (product_id)
JOIN dwd.dim_customer c ON c.customer_id = l.customer_id, ads.params pr
WHERE o.approved_ts < pr.as_of GROUP BY ALL;

CREATE OR REPLACE VIEW ads.cohort_retention AS
WITH v AS (SELECT o.customer_id, date_trunc('month', CAST(o.purchase_ts AS DATE)) AS m FROM dwd.fact_order o, ads.params p WHERE o.approved_ts < p.as_of),
f AS (SELECT customer_id, min(m) AS cohort FROM v GROUP BY 1),
a AS (SELECT DISTINCT f.cohort, v.customer_id, datediff('month', f.cohort, v.m) AS k FROM v JOIN f USING (customer_id)),
size AS (SELECT cohort, count(*) AS cohort_customers FROM f GROUP BY 1),
grid AS (SELECT s.cohort, s.cohort_customers, k.k FROM size s, range(0, 36) k(k)
         WHERE s.cohort + to_months(CAST(k.k AS INTEGER)) <= DATE '2026-11-01')
SELECT strftime(g.cohort, '%Y-%m') AS cohort_month, g.k AS months_since_first, g.cohort_customers,
       CASE WHEN g.cohort + to_months(CAST(g.k AS INTEGER)) < DATE '2026-11-01' THEN count(a.customer_id) END AS active_customers,
       CASE WHEN g.cohort + to_months(CAST(g.k AS INTEGER)) < DATE '2026-11-01'
            THEN count(a.customer_id) / g.cohort_customers END AS retention_rate,
       g.cohort + to_months(CAST(g.k AS INTEGER)) >= DATE '2026-11-01' AS immature
FROM grid g LEFT JOIN a ON a.cohort = g.cohort AND a.k = g.k GROUP BY g.cohort, g.k, g.cohort_customers;

CREATE OR REPLACE VIEW ads.lifecycle_mix_weekly AS
SELECT as_of::DATE AS as_of_date, lifecycle_state, count(*) AS customers, 'lifecycle-default-v0' AS rule_version
FROM dws.customer_snapshot WHERE snapshot_version = 'snapshot-v1' GROUP BY ALL;

CREATE OR REPLACE VIEW ads.customer_profile_latest AS
SELECT s.customer_id, s.as_of::DATE AS as_of_date, c.customer_state, c.customer_region, s.recency_days, s.frequency_90d,
       s.monetary_90d_usd, s.orders_all_time, s.merch_all_time_usd, s.first_purchase_ts::DATE AS first_purchase_date,
       s.tenure_days, s.lifecycle_state, s.frequency_90d >= 1 AS in_repurchase_population
FROM dws.customer_snapshot s JOIN dwd.dim_customer c USING (customer_id)
WHERE s.snapshot_version = 'snapshot-v1' AND s.as_of = (SELECT max(as_of) FROM dws.customer_snapshot WHERE snapshot_version = 'snapshot-v1');

CREATE OR REPLACE VIEW ads.repurchase_rate_weekly AS
SELECT l.as_of::DATE AS as_of_date, count(*) AS population, sum(l.y::INT) AS repurchasers, avg(l.y::INT) AS repurchase_rate_30d,
       1 - avg(l.y::INT) AS non_repurchase_rate_30d
FROM dws.label_repurchase l JOIN dws.customer_snapshot s USING (customer_id, as_of)
WHERE l.label_version = 'label-repurchase-v1' AND s.snapshot_version = 'snapshot-v1' AND s.frequency_90d >= 1 AND l.horizon_days = 30
GROUP BY 1;

-- name: allowed
DELETE FROM meta.allowed_view;
INSERT INTO meta.allowed_view VALUES
 ('ads.kpi_daily', '经营总览：日有效订单、商品金额、运费、购买客户、客单价'),
 ('ads.kpi_monthly', '经营总览：月度指标（去重客户按月重算）与取消；2026-11 为不完整月'),
 ('ads.sales_month_category_region', '月×品类×客户大区：明细数、商品金额（可加）；含该品类订单数（不可跨品类相加）'),
 ('ads.cohort_retention', '首次可观测购买月 cohort 留存；未成熟格子为空'),
 ('ads.lifecycle_mix_weekly', '按周的规则生命周期分布（默认阈值）'),
 ('ads.repurchase_rate_weekly', '按周的 30 天经验复购率（90 天母体，已成熟标签）');

-- name: list
SELECT view_name, purpose FROM meta.allowed_view ORDER BY 1;
