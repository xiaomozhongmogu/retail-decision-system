"""DW-01 checks: DDL executes; ODS/DWD columns trace to the contract or to the documented
derived list; the design doc covers every table, its FKs and the layer duties.
usage: .venv/bin/python evidence/DW-01/verify_design.py
"""
import json
import re
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
C = json.loads((ROOT / 'contracts/data_contract.json').read_text(encoding='utf-8'))
doc = (ROOT / 'docs/warehouse_design.md').read_text(encoding='utf-8')
ddl = (ROOT / 'sql/ddl.sql').read_text(encoding='utf-8')
con = duckdb.connect()
con.execute(ddl)
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


tables = con.execute("SELECT table_schema, table_name FROM information_schema.tables").fetchall()
check('DDL executes in DuckDB (10 ods + 9 dwd + 5 dws + 3 meta)', len(tables) == 27, f'{len(tables)} tables')
META = {'_batch_id', '_source_file', '_source_sha256', '_row_no', '_loaded_at'}
for t, spec in C['tables'].items():
    cols = [r[0] for r in con.execute(f'DESCRIBE ods.{t}').fetchall()]
    check(f'ods.{t} = contract raw columns + load metadata', cols == [c['raw_name'] for c in spec['columns']] + sorted(META, key=list(META).index) or
          (cols[:len(spec['columns'])] == [c['raw_name'] for c in spec['columns']] and set(cols[len(spec['columns']):]) == META))
std = {c['standard_name'] for s in C['tables'].values() for c in s['columns']}
derived_doc = set(re.findall(r'`([a-z_]+)`', doc.split('## 8.')[1]))
bad = []
for s, t in tables:
    if s != 'dwd':
        continue
    for name, typ, *_ in con.execute(f'DESCRIBE dwd.{t}').fetchall():
        if name not in std and name not in derived_doc:
            bad.append(f'{t}.{name}')
check('every DWD column is a contract standard name or a documented derived column', not bad, str(bad))
for s, t in tables:
    if s in ('dwd', 'dws'):
        check(f'design doc describes {s}.{t}', f'`{s}.{t}`' in doc)
fks = con.execute("SELECT table_name, constraint_text FROM duckdb_constraints() WHERE constraint_type = 'FOREIGN KEY'").fetchall()
er = doc.split('```mermaid')[1].split('```')[0]
for t, txt in fks:
    parent = re.search(r'REFERENCES (?:dwd\.)?(\w+)', txt).group(1)
    check(f'ER diagram has {parent} -> {t}', f'{parent} ' in er and f' {t} ' in er)
check('layer duties for ODS/DWD/DWS/ADS', all(f'| {x} | `{x.lower()}`' in doc for x in ['ODS', 'DWD', 'DWS', 'ADS']))
check('only source-supported hierarchies; no subcategory', '没有子品类' in doc and '大区 → 州 → 城市' in doc)
check('generator labels not in dim_customer', 'customer_segment' not in [r[0] for r in con.execute('DESCRIBE dwd.dim_customer').fetchall()]
      and '永远不回写维度表' in doc)
check('lineage and refresh order documented', '## 6. 血缘' in doc and '## 7. 刷新顺序' in doc)
check('DDL is generated from the contract version', C['contract_version'] in ddl)
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
