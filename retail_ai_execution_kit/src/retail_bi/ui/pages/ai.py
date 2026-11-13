"""UI page: AI workbench (UI-06) — query assistant, weekly report, retention agent.

Every result is stored in st.session_state under a request key, so Streamlit reruns never call the model again;
a new model call happens only on an explicit button press. State lives in this browser session only. Replay output is
labelled and is not evidence of a live call. Drafts are proposals for review: nothing is ever sent.
"""
import hashlib
import json
import sys
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

UI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(UI))
sys.path.insert(0, str(UI.parent / 'ai'))
from common import ROOT, banner  # noqa: E402

st.title('AI 工作台')
info = banner()
if info is None:
    st.stop()

from client import Config  # noqa: E402

cfg = Config.from_env()
llm_ready = bool(cfg.api_key and cfg.base_url and cfg.model and cfg.allow_paid)
S = st.session_state
S.setdefault('sid', 'ui-' + uuid.uuid4().hex[:8])
c1, c2 = st.columns([3, 1])
c1.caption(f"LLM：{'已配置（' + cfg.model + '）' if llm_ready else '未配置或未授权付费，AI 部分将使用规则与模板'} · 会话 {S['sid']} · 结果只保存在本浏览器会话中")
# the switch is kept in the URL (?llm=0), so a page refresh does not silently turn paid calls back on (external UI test U-005)
use_llm = c2.toggle('使用 LLM', value=llm_ready and st.query_params.get('llm', '1') != '0', disabled=not llm_ready, key='use_llm')
st.query_params['llm'] = '1' if use_llm else '0'
st.caption('刷新页面会清空本页的对话、周报与 Agent 结果（“使用 LLM”开关和草稿库会保留）；需要保存时请先用各处的导出按钮。')
TIER_ZH = {'high': '高价值（近 90 天常买）', 'normal': '普通（近 90 天买过）', 'lapsed_high': '历史高价值（近 90 天未买）', 'lapsed_normal': '历史普通（近 90 天未买）'}
STATE_ZH = {'ok': '已回答', 'clarify': '需要澄清', 'unsupported': '不支持', 'empty': '没有数据', 'error': '执行失败', 'cancelled': '已取消'}

t1, t2, t3 = st.tabs(['查询助手', '经营周报', '挽回 Agent'])

# ---------------- 1. query assistant ----------------
with t1:
    import query_assistant as QA
    if 'qa' not in S or S.get('qa_llm') != use_llm:
        S['qa'], S['qa_llm'], S['qa_log'], S['qa_pending'] = QA.Session(S['sid'], use_llm=use_llm), use_llm, [], None
    st.caption('示例：2026年10月的商品金额是多少？ / 那西部呢 / 2025年哪个品类的商品金额最高？ / 最近6个月订单数趋势。数字只来自实际执行的查询。')
    q = st.chat_input('输入经营问题', key='qa_input')
    if q:
        S['qa_pending'] = q
    if S['qa_pending']:
        st.info(f"待执行：{S['qa_pending']}")
        b1, b2, _ = st.columns([1, 1, 4])
        if b1.button('执行', key='qa_run', type='primary'):
            with st.spinner('正在查询…'):
                S['qa_log'].append(S['qa'].ask(S['qa_pending']))
            S['qa_pending'] = None
            st.rerun()
        if b2.button('取消', key='qa_cancel'):
            S['qa'].cancel()
            S['qa_log'].append(S['qa'].ask(S['qa_pending']))
            S['qa_pending'] = None
            st.rerun()
    for i, a in enumerate(S['qa_log']):
        with st.chat_message('user'):
            st.write(a['question'])
        with st.chat_message('assistant'):
            st.markdown(f"**{STATE_ZH.get(a['status'], a['status'])}** · {a.get('answer') or ''}")
            if a.get('note'):
                st.caption('口径提示（LLM 生成，已校验不含数字）：' + a['note'])
            for w in a.get('warnings') or []:
                st.warning(w['message'])
            res = a.get('result') or {}
            if res.get('rows'):
                st.dataframe(pd.DataFrame(res['rows'], columns=res.get('columns')), hide_index=True)
            if a.get('query'):
                with st.expander('查询与证据'):
                    st.code(a['query']['sql'], language='sql')
                    st.json({'视图': a['query']['view'], '后处理': a['query']['post_processing'], '期间': a['query']['periods'], '口径': a.get('metric_definition'),
                             'as_of': a.get('as_of'), '数据版本': a.get('dataset_version'), '证据': a.get('evidence_ids')}, expanded=False)
            if a['status'] == 'error' and st.button('重试', key=f'qa_retry_{i}'):
                S['qa_pending'] = a['question']
                st.rerun()
    if S['qa_log']:
        d1, d2, _ = st.columns([1, 1, 4])
        d1.download_button('导出对话 JSON', json.dumps(S['qa_log'], ensure_ascii=False, indent=1, default=str), file_name=f"qa_{S['sid']}.json", key='qa_export')
        if d2.button('清空会话', key='qa_clear'):
            S.pop('qa')
            st.rerun()

# ---------------- 2. weekly report ----------------
with t2:
    import report_generator as G
    from report_facts import build_weekly_facts
    replay = ROOT / 'reports/ai/weekly_report_replay.json'
    mode = st.radio('生成方式', ['live', 'template', 'replay'], horizontal=True, key='wr_mode',
                    format_func={'live': '真实 LLM', 'template': '可信模板（不调用 LLM）', 'replay': '回放上次记录的 LLM 文本'}.get, index=0 if use_llm else 1)
    if mode == 'live' and not use_llm:
        st.warning('LLM 未启用，选择“真实 LLM”时将自动回退为可信模板。')
    if st.button('生成本周周报', key='wr_go', type='primary'):
        with st.spinner('正在计算事实并生成周报…'):
            facts = build_weekly_facts()
            if mode == 'replay':
                body = json.loads(replay.read_text(encoding='utf-8')).get('llm_body') if replay.exists() else None
                r = G.generate_weekly_report(facts, mode='replay', replay_text=json.dumps(body, ensure_ascii=False)) if body else {'status': 'error', 'mode': 'replay', 'text': '', 'attempts': [], 'final_check_errors': ['没有可回放的记录']}
            else:
                r = G.generate_weekly_report(facts, mode=mode if use_llm else 'template')
        S['wr'] = r
    r = S.get('wr')
    if r:
        if r['mode'] == 'replay':
            st.error('回放模式：以下解释文字来自上次记录的 LLM 输出，不是本次真实调用，不能作为在线调用的验收证据。')
        st.markdown(f"生成模式 **{r['mode']}**（请求 {r.get('requested_mode', mode)}） · LLM 尝试 {len(r.get('attempts', []))} 次 · 最终数字复核 "
                    + ('**通过**' if not r.get('final_check_errors') else '**未通过：** ' + '；'.join(r['final_check_errors'])))
        if r.get('attempts'):
            with st.expander('LLM 尝试与校验记录'):
                st.json(r['attempts'], expanded=False)
        st.markdown(r.get('text') or '')
        if r.get('evidence_ids'):
            st.caption('引用：' + '、'.join(r['evidence_ids']))
        st.download_button('下载周报 Markdown', r.get('text') or '', file_name='weekly_report.md', key='wr_export')

# ---------------- 3. retention agent ----------------
with t3:
    import retention_agent as RA
    from drafts import DraftStore
    from runtime import open_current
    store = DraftStore()
    con, _ = open_current()
    samples = [r[0] for r in con.execute("""SELECT customer_id FROM ads.customer_profile_latest WHERE lifecycle_state IN ('dormant', 'at_risk') AND orders_all_time >= 2
                                            ORDER BY customer_id LIMIT 20""").fetchall()]
    con.close()
    a1, a2 = st.columns([2, 3])
    cid = a1.selectbox('客户编号（示例：沉睡或沉默预警的多单客户）', samples, key='ag_cid')
    cid = a1.text_input('或输入其他客户编号', value='', key='ag_cid2').strip() or cid
    with a2.expander('演示配置（不是数据事实）', expanded=True):
        consent = st.checkbox('已同意营销', value=True, key='ag_consent')
        complaint = st.checkbox('有未结投诉', value=False, key='ag_complaint')
        stock = st.checkbox('相关商品有货', value=True, key='ag_stock')
        contacts = st.number_input('近 30 天已触达次数', 0, 5, 0, key='ag_contacts')
        # no upper bound: an invalid entry used to keep the old value silently (U-004); the rule engine denies over-budget runs
        spent = st.number_input('本周已用预算（USD，周预算 200）', min_value=0.0, value=0.0, step=1.0, key='ag_spent')
    ctx = {'consent': consent, 'open_complaint': complaint, 'in_stock': stock, 'contacts_last_30d': int(contacts)}
    rid = 'ui-' + hashlib.sha256(json.dumps([cid, ctx, spent, use_llm, S['sid']], sort_keys=True).encode()).hexdigest()[:12]
    S.setdefault('ag_runs', {})
    if st.button('运行 Agent（生成待审草稿）', key='ag_go', type='primary'):
        if rid in S['ag_runs']:
            st.info('相同客户与配置已经运行过，显示上次结果，不重复调用模型。')
        else:
            with st.spinner('Agent 运行中：画像 → 风险 → 政策 → 提议 → 约束 → 文案 → 草稿'):
                S['ag_runs'][rid] = RA.RetentionAgent(store, use_llm=use_llm).run({'request_id': rid, 'customer_id': cid, 'context': ctx, 'spent_usd': spent})
        S['ag_last'] = rid
    run = S['ag_runs'].get(S.get('ag_last'))
    if run:
        st.markdown(f"结束状态 **{run['state']}** · 用时 {run.get('seconds')} 秒 · **未发送**（本系统没有发送或发券能力）")
        st.dataframe(pd.DataFrame([{'步骤': t['step'], '工具': t['tool'], '成功': t['ok'], '耗时 ms': t.get('ms'), '结果摘要': json.dumps(t['result'], ensure_ascii=False, default=str)[:160]}
                                   for t in run['trace']]), hide_index=True)
        if run.get('proposal'):
            st.caption(f"LLM/规则提议（{run['proposal'].get('mode')}）：{run['proposal'].get('action')} {run['proposal'].get('discount')} — {run['proposal'].get('rationale')}")
        if run.get('decision'):
            d = run['decision']
            st.markdown(f"规则判定：**{d['decision']}**；成本 {d['cost_usd']} USD；周预算使用后 {d['budget_after_usd']} USD；"
                        f"价值层级 **{TIER_ZH.get(d['value_tier'], d['value_tier'])}**")
            st.caption('价值层级由规则按历史购买计算，只决定折扣上限；是否给优惠还要看资格、库存、毛利和预算，模型概率不参与判定。')
            for x in d['reasons']:
                st.caption('· ' + x)
        if run.get('error'):
            st.error(run['error'].get('message'))
        st.download_button('导出本次轨迹 JSON', json.dumps(run, ensure_ascii=False, indent=1, default=str), file_name=f'agent_{rid}.json', key='ag_export')
    st.subheader('草稿审核')
    rows = store.list()
    if not rows:
        st.info('还没有草稿。')
    else:
        st.dataframe(pd.DataFrame([{'草稿': x['draft_id'], '客户': x['customer_id'], '动作': x['action'], '折扣': x['discount'], '状态': x['status'],
                                    '已发送': '否' if not x['sent'] else '是', '文案': x['copy'], '文案来源': x['mode']} for x in rows]), hide_index=True)
        pend = [x['draft_id'] for x in rows if x['status'] == 'pending_review']
        if pend:
            r1, r2, r3, r4 = st.columns([2, 1, 1, 1])
            did = r1.selectbox('待审草稿', pend, key='dr_pick')
            for col, (lab, act) in zip((r2, r3, r4), (('通过', 'approved'), ('驳回', 'rejected'), ('撤回', 'withdraw'))):
                if col.button(lab, key=f'dr_{act}'):
                    res = store.withdraw(did, by='页面审核人') if act == 'withdraw' else store.review(did, act, reviewer='页面审核人')
                    (st.success if res['status'] == 'ok' else st.error)(f"{did}：{res['data']['status'] if res['status'] == 'ok' else res['error']['message']}（仍未发送）")
        st.caption('“通过”只表示内容获准，不会发送消息或发放优惠。')
