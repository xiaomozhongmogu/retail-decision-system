-- Point-in-time customer snapshot and separate labels (DW-05). Run by src/retail_bi/features/snapshot.py.
-- One row = customer x as_of. Only orders with purchase_ts < as_of AND approved_ts < as_of are used
-- (an order is a valid purchase once approved, transaction-rules-v1). Final order_status, delivery outcomes,
-- generator labels and anything at or after as_of are never read here.
-- Parameters: $first_as_of, $cutoff (data cutoff, exclusive), $step_days, $horizon, $maturity_days,
--             $snapshot_version, $label_version.

-- name: as_of_grid
CREATE OR REPLACE TEMP TABLE as_of_grid AS
SELECT CAST(t AS TIMESTAMP)::TIMESTAMPTZ AS as_of
FROM range(CAST($first_as_of AS TIMESTAMP), CAST($cutoff AS TIMESTAMP) + INTERVAL 1 SECOND, to_days(CAST($step_days AS INTEGER))) r(t);

-- name: snapshot
DELETE FROM dws.customer_snapshot WHERE snapshot_version = $snapshot_version;
INSERT INTO dws.customer_snapshot
WITH seen AS (                       -- purchases visible at each as_of
    SELECT g.as_of, o.customer_id, o.purchase_ts, o.merch_usd
    FROM as_of_grid g JOIN dwd.fact_order o ON o.purchase_ts < g.as_of AND o.approved_ts < g.as_of)
SELECT customer_id, as_of, as_of - INTERVAL 90 DAY,
       epoch(as_of - max(purchase_ts)) / 86400.0,
       count(*) FILTER (WHERE purchase_ts >= as_of - INTERVAL 90 DAY),
       coalesce(sum(merch_usd) FILTER (WHERE purchase_ts >= as_of - INTERVAL 90 DAY), 0),
       count(*), sum(merch_usd), min(purchase_ts),
       epoch(as_of - min(purchase_ts)) / 86400.0,
       CASE WHEN min(purchase_ts) >= as_of - INTERVAL 30 DAY THEN 'new'
            WHEN max(purchase_ts) >= as_of - INTERVAL 90 DAY THEN 'active'
            WHEN max(purchase_ts) >= as_of - INTERVAL 180 DAY THEN 'at_risk'
            ELSE 'dormant' END,
       $snapshot_version
FROM seen GROUP BY customer_id, as_of;

-- name: labels
DELETE FROM dws.label_repurchase WHERE label_version = $label_version AND horizon_days = CAST($horizon AS INTEGER);
INSERT INTO dws.label_repurchase
SELECT s.customer_id, s.as_of, CAST($horizon AS INTEGER),
       EXISTS (SELECT 1 FROM dwd.fact_order o
               WHERE o.customer_id = s.customer_id
                 AND o.purchase_ts >= s.as_of AND o.purchase_ts < s.as_of + to_days(CAST($horizon AS INTEGER))
                 AND o.approved_ts < s.as_of + to_days(CAST($horizon AS INTEGER) + CAST($maturity_days AS INTEGER))),
       s.as_of + to_days(CAST($horizon AS INTEGER) + CAST($maturity_days AS INTEGER)),
       $label_version
FROM dws.customer_snapshot s
WHERE s.snapshot_version = $snapshot_version
  AND s.as_of + to_days(CAST($horizon AS INTEGER) + CAST($maturity_days AS INTEGER)) <= CAST($cutoff AS TIMESTAMPTZ);

-- name: coverage
SELECT count(DISTINCT as_of) AS as_of_points, min(as_of)::VARCHAR AS first_as_of, max(as_of)::VARCHAR AS last_as_of,
       count(*) AS rows, count(DISTINCT customer_id) AS customers,
       count(*) FILTER (WHERE frequency_90d >= 1) AS rows_in_90d_population
FROM dws.customer_snapshot WHERE snapshot_version = $snapshot_version;

-- name: label_coverage
SELECT count(DISTINCT l.as_of), min(l.as_of)::VARCHAR, max(l.as_of)::VARCHAR, count(*), sum(l.y::INT),
       count(*) FILTER (WHERE s.frequency_90d >= 1), sum(l.y::INT) FILTER (WHERE s.frequency_90d >= 1)
FROM dws.label_repurchase l JOIN dws.customer_snapshot s USING (customer_id, as_of)
WHERE l.label_version = $label_version AND s.snapshot_version = $snapshot_version;

-- name: lifecycle_mix
SELECT lifecycle_state, count(*) FROM dws.customer_snapshot WHERE snapshot_version = $snapshot_version GROUP BY 1 ORDER BY 1;
