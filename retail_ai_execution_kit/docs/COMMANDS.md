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

## 计划中：业务命令

以下入口要等对应实现任务实际建立后才能登记为可用（环境已由 GOV-07 建立）：

| 目的 | 拟定形式 | 当前状态 |
| --- | --- | --- |
| 数据探查/导入 | `python -m retail_bi.cli ingest --config ...` | 未实现 |
| 清洗和建仓 | `python -m retail_bi.cli build --config ...` | 未实现 |
| 构建样本/训练 | `python -m retail_bi.cli train --config ...` | 未实现 |
| 数据/模型/AI验证 | `python -m retail_bi.cli verify --suite ...` | 未实现 |
| Web | `streamlit run app.py` | 未实现 |

实现后填写精确命令、工作目录、输入配置、输出路径、成功条件、预期耗时和真实运行证据。不能因为本文列出命令就写“已运行”。
