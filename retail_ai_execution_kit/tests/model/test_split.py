"""ML-04 split tests. run: .venv/bin/python -m pytest tests/model/test_split.py -q"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in ('src/retail_bi/model', 'src/retail_bi/data'):
    sys.path.insert(0, str(ROOT / p))
from split import SETS, LABEL_MATURITY_DAYS, assign, check_order  # noqa: E402
from transform import TrainOnlyFit  # noqa: E402

M = json.loads((ROOT / 'reports/model/split_manifest.json').read_text(encoding='utf-8'))
F = pd.read_parquet(ROOT / json.loads((ROOT / 'reports/model/feature_build.json').read_text())['file'])
F['set'] = assign(F.as_of)
F['t'] = pd.to_datetime(F.as_of, utc=True)


def test_sets_are_time_ordered_and_disjoint():
    first = {s: F[F.set == s].t.min() for s in SETS}
    last = {s: F[F.set == s].t.max() for s in SETS}
    assert last['train'] < first['validation'] and last['validation'] < first['test']


def test_labels_of_each_set_mature_before_next_set_predicts():
    assert all(v['ok'] for v in check_order().values())
    names = list(SETS)
    for a, b in zip(names, names[1:]):
        matured = F[F.set == a].t.max() + pd.Timedelta(days=LABEL_MATURITY_DAYS)
        assert matured <= F[F.set == b].t.min()


def test_partial_quarter_is_inside_test_not_alone():
    assert assign(pd.Series(['2026-10-05 00:00:00+00']))[0] == 'test'


def test_embargo_rows_excluded_from_all_sets():
    e = F[F.set == 'embargo']
    assert len(e) == M['sets']['embargo']['rows'] and e.t.between(pd.Timestamp('2025-08-26', tz='UTC'), pd.Timestamp('2025-09-28', tz='UTC')).sum() \
        + e.t.between(pd.Timestamp('2026-02-24', tz='UTC'), pd.Timestamp('2026-03-29', tz='UTC')).sum() == len(e)


def test_fitting_preprocessing_on_validation_rows_is_refused():
    train_end = pd.Timestamp(SETS['validation'][0], tz='UTC')
    train = F[F.set == 'train']
    TrainOnlyFit('standard', 'merch_90d', 't', train_end).fit(train)            # allowed
    with pytest.raises(ValueError):
        TrainOnlyFit('standard', 'merch_90d', 't', train_end).fit(F[F.set.isin(['train', 'validation'])])


def test_manifest_counts_match_data():
    for s in SETS:
        d = F[F.set == s]
        assert M['sets'][s]['rows'] == len(d) and M['sets'][s]['positives'] == int(d.y.sum())
