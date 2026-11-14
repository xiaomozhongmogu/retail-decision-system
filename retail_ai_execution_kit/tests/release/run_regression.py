"""REL-01: targeted integration and regression run over the critical paths.

Runs the checks each accepted task used (read-only checks; no rebuild of data, warehouse or models), records the
real command, exit code, duration and the summary line, and writes reports/release/test_summary.json.

Many checks also rewrite a committed report (for example reports/data/quality_checks.json). After each check the
runner compares every rewritten committed JSON file with the committed version, ignoring run-specific fields
(timestamps, durations, token use, cost, live model text), records whether the content was reproduced, and then
restores the committed file so evidence bound to it stays valid. Non-JSON rewrites are compared line by line.

usage: .venv/bin/python tests/release/run_regression.py [--only ID,ID] [--skip-live]
"""
from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = str(ROOT / '.venv/bin/python')
OUT = ROOT / 'reports/release/test_summary.json'
LOGS = ROOT / 'reports/release/regression_logs'

# id, critical path, command (relative to ROOT), uses the real LLM
CHECKS = [
    ('pytest', '数据规则 / 指标对账 / 时间切分与预处理范围', [PY, '-m', 'pytest', 'tests', '-q', '-p', 'no:cacheprovider'], False),
    ('data_quality_gate', '数据规则：清洗后质量门槛', [PY, 'tests/data/quality_gate.py'], False),
    ('dw_reconciliation', '指标对账：ODS→DWD→DWS→ADS 金额与计数', [PY, 'tests/warehouse/recon.py'], False),
    ('data_release', '数据发布包身份与内容', [PY, 'evidence/DATA-12/verify_release.py'], False),
    ('olap', 'OLAP 标准查询集与 DWD 重算一致', [PY, 'evidence/DW-08/run_and_check_olap.py'], False),
    ('runtime', '只读查询快照：发布、回滚、中断发布、只读', [PY, 'evidence/DW-10/verify_runtime.py'], False),
    ('trends', '经营趋势与不完整期间标识', [PY, 'evidence/EDA-02/verify_trends.py'], False),
    ('model_eval', '冻结测试结果可复核', [PY, 'evidence/ML-09/verify_evaluation.py'], False),
    ('scoring', '模型加载、版本校验、评分与适用性', [PY, 'evidence/ML-11/verify_scoring.py'], False),
    ('model_reproduce', '模型文件在新进程中加载并复现分数', [PY, 'evidence/ML-12/publish_model.py', 'reproduce'], False),
    ('intent', 'AI 查询意图与 Schema 约束', [PY, 'evidence/AI-04/check_intent.py'], True),
    ('sql_boundary', 'SQL 约束：只读、白名单视图、超时', [PY, 'evidence/AI-05/boundary_checks.py'], False),
    ('assistant', 'AI 查询回答与结果证据', [PY, 'evidence/AI-06/check_assistant.py'], True),
    ('nl2sql', 'NL2SQL 标准集按结果语义评测', [PY, 'eval/nl2sql_eval.py', '--tag', 'final'], True),
    ('report_facts', '周报事实与 DWD 重算一致', [PY, 'evidence/AI-08/verify_facts.py'], False),
    ('report_verify', '周报数字校验与修复上限（含真实调用）', [PY, 'evidence/AI-09/verify_report.py'], True),
    ('report_blind', '周报盲测包：已知问题拦截与误判', [PY, 'evidence/AI-09/recheck_blind_packet.py'], False),
    ('rag', '知识检索与依据引用', [PY, 'eval/rag_eval.py'], True),
    ('policy', '运营政策与预算规则', [PY, 'evidence/AI-11/policy_checks.py'], False),
    ('agent', '有限步骤 Agent（含真实调用）', [PY, 'evidence/AI-12/check_agent.py'], True),
    ('drafts', '草稿存储与审阅状态', [PY, 'evidence/AI-13/check_drafts.py'], False),
    ('agent_eval', 'Agent 边界场景', [PY, 'eval/agent_eval.py'], True),
    ('integration', '三模块联调、模式区分与脱敏日志', [PY, 'evidence/AI-15/integration_eval.py'], True),
    ('ui_smoke', '主要页面路径：五页冒烟与无发布版本空状态', [PY, 'evidence/UI-01/smoke.py'], False),
    ('ui_data', '数据口径页', [PY, 'evidence/UI-02/check.py'], False),
    ('ui_business', '经营页与 OLAP 下钻', [PY, 'evidence/UI-03/check.py'], False),
    ('ui_customers', '客户生命周期页', [PY, 'evidence/UI-04/check.py'], False),
    ('ui_prediction', '预测页与名单试算', [PY, 'evidence/UI-05/check.py'], False),
    ('ui_ai', 'AI 工作台页', [PY, 'evidence/UI-06/check_ai_page.py'], False),
    ('ui_review', '缓存、连接边界、异常恢复与密钥不外露', [PY, 'evidence/UI-07/check.py'], False),
]
VOLATILE = re.compile(r'(_at|^at$|rationale|_time|timestamp|seconds|_ms|^ms$|elapsed|duration|cost|tokens|usage|latency|run_id|session|sid|'
                      r'draft_id|request_id|tmp|path|llm|text|note|copy|proposal|attempts|answer|explanation|actions|hypotheses|raw)', re.I)
SUMMARY = re.compile(r'(\d+/\d+ (checks passed|pages ok|passed)|\d+ passed|passed.*in [\d.]+s|failed|ok \d+ facts|accuracy|\bok\b)', re.I)


def git(*a, cwd=ROOT):
    return subprocess.run(['git', *a], cwd=cwd, capture_output=True, text=True).stdout


TOP = Path(git('rev-parse', '--show-toplevel').strip())


def changed_tracked():
    """Tracked files under ROOT with uncommitted changes, as paths relative to ROOT."""
    out = []
    for l in git('status', '--porcelain', '--untracked-files=no', '--', '.').splitlines():   # porcelain paths are repo-root relative
        if l.strip():
            out.append(str((TOP / l[3:].strip().strip('"')).relative_to(ROOT)))
    return out


def untracked():
    return set(git('ls-files', '--others', '--exclude-standard', '--', '.').splitlines())


def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if not VOLATILE.search(str(k))}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o


def compare(rel):
    """True if the rewritten file reproduces the committed content apart from run-specific fields."""
    old = subprocess.run(['git', 'show', f'HEAD:./{rel}'], cwd=ROOT, capture_output=True, text=True).stdout
    new = (ROOT / rel).read_text(encoding='utf-8', errors='replace')
    if rel.endswith('.json'):
        try:
            if rel.endswith('.jsonl'):
                return [strip(json.loads(x)) for x in old.splitlines() if x.strip()] == [strip(json.loads(x)) for x in new.splitlines() if x.strip()]
            return strip(json.loads(old)) == strip(json.loads(new))
        except ValueError:
            pass
    keep = lambda t: [l for l in t.splitlines() if not re.search(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}|seconds|耗时|用时|cost|tokens', l)]  # noqa: E731
    return keep(old) == keep(new)


def restore(paths):
    if paths:
        subprocess.run(['git', 'checkout', '--', *paths], cwd=ROOT, check=True)


def server_paths():
    """Start the app on a spare port, request health and the five page paths, stop it."""
    t0 = time.time()
    p = subprocess.Popen([str(ROOT / '.venv/bin/streamlit'), 'run', 'app.py', '--server.headless', 'true', '--server.port', '8611',
                          '--browser.gatherUsageStats', 'false'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    codes = {}
    try:
        for _ in range(60):
            try:
                codes['health'] = urllib.request.urlopen('http://localhost:8611/_stcore/health', timeout=2).status
                break
            except OSError:
                time.sleep(1)
        for page in ('data', 'business', 'customers', 'prediction', 'ai'):
            codes[page] = urllib.request.urlopen(f'http://localhost:8611/{page}', timeout=5).status
    except OSError as e:
        codes['error'] = type(e).__name__
    finally:
        p.terminate()
        p.wait(timeout=20)
    ok = codes.get('health') == 200 and all(codes.get(k) == 200 for k in ('data', 'business', 'customers', 'prediction', 'ai'))
    return {'id': 'server_paths', 'critical_path': '应用启动：健康检查与五个页面路径', 'command': 'streamlit run app.py --server.port 8611; GET /_stcore/health and 5 page paths',
            'uses_live_llm': False, 'exit_code': 0 if ok else 1, 'status': 'passed' if ok else 'failed', 'seconds': round(time.time() - t0, 1),
            'summary': json.dumps(codes), 'rewritten_files': [], 'not_reproduced': []}


def main():
    only = set(sys.argv[sys.argv.index('--only') + 1].split(',')) if '--only' in sys.argv else None
    skip_live = '--skip-live' in sys.argv
    if changed_tracked():
        sys.exit('refusing to run: the working tree has uncommitted changes to tracked files (they would be restored)')
    LOGS.mkdir(parents=True, exist_ok=True)
    results = []
    for cid, path, cmd, live in CHECKS:
        if only and cid not in only:
            continue
        rel_cmd = ' '.join(c.replace(str(ROOT) + '/', '') for c in cmd)
        if live and skip_live:
            results.append({'id': cid, 'critical_path': path, 'command': rel_cmd, 'uses_live_llm': True, 'exit_code': None, 'status': 'not_run',
                            'summary': 'skipped (--skip-live)', 'rewritten_files': [], 'not_reproduced': []})
            continue
        before_untracked = untracked()
        t0 = time.time()
        try:
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1200)
            code, out = r.returncode, r.stdout + r.stderr
        except subprocess.TimeoutExpired as e:
            code, out = 'timeout', (e.stdout or b'').decode(errors='replace') if isinstance(e.stdout, bytes) else str(e.stdout or '')
        secs = round(time.time() - t0, 1)
        (LOGS / f'{cid}.log').write_text(f'$ {rel_cmd}\nexit={code} seconds={secs}\n\n{out}', encoding='utf-8')
        lines = [l.strip() for l in out.splitlines() if re.search(r'\d+/\d+ (checks passed|pages ok|passed)|^\d+ passed|gate passed', l.strip())] \
            or [l.strip() for l in out.splitlines() if SUMMARY.search(l) and 'Error' not in l]
        rewritten = changed_tracked()
        not_repro = [f for f in rewritten if not compare(f)]
        restore(rewritten)
        new_untracked = sorted(untracked() - before_untracked - {str(p.relative_to(ROOT)) for p in LOGS.glob('*.log')})
        results.append({'id': cid, 'critical_path': path, 'command': rel_cmd, 'uses_live_llm': live, 'exit_code': code,
                        'status': 'passed' if code == 0 else 'failed', 'seconds': secs, 'summary': (lines[-1] if lines else out.strip()[-200:])[:300],
                        'rewritten_files': rewritten, 'not_reproduced': not_repro, 'new_untracked_files': new_untracked})
        print(f"{results[-1]['status']:7} {cid:18} exit={code} {secs:>6}s  {results[-1]['summary'][:90]}"
              + (f'  NOT REPRODUCED: {not_repro}' if not_repro else ''), flush=True)
    if not only or 'server_paths' in only:
        results.append(server_paths())
        print(f"{results[-1]['status']:7} server_paths       {results[-1]['summary']}", flush=True)
    # the run must not leave any evidence stale (a check rewriting a bound file that is not tracked would show up here)
    v = subprocess.run(['python3', 'scripts/project.py', 'validate'], cwd=ROOT, capture_output=True, text=True)
    ledger = json.loads(v.stdout) if v.stdout.strip().startswith('{') else {'result': 'unreadable', 'errors': [v.stderr[-300:]]}
    results.append({'id': 'ledger_after_run', 'critical_path': '回归后所有证据仍与文件一致（台账校验）', 'command': 'python3 scripts/project.py validate',
                    'uses_live_llm': False, 'exit_code': v.returncode, 'status': 'passed' if ledger.get('result') == 'ledger_valid' else 'failed',
                    'summary': ledger.get('result', '') + ('' if ledger.get('result') == 'ledger_valid' else ' ' + '; '.join(ledger.get('errors', [])[:5])),
                    'rewritten_files': [], 'not_reproduced': []})
    print(f"{results[-1]['status']:7} ledger_after_run   {results[-1]['summary'][:200]}", flush=True)
    import importlib.metadata as md
    summary = {
        'task_id': 'REL-01', 'run_at': datetime.now(timezone.utc).isoformat(), 'git_commit': git('rev-parse', 'HEAD').strip(),
        'environment': {'os': platform.platform(), 'python': platform.python_version(),
                        'packages': {p: md.version(p) for p in ('duckdb', 'pandas', 'scikit-learn', 'streamlit', 'altair') if _has(md, p)},
                        'llm_configured': bool(os.environ.get('LLM_API_KEY') or (ROOT / '.env').exists())},
        'totals': {s: sum(r['status'] == s for r in results) for s in ('passed', 'failed', 'not_run')},
        'not_reproduced_files': sorted({f for r in results for f in r['not_reproduced']}),
        'checks': results,
        'notes': ['重写的已提交文件在比较后已恢复为提交版本；比较时忽略时间、耗时、令牌、费用与真实模型生成文本等字段。',
                  '真实 LLM 调用的检查依赖网络与服务状态；失败如实记录，不重试到通过。', '未运行的检查记为 not_run，不记为 passed。'],
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(summary['totals'], ensure_ascii=False), 'not reproduced:', summary['not_reproduced_files'])
    sys.exit(0 if summary['totals']['failed'] == 0 else 1)


def _has(md, p):
    try:
        md.version(p)
        return True
    except md.PackageNotFoundError:
        return False


if __name__ == '__main__':
    main()
