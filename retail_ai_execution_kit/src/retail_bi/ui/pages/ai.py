"""UI page: ai (UI-01 skeleton)."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import banner, show, view  # noqa: E402,F401

st.title('AI 工作台')
banner()
st.info('查询助手、诊断周报和运营 Agent 由 AI-01 至 AI-15 与 UI-06 接入。当前未配置 LLM 凭据，AI 功能不可用。')
