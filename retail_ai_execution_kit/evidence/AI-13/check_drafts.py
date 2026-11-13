"""AI-13 check: stored fields, idempotency, revise/withdraw/review transitions, approved is still not sent,
and agent reruns of the same request create no second draft. usage: .venv/bin/python evidence/AI-13/check_drafts.py"""
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/ai'))
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
import retention_agent as RA  # noqa: E402
from drafts import DraftStore  # noqa: E402
from runtime import open_current  # noqa: E402

ok, examples = [], []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, '' if cond else str(detail)[:300])


tmp = Path(tempfile.mkdtemp())
st = DraftStore(tmp / 'd.sqlite')
base = dict(customer_id='customer_000001', action='coupon', discount=0.1, copy='您好，我们为您准备了一张 10% 的专属优惠。', reasons=['所有检查通过'],
            evidence=['profile:customer_000001@wh', 'doc:retention_policy#4@retention-policy-v1'], policy_version='retention-policy-v1',
            budget={'cost_usd': 15.05, 'budget_after_usd': 15.05}, mode='live_llm')
a = st.save('req-A', **base)
d = a['data']
check('saved fields: suggestion, reasons, evidence, rule version, budget result, copy, pending status', a['created'] and d['action'] == 'coupon' and d['reasons'] and d['evidence']
      and d['policy_version'] == 'retention-policy-v1' and d['budget']['cost_usd'] == 15.05 and d['copy'] and d['status'] == 'pending_review')
check('saved draft is explicitly not sent', d['sent'] is False and d['delivery'] == 'not_sent')
b = st.save('req-A', **base)
check('same request again returns the same draft, no second row', b['created'] is False and b['data']['draft_id'] == d['draft_id'] and len(st.list()) == 1)
c = st.save('req-A', **{**base, 'discount': 0.15})
check('same request id with different content is refused, original kept', c['status'] == 'error' and c['error']['code'] == 'idempotency_conflict' and st.get(d['draft_id'])['discount'] == 0.1)
# since the external test (G-034) a revision must pass the same copy rules as the agent: a coupon draft keeps its own percentage
bad = st.revise(d['draft_id'], '尊敬的客户，已为您发放五折券，立减五十元！', editor='运营审核员')
check('revise with copy that breaks the copy rules is refused, draft unchanged', bad['status'] == 'error' and bad['error']['code'] == 'invalid_argument'
      and st.get(d['draft_id'])['copy'].startswith('您好，我们为您'), bad)
r = st.revise(d['draft_id'], '您好，欢迎回来看看，10% 的专属优惠为您保留。', editor='运营审核员')
check('revise while pending: new copy, previous copy kept in history, still pending', r['status'] == 'ok' and r['data']['copy'].startswith('您好，欢迎')
      and any(h.get('_previous_copy', '').startswith('您好，我们为您') for h in r['data']['history']) and r['data']['status'] == 'pending_review')
r = st.review(d['draft_id'], 'approved', reviewer='运营审核员')
check('approve changes review status only; sent stays false', r['status'] == 'ok' and r['data']['status'] == 'approved' and r['data']['sent'] is False and r['data']['delivery'] == 'not_sent')
r = st.revise(d['draft_id'], 'x', editor='y')
check('cannot revise after approval', r['status'] == 'error' and r['error']['code'] == 'invalid_state')
r = st.withdraw(d['draft_id'], by='y')
check('cannot withdraw after approval', r['status'] == 'error' and r['error']['code'] == 'invalid_state')
e = st.save('req-B', **{**base, 'customer_id': 'customer_000002'})['data']
r = st.withdraw(e['draft_id'], by='运营审核员', reason='客户近期已购买')
check('withdraw while pending -> withdrawn, record kept (not deleted)', r['status'] == 'ok' and r['data']['status'] == 'withdrawn' and st.get(e['draft_id']) is not None)
r = st.review(e['draft_id'], 'approved', reviewer='x')
check('cannot approve a withdrawn draft', r['status'] == 'error')
r = st.review('draft-nope', 'approved', reviewer='x')
check('unknown draft -> not_found', r['status'] == 'error' and r['error']['code'] == 'not_found')
r = st.review(e['draft_id'], 'sent', reviewer='x')
check('there is no "sent" decision', r['status'] == 'error' and r['error']['code'] == 'invalid_argument')
cols = [x[1] for x in sqlite3.connect(tmp / 'd.sqlite').execute('PRAGMA table_info(drafts)')]
check('storage has sent/delivery columns and no send-time or channel columns', 'sent' in cols and 'delivery' in cols and not any(c in cols for c in ('sent_at', 'channel', 'phone', 'email')))
vals = {x['status'] for x in st.list()}
check('status vocabulary is review-only (pending_review / approved / rejected / withdrawn)', vals <= {'pending_review', 'approved', 'rejected', 'withdrawn'})
# agent idempotency end to end
con, _ = open_current()
cid = con.execute("SELECT customer_id FROM ads.customer_profile_latest WHERE lifecycle_state = 'dormant' AND orders_all_time >= 2 ORDER BY customer_id LIMIT 1").fetchone()[0]
con.close()
ag = RA.RetentionAgent(DraftStore(tmp / 'agent.sqlite'), use_llm=False)
r1 = ag.run({'request_id': 'weekly-2026-11-09-' + cid, 'customer_id': cid, 'context': {'consent': True}})
r2 = ag.run({'request_id': 'weekly-2026-11-09-' + cid, 'customer_id': cid, 'context': {'consent': True}})
check('agent rerun of the same request: second run finds the existing draft, no duplicate', r1['state'] == 'draft_saved' and r1['draft_created'] and r2['draft_created'] is False
      and r1['draft']['draft_id'] == r2['draft']['draft_id'] and len(ag.store.list()) == 1, (r1['state'], r2.get('draft_created')))
examples = [st.get(d['draft_id']), st.get(e['draft_id']), r1['draft']]
(ROOT / 'reports/ai/draft_examples.json').write_text(json.dumps({'task_id': 'AI-13', 'note': '草稿只是待审建议；本系统没有发送或发券能力，sent 始终为 false', 'examples': examples},
                                                                ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print(f'{sum(ok)}/{len(ok)} checks passed')
sys.exit(0 if all(ok) else 1)
