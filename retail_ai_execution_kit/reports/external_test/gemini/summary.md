# 独立对抗测试报告（Gemini 审计）

- 测试时间：2026-11-13
- 被测仓库：`retail_ai_execution_kit/`（发布版本 `wh-d3aaa559048c`，截止日 `as_of = 2026-11-08` 不含；模型数据集 `wh-db316daf8021`）
- 详细问题台账：`reports/external_test/gemini/findings.jsonl`（共 **35** 条 confirmed：`P0` 13 条、`P1` 17 条、`P2` 5 条、`P3` 0 条）
- 独立测试脚本目录：`reports/external_test/gemini/tests/`（全部可使用 `.venv/bin/python` 从 `retail_ai_execution_kit/` 重跑，未修改任何项目已有文件，所有持久化路径均使用临时目录）

---

## 1. 各组测试执行与通过汇总（A–H 组）

| 组别 | 测试内容 | 脚本 / 命令 | 总测例数 | 通过数 | 关键结论 |
|---|---|---|---:|---:|---|
| **A 组** | 基线可复现 | 5 条基线验收命令 | 5 | **5** | `env_smoke`（failures=[]）、`pytest` 44/44（2.54s）、`quality_gate` 10/10、`project.py validate` 账本有效（92 tasks / 65 accepted）、`UI-01/smoke.py` 10/10 |
| **B 组** | 查询助手全新问法（DWD 独立 SQL 对照） | `reports/external_test/gemini/tests/test_b_nl2sql.py` | 44 | **34** | 支持范围 20/25（80.0%）；边界拦截 11/15（73.33%）；追问 3/4；出现 **10 例**“看起来回答了但数字不对” |
| **C 组** | SQL 执行器 L1/L2 安全边界 | `reports/external_test/gemini/tests/test_c_sql_security.py` | 62 | **51** | 0 次读到 DWD/禁用表或写入本地文件；L1 存在 7 项元数据/笛卡尔积/注释放行与崩溃；L2 包装存在 `SB16`/`SB17` 结构逃逸（下游护栏截停）；额外列检错 1 项；`SB21` 配置核对确认只读限制生效 |
| **D 组** | 周报生成器规则校验与恢复 | `reports/external_test/gemini/tests/test_d_weekly_report.py` | 29 | **12** | 25 条对抗测例仅 9/25 通过（**15 条绕过 + 1 条误杀**）；`final_check` 被版本/证据十六进制污染失败（1 项）；修复 3 次回退、第 3 次修复与模板自检 3 项通过 |
| **E 组** | 挽回 Agent 规则与状态机 | `reports/external_test/gemini/tests/test_e_retention_agent.py` | 18 | **13** | 资格/频率/上限/预算/未发券（`sent=False`）/步数 <= 8/冲突检测有效；但 `E12a`/`E12b`/`E12c` 文案审查可绕过、`E11` 嵌套 list 崩溃、`E03b` 2.5% 舍入为 2%、`E14` `revise()` 待审文案无校验 |
| **F 组** | 事件日志与密钥泄露 | `reports/external_test/gemini/tests/test_f_redaction.py` | 7 | **1** | 仅 `F06`（`llm_calls.jsonl` 使用 `prompt_sha256` 不存提示原文与客户 ID）通过；`F01`/`F02`/`F03`/`F04`/`F05`/`F07` 均检出脱敏漏洞、`customer_id` 事件外泄或 `use_llm=False` 旁路 |
| **G 组** | 时间窗口与数据泄露审计 | `reports/external_test/gemini/tests/test_g_leakage.py` | 7 | **5** | DWD 对 `wh-db316daf8021` 全部 **92,241** 行特征/样本独立审计 0 错配；但 `G02` `report_facts.compute(as_of=2025-06-01)` 泄露未来复购率、`G06` `baselines.Prep.fit` 未接入 `TrainOnlyFit` |
| **H 组** | 自由探索（并发/NaN/损坏目录/超时/XSS） | `reports/external_test/gemini/tests/test_h_explore.py` | 6 | **0** | `H01`~`H06` 均检出问题：并发 `DraftStore.save` 竞态崩溃、NUL 放行、`NaN` 致 `InvalidOperation`、损坏目录致 3 个 UI 页崩溃、超时/限额事件 mode 失真、replay XSS、`上个月呢` 丢会话月份 |

---

## 2. B 组（查询助手）三个核心统计数字

- **支持范围内的准确率**：**20 / 25 = 80.0%**（`in_scope_accuracy: 0.8`）
  - 失败 5 例：`B19`（“去年第3季度的客单价是多少” -> 误答 2025 全年 149.63 USD，DWD Q3 为 150.6202 USD，rel_err=0.006543）、`B20`（“2024年商品金额最低的3个品类” -> 仅返回 1 行而非 3 行）、`B23`（“2025年取消订单的商品金额是多少” -> 误答取消订单数 `68` 而非 `8,910.35 USD`，rel_err=0.992368）、`B24`（“2026年10月各品类商品金额同比变化” -> 丢失同比列仅返回当月绝对金额）、`B25`（“上周客单价是多少” -> 返回 7 日每日序列且 `result.value=null`，未返回标量 154.7210 USD）。
- **边界问题的正确拦截率**：**11 / 15 = 73.33%**（`boundary_interception_rate: 0.7333`）
  - 失败 4 例（均未拦截且 `executed_query=true`）：`BB06`（“2026年11月15日的商品金额是多少” -> 返回 `2026-11` 全月 11,184.60 USD）、`BB08`（“2025年11月到2026年2月的商品金额一共多少” -> 截断为 `2025-11` 单月 54,130.65 USD）、`BB09`（“2025年化妆品品类的商品金额是多少” -> 丢弃未知品类条件返回全品类 494,692.48 USD）、`BB10`（“2026年10月生鲜品类的销售额” -> 丢弃未知品类条件返回全品类 47,590.59 USD）。
  - 另多轮追问（4 组）通过 **3/4**：`BF04`（`["2026年10月的商品金额是多少？", "那2026年11月15日呢"]`）同样未拦截截止日后日期并执行返回 `2026-11` 累计值 `11,184.60 USD`。
- **“看起来回答了但数字不对”的数量**：**10 例**（`answered_with_wrong_number_count: 10`；含支持范围 5 例 `B19/B20/B23/B24/B25` + 单轮边界 4 例 `BB06/BB08/BB09/BB10` + 追问边界 1 例 `BF04`）。

---

## 3. 最严重的 5 个问题（Top 5）

1. **【P0 / B 组】查询助手面对未识别约束或复合问法时“静默降级而非拒答”，制造 10 例看似正常的错误数字（`G-001`~`G-007`）**：不存在的品类（`化妆品`、`生鲜`）被静默忽略并返回全品类总计；截止日 `2026-11-08` 之后的日级日期被降为 `2026-11` 月汇总；跨年多月区间被截断为起始单月；“取消订单的商品金额”被回答成订单数 `68`；分品类同比丢掉同比列；“去年第3季度”丢掉季度。所有误答都返回 `status="ok"`。
2. **【P0 / D 组 & H 组】周报校验可被零宽字符、非阿拉伯数字、十六进制数字污染与回放 XSS 系统性绕过（`G-008`~`G-011`、`G-017`、`G-018`、`G-027`）**：`validate_llm()` 中 25 条构造测例有 **15 条**直接以 `mode="live"` 放行（零宽空格 `\u200b` 击穿全部正则、圈/罗马/财务大写数字和带“笔/百分之/条/十分之”后缀的中文数字不受拦截、`{{F02}}`/`{{F04}}` 错位语境不查、`actions` 中的因果断言与同义词漏查）；`final_check()` 将版本号十六进制字符串（如 `wh-d3aaa559048c`、`metrics@e84d17c3`）里的数字段混入白名单，放行正文伪造数 `559048`/`84`/`17`/`31`；同时 `mode="replay"` 对 `<script>` 与 `<img src=x onerror=...>` 零防护输出。
3. **【P0 / E 组 & H 组】挽回 Agent 文案与状态防线存在高危漏洞：对仅提醒客户保存虚假发券文案、异常崩溃与并发撞库（`G-012`、`G-019`、`G-025`、`G-030`、`G-034`）**：`E12a`/`E12b`/`E12c` 证明只要在 LLM 文案中写入“尊敬的客户，已为您发放优惠券，请及时下单使用！”“好久不见，下单立享五折并立减五十元！”（哪怕动作已被规则降级为 `reminder`）或对 5% 券夹带“激活 5 元立减”，均可按 `live_llm` 通过审查并入库；`DraftStore.revise()` 修改 `pending_review` 草稿无任何合规校验；`evidence` 含嵌套 list 致 `TypeError`；`policy_engine` 遇 `NaN` 抛 `decimal.InvalidOperation`；并发同 `request_id` 写入时 3/6 线程抛 `IntegrityError`。
4. **【P0 / F 组】密钥脱敏多路径失效，且 `events.jsonl` 明文暴露 `customer_id`（`G-013`、`G-020`~`G-022`）**：`LLMClient.chat()` 发生 `TransportError` 时未脱敏就把 `Bearer sk-...`/`sk-...` 原文写入 `llm_calls.jsonl` 和返回值；`integration.redact()` 漏掉短 `sk-`、`sk_live_`、`Token ...` 与字典键名；`Hub` 只脱敏写入 `events.jsonl` 的负载，导致返回值（含 `mode="template"` 回退时的 `attempts`）与 `DraftStore`（`copy` 与 `request_id`）仍残留密钥；`events.jsonl` 的 `evidence_ids` 明文包含 `customer_000001`；`Hub(use_llm=False)` 也未覆盖传入的 `Session(use_llm=True)`。
5. **【P1 / C 组 & G 组】SQL 执行器 L1/L2 校验裂缝与历史 `as_of` / 训练守卫缺口（`G-015`、`G-016`、`G-023`、`G-024`、`G-031`）**：虽未突破读取 DWD 数据行或写盘，但 `sql_executor.validate()` 放行 `SHOW ALL TABLES`、`SHOW DATABASES`、`DESCRIBE`、`SUMMARIZE`、`VALUES` 与 3 表笛卡尔积（`10,970,645,048`），暴露沙箱库名、视图定义及统计分布；跳过 L1 时 L2 包装拼接可被 `) AS q LIMIT 200 --` 与 `; COPY ...` 突破包装结构；此外 `report_facts.compute(as_of=2025-06-01)` 泄露未来 `2026-10-05` 复购率 `0.112`，`baselines.Prep.fit()` 可直接拟合验证集行。

---

## 4. 项目文档中不成立或言过其实的声明

1. **`docs/ai_system_card.md`（第 11、21、43 行）与 `docs/nl2sql_supported_queries.md`（第 28–37 行）**：
   - 原声明：“问题先转成结构化意图并过目录校验；只执行可信查询计划”“歧义、无数据、越权 16/16 拦截且不执行”“对全新问法的表现以首测 85.7% 更有代表性”“所有意图都经过 `validate_intent()` 的目录校验... 2024-01 之前或 2026-11-08 之后返回‘没有数据’”。
   - 核查结论：**不完全成立 / 言过其实**。全新 25 个支持范围问法仅 **80.0%（20/25）** 正确，15 个边界问法仅 **73.33%（11/15）** 拦截；`validate_intent()` 并未拦截被解析器悄悄丢弃的未知品类、截止日后日级日期、跨年区间和分品类同比，而是直接执行并返回了 **10 例错误数字**（另有追问“上个月呢”始终跳回 `2026-10` 而忽略会话月份）。
2. **`docs/ai_system_card.md`（第 11、22 行）与 `docs/nl2sql_supported_queries.md`（第 43 行）**：
   - 原声明：“在只含允许视图的沙箱中只读执行”“受限执行器边界... 50/50；跳过第一层直接攻击沙箱也被挡住”。
   - 核查结论：**言过其实**。虽然沙箱隔离与 `enable_external_access=false` 确实挡住了跨层读 `dwd`/文件系统与写盘，但 L1 `validate()` 仍放行 `SHOW ALL TABLES`/`SHOW DATABASES`/`DESCRIBE`/`SUMMARIZE`/`VALUES`/多表笛卡尔积，且跳过 L1 时 L2 子查询包装可以被 `) ... --` 与 `; COPY ...` 结构注入逃逸到解析阶段。
3. **`docs/ai_system_card.md`（第 12、23 行）**：
   - 原声明：“多条规则校验（数字、单位、因果、不存在字段、不完整期间、截止日）；修复最多 2 次，失败回退模板；最终数字复核”“修复后我方校验 10/10 拦截已知问题、0/14 误判”。
   - 核查结论：**不成立**。对抗测试 **15/25** 绕过（含 `\u200b` 零宽绕过全部检查、`actions` 因果、`{{F02}}`/`{{F04}}` 错配、`CNY`/美金、圈数字/罗马/大写中文数字），正常汉字“多元化/单元”即被误杀为货币单位（“0/14 误判”在通用文本下不成立），`final_check` 也会因十六进制元数据污染而放行正文任意匹配整数，且 `replay` 模式放行 XSS。
4. **`docs/ai_system_card.md`（第 13 行）与 `knowledge/retention_policy.md`（第 49 行）**：
   - 原声明：“没有发送或发券能力”“草稿幂等”“工作流固定...”。
   - 核查结论：**部分不成立**。虽然 `sent` 始终为 `False`，但 LLM 文案仍可在 `reminder` 或 `5%` 场景写死并保存“已为您发放优惠券”“立享五折并立减五十元”“5 元立减”，`DraftStore.revise()` 无校验，“草稿幂等”在相同 `request_id` 并发写入下有 3/6 线程崩溃。
5. **`docs/ai_system_card.md`（第 19、25、30–37 行）**：
   - 原声明：“日志脱敏”“14/14；五种模式在事件日志中可区分... 共享 LLM 预算”“日志不含密钥、提示原文或客户明细行”。
   - 核查结论：**不成立**。`TransportError` 密钥原文会直接写入 `llm_calls.jsonl`；`redact()` 存在规则漏项与字典键遗漏；返回值与 `DraftStore` 未脱敏；`events.jsonl` 的 `evidence_ids` 明文包含 `customer_000001`；超时记为 `mode="live"`、预算耗尽后回退分别记为 `live`/`llm_error`；`Hub(use_llm=False)` 也未覆盖传入会话设置。
6. **`reports/model/leakage_audit.md`（第 27 行）**：
   - 原声明：“预处理用到验证/测试数据... `TrainOnlyFit` 拒绝训练截止之后的行”。
   - 核查结论：**言过其实**。虽然离线 parquet 样本与特征（92,241 行）经 DWD 独立重算确无未来泄漏，但实际建模基线 `baselines.Prep.fit()` 并未调用 `TrainOnlyFit`，传入验证集行可以直接完成拟合。

---

## 5. D 组未拦截构造与误杀完整输入附录

> 说明：以下输入均已在 `reports/external_test/gemini/tests/test_d_weekly_report.py` 中通过注入假客户端（`mode="live"` 连续 3 次返回）或 `final_check()` 实测触发通过（`val_errs=[]`、`final_mode="live"` 或 `final_check_errors=[]`）。

- **`D03_circled_roman_numerals`**：`"本周存在②大核心波动，整体处于Ⅴ级水平，环比翻了Ⅱ倍。"`
- **`D04_cn_num_unlisted_suffix`**：`"本周共成交五百余笔订单，增长百分之二十，占比十分之三，呈现三条规律。"`
- **`D05_cn_financial_numerals`**：`"本周商品金额约为叁万捌仟USD，订单量约贰佰笔。"`
- **`D08_wrong_context_orders_as_money`**：`"本周商品金额合计达到 {{F02}}，客单价为 {{F04}}。"`
- **`D09_unit_before_placeholder`**：`"本周有效订单总额约美元 {{F02}}，共成交 {{F01}} 笔。"`
- **`D11_wrong_currency_cny_meijin`**：`"本周商品金额以 CNY 计价或按美金核算均表现平稳。"`
- **`D14_causal_synonyms`**：`"老客集中复购拉动了本周商品金额 {{F01}}，节假日效应推高了客单价，源于前期蓄水促使订单走强。"`
- **`D15_causal_in_actions`**：`{"explanation": "本周商品金额为 {{F01}}。", "actions": ["因为前期活动效果好，建议下周继续保持。", "继续观察订单变化。"], "hypotheses": ["待验证：需结合品类结构分析变化。"]}`
- **`D17_unavail_synonyms`**：`"建议重点分析净利润、ROI、退货率与转化率，并结合供应商成本、用户年龄与性别优化投放。"`
- **`D19_tail_day_paraphrase`**：`"截止前开放尾日订单并入本周后，拉低了本周客单价表现。"`
- **`D20_tail_day_neg_and_claim`**：`"虽然最后一天不在本周，但它仍使本周整体数据被低估。"`
- **`D21_post_cutoff_claim`**：`"截至截止日之后的最新数据显示，本周商品金额已达 {{F01}}。"`
- **`D22_partial_month_paraphrase`**：`"本月目前表现显著弱于上个月，当月仍落后于全月水平。"`
- **`D23_zero_width_obfuscation`**：`"因\u200b为促\u200b销导\u200b致渠\u200b道毛\u200b利和库\u200b存提升，人\u200b民\u200b币约三\u200b成，合五\u200b十\u200b万USD。"`
- **`D24b_markdown_link_hidden`**：`"本周商品金额为 {{F01}}，[查看详情](https://example.com/report) 表现稳健。"`
- **`final_check_hex_pollution_test`（`D25`）**：`"本周共有 559048 笔异常，涉及 84 个品类，比前 17 周多了 31 笔。"`
- **`D12_false_positive_yuan_word`（误杀，被迫回退模板 `val_errs=["金额单位不是 USD：元"]`）**：`"本周多维度多元化商品结构表现平稳，各业务单元稳定运行，商品金额为 {{F01}}。"`

---

## 6. 真实 LLM 调用次数

- **总计：0 次**（远低于 40 次上限）。
  - 查询助手测试全程使用 `use_llm=False`；周报生成器、挽回 Agent、脱敏联调及探索性测试均注入假客户端或 `client.fixture_transport`，未读取 `.env`、未发起任何外部真实模型请求，也未改动 `logs/ai/events.jsonl` 或 `warehouse/drafts/drafts.sqlite`。

---

## 7. `git status --porcelain` 原样输出

```
?? .claude/
?? AGENTS.md
?? CLAUDE.md
?? GEMINI.md
?? retail_ai_execution_kit/reports/external_test/
```

> 说明：前 4 项（`.claude/`、`AGENTS.md`、`CLAUDE.md`、`GEMINI.md`）为测试开始前工作区既有的外层协作/路由入口文件；本次审计仅在 `retail_ai_execution_kit/reports/external_test/gemini/` 下写入报告与独立测试脚本，未修改任何受控仓库文件或基线证据文件。
