"""DW-05 checks: point-in-time correctness (leakage test), separate labels, keys, coverage.
For three as_of points the features are recomputed in pandas from orders truncated to what was
visible at as_of; they must equal the snapshot. Labels are recomputed from the following window.
usage: .venv/bin/python evidence/DW-05/verify_snapshot.py
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
from db import connect  # noqa: E402

C = json.loads((ROOT / 'reports/warehouse/snapshot_contract.json').read_text(encoding='utf-8'))
Q = json.loads((ROOT / 'reports/data/quality_checks.json').read_text(encoding='utf-8'))
PA = json.loads((ROOT / 'reports/data/profile_after.json').read_text(encoding='utf-8'))
sql = (ROOT / 'sql/customer_snapshot.sql').read_text(encoding='utf-8')
con = connect(ROOT / 'warehouse/build/dev.duckdb', read_only=True)
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


O = con.execute("""SELECT customer_id, purchase_ts::VARCHAR p, approved_ts::VARCHAR a, merch_usd::DOUBLE m FROM dwd.fact_order""").df()
O['p'] = pd.to_datetime(O.p, utc=True)
O['a'] = pd.to_datetime(O.a, utc=True)
for as_of in ['2024-07-01', '2025-06-02', '2026-09-07']:
    t = pd.Timestamp(as_of, tz='UTC')
    vis = O[(O.p < t) & (O.a < t)]                      # what was knowable at as_of
    g = vis.groupby('customer_id')
    exp = pd.DataFrame({'recency_days': (t - g.p.max()).dt.total_seconds() / 86400,
                        'frequency_90d': g.apply(lambda d: int((d.p >= t - pd.Timedelta(days=90)).sum()), include_groups=False),
                        'monetary_90d_usd': g.apply(lambda d: round(d.m[d.p >= t - pd.Timedelta(days=90)].sum(), 2), include_groups=False),
                        'orders_all_time': g.size(), 'merch_all_time_usd': g.m.sum().round(2),
                        'tenure_days': (t - g.p.min()).dt.total_seconds() / 86400})
    first, last = g.p.min(), g.p.max()
    exp['lifecycle_state'] = np.where(first >= t - pd.Timedelta(days=30), 'new', np.where(last >= t - pd.Timedelta(days=90), 'active',
                                      np.where(last >= t - pd.Timedelta(days=180), 'at_risk', 'dormant')))
    got = con.execute(f"""SELECT customer_id, recency_days, frequency_90d, monetary_90d_usd::DOUBLE monetary_90d_usd, orders_all_time,
                                 merch_all_time_usd::DOUBLE merch_all_time_usd, tenure_days, lifecycle_state
                          FROM dws.customer_snapshot WHERE snapshot_version = 'snapshot-v1' AND as_of = TIMESTAMPTZ '{as_of} 00:00:00+00'""").df().set_index('customer_id').sort_index()
    exp = exp.sort_index()
    same_rows = list(got.index) == list(exp.index)
    num = ['recency_days', 'frequency_90d', 'monetary_90d_usd', 'orders_all_time', 'merch_all_time_usd', 'tenure_days']
    same_vals = same_rows and np.allclose(got[num].astype(float).values, exp[num].astype(float).values, atol=1e-6) and (got.lifecycle_state == exp.lifecycle_state).all()
    check(f'as_of {as_of}: snapshot equals recomputation from orders truncated to as_of (no future data)', same_vals, f'{len(got)} customers')
    # labels
    end, mat = t + pd.Timedelta(days=30), t + pd.Timedelta(days=31)
    buyers = set(O[(O.p >= t) & (O.p < end) & (O.a.notna()) & (O.a < mat)].customer_id)
    lab = con.execute(f"""SELECT customer_id, y FROM dws.label_repurchase WHERE label_version = 'label-repurchase-v1'
                          AND as_of = TIMESTAMPTZ '{as_of} 00:00:00+00'""").df()
    check(f'as_of {as_of}: labels equal recomputation from the following 30-day window', set(lab.customer_id) == set(got.index)
          and all(lab.y == lab.customer_id.isin(buyers)), f'{int(lab.y.sum())} positives')
snap_block = sql.split('-- name: snapshot')[1].split('-- name: labels')[0]
check('snapshot SQL never reads final status, delivery outcomes or generator labels',
      not re.search(r'order_status|delivered|late_by|segment|lifecycle_stage|review', snap_block))
check('labels live in a separate table with their own version and maturity time', C['label_table'] == 'dws.label_repurchase'
      and 'label_matured_at TIMESTAMPTZ NOT NULL' in (ROOT / 'sql/ddl.sql').read_text() and C['params']['label_version'] != C['params']['snapshot_version'])
dup = con.execute("SELECT count(*) - count(DISTINCT (customer_id, as_of)) FROM dws.customer_snapshot").fetchone()[0]
check('snapshot key (customer_id, as_of) unique', dup == 0)
late = con.execute("SELECT count(*) FROM dws.customer_snapshot WHERE as_of > TIMESTAMPTZ '2026-11-08 00:00:00+00'").fetchone()[0]
immature = con.execute("SELECT count(*) FROM dws.label_repurchase WHERE label_matured_at > TIMESTAMPTZ '2026-11-08 00:00:00+00'").fetchone()[0]
check('no snapshot after the cutoff and no immature label', late == 0 and immature == 0)
lab = PA['label_30d_with_frozen_rule']
check('90-day population labels equal the DATA-11 gate (independent SQL)', C['labels']['rows_in_90d_population'] == lab['rows']
      and C['labels']['positives_in_90d_population'] == lab['positives'], f"{lab['rows']} rows / {lab['positives']} positives")
check('coverage queryable: as_of points, window start, version', C['coverage']['as_of_points'] == 136 and 'feature_window_start' in C['columns'])
con.close()
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
