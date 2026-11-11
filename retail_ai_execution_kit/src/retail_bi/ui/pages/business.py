"""UI page: business (UI-01 skeleton)."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import banner, show, view  # noqa: E402,F401

st.title('经营总览')
banner()
status, df, msg = view('ads.kpi_monthly', ['month', 'valid_orders', 'merchandise_sales_usd', 'buyers', 'aov_usd', 'partial_period'])
if show(status, df, msg, '暂无经营数据'):
    st.dataframe(df, hide_index=True)
    st.caption('2026-11 为不完整月（partial_period = True）。OLAP 交互由 UI-03 接入。')
