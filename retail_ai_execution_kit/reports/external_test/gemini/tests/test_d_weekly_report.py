"""Group D adversarial test: Weekly Report validation, final_check, and repair fallback.

Uses an injected fake LLM client (0 real LLM calls) to test whether validate_llm(),
final_check(), and generate_weekly_report() block disguised digits, wrong contexts,
wrong currencies, unfounded causal claims, unavailable fields, cutoff violations,
zero-width obfuscation, and >2 repair fallback.
Run from retail_ai_execution_kit/:
    .venv/bin/python reports/external_test/gemini/tests/test_d_weekly_report.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src/retail_bi/ai"))

import report_facts as RF  # noqa: E402
import report_generator as RG  # noqa: E402


class FakeClient:
    def __init__(self, payloads: list[str | dict]):
        self.payloads = list(payloads)
        self.calls = 0
        self.history = []

    def chat(self, messages, *, json_schema=None, max_tokens=400, purpose="unspecified"):
        idx = min(self.calls, len(self.payloads) - 1)
        self.calls += 1
        self.history.append({"purpose": purpose, "messages": messages})
        item = self.payloads[idx]
        text = json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item)
        out = {
            "status": "ok",
            "mode": "live",
            "model": "fake-model",
            "text": text,
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "cost_usd": 0.0},
        }
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


def make_body(explanation: str, actions=None, hypotheses=None) -> dict:
    return {
        "explanation": explanation,
        "actions": actions or ["保持跟踪本周商品金额 {{F01}} 的变化趋势。", "下周复核订单与客单价结构。"],
        "hypotheses": hypotheses or ["待验证：需结合品类结构分析变化。"],
    }


def main() -> int:
    facts = RF.build_weekly_facts()
    assert facts["status"] == "ok"
    sel = RG.pick_facts(facts)

    # Pairs: (id, should_be_blocked, body_dict, note)
    cases = [
        # Hardcoded digits (control + adversarial)
        ("D01_ascii_digit_control", True, make_body("本周商品金额达到 12345 USD。"), "ASCII digits should be blocked"),
        ("D02_fullwidth_digits", True, make_body("本周商品金额达到 １２３４５．６７ USD，订单稳定。"), "Full-width digits １２３ without ％"),
        ("D03_circled_roman_numerals", True, make_body("本周存在②大核心波动，整体处于Ⅴ级水平，环比翻了Ⅱ倍。"), "Circled/Roman numerals"),
        ("D04_cn_num_unlisted_suffix", True, make_body("本周共成交五百余笔订单，增长百分之二十，占比十分之三，呈现三条规律。"), "Chinese numbers with unlisted suffixes (笔/百分之/条/十分之)"),
        ("D05_cn_financial_numerals", True, make_body("本周商品金额约为叁万捌仟USD，订单量约贰佰笔。"), "Uppercase Chinese financial numerals 叁万/贰佰"),

        # Placeholders
        ("D06_unknown_placeholder", True, make_body("本周商品金额为 {{F99}}。"), "Unknown placeholder control"),
        ("D07_malformed_placeholder", True, make_body("本周商品金额为 {F01} 或 {{F1}}。"), "Malformed placeholder braces/digits"),
        ("D08_wrong_context_orders_as_money", True, make_body("本周商品金额合计达到 {{F02}}，客单价为 {{F04}}。"), "Order count {{F02}} presented as sales; ratio {{F04}} as AOV"),
        ("D09_unit_before_placeholder", True, make_body("本周有效订单总额约美元 {{F02}}，共成交 {{F01}} 笔。"), "Unit placed BEFORE placeholder + unlisted unit 笔"),

        # Currency
        ("D10_wrong_currency_rmb_control", True, make_body("本周商品金额折合人民币较高，约为 {{F01}}。"), "RMB control"),
        ("D11_wrong_currency_cny_meijin", True, make_body("本周商品金额以 CNY 计价或按美金核算均表现平稳。"), "CNY / 美金"),
        ("D12_false_positive_yuan_word", False, make_body("本周多维度多元化商品结构表现平稳，各业务单元稳定运行，商品金额为 {{F01}}。"), "Legitimate Chinese words containing '元' (多元/单元) shouldn't be flagged as currency"),

        # Unfounded causation
        ("D13_causal_control", True, make_body("因为本周开展活动，所以商品金额为 {{F01}}。"), "Explicit '因为' control"),
        ("D14_causal_synonyms", True, make_body("老客集中复购拉动了本周商品金额 {{F01}}，节假日效应推高了客单价，源于前期蓄水促使订单走强。"), "Causal synonyms 拉动/推高/源于/促使"),
        ("D15_causal_in_actions", True, make_body("本周商品金额为 {{F01}}。", actions=["因为前期活动效果好，建议下周继续保持。", "继续观察订单变化。"]), "Causal assertion placed in actions instead of explanation"),

        # Unavailable fields
        ("D16_unavail_control", True, make_body("本周各渠道和库存表现带动商品金额 {{F01}}。"), "渠道/库存 control"),
        ("D17_unavail_synonyms", True, make_body("建议重点分析净利润、ROI、退货率与转化率，并结合供应商成本、用户年龄与性别优化投放。"), "Unavailable synonyms 净利润/ROI/退货/转化率/供应商/成本/年龄/性别/投放"),

        # Last day / partial month / post-cutoff
        ("D18_tail_day_control", True, make_body("截止前最后一天使本周商品金额出现明显下降。"), "最后一天 control"),
        ("D19_tail_day_paraphrase", True, make_body("截止前开放尾日订单并入本周后，拉低了本周客单价表现。"), "Paraphrased tail day 尾日 + 并入/拉低"),
        ("D20_tail_day_neg_and_claim", True, make_body("虽然最后一天不在本周，但它仍使本周整体数据被低估。"), "Negation + false claim in same sentence"),
        ("D21_post_cutoff_claim", True, make_body("截至截止日之后的最新数据显示，本周商品金额已达 {{F01}}。"), "Post-cutoff claim"),
        ("D22_partial_month_paraphrase", True, make_body("本月目前表现显著弱于上个月，当月仍落后于全月水平。"), "Partial vs full month using 弱于/落后于"),

        # Obfuscation with zero-width characters / HTML
        ("D23_zero_width_obfuscation", True, make_body("因\u200b为促\u200b销导\u200b致渠\u200b道毛\u200b利和库\u200b存提升，人\u200b民\u200b币约三\u200b成，合五\u200b十\u200b万USD。"), "Zero-width space breaking regex checks without triggering ASCII digits or 元"),
        ("D24_html_hidden_tag_text", True, make_body("本周商品金额为 {{F01}}<!-- 隐藏：因为促销导致毛利和库存上升三成 -->，整体平稳。"), "HTML comment containing causal claim/unavailable fields/三成? Wait 三成 caught unless zero-width; test HTML comment"),
        ("D24b_markdown_link_hidden", True, make_body("本周商品金额为 {{F01}}，[查看详情](https://example.com/report) 表现稳健。"), "External markdown link injected into report body"),
    ]

    results = []
    for cid, should_block, body, note in cases:
        # Test validate_llm directly AND generate_weekly_report end-to-end (3 identical bad responses -> must fallback to template if blocked!)
        val_errs = RG.validate_llm(body, sel)
        fc = FakeClient([body, body, body])
        gen = RG.generate_weekly_report(facts=facts, client=fc, mode="live")
        actually_blocked = (len(val_errs) > 0) or (gen["mode"] == "template")
        bypassed = should_block and (gen["mode"] == "live")
        false_pos = (not should_block) and (gen["mode"] != "live")
        results.append({
            "id": cid,
            "should_block": should_block,
            "val_errs": val_errs,
            "final_mode": gen["mode"],
            "final_check_errors": gen["final_check_errors"],
            "bypassed": bypassed,
            "false_positive": false_pos,
            "passed": (not bypassed) and (not false_pos),
            "note": note,
            "input_text": body["explanation"] if not (cid in ("D15_causal_in_actions",)) else body,
        })

    # Test D25: direct final_check() test with version/evidence hex digit pollution
    polluted_body = make_body("本周共有 559048 笔异常，涉及 84 个品类，比前 17 周多了 31 笔。")
    assembled_polluted = RG.assemble(facts, sel, polluted_body, "live", [], [])
    fc_errs = RG.final_check(assembled_polluted, sel, facts)

    # Test D26: repair > MAX_REPAIRS (2) fallback behavior + repair succeeds on 3rd attempt
    bad = make_body("本周商品金额 999 USD。")
    good = make_body("本周商品金额为 {{F01}}，有效订单为 {{F02}}，环比 {{F04}}。")
    fc_fail3 = FakeClient([bad, bad, bad])
    r_fail3 = RG.generate_weekly_report(facts=facts, client=fc_fail3, mode="live")
    fc_fix2 = FakeClient([bad, bad, good])
    r_fix2 = RG.generate_weekly_report(facts=facts, client=fc_fix2, mode="live")

    # Test D27: replay mode check & template numeric provenance
    r_tmpl = RG.generate_weekly_report(facts=facts, mode="template")

    summary = {
        "total_cases": len(results) + 4,
        "attack_cases": len(results),
        "attack_passed": sum(1 for r in results if r["passed"]),
        "bypasses": [r for r in results if r["bypassed"]],
        "false_positives": [r for r in results if r["false_positive"]],
        "final_check_hex_pollution_test": {
            "input": polluted_body["explanation"],
            "final_check_errors": fc_errs,
            "passed": len(fc_errs) > 0,
        },
        "repair_fallback_after_3_attempts": {
            "attempts": len(r_fail3["attempts"]),
            "calls": fc_fail3.calls,
            "mode": r_fail3["mode"],
            "llm_body_is_none": r_fail3["llm_body"] is None,
            "passed": r_fail3["mode"] == "template" and len(r_fail3["attempts"]) == 3 and r_fail3["llm_body"] is None,
        },
        "repair_succeeds_on_3rd_attempt": {
            "attempts": len(r_fix2["attempts"]),
            "calls": fc_fix2.calls,
            "mode": r_fix2["mode"],
            "passed": r_fix2["mode"] == "live" and len(r_fix2["attempts"]) == 3 and not r_fix2["final_check_errors"],
        },
        "template_final_check": {
            "status": r_tmpl["status"],
            "mode": r_tmpl["mode"],
            "final_check_errors": r_tmpl["final_check_errors"],
            "passed": r_tmpl["status"] == "ok" and not r_tmpl["final_check_errors"],
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
