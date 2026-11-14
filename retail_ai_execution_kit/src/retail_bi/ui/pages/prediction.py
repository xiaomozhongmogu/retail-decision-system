"""UI page: repurchase model evaluation and weekly list what-if (UI-05).

Frozen records (split, baselines, selection, test, error analysis) are read from reports/model/*.json and
only displayed; the K / threshold controls are a what-if over the latest scoring list and never write.
"""
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import banner, release_dir  # noqa: E402
from model_data import EXPECTED_MODEL, frozen_reports, score_list, trial  # noqa: E402


# readable metric names for the tables (UI-07); the JSON records keep their field names
MET = {'roc_auc': 'ROC-AUC', 'roc_auc_95ci': 'ROC-AUC 95% 区间', 'pr_auc': 'PR-AUC', 'pr_auc_95ci': 'PR-AUC 95% 区间',
       'lift@10%': 'Lift@10%', 'weekly_lift@10%': '周内 Lift@10%', 'mean_weekly_roc_auc': '周均 ROC-AUC', 'brier': 'Brier', 'ece': 'ECE'}


def cell(v):
    """Text for every cell, so a column never mixes numbers and '—' (Arrow cannot serialise that)."""
    if v is None:
        return '—'
    if isinstance(v, list):
        return f'{v[0]:.3f}–{v[1]:.3f}'
    return f'{v:.4f}' if isinstance(v, (int, float)) else str(v)


@st.cache_data(show_spinner='读取评分名单…', max_entries=4)
def scores(version: str, releases: str) -> dict:
    """Scoring list, cached per release version (a new release is a new key); returns a copy to each session."""
    return score_list(Path(releases))


st.title('复购预测')
info = banner()
st.warning('模型 repurchase-logreg-v1 在测试期的个体区分能力接近随机（ROC-AUC 0.515，95% 区间 0.483–0.546）。概率只作平均水平参考；'
           '名单排序用冻结的规则（近 90 天订单数），因素是模型解释，不是因果效果。')
R, missing = frozen_reports(('split_manifest', 'baselines', 'model_selection', 'test_metrics', 'error_analysis'))
if missing:
    st.error(f"模型评估记录缺失或无法读取：{', '.join(missing)}（reports/model/）。请按 docs/COMMANDS.md 重新运行模型步骤；本页只显示冻结记录，不在网页中训练模型。")
    st.stop()
sp, bl, ms, tm, ea = (R[k] for k in ('split_manifest', 'baselines', 'model_selection', 'test_metrics', 'error_analysis'))
t1, t2, t3, t4, t5 = st.tabs(['样本与切分', '基线与选模', '测试结果（冻结）', '误差分析', '名单试算'])

with t1:
    st.markdown(f"目标 `{sp['target']}`：客户 × 每周一 as_of，母体为近 90 天有有效购买的客户，标签 = 之后 30 天内是否再次购买；标签窗结束再等 1 天审批落定（成熟 {sp['label_maturity_days']} 天）。")
    rows = [{'集合': {'train': '训练', 'validation': '验证', 'test': '测试', 'embargo': '隔离（不使用）'}[k], 'as_of 范围': ' 至 '.join(v['as_of_range']) if v['as_of_range'] else '—',
             '周数': v['as_of_points'], '样本行（客户×周）': v['rows'], '客户': v['customers'], '正例': v['positives'], '正例率': v['positive_rate']} for k, v in sp['sets'].items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, column_config={'正例率': st.column_config.NumberColumn(format='percent')})
    st.caption(f"样本行是客户×周，同一客户出现在多周和多个集合（测试客户中 {sp['customer_overlap']['test_customers_seen_in_train_share']:.0%} 在训练中出现过），不是原始订单数。"
               f"集合之间隔离 {sp['embargo_weeks']} 周，标签成熟后才进入下一个集合。")

with t2:
    cand = ms['candidates_validation']
    keys = ['roc_auc', 'pr_auc', 'lift@10%', 'brier']
    st.dataframe(pd.DataFrame([{'候选（验证集）': k, **{MET[m]: cell(v.get(m)) for m in keys}} for k, v in cand.items()]), hide_index=True)
    pm = ms['probability_model']
    st.markdown(f"**概率模型**：{pm['choice']} — {pm['why']}")
    st.markdown(f"**校准**：{ms['calibration']['choice']} — {ms['calibration']['why']}")
    st.markdown(f"**名单排序**：{ms['ranking_policy']['choice']} — {ms['ranking_policy']['why']}")
    st.markdown(f"**名单规模**：{ms['threshold_and_capacity']['rule']}")
    st.caption(f"冻结于 {ms['frozen_at'][:19]}；{ms['no_switch_after_test']}")

with t3:
    sc = tm['scores']
    lab = {'p_model': '冻结模型', 'rule_frequency_90d': '规则：近 90 天订单数', 'rule_recency': '规则：最近购买', 'base_rate': '基率'}
    keys = ['roc_auc', 'roc_auc_95ci', 'pr_auc', 'pr_auc_95ci', 'lift@10%', 'weekly_lift@10%', 'mean_weekly_roc_auc', 'brier', 'ece']
    st.dataframe(pd.DataFrame([{'方法': lab.get(k, k), **{MET[m]: cell(v.get(m)) for m in keys}} for k, v in sc.items()]), hide_index=True)
    st.caption('ROC-AUC / PR-AUC：排序区分能力（0.5 与正例比例分别是随机水平）；Lift@10%：前 10% 的复购率是平均的几倍；周内指标按每周分别计算再平均；'
               'Brier、ECE：概率误差，越小越好。区间为按客户分块重抽样的 95% 区间。“—”表示该方法没有这项指标（基率是常数，不排序）。')
    ts = tm['test_set']
    st.caption(f"测试集 {ts['as_of_range'][0][:10]} 至 {ts['as_of_range'][1][:10]}，{ts['rows']:,} 行、{ts['customers']:,} 名客户、正例 {ts['positives']:,}（{ts['positive_rate']:.1%}）；"
               f"只使用一次（{tm['evaluated_at'][:10]}），页面只读显示，不会被试算覆盖。")
    rel = pd.DataFrame(sc['p_model']['reliability'])
    line = alt.Chart(pd.DataFrame({'x': [0, 0.12], 'y': [0, 0.12]})).mark_line(strokeDash=[4, 4], color='gray').encode(x='x:Q', y='y:Q')
    pts = alt.Chart(rel).mark_line(point=True).encode(x=alt.X('mean_pred:Q', title='平均预测概率', scale=alt.Scale(domain=[0, 0.12])),
                                                       y=alt.Y('observed:Q', title='实际复购比例', scale=alt.Scale(domain=[0, 0.12])), tooltip=['bin', 'n', 'mean_pred', 'observed'])
    st.altair_chart(line + pts, width='stretch')
    st.caption(f"校准：10 个等量分箱，ECE {sc['p_model']['ece']}。概率集中在 5%–9%，平均水平接近实际（{sc['p_model']['mean_pred']:.1%} 对 {ts['positive_rate']:.1%}），但分不出谁更可能复购。")

with t4:
    c = ea['confusion_at_weekly_top_k']
    st.markdown(f"**每周取前 10% 时的混淆矩阵**（测试集）：TP {c['TP']}、FP {c['FP']}、FN {c['FN']}、TN {c['TN']}；入选者复购率 {c['TP'] / (c['TP'] + c['FP']):.1%}，基率 {ts['positive_rate']:.1%}。")
    for k, name in (('by_month', '按月'), ('by_region', '按客户大区'), ('by_value_segment', '按价值群')):
        st.markdown(f'**{name}**')
        st.dataframe(pd.DataFrame(ea[k]), hide_index=True)
    st.markdown('**系数最大的 10 个特征**（标准化后；模型关联，不是因果）')
    st.dataframe(pd.DataFrame(ea['coefficients_top10'], columns=['特征', '系数']), hide_index=True)

with t5:
    if info is None:
        st.info('暂无评分名单：没有已发布的数据版本')
    else:
        sl = scores(info['version'], str(release_dir()))
        if sl['model_version'] != EXPECTED_MODEL:
            st.error(f"评分表中的模型版本 `{sl['model_version']}` 与冻结版本 `{EXPECTED_MODEL}` 不一致，名单不显示。"
                     '请重新运行评分并发布数据版本（docs/COMMANDS.md）。')
        else:
            lst = sl['list']
            st.markdown(f"评分快照 as_of {sl['as_of_date']}，模型 `{sl['model_version']}`；母体内 {len(lst):,} 人，**母体外 {sl['out_of_population']:,} 人不适用模型**（近 90 天没有购买，由生命周期规则管理，没有概率）。")
            c1, c2 = st.columns(2)
            k = c1.slider('名单规模 K（母体占比，试算）', 0.01, 0.5, 0.10, 0.01, key='k')
            pmin = c2.slider('附加概率下限（试算）', 0.0, 0.2, 0.0, 0.005, key='pmin')
            r = trial(lst, k, pmin)
            m1, m2, m3 = st.columns(3)
            m1.metric('入选人数', f"{r['selected']:,} / {r['population']:,}")
            m2.metric('入选者平均预测概率', f"{r['mean_p_selected']:.1%}" if r['mean_p_selected'] is not None else '—')
            m3.metric('母体平均预测概率', f"{r['mean_p_population']:.1%}")
            frozen = ms['threshold_and_capacity']['capacity_share_per_week']
            st.caption(f"冻结的名单规则：K = {frozen:.0%}、不设概率阈值（ML-08）。上面的滑块只是试算，不修改冻结记录或测试结果；"
                       f"测试期规则排序的周内 Lift@10% 为 {sc['rule_frequency_90d']['weekly_lift@10%']}，模型为 {sc['p_model']['weekly_lift@10%']}，"
                       '所以预测概率之差不代表真实复购差异，也不能当作触达带来的增量。')
            st.dataframe(r['rows'][['rank', 'customer_id', 'frequency_90d', 'monetary_90d_usd', 'recency_days', 'lifecycle_state', 'p_repurchase_30d', 'top_factors']].rename(
                columns={'rank': '排名', 'customer_id': '客户编号', 'frequency_90d': '近 90 天订单', 'monetary_90d_usd': '近 90 天金额 USD', 'recency_days': '距上次购买（天）',
                         'lifecycle_state': '生命周期', 'p_repurchase_30d': '预测复购概率', 'top_factors': '模型因素（非因果）'}), hide_index=True,
                column_config={'预测复购概率': st.column_config.NumberColumn(format='%.3f'), '距上次购买（天）': st.column_config.NumberColumn(format='%.1f'),
                               '近 90 天金额 USD': st.column_config.NumberColumn(format='%.2f')})
