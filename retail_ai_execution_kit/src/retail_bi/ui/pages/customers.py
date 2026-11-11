"""UI page: customers (UI-01 skeleton)."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import banner, show, view  # noqa: E402,F401

st.title('客户生命周期与分群')
banner()
status, df, msg = view('ads.lifecycle_mix_weekly', ['as_of_date', 'lifecycle_state', 'customers'], {'as_of_date': '2026-11-02'})
if show(status, df, msg, '暂无生命周期数据'):
    st.dataframe(df, hide_index=True)
    st.caption('状态只描述距上次购买的时间，不代表流失（docs/lifecycle_rules.md）。cohort 与分群由 UI-04 接入。')
