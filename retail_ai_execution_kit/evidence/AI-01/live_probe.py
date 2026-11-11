"""AI-01 live probe: one structured-JSON call through the adapter (real provider, small budget).
usage: .venv/bin/python evidence/AI-01/live_probe.py  (writes reports/ai/client_live_probe.json, key never written)"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/ai'))
from client import Config, LLMClient  # noqa: E402

cfg = Config.from_env()
cfg.max_calls, cfg.max_cost_usd = 3, 0.01
c = LLMClient(cfg=cfg)
r = c.chat([{'role': 'system', 'content': '只输出 JSON 对象。'},
            {'role': 'user', 'content': '把“有效订单 9113 单”拆成 JSON：{"metric": 指标名, "value": 数值, "unit": 单位}。'}],
           json_schema={'required': ['metric', 'value', 'unit']}, max_tokens=80, purpose='ai01_live_probe')
out = {'task_id': 'AI-01', 'config': cfg.redacted(), 'requested_model': cfg.model, 'returned_model': r.get('model'),
       'status': r['status'], 'json': r.get('json'), 'usage': r.get('usage'), 'seconds': r.get('seconds'), 'budget': c.budget(), 'error': r.get('error')}
(ROOT / 'reports/ai/client_live_probe.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(out, ensure_ascii=False))
ok = r['status'] == 'ok' and str(r['json'].get('value')).replace(',', '') in ('9113', '9113.0')
print('structured output ok:', ok)
sys.exit(0 if ok else 1)
