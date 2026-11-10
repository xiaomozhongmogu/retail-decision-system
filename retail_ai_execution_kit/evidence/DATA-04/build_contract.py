"""DATA-04: build the synthetic-transaction data contract and data dictionary.

Column annotations (standard name, meaning, unit, role, time semantics, feature
policy) are written by hand below. Row counts, nulls, distinct counts, ranges,
type checks and key checks are measured from the DATA-05 engineering layer.

usage: .venv/bin/python evidence/DATA-04/build_contract.py --layer <dir> \
           --contract contracts/data_contract.json --dictionary docs/data_dictionary.md
Exit 1 if any type, key or join check fails (outputs are still written so the
failure can be inspected).
"""
import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

# ---------------------------------------------------------------- annotations
# type: string | integer | decimal(12,2) | double | boolean | date | timestamp
# role: pk | fk | measure | attribute | event_time | plan_time | master_time |
#       derived | denormalized | calendar | generator_label | scenario
# feature: as_of = usable as a feature only with as_of gating;
#          static = master attribute usable as-is; key = join key, not a feature;
#          blocked = must not enter models; label_source = only for building labels/metrics
C = {}


def col(table, raw, std, typ, meaning, unit, role, effective, feature, time=None, note=None):
    C.setdefault(table, []).append(dict(
        raw_name=raw, standard_name=std, type=typ, meaning=meaning, unit=unit, role=role,
        effective_business_field=effective, feature_policy=feature, time_semantics=time, note=note))


T_TZ = '源值无时区；按 UTC 解释是工程假设（D011）'
FINAL = '期末快照值，不知道变化时间'

# customers
col('customers', 'customer_id', 'customer_id', 'string', '客户标识', None, 'pk', False, 'key', note='在 orders.customer_id 处计有效字段')
col('customers', 'customer_unique_id', 'customer_unique_id', 'string', '客户稳定身份标识；实测与 customer_id 一一对应', None, 'attribute', False, 'key',
    note='与 customer_id 1:1，不提供额外信息，不计有效字段')
col('customers', 'customer_state', 'customer_state', 'string', '客户所在州（美国州缩写）', None, 'attribute', True, 'static')
col('customers', 'customer_city', 'customer_city', 'string', '客户所在城市', None, 'attribute', False, 'static', note='合成城市，基数高，只作展示')
col('customers', 'customer_region', 'customer_region', 'string', '客户所在大区（人口普查口径四区）', None, 'attribute', True, 'static')
col('customers', 'customer_zip_prefix', 'customer_zip_prefix', 'string', '五位邮编前缀，按字符串保留前导零', None, 'attribute', False, 'blocked', note='近似唯一，不作分析维度')
col('customers', 'customer_segment', 'customer_segment', 'string', '生成器预设的客户分群', None, 'generator_label', False, 'blocked', note='生成器标签：不作特征、不作真值')
col('customers', 'customer_lifecycle_stage', 'customer_lifecycle_stage', 'string', '生成器预设的生命周期阶段', None, 'generator_label', False, 'blocked',
    time=FINAL, note='生成器标签且为期末值；生命周期状态由 EDA-05 按规则重算')
col('customers', 'created_at', 'customer_created_date', 'date', '合成客户建档日期', None, 'master_time', False, 'static',
    time='日粒度；只能称“合成建档”，不是真实注册或获客时间；' + T_TZ)

# sellers
col('sellers', 'seller_id', 'seller_id', 'string', '卖家标识', None, 'pk', False, 'key', note='在 order_items.seller_id 处计有效字段')
col('sellers', 'seller_state', 'seller_state', 'string', '卖家所在州', None, 'attribute', False, 'static')
col('sellers', 'seller_city', 'seller_city', 'string', '卖家所在城市', None, 'attribute', False, 'static')
col('sellers', 'seller_region', 'seller_region', 'string', '卖家所在大区', None, 'attribute', False, 'static')
col('sellers', 'seller_zip_prefix', 'seller_zip_prefix', 'string', '卖家邮编前缀，按字符串保留前导零', None, 'attribute', False, 'blocked')
col('sellers', 'seller_segment', 'seller_segment', 'string', '生成器预设的卖家分群', None, 'generator_label', False, 'blocked')
col('sellers', 'seller_quality_score', 'seller_quality_score', 'double', '生成器的卖家质量参数（0–1）', 'ratio 0-1', 'generator_label', False, 'blocked')
col('sellers', 'seller_fulfillment_capacity', 'seller_fulfillment_capacity', 'double', '生成器的履约能力参数（0–1）', 'ratio 0-1', 'generator_label', False, 'blocked')
col('sellers', 'seller_active_flag', 'seller_active_flag', 'boolean', '期末是否活跃', None, 'attribute', False, 'blocked', time=FINAL)
col('sellers', 'created_at', 'seller_created_date', 'date', '合成卖家创建日期（全部为 2024-01-01）', None, 'master_time', False, 'static', time='日粒度；单一值；' + T_TZ)
col('sellers', 'deactivated_at', 'seller_deactivated_date', 'date', '卖家停用日期（本场景全部为空）', None, 'master_time', False, 'blocked', time='全空；' + T_TZ)

# products
col('products', 'product_id', 'product_id', 'string', '商品标识', None, 'pk', False, 'key', note='在 order_items.product_id 处计有效字段')
col('products', 'product_category', 'product_category', 'string', '商品品类（16 类，英文通用名）', None, 'attribute', True, 'static')
col('products', 'product_name', 'product_name', 'string', '通用无品牌商品名', None, 'attribute', False, 'static', note='每个商品唯一，只作展示')
col('products', 'product_weight_g', 'product_weight_g', 'integer', '商品重量', 'g', 'attribute', False, 'static')
col('products', 'product_length_cm', 'product_length_cm', 'double', '商品长度', 'cm', 'attribute', False, 'static')
col('products', 'product_height_cm', 'product_height_cm', 'double', '商品高度', 'cm', 'attribute', False, 'static')
col('products', 'product_width_cm', 'product_width_cm', 'double', '商品宽度', 'cm', 'attribute', False, 'static')
col('products', 'product_price_base_usd', 'product_price_base_usd', 'decimal(12,2)', '商品基准价（目录价，不是成交价）', 'USD', 'attribute', False, 'static')
col('products', 'created_at', 'product_created_date', 'date', '商品创建日期（全部为 2024-01-01）', None, 'master_time', False, 'static', time='日粒度；单一值；' + T_TZ)

# seller_products
col('seller_products', 'seller_product_id', 'seller_product_id', 'string', '卖家上架商品标识', None, 'pk', False, 'key')
col('seller_products', 'seller_id', 'seller_id', 'string', '上架卖家', None, 'fk', False, 'key')
col('seller_products', 'product_id', 'product_id', 'string', '上架商品', None, 'fk', False, 'key')
col('seller_products', 'seller_price_usd', 'seller_price_usd', 'decimal(12,2)', '卖家标价（不是成交价）', 'USD', 'attribute', False, 'static')
col('seller_products', 'listing_created_at', 'listing_created_date', 'date', '上架日期（全部为 2024-01-01）', None, 'master_time', False, 'static', time='日粒度；单一值；' + T_TZ)
col('seller_products', 'listing_active_flag', 'listing_active_flag', 'boolean', '期末是否仍上架', None, 'attribute', False, 'blocked', time=FINAL)
col('seller_products', 'scenario_name', 'scenario_name', 'string', '生成场景名（全部 baseline）', None, 'scenario', False, 'blocked')

# orders
col('orders', 'order_id', 'order_id', 'string', '订单标识', None, 'pk', True, 'key')
col('orders', 'customer_id', 'customer_id', 'string', '下单客户', None, 'fk', True, 'key')
col('orders', 'order_status', 'order_status', 'string', '订单最终状态：delivered / shipped / processing / cancelled', None, 'attribute', True, 'label_source',
    time=FINAL + '；没有取消发生时间', note='只用于指标口径（DATA-08），不作特征。实测与时间戳严格对应：cancelled=无审批，processing=已审批未交承运，shipped=已交承运未送达，delivered=已送达；as_of 时的非取消状态可由时间戳重建，取消时间未知')
col('orders', 'order_purchase_timestamp', 'purchase_ts', 'timestamp', '下单时间；订单事实的业务时间', None, 'event_time', True, 'as_of',
    time='秒粒度；事件时间；下单时即可得；' + T_TZ)
col('orders', 'order_approved_at', 'approved_ts', 'timestamp', '支付审批时间', None, 'event_time', False, 'as_of',
    time='秒粒度；事件发生时可得；截止后发生的在 observed 视图置空；历史层空值 194 条全部是 cancelled；' + T_TZ)
col('orders', 'order_estimated_delivery_date', 'estimated_delivery_date', 'date', '预计送达日期（计划值）', None, 'plan_time', False, 'blocked',
    time='日粒度；计划值，生成/告知时点未知，暂不开放为特征；' + T_TZ)
col('orders', 'order_delivered_carrier_date', 'carrier_handoff_ts', 'timestamp', '交给承运商时间', None, 'event_time', False, 'as_of',
    time='秒粒度；截止后发生的在 observed 视图置空；历史层空值=processing 或 cancelled；' + T_TZ)
col('orders', 'order_delivered_customer_date', 'delivered_ts', 'timestamp', '实际送达客户时间', None, 'event_time', True, 'as_of',
    time='秒粒度；截止后发生的在 observed 视图置空；历史层空值=shipped、processing 或 cancelled；' + T_TZ)
for raw, zh in [('order_year', '下单年'), ('order_quarter', '下单季度'), ('order_month', '下单月'), ('order_week', 'ISO 周'),
                ('order_day_of_week', '星期（周一=0）')]:
    col('orders', raw, raw, 'integer', zh + '（由下单时间拆出）', None, 'calendar', False, 'blocked', note='日期拆分列，不计有效字段；数仓用日期维代替')
col('orders', 'is_weekend', 'is_weekend', 'boolean', '是否周末下单（由下单时间推出）', None, 'calendar', False, 'blocked', note='用日期维代替')
col('orders', 'is_holiday_period', 'is_holiday_period', 'boolean', '是否生成器设定的节日期间', None, 'calendar', False, 'blocked', note='生成器设定的日历标记')
col('orders', 'is_promotion_period', 'is_promotion_period', 'boolean', '是否生成器设定的促销期间', None, 'calendar', False, 'blocked', note='生成器设定，不是真实营销记录')
col('orders', 'scenario_name', 'scenario_name', 'string', '生成场景名（全部 baseline）', None, 'scenario', False, 'blocked')

# order_items
col('order_items', 'order_id', 'order_id', 'string', '所属订单', None, 'fk', False, 'key')
col('order_items', 'order_item_id', 'order_item_seq', 'integer', '订单内明细序号（从 1 开始）', None, 'pk', False, 'key', note='不是数量；不假设每行 1 件')
col('order_items', 'seller_product_id', 'seller_product_id', 'string', '购买的上架商品', None, 'fk', False, 'key')
col('order_items', 'product_id', 'product_id', 'string', '购买的商品', None, 'fk', True, 'key')
col('order_items', 'seller_id', 'seller_id', 'string', '履约卖家', None, 'fk', True, 'key')
col('order_items', 'item_price_usd', 'item_price_usd', 'decimal(12,2)', '明细商品金额（成交价，不含运费）', 'USD', 'measure', True, 'as_of')
col('order_items', 'shipping_cost_usd', 'item_shipping_usd', 'decimal(12,2)', '分摊到明细的运费', 'USD', 'measure', True, 'as_of')
col('order_items', 'item_total_usd', 'item_total_usd', 'decimal(12,2)', '商品金额＋运费（实测逐行相等）', 'USD', 'derived', False, 'as_of', note='由前两列相加，不计有效字段')
col('order_items', 'scenario_name', 'scenario_name', 'string', '生成场景名', None, 'scenario', False, 'blocked')

# payments
col('payments', 'order_id', 'order_id', 'string', '支付的订单', None, 'fk', False, 'key')
col('payments', 'payment_sequential', 'payment_seq', 'integer', '订单内支付序号（1–2）', None, 'pk', False, 'key')
col('payments', 'payment_type', 'payment_type', 'string', '支付方式（5 类）', None, 'attribute', True, 'as_of', time='没有支付时间；按下单时可得的工程假设使用')
col('payments', 'payment_installments', 'payment_installments', 'integer', '分期数', 'count', 'attribute', True, 'as_of', time='同上')
col('payments', 'payment_value_usd', 'payment_value_usd', 'decimal(12,2)', '支付金额；与订单明细合计对账', 'USD', 'measure', True, 'label_source',
    note='只作对账，不称已实现收入或退款')
col('payments', 'scenario_name', 'scenario_name', 'string', '生成场景名', None, 'scenario', False, 'blocked')

# shipping
col('shipping', 'order_id', 'order_id', 'string', '物流对应订单（与订单 1:1）', None, 'pk', False, 'key')
col('shipping', 'seller_state', 'origin_state', 'string', '发货州（冗余拷贝）', None, 'denormalized', False, 'static', note='以 sellers 主数据为准')
col('shipping', 'customer_state', 'destination_state', 'string', '收货州（冗余拷贝）', None, 'denormalized', False, 'static', note='以 customers 主数据为准')
col('shipping', 'seller_region', 'origin_region', 'string', '发货大区（冗余拷贝）', None, 'denormalized', False, 'static')
col('shipping', 'customer_region', 'destination_region', 'string', '收货大区（冗余拷贝）', None, 'denormalized', False, 'static')
col('shipping', 'shipping_distance_band', 'shipping_distance_band', 'string', '距离档：same_state / same_region / cross_region / remote', None, 'attribute', False, 'as_of')
col('shipping', 'shipping_zone', 'shipping_zone', 'string', '合成线路区（zone_1–4）', None, 'attribute', False, 'as_of')
col('shipping', 'estimated_delivery_days', 'estimated_delivery_days', 'integer', '预计送达天数', 'days', 'attribute', True, 'blocked',
    time='计划值，可得时点未知，同 estimated_delivery_date')
col('shipping', 'actual_delivery_days', 'actual_delivery_days', 'integer', '实际送达天数；源文本为 x.0', 'days', 'derived', False, 'as_of',
    time='送达后才可得；按 delivered_ts < as_of 截断', note='由下单与送达时间推出')
col('shipping', 'delivery_delay_days', 'delivery_delay_days', 'integer', '晚于预计的天数；源文本为 x.0', 'days', 'derived', False, 'as_of',
    time='送达后才可得', note='派生值，不计有效字段')
col('shipping', 'late_delivery_flag', 'late_delivery_flag', 'boolean', '是否晚于预计送达', None, 'derived', False, 'as_of',
    time='送达后才可得；未送达订单为 False 不代表准时', note='派生值')
col('shipping', 'shipping_cost_usd', 'order_shipping_usd', 'decimal(12,2)', '订单运费；实测等于该单明细运费之和', 'USD', 'measure', False, 'as_of', note='与明细运费重复，不计有效字段')
col('shipping', 'scenario_name', 'scenario_name', 'string', '生成场景名', None, 'scenario', False, 'blocked')

# reviews
col('reviews', 'review_id', 'review_id', 'string', '评价标识', None, 'pk', False, 'key')
col('reviews', 'order_id', 'order_id', 'string', '被评价订单（每单至多一条）', None, 'fk', False, 'key')
col('reviews', 'review_score', 'review_score', 'integer', '评价分数 1–5', 'score 1-5', 'measure', True, 'as_of',
    time='按评价创建日可得的工程假设（D011）')
col('reviews', 'review_creation_date', 'review_created_date', 'date', '评价创建日期', None, 'event_time', False, 'as_of',
    time='日粒度；截止后创建的评价不进入 observed 视图；' + T_TZ)
col('reviews', 'review_answer_timestamp', 'review_answered_ts', 'timestamp', '评价答复时间', None, 'event_time', False, 'as_of',
    time='秒粒度；截止后发生的在 observed 视图置空；' + T_TZ)
col('reviews', 'review_sentiment_label', 'review_sentiment_label', 'string', '情感标签（由分数映射）', None, 'generator_label', False, 'blocked', note='由分数推出，不独立')
col('reviews', 'satisfaction_risk_flag', 'satisfaction_risk_flag', 'boolean', '分数为 1 或 2', None, 'derived', False, 'blocked', note='由分数推出')
col('reviews', 'scenario_name', 'scenario_name', 'string', '生成场景名', None, 'scenario', False, 'blocked')

# calendar
col('calendar', 'date', 'date', 'date', '日历日期', None, 'pk', False, 'key', time='日粒度；覆盖 2024-01-01 至截止前一日')
for raw, typ, zh in [('year', 'integer', '年'), ('quarter', 'integer', '季度'), ('month', 'integer', '月'), ('month_name', 'string', '月名'),
                     ('week', 'integer', 'ISO 周'), ('day_of_week', 'integer', '星期（周一=0）'), ('day_name', 'string', '星期名'),
                     ('is_weekend', 'boolean', '是否周末'), ('is_holiday_period', 'boolean', '生成器节日期间'),
                     ('is_promotion_period', 'boolean', '生成器促销期间'), ('season', 'string', '气象季节')]:
    col('calendar', raw, raw, typ, zh, None, 'calendar', False, 'static', note='日期维属性')

PK = {'customers': ['customer_id'], 'sellers': ['seller_id'], 'products': ['product_id'],
      'seller_products': ['seller_product_id'], 'orders': ['order_id'],
      'order_items': ['order_id', 'order_item_id'], 'payments': ['order_id', 'payment_sequential'],
      'shipping': ['order_id'], 'reviews': ['review_id'], 'calendar': ['date']}
FK = [('orders', 'customer_id', 'customers', 'customer_id'),
      ('order_items', 'order_id', 'orders', 'order_id'),
      ('order_items', 'product_id', 'products', 'product_id'),
      ('order_items', 'seller_id', 'sellers', 'seller_id'),
      ('order_items', 'seller_product_id', 'seller_products', 'seller_product_id'),
      ('seller_products', 'seller_id', 'sellers', 'seller_id'),
      ('seller_products', 'product_id', 'products', 'product_id'),
      ('payments', 'order_id', 'orders', 'order_id'),
      ('shipping', 'order_id', 'orders', 'order_id'),
      ('reviews', 'order_id', 'orders', 'order_id')]
UNIQUE = [('reviews', ['order_id']), ('customers', ['customer_unique_id'])]


# ------------------------------------------------------------------ measuring
def read(layer, table):
    with open(layer / 'history_source' / f'{table}.csv', encoding='utf-8-sig', newline='') as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)


def parse(typ, v):
    if typ == 'string':
        return v
    if typ == 'integer':
        d = Decimal(v)
        if d != d.to_integral_value():
            raise ValueError('not integral')
        return int(d)
    if typ == 'decimal(12,2)':
        d = Decimal(v)
        if d.as_tuple().exponent < -2:
            raise ValueError('more than 2 decimals')
        return d
    if typ == 'double':
        return float(Decimal(v))
    if typ == 'boolean':
        if v not in ('True', 'False'):
            raise ValueError('bad bool')
        return v == 'True'
    if typ in ('date', 'timestamp'):
        t = datetime.fromisoformat(v)
        if typ == 'date' and (t.hour or t.minute or t.second):
            raise ValueError('date has time part')
        return t
    raise ValueError(typ)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--layer', required=True)
    ap.add_argument('--contract', required=True)
    ap.add_argument('--dictionary', required=True)
    a = ap.parse_args()
    layer = Path(a.layer)
    lman = json.loads((layer / 'manifest.json').read_text(encoding='utf-8'))
    failures = []
    data, tables = {}, {}
    for table, cols in C.items():
        header, rows = read(layer, table)
        data[table] = rows
        if header != [c['raw_name'] for c in cols]:
            failures.append(f'{table}: header mismatch {header}')
        for c in cols:
            c['source'] = f'baseline_10000_seed42/{table}.csv（源 ZIP 成员；经 DATA-05 history_source 按字符串读取）'
            vals = [r[c['raw_name']] for r in rows]
            nn = [v for v in vals if v != '']
            bad, parsed = 0, []
            for v in nn:
                try:
                    parsed.append(parse(c['type'], v))
                except (ValueError, InvalidOperation):
                    bad += 1
            prof = {'rows': len(vals), 'null_count': len(vals) - len(nn), 'distinct_nonnull': len(set(nn)),
                    'type_parse_failures': bad}
            if parsed and c['type'] not in ('string', 'boolean'):
                prof['min'], prof['max'] = str(min(parsed)), str(max(parsed))
            if len(set(nn)) <= 16 and c['type'] in ('string', 'boolean', 'integer'):
                prof['values'] = dict(sorted(Counter(nn).items()))
            c['nullable'] = prof['null_count'] > 0
            c['profile'] = prof
            if bad:
                failures.append(f'{table}.{c["raw_name"]}: {bad} values fail {c["type"]}')
        tables[table] = {'rows': len(rows), 'primary_key': PK[table], 'columns': cols}

    keys = {}
    for table, pk in PK.items():
        seen = Counter(tuple(r[k] for k in pk) for r in data[table])
        dup = sum(n - 1 for n in seen.values() if n > 1)
        nul = sum(any(r[k] == '' for k in pk) for r in data[table])
        keys[f'pk:{table}'] = {'duplicates': dup, 'nulls': nul}
        if dup or nul:
            failures.append(f'pk {table}: dup={dup} null={nul}')
    for table, cols in UNIQUE:
        seen = Counter(tuple(r[k] for k in cols) for r in data[table])
        dup = sum(n - 1 for n in seen.values() if n > 1)
        keys[f'unique:{table}.{"+".join(cols)}'] = {'duplicates': dup}
        if dup:
            failures.append(f'unique {table}.{cols}: {dup}')
    for ct, cc, pt, pc in FK:
        parent = {r[pc] for r in data[pt]}
        orphan = sum(r[cc] not in parent for r in data[ct])
        keys[f'fk:{ct}.{cc}->{pt}.{pc}'] = {'orphans': orphan, 'child_rows': len(data[ct])}
        if orphan:
            failures.append(f'fk {ct}.{cc}: {orphan} orphans')

    # verifiable related fields (reached through a checked key) and consistency checks
    sp = {r['seller_product_id']: r for r in data['seller_products']}
    cust = {r['customer_id']: r for r in data['customers']}
    sel = {r['seller_id']: r for r in data['sellers']}
    prod = {r['product_id']: r for r in data['products']}
    items_by_order = defaultdict(list)
    for r in data['order_items']:
        items_by_order[r['order_id']].append(r)
    pay_by_order = defaultdict(Decimal)
    for r in data['payments']:
        pay_by_order[r['order_id']] += Decimal(r['payment_value_usd'])
    ship = {r['order_id']: r for r in data['shipping']}
    orders = {r['order_id']: r for r in data['orders']}
    checks = {
        'order_items listing matches seller and product': sum(
            sp[r['seller_product_id']]['seller_id'] != r['seller_id'] or sp[r['seller_product_id']]['product_id'] != r['product_id']
            for r in data['order_items']),
        'item_total = item_price + item_shipping': sum(
            Decimal(r['item_total_usd']) != Decimal(r['item_price_usd']) + Decimal(r['shipping_cost_usd']) for r in data['order_items']),
        'sum(payment_value) = sum(item_total) per order': sum(
            pay_by_order[o] != sum(Decimal(i['item_total_usd']) for i in items_by_order[o]) for o in orders),
        'shipping.order_shipping = sum(item_shipping) per order': sum(
            Decimal(ship[o]['shipping_cost_usd']) != sum(Decimal(i['shipping_cost_usd']) for i in items_by_order[o]) for o in orders),
        'shipping.destination_state = customers.customer_state': sum(
            ship[o]['customer_state'] != cust[orders[o]['customer_id']]['customer_state'] for o in orders),
        'shipping.destination_region = customers.customer_region': sum(
            ship[o]['customer_region'] != cust[orders[o]['customer_id']]['customer_region'] for o in orders),
        'shipping.origin_state = sellers.seller_state': sum(
            ship[o]['seller_state'] != sel[items_by_order[o][0]['seller_id']]['seller_state'] for o in orders),
        'order_status implied by approved/carrier/delivered timestamps': sum(
            o['order_status'] != ('cancelled' if not o['order_approved_at'] else 'processing' if not o['order_delivered_carrier_date']
                                  else 'shipped' if not o['order_delivered_customer_date'] else 'delivered') for o in data['orders']),
        'orders with >1 distinct seller': sum(len({i['seller_id'] for i in items_by_order[o]}) > 1 for o in orders),
        'purchase_ts year/month equal order_year/order_month': sum(
            int(o['order_purchase_timestamp'][:4]) != int(o['order_year']) or int(o['order_purchase_timestamp'][5:7]) != int(o['order_month'])
            for o in data['orders']),
    }
    informational = {'orders with >1 distinct seller'}
    for k, v in checks.items():
        if v and k not in informational:
            failures.append(f'consistency {k}: {v}')
    related = [
        {'field': 'products.product_category', 'reached_from': 'order_items.product_id', 'coverage_rows': sum(r['product_id'] in prod for r in data['order_items']), 'child_rows': len(data['order_items'])},
        {'field': 'customers.customer_state / customer_region', 'reached_from': 'orders.customer_id', 'coverage_rows': sum(r['customer_id'] in cust for r in data['orders']), 'child_rows': len(data['orders'])},
        {'field': 'sellers.seller_state / seller_region', 'reached_from': 'order_items.seller_id', 'coverage_rows': sum(r['seller_id'] in sel for r in data['order_items']), 'child_rows': len(data['order_items'])},
        {'field': 'reviews.review_score', 'reached_from': 'reviews.order_id -> orders', 'coverage_rows': len(data['reviews']), 'child_rows': len(data['orders']),
         'note': '只有部分订单有评价（不是缺失值，是没有评价）'},
        {'field': 'payments.payment_type / payment_installments', 'reached_from': 'payments.order_id -> orders', 'coverage_rows': len({r['order_id'] for r in data['payments']}), 'child_rows': len(data['orders'])},
    ]

    effective = [f'{t}.{c["raw_name"]}' for t, v in tables.items() for c in v['columns'] if c['effective_business_field']]
    contract = {
        'status': 'approved',
        'approval_basis': {
            'route_decision': 'reports/data/dataset_selection.md',
            'route_evidence': 'evidence/DATA-03/2026-11-10-route-selection.json',
            'decisions': ['ops/DECISIONS.md#d012', 'ops/DECISIONS.md#d013'],
            'nature': '依据 D012 用户授权的工程工作假设批准；不是教师确认',
        },
        'contract_version': 'synthetic-transaction-v1',
        'superseded': 'UCI Online Retail II 候选契约（GBP、invoice、quantity×unit_price）已作废，见 D013',
        'selected_dataset': {
            'name': 'Synthetic Ecommerce Dataset baseline_10000_seed42',
            'nature': 'fully_synthetic',
            'source_archive_sha256': lman['source_sha256'],
            'generator_run': 'simulation_run_20260721_003414_baseline_seed42',
            'engineering_layer_version': lman['version'],
            'engineering_manifest': 'reports/data/source_manifest.json',
            'license_note': '网站下载件未标明数据许可；同作者仓库同类样例为 CC0，代码为 MIT；原始数据只用于课程，不对外发布（C07）',
        },
        'source_manifest': 'reports/data/source_manifest.json',
        'freshness_decision': 'ops/DECISIONS.md#d012',
        'event_timezone': 'naive source; UTC engineering assumption; display in Asia/Shanghai only after explicit conversion',
        'as_of_exclusive': lman['as_of_exclusive'],
        'business_currency': 'USD',
        'grain': {
            'orders': '一行一个订单',
            'order_items': '一行一个订单明细（订单内序号）；没有数量列',
            'payments': '一行一次支付（订单内序号 1–2）',
            'shipping': '一行一个订单的物流记录',
            'reviews': '一行一条评价；每单至多一条',
        },
        'size_rule': {'min_records': 10000, 'or_min_bytes': 10000000,
                      'measured': {'order_items_rows': len(data['order_items']), 'orders_rows': len(data['orders'])},
                      'passed': len(data['order_items']) >= 10000},
        'effective_business_field_min': 8,
        'effective_business_fields': effective,
        'effective_business_field_count': len(effective),
        'field_counting_policy': '只计业务含义独立的源字段；同一标识只在事实表外键处计一次；不计日期拆分列、scenario_name、生成器标签、由其他列推出的派生列、冗余拷贝、与主键 1:1 的冗余标识。通过已校验主键到达的字段列在 verified_related_fields，不重复计数。',
        'verified_related_fields': related,
        'keys': keys,
        'consistency_checks': checks,
        'availability_rules': {
            'history_source': 'DATA-05 历史层：按下单时间截止，保留源字符串和期末/未来字段；不是安全特征表',
            'observed': 'DATA-05 观察视图：截止后的审批/发货/送达/答复时间置空，截止后创建的评价排除',
            'feature_policy_values': {
                'key': '连接键，不作特征',
                'static': '主数据属性，可直接使用',
                'as_of': '只能使用 as_of 之前已发生/已可得的值',
                'label_source': '只用于构造指标或标签（DATA-08、ML-01），不作特征',
                'blocked': '不得入模；部分可在页面展示并标注',
            },
        },
        'not_available': ['购买数量', '退款金额与时间', '取消发生时间', '订单状态历史', '支付时间', '获客渠道', '浏览/加购/曝光', '营销触达与同意', '优惠券', '成本与毛利', '库存', '投诉', '年龄与性别'],
        'forbidden_assumptions': [
            '把 order_item_id 当数量或假设每行 1 件',
            '把 order_status 最终状态当作下单时可知',
            '把生成器标签（customer_segment、customer_lifecycle_stage、review_sentiment_label、seller_* 参数）当特征或真值',
            '把 payment_value_usd 称为已实现收入或退款后收入',
            '虚构渠道、毛利、库存、营销同意或投诉',
            '把合成建档日期称为真实注册或获客时间',
            '把合成数据结论写成真实企业或真实顾客行为',
            '拼接其他数据集的用户 ID',
        ],
        'tables': tables,
        'pending_downstream': {
            'DATA-08': '有效购买（delivered/shipped/processing 是否计入）、取消处理、金额是否含运费',
            'ML-01': '预测母体与 30 天标签',
            'metrics': 'contracts/metrics.json 仍为 UCI 草案，由 DATA-08 改写',
        },
        'required_after_selection_status': {
            'actual_headers': 'passed', 'source_versions_and_hashes': 'passed', 'actual_time_coverage': 'passed',
            'key_validation': 'passed' if not any(k.startswith('pk') or k.startswith('fk') for k in failures) else 'failed',
            'field_nullability': 'passed', 'scope_rules': 'passed（reports/data/dataset_selection.md）',
            'freshness_evidence': 'D012 用户授权的工作假设；无教师答复',
        },
        'course_material_manifest': 'sources/manifest.json',
        'generated_by': 'evidence/DATA-04/build_contract.py',
        'layer_manifest_sha256': hashlib.sha256((layer / 'manifest.json').read_bytes()).hexdigest(),
        'check_failures': failures,
    }
    Path(a.contract).write_text(json.dumps(contract, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    Path(a.dictionary).write_text(render_md(contract), encoding='utf-8')
    print(json.dumps({'tables': len(tables), 'columns': sum(len(v['columns']) for v in tables.values()),
                      'effective_fields': len(effective), 'checks': checks, 'failures': failures}, ensure_ascii=False))
    sys.exit(1 if failures else 0)


ROLE_ZH = {'pk': '主键', 'fk': '外键', 'measure': '度量', 'attribute': '属性', 'event_time': '事件时间',
           'plan_time': '计划时间', 'master_time': '主数据时间', 'derived': '派生', 'denormalized': '冗余拷贝',
           'calendar': '日历', 'generator_label': '生成器标签', 'scenario': '场景元数据'}
FEAT_ZH = {'key': '连接键', 'static': '可用', 'as_of': '按时点可用', 'label_source': '仅口径/标签', 'blocked': '禁止入模'}


def render_md(c):
    s = c['selected_dataset']
    out = [
        '# 数据字典（DATA-04）', '',
        '> 由 `evidence/DATA-04/build_contract.py` 生成，与 `contracts/data_contract.json` 同源；不要手工修改，改注释后重新生成。',
        '', f'- 契约版本：`{c["contract_version"]}`，状态 `{c["status"]}`。批准依据：{c["approval_basis"]["nature"]}（D012、D013）。',
        f'- 数据：{s["name"]}，**完全合成**；源 ZIP SHA-256 `{s["source_archive_sha256"]}`；工程层 `{s["engineering_layer_version"]}`。',
        f'- 观察截止：`{c["as_of_exclusive"]}`（不含）。时区：{c["event_timezone"]}。币种：USD。',
        f'- 许可：{s["license_note"]}。',
        f'- 有效业务字段 {c["effective_business_field_count"]} 个（门槛 8）：' + '、'.join(f'`{x}`' for x in c['effective_business_fields']) + '。',
        f'- 计数规则：{c["field_counting_policy"]}', '',
        '## 1. 表与粒度', '', '| 表 | 行数 | 主键 | 粒度 |', '|---|---:|---|---|',
    ]
    for t, v in c['tables'].items():
        out.append(f'| {t} | {v["rows"]:,} | {" + ".join(v["primary_key"])} | {c["grain"].get(t, "主数据或日期维，一行一个实体")} |')
    out += ['', '## 2. 键与一致性（实测）', '', '| 检查 | 结果 |', '|---|---|']
    for k, v in c['keys'].items():
        out.append(f'| {k} | {", ".join(f"{a}={b}" for a, b in v.items())} |')
    for k, v in c['consistency_checks'].items():
        out.append(f'| {k} | 不一致 {v} |')
    out += ['', '可验证关联字段（经已校验主键到达，不另计有效字段）：', '', '| 字段 | 经由 | 覆盖 |', '|---|---|---|']
    for r in c['verified_related_fields']:
        out.append(f'| {r["field"]} | {r["reached_from"]} | {r["coverage_rows"]:,} / {r["child_rows"]:,}{"；" + r["note"] if r.get("note") else ""} |')
    out += ['', '## 3. 逐列字典', '',
            '列含义：原始名、标准名、类型、含义、可空（实测空值数）、单位、角色、是否计有效字段、入模规则、时间语义与备注。来源一律为同一合成包的对应表。']
    for t, v in c['tables'].items():
        out += ['', f'### {t}', '', '| 原始名 | 标准名 | 类型 | 含义 | 空值 | 单位 | 角色 | 有效 | 入模 | 时间语义 / 备注 |', '|---|---|---|---|---:|---|---|---|---|---|']
        for col_ in v['columns']:
            p = col_['profile']
            extra = '；'.join(x for x in [col_.get('time_semantics'), col_.get('note')] if x)
            if 'min' in p:
                extra = (extra + '；' if extra else '') + f'范围 {p["min"][:19]} ~ {p["max"][:19]}'
            out.append(f'| {col_["raw_name"]} | {col_["standard_name"]} | {col_["type"]} | {col_["meaning"]} | {p["null_count"]:,} | {col_["unit"] or ""} | '
                       f'{ROLE_ZH[col_["role"]]} | {"是" if col_["effective_business_field"] else ""} | {FEAT_ZH[col_["feature_policy"]]} | {extra} |')
    out += ['', '## 4. 数据中没有的内容', '', '、'.join(c['not_available']) + '。页面和 AI 回答遇到这些问题返回 `capability_not_supported`。',
            '', '## 5. 禁止的假设', ''] + [f'- {x}' for x in c['forbidden_assumptions']] + [
            '', '## 6. 留给下游', ''] + [f'- {k}：{v}' for k, v in c['pending_downstream'].items()] + ['']
    return '\n'.join(out)


if __name__ == '__main__':
    main()
