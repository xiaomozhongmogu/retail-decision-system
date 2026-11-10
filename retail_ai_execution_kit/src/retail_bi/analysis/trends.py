"""EDA-02: business trends and structure on comparable complete periods.

Comparable period = January-October of each year (2026 is complete only through October; November 2026 has
7 days and is excluded). Valid purchase = approved before the 2026-11-08 cutoff; money = USD merchandise amount
(shipping is a non-merchandise charge, reported separately; there are no refunds in the data, cancelled orders
are excluded and counted separately). Growth rates are only computed when the base has >= 30 orders;
otherwise the status is 'small_sample'; a zero base gives 'no_base' (never a percentage).

Every query is stored with its result in reports/analysis/business_trends.json so findings can be traced.
usage: .venv/bin/python src/retail_bi/analysis/trends.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'warehouse'))
from db import ROOT  # noqa: E402
from runtime import open_current  # noqa: E402

V = "o.approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'"
YTD = "month(o.purchase_ts) <= 10"
MIN_BASE = 30
Q = {
    'ytd_by_year': f"""SELECT year(o.purchase_ts) AS year, count(*) AS orders, sum(o.merch_usd)::DOUBLE AS merch_usd, sum(o.shipping_usd)::DOUBLE AS shipping_usd,
        count(DISTINCT o.customer_id) AS buyers, (sum(o.merch_usd) / count(*))::DOUBLE AS aov_usd,
        (count(*)::DOUBLE / count(DISTINCT o.customer_id)) AS orders_per_buyer
        FROM dwd.fact_order o WHERE {V} AND {YTD} GROUP BY 1 ORDER BY 1""",
    'cancelled_ytd_by_year': f"""SELECT year(o.purchase_ts) AS year, count(*) AS cancelled_orders, sum(o.merch_usd)::DOUBLE AS cancelled_merch_usd
        FROM dwd.fact_order o WHERE o.approved_ts IS NULL AND {YTD} GROUP BY 1 ORDER BY 1""",
    'quarterly': f"""SELECT year(o.purchase_ts) || '-Q' || quarter(o.purchase_ts) AS quarter, count(*) AS orders, sum(o.merch_usd)::DOUBLE AS merch_usd,
        count(DISTINCT o.customer_id) AS buyers FROM dwd.fact_order o WHERE {V} AND o.purchase_ts < TIMESTAMPTZ '2026-10-01 00:00:00+00' GROUP BY 1 ORDER BY 1""",
    'category_ytd': f"""SELECT p.product_category, year(o.purchase_ts) AS year, count(*) AS lines, count(DISTINCT l.order_id) AS orders_containing,
        sum(l.item_price_usd)::DOUBLE AS merch_usd FROM dwd.fact_order_line l JOIN dwd.fact_order o USING (order_id) JOIN dwd.dim_product p USING (product_id)
        WHERE {V} AND {YTD} AND year(o.purchase_ts) IN (2025, 2026) GROUP BY 1, 2 ORDER BY 1, 2""",
    'region_ytd': f"""SELECT c.customer_region, year(o.purchase_ts) AS year, count(*) AS orders, count(DISTINCT o.customer_id) AS buyers,
        sum(o.merch_usd)::DOUBLE AS merch_usd FROM dwd.fact_order o JOIN dwd.dim_customer c USING (customer_id)
        WHERE {V} AND {YTD} AND year(o.purchase_ts) IN (2025, 2026) GROUP BY 1, 2 ORDER BY 1, 2""",
    'seasonality': f"""SELECT month(o.purchase_ts) AS month, year(o.purchase_ts) AS year, count(*) AS orders FROM dwd.fact_order o
        WHERE {V} AND o.purchase_ts < TIMESTAMPTZ '2026-11-01 00:00:00+00' GROUP BY 1, 2 ORDER BY 1, 2""",
    'small_cells_example': f"""SELECT c.customer_region, p.product_category, count(DISTINCT l.order_id) AS orders FROM dwd.fact_order_line l
        JOIN dwd.fact_order o USING (order_id) JOIN dwd.dim_product p USING (product_id) JOIN dwd.dim_customer c ON c.customer_id = l.customer_id
        WHERE {V} AND strftime(o.purchase_ts, '%Y-%m') = '2025-10' GROUP BY 1, 2 HAVING count(DISTINCT l.order_id) < {MIN_BASE} ORDER BY 3 LIMIT 10""",
}


def growth(new, base, base_orders):
    if base == 0:
        return {'status': 'no_base', 'value': None}
    if base_orders < MIN_BASE:
        return {'status': 'small_sample', 'value': None}
    return {'status': 'ok', 'value': round((new - base) / base, 4)}


def main():
    con, ptr = open_current()
    res = {}
    for k, sql in Q.items():
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        res[k] = {'sql': ' '.join(sql.split()), 'rows': [dict(zip(cols, r)) for r in cur.fetchall()]}
    con.close()
    y = {r['year']: r for r in res['ytd_by_year']['rows']}
    yoy = {}
    for a, b in [(2024, 2025), (2025, 2026)]:
        yoy[f'{b}_vs_{a}'] = {m: growth(y[b][m], y[a][m], y[a]['orders']) for m in ('orders', 'merch_usd', 'buyers', 'aov_usd', 'orders_per_buyer')}
    # volume x price decomposition of the 2026 vs 2025 merchandise change (log split, exact sum)
    import math
    d_total = y[2026]['merch_usd'] - y[2025]['merch_usd']
    lr = math.log(y[2026]['merch_usd'] / y[2025]['merch_usd'])
    share_buyers = math.log(y[2026]['buyers'] / y[2025]['buyers']) / lr
    share_freq = math.log(y[2026]['orders_per_buyer'] / y[2025]['orders_per_buyer']) / lr
    share_aov = math.log(y[2026]['aov_usd'] / y[2025]['aov_usd']) / lr
    decomposition = {'delta_merch_usd': round(d_total, 2), 'due_to_buyers_usd': round(d_total * share_buyers, 2),
                     'due_to_orders_per_buyer_usd': round(d_total * share_freq, 2), 'due_to_aov_usd': round(d_total * share_aov, 2),
                     'method': '商品金额 = 购买客户数 × 人均订单数 × 客单价，按对数分解，三部分之和等于总变化'}
    cat = {}
    for r in res['category_ytd']['rows']:
        cat.setdefault(r['product_category'], {})[r['year']] = r
    cat_rows = []
    for c, v in cat.items():
        a, b = v.get(2025, {'merch_usd': 0, 'orders_containing': 0}), v.get(2026, {'merch_usd': 0, 'orders_containing': 0})
        cat_rows.append({'category': c, 'merch_2025': round(a['merch_usd'], 2), 'merch_2026': round(b['merch_usd'], 2), 'delta': round(b['merch_usd'] - a['merch_usd'], 2),
                         'delta_vs_2025_total': round((b['merch_usd'] - a['merch_usd']) / y[2025]['merch_usd'], 4),
                         'growth': growth(b['merch_usd'], a['merch_usd'], a['orders_containing'])})
    cat_rows.sort(key=lambda r: r['delta'])
    reg = {}
    for r in res['region_ytd']['rows']:
        reg.setdefault(r['customer_region'], {})[r['year']] = r
    reg_rows = [{'region': k, 'merch_2025': round(v[2025]['merch_usd'], 2), 'merch_2026': round(v[2026]['merch_usd'], 2),
                 'delta': round(v[2026]['merch_usd'] - v[2025]['merch_usd'], 2), 'buyers_2025': v[2025]['buyers'], 'buyers_2026': v[2026]['buyers'],
                 'delta_vs_2025_total': round((v[2026]['merch_usd'] - v[2025]['merch_usd']) / y[2025]['merch_usd'], 4),
                 'growth': growth(v[2026]['merch_usd'], v[2025]['merch_usd'], v[2025]['orders'])} for k, v in reg.items()]
    seas = {}
    for r in res['seasonality']['rows']:
        seas.setdefault(r['month'], []).append(r['orders'])
    avg_all = sum(sum(v) for v in seas.values()) / sum(len(v) for v in seas.values())
    season_index = {m: round(sum(v) / len(v) / avg_all, 3) for m, v in sorted(seas.items())}
    out = {'task_id': 'EDA-02', 'release': ptr['version'], 'comparable_period': '每年 1–10 月（2026-11 不完整，排除）', 'min_base_orders': MIN_BASE,
           'rules': {'merchandise': 'USD 商品金额；运费为非商品收费，单列', 'refunds': '数据中没有退款', 'cancellations': '取消订单不计入，单列统计'},
           'queries': res, 'yoy': yoy, 'decomposition_2026_vs_2025': decomposition, 'category_contribution': cat_rows, 'region_contribution': reg_rows,
           'seasonality_index': season_index}
    (ROOT / 'reports/analysis/business_trends.json').write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    (ROOT / 'reports/analysis/business_trends.md').write_text(render(out, y), encoding='utf-8')
    print(json.dumps({'yoy': yoy, 'decomp': decomposition}, ensure_ascii=False))


def pct(g):
    return f'{g["value"]:+.1%}' if g['status'] == 'ok' else ('样本不足' if g['status'] == 'small_sample' else '无基期')


def render(o, y):
    yo, d = o['yoy'], o['decomposition_2026_vs_2025']
    c = {r['year']: r for r in o['queries']['cancelled_ytd_by_year']['rows']}
    L = ['# 经营趋势与结构（EDA-02）', '',
         f'- 只读发布 `{o["release"]}`；可比期间：{o["comparable_period"]}；增长率只在基期订单数 ≥ {o["min_base_orders"]} 时计算，否则标“样本不足”。',
         '- 口径：' + '；'.join(f'{k}：{v}' for k, v in o['rules'].items()) + '。数据完全合成。', '',
         '## 1. 可比期间（1–10 月）', '', '| 年份 | 有效订单 | 商品金额 | 运费 | 购买客户 | 客单价 | 人均订单 | 取消订单 |', '|---|---:|---:|---:|---:|---:|---:|---:|']
    L += [f'| {k} | {v["orders"]:,} | {v["merch_usd"]:,.2f} | {v["shipping_usd"]:,.2f} | {v["buyers"]:,} | {v["aov_usd"]:.2f} | {v["orders_per_buyer"]:.3f} | {c.get(k, {}).get("cancelled_orders", 0)} |' for k, v in y.items()]
    L += ['', '| 同比 | 订单 | 商品金额 | 购买客户 | 客单价 | 人均订单 |', '|---|---:|---:|---:|---:|---:|']
    L += [f'| {k.replace("_vs_", " 对 ")} | {pct(v["orders"])} | {pct(v["merch_usd"])} | {pct(v["buyers"])} | {pct(v["aov_usd"])} | {pct(v["orders_per_buyer"])} |' for k, v in yo.items()]
    L += ['', f'**量价分解（2026 对 2025，1–10 月）**：商品金额变化 {d["delta_merch_usd"]:+,.2f} USD，其中购买客户数贡献 {d["due_to_buyers_usd"]:+,.2f}，'
          f'人均订单数贡献 {d["due_to_orders_per_buyer_usd"]:+,.2f}，客单价贡献 {d["due_to_aov_usd"]:+,.2f}（{d["method"]}）。', '',
          '## 2. 品类贡献（2026 对 2025，1–10 月）', '', '| 品类 | 2025 | 2026 | 变化 | 变化占 2025 总额 | 增长 |', '|---|---:|---:|---:|---:|---:|']
    L += [f'| {r["category"]} | {r["merch_2025"]:,.2f} | {r["merch_2026"]:,.2f} | {r["delta"]:+,.2f} | {r["delta_vs_2025_total"]:+.2%} | {pct(r["growth"])} |' for r in o['category_contribution']]
    L += ['', '## 3. 大区贡献（本数据没有国家维度）', '', '| 大区 | 2025 | 2026 | 变化 | 变化占 2025 总额 | 客户 2025→2026 | 增长 |', '|---|---:|---:|---:|---:|---|---:|']
    L += [f'| {r["region"]} | {r["merch_2025"]:,.2f} | {r["merch_2026"]:,.2f} | {r["delta"]:+,.2f} | {r["delta_vs_2025_total"]:+.2%} | {r["buyers_2025"]}→{r["buyers_2026"]} | {pct(r["growth"])} |' for r in o['region_contribution']]
    si = o['seasonality_index']
    small = o['queries']['small_cells_example']['rows']
    L += ['', '## 4. 季节性', '', '月度订单指数（各年同月平均 / 全部月份平均，2024-01 至 2026-10）：' + '，'.join(f'{m} 月 {v}' for m, v in si.items()) + '。', '',
          '## 5. 小样本与分母为零', '',
          f'- 月 × 大区 × 品类的格子很小：以 2025-10 为例，订单少于 {o["min_base_orders"]} 的组合有 {len(small)} 个以上（如 ' +
          '、'.join(f'{r["customer_region"]}/{r["product_category"]} {r["orders"]} 单' for r in small[:3]) + '），这类格子不计算增长率。',
          '- 指标视图在分母为 0 时返回空值（DW-06 已验证），不输出 0% 或无穷大。', '',
          '## 6. 发现（每条可追溯到 `reports/analysis/business_trends.json` 中的查询与结果）', '']
    worst, best = o['category_contribution'][0], o['category_contribution'][-1]
    L += [f'1. 2026 年 1–10 月商品金额基本持平（{pct(yo["2026_vs_2025"]["merch_usd"])}），订单 {pct(yo["2026_vs_2025"]["orders"])}、购买客户 {pct(yo["2026_vs_2025"]["buyers"])}，'
          f'客单价 {pct(yo["2026_vs_2025"]["aov_usd"])}。查询：ytd_by_year。',
          f'2. 量价分解：客户数减少的影响 {d["due_to_buyers_usd"]:+,.0f} USD 几乎被客单价上升的 {d["due_to_aov_usd"]:+,.0f} USD 抵消，人均订单数影响 {d["due_to_orders_per_buyer_usd"]:+,.0f}。'
          '客户数减少与 2024 年中之后没有新建档客户的合成人口封闭一致（EDA-01），不能解读为获客或运营能力变化；客单价上升的原因数据无法说明。查询：ytd_by_year。',
          f'3. 品类层面，变化最大的下降是 {worst["category"]}（{worst["delta"]:+,.0f} USD，相当于 2025 年总额的 {worst["delta_vs_2025_total"]:+.1%}），'
          f'最大的上升是 {best["category"]}（{best["delta"]:+,.0f} USD，{best["delta_vs_2025_total"]:+.1%}）；品类之间有升有降、相互抵消。查询：category_ytd。',
          f'4. 季节性：12 月订单指数 {si.get(12)}，2 月 {si.get(2)}，年末旺季明显。查询：seasonality。', '',
          '以上是相关描述，不是因果；数据没有渠道、价格调整、成本或竞争信息，原因解释需在 EDA-04 中标为待验证。', '']
    return '\n'.join(L)


if __name__ == '__main__':
    main()
