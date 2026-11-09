# DATA-02 本地合成数据实读核验

全量读取本地 ZIP 的 12 张 CSV 与历史目录的 10 张 CSV；未下载其他候选。数据完全合成，用户已授权先行开发，教师 D001/D006 仍待确认。

| 表 | 原始行数 | 历史行数 | 列数 |
|---|---:|---:|---:|
| customers | 3647 | 3647 | 9 |
| products | 8000 | 8000 | 9 |
| reviews | 6528 | 6190 | 8 |
| orders | 10000 | 9311 | 17 |
| calendar | 1096 | 1042 | 12 |
| payments | 10750 | 10010 | 6 |
| sellers | 800 | 800 | 11 |
| order_items | 16784 | 15639 | 9 |
| seller_products | 13966 | 13966 | 7 |
| shipping | 10000 | 9311 | 13 |

## 核验结果

- 断言：`{"zip_crc_passed": true, "history_matches_declared_order_cutoff": false, "raw_keys_links_amounts_temporal_order_checks_zero": true, "historical_keys_links_amounts_temporal_order_checks_zero": true, "source_unchanged": true}`。
- 原始 ZIP：1310750 字节；SHA-256 `d50ee64a0478d8ae8df1b8b66521671a4911e19f911ae86196452a668f917a16`。
- 主键、外键、明细与上架商品/商家一致性、金额（Decimal 精确对账）、购买不早于客户/商品/上架创建的异常计数见 JSON；不把脚本退出 0 当全部业务口径正确。
- 历史 CSV 与按既有下单截止时间从原包重建的记录逐行多重集比较，含重复次数；原始目录读取前后哈希一致。差异详情见下面，不能据此宣称历史目录无损。
- 已发现字段转换差异：`{"customers": {"customer_zip_prefix": {"changed_rows": 334, "leading_zero_loss_rows": 334}}, "sellers": {"seller_zip_prefix": {"changed_rows": 75, "leading_zero_loss_rows": 75}}}`。客户/商家邮编前导零丢失，不能直接视为无损导入；后续从原始 ZIP 按字符串重新导入并重建历史层，不在本阶段修改原包。

## 字段与时间

- 有订单/客户/商品/商家标识、商品金额/运费/支付金额；USD。没有独立数量列，order_item_id 是明细序号，不能把它当数量，也不擅自补 quantity=1。
- 不以日期拆列、scenario_name 或模拟生命周期标签凑有效业务字段。跨订单、客户、商品、明细有超过8个有意义的模拟源字段，是否满足课程“真实原始数据”仍待教师确认。
- 源时间戳没有时区；既有历史处理将其按 UTC 解释，本轮沿用以复算，不认定为发布者已声明时区。
- 历史下单截止不代表其他信息截至观察时点可得：实际审批、发货、收货、评价需按可得时点截断。预计送达日期是计划值，晚于截止本身不等于泄漏，还需验证其生成/可得时点。

| 表.字段 | 最早 | 最晚 | 空值 | 非空解析失败 | 截止后/含截止 |
|---|---|---|---:|---:|---:|
| customers.created_at | 2024-01-01T00:00:00+00:00 | 2024-06-29T00:00:00+00:00 | 0 | 0 | 0 |
| products.created_at | 2024-01-01T00:00:00+00:00 | 2024-01-01T00:00:00+00:00 | 0 | 0 | 0 |
| reviews.review_creation_date | 2024-01-11T00:00:00+00:00 | 2026-11-26T00:00:00+00:00 | 0 | 0 | 94 |
| reviews.review_answer_timestamp | 2024-01-11T09:00:00+00:00 | 2026-11-27T04:00:00+00:00 | 0 | 0 | 101 |
| orders.order_purchase_timestamp | 2024-01-01T09:06:48+00:00 | 2026-11-07T22:15:48+00:00 | 0 | 0 | 0 |
| orders.order_approved_at | 2024-01-01T12:24:55+00:00 | 2026-11-08T21:05:07+00:00 | 194 | 0 | 4 |
| orders.order_estimated_delivery_date | 2024-01-08T00:00:00+00:00 | 2026-11-16T00:00:00+00:00 | 0 | 0 | 96 |
| orders.order_delivered_carrier_date | 2024-01-03T12:24:55+00:00 | 2026-11-11T15:03:52+00:00 | 477 | 0 | 28 |
| orders.order_delivered_customer_date | 2024-01-08T11:33:00+00:00 | 2026-11-21T14:05:07+00:00 | 656 | 0 | 94 |
| calendar.date | 2024-01-01T00:00:00+00:00 | 2026-11-07T00:00:00+00:00 | 0 | 0 | 0 |
| sellers.created_at | 2024-01-01T00:00:00+00:00 | 2024-01-01T00:00:00+00:00 | 0 | 0 | 0 |
| sellers.deactivated_at | None | None | 800 | 0 | 0 |
| seller_products.listing_created_at | 2024-01-01T00:00:00+00:00 | 2024-01-01T00:00:00+00:00 | 0 | 0 | 0 |

## 范围和限制

- Synthetic fields do not prove real industry data or real model performance.
- Historical order cutoff does not censor later approvals/deliveries/reviews or end-of-period customer/listing attributes; must enforce as_of availability downstream.
- No clickstream/cart/ad attribution; preassigned lifecycle/segment labels cannot be prediction truth.
- Website ZIP license remains unconfirmed per DATA-01.
- Type checks apply generator dictionary to actual values; all values loaded as strings to preserve IDs and precision.

## 复现

`.venv/bin/python src/retail_bi/data/candidate_probe.py --source ../ecommerce-sample-database-100k --out reports/data`

脚本只读源文件；输出为 JSON 与本报告。字段逐列类型、缺失、不同值数量、日期样本、字节数与哈希均见 candidate_probe.json。读取/解析异常非零退出；默认退出0仅表示探查报告成功生成，数据问题仍保留在 assertions 中。--strict 在任何数据断言不通过时返回1；日志均保留。此脚本独立按路径执行，尚未建立可安装的 retail_bi 公共包，暂不改环境锁；在后续接口实现时再完成包安装与环境复核。
