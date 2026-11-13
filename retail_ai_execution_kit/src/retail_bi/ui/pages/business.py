"""UI page: business KPIs with OLAP interaction (UI-03).

Reads only allowed views: ads.kpi_monthly, ads.kpi_daily (time hierarchy) and ads.sales_month_category_region
(category x region cube). Measures are summed only where additive; AOV is recomputed from sums.
"""
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import banner, show, view  # noqa: E402
from olap import DIMS, MEASURES, UNSUPPORTED_DIMS, cube, time_series  # noqa: E402

st.title('经营总览')
banner()
sm, monthly, mmsg = view('ads.kpi_monthly')
sd, daily, dmsg = view('ads.kpi_daily')
sc, catreg, cmsg = view('ads.sales_month_category_region')
if not show(sm, monthly, mmsg, '暂无经营数据'):
    st.stop()
months = sorted(monthly.month)
GRAINS = {'year': '年', 'quarter': '季度', 'month': '月', 'week': '周（周一开始）', 'day': '日'}

# ---------------- 1. time roll-up / drill-down ----------------
ZH_COLS = {'period': '期间', 'valid_orders': '有效订单', 'merchandise_sales_usd': '商品金额 USD', 'shipping_usd': '运费 USD',
           'aov_usd': '客单价 USD', 'buyers': '购买客户（月内去重）', 'complete': '完整期间'}
st.subheader('1. 时间趋势（上卷 / 下钻）')
c1, c2, c3 = st.columns(3)
start = c1.selectbox('开始月份', months, index=0, key='start')
end = c2.selectbox('结束月份', months, index=len(months) - 1, key='end')
grain = c3.radio('粒度', list(GRAINS), index=2, format_func=GRAINS.get, horizontal=True, key='grain')
status, ts, msg = time_series(monthly, daily if sd == 'ok' else pd.DataFrame(columns=monthly.columns), grain, start, end)
if status != 'ok':
    (st.info if status == 'empty' else st.error)(msg)
else:
    o, s, sh = int(ts.valid_orders.sum()), float(ts.merchandise_sales_usd.sum()), float(ts.shipping_usd.sum())
    k1, k2, k3, k4 = st.columns(4)
    k1.metric('有效订单', f'{o:,}')
    k2.metric('商品金额（USD）', f'{s:,.2f}')
    k3.metric('客单价（USD）', f'{s / o:,.2f}' if o else '—')
    k4.metric('运费（USD）', f'{sh:,.2f}')
    st.caption('客单价 = 期间商品金额合计 ÷ 有效订单合计（不对各期客单价取平均）。购买客户按月去重，跨月不能相加，只在“月”粒度显示。')
    if msg:
        st.warning(f'{msg}：' + '、'.join(ts.period[~ts.complete].astype(str)))
    chart = alt.Chart(ts.assign(状态=ts.complete.map({True: '完整', False: '不完整'}))).mark_bar().encode(
        x=alt.X('period:N', title=f'期间（{GRAINS[grain]}）', sort=None),
        y=alt.Y('merchandise_sales_usd:Q', title='商品金额（USD）'),
        color=alt.Color('状态:N', scale=alt.Scale(domain=['完整', '不完整'], range=['#4C78A8', '#BAB0AC'])),
        tooltip=['period', 'valid_orders', 'merchandise_sales_usd', 'aov_usd'])
    st.altair_chart(chart, width='stretch')
    st.dataframe(ts.rename(columns=ZH_COLS), hide_index=True)

with st.expander('逐级下钻：年 → 季度 → 月 → 日'):
    years = sorted({m[:4] for m in months})
    y = st.selectbox('年份', years, key='dy')
    _, q, _ = time_series(monthly, daily, 'quarter', f'{y}-01', f'{y}-12')
    st.dataframe(q.rename(columns=ZH_COLS), hide_index=True)            # Chinese headers (external UI test U-006)
    qs = list(q.period) if q is not None else []
    qq = st.selectbox('季度', qs, key='dq')
    qn = int(qq[-1])
    _, mm, _ = time_series(monthly, daily, 'month', f'{y}-{3 * qn - 2:02d}', f'{y}-{3 * qn:02d}')
    st.dataframe(mm.rename(columns=ZH_COLS), hide_index=True)
    mo = st.selectbox('月份', list(mm.period), key='dm')
    _, dd, _ = time_series(monthly, daily, 'day', mo, mo)
    st.dataframe(dd.rename(columns=ZH_COLS), hide_index=True)
    st.caption('日粒度中标记为不完整的日期：截止前最后一天的订单可能尚未审批（下单到审批最长 24 小时）。')

# ---------------- 2. category x region cube ----------------
st.subheader('2. 品类 × 客户大区（切片 / 切块 / 旋转）')
if not show(sc, catreg, cmsg, '暂无品类数据'):
    st.stop()
row_opts = list(DIMS) + list(UNSUPPORTED_DIMS)
label = lambda d: DIMS.get(d) or f'{UNSUPPORTED_DIMS[d]}（数据不支持）'  # noqa: E731
c1, c2, c3, c4 = st.columns(4)
rows = c1.selectbox('行维度', row_opts, index=row_opts.index('product_category'), format_func=label, key='rows')
cols = c2.selectbox('列维度（旋转）', ['none'] + list(DIMS), index=1 + list(DIMS).index('customer_region'), format_func=lambda d: '无' if d == 'none' else DIMS[d], key='cols')
cols = None if cols == 'none' else cols
measure = c3.selectbox('指标', list(MEASURES), format_func=lambda m: f'{MEASURES[m][0]}（{MEASURES[m][1]}）', key='measure')
swap = c4.checkbox('交换行列', key='swap')
if swap and cols:
    rows, cols = cols, rows
f1, f2, f3 = st.columns(3)
fy = f1.multiselect('年份筛选', sorted(catreg.month.str[:4].unique()), key='fy')
fr = f2.multiselect('客户大区筛选', sorted(catreg.customer_region.unique()), key='fr')
fc = f3.multiselect('品类筛选', sorted(catreg.product_category.unique()), key='fc')
filters = {'product_category': fc, 'customer_region': fr}
cat = catreg.assign(year=catreg.month.str[:4])
if fy:
    cat = cat[cat.year.isin(fy)]
ops = [n for n, v in (('切片', any(len(v) == 1 for v in [fy, fr, fc])), ('切块', sum(bool(v) for v in [fy, fr, fc]) >= 2), ('旋转', bool(swap and cols)))if v]
st.caption('当前操作：' + ('、'.join(ops) if ops else '全量汇总') + '。单值筛选 = 切片；两个以上维度同时筛选 = 切块；交换行列 = 旋转。')
status, pv, msg = cube(cat.drop(columns=['year']), rows, cols, measure, filters)
if status == 'ok':
    st.dataframe(pv, hide_index=True)
    unit = MEASURES[measure][1]
    st.caption(f'单位：{unit}。合计 {float(pv.drop(columns=[rows]).to_numpy().sum()):,.2f} {unit}' if measure == 'merchandise_sales_usd'
               else f'单位：{unit}。')
    if rows == 'month' or cols == 'month':
        if '2026-11' in set(cat.month):
            st.warning('2026-11 为不完整月（截至 2026-11-07）。')
else:
    (st.info if status == 'empty' else st.error)(msg)
st.caption('客户大区按客户所在地（人口普查四区）；州、渠道、毛利不在允许视图或数据中。金额为商品金额，不含运费。')
