"""ML-11: scoring service for the frozen repurchase model.

score_frame(model, X)   strict scoring: X must have exactly the model's features in the model's order, numeric,
                        and the model must be the expected version; anything else raises ScoringError.
get_risk_score(customer_id, as_of)
                        service result (contracts/interfaces.md envelope): probability, 1 - probability,
                        applicability, model version and the top model factors; customers outside the
                        target-v1 population get status 'unsupported' / out_of_population and no probability.
write_scores(build_db)  offline: score every snapshot customer at the latest as_of into ads.model_scores of a
                        warehouse build (then publish it with release.py).

usage: .venv/bin/python src/retail_bi/model/scoring.py write      # writes into warehouse/builds/latest
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
for p in ('src/retail_bi/warehouse', 'src/retail_bi/features'):
    sys.path.insert(0, str(ROOT / p))
from db import connect, sql_blocks  # noqa: E402
from customer_features import FEATURE_VERSION, FEATURES, compute  # noqa: E402

EXPECTED_MODEL = 'repurchase-logreg-v1'
MODEL_FILE = ROOT / f'models/{EXPECTED_MODEL}.json'


class ScoringError(ValueError):
    pass


def load_model(path: Path = MODEL_FILE, expected: str = EXPECTED_MODEL) -> dict:
    m = json.loads(Path(path).read_text(encoding='utf-8'))
    if m.get('model_version') != expected:
        raise ScoringError(f'model version {m.get("model_version")} != expected {expected}')
    if m.get('feature_version') != FEATURE_VERSION or m.get('features') != FEATURES:
        raise ScoringError('model was trained on a different feature version or feature order')
    return m


def score_frame(model: dict, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    if list(X.columns) != model['features']:
        raise ScoringError('feature columns or order differ from the model: ' + str([c for c in model['features'] if c not in X.columns][:5] or 'order'))
    bad = [c for c in X.columns if not pd.api.types.is_numeric_dtype(X[c])]
    if bad:
        raise ScoringError(f'non-numeric feature columns: {bad}')
    pp = model['preprocessing']
    Z = X.astype(float).fillna(pp['medians'])
    for c in pp['log1p_columns']:
        Z[c] = np.log1p(Z[c].clip(lower=0))
    Z = ((Z - pd.Series(pp['mean'])) / pd.Series(pp['std']))[model['features']].to_numpy()
    w = np.array([model['coefficients'][f] for f in model['features']])
    contrib = Z * w
    p = 1 / (1 + np.exp(-(contrib.sum(1) + model['intercept'])))
    return p, contrib


def top_factors(model, contrib_row, n=3):
    idx = np.argsort(-np.abs(contrib_row))[:n]
    return '; '.join(f'{model["features"][i]} {"+" if contrib_row[i] > 0 else "-"}' for i in idx)


def _features_at(con, customer_ids, as_of):
    keys = pd.DataFrame({'customer_id': customer_ids, 'as_of': as_of, 'y': pd.array([pd.NA] * len(customer_ids), dtype='Int64')})
    return compute(con, keys)


def get_risk_score(customer_id: str, as_of: str, model: dict | None = None) -> dict:
    from runtime import open_current
    model = model or load_model()
    con, ptr = open_current()
    try:
        f = _features_at(con, [customer_id], as_of)
    finally:
        con.close()
    env = {'as_of': as_of, 'dataset_version': ptr['version'], 'model_version': model['model_version'], 'mode': 'live',
           'units': {'p_repurchase_30d': 'probability', 'p_non_repurchase_30d': 'probability'}}
    if f.empty or int(f.orders_90d.iloc[0]) < 1:
        return {**env, 'status': 'unsupported', 'data': {'customer_id': customer_id, 'applicability': 'out_of_population'},
                'error': {'code': 'out_of_population', 'message': '过去 90 天没有有效购买，按规则队列处理，不输出模型概率', 'retryable': False}}
    p, c = score_frame(model, f[FEATURES])
    return {**env, 'status': 'ok', 'data': {'customer_id': customer_id, 'applicability': 'in_population', 'p_repurchase_30d': float(p[0]),
            'p_non_repurchase_30d': float(1 - p[0]), 'top_factors': top_factors(model, c[0]),
            'caveat': '模型在测试期的个体排序接近随机（ML-09）；概率只代表平均水平，因素是模型解释而非因果'},
            'warnings': [{'code': 'weak_model', 'message': 'test ROC-AUC 0.515'}]}


def write_scores(build_db: Path, model: dict | None = None) -> dict:
    model = model or load_model()
    con = connect(build_db)
    blocks = sql_blocks(ROOT / 'sql/scores.sql')
    as_of = con.execute("SELECT max(as_of)::VARCHAR FROM dws.customer_snapshot WHERE snapshot_version = 'snapshot-v1'").fetchone()[0]
    snap = con.execute(f"""SELECT customer_id, frequency_90d FROM dws.customer_snapshot
                           WHERE snapshot_version = 'snapshot-v1' AND as_of = TIMESTAMPTZ '{as_of}' ORDER BY customer_id""").df()
    inpop = snap[snap.frequency_90d >= 1].customer_id.tolist()
    f = _features_at(con, inpop, as_of)
    p, c = score_frame(model, f[FEATURES])
    rows = pd.DataFrame({'customer_id': f.customer_id, 'as_of': as_of, 'model_version': model['model_version'], 'applicability': 'in_population',
                         'p_repurchase_30d': p, 'p_non_repurchase_30d': 1 - p, 'ranking_score': f.orders_90d + f.merch_90d / 1e6,
                         'top_factors': [top_factors(model, r) for r in c]})
    out = snap[snap.frequency_90d < 1][['customer_id']].assign(as_of=as_of, model_version=model['model_version'], applicability='out_of_population',
                                                               p_repurchase_30d=np.nan, p_non_repurchase_30d=np.nan, ranking_score=np.nan, top_factors=None)
    allrows = pd.concat([rows, out], ignore_index=True)
    con.execute('BEGIN TRANSACTION')
    con.execute(blocks['ddl'])
    con.execute('DELETE FROM ads.model_scores WHERE model_version = ? AND as_of = CAST(? AS TIMESTAMPTZ)', [model['model_version'], as_of])
    con.register('new_scores', allrows)
    con.execute("""INSERT INTO ads.model_scores SELECT customer_id, CAST(as_of AS TIMESTAMPTZ), model_version, applicability,
                   p_repurchase_30d, p_non_repurchase_30d, ranking_score, top_factors FROM new_scores""")
    con.execute(blocks['summary_view'])
    con.execute(blocks['allow_summary'])
    con.execute('COMMIT')
    summary = con.execute('SELECT customers_scored, mean_p_repurchase_30d, out_of_population_customers FROM ads.risk_summary_latest').fetchone()
    con.execute('CHECKPOINT')
    con.close()
    return {'as_of': as_of, 'rows': len(allrows), 'in_population': len(rows), 'out_of_population': len(out), 'summary': summary}


def main():
    if sys.argv[1:] != ['write']:
        raise SystemExit(__doc__)
    latest = json.loads((ROOT / 'warehouse/builds/latest.json').read_text(encoding='utf-8'))
    print(json.dumps(write_scores(ROOT / 'warehouse/builds' / latest['file']), ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
