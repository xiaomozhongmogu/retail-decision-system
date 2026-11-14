"""G-024 follow-up: which rows the model preprocessing (`baselines.Prep`) is actually fitted on.

`Prep` itself does not look at time; the guarantee comes from the callers splitting first.
These tests check the callers and the frozen artefact, not `Prep` alone.
run: .venv/bin/python -m pytest tests/model/test_prep_scope.py -q
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for p in ('src/retail_bi/model', 'src/retail_bi/data'):
    sys.path.insert(0, str(ROOT / p))
import baselines  # noqa: E402
from common import FEATURES, load_frame  # noqa: E402

DF = load_frame()


def test_baselines_fit_prep_on_training_rows_only(monkeypatch):
    seen = []
    orig = baselines.Prep.fit

    def spy(self, X):
        seen.append(X.index)
        return orig(self, X)

    monkeypatch.setattr(baselines.Prep, 'fit', spy)
    baselines.run()
    assert seen, 'Prep.fit was not called'
    for idx in seen:
        assert set(DF.loc[idx, 'set']) == {'train'}


def _medians(frame):
    return {c: float(frame[c].median()) for c in FEATURES}


def test_frozen_model_preprocessing_matches_train_plus_validation_not_test():
    model = json.loads((ROOT / 'models/repurchase-logreg-v1.json').read_text(encoding='utf-8'))
    tv = DF[DF.set.isin(['train', 'validation'])]
    assert model['fitted_rows'] == len(tv)
    stored = model['preprocessing']['medians']
    assert all(np.isclose(stored[c], v) for c, v in _medians(tv).items())
    # the stored means would move if test rows had been included
    with_test = DF[DF.set.isin(['train', 'validation', 'test'])][FEATURES].fillna(stored)
    z = with_test.copy()
    for c in model['preprocessing']['log1p_columns']:
        z[c] = np.log1p(z[c].clip(lower=0))
    assert not all(np.isclose(model['preprocessing']['mean'][c], float(z[c].mean())) for c in FEATURES)
