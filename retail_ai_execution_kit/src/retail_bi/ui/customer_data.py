"""UI-04: read-only customer queries for the customer page through runtime.open_current().

Only two kinds of query, both fixed SQL with bound parameters (no free SQL, not exposed to the AI layer):
- aggregates(): customer counts by lifecycle state and by recency bucket at the latest snapshot, plus the
  number of customers with no visible purchase (unknown_no_purchase) and with no customer id (anonymous).
- lookup(customer_id): one customer's observable snapshot fields, the lifecycle rule that applied, the
  value segment (ML-05 rule cut points) and the model reference (applicability, probability). City, zip,
  generator labels and any attribute not in the data (age, channel, identity) are never returned.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
from runtime import ReleaseError, open_current  # noqa: E402

ID = re.compile(r'^customer_\d{6}$')
R_RECENT, M_HIGH, F_MULTI = 30.0, 203.19, 2        # ML-05 segments-v1 cut points (reports/model/rfm_segments.md)
THRESH = {'new': 30, 'active': 90, 'at_risk': 180}  # lifecycle-v1 (docs/lifecycle_rules.md)
STATE_ZH = {'new': '新客', 'active': '活跃', 'at_risk': '沉默预警', 'dormant': '沉睡', 'unknown_no_purchase': '未知：尚无购买',
            'unknown_anonymous': '未知：匿名', 'unknown_short_history': '未知：观察期不足'}


def _con(releases=None):
    return open_current(releases) if releases else open_current()


def aggregates(releases=None) -> dict:
    con, ptr = _con(releases)
    try:
        as_of = con.execute('SELECT max(as_of_date)::VARCHAR FROM ads.customer_profile_latest').fetchone()[0]
        states = dict(con.execute('SELECT lifecycle_state, count(*) FROM ads.customer_profile_latest GROUP BY 1').fetchall())
        buckets = con.execute("""SELECT CASE WHEN recency_days < 365 THEN '180–365 天' WHEN recency_days < 730 THEN '365–730 天' ELSE '730 天以上' END b,
                                 count(*), round(min(recency_days), 1), round(max(recency_days), 1) FROM ads.customer_profile_latest
                                 WHERE lifecycle_state = 'dormant' GROUP BY 1 ORDER BY min(recency_days)""").fetchall()
        total = con.execute('SELECT count(*) FROM dwd.dim_customer').fetchone()[0]
        anon = con.execute('SELECT count(*) FROM dwd.fact_order WHERE customer_id IS NULL').fetchone()[0]
    finally:
        con.close()
    return {'release': ptr['version'], 'as_of_date': as_of, 'states': states, 'customers_total': total,
            'no_visible_purchase': total - sum(states.values()), 'anonymous_orders': anon,
            'dormant_by_recency': [{'bucket': b, 'customers': n, 'min_days': lo, 'max_days': hi} for b, n, lo, hi in buckets]}


def rule_basis(p: dict) -> str:
    r, ten = float(p['recency_days']), float(p['tenure_days'])
    s = p['lifecycle_state']
    if s == 'new':
        return f'首次可观测购买距 as_of {ten:.1f} 天 < {THRESH["new"]} 天 → 新客'
    if s == 'active':
        return f'最近一次购买距 as_of {r:.1f} 天 < {THRESH["active"]} 天，且首购已超过 {THRESH["new"]} 天 → 活跃'
    if s == 'at_risk':
        return f'最近一次购买距 as_of {r:.1f} 天，在 [{THRESH["active"]}, {THRESH["at_risk"]}) 天内 → 沉默预警'
    if s == 'dormant':
        return f'最近一次购买距 as_of {r:.1f} 天 ≥ {THRESH["at_risk"]} 天 → 沉睡（只描述距上次购买多久，不表示已流失）'
    return STATE_ZH.get(s, s)


def value_segment(p: dict) -> str:
    if int(p['frequency_90d']) < 1:
        return '不在 RFM 分群母体（近 90 天没有购买），由生命周期规则管理'
    recent = float(p['recency_days']) < R_RECENT
    high = int(p['frequency_90d']) >= F_MULTI or float(p['monetary_90d_usd']) >= M_HIGH
    return ('近期' if recent else '较早') + ('高价值' if high else '一般') + \
        f'（近 90 天 {int(p["frequency_90d"])} 单、{float(p["monetary_90d_usd"]):.2f} USD；高价值 = 多单或 ≥ {M_HIGH} USD）'


def lookup(customer_id: str, releases=None) -> dict:
    if not isinstance(customer_id, str) or not ID.match(customer_id.strip()):
        return {'status': 'error', 'error': {'code': 'invalid_argument', 'message': '客户编号格式应为 customer_ 加 6 位数字'}}
    cid = customer_id.strip()
    try:
        con, ptr = _con(releases)
    except (ReleaseError, FileNotFoundError, OSError):
        return {'status': 'error', 'error': {'code': 'snapshot_unavailable', 'message': '没有已发布的快照'}}
    try:
        cur = con.execute("""SELECT customer_id, as_of_date::VARCHAR AS as_of_date, customer_region, recency_days, frequency_90d, monetary_90d_usd,
                             orders_all_time, merch_all_time_usd, first_purchase_date::VARCHAR AS first_purchase_date, tenure_days, lifecycle_state
                             FROM ads.customer_profile_latest WHERE customer_id = ?""", [cid])
        names = [d[0] for d in cur.description]
        row = cur.fetchone()
        known = con.execute('SELECT count(*) FROM dwd.dim_customer WHERE customer_id = ?', [cid]).fetchone()[0]
        score = con.execute("""SELECT applicability, p_repurchase_30d, top_factors FROM ads.model_scores
                               WHERE customer_id = ? AND as_of = (SELECT max(as_of) FROM ads.model_scores)""", [cid]).fetchone()
    finally:
        con.close()
    if row is None:
        if known:
            return {'status': 'ok', 'release': ptr['version'], 'data': {'customer_id': cid, 'lifecycle_state': 'unknown_no_purchase',
                    'state_zh': STATE_ZH['unknown_no_purchase'], 'rule_basis': '截至最新快照没有可见的有效购买，不进入快照、分群和模型'}}
        return {'status': 'empty', 'release': ptr['version'], 'error': {'code': 'not_found', 'message': '没有这个客户编号'}}
    p = dict(zip(names, row))
    p.update({'state_zh': STATE_ZH.get(p['lifecycle_state'], p['lifecycle_state']), 'rule_basis': rule_basis(p), 'value_segment': value_segment(p),
              'model': {'applicability': score[0] if score else 'not_scored', 'p_repurchase_30d': None if not score or score[1] is None else round(float(score[1]), 4),
                        'top_factors': score[2] if score else None,
                        'caveat': '模型个体排序接近随机（测试 ROC-AUC 0.515），概率只代表平均水平；因素是模型解释，不是因果'}})
    return {'status': 'ok', 'release': ptr['version'], 'data': p}
