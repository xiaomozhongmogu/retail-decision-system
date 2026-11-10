"""EDA-01: initial descriptive statistics from the published warehouse release (read-only).

Every number in reports/analysis/eda_initial.{json,md} comes from this program. Scope: fully synthetic
data, purchases placed before the 2026-11-08 cutoff, valid purchase = approved before the cutoff, money in USD
(merchandise, shipping separate). This is a historical simulated period, not live 2026 operations.

usage: .venv/bin/python src/retail_bi/analysis/eda_initial.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'warehouse'))
from db import ROOT  # noqa: E402
from runtime import open_current  # noqa: E402

V = "approved_ts < TIMESTAMPTZ '2026-11-08 00:00:00+00'"


def rows(con, sql):
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, [float(v) if hasattr(v, 'as_tuple') else v for v in r])) for r in cur.fetchall()]


def one(con, sql):
    return rows(con, sql)[0]


def main():
    con, ptr = open_current()
    r = {'task_id': 'EDA-01', 'release': ptr['version'], 'release_sha256': ptr['sha256'],
         'scope': {'data': '完全合成（D012/D013），不是真实企业或顾客', 'period': '下单时间 2024-01-01 至 2026-11-07（截止 2026-11-08，不含）',
                   'valid_purchase': '截止前已审批的订单（transaction-rules-v1）', 'money': 'USD 商品金额，运费单列', 'sample': '全量，未抽样',
                   'timezone': 'UTC 工程假设', 'not_live': '这是模拟的历史区间，不代表 2026 年实时经营'}}
    r['volume'] = one(con, f"""SELECT count(*) AS orders_all, count(*) FILTER (WHERE {V}) AS valid_orders,
            count(*) FILTER (WHERE approved_ts IS NULL) AS cancelled_orders,
            (SELECT count(*) FROM dwd.fact_order_line) AS lines_all, (SELECT count(*) FROM dwd.dim_customer) AS customers_master,
            count(DISTINCT customer_id) FILTER (WHERE {V}) AS buyers, (SELECT count(DISTINCT product_id) FROM dwd.fact_order_line) AS products_sold,
            sum(merch_usd) FILTER (WHERE {V}) AS merch_usd, sum(shipping_usd) FILTER (WHERE {V}) AS shipping_usd FROM dwd.fact_order""")
    r['monthly'] = rows(con, "SELECT month, valid_orders, merchandise_sales_usd AS merch_usd, buyers, round(aov_usd, 2) AS aov_usd, cancelled_orders, partial_period FROM ads.kpi_monthly ORDER BY month")
    full = [m for m in r['monthly'] if not m['partial_period']]
    by_year = {}
    for m in full:
        y = m['month'][:4]
        by_year.setdefault(y, {'orders': 0, 'merch_usd': 0.0, 'months': 0})
        by_year[y]['orders'] += m['valid_orders']
        by_year[y]['merch_usd'] += m['merch_usd']
        by_year[y]['months'] += 1
    r['by_year'] = {y: {**v, 'orders_per_month': round(v['orders'] / v['months'], 1)} for y, v in by_year.items()}
    r['calendar_month_profile'] = rows(con, f"""SELECT month(purchase_ts) AS month_of_year, count(*) AS orders, count(DISTINCT year(purchase_ts)) AS years
            FROM dwd.fact_order WHERE {V} AND purchase_ts < TIMESTAMPTZ '2026-11-01 00:00:00+00' GROUP BY 1 ORDER BY 1""")
    for m in r['calendar_month_profile']:
        m['orders_per_year'] = round(m['orders'] / m['years'], 1)
    r['order_value'] = one(con, f"""SELECT quantile_cont(merch_usd, 0.1) AS p10, median(merch_usd) AS p50, quantile_cont(merch_usd, 0.9) AS p90,
            quantile_cont(merch_usd, 0.99) AS p99, max(merch_usd) AS max, avg(item_lines) AS lines_per_order FROM dwd.fact_order WHERE {V}""")
    r['concentration'] = one(con, f"""WITH c AS (SELECT customer_id, sum(merch_usd) m FROM dwd.fact_order WHERE {V} GROUP BY 1),
            k AS (SELECT m, ntile(10) OVER (ORDER BY m DESC) d FROM c)
            SELECT sum(m) FILTER (WHERE d = 1) / sum(m) AS top10pct_customers_share, sum(m) FILTER (WHERE d <= 2) / sum(m) AS top20pct_customers_share FROM k""")
    r['customers'] = {
        'orders_per_customer': rows(con, f"""SELECT n AS orders, count(*) AS customers FROM (SELECT customer_id, count(*) n FROM dwd.fact_order WHERE {V} GROUP BY 1) GROUP BY 1 ORDER BY 1"""),
        'repeat': one(con, f"""SELECT count(*) AS buyers, count(*) FILTER (WHERE n >= 2) AS repeat_buyers, count(*) FILTER (WHERE n >= 2) / count(*) AS repeat_share
                              FROM (SELECT customer_id, count(*) n FROM dwd.fact_order WHERE {V} GROUP BY 1)"""),
        'gap_days': one(con, f"""WITH o AS (SELECT customer_id, purchase_ts, lag(purchase_ts) OVER (PARTITION BY customer_id ORDER BY purchase_ts) prev
                                 FROM dwd.fact_order WHERE {V})
                                SELECT count(*) AS gaps, quantile_cont(epoch(purchase_ts - prev) / 86400, 0.25) AS p25, median(epoch(purchase_ts - prev) / 86400) AS p50,
                                       quantile_cont(epoch(purchase_ts - prev) / 86400, 0.75) AS p75,
                                       avg((epoch(purchase_ts - prev) / 86400 < 30)::INT) AS share_within_30d FROM o WHERE prev IS NOT NULL"""),
        'new_buyers_by_half_year': rows(con, f"""SELECT strftime(first, '%Y') || CASE WHEN month(first) <= 6 THEN '-H1' ELSE '-H2' END AS half, count(*) AS new_buyers
                                     FROM (SELECT customer_id, min(purchase_ts) first FROM dwd.fact_order WHERE {V} GROUP BY 1) GROUP BY 1 ORDER BY 1"""),
        'customer_created_range': one(con, 'SELECT min(customer_created_date) AS first, max(customer_created_date) AS last FROM dwd.dim_customer'),
        'never_bought': one(con, f"""SELECT count(*) AS customers FROM dwd.dim_customer c WHERE NOT EXISTS
                                     (SELECT 1 FROM dwd.fact_order o WHERE o.customer_id = c.customer_id AND {V.replace('approved_ts', 'o.approved_ts')})"""),
    }
    r['category'] = rows(con, f"""SELECT p.product_category, count(*) AS lines, sum(l.item_price_usd) AS merch_usd, sum(l.item_price_usd) / sum(sum(l.item_price_usd)) OVER () AS share,
            avg(l.item_price_usd) AS avg_line_usd FROM dwd.fact_order_line l JOIN dwd.fact_order o USING (order_id) JOIN dwd.dim_product p USING (product_id)
            WHERE o.{V} GROUP BY 1 ORDER BY merch_usd DESC""")
    r['region'] = rows(con, f"""SELECT c.customer_region, count(*) AS orders, count(DISTINCT o.customer_id) AS buyers, sum(o.merch_usd) AS merch_usd,
            sum(o.merch_usd) / count(*) AS aov_usd FROM dwd.fact_order o JOIN dwd.dim_customer c USING (customer_id) WHERE o.{V} GROUP BY 1 ORDER BY merch_usd DESC""")
    r['weekday'] = rows(con, f"SELECT dayofweek(purchase_ts) AS dow_sun0, count(*) AS orders FROM dwd.fact_order WHERE {V} GROUP BY 1 ORDER BY 1")
    r['hour_utc'] = rows(con, f"SELECT hour(purchase_ts) AS hour, count(*) AS orders FROM dwd.fact_order WHERE {V} GROUP BY 1 ORDER BY 1")
    r['generator_calendar_flags'] = rows(con, f"""SELECT d.is_promotion_period, d.is_holiday_period, count(DISTINCT d.date_key) AS days, count(*) AS orders,
            count(*) / count(DISTINCT d.date_key) AS orders_per_day FROM dwd.fact_order o JOIN dwd.dim_date d ON d.date_key = o.purchase_date_key
            WHERE o.{V} GROUP BY 1, 2 ORDER BY 1, 2""")
    r['delivery_review'] = {
        'late_rates': one(con, f"""SELECT count(*) FILTER (WHERE delivered_ts IS NOT NULL) AS delivered, avg(late_by_date::INT) AS late_by_date_rate,
                                   avg(late_by_days::INT) AS late_by_days_rate FROM dwd.fact_order WHERE {V}"""),
        'score_by_late': rows(con, f"""SELECT late_by_days, count(review_score) AS reviews, avg(review_score) AS avg_score,
                                     avg((review_score <= 2)::INT) AS low_score_share FROM dwd.fact_order WHERE {V} AND delivered_ts IS NOT NULL GROUP BY 1 ORDER BY 1"""),
        'score_distribution': rows(con, f"SELECT review_score, count(*) AS reviews FROM dwd.fact_order WHERE {V} AND review_score IS NOT NULL GROUP BY 1 ORDER BY 1"),
    }
    r['payment'] = rows(con, f"""SELECT pm.payment_type, count(DISTINCT pm.order_id) AS orders_using, sum(pm.payment_value_usd) AS paid_usd,
            avg(pm.payment_installments) AS avg_installments FROM dwd.fact_payment pm JOIN dwd.fact_order o USING (order_id) WHERE o.{V} GROUP BY 1 ORDER BY paid_usd DESC""")
    r['anomalies'] = {
        'cancel_rate_by_year': rows(con, "SELECT year(purchase_ts) AS year, avg((approved_ts IS NULL)::INT) AS cancel_rate, count(*) AS orders FROM dwd.fact_order GROUP BY 1 ORDER BY 1"),
        'stuck_orders': rows(con, f"""SELECT order_status, count(*) AS orders, median(epoch(TIMESTAMPTZ '2026-11-08 00:00:00+00' - purchase_ts) / 86400) AS median_age_days
                                     FROM dwd.fact_order WHERE order_status IN ('processing', 'shipped') GROUP BY 1"""),
        'partial_month': '2026-11 只有 7 天数据，趋势图应标注或排除',
    }
    r['unknown_coverage'] = ['没有获客渠道、浏览/加购、营销触达与同意、优惠券', '没有购买数量、退款、取消发生时间、支付时间', '没有成本与毛利、库存、投诉',
                             '客户只在 2024 年上半年建档，之后没有新客户进入（合成人口封闭）', '生成器的促销/节日标记、客户分群和生命周期标签不是真实业务记录']
    con.close()
    (ROOT / 'reports/analysis/eda_initial.json').write_text(json.dumps(r, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    (ROOT / 'reports/analysis/eda_initial.md').write_text(render(r), encoding='utf-8')
    print(json.dumps({'volume': r['volume'], 'by_year': r['by_year']}, ensure_ascii=False, default=str))


def f(x, n=2):
    return f'{x:,.{n}f}' if isinstance(x, float) else (f'{x:,}' if isinstance(x, int) else str(x))


def render(r):
    v, c, dr = r['volume'], r['customers'], r['delivery_review']
    yr = r['by_year']
    L = ['# 初步描述性统计（EDA-01）', '',
         '> 由 `src/retail_bi/analysis/eda_initial.py` 从只读发布 `' + r['release'] + '` 生成，数字均来自 `reports/analysis/eda_initial.json`。', '',
         '**范围与口径**：' + '；'.join(f'{k}：{x}' for k, x in r['scope'].items()) + '。', '',
         '## 1. 规模', '',
         f'截止前共 {f(v["orders_all"])} 单，其中有效 {f(v["valid_orders"])} 单、取消 {f(v["cancelled_orders"])} 单；订单明细 {f(v["lines_all"])} 行；'
         f'主数据客户 {f(v["customers_master"])} 人，其中 {f(v["buyers"])} 人有有效购买；售出商品 {f(v["products_sold"])} 种。'
         f'有效商品金额 {f(v["merch_usd"])} USD，运费 {f(v["shipping_usd"])} USD。', '',
         '## 2. 趋势', '', '| 年份 | 完整月数 | 有效订单 | 月均订单 | 商品金额（USD） |', '|---|---:|---:|---:|---:|']
    L += [f'| {y} | {d["months"]} | {f(d["orders"])} | {d["orders_per_month"]} | {f(d["merch_usd"])} |' for y, d in yr.items()]
    peak = max(r['calendar_month_profile'], key=lambda m: m['orders_per_year'])
    low = min(r['calendar_month_profile'], key=lambda m: m['orders_per_year'])
    L += ['', f'- 按自然月平均（不含 2026-11）：{peak["month_of_year"]} 月最多（每年平均 {peak["orders_per_year"]} 单），{low["month_of_year"]} 月最少（{low["orders_per_year"]} 单）。',
          '- 2026 年只到 10 月完整，年度比较用月均值。2026-11 为不完整月。', '',
          '| 月份 | 有效订单 | 商品金额 | 购买客户 | 客单价 | 取消 |', '|---|---:|---:|---:|---:|---:|']
    L += [f'| {m["month"]}{"（不完整）" if m["partial_period"] else ""} | {m["valid_orders"]} | {f(m["merch_usd"])} | {m["buyers"]} | {f(m["aov_usd"])} | {m["cancelled_orders"]} |' for m in r['monthly']]
    ov, cc = r['order_value'], r['concentration']
    L += ['', '## 3. 金额分布与集中度', '',
          f'- 每单商品金额：P10 {f(ov["p10"])}，中位数 {f(ov["p50"])}，P90 {f(ov["p90"])}，P99 {f(ov["p99"])}，最大 {f(ov["max"])}；平均每单 {ov["lines_per_order"]:.2f} 行。右偏明显，平均值高于中位数。',
          f'- 客户集中度：金额最高的 10% 客户贡献 {cc["top10pct_customers_share"]:.1%}，最高的 20% 贡献 {cc["top20pct_customers_share"]:.1%}。', '',
          '## 4. 客户与复购', '',
          f'- 有效购买客户 {f(c["repeat"]["buyers"])} 人，其中买过至少两次的 {f(c["repeat"]["repeat_buyers"])} 人（{c["repeat"]["repeat_share"]:.1%}）。',
          f'- 相邻两次购买间隔：四分位 {c["gap_days"]["p25"]:.0f} / {c["gap_days"]["p50"]:.0f} / {c["gap_days"]["p75"]:.0f} 天；30 天内再次购买的间隔只占 {c["gap_days"]["share_within_30d"]:.1%}。'
          '这说明“未来 30 天复购”是一个低基率目标（ML-01）。',
          f'- 客户建档日期只在 {c["customer_created_range"]["first"]} 至 {c["customer_created_range"]["last"]}；有 {c["never_bought"]["customers"]} 名客户截至截止从未有效购买。',
          '- 新增购买客户（首次可观测有效购买）按半年：' + '，'.join(f'{x["half"]} {x["new_buyers"]}' for x in c['new_buyers_by_half_year']) +
          '。新客逐期减少是合成人口封闭（2024 年中以后没有新建档客户）造成的，不能解读为获客能力下降。', '',
          '| 每客户订单数 | 客户数 |', '|---:|---:|'] + [f'| {x["orders"]} | {x["customers"]} |' for x in c['orders_per_customer']]
    L += ['', '## 5. 品类与地区', '', '| 品类 | 明细 | 商品金额 | 占比 | 平均每行 |', '|---|---:|---:|---:|---:|']
    L += [f'| {x["product_category"]} | {x["lines"]} | {f(x["merch_usd"])} | {x["share"]:.1%} | {f(x["avg_line_usd"])} |' for x in r['category']]
    L += ['', '| 客户大区 | 订单 | 购买客户 | 商品金额 | 客单价 |', '|---|---:|---:|---:|---:|']
    L += [f'| {x["customer_region"]} | {x["orders"]} | {x["buyers"]} | {f(x["merch_usd"])} | {f(x["aov_usd"])} |' for x in r['region']]
    hi, lo = r['category'][0], r['category'][-1]
    reg_hi, reg_lo = r['region'][0], r['region'][-1]
    L += ['', f'品类金额差别明显：最高的 {hi["product_category"]} 占 {hi["share"]:.1%}（平均每行 {f(hi["avg_line_usd"])}），'
              f'最低的 {lo["product_category"]} 占 {lo["share"]:.1%}（平均每行 {f(lo["avg_line_usd"])}）；各品类明细行数相近，差别主要来自平均每行金额。'
              f'大区中 {reg_hi["customer_region"]} 金额最高（{f(reg_hi["merch_usd"])}），{reg_lo["customer_region"]} 最低（{f(reg_lo["merch_usd"])}），'
              f'各大区客单价相近（{f(min(x["aov_usd"] for x in r["region"]))}–{f(max(x["aov_usd"] for x in r["region"]))}），差别主要来自购买客户数。', '',
          '## 6. 时间分布', '',
          '- 星期（0=周日）：' + '，'.join(f'{x["dow_sun0"]}:{x["orders"]}' for x in r['weekday']) + '。',
          '- 小时（UTC）：' + '，'.join(f'{x["hour"]}:{x["orders"]}' for x in r['hour_utc']) + '。',
          '- 生成器促销/节日标记：' + '；'.join(f'促销={x["is_promotion_period"]}、节日={x["is_holiday_period"]}：{x["days"]} 天，{x["orders_per_day"]:.1f} 单/天' for x in r['generator_calendar_flags']) +
          '。这些是生成器设定，只能说明模拟规则，不是真实营销效果。', '',
          '## 7. 物流与评价（相关，不是因果）', '',
          f'- 已送达 {f(dr["late_rates"]["delivered"])} 单：按日期口径晚到 {dr["late_rates"]["late_by_date_rate"]:.1%}，按生成器口径 {dr["late_rates"]["late_by_days_rate"]:.1%}。',
          '- 评价分数与生成器口径延迟：' + '；'.join(f'延迟={x["late_by_days"]}：{x["reviews"]} 条评价，平均 {x["avg_score"]:.2f} 分，1–2 分占 {x["low_score_share"]:.1%}' for x in dr['score_by_late']) + '。',
          '- 分数分布：' + '，'.join(f'{x["review_score"]} 分 {x["reviews"]}' for x in dr['score_distribution']) + '。', '',
          '## 8. 支付', '', '| 支付方式 | 使用订单 | 支付金额 | 平均分期 |', '|---|---:|---:|---:|']
    L += [f'| {x["payment_type"]} | {x["orders_using"]} | {f(x["paid_usd"])} | {x["avg_installments"]:.2f} |' for x in r['payment']]
    a = r['anomalies']
    L += ['', '## 9. 异常与注意', '',
          '- 取消率按年：' + '，'.join(f'{x["year"]} {x["cancel_rate"]:.1%}（{x["orders"]} 单）' for x in a['cancel_rate_by_year']) + '。',
          '- 长期停留在中间状态的订单：' + '；'.join(f'{x["order_status"]} {x["orders"]} 单，距截止的中位天数 {x["median_age_days"]:.0f}' for x in a['stuck_orders']) +
          '。它们已审批，计为有效购买，但长期未完成，是生成器的期末状态。', f'- {a["partial_month"]}。', '',
          '## 10. 数据不能回答的问题', ''] + [f'- {x}' for x in r['unknown_coverage']] + ['']
    return '\n'.join(L)


if __name__ == '__main__':
    main()
