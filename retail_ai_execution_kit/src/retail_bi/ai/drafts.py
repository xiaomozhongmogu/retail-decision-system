"""AI-13: draft store for the retention agent (save_draft in contracts/interfaces.md).

A draft is a proposal waiting for human review. Nothing here sends a message or issues a coupon: every record has
sent = false and delivery = "not_sent"; approving a draft only changes its review status.
- save(request_id, ...)   idempotent: the draft id is derived from request_id; repeating the same request returns the
                          existing draft (no second row, no second side effect). A different payload under the same
                          request_id is refused (idempotency_conflict).
- revise(draft_id, copy)  only while pending_review; keeps the previous text in the history.
- withdraw(draft_id)      pending_review -> withdrawn (kept, not deleted).
- review(draft_id, decision, reviewer)  pending_review -> approved | rejected; still not sent.
Storage: SQLite file under warehouse/drafts/ (git-ignored), separate from the read-only release.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = ROOT / 'warehouse/drafts/drafts.sqlite'
STATES = {'pending_review', 'approved', 'rejected', 'withdrawn'}
DDL = """CREATE TABLE IF NOT EXISTS drafts (
  draft_id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, payload_sha TEXT NOT NULL, customer_id TEXT NOT NULL,
  action TEXT NOT NULL, discount REAL NOT NULL, copy TEXT NOT NULL, reasons TEXT NOT NULL, evidence TEXT NOT NULL,
  policy_version TEXT NOT NULL, budget TEXT NOT NULL, mode TEXT NOT NULL, status TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0,
  delivery TEXT NOT NULL DEFAULT 'not_sent', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, history TEXT NOT NULL)"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class DraftStore:
    def __init__(self, path: Path = DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._con() as c:
            c.execute(DDL)

    def _con(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    @staticmethod
    def _row(r):
        if r is None:
            return None
        d = dict(r)
        for k in ('reasons', 'evidence', 'budget', 'history'):
            d[k] = json.loads(d[k])
        d['sent'] = bool(d['sent'])
        return d

    def save(self, request_id: str, customer_id: str, action: str, discount: float, copy: str, reasons: list, evidence: list,
             policy_version: str, budget: dict, mode: str) -> dict:
        payload = json.dumps([customer_id, action, float(discount), copy, reasons, evidence, policy_version, budget, mode], ensure_ascii=False, sort_keys=True)
        sha = hashlib.sha256(payload.encode()).hexdigest()[:16]
        did = 'draft-' + hashlib.sha256(request_id.encode()).hexdigest()[:12]
        with self._con() as c:
            old = c.execute('SELECT * FROM drafts WHERE request_id = ?', [request_id]).fetchone()
            if old is not None:
                if old['payload_sha'] != sha:
                    return {'status': 'error', 'error': {'code': 'idempotency_conflict', 'message': '同一请求编号已保存过内容不同的草稿，未覆盖', 'retryable': False},
                            'data': self._row(old)}
                return {'status': 'ok', 'created': False, 'data': self._row(old)}
            t = _now()
            try:
                c.execute('INSERT INTO drafts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?,?,?)',
                          [did, request_id, sha, customer_id, action, float(discount), copy, json.dumps(reasons, ensure_ascii=False), json.dumps(evidence, ensure_ascii=False),
                           policy_version, json.dumps(budget, ensure_ascii=False), mode, 'pending_review', 'not_sent', t, t,
                           json.dumps([{'at': t, 'event': 'created', 'status': 'pending_review'}], ensure_ascii=False)])
            except sqlite3.IntegrityError:                     # another writer saved the same request first (G-025): same rules as above
                old = c.execute('SELECT * FROM drafts WHERE request_id = ?', [request_id]).fetchone()
                if old is None or old['payload_sha'] != sha:
                    return {'status': 'error', 'error': {'code': 'idempotency_conflict', 'message': '同一请求编号已保存过内容不同的草稿，未覆盖', 'retryable': False},
                            'data': self._row(old) if old else None}
                return {'status': 'ok', 'created': False, 'data': self._row(old)}
            return {'status': 'ok', 'created': True, 'data': self._row(c.execute('SELECT * FROM drafts WHERE draft_id = ?', [did]).fetchone())}

    def get(self, draft_id: str):
        with self._con() as c:
            return self._row(c.execute('SELECT * FROM drafts WHERE draft_id = ?', [draft_id]).fetchone())

    def list(self, status: str | None = None):
        with self._con() as c:
            q = 'SELECT * FROM drafts' + (' WHERE status = ?' if status else '') + ' ORDER BY created_at, draft_id'
            return [self._row(r) for r in c.execute(q, [status] if status else []).fetchall()]

    def _transition(self, draft_id, allowed_from, new_status, event, **changes):
        with self._con() as c:
            r = c.execute('SELECT * FROM drafts WHERE draft_id = ?', [draft_id]).fetchone()
            if r is None:
                return {'status': 'error', 'error': {'code': 'not_found', 'message': '没有这个草稿', 'retryable': False}}
            if r['status'] not in allowed_from:
                return {'status': 'error', 'error': {'code': 'invalid_state', 'message': f"草稿当前状态为 {r['status']}，不能{event}", 'retryable': False}, 'data': self._row(r)}
            hist = json.loads(r['history'])
            t = _now()
            hist.append({'at': t, 'event': event, 'status': new_status, **{k: v for k, v in changes.items() if k.startswith('_')}})
            sets = {k: v for k, v in changes.items() if not k.startswith('_')}
            cols = ', '.join(f'{k} = ?' for k in sets)
            c.execute(f"UPDATE drafts SET status = ?, updated_at = ?, history = ?{', ' + cols if cols else ''} WHERE draft_id = ?",
                      [new_status, t, json.dumps(hist, ensure_ascii=False), *sets.values(), draft_id])
            return {'status': 'ok', 'data': self._row(c.execute('SELECT * FROM drafts WHERE draft_id = ?', [draft_id]).fetchone())}

    def revise(self, draft_id: str, new_copy: str, editor: str):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import policy_engine as PE
        cur0 = self.get(draft_id)
        if cur0 and cur0['status'] == 'pending_review':      # other states are refused below as invalid_state
            v = PE.copy_violations(new_copy, cur0['action'], cur0['discount'])      # same copy rules as the agent (G-034)
            if v:
                return {'status': 'error', 'error': {'code': 'invalid_argument', 'message': '修改后的文案未通过校验：' + '；'.join(v), 'retryable': False}, 'data': cur0}
        cur = self.get(draft_id)
        return self._transition(draft_id, {'pending_review'}, 'pending_review', '修改文案', copy=new_copy,
                                _previous_copy=cur['copy'] if cur else None, _editor=editor)

    def withdraw(self, draft_id: str, by: str, reason: str = ''):
        return self._transition(draft_id, {'pending_review'}, 'withdrawn', '撤回', _by=by, _reason=reason)

    def review(self, draft_id: str, decision: str, reviewer: str, comment: str = ''):
        if decision not in ('approved', 'rejected'):
            return {'status': 'error', 'error': {'code': 'invalid_argument', 'message': 'decision 只能是 approved 或 rejected', 'retryable': False}}
        return self._transition(draft_id, {'pending_review'}, decision, '审核', _reviewer=reviewer, _comment=comment,
                                _note='审核通过只表示内容获准，本系统没有发送或发券能力，sent 仍为 false')
