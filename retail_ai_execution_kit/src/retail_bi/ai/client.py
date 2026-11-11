"""AI-01: one LLM adapter with configuration boundaries (OpenAI-compatible chat completions over HTTP).

Configuration comes only from the environment (or a local .env that is git-ignored):
  LLM_API_KEY, LLM_BASE_URL, LLM_MODEL       provider credentials and model
  LLM_ALLOW_PAID=1                           explicit permission to make paid calls (default: not allowed)
  LLM_MAX_CALLS (default 50)                 call budget per process
  LLM_MAX_COST_USD (default 0.50)            cost budget per process, estimated from token prices below
  LLM_PRICE_IN_PER_1K / LLM_PRICE_OUT_PER_1K token prices in USD (default 0 = unknown -> calls refused
                                             unless LLM_ALLOW_UNKNOWN_PRICE=1)
  LLM_TIMEOUT_S (default 30), LLM_MAX_RETRIES (default 2)
Without a key, without paid permission, or over budget the client does not call anything and returns
status 'error' with code 'llm_unavailable' / 'budget_denied'. mode is 'live', 'replay' or 'fixture'.

The transport uses the standard library (urllib), because the installed OpenAI SDK fails to start when a
SOCKS proxy variable is set (socksio not installed). Logs never contain the key or full prompts.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[3]


def _load_dotenv(path: Path = ROOT / '.env') -> dict:
    out = {}
    if path.is_file():
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


@dataclass
class Config:
    api_key: str = ''
    base_url: str = ''
    model: str = ''
    allow_paid: bool = False
    allow_unknown_price: bool = False
    max_calls: int = 50
    max_cost_usd: float = 0.50
    price_in_per_1k: float = 0.0
    price_out_per_1k: float = 0.0
    timeout_s: float = 30.0
    max_retries: int = 2

    @classmethod
    def from_env(cls, env: dict | None = None) -> 'Config':
        e = {**_load_dotenv(), **os.environ} if env is None else env
        f = lambda k, d: float(e.get(k) or d)  # noqa: E731
        return cls(api_key=e.get('LLM_API_KEY', ''), base_url=e.get('LLM_BASE_URL', '').rstrip('/'), model=e.get('LLM_MODEL', ''),
                   allow_paid=e.get('LLM_ALLOW_PAID') == '1', allow_unknown_price=e.get('LLM_ALLOW_UNKNOWN_PRICE') == '1',
                   max_calls=int(e.get('LLM_MAX_CALLS') or 50), max_cost_usd=f('LLM_MAX_COST_USD', 0.5),
                   price_in_per_1k=f('LLM_PRICE_IN_PER_1K', 0), price_out_per_1k=f('LLM_PRICE_OUT_PER_1K', 0),
                   timeout_s=f('LLM_TIMEOUT_S', 30), max_retries=int(e.get('LLM_MAX_RETRIES') or 2))

    def redacted(self) -> dict:
        return {'base_url': self.base_url, 'model': self.model, 'api_key': ('set, ' + str(len(self.api_key)) + ' chars') if self.api_key else 'missing',
                'allow_paid': self.allow_paid, 'max_calls': self.max_calls, 'max_cost_usd': self.max_cost_usd,
                'price_in_per_1k': self.price_in_per_1k, 'price_out_per_1k': self.price_out_per_1k, 'timeout_s': self.timeout_s, 'max_retries': self.max_retries}


class TransportError(RuntimeError):
    def __init__(self, msg, retryable, status=None):
        super().__init__(msg)
        self.retryable, self.status = retryable, status


def http_transport(cfg: Config, payload: dict) -> dict:
    req = urllib.request.Request(cfg.base_url + '/chat/completions', data=json.dumps(payload).encode('utf-8'), method='POST',
                                 headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {cfg.api_key}'})
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout_s) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise TransportError(f'HTTP {e.code}', retryable=e.code in (408, 409, 429, 500, 502, 503, 504), status=e.code) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise TransportError(f'network: {type(e).__name__}', retryable=True) from None


@dataclass
class LLMClient:
    cfg: Config = field(default_factory=Config.from_env)
    transport: Callable[[Config, dict], dict] = http_transport
    mode: str = 'live'                       # 'live' | 'replay' | 'fixture'
    log_path: Path | None = ROOT / 'logs/ai/llm_calls.jsonl'
    calls: int = 0
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    sleep: Callable[[float], None] = time.sleep

    def _deny(self, code, message, retryable=False):
        return {'status': 'error', 'mode': self.mode, 'model': self.cfg.model or None,
                'error': {'code': code, 'message': message, 'retryable': retryable}}

    def _log(self, rec):
        if self.log_path is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')

    def chat(self, messages: list[dict], *, json_schema: dict | None = None, max_tokens: int = 400, purpose: str = 'unspecified') -> dict:
        """One bounded call. json_schema -> ask for a JSON object and validate required keys."""
        if self.mode == 'live':
            if not (self.cfg.api_key and self.cfg.base_url and self.cfg.model):
                return self._deny('llm_unavailable', 'LLM 未配置（缺 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）', retryable=True)
            if not self.cfg.allow_paid:
                return self._deny('budget_denied', '未授权付费调用（需要 LLM_ALLOW_PAID=1）')
            if self.cfg.price_in_per_1k == 0 and self.cfg.price_out_per_1k == 0 and not self.cfg.allow_unknown_price:
                return self._deny('budget_denied', '模型价格未配置，无法控制费用（设置 LLM_PRICE_*_PER_1K 或 LLM_ALLOW_UNKNOWN_PRICE=1）')
        if self.calls >= self.cfg.max_calls:
            return self._deny('budget_denied', f'调用次数已达上限 {self.cfg.max_calls}')
        worst = (sum(len(m['content']) for m in messages) / 4 / 1000) * self.cfg.price_in_per_1k + (max_tokens / 1000) * self.cfg.price_out_per_1k
        if self.cost_usd + worst > self.cfg.max_cost_usd:
            return self._deny('budget_denied', f'预计费用将超过上限 {self.cfg.max_cost_usd} USD')
        payload = {'model': self.cfg.model, 'messages': messages, 'max_tokens': max_tokens, 'temperature': 0}
        if json_schema:
            payload['response_format'] = {'type': 'json_object'}
        t0, attempt, last = time.perf_counter(), 0, None
        while True:
            attempt += 1
            self.calls += 1
            try:
                resp = self.transport(self.cfg, payload)
                break
            except TransportError as e:
                last = e
                if not e.retryable or attempt > self.cfg.max_retries or self.calls >= self.cfg.max_calls:
                    self._log({'at': datetime.now(timezone.utc).isoformat(), 'purpose': purpose, 'mode': self.mode, 'model': self.cfg.model,
                               'status': 'error', 'error': str(e), 'attempts': attempt, 'seconds': round(time.perf_counter() - t0, 3)})
                    code = 'timeout' if 'Timeout' in str(e) else ('rate_limited' if e.status == 429 else 'llm_unavailable')
                    return self._deny(code, f'调用失败：{e}（{attempt} 次尝试）', retryable=e.retryable)
                self.sleep(min(2 ** attempt, 8))
        usage = resp.get('usage') or {}
        ti, to = int(usage.get('prompt_tokens', 0)), int(usage.get('completion_tokens', 0))
        cost = ti / 1000 * self.cfg.price_in_per_1k + to / 1000 * self.cfg.price_out_per_1k
        self.tokens_in, self.tokens_out, self.cost_usd = self.tokens_in + ti, self.tokens_out + to, self.cost_usd + cost
        text = ((resp.get('choices') or [{}])[0].get('message') or {}).get('content') or ''
        out = {'status': 'ok', 'mode': self.mode, 'model': resp.get('model', self.cfg.model), 'text': text,
               'usage': {'prompt_tokens': ti, 'completion_tokens': to, 'cost_usd': round(cost, 6)}, 'attempts': attempt,
               'seconds': round(time.perf_counter() - t0, 3)}
        if json_schema:
            try:
                obj = json.loads(text)
                missing = [k for k in json_schema.get('required', []) if k not in obj]
                if missing:
                    raise ValueError(f'missing keys {missing}')
                out['json'] = obj
            except (ValueError, TypeError) as e:
                out = {**out, 'status': 'error', 'error': {'code': 'invalid_output', 'message': f'结构化输出不合格：{e}', 'retryable': False}}
        self._log({'at': datetime.now(timezone.utc).isoformat(), 'purpose': purpose, 'mode': self.mode, 'model': out['model'], 'status': out['status'],
                   'prompt_sha256': hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode()).hexdigest()[:16],
                   'tokens_in': ti, 'tokens_out': to, 'cost_usd': round(cost, 6), 'attempts': attempt, 'seconds': out['seconds']})
        return out

    def budget(self) -> dict:
        return {'calls': self.calls, 'max_calls': self.cfg.max_calls, 'cost_usd': round(self.cost_usd, 6), 'max_cost_usd': self.cfg.max_cost_usd,
                'tokens_in': self.tokens_in, 'tokens_out': self.tokens_out}


def fixture_transport(responses: list):
    """Deterministic transport for tests/replay: returns or raises items in order."""
    it = iter(responses)

    def t(cfg, payload):
        r = next(it)
        if isinstance(r, Exception):
            raise r
        return r
    return t
