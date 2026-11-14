"""DW-09 tests: the published warehouse passes every check; a small fixture warehouse copied without
constraints fails the matching check when a duplicate dimension key, a null date key or a wrong grain
is injected.  run: .venv/bin/python -m pytest tests/warehouse -q
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in ('src/retail_bi/warehouse', 'src/retail_bi/features', 'tests/data', 'tests/warehouse'):
    sys.path.insert(0, str(ROOT / p))
from db import connect, sql_blocks  # noqa: E402
import ods  # noqa: E402
import dwd  # noqa: E402
from conftest import write_layer  # noqa: E402
from recon import reconcile, run_checks  # noqa: E402

TABLES = ['dwd.dim_date', 'dwd.dim_geo', 'dwd.dim_customer', 'dwd.dim_product', 'dwd.dim_seller', 'dwd.fact_order',
          'dwd.fact_order_line', 'dwd.fact_payment', 'dwd.fact_fulfillment', 'dws.orders_daily_region',
          'dws.sales_daily_category_region', 'dws.customer_daily', 'dws.product_daily']


def test_published_build_passes_all_checks_and_reconciles():
    latest = json.loads((ROOT / 'warehouse/builds/latest.json').read_text(encoding='utf-8'))
    con = connect(ROOT / 'warehouse/builds' / latest['file'], read_only=True)
    checks = run_checks(con)
    steps, ok = reconcile(con, ROOT.parent / 'ecommerce-sample-database-100k/01_source/baseline_10000_seed42.zip')
    con.close()
    assert all(c['passed'] for c in checks.values()), [k for k, c in checks.items() if not c['passed']]
    assert ok and steps[-1]['orders'] == 9113


@pytest.fixture
def loose(tmp_path):
    """Build a tiny warehouse from the hand-made fixture layer, then copy it without constraints."""
    lay = write_layer(tmp_path)
    man = json.loads((lay / 'manifest.json').read_text(encoding='utf-8'))
    for o in man['outputs']:
        o['rows'] = sum(1 for _ in open(lay / o['path'], encoding='utf-8-sig')) - 1
    man['version'] = 'fixture-v1'
    (lay / 'manifest.json').write_text(json.dumps(man), encoding='utf-8')
    db = tmp_path / 'fx.duckdb'
    ods.load(lay, db)
    dwd.build(db)
    con = connect(db)
    for s in [x.strip() for x in sql_blocks(ROOT / 'sql/dws.sql')['build'].split(';') if x.strip()]:
        con.execute(s, {'as_of': '2025-02-05 00:00:00+00'}) if '$as_of' in s else con.execute(s)
    con.close()
    loose_db = tmp_path / 'loose.duckdb'
    c2 = connect(loose_db)
    c2.execute(f"ATTACH '{db}' AS src (READ_ONLY)")
    c2.execute('CREATE SCHEMA dwd; CREATE SCHEMA dws;')
    for t in TABLES:
        c2.execute(f'CREATE TABLE {t} AS SELECT * FROM src.{t}')
    c2.execute('DETACH src')
    return c2


def failed(con):
    # the fixture's DWS was built with as_of 2025-02-05, the checks use the real cutoff, so ignore that one comparison
    return sorted(k for k, c in run_checks(con).items() if not c['passed'] and k != 'dws_equals_dwd_valid')


def test_fixture_is_clean(loose):
    assert failed(loose) == []


def test_duplicate_dimension_key_fails(loose):
    loose.execute("INSERT INTO dwd.dim_customer SELECT * FROM dwd.dim_customer WHERE customer_id = 'c1'")
    f = failed(loose)
    assert 'unique_key:dim_customer' in f
    assert 'star_join_no_inflation' in f           # the duplicate also inflates joined lines


def test_null_date_key_fails(loose):
    loose.execute("UPDATE dwd.fact_order SET purchase_date_key = NULL WHERE order_id = 'o1'")
    f = failed(loose)
    assert 'not_null:fact_order.purchase_date_key' in f


def test_wrong_grain_fails(loose):
    # a line duplicated (wrong grain) and a DWS key duplicated
    loose.execute("INSERT INTO dwd.fact_order_line SELECT * FROM dwd.fact_order_line WHERE order_id = 'o1' AND order_item_seq = 1")
    loose.execute("INSERT INTO dws.orders_daily_region SELECT * FROM dws.orders_daily_region LIMIT 1")
    f = failed(loose)
    assert {'unique_key:fact_order_line', 'grain:order_header_matches_lines', 'grain:dws.orders_daily_region'} <= set(f)


def test_orphan_fact_row_fails(loose):
    loose.execute("UPDATE dwd.fact_order_line SET product_id = 'p_missing' WHERE order_id = 'o2'")
    assert 'no_orphans:fact_order_line.product_id->dim_product' in failed(loose)
