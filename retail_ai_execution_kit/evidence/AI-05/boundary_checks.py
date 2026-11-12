"""AI-05 boundary tests: layer-1 refusals, the sandbox boundary on its own (validation skipped), resource limits,
parameter binding, and AI-04 plans vs an independent DWD recompute. usage: .venv/bin/python evidence/AI-05/boundary_checks.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/ai'))
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
import query_intent as QI  # noqa: E402
import sql_executor as X  # noqa: E402
from runtime import open_current, pointer  # noqa: E402

res = []


def check(group, name, cond, detail=''):
    res.append({'group': group, 'check': name, 'status': 'passed' if cond else 'failed', 'detail': str(detail)[:240]})
    print('PASS' if cond else 'FAIL', f'[{group}]', name, '' if cond else str(detail)[:240])


REL = str(ROOT / 'warehouse/releases' / pointer()['file'])
# 1. allowed queries
r = X.execute('SELECT month, merchandise_sales_usd FROM ads.kpi_monthly WHERE month = ?', ['2026-10'])
check('allowed', 'single SELECT on an allowed view with a bound parameter', r['status'] == 'ok' and r['rows'][0][1] == 47590.59, r)
r = X.execute("WITH m AS (SELECT strftime(CAST(month || '-01' AS DATE), '%Y') AS y, merchandise_sales_usd FROM ads.kpi_monthly) SELECT y, round(sum(merchandise_sales_usd), 2) AS s FROM m GROUP BY y ORDER BY y")
check('allowed', 'CTE + aggregation + whitelisted functions', r['status'] == 'ok' and len(r['rows']) == 3, r)
# 2. layer-1 refusals
L1 = {'insert': "INSERT INTO ads.kpi_monthly VALUES ('x')", 'delete': 'DELETE FROM ads.kpi_monthly', 'update': "UPDATE ads.kpi_monthly SET month = 'x'",
      'create': 'CREATE TABLE t AS SELECT 1', 'drop': 'DROP VIEW ads.kpi_monthly', 'copy': "COPY ads.kpi_monthly TO '/tmp/x.csv'",
      'attach': f"ATTACH '{REL}' AS w (READ_ONLY)", 'install': 'INSTALL httpfs', 'load': 'LOAD httpfs', 'pragma': 'PRAGMA database_list', 'set': "SET enable_external_access = true",
      'two statements': 'SELECT 1; SELECT 2', 'stacked injection': "SELECT * FROM ads.kpi_monthly; DROP TABLE x",
      'read_csv': "SELECT * FROM read_csv('/etc/passwd')", 'read_text': "SELECT * FROM read_text('/etc/hosts')", 'glob': "SELECT * FROM glob('/Users/*')",
      'read_parquet url': "SELECT * FROM read_parquet('https://example.com/x.parquet')", 'dwd table': 'SELECT * FROM dwd.fact_order',
      'customer-level scores': 'SELECT * FROM ads.model_scores', 'customer profile': 'SELECT * FROM ads.customer_profile_latest',
      'catalog': 'SELECT * FROM information_schema.tables', 'duckdb_tables()': 'SELECT * FROM duckdb_tables()', 'getenv': "SELECT getenv('HOME')",
      'unknown column': 'SELECT customer_id FROM ads.kpi_monthly', 'param count': 'SELECT * FROM ads.kpi_monthly WHERE month = ?'}
for name, sql in L1.items():
    r = X.execute(sql)
    check('layer1', f'refused: {name}', r['status'] in ('unsupported', 'error') and r['error']['code'] in ('query_rejected', 'unknown_field', 'invalid_argument'), r)
# 3. sandbox boundary with validation skipped (proves layer 1 is not the security boundary)
SB = {'read_csv file': "SELECT * FROM read_csv('/etc/passwd')", 'read_text file': "SELECT * FROM read_text('/etc/hosts')", 'glob': "SELECT * FROM glob('/Users/*')",
      'http parquet': "SELECT * FROM read_parquet('https://example.com/x.parquet')", 'dwd table': 'SELECT * FROM dwd.fact_order',
      'model scores': 'SELECT * FROM ads.model_scores', 'customer profile': 'SELECT * FROM ads.customer_profile_latest', 'getenv': "SELECT getenv('HOME') AS h"}
for name, sql in SB.items():
    r = X.execute(sql, skip_validation=True)
    check('sandbox', f'blocked inside the sandbox without layer 1: {name}', r['status'] == 'error', r)
r = X.execute('SELECT table_schema, table_name FROM information_schema.tables ORDER BY 2', skip_validation=True)
names = {f'{a}.{b}' for a, b in r.get('rows', [])}
check('sandbox', 'sandbox holds only the allowed views as tables (no dwd/dws/customer tables)', r['status'] == 'ok' and names == set(pointer()['allowed_views']), names)
r = X.execute("SELECT current_setting('enable_external_access') AS e, current_setting('lock_configuration') AS l", skip_validation=True)
check('sandbox', 'external access off and configuration locked in the worker', r['status'] == 'ok' and r['rows'][0] == [False, True], r)
# 4. resources and injection
r = X.execute('SELECT count(*) FROM range(1000000000000) a, range(1000000000000) b', skip_validation=True, timeout_s=3)
check('resources', 'runaway query killed at the timeout', r['status'] == 'error' and r['error']['code'] == 'timeout', r)
r = X.execute('SELECT a.month, b.month AS m2 FROM ads.kpi_monthly a, ads.kpi_monthly b, ads.kpi_monthly c', max_rows=1000)
check('resources', 'result over the row limit refused (row_limit_exceeded)', r['status'] == 'error' and r['error']['code'] == 'row_limit_exceeded', r)
r = X.execute('SELECT month FROM ads.kpi_monthly WHERE month = ?', ["2026-10' OR '1'='1"])
check('injection', 'quote injection in a bound value matches nothing', r['status'] == 'empty', r)
r = X.execute('SELECT month FROM ads.kpi_monthly WHERE month = ?', ["x'; DROP TABLE ads.kpi_monthly; --"])
r2 = X.execute('SELECT count(*) AS n FROM ads.kpi_monthly')
check('injection', 'stacked-statement text in a bound value is only data; table intact', r['status'] == 'empty' and r2['rows'][0][0] == 35, (r, r2))
# 5. AI-04 plans executed, vs independent DWD
con, _ = open_current()
V = "approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'"
q = lambda s: con.execute(s).fetchone()  # noqa: E731
P = lambda text: X.run_plan(QI.plan(QI.parse(text)))  # noqa: E731
r = P('2026年10月的商品金额是多少？')
check('plans', '2026-10 merchandise = DWD', abs(r['value'] - float(q(f"SELECT sum(merch_usd) FROM dwd.fact_order WHERE {V} AND strftime(purchase_ts,'%Y-%m')='2026-10'")[0])) < 0.005, r)
r = P('2025年的客单价是多少')
s, o = q(f"SELECT sum(merch_usd), count(*) FROM dwd.fact_order WHERE {V} AND year(purchase_ts)=2025")
check('plans', '2025 AOV recomputed from sums = DWD', abs(r['value'] - float(s) / o) < 1e-6 and r['aov_recomputed_from_sums'], r)
r = P('2025年哪个品类的商品金额最高？')
top = con.execute(f"""SELECT p.product_category, sum(l.item_price_usd) s FROM dwd.fact_order_line l JOIN dwd.fact_order o USING (order_id) JOIN dwd.dim_product p USING (product_id)
                      WHERE o.{V} AND year(o.purchase_ts)=2025 GROUP BY 1 ORDER BY 2 DESC LIMIT 1""").fetchone()
check('plans', '2025 top category by merchandise = DWD', r['rows'][0][0] == top[0] and abs(r['rows'][0][1] - float(top[1])) < 0.005, (r['rows'], top))
r = P('2026年10月商品金额同比变化')
b = float(q(f"SELECT sum(merch_usd) FROM dwd.fact_order WHERE {V} AND strftime(purchase_ts,'%Y-%m')='2025-10'")[0])
check('plans', 'year-on-year base = 2025-10 from DWD and change computed', abs(r['base_value'] - b) < 0.005 and abs(r['change'] - (r['value'] - b) / b) < 1e-9, r)
r = P('2025年各大区商品金额占比')
check('plans', 'region shares sum to 1', abs(sum(x[2] for x in r['rows']) - 1) < 1e-9 and len(r['rows']) == 4, r)
r = P('最近6个月商品金额的趋势')
check('plans', 'trend returns six months 2026-05..2026-10', [x[0] for x in r['rows']] == ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10'], r)
r = P('现在沉睡客户有多少')
check('plans', 'a named lifecycle state returns its count: dormant 2,098 (behaviour since AI-07)', r.get('value') == 2098 and r.get('state') == 'dormant', r)
r = P('各生命周期状态分别有多少人')
check('plans', 'an unnamed lifecycle question still returns all states', r.get('kind') == 'table' and dict(r['rows']).get('dormant') == 2098 and len(r['rows']) == 4, r)
con.close()
src = (ROOT / 'src/retail_bi/ai/sql_executor.py').read_text(encoding='utf-8')
check('design', 'trusted plans never build SQL from the question (run_plan uses query_view only)', 'query_view(call' in src and 'execute(' not in src.split('def run_plan', 1)[1])
ok = all(x['status'] == 'passed' for x in res)
(ROOT / 'reports/ai/sql_boundary_checks.json').write_text(json.dumps({'task_id': 'AI-05', 'passed': sum(x['status'] == 'passed' for x in res), 'total': len(res), 'checks': res}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print(f"{sum(x['status'] == 'passed' for x in res)}/{len(res)} checks passed")
sys.exit(0 if ok else 1)
