# 复现与运行手册（DOC-05）

- 适用：`retail_ai_execution_kit/`（工作目录），解释器 `.venv/bin/python`。
- 只在 macOS arm64（Apple M1 Pro，macOS 27.2，Python 3.12）上实际验证过。Windows 和 Intel 机器的干净环境复现由 REL-02 负责，目前**尚未验证**。
- 数据完全合成（D012/D013），不是真实企业数据。每条命令的实际运行证据见 `reports/submission/evidence_index.md`。

## 0. 总览

```
原始 ZIP ──导入/清洗/集成/转换──► ODS ─► DWD ─► DWS ─► 时点快照与标签 ─► ADS（+ 模型评分）
                               └────────────── pipeline.py build ──────────────┘
                                                          │ release.py publish（只读、校验哈希、原子切换）
                                                          ▼
                       warehouse/releases/current.json ──► Streamlit 页面 / AI 工具（只读查询允许的视图）
样本 ─► 特征 ─► 切分 ─► 基线/LightGBM ─► 选模与冻结 ─► 时间外评估 ─► models/repurchase-logreg-v1.json
```

## 1. 安装环境（一次）

```bash
brew install libomp
uv venv --python 3.12 .venv
uv pip sync --python .venv/bin/python requirements.lock
.venv/bin/python scripts/env_smoke.py
```

- `env_smoke.py` 退出码为 0，表示核心依赖可以导入，LightGBM 能训练，DuckDB 只读连接拒绝写入。
- 没有安装 `libomp` 时，`import lightgbm` 会报 `libomp.dylib` 缺失。

## 2. 放置数据

- 原始数据：`../ecommerce-sample-database-100k/01_source/baseline_10000_seed42.zip`，也就是与 `retail_ai_execution_kit/` 同级的目录。SHA-256 为 `d50ee64a0478d8ae8df1b8b66521671a4911e19f911ae86196452a668f917a16`，流水线会先核对这个哈希。
- 派生数据（`data/processed/`、`warehouse/`）不提交，由第 3、4 节的命令重建。各层的位置见 `docs/data_readme.md`。
- 只有运行台账校验（`scripts/project.py validate`）时才需要下面这一步：DATA-02 的证据把输入登记在本地快照目录里，新机器上要先从仓库内的源文件恢复它（2026-11-14 REL-02 核对，哈希一致）：

```bash
mkdir -p data/raw/data02-input-snapshot
cp -R ../ecommerce-sample-database-100k/01_source ../ecommerce-sample-database-100k/02_historical_utf8 data/raw/data02-input-snapshot/
```

## 3. ETL：从原始 ZIP 到发布版本

```bash
.venv/bin/python src/retail_bi/pipeline.py build
.venv/bin/python src/retail_bi/warehouse/release.py publish
.venv/bin/python src/retail_bi/warehouse/release.py status
```

- `build` 依次运行：导入 → 清洗 → ODS → DWD → DWS → 快照与标签 → ADS →（如果有冻结模型）评分 → 交叉检查。
  - 版本号由输入内容决定，同样的输入重跑只复核已有版本；`--force` 强制重建。
  - 任一阶段失败时退出码为 1，报告 `reports/warehouse/etl_run.json` 写明失败阶段，不留半成品（DW-07 实测）。
- 阶段一数据包（集成层、转换层，以及数据发布包检查所需的各层登记）由 `docs/data_readme.md` 第 2 节的分步命令生成。`pipeline.py build` 不生成这两层，新机器上需要再运行一次那条命令。
- `publish` 把构建结果复制为只读文件，核对哈希后原子切换 `warehouse/releases/current.json`。
  - 页面和 AI 只读取这个指针指向的版本。
  - 当前版本 `wh-d3aaa559048c`。
- 数据规则与质量检查：

```bash
.venv/bin/python -m pytest tests -q -p no:cacheprovider
.venv/bin/python tests/data/quality_gate.py
.venv/bin/python tests/warehouse/recon.py
```

## 4. 样本、特征与训练

### 4a. 生成样本与特征（新机器必做）

模型测试（`tests/model`）、测试结果复核和评分检查都要读取特征文件。特征文件是派生数据，不在仓库里，所以新机器上要先生成：

```bash
.venv/bin/python src/retail_bi/features/build_samples.py      # ML-02 时点样本与标签
.venv/bin/python src/retail_bi/features/customer_features.py  # ML-03 历史特征
```

- 这两步会改写 `reports/model/feature_build.json` 与 `sample_audit.json`：把其中的发布名改为本机构建的版本。
  - 已提交的记录写的是训练时所用的 `wh-db316daf8021`，新机器构建出的是 `wh-d3aaa559048c`。
  - REL-02 实测：两边的特征文件 92,241 行 × 33 列逐列相同。
- 运行检查时保留这两个改动，不要还原。

### 4b. 重新训练（只在需要时）

冻结的模型 `models/repurchase-logreg-v1.json` 已经提交，演示时**不需要**重新训练。REL-02 在干净环境中重新训练过一次，系数、截距和中位数与冻结模型完全相同（差为 0）。

需要重做时，在 4a 之后按下面的顺序运行：

```bash
.venv/bin/python src/retail_bi/model/split.py                 # ML-04 时间切分（split-v1）
.venv/bin/python src/retail_bi/model/segments.py              # ML-05 RFM 规则与 K-Means
.venv/bin/python src/retail_bi/model/baselines.py             # ML-06 规则与逻辑回归基线
.venv/bin/python src/retail_bi/model/boosting.py              # ML-07 LightGBM
.venv/bin/python src/retail_bi/model/model_select.py          # ML-08 选模、校准、名单规则、冻结
.venv/bin/python src/retail_bi/model/evaluate.py              # ML-09 测试集，只用一次
.venv/bin/python evidence/ML-10/error_analysis.py             # ML-10 误差分析
.venv/bin/python evidence/ML-12/publish_model.py reproduce    # 在新进程中加载模型并复现分数
```

- **测试集只用一次。** 重新运行 `evaluate.py` 就是又看了一次测试集，必须作为新版本记录，不能改写旧结论。
- 模型更新后，重跑第 3 节的 `build` 与 `publish`，评分才会进入发布版本。
- 页面会检查评分表里的模型版本是否等于冻结版本，不一致时不显示名单。

## 5. 启动应用

```bash
.venv/bin/streamlit run app.py --server.port 8599 --browser.gatherUsageStats false
```

- 打开 `http://localhost:8599`，侧栏有五个页面：数据口径、经营、客户、预测、AI 工作台。直接打开 `/data` 会提示 “Page not found” 再显示首页，从侧栏进入不受影响。
- 页面只读取发布版本和冻结记录，不在网页中运行 ETL 或训练。

## 6. 配置 LLM（可选）

复制 `.env.example` 为 `.env`（`.env` 已被 Git 忽略），然后填写：

| 变量 | 含义 |
|---|---|
| `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL` | 服务凭据与模型（本项目实测为 DeepSeek） |
| `LLM_ALLOW_PAID=1` | 明确允许付费调用；不设置时不发起任何调用 |
| `LLM_MAX_CALLS`、`LLM_MAX_COST_USD` | 每个进程的调用次数与费用上限（默认 50 次、0.50 USD） |
| `LLM_PRICE_IN_PER_1K`、`LLM_PRICE_OUT_PER_1K` | 用于估算费用的单价（未与供应商账单核对） |
| `LLM_TIMEOUT_S`、`LLM_MAX_RETRIES` | 超时与重试次数 |

没有密钥时，三个 AI 模块都使用规则和模板，页面会写明当前状态。密钥不会进入日志、页面或仓库。

## 7. 回归验证

```bash
.venv/bin/python tests/release/run_regression.py
.venv/bin/python tests/release/run_regression.py --skip-live
```

- 第一条运行全部 30 项关键路径检查，再加上启动服务、请求五个页面路径，结果写入 `reports/release/test_summary.json`。第二条跳过真实 LLM 调用的检查（没有配置密钥时用它）。
- 运行器默认拒绝在有未提交改动时运行：检查过程中被改写的已提交报告会先与提交版本比较，再恢复原样。
- 新机器上，第 3 节和第 4a 节会改写几份已提交的记录（`etl_run.json`、`feature_build.json`、`sample_audit.json`）。这时加 `--allow-dirty`：

```bash
.venv/bin/python tests/release/run_regression.py --skip-live --allow-dirty
```

  这些文件保持原样，不参与比较；台账检查只要求运行**没有新增**失效证据。
- 再次运行回归会改写 `reports/release/` 下的日志，REL-01 的证据描述的是 2026-11-14 那一次运行，不会随之更新。

## 8. 异常与恢复

| 现象 | 原因 | 恢复 |
|---|---|---|
| 页面显示“尚无已发布的数据版本” | 没有 `warehouse/releases/current.json`，或指针、文件损坏 | 运行第 3 节的 `build` 和 `publish` |
| 新发布有问题 | — | `release.py rollback` 切回上一个版本，再用 `release.py status` 确认 |
| `pipeline.py build` 退出码 1 | 某个阶段失败 | 看 `reports/warehouse/etl_run.json` 中的 `failed_stage`；修复后重跑，已发布的版本不受影响 |
| 输入哈希不符，拒绝运行 | 原始 ZIP 或已有输出被改动 | 换回正确的 ZIP；派生目录可以删除后重建 |
| 预测页显示“模型评估记录缺失” | `reports/model/*.json` 缺失或损坏 | 从 Git 恢复，或按第 4 节重新生成 |
| 预测页显示“模型版本不一致” | 发布版本里的评分来自另一个模型 | 重跑 `build` 和 `publish` |
| AI 页回答较简单，周报为“template” | 没有密钥、未设 `LLM_ALLOW_PAID=1`、超时、限流或预算用完 | 属于设计内的降级；事件日志 `logs/ai/events.jsonl` 记录了具体模式 |
| `import lightgbm` 报错 | 缺 OpenMP | `brew install libomp` |
| 模型测试或评分检查报 `features-…parquet` 不存在 | 新机器还没有生成特征 | 运行第 4a 节 |
| 数据发布包检查只有“工程导入层文件与登记一致”一项失败 | 导入层的 `manifest.json` 记录了归档文件的绝对路径，换目录重建后这个文件的哈希不同；数据文件本身相同 | 已知差异（REL-02），不影响数据。要消除它，需要改为相对路径并重新登记 DATA-05 至 DATA-12 |
| 用 `fetchall()` 读取带时区的时间列报 `pytz` 缺失 | 锁文件里没有 `pytz` | 页面和 AI 能访问的视图里没有这类列；自行写查询时先转成文本，例如 `ts::VARCHAR` |
| 端口被占用 | 已有服务在运行 | 换一个 `--server.port` |
