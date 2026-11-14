"""UI-05: read-only weekly scoring list for the prediction page through runtime.open_current().

score_list() returns the latest scored snapshot with the frozen weekly-list ranking (ML-08: 90-day order
count, then 90-day amount) and the model probability; out-of-population customers (no purchase in 90 days)
are counted separately and have no probability. Fixed SQL only; only observable fields, no city or zip.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
from runtime import open_current  # noqa: E402

REPORTS = ROOT / 'reports/model'
EXPECTED_MODEL = 'repurchase-logreg-v1'   # frozen in ML-08; the page refuses a scoring table from another version


def frozen_reports(names) -> tuple[dict, list]:
    """Frozen model records shown by the pages (read only). Returns (records, missing or unreadable names)."""
    out, missing = {}, []
    for n in names:
        try:
            out[n] = json.loads((REPORTS / f'{n}.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            missing.append(n)
    return out, missing


def score_list(releases=None) -> dict:
    con, ptr = open_current(releases) if releases else open_current()
    try:
        df = con.execute("""SELECT s.customer_id, s.as_of::DATE::VARCHAR AS as_of_date, s.model_version, s.applicability, p.frequency_90d, p.monetary_90d_usd,
                                   p.recency_days, p.lifecycle_state, s.p_repurchase_30d, s.ranking_score, s.top_factors
                            FROM ads.model_scores s JOIN ads.customer_profile_latest p USING (customer_id)
                            WHERE s.as_of = (SELECT max(as_of) FROM ads.model_scores)""").df()
    finally:
        con.close()
    inpop = df[df.applicability == 'in_population'].sort_values(['ranking_score', 'customer_id'], ascending=[False, True]).reset_index(drop=True)
    inpop.insert(0, 'rank', inpop.index + 1)
    return {'release': ptr['version'], 'as_of_date': df.as_of_date.max() if len(df) else None, 'list': inpop,
            'out_of_population': int((df.applicability == 'out_of_population').sum()), 'model_version': df.model_version.iloc[0] if len(df) else None}


def trial(lst: pd.DataFrame, k_share: float, p_min: float = 0.0) -> dict:
    """What-if only: take the top k_share of the ranked list, optionally keep p >= p_min. Nothing is saved."""
    n = len(lst)
    k = int(round(n * k_share))
    top = lst.head(k)
    sel = top[top.p_repurchase_30d >= p_min]
    return {'population': n, 'k': k, 'selected': int(len(sel)), 'mean_p_selected': float(sel.p_repurchase_30d.mean()) if len(sel) else None,
            'expected_repurchasers': float(sel.p_repurchase_30d.sum()), 'mean_p_population': float(lst.p_repurchase_30d.mean()) if n else None, 'rows': sel}
