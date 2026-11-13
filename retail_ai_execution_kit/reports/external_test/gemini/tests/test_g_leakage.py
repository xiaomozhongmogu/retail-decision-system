"""Group G adversarial test: Report window cutoffs, feature/label leakage, split isolation, and release alignment.

Reads parquet artifacts and DuckDB warehouse releases in read-only mode.
Run from retail_ai_execution_kit/:
    .venv/bin/python reports/external_test/gemini/tests/test_g_leakage.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src/retail_bi/ai"))
sys.path.insert(0, str(ROOT / "src/retail_bi/warehouse"))
sys.path.insert(0, str(ROOT / "src/retail_bi/model"))
sys.path.insert(0, str(ROOT / "src/retail_bi/features"))

import baselines  # noqa: E402
import customer_features  # noqa: E402
import report_facts as RF  # noqa: E402
import scoring  # noqa: E402
import split  # noqa: E402


def by_metric(facts_res: dict) -> dict[str, dict]:
    return {x["metric"]: x for x in facts_res["data"]["facts"] if "metric" in x}


def main() -> int:
    results = []

    def check(cid: str, cond: bool, detail: dict) -> None:
        results.append({"id": cid, "passed": bool(cond), "detail": detail})

    wh_curr = ROOT / "warehouse/releases/wh-d3aaa559048c.duckdb"
    wh_prev = ROOT / "warehouse/releases/wh-db316daf8021.duckdb"
    feat_path = ROOT / "data/processed/model/features-wh-db316daf8021-target-v1-features-v1.parquet"
    samp_path = ROOT / "data/processed/model/samples-wh-db316daf8021-target-v1.parquet"

    con = duckdb.connect(str(wh_curr), read_only=True)
    try:
        # G01: Weekly report_facts vs independent dwd.fact_order SQL + open tail exclusion
        facts = RF.build_weekly_facts()
        m = by_metric(facts)
        rw = facts["window"]  # {'start': '2026-10-31', 'end': '2026-11-07', 'closed': 'left'}
        dwd_rw = con.execute(
            """
            SELECT COUNT(*) AS valid_orders,
                   ROUND(SUM(merch_usd), 2) AS sales_usd,
                   ROUND(SUM(shipping_usd), 2) AS shipping_usd,
                   COUNT(DISTINCT customer_id) AS buyers
            FROM dwd.fact_order
            WHERE order_status <> 'cancelled'
              AND approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'
              AND (purchase_ts AT TIME ZONE 'UTC')::DATE >= CAST(? AS DATE)
              AND (purchase_ts AT TIME ZONE 'UTC')::DATE < CAST(? AS DATE)
            """,
            [rw["start"], rw["end"]],
        ).fetchone()
        dwd_tail = con.execute(
            """
            SELECT COUNT(*) FILTER (WHERE approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00') AS approved_before_cutoff,
                   COALESCE(ROUND(SUM(merch_usd) FILTER (WHERE approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'), 2), 0.0) AS approved_sales,
                   COUNT(*) AS all_placed_on_tail_day
            FROM dwd.fact_order
            WHERE order_status <> 'cancelled'
              AND (purchase_ts AT TIME ZONE 'UTC')::DATE = DATE '2026-11-07'
            """
        ).fetchone()
        after_cutoff = con.execute(
            "SELECT COUNT(*) FROM dwd.fact_order WHERE (purchase_ts AT TIME ZONE 'UTC')::DATE >= DATE '2026-11-08'"
        ).fetchone()[0]
        rw_f = m["report_week.sales"]["value"]
        rw_o = m["report_week.orders"]["value"]
        rw_aov = m["report_week.aov"]["value"]
        tail_o = m["open_tail.orders"]["value"]
        check(
            "G01_weekly_facts_vs_dwd",
            (rw["start"] == "2026-10-31" and rw["end"] == "2026-11-07"
             and int(dwd_rw[0]) == int(rw_o)
             and abs(float(dwd_rw[1]) - float(rw_f)) < 1e-6
             and abs((float(dwd_rw[1]) / int(dwd_rw[0])) - float(rw_aov)) < 0.02
             and int(dwd_tail[0]) == int(tail_o)
             and after_cutoff == 0),
            {
                "window": rw,
                "dwd_rw": {"orders": int(dwd_rw[0]), "sales": float(dwd_rw[1]), "shipping": float(dwd_rw[2])},
                "facts_rw": {"orders": rw_o, "sales": rw_f, "aov": rw_aov, "open_tail_orders": tail_o},
                "open_tail_dwd": {"day": "2026-11-07", "approved_before_cutoff_orders": int(dwd_tail[0]), "sales": float(dwd_tail[1]), "all_placed_utc": int(dwd_tail[2])},
                "after_cutoff_2026_11_08_rows": int(after_cutoff),
            },
        )

        # G02: Historical as_of time-travel leakage in report_facts.compute(..., as_of=2025-06-01)
        def fetch_dicts(sql_q: str) -> list[dict]:
            cur = con.execute(sql_q)
            cols = [d[0] for d in cur.description]
            rows_out = []
            for row in cur.fetchall():
                rows_out.append({c: (v.isoformat() if hasattr(v, "isoformat") else v) for c, v in zip(cols, row)})
            return rows_out

        daily = fetch_dicts("SELECT day, valid_orders, merchandise_sales_usd, shipping_usd, buyers, aov_usd FROM ads.kpi_daily ORDER BY day")
        monthly = fetch_dicts("SELECT month, valid_orders, merchandise_sales_usd, shipping_usd, buyers, aov_usd, cancelled_orders, cancelled_merchandise_usd, partial_period FROM ads.kpi_monthly ORDER BY month")
        catreg = fetch_dicts("SELECT month, product_category, customer_region, valid_lines, merchandise_sales_usd, orders_containing FROM ads.sales_month_category_region")
        lifecycle = fetch_dicts("SELECT as_of_date, lifecycle_state, customers, rule_version FROM ads.lifecycle_mix_weekly ORDER BY as_of_date, lifecycle_state")
        repurchase = fetch_dicts("SELECT as_of_date, population, repurchasers, repurchase_rate_30d, non_repurchase_rate_30d FROM ads.repurchase_rate_weekly ORDER BY as_of_date")

        hist_as_of = date(2025, 6, 1)
        hist_facts = RF.compute(daily, monthly, catreg, lifecycle, repurchase, as_of=hist_as_of)
        hm = {x["metric"]: x for x in hist_facts["facts"] if "metric" in x}
        rep_win_start = hm["repurchase_rate_30d.latest_matured"]["window"]["start"]
        life_win_start = hm["lifecycle_mix"]["window"]["start"]
        rw_hist_start = hm["report_week.orders"]["window"]["start"]
        default_rep_end = m["repurchase_rate_30d.latest_matured"]["window"]["end"]
        check(
            "G02_report_facts_compute_as_of_leakage",
            (date.fromisoformat(rep_win_start) <= hist_as_of)
            and (date.fromisoformat(life_win_start) <= hist_as_of)
            and (date.fromisoformat(default_rep_end) <= date(2026, 11, 8)),
            {
                "requested_as_of": str(hist_as_of),
                "report_window_start": rw_hist_start,
                "report_month_window_returned": hm["report_month.sales"]["window"],
                "repurchase_window_returned": hm["repurchase_rate_30d.latest_matured"]["window"],
                "repurchase_value_returned": hm["repurchase_rate_30d.latest_matured"]["value"],
                "lifecycle_window_returned": hm["lifecycle_mix"]["window"],
                "default_repurchase_window": m["repurchase_rate_30d.latest_matured"]["window"],
                "max_repurchase_in_ads": str(max(r["as_of_date"] for r in repurchase)),
            },
        )

        # G03 & G04: Independent DWD SQL audit of ALL 92,241 feature/sample parquet rows
        con_prev = duckdb.connect(str(wh_prev), read_only=True)
        try:
            diff_dwd_cnt = con_prev.execute("SELECT COUNT(*) FROM dwd.fact_order").fetchone()[0]
            curr_dwd_cnt = con.execute("SELECT COUNT(*) FROM dwd.fact_order").fetchone()[0]
        finally:
            con_prev.close()

        feat_audit_con = duckdb.connect(str(wh_prev), read_only=True)
        try:
            audit_stats = feat_audit_con.execute(
                f"""
                WITH f AS (
                    SELECT *,
                           as_of::TIMESTAMPTZ AS as_of_ts,
                           as_of::DATE AS as_of_date
                    FROM read_parquet('{feat_path.as_posix()}')
                ),
                s AS (
                    SELECT customer_id, as_of, label_matured_at
                    FROM read_parquet('{samp_path.as_posix()}')
                ),
                lbl AS (
                    SELECT f.customer_id, f.as_of,
                           f.y AS feat_y,
                           MAX(CASE
                               WHEN o.order_status <> 'cancelled'
                                AND o.purchase_ts >= f.as_of_ts
                                AND o.purchase_ts < f.as_of_ts + INTERVAL '30 days'
                               THEN 1 ELSE 0 END) AS dwd_y_excl_cancel,
                           MAX(CASE
                               WHEN o.purchase_ts >= f.as_of_ts
                                AND o.purchase_ts < f.as_of_ts + INTERVAL '30 days'
                               THEN 1 ELSE 0 END) AS dwd_y_incl_cancel
                    FROM f
                    LEFT JOIN dwd.fact_order o
                      ON o.customer_id = f.customer_id
                     AND o.purchase_ts >= f.as_of_ts
                     AND o.purchase_ts < f.as_of_ts + INTERVAL '30 days'
                    GROUP BY f.customer_id, f.as_of, f.y
                ),
                hist_feats AS (
                    SELECT f.customer_id, f.as_of,
                           f.orders_all_time, f.orders_30d, f.merch_30d,
                           f.delivered_count, f.late_by_date_share, f.last_review_score, f.has_review,
                           SUM(CASE WHEN o.purchase_ts < f.as_of_ts AND (o.approved_ts IS NOT NULL AND o.approved_ts < f.as_of_ts) THEN 1 ELSE 0 END) AS recomputed_orders_all,
                           SUM(CASE WHEN o.purchase_ts < f.as_of_ts AND o.order_status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_prior_orders,
                           SUM(CASE WHEN o.purchase_ts < f.as_of_ts AND o.delivered_ts IS NOT NULL AND o.delivered_ts < f.as_of_ts THEN 1 ELSE 0 END) AS recomputed_delivered
                    FROM f
                    LEFT JOIN dwd.fact_order o
                      ON o.customer_id = f.customer_id
                    GROUP BY 1,2,3,4,5,6,7,8,9
                ),
                cust_birth AS (
                    SELECT COUNT(*) AS pre_birth_rows
                    FROM f
                    JOIN dwd.dim_customer c ON c.customer_id = f.customer_id
                    WHERE c.customer_created_date > f.as_of_date
                ),
                maturity AS (
                    SELECT COUNT(*) FILTER (WHERE label_matured_at::TIMESTAMPTZ > (SELECT MAX(purchase_ts) FROM dwd.fact_order)) AS immature_rows,
                           MAX(label_matured_at::TIMESTAMPTZ)::VARCHAR AS max_matured_at,
                           (SELECT MAX(purchase_ts) FROM dwd.fact_order)::VARCHAR AS max_order_ts
                    FROM s
                )
                SELECT
                    (SELECT COUNT(*) FROM lbl) AS total_rows,
                    (SELECT SUM(CASE WHEN feat_y <> dwd_y_excl_cancel THEN 1 ELSE 0 END) FROM lbl) AS y_mismatch_excl_cancel,
                    (SELECT SUM(CASE WHEN feat_y <> dwd_y_incl_cancel THEN 1 ELSE 0 END) FROM lbl) AS y_mismatch_incl_cancel,
                    (SELECT SUM(CASE WHEN orders_all_time <> recomputed_orders_all THEN 1 ELSE 0 END) FROM hist_feats) AS orders_all_mismatch,
                    (SELECT SUM(CASE WHEN delivered_count <> recomputed_delivered THEN 1 ELSE 0 END) FROM hist_feats) AS delivered_mismatch,
                    (SELECT SUM(cancelled_prior_orders) FROM hist_feats) AS total_prior_cancelled_orders,
                    (SELECT pre_birth_rows FROM cust_birth) AS pre_birth_rows,
                    (SELECT immature_rows FROM maturity) AS immature_rows,
                    (SELECT max_matured_at FROM maturity) AS max_matured_at,
                    (SELECT max_order_ts FROM maturity) AS max_order_ts
                """
            ).fetchone()
            review_boundary = feat_audit_con.execute(
                f"""
                WITH f AS (
                    SELECT customer_id, as_of, as_of::TIMESTAMPTZ AS as_of_ts, as_of::DATE AS as_of_date,
                           orders_all_time, has_review, last_review_score, delivered_count
                    FROM read_parquet('{feat_path.as_posix()}')
                ),
                r_hist AS (
                    SELECT f.customer_id, f.as_of_ts, f.has_review,
                           COUNT(o.order_id) FILTER (WHERE o.purchase_ts < f.as_of_ts AND o.approved_ts < f.as_of_ts AND o.review_created_date < f.as_of_date AND o.review_score IS NOT NULL) AS cnt_strict_before,
                           COUNT(o.order_id) FILTER (WHERE o.purchase_ts < f.as_of_ts AND o.approved_ts < f.as_of_ts AND o.review_created_date <= f.as_of_date AND o.review_score IS NOT NULL) AS cnt_le_as_of_date,
                           COUNT(o.order_id) FILTER (WHERE o.order_status = 'cancelled' AND o.purchase_ts < f.as_of_ts AND o.approved_ts IS NULL) AS cancelled_no_approval,
                           COUNT(o.order_id) FILTER (WHERE o.order_status = 'cancelled' AND o.purchase_ts < f.as_of_ts AND o.approved_ts IS NOT NULL AND o.approved_ts < f.as_of_ts) AS cancelled_but_approved_prior
                    FROM f
                    JOIN dwd.fact_order o ON o.customer_id = f.customer_id
                    GROUP BY 1,2,3
                )
                SELECT
                    COUNT(*) FILTER (WHERE has_review = 1 AND cnt_le_as_of_date = 0) AS future_rev_leaked,
                    COUNT(*) FILTER (WHERE has_review = 1 AND cnt_strict_before = 0 AND cnt_le_as_of_date > 0) AS same_day_rev_included,
                    COALESCE(SUM(cancelled_no_approval), 0) AS cancelled_no_approval,
                    COALESCE(SUM(cancelled_but_approved_prior), 0) AS cancelled_but_approved_prior
                FROM r_hist
                """
            ).fetchone()
            cancel_leak = feat_audit_con.execute(
                f"""
                WITH f AS (
                    SELECT customer_id, as_of, as_of::TIMESTAMPTZ AS as_of_ts, orders_all_time
                    FROM read_parquet('{feat_path.as_posix()}')
                ),
                c_cust AS (
                    SELECT DISTINCT f.customer_id, f.as_of, f.as_of_ts, f.orders_all_time
                    FROM f
                    JOIN dwd.fact_order o ON o.customer_id = f.customer_id
                    WHERE o.order_status = 'cancelled' AND o.purchase_ts < f.as_of_ts
                )
                SELECT c.customer_id, c.as_of::VARCHAR, c.orders_all_time,
                       COUNT(o.order_id) FILTER (WHERE o.purchase_ts < c.as_of_ts AND o.approved_ts < c.as_of_ts) AS cnt_all_approved,
                       COUNT(o.order_id) FILTER (WHERE o.purchase_ts < c.as_of_ts AND o.order_status <> 'cancelled') AS cnt_excl_cancelled
                FROM c_cust c
                JOIN dwd.fact_order o ON o.customer_id = c.customer_id
                GROUP BY 1,2,3
                LIMIT 10
                """
            ).fetchall()
        finally:
            feat_audit_con.close()

        keys = [
            "total_rows", "y_mismatch_excl_cancel", "y_mismatch_incl_cancel",
            "orders_all_mismatch", "delivered_mismatch", "total_prior_cancelled_orders",
            "pre_birth_rows", "immature_rows", "max_matured_at", "max_order_ts",
        ]
        audit_dict = dict(zip(keys, audit_stats))
        check(
            "G03_sample_y_and_maturity_vs_dwd",
            (audit_dict["y_mismatch_excl_cancel"] == 0 or audit_dict["y_mismatch_incl_cancel"] == 0)
            and audit_dict["immature_rows"] == 0
            and audit_dict["pre_birth_rows"] == 0,
            {
                "wh_curr_dwd_orders": int(curr_dwd_cnt),
                "wh_prev_dwd_orders": int(diff_dwd_cnt),
                "audit": {k: (int(v) if isinstance(v, int) else str(v)) for k, v in audit_dict.items()},
                "cancel_sample_rows": [(r[0], r[1], int(r[2]), int(r[3]), int(r[4])) for r in cancel_leak[:5]],
            },
        )
        check(
            "G04_feature_time_truncation_vs_dwd",
            audit_dict["orders_all_mismatch"] == 0
            and audit_dict["delivered_mismatch"] == 0
            and int(review_boundary[0]) == 0,
            {
                "orders_all_mismatch": int(audit_dict["orders_all_mismatch"]),
                "delivered_mismatch": int(audit_dict["delivered_mismatch"]),
                "review_boundary": {
                    "future_rev_leaked": int(review_boundary[0]),
                    "same_day_rev_included": int(review_boundary[1]),
                    "cancelled_no_approval": int(review_boundary[2]),
                    "cancelled_approved_prior": int(review_boundary[3]),
                },
            },
        )

        # G05: Split order, 5-week embargo, customer overlap audit
        df = pd.read_parquet(feat_path)
        df["set"] = split.assign(df["as_of"])
        df["_ts"] = pd.to_datetime(df["as_of"], utc=True)
        ord_checks = split.check_order()
        tr = df[df["set"] == "train"]
        va = df[df["set"] == "validation"]
        te = df[df["set"] == "test"]
        gap_tv = (va["_ts"].min() - tr["_ts"].max()).days
        gap_vt = (te["_ts"].min() - va["_ts"].max()).days
        overlap_tr_te = len(set(tr["customer_id"]) & set(te["customer_id"])) / len(set(te["customer_id"]))
        check(
            "G05_split_embargo_and_overlap",
            all(v["ok"] for v in ord_checks.values()) and gap_tv == 35 and gap_vt == 35
            and len(set(tr["as_of"]) & set(va["as_of"])) == 0
            and len(set(va["as_of"]) & set(te["as_of"])) == 0,
            {
                "order_checks": ord_checks,
                "gap_train_val_days": int(gap_tv),
                "gap_val_test_days": int(gap_vt),
                "test_customers_seen_in_train_share": round(overlap_tr_te, 4),
                "rows": {"train": len(tr), "val": len(va), "test": len(te), "embargo": int((df["set"] == "embargo").sum())},
            },
        )

        # G06: Does baselines.Prep.fit reject validation/test feature rows at runtime?
        prep = baselines.Prep()
        prep_rejected_val = False
        prep_err = None
        try:
            prep.fit(va[customer_features.FEATURES].head(200))
        except Exception as exc:
            prep_rejected_val = True
            prep_err = f"{type(exc).__name__}: {exc}"
        check(
            "G06_prep_fit_rejects_non_train_rows",
            prep_rejected_val,
            {"rejected_val_rows": prep_rejected_val, "error": prep_err, "fitted_medians_count": len(getattr(prep, "medians", {}))},
        )

        # G07: Release alignment (wh-db316daf8021 features vs wh-d3aaa559048c ads.model_scores & scoring API)
        ms_counts = con.execute(
            """
            SELECT applicability,
                   COUNT(*),
                   COUNT(p_repurchase_30d),
                   MAX(ABS(p_repurchase_30d + p_non_repurchase_30d - 1.0))
            FROM ads.model_scores
            GROUP BY 1
            """
        ).fetchall()
        in_pop_row = con.execute(
            "SELECT customer_id, as_of::DATE::VARCHAR, p_repurchase_30d FROM ads.model_scores WHERE applicability='in_population' ORDER BY customer_id LIMIT 1"
        ).fetchone()
        out_pop_row = con.execute(
            "SELECT customer_id, as_of::DATE::VARCHAR, p_repurchase_30d FROM ads.model_scores WHERE applicability<>'in_population' ORDER BY customer_id LIMIT 1"
        ).fetchone()
        live_in = scoring.get_risk_score(in_pop_row[0], in_pop_row[1])
        live_out = scoring.get_risk_score(out_pop_row[0], out_pop_row[1])
        check(
            "G07_scoring_and_ads_model_scores_alignment",
            abs(float(live_in["data"]["p_repurchase_30d"]) - float(in_pop_row[2])) < 1e-9
            and live_out["data"].get("p_repurchase_30d") is None,
            {
                "ads_model_scores_summary": [(r[0], int(r[1]), int(r[2]), r[3]) for r in ms_counts],
                "in_pop_ads_p": float(in_pop_row[2]),
                "in_pop_scoring_p": float(live_in["data"]["p_repurchase_30d"]),
                "out_pop_ads_p": out_pop_row[2],
                "out_pop_scoring": live_out,
            },
        )
    finally:
        con.close()

    print(json.dumps({
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failures": [r for r in results if not r["passed"]],
        "all_results": results,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
