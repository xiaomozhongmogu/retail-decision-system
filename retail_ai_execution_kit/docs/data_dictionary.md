# 数据字典（DATA-04）

> 由 `evidence/DATA-04/build_contract.py` 生成，与 `contracts/data_contract.json` 同源；不要手工修改，改注释后重新生成。

- 契约版本：`synthetic-transaction-v1`，状态 `approved`。批准依据：依据 D012 用户授权的工程工作假设批准；不是教师确认（D012、D013）。
- 数据：Synthetic Ecommerce Dataset baseline_10000_seed42，**完全合成**；源 ZIP SHA-256 `d50ee64a0478d8ae8df1b8b66521671a4911e19f911ae86196452a668f917a16`；工程层 `engineering-import-v1`。
- 观察截止：`2026-11-08T00:00:00+00:00`（不含）。时区：naive source; UTC engineering assumption; display in Asia/Shanghai only after explicit conversion。币种：USD。
- 许可：网站下载件未标明数据许可；同作者仓库同类样例为 CC0，代码为 MIT；原始数据只用于课程，不对外发布（C07）。
- 有效业务字段 17 个（门槛 8）：`customers.customer_state`、`customers.customer_region`、`products.product_category`、`orders.order_id`、`orders.customer_id`、`orders.order_status`、`orders.order_purchase_timestamp`、`orders.order_delivered_customer_date`、`order_items.product_id`、`order_items.seller_id`、`order_items.item_price_usd`、`order_items.shipping_cost_usd`、`payments.payment_type`、`payments.payment_installments`、`payments.payment_value_usd`、`shipping.estimated_delivery_days`、`reviews.review_score`。
- 计数规则：只计业务含义独立的源字段；同一标识只在事实表外键处计一次；不计日期拆分列、scenario_name、生成器标签、由其他列推出的派生列、冗余拷贝、与主键 1:1 的冗余标识。通过已校验主键到达的字段列在 verified_related_fields，不重复计数。

## 1. 表与粒度

| 表 | 行数 | 主键 | 粒度 |
|---|---:|---|---|
| customers | 3,647 | customer_id | 主数据或日期维，一行一个实体 |
| sellers | 800 | seller_id | 主数据或日期维，一行一个实体 |
| products | 8,000 | product_id | 主数据或日期维，一行一个实体 |
| seller_products | 13,966 | seller_product_id | 主数据或日期维，一行一个实体 |
| orders | 9,311 | order_id | 一行一个订单 |
| order_items | 15,639 | order_id + order_item_id | 一行一个订单明细（订单内序号）；没有数量列 |
| payments | 10,010 | order_id + payment_sequential | 一行一次支付（订单内序号 1–2） |
| shipping | 9,311 | order_id | 一行一个订单的物流记录 |
| reviews | 6,190 | review_id | 一行一条评价；每单至多一条 |
| calendar | 1,042 | date | 主数据或日期维，一行一个实体 |

## 2. 键与一致性（实测）

| 检查 | 结果 |
|---|---|
| pk:customers | duplicates=0, nulls=0 |
| pk:sellers | duplicates=0, nulls=0 |
| pk:products | duplicates=0, nulls=0 |
| pk:seller_products | duplicates=0, nulls=0 |
| pk:orders | duplicates=0, nulls=0 |
| pk:order_items | duplicates=0, nulls=0 |
| pk:payments | duplicates=0, nulls=0 |
| pk:shipping | duplicates=0, nulls=0 |
| pk:reviews | duplicates=0, nulls=0 |
| pk:calendar | duplicates=0, nulls=0 |
| unique:reviews.order_id | duplicates=0 |
| unique:customers.customer_unique_id | duplicates=0 |
| fk:orders.customer_id->customers.customer_id | orphans=0, child_rows=9311 |
| fk:order_items.order_id->orders.order_id | orphans=0, child_rows=15639 |
| fk:order_items.product_id->products.product_id | orphans=0, child_rows=15639 |
| fk:order_items.seller_id->sellers.seller_id | orphans=0, child_rows=15639 |
| fk:order_items.seller_product_id->seller_products.seller_product_id | orphans=0, child_rows=15639 |
| fk:seller_products.seller_id->sellers.seller_id | orphans=0, child_rows=13966 |
| fk:seller_products.product_id->products.product_id | orphans=0, child_rows=13966 |
| fk:payments.order_id->orders.order_id | orphans=0, child_rows=10010 |
| fk:shipping.order_id->orders.order_id | orphans=0, child_rows=9311 |
| fk:reviews.order_id->orders.order_id | orphans=0, child_rows=6190 |
| order_items listing matches seller and product | 不一致 0 |
| item_total = item_price + item_shipping | 不一致 0 |
| sum(payment_value) = sum(item_total) per order | 不一致 0 |
| shipping.order_shipping = sum(item_shipping) per order | 不一致 0 |
| shipping.destination_state = customers.customer_state | 不一致 0 |
| shipping.destination_region = customers.customer_region | 不一致 0 |
| shipping.origin_state = sellers.seller_state | 不一致 0 |
| order_status implied by approved/carrier/delivered timestamps | 不一致 0 |
| orders with >1 distinct seller | 不一致 0 |
| purchase_ts year/month equal order_year/order_month | 不一致 0 |

可验证关联字段（经已校验主键到达，不另计有效字段）：

| 字段 | 经由 | 覆盖 |
|---|---|---|
| products.product_category | order_items.product_id | 15,639 / 15,639 |
| customers.customer_state / customer_region | orders.customer_id | 9,311 / 9,311 |
| sellers.seller_state / seller_region | order_items.seller_id | 15,639 / 15,639 |
| reviews.review_score | reviews.order_id -> orders | 6,190 / 9,311；只有部分订单有评价（不是缺失值，是没有评价） |
| payments.payment_type / payment_installments | payments.order_id -> orders | 9,311 / 9,311 |

## 3. 逐列字典

列含义：原始名、标准名、类型、含义、可空（实测空值数）、单位、角色、是否计有效字段、入模规则、时间语义与备注。来源一律为同一合成包的对应表。

### customers

| 原始名 | 标准名 | 类型 | 含义 | 空值 | 单位 | 角色 | 有效 | 入模 | 时间语义 / 备注 |
|---|---|---|---|---:|---|---|---|---|---|
| customer_id | customer_id | string | 客户标识 | 0 |  | 主键 |  | 连接键 | 在 orders.customer_id 处计有效字段 |
| customer_unique_id | customer_unique_id | string | 客户稳定身份标识；实测与 customer_id 一一对应 | 0 |  | 属性 |  | 连接键 | 与 customer_id 1:1，不提供额外信息，不计有效字段 |
| customer_state | customer_state | string | 客户所在州（美国州缩写） | 0 |  | 属性 | 是 | 可用 |  |
| customer_city | customer_city | string | 客户所在城市 | 0 |  | 属性 |  | 可用 | 合成城市，基数高，只作展示 |
| customer_region | customer_region | string | 客户所在大区（人口普查口径四区） | 0 |  | 属性 | 是 | 可用 |  |
| customer_zip_prefix | customer_zip_prefix | string | 五位邮编前缀，按字符串保留前导零 | 0 |  | 属性 |  | 禁止入模 | 近似唯一，不作分析维度 |
| customer_segment | customer_segment | string | 生成器预设的客户分群 | 0 |  | 生成器标签 |  | 禁止入模 | 生成器标签：不作特征、不作真值 |
| customer_lifecycle_stage | customer_lifecycle_stage | string | 生成器预设的生命周期阶段 | 0 |  | 生成器标签 |  | 禁止入模 | 期末快照值，不知道变化时间；生成器标签且为期末值；生命周期状态由 EDA-05 按规则重算 |
| created_at | customer_created_date | date | 合成客户建档日期 | 0 |  | 主数据时间 |  | 可用 | 日粒度；只能称“合成建档”，不是真实注册或获客时间；源值无时区；按 UTC 解释是工程假设（D011）；范围 2024-01-01 00:00:00 ~ 2024-06-29 00:00:00 |

### sellers

| 原始名 | 标准名 | 类型 | 含义 | 空值 | 单位 | 角色 | 有效 | 入模 | 时间语义 / 备注 |
|---|---|---|---|---:|---|---|---|---|---|
| seller_id | seller_id | string | 卖家标识 | 0 |  | 主键 |  | 连接键 | 在 order_items.seller_id 处计有效字段 |
| seller_state | seller_state | string | 卖家所在州 | 0 |  | 属性 |  | 可用 |  |
| seller_city | seller_city | string | 卖家所在城市 | 0 |  | 属性 |  | 可用 |  |
| seller_region | seller_region | string | 卖家所在大区 | 0 |  | 属性 |  | 可用 |  |
| seller_zip_prefix | seller_zip_prefix | string | 卖家邮编前缀，按字符串保留前导零 | 0 |  | 属性 |  | 禁止入模 |  |
| seller_segment | seller_segment | string | 生成器预设的卖家分群 | 0 |  | 生成器标签 |  | 禁止入模 |  |
| seller_quality_score | seller_quality_score | double | 生成器的卖家质量参数（0–1） | 0 | ratio 0-1 | 生成器标签 |  | 禁止入模 | 范围 0.45 ~ 0.988 |
| seller_fulfillment_capacity | seller_fulfillment_capacity | double | 生成器的履约能力参数（0–1） | 0 | ratio 0-1 | 生成器标签 |  | 禁止入模 | 范围 0.2 ~ 0.8185 |
| seller_active_flag | seller_active_flag | boolean | 期末是否活跃 | 0 |  | 属性 |  | 禁止入模 | 期末快照值，不知道变化时间 |
| created_at | seller_created_date | date | 合成卖家创建日期（全部为 2024-01-01） | 0 |  | 主数据时间 |  | 可用 | 日粒度；单一值；源值无时区；按 UTC 解释是工程假设（D011）；范围 2024-01-01 00:00:00 ~ 2024-01-01 00:00:00 |
| deactivated_at | seller_deactivated_date | date | 卖家停用日期（本场景全部为空） | 800 |  | 主数据时间 |  | 禁止入模 | 全空；源值无时区；按 UTC 解释是工程假设（D011） |

### products

| 原始名 | 标准名 | 类型 | 含义 | 空值 | 单位 | 角色 | 有效 | 入模 | 时间语义 / 备注 |
|---|---|---|---|---:|---|---|---|---|---|
| product_id | product_id | string | 商品标识 | 0 |  | 主键 |  | 连接键 | 在 order_items.product_id 处计有效字段 |
| product_category | product_category | string | 商品品类（16 类，英文通用名） | 0 |  | 属性 | 是 | 可用 |  |
| product_name | product_name | string | 通用无品牌商品名 | 0 |  | 属性 |  | 可用 | 每个商品唯一，只作展示 |
| product_weight_g | product_weight_g | integer | 商品重量 | 0 | g | 属性 |  | 可用 | 范围 50 ~ 30000 |
| product_length_cm | product_length_cm | double | 商品长度 | 0 | cm | 属性 |  | 可用 | 范围 4.0 ~ 21.8 |
| product_height_cm | product_height_cm | double | 商品高度 | 0 | cm | 属性 |  | 可用 | 范围 2.0 ~ 16.4 |
| product_width_cm | product_width_cm | double | 商品宽度 | 0 | cm | 属性 |  | 可用 | 范围 3.0 ~ 17.8 |
| product_price_base_usd | product_price_base_usd | decimal(12,2) | 商品基准价（目录价，不是成交价） | 0 | USD | 属性 |  | 可用 | 范围 5.93 ~ 1176.47 |
| created_at | product_created_date | date | 商品创建日期（全部为 2024-01-01） | 0 |  | 主数据时间 |  | 可用 | 日粒度；单一值；源值无时区；按 UTC 解释是工程假设（D011）；范围 2024-01-01 00:00:00 ~ 2024-01-01 00:00:00 |

### seller_products

| 原始名 | 标准名 | 类型 | 含义 | 空值 | 单位 | 角色 | 有效 | 入模 | 时间语义 / 备注 |
|---|---|---|---|---:|---|---|---|---|---|
| seller_product_id | seller_product_id | string | 卖家上架商品标识 | 0 |  | 主键 |  | 连接键 |  |
| seller_id | seller_id | string | 上架卖家 | 0 |  | 外键 |  | 连接键 |  |
| product_id | product_id | string | 上架商品 | 0 |  | 外键 |  | 连接键 |  |
| seller_price_usd | seller_price_usd | decimal(12,2) | 卖家标价（不是成交价） | 0 | USD | 属性 |  | 可用 | 范围 5.72 ~ 1187.35 |
| listing_created_at | listing_created_date | date | 上架日期（全部为 2024-01-01） | 0 |  | 主数据时间 |  | 可用 | 日粒度；单一值；源值无时区；按 UTC 解释是工程假设（D011）；范围 2024-01-01 00:00:00 ~ 2024-01-01 00:00:00 |
| listing_active_flag | listing_active_flag | boolean | 期末是否仍上架 | 0 |  | 属性 |  | 禁止入模 | 期末快照值，不知道变化时间 |
| scenario_name | scenario_name | string | 生成场景名（全部 baseline） | 0 |  | 场景元数据 |  | 禁止入模 |  |

### orders

| 原始名 | 标准名 | 类型 | 含义 | 空值 | 单位 | 角色 | 有效 | 入模 | 时间语义 / 备注 |
|---|---|---|---|---:|---|---|---|---|---|
| order_id | order_id | string | 订单标识 | 0 |  | 主键 | 是 | 连接键 |  |
| customer_id | customer_id | string | 下单客户 | 0 |  | 外键 | 是 | 连接键 |  |
| order_status | order_status | string | 订单最终状态：delivered / shipped / processing / cancelled | 0 |  | 属性 | 是 | 仅口径/标签 | 期末快照值，不知道变化时间；没有取消发生时间；只用于指标口径（DATA-08），不作特征。实测与时间戳严格对应：cancelled=无审批，processing=已审批未交承运，shipped=已交承运未送达，delivered=已送达；as_of 时的非取消状态可由时间戳重建，取消时间未知 |
| order_purchase_timestamp | purchase_ts | timestamp | 下单时间；订单事实的业务时间 | 0 |  | 事件时间 | 是 | 按时点可用 | 秒粒度；事件时间；下单时即可得；源值无时区；按 UTC 解释是工程假设（D011）；范围 2024-01-01 09:06:48 ~ 2026-11-07 22:15:48 |
| order_approved_at | approved_ts | timestamp | 支付审批时间 | 194 |  | 事件时间 |  | 按时点可用 | 秒粒度；事件发生时可得；截止后发生的在 observed 视图置空；历史层空值 194 条全部是 cancelled；源值无时区；按 UTC 解释是工程假设（D011）；范围 2024-01-01 12:24:55 ~ 2026-11-08 21:05:07 |
| order_estimated_delivery_date | estimated_delivery_date | date | 预计送达日期（计划值） | 0 |  | 计划时间 |  | 禁止入模 | 日粒度；计划值，生成/告知时点未知，暂不开放为特征；源值无时区；按 UTC 解释是工程假设（D011）；范围 2024-01-08 00:00:00 ~ 2026-11-16 00:00:00 |
| order_delivered_carrier_date | carrier_handoff_ts | timestamp | 交给承运商时间 | 477 |  | 事件时间 |  | 按时点可用 | 秒粒度；截止后发生的在 observed 视图置空；历史层空值=processing 或 cancelled；源值无时区；按 UTC 解释是工程假设（D011）；范围 2024-01-03 12:24:55 ~ 2026-11-11 15:03:52 |
| order_delivered_customer_date | delivered_ts | timestamp | 实际送达客户时间 | 656 |  | 事件时间 | 是 | 按时点可用 | 秒粒度；截止后发生的在 observed 视图置空；历史层空值=shipped、processing 或 cancelled；源值无时区；按 UTC 解释是工程假设（D011）；范围 2024-01-08 11:33:00 ~ 2026-11-21 14:05:07 |
| order_year | order_year | integer | 下单年（由下单时间拆出） | 0 |  | 日历 |  | 禁止入模 | 日期拆分列，不计有效字段；数仓用日期维代替；范围 2024 ~ 2026 |
| order_quarter | order_quarter | integer | 下单季度（由下单时间拆出） | 0 |  | 日历 |  | 禁止入模 | 日期拆分列，不计有效字段；数仓用日期维代替；范围 1 ~ 4 |
| order_month | order_month | integer | 下单月（由下单时间拆出） | 0 |  | 日历 |  | 禁止入模 | 日期拆分列，不计有效字段；数仓用日期维代替；范围 1 ~ 12 |
| order_week | order_week | integer | ISO 周（由下单时间拆出） | 0 |  | 日历 |  | 禁止入模 | 日期拆分列，不计有效字段；数仓用日期维代替；范围 1 ~ 52 |
| order_day_of_week | order_day_of_week | integer | 星期（周一=0）（由下单时间拆出） | 0 |  | 日历 |  | 禁止入模 | 日期拆分列，不计有效字段；数仓用日期维代替；范围 0 ~ 6 |
| is_weekend | is_weekend | boolean | 是否周末下单（由下单时间推出） | 0 |  | 日历 |  | 禁止入模 | 用日期维代替 |
| is_holiday_period | is_holiday_period | boolean | 是否生成器设定的节日期间 | 0 |  | 日历 |  | 禁止入模 | 生成器设定的日历标记 |
| is_promotion_period | is_promotion_period | boolean | 是否生成器设定的促销期间 | 0 |  | 日历 |  | 禁止入模 | 生成器设定，不是真实营销记录 |
| scenario_name | scenario_name | string | 生成场景名（全部 baseline） | 0 |  | 场景元数据 |  | 禁止入模 |  |

### order_items

| 原始名 | 标准名 | 类型 | 含义 | 空值 | 单位 | 角色 | 有效 | 入模 | 时间语义 / 备注 |
|---|---|---|---|---:|---|---|---|---|---|
| order_id | order_id | string | 所属订单 | 0 |  | 外键 |  | 连接键 |  |
| order_item_id | order_item_seq | integer | 订单内明细序号（从 1 开始） | 0 |  | 主键 |  | 连接键 | 不是数量；不假设每行 1 件；范围 1 ~ 5 |
| seller_product_id | seller_product_id | string | 购买的上架商品 | 0 |  | 外键 |  | 连接键 |  |
| product_id | product_id | string | 购买的商品 | 0 |  | 外键 | 是 | 连接键 |  |
| seller_id | seller_id | string | 履约卖家 | 0 |  | 外键 | 是 | 连接键 |  |
| item_price_usd | item_price_usd | decimal(12,2) | 明细商品金额（成交价，不含运费） | 0 | USD | 度量 | 是 | 按时点可用 | 范围 5.42 ~ 1325.46 |
| shipping_cost_usd | item_shipping_usd | decimal(12,2) | 分摊到明细的运费 | 0 | USD | 度量 | 是 | 按时点可用 | 范围 3.5 ~ 31.27 |
| item_total_usd | item_total_usd | decimal(12,2) | 商品金额＋运费（实测逐行相等） | 0 | USD | 派生 |  | 按时点可用 | 由前两列相加，不计有效字段；范围 11.47 ~ 1333.17 |
| scenario_name | scenario_name | string | 生成场景名 | 0 |  | 场景元数据 |  | 禁止入模 |  |

### payments

| 原始名 | 标准名 | 类型 | 含义 | 空值 | 单位 | 角色 | 有效 | 入模 | 时间语义 / 备注 |
|---|---|---|---|---:|---|---|---|---|---|
| order_id | order_id | string | 支付的订单 | 0 |  | 外键 |  | 连接键 |  |
| payment_sequential | payment_seq | integer | 订单内支付序号（1–2） | 0 |  | 主键 |  | 连接键 | 范围 1 ~ 2 |
| payment_type | payment_type | string | 支付方式（5 类） | 0 |  | 属性 | 是 | 按时点可用 | 没有支付时间；按下单时可得的工程假设使用 |
| payment_installments | payment_installments | integer | 分期数 | 0 | count | 属性 | 是 | 按时点可用 | 同上；范围 1 ~ 12 |
| payment_value_usd | payment_value_usd | decimal(12,2) | 支付金额；与订单明细合计对账 | 0 | USD | 度量 | 是 | 仅口径/标签 | 只作对账，不称已实现收入或退款；范围 4.7 ~ 1672.39 |
| scenario_name | scenario_name | string | 生成场景名 | 0 |  | 场景元数据 |  | 禁止入模 |  |

### shipping

| 原始名 | 标准名 | 类型 | 含义 | 空值 | 单位 | 角色 | 有效 | 入模 | 时间语义 / 备注 |
|---|---|---|---|---:|---|---|---|---|---|
| order_id | order_id | string | 物流对应订单（与订单 1:1） | 0 |  | 主键 |  | 连接键 |  |
| seller_state | origin_state | string | 发货州（冗余拷贝） | 0 |  | 冗余拷贝 |  | 可用 | 以 sellers 主数据为准 |
| customer_state | destination_state | string | 收货州（冗余拷贝） | 0 |  | 冗余拷贝 |  | 可用 | 以 customers 主数据为准 |
| seller_region | origin_region | string | 发货大区（冗余拷贝） | 0 |  | 冗余拷贝 |  | 可用 |  |
| customer_region | destination_region | string | 收货大区（冗余拷贝） | 0 |  | 冗余拷贝 |  | 可用 |  |
| shipping_distance_band | shipping_distance_band | string | 距离档：same_state / same_region / cross_region / remote | 0 |  | 属性 |  | 按时点可用 |  |
| shipping_zone | shipping_zone | string | 合成线路区（zone_1–4） | 0 |  | 属性 |  | 按时点可用 |  |
| estimated_delivery_days | estimated_delivery_days | integer | 预计送达天数 | 0 | days | 属性 | 是 | 禁止入模 | 计划值，可得时点未知，同 estimated_delivery_date；范围 4 ~ 13 |
| actual_delivery_days | actual_delivery_days | integer | 实际送达天数；源文本为 x.0 | 656 | days | 派生 |  | 按时点可用 | 送达后才可得；按 delivered_ts < as_of 截断；由下单与送达时间推出；范围 3 ~ 17 |
| delivery_delay_days | delivery_delay_days | integer | 晚于预计的天数；源文本为 x.0 | 656 | days | 派生 |  | 按时点可用 | 送达后才可得；派生值，不计有效字段；范围 0 ~ 5 |
| late_delivery_flag | late_delivery_flag | boolean | 是否晚于预计送达 | 0 |  | 派生 |  | 按时点可用 | 送达后才可得；未送达订单为 False 不代表准时；派生值 |
| shipping_cost_usd | order_shipping_usd | decimal(12,2) | 订单运费；实测等于该单明细运费之和 | 0 | USD | 度量 |  | 按时点可用 | 与明细运费重复，不计有效字段；范围 3.5 ~ 82.75 |
| scenario_name | scenario_name | string | 生成场景名 | 0 |  | 场景元数据 |  | 禁止入模 |  |

### reviews

| 原始名 | 标准名 | 类型 | 含义 | 空值 | 单位 | 角色 | 有效 | 入模 | 时间语义 / 备注 |
|---|---|---|---|---:|---|---|---|---|---|
| review_id | review_id | string | 评价标识 | 0 |  | 主键 |  | 连接键 |  |
| order_id | order_id | string | 被评价订单（每单至多一条） | 0 |  | 外键 |  | 连接键 |  |
| review_score | review_score | integer | 评价分数 1–5 | 0 | score 1-5 | 度量 | 是 | 按时点可用 | 按评价创建日可得的工程假设（D011）；范围 1 ~ 5 |
| review_creation_date | review_created_date | date | 评价创建日期 | 0 |  | 事件时间 |  | 按时点可用 | 日粒度；截止后创建的评价不进入 observed 视图；源值无时区；按 UTC 解释是工程假设（D011）；范围 2024-01-11 00:00:00 ~ 2026-11-26 00:00:00 |
| review_answer_timestamp | review_answered_ts | timestamp | 评价答复时间 | 0 |  | 事件时间 |  | 按时点可用 | 秒粒度；截止后发生的在 observed 视图置空；源值无时区；按 UTC 解释是工程假设（D011）；范围 2024-01-11 09:00:00 ~ 2026-11-27 04:00:00 |
| review_sentiment_label | review_sentiment_label | string | 情感标签（由分数映射） | 0 |  | 生成器标签 |  | 禁止入模 | 由分数推出，不独立 |
| satisfaction_risk_flag | satisfaction_risk_flag | boolean | 分数为 1 或 2 | 0 |  | 派生 |  | 禁止入模 | 由分数推出 |
| scenario_name | scenario_name | string | 生成场景名 | 0 |  | 场景元数据 |  | 禁止入模 |  |

### calendar

| 原始名 | 标准名 | 类型 | 含义 | 空值 | 单位 | 角色 | 有效 | 入模 | 时间语义 / 备注 |
|---|---|---|---|---:|---|---|---|---|---|
| date | date | date | 日历日期 | 0 |  | 主键 |  | 连接键 | 日粒度；覆盖 2024-01-01 至截止前一日；范围 2024-01-01 00:00:00 ~ 2026-11-07 00:00:00 |
| year | year | integer | 年 | 0 |  | 日历 |  | 可用 | 日期维属性；范围 2024 ~ 2026 |
| quarter | quarter | integer | 季度 | 0 |  | 日历 |  | 可用 | 日期维属性；范围 1 ~ 4 |
| month | month | integer | 月 | 0 |  | 日历 |  | 可用 | 日期维属性；范围 1 ~ 12 |
| month_name | month_name | string | 月名 | 0 |  | 日历 |  | 可用 | 日期维属性 |
| week | week | integer | ISO 周 | 0 |  | 日历 |  | 可用 | 日期维属性；范围 1 ~ 52 |
| day_of_week | day_of_week | integer | 星期（周一=0） | 0 |  | 日历 |  | 可用 | 日期维属性；范围 0 ~ 6 |
| day_name | day_name | string | 星期名 | 0 |  | 日历 |  | 可用 | 日期维属性 |
| is_weekend | is_weekend | boolean | 是否周末 | 0 |  | 日历 |  | 可用 | 日期维属性 |
| is_holiday_period | is_holiday_period | boolean | 生成器节日期间 | 0 |  | 日历 |  | 可用 | 日期维属性 |
| is_promotion_period | is_promotion_period | boolean | 生成器促销期间 | 0 |  | 日历 |  | 可用 | 日期维属性 |
| season | season | string | 气象季节 | 0 |  | 日历 |  | 可用 | 日期维属性 |

## 4. 数据中没有的内容

购买数量、退款金额与时间、取消发生时间、订单状态历史、支付时间、获客渠道、浏览/加购/曝光、营销触达与同意、优惠券、成本与毛利、库存、投诉、年龄与性别。页面和 AI 回答遇到这些问题返回 `capability_not_supported`。

## 5. 禁止的假设

- 把 order_item_id 当数量或假设每行 1 件
- 把 order_status 最终状态当作下单时可知
- 把生成器标签（customer_segment、customer_lifecycle_stage、review_sentiment_label、seller_* 参数）当特征或真值
- 把 payment_value_usd 称为已实现收入或退款后收入
- 虚构渠道、毛利、库存、营销同意或投诉
- 把合成建档日期称为真实注册或获客时间
- 把合成数据结论写成真实企业或真实顾客行为
- 拼接其他数据集的用户 ID

## 6. 留给下游

- DATA-08：有效购买（delivered/shipped/processing 是否计入）、取消处理、金额是否含运费
- ML-01：预测母体与 30 天标签
- metrics：contracts/metrics.json 仍为 UCI 草案，由 DATA-08 改写
