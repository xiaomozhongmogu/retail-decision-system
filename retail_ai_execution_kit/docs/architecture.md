# 轻量架构与数据流（GOV-06）

- 任务：GOV-06；验收规格哈希 `be5703bac6955cf9c3089b9cc7aab1fbc2de099229ad1301a5b4453b8502280d`
- 版本：v1 草案，2026-11-09，claude-opus-5-5 起草并自审
- 依据：`PROJECT_SPEC.md` §4–§6、`docs/business_scope.md`、`contracts/`、`reports/governance/workspace_inventory.md`
- 状态：**设计草案，没有任何业务代码实现**。各层由 DW-*、ML-*、AI-*、UI-* 任务实现后，才能当作事实引用。主数据路线待 DATA-03 确定，本架构对两条候选路线都适用（见 §3）。

## 1. 总体数据流

```
            离线批处理（命令行，可重跑）                              在线只读（Streamlit 进程内）
┌───────────────────────────────────────────────────────┐   ┌─────────────────────────────────────────┐
│ data/raw/<source>/<version>/   原始文件，只读，登记 SHA-256 │   │ app.py  →  src/retail_bi/ui/ 五类页面      │
│        │ ingest（来源适配器：uci / synthetic）            │   │        │ 只调用 service 层，不直接写 SQL     │
│        ▼                                               │   │        ▼                                 │
│ ODS  ods_*            字段原样＋批次元数据               │   │ service 层  src/retail_bi/service/       │
│        │ clean（规则见 DATA-07/08）                      │   │  get_kpis / query_olap / get_customer_   │
│        ▼                                               │   │  profile / get_risk_score …（契约见      │
│ DWD  dwd_* 事实与维度（星型）                            │   │  contracts/interfaces.md）               │
│        │ aggregate                                     │   │        │ 只读连接（read_only=True）        │
│        ▼                                               │   │        ▼                                 │
│ DWS  dws_* 汇总；客户时点快照 customer_snapshot           │──▶│ 发布快照 warehouse/releases/<ver>.duckdb │
│        │                                               │   │        ▲                                 │
│        ▼                                               │   │ AI 工具层 src/retail_bi/ai/              │
│ ADS  ads_* 指标语义视图（只暴露白名单字段）               │   │  查询助手：意图→受限 SQL 构造器→只读执行   │
│        │                                               │   │  周报：build_weekly_facts（SQL）→LLM→数字校验│
│ features / labels（客户×as_of）→ train → models/<ver>/  │──▶│  Agent：画像→retrieve_policy→check_budget │
│ score → model_scores（客户×as_of×model_version）        │   │         →save_draft（只存草稿）           │
│ knowledge/  指标词典、数据字典、模型卡、运营规则（RAG 语料）│──▶│  LLM 适配器（OpenAI 兼容接口，凭据来自 .env）│
└───────────────────────────────────────────────────────┘   │  调用日志 → logs/ai/（脱敏）               │
                                                            │ 草稿库 app_state.duckdb（唯一可写，与仓库分离）│
                                                            └─────────────────────────────────────────┘
```

设计原则：

1. **离线写、在线读。** ETL、训练和评分只在命令行中运行，完成后发布一个带版本号的 DuckDB 快照文件。Streamlit 和 AI 工具只以 `read_only=True` 打开快照；唯一可写的是与仓库分开的草稿库。
2. **发布即原子。** 新快照校验通过（DW-09）后，才更新 `warehouse/releases/current` 指针；失败时保留上一版（ACCEPTANCE 第三节）。
3. **数字只来自 SQL。** LLM 不计算数字。周报和查询的数字都由程序算好，再交给 LLM 组织文字，最后回查校验。
4. **单机足够。** 数据量为 10⁴～10⁶ 行，单机 DuckDB 即可，不引入 Spark、Kafka、向量数据库集群或微服务（PROJECT_SPEC §2）。

## 2. 技术栈（候选；版本在 GOV-07 安装验证后锁定）

| 用途 | 选择 | 理由 | 2026-11-09 解析结果 |
|---|---|---|---|
| 运行环境 | Python 3.12（uv 管理的 `.venv`） | 本机已有 3.12.14 和 uv；系统 Python 3.9.6 低于课程推荐的 3.10 | — |
| 数据处理 | pandas＋pyarrow | 读取 CSV/xlsx/Parquet | pandas 3.1.1、pyarrow 26.0.1 |
| 存储与 SQL | DuckDB（单文件）＋Parquet | 嵌入式 OLAP，支持只读连接；不需要服务进程 | duckdb 2.0.0 |
| 读取 UCI xlsx | openpyxl | UCI 原件是 xlsx | 3.1.5 |
| 机器学习 | scikit-learn、LightGBM | RFM/K-Means、逻辑回归、LightGBM（U03） | 1.9.1、4.7.0 |
| 可视化与应用 | Plotly、Streamlit | U05 | 7.1.0、1.67.0 |
| LLM 接入 | `openai` SDK 的 OpenAI 兼容接口（base_url 可换成 DeepSeek、通义等） | 一个适配层可以对接多家服务；具体厂商待用户提供凭据后确定（AI-01） | openai 3.46.0 |
| 检索（RAG） | 先用 BM25/TF-IDF，基于 scikit-learn，语料只有几十到几百条 | 语料小，不需要向量库；以后可以换成本地嵌入，但不作为前置条件 | 复用 scikit-learn |
| 测试 | pytest | 夹具、对账、拒绝测例 | 9.2.0 |

- “解析结果”是 `uv pip compile --python-version 3.12 --python-platform aarch64-apple-darwin` 的输出（`evidence/GOV-06/resolve.txt`）。它只证明这些版本在该平台**存在可解析的组合**，**没有安装，也没有导入测试**。
- 已知风险：LightGBM 在 macOS 上可能依赖 OpenMP 运行库（`libomp`）。GOV-07 必须实际 `import lightgbm` 并训练一个小样本来验证，失败时记录真实报错与处理方式。
- 其他组员的电脑（Windows 或 Intel）没有验证，由 REL-02 负责。

## 3. 表与粒度

两条候选路线共用同一套 DWD 契约，差异只在来源适配器。“路线 A”指 UCI，“路线 B”指合成电商包（见 `docs/data_candidates.md`）。

| 层 | 表 | 一行代表 | 主键 / 唯一键 | 路线 A 来源 | 路线 B 来源 | 负责任务 |
|---|---|---|---|---|---|---|
| ODS | `ods_<source>_<file>` | 源文件的一行，原样保留 | `batch_id`＋`row_no` | xlsx 两个工作表 | 10 张 CSV | DW-02 |
| DWD | `dwd_order_line` | 一条订单明细行 | `order_id`＋`line_no` | 发票明细行（保留取消前缀） | `order_items` | DW-03 |
| DWD | `dwd_order` | 一张订单或发票 | `order_id` | 按发票号去重 | `orders` | DW-03 |
| DWD | `dim_customer` | 一个客户 | `customer_id`（字符串，不填充） | CustomerID | `customers`（生成器标签只作展示，不作特征） | DW-03 |
| DWD | `dim_product` | 一个商品 | `product_id` | StockCode（描述取众数） | `products` | DW-03 |
| DWD | `dim_date` | 一个日历日 | `date` | 由事件区间生成 | `calendar` | DW-03 |
| DWD | `dim_geo` | 一个地区 | `geo_id` | Country | state/region | DW-03 |
| DWD | `dwd_fulfillment`（仅 B） | 一张订单的物流与评价 | `order_id` | — | `shipping`＋`reviews` | DW-03 |
| DWS | `dws_sales_daily` | 日期×地区×品类 | 三者组合 | 由 DWD 聚合 | 由 DWD 聚合 | DW-04 |
| DWS | `dws_customer_snapshot` | 客户×as_of | `customer_id`＋`as_of` | 只用 as_of 之前的事件 | 同左 | DW-05 |
| ADS | `ads_*` 视图 | 按指标定义 | — | `contracts/metrics.json` | 同左 | DW-06 |
| 模型 | `features` / `labels` | 客户×as_of | `customer_id`＋`as_of` | 特征窗 `[t−90天,t)`，标签窗 `[t,t+30天)` | 同左 | ML-02/03 |
| 模型 | `model_scores` | 客户×as_of×模型版本 | 三者组合 | — | — | ML-11 |
| 应用 | `ai_call_log` | 一次 LLM 调用 | `request_id` | — | — | AI-01 |
| 应用 | `strategy_draft` | 一份策略草稿 | `draft_id`（幂等键） | — | — | AI-13 |

- “订单数”按 `dwd_order` 去重计数，不按明细行计数（PROJECT_SPEC §5）。
- 金额单位按路线：A 为 GBP，B 为 USD。每个指标都带 `unit`，不跨路线混算。
- 客户级指标只使用 `customer_id` 已知的行；未知客户的交易可以进入经营汇总，但不进入客户模型（ACCEPTANCE 第三节）。

## 4. 目录与命令入口（由 GOV-07 实际建立）

```
retail_ai_execution_kit/
  src/retail_bi/{data,warehouse,features,model,analysis,service,ai,ui}/
  sql/               DDL 与标准 OLAP 查询
  knowledge/         RAG 语料（带版本）
  data/raw|processed|quarantine/   已在 .gitignore 中排除
  warehouse/releases/              发布快照（被 *.duckdb 规则排除）
  models/                          模型文件（已排除，模型卡另行登记）
  tests/
  app.py
```

拟定的命令形式沿用 `docs/COMMANDS.md`（`python -m retail_bi.cli ingest|build|train|verify`）。在 GOV-07 实际跑通之前，这些命令都**不可用**。

## 5. 安全与降级边界

| 风险 | 控制点 | 负责任务 |
|---|---|---|
| LLM 生成任意 SQL | 只接受结构化意图，由程序拼接白名单 SQL；执行连接为只读，禁止 ATTACH、COPY、加载扩展、读取外部文件，限制行数和超时 | AI-04/05 |
| LLM 编造数字 | 周报的数字从事实 JSON 注入，生成后逐个回查 | AI-08/09 |
| Agent 越权 | 工具只有读画像、检索、预算检查和存草稿四种，没有发送接口；预算和资格由代码判断 | AI-11～13 |
| 缺凭据或调用失败 | 返回 `status=error` 和 `error_code=llm_unavailable`；页面显示降级状态；离线回放必须打上 `mode=replay` 标记 | AI-01、UI-06 |
| 缓存串用 | 缓存键包含 `dataset_version`、`model_version` 和筛选参数 | UI-07 |

## 6. 本次没有验证的内容

- 没有安装依赖，也没有运行任何代码；§2 中的版本只是解析结果。
- 表结构没有写成 DDL（DW-01）；字段级定义要等 DATA-04。
- 没有选定 LLM 厂商。
