"""DW-05: build the point-in-time customer snapshot and the separate label table.

usage: .venv/bin/python src/retail_bi/features/snapshot.py --db warehouse/build/dev.duckdb \
         --contract-out reports/warehouse/snapshot_contract.json
Versions: snapshot-v1 (features), label-repurchase-v1 (labels). Lifecycle state uses the default
thresholds of docs/business_scope.md §3 (rule 'lifecycle-default-v0'); EDA-05 calibrates them.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'warehouse'))
from db import ROOT, connect, sql_blocks  # noqa: E402

SQL = sql_blocks(ROOT / 'sql/customer_snapshot.sql')
PARAMS = {'first_as_of': '2024-04-01 00:00:00', 'cutoff': '2026-11-08 00:00:00', 'step_days': 7, 'horizon': 30, 'maturity_days': 1,
          'snapshot_version': 'snapshot-v1', 'label_version': 'label-repurchase-v1'}


def run_block(con, name, params):
    for stmt in [s.strip() for s in SQL[name].split(';') if s.strip()]:
        used = {k: v for k, v in params.items() if f'${k}' in stmt}
        con.execute(stmt, used) if used else con.execute(stmt)


def build(db: Path, params: dict = PARAMS) -> dict:
    con = connect(db)
    con.execute('BEGIN TRANSACTION')
    try:
        for b in ('as_of_grid', 'snapshot', 'labels'):
            run_block(con, b, params)
        con.execute('COMMIT')
    except BaseException:
        con.execute('ROLLBACK')
        con.close()
        raise
    cur = con.execute(SQL['coverage'], {'snapshot_version': params['snapshot_version']})
    coverage = dict(zip([d[0] for d in cur.description], cur.fetchone()))
    lc = con.execute(SQL['label_coverage'], {'snapshot_version': params['snapshot_version'], 'label_version': params['label_version']}).fetchone()
    labels = dict(zip(['as_of_points', 'first_as_of', 'last_as_of', 'rows', 'positives', 'rows_in_90d_population', 'positives_in_90d_population'], lc))
    mix = dict(con.execute(SQL['lifecycle_mix'], {'snapshot_version': params['snapshot_version']}).fetchall())
    con.close()
    return {
        'task_id': 'DW-05', 'params': params,
        'keys': {'snapshot': ['customer_id', 'as_of', 'snapshot_version (filter)'],
                 'labels': ['customer_id', 'as_of', 'horizon_days', 'label_version']},
        'snapshot_table': 'dws.customer_snapshot', 'label_table': 'dws.label_repurchase',
        'feature_rule': '只用 purchase_ts < as_of 且 approved_ts < as_of 的有效订单；不读最终状态、物流结果、生成器标签',
        'columns': {
            'feature_window_start': 'as_of - 90 天（近 90 天特征的起点，左闭右开）',
            'recency_days': 'as_of 距最近一次有效购买的天数',
            'frequency_90d': '[as_of-90d, as_of) 有效订单数；>=1 即为默认模型母体（ML-01 冻结）',
            'monetary_90d_usd': '同窗有效订单商品金额（USD，不含运费）',
            'orders_all_time / merch_all_time_usd': 'as_of 前全部有效订单数与商品金额',
            'first_purchase_ts / tenure_days': '首次可观测有效购买时间与距今天数',
            'lifecycle_state': 'new / active / at_risk / dormant，默认阈值 30/90/180 天（lifecycle-default-v0，EDA-05 校准）',
        },
        'label_rule': 'y = [as_of, as_of+30d) 内有下单且在 as_of+31d 前已审批的订单；成熟时间 label_matured_at = as_of + 31 天，只为成熟时间不晚于截止的 as_of 生成',
        'coverage': coverage, 'labels': labels, 'lifecycle_mix': mix,
        'data_cutoff_exclusive': params['cutoff'] + 'Z', 'timezone': 'UTC engineering assumption',
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--db', type=Path, required=True)
    ap.add_argument('--contract-out', type=Path)
    a = ap.parse_args()
    r = build(a.db)
    if a.contract_out:
        a.contract_out.write_text(json.dumps(r, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps({'coverage': r['coverage'], 'labels': r['labels'], 'mix': r['lifecycle_mix']}, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
