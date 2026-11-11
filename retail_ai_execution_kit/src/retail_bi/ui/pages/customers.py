"""UI page: customer lifecycle, value segments, model risk and cohorts — shown as separate concepts (UI-04).

Lifecycle mix and cohorts come from allowed views; segments from the ML-05 report; risk only as the average
from ads.risk_summary_latest; one-customer lookup and aggregates through ui/customer_data.py (read-only,
fixed SQL). Only observable history is shown: no age, channel, city, zip or real identity.
"""
import json
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, banner, release_info, show, view  # noqa: E402
from customer_data import STATE_ZH, aggregates, lookup  # noqa: E402

st.title('客户生命周期与分群')
info = banner()
st.caption('三个概念分开：**生命周期阶段**（距上次购买多久，规则 lifecycle-v1）、**价值群**（近 90 天 RFM 规则分群，segments-v1）、'
           '**复购风险**（模型 repurchase-logreg-v1，个体排序接近随机）。它们回答不同问题，不能互相替代。')
t1, t2, t3, t4, t5 = st.tabs(['生命周期阶段', '价值群', '复购风险', 'cohort 留存', '查看客户'])

with t1:
    status, mix, msg = view('ads.lifecycle_mix_weekly')
    if show(status, mix, msg, '暂无生命周期数据'):
        mix['customers'] = mix.customers.astype(int)
        latest = mix.as_of_date.max()
        cur = mix[mix.as_of_date == latest]
        agg = aggregates() if info else None
        cols = st.columns(4)
        for c, s in zip(cols, ['new', 'active', 'at_risk', 'dormant']):
            n = int(cur.loc[cur.lifecycle_state == s, 'customers'].sum())
            c.metric(STATE_ZH[s], f'{n:,}')
        st.caption(f'快照 as_of {latest}（每周一）。规则：新客 = 首次可观测购买在 30 天内；活跃 = 最近购买在 90 天内；沉默预警 = 90–180 天；沉睡 = 180 天以上。')
        if agg:
            st.markdown(f"- 未知：尚无购买 **{agg['no_visible_purchase']:,}** 人（共 {agg['customers_total']:,} 名合成客户中截至快照没有可见有效购买，不进入快照、分群和模型）。\n"
                        f"- 未知：匿名 **{agg['anonymous_orders']}** 单（本数据所有订单都有客户编号）。")
            st.markdown('**沉睡客户按距上次购买天数**（长期沉睡仍是“沉睡”，不标为已流失）')
            st.dataframe(pd.DataFrame(agg['dormant_by_recency']).rename(columns={'bucket': '距上次购买', 'customers': '客户', 'min_days': '最短天数', 'max_days': '最长天数'}), hide_index=True)
        st.info('各状态未来 180 天再次购买的比例几乎相同（活跃 35.0%、预警 35.1%、沉睡 35.2%、新客 36.3%，docs/lifecycle_rules.md）：状态描述跟进时机，不预测流失。')
        trend = alt.Chart(mix.assign(状态=mix.lifecycle_state.map(STATE_ZH))).mark_line().encode(
            x=alt.X('as_of_date:T', title='快照日期'), y=alt.Y('customers:Q', title='客户数（人）'), color=alt.Color('状态:N'))
        st.altair_chart(trend, width='stretch')

with t2:
    if info is None:
        st.info('暂无价值群：没有已发布的数据版本（分群对应发布数据的近 90 天母体）')
    else:
        seg = json.loads((ROOT / 'reports/model/cluster_metrics.json').read_text(encoding='utf-8'))
        d = seg['definition']
        st.markdown(f"母体：{d['population']}；R：{d['R']}；F：{d['F']}；M：{d['M']}。")
        st.markdown('**规则分群**（切分点：最近购买 < 30 天为近期；近 90 天 ≥ 2 单或金额 ≥ 203.19 USD 为高价值；切分点在 2025-08-25 拟合）')
        rs = pd.DataFrame(seg['rule_segments']['apply_as_of_profile'])
        st.dataframe(rs.rename(columns={'segment': '规则分群', 'customers': '客户', 'share': '占比', 'r_median_days': 'R 中位数（天）', 'f_mean': '平均 F（单）',
                                        'm_median_usd': 'M 中位数（USD）', 'm_total_share': '占 M 总额'}), hide_index=True,
                     column_config={'占比': st.column_config.NumberColumn(format='percent'), '占 M 总额': st.column_config.NumberColumn(format='percent')})
        st.caption(f"应用时点 {d['as_of_apply'][:10]}，共 {int(rs.customers.sum())} 人（近 90 天有购买）。来源 reports/model/rfm_segments.md（发布 {seg['release']}，交易数据与当前发布相同）。"
                   '近 90 天无购买的客户不在分群母体内，由生命周期规则管理。K-Means 聚类只作探索对照，见 ML-05 报告。')

with t3:
    status, rk, msg = view('ads.risk_summary_latest')
    if show(status, rk, msg, '暂无评分'):
        r = rk.iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric('已评分客户', f"{int(r.customers_scored) - int(r.out_of_population_customers):,}")
        c2.metric('平均 30 天复购概率', f"{float(r.mean_p_repurchase_30d):.1%}")
        c3.metric('母体外（近 90 天无购买）', f"{int(r.out_of_population_customers):,}")
        st.warning('复购风险 = 1 − 复购概率。模型测试 ROC-AUC 0.515 [0.483, 0.546]，周内个体排序接近随机：只用平均水平作参考，'
                   '不用来挑选个人、不显示“高风险名单”；母体外客户没有模型概率（docs/model_card.md）。')

with t4:
    status, co, msg = view('ads.cohort_retention')
    if show(status, co, msg, '暂无 cohort 数据'):
        co['months_since_first'] = co.months_since_first.astype(int)
        co['retention_rate'] = pd.to_numeric(co.retention_rate)
        co['immature'] = co.immature.astype(str) == 'True'
        co['显示'] = [('未成熟' if im else f'{v:.0%}') for v, im in zip(co.retention_rate, co.immature)]
        kmax = st.slider('显示首单后月数', 1, 35, 12, key='kmax')
        sub = co[(co.months_since_first >= 1) & (co.months_since_first <= kmax)]
        base = alt.Chart(sub).encode(x=alt.X('months_since_first:O', title='首单后第几个月'), y=alt.Y('cohort_month:O', title='首次可观测购买月份'))
        heat = base.mark_rect().encode(color=alt.Color('retention_rate:Q', title='留存率', scale=alt.Scale(scheme='blues')), tooltip=['cohort_month', 'months_since_first', 'cohort_customers', 'active_customers', '显示'])
        st.altair_chart(heat + base.mark_text(fontSize=9).encode(text='显示:N'), width='stretch')
        n_imm = int(sub.immature.sum())
        st.caption(f'留存率 = 该月再次有有效购买的客户 ÷ cohort 人数。未成熟格子（月份未结束，{n_imm} 格）显示“未成熟”，不是 0%。'
                   'cohort 按首次可观测购买划分；所有客户都在 2024 年上半年建档，后期 cohort 很小。')

with t5:
    cid = st.text_input('客户编号（如 customer_001045）', key='cid')
    if cid:
        r = lookup(cid)
        if r['status'] == 'error':
            st.error(r['error']['message'])
        elif r['status'] == 'empty':
            st.info(r['error']['message'])
        else:
            p = r['data']
            st.markdown(f"**生命周期阶段**：{p['state_zh']} — {p['rule_basis']}")
            if 'value_segment' in p:
                st.markdown(f"**价值群**：{p['value_segment']}")
                m = p['model']
                st.markdown(f"**模型参考**：适用性 {m['applicability']}；30 天复购概率 {m['p_repurchase_30d'] if m['p_repurchase_30d'] is not None else '无（母体外）'}。{m['caveat']}")
                obs = {k: p[k] for k in ('as_of_date', 'customer_region', 'recency_days', 'frequency_90d', 'monetary_90d_usd', 'orders_all_time',
                                         'merch_all_time_usd', 'first_purchase_date', 'tenure_days')}
                st.dataframe(pd.DataFrame([{'字段': k, '值': str(round(v, 2) if isinstance(v, float) else v)} for k, v in obs.items()]), hide_index=True)
            st.caption('只显示可观测的交易历史与客户大区；数据没有年龄、渠道或真实身份，城市与邮编不显示。')
