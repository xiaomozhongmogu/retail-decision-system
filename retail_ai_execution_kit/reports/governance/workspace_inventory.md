# GOV-02 现有仓库与 AI 运行能力盘点

- 任务：GOV-02；验收规格哈希 `dd9b25ccf66ec67eba441bbbc333d9430bb3b7181443d80a1b64df53c0548195`
- 执行：claude-opus-5-5（Claude Code 桌面端），2026-11-09 20:01–20:05，Asia/Shanghai；自审
- 本文是某一时刻的快照。当前状态以 `project/tasks.json` 为准。

## 1. 仓库、文件快照与未提交修改

### 1.1 版本控制

- `retail_ai_execution_kit/` 及其上级目录**都不是 Git 仓库**（`git rev-parse` 返回 not a git repository）。所以没有分支、提交或"未提交修改"可查。
- 替代做法：对上级目录下两个子目录的全部 60 个文件（不含 `.DS_Store` 和本任务证据目录）计算 SHA-256，结果存为 `evidence/GOV-02/file_snapshot.tsv`。后续可以用它判断文件有没有被改过。
- 风险：C23 要求“Git 提交历史”作为个人贡献证据。目前没有任何 Git 历史，越晚建仓库，可展示的真实过程记录越少。建立仓库属于 GOV-07 / GOV-08，本任务不擅自 `git init`。

### 1.2 目录与归属

| 位置 | 内容 | 修改时间 | 归属判断 | 处理 |
|---|---|---|---|---|
| `retail_ai_execution_kit/` 初始文件（38 个） | 治理执行包：AGENTS、规格、契约、台账、模板、课程原件、治理脚本 | 2026-11-05（其中 33 个快照时未改动） | 初始执行包 | 按 AGENTS 规则使用 |
| 其中 2026-11-09 改动的 5 个 | `project/tasks.json`、`ops/DECISIONS.md`、`TASKS.md`、`STATUS.md`、`REQUIREMENTS.md` | 2026-11-09 19:59–20:01 | 本会话 GOV-01 写入 | 见 GOV-01 证据 |
| 本会话新建 | `reports/governance/requirements_review.md`、`evidence/GOV-01/` 3 个文件；随后又新建本文件与 `evidence/GOV-02/` | 2026-11-09 | 本会话 | 快照中不含本文件和 GOV-02 证据 |
| `../ecommerce-sample-database-100k/`（18 个文件，8.9 MB） | 合成电商数据包：原始 ZIP、10 张历史 CSV、RFM 派生快照、字典、质量报告、`build_retail_verified.py` | 2026-11-08 13:40–13:41 | **未知**：README 写“原样保留你上传的原始 ZIP”，看起来是用户在别处让其他工具准备的，台账中没有记录 | 不修改、不移动；只读核验 |

### 1.3 可复用的已有成果

| 成果 | 已做的核验 | 可供哪些任务复用 | 尚未核验 |
|---|---|---|---|
| `01_source/baseline_10000_seed42.zip` | SHA-256 `d50ee64a…7a16` 与包内 `quality_report.json` 一致；ZIP 含 30 个条目（含 `__MACOSX` 元数据），有 orders、order_items、customers、products、payments、shipping、reviews、sellers、seller_products、calendar、simulation_metadata、validation_summary 等 CSV/JSON | DATA-01、DATA-02、DATA-05 | 来源页面与 CC0 许可（需联网核对原发布页）；ZIP 内文件是否由生成器原样产出 |
| `02_historical_utf8/*.csv`（10 张） | 只核对了文件大小与哈希（见快照） | DATA-02、DATA-05 | 行数、字段、外键、时间截断规则都没有本 AI 实测（包内报告声称已核验，属于他人结果） |
| `03_derived_demo/customer_rfm_snapshot_asof_2026-11-08.csv` | 无 | 可作 ML-05 对照 | 口径尚未与 `contracts/` 对齐，不能直接当正式特征 |
| `04_audit/`（字典、质量报告、模拟元数据） | 读取了质量报告摘要 | DATA-04、DATA-06 | 报告数字由他人生成，需 DATA-02 重算 |
| `build_retail_verified.py` | 没有运行，也没有审阅代码 | DATA-05 | 依赖 pandas（本机系统 Python 未装） |
| 治理脚本 `scripts/project.py` | `validate`、`render`、`next`、`show`、`gate` 实际运行，退出码 0 | 全部任务 | — |

注意：数据包的 `DATA_SOURCE.md` 把数据定性为“完全合成”，事件时间为 2024-01 至 2026-12（其中 2026-11-08 以后的是“未来模拟订单”）。这与 `PROJECT_SPEC.md`、`contracts/` 中以 Online Retail II 为默认交易路线的假设不同。是否改路线属于 DATA-03 和 D001/D006 的决定，本任务不改契约。

## 2. 执行环境

| 项目 | 实测值 | 方式 |
|---|---|---|
| 操作系统 | macOS 27.2（build 26B123） | `sw_vers` |
| CPU / 架构 | Apple M1 Pro，8 核，arm64 | `sysctl`、`uname -m` |
| 内存 / 磁盘 | 16 GB；数据卷剩余约 93 GB（已用 79%） | `sysctl hw.memsize`、`df -h` |
| 默认 Python | `/usr/bin/python3` = 3.9.6（Xcode 自带），pip 21.2.4 | `python3 --version` |
| 其他 Python | `~/.local/bin/python3.12` = 3.12.14；`uv` 可用；Homebrew 可用 | `which -a` |
| 业务依赖 | 系统 Python 下 pandas、duckdb、scikit-learn、lightgbm、streamlit、plotly、openai、anthropic **全部未安装**；3.12 环境下没有检查 | `importlib.util.find_spec` |
| 文件读写 | 可以读写项目目录与会话临时目录 | 实际写入了本任务文件 |
| 命令执行 | 可以执行 shell 与 Python | 实际执行 |
| 联网 | 可以访问：pypi.org 返回 200 但下载较慢（10 秒内只收到约 0.44/1.37 MB）；github.com 返回 200 | `curl` |
| LLM API 可达性 | DeepSeek、Anthropic、阿里云 DashScope、OpenAI 的 `/models` 端点都返回 401，即网络可达、需要凭据 | 不带凭据的 `curl` |
| 项目 LLM 凭据 | **没有**：没有 `.env`，环境变量中没有项目 API key。`ANTHROPIC_BASE_URL` 属于本 Claude Code 会话，不是项目凭据，不能用于项目 | `env` 只看变量名 |

**关于“用户 M1 机器”**：本会话运行在一台 Apple M1 Pro Mac 上，而且是用户本人的机器（用户主目录）。但本次只盘点了能力，**没有在这台机器上安装或运行项目技术栈**，因此不能说“目标 Mac/ARM64 环境已验证通过”。其他组员的电脑完全没有验证。环境验收属于 GOV-07 和 REL-02。

课程推荐 Python 3.10 以上，而系统默认 3.9.6 不满足。建议 GOV-07 用已有的 `uv` 和 Python 3.12 建立项目虚拟环境并锁定依赖；需要实际安装后才算验证。

## 3. 能实际执行与只能交付补丁的范围

本会话（claude-opus-5-5，Claude Code 桌面端）可以直接完成：

- 读写项目文件、运行 Python 和 shell、计算哈希、运行治理脚本。
- 联网下载公开依赖与公开数据（受网速影响；PyPI 较慢），访问公开网页核对来源和许可。
- 在本机建立 Python 3.12 虚拟环境并安装依赖（GOV-07 的工作，本任务没有执行）。
- 运行 ETL、训练、Streamlit 本地启动，以及在本地浏览器中截图验证（实现后）。

需要用户或真实成员提供，AI 不能代办：

- **项目 LLM API 凭据**：由用户写入 `.env`，AI 不填写、不回显密钥。没有凭据时，AI-01 只能做适配层和夹具测试，标“待真实调用”。
- 联系教师并取得 D001/D002/D006–D009 的解释；填写真实成员、学号、组长签名（GOV-03）。
- 课程平台上传与提交回执（REL-07）。
- 其他组员电脑上的复现（REL-02）。

不覆盖未知文件的约定：`../ecommerce-sample-database-100k/` 归属不明，后续任务只读引用或复制到 `data/raw/`（已在 `.gitignore` 中排除），不在原位置修改或删除。执行包中 2026-11-05 的原始文件只按 AGENTS 规定的职责修改。

## 4. 本次没有验证的范围

- 没有在 Python 3.12 环境下检查已装包，也没有安装任何依赖。
- 没有审阅或运行 `build_retail_verified.py`，没有重算数据包的行数和质量结论。
- 没有用真实凭据调用任何 LLM。
- 没有核对合成数据发布页面与许可原文。
- 网速只测了一次，没有做稳定性测试。
