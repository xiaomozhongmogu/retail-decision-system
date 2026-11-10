"""EDA-05: mutually exclusive lifecycle rules (lifecycle-v1) and their checks.

State at as_of t, from the customer's valid purchases visible at t (purchase and approval before t):
  priority 1  unknown_anonymous     customer_id missing
  priority 2  unknown_no_purchase   no visible valid purchase before t
  priority 3  new                   first visible purchase in [t-30d, t)
  priority 4  active                last visible purchase in [t-90d, t)
  priority 5  at_risk               last visible purchase in [t-180d, t-90d)
  priority 6  dormant               last visible purchase before t-180d
  guard       unknown_short_history if t - data_start < the window a state needs, that state cannot be observed
                                    (e.g. 'dormant' needs 180 days of history); 'new' needs 30 days.
Windows are left-closed, right-open. The first matching rule wins, so states never overlap and every
customer x as_of gets exactly one state. Rules do not depend on K-Means clusters or generator labels.

usage: .venv/bin/python src/retail_bi/analysis/lifecycle.py   (writes reports/analysis/lifecycle_checks.json)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RULE_VERSION = 'lifecycle-v1'
DATA_START = pd.Timestamp('2024-01-01', tz='UTC')
NEW_DAYS, ACTIVE_DAYS, AT_RISK_DAYS = 30, 90, 180
STATES = ['unknown_anonymous', 'unknown_no_purchase', 'unknown_short_history', 'new', 'active', 'at_risk', 'dormant']


def classify(customer_id, first_ts, last_ts, as_of, data_start=DATA_START) -> np.ndarray:
    cid = pd.Series(customer_id)
    first, last, t = pd.to_datetime(pd.Series(first_ts), utc=True), pd.to_datetime(pd.Series(last_ts), utc=True), pd.to_datetime(pd.Series(as_of), utc=True)
    hist = (t - data_start).dt.total_seconds() / 86400
    rec = (t - last).dt.total_seconds() / 86400
    first_age = (t - first).dt.total_seconds() / 86400
    conds = [cid.isna() | (cid == ''),
             last.isna(),
             False, False, False, False, False]
    new = first_age <= NEW_DAYS
    active = rec <= ACTIVE_DAYS
    at_risk = (rec > ACTIVE_DAYS) & (rec <= AT_RISK_DAYS)
    dormant = rec > AT_RISK_DAYS
    # a state is observable only when the history covers its window
    short = (new & (hist < NEW_DAYS)) | (at_risk & (hist < ACTIVE_DAYS)) | (dormant & (hist < AT_RISK_DAYS))
    conds[2], conds[3], conds[4], conds[5], conds[6] = short, new, active, at_risk, dormant
    return np.select([np.asarray(c, dtype=bool) for c in conds], STATES, default='unknown_no_purchase')


def boundary_cases() -> list[dict]:
    t = pd.Timestamp('2025-06-02', tz='UTC')
    d = lambda days: t - pd.Timedelta(days=days)  # noqa: E731
    cases = [
        ('first purchase exactly 30 days before as_of -> new (left-closed)', 'c', d(30), d(30), t, 'new'),
        ('first purchase 30 days + 1 s before -> active', 'c', d(30) - pd.Timedelta(seconds=1), d(30) - pd.Timedelta(seconds=1), t, 'active'),
        ('last purchase exactly 90 days before -> active', 'c', d(400), d(90), t, 'active'),
        ('last purchase 90 days + 1 s before -> at_risk', 'c', d(400), d(90) - pd.Timedelta(seconds=1), t, 'at_risk'),
        ('last purchase exactly 180 days before -> at_risk', 'c', d(400), d(180), t, 'at_risk'),
        ('last purchase 180 days + 1 s before -> dormant', 'c', d(400), d(180) - pd.Timedelta(seconds=1), t, 'dormant'),
        ('no purchase visible -> unknown_no_purchase', 'c', pd.NaT, pd.NaT, t, 'unknown_no_purchase'),
        ('anonymous customer -> unknown_anonymous', None, d(10), d(10), t, 'unknown_anonymous'),
        ('anonymous wins over everything (priority)', '', pd.NaT, pd.NaT, t, 'unknown_anonymous'),
        ('160 days since purchase with 161 days of history -> at_risk (recency can never exceed history here, so the dormant guard cannot trigger)',
         'c', pd.Timestamp('2024-01-02', tz='UTC'), pd.Timestamp('2024-01-02', tz='UTC'), pd.Timestamp('2024-06-10', tz='UTC'), 'at_risk'),
        ('guard with a purchase dated before data start (other data) -> unknown_short_history', 'c', pd.Timestamp('2023-10-01', tz='UTC'),
         pd.Timestamp('2023-10-01', tz='UTC'), pd.Timestamp('2024-03-01', tz='UTC'), 'unknown_short_history'),
        ('new needs 30 days of history (as_of 10 days after data start)', 'c', pd.Timestamp('2024-01-05', tz='UTC'), pd.Timestamp('2024-01-05', tz='UTC'),
         pd.Timestamp('2024-01-11', tz='UTC'), 'unknown_short_history'),
        ('very long inactivity (700 days) -> dormant', 'c', d(800), d(700), t, 'dormant'),
    ]
    got = classify([c[1] for c in cases], [c[2] for c in cases], [c[3] for c in cases], [c[4] for c in cases])
    return [{'case': c[0], 'expected': c[5], 'got': str(g), 'passed': c[5] == g} for c, g in zip(cases, got)]


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'warehouse'))
    from db import ROOT
    from runtime import open_current
    con, ptr = open_current()
    grid = con.execute("SELECT DISTINCT as_of::VARCHAR AS as_of FROM dws.customer_snapshot ORDER BY 1").df()
    con.register('g_df', grid)
    full = con.execute(f"""WITH g AS (SELECT CAST(as_of AS TIMESTAMPTZ) AS as_of FROM g_df)
        SELECT c.customer_id, g.as_of::VARCHAR AS as_of,
               min(o.purchase_ts)::VARCHAR AS first_ts, max(o.purchase_ts)::VARCHAR AS last_ts
        FROM g CROSS JOIN dwd.dim_customer c
        LEFT JOIN dwd.fact_order o ON o.customer_id = c.customer_id AND o.approved_ts < g.as_of AND o.purchase_ts < g.as_of
        GROUP BY 1, 2""").df()
    snap = con.execute("SELECT customer_id, as_of::VARCHAR AS as_of, lifecycle_state FROM dws.customer_snapshot WHERE snapshot_version = 'snapshot-v1'").df()
    gaps = con.execute("""WITH o AS (SELECT customer_id, purchase_ts, lag(purchase_ts) OVER (PARTITION BY customer_id ORDER BY purchase_ts) prev
                          FROM dwd.fact_order WHERE approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00')
                          SELECT quantile_cont(epoch(purchase_ts - prev) / 86400, [0.25, 0.5, 0.75, 0.9]) FROM o WHERE prev IS NOT NULL""").fetchone()[0]
    future = con.execute("""WITH s AS (SELECT customer_id, as_of, lifecycle_state FROM dws.customer_snapshot
                                       WHERE snapshot_version = 'snapshot-v1' AND as_of <= TIMESTAMPTZ '2026-05-01 00:00:00+00')
                            SELECT lifecycle_state, count(*) AS rows,
                                   avg((EXISTS (SELECT 1 FROM dwd.fact_order o WHERE o.customer_id = s.customer_id AND o.purchase_ts >= s.as_of
                                         AND o.purchase_ts < s.as_of + INTERVAL 180 DAY AND o.approved_ts < s.as_of + INTERVAL 181 DAY))::INT) AS buy_within_180d
                            FROM s GROUP BY 1 ORDER BY 1""").df()
    con.close()
    full['state'] = classify(full.customer_id, full.first_ts, full.last_ts, full.as_of)
    m = full.merge(snap, on=['customer_id', 'as_of'], how='left')
    seen = m[m.lifecycle_state.notna()]
    cases = boundary_cases()
    counts = full.state.value_counts().to_dict()
    out = {
        'task_id': 'EDA-05', 'rule_version': RULE_VERSION, 'release': ptr['version'],
        'thresholds_days': {'new': NEW_DAYS, 'active': ACTIVE_DAYS, 'at_risk': AT_RISK_DAYS},
        'evidence_for_thresholds': {'gap_days_p25_p50_p75_p90': [round(x, 1) for x in gaps],
                                    'buy_within_180d_by_state': future.to_dict('records')},
        'boundary_cases': cases,
        'coverage': {'customer_x_as_of_rows': int(len(full)), 'as_of_points': int(full.as_of.nunique()), 'customers': int(full.customer_id.nunique()),
                     'state_counts': {k: int(v) for k, v in counts.items()},
                     'every_row_has_exactly_one_state': bool(full.state.isin(STATES).all() and not full.duplicated(['customer_id', 'as_of']).any())},
        'agreement_with_warehouse_snapshot': {'rows_compared': int(len(seen)), 'agree': int((seen.state == seen.lifecycle_state).sum()),
                                              'note': '数仓快照只含有可见购买的客户，其 lifecycle_state 用相同阈值（默认值），与 lifecycle-v1 一致'},
        'independent_of_clusters': True,
    }
    out['all_checks_passed'] = all(c['passed'] for c in cases) and out['coverage']['every_row_has_exactly_one_state'] \
        and out['agreement_with_warehouse_snapshot']['agree'] == out['agreement_with_warehouse_snapshot']['rows_compared']
    (ROOT / 'reports/analysis/lifecycle_checks.json').write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps({k: out[k] for k in ('coverage', 'agreement_with_warehouse_snapshot', 'all_checks_passed')}, ensure_ascii=False, default=str))
    print([c for c in cases if not c['passed']])
    sys.exit(0 if out['all_checks_passed'] else 1)


if __name__ == '__main__':
    main()
