# 唯一主数据路线（DATA-03）

- 版本：v1，2026-11-10，claude-opus-5-5 执行并自审
- 对应要求：C06、C07、U01、Q01；验收规格哈希见 `evidence/DATA-03/` 主证据
- 数字全部取自 `reports/data/dataset_selection_facts.json`（由 `evidence/DATA-03/route_facts.py` 从 DATA-05 工程工作层实际计算），不手填。

## 1. 结论

**工程主数据冻结为：合成电商市场交易包 `baseline_10000_seed42`，走交易路线。**

| 项 | 冻结值 |
|---|---|
| 源文件 | `../ecommerce-sample-database-100k/01_source/baseline_10000_seed42.zip`，SHA-256 `d50ee64a0478d8ae8df1b8b66521671a4911e19f911ae86196452a668f917a16` |
| 工程输入 | DATA-05 的 `engineering-import-v1` 工作层（从原 ZIP 按字符串重建，清单 `reports/data/source_manifest.json`） |
| 观察截止 | `2026-11-08T00:00:00Z`（不含）；源时间没有时区，按 UTC 解释是工程假设 |
| 数据性质 | **完全合成**，生成器运行时间 2026-07-21；不是真实企业或真实顾客 |
| 币种 | USD |
| 研究范围 | 截止前的全部历史：订单 9,311、订单明细 15,639、支付 10,010、客户 3,647、商品 8,000、卖家 800、物流 9,311、评价 6,190；下单月份 2024-01 至 2026-11，共 35 个月 |

### 授权依据（不是教师答复）

- 用户 2026-11-10 原话：“不需要考试口径，你就当已经确认了”，登记为 `ops/DECISIONS.md` D012。此前 D010、D011 已授权先用这份数据推进工程。
- 本结论是**按用户授权的工作假设**冻结的工程主数据。没有收到教师对 D001（数据时效）或 D006（合成数据能否作为原始数据）的实际答复，任何报告都不能写成“教师已确认”。
- 课程原文 C06 的较严格时效条款没有被改写。按事件时间，模拟订单有一部分落在 2026 年以后，但这些事件是模拟的，不是真实采集（`docs/data_candidates.md` 第 2 节）。

## 2. 交易路线还是行为路线

**选交易路线。**

| 候选 | 处理 | 理由 |
|---|---|---|
| B 合成交易包（本次选定） | 主数据 | 有订单、明细、金额、状态、支付、物流、评价，能支持 RFM、cohort 留存、30 天复购标签和星型模型；已完成全量实读（DATA-02）和工程重建（DATA-05） |
| A UCI Online Retail II | 不采用，不下载 | 2009–2011 年数据，需要 D001 例外；用户已决定按合成数据推进 |
| C Cosmetics 行为日志 | 不采用 | 行为路线；没有订单号和数量，2019–2020 年数据；会让页面和模型全部改为代理指标 |
| D T-ECD | 不采用 | 只有相对天数，没有绝对日期，原本就只作背景 |

**不拼接其他来源的用户 ID。** 所有标识都来自同一个包内部。实测 7 条内部关联全部没有孤儿记录：

| 关联 | 孤儿行数 |
|---|---:|
| orders.customer_id → customers | 0 |
| order_items.order_id → orders | 0 |
| order_items.product_id → products | 0 |
| order_items.seller_id → sellers | 0 |
| payments.order_id → orders | 0 |
| shipping.order_id → orders | 0 |
| reviews.order_id → orders | 0 |

## 3. 有效业务字段核验（至少 8 个）

只算源字段本身。不算拆出来的日期列（`order_year`、`order_month`、`order_week` 等）、`scenario_name`，也不算生成器打的标签。

| # | 字段 | 含义 | 非空 / 行数 | 不同值 |
|---:|---|---|---:|---:|
| 1 | orders.order_id | 订单标识 | 9,311 / 9,311 | 9,311 |
| 2 | orders.customer_id | 下单客户 | 9,311 / 9,311 | 3,356 |
| 3 | orders.order_status | 订单最终状态 | 9,311 / 9,311 | 4 |
| 4 | orders.order_purchase_timestamp | 下单时间 | 9,311 / 9,311 | 9,310 |
| 5 | orders.order_delivered_customer_date | 实际送达时间 | 8,655 / 9,311 | 8,655 |
| 6 | order_items.product_id | 明细商品 | 15,639 / 15,639 | 5,418 |
| 7 | order_items.seller_id | 明细卖家 | 15,639 / 15,639 | 766 |
| 8 | order_items.item_price_usd | 明细商品金额 | 15,639 / 15,639 | 10,133 |
| 9 | order_items.shipping_cost_usd | 明细运费 | 15,639 / 15,639 | 1,431 |
| 10 | products.product_category | 商品品类 | 8,000 / 8,000 | 16 |
| 11 | payments.payment_type | 支付方式 | 10,010 / 10,010 | 5 |
| 12 | payments.payment_installments | 分期数 | 10,010 / 10,010 | 12 |
| 13 | payments.payment_value_usd | 支付金额 | 10,010 / 10,010 | 8,489 |
| 14 | customers.customer_state | 客户所在州 | 3,647 / 3,647 | 51 |
| 15 | customers.customer_region | 客户所在大区 | 3,647 / 3,647 | 4 |
| 16 | shipping.estimated_delivery_days | 预计送达天数 | 9,311 / 9,311 | 10 |
| 17 | reviews.review_score | 评价分数（1–5） | 6,190 / 6,190 | 5 |

共 17 个，满足“至少 8 个”。这些字段都是**模拟**的源字段，有业务含义，但不能证明真实行业规律。

明确排除、不计数也不作特征的字段：`customers.customer_segment`、`customers.customer_lifecycle_stage`、`reviews.review_sentiment_label`、`reviews.satisfaction_risk_flag`、`sellers.seller_segment`、`sellers.seller_quality_score`、`sellers.seller_fulfillment_capacity`（生成器标签或参数）；`orders.is_promotion_period`、`is_holiday_period`、`is_weekend` 及全部日期拆分列；`scenario_name`。

## 4. 路线能否支撑核心目标（实测）

**订单状态**（最终状态，不是状态历史）：已送达 8,655；处理中 283；已取消 194；已发货 179。

**规模**：最大事实表 `order_items` 15,639 行，达到契约 `size_rule` 的 10,000 条门槛。订单表截止前 9,311 行，低于 10,000，所以规模按明细行计。每月订单 84 至 383 单。

**复购结构**（排除已取消订单）：3,339 名有订单的客户中，2,586 人至少两单；相邻两单间隔的中位数 172.1 天，四分位 70.0 天和 322.6 天。

**30 天复购基率示例**（母体：as_of 前 90 天有非取消订单的客户；只用来说明可行性，**不是冻结的标签**）：

| as_of | 母体人数 | 30 天内再下单 | 比例 |
|---|---:|---:|---:|
| 2025-01-01 | 867 | 66 | 7.6% |
| 2025-04-01 | 690 | 23 | 3.3% |
| 2025-07-01 | 631 | 51 | 8.1% |
| 2025-10-01 | 673 | 58 | 8.6% |
| 2026-01-01 | 904 | 65 | 7.2% |
| 2026-04-01 | 642 | 39 | 6.1% |
| 2026-07-01 | 649 | 42 | 6.5% |
| 2026-09-01 | 651 | 47 | 7.2% |

结论：正类约 3%–9%，单个快照只有几十个正例。ML-01/ML-02 需要用多个 as_of 快照（例如按周）拼接训练样本，评估时以 PR-AUC 和校准为主，不能只看准确率。复购间隔中位数约 170 天，“30 天”窗口偏短，ML-01 冻结目标时应把这一点写进模型卡；本任务不改目标。

## 5. 被删除或调整的指标、模型和页面

### 指标（`contracts/metrics.json` 目前是 UCI 草案，由 DATA-04/DATA-08 改写）

| 原指标（UCI 草案） | 处理 | 新口径方向 |
|---|---|---|
| positive_sales：quantity×unit_price，GBP | **调整** | `item_price_usd` 之和；运费另列，是否计入由 DATA-08 冻结 |
| net_sales：正向减冲销 | **调整** | 包里没有退款金额和取消发生时间，只能“排除已取消订单”，不能称“净退款后销售额” |
| orders：invoice 去重 | **调整** | `order_id` 去重；“有效购买”是否包含处理中/已发货由 DATA-08 冻结 |
| customers：已知 customer_id | **调整** | 包里 `customer_id` 全部非空，删除“未知客户”分支 |
| aov | **调整** | 单位改为 USD/订单 |
| rfm：M 为 GBP 正向开票 | **调整** | M 为 USD 商品金额 |
| repurchase_30d / non_repurchase_30d | 保留 | 母体和标签由 ML-01 冻结 |
| 销量件数、退货件数 | **删除** | 没有数量列；`order_item_id` 只是明细序号，不能当数量，也不假设每行 1 件 |
| 按国家统计 | **删除** | 改为美国州和大区 |

新增可用的分析维度：商品品类、卖家、支付方式与分期、客户州/大区、物流时效与延迟、评价分数。物流和评价只能作诊断线索，并按 as_of 可得时点截断（DATA-05 的 observed 视图）。

### 模型

- 保留：RFM＋K-Means、规则与逻辑回归基线、LightGBM、未来 30 天复购。
- 删除：依赖“取消发票 C 前缀 / 负数量”的退货特征。
- 禁止入模：上节排除的生成器标签；订单最终状态；可得时点不明的预计送达日期；截止后才发生的审批、发货、送达、评价。
- 需注意：正类比例低（见第 4 节）。

### 页面

- 不做：浏览/加购漏斗、广告归因、渠道 ROI（本来就不在范围，`docs/business_scope.md` 第 4 节）。
- 调整：数据质量与口径页、经营指标页、生命周期页都要常驻“合成数据，非真实企业”的标注；地域分析用州/大区；“建档→首单”只能作为合成演示指标。
- 新增可选视图：品类、支付方式、物流延迟与评价分布（诊断用，不作因果结论）。

## 6. 仍然有效的限制

- **合成数据**：所有结论只说明方法在模拟数据上的表现，不代表真实市场规律和真实模型效果。
- **许可**：网站下载件没有标明数据许可；同作者仓库里的同类样例是 CC0，代码是 MIT（`docs/data_candidates.md` 第 3 节）。按 C07，原始数据只用于课程，不对外发布。
- **时区**：源时间没有时区，按 UTC 解释是工程假设。
- **状态**：`order_status` 只有最终状态，没有取消或退款的发生时间。
- **教师确认**：D001/D006 的教师答复仍然没有；GOV-04 保持非阻塞的 in_review。

## 7. 下游影响

| 任务 | 需要做的事 |
|---|---|
| DATA-04 | 按本路线把 `contracts/data_contract.json` 从 UCI 候选改写为合成交易契约，并写 `docs/data_dictionary.md`；同时把 `docs/business_scope.md` 中未选的路线 A 删去并复核（该文件不在 DATA-03 的写入范围内） |
| DATA-05 | 现有工程导入可直接复用，等 DATA-04 契约冻结后复核适配性并出新证据 |
| DATA-08 | 冻结有效购买（处理中/已发货是否计入）、取消、运费是否计入金额 |
| ML-01 | 冻结母体和标签；处理正类比例低和复购间隔偏长的问题 |
| 所有页面和报告 | 常驻“合成数据”标注；不写“教师已确认” |

## 8. 复现

```bash
.venv/bin/python evidence/DATA-03/route_facts.py --layer data/processed/engineering/d50ee64a0478d8ae-20261108T000000Z-engineering-import-v1 --out reports/data/dataset_selection_facts.json
```

工作层目录被 Git 忽略。其他机器需要先按 `reports/data/engineering_import_review.md` 从原 ZIP 重建，再运行上面的命令。
