"""Group H exploratory adversarial test: Concurrency, extremes/NaN, broken release/UI resilience, timeouts, budgets, replay & session state.

Uses temporary paths for DraftStore/events/logs/releases and 0 real LLM calls.
Run from retail_ai_execution_kit/:
    .venv/bin/python reports/external_test/gemini/tests/test_h_explore.py
"""
from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/retail_bi/ai"))
sys.path.insert(0, str(ROOT / "src/retail_bi/warehouse"))

import client as C  # noqa: E402
import integration as I  # noqa: E402
import policy_engine as PE  # noqa: E402
import query_assistant as QA  # noqa: E402
import report_facts as RF  # noqa: E402
import report_generator as RG  # noqa: E402
import retrieval as RET  # noqa: E402
import sql_executor as SE  # noqa: E402
from drafts import DraftStore  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402


def mk_resp(content: str) -> dict:
    return {
        "model": "fake-model",
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 30, "completion_tokens": 15},
    }


def main() -> int:
    results = []

    def check(cid: str, cond: bool, detail: dict) -> None:
        results.append({"id": cid, "passed": bool(cond), "detail": detail})

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # H01a: Concurrent QA.Session isolation & shared-session thread safety
        iso_ok = True
        iso_outputs = {}

        def run_iso(idx: int, month: str, prev_month: str) -> None:
            nonlocal iso_ok
            s = QA.Session(f"iso-{idx}", use_llm=False)
            r1 = s.ask(f"{month}的商品金额是多少")
            r2 = s.ask("上个月呢")
            iso_outputs[idx] = (r1["status"], prev_month in r2.get("answer", ""), r2.get("answer", ""))
            if not (r1["status"] == "ok" and r2["status"] == "ok" and prev_month in r2.get("answer", "")):
                iso_ok = False

        t_iso = [
            threading.Thread(target=run_iso, args=(i, m, pm))
            for i, (m, pm) in enumerate([("2025-02", "2025-01"), ("2025-04", "2025-03"), ("2025-06", "2025-05"), ("2025-08", "2025-07")])
        ]
        for t in t_iso:
            t.start()
        for t in t_iso:
            t.join()

        # H01b: Concurrent DraftStore threads (different & identical request_id)
        conc_db = DraftStore(tmp / "conc_drafts.sqlite")
        conc_errs = []
        conc_results = []

        def save_worker(i: int, same_req: bool = False) -> None:
            try:
                res = conc_db.save(
                    request_id="req-race" if same_req else f"req-{i}",
                    customer_id="customer_000001",
                    action="reminder",
                    discount=0.0,
                    copy="您好，欢迎来看看" if same_req else f"您好，欢迎来看看 #{i}",
                    reasons=[],
                    evidence=[],
                    policy_version="retention-policy-v1",
                    budget={},
                    mode="template_fallback",
                )
                conc_results.append((i, same_req, res.get("status"), res.get("created"), (res.get("error") or {}).get("code")))
            except Exception as exc:
                conc_errs.append(f"{type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=save_worker, args=(i, False)) for i in range(8)]
        threads += [threading.Thread(target=save_worker, args=(i, True)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        check(
            "H01_concurrency_sessions_and_draftstore",
            iso_ok and len(conc_errs) == 0 and len(conc_db.list()) == 9,
            {
                "isolated_sessions_ok": iso_ok,
                "iso_outputs": iso_outputs,
                "draftstore_exceptions": conc_errs,
                "draftstore_total_rows": len(conc_db.list()),
                "same_req_created_count": sum(1 for r in conc_results if r[1] and r[3] is True),
                "same_req_outcomes": [r for r in conc_results if r[1]],
            },
        )

        # H02: Extreme & malformed inputs (25k chars, empty, NUL bytes)
        sess_ext = QA.Session("ext", use_llm=False)
        r_huge_valid = sess_ext.ask("2026年10月的商品金额是多少？" + ("哈" * 25000))
        r_huge_garbage = sess_ext.ask("哈" * 25000)
        r_nul = sess_ext.ask("\x00\x00SELECT * FROM ads.kpi_monthly")
        ret_huge = RET.retrieve("退货 " * 5000)
        ret_nul = RET.retrieve("\x00\x00")
        sql_nul = SE.execute("SELECT 1\x00")
        check(
            "H02_extreme_and_malformed_inputs",
            r_huge_garbage["status"] in ("clarify", "unsupported")
            and r_nul["status"] in ("clarify", "unsupported")
            and isinstance(ret_huge, dict)
            and isinstance(ret_nul, dict)
            and sql_nul["status"] != "ok",
            {
                "huge_valid_status": r_huge_valid["status"],
                "huge_garbage_status": r_huge_garbage["status"],
                "nul_qa_status": r_nul["status"],
                "ret_huge_count": len(ret_huge.get("chunks", [])),
                "ret_nul_count": len(ret_nul.get("chunks", [])),
                "sql_nul_status": sql_nul["status"],
            },
        )

        # H03: policy_engine NaN / negative margin / NaN budget & NaN discount attacks
        base_c = {
            "customer_id": "customer_000001", "recency_days": 120, "frequency_90d": 0,
            "monetary_90d_usd": 0.0, "orders_all_time": 1, "merch_all_time_usd": 100.0,
            "tenure_days": 120, "lifecycle_state": "dormant", "applicability": "out_of_population",
            "return_rate": None, "aov_usd": 100.0,
        }
        def safe_decide(prop, ctx, bud):
            try:
                out = PE.decide(base_c, prop, ctx, bud)
                disc = (out.get("data") or {}).get("action", {}).get("discount")
                return {
                    "crashed": False,
                    "status": out["status"],
                    "decision": (out.get("data") or {}).get("decision"),
                    "action": (out.get("data") or {}).get("action"),
                    "disc_is_nan": isinstance(disc, float) and math.isnan(disc),
                    "reasons": (out.get("data") or {}).get("reasons"),
                }
            except Exception as exc:
                return {"crashed": True, "exception": f"{type(exc).__name__}: {exc}"}

        d_nan_margin = safe_decide({"type": "coupon", "discount": 0.15}, {"consent": True, "gross_margin": float("nan")}, {"spent_usd": 0.0})
        d_neg_margin = safe_decide({"type": "coupon", "discount": 0.15}, {"consent": True, "gross_margin": -0.5}, {"spent_usd": 0.0})
        d_nan_budget = safe_decide({"type": "coupon", "discount": 0.05}, {"consent": True}, {"spent_usd": float("nan")})
        d_nan_disc = safe_decide({"type": "coupon", "discount": float("nan")}, {"consent": True}, {"spent_usd": 0.0})
        check(
            "H03_policy_engine_nan_and_negative_guards",
            not any(d["crashed"] for d in (d_nan_margin, d_neg_margin, d_nan_budget, d_nan_disc))
            and (not d_neg_margin["crashed"] and d_neg_margin["action"]["discount"] == 0.0 and d_neg_margin["action"]["type"] == "reminder")
            and (d_nan_budget.get("status") == "error" or d_nan_budget.get("decision") == "deny")
            and not d_nan_disc.get("disc_is_nan", False),
            {
                "nan_margin": d_nan_margin,
                "neg_margin": d_neg_margin,
                "nan_budget": d_nan_budget,
                "nan_discount": d_nan_disc,
            },
        )

        # H04: Broken RETAIL_BI_RELEASES_DIR (corrupt JSON & missing .duckdb file) in ui.common / report_facts / AppTest
        from retail_bi.ui import common as UI_COMMON  # noqa: E402

        orig_env = os.environ.get("RETAIL_BI_RELEASES_DIR")
        corrupt_dir = tmp / "rel_corrupt"
        corrupt_dir.mkdir()
        (corrupt_dir / "current.json").write_text("{broken json", encoding="utf-8")

        missing_db_dir = tmp / "rel_missing_db"
        missing_db_dir.mkdir()
        (missing_db_dir / "current.json").write_text(
            json.dumps({
                "version": "wh-missing",
                "file": "does_not_exist.duckdb",
                "sha256": "0" * 64,
                "allowed_views": ["ads.kpi_monthly", "ads.lifecycle_mix_weekly", "ads.risk_summary_latest", "ads.sales_month_category_region"],
            }),
            encoding="utf-8",
        )
        incomplete_json_dir = tmp / "rel_incomplete"
        incomplete_json_dir.mkdir()
        (incomplete_json_dir / "current.json").write_text(
            json.dumps({"version": "wh-partial", "file": "does_not_exist.duckdb", "sha256": "0" * 64}),
            encoding="utf-8",
        )

        corrupt_info_exc = None
        corrupt_ui_exc = None
        incomplete_ui_exc = None
        missing_info_res = None
        missing_rf_exc = None
        missing_ui_exc = {}
        try:
            os.environ["RETAIL_BI_RELEASES_DIR"] = str(corrupt_dir)
            try:
                UI_COMMON.release_info()
            except Exception as exc:
                corrupt_info_exc = f"{type(exc).__name__}: {exc}"
            try:
                at = AppTest.from_file(str(ROOT / "src/retail_bi/ui/pages/business.py"), default_timeout=15)
                at.run()
                if at.exception:
                    corrupt_ui_exc = [str(e.value) for e in at.exception]
            except Exception as exc:
                corrupt_ui_exc = f"{type(exc).__name__}: {exc}"

            os.environ["RETAIL_BI_RELEASES_DIR"] = str(incomplete_json_dir)
            try:
                at = AppTest.from_file(str(ROOT / "src/retail_bi/ui/pages/business.py"), default_timeout=15)
                at.run()
                if at.exception:
                    incomplete_ui_exc = [str(e.value) for e in at.exception]
            except Exception as exc:
                incomplete_ui_exc = f"{type(exc).__name__}: {exc}"

            os.environ["RETAIL_BI_RELEASES_DIR"] = str(missing_db_dir)
            try:
                missing_info_res = UI_COMMON.release_info()
            except Exception as exc:
                missing_info_res = f"ERR: {type(exc).__name__}: {exc}"
            try:
                RF.build_weekly_facts(releases=missing_db_dir)
            except Exception as exc:
                missing_rf_exc = f"{type(exc).__name__}: {exc}"
            for pname in ("business.py", "customers.py", "data.py", "prediction.py", "ai.py"):
                try:
                    at = AppTest.from_file(str(ROOT / "src/retail_bi/ui/pages" / pname), default_timeout=15)
                    at.run()
                    if at.exception:
                        missing_ui_exc[pname] = [str(e.value) for e in at.exception]
                except Exception as exc:
                    missing_ui_exc[pname] = f"{type(exc).__name__}: {exc}"
        finally:
            if orig_env is None:
                os.environ.pop("RETAIL_BI_RELEASES_DIR", None)
            else:
                os.environ["RETAIL_BI_RELEASES_DIR"] = orig_env

        check(
            "H04_broken_release_dir_resilience",
            corrupt_info_exc is None and corrupt_ui_exc is None and incomplete_ui_exc is None and len(missing_ui_exc) == 0,
            {
                "corrupt_json_release_info_exc": corrupt_info_exc,
                "corrupt_json_business_ui_exc": corrupt_ui_exc,
                "incomplete_json_business_ui_exc": incomplete_ui_exc,
                "missing_db_release_info": missing_info_res,
                "missing_db_report_facts_exc": missing_rf_exc,
                "missing_db_ui_page_exceptions": missing_ui_exc,
            },
        )

        # H05: Timeout, 429 retry exhaustion & shared Hub budget exhaustion (max_calls=2)
        ev_h05 = tmp / "events_h05.jsonl"
        llm_h05 = tmp / "llm_h05.jsonl"
        cfg_h05 = C.Config(
            api_key="sk-fakeH05Key123456",
            base_url="https://example.invalid/v1",
            model="fake-model",
            allow_paid=True,
            allow_unknown_price=True,
            max_calls=10,
            max_retries=2,
        )
        sleep_calls = []
        cl_err = C.LLMClient(
            cfg=cfg_h05,
            transport=C.fixture_transport([
                C.TransportError("Timeout reading upstream", retryable=True),
                C.TransportError("Timeout reading upstream", retryable=True),
                C.TransportError("Timeout reading upstream", retryable=True),
                C.TransportError("HTTP 429 Too Many Requests", retryable=True, status=429),
                C.TransportError("HTTP 429 Too Many Requests", retryable=True, status=429),
                C.TransportError("HTTP 429 Too Many Requests", retryable=True, status=429),
            ]),
            mode="live",
            log_path=llm_h05,
            sleep=lambda s: sleep_calls.append(s),
        )
        hub_err = I.Hub(client=cl_err, use_llm=True, events=ev_h05)
        q_to, ev_to = hub_err.run_query("为什么 2026 年 10 月波动这么大？")
        rep_429, ev_429 = hub_err.run_report(mode="live")

        # Shared Hub budget exhaustion across modules (max_calls=2)
        cl_bud = C.LLMClient(
            cfg=C.Config(
                api_key="sk-fakeBudget123456",
                base_url="https://example.invalid/v1",
                model="fake-model",
                allow_paid=True,
                allow_unknown_price=True,
                max_calls=2,
                max_retries=0,
            ),
            transport=C.fixture_transport([
                mk_resp(json.dumps({"supported": False, "reason": "need clarification"})),
                mk_resp(json.dumps({"action": "coupon", "discount": 0.05, "rationale": "r", "evidence": []})),
                mk_resp(json.dumps({"copy": "should not execute"})),
            ]),
            mode="live",
            log_path=tmp / "llm_bud.jsonl",
            sleep=lambda _: None,
        )
        hub_bud = I.Hub(client=cl_bud, use_llm=True, events=tmp / "ev_bud.jsonl")
        _, ev_b1 = hub_bud.run_query("为什么 2026 年 10 月增长这么多？")  # call #1
        ag_b2, ev_b2 = hub_bud.run_agent({"customer_id": "customer_000001", "context": {"consent": True}}, store=DraftStore(tmp / "d_bud.sqlite"))  # call #2 succeeds, call #3 denied
        rep_b3, ev_b3 = hub_bud.run_report(mode="live")  # denied immediately

        check(
            "H05_retries_and_shared_budget",
            ev_to["mode"] == "timeout"
            and ev_429["mode"] == "rate_limited"
            and rep_429["mode"] == "template"
            and len(sleep_calls) == 4
            and cl_bud.calls == 2
            and ag_b2["state"] == "draft_saved"
            and ag_b2["draft"]["mode"] == "template_fallback"
            and rep_b3["mode"] == "template",
            {
                "timeout_ev_mode": ev_to["mode"],
                "timeout_qa_status": q_to["status"],
                "timeout_qa_note": q_to.get("note"),
                "rate_limit_ev_mode": ev_429["mode"],
                "sleep_backoffs": sleep_calls,
                "budget_calls_total": cl_bud.calls,
                "budget_ev2_mode": ev_b2["mode"],
                "budget_ev3_mode": ev_b3["mode"],
                "budget_ag_draft_mode": ag_b2["draft"]["mode"],
                "budget_rep_mode": rep_b3["mode"],
            },
        )

        # H06: replay_text HTML/XSS injection & QA.Session state after clarify/cancel
        facts = RF.build_weekly_facts()
        xss_body = json.dumps({
            "explanation": "<script>alert('xss')</script> 本周商品金额为 {{F01}}，环比 {{F05}}。",
            "actions": ["<img src=x onerror=alert('xss')> 继续观察。"],
            "hypotheses": ["待验证：需结合品类结构分析变化。"],
        }, ensure_ascii=False)
        rep_xss = RG.generate_weekly_report(facts, client=None, mode="replay", replay_text=xss_body)
        rep_xss_dump = json.dumps(rep_xss, ensure_ascii=False)

        sess_direct = QA.Session("direct-test", use_llm=False)
        d1 = sess_direct.ask("2025年05月的商品金额是多少")
        d2 = sess_direct.ask("上个月呢")

        sess_state = QA.Session("state-test", use_llm=False)
        st1 = sess_state.ask("2025年05月的商品金额是多少")
        st2 = sess_state.ask("为什么这么高")  # clarify/unsupported mid-session
        st3 = sess_state.ask("上个月呢")  # should carry forward 2025-05 -> 2025-04!

        sess_cancel = QA.Session("cancel-test", use_llm=False)
        c1 = sess_cancel.ask("2025年05月的商品金额是多少")
        sess_cancel.cancel()
        c2 = sess_cancel.ask("上个月呢")
        check(
            "H06_replay_xss_and_session_state",
            rep_xss["mode"] == "template"
            and "<script>" not in rep_xss_dump
            and st1["status"] == "ok"
            and st3["status"] == "ok" and "2025-04" in st3.get("answer", ""),
            {
                "xss_replay_mode": rep_xss["mode"],
                "xss_rep_keys": list(rep_xss.keys()),
                "script_in_report_output": "<script>" in (rep_xss.get("text") or ""),
                "onerror_in_report_output": "onerror=" in (rep_xss.get("text") or ""),
                "direct_followup_answer": d2.get("answer", ""),
                "st2_status": st2["status"],
                "st3_status": st3["status"],
                "st3_after_clarify_answer": st3.get("answer", ""),
                "after_cancel_answer": c2.get("answer", ""),
                "has_cancel_method": hasattr(sess_state, "cancel"),
            },
        )

    print(json.dumps({
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failures": [r for r in results if not r["passed"]],
        "all_results": results,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
