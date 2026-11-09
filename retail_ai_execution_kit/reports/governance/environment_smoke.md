# GOV-07 环境、目录与命令入口冒烟报告

- 任务：GOV-07；验收规格哈希 `45bcd39c48a6047891584bb8abae2d2b3877aee6686cd9521aa21560dcab14dc`
- 执行：claude-opus-5-5（Claude Code 桌面端），2026-11-09 20:38–20:49 +08:00；自审
- 运行日志：`evidence/GOV-07/setup_run.log`（锁定与安装）、`smoke_run.log`（冒烟检查，含第一次失败与修复后重跑）、`gitignore_check.log`（忽略规则）

## 1. 环境与锁文件（条件 1）

| 项目 | 实际值 |
|---|---|
| 机器 | Apple M1 Pro，arm64，macOS 27.2（`platform`: `macOS-27.2-arm64-arm-64bit`） |
| Python | 3.12.14，uv 管理的 `.venv`（uv 0.12.7） |
| 直接依赖 | `pyproject.toml`：pandas、pyarrow、duckdb、openpyxl、scikit-learn、lightgbm、plotly、streamlit、openai；dev 组：pytest |
| 锁文件 | `requirements.lock`，共 57 个固定版本。文件头记录了生成命令（目标为 Python 3.12、aarch64-apple-darwin） |
| 关键版本 | pandas 3.1.1、pyarrow 26.0.1、duckdb 2.0.0、scikit-learn 1.9.1、lightgbm 4.7.0、plotly 7.1.0、streamlit 1.67.0、openai 3.46.0、pytest 9.2.0 |
| 系统级前置 | Homebrew `libomp` 23.1.5（MIT），LightGBM 需要它 |
| 启动方式 | 见 `docs/COMMANDS.md` 的“已实现：项目环境” |

### 实际过程（含失败）

1. 用 `uv pip compile` 生成锁文件，退出码 0。
2. 新建干净的 `.venv`，再用 `uv pip sync` 按锁文件安装，退出码 0；`uv pip check` 显示 57 个包相互兼容。
3. **第一次冒烟失败**（退出码 1）：`import lightgbm` 报 `Library not loaded: @rpath/libomp.dylib`。其他检查都通过。这是 GOV-06 中已经登记的风险。
4. 修复：`brew install libomp`（LightGBM 官方对 macOS 的做法；可以用 `brew uninstall libomp` 撤销）。
5. **重跑冒烟，全部通过**（退出码 0）：10 个依赖都能导入；LightGBM 训练 200 行，预测概率在 [0.066, 0.934]；逻辑回归训练成功；DuckDB 只读连接能读到 5 行，并拒绝 `INSERT`；Plotly 能生成图对象。`streamlit --version` 输出 1.67.0。

## 2. Git 忽略与私有边界（条件 2）

`.gitignore` 新增了 `warehouse/`、`logs/`、`*.parquet`、`.pytest_cache/`、`.intent-lens/`（`.intent-lens/` 中保存有用户原话）。在一个只复制了 `.gitignore` 的临时仓库中，用 `git check-ignore --no-index` 实测：

- **忽略**：`.env`、`.env.local`、`.venv/`、`data/raw|processed/`、`models/`、`warehouse/`、`*.duckdb`、`logs/`、`.intent-lens/`
- **保留跟踪**：`.env.example`（否定规则）、`sources/` 课程原件、`contracts/`、`requirements.lock`

`.env.example` 中三个键（`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`）的值都为空，没有真实密钥。课程原件和 `deliverables/` 会被跟踪，所以仓库不能设为公开（C07、D005）；数据文件不进入仓库。项目目前仍不是 Git 仓库，是否 `git init` 由用户决定。

## 3. 已实现与计划中的命令（条件 3）

- 已实现并实际跑通：环境建立三步、`scripts/env_smoke.py`、`streamlit --version`，以及原有的治理命令。
- 仍是计划：`python -m retail_bi.cli ingest|build|train|verify` 和 `streamlit run app.py`。`src/retail_bi/` 和 `app.py` 还不存在，由 DATA-02、DW-*、UI-01 等任务建立。`docs/COMMANDS.md` 已把这两类分开列出。
- “干净环境”指本机上新建的 `.venv`，**不是第二台机器**；他机复现属于 REL-02。

## 4. 本次没有验证的内容

- Windows、Intel Mac 和其他组员的电脑。
- Streamlit 实际启动页面（还没有 `app.py`）。
- 带凭据调用 LLM。
- 用真实项目数据跑 pandas 或 DuckDB（属于 DATA-02）。
