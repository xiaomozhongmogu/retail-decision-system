"""Group C adversarial test: SQL executor Layer 1 (validate) & Layer 2 (sandbox) attacks.

Contains 36 new attack vectors distinct from evidence/AI-05/boundary_checks.py.
Run from retail_ai_execution_kit/:
    .venv/bin/python reports/external_test/gemini/tests/test_c_sql_security.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src/retail_bi/ai"))
sys.path.insert(0, str(ROOT / "src/retail_bi/warehouse"))

import sql_executor as X  # noqa: E402
from runtime import pointer  # noqa: E402


def main() -> int:
    rel_file = str(ROOT / "warehouse/releases" / pointer()["file"])
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        export_dir = str(tmp / "exported_db")
        copy_file = str(tmp / "leak.csv")
        json_file = str(ROOT / "warehouse/builds/latest.json")
        parquet_glob = str(ROOT / "data/processed/model/*.parquet")

        # 1. Layer-1 attacks (must be refused by validate / execute without skip_validation)
        l1_attacks = [
            ("C01_case_comment_dwd", "/* benign */ sElEcT * FrOm dWd.fact_order", []),
            ("C02_union_disallowed_view", "SELECT month FROM ads.kpi_monthly UNION ALL SELECT customer_id FROM ads.customer_profile_latest", []),
            ("C03_cte_disallowed_source", "WITH kpi_monthly AS (SELECT customer_id AS month FROM ads.customer_profile_latest) SELECT month FROM kpi_monthly", []),
            ("C04_cte_dwd", "WITH t AS (SELECT * FROM dwd.fact_order) SELECT * FROM t", []),
            ("C05_scalar_subquery_dwd", "SELECT (SELECT count(*) FROM dwd.fact_order) AS n FROM ads.kpi_monthly", []),
            ("C06_export_database", f"EXPORT DATABASE '{export_dir}'", []),
            ("C07_copy_to_file", f"COPY (SELECT * FROM ads.kpi_monthly) TO '{copy_file}'", []),
            ("C08_describe_stmt", "DESCRIBE ads.kpi_monthly", []),
            ("C08b_describe_dwd", "DESCRIBE dwd.fact_order", []),
            ("C09_summarize_stmt", "SUMMARIZE ads.kpi_monthly", []),
            ("C09b_summarize_dwd", "SUMMARIZE dwd.fact_order", []),
            ("C10_explain_stmt", "EXPLAIN SELECT * FROM ads.kpi_monthly", []),
            ("C11_show_tables", "SHOW ALL TABLES", []),
            ("C11b_show_databases", "SHOW DATABASES", []),
            ("C12_call_duckdb_tables", "CALL duckdb_tables()", []),
            ("C13_set_threads", "SET threads = 4", []),
            ("C14_reset_external", "RESET enable_external_access", []),
            ("C15_create_macro", "CREATE MACRO evil(x) AS x", []),
            ("C16_attach_real_wh", f"ATTACH '{rel_file}' AS real_wh (READ_ONLY)", []),
            ("C17_read_csv_auto", "SELECT * FROM read_csv_auto('/etc/passwd')", []),
            ("C18_read_json_auto", f"SELECT * FROM read_json_auto('{json_file}')", []),
            ("C19_parquet_scan", f"SELECT * FROM parquet_scan('{parquet_glob}')", []),
            ("C20_duckdb_secrets", "SELECT * FROM duckdb_secrets()", []),
            ("C21_duckdb_settings", "SELECT * FROM duckdb_settings()", []),
            ("C22_duckdb_views", "SELECT * FROM duckdb_views()", []),
            ("C23_pg_tables", "SELECT * FROM pg_catalog.pg_tables", []),
            ("C24_info_schema_cols", "SELECT * FROM information_schema.columns", []),
            ("C25_query_table_fn", "SELECT * FROM query_table('dwd.fact_order')", []),
            ("C26_sys_funcs", "SELECT version(), current_database(), current_user FROM ads.kpi_monthly", []),
            ("C27_chr_func", "SELECT chr(65) FROM ads.kpi_monthly", []),
            ("C28_unicode_homoglyph_kw", "ＳＥＬＥＣＴ * FROM ads.kpi_monthly", []),
            ("C29_unicode_homoglyph_col", "SELECT mоnth FROM ads.kpi_monthly", []),
            ("C30_oversized_sql", "SELECT month FROM ads.kpi_monthly WHERE month = '" + ("a" * 4000) + "'", []),
            ("C31_values_no_table", "SELECT * FROM (VALUES (1), (2)) AS t(x)", []),
            ("C32_wrong_param_extra", "SELECT month FROM ads.kpi_monthly WHERE month = ?", ["2026-10", "extra"]),
            ("C33_param_injection", "SELECT month FROM ads.kpi_monthly WHERE month = ?", ["2026-10' UNION SELECT * FROM dwd.fact_order --"]),
            ("C34_cartesian_3way", "SELECT count(*) FROM ads.sales_month_category_region a, ads.sales_month_category_region b, ads.sales_month_category_region c", []),
            ("C35_recursive_cte_dos", "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM r WHERE n < 100000000) SELECT count(*) FROM r", []),
            ("C36_trailing_line_comment", "SELECT month FROM ads.kpi_monthly -- trailing comment", []),
        ]

        l1_results = []
        for name, sql, params in l1_attacks:
            r = X.execute(sql, params=params, timeout_s=3.0)
            l1_results.append({
                "id": name,
                "status": r["status"],
                "code": (r.get("error") or {}).get("code"),
                "message": (r.get("error") or {}).get("message"),
                "rows_count": len(r.get("rows") or []),
                "rows_sample": (r.get("rows") or [])[:3],
            })

        # 2. Layer-2 standalone sandbox attacks (skip_validation=True)
        l2_attacks = [
            ("SB01_dwd_fact_order", "SELECT * FROM dwd.fact_order LIMIT 5", []),
            ("SB02_dws_snapshot", "SELECT * FROM dws.customer_snapshot LIMIT 5", []),
            ("SB03_ods_customers", "SELECT * FROM ods.customers LIMIT 5", []),
            ("SB04_meta_load_batch", "SELECT * FROM meta.load_batch", []),
            ("SB05_ads_model_scores", "SELECT * FROM ads.model_scores LIMIT 5", []),
            ("SB06_ads_customer_profile", "SELECT * FROM ads.customer_profile_latest LIMIT 5", []),
            ("SB07_attach_real_wh", f"ATTACH '{rel_file}' AS real_wh (READ_ONLY)", []),
            ("SB08_copy_to_file", f"COPY (SELECT * FROM ads.kpi_monthly) TO '{copy_file}'", []),
            ("SB09_export_db", f"EXPORT DATABASE '{export_dir}'", []),
            ("SB10_set_unlock", "SET enable_external_access = true", []),
            ("SB11_load_httpfs", "LOAD 'httpfs'", []),
            ("SB12_read_json_auto", f"SELECT * FROM read_json_auto('{json_file}')", []),
            ("SB13_parquet_scan", f"SELECT * FROM parquet_scan('{parquet_glob}')", []),
            ("SB14_duckdb_secrets", "SELECT * FROM duckdb_secrets()", []),
            ("SB15_query_table_dwd", "SELECT * FROM query_table('dwd.fact_order')", []),
            ("SB16_wrapper_breakout_limit", "SELECT a.month FROM ads.kpi_monthly a, ads.kpi_monthly b) AS q LIMIT 200 --", []),
            ("SB17_wrapper_stacked", "SELECT 1) AS q; COPY ads.kpi_monthly TO '" + copy_file + "'; --", []),
            ("SB18_recursive_cte_dos", "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM r WHERE n < 100000000) SELECT count(*) FROM r", []),
            ("SB19_ddl_create", "CREATE TABLE ads.evil (x INT)", []),
            ("SB20_dml_delete", "DELETE FROM ads.kpi_monthly", []),
            ("SB21_duckdb_settings", "SELECT name, value FROM duckdb_settings() WHERE name IN ('enable_external_access','lock_configuration','memory_limit','threads')", []),
        ]

        l2_results = []
        for name, sql, params in l2_attacks:
            r = X.execute(sql, params=params, max_rows=5, timeout_s=3.0, skip_validation=True)
            l2_results.append({
                "id": name,
                "status": r["status"],
                "code": (r.get("error") or {}).get("code"),
                "message": (r.get("error") or {}).get("message"),
                "rows_count": len(r.get("rows") or []),
                "rows_sample": (r.get("rows") or [])[:5],
            })

        # Verify no side-effect files were written
        leaked_files = Path(copy_file).exists() or Path(export_dir).exists()

        # Benign CTE colliding with real DWD table name + wrong-view column check
        benign_cte = X.execute("WITH fact_order AS (SELECT month FROM ads.kpi_monthly) SELECT month FROM fact_order LIMIT 2")
        cross_view_col = X.execute("SELECT buyers FROM ads.sales_month_category_region LIMIT 2")

        report = {
            "leaked_files_written": leaked_files,
            "l1_total": len(l1_results),
            "l1_results": l1_results,
            "l2_total": len(l2_results),
            "l2_results": l2_results,
            "extra_benign_cte_with_dwd_name": {"status": benign_cte["status"], "error": benign_cte.get("error"), "rows": benign_cte.get("rows")},
            "extra_cross_view_col_in_validate": {"status": cross_view_col["status"], "error": cross_view_col.get("error")},
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
