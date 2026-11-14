# 命令登记表

## 已提供：治理检查（Python标准库）

在包的根目录执行，macOS可用`python3`：

```bash
python3 scripts/project.py validate
python3 scripts/project.py next
python3 scripts/project.py show DATA-02
python3 scripts/project.py render
python3 scripts/project.py gate proposal-ready
python3 scripts/project.py gate midterm-ready
python3 scripts/project.py gate final-ready
python3 scripts/project.py gate final-submitted
```

`validate`只验证台账结构、引用、依赖与声明完成项的证据。初始所有业务任务未验收，`gate`返回非0是预期阻断，不能修改脚本绕过。
`render`重建TASKS.md、REQUIREMENTS.md、STATUS.md；其他代理不要直接编辑这些视图。
`show <task_id>`输出该任务及相关要求，并给出验收证据所需的task_spec_sha256。规格或要求变化后旧哈希失效；重新核验后生成新的证据，不只替换哈希冒充重验。

## 已实现：项目环境（GOV-07，2026-11-09 实际运行通过）

工作目录：`retail_ai_execution_kit/`。在 macOS arm64（Apple M1 Pro，macOS 27.2）上验证过，其他平台没有验证。

```bash
# 1. 前置（只需一次）：uv，以及 LightGBM 在 macOS 上需要的 OpenMP 运行库
brew install libomp
# 2. 建立干净的虚拟环境并按锁文件安装（约 57 个包；本机耗时数分钟，取决于 PyPI 网速）
uv venv --python 3.12 .venv
uv pip sync --python .venv/bin/python requirements.lock
# 3. 冒烟检查：退出码 0 表示核心依赖可导入，LightGBM、逻辑回归可训练，DuckDB 只读连接拒绝写入
.venv/bin/python scripts/env_smoke.py
.venv/bin/streamlit --version
```

- 锁文件来源：`requirements.lock` 文件头记录了生成命令 `uv pip compile pyproject.toml --extra dev --python-version 3.12 --python-platform aarch64-apple-darwin -o requirements.lock`。修改 `pyproject.toml` 后要重新生成锁文件，并重跑冒烟检查。
- 没有 `brew install libomp` 时，`import lightgbm` 会报 `Library not loaded: @rpath/libomp.dylib`（2026-11-09 实际遇到过）。
- LLM 凭据：复制 `.env.example` 为 `.env` 后填写；`.env` 已被 `.gitignore` 忽略。冒烟检查不读取凭据，也不联网。
- 系统自带的 `python3`（3.9.6）只用于运行上面的治理脚本，不用于业务代码。

## 已实现：数据与数仓（2026-11-10 实际运行通过）

工作目录：`retail_ai_execution_kit/`，解释器 `.venv/bin/python`。数据完全合成（D012/D013）。

```bash
.venv/bin/python src/retail_bi/pipeline.py build
```

- 用途：从原始 ZIP 一条命令重建到 ADS（导入 → 清洗 → ODS → DWD → DWS → 时点快照与标签 → ADS → 交叉检查 → 原子发布）。
- 输出：`warehouse/builds/<版本>.duckdb`（版本由输入内容决定）与指针 `warehouse/builds/latest.json`；运行报告 `reports/warehouse/etl_run.json`。
- 成功条件：退出码 0，报告 `status: ok`。同样的输入重跑只复核已有版本；`--force` 强制重建。失败时退出码 1，报告写明失败阶段，不留半成品，不改动已发布版本（DW-07 实测）。
- 本机耗时约 2 秒（DW-07 实测）。

```bash
.venv/bin/python -m pytest tests/data -q
```

- 数据规则测试（隔离、重复导入、取消/待审批、金额差额、时间解析），夹具只在临时目录中使用。

```bash
.venv/bin/python tests/data/quality_gate.py
```

- 清洗后质量门槛，成功时输出 `gate passed 10/10`。
- 只重建数据层（不建仓）的分步命令见 `docs/data_readme.md` 第 2 节。

## 已实现：训练、应用与回归（2026-11-14 更新）

本节原本是“计划中”的命令表，现在各项都已实现。完整步骤、环境变量与异常恢复见 `docs/runbook.md`。

| 目的 | 命令 | 状态 |
| --- | --- | --- |
| 数据导入与建仓 | `.venv/bin/python src/retail_bi/pipeline.py build` | 已实现（DW-07），见上节 |
| 发布只读版本 / 回滚 | `.venv/bin/python src/retail_bi/warehouse/release.py publish`（或 `rollback`、`status`） | 已实现（DW-10） |
| 样本、特征、训练与评估 | 见 `docs/runbook.md` 第 4 节（ML-02 至 ML-12 的顺序） | 已实现；冻结模型 `models/repurchase-logreg-v1.json` |
| Web | `.venv/bin/streamlit run app.py --server.port 8599` | 已实现（UI-01 至 UI-07） |
| 关键路径回归 | `.venv/bin/python tests/release/run_regression.py`（`--skip-live` 跳过真实 LLM 调用） | 已实现（REL-01），2026-11-14 运行 32/32 通过 |

“已实现”以 `reports/submission/evidence_index.md` 中的运行证据为准，不能因为本文列出命令就写“已运行”。
