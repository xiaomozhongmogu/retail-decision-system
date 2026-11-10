"""ML-04: frozen time split for target-v1 samples (split-v1).

Sets are ordered by prediction time (as_of, weekly Mondays). Between sets there is a 5-week embargo so every
label of an earlier set (matured at as_of + 31 days) is known before the first prediction of the next set.
The partial quarter 2026-Q4 (one mature as_of, 2026-10-05) is part of the test set, never a set on its own.

usage: .venv/bin/python src/retail_bi/model/split.py      (writes reports/model/split_manifest.json)
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SPLIT_VERSION = 'split-v1'
LABEL_MATURITY_DAYS = 31
SETS = {   # inclusive as_of ranges (UTC Mondays)
    'train': ('2024-04-01', '2025-08-25'),
    'validation': ('2025-09-29', '2026-02-23'),
    'test': ('2026-03-30', '2026-10-05'),
}


def assign(as_of: pd.Series) -> pd.Series:
    """Return the set name for each as_of (string or timestamp); 'embargo' for points between sets."""
    t = pd.to_datetime(as_of, utc=True)
    out = pd.Series('embargo', index=as_of.index, dtype=object)
    for name, (a, b) in SETS.items():
        out[(t >= pd.Timestamp(a, tz='UTC')) & (t <= pd.Timestamp(b, tz='UTC'))] = name
    return out


def check_order() -> dict:
    names = list(SETS)
    res = {}
    for prev, nxt in zip(names, names[1:]):
        last_label = pd.Timestamp(SETS[prev][1], tz='UTC') + pd.Timedelta(days=LABEL_MATURITY_DAYS)
        first_pred = pd.Timestamp(SETS[nxt][0], tz='UTC')
        res[f'{prev}_labels_mature_before_{nxt}'] = {'last_label_matures': str(last_label.date()), 'next_first_as_of': str(first_pred.date()),
                                                     'ok': bool(last_label <= first_pred)}
    return res


def main():
    meta = json.loads((ROOT / 'reports/model/feature_build.json').read_text(encoding='utf-8'))
    df = pd.read_parquet(ROOT / meta['file'], columns=['customer_id', 'as_of', 'y'])
    df['set'] = assign(df.as_of)
    sets = {}
    cust = {}
    for name in [*SETS, 'embargo']:
        d = df[df.set == name]
        cust[name] = set(d.customer_id)
        sets[name] = {'as_of_range': SETS.get(name), 'as_of_points': int(d.as_of.nunique()), 'rows': int(len(d)),
                      'customers': int(d.customer_id.nunique()), 'positives': int(d.y.sum()),
                      'positive_rate': round(float(d.y.mean()), 4) if len(d) else None}
    overlap = {'train_validation': len(cust['train'] & cust['validation']), 'train_test': len(cust['train'] & cust['test']),
               'validation_test': len(cust['validation'] & cust['test']),
               'test_customers_seen_in_train_share': round(len(cust['train'] & cust['test']) / len(cust['test']), 4)}
    manifest = {'task_id': 'ML-04', 'split_version': SPLIT_VERSION, 'target': 'target-v1', 'feature_version': meta['feature_version'],
                'feature_file_sha256': meta['sha256'], 'unit': 'customer x weekly as_of', 'embargo_weeks': 5,
                'label_maturity_days': LABEL_MATURITY_DAYS, 'sets': sets, 'order_checks': check_order(), 'customer_overlap': overlap,
                'notes': ['同一客户在多个 as_of 和多个集合中出现：样本不独立，评估区间估计按客户或时间分块（ML-09）',
                          '测试集包含不完整的 2026-Q4（仅 2026-10-05 一个成熟 as_of），不单独评估',
                          '验收条件中的 UCI 月份示例不适用于本数据（合成交易包，D013）',
                          '拟合型预处理（填补中位数、标准化、截尾、分箱、聚类、特征选择）只在 train 拟合；验证/测试只调用 transform']}
    (ROOT / 'reports/model/split_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'sets': sets, 'overlap': overlap, 'order': check_order()}, ensure_ascii=False))


if __name__ == '__main__':
    main()
