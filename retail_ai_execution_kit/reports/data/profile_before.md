# 清洗前质量剖析（DATA-06）

> 由 `src/retail_bi/data/profile.py` 生成，数字均来自 `reports/data/profile_before.json`。数据完全合成。

- 范围：截止前全部历史（DATA-03/D013），未抽样；history_source 全部 10 张表与 observed 两张视图逐行读取。抽样：none。
- 抽样与历史保留规则：若以后为开发抽样，按客户整体抽取并保留其全部历史订单，标为开发样本；最终建模与报告用全量（DATA-10）。
- 契约：`synthetic-transaction-v1`；时区：naive source; UTC engineering assumption; display in Asia/Shanghai only after explicit conversion。

## 1. 规模与实体覆盖

| 表 | 行数 |
|---|---:|
| customers | 3,647 |
| sellers | 800 |
| products | 8,000 |
| seller_products | 13,966 |
| orders | 9,311 |
| order_items | 15,639 |
| payments | 10,010 |
| shipping | 9,311 |
| reviews | 6,190 |
| calendar | 1,042 |
| observed_orders | 9,311 |
| observed_reviews | 6,096 |

| 实体 | 数量 |
|---|---:|
| customers_master | 3,647 |
| customers_with_orders | 3,356 |
| customers_without_orders_before_cutoff | 291 |
| products_master | 8,000 |
| products_sold | 5,418 |
| sellers_master | 800 |
| sellers_with_sales | 766 |
| listings_master | 13,966 |
| listings_sold | 7,808 |

## 2. 缺失

| 字段 | 空值 | 比例 |
|---|---:|---:|
| sellers.deactivated_at | 800 | 100.00% |
| orders.order_approved_at | 194 | 2.08% |
| orders.order_delivered_carrier_date | 477 | 5.12% |
| orders.order_delivered_customer_date | 656 | 7.05% |
| shipping.actual_delivery_days | 656 | 7.05% |
| shipping.delivery_delay_days | 656 | 7.05% |

审批、交承运、送达时间的空值与最终状态严格对应（见契约一致性检查），是“事件尚未发生”，不是录入缺失；`sellers.deactivated_at` 全空表示没有卖家停用。

## 3. 重复与重复候选

| 检查 | 数量 |
|---|---:|
| exact_duplicate_rows:customers | 0 |
| exact_duplicate_rows:sellers | 0 |
| exact_duplicate_rows:products | 0 |
| exact_duplicate_rows:seller_products | 0 |
| exact_duplicate_rows:orders | 0 |
| exact_duplicate_rows:order_items | 0 |
| exact_duplicate_rows:payments | 0 |
| exact_duplicate_rows:shipping | 0 |
| exact_duplicate_rows:reviews | 0 |
| exact_duplicate_rows:calendar | 0 |
| orders_same_customer_same_timestamp | 0 |
| customer_days_with_2plus_orders | 11 |
| purchase_timestamps_shared_by_2plus_orders | 1 |
| order_items_same_product_repeated_in_order | 779 |
| orders_with_2_payments | 699 |
| order_items_same_listing_repeated_in_order | 779 |
| repeated_product_groups | 668 |
| repeated_product_groups_with_identical_prices | 0 |

样本（同一客户同一天多单）：[['customer_002008', '2026-04-29'], ['customer_002557', '2026-09-03'], ['customer_002314', '2025-09-02'], ['customer_001004', '2024-06-17'], ['customer_003588', '2025-11-15']]；（同单重复商品）：[['order_0000013', 'product_002590'], ['order_0000015', 'product_002523'], ['order_0000025', 'product_002647'], ['order_0000102', 'product_000620'], ['order_0000112', 'product_002449']]。
完全重复行为 0。同单重复商品全部是同一个上架商品，但每组价格都不相同（价格完全相同的组为 0），更像生成器有放回地多次抽取同一商品，不是重复导入；按独立明细行保留，不推断为数量。同一客户同日多单是可能的正常行为。DATA-07 记录处理理由，不默认删除。

## 4. 时间

- 下单时间 2024-01-01T09:06:48 至 2026-11-07T22:15:48，共 35 个月；跨度 1,042 天，其中 0 天没有订单。
- 最后一个月不完整：True（截止 2026-11-08T00:00:00+00:00）。日期维覆盖所有下单日：True。
- 事件先后检查（共 9,311 单）：。
- 客户建档日期范围 2024-01-01 至 2024-06-29。

| 月份 | 订单 |
|---|---:|
| 2024-01 | 234 |
| 2024-02 | 261 |
| 2024-03 | 252 |
| 2024-04 | 237 |
| 2024-05 | 255 |
| 2024-06 | 233 |
| 2024-07 | 245 |
| 2024-08 | 278 |
| 2024-09 | 262 |
| 2024-10 | 359 |
| 2024-11 | 327 |
| 2024-12 | 371 |
| 2025-01 | 263 |
| 2025-02 | 234 |
| 2025-03 | 279 |
| 2025-04 | 227 |
| 2025-05 | 240 |
| 2025-06 | 251 |
| 2025-07 | 276 |
| 2025-08 | 280 |
| 2025-09 | 239 |
| 2025-10 | 335 |
| 2025-11 | 367 |
| 2025-12 | 383 |
| 2026-01 | 257 |
| 2026-02 | 193 |
| 2026-03 | 264 |
| 2026-04 | 233 |
| 2026-05 | 249 |
| 2026-06 | 250 |
| 2026-07 | 258 |
| 2026-08 | 247 |
| 2026-09 | 246 |
| 2026-10 | 342 |
| 2026-11 | 84 |

## 5. 取消、零值、负值与极端交易

- 状态：{'delivered': 8655, 'processing': 283, 'cancelled': 194, 'shipped': 179}。已取消订单商品金额 27778.26 USD；其中有支付记录的取消单 194 单，有评价的取消单 0 单。
- 没有退款表、负金额或冲销记录；取消只能由最终状态识别，且没有取消发生时间。

| 金额字段 | 负值 | 零值 | 中位数 | P99 | 最大 | 极端（>Q3+3IQR） |
|---|---:|---:|---:|---:|---:|---:|
| order_items.item_price_usd | 0 | 0 | 64.04 | 441.59 | 1325.46 | 366 |
| order_items.shipping_cost_usd | 0 | 0 | 8.2 | 18.1 | 31.27 | 413 |
| order_items.item_total_usd | 0 | 0 | 72.59 | 451.55 | 1333.17 | 363 |
| payments.payment_value_usd | 0 | 0 | 107.04 | 709.96 | 1672.39 | 151 |
| shipping.shipping_cost_usd | 0 | 0 | 10.12 | 45.75 | 82.75 | 78 |
| products.product_price_base_usd | 0 | 0 | 62.48 | 411.01 | 1176.47 | 180 |
| seller_products.seller_price_usd | 0 | 0 | 64.63 | 436.09 | 1187.35 | 319 |

- 订单金额（含运费）中位数 117.18，P99 742.15，最大 1672.39；超过 666.72 的极端订单 140 单。
- 金额最高的 5 单：order_0007105 1672.39（5 行，delivered）；order_0002682 1490.14（2 行，delivered）；order_0001423 1476.09（5 行，delivered）；order_0007358 1468.71（5 行，delivered）；order_0004016 1419.84（5 行，delivered）。
- 每单明细行数：{1: 5401, 2: 2347, 3: 950, 4: 371, 5: 242}。成交价/卖家标价比值分位：{'p00': '0.6332', 'p01': '0.7626', 'p25': '0.9229', 'p50': '0.9920', 'p75': '1.0642', 'p99': '1.2611', 'p100': '1.4829'}。分期数：{1: 6964, 2: 1653, 3: 552, 4: 265, 5: 204, 6: 115, 7: 82, 8: 60, 9: 39, 10: 29, 11: 26, 12: 21}。
- 极端值只标记不删除：合成数据没有录入错误的依据，DATA-07/10 决定是否截尾或变换。

## 6. 字段有效性

| 检查 | 不一致数 |
|---|---:|
| actual_delivery_days != floor(delivered - purchase) | 0 |
| delivery_delay_days != max(0, actual - estimated_days) | 0 |
| late_flag != (delay_days > 0) | 0 |
| delivered after estimated DATE but late_flag False | 4,268 |
| undelivered but actual/delay present | 0 |
| undelivered but late_flag True | 0 |
| estimated_date - purchase_date != estimated_delivery_days | 0 |
| review on non-delivered order | 0 |
| review created before delivery date | 0 |
| satisfaction_flag != score<=2 | 0 |

（已送达订单共检查 8,655 单。）样本：{'late_by_date_not_flagged': [['order_0000001', '2025-08-08T02:10:36', '2025-08-07T00:00:00'], ['order_0000003', '2026-05-29T11:05:42', '2026-05-28T00:00:00'], ['order_0000004', '2024-04-29T15:08:31', '2024-04-28T00:00:00'], ['order_0000005', '2026-07-24T07:34:34', '2026-07-23T00:00:00'], ['order_0000007', '2026-08-22T00:41:15', '2026-08-21T00:00:00']]}。
“按日期晚到但未标记延迟”的原因：生成器用“实际天数向下取整 > 预计天数”判断延迟，而预计送达日期是下单日加预计天数的零点；下单当天较晚的订单，即使送达日期晚于预计日期，取整后天数也可能不超过预计天数。两种口径都自洽但结果不同：页面和特征必须写明用哪一种，推荐从时间戳按日期重算（DATA-10）。
评价覆盖已送达订单的比例 71.5%。

## 7. 客户覆盖与正类潜力

- 口径：provisional: purchase = order not cancelled (DATA-08 freezes the rule)。有购买的客户 3,339，其中至少两次 2,586；首购在数据开始 90 天内的客户 618。

| 标签窗 | 周快照数 | as_of 范围 | 客户样本行 | 正例 | 整体比例 | 单快照比例（最小/中位/最大） | 单快照母体 |
|---|---:|---|---:|---:|---:|---|---|
| 30d | 132 | 2024-04-01 ~ 2026-10-05 | 92,880 | 6,668 | 7.2% | 3.0% / 7.1% / 11.1% | 624–896 |
| 60d | 128 | 2024-04-01 ~ 2026-09-07 | 90,298 | 12,364 | 13.7% | 7.5% / 13.6% / 18.3% | 624–896 |
| 90d | 124 | 2024-04-01 ~ 2026-08-10 | 87,659 | 17,220 | 19.6% | 14.5% / 19.4% / 25.4% | 624–896 |

结论：35 个月历史；按周快照可得 92880 行客户样本、6668 个 30 天正例（整体 7.2%）。正例足以训练和按时间外评估，但比例低，需看 PR-AUC 与校准；跨度足够，不需要回到选型。

首购分布：{'2024-01': 216, '2024-02': 222, '2024-03': 195, '2024-04': 176, '2024-05': 187, '2024-06': 162, '2024-07': 159, '2024-08': 168, '2024-09': 153, '2024-10': 166, '2024-11': 162, '2024-12': 136, '2025-01': 105, '2025-02': 90, '2025-03': 99, '2025-04': 76, '2025-05': 67, '2025-06': 65, '2025-07': 72, '2025-08': 79, '2025-09': 55, '2025-10': 75, '2025-11': 73, '2025-12': 65, '2026-01': 40, '2026-02': 32, '2026-03': 46, '2026-04': 35, '2026-05': 35, '2026-06': 37, '2026-07': 28, '2026-08': 21, '2026-09': 14, '2026-10': 21, '2026-11': 7}。客户建档日期都在 2024-01-01 至 2024-06-29，没有早于数据起点的客户，所以本数据中首次可观测购买没有被数据起点截断；但早期月份首购集中，是生成器的建档节奏造成的，cohort 分析（EDA-03）要按建档节奏解读，仍称“首次可观测购买”。

## 8. 交给下游的问题清单

- DATA-07：没有缺失 ID、没有解析失败、没有完全重复行；记录“同客户同日多单”“同单重复商品”的处理理由。
- DATA-08：取消单的金额、支付和评价如何计入；processing/shipped 是否算有效购买；运费是否计入金额。
- DATA-10 / ML：物流派生字段与日期的不一致（见第 6 节）意味着要从时间戳重算，不直接使用源派生列。
- ML-01：30 天正例比例低；也列出 60/90 天作参考，目标仍由 ML-01 冻结。

隐私：样本只给合成 ID、日期和金额；不输出邮编、城市等地址字段。
