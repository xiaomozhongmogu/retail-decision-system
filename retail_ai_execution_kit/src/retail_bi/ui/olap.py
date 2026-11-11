"""UI-03: OLAP helpers for the business page, over rows of the allowed ADS views (pure pandas, no SQL).

- time_series(monthly, daily, grain, start, end): roll-up / drill-down along year > quarter > month > week > day.
  Sums only additive measures (orders, merchandise, shipping); AOV is recomputed as sum(merch) / sum(orders),
  never averaged. Monthly distinct buyers are not additive across months, so they are reported only at month
  grain. Periods not fully inside the data (2026, 2026-Q4, 2026-11, the last week, the last day whose orders
  are still awaiting approval) are flagged incomplete.
- cube(catreg, rows, cols, measure, filters): slice / dice / pivot over month x category x region.
  orders_containing is additive across months and regions (an order has one month and one customer region)
  but not across categories, so it is refused when categories are aggregated.
Each call returns (status, DataFrame | None, message) with status ok | empty | unsupported.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

DATA_START, LAST_SETTLED_DAY, AS_OF = date(2024, 1, 1), date(2026, 11, 6), date(2026, 11, 8)
DIMS = {'month': '月份', 'year': '年份', 'quarter': '季度', 'product_category': '品类', 'customer_region': '客户大区'}
UNSUPPORTED_DIMS = {'channel': '渠道', 'customer_state': '州（不在允许视图中）', 'gross_margin': '毛利', 'customer_age': '年龄'}
MEASURES = {'merchandise_sales_usd': ('商品金额', 'USD'), 'valid_lines': ('有效明细行', 'lines'), 'orders_containing': ('含该品类的订单', 'orders')}


def _num(df, cols):
    df = df.copy()
    for c in cols:
        df[c] = pd.to_numeric(df[c])
    return df


def time_series(monthly: pd.DataFrame, daily: pd.DataFrame, grain: str, start: str, end: str):
    """start/end are 'YYYY-MM' (inclusive months)."""
    if grain not in ('year', 'quarter', 'month', 'week', 'day'):
        return 'unsupported', None, f'不支持的时间粒度：{grain}'
    if start > end:
        return 'empty', None, '开始月份晚于结束月份'
    if grain in ('year', 'quarter', 'month'):
        m = _num(monthly, ['valid_orders', 'merchandise_sales_usd', 'shipping_usd', 'buyers'])
        m = m[(m.month >= start) & (m.month <= end)]
        if m.empty:
            return 'empty', None, '所选期间没有有效订单'
        m['year'] = m.month.str[:4]
        m['quarter'] = m.year + '-Q' + ((m.month.str[5:7].astype(int) - 1) // 3 + 1).astype(str)
        key = {'year': 'year', 'quarter': 'quarter', 'month': 'month'}[grain]
        g = m.groupby(key, as_index=False).agg(valid_orders=('valid_orders', 'sum'), merchandise_sales_usd=('merchandise_sales_usd', 'sum'),
                                                shipping_usd=('shipping_usd', 'sum'), months=('month', 'nunique'),
                                                partial=('partial_period', lambda s: (s.astype(str) == 'True').any()))
        if grain == 'month':
            g = g.merge(m[['month', 'buyers']], on='month')
        full = {'year': 12, 'quarter': 3, 'month': 1}[grain]
        g['complete'] = (g.months == full) & ~g.partial
        g = g.rename(columns={key: 'period'}).drop(columns=['months', 'partial'])
    else:
        d = _num(daily, ['valid_orders', 'merchandise_sales_usd', 'shipping_usd'])
        d['day'] = pd.to_datetime(d.day)
        lo = pd.Timestamp(start + '-01')
        hi = (pd.Timestamp(end + '-01') + pd.offsets.MonthBegin(1))
        d = d[(d.day >= lo) & (d.day < hi)]
        if d.empty:
            return 'empty', None, '所选期间没有有效订单'
        if grain == 'day':
            g = d[['day', 'valid_orders', 'merchandise_sales_usd', 'shipping_usd']].rename(columns={'day': 'period'})
            g['complete'] = g.period.dt.date <= LAST_SETTLED_DAY
        else:
            d['period'] = d.day - pd.to_timedelta(d.day.dt.weekday, unit='D')       # Monday of the ISO week
            g = d.groupby('period', as_index=False).agg(valid_orders=('valid_orders', 'sum'), merchandise_sales_usd=('merchandise_sales_usd', 'sum'),
                                                         shipping_usd=('shipping_usd', 'sum'))
            g['complete'] = (g.period >= lo) & (g.period + pd.Timedelta(days=7) <= hi) & ((g.period + pd.Timedelta(days=6)).dt.date <= LAST_SETTLED_DAY)
        g['period'] = g.period.dt.strftime('%Y-%m-%d')
    g['aov_usd'] = (g.merchandise_sales_usd / g.valid_orders.where(g.valid_orders > 0)).round(2)
    g['merchandise_sales_usd'] = g.merchandise_sales_usd.round(2)
    g['shipping_usd'] = g.shipping_usd.round(2)
    msg = '' if g.complete.all() else '标记为不完整的期间不能与完整期间直接比较'
    return 'ok', g.reset_index(drop=True), msg


def cube(catreg: pd.DataFrame, rows: str, cols: str | None, measure: str, filters: dict | None = None):
    """Slice/dice with filters {dim: [values]} (a one-value list is a slice), then group by rows (x cols = pivot)."""
    for d in [rows, cols] + list((filters or {}).keys()):
        if d is None:
            continue
        if d in UNSUPPORTED_DIMS:
            return 'unsupported', None, f'数据不支持该维度：{UNSUPPORTED_DIMS[d]}'
        if d not in DIMS:
            return 'unsupported', None, f'未知维度：{d}'
    if measure not in MEASURES:
        return 'unsupported', None, f'未知指标：{measure}'
    if cols == rows:
        return 'unsupported', None, '行和列不能是同一维度'
    c = _num(catreg, ['valid_lines', 'merchandise_sales_usd', 'orders_containing'])
    c['year'] = c.month.str[:4]
    c['quarter'] = c.year + '-Q' + ((c.month.str[5:7].astype(int) - 1) // 3 + 1).astype(str)
    for d, vals in (filters or {}).items():
        if vals:
            c = c[c[d].isin(vals)]
    if measure == 'orders_containing' and 'product_category' not in (rows, cols):
        cats = (filters or {}).get('product_category') or []
        if len(cats) != 1:
            return 'unsupported', None, '“含该品类的订单”不能跨品类相加（同一订单可含多个品类）；请把品类放在行或列，或只选一个品类'
    if c.empty:
        return 'empty', None, '筛选后没有数据'
    keys = [rows] + ([cols] if cols else [])
    g = c.groupby(keys, as_index=False)[measure].sum()
    if cols:
        g = g.pivot(index=rows, columns=cols, values=measure).fillna(0).reset_index()
        g.columns.name = None
    if measure == 'merchandise_sales_usd':
        num = g.columns.drop(rows)
        g[num] = g[num].round(2)
    return 'ok', g, ''
