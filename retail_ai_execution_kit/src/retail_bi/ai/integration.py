"""AI-15: one entry point for the three AI modules with shared versions, one LLM client and one event log.

run_query / run_report / run_agent call the modules (AI-06, AI-09, AI-12) with a shared LLMClient, so calls, tokens and
estimated cost add up across modules, and append one event per run to logs/ai/events.jsonl:
  module, request, mode, outcome, seconds, llm calls/tokens/cost for this run, tool steps, evidence ids, errors,
  dataset / metric / kb / policy versions.
The event never contains the API key, prompt text or raw customer rows (redact() removes key-like strings).
mode is derived from what actually happened: live (a model reply was used) | fallback_no_key | timeout | rate_limited |
llm_error | rules_only (LLM switched off) | replay. A replay or fallback is never reported as live.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src/retail_bi/ai'))
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
import client as C  # noqa: E402

EVENTS = ROOT / 'logs/ai/events.jsonl'
KEYLIKE = re.compile(r'sk-[A-Za-z0-9_-]{8,}|Bearer\s+\S+|api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s,}]+', re.I)


def redact(obj):
    """Mask key-like substrings in every string value (structure is kept intact)."""
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        return KEYLIKE.sub('[REDACTED]', obj)
    if obj is None or isinstance(obj, (int, float, bool)):
        return obj
    return KEYLIKE.sub('[REDACTED]', str(obj))


def versions():
    from runtime import pointer
    import report_facts as RF
    import retrieval as R
    import policy_engine as PE
    return {'dataset_version': pointer()['version'], 'metric_version': RF.metric_version(), 'kb_version': R.KB_VERSION,
            'policy_version': PE.load_policy()['policy_version']}


class Hub:
    def __init__(self, client=None, use_llm: bool = True, events: Path | None = EVENTS):
        self.client = client or C.LLMClient()
        self.use_llm, self.events = use_llm, events
        self.v = versions()

    def _llm_delta(self, before):
        b = self.client.budget()
        return {'calls': b['calls'] - before['calls'], 'tokens_in': b['tokens_in'] - before['tokens_in'], 'tokens_out': b['tokens_out'] - before['tokens_out'],
                'cost_usd': round(b['cost_usd'] - before['cost_usd'], 6)}

    @staticmethod
    def _mode(errors: list, used_llm_text: bool, use_llm: bool, replay=False):
        if replay:
            return 'replay'
        if not use_llm:
            return 'rules_only'
        if used_llm_text:
            return 'live'
        codes = [e.get('code') for e in errors if isinstance(e, dict)]
        for c, m in (('llm_unavailable', 'fallback_no_key'), ('timeout', 'timeout'), ('rate_limited', 'rate_limited')):
            if c in codes:
                return m
        return 'llm_error' if codes else 'fallback_no_key'

    def _log(self, ev):
        ev = redact({'at': datetime.now(timezone.utc).isoformat(timespec='seconds'), **ev, 'versions': self.v})
        if self.events:
            self.events.parent.mkdir(parents=True, exist_ok=True)
            with open(self.events, 'a', encoding='utf-8') as f:
                f.write(json.dumps(ev, ensure_ascii=False) + '\n')
        return ev

    def _llm_errors(self):
        """Error codes of the LLM calls in this run, from the client's own call log when available."""
        return list(getattr(self, '_errs', []))

    def _wrap_client(self):
        """Record error codes the client returns, without changing its behaviour."""
        self._errs = []
        orig = self.client.chat

        def chat(*a, **k):
            r = orig(*a, **k)
            if r.get('status') != 'ok' and r.get('error'):
                self._errs.append({'code': r['error'].get('code')})
            return r
        self.client.chat = chat
        return orig

    # ---- modules ----
    def run_query(self, question: str, session=None):
        import query_assistant as QA
        s = session or QA.Session('hub', use_llm=self.use_llm, client=self.client)
        s.client = self.client
        b0, t0, orig = self.client.budget(), time.perf_counter(), self._wrap_client()
        try:
            a = s.ask(question)
        finally:
            self.client.chat = orig
        used = bool(a.get('note')) or (a.get('intent') or {}).get('parser') == 'llm'
        ev = self._log({'module': 'query_assistant', 'request': hashlib.sha256(question.encode()).hexdigest()[:10], 'outcome': a['status'],
                        'mode': self._mode(self._llm_errors(), used, self.use_llm), 'seconds': round(time.perf_counter() - t0, 3), 'llm': self._llm_delta(b0),
                        'tools': ['understand', 'plan', 'run_plan'] if a.get('query') else ['understand'], 'evidence_ids': a.get('evidence_ids', []),
                        'errors': [a['error']] if a.get('error') else [], 'result_dataset_version': a.get('dataset_version')})
        return a, ev

    def run_report(self, mode: str = 'live', replay_text: str | None = None):
        import report_generator as G
        from report_facts import build_weekly_facts
        b0, t0, orig = self.client.budget(), time.perf_counter(), self._wrap_client()
        try:
            facts = build_weekly_facts()
            r = G.generate_weekly_report(facts, client=self.client, mode=(mode if self.use_llm or mode == 'replay' else 'template'), replay_text=replay_text)
        finally:
            self.client.chat = orig
        ev = self._log({'module': 'weekly_report', 'request': f'week:{facts["window"]["start"]}', 'outcome': r['status'],
                        'mode': self._mode(self._llm_errors(), r['mode'] == 'live', self.use_llm or mode == 'replay', replay=r['mode'] == 'replay'),
                        'generator_mode': r['mode'], 'seconds': round(time.perf_counter() - t0, 3), 'llm': self._llm_delta(b0),
                        'tools': ['build_weekly_facts', 'retrieve', 'llm_write' if mode != 'template' else 'template', 'final_check'],
                        'attempts': [{k: x.get(k) for k in ('attempt', 'result', 'errors')} for x in r.get('attempts', [])],
                        'evidence_ids': r.get('evidence_ids', []), 'errors': [{'code': e} for e in r.get('final_check_errors', [])],
                        'result_dataset_version': facts['dataset_version']})
        return r, ev

    def run_agent(self, request: dict, store=None):
        import retention_agent as RA
        from drafts import DraftStore
        b0, t0, orig = self.client.budget(), time.perf_counter(), self._wrap_client()
        try:
            r = RA.RetentionAgent(store or DraftStore(), client=self.client, use_llm=self.use_llm).run(request)
        finally:
            self.client.chat = orig
        used = (r.get('proposal') or {}).get('mode') == 'live_llm'
        ev = self._log({'module': 'retention_agent', 'request': r['request_id'], 'outcome': r['state'], 'mode': self._mode(self._llm_errors(), used, self.use_llm),
                        'seconds': round(time.perf_counter() - t0, 3), 'llm': self._llm_delta(b0),
                        'tools': [{'tool': t['tool'], 'ok': t['ok'], 'ms': t.get('ms')} for t in r['trace']], 'evidence_ids': r.get('evidence', []),
                        'errors': [r['error']] if r.get('error') else [], 'sent': False,
                        'result_dataset_version': next((e.split('@')[1] for e in r.get('evidence', []) if e.startswith('profile:')), None)})
        return r, ev
