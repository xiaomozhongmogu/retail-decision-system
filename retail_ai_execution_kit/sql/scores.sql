-- Model scores in ADS (ML-11). Written offline by src/retail_bi/model/scoring.py into a warehouse build,
-- then published read-only with the release. Customer-level scores are NOT in meta.allowed_view (not for the AI query layer);
-- only the aggregate view ads.risk_summary_latest is registered.

-- name: ddl
CREATE TABLE IF NOT EXISTS ads.model_scores (
    customer_id VARCHAR NOT NULL,
    as_of TIMESTAMPTZ NOT NULL,
    model_version VARCHAR NOT NULL,
    applicability VARCHAR NOT NULL,          -- in_population | out_of_population
    p_repurchase_30d DOUBLE,                 -- NULL when out_of_population
    p_non_repurchase_30d DOUBLE,             -- 1 - p_repurchase_30d
    ranking_score DOUBLE,                    -- frozen weekly-list policy (90-day order frequency), ML-08
    top_factors VARCHAR,                     -- model explanation, not causal
    PRIMARY KEY (customer_id, as_of, model_version)
);

-- name: summary_view
CREATE OR REPLACE VIEW ads.risk_summary_latest AS
SELECT s.as_of::DATE AS as_of_date, s.model_version, count(*) AS customers_scored,
       avg(s.p_repurchase_30d) AS mean_p_repurchase_30d, avg(s.p_non_repurchase_30d) AS mean_p_non_repurchase_30d,
       count(*) FILTER (WHERE s.applicability = 'out_of_population') AS out_of_population_customers,
       'model ranking within a week is near random on test (ML-09); use for average level only' AS caveat
FROM ads.model_scores s WHERE s.as_of = (SELECT max(as_of) FROM ads.model_scores) GROUP BY 1, 2;

-- name: allow_summary
DELETE FROM meta.allowed_view WHERE view_name = 'ads.risk_summary_latest';
INSERT INTO meta.allowed_view VALUES ('ads.risk_summary_latest', '最新 as_of 的平均复购概率与母体外人数（模型个体排序接近随机，只用于平均水平）');
