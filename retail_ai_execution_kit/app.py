"""Streamlit entry (UI-01): five page groups — 数据口径, 经营, 客户, 预测, AI 工作台.

run:  .venv/bin/streamlit run app.py
Pages live in src/retail_bi/ui/pages/ and read only the published read-only release (runtime.py).
"""
import streamlit as st

st.set_page_config(page_title='电商零售智能决策与 AI 运营助手', layout='wide')
P = 'src/retail_bi/ui/pages/'
PAGES = {
    '数据口径': [st.Page(P + 'data.py', title='数据口径与质量', url_path='data', default=True)],
    '经营': [st.Page(P + 'business.py', title='经营总览', url_path='business')],
    '客户': [st.Page(P + 'customers.py', title='生命周期与分群', url_path='customers')],
    '预测': [st.Page(P + 'prediction.py', title='复购预测', url_path='prediction')],
    'AI 工作台': [st.Page(P + 'ai.py', title='AI 工作台', url_path='ai')],
}
st.navigation(PAGES).run()
