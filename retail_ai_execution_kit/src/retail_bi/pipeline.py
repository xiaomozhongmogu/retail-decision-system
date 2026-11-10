"""DW-07: one command from the source ZIP to the ADS layer, with atomic publish.

    .venv/bin/python src/retail_bi/pipeline.py build

Stages: ingest -> clean (independent Python cleaning, used as a cross-check) -> ods -> dwd -> dws ->
snapshot (+labels) -> ads -> checks -> publish. The warehouse is built in a temporary file under
warehouse/builds/; only after every stage and check passes is it renamed to
warehouse/builds/<version>.duckdb and warehouse/builds/latest.json replaced (os.replace, atomic).
Readers use latest.json, so a failed or half-finished run is never visible.

The version is a hash of the ODS batch id and every SQL/contract file used, so the same inputs give
the same version; if that version already exists and passes its checks the run is a no-op.
Each run writes reports/warehouse/etl_run.json (stages, rows, amounts, durations, versions, errors);
a failed run records the failing stage and exits 1.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
for sub in ('data', 'warehouse', 'features', 'model'):
    sys.path.insert(0, str(HERE / sub))
from db import ROOT, connect, sql_blocks  # noqa: E402
import ingest  # noqa: E402
import clean  # noqa: E402
import ods  # noqa: E402
import dwd  # noqa: E402
import snapshot  # noqa: E402
import scoring  # noqa: E402

SOURCE = ROOT.parent / 'ecommerce-sample-database-100k/01_source/baseline_10000_seed42.zip'
SOURCE_SHA = 'd50ee64a0478d8ae8df1b8b66521671a4911e19f911ae86196452a668f917a16'
CUTOFF = '2026-11-08T00:00:00Z'
AS_OF_SQL = '2026-11-08 00:00:00+00'
CONTRACT = ROOT / 'contracts/data_contract.json'
VERSIONED_FILES = ['sql/ddl.sql', 'sql/ods.sql', 'sql/dwd.sql', 'sql/dws.sql', 'sql/customer_snapshot.sql', 'sql/ads.sql',
                   'sql/scores.sql', 'contracts/data_contract.json', 'contracts/metrics.json']
MODEL_FILE = scoring.MODEL_FILE      # frozen model (ML-08); when present, its hash is part of the build version
BUILDS = ROOT / 'warehouse/builds'


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def statements(block: str):
    return [s.strip() for s in block.split(';') if s.strip()]


def table_stats(con) -> dict:
    out = {}
    for s, t in con.execute("SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema IN ('ods','dwd','dws') ORDER BY 1, 2").fetchall():
        out[f'{s}.{t}'] = con.execute(f'SELECT count(*) FROM {s}.{t}').fetchone()[0]
    return out


def checks(con, clean_dir: Path) -> dict:
    c = {}
    o = con.execute(f"""SELECT count(*), sum(merch_usd)::VARCHAR, count(*) FILTER (WHERE approved_ts < TIMESTAMPTZ '{AS_OF_SQL}'),
                               sum(merch_usd) FILTER (WHERE approved_ts < TIMESTAMPTZ '{AS_OF_SQL}')::VARCHAR FROM dwd.fact_order""").fetchone()
    p = con.execute(f"SELECT count(*), sum(item_price_usd)::VARCHAR FROM read_parquet('{(clean_dir / 'order_items.parquet').as_posix()}')").fetchone()
    c['dwd_orders_equal_clean'] = o[0] == con.execute(f"SELECT count(*) FROM read_parquet('{(clean_dir / 'orders.parquet').as_posix()}')").fetchone()[0]
    c['dwd_merch_equals_clean_lines'] = o[1] == p[1]
    for t in ('orders_daily_region', 'sales_daily_category_region', 'customer_daily', 'product_daily'):
        c[f'dws_{t}_merch_equals_dwd_valid'] = con.execute(f'SELECT sum(merch_usd)::VARCHAR FROM dws.{t}').fetchone()[0] == o[3]
    c['ads_monthly_orders_equal_dwd_valid'] = con.execute('SELECT sum(valid_orders) FROM ads.kpi_monthly').fetchone()[0] == o[2]
    has_scores = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'ads' AND table_name = 'model_scores'").fetchone()[0] == 1
    c['allowed_views_registered'] = con.execute('SELECT count(*) FROM meta.allowed_view').fetchone()[0] == (7 if has_scores else 6)
    if has_scores:
        c['scores_complementary'] = con.execute('SELECT count(*) FROM ads.model_scores WHERE abs(p_repurchase_30d + p_non_repurchase_30d - 1) > 1e-12').fetchone()[0] == 0
    c['no_immature_labels'] = con.execute(f"SELECT count(*) FROM dws.label_repurchase WHERE label_matured_at > TIMESTAMPTZ '{AS_OF_SQL}'").fetchone()[0] == 0
    c['single_loaded_batch'] = con.execute("SELECT count(*) FROM meta.load_batch WHERE status = 'loaded'").fetchone()[0] == 1
    return {'values': {'orders': o[0], 'merch_usd': o[1], 'valid_orders': o[2], 'valid_merch_usd': o[3]}, 'checks': c}


def run(force: bool = False, fail_at: str | None = None) -> dict:
    report = {'task_id': 'DW-07', 'started_at': datetime.now(timezone.utc).isoformat(), 'stages': [], 'status': 'running'}
    BUILDS.mkdir(parents=True, exist_ok=True)
    tmp = None

    def stage(name, fn):
        t0 = time.perf_counter()
        entry = {'stage': name, 'status': 'running'}
        report['stages'].append(entry)
        try:
            if fail_at == name:
                raise RuntimeError(f'injected failure at stage {name} (test)')
            entry.update(fn() or {})
            entry['status'] = 'ok'
        except BaseException as exc:
            entry['status'] = 'failed'
            entry['error'] = f'{type(exc).__name__}: {exc}'
            entry['traceback'] = traceback.format_exc(limit=3)
            raise
        finally:
            entry['seconds'] = round(time.perf_counter() - t0, 3)

    try:
        st = {}
        stage('ingest', lambda: st.update(layer=ingest.build(SOURCE, ROOT / 'data/raw/archives', ROOT / 'data/processed/engineering', CUTOFF, SOURCE_SHA)[0])
              or {'layer': st['layer'].name})

        def do_clean():
            target, man, reused = clean.build(st['layer'], CONTRACT, ROOT / 'data/processed/clean', ROOT / 'data/quarantine')
            st['clean'] = target
            return {'clean': target.name, 'reused': reused, 'quarantined_rows': sum(v['rows_quarantined'] for v in man['tables'].values())}
        stage('clean', do_clean)

        layer_manifest = json.loads((st['layer'] / 'manifest.json').read_text(encoding='utf-8'))
        batch_id = f'{clean.layer_fingerprint(layer_manifest)[:16]}-{layer_manifest["version"]}'
        files = {f: sha(ROOT / f) for f in VERSIONED_FILES}
        if MODEL_FILE.exists():
            files[str(MODEL_FILE.relative_to(ROOT))] = sha(MODEL_FILE)
        version = 'wh-' + hashlib.sha256(json.dumps({'batch': batch_id, 'files': files}, sort_keys=True).encode()).hexdigest()[:12]
        final = BUILDS / f'{version}.duckdb'
        report.update({'version': version, 'batch_id': batch_id, 'inputs': {'source_sha256': SOURCE_SHA, 'cutoff': CUTOFF, 'files': files}})
        if final.exists() and not force:
            def verify_existing():
                con = connect(final, read_only=True)
                r = checks(con, st['clean'])
                stats = table_stats(con)
                con.close()
                if not all(r['checks'].values()):
                    raise ValueError(f'existing build {final.name} fails its checks; rerun with --force')
                return {'reused_existing': final.name, **r, 'rows': stats}
            stage('verify_existing', verify_existing)
        else:
            tmp = BUILDS / f'.{version}.{os.getpid()}.building.duckdb'
            tmp.unlink(missing_ok=True)
            stage('ods', lambda: {'batch_id': ods.load(st['layer'], tmp)['batch_id']})
            stage('dwd', lambda: {'rows': dwd.build(tmp)['row_counts']})

            def do_dws():
                con = connect(tmp)
                con.execute('BEGIN TRANSACTION')
                for s in statements(sql_blocks(ROOT / 'sql/dws.sql')['build']):
                    con.execute(s, {'as_of': AS_OF_SQL}) if '$as_of' in s else con.execute(s)
                con.execute('COMMIT')
                r = {t: con.execute(f'SELECT count(*), sum(merch_usd)::VARCHAR FROM dws.{t}').fetchone()
                     for t in ('orders_daily_region', 'sales_daily_category_region', 'customer_daily', 'product_daily')}
                con.close()
                return {'rows_and_merch': r}
            stage('dws', do_dws)
            stage('snapshot', lambda: {k: v for k, v in snapshot.build(tmp).items() if k in ('coverage', 'labels')})

            def do_ads():
                con = connect(tmp)
                b = sql_blocks(ROOT / 'sql/ads.sql')
                con.execute('BEGIN TRANSACTION')
                con.execute(b['views'])
                con.execute(b['allowed'])
                con.execute('COMMIT')
                n = len(con.execute("SELECT * FROM information_schema.tables WHERE table_schema = 'ads'").fetchall())
                con.close()
                return {'ads_views': n}
            stage('ads', do_ads)
            if MODEL_FILE.exists():
                stage('scores', lambda: scoring.write_scores(tmp))
            else:
                report['warnings'] = ['frozen model file missing: scores stage skipped (train with ML-06..08 first)']

            def do_checks():
                con = connect(tmp)
                r = checks(con, st['clean'])
                r['rows'] = table_stats(con)
                con.execute('CHECKPOINT')
                con.close()
                bad = [k for k, v in r['checks'].items() if not v]
                if bad:
                    raise ValueError(f'checks failed: {bad}')
                return r
            stage('checks', do_checks)

            def publish():
                os.replace(tmp, final)                       # atomic on the same file system
                return {'published': final.name}
            stage('publish', publish)
            tmp = None
        current = json.loads((BUILDS / 'latest.json').read_text(encoding='utf-8')) if (BUILDS / 'latest.json').exists() else {}
        if report['stages'][-1]['stage'] == 'publish' or current.get('version') != version:   # a reused build keeps the pointer as is
            pointer = {'version': version, 'file': final.name, 'published_at': datetime.now(timezone.utc).isoformat(), 'cutoff': CUTOFF}
            ptmp = BUILDS / '.latest.json.tmp'
            ptmp.write_text(json.dumps(pointer, indent=2) + '\n', encoding='utf-8')
            os.replace(ptmp, BUILDS / 'latest.json')
        report['status'] = 'ok'
    except BaseException:
        report['status'] = 'failed'
        report['failed_stage'] = next((s['stage'] for s in report['stages'] if s['status'] == 'failed'), None)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)                      # never leave a half-built file
            Path(str(tmp) + '.wal').unlink(missing_ok=True)
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['build'])
    ap.add_argument('--force', action='store_true', help='rebuild even if this version exists')
    ap.add_argument('--fail-at', help='inject a failure at a stage (tests only)')
    ap.add_argument('--report', type=Path, default=ROOT / 'reports/warehouse/etl_run.json')
    a = ap.parse_args()
    r = run(force=a.force, fail_at=a.fail_at)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(r, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps({'status': r['status'], 'version': r.get('version'), 'failed_stage': r.get('failed_stage'),
                      'stages': [(s['stage'], s['status'], s['seconds']) for s in r['stages']]}, ensure_ascii=False))
    raise SystemExit(0 if r['status'] == 'ok' else 1)


if __name__ == '__main__':
    main()
