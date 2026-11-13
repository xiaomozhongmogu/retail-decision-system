"""Group E adversarial test: Retention Agent, Policy Engine, and DraftStore boundaries.

Uses fake LLM clients (0 real LLM calls) and temporary SQLite DraftStore paths.
Run from retail_ai_execution_kit/:
    .venv/bin/python reports/external_test/gemini/tests/test_e_retention_agent.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src/retail_bi/ai"))
sys.path.insert(0, str(ROOT / "src/retail_bi/warehouse"))

import policy_engine as PE  # noqa: E402
import retention_agent as RA  # noqa: E402
from drafts import DraftStore  # noqa: E402


class FakeClient:
    def __init__(self, responses: list):
        self.responses = list(responses)
        self.calls = 0

    def chat(self, messages, *, json_schema=None, max_tokens=200, purpose="unspecified"):
        idx = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        item = self.responses[idx]
        if isinstance(item, Exception):
            return {"status": "error", "mode": "live", "error": {"code": "llm_unavailable", "message": str(item), "retryable": True}}
        text = json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item)
        out = {"status": "ok", "mode": "live", "model": "fake", "text": text, "usage": {"prompt_tokens": 50, "completion_tokens": 20, "cost_usd": 0.0}}
        if json_schema:
            try:
                obj = json.loads(text)
                missing = [k for k in json_schema.get("required", []) if k not in obj]
                if missing:
                    raise ValueError(f"missing {missing}")
                out["json"] = obj
            except Exception as e:
                out["status"] = "error"
                out["error"] = {"code": "invalid_output", "message": str(e), "retryable": False}
        return out

    def budget(self):
        return {"calls": self.calls, "max_calls": 50, "cost_usd": 0.0, "max_cost_usd": 0.5, "tokens_in": 0, "tokens_out": 0}


def run_case(store, cid, ctx, responses, spent=0.0, req_id=None, use_llm=True):
    fc = FakeClient(responses)
    ag = RA.RetentionAgent(store, client=fc, use_llm=use_llm)
    req = {"customer_id": cid, "context": ctx, "spent_usd": spent}
    if req_id:
        req["request_id"] = req_id
    return ag.run(req)


def main() -> int:
    results = []
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        def check(cid, cond, detail):
            results.append({"id": cid, "passed": bool(cond), "detail": detail})

        # E01: Over-cap discount proposed by LLM for lapsed_normal (cap 5%) -> capped at 0.05
        s = DraftStore(tmp / "e01.sqlite")
        r = run_case(s, "customer_000005", {"consent": True}, [
            {"action": "coupon", "discount": 0.45, "rationale": "give big discount", "evidence": []},
            {"copy": "您好，为您准备了 5% 专属优惠，欢迎选购。"},
        ])
        check("E01_over_cap_lapsed_normal",
              r["state"] == "draft_saved" and r["decision"]["decision"] == "modify"
              and r["decision"]["action"]["discount"] == 0.05 and not r["sent"] and not r["draft"]["sent"]
              and len(r["trace"]) <= 8,
              {"state": r["state"], "discount": r["decision"]["action"]["discount"], "steps": len(r["trace"])})

        # E02: Extreme discount (0.9) rejected by _propose -> rule fallback (0.05)
        r = run_case(s, "customer_000005", {"consent": True}, [
            {"action": "coupon", "discount": 0.90, "rationale": "90% off", "evidence": []},
            {"copy": "您好，为您准备了 5% 专属优惠，欢迎选购。"},
        ])
        check("E02_extreme_discount_fallback",
              r["state"] == "draft_saved" and r["proposal"]["mode"] == "rule_fallback"
              and r["decision"]["action"]["discount"] == 0.05 and len(r["trace"]) <= 8,
              {"proposal": r["proposal"], "discount": r["decision"]["action"]["discount"]})

        # E03: Zero gross margin -> discount cap 0 -> downgraded to reminder; and margin=0.05 -> 2.5% rounding check
        r0 = run_case(s, "customer_000001", {"consent": True, "gross_margin": 0.0}, [
            {"action": "coupon", "discount": 0.1, "rationale": "coupon", "evidence": []},
            {"copy": "您好，欢迎回来看看新品。"},
        ])
        check("E03a_zero_margin_to_reminder",
              r0["state"] == "draft_saved" and r0["decision"]["action"]["type"] == "reminder" and r0["decision"]["action"]["discount"] == 0.0,
              {"action": r0["decision"]["action"], "reasons": r0["decision"]["reasons"]})

        r_half = run_case(s, "customer_000001", {"consent": True, "gross_margin": 0.05}, [
            {"action": "coupon", "discount": 0.05, "rationale": "coupon", "evidence": []},
            "not json -> trigger template copy",
        ])
        check("E03b_half_percent_template_rounding",
              "2.5%" in r_half["draft"]["copy"],
              {"discount": r_half["decision"]["action"]["discount"], "template_copy": r_half["draft"]["copy"]})

        # E04: No consent (None & False) even with LLM proposing coupon
        r_nc1 = run_case(s, "customer_000001", {}, [{"action": "coupon", "discount": 0.1, "rationale": "x", "evidence": []}])
        r_nc2 = run_case(s, "customer_000001", {"consent": False}, [{"action": "coupon", "discount": 0.1, "rationale": "x", "evidence": []}])
        check("E04_no_consent_denied",
              r_nc1["state"] == "not_eligible" and r_nc2["state"] == "not_eligible" and not r_nc1["sent"],
              {"none_state": r_nc1["state"], "false_state": r_nc2["state"]})

        # E05: Open complaint -> denied
        r_cmp = run_case(s, "customer_000001", {"consent": True, "open_complaint": True}, [{"action": "coupon", "discount": 0.1, "rationale": "x", "evidence": []}])
        check("E05_open_complaint_denied", r_cmp["state"] == "not_eligible", {"state": r_cmp["state"], "reasons": r_cmp["decision"]["reasons"]})

        # E06: Frequency limit (contacts=2; gap=6; negative contacts=-1)
        r_f1 = run_case(s, "customer_000001", {"consent": True, "contacts_last_30d": 2, "days_since_last_contact": 14},
                        [{"action": "reminder", "discount": 0.0, "rationale": "x", "evidence": []}])
        r_f2 = run_case(s, "customer_000001", {"consent": True, "contacts_last_30d": 1, "days_since_last_contact": 6},
                        [{"action": "reminder", "discount": 0.0, "rationale": "x", "evidence": []}])
        r_fneg = run_case(s, "customer_000001", {"consent": True, "contacts_last_30d": -1},
                          [{"action": "reminder", "discount": 0.0, "rationale": "x", "evidence": []}, {"copy": "您好，新品已上架。"}])
        check("E06_frequency_and_negative_count",
              r_f1["state"] == "not_eligible" and r_f2["state"] == "not_eligible",
              {"max_contacts": r_f1["state"], "min_gap_6d": r_f2["state"], "negative_contacts_state": r_fneg["state"]})

        # E07: Weekly budget ($199.96 + $0.05) AND per-customer cost cap ($20 on customer_003591 AOV $958.44 at 15% = $143.82)
        r_wb = run_case(s, "customer_000001", {"consent": True}, [{"action": "reminder", "discount": 0.0, "rationale": "x", "evidence": []}], spent=199.96)
        r_pc = run_case(s, "customer_003591", {"consent": True}, [{"action": "coupon", "discount": 0.15, "rationale": "x", "evidence": []}], spent=0.0)
        check("E07_budget_and_per_customer_cap",
              r_wb["state"] == "budget_denied" and r_pc["state"] == "budget_denied",
              {"weekly_budget": r_wb["state"], "per_customer_cap": r_pc["state"], "pc_reasons": r_pc["decision"]["reasons"]})

        # E08: Non-existent customer & dim_customer without valid purchase -> unknown_customer, 0 LLM calls
        fc_u1 = FakeClient([{"action": "coupon", "discount": 0.1, "rationale": "x", "evidence": []}])
        r_u1 = RA.RetentionAgent(s, client=fc_u1, use_llm=True).run({"customer_id": "customer_888888", "context": {"consent": True}})
        fc_u2 = FakeClient([{"action": "coupon", "discount": 0.1, "rationale": "x", "evidence": []}])
        r_u2 = RA.RetentionAgent(s, client=fc_u2, use_llm=True).run({"customer_id": "customer_000004", "context": {"consent": True}})
        check("E08_unknown_or_no_purchase_customer",
              r_u1["state"] == "unknown_customer" and r_u2["state"] == "unknown_customer" and fc_u1.calls == 0 and fc_u2.calls == 0,
              {"u1": r_u1["state"], "u2": r_u2["state"], "calls": (fc_u1.calls, fc_u2.calls)})

        # E09: Fake action/tool injection in LLM JSON ("send_email" / "issue_coupon")
        r_fake_act = run_case(s, "customer_000001", {"consent": True}, [
            {"action": "send_email_now", "tool": "issue_coupon", "sent": True, "discount": 0.1, "rationale": "send now", "evidence": []},
            {"copy": "您好，为您准备了 5% 专属优惠，欢迎回来看看。"},
        ])
        check("E09_fake_action_rejected",
              r_fake_act["proposal"]["mode"] == "rule_fallback" and not r_fake_act["sent"] and not r_fake_act["draft"]["sent"],
              {"proposal": r_fake_act["proposal"], "sent": r_fake_act["sent"]})

        # E10: Malformed JSON / non-dict JSON -> safe fallback
        r_bad_json = run_case(s, "customer_000001", {"consent": True}, ["{not valid json", "still bad json"])
        check("E10_malformed_json_fallback",
              r_bad_json["state"] == "draft_saved" and r_bad_json["proposal"]["mode"] == "rule_fallback" and r_bad_json["draft"]["mode"] == "template_fallback",
              {"state": r_bad_json["state"], "prop_mode": r_bad_json["proposal"]["mode"], "draft_mode": r_bad_json["draft"]["mode"]})

        # E11: Unhashable element inside evidence list -> must NOT raise unhandled TypeError
        try:
            r_unhash = run_case(s, "customer_000001", {"consent": True}, [
                {"action": "coupon", "discount": 0.05, "rationale": "x", "evidence": [["nested"]]},
                {"copy": "您好，为您准备了 5% 专属优惠。"},
            ])
            e11_ok = r_unhash["state"] == "draft_saved"
            e11_detail = {"state": r_unhash["state"]}
        except Exception as exc:
            e11_ok = False
            e11_detail = {"exception": f"{type(exc).__name__}: {exc}"}
        check("E11_unhashable_evidence_no_crash", e11_ok, e11_detail)

        # E12: Deceptive copy smuggling in _copy()
        # E12a: New customer (action downgraded to reminder!) with LLM claiming "已为您发放优惠券"
        r_smuggle_rem = run_case(s, "customer_000476", {"consent": True}, [
            {"action": "coupon", "discount": 0.1, "rationale": "new user", "evidence": []},
            {"copy": "尊敬的客户，已为您发放优惠券，请及时下单使用！"},
        ])
        # E12b: Coupon 5% with LLM claiming "已为您发放 5% 优惠券，下单即送 5 元"
        r_smuggle_cpn = run_case(s, "customer_000001", {"consent": True}, [
            {"action": "coupon", "discount": 0.05, "rationale": "dormant", "evidence": []},
            {"copy": "已为您发放 5% 优惠券并激活 5 元立减，请立即使用！"},
        ])
        # E12c: Reminder with Chinese numeral discount claim "立享五折，立减五十元"
        r_smuggle_cn = run_case(s, "customer_000476", {"consent": True}, [
            {"action": "reminder", "discount": 0.0, "rationale": "remind", "evidence": []},
            {"copy": "好久不见，下单立享五折并立减五十元！"},
        ])
        check("E12a_copy_blocks_issued_coupon_claim_on_reminder",
              r_smuggle_rem["draft"]["mode"] == "template_fallback",
              {"mode": r_smuggle_rem["draft"]["mode"], "saved_copy": r_smuggle_rem["draft"]["copy"], "action": r_smuggle_rem["draft"]["action"]})
        check("E12b_copy_blocks_issued_coupon_and_yuan_on_coupon",
              r_smuggle_cpn["draft"]["mode"] == "template_fallback",
              {"mode": r_smuggle_cpn["draft"]["mode"], "saved_copy": r_smuggle_cpn["draft"]["copy"], "action": r_smuggle_cpn["draft"]["action"]})
        check("E12c_copy_blocks_chinese_numeral_discount_promise",
              r_smuggle_cn["draft"]["mode"] == "template_fallback",
              {"mode": r_smuggle_cn["draft"]["mode"], "saved_copy": r_smuggle_cn["draft"]["copy"], "action": r_smuggle_cn["draft"]["action"]})

        # E13: Idempotency & Conflict + LLM non-determinism on retry
        s_idem = DraftStore(tmp / "idem.sqlite")
        a1 = RA.RetentionAgent(s_idem, use_llm=False).run({"request_id": "req-idem-1", "customer_id": "customer_000001", "context": {"consent": True}})
        a2 = RA.RetentionAgent(s_idem, use_llm=False).run({"request_id": "req-idem-1", "customer_id": "customer_000001", "context": {"consent": True}})
        a3 = RA.RetentionAgent(s_idem, use_llm=False).run({"request_id": "req-idem-1", "customer_id": "customer_000005", "context": {"consent": True}})
        # Retry same request_id with live LLM producing slightly different copy
        b1 = run_case(s_idem, "customer_000001", {"consent": True}, [{"action": "coupon", "discount": 0.05, "rationale": "a", "evidence": []}, {"copy": "您好，送上 5% 专属优惠。"}], req_id="req-idem-llm")
        b2 = run_case(s_idem, "customer_000001", {"consent": True}, [{"action": "coupon", "discount": 0.05, "rationale": "a", "evidence": []}, {"copy": "好久不见，欢迎领取 5% 优惠。"}], req_id="req-idem-llm")
        check("E13_idempotency_and_conflict",
              a1["state"] == "draft_saved" and a2["state"] == "draft_saved" and not a2["draft_created"]
              and len(s_idem.list()) == 2 and a3["state"] == "tool_failure" and a3["error"]["code"] == "idempotency_conflict",
              {"a2_created": a2["draft_created"], "a3_code": a3.get("error", {}).get("code"), "b2_state": b2["state"], "b2_error": b2.get("error")})

        # E14: Reviewed / rejected / withdrawn drafts cannot be modified or re-reviewed
        did = a1["draft"]["draft_id"]
        rev_ok = s_idem.review(did, "approved", reviewer="tester")
        rev_again = s_idem.review(did, "rejected", reviewer="tester2")
        revise_after = s_idem.revise(did, "hacked copy", editor="tester2")
        withdraw_after = s_idem.withdraw(did, by="tester2")
        # Revise pending_review draft with deceptive copy
        did2 = b1["draft"]["draft_id"]
        revise_pending = s_idem.revise(did2, "保证一定免费返现100元", editor="editor1")
        check("E14_reviewed_draft_immutable",
              rev_ok["status"] == "ok" and not rev_ok["data"]["sent"]
              and rev_again["status"] == "error" and rev_again["error"]["code"] == "invalid_state"
              and revise_after["status"] == "error" and revise_after["error"]["code"] == "invalid_state"
              and withdraw_after["status"] == "error" and withdraw_after["error"]["code"] == "invalid_state"
              and s_idem.get(did)["status"] == "approved" and not s_idem.get(did)["sent"],
              {"rev_again": rev_again["error"]["code"], "revise_after": revise_after["error"]["code"],
               "withdraw_after": withdraw_after["error"]["code"], "revise_pending_unvalidated": revise_pending["status"]})

        # E15: Model probability does NOT affect policy_engine decision
        base_c = {"recency_days": 45, "frequency_90d": 1, "monetary_90d_usd": 100.0, "orders_all_time": 1,
                  "merch_all_time_usd": 100.0, "tenure_days": 45, "lifecycle_state": "active", "applicability": "in_population", "return_rate": None}
        d_low = PE.decide({**base_c, "p_repurchase_30d": 0.01}, {"type": "coupon", "discount": 0.1}, {"consent": True}, {"spent_usd": 0})
        d_high = PE.decide({**base_c, "p_repurchase_30d": 0.99}, {"type": "coupon", "discount": 0.1}, {"consent": True}, {"spent_usd": 0})
        check("E15_model_prob_ignored_by_policy",
              d_low["data"]["decision"] == d_high["data"]["decision"]
              and d_low["data"]["action"] == d_high["data"]["action"]
              and d_low["data"]["cost_usd"] == d_high["data"]["cost_usd"],
              {"low": d_low["data"]["action"], "high": d_high["data"]["action"]})

    print(json.dumps({
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failures": [r for r in results if not r["passed"]],
        "all_results": results,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
