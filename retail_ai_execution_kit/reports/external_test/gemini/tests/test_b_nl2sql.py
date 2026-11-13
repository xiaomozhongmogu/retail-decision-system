"""Group B adversarial test: NL2SQL Query Assistant accuracy & boundary interception.

Tests 40 brand-new questions (not copied from eval/nl2sql_cases.jsonl) against
independent DWD SQL gold answers using query_assistant.Session(..., use_llm=False).
Run from retail_ai_execution_kit/:
    .venv/bin/python reports/external_test/gemini/tests/test_b_nl2sql.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src/retail_bi/ai"))
sys.path.insert(0, str(ROOT / "src/retail_bi/warehouse"))

import query_assistant as QA  # noqa: E402
from runtime import open_current  # noqa: E402

V = "o.approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'"
JOIN_DWD = (
    "FROM dwd.fact_order_line l "
    "JOIN dwd.fact_order o USING (order_id) "
    "JOIN dwd.dim_product p USING (product_id) "
    "JOIN dwd.dim_customer c ON c.customer_id = l.customer_id"
)

# 22 questions intended to be in claimed scope (docs/nl2sql_supported_queries.md)
IN_SCOPE_CASES = [
    {
        "id": "B01",
        "question": "2025年第四季度的商品金额一共多少？",
        "compare": "value",
        "gold_sql": f"SELECT sum(o.merch_usd) FROM dwd.fact_order o WHERE {V} AND year(o.purchase_ts)=2025 AND quarter(o.purchase_ts)=4",
    },
    {
        "id": "B02",
        "question": "2025-05的销售金额是多少",
        "compare": "value",
        "gold_sql": f"SELECT sum(o.merch_usd) FROM dwd.fact_order o WHERE {V} AND strftime(o.purchase_ts,'%Y-%m')='2025-05'",
    },
    {
        "id": "B03",
        "question": "2026年1月的购买客户一共有多少位",
        "compare": "value",
        "gold_sql": f"SELECT count(DISTINCT o.customer_id) FROM dwd.fact_order o WHERE {V} AND strftime(o.purchase_ts,'%Y-%m')='2026-01'",
    },
    {
        "id": "B04",
        "question": "上个月取消了多少单",
        "compare": "value",
        "gold_sql": "SELECT count(*) FROM dwd.fact_order o WHERE o.approved_ts IS NULL AND strftime(o.purchase_ts,'%Y-%m')='2026-10'",
    },
    {
        "id": "B05",
        "question": "2026年第一季度运费总计多少",
        "compare": "value",
        "gold_sql": f"SELECT sum(o.shipping_usd) FROM dwd.fact_order o WHERE {V} AND year(o.purchase_ts)=2026 AND quarter(o.purchase_ts)=1",
    },
    {
        "id": "B06",
        "question": "最近4个月的订单量走势",
        "compare": "series",
        "gold_sql": f"SELECT strftime(o.purchase_ts,'%Y-%m') m, count(*) FROM dwd.fact_order o WHERE {V} AND strftime(o.purchase_ts,'%Y-%m') BETWEEN '2026-07' AND '2026-10' GROUP BY 1 ORDER BY 1",
    },
    {
        "id": "B07",
        "question": "2026年8月各品类的商品金额前3名",
        "compare": "table_topn",
        "gold_sql": f"SELECT p.product_category, sum(l.item_price_usd) s {JOIN_DWD} WHERE {V} AND strftime(o.purchase_ts,'%Y-%m')='2026-08' GROUP BY 1 ORDER BY 2 DESC LIMIT 3",
    },
    {
        "id": "B08",
        "question": "2025年第二季度中西部地区的销售金额",
        "compare": "value",
        "gold_sql": f"SELECT sum(l.item_price_usd) {JOIN_DWD} WHERE {V} AND year(o.purchase_ts)=2025 AND quarter(o.purchase_ts)=2 AND c.customer_region='Midwest'",
    },
    {
        "id": "B09",
        "question": "2025年南部客户购买母婴品类的销售额",
        "compare": "value",
        "gold_sql": f"SELECT sum(l.item_price_usd) {JOIN_DWD} WHERE {V} AND year(o.purchase_ts)=2025 AND c.customer_region='South' AND p.product_category='Baby Products'",
    },
    {
        "id": "B10",
        "question": "2026年10月园艺品类的销售金额",
        "compare": "value",
        "gold_sql": f"SELECT sum(l.item_price_usd) {JOIN_DWD} WHERE {V} AND strftime(o.purchase_ts,'%Y-%m')='2026-10' AND p.product_category='Garden & Outdoor'",
    },
    {
        "id": "B11",
        "question": "2026年9月各大区商品金额贡献占比",
        "compare": "share",
        "gold_sql": f"SELECT c.customer_region, sum(l.item_price_usd) s {JOIN_DWD} WHERE {V} AND strftime(o.purchase_ts,'%Y-%m')='2026-09' GROUP BY 1 ORDER BY 2 DESC",
    },
    {
        "id": "B12",
        "question": "2025年第四季度商品金额环比变化",
        "compare": "compare",
        "gold_sql": (
            f"SELECT (SELECT sum(o.merch_usd) FROM dwd.fact_order o WHERE {V} AND year(o.purchase_ts)=2025 AND quarter(o.purchase_ts)=4),"
            f"(SELECT sum(o.merch_usd) FROM dwd.fact_order o WHERE {V} AND year(o.purchase_ts)=2025 AND quarter(o.purchase_ts)=3)"
        ),
    },
    {
        "id": "B13",
        "question": "2026年8月订单数同比变化",
        "compare": "compare",
        "gold_sql": (
            f"SELECT (SELECT count(*) FROM dwd.fact_order o WHERE {V} AND strftime(o.purchase_ts,'%Y-%m')='2026-08'),"
            f"(SELECT count(*) FROM dwd.fact_order o WHERE {V} AND strftime(o.purchase_ts,'%Y-%m')='2025-08')"
        ),
    },
    {
        "id": "B14",
        "question": "本周每日订单数",
        "compare": "series",
        "gold_sql": f"SELECT CAST(CAST(o.purchase_ts AS DATE) AS VARCHAR) d, count(*) FROM dwd.fact_order o WHERE {V} AND CAST(o.purchase_ts AS DATE) BETWEEN DATE '2026-10-31' AND DATE '2026-11-06' GROUP BY 1 ORDER BY 1",
    },
    {
        "id": "B15",
        "question": "本月商品金额是多少",
        "compare": "value",
        "gold_sql": f"SELECT sum(o.merch_usd) FROM dwd.fact_order o WHERE {V} AND strftime(o.purchase_ts,'%Y-%m')='2026-11'",
    },
    {
        "id": "B16",
        "question": "2025年平均每单商品金额是多少",
        "compare": "value",
        "gold_sql": f"SELECT sum(o.merch_usd)/count(*) FROM dwd.fact_order o WHERE {V} AND year(o.purchase_ts)=2025",
    },
    {
        "id": "B17",
        "question": "首单后第一个月的留存率是多少",
        "compare": "value",
        "gold_sql": (
            f"WITH v AS (SELECT o.customer_id, date_trunc('month', CAST(o.purchase_ts AS DATE)) m FROM dwd.fact_order o WHERE {V}),"
            "f AS (SELECT customer_id, min(m) cohort FROM v GROUP BY 1),"
            "a AS (SELECT DISTINCT f.cohort, v.customer_id FROM v JOIN f USING (customer_id) WHERE datediff('month', f.cohort, v.m)=1),"
            "sz AS (SELECT cohort, count(*) n FROM f WHERE cohort + INTERVAL 1 MONTH < DATE '2026-11-01' GROUP BY 1),"
            "act AS (SELECT cohort, count(*) k FROM a WHERE cohort + INTERVAL 1 MONTH < DATE '2026-11-01' GROUP BY 1)"
            "SELECT sum(coalesce(act.k,0))::DOUBLE / sum(sz.n) FROM sz LEFT JOIN act USING (cohort)"
        ),
    },
    {
        "id": "B18",
        "question": "活跃客户现在有多少人",
        "compare": "value",
        "gold_sql": (
            "WITH snap_t AS (SELECT TIMESTAMPTZ '2026-11-02 00:00:00+00' AS t),"
            "seen AS (SELECT o.customer_id, min(o.purchase_ts) fp, max(o.purchase_ts) lp "
            "FROM dwd.fact_order o, snap_t s WHERE o.purchase_ts < s.t AND o.approved_ts < s.t GROUP BY 1),"
            "st AS (SELECT CASE WHEN fp >= (SELECT t FROM snap_t) - INTERVAL 30 DAY THEN 'new' "
            "WHEN lp >= (SELECT t FROM snap_t) - INTERVAL 90 DAY THEN 'active' "
            "WHEN lp >= (SELECT t FROM snap_t) - INTERVAL 180 DAY THEN 'at_risk' ELSE 'dormant' END AS state FROM seen)"
            "SELECT count(*) FROM st WHERE state='active'"
        ),
    },
    # Rephrasings / adversarial in-scope queries designed to expose parser flaws
    {
        "id": "B19",
        "question": "去年第3季度的客单价是多少",
        "compare": "value",
        "gold_sql": f"SELECT sum(o.merch_usd)/count(*) FROM dwd.fact_order o WHERE {V} AND year(o.purchase_ts)=2025 AND quarter(o.purchase_ts)=3",
        "note": "relative year + quarter phrasing ('去年第3季度')",
    },
    {
        "id": "B20",
        "question": "2024年商品金额最低的3个品类",
        "compare": "table_topn",
        "gold_sql": f"SELECT p.product_category, sum(l.item_price_usd) s {JOIN_DWD} WHERE {V} AND year(o.purchase_ts)=2024 GROUP BY 1 ORDER BY 2 ASC LIMIT 3",
        "note": "bottom-N ranking phrasing without '前N'",
    },
    {
        "id": "B21",
        "question": "2025年美妆和时尚品类的商品金额",
        "compare": "value",
        "gold_sql": f"SELECT sum(l.item_price_usd) {JOIN_DWD} WHERE {V} AND year(o.purchase_ts)=2025 AND p.product_category IN ('Health & Beauty','Fashion')",
        "note": "multi-category OR filter",
    },
    {
        "id": "B22",
        "question": "2025年Electronics & Accessories的销售额",
        "compare": "value",
        "gold_sql": f"SELECT sum(l.item_price_usd) {JOIN_DWD} WHERE {V} AND year(o.purchase_ts)=2025 AND p.product_category='Electronics & Accessories'",
        "note": "mixed Chinese-English with official English category name",
    },
    {
        "id": "B23",
        "question": "2025年取消订单的商品金额是多少",
        "compare": "value",
        "gold_sql": "SELECT sum(o.merch_usd) FROM dwd.fact_order o WHERE o.approved_ts IS NULL AND year(o.purchase_ts)=2025",
        "note": "cancelled merchandise amount vs cancelled order count",
    },
    {
        "id": "B24",
        "question": "2026年10月各品类商品金额同比变化",
        "compare": "table_compare",
        "gold_sql": (
            f"SELECT a.product_category, (a.s - b.s)/b.s FROM "
            f"(SELECT p.product_category, sum(l.item_price_usd) s {JOIN_DWD} WHERE {V} AND strftime(o.purchase_ts,'%Y-%m')='2026-10' GROUP BY 1) a "
            f"JOIN (SELECT p.product_category, sum(l.item_price_usd) s {JOIN_DWD} WHERE {V} AND strftime(o.purchase_ts,'%Y-%m')='2025-10' GROUP BY 1) b USING (product_category) ORDER BY 1"
        ),
        "note": "YoY comparison grouped by category",
    },
    {
        "id": "B25",
        "question": "上周客单价是多少",
        "compare": "value",
        "gold_sql": f"SELECT sum(o.merch_usd)/count(*) FROM dwd.fact_order o WHERE {V} AND CAST(o.purchase_ts AS DATE) BETWEEN DATE '2026-10-31' AND DATE '2026-11-06'",
        "note": "weekly AOV scalar question",
    },
]

# 15 boundary / adversarial questions (should NOT answer with wrong numbers; should clarify / empty / unsupported)
BOUNDARY_CASES = [
    {"id": "BB01", "kind": "ambiguous", "question": "2025年各月收入趋势", "expect": ("clarify",)},
    {"id": "BB02", "kind": "ambiguous", "question": "2026年10月哪个品类卖得最好", "expect": ("clarify",)},
    {"id": "BB03", "kind": "ambiguous", "question": "商品金额同比变化", "expect": ("clarify",)},
    {"id": "BB04", "kind": "ambiguous", "question": "2025年商品金额排名", "expect": ("clarify",)},
    {"id": "BB05", "kind": "future", "question": "2027年3月的订单数是多少", "expect": ("empty", "unsupported", "clarify")},
    {"id": "BB06", "kind": "after_cutoff", "question": "2026年11月15日的商品金额是多少", "expect": ("empty", "unsupported", "clarify")},
    {"id": "BB07", "kind": "after_cutoff", "question": "2026年12月有多少有效订单", "expect": ("empty", "unsupported", "clarify")},
    {"id": "BB08", "kind": "cross_year_range", "question": "2025年11月到2026年2月的商品金额一共多少", "expect": ("clarify", "unsupported")},
    {"id": "BB09", "kind": "nonexistent_cat", "question": "2025年化妆品品类的商品金额是多少", "expect": ("clarify", "unsupported", "empty")},
    {"id": "BB10", "kind": "nonexistent_cat", "question": "2026年10月生鲜品类的销售额", "expect": ("clarify", "unsupported", "empty")},
    {"id": "BB11", "kind": "write_intent", "question": "请把2026年10月的商品金额修改为0", "expect": ("unsupported",)},
    {"id": "BB12", "kind": "write_intent", "question": "帮我把2025年的订单导出成CSV文件", "expect": ("unsupported",)},
    {"id": "BB13", "kind": "mixed_en_cn", "question": "2025年Q4各region的merchandise sales是多少", "expect": ("clarify", "unsupported")},
    {"id": "BB14", "kind": "unsupported_cross_month_buyers", "question": "2025年全年的购买客户数是多少", "expect": ("unsupported", "clarify")},
    {"id": "BB15", "kind": "unsupported_sliced_aov", "question": "2025年各品类的客单价分别是多少", "expect": ("unsupported",)},
]


def rel_diff(a: float, b: float) -> float:
    if a == b:
        return 0.0
    if b == 0:
        return float("inf")
    return abs(a - b) / abs(b)


def eval_in_scope(con, session: QA.Session, case: dict) -> dict:
    resp = session.ask(case["question"])
    cid, cmp_mode = case["id"], case["compare"]
    if resp["status"] != "ok":
        return {"id": cid, "question": case["question"], "status": resp["status"], "passed": False, "wrong_number_answered": False,
                "reason": f"expected status=ok, got {resp['status']}: {resp.get('answer')}", "note": case.get("note")}
    res = resp.get("result") or {}
    if cmp_mode == "value":
        gold = float(con.execute(case["gold_sql"]).fetchone()[0])
        if res.get("kind") != "value" or res.get("value") is None:
            return {"id": cid, "question": case["question"], "status": "ok", "passed": False, "wrong_number_answered": True,
                    "reason": f"expected scalar value (~{gold:.4f}), got kind={res.get('kind')} value={res.get('value')} rows={res.get('rows')}",
                    "answer": resp.get("answer"), "note": case.get("note")}
        got = float(res["value"])
        err = rel_diff(got, gold)
        ok = err <= 0.006
        return {"id": cid, "question": case["question"], "status": "ok", "passed": ok, "wrong_number_answered": not ok,
                "gold": gold, "got": got, "rel_err": round(err, 6), "answer": resp.get("answer"), "note": case.get("note")}
    if cmp_mode == "series":
        gold_rows = [(r[0], float(r[1])) for r in con.execute(case["gold_sql"]).fetchall()]
        got_rows = [(r[0], float(r[1])) for r in res.get("rows", [])]
        ok = len(gold_rows) == len(got_rows) and all(g[0] == a[0] and rel_diff(a[1], g[1]) <= 0.006 for g, a in zip(gold_rows, got_rows))
        return {"id": cid, "question": case["question"], "status": "ok", "passed": ok, "wrong_number_answered": not ok,
                "gold": gold_rows, "got": got_rows, "reason": None if ok else "series mismatch", "note": case.get("note")}
    if cmp_mode == "table_topn":
        gold_rows = [(r[0], float(r[1])) for r in con.execute(case["gold_sql"]).fetchall()]
        got_rows = [(r[0], float(r[1])) for r in res.get("rows", [])]
        ok = len(gold_rows) == len(got_rows) and all(g[0] == a[0] and rel_diff(a[1], g[1]) <= 0.006 for g, a in zip(gold_rows, got_rows))
        return {"id": cid, "question": case["question"], "status": "ok", "passed": ok, "wrong_number_answered": not ok,
                "gold": gold_rows, "got": got_rows, "reason": None if ok else f"expected {len(gold_rows)} rows {gold_rows}, got {got_rows}", "note": case.get("note")}
    if cmp_mode == "share":
        gold_raw = [(r[0], float(r[1])) for r in con.execute(case["gold_sql"]).fetchall()]
        tot = sum(v for _, v in gold_raw)
        gold_map = {k: (v, v / tot) for k, v in gold_raw}
        got_map = {r[0]: (float(r[1]), float(r[2])) for r in res.get("rows", [])}
        ok = set(gold_map) == set(got_map) and all(
            rel_diff(got_map[k][0], gold_map[k][0]) <= 0.006 and rel_diff(got_map[k][1], gold_map[k][1]) <= 0.006 for k in gold_map
        )
        return {"id": cid, "question": case["question"], "status": "ok", "passed": ok, "wrong_number_answered": not ok,
                "gold": gold_map, "got": got_map, "note": case.get("note")}
    if cmp_mode == "compare":
        cur_g, base_g = [float(x) for x in con.execute(case["gold_sql"]).fetchone()]
        chg_g = (cur_g - base_g) / base_g
        ok = (
            res.get("kind") == "value"
            and res.get("value") is not None
            and res.get("base_value") is not None
            and res.get("change") is not None
            and rel_diff(float(res["value"]), cur_g) <= 0.006
            and rel_diff(float(res["base_value"]), base_g) <= 0.006
            and rel_diff(float(res["change"]), chg_g) <= 0.006
        )
        return {"id": cid, "question": case["question"], "status": "ok", "passed": ok, "wrong_number_answered": not ok,
                "gold": (cur_g, base_g, chg_g), "got": (res.get("value"), res.get("base_value"), res.get("change")), "note": case.get("note")}
    if cmp_mode == "table_compare":
        # Must include comparison change, not silently drop YoY
        gold_rows = con.execute(case["gold_sql"]).fetchall()
        has_change = "change" in res or any("change" in str(c) for c in res.get("columns", []))
        return {"id": cid, "question": case["question"], "status": "ok", "passed": False if not has_change else True,
                "wrong_number_answered": not has_change,
                "reason": "grouped YoY comparison silently dropped compare='yoy' and returned raw single-period amounts" if not has_change else None,
                "got_columns": res.get("columns"), "got_sample": res.get("rows", [])[:2], "note": case.get("note")}
    raise ValueError(cmp_mode)


def eval_boundary(case: dict) -> dict:
    s = QA.Session(f"bound-{case['id']}", use_llm=False)
    resp = s.ask(case["question"])
    executed = "query" in resp
    intercepted = resp["status"] in case["expect"] and not executed
    wrong_num = resp["status"] == "ok"
    return {
        "id": case["id"],
        "kind": case["kind"],
        "question": case["question"],
        "status": resp["status"],
        "executed_query": executed,
        "intercepted": intercepted,
        "wrong_number_answered": wrong_num,
        "answer": resp.get("answer"),
        "result": resp.get("result"),
        "intent": resp.get("intent"),
    }


def eval_followups() -> list[dict]:
    out = []
    # Follow-up 1: turn 1 valid, turn 2 unsupported metric ("那毛利呢")
    s1 = QA.Session("fu-1", use_llm=False)
    s1.ask("2026年10月的商品金额是多少？")
    r1 = s1.ask("那毛利呢")
    out.append({"id": "BF01", "turns": ["2026年10月的商品金额是多少？", "那毛利呢"], "status": r1["status"],
                "passed": r1["status"] == "unsupported" and "query" not in r1, "answer": r1.get("answer")})

    # Follow-up 2: turn 1 valid, turn 2 nonexistent category ("那化妆品品类呢")
    s2 = QA.Session("fu-2", use_llm=False)
    s2.ask("2025年电子品类的商品金额是多少？")
    r2 = s2.ask("那化妆品品类呢")
    out.append({"id": "BF02", "turns": ["2025年电子品类的商品金额是多少？", "那化妆品品类呢"], "status": r2["status"],
                "passed": r2["status"] in ("clarify", "unsupported", "empty") and "query" not in r2, "answer": r2.get("answer")})

    # Follow-up 3: turn 1 valid YoY comparison, turn 2 switch month ("那2026年9月呢")
    s3 = QA.Session("fu-3", use_llm=False)
    s3.ask("2026年10月商品金额同比变化")
    r3 = s3.ask("那2026年9月呢")
    out.append({"id": "BF03", "turns": ["2026年10月商品金额同比变化", "那2026年9月呢"], "status": r3["status"],
                "passed": r3["status"] == "ok" and "change" in (r3.get("result") or {}), "answer": r3.get("answer")})

    # Follow-up 4: turn 1 valid, turn 2 post-cutoff date ("那2026年11月15日呢")
    s4 = QA.Session("fu-4", use_llm=False)
    s4.ask("2026年10月的商品金额是多少？")
    r4 = s4.ask("那2026年11月15日呢")
    out.append({"id": "BF04", "turns": ["2026年10月的商品金额是多少？", "那2026年11月15日呢"], "status": r4["status"],
                "passed": r4["status"] != "ok", "executed_query": "query" in r4, "answer": r4.get("answer")})
    return out


def main() -> int:
    con, ptr = open_current()
    in_scope_results = []
    for c in IN_SCOPE_CASES:
        sess = QA.Session(f"in-{c['id']}", use_llm=False)
        in_scope_results.append(eval_in_scope(con, sess, c))
    con.close()

    boundary_results = [eval_boundary(c) for c in BOUNDARY_CASES]
    followup_results = eval_followups()

    in_passed = sum(1 for r in in_scope_results if r["passed"])
    bound_intercepted = sum(1 for r in boundary_results if r["intercepted"])
    wrong_num_count = sum(1 for r in in_scope_results if r["wrong_number_answered"]) + sum(
        1 for r in boundary_results if r["wrong_number_answered"]
    ) + sum(1 for r in followup_results if r.get("executed_query") and not r["passed"])

    summary = {
        "dataset_version": ptr["version"],
        "in_scope_total": len(in_scope_results),
        "in_scope_passed": in_passed,
        "in_scope_accuracy": round(in_passed / len(in_scope_results), 4),
        "boundary_total": len(boundary_results),
        "boundary_intercepted": bound_intercepted,
        "boundary_interception_rate": round(bound_intercepted / len(boundary_results), 4),
        "answered_with_wrong_number_count": wrong_num_count,
        "followup_total": len(followup_results),
        "followup_passed": sum(1 for r in followup_results if r["passed"]),
        "in_scope_failures": [r for r in in_scope_results if not r["passed"]],
        "boundary_failures": [r for r in boundary_results if not r["intercepted"]],
        "followup_results": followup_results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
