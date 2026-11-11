"""AI-11 verification: boundary fixtures for eligibility, discount caps, frequency and budget, plus a real
weekly-list batch over the latest published snapshot (offline, read-only). Writes reports/ai/policy_checks.json.
usage: .venv/bin/python evidence/AI-11/policy_checks.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/ai'))
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
import policy_engine as PE  # noqa: E402
from runtime import open_current  # noqa: E402

P = PE.load_policy()
res = []


def check(name, cond, detail=''):
    res.append({'check': name, 'status': 'passed' if cond else 'failed', 'detail': str(detail)[:300]})
    print('PASS' if cond else 'FAIL', name, detail if not cond else '')


HV = {'customer_id': 'hv', 'recency_days': 45, 'frequency_90d': 2, 'monetary_90d_usd': 300.0, 'orders_all_time': 5, 'merch_all_time_usd': 800.0,
      'tenure_days': 400, 'lifecycle_state': 'at_risk', 'applicability': 'in_population', 'p_repurchase_30d': 0.4, 'return_rate': None}
NV = {**HV, 'customer_id': 'nv', 'frequency_90d': 1, 'monetary_90d_usd': 80.0}
OK = {'consent': True}
coupon = lambda d: {'type': 'coupon', 'discount': d}  # noqa: E731
D = lambda c, a, ctx=OK, b=None: PE.decide(c, a, ctx, b, P)['data']  # noqa: E731

check('config parsed from knowledge/retention_policy.md', P['policy_version'] == 'retention-policy-v1')
check('tier boundary: 2 orders in 90d -> high; 1 order and 203.18 USD -> normal; 203.19 USD -> high',
      PE.value_tier(HV, P) == 'high' and PE.value_tier({**NV, 'monetary_90d_usd': 203.18}, P) == 'normal' and PE.value_tier({**NV, 'monetary_90d_usd': 203.19}, P) == 'high')
check('lapsed tiers: no purchase in 90d split by history', PE.value_tier({**HV, 'frequency_90d': 0, 'monetary_90d_usd': 0}, P) == 'lapsed_high'
      and PE.value_tier({**HV, 'frequency_90d': 0, 'monetary_90d_usd': 0, 'orders_all_time': 1, 'merch_all_time_usd': 299.99}, P) == 'lapsed_normal')
r = D(HV, coupon(0.10))
check('discount exactly at the high-value cap (10%) is allowed unchanged', r['decision'] == 'allow' and r['action']['discount'] == 0.10, r['reasons'])
r = D(HV, coupon(0.11))
check('discount above the cap is lowered to the cap (modify)', r['decision'] == 'modify' and r['action']['discount'] == 0.10, r['reasons'])
r = D(NV, coupon(0.10))
check('normal tier cap is 5%', r['decision'] == 'modify' and r['action']['discount'] == 0.05)
r = D({**HV, 'frequency_90d': 0, 'monetary_90d_usd': 0, 'lifecycle_state': 'dormant'}, coupon(0.20), {**OK, 'gross_margin': 0.20})
check('margin cap binds below tier cap (lapsed_high 15% vs margin 20% x 0.5 = 10%)', r['action']['discount'] == 0.10, r['reasons'])
r1, r2 = D({**HV, 'p_repurchase_30d': 0.05}, coupon(0.10)), D({**HV, 'p_repurchase_30d': 0.95}, coupon(0.10))
check('risk does not raise the discount: p=0.05 and p=0.95 get the same action and cost', r1['action'] == r2['action'] and r1['cost_usd'] == r2['cost_usd']
      and r1['model_reference']['used_for_decision'] is False)
r = D({**HV, 'applicability': 'out_of_population', 'p_repurchase_30d': None, 'frequency_90d': 0, 'monetary_90d_usd': 0}, coupon(0.05))
check('out-of-population customer is decided by rules without a model probability', r['decision'] == 'allow' and r['model_reference']['p_repurchase_30d'] is None)
check('consent unknown (default) -> deny not_eligible', D(HV, coupon(0.05), {})['code'] == 'not_eligible')
check('consent false -> deny', D(HV, coupon(0.05), {'consent': False})['decision'] == 'deny')
check('open complaint -> deny', D(HV, {'type': 'reminder'}, {**OK, 'open_complaint': True})['decision'] == 'deny')
check('frequency: 1 contact in 30 days allowed, 2 (= cap) denied', D(HV, {'type': 'reminder'}, {**OK, 'contacts_last_30d': 1, 'days_since_last_contact': 10})['decision'] == 'allow'
      and D(HV, {'type': 'reminder'}, {**OK, 'contacts_last_30d': 2, 'days_since_last_contact': 10})['decision'] == 'deny')
check('gap: 7 days allowed, 6 days denied', D(HV, {'type': 'reminder'}, {**OK, 'contacts_last_30d': 1, 'days_since_last_contact': 7})['decision'] == 'allow'
      and D(HV, {'type': 'reminder'}, {**OK, 'contacts_last_30d': 1, 'days_since_last_contact': 6})['decision'] == 'deny')
r = D({**HV, 'tenure_days': 29}, coupon(0.05))
check('new customer (tenure 29 < 30 days) gets a reminder instead of a coupon', r['decision'] == 'modify' and r['action']['type'] == 'reminder')
r = D({**HV, 'lifecycle_state': 'active', 'recency_days': 10}, coupon(0.05))
check('active recent buyer gets a reminder instead of a coupon', r['action']['type'] == 'reminder')
r = D(HV, coupon(0.05), {**OK, 'in_stock': False})
check('out of stock (demo) -> reminder', r['action']['type'] == 'reminder')
r = D({**HV, 'return_rate': 0.31}, coupon(0.05))
check('return rate 0.31 > 0.30 -> reminder; None (no returns in data) noted, not triggered', r['action']['type'] == 'reminder'
      and any('数据无退货记录' in c['detail'] for c in D(HV, coupon(0.05))['checks']))
r = D(HV, coupon(0.10))
check('deterministic cost = discount x 90-day avg order + reminder', r['cost_usd'] == round(0.10 * 150.0 + 0.05, 2), r['cost_usd'])
a, b = D({**HV, 'monetary_90d_usd': 399.0}, coupon(0.10)), D({**HV, 'monetary_90d_usd': 399.2}, coupon(0.10))   # high tier, 2 orders: avg 199.5 / 199.6
check('per-customer cap: cost 20.00 allowed, 20.01 denied (budget_denied)', a['decision'] == 'allow' and a['cost_if_allowed_usd'] == 20.0
      and b['code'] == 'budget_denied' and b['cost_if_allowed_usd'] == 20.01, (a['cost_if_allowed_usd'], b['cost_if_allowed_usd']))
c = D(HV, coupon(0.10))['cost_usd']
check('weekly budget: spent so that total equals 200 allowed; one cent more denied',
      D(HV, coupon(0.10), OK, {'spent_usd': 200 - c})['decision'] == 'allow' and D(HV, coupon(0.10), OK, {'spent_usd': 200 - c + 0.01})['code'] == 'budget_denied')
check('invalid action rejected', PE.decide(HV, {'type': 'sms_blast'}, OK, None, P)['status'] == 'error')
check('demo settings reported separately from facts', set(D(HV, coupon(0.05))['demo_config_used']) == set(P['demo_defaults'])
      and all(ch['basis'] for ch in D(HV, coupon(0.05))['checks']))
src = (ROOT / 'src/retail_bi/ai/policy_engine.py').read_text(encoding='utf-8')
check('policy engine does not import the LLM client', 'import client' not in src and 'LLMClient' not in src)

# ---- real batch over the latest snapshot (offline, read-only; customer rows never leave this process) ----
con, ptr = open_current()
rows = con.execute("""SELECT p.customer_id, p.recency_days, p.frequency_90d, p.monetary_90d_usd, p.orders_all_time, p.merch_all_time_usd, p.tenure_days,
    p.lifecycle_state, s.applicability, s.p_repurchase_30d FROM ads.customer_profile_latest p
    LEFT JOIN ads.model_scores s ON s.customer_id = p.customer_id AND s.as_of = (SELECT max(as_of) FROM ads.model_scores)""").df()
con.close()
cust = [{**r, 'return_rate': None, 'p_repurchase_30d': None if r['p_repurchase_30d'] != r['p_repurchase_30d'] else float(r['p_repurchase_30d'])}
        for r in rows.to_dict('records')]
# frozen weekly-list ranking (ML-08): 90-day orders, then 90-day amount; in-population only
ranked = sorted([c for c in cust if c['frequency_90d'] >= 1], key=lambda c: (-c['frequency_90d'], -c['monetary_90d_usd'], c['customer_id']))
batch = PE.allocate(ranked, coupon(0.10), lambda c: {'consent': True}, P)
dec = batch['decisions']
from collections import Counter  # noqa: E402
counts = Counter(d['decision'] for d in dec)
codes = Counter(d['code'] for d in dec if d['decision'] == 'deny')
acts = Counter((d['action'] or {}).get('type') for d in dec if d['decision'] != 'deny')
check('real batch: weekly budget never exceeded', batch['spent_usd'] <= batch['weekly_budget_usd'], batch['spent_usd'])
rule_of = lambda d: d['reasons'][-1].split('：')[0] if d['decision'] == 'deny' else None  # noqa: E731
by_rule = Counter(rule_of(d) for d in dec if d['decision'] == 'deny')
first_budget_deny = next((i for i, d in enumerate(dec) if rule_of(d) == '每周预算'), None)
after = dec[first_budget_deny:] if first_budget_deny is not None else []
check('real batch: weekly budget runs out partway down the ranked list; afterwards only actions that still fit are allowed',
      first_budget_deny is not None and all(d['decision'] == 'deny' or d['cost_usd'] <= 200 - batch['spent_usd'] + d['cost_usd'] for d in after), (first_budget_deny, dict(by_rule)))
check('real batch: every decision has a reason or passes all checks', all(d['reasons'] or d['decision'] == 'allow' for d in dec))
summary = {'release': ptr['version'], 'population_ranked': len(ranked), 'decisions': dict(counts), 'deny_codes': {str(k): v for k, v in codes.items()}, 'deny_by_rule': dict(by_rule),
           'actions': {str(k): v for k, v in acts.items()}, 'tiers': dict(Counter(d['tier'] for d in dec)), 'spent_usd': batch['spent_usd'],
           'weekly_budget_usd': batch['weekly_budget_usd'], 'first_weekly_budget_denied_rank': first_budget_deny,
           'assumptions': '演示：所有客户假设已同意营销、无投诉、无近期触达、毛利 30%、有货；请求 10% 优惠；名单按冻结规则排序',
           'examples': [{k: d[k] for k in ('decision', 'action', 'cost_usd', 'tier', 'reasons')} for d in dec[:3]] + [{k: d[k] for k in ('decision', 'code', 'cost_usd', 'tier', 'reasons')} for d in dec if d['code'] == 'budget_denied'][:1]
           + ([{k: dec[first_budget_deny][k] for k in ('decision', 'code', 'tier', 'reasons')}] if first_budget_deny is not None else [])}
print(json.dumps(summary, ensure_ascii=False, default=str)[:1500])
ok = all(r['status'] == 'passed' for r in res)
out = {'task_id': 'AI-11', 'policy_version': P['policy_version'], 'policy_source': 'knowledge/retention_policy.md', 'checks': res,
       'passed': sum(r['status'] == 'passed' for r in res), 'total': len(res), 'real_batch': summary}
(ROOT / 'reports/ai/policy_checks.json').write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
print(f'{out["passed"]}/{out["total"]} checks passed')
sys.exit(0 if ok else 1)
