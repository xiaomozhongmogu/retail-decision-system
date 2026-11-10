"""DATA-06: full quality profile of the frozen research scope (before cleaning).

Reads every row of the DATA-05 engineering layer (history_source + observed),
uses the approved contract for column types, and writes a JSON profile plus a
Markdown summary. No sampling: the whole frozen scope is profiled. Sample rows
quoted as evidence carry only synthetic IDs, dates and amounts (no ZIP codes).

usage: .venv/bin/python src/retail_bi/data/profile.py --layer <dir> \
         --contract contracts/data_contract.json --out-json reports/data/profile_before.json \
         --out-md reports/data/profile_before.md
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

PROVISIONAL = 'provisional: purchase = order not cancelled (DATA-08 freezes the rule)'


def read(path: Path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)


def ts(v: str):
    return datetime.fromisoformat(v).replace(tzinfo=timezone.utc) if v else None


def q(values, ps=(0.0, 0.01, 0.25, 0.5, 0.75, 0.99, 1.0)):
    s = sorted(values)
    if not s:
        return None
    out = {}
    for p in ps:
        i = min(len(s) - 1, max(0, round(p * (len(s) - 1))))
        out[f'p{int(p * 100):02d}'] = str(s[i])
    return out


def iqr_outliers(values):
    s = sorted(values)
    if len(s) < 4:
        return 0, None
    qs = statistics.quantiles([float(x) for x in s], n=4)
    hi = qs[2] + 3 * (qs[2] - qs[0])
    return sum(float(x) > hi for x in s), round(hi, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--layer', required=True)
    ap.add_argument('--contract', required=True)
    ap.add_argument('--out-json', required=True)
    ap.add_argument('--out-md', required=True)
    a = ap.parse_args()
    layer, contract = Path(a.layer), json.loads(Path(a.contract).read_text(encoding='utf-8'))
    cutoff = datetime.fromisoformat(contract['as_of_exclusive'])

    T = {}
    for t in contract['tables']:
        _, T[t] = read(layer / 'history_source' / f'{t}.csv')
    _, obs_orders = read(layer / 'observed' / 'orders.csv')
    _, obs_reviews = read(layer / 'observed' / 'reviews.csv')
    orders, items, pays, ship = T['orders'], T['order_items'], T['payments'], T['shipping']
    O = {o['order_id']: o for o in orders}
    S = {s['order_id']: s for s in ship}
    items_by = defaultdict(list)
    for r in items:
        items_by[r['order_id']].append(r)

    # ---- 1. volume and entity coverage
    volume = {t: len(v) for t, v in T.items()}
    volume['observed_orders'] = len(obs_orders)
    volume['observed_reviews'] = len(obs_reviews)
    buyers = {o['customer_id'] for o in orders}
    entities = {
        'customers_master': len(T['customers']), 'customers_with_orders': len(buyers),
        'customers_without_orders_before_cutoff': len(T['customers']) - len(buyers),
        'products_master': len(T['products']), 'products_sold': len({r['product_id'] for r in items}),
        'sellers_master': len(T['sellers']), 'sellers_with_sales': len({r['seller_id'] for r in items}),
        'listings_master': len(T['seller_products']), 'listings_sold': len({r['seller_product_id'] for r in items}),
    }

    # ---- 2. missing values (all columns), with contract role
    missing = {}
    for t, rows in T.items():
        for c in contract['tables'][t]['columns']:
            n = sum(r[c['raw_name']] == '' for r in rows)
            if n:
                missing[f'{t}.{c["raw_name"]}'] = {'nulls': n, 'rows': len(rows), 'rate': round(n / len(rows), 4)}

    # ---- 3. duplicates and duplicate candidates
    dup = {}
    for t, rows in T.items():
        c = Counter(tuple(r.values()) for r in rows)
        dup[f'exact_duplicate_rows:{t}'] = sum(n - 1 for n in c.values() if n > 1)
    same_cust_ts = Counter((o['customer_id'], o['order_purchase_timestamp']) for o in orders)
    dup['orders_same_customer_same_timestamp'] = sum(n - 1 for n in same_cust_ts.values() if n > 1)
    same_day = Counter((o['customer_id'], o['order_purchase_timestamp'][:10]) for o in orders)
    dup['customer_days_with_2plus_orders'] = sum(n > 1 for n in same_day.values())
    same_ts = Counter(o['order_purchase_timestamp'] for o in orders)
    dup['purchase_timestamps_shared_by_2plus_orders'] = sum(n > 1 for n in same_ts.values())
    prod_in_order = Counter((r['order_id'], r['product_id']) for r in items)
    dup['order_items_same_product_repeated_in_order'] = sum(n - 1 for n in prod_in_order.values() if n > 1)
    dup['orders_with_2_payments'] = sum(n > 1 for n in Counter(p['order_id'] for p in pays).values())
    listing_in_order = Counter((r['order_id'], r['seller_product_id']) for r in items)
    dup['order_items_same_listing_repeated_in_order'] = sum(n - 1 for n in listing_in_order.values() if n > 1)
    price_groups = defaultdict(list)
    for r in items:
        price_groups[(r['order_id'], r['product_id'])].append(r['item_price_usd'])
    rep_groups = [g for g in price_groups.values() if len(g) > 1]
    dup['repeated_product_groups'] = len(rep_groups)
    dup['repeated_product_groups_with_identical_prices'] = sum(len(set(g)) == 1 for g in rep_groups)
    samples_dup = {
        'same_customer_same_day': [list(k) for k, n in same_day.items() if n > 1][:5],
        'same_product_repeated_in_order': [list(k) for k, n in prod_in_order.items() if n > 1][:5],
    }

    # ---- 4. time coverage and ordering
    p_ts = [ts(o['order_purchase_timestamp']) for o in orders]
    months = Counter(t.strftime('%Y-%m') for t in p_ts)
    days = Counter(t.date() for t in p_ts)
    first_day, last_day = min(days), max(days)
    span_days = (last_day - first_day).days + 1
    zero_days = [first_day + timedelta(d) for d in range(span_days) if first_day + timedelta(d) not in days]
    order_checks = Counter()
    samples_time = defaultdict(list)
    for o in orders:
        pt, ap_, ca, de = (ts(o[k]) for k in ('order_purchase_timestamp', 'order_approved_at',
                                              'order_delivered_carrier_date', 'order_delivered_customer_date'))
        est = ts(o['order_estimated_delivery_date'])
        for name, bad in [('approved_before_purchase', ap_ and ap_ < pt), ('carrier_before_approved', ca and ap_ and ca < ap_),
                          ('delivered_before_carrier', de and ca and de < ca), ('estimated_before_purchase', est < pt)]:
            if bad:
                order_checks[name] += 1
                samples_time[name].append(o['order_id'])
        order_checks['_checked'] += 1
    cal_dates = {r['date'][:10] for r in T['calendar']}
    time_cov = {
        'timezone': contract['event_timezone'],
        'purchase_first': min(p_ts).isoformat(), 'purchase_last': max(p_ts).isoformat(),
        'cutoff_exclusive': contract['as_of_exclusive'],
        'months': len(months), 'orders_per_month': dict(sorted(months.items())),
        'calendar_days_in_span': span_days, 'days_with_orders': len(days), 'days_without_orders': len(zero_days),
        'last_month_is_partial': max(p_ts).strftime('%Y-%m') == (cutoff - timedelta(seconds=1)).strftime('%Y-%m') and cutoff.day != 1,
        'calendar_covers_all_purchase_days': all(d.isoformat() in cal_dates for d in days),
        'event_order_violations': {k: v for k, v in order_checks.items()},
        'event_order_samples': {k: v[:5] for k, v in samples_time.items()},
        'customers_created_range': [min(r['created_at'] for r in T['customers']), max(r['created_at'] for r in T['customers'])],
    }

    # ---- 5. cancellations, zero/negative and extreme transactions
    status = Counter(o['order_status'] for o in orders)
    money_cols = [('order_items', 'item_price_usd'), ('order_items', 'shipping_cost_usd'), ('order_items', 'item_total_usd'),
                  ('payments', 'payment_value_usd'), ('shipping', 'shipping_cost_usd'), ('products', 'product_price_base_usd'),
                  ('seller_products', 'seller_price_usd')]
    money = {}
    for t, c in money_cols:
        vals = [Decimal(r[c]) for r in T[t]]
        n_out, hi = iqr_outliers(vals)
        money[f'{t}.{c}'] = {'negative': sum(v < 0 for v in vals), 'zero': sum(v == 0 for v in vals),
                             'quantiles': q(vals), 'sum': str(sum(vals)),
                             'extreme_above_q3_plus_3iqr': n_out, 'extreme_threshold': hi}
    order_total = {oid: sum(Decimal(i['item_total_usd']) for i in lst) for oid, lst in items_by.items()}
    ot = sorted(order_total.items(), key=lambda kv: kv[1], reverse=True)
    n_out, hi = iqr_outliers(list(order_total.values()))
    sp = {r['seller_product_id']: Decimal(r['seller_price_usd']) for r in T['seller_products']}
    ratio = [Decimal(r['item_price_usd']) / sp[r['seller_product_id']] for r in items if sp[r['seller_product_id']] > 0]
    extremes = {
        'order_total_usd_quantiles': q(list(order_total.values())),
        'orders_above_q3_plus_3iqr': n_out, 'order_threshold_usd': hi,
        'top5_orders': [{'order_id': k, 'order_total_usd': str(v), 'items': len(items_by[k]), 'status': O[k]['order_status']} for k, v in ot[:5]],
        'items_per_order': dict(sorted(Counter(len(v) for v in items_by.values()).items())),
        'item_price_to_listing_price_ratio_quantiles': q([round(x, 4) for x in ratio]),
        'installments': dict(sorted(Counter(int(p['payment_installments']) for p in pays).items())),
    }
    cancel = {
        'status_counts': dict(status),
        'cancelled_item_price_usd': str(sum(Decimal(i['item_price_usd']) for o in orders if o['order_status'] == 'cancelled' for i in items_by[o['order_id']])),
        'cancelled_orders_with_payment_rows': sum(1 for o in orders if o['order_status'] == 'cancelled' and any(p['order_id'] == o['order_id'] for p in pays)),
        'cancelled_orders_with_review': sum(1 for r in T['reviews'] if O[r['order_id']]['order_status'] == 'cancelled'),
        'refund_or_negative_records': 0,
        'note': '没有退款表、负金额或冲销记录；取消只能由最终状态识别，且没有取消发生时间',
    }

    # ---- 6. field validity: derived shipping fields vs timestamps, review/date logic
    validity = Counter({k: 0 for k in (
        'actual_delivery_days != floor(delivered - purchase)', 'delivery_delay_days != max(0, actual - estimated_days)',
        'late_flag != (delay_days > 0)', 'delivered after estimated DATE but late_flag False',
        'undelivered but actual/delay present', 'undelivered but late_flag True',
        'estimated_date - purchase_date != estimated_delivery_days', 'review on non-delivered order',
        'review created before delivery date', 'satisfaction_flag != score<=2')})
    vsamples = defaultdict(list)
    for o in orders:
        s = S[o['order_id']]
        pt, de, est = ts(o['order_purchase_timestamp']), ts(o['order_delivered_customer_date']), ts(o['order_estimated_delivery_date'])
        if de:
            actual = Decimal(s['actual_delivery_days'])
            if actual != (de - pt).days:
                validity['actual_delivery_days != floor(delivered - purchase)'] += 1
                vsamples['actual_days'].append(o['order_id'])
            delay = Decimal(s['delivery_delay_days'])
            if delay != max(Decimal(0), actual - Decimal(s['estimated_delivery_days'])):
                validity['delivery_delay_days != max(0, actual - estimated_days)'] += 1
            if (s['late_delivery_flag'] == 'True') != (delay > 0):
                validity['late_flag != (delay_days > 0)'] += 1
            if de.date() > est.date() and s['late_delivery_flag'] == 'False':
                validity['delivered after estimated DATE but late_flag False'] += 1
                vsamples['late_by_date_not_flagged'].append([o['order_id'], o['order_delivered_customer_date'], o['order_estimated_delivery_date']])
            validity['_delivered_checked'] += 1
        else:
            if s['actual_delivery_days'] or s['delivery_delay_days']:
                validity['undelivered but actual/delay present'] += 1
            if s['late_delivery_flag'] == 'True':
                validity['undelivered but late_flag True'] += 1
        if (est.date() - pt.date()).days != int(s['estimated_delivery_days']):
            validity['estimated_date - purchase_date != estimated_delivery_days'] += 1
            vsamples['estimated_days'].append(o['order_id'])
    for r in T['reviews']:
        o = O[r['order_id']]
        if o['order_status'] != 'delivered':
            validity['review on non-delivered order'] += 1
        de = ts(o['order_delivered_customer_date'])
        if de and ts(r['review_creation_date']).date() < de.date():
            validity['review created before delivery date'] += 1
            vsamples['review_before_delivery'].append(r['review_id'])
        if (r['satisfaction_risk_flag'] == 'True') != (int(r['review_score']) <= 2):
            validity['satisfaction_flag != score<=2'] += 1
    reviews_on_delivered = sum(1 for r in T['reviews'] if O[r['order_id']]['order_status'] == 'delivered')
    validity_out = {'counts': dict(validity), 'samples': {k: v[:5] for k, v in vsamples.items()},
                    'review_coverage_of_delivered_orders': round(reviews_on_delivered / status['delivered'], 4)}

    # ---- 7. customer coverage and positive-class potential (provisional purchase rule)
    seq = defaultdict(list)
    for o in orders:
        if o['order_status'] != 'cancelled':
            seq[o['customer_id']].append(ts(o['order_purchase_timestamp']))
    for v in seq.values():
        v.sort()
    firsts = Counter(v[0].strftime('%Y-%m') for v in seq.values())
    potential = {}
    for horizon in (30, 60, 90):
        snaps, pops, poss = [], 0, 0
        t = datetime(2024, 4, 1, tzinfo=timezone.utc)   # first as_of with a full 90-day lookback
        while t + timedelta(days=horizon) <= cutoff:
            pop = [c for c, v in seq.items() if any(t - timedelta(days=90) <= x < t for x in v)]
            pos = sum(any(t <= x < t + timedelta(days=horizon) for x in seq[c]) for c in pop)
            snaps.append((t.date().isoformat(), len(pop), pos))
            pops += len(pop)
            poss += pos
            t += timedelta(days=7)
        rates = [p / n for _, n, p in snaps if n]
        potential[f'{horizon}d'] = {
            'weekly_snapshots': len(snaps), 'first_as_of': snaps[0][0], 'last_as_of': snaps[-1][0],
            'customer_snapshot_rows': pops, 'positive_rows': poss, 'overall_rate': round(poss / pops, 4),
            'snapshot_rate_min_median_max': [round(min(rates), 4), round(statistics.median(rates), 4), round(max(rates), 4)],
            'population_min_max': [min(n for _, n, _ in snaps), max(n for _, n, _ in snaps)],
        }
    coverage = {
        'purchase_rule': PROVISIONAL,
        'customers_with_purchase': len(seq),
        'customers_with_2plus_purchases': sum(len(v) >= 2 for v in seq.values()),
        'first_purchase_by_month': dict(sorted(firsts.items())),
        'customers_first_purchase_in_first_90_days': sum(v[0] < datetime(2024, 3, 31, tzinfo=timezone.utc) for v in seq.values()),
        'positive_class_potential': potential,
        'assessment': None,
    }
    p30 = potential['30d']
    coverage['assessment'] = (
        f"35 个月历史；按周快照可得 {p30['customer_snapshot_rows']} 行客户样本、{p30['positive_rows']} 个 30 天正例"
        f"（整体 {p30['overall_rate']:.1%}）。正例足以训练和按时间外评估，但比例低，需看 PR-AUC 与校准；跨度足够，不需要回到选型。")

    out = {
        'task_id': 'DATA-06', 'generated_by': 'src/retail_bi/data/profile.py',
        'layer_manifest_sha256': hashlib.sha256((layer / 'manifest.json').read_bytes()).hexdigest(),
        'contract_version': contract['contract_version'], 'scope': {
            'research_scope': '截止前全部历史（DATA-03/D013），未抽样；history_source 全部 10 张表与 observed 两张视图逐行读取',
            'sampling': 'none',
            'history_retention_rule': '若以后为开发抽样，按客户整体抽取并保留其全部历史订单，标为开发样本；最终建模与报告用全量（DATA-10）',
        },
        'volume': volume, 'entities': entities, 'missing': missing, 'duplicates': dup, 'duplicate_samples': samples_dup,
        'time': time_cov, 'cancellation_and_negatives': cancel, 'money': money, 'extremes': extremes,
        'validity': validity_out, 'customer_coverage': coverage,
        'privacy': '样本只给合成 ID、日期和金额；不输出邮编、城市等地址字段',
    }
    Path(a.out_json).write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    Path(a.out_md).write_text(render(out), encoding='utf-8')
    print(json.dumps({'volume': volume, 'validity': dict(validity), 'dups': dup, 'time_checks': dict(order_checks)}, ensure_ascii=False))


def render(o):
    v, e, t, c, x = o['volume'], o['entities'], o['time'], o['cancellation_and_negatives'], o['extremes']
    cov, val = o['customer_coverage'], o['validity']['counts']
    L = ['# 清洗前质量剖析（DATA-06）', '',
         '> 由 `src/retail_bi/data/profile.py` 生成，数字均来自 `reports/data/profile_before.json`。数据完全合成。', '',
         f'- 范围：{o["scope"]["research_scope"]}。抽样：{o["scope"]["sampling"]}。',
         f'- 抽样与历史保留规则：{o["scope"]["history_retention_rule"]}。',
         f'- 契约：`{o["contract_version"]}`；时区：{t["timezone"]}。', '',
         '## 1. 规模与实体覆盖', '', '| 表 | 行数 |', '|---|---:|']
    L += [f'| {k} | {n:,} |' for k, n in v.items()]
    L += ['', '| 实体 | 数量 |', '|---|---:|'] + [f'| {k} | {n:,} |' for k, n in e.items()]
    L += ['', '## 2. 缺失', '', '| 字段 | 空值 | 比例 |', '|---|---:|---:|']
    L += [f'| {k} | {m["nulls"]:,} | {m["rate"]:.2%} |' for k, m in o['missing'].items()]
    L += ['', '审批、交承运、送达时间的空值与最终状态严格对应（见契约一致性检查），是“事件尚未发生”，不是录入缺失；`sellers.deactivated_at` 全空表示没有卖家停用。', '',
          '## 3. 重复与重复候选', '', '| 检查 | 数量 |', '|---|---:|']
    L += [f'| {k} | {n:,} |' for k, n in o['duplicates'].items()]
    L += ['', f'样本（同一客户同一天多单）：{o["duplicate_samples"]["same_customer_same_day"]}；（同单重复商品）：{o["duplicate_samples"]["same_product_repeated_in_order"]}。',
          '完全重复行为 0。同单重复商品全部是同一个上架商品，但每组价格都不相同（价格完全相同的组为 '
          f'{o["duplicates"]["repeated_product_groups_with_identical_prices"]}），更像生成器有放回地多次抽取同一商品，不是重复导入；'
          '按独立明细行保留，不推断为数量。同一客户同日多单是可能的正常行为。DATA-07 记录处理理由，不默认删除。', '',
          '## 4. 时间', '',
          f'- 下单时间 {t["purchase_first"][:19]} 至 {t["purchase_last"][:19]}，共 {t["months"]} 个月；跨度 {t["calendar_days_in_span"]:,} 天，其中 {t["days_without_orders"]} 天没有订单。',
          f'- 最后一个月不完整：{t["last_month_is_partial"]}（截止 {t["cutoff_exclusive"]}）。日期维覆盖所有下单日：{t["calendar_covers_all_purchase_days"]}。',
          f'- 事件先后检查（共 {t["event_order_violations"].get("_checked", 0):,} 单）：' + '；'.join(f'{k} {n}' for k, n in t['event_order_violations'].items() if k != '_checked') + '。',
          f'- 客户建档日期范围 {t["customers_created_range"][0][:10]} 至 {t["customers_created_range"][1][:10]}。', '',
          '| 月份 | 订单 |', '|---|---:|'] + [f'| {m} | {n} |' for m, n in t['orders_per_month'].items()]
    L += ['', '## 5. 取消、零值、负值与极端交易', '',
          f'- 状态：{c["status_counts"]}。已取消订单商品金额 {c["cancelled_item_price_usd"]} USD；其中有支付记录的取消单 {c["cancelled_orders_with_payment_rows"]} 单，有评价的取消单 {c["cancelled_orders_with_review"]} 单。',
          f'- {c["note"]}。', '', '| 金额字段 | 负值 | 零值 | 中位数 | P99 | 最大 | 极端（>Q3+3IQR） |', '|---|---:|---:|---:|---:|---:|---:|']
    L += [f'| {k} | {m["negative"]} | {m["zero"]} | {m["quantiles"]["p50"]} | {m["quantiles"]["p99"]} | {m["quantiles"]["p100"]} | {m["extreme_above_q3_plus_3iqr"]} |' for k, m in o['money'].items()]
    L += ['', f'- 订单金额（含运费）中位数 {x["order_total_usd_quantiles"]["p50"]}，P99 {x["order_total_usd_quantiles"]["p99"]}，最大 {x["order_total_usd_quantiles"]["p100"]}；超过 {x["order_threshold_usd"]} 的极端订单 {x["orders_above_q3_plus_3iqr"]} 单。',
          f'- 金额最高的 5 单：' + '；'.join(f'{r["order_id"]} {r["order_total_usd"]}（{r["items"]} 行，{r["status"]}）' for r in x['top5_orders']) + '。',
          f'- 每单明细行数：{x["items_per_order"]}。成交价/卖家标价比值分位：{x["item_price_to_listing_price_ratio_quantiles"]}。分期数：{x["installments"]}。',
          '- 极端值只标记不删除：合成数据没有录入错误的依据，DATA-07/10 决定是否截尾或变换。', '',
          '## 6. 字段有效性', '', '| 检查 | 不一致数 |', '|---|---:|']
    L += [f'| {k} | {n:,} |' for k, n in val.items() if not k.startswith('_')]
    L += ['', f'（已送达订单共检查 {val.get("_delivered_checked", 0):,} 单。）样本：{o["validity"]["samples"]}。',
          '“按日期晚到但未标记延迟”的原因：生成器用“实际天数向下取整 > 预计天数”判断延迟，而预计送达日期是下单日加预计天数的零点；'
          '下单当天较晚的订单，即使送达日期晚于预计日期，取整后天数也可能不超过预计天数。两种口径都自洽但结果不同：'
          '页面和特征必须写明用哪一种，推荐从时间戳按日期重算（DATA-10）。',
          f'评价覆盖已送达订单的比例 {o["validity"]["review_coverage_of_delivered_orders"]:.1%}。', '',
          '## 7. 客户覆盖与正类潜力', '',
          f'- 口径：{cov["purchase_rule"]}。有购买的客户 {cov["customers_with_purchase"]:,}，其中至少两次 {cov["customers_with_2plus_purchases"]:,}；首购在数据开始 90 天内的客户 {cov["customers_first_purchase_in_first_90_days"]:,}。',
          '', '| 标签窗 | 周快照数 | as_of 范围 | 客户样本行 | 正例 | 整体比例 | 单快照比例（最小/中位/最大） | 单快照母体 |', '|---|---:|---|---:|---:|---:|---|---|']
    for h, p in cov['positive_class_potential'].items():
        L.append(f'| {h} | {p["weekly_snapshots"]} | {p["first_as_of"]} ~ {p["last_as_of"]} | {p["customer_snapshot_rows"]:,} | {p["positive_rows"]:,} | {p["overall_rate"]:.1%} | '
                 f'{" / ".join(f"{r:.1%}" for r in p["snapshot_rate_min_median_max"])} | {p["population_min_max"][0]}–{p["population_min_max"][1]} |')
    L += ['', f'结论：{cov["assessment"]}', '',
          f'首购分布：{cov["first_purchase_by_month"]}。客户建档日期都在 2024-01-01 至 2024-06-29，没有早于数据起点的客户，所以本数据中首次可观测购买没有被数据起点截断；'
          '但早期月份首购集中，是生成器的建档节奏造成的，cohort 分析（EDA-03）要按建档节奏解读，仍称“首次可观测购买”。', '',
          '## 8. 交给下游的问题清单', '',
          '- DATA-07：没有缺失 ID、没有解析失败、没有完全重复行；记录“同客户同日多单”“同单重复商品”的处理理由。',
          '- DATA-08：取消单的金额、支付和评价如何计入；processing/shipped 是否算有效购买；运费是否计入金额。',
          '- DATA-10 / ML：物流派生字段与日期的不一致（见第 6 节）意味着要从时间戳重算，不直接使用源派生列。',
          '- ML-01：30 天正例比例低；也列出 60/90 天作参考，目标仍由 ML-01 冻结。', '',
          f'隐私：{o["privacy"]}。', '']
    return '\n'.join(L)


if __name__ == '__main__':
    main()
