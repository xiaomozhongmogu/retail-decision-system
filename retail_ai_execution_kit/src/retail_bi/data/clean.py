"""DATA-07: typed, contract-driven cleaning with quarantine and import guard.

Input: the DATA-05 engineering layer (history_source, all strings).
Output: one Parquet file per table with contract standard names and types,
plus a manifest. Rows that fail type parsing, primary-key uniqueness or a
foreign key go to data/quarantine/<key>/ with source row number and reason;
nothing disappears silently. No value is imputed: IDs are never filled, null
event times mean "not happened yet" and stay null.

Re-running with the same input layer and contract re-verifies the existing
output and changes nothing; a changed input needs a new version key.

usage: .venv/bin/python src/retail_bi/data/clean.py --layer <engineering layer dir> \
         --contract contracts/data_contract.json --out-root data/processed/clean \
         --quarantine-root data/quarantine --report reports/data/cleaning_missing_duplicates.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

CLEAN_VERSION = 'clean-v1'
ARROW = {'string': pa.string(), 'integer': pa.int64(), 'decimal(12,2)': pa.decimal128(12, 2),
         'double': pa.float64(), 'boolean': pa.bool_(), 'date': pa.date32(),
         'timestamp': pa.timestamp('ms', tz='UTC')}


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def parse(typ: str, v: str):
    if v == '':
        return None
    if typ == 'string':
        return v
    if typ == 'integer':
        d = Decimal(v)
        if d != d.to_integral_value():
            raise ValueError('not an integer')
        return int(d)
    if typ == 'decimal(12,2)':
        d = Decimal(v)
        if d.as_tuple().exponent < -2:
            raise ValueError('more than 2 decimals')
        return d.quantize(Decimal('0.01'))
    if typ == 'double':
        return float(Decimal(v))
    if typ == 'boolean':
        if v not in ('True', 'False'):
            raise ValueError('not True/False')
        return v == 'True'
    if typ == 'date':
        t = datetime.fromisoformat(v)
        if t.hour or t.minute or t.second:
            raise ValueError('date has a time part')
        return t.date()
    if typ == 'timestamp':
        return datetime.fromisoformat(v).replace(tzinfo=timezone.utc)   # naive source, UTC assumption (D011)
    raise ValueError(f'unknown type {typ}')


def read(path: Path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)


def verify_existing(target: Path, identity: dict) -> dict:
    m = json.loads((target / 'manifest.json').read_text(encoding='utf-8'))
    if m['identity'] != identity:
        raise ValueError(f'existing output {target} was built from different inputs; use a new version')
    for item in m['outputs']:
        if sha(target / item['path']) != item['sha256']:
            raise ValueError(f'existing output changed: {item["path"]}')
    return m


def build(layer: Path, contract_path: Path, out_root: Path, quarantine_root: Path):
    layer, out_root, quarantine_root = layer.resolve(), out_root.resolve(), quarantine_root.resolve()
    contract = json.loads(contract_path.read_text(encoding='utf-8'))
    layer_sha = sha(layer / 'manifest.json')
    layer_manifest = json.loads((layer / 'manifest.json').read_text(encoding='utf-8'))
    for item in layer_manifest['outputs']:   # input files must still match the import manifest
        if sha(layer / item['path']) != item['sha256']:
            raise ValueError(f'input layer file changed after import: {item["path"]}')
    identity ={'layer_manifest_sha256': layer_sha, 'contract_version': contract['contract_version'],
                'contract_sha256': sha(contract_path), 'clean_version': CLEAN_VERSION}
    key = f'{layer_sha[:16]}-{contract["contract_version"]}-{CLEAN_VERSION}'
    out_root.mkdir(parents=True, exist_ok=True)
    target, lock = out_root / key, out_root / f'{key}.lock'
    lock.mkdir()   # exclusive writer; a leftover lock must be checked by a person, never stolen
    stage = qstage = None
    try:
        if target.exists():
            return target, verify_existing(target, identity), True
        stage = Path(tempfile.mkdtemp(dir=out_root, prefix=f'{key}.partial-'))
        quarantine, stats, kept = defaultdict(list), {}, {}
        # pass 1: types and primary keys
        for table, spec in contract['tables'].items():
            header, rows = read(layer / 'history_source' / f'{table}.csv')
            cols = spec['columns']
            if header != [c['raw_name'] for c in cols]:
                raise ValueError(f'{table}: header differs from contract')
            good, seen = [], set()
            for n, row in enumerate(rows, start=2):           # n = line number in the source CSV
                rec, bad = {}, []
                for c in cols:
                    try:
                        rec[c['standard_name']] = parse(c['type'], row[c['raw_name']])
                    except (ValueError, InvalidOperation) as exc:
                        bad.append((c['raw_name'], row[c['raw_name']], f'type {c["type"]}: {exc}'))
                pk = tuple(row[k] for k in spec['primary_key'])
                if any(x == '' for x in pk):
                    bad.append(('+'.join(spec['primary_key']), '', 'null primary key'))
                elif pk in seen:
                    bad.append(('+'.join(spec['primary_key']), '|'.join(pk), 'duplicate primary key'))
                seen.add(pk)
                if bad:
                    for col, val, why in bad:
                        quarantine[table].append({'source_line': n, 'column': col, 'value': val, 'reason': why})
                else:
                    good.append(rec)
            kept[table] = good
            stats[table] = {'rows_in': len(rows), 'rows_after_type_and_pk': len(good)}
        # pass 2: foreign keys against the kept parents
        std = {t: {c['raw_name']: c['standard_name'] for c in s['columns']} for t, s in contract['tables'].items()}
        for k in contract['keys']:
            if not k.startswith('fk:'):
                continue
            child, parent = k[3:].split('->')
            ct, cc = child.split('.')
            pt, pc = parent.split('.')
            parents = {r[std[pt][pc]] for r in kept[pt]}
            ok = []
            for r in kept[ct]:
                if r[std[ct][cc]] in parents:
                    ok.append(r)
                else:
                    quarantine[ct].append({'source_line': None, 'column': cc, 'value': r[std[ct][cc]], 'reason': f'orphan foreign key -> {pt}'})
            kept[ct] = ok
        outputs = []
        for table, spec in contract['tables'].items():
            schema = pa.schema([(c['standard_name'], ARROW[c['type']]) for c in spec['columns']])
            tbl = pa.Table.from_pylist(kept[table], schema=schema)
            rel = f'{table}.parquet'
            pq.write_table(tbl, stage / rel, compression='zstd')
            back = pq.read_table(stage / rel)
            if back.num_rows != len(kept[table]) or not back.equals(tbl):
                raise ValueError(f'{table}: Parquet round trip changed data')
            stats[table]['rows_out'] = len(kept[table])
            stats[table]['rows_quarantined'] = stats[table]['rows_in'] - len(kept[table])
            outputs.append({'path': rel, 'sha256': sha(stage / rel), 'rows': len(kept[table]),
                            'columns': [c['standard_name'] for c in spec['columns']]})
        qdir = quarantine_root / key
        if any(quarantine.values()):
            if qdir.exists():
                raise ValueError(f'quarantine dir already exists without matching output: {qdir}')
            quarantine_root.mkdir(parents=True, exist_ok=True)
            qstage = Path(tempfile.mkdtemp(dir=quarantine_root, prefix=f'{key}.partial-'))
            for table, items in quarantine.items():
                with open(qstage / f'{table}.csv', 'w', encoding='utf-8', newline='') as f:
                    w = csv.DictWriter(f, fieldnames=['source_line', 'column', 'value', 'reason'])
                    w.writeheader()
                    w.writerows(items)
        manifest = {'identity': identity, 'key': key, 'layer': str(layer), 'as_of_exclusive': contract['as_of_exclusive'],
                    'synthetic': True, 'timezone': 'UTC engineering assumption (D011)',
                    'tables': stats, 'outputs': outputs,
                    'quarantine': {'dir': str(qdir) if any(quarantine.values()) else None,
                                   'counts': {t: Counter(i['reason'].split(':')[0] for i in v) for t, v in quarantine.items() if v}},
                    'imputation': 'none'}
        (stage / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=dict) + '\n', encoding='utf-8')
        if sha(layer / 'manifest.json') != layer_sha:
            raise ValueError('input layer changed during cleaning')
        if qstage is not None:
            qstage.rename(qdir)
            qstage = None
        stage.rename(target)
        stage = None
        return target, verify_existing(target, identity), False
    finally:
        if stage is not None:
            shutil.rmtree(stage)
        if qstage is not None:
            shutil.rmtree(qstage)
        lock.rmdir()


def report(target: Path, manifest: dict, reused: bool, contract: dict, out: Path):
    orders = pq.read_table(target / 'orders.parquet').to_pandas()
    items = pq.read_table(target / 'order_items.parquet').to_pandas()
    known = orders['customer_id'].notna()
    tables = contract['tables']
    null_policy = {}
    for t, s in tables.items():
        for c in s['columns']:
            if c['profile']['null_count']:
                if c['role'] in ('pk', 'fk'):
                    rule = '标识不插补；缺失则进入隔离区'
                elif c['role'] == 'event_time':
                    rule = '保留空值，表示事件在截止前尚未发生（与最终状态严格对应）；不插补'
                elif c['role'] == 'derived':
                    rule = '保留空值（未送达订单没有实际天数）；DATA-10 从时间戳重算'
                else:
                    rule = '保留空值；该列全空或不适用'
                null_policy[f'{t}.{c["raw_name"]}'] = {'nulls': c['profile']['null_count'], 'rule': rule}
    dup_lines = int(items.duplicated(['order_id', 'product_id']).sum())
    data = {
        'task_id': 'DATA-07', 'generated_by': 'src/retail_bi/data/clean.py', 'clean_key': manifest['key'],
        'identity': manifest['identity'], 'reused_existing_output': reused,
        'row_counts': manifest['tables'],
        'quarantine': manifest['quarantine'],
        'imputation': '没有任何插补：ID 不插补，数值不做均值填充，事件时间空值保留',
        'missing_policy': null_policy,
        'customer_coverage': {
            'summary_scope_orders': int(len(orders)),
            'customer_model_scope_orders': int(known.sum()),
            'unknown_customer_orders': int((~known).sum()),
            'rule': '未知客户的订单可进入经营汇总，但不进入客户级指标和模型；本数据 customer_id 全部已知，所以两种覆盖都等于全部订单，仍分别报告',
        },
        'duplicates': {
            'exact_duplicate_rows_removed': 0,
            'primary_key_duplicates_quarantined': sum(v.get('duplicate primary key', 0) for v in manifest['quarantine']['counts'].values()),
            'same_product_repeated_lines_kept': dup_lines,
            'same_product_rule': '保留。同单重复商品是同一上架、每行价格不同的独立明细（DATA-06），不是重复导入；主键是 order_id+order_item_seq，不假定订单+商品唯一，也不把重复行合并成数量',
            'same_customer_same_day_orders': '保留。订单号不同、时间不同，是独立订单',
        },
        'duplicate_import_guard': '输出目录键 = 输入层清单哈希前 16 位 + 契约版本 + clean-v1；同一输入重跑会校验已有输出哈希后直接返回，不重写；身份不一致或文件被改则拒绝；独占锁防并发写入',
        'type_conversion': {c_type: str(a) for c_type, a in ARROW.items()},
        'standard_names': '输出列使用契约 standard_name（如 order_purchase_timestamp → purchase_ts）',
    }
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=dict) + '\n', encoding='utf-8')
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--layer', type=Path, required=True)
    ap.add_argument('--contract', type=Path, required=True)
    ap.add_argument('--out-root', type=Path, required=True)
    ap.add_argument('--quarantine-root', type=Path, required=True)
    ap.add_argument('--report', type=Path)
    a = ap.parse_args()
    target, manifest, reused = build(a.layer, a.contract, a.out_root, a.quarantine_root)
    if a.report:
        report(target, manifest, reused, json.loads(a.contract.read_text(encoding='utf-8')), a.report)
    print(json.dumps({'target': str(target), 'reused': reused, 'tables': manifest['tables'],
                      'quarantine': manifest['quarantine']}, ensure_ascii=False, default=dict))


if __name__ == '__main__':
    main()
