"""UI page: data (UI-01 skeleton)."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import banner, show, view  # noqa: E402,F401

st.title('数据口径与质量')
banner()
st.markdown('- 有效购买 = 截止前已审批的订单；取消单列；数据中没有退款（`docs/transaction_rules.md`）。\n'
            '- 数据字典：`docs/data_dictionary.md`；质量门槛：`reports/data/quality_checks.json`。')
st.info('详细的质量与口径页面由 UI-02 接入。')
