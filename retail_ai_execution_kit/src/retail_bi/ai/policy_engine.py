"""AI-11: deterministic retention policy and budget checks (check_budget in contracts/interfaces.md).

The rules and their demo settings live in knowledge/retention_policy.md (the JSON block tagged
policy-config); this module only reads and applies them. Nothing here calls an LLM.

decide(customer, action, context, budget) -> envelope with data.decision = allow | modify | deny
  customer : fact fields from the published release (recency_days, frequency_90d, monetary_90d_usd,
             orders_all_time, merch_all_time_usd, tenure_days, lifecycle_state, applicability,
             p_repurchase_30d, return_rate=None when the data has no returns)
  action   : {'type': 'reminder' | 'coupon', 'discount': 0..1}
  context  : demo configuration supplied by the caller (consent, open_complaint, contacts_last_30d,
             days_since_last_contact, gross_margin, in_stock); missing keys take the documented defaults
  budget   : {'spent_usd': already committed this week}
Each check records whether it used a fact field or a demo setting. The model probability is never used
for eligibility, discount or budget (the model's ranking is near random, ML-09); risk never raises a
discount. 'modify' means the action was reduced (discount lowered to its cap, or coupon -> reminder).
"""
from __future__ import annotations

import json
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
POLICY_DOC = ROOT / 'knowledge/retention_policy.md'


def load_policy(path: Path = POLICY_DOC) -> dict:
    m = re.search(r'```json policy-config\n(.*?)\n```', path.read_text(encoding='utf-8'), re.S)
    if not m:
        raise ValueError('policy-config block not found in ' + str(path))
    return json.loads(m.group(1))


def usd(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def value_tier(c: dict, P: dict) -> str:
    f = P['facts']
    if int(c.get('frequency_90d') or 0) >= 1:
        high = int(c['frequency_90d']) >= f['high_value_min_orders_90d'] or float(c['monetary_90d_usd']) >= f['high_value_min_merch_90d_usd']
        return 'high' if high else 'normal'
    high = int(c.get('orders_all_time') or 0) >= f['lapsed_high_min_orders_all_time'] or float(c.get('merch_all_time_usd') or 0) >= f['lapsed_high_min_merch_all_time_usd']
    return 'lapsed_high' if high else 'lapsed_normal'


def avg_order_value(c: dict) -> Decimal | None:
    if int(c.get('frequency_90d') or 0) >= 1:
        return Decimal(str(c['monetary_90d_usd'])) / int(c['frequency_90d'])
    if int(c.get('orders_all_time') or 0) >= 1:
        return Decimal(str(c['merch_all_time_usd'])) / int(c['orders_all_time'])
    return None


def _finite(v) -> bool:
    import math
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


SENT_CLAIM = re.compile(r'已(?:为您|给您|经|帮您)?(?:发放|发送|到账|领取|存入|充值|发券|发到)|已发|请(?:及时)?(?:查收|领取|使用)|已为您准备好')
OFFER_WORD = re.compile(r'优惠|券|折扣|打折|[几一二三四五六七八九]折|立减|满减|减免|红包|返现|返利|赠送|免单|半价|特价')
CN_AMOUNT = re.compile(r'[零〇一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]+\s*(?:元|块|美元|折|成|倍|张|%|个百分点)')
KEYLIKE = re.compile(r'sk[-_][A-Za-z0-9_-]{4,}|Bearer\s+\S+|Token\s+\S+', re.I)


def copy_violations(copy: str, action_type: str, discount: float, promise=None) -> list[str]:
    """Draft copy must match the decided action (G-012/G-034): nothing is sent or issued, and the only number a coupon
    may carry is its own percentage; a reminder mentions no offer at all."""
    import unicodedata
    c = unicodedata.normalize('NFKC', re.sub(r'[\u200b-\u200f\u2060-\u2064\ufeff\u00ad]', '', str(copy)))
    errs = []
    pct = f'{float(discount) * 100:g}'
    if len(c) > 80:
        errs.append('文案超过 80 字')
    if '\x00' in c or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', c):
        errs.append('文案含控制字符')
    if SENT_CLAIM.search(c):
        errs.append(f'文案声称已发送或已发放：{SENT_CLAIM.search(c).group(0)}（草稿不会发送，也不发券）')
    if KEYLIKE.search(c):
        errs.append('文案含类似密钥的字符串')
    if re.search(r'customer_\d+|先生|女士', c):
        errs.append('文案含客户编号或称谓')
    if promise is not None and promise.search(c):
        errs.append(f'文案含承诺用语：{promise.search(c).group(0)}')
    nums = re.findall(r'\d+(?:\.\d+)?', c)
    if action_type == 'coupon':
        if [n for n in nums if n != pct] or CN_AMOUNT.search(c) or re.search(r'立减|满减|红包|返现|免单|半价|[几一二三四五六七八九]折', c):
            errs.append(f'优惠文案只能写本次折扣 {pct}%，不能写其他数字或优惠形式')
        if pct not in nums:
            errs.append(f'优惠文案没有写明本次折扣 {pct}%')
    else:
        if nums or CN_AMOUNT.search(c):
            errs.append('提醒文案不能写数字或金额')
        if OFFER_WORD.search(c):
            errs.append(f'提醒文案不能提优惠：{OFFER_WORD.search(c).group(0)}（规则只批准了提醒）')
    return errs


def decide(customer: dict, action: dict, context: dict | None = None, budget: dict | None = None, policy: dict | None = None) -> dict:
    P = policy or load_policy()
    ctx = {**P['demo_defaults'], **(context or {})}
    demo_keys = sorted(k for k in P['demo_defaults'])
    import math
    nums = {'spent_usd': (budget or {}).get('spent_usd', 0), 'gross_margin': ctx.get('gross_margin'), 'discount': action.get('discount', 0)}
    bad = [k for k, v in nums.items() if v is not None and not (isinstance(v, (int, float, Decimal, str)) and _finite(v))]
    if bad or float(nums['spent_usd'] or 0) < 0:       # NaN / inf crashed Decimal (G-030); a negative margin gives a cap of 0 below
        return {'status': 'error', 'mode': 'live', 'data': {}, 'error': {'code': 'invalid_argument', 'retryable': False,
                'message': f'输入不是有效的非负有限数：{bad or ["spent_usd"]}'}}
    spent = usd((budget or {}).get('spent_usd', 0))
    checks, reasons = [], []

    def chk(rule, passed, detail, basis):
        checks.append({'rule': rule, 'passed': bool(passed), 'detail': detail, 'basis': basis})
        if not passed:
            reasons.append(f'{rule}：{detail}')
        return passed

    kind = action.get('type')
    want = Decimal(str(action.get('discount', 0) if kind == 'coupon' else 0))
    if kind not in ('reminder', 'coupon') or want < 0 or want >= 1:
        return {'status': 'error', 'mode': 'live', 'data': {}, 'error': {'code': 'invalid_argument', 'message': f'unsupported action {action}', 'retryable': False}}

    tier = value_tier(customer, P)
    f = P['facts']
    # ---- eligibility (any failure -> deny) ----
    eligible = all([
        chk('营销同意', ctx['consent'] is True, f'consent={ctx["consent"]}（未知按未同意处理）', 'demo_config'),
        chk('未结投诉', not ctx['open_complaint'], '有未结投诉，转人工服务' if ctx['open_complaint'] else '无', 'demo_config'),
    ])
    # frequency
    freq = P['frequency']
    n_recent = int(ctx['contacts_last_30d'] or 0)
    gap = ctx['days_since_last_contact']
    eligible &= chk('触达频率', n_recent < freq['max_contacts'], f'{freq["window_days"]} 天内已触达 {n_recent} 次，上限 {freq["max_contacts"]}', 'demo_config')
    eligible &= chk('触达间隔', gap is None or int(gap) >= freq['min_gap_days'], f'距上次触达 {gap} 天，至少 {freq["min_gap_days"]} 天', 'demo_config')

    # ---- coupon-specific rules (failure -> fall back to reminder) ----
    final_kind, disc, modified = kind, want, False
    if kind == 'coupon' and eligible:
        rr = customer.get('return_rate')
        coupon_ok = all([
            chk('新客不发优惠', int(customer.get('tenure_days') or 0) >= f['new_customer_tenure_days'] or int(customer.get('orders_all_time') or 0) == 0,
                f'首单后 {customer.get("tenure_days")} 天，少于 {f["new_customer_tenure_days"]} 天只发提醒', 'fact'),
            chk('近期购买者不发优惠', not (customer.get('lifecycle_state') == 'active' and float(customer.get('recency_days') or 1e9) < f['recent_buyer_days']),
                f'活跃且 {float(customer.get("recency_days") or 0):.1f} 天前刚买过', 'fact'),
            chk('退货率', rr is None or float(rr) <= f['max_return_rate_for_coupon'],
                '数据无退货记录，规则不触发' if rr is None else f'退货率 {rr}，上限 {f["max_return_rate_for_coupon"]}', 'fact (not in data)' if rr is None else 'fact'),
            chk('库存', ctx['in_stock'] is True, '相关商品缺货' if not ctx['in_stock'] else '有货', 'demo_config'),
        ])
        if not coupon_ok:
            final_kind, disc, modified = 'reminder', Decimal(0), True
        else:
            cap_tier = Decimal(str(P['discount_cap_by_tier'][tier]))
            cap_margin = (Decimal(str(ctx['gross_margin'])) * Decimal(str(P['margin_share_for_discount']))).quantize(Decimal('0.0001'))
            cap = max(Decimal(0), min(cap_tier, cap_margin))
            checks.append({'rule': '折扣上限', 'passed': want <= cap, 'basis': 'fact (value tier) + demo_config (margin)',
                           'detail': f'请求 {want}，价值层级 {tier} 上限 {cap_tier}，毛利上限 {cap_margin}（毛利 {ctx["gross_margin"]} × {P["margin_share_for_discount"]}）'})
            if want > cap:
                disc, modified = cap, True
                reasons.append(f'折扣由 {want} 下调到上限 {cap}')
            if disc <= 0:
                final_kind, disc, modified = 'reminder', Decimal(0), True
                reasons.append('折扣上限为 0，改为只发提醒')

    # ---- deterministic cost and budget ----
    cost = Decimal(str(P['cost']['reminder_usd']))
    aov = avg_order_value(customer)
    if final_kind == 'coupon':
        if aov is None:
            final_kind, disc, modified = 'reminder', Decimal(0), True
            reasons.append('没有历史订单，无法计算优惠成本，改为提醒')
        else:
            cost += disc * aov
    cost = usd(cost)
    if eligible:
        eligible &= chk('单客成本上限', cost <= usd(P['cost']['per_customer_cap_usd']), f'成本 {cost} USD，上限 {P["cost"]["per_customer_cap_usd"]}', 'demo_config')
        eligible &= chk('每周预算', spent + cost <= usd(P['cost']['weekly_budget_usd']),
                        f'已用 {spent} + 本次 {cost} USD，周预算 {P["cost"]["weekly_budget_usd"]}', 'demo_config')

    decision = 'deny' if not eligible else ('modify' if modified else 'allow')
    p = customer.get('p_repurchase_30d')
    return {'status': 'ok', 'mode': 'live',
            'data': {'decision': decision, 'code': None if eligible else ('budget_denied' if any(c['rule'] in ('每周预算', '单客成本上限') and not c['passed'] for c in checks) else 'not_eligible'),
                     'requested': {'type': kind, 'discount': float(want)},
                     'action': None if not eligible else {'type': final_kind, 'discount': float(disc), 'draft_only': True},
                     'cost_usd': float(cost) if eligible else 0.0, 'cost_if_allowed_usd': float(cost), 'value_tier': tier,
                     'budget_after_usd': float(spent + cost) if eligible else float(spent),
                     'reasons': reasons, 'checks': checks,
                     'model_reference': {'applicability': customer.get('applicability'), 'p_repurchase_30d': p, 'used_for_decision': False,
                                         'note': '模型个体排序接近随机（ML-09），概率不参与资格、折扣和预算判定'},
                     'demo_config_used': {k: ctx[k] for k in demo_keys}},
            'policy_version': P['policy_version'], 'policy_source': 'knowledge/retention_policy.md',
            'warnings': [{'code': 'demo_config', 'message': '同意、投诉、触达、库存、毛利和预算是演示配置，不是数据事实'}]}


def allocate(candidates: list[dict], action: dict, context_fn, policy: dict | None = None) -> dict:
    """Walk a ranked list and decide each in turn against one weekly budget (drafts only)."""
    P = policy or load_policy()
    spent, out = Decimal(0), []
    for c in candidates:
        r = decide(c, action, context_fn(c), {'spent_usd': spent}, P)
        if r['data']['decision'] != 'deny':
            spent += Decimal(str(r['data']['cost_usd']))
        out.append({'customer_id': c.get('customer_id'), 'decision': r['data']['decision'], 'code': r['data']['code'],
                    'action': r['data']['action'], 'cost_usd': r['data']['cost_usd'], 'tier': r['data']['value_tier'], 'reasons': r['data']['reasons']})
    return {'decisions': out, 'spent_usd': float(usd(spent)), 'weekly_budget_usd': P['cost']['weekly_budget_usd']}
