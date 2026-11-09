# 公共接口契约（草案 v0.2）

当前只定义约定，**没有实现任何业务接口**。DATA-03/04 完成后由集成者统一冻结；接口变更需要同步调用者与相关证据。

- v0.1：初始执行包（2026-11-05）。
- v0.2：GOV-06（2026-11-09，claude-opus-5-5）。在 v0.1 的基础上补充结果信封字段、错误码、单位、空结果语义、版本字段和每个接口的粒度。v0.1 的语义没有删除或改变，因此不影响任何已有证据。

## 1. 通用结果信封

每个服务都返回同一种结构：

```json
{
  "status": "ok | empty | unsupported | error",
  "data": {},
  "as_of": "2026-11-01T00:00:00+08:00",
  "window": {"start": "…", "end": "…", "closed": "left"},
  "dataset_version": "src=<uci|synthetic>;rel=<release_id>",
  "metric_version": "metrics@<hash8>",
  "model_version": "lgbm-<date>-<hash8> | null",
  "units": {"<field>": "GBP | USD | count | customers | ratio | probability | days"},
  "mode": "live | replay | fixture",
  "evidence_ids": ["sql:<hash8>", "doc:<id>@<ver>"],
  "warnings": [{"code": "…", "message": "…"}],
  "error": {"code": "…", "message": "…", "retryable": false} 
}
```

| 字段 | 规则 |
|---|---|
| `status` | `ok`：有结果。`empty`：查询合法但没有符合条件的数据（例如所选期间没有订单），此时 `data` 为空集合，不是错误。`unsupported`：请求超出支持范围（母体外客户、未开放的字段或指标、数据中不存在的维度）。`error`：执行失败。**不能用空数组代替 `error` 或 `unsupported`。** |
| `as_of` | 计算所依据的时点，ISO-8601，带时区。所有特征和快照都只使用 `as_of` 之前的信息。没有时点概念的接口（如 `retrieve_policy`）填写检索时间。 |
| `window` | 时间窗，统一左闭右开 `[start, end)`。 |
| `dataset_version` | 数据来源＋发布快照 ID。在线接口只读取已发布的快照。 |
| `metric_version` | `contracts/metrics.json` 冻结版本的哈希前 8 位。 |
| `model_version` | 只有与模型相关的接口才填写，其余为 `null`。 |
| `units` | 每个数值字段的单位。金额单位随路线而定（A 为 GBP，B 为 USD），不允许跨路线混算或只写“元”。比率用 0～1 表示，页面再格式化为百分比。 |
| `mode` | `live` 表示实际执行；`replay` 表示离线回放；`fixture` 表示测试夹具。`replay` 和 `fixture` 不能当作在线成功的证据。 |
| `evidence_ids` | 可回溯的依据：SQL 文本的哈希、知识库文档 ID 与版本、模型卡版本等。 |
| `warnings` | 不影响结果但需要提示的情况，例如 `immature_cohort`、`partial_period`、`zero_denominator`。 |
| `error` | 只在 `status=error` 或 `unsupported` 时填写，给出可展示的错误码和是否可以重试。 |

数值规则：金额在计算层用固定精度的十进制，展示格式不能改变计算值；分母为 0 时返回 `null` 并附 `zero_denominator` 警告，不返回 0；未成熟的 cohort 返回 `null` 并附 `immature_cohort`。

## 2. 错误码

| 错误码 | 状态 | 含义 | 可重试 |
|---|---|---|---|
| `invalid_argument` | error | 参数格式错误或缺失 | 否 |
| `out_of_population` | unsupported | 客户不在模型母体内（例如过去 90 天没有有效购买） | 否 |
| `unknown_field` / `unknown_metric` | unsupported | 字段或指标不在白名单内 | 否 |
| `capability_not_supported` | unsupported | 数据不支持该能力（如浏览漏斗、渠道、毛利） | 否 |
| `ambiguous_question` | ok（`data.clarification`） | 问题有歧义，需要澄清，不算失败 | — |
| `query_rejected` | unsupported | 请求的操作被受限执行器拒绝（写操作、ATTACH、COPY、外部文件、无限结果） | 否 |
| `timeout` / `row_limit_exceeded` | error | 超出资源限制 | 是 / 否 |
| `llm_unavailable` | error | 缺凭据、网络或厂商失败；页面显示降级状态 | 是 |
| `validation_failed` | error | 生成的文字中数字、单位、期间或引用与事实 JSON 不一致 | 否（需要重新生成或降级为模板） |
| `budget_denied` / `not_eligible` | ok（`data.decision=deny`） | 业务规则判定为拒绝，是正常结果，不算故障 | — |
| `snapshot_unavailable` | error | 没有已发布的快照 | 否 |

## 3. 接口一览

| 接口 | 输入 | 输出粒度与限制 | 版本字段 | 负责任务 |
|---|---|---|---|---|
| `get_kpis` | 时间范围、真实维度筛选、数据版本 | 每个指标一行：值、单位、覆盖率、可比周期状态 | dataset, metric | DW-06、UI-03 |
| `query_olap` | 白名单指标、维度、筛选、粒度（日/周/月） | 维度组合×指标的有限结果（默认最多 5,000 行），附使用的指标口径 | dataset, metric | DW-08、UI-03 |
| `get_customer_profile` | 客户 ID、as_of、数据版本 | 一位客户在 as_of 时的一行快照：真实可得特征、生命周期状态、价值群、缺失与母体资格 | dataset, metric | DW-05、EDA-05、ML-05 |
| `get_risk_score` | 客户 ID、as_of、模型版本 | 一位客户一行：复购概率、未复购风险（=1−P）、适用性、模型说明；母体外返回 `out_of_population` | dataset, model | ML-11 |
| `answer_business_question` | 问题、会话筛选、允许视图 | 澄清，或查询结果＋SQL/参数＋解释＋证据；不开放任意 SQL 执行 | dataset, metric | AI-04～07 |
| `build_weekly_facts` | 完整期间、比较期间、版本 | 一份事实 JSON：每个事实都带单位、窗口和 evidence_id；不完整的期间附 `partial_period` | dataset, metric | AI-08 |
| `generate_weekly_report` | 已核验的事实、检索到的知识 | 一份报告：数字经过校验，带引用、生成模式和降级状态 | dataset, metric, prompt | AI-09 |
| `retrieve_policy` | 任务类型、适用时间 | 规则片段列表：来源、版本、是真实规则还是**演示配置** | knowledge | AI-02、AI-11 |
| `check_budget` | 策略、预算、资格与频率配置 | 一次判定：allow/deny、原因、确定性成本 | policy | AI-11 |
| `save_draft` | 客户引用、草稿、证据、规则版本 | 草稿 ID（幂等键）和待审状态；不发送消息、不发券 | policy | AI-13 |

时间窗统一采用左闭右开；时间单位和原点先验证。禁止把明细数据无限制地传给 LLM：传给 LLM 的只能是聚合结果或限定行数的样本。

## 4. 接口演进

变化记录内容：任务 ID、原语义、新语义、原因、受影响的 SQL/模型/页面、版本变化、需要重验的证据。
常规实现修复可以自主继续；改变用户要求、数据可用边界、付费或外发范围，或遇到无法判断的教师口径时，才需要相应确认。
