"""UI-06 check (draft, before AI-15): the AI workbench with AppTest — three modules usable, evidence shown, execute/
cancel/retry/export, replay labelled, drafts never sent, reruns never repeat model or agent calls, sessions isolated.
LLM is switched off here (deterministic, no cost); live calls are covered by AI-06/AI-09/AI-12 checks.
usage: .venv/bin/python evidence/UI-06/check_ai_page.py"""
import sys
import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/ai'))
sys.path.insert(0, str(ROOT / 'src/retail_bi/ui'))
import drafts  # noqa: E402
import query_assistant as QA  # noqa: E402
import report_generator as G  # noqa: E402
import retention_agent as RA  # noqa: E402

TMP = Path(tempfile.mkdtemp()) / 'ui_drafts.sqlite'
drafts.DraftStore.__init__.__defaults__ = (TMP,)          # keep test drafts out of the real store
calls = {'ask': 0, 'report': 0, 'agent': 0}
_ask, _rep, _run = QA.Session.ask, G.generate_weekly_report, RA.RetentionAgent.run
QA.Session.ask = lambda self, q: (calls.__setitem__('ask', calls['ask'] + 1), _ask(self, q))[1]
G.generate_weekly_report = lambda *a, **k: (calls.__setitem__('report', calls['report'] + 1), _rep(*a, **k))[1]
RA.RetentionAgent.run = lambda self, req: (calls.__setitem__('agent', calls['agent'] + 1), _run(self, req))[1]
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, '' if cond else str(detail)[:300])


def page():
    at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=180)
    at.run()
    at.switch_page('src/retail_bi/ui/pages/ai.py')
    at.run()
    t = [x for x in at.toggle if x.key == 'use_llm']
    if t and t[0].value:
        t[0].set_value(False).run()
    return at


def btn(at, key):
    return [b for b in at.button if b.key == key][0]


def text(at):
    return '\n'.join([m.value for m in at.markdown] + [c.value for c in at.caption] + [x.value for x in at.info] + [x.value for x in at.warning]
                     + [x.value for x in at.error] + [x.value for x in at.success])


at = page()
check('page renders, three tabs, LLM status shown', not at.exception and [x.label for x in at.tabs] == ['查询助手', '经营周报', '挽回 Agent'] and 'LLM：' in text(at), [str(e.value) for e in at.exception])
# query assistant: pending -> execute
at.chat_input[0].set_value('2026年10月的商品金额是多少？').run()
check('question waits for an explicit execute (pending shown, no call yet)', '待执行：2026年10月的商品金额是多少？' in text(at) and calls['ask'] == 0)
btn(at, 'qa_run').click().run()
t = text(at)
check('answer shown with status, value and the query/evidence expander', '已回答' in t and '47,590.59 USD' in t and any(e.label == '查询与证据' for e in at.expander) and len(at.code) >= 1, t[:300])
n = calls['ask']
for _ in range(3):
    at.run()
check('reruns do not ask again (results cached in session state)', calls['ask'] == n == 1, calls)
at.chat_input[0].set_value('那西部呢').run()
btn(at, 'qa_run').click().run()
check('follow-up in the same browser session uses its context', 'West' in text(at) and '10,514.63 USD' in text(at), text(at)[-300:])
at.chat_input[0].set_value('2025年的毛利是多少').run()
btn(at, 'qa_cancel').click().run()
check('cancel records a cancelled turn without running a query', '已取消' in text(at))
check('export button for the conversation exists', any(d.key == 'qa_export' for d in at.get('download_button')))
# error + retry
orig = QA.X.run_plan
QA.X.run_plan = lambda plan: (_ for _ in ()).throw(RuntimeError('db down'))
at.chat_input[0].set_value('2025年的客单价是多少').run()
btn(at, 'qa_run').click().run()
QA.X.run_plan = orig
check('failure shown as an error state with a retry button', '执行失败' in text(at) and any(b.key.startswith('qa_retry_') for b in at.button))
[b for b in at.button if b.key.startswith('qa_retry_')][0].click().run()
btn(at, 'qa_run').click().run()
check('retry re-runs the question and now answers', text(at).count('已回答') >= 3)
# session isolation
at2 = page()
at2.chat_input[0].set_value('那西部呢').run()
btn(at2, 'qa_run').click().run()
check('a second browser session does not see the first session context', '需要澄清' in text(at2) or '不支持' in text(at2), text(at2)[-200:])
# weekly report
at.radio[[r.key for r in at.radio].index('wr_mode')].set_value('template').run()
r0 = calls['report']
btn(at, 'wr_go').click().run()
t = text(at)
check('weekly report (template) shows mode, final check passed, citations and a download', '生成模式 **template**' in t and '最终数字复核 **通过**' in t and '引用：' in t
      and any(d.key == 'wr_export' for d in at.get('download_button')) and calls['report'] == r0 + 1, t[:200])
at.run(); at.run()
check('report is not regenerated on rerun', calls['report'] == r0 + 1)
at.radio[[r.key for r in at.radio].index('wr_mode')].set_value('replay').run()
btn(at, 'wr_go').click().run()
check('replay output carries a prominent label that it is not a live call', any('回放模式' in e.value and '不能作为在线调用的验收证据' in e.value for e in at.error))
# retention agent
a0 = calls['agent']
btn(at, 'ag_go').click().run()
t = text(at)
check('agent run shows end state, trace table, decision and "未发送"', '结束状态 **' in t and '**未发送**' in t and any('工具' in d.value.columns for d in at.dataframe) and calls['agent'] == a0 + 1, t[-400:])
btn(at, 'ag_go').click().run()
check('same customer and settings again: shown from cache, no second agent call', calls['agent'] == a0 + 1 and any('不重复调用模型' in i.value for i in at.info))
store = drafts.DraftStore(TMP)
ds = store.list()
check('the run produced exactly one pending draft, not sent', len(ds) == 1 and ds[0]['status'] == 'pending_review' and ds[0]['sent'] is False, ds)
if ds:
    btn(at, 'dr_approved').click().run()
    d = store.get(ds[0]['draft_id'])
    check('approving in the page changes review status only; still not sent', d['status'] == 'approved' and d['sent'] is False and any('仍未发送' in s.value for s in at.success))
check('no exceptions across the whole session', not at.exception and not at2.exception, [str(e.value) for e in at.exception])
print(f'{sum(ok)}/{len(ok)} checks passed; calls {calls}')
sys.exit(0 if all(ok) else 1)
