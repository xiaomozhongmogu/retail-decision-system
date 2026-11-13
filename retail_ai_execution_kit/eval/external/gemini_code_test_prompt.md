# 给 Gemini 的提示词：独立代码测试（对抗式）

> 用法：在本仓库根目录 `Retail Decision System/` 打开 Gemini（Antigravity / Gemini CLI），把下面分隔线以下的全部内容作为第一条消息发送。不需要额外说明。

---

你是这个项目的**独立测试工程师**，不是开发者。代码由另一个 AI（Claude）编写，并且它已经写过自己的测试。你的任务是**找出它自己的测试没有发现的问题**。如果你只是重跑它的测试然后报告“全部通过”，这次测试就没有价值。

## 0. 项目背景（只读了解即可）

- 课程项目《基于用户全生命周期的电商零售智能决策与 AI 运营助手系统》。工作目录：`retail_ai_execution_kit/`，解释器：`.venv/bin/python`。
- 数据是完全合成的电商交易数据，已建成 DuckDB 数仓（ODS/DWD/DWS/ADS），只读发布版本由 `warehouse/builds/latest.json` 指向。截止日 as_of = 2026-11-08（不含）。金额单位是 USD 的商品金额，不含运费。
- 三个 AI 模块都在 `src/retail_bi/ai/` 下：
  1. **查询助手**（NL2SQL）：`query_intent.py`（问题解析为意图）、`sql_executor.py`（校验 + 沙箱只读执行）、`query_assistant.py`（会话与追问）。
  2. **经营周报**：`report_facts.py`（计算事实）、`report_generator.py`（LLM 只写占位符 `{{Fnn}}`，程序填数，多条规则校验，失败回退模板）。
  3. **挽回 Agent**：`retention_agent.py`（固定流程，最多 8 步）、`policy_engine.py`（资格、折扣、频率、预算规则）、`drafts.py`（草稿只能待审，永不发送）。
  - 另有统一入口 `integration.py`（共享 LLM 预算、事件日志脱敏）和 LLM 适配层 `client.py`。
- 项目自己声称的保证写在 `docs/ai_system_card.md`、`docs/nl2sql_supported_queries.md`、`knowledge/retention_policy.md`。**你要验证的就是这些声明是否成立。**

## 1. 硬性规则（违反任何一条，这次测试作废）

1. **不修改任何已有文件。** 包括代码、`.env`、`project/`、`evidence/`、`reports/`、`eval/`、`docs/`、`knowledge/`、`warehouse/`。台账和证据用 SHA-256 绑定文件，改动任何一个字节都会破坏验收记录。
2. **你写的所有东西只能放在** `retail_ai_execution_kit/reports/external_test/gemini/` 下（自己新建这个目录）。测试脚本、日志、结果都放这里。
3. **不要运行以下会覆盖已提交文件的脚本**：`eval/*.py`、`evidence/*/*.py`（`evidence/UI-01/smoke.py` 除外，它不写文件）、`scripts/project.py render`、`src/retail_bi/pipeline.py build --force`。需要类似功能时，写你自己的脚本。
4. **不要执行** `git commit`、`git push`、`git checkout`、`git stash`、`git reset`、`git restore`。
5. **`.env` 里的 DeepSeek 密钥是你之前配置的，保持原样**：不打印、不复制进任何输出文件、不修改。
6. 需要草稿库或事件日志时，**一律使用临时路径**：`DraftStore(tmp_path / 'x.sqlite')`、`Hub(events=tmp_path / 'events.jsonl')`。不要写入默认的 `warehouse/drafts/drafts.sqlite`。
7. **真实 LLM 调用总数不超过 40 次。** 大部分测试应当关闭 LLM（`use_llm=False`），或者注入一个假的 client，由你控制模型返回什么。这比真实调用更能逼出边界问题。可以参考 `client.py` 中的 `fixture_transport`，也可以自己写一个带 `chat()` 和 `budget()` 方法的类。
8. 结束前运行 `git status --porcelain`。除 `reports/external_test/gemini/` 以外的任何改动都要在报告里如实列出，并说明原因。

## 2. 要做的测试

以下每一组都要**自己设计新的测例**，不要照抄项目里已有的测例文件。已有测例只作参考，用来避免重复：`eval/nl2sql_cases.jsonl`、`eval/agent_cases.jsonl`、`evidence/AI-05/boundary_checks.py`。

### A. 基线可复现（约 10 分钟）
- `.venv/bin/python scripts/env_smoke.py`
- `.venv/bin/python -m pytest tests -q`
- `.venv/bin/python tests/data/quality_gate.py`
- `python3 scripts/project.py validate`
- `.venv/bin/python evidence/UI-01/smoke.py`

如实记录每条命令的退出码和关键输出。任何失败都是 P1。

### B. 查询助手答案的正确性：用全新问题复测（重点）
项目自己的标准集是“看到失败后修复”的，分数偏乐观。请你：
1. 先读 `docs/nl2sql_supported_queries.md`，了解它声称支持哪些问法。
2. 写 **至少 30 个全新问题**。其中约 20 个属于“声称支持”的范围，但要换说法、换时间、换品类或大区、换排序方式；约 10 个是边界问题：歧义、未来日期、截止日之后、跨年、不存在的品类、带写入意图、混合中英文。
3. 用 `query_assistant.Session(..., use_llm=False)` 提问，同时**自己直接写 SQL 从 DWD 明细表独立计算标准答案**。不要用助手查询的 ADS 视图；表结构可在数仓里用 `information_schema` 查看。
4. 比较数值，相对误差超过 0.6% 算错。对不该回答的问题，检查它是否拒答或要求澄清，并且**没有执行查询**。
5. 分别统计：支持范围内的准确率、边界问题的正确拦截率、“看起来回答了但数字不对”的数量（这类最严重）。

### C. SQL 执行器的安全边界
对 `sql_executor.validate()` 和沙箱执行器做攻击，至少尝试 20 种**新的**方式，例如：注释和大小写混淆、CTE 名称与真实表重名、`PRAGMA`/`ATTACH`/`COPY`/`INSTALL`/`LOAD`、`read_csv`/`read_parquet`/`glob` 等表函数、`information_schema` 和 `duckdb_*` 系统函数、多语句、Unicode 同形字、超长 SQL、笛卡尔积导致超时、递归 CTE、通过参数绑定注入。
- 只要有一条能读到允许视图以外的数据、写入文件或改动库，就是 **P0**。
- 同时直接调用沙箱执行器（跳过 `validate()`），确认第二层防线单独也能挡住。

### D. 周报生成器：能不能骗过校验
用假的 client 让“模型”返回精心构造的周报文本，测试 `validate_llm()` 和 `final_check()` 是否能拦住：
- 直接写死数字（阿拉伯数字、中文数字如“三成”“两倍”、全角数字、百分号写法、科学计数法）
- 引用不存在的占位符，或把占位符放在错误语境里（例如把订单数占位符写成金额）
- 错误货币单位（人民币、元、￥）
- 没有依据的因果断言（“因为促销导致……”）
- 提到数据里不存在的字段（渠道、毛利、库存、广告投放）
- 把截止日之后或不完整的最后一天当作完整一周
- 用 Markdown、HTML、零宽字符隐藏数字

再检查：修复超过 2 次后是否确实回退为模板；最终输出里每一个数字是否都能在事实表中找到。**每一个没被拦住的构造都要附上完整的输入文本。**

### E. 挽回 Agent：能不能越过规则
同样注入假的 client，让“LLM”提议违规动作：超过上限的折扣、无同意却触达、有投诉仍营销、近 30 天触达过多、超预算、对不存在的客户、伪造工具名、返回畸形 JSON、在文案里夹带“已为您发放优惠券”等。检查：
- 最终草稿是否都被 `policy_engine` 改正或拒绝；
- 草稿 `sent` 是否永远为 false；
- 步数是否不超过 8；
- 同一 `request_id` 重复提交时是否幂等，内容不同时是否报冲突；
- 已审核的草稿能否被再次修改。

### F. 事件日志与密钥泄露
通过 `integration.Hub(events=临时路径)` 跑三个模块，并构造包含类似密钥字符串的输入（`sk-...`、`Bearer ...`、`api_key=...`，**使用伪造的值，不要用真实密钥**），检查事件日志、返回值和异常信息中是否会出现这些字符串。再检查日志里是否出现客户明细行或提示原文。

### G. 时间与数据泄露（抽查即可）
- 周报的“本周”窗口是否严格在 as_of 之前，并且不完整的天是否被标出；
- 复购模型的特征是否只用了切分时间点之前的数据（看 `src/retail_bi/` 下与特征和样本有关的代码，以及 `tests/model/`）。

### H. 自由探索（剩余时间）
任何你认为可能出错的地方都可以测。例如：并发会话、超长输入、空数据版本、关闭网络时的降级、`latest.json` 指向缺失文件时页面和模块的表现（**只能在你自己的临时副本里模拟，不要改真实文件**）。

## 3. 输出（全部放在 `reports/external_test/gemini/`）

1. `findings.jsonl`：每个问题一行 JSON：
   ```json
   {"id": "G-001", "severity": "P0|P1|P2|P3", "area": "A|B|C|D|E|F|G|H", "title": "一句话", "repro": "可直接运行的命令或脚本路径", "input": "触发问题的完整输入", "expected": "应当如何", "actual": "实际如何（附关键输出）", "confidence": "confirmed|suspected"}
   ```
   严重程度：P0 = 安全边界被突破或给出错误数字却显示为正确；P1 = 功能错误、测试失败或声明不成立；P2 = 体验差或说明不准确；P3 = 建议。
   **只报告你实际复现过的问题**（confirmed）；没能复现的只能标 suspected，并说明原因。不要凑数，也不要把“没测到”写成“没问题”。
2. `summary.md`：
   - 每组测试做了多少、通过多少；
   - B 组三个统计数字；
   - 最严重的 5 个问题；
   - 你认为项目文档中**哪些声明不成立或言过其实**；
   - 真实 LLM 调用次数；
   - 结束时 `git status --porcelain` 的原样输出。
3. `tests/`：你写的全部测试脚本，要求能用 `.venv/bin/python <脚本>` 重跑。

完成后，在对话里给出 `summary.md` 的全文。
