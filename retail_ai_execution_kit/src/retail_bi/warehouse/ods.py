"""DW-02: load the engineering layer into ODS with load audit.

Every value is stored as the exact source text (empty fields stay '' — not NULL),
with batch id, source file, file hash, 1-based row number and load time. One batch
is loaded in one transaction: on any error the transaction rolls back, so no
'loaded' status (and no partial rows) can be left behind. A batch already marked
'loaded' is skipped after its row counts are re-checked.

batch id = engineering layer content fingerprint (16 hex) + import version, so the
same input gives the same batch id on any machine.

usage: .venv/bin/python src/retail_bi/warehouse/ods.py --layer <engineering layer dir> \
         --db warehouse/build/dev.duckdb --audit reports/warehouse/ods_audit.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'data'))
from db import ROOT, connect, sql_blocks  # noqa: E402
from clean import layer_fingerprint  # noqa: E402

SQL = sql_blocks(ROOT / 'sql/ods.sql')
DDL = (ROOT / 'sql/ddl.sql').read_text(encoding='utf-8')


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(layer: Path, db: Path, contract_path: Path = ROOT / 'contracts/data_contract.json') -> dict:
    layer = layer.resolve()
    contract = json.loads(contract_path.read_text(encoding='utf-8'))
    manifest_path = layer / 'manifest.json'
    if not manifest_path.is_file():
        raise FileNotFoundError(f'missing import manifest: {manifest_path}')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    outputs = {o['path']: o for o in manifest['outputs']}
    batch_id = f'{layer_fingerprint(manifest)[:16]}-{manifest.get("version", "unknown")}'
    db.parent.mkdir(parents=True, exist_ok=True)
    con = connect(db)
    con.execute(DDL)
    status = con.execute(SQL['batch_status'], {'batch_id': batch_id}).fetchone()
    files = []
    if status and status[0] == 'loaded':
        for t in contract['tables']:
            n = con.execute(SQL['count_loaded'].format(table=t), {'batch_id': batch_id}).fetchone()[0]
            exp = outputs[f'history_source/{t}.csv']['rows']
            if n != exp:
                raise ValueError(f'batch {batch_id} marked loaded but ods.{t} has {n} rows, manifest {exp}')
        skipped = True
    else:
        skipped = False
        con.execute('BEGIN TRANSACTION')
        try:
            if status:   # a stale 'loading' row can only exist if a previous transaction was not rolled back
                raise ValueError(f'batch {batch_id} is in state {status[0]}; inspect before reloading')
            con.execute(SQL['begin_batch'], {'batch_id': batch_id, 'layer_version': manifest.get('version')})
            for t, spec in contract['tables'].items():
                rel = f'history_source/{t}.csv'
                path = layer / rel
                if not path.is_file():
                    raise FileNotFoundError(f'missing source file for ods.{t}: {path}')
                if rel not in outputs or sha(path) != outputs[rel]['sha256']:
                    raise ValueError(f'{rel} does not match the import manifest hash')
                with open(path, encoding='utf-8-sig', newline='') as f:
                    reader = csv.reader(f)
                    header = next(reader)
                    rows = list(reader)
                raw = [c['raw_name'] for c in spec['columns']]
                if header != raw:
                    raise ValueError(f'{rel}: header differs from contract')
                cols = {name: pa.array([r[i] for r in rows], pa.string()) for i, name in enumerate(raw)}
                cols['_row_no'] = pa.array(range(1, len(rows) + 1), pa.int64())
                con.register('src_rows', pa.table(cols))
                quoted = ', '.join(f'"{c}"' for c in raw)
                con.execute(f"""INSERT INTO ods.{t} ({quoted}, _batch_id, _source_file, _source_sha256, _row_no, _loaded_at)
                                SELECT {quoted}, $batch_id, $source_file, $sha, _row_no, now() FROM src_rows""",
                            {'batch_id': batch_id, 'source_file': rel, 'sha': outputs[rel]['sha256']})
                con.unregister('src_rows')
                n = con.execute(SQL['count_loaded'].format(table=t), {'batch_id': batch_id}).fetchone()[0]
                if n != outputs[rel]['rows'] or n != len(rows):
                    raise ValueError(f'ods.{t}: loaded {n} rows, file {len(rows)}, manifest {outputs[rel]["rows"]}')
                con.execute(SQL['register_file'], {'batch_id': batch_id, 'table_name': t, 'source_file': rel,
                                                   'source_sha256': outputs[rel]['sha256'], 'manifest_rows': outputs[rel]['rows'],
                                                   'loaded_rows': n})
            con.execute(SQL['finish_batch'], {'batch_id': batch_id})
            con.execute('COMMIT')
        except BaseException:
            con.execute('ROLLBACK')
            con.close()
            raise
    for row in con.execute(SQL['audit_files'], {'batch_id': batch_id}).fetchall():
        files.append(dict(zip(['table', 'source_file', 'source_sha256', 'manifest_rows', 'loaded_rows', 'status', 'started_at', 'finished_at'], row)))
    batches = con.execute("SELECT batch_id, status FROM meta.load_batch ORDER BY batch_id").fetchall()
    con.close()
    return {'task_id': 'DW-02', 'db': str(db), 'batch_id': batch_id, 'skipped_already_loaded': skipped,
            'files': files, 'batches_in_db': [list(b) for b in batches],
            'all_counts_match': all(f['manifest_rows'] == f['loaded_rows'] for f in files) and len(files) == len(contract['tables'])}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--layer', type=Path, required=True)
    ap.add_argument('--db', type=Path, required=True)
    ap.add_argument('--audit', type=Path)
    a = ap.parse_args()
    r = load(a.layer, a.db)
    if a.audit:
        a.audit.parent.mkdir(parents=True, exist_ok=True)
        a.audit.write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: r[k] for k in ('batch_id', 'skipped_already_loaded', 'all_counts_match')}, ensure_ascii=False))
    raise SystemExit(0 if r['all_counts_match'] else 1)


if __name__ == '__main__':
    main()
