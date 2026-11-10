# 数据预处理方法（DATA-10）

- 版本：v1，2026-11-10，claude-opus-5-5 起草并自审
- 对应要求：C08（清理、集成、归约、转换均有处理或适用性说明，保留前后对比）、Q03（预处理只在允许阶段拟合）
- 数据：合成交易包，契约 `synthetic-transaction-v1`；所有数字来自下列报告，不手填。

| 类别 | 处理 | 代码 | 前后对比与证据 |
|---|---|---|---|
| 清理 | 类型、缺失、重复、隔离 | `src/retail_bi/data/clean.py` | `reports/data/profile_before.json`、`cleaning_missing_duplicates.json` |
| 清理（业务口径） | 有效购买、取消、金额 | `src/retail_bi/data/transactions.py` | `reports/data/transaction_reconciliation.json` |
| 集成 | 来源内按主外键连接 | `src/retail_bi/data/integrate.py` | `reports/data/integration_audit.json` |
| 归约 | 列、行、粒度的取舍 | `clean.py`、`integrate.py`、下游 DW-05 | 本文第 3 节 |
| 转换 | 时间派生、对数、编码、只在训练期拟合的变换 | `src/retail_bi/data/transform.py` | `reports/data/transform_audit.json` |

## 1. 清理

| 问题 | 实测（清洗前） | 处理 | 清洗后 |
|---|---|---|---|
| 类型 | 101 列全部以文本读入 | 按契约解析为整数、DECIMAL(12,2)、布尔、日期、UTC 时间戳 | 0 行解析失败 |
| 缺失 | 6 列有空值：审批 194、交承运 477、送达 656、实际/延迟天数 656、卖家停用 800 | **不插补**。时间空值是“事件尚未发生”，与最终状态严格对应；ID 不插补，若缺失进入隔离区 | 空值数不变 |
| 重复 | 完全重复行 0；同单重复商品 779 行；同客户同日 11 组 | 保留：每行价格不同的独立明细、订单号不同的独立订单；不假定“订单+商品”唯一 | 行数不变 |
| 异常与极端值 | 负值 0、零值 0；商品金额 Q3+3IQR 以上 366 行 | 只标记不删除：合成数据中没有录入错误的依据。建模时如需截尾，用训练期拟合的阈值（第 4.2 节） | 行数不变 |
| 字段口径冲突 | 按日期晚到但生成器未标记延迟 4,268 单 | 两种延迟口径都从时间戳重算并分开命名（第 4.1 节） | — |
| 业务口径 | 取消 194 单，截止时未审批 4 单 | 有效购买 = 已审批订单；取消单列；无退款 | 有效 9,113 单 |
| 隔离 | — | 类型失败、主键重复、外键孤儿写入 `data/quarantine/`，保留源行号与原因 | 本数据 0 行 |

## 2. 集成

- 只有一个来源，不做跨来源集成，也不拼接外部用户 ID（D013）。
- 来源内整合：明细依次连接订单、商品、卖家、上架、物流（覆盖率均为 100%）和评价（左连接，覆盖 66.8% 的明细），每一步行数 15,639、商品金额 1,408,601.73 USD 不变。
- 支付是一对多（699 单有两次支付），先按订单汇总再连接。直接连接会多出 1,212 行、虚增 114,614.67 USD，审计中保留了这个反例。

## 3. 归约

| 方式 | 处理 | 理由 |
|---|---|---|
| 列（属性）归约 | 去掉不进入分析和模型的列：日期拆分列、`scenario_name`、生成器标签（客户分群、生命周期、情感、卖家参数）、冗余拷贝（物流表中的州和大区） | 不增加信息，或者属于生成器的“答案”，会造成泄漏（契约 `feature_policy`） |
| 粒度（聚合）归约 | 明细 → 订单 → 客户×as_of 快照（DW-05） | 模型样本是客户×as_of，不是交易行 |
| 行（数量）归约 | **不抽样**，全量 9,311 单 | 源 ZIP 1,310,750 字节，解压后 12 个 CSV 共 7,974,631 字节，单机全量处理只需数秒；以后若为开发抽样，按客户整体抽取并保留其完整历史，明确标为开发样本；最终建模和报告用全量，不取文件前 N 行 |
| 维度归约（PCA 等） | 不适用 | 数值特征只有十几个，彼此含义清楚，PCA 会损失可解释性；课程方法表是选择菜单（C08 注释） |
| 离散化 | RFM 分档、金额分箱放在训练期拟合（第 4.2 节） | 分档边界是从数据学到的参数 |

## 4. 转换

### 4.1 确定性转换（逐行计算，不从数据学参数，可用于任何时期）

| 新列 | 规则 | 实测 |
|---|---|---|
| `purchase_date`、`purchase_week_start`（周一）、`purchase_month`、`purchase_dow`、`purchase_hour_utc` | 由 `purchase_ts` 拆出（UTC 工程假设） | 9,311 行 |
| `approval_lag_hours` | 审批 − 下单 | 0–24 小时；空值正好是 194 个取消单 |
| `delivery_days_floor` | ⌊送达 − 下单⌋ 天 | 与源 `actual_delivery_days` 一致 |
| `late_by_days` | 生成器口径：取整天数 > 预计天数 | 已送达订单中 14.75% |
| `late_by_date` | 日期口径：送达日期 > 预计送达日期 | 已送达订单中 64.07% |
| `log1p_merch_usd` 等 | log(1+金额) | 商品金额偏度 2.39 → −0.04；订单金额 2.32 → 0.07；运费 1.75 → 0.58 |
| `multi_payment`、`has_review` | 支付行数 > 1；有评价 | — |

两种延迟口径差别很大，页面和特征必须写明用的是哪一种。默认用 `late_by_date`，因为它和顾客看到的“晚于预计日期”一致。

可得时点：送达类特征在 as_of 使用前必须满足 `delivered_ts < as_of`，审批类必须满足 `approved_ts < as_of`（ML-03 实现截断）。

### 4.2 需要拟合的转换（只在训练期拟合）

- 标准化、分位数分箱、截尾阈值、K-Means 等都通过 `TrainOnlyFit`（`transform.py`）或同等方式拟合。传入的数据只要有一行时间不早于训练截止，`fit()` 就直接报错。
- 审计中的示例：以 2025-07-01 为示例训练截止，用 4,808 单拟合。商品金额均值 150.69、分箱边界与 P99 截尾阈值 724.51 都只来自训练行；用全时段数据拟合被拒绝。正式切分由 ML-04 冻结。
- 验证期、测试期和线上评分只调用 `transform()`，不重新拟合。

### 4.3 编码

- 品类（16 类）、支付方式（5 类）、大区（4 类）、距离档（4 类）：独热编码。类别清单来自契约中的主数据取值，不来自标签，可以在全时段固定；训练期没出现的类别编码为全 0。
- 州（51 个）：基数较高，模型中先合并为大区；需要时用训练期频率编码。

## 5. 复现

```bash
.venv/bin/python src/retail_bi/data/clean.py --layer data/processed/engineering/d50ee64a0478d8ae-20261108T000000Z-engineering-import-v1 --contract contracts/data_contract.json --out-root data/processed/clean --quarantine-root data/quarantine --report reports/data/cleaning_missing_duplicates.json
```

```bash
.venv/bin/python src/retail_bi/data/integrate.py --clean-dir data/processed/clean/9f5ba7d8e03a46b4-synthetic-transaction-v1-clean-v2 --out-root data/processed/integrated --audit reports/data/integration_audit.json
```

```bash
.venv/bin/python src/retail_bi/data/transform.py --integrated-dir data/processed/integrated/f4f1d4c30d91d6a0-integrate-v1 --out-root data/processed/transformed --audit reports/data/transform_audit.json
```

每一步的输出目录名包含上一步清单哈希和版本号；同一输入重跑得到同一文件（转换重跑哈希一致已实测），转换逻辑改变时必须提升版本号。
