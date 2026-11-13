"""AI-05: restricted SQL execution for the query assistant.

Two layers; the second one is the security boundary, the first only gives early, readable refusals:
1. validate(sql, params): DuckDB's own parser (json_serialize_sql) must return exactly one SELECT; every table is an
   allowed ADS view (or a CTE of the same query), no table functions, every function and column is on a whitelist,
   values are bound parameters, a row limit is enforced.
2. execute(): runs in a separate process against a *sandbox* database that contains only the allowed views,
   materialised as tables (no DWD/DWS, no customer-level tables, no warehouse attached), opened read-only, with
   external access and extension autoload/autoinstall disabled, memory and threads capped, and the configuration
   locked before the query runs. The process is killed at the timeout. Even a query that slipped past layer 1 can
   only read the allowed aggregates and cannot reach files, the network or other databases.
run_plan(plan) executes AI-04's trusted plans (query_view calls + post-processing) without any SQL from the question.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
SANDBOX_DIR = ROOT / 'warehouse/sandbox'
MAX_ROWS, TIMEOUT_S = 5000, 5.0
FUNCS = {'sum', 'count', 'count_star', 'avg', 'min', 'max', 'median', 'stddev_samp', 'round', 'abs', 'coalesce', 'nullif', 'ifnull', 'greatest', 'least',
         'strftime', 'date_trunc', 'year', 'month', 'quarter', 'lower', 'upper', 'concat', 'row_number', 'rank', 'dense_rank', 'lag', 'lead', 'first', 'any_value',
         '+', '-', '*', '/', '//', '%', '~~', '!~~', '||'}


class Refused(ValueError):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def _allowed():
    from runtime import pointer, query_view
    ptr = pointer()
    cols = {}
    for v in ptr['allowed_views']:
        r = query_view(v, limit=1)
        cols[v] = r.get('columns', [])
    return ptr, cols


def _walk(node, acc):
    if isinstance(node, dict):
        t = node.get('type')
        if t == 'BASE_TABLE':
            acc['tables'].add((node.get('schema_name') or '', node.get('table_name', '')))
        elif t == 'TABLE_FUNCTION':
            acc['table_functions'].add(json.dumps(node.get('function', {}).get('function_name')))
        if node.get('class') == 'FUNCTION' or t == 'FUNCTION':
            acc['functions'].add(node.get('function_name', ''))
        if node.get('class') == 'COLUMN_REF':
            acc['columns'].add(tuple(node.get('column_names', [])))
        if node.get('class') == 'PARAMETER':
            acc['params'] += 1
        if node.get('class') == 'SUBQUERY' or t == 'SUBQUERY':
            acc['subqueries'] += 1
        if isinstance(node.get('alias'), str) and node['alias']:
            acc['aliases'].add(node['alias'])
        if 'cte_map' in node:
            for e in node['cte_map'].get('map', []):
                acc['ctes'].add(e.get('key', ''))
                for a in (e.get('value', {}).get('aliases') or []):
                    acc['aliases'].add(a)
        for v in node.values():
            _walk(v, acc)
    elif isinstance(node, list):
        for v in node:
            _walk(v, acc)


def validate(sql: str, params: list | None = None) -> dict:
    """Layer 1. Returns the AST summary or raises Refused(code, message)."""
    import duckdb
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 4000:
        raise Refused('invalid_argument', 'SQL 为空或过长')
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', sql):
        raise Refused('invalid_argument', 'SQL 含控制字符')                    # NUL bytes (G-035)
    j = json.loads(duckdb.connect().execute('SELECT json_serialize_sql(?)', [sql]).fetchone()[0])
    if j.get('error'):
        raise Refused('query_rejected', f"只允许单条只读 SELECT（{j.get('error_message', '')[:80]}）")
    if len(j['statements']) != 1:
        raise Refused('query_rejected', '只允许一条语句')
    if '"SHOW_REF"' in json.dumps(j):                                          # SHOW / DESCRIBE / SUMMARIZE parse as SELECT (G-015)
        raise Refused('query_rejected', '不允许查看库结构（SHOW / DESCRIBE / SUMMARIZE）')
    acc = {'tables': set(), 'table_functions': set(), 'functions': set(), 'columns': set(), 'params': 0, 'subqueries': 0, 'aliases': set(), 'ctes': set()}
    _walk(j['statements'][0], acc)
    if not acc['tables']:
        raise Refused('query_rejected', '查询必须读取允许的视图（不接受 VALUES 或无表 SELECT）')
    ptr, cols = _allowed()
    allowed_tables = {tuple(v.split('.', 1)) for v in ptr['allowed_views']}
    for sch, name in acc['tables']:
        if (sch, name) not in allowed_tables and not (sch == '' and name in acc['ctes']):
            raise Refused('query_rejected', f'不允许的表：{sch + "." if sch else ""}{name}')
    if acc['table_functions']:
        raise Refused('query_rejected', f"不允许表函数（如读取文件）：{', '.join(acc['table_functions'])}")
    bad_f = sorted(f for f in acc['functions'] if f.lower() not in FUNCS)
    if bad_f:
        raise Refused('query_rejected', f'不允许的函数：{bad_f}')
    names = {c for cs in cols.values() for c in cs} | acc['aliases'] | acc['ctes']
    bad_c = sorted('.'.join(c) for c in acc['columns'] if c[-1] not in names)
    if bad_c:
        raise Refused('unknown_field', f'不允许的列：{bad_c}')
    if acc['params'] != len(params or []):
        raise Refused('invalid_argument', f"参数个数不符：SQL 中 {acc['params']} 个，提供 {len(params or [])} 个")
    return {'tables': sorted('.'.join(t) for t in acc['tables']), 'functions': sorted(acc['functions']), 'params': acc['params'], 'release': ptr['version']}


def sandbox_path() -> Path:
    """Build (once per release) a database holding only the allowed views as tables."""
    import duckdb
    from runtime import pointer, query_view
    ptr = pointer()
    p = SANDBOX_DIR / f"{ptr['version']}-allowed.duckdb"
    if p.exists():
        return p
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    con.execute('CREATE SCHEMA ads')
    for v in ptr['allowed_views']:
        r = query_view(v, limit=5000)
        df = __import__('pandas').DataFrame(r['rows'], columns=r['columns'])
        for c in df.columns:
            num = __import__('pandas').to_numeric(df[c], errors='coerce')
            if df[c].notna().sum() and num.notna().sum() == df[c].notna().sum() and not c.endswith(('month', 'date', 'day')):
                df[c] = num
        con.register('src_df', df)
        con.execute(f'CREATE TABLE {v} AS SELECT * FROM src_df')
        con.unregister('src_df')
    con.execute('CHECKPOINT')
    con.close()
    os.replace(tmp, p)
    os.chmod(p, 0o444)
    return p


WORKER = r'''
import duckdb, json, sys
req = json.loads(sys.stdin.read())
con = duckdb.connect(req['db'], read_only=True)
for s in ["SET enable_external_access = false", "SET autoload_known_extensions = false", "SET autoinstall_known_extensions = false",
          "SET memory_limit = '256MB'", "SET threads = 1", "SET lock_configuration = true"]:
    con.execute(s)
try:
    # layer 2 on its own: exactly one SELECT statement before it is wrapped; newlines keep a trailing -- comment inside (G-016/G-031)
    st = con.extract_statements(req['sql'])
    if len(st) != 1 or st[0].type != duckdb.StatementType.SELECT or '\x00' in req['sql']:
        raise PermissionError('only one SELECT statement is allowed')
    cur = con.execute("SELECT * FROM (\n" + req['sql'] + "\n) AS q LIMIT " + str(req['max_rows'] + 1), req['params'])
    cols = [d[0] for d in cur.description]
    rows = [[None if v is None else (v if isinstance(v, (int, float, str, bool)) else str(v)) for v in r] for r in cur.fetchall()]
    print(json.dumps({'ok': True, 'columns': cols, 'rows': rows}))
except Exception as e:
    print(json.dumps({'ok': False, 'error': type(e).__name__ + ': ' + str(e)[:200]}))
'''


def execute(sql: str, params: list | None = None, max_rows: int = MAX_ROWS, timeout_s: float = TIMEOUT_S, skip_validation: bool = False) -> dict:
    """Validated query in the sandbox process. skip_validation exists only to test the sandbox boundary on its own."""
    params = list(params or [])
    try:
        meta = {} if skip_validation else validate(sql, params)
    except Refused as e:
        return {'status': 'unsupported', 'error': {'code': e.code, 'message': str(e), 'retryable': False}}
    db = sandbox_path()
    req = json.dumps({'db': str(db), 'sql': sql, 'params': params, 'max_rows': max_rows})
    try:
        p = subprocess.run([sys.executable, '-I', '-c', WORKER], input=req, capture_output=True, text=True, timeout=timeout_s,
                           env={'PATH': '/usr/bin:/bin'})
    except subprocess.TimeoutExpired:
        return {'status': 'error', 'error': {'code': 'timeout', 'message': f'查询超过 {timeout_s} 秒被终止', 'retryable': True}}
    try:
        out = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {'status': 'error', 'error': {'code': 'error', 'message': (p.stderr or 'worker failed')[-200:], 'retryable': False}}
    if not out['ok']:
        return {'status': 'error', 'error': {'code': 'query_rejected' if 'Permission' in out['error'] or 'disabled' in out['error'] else 'error', 'message': out['error'], 'retryable': False}}
    if len(out['rows']) > max_rows:
        return {'status': 'error', 'error': {'code': 'row_limit_exceeded', 'message': f'结果超过 {max_rows} 行', 'retryable': False}}
    return {'status': 'ok' if out['rows'] else 'empty', 'columns': out['columns'], 'rows': out['rows'], 'mode': 'live', 'dataset_version': db.name.split('-allowed')[0],
            'evidence_ids': ['sql:' + hashlib.sha256((sql + json.dumps(params)).encode()).hexdigest()[:8]], 'validation': meta}


# ---------------- trusted plans from AI-04 ----------------
def _num(x):
    return Decimal(str(x)) if x not in (None, '') else Decimal(0)


def run_plan(plan: dict) -> dict:
    """Execute an AI-04 plan: query_view calls only, then deterministic post-processing."""
    from runtime import query_view
    if plan.get('status') != 'ok':
        return {'status': plan.get('status', 'error'), 'rows': []}
    call = plan['calls'][0]
    r = query_view(call['view'], call['columns'], call['where'] or None)
    if r['status'] in ('error', 'unsupported'):
        return r
    data = [dict(zip(r['columns'], x)) for x in r['rows']]
    ev = ['view:' + call['view'], 'sql:' + hashlib.sha256(json.dumps(call, sort_keys=True).encode()).hexdigest()[:8]]
    post = plan.get('post', {})
    if post.get('latest_snapshot'):
        last = max(d['as_of_date'] for d in data)
        if post.get('state'):
            n = sum(int(d['customers']) for d in data if d['as_of_date'] == last and d['lifecycle_state'] == post['state'])
            return {'status': 'ok', 'kind': 'value', 'value': n, 'unit': 'customers', 'as_of': last, 'state': post['state'], 'evidence_ids': ev, 'dataset_version': r['dataset_version']}
        return {'status': 'ok', 'kind': 'table', 'columns': ['lifecycle_state', 'customers'], 'rows': [[d['lifecycle_state'], int(d['customers'])] for d in data if d['as_of_date'] == last],
                'as_of': last, 'evidence_ids': ev, 'dataset_version': r['dataset_version']}
    if post.get('latest_matured'):
        d = max(data, key=lambda d: d['as_of_date'])
        return {'status': 'ok', 'kind': 'value', 'value': float(d['repurchase_rate_30d']), 'unit': 'ratio', 'n': int(d['population']), 'as_of': d['as_of_date'],
                'evidence_ids': ev, 'dataset_version': r['dataset_version']}
    if 'months_since_first' in post:
        cells = [d for d in data if int(d['months_since_first']) == post['months_since_first'] and str(d['immature']) != 'True']
        act, size = sum(int(d['active_customers']) for d in cells), sum(int(d['cohort_customers']) for d in cells)
        return {'status': 'ok', 'kind': 'value', 'value': round(act / size, 4) if size else None, 'unit': 'ratio', 'n': size, 'cohorts': len(cells),
                'note': '各成熟 cohort 合并：首单后第 1 个月仍有购买的客户 ÷ cohort 人数', 'evidence_ids': ev, 'dataset_version': r['dataset_version']}
    m, f, group = post['measure'], post.get('filters') or {}, post.get('group_by') or []
    timekey = 'day' if post.get('by_day') and 'day' in data[0] else 'month'

    def agg(rows):
        s = lambda k: sum(_num(x.get(k)) for x in rows)  # noqa: E731
        if m == 'aov_usd':
            o = s('valid_orders')
            return (s('merchandise_sales_usd') / o) if o else None
        return s(m)

    def select(period):
        out = []
        for d in data:
            if period.get('months') is not None and d.get('month', d.get('day', ''))[:7] not in period['months']:
                continue
            if period.get('days') and not (period['days'][0] <= d['day'] < period['days'][1]):
                continue
            if any(d.get(k) not in v for k, v in f.items()):
                continue
            out.append(d)
        return out

    cur = select(post['periods'][0])
    if not cur:
        return {'status': 'empty', 'rows': [], 'message': '所选条件没有数据', 'evidence_ids': ev}
    res = {'status': 'ok', 'measure': m, 'evidence_ids': ev, 'dataset_version': r['dataset_version'], 'aov_recomputed_from_sums': post.get('aov_recomputed_from_sums', False)}
    if group:
        keys = sorted({tuple(d[g] for g in group) for d in cur})
        table = [[*k, agg([d for d in cur if tuple(d[g] for g in group) == k])] for k in keys]
        if post.get('share'):
            tot = sum(v for *_, v in table)
            table = [[*k, v, (v / tot) if tot else None] for *k, v in table]
        table.sort(key=lambda x: x[len(group)] or 0, reverse=(post.get('rank') or {}).get('descending', True))
        if post.get('rank'):
            if post['rank']['top_n']:
                table = table[:post['rank']['top_n']]
        res.update({'kind': 'table', 'columns': group + [m] + (['share'] if post.get('share') else []), 'rows': [[*x[:-1], float(x[-1]) if x[-1] is not None else None] if not post.get('share') else [*x[:-2], float(x[-2]), float(x[-1]) if x[-1] is not None else None] for x in table]})
    elif post.get('by_month') or post.get('by_day'):
        keys = sorted({d[timekey][:7] if timekey == 'month' else d['day'] for d in cur})
        res.update({'kind': 'series', 'columns': [timekey, m], 'rows': [[k, float(v) if (v := agg([d for d in cur if (d[timekey][:7] if timekey == 'month' else d['day']) == k])) is not None else None] for k in keys]})
    else:
        v = agg(cur)
        res.update({'kind': 'value', 'value': float(v) if v is not None else None, 'n_rows': len(cur)})
        if post.get('compare') and len(post['periods']) > 1:
            base = select(post['periods'][1])
            b = agg(base) if base else None
            res.update({'base_value': float(b) if b is not None else None, 'base_months': post['periods'][1]['months'] or [f"{post['periods'][1]['days'][0]} 至 {post['periods'][1]['days'][1]}（不含）"],
                        'change': float((v - b) / b) if (b not in (None, 0) and v is not None) else None,
                        'change_status': 'ok' if b not in (None, 0) else 'zero_denominator' if b == 0 else 'no_base'})
    if m in ('valid_lines', 'merchandise_sales_usd') and any(d.get('month') == '2026-11' for d in cur) or any(str(d.get('partial_period')) == 'True' for d in cur):
        res.setdefault('warnings', []).append({'code': 'partial_period', 'message': '包含不完整月份 2026-11'})
    return res
