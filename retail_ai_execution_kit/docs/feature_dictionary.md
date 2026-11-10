# 特征字典（ML-03，`features-v1`）

- 代码：`src/retail_bi/features/customer_features.py`（`FEATURES` 列表即模型输入顺序）；测试：`tests/model/test_features.py`
- 样本：`target-v1`（客户 × 每周一 as_of，90 天母体，30 天标签），见 `docs/model_target.md`
- **可见订单**：下单时间 < as_of 且审批时间 < as_of 的有效订单。所有窗口左闭右开，以 as_of 为右端点。数据完全合成。

| # | 特征 | 公式 | 窗口 | 空值 | 来源 |
|---:|---|---|---|---|---|
| 1 | recency_days | as_of − 最近一次可见购买的下单时间（天） | 全部可见历史 | 不会为空（母体至少一单） | fact_order |
| 2 | tenure_days | as_of − 首次可见购买时间（天） | 全部可见历史 | 不会为空 | fact_order |
| 3–5 | orders_7d / orders_30d / orders_90d | 可见订单数 | [as_of−7/30/90 天, as_of) | 0 | fact_order |
| 6–8 | merch_7d / merch_30d / merch_90d | 可见订单商品金额（USD，不含运费） | 同上 | 0 | fact_order |
| 9 | orders_all_time | 可见订单数 | 全部可见历史 | 不会为空 | fact_order |
| 10 | merch_all_time | 可见订单商品金额 | 全部可见历史 | 不会为空 | fact_order |
| 11 | aov_all_time | merch_all_time / orders_all_time | 全部可见历史 | 不会为空 | fact_order |
| 12 | lines_per_order | 可见订单平均明细行数 | 全部可见历史 | 不会为空 | fact_order |
| 13 | active_days_90d | 有购买的不同日期数 | [as_of−90 天, as_of) | ≥1 | fact_order |
| 14 | gap_mean_days | 相邻两次可见购买的平均间隔（天） | 全部可见历史 | **只买过一次时为空**，见 has_gap | fact_order |
| 15 | gap_last_days | 最近两次可见购买的间隔（天） | 全部可见历史 | 同上 | fact_order |
| 16 | has_gap | 至少两次可见购买 = 1 | — | 0/1 | 派生 |
| 17 | categories_all_time | 购买过的不同品类数 | 全部可见历史 | ≥1 | fact_order_line + dim_product |
| 18 | categories_90d | 不同品类数 | [as_of−90 天, as_of) | ≥1 | 同上 |
| 19 | products_90d | 不同商品数 | [as_of−90 天, as_of) | ≥1 | fact_order_line |
| 20 | installment_share | 可见订单中分期数 > 1 的比例 | 全部可见历史 | 不会为空 | fact_payment |
| 21 | credit_card_share | 可见订单中用过信用卡的比例 | 全部可见历史 | 不会为空 | fact_payment |
| 22 | delivered_count | 送达时间 < as_of 的可见订单数 | 全部可见历史 | 0 | fact_order |
| 23 | late_by_date_share | 上述已送达订单中按日期晚到的比例 | 全部可见历史 | **没有已送达订单时为空**（delivered_count = 0） | fact_order（late_by_date） |
| 24 | last_review_score | 创建日期 < as_of 日期的最近一条评价分数 | 全部可见历史 | **没有评价时为空**，见 has_review | fact_order（评价） |
| 25 | has_review | 有上述评价 = 1 | — | 0/1 | 派生 |
| 26–29 | region_midwest / northeast / south / west | 客户大区独热编码 | 静态 | 0/1 | dim_customer |
| 30 | as_of_month | as_of 所在月份（1–12） | — | 不会为空 | 日历 |

## 空值策略

- 空值都有业务含义（没有第二次购买、没有已送达订单、没有评价），不在特征层填补，并配有指示列（has_gap、delivered_count、has_review）。
- LightGBM 直接处理空值；逻辑回归在 ML-06 中用**训练期中位数**填补并保留参数（DATA-10 的 TrainOnlyFit 规则）。

## 时点可得性

- 订单：下单与审批都早于 as_of；送达：送达时间早于 as_of；评价：创建日期早于 as_of 所在日期（日粒度，当天的评价不用）。
- 支付方式与分期没有支付时间，按“下单时即可得”的工程假设使用（D011）。
- 商品品类与客户大区是主数据，全部在 2024-01-01（早于任何 as_of）创建。
- 实测：在 3 个 as_of 上把之后的订单、审批、送达和评价全部删除或置空后重算，30 个特征与原值完全一致（`tests/model/test_features.py`）。

## 不使用的信息

- `customer_id`（只作主键，不作特征）。
- 最终订单状态、取消（没有取消发生时间，按时点无法使用）、截止后才发生的任何事件或金额。
- 退货与退款：数据中没有，因此没有“已发生退货”特征。
- 生成器标签：客户分群、生命周期阶段、评价情感、卖家质量与产能参数；规则生命周期状态和 RFM 聚类也不作为特征（ML-05 若作特征必须只在训练期拟合）。
- 预计送达日期（生成和告知时点未知）。
