"""Group F adversarial test: Redaction, secret protection, trace leakage, and Hub linkage.

Uses fake LLM transports (0 real LLM calls) and temporary paths for logs/events/drafts.
Run from retail_ai_execution_kit/:
    .venv/bin/python reports/external_test/gemini/tests/test_f_redaction.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src/retail_bi/ai"))
sys.path.insert(0, str(ROOT / "src/retail_bi/warehouse"))

import client as C  # noqa: E402
import integration as I  # noqa: E402
import query_assistant as QA  # noqa: E402
from drafts import DraftStore  # noqa: E402


def mk_resp(content: str, model: str = "fake-chat") -> dict:
    return {
        "model": model,
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 40, "completion_tokens": 20},
    }


SECRETS = [
    ("sk_std", "sk-fakeSecretKey12345678"),
    ("sk_short", "sk-12345"),
    ("sk_underscore", "sk_live_fakeSecretKey1234"),
    ("bearer", "Bearer mySecretBearerTok999"),
    ("token_hdr", "Token myCustomToken999"),
    ("api_key_eq", "api_key=myRawApiKey98765"),
    ("deepseek_eq", "DEEPSEEK_API_KEY=dsKeySecret4321"),
]


def main() -> int:
    results = []
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        def check(cid: str, cond: bool, detail: dict) -> None:
            results.append({"id": cid, "passed": bool(cond), "detail": detail})

        # F01: Direct redact() coverage across secret patterns
        redacted_map = {}
        missed_patterns = []
        for label, secret in SECRETS:
            out = I.redact(f"prefix {secret} suffix")
            leaked = secret in out
            redacted_map[label] = {"output": out, "leaked": leaked}
            if leaked:
                missed_patterns.append(label)
        # Dict key redaction check
        dict_key_out = I.redact({"sk-fakeSecretKey12345678": "safe_val"})
        dict_key_leaked = "sk-fakeSecretKey12345678" in json.dumps(dict_key_out)
        check(
            "F01_redact_pattern_gaps",
            len(missed_patterns) == 0 and not dict_key_leaked,
            {"missed_patterns": missed_patterns, "dict_key_leaked": dict_key_leaked, "samples": redacted_map},
        )

        # F02: LLMClient.chat TransportError logs unredacted secret into llm_calls.jsonl
        llm_log_f02 = tmp / "llm_f02.jsonl"
        err_secret = "Bearer sk-transportErrSecret9999"
        cfg_f02 = C.Config(
            api_key="sk-cfgSecretKey12345678",
            base_url="https://example.invalid/v1",
            model="fake-model",
            allow_paid=True,
            allow_unknown_price=True,
            max_retries=0,
        )
        cl_f02 = C.LLMClient(
            cfg=cfg_f02,
            transport=C.fixture_transport([C.TransportError(f"HTTP 401 header {err_secret}", retryable=False, status=401)]),
            mode="live",
            log_path=llm_log_f02,
            sleep=lambda _: None,
        )
        res_f02 = cl_f02.chat([{"role": "user", "content": "hi sk-promptSecret123456"}], purpose="f02_test")
        log_text_f02 = llm_log_f02.read_text(encoding="utf-8") if llm_log_f02.exists() else ""
        check(
            "F02_client_error_log_redaction",
            ("sk-transportErrSecret9999" not in log_text_f02) and ("mySecret" not in log_text_f02)
            and ("sk-transportErrSecret9999" not in json.dumps(res_f02, ensure_ascii=False)),
            {
                "secret_in_llm_log": "sk-transportErrSecret9999" in log_text_f02,
                "secret_in_return": "sk-transportErrSecret9999" in json.dumps(res_f02, ensure_ascii=False),
                "llm_log": log_text_f02.strip(),
            },
        )

        # F03: Hub.run_query error / answer / events secret exposure
        ev_f03 = tmp / "events_f03.jsonl"
        llm_f03 = tmp / "llm_f03.jsonl"
        cfg_f03 = C.Config(
            api_key="sk-cfgSecretKey12345678",
            base_url="https://example.invalid/v1",
            model="fake-model",
            allow_paid=True,
            allow_unknown_price=True,
            max_retries=0,
        )
        # Transport succeeds with SQL containing comment secret OR TransportError in run_query
        cl_f03 = C.LLMClient(
            cfg=cfg_f03,
            transport=C.fixture_transport([
                mk_resp(json.dumps({
                    "supported": True,
                    "metric": "merchandise_sales_usd",
                    "sql": "SELECT month, merchandise_sales_usd FROM ads.kpi_monthly WHERE month='2026-10' -- sk-sqlSecret12345678",
                    "note": "ok sk-noteSecret12345678",
                })),
                # Next query triggers TransportError with secret in message
                C.TransportError("upstream sk-upstreamSecret8888", retryable=False, status=500),
            ]),
            mode="live",
            log_path=llm_f03,
            sleep=lambda _: None,
        )
        hub_f03 = I.Hub(client=cl_f03, use_llm=True, events=ev_f03)
        q_secret = "为什么 2026 年 10 月销量这么高？sk-questionSecret9999 Bearer tokSecret999"
        ans1, ev1 = hub_f03.run_query(q_secret)
        # Second fallback question triggers TransportError with secret in message
        ans2, ev2 = hub_f03.run_query("为什么 2026 年 9 月增长这么快 sk-query2Secret7777")
        ev_text_f03 = ev_f03.read_text(encoding="utf-8")
        llm_text_f03 = llm_f03.read_text(encoding="utf-8") if llm_f03.exists() else ""
        check(
            "F03_hub_query_return_and_event_leak",
            ("sk-questionSecret9999" not in json.dumps(ans1, ensure_ascii=False))
            and ("sk-sqlSecret12345678" not in json.dumps(ans1, ensure_ascii=False))
            and ("sk-upstreamSecret8888" not in json.dumps(ans2, ensure_ascii=False))
            and ("sk-upstreamSecret8888" not in llm_text_f03),
            {
                "ans1_status": ans1["status"],
                "ans2_status": ans2["status"],
                "question_secret_in_return": "sk-questionSecret9999" in json.dumps(ans1, ensure_ascii=False),
                "sql_secret_in_return": "sk-sqlSecret12345678" in json.dumps(ans1, ensure_ascii=False),
                "note_secret_in_return": "sk-noteSecret12345678" in json.dumps(ans1, ensure_ascii=False),
                "upstream_secret_in_ans2_return": "sk-upstreamSecret8888" in json.dumps(ans2, ensure_ascii=False),
                "upstream_secret_in_events": "sk-upstreamSecret8888" in ev_text_f03,
                "upstream_secret_in_llm_log": "sk-upstreamSecret8888" in llm_text_f03,
            },
        )

        # F04: Hub.run_report with secret inside replay_text AND inside LLM JSON error
        ev_f04 = tmp / "events_f04.jsonl"
        llm_f04 = tmp / "llm_f04.jsonl"
        f04_bad_payload = json.dumps({
            "explanation": "本周商品金额为 {{F01}}，密钥 sk-reportBodySecret12345。",
            "hypotheses": ["待验证：需结合结构数据。"],
            "actions": ["继续跟踪。"],
        })
        cl_f04 = C.LLMClient(
            cfg=cfg_f03,
            transport=C.fixture_transport([
                mk_resp(f04_bad_payload),
                mk_resp(f04_bad_payload),
                mk_resp(f04_bad_payload),
                mk_resp(f04_bad_payload),
            ]),
            mode="live",
            log_path=llm_f04,
            sleep=lambda _: None,
        )
        hub_f04 = I.Hub(client=cl_f04, use_llm=True, events=ev_f04)
        rep_replay, ev_rep_replay = hub_f04.run_report(
            mode="replay",
            replay_text=json.dumps({
                "explanation": "本周商品金额 {{F01}}，包含秘密 sk-replaySecret123456。",
                "hypotheses": ["待验证：无"],
                "actions": ["继续观察。"],
            }),
        )
        rep_live, ev_rep_live = hub_f04.run_report(mode="live")
        f04_ev_text = ev_f04.read_text(encoding="utf-8")
        check(
            "F04_hub_report_secret_leak",
            ("sk-replaySecret123456" not in json.dumps(rep_replay, ensure_ascii=False))
            and ("sk-reportBodySecret12345" not in json.dumps(rep_live, ensure_ascii=False))
            and ("sk-replaySecret123456" not in f04_ev_text)
            and ("sk-reportBodySecret12345" not in f04_ev_text),
            {
                "replay_mode": rep_replay["mode"],
                "replay_secret_in_return": "sk-replaySecret123456" in json.dumps(rep_replay, ensure_ascii=False),
                "live_mode": rep_live["mode"],
                "live_secret_in_return": "sk-reportBodySecret12345" in json.dumps(rep_live, ensure_ascii=False),
                "replay_secret_in_events": "sk-replaySecret123456" in f04_ev_text,
                "live_secret_in_events": "sk-reportBodySecret12345" in f04_ev_text,
            },
        )

        # F05: Hub.run_agent secrets in request_id / LLM copy / DraftStore / customer_id PII in events
        ev_f05 = tmp / "events_f05.jsonl"
        llm_f05 = tmp / "llm_f05.jsonl"
        store_f05 = DraftStore(tmp / "drafts_f05.sqlite")
        cl_f05 = C.LLMClient(
            cfg=cfg_f03,
            transport=C.fixture_transport([
                mk_resp(json.dumps({
                    "action": "coupon",
                    "discount": 0.05,
                    "rationale": "secret sk-rationaleSecret12345",
                    "evidence": ["doc:retention_policy#5-模型的使用@retention-policy-v1"],
                })),
                mk_resp(json.dumps({
                    "copy": "您好，送上 5% 专属优惠，客服密钥 sk-copyAlphaSecretXYZ，欢迎选购。",
                })),
            ]),
            mode="live",
            log_path=llm_f05,
            sleep=lambda _: None,
        )
        hub_f05 = I.Hub(client=cl_f05, use_llm=True, events=ev_f05)
        ag_res, ev_ag = hub_f05.run_agent(
            {
                "request_id": "req-sk-requestIdSecret12345",
                "customer_id": "customer_000001",
                "context": {"consent": True, "operator_token": "Bearer opSecretTok999"},
            },
            store=store_f05,
        )
        ev_text_f05 = ev_f05.read_text(encoding="utf-8")
        draft_stored = store_f05.get(ag_res["draft"]["draft_id"])
        check(
            "F05_hub_agent_secrets_and_customer_pii",
            ("sk-copyAlphaSecretXYZ" not in json.dumps(ag_res, ensure_ascii=False))
            and ("sk-requestIdSecret12345" not in json.dumps(ag_res, ensure_ascii=False))
            and ("customer_000001" not in ev_text_f05),
            {
                "draft_mode": ag_res["draft"]["mode"],
                "request_id_redacted_in_events": "sk-requestIdSecret12345" not in ev_text_f05,
                "request_id_in_draft_db": draft_stored["request_id"],
                "copy_secret_in_draft_db": "sk-copyAlphaSecretXYZ" in draft_stored["copy"],
                "rationale_secret_in_return": "sk-rationaleSecret12345" in json.dumps(ag_res, ensure_ascii=False),
                "customer_id_logged_in_events": "customer_000001" in ev_text_f05,
                "ev_ag_evidence_ids": ev_ag.get("evidence_ids"),
            },
        )

        # F06: Does llm_calls.jsonl ever log raw prompt text or full responses?
        llm_log_combined = (llm_log_f02.read_text(encoding="utf-8") if llm_log_f02.exists() else "") + (
            llm_f05.read_text(encoding="utf-8") if llm_f05.exists() else ""
        )
        check(
            "F06_llm_log_no_raw_prompts_or_pii",
            ("prompt_sha256" in llm_log_combined)
            and ("sk-promptSecret123456" not in llm_log_combined)
            and ("customer_000001" not in llm_log_combined),
            {
                "has_prompt_sha256": "prompt_sha256" in llm_log_combined,
                "prompt_secret_in_llm_log": "sk-promptSecret123456" in llm_log_combined,
                "customer_id_in_llm_log": "customer_000001" in llm_log_combined,
            },
        )

        # F07: Hub(use_llm=False) linkage & shared session bug check
        # What happens if a caller passes an existing QA.Session(use_llm=True) to Hub(use_llm=False)?
        ev_f07 = tmp / "events_f07.jsonl"
        llm_f07 = tmp / "llm_f07.jsonl"
        cl_f07 = C.LLMClient(
            cfg=cfg_f03,
            transport=C.fixture_transport([
                mk_resp(json.dumps({"supported": False, "reason": "test llm was called despite Hub(use_llm=False)"})),
            ]),
            mode="live",
            log_path=llm_f07,
            sleep=lambda _: None,
        )
        hub_off = I.Hub(client=cl_f07, use_llm=False, events=ev_f07)
        pre_session = QA.Session("ext", use_llm=True, client=cl_f07)
        a_off, ev_off = hub_off.run_query("为什么 2026 年 10 月增长这么快？", session=pre_session)
        r_rep_off, ev_rep_off = hub_off.run_report(mode="live")
        r_ag_off, ev_ag_off = hub_off.run_agent({"customer_id": "customer_000001", "context": {"consent": True}}, store=DraftStore(tmp / "d07.sqlite"))
        check(
            "F07_hub_use_llm_false_overrides_session",
            cl_f07.calls == 0 and ev_off["llm"]["calls"] == 0,
            {
                "llm_calls_when_hub_use_llm_false": cl_f07.calls,
                "query_ev_mode": ev_off["mode"],
                "query_ev_llm": ev_off["llm"],
                "report_ev_mode": ev_rep_off["mode"],
                "agent_ev_mode": ev_ag_off["mode"],
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
