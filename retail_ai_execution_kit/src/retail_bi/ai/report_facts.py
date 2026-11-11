"""AI-08: weekly report facts, computed by code from the published ADS views (no LLM involved).

build_weekly_facts() reads only allowed views through runtime.query_view (the same views the business
page uses) and returns one fact JSON in the result envelope of contracts/interfaces.md:
  - report week: the last 7 days whose orders have all had time to be approved. Purchase-to-approval takes
    at most 24 hours (docs/transaction_rules.md), so the last day before as_of is still open and is reported
    separately with status partial_period; it is never compared.
  - comparisons: previous 7 days, the same weekdays 52 weeks earlier, the trailing 8-week average;
    latest complete month vs previous month and the same month last year.
  - contribution splits: week sales = orders x AOV; month sales = buyers x orders per buyer x AOV
    (log-mean split, the parts add up exactly); month change by category and by customer region.
  - anomaly candidates: daily robust z-scores, the week against its 8-week baseline, large category moves.
    They are candidates for a person to check, not conclusions.
Every fact carries evidence_id, unit, window [start, end), the query (view, columns, filter, SQL hash),
dataset and metric versions, a status and its sample size. A zero denominator gives value null with status
zero_denominator; a window outside the data gives incomplete_period; a base under MIN_BASE gives small_sample.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))

AS_OF = date(2026, 11, 8)        # data cutoff (exclusive), transaction-rules-v1
APPROVAL_LAG_DAYS = 1            # purchase-to-approval at most 24 h (measured, docs/transaction_rules.md)
MIN_BASE = 30                    # minimum orders/lines in a base period before a growth rate is reported
DAILY_Z, WEEKLY_Z = 3.0, 2.0     # anomaly-candidate thresholds
CATEGORY_SHARE = 0.03            # a category moving the month total by >= 3 % of the base is a candidate
FACTS_VERSION = 'report-facts-v1'
ZH = {'orders': '有效订单', 'sales': '商品金额', 'aov': '客单价'}
UNITS = {'orders': 'count', 'sales': 'USD', 'shipping': 'USD', 'aov': 'USD', 'buyers': 'customers',
         'orders_per_buyer': 'ratio', 'rate': 'ratio', 'customers': 'customers', 'z': 'z-score', 'share': 'ratio'}


def sha8(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()[:8]


def metric_version() -> str:
    return 'metrics@' + hashlib.sha256((ROOT / 'contracts/metrics.json').read_bytes()).hexdigest()[:8]


def view_sql(view, columns=None, where=None, limit=5000):
    """Same SELECT text runtime.query_view builds; hashed into evidence ids."""
    sql = f'SELECT {", ".join(columns or ["*"])} FROM {view}'
    if where:
        sql += ' WHERE ' + ' AND '.join(f'{k} = ?' for k in where)
    return sql + f' LIMIT {limit}' + (' -- ' + json.dumps(where, sort_keys=True) if where else '')


def window(start: date, end: date) -> dict:
    return {'start': start.isoformat(), 'end': end.isoformat(), 'closed': 'left'}


def money(x) -> float:
    return float(Decimal(x).quantize(Decimal('0.01')))


def ratio(num, den, nd=4):
    return None if not den else round(float(num) / float(den), nd)


def log_split(new: dict, base: dict, factors: list, total_new, total_base):
    """Log-mean (LMDI) split of total_new - total_base into factor effects that add up exactly."""
    if any(not new[f] or not base[f] for f in factors) or not total_new or not total_base:
        return None, 'zero_denominator'
    d = float(total_new) - float(total_base)
    if d == 0:
        return {f: 0.0 for f in factors}, 'ok'
    L = d / math.log(float(total_new) / float(total_base))
    eff = {f: round(L * math.log(float(new[f]) / float(base[f])), 2) for f in factors}
    eff[factors[-1]] = round(d - sum(eff[f] for f in factors[:-1]), 2)   # absorb rounding so parts sum exactly
    return eff, 'ok'


class Facts:
    def __init__(self, dataset_version, mversion):
        self.items, self.dv, self.mv = [], dataset_version, mversion

    def add(self, metric, label, value, unit, win, query, status='ok', n=None, **extra):
        q = {'view': query[0], 'columns': query[1], 'where': query[2], 'sql_id': 'sql:' + sha8(view_sql(*query))}
        if value is None and status == 'ok':
            status = 'zero_denominator'
        eid = 'fact:' + sha8(json.dumps([metric, win, q['sql_id'], self.dv, extra.get('compare_window')], sort_keys=True))
        f = {'evidence_id': eid, 'metric': metric, 'label': label, 'value': value, 'unit': unit, 'window': win,
             'status': status, 'sample_size': n, 'query': q, 'dataset_version': self.dv, 'metric_version': self.mv, **extra}
        self.items.append(f)
        return f


def compute(daily, monthly, catreg, lifecycle, repurchase, as_of=AS_OF, dataset_version='fixture', mversion='metrics@fixture'):
    """Pure computation over view rows (lists of dicts with string values, as query_view returns)."""
    F = Facts(dataset_version, mversion)
    warnings, candidates, not_available = [], [], []
    QD = ('ads.kpi_daily', ['day', 'valid_orders', 'merchandise_sales_usd', 'shipping_usd'], None)
    QM = ('ads.kpi_monthly', ['month', 'valid_orders', 'merchandise_sales_usd', 'buyers', 'aov_usd', 'partial_period'], None)
    QC = ('ads.sales_month_category_region', ['month', 'product_category', 'customer_region', 'valid_lines', 'merchandise_sales_usd'], None)
    QL = ('ads.lifecycle_mix_weekly', ['as_of_date', 'lifecycle_state', 'customers', 'rule_version'], None)
    QR = ('ads.repurchase_rate_weekly', ['as_of_date', 'population', 'repurchasers', 'repurchase_rate_30d'], None)

    # ---- daily series (days without valid orders are absent from the view -> zero) ----
    by_day = {date.fromisoformat(r['day']): r for r in daily}
    data_start = min(by_day) if by_day else as_of

    def day_vals(d):
        r = by_day.get(d)
        return (int(r['valid_orders']), Decimal(r['merchandise_sales_usd']), Decimal(r['shipping_usd'])) if r else (0, Decimal(0), Decimal(0))

    def period(start, end):
        if start < data_start:
            return None
        o, s, sh = 0, Decimal(0), Decimal(0)
        d = start
        while d < end:
            a, b, c = day_vals(d)
            o, s, sh = o + a, s + b, sh + c
            d += timedelta(days=1)
        return {'orders': o, 'sales': s, 'shipping': sh, 'aov': (s / o) if o else None}

    settled_end = as_of - timedelta(days=APPROVAL_LAG_DAYS)
    W = (settled_end - timedelta(days=7), settled_end)
    P = (W[0] - timedelta(days=7), W[0])
    Y = (W[0] - timedelta(days=364), W[1] - timedelta(days=364))
    weeks = {'report_week': W, 'previous_week': P, 'same_week_last_year': Y}
    vals = {k: period(*w) for k, w in weeks.items()}
    for k, w in weeks.items():
        v = vals[k]
        win = window(*w)
        if v is None:
            for m in ('orders', 'sales', 'aov'):
                F.add(f'{k}.{m}', f'{k} {ZH[m]}', None, UNITS[m], win, QD, status='incomplete_period', n=0)
            continue
        F.add(f'{k}.orders', '有效订单', v['orders'], 'count', win, QD, n=v['orders'])
        F.add(f'{k}.sales', '商品金额', money(v['sales']), 'USD', win, QD, n=v['orders'])
        F.add(f'{k}.shipping', '运费', money(v['shipping']), 'USD', win, QD, n=v['orders'])
        F.add(f'{k}.aov', '客单价', money(v['aov']) if v['aov'] is not None else None, 'USD', win, QD, n=v['orders'])

    w = vals['report_week']
    for k, label in (('previous_week', '环比'), ('same_week_last_year', '同比（52 周前同星期）')):
        b = vals[k]
        cw = window(*weeks[k])
        for m in ('orders', 'sales', 'aov'):
            if w is None or b is None:
                F.add(f'change_vs_{k}.{m}', f'{ZH[m]}{label}', None, 'ratio', window(*W), QD, status='incomplete_period', compare_window=cw)
                continue
            status = 'small_sample' if b['orders'] < MIN_BASE else 'ok'
            if b[m] in (None, 0) or w[m] is None:
                F.add(f'change_vs_{k}.{m}', f'{ZH[m]}{label}', None, 'ratio', window(*W), QD, status='zero_denominator', n=b['orders'], compare_window=cw)
                continue
            g = round(float(w[m] - b[m]) / float(b[m]), 4)
            F.add(f'change_vs_{k}.{m}', f'{ZH[m]}{label}变化率', g if status == 'ok' else None, 'ratio', window(*W), QD, status=status,
                  n=b['orders'], compare_window=cw, absolute_change=(w[m] - b[m]) if m == 'orders' else money(w[m] - b[m]))
        if w and b:
            eff, st = log_split({'orders': w['orders'], 'aov': w['aov']}, {'orders': b['orders'], 'aov': b['aov']}, ['orders', 'aov'], w['sales'], b['sales'])
            F.add(f'split_vs_{k}', f'商品金额{label}变化 = 订单数影响 + 客单价影响', eff, 'USD', window(*W), QD, status=st, n=b['orders'],
                  compare_window=cw, total_change=money(w['sales'] - b['sales']) if st == 'ok' else None)

    # trailing 8 weeks before the report week
    trail = [period(W[0] - timedelta(days=7 * i), W[0] - timedelta(days=7 * (i - 1))) for i in range(1, 9)]
    trail = [t for t in trail if t]
    if len(trail) == 8 and w:
        tw = window(W[0] - timedelta(days=56), W[0])
        for m in ('orders', 'sales'):
            xs = [float(t[m]) for t in trail]
            mean, sd = statistics.mean(xs), statistics.stdev(xs)
            F.add(f'trailing_8w_mean.{m}', f'前 8 周周均{ZH[m]}', round(mean, 2), UNITS[m], tw, QD, n=sum(t['orders'] for t in trail))
            z = round((float(w[m]) - mean) / sd, 2) if sd else None
            f = F.add(f'report_week_z.{m}', f'本周{ZH[m]}相对前 8 周的 z 值', z, 'z-score', window(*W), QD, n=8, compare_window=tw)
            if z is not None and abs(z) >= WEEKLY_Z:
                candidates.append({'type': 'weekly', 'metric': m, 'z': z, 'evidence_id': f['evidence_id'],
                                   'note': f'本周{ZH[m]}偏离前 8 周均值 {z} 个标准差（阈值 {WEEKLY_Z}），需人工核实'})
    else:
        F.add('trailing_8w_mean.sales', '前 8 周周均商品金额', None, 'USD', window(W[0] - timedelta(days=56), W[0]), QD, status='incomplete_period')

    # daily robust z for the report week and the open tail day
    hist_days = [W[0] - timedelta(days=i) for i in range(1, 57)]
    for m, idx in (('orders', 0), ('sales', 1)):
        hist = [float(day_vals(d)[idx]) for d in hist_days if d >= data_start]
        if len(hist) < 28:
            continue
        med = statistics.median(hist)
        mad = statistics.median([abs(x - med) for x in hist]) * 1.4826
        for d in [W[0] + timedelta(days=i) for i in range(7)] + [settled_end]:
            x = float(day_vals(d)[idx])
            z = round((x - med) / mad, 2) if mad else None
            if z is not None and abs(z) >= DAILY_Z:
                f = F.add(f'daily_z.{m}.{d}', f'{d} 日{ZH[m]}的稳健 z 值', z, 'z-score', window(d, d + timedelta(days=1)), QD,
                          n=len(hist), compare_window=window(hist_days[-1], W[0]), value_on_day=x if m == 'orders' else round(x, 2))
                note = f'{d} 日{ZH[m]}={x:g}，前 56 天中位数 {med:g}，稳健 z={z}'
                if d >= settled_end:
                    note += '；该日订单尚未全部审批（下单到审批最长 24 小时），偏低是预期的，不代表经营变化'
                candidates.append({'type': 'daily', 'metric': m, 'day': d.isoformat(), 'z': z, 'evidence_id': f['evidence_id'], 'note': note})

    tail = period(settled_end, as_of)
    if tail is not None:
        F.add('open_tail.orders', '截止前最后一天的有效订单（审批未落定，不参与比较）', tail['orders'], 'count', window(settled_end, as_of), QD,
              status='partial_period', n=tail['orders'])
        warnings.append({'code': 'partial_period', 'message': f'{settled_end} 当天的订单可能尚未审批，只单独列出，不参与环比/同比'})

    # ---- latest complete month ----
    mrows = {r['month']: r for r in monthly}
    cur_month = as_of.strftime('%Y-%m')
    first = as_of.replace(day=1)
    M = (first - timedelta(days=1)).replace(day=1)               # latest month that ended before as_of - lag
    if date(M.year + (M.month // 12), M.month % 12 + 1, 1) > settled_end:
        M = (M - timedelta(days=1)).replace(day=1)
    def mkey(d): return d.strftime('%Y-%m')
    PM = (M - timedelta(days=1)).replace(day=1)
    YM = M.replace(year=M.year - 1)
    def mend(d): return date(d.year + (d.month // 12), d.month % 12 + 1, 1)
    months = {'report_month': M, 'previous_month': PM, 'same_month_last_year': YM}
    mv = {}
    for k, d in months.items():
        r = mrows.get(mkey(d))
        win = window(d, mend(d))
        if r is None or d < data_start.replace(day=1) or r.get('partial_period') == 'True':
            mv[k] = None
            F.add(f'{k}.sales', f'{mkey(d)} 商品金额', None, 'USD', win, QM, status='incomplete_period', n=0)
            continue
        o, s, b = int(r['valid_orders']), Decimal(r['merchandise_sales_usd']), int(r['buyers'])
        mv[k] = {'orders': o, 'sales': s, 'buyers': b, 'aov': (s / o) if o else None, 'orders_per_buyer': (Decimal(o) / b) if b else None}
        F.add(f'{k}.orders', f'{mkey(d)} 有效订单', o, 'count', win, QM, n=o)
        F.add(f'{k}.buyers', f'{mkey(d)} 购买客户（月内去重）', b, 'customers', win, QM, n=b)
        F.add(f'{k}.sales', f'{mkey(d)} 商品金额', money(s), 'USD', win, QM, n=o)
        F.add(f'{k}.aov', f'{mkey(d)} 客单价', money(mv[k]['aov']) if o else None, 'USD', win, QM, n=o)
        F.add(f'{k}.orders_per_buyer', f'{mkey(d)} 人均订单', round(float(mv[k]['orders_per_buyer']), 4) if b else None, 'ratio', win, QM, n=b)
    if cur_month in mrows and mrows[cur_month].get('partial_period') == 'True':
        warnings.append({'code': 'partial_period', 'message': f'{cur_month} 为不完整月，月度比较使用 {mkey(M)}'})

    cat = {}
    for r in catreg:
        cat.setdefault(r['month'], []).append(r)
    for k in ('previous_month', 'same_month_last_year'):
        a, b = mv['report_month'], mv[k]
        cw = window(months[k], mend(months[k]))
        mw = window(M, mend(M))
        if not a or not b:
            F.add(f'month_split_vs_{k}', '月商品金额变化分解', None, 'USD', mw, QM, status='incomplete_period', compare_window=cw)
            continue
        eff, st = log_split(a, b, ['buyers', 'orders_per_buyer', 'aov'], a['sales'], b['sales'])
        F.add(f'month_split_vs_{k}', '月商品金额变化 = 客户数影响 + 人均订单影响 + 客单价影响', eff, 'USD', mw, QM, status=st, n=b['orders'],
              compare_window=cw, total_change=money(a['sales'] - b['sales']),
              growth=ratio(a['sales'] - b['sales'], b['sales']) if b['orders'] >= MIN_BASE else None)
        base_total = b['sales']
        for dim in ('product_category', 'customer_region'):
            def agg(rows):
                out = {}
                for r in rows:
                    x = out.setdefault(r[dim], [Decimal(0), 0])
                    x[0] += Decimal(r['merchandise_sales_usd'])
                    x[1] += int(r['valid_lines'])
                return out
            na, nb = agg(cat.get(mkey(M), [])), agg(cat.get(mkey(months[k]), []))
            parts = []
            for key in sorted(set(na) | set(nb)):
                sa, la = na.get(key, [Decimal(0), 0])
                sb, lb = nb.get(key, [Decimal(0), 0])
                share = ratio(sa - sb, base_total)
                st2 = 'small_sample' if lb < MIN_BASE else 'ok'
                parts.append({'key': key, 'sales_new': money(sa), 'sales_base': money(sb), 'change': money(sa - sb),
                              'share_of_base_total': share, 'growth': ratio(sa - sb, sb) if st2 == 'ok' else None,
                              'lines_new': la, 'lines_base': lb, 'status': st2})
            f = F.add(f'month_contribution_vs_{k}.{dim}', f'{"品类" if dim == "product_category" else "客户大区"}对月商品金额变化的贡献',
                      parts, 'USD', mw, QC, n=sum(p['lines_base'] for p in parts), compare_window=cw,
                      sum_of_changes=money(sum(Decimal(str(p['change'])) for p in parts)))
            if dim == 'product_category' and k == 'previous_month':
                for p in parts:
                    if p['share_of_base_total'] is not None and abs(p['share_of_base_total']) >= CATEGORY_SHARE and p['status'] == 'ok':
                        candidates.append({'type': 'category_month', 'key': p['key'], 'share': p['share_of_base_total'], 'evidence_id': f['evidence_id'],
                                           'note': f'{p["key"]} 使 {mkey(M)} 商品金额相对上月变化 {p["change"]:+.2f} USD（基期总额的 {p["share_of_base_total"]:+.1%}），需结合价格与促销核实'})

    # ---- lifecycle mix (latest two weekly snapshots at or before as_of) and matured repurchase rate ----
    ls = sorted({r['as_of_date'] for r in lifecycle if date.fromisoformat(r['as_of_date']) <= as_of})
    if len(ls) >= 2:
        cur, prev = ls[-1], ls[-2]
        mix = {s: {'customers': 0, 'previous': 0} for s in {r['lifecycle_state'] for r in lifecycle}}
        rv = None
        for r in lifecycle:
            if r['as_of_date'] == cur:
                mix[r['lifecycle_state']]['customers'] = int(r['customers']); rv = r['rule_version']
            elif r['as_of_date'] == prev:
                mix[r['lifecycle_state']]['previous'] = int(r['customers'])
        for s in mix:
            mix[s]['change'] = mix[s]['customers'] - mix[s]['previous']
        F.add('lifecycle_mix', f'生命周期状态人数（快照 {cur}，对比 {prev}）', mix, 'customers', window(date.fromisoformat(cur), date.fromisoformat(cur) + timedelta(days=1)),
              QL, n=sum(v['customers'] for v in mix.values()), rule_version=rv)
    rr = sorted((r for r in repurchase), key=lambda r: r['as_of_date'])
    if rr:
        last = rr[-1]
        d = date.fromisoformat(last['as_of_date'])
        prev4 = [float(r['repurchase_rate_30d']) for r in rr[-5:-1]]
        F.add('repurchase_rate_30d.latest_matured', f'最近已成熟的 30 天复购率（as_of {d}，标签窗到 {d + timedelta(days=30)}）',
              round(float(last['repurchase_rate_30d']), 4), 'ratio', window(d, d + timedelta(days=30)), QR, n=int(last['population']),
              previous_4_mean=round(statistics.mean(prev4), 4) if len(prev4) == 4 else None,
              note='标签需 30 天窗口加 1 天审批落定，最新成熟时点早于本周')
    not_available += [
        {'metric': 'weekly_distinct_buyers', 'reason': 'ADS 只有按日去重的购买客户；同一周内跨日去重需要新视图，周报不报告周客户数，月度用月内去重客户'},
        {'metric': 'weekly_category_region_split', 'reason': 'ADS 的品类×大区视图是月粒度；品类/大区贡献在最近完整月上计算'},
        {'metric': 'channel / margin / promotion / marketing touch', 'reason': '数据不含这些字段（capability_not_supported）'},
    ]
    return {'facts': F.items, 'anomaly_candidates': candidates, 'not_available': not_available, 'warnings': warnings,
            'periods': {'report_week': window(*W), 'previous_week': window(*P), 'same_week_last_year': window(*Y),
                        'open_tail': window(settled_end, as_of), 'report_month': window(M, mend(M)),
                        'previous_month': window(PM, mend(PM)), 'same_month_last_year': window(YM, mend(YM))}}


def _rows(r):
    return [dict(zip(r['columns'], row)) for row in r['rows']] if r['status'] == 'ok' else []


def build_weekly_facts(releases: Path | None = None) -> dict:
    """Envelope of contracts/interfaces.md (build_weekly_facts). Reads only allowed views; mode live."""
    from runtime import ReleaseError, pointer, query_view
    kw = {'releases': releases} if releases else {}
    try:
        ptr = pointer(**kw)
    except (ReleaseError, FileNotFoundError, OSError):
        return {'status': 'error', 'mode': 'live', 'data': {}, 'error': {'code': 'snapshot_unavailable', 'message': '没有已发布的快照', 'retryable': False}}
    views = {'daily': 'ads.kpi_daily', 'monthly': 'ads.kpi_monthly', 'catreg': 'ads.sales_month_category_region',
             'lifecycle': 'ads.lifecycle_mix_weekly', 'repurchase': 'ads.repurchase_rate_weekly'}
    got = {}
    for k, v in views.items():
        r = query_view(v, **kw)
        if r['status'] in ('error', 'unsupported'):
            return {'status': 'error', 'mode': 'live', 'data': {}, 'error': r['error']}
        if len(r['rows']) >= 5000:
            return {'status': 'error', 'mode': 'live', 'data': {}, 'error': {'code': 'row_limit_exceeded', 'message': v, 'retryable': False}}
        got[k] = _rows(r)
    mv = metric_version()
    data = compute(**got, dataset_version=ptr['version'], mversion=mv)
    W = data['periods']['report_week']
    return {'status': 'ok' if data['facts'] else 'empty', 'data': {'facts_version': FACTS_VERSION, **{k: v for k, v in data.items() if k != 'warnings'}},
            'as_of': '2026-11-08T00:00:00+00:00', 'window': W, 'dataset_version': f'src=synthetic;rel={ptr["version"]}', 'metric_version': mv,
            'model_version': None, 'units': UNITS, 'mode': 'live', 'evidence_ids': sorted({f['query']['sql_id'] for f in data['facts']}),
            'warnings': data['warnings'], 'computed_by': 'deterministic code (no LLM)'}


if __name__ == '__main__':
    out = build_weekly_facts()
    dst = ROOT / 'reports/ai/report_facts_example.json'
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(dst, out['status'], len(out['data'].get('facts', [])), 'facts', len(out['data'].get('anomaly_candidates', [])), 'candidates')
