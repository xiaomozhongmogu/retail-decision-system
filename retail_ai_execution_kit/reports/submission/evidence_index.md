# 证据索引（DOC-05）

- 2026-11-14 整理。所用版本如下：
  - 数据：页面、AI 与分析报告使用发布 `wh-d3aaa559048c`（截至 2026-11-08，不含当天，完全合成）。
  - 模型：`repurchase-logreg-v1`。特征、训练和分群是在较早的发布 `wh-db316daf8021` 上完成的，两个发布的交易数据相同；后一个发布只多了模型评分表（见 `reports/model/feature_build.json`、`reports/ui/customer_page_review.md`）。
  - 其他：指标 `contracts/metrics.json`，知识库 `kb-v1`，政策 `retention-policy-v1`。
- 用法：报告里的每个结论，都可以在下表找到产生它的代码、运行命令、结果文件和证据记录。证据记录 `evidence/<任务>/*.json` 用 SHA-256 绑定了输入和产物；运行 `python3 scripts/project.py validate` 可以核对这些文件有没有被改过。
- 密钥与个人信息（2026-11-14 扫描已提交文件）：
  - 没有真实密钥。日志都经过脱敏，客户编号以短哈希记录，`.env` 不提交。
  - 页面和报告不显示城市、邮编或真实身份，数据本来也没有真实身份。
  - **待处理**：`evidence/DOC-01/proposal_extracted_text.txt`（从选题报告原件提取的文本）里有一个作者邮箱，属于不必要的个人信息。这份文件被 DOC-01 的证据绑定，是否脱敏由项目负责人决定。
- 复现命令见 `docs/runbook.md`；最近一次关键路径回归的结果见第 7 节。

## 1. 数据采集与预处理

| 步骤 / 结论 | 代码 | 结果 | 证据记录 |
|---|---|---|---|
| 来源核验与许可边界 | — | `reports/data/candidate_probe.md`、`dataset_selection.md` | `evidence/DATA-01/`、`DATA-03/` |
| 全量实读：17 个字段、订单明细 15,639 行 | `src/retail_bi/data/candidate_probe.py` | `reports/data/candidate_probe.json` | `evidence/DATA-02/` |
| 导入（核对哈希、可重复） | `src/retail_bi/data/ingest.py` | `reports/data/source_manifest.json` | `evidence/DATA-05/` |
| 质量剖析（清洗前） | `src/retail_bi/data/profile.py` | `reports/data/profile_before.md` | `evidence/DATA-06/` |
| 缺失、类型与重复处理 | `src/retail_bi/data/clean.py` | `reports/data/cleaning_missing_duplicates.json` | `evidence/DATA-07/` |
| 购买、取消与金额规则 | `src/retail_bi/data/transactions.py`；`docs/transaction_rules.md` | `reports/data/transaction_reconciliation.json` | `evidence/DATA-08/` |
| 集成与转换 | `src/retail_bi/data/integrate.py`、`transform.py` | `reports/data/integration_audit.json`、`transform_audit.json` | `evidence/DATA-09/`、`DATA-10/` |
| 清洗后质量门槛 10/10 | `tests/data/quality_gate.py` | `reports/data/quality_checks.json` | `evidence/DATA-11/` |
| 阶段一数据包 | `docs/data_readme.md` | `reports/data/dataset_release.json` | `evidence/DATA-12/` |

## 2. 数据仓库与 OLAP

| 步骤 / 结论 | 代码 | 结果 | 证据记录 |
|---|---|---|---|
| 概念、逻辑和物理设计 | `sql/`、`docs/` 中的数仓设计 | DDL 与设计校验 | `evidence/DW-01/` |
| ODS → DWD → DWS | `src/retail_bi/warehouse/ods.py`、`dwd.py`；`sql/` | `reports/warehouse/` | `evidence/DW-02/` 至 `DW-04/` |
| 时点快照（不读 as_of 之后的数据） | `src/retail_bi/features/snapshot.py` | `reports/warehouse/snapshot_contract.json` | `evidence/DW-05/` |
| ADS 与指标语义 | `sql/`；`contracts/metrics.json` | ADS 视图 | `evidence/DW-06/` |
| 一键重建；失败不留半成品 | `src/retail_bi/pipeline.py` | `reports/warehouse/etl_run.json` | `evidence/DW-07/`（含注入失败的记录 `injected_failure_report.json`） |
| OLAP 标准查询集（上卷、下钻、切片、切块） | `evidence/DW-08/run_and_check_olap.py` | 与 DWD 独立重算一致 | `evidence/DW-08/` |
| 约束与对账 | `tests/warehouse/recon.py` | `reports/warehouse/reconciliation.json` | `evidence/DW-09/` |
| 只读发布、回滚、中断发布 | `src/retail_bi/warehouse/release.py`、`runtime.py` | `warehouse/releases/current.json` | `evidence/DW-10/` |

## 3. 分析

| 结论 | 结果 | 证据记录 |
|---|---|---|
| 描述性统计 | `reports/analysis/eda_initial.md` | `evidence/EDA-01/` |
| 经营趋势：2026 年 1–10 月金额 −0.3%（客户数影响 −11,689 USD，被客单价 +11,546 USD 抵消） | `reports/analysis/business_trends.md`、`diagnosis.md` | `evidence/EDA-02/`、`EDA-04/` |
| cohort 留存：+1 月 6.7%–8.7% | `reports/analysis/cohort.md` | `evidence/EDA-03/` |
| 生命周期规则；各状态未来 180 天复购率都约 35% | `docs/lifecycle_rules.md`、`reports/analysis/lifecycle_checks.json` | `evidence/EDA-05/` |
| 决策简报 | `reports/analysis/decision_brief.md` | `evidence/EDA-06/` |
| 问题分析、反思与应用前景 | `reports/analysis/reflection_and_roadmap.md` | `evidence/DOC-08/` |

## 4. 分群与预测

| 结论 | 代码 | 结果 | 证据记录 |
|---|---|---|---|
| 目标与母体：30 天复购，近 90 天有购买的客户 | — | `docs/model_target.md` | `evidence/ML-01/` |
| 时点样本、历史特征 | `src/retail_bi/features/build_samples.py`、`customer_features.py` | `reports/model/sample_audit.json`、`feature_build.json` | `evidence/ML-02/`、`ML-03/` |
| 时间切分与泄漏审计 | `src/retail_bi/model/split.py`；`tests/model/` | `reports/model/split_manifest.json`、`leakage_audit.md` | `evidence/ML-04/` |
| RFM 规则分群与 K-Means | `src/retail_bi/model/segments.py` | `reports/model/rfm_segments.md`、`cluster_metrics.json` | `evidence/ML-05/` |
| 基线、LightGBM、选模（逻辑回归验证 PR-AUC 0.0897，LightGBM 0.0882） | `baselines.py`、`boosting.py`、`model_select.py` | `reports/model/baselines.md`、`model_selection.json` | `evidence/ML-06/` 至 `ML-08/` |
| 时间外测试：ROC-AUC 0.515（0.483–0.546），周内 Lift@10% 规则 1.02、模型 0.84 | `src/retail_bi/model/evaluate.py` | `reports/model/evaluation.md`、`test_metrics.json` | `evidence/ML-09/` |
| 误差与适用限制 | `evidence/ML-10/error_analysis.py` | `reports/model/error_analysis.md` | `evidence/ML-10/` |
| 评分服务、模型文件与模型卡 | `src/retail_bi/model/scoring.py` | `models/repurchase-logreg-v1.json`、`docs/model_card.md` | `evidence/ML-11/`、`ML-12/` |

## 5. AI 模块

| 结论 | 代码 | 结果 | 证据记录 |
|---|---|---|---|
| LLM 适配：超时、重试、预算、无密钥降级、脱敏；真实调用成功 | `src/retail_bi/ai/client.py` | `reports/ai/client_live_probe.json` | `evidence/AI-01/` |
| 知识检索与引用 24/25 | `src/retail_bi/ai/`（检索） | `reports/ai/rag_evaluation.json` | `evidence/AI-02/`、`AI-03/` |
| 查询助手；NL2SQL 标准集首测 85.7%，修复后 28/28；越权等 16/16 拦截 | `query_intent.py`、`sql_executor.py`、`query_assistant.py` | `reports/ai/nl2sql_evaluation.json` | `evidence/AI-04/` 至 `AI-07/` |
| 周报：事实、生成与数值校验；盲测 10/10 拦截、0/14 误判 | `report_facts.py`、`report_generator.py` | `reports/ai/weekly_report_example.md`、`report_evaluation.json` | `evidence/AI-08/` 至 `AI-10/`（AI-10 人工抽查**待组员完成**） |
| 挽回 Agent：政策、有限步骤、草稿只能待审，36/36 场景 | `policy_engine.py`、`retention_agent.py`、`drafts.py` | `reports/ai/agent_evaluation.json`、`agent_trace_example.json` | `evidence/AI-11/` 至 `AI-14/` |
| 三模块联调 14/14；五种模式可区分 | `src/retail_bi/ai/integration.py` | `reports/ai/integration_evaluation.json`；`docs/ai_system_card.md` | `evidence/AI-15/` |
| 外部 AI 测试（Gemini 对抗测试、GPT 模拟用户测试）与修复 | — | `reports/external_test/` | 各任务 2026-11-13 的复验证据 |

## 6. 可视化应用（截图）

| 页面 | 截图 | 检查 |
|---|---|---|
| 数据口径与质量 | `evidence/UI-02/data_page_browser.jpg` | `evidence/UI-02/check.py` |
| 经营总览：趋势、下钻 | `evidence/UI-03/business_trend_browser.jpg`、`business_cube_browser.jpg`、`evidence/UI-01/business_page_browser.jpg` | `evidence/UI-03/check.py` |
| 客户：生命周期、cohort | `evidence/UI-04/lifecycle_browser.jpg`、`cohort_browser.jpg`；对比修复前后：`evidence/UI-07/cohort_before.png`、`cohort_after.png` | `evidence/UI-04/check.py` |
| 复购预测：测试结果、名单试算 | `evidence/UI-05/test_results_browser.jpg`、`list_trial_browser.jpg` | `evidence/UI-05/check.py` |
| AI 工作台：查询助手、Agent（真实调用） | `evidence/UI-06/query_assistant_live.jpg`、`agent_live.jpg` | `evidence/UI-06/check_ai_page.py` |
| 全站可读性、缓存与异常 | `reports/ui/full_ui_review.md` | `evidence/UI-07/check.py` |
| AI 模拟用户测试截图 | `reports/external_test/gpt_ui/screenshots/` | — |

## 7. 关键路径回归（REL-01）

- 运行器：`tests/release/run_regression.py`。2026-11-14 在提交 `02a8b52` 上运行，**32/32 通过**，结束后台账仍然有效。
- 结果：`reports/release/test_summary.json`；关键路径与对应检查的对照见 `reports/release/critical_paths.md`；每条检查的完整输出在 `reports/release/regression_logs/`。
- 本次回归发现并修复了两个问题：数仓代码此前未被提交（`.gitignore`）；预测页表格静默兜底。详见 `critical_paths.md` 第 3 节。
