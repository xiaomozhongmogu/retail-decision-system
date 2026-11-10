# 阶段一数据包说明（DATA-12）

- 发布：`stage1-data-2026-11-10`；登记表 `reports/data/dataset_release.json`（各层版本、文件哈希、文档哈希都在那里）
- **数据完全合成**，不是真实企业或真实顾客。按 D012 用户授权的工作假设使用（D013 冻结主数据），**没有教师确认**。

## 1. 数据在哪里

| 层 | 位置 | 是否提交 Git |
|---|---|---|
| 原始数据 | `../ecommerce-sample-database-100k/01_source/baseline_10000_seed42.zip`（1,310,750 字节，SHA-256 `d50ee64a…7a16`） | 是，课程私有仓库 |
| 导入存档与工程层 | `data/raw/archives/`、`data/processed/engineering/` | 否（Git 忽略），可重建 |
| 清洗层（Parquet） | `data/processed/clean/9f5ba7d8e03a46b4-synthetic-transaction-v1-clean-v2/` | 否，可重建 |
| 集成层 | `data/processed/integrated/f4f1d4c30d91d6a0-integrate-v1/` | 否，可重建 |
| 转换层 | `data/processed/transformed/f6f9711c5b7cb385-transform-v1/` | 否，可重建 |
| 隔离区 | `data/quarantine/`（本数据 0 行） | 否 |

目录名由上一层的内容指纹和版本号组成。不同电脑上从同一 ZIP 重建，目录名和每个文件的哈希都相同（2026-11-10 在另一路径实测，16 个文件一致）。

## 2. 一键重建

在 `retail_ai_execution_kit/` 下，环境按 `docs/COMMANDS.md` 建好后执行：

```bash
.venv/bin/python src/retail_bi/data/ingest.py --source ../ecommerce-sample-database-100k/01_source/baseline_10000_seed42.zip --raw-root data/raw/archives --work-root data/processed/engineering --cutoff 2026-11-08T00:00:00Z --expected-sha256 d50ee64a0478d8ae8df1b8b66521671a4911e19f911ae86196452a668f917a16 > /dev/null && .venv/bin/python src/retail_bi/data/clean.py --layer data/processed/engineering/d50ee64a0478d8ae-20261108T000000Z-engineering-import-v1 --contract contracts/data_contract.json --out-root data/processed/clean --quarantine-root data/quarantine > /dev/null && .venv/bin/python src/retail_bi/data/integrate.py --clean-dir data/processed/clean/9f5ba7d8e03a46b4-synthetic-transaction-v1-clean-v2 --out-root data/processed/integrated --audit /dev/null > /dev/null && .venv/bin/python src/retail_bi/data/transform.py --integrated-dir data/processed/integrated/f4f1d4c30d91d6a0-integrate-v1 --out-root data/processed/transformed --audit /dev/null > /dev/null && .venv/bin/python tests/data/quality_gate.py
```

- 每一步都先核对输入哈希；同一输入重跑时校验已有输出、不重写；已有输出被改动时拒绝运行。
- 最后一步输出 `gate passed 10/10` 表示重建成功并通过质量门槛。
- 想更新报告文件时，把命令中的 `/dev/null` 换成 `reports/data/` 下对应文件，并另加 `--report reports/data/cleaning_missing_duplicates.json`。

## 3. 规模、字段与时间

| 课程条件 | 实测 | 说明 |
|---|---|---|
| ≥ 10,000 条记录或 ≥ 10 MB | 订单明细 15,639 行 | 按记录数满足；解压后 7,974,631 字节，不以字节数主张 |
| ≥ 8 个有效字段 | 17 个 | 见 `docs/data_dictionary.md` |
| 明确的时间维度 | 下单时间 2024-01-01 至 2026-11-07，35 个月 | 源时间无时区，UTC 是工程假设 |
| 数据时效 | 模拟事件 2024–2026，生成于 2026-07-21 | 按 D012 用户授权视为已确认；**教师未答复** |

## 4. 字典与报告

- 逐列字典：`docs/data_dictionary.md`；契约：`contracts/data_contract.json`
- 购买、取消与金额规则：`docs/transaction_rules.md`；指标：`contracts/metrics.json`
- 预处理方法（清理、集成、归约、转换）：`docs/preprocessing_methods.md`
- 质量：清洗前 `reports/data/profile_before.md`；清洗后 `reports/data/profile_after.json`、`reports/data/quality_checks.json`（10/10，附 1 条警告：2026 年第四季度只有 1 个周快照，不能单独作测试期）

## 5. 交付方式

- 代码、契约、文档、报告和原始 ZIP 放在课程私有仓库里。派生数据不提交，接收者按第 2 节重建，并用登记表中的哈希核对。
- 原始数据和派生数据都不公开发布（C07）。
- 范围是冻结研究范围的全量，没有抽样；`tests/data` 中的夹具只用于测试，不是数据样本。

## 6. 未知事项

- 教师是否认可完全合成数据作为课程“原始数据”，以及时效按哪个日期判断（D001、D006，GOV-04）。
- 课程最终提交时的数据交付方式，教师没有规定。
- 网站下载件未标明数据许可（同作者同类样例为 CC0）。
- 源时间没有时区。
- 其他成员的电脑（Windows 或 Intel）没有验证重建（REL-02）。
