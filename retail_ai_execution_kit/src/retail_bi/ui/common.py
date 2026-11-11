"""Shared UI helpers: read-only release access and the global data banner (UI-01).

The UI never writes and never opens the warehouse directly: it reads warehouse/releases/current.json and
queries only allowed ADS views through runtime.query_view. If no release exists the pages show an
explanatory empty state instead of failing.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))

import streamlit as st  # noqa: E402

from runtime import ReleaseError, pointer, query_view  # noqa: E402
from release import RELEASES  # noqa: E402

AS_OF = '2026-11-08T00:00:00Z'
# release directory; RETAIL_BI_RELEASES_DIR lets tests or a second deployment point elsewhere
def release_dir() -> Path:
    return Path(os.environ.get('RETAIL_BI_RELEASES_DIR', str(RELEASES)))


def release_info():
    try:
        return pointer(release_dir())
    except (ReleaseError, FileNotFoundError, OSError):
        return None


def banner():
    """Global header shown on every page: data version, data period, as_of, synthetic notice."""
    info = release_info()
    if info is None:
        st.warning('尚无已发布的数据版本。请先运行 `pipeline.py build` 与 `release.py publish`（见 docs/COMMANDS.md），页面将显示空状态。')
        return None
    # one text line instead of metric cards: cards truncate long values in narrow windows
    st.markdown(f"**数据版本** `{info['version']}` · **数据时间范围** 2024-01-01 至 2026-11-07 · **as_of（截止，不含）** {AS_OF[:10]}")
    st.caption('完全合成数据，模拟的历史区间，不是真实企业，也不是 2026 年实时经营。金额单位 USD（商品金额，不含运费）。')
    return info


def view(name, columns=None, where=None, limit=5000):
    """Query an allowed view; returns (status, DataFrame or None, message)."""
    import pandas as pd
    if release_info() is None:
        return 'empty', None, '没有已发布版本'
    r = query_view(name, columns, where, limit, releases=release_dir())
    if r['status'] in ('unsupported', 'error'):
        return r['status'], None, r['error']['message']
    if r['status'] == 'empty':
        return 'empty', pd.DataFrame(columns=r['columns']), '查询合法，但没有符合条件的数据'
    return 'ok', pd.DataFrame(r['rows'], columns=r['columns']), ''


def show(status, df, msg, empty_hint='暂无数据'):
    if status == 'ok':
        return True
    if status == 'empty':
        st.info(f'{empty_hint}：{msg}')
    else:
        st.error(f'无法查询：{msg}')
    return False
