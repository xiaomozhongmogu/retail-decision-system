"""UI page: prediction (UI-01 skeleton)."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import banner, show, view  # noqa: E402,F401

st.title('复购预测')
banner()
status, df, msg = view('ads.risk_summary_latest')
if show(status, df, msg, '暂无评分'):
    st.dataframe(df, hide_index=True)
st.warning('模型在测试期的个体区分能力接近随机（ROC-AUC 0.515），只用于平均复购水平参考（docs/model_card.md）。评估与名单试算由 UI-05 接入。')
