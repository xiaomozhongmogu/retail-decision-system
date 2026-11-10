# 数据阶段（DATA-06 至 DATA-12）交接与检查点（claude-opus-5-5）

## 2026-11-10 15:10 +08:00

- 协调者：claude-opus-5-5（对话“电商项目接力｜说继续即可”）。台账 `0c653aa3…` 之后的提交为 `988c8e9`。没有后台作业。
- 已验收 18 项：GOV-01/02/05/06/07/08，DATA-01 至 DATA-12。

### 数据管线（每步检查输入哈希，同输入重跑不重写）

| 步骤 | 代码 | 输出（Git 忽略） | 报告 |
|---|---|---|---|
| 导入（codex） | `src/retail_bi/data/ingest.py` | `data/processed/engineering/d50ee64a…-engineering-import-v1` | `reports/data/source_manifest.json` |
| 剖析 | `profile.py` | — | `profile_before.{json,md}` |
| 清洗 | `clean.py`（clean-v2，内容指纹键） | `data/processed/clean/9f5ba7d8e03a46b4-…-clean-v2` | `cleaning_missing_duplicates.json` |
| 交易规则 | `transactions.py`（transaction-rules-v1） | — | `transaction_reconciliation.json`，`contracts/metrics.json` |
| 集成 | `integrate.py` | `data/processed/integrated/f4f1d4c30d91d6a0-integrate-v1` | `integration_audit.json` |
| 转换 | `transform.py`（含 TrainOnlyFit） | `data/processed/transformed/f6f9711c5b7cb385-transform-v1` | `transform_audit.json` |
| 质量门槛 | `tests/data/quality_gate.py`、`tests/data/test_rules.py` | — | `profile_after.json`、`quality_checks.json` |
| 发布 | — | — | `dataset_release.json`、`docs/data_readme.md` |

### 下游必须知道的口径

- 有效购买 = 已审批订单（`approved_ts` 非空且早于 as_of）；按 `purchase_ts` 归属；取消单列；无退款；商品金额不含运费。
- 30 天标签（冻结口径重算）：132 个周快照、92,241 行、正例 6,618（7.17%）。**2026-Q4 只有 1 个快照、72 个正例，不能单独作测试期**（ML-04）。
- 两种延迟口径：`late_by_days`（生成器，14.75%）和 `late_by_date`（64.07%），默认 `late_by_date`。
- DuckDB 取带时区时间戳到 Python 需要 pytz（未安装）：在 SQL 中先 `::VARCHAR`。
- 生成器标签（客户分群、生命周期、情感、卖家参数）、最终状态、预计送达不得入模。

### 已知遗留

- `docs/architecture.md`、`contracts/interfaces.md` 仍有路线 A/GBP 的历史描述 → DW-01 收窄（会触发 GOV-06/07 复核）。
- `docs/COMMANDS.md` 的“计划中”表格未登记数据命令（GOV-07 产物，改动会使其证据失效）；命令目前登记在 `docs/data_readme.md`。
- 改 `contracts/*`、`docs/business_scope.md`、`ops/DECISIONS.md` 都会使多项已完成任务的证据失效，需要审阅后重出。

### 需要用户或团队提供

GOV-03 分工表与孙卓班级；教师对 D001/D006 的实际答复（非阻塞）；选题报告提交回执；AI-01 实际调用所需的 LLM 凭据。

### 下一步

DW-01 数仓设计 → DW-02…；并行可做 EDA-01、UI-01、AI-01（无凭据只做适配层）、DOC-04、ML-01。
