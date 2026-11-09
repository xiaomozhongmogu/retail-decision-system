# GOV-08 认领、证据与交接流程冒烟检查

- 任务：GOV-08；验收规格哈希 `5428bd5927aea2915a78b0ad0307f4c39acd2c510ce75763c8681c9137672335`
- 执行：claude-opus-5-5（Claude Code 桌面端），2026-11-09 20:04–20:10 +08:00；自审
- 运行记录：`evidence/GOV-08/smoke_run.log`。第一次运行时，项目路径含空格，被 `eval` 拆开，反例脚本没有执行；原始失败日志保留为 `smoke_run_attempt1_failed_quoting.log`，修正引号后重跑。
- 说明：本任务在台账中的认领（in_progress）晚于第一轮冒烟运行，顺序如实记录在此。

## 1. 治理脚本实际运行结果（条件 1）

| 命令 | 退出码 | 结果 | 解读 |
|---|---|---|---|
| `python3 scripts/test_project_tool.py` | 0 | 13 个测试通过 | 只是治理工具的自测夹具，不是业务证据 |
| `python3 scripts/project.py validate` | 0 | `ledger_valid`，accepted=2（GOV-01、GOV-02） | 只说明台账结构和已声明的证据完整 |
| `python3 scripts/project.py next` | 0 | 可认领 GOV-03、GOV-05、GOV-08；GOV-04 为 blocked | 符合依赖关系 |
| `python3 scripts/project.py gate proposal-ready` | 2 | blocked，23 项中 2 项已验收 | 预期的阻断，不是待修的缺陷 |
| `python3 scripts/project.py gate midterm-ready` | 2 | blocked | 同上 |

阶段关卡返回 2 是正确的阻断结果。不能为了让关卡通过而修改脚本、删除任务或伪造证据。

## 2. 单写者、认领与交接示例（条件 2）

### 2.1 台账单写者

- `project/tasks.json` 的 `coordinator` 已写为本会话（claude-opus-5-5，2026-11-09 会话）。本会话期间，只有协调者写台账。
- 写台账时使用基线哈希比对：先计算当前 SHA-256，写入前再比对，不一致就拒绝写入，避免用旧副本覆盖新台账。本会话的台账版本链：

| 时刻 | 动作 | 台账 SHA-256（前 8 位） |
|---|---|---|
| 初始包 | — | `8520f5d7` |
| 认领 GOV-01 | coordinator＋GOV-01 in_progress | `a57cbb95` |
| GOV-01 done | 证据＋self_review | `6a1e0781` |
| GOV-02 done，GOV-04 blocker 补充 D006 | 证据＋self_review | `733c3bf1` |
| 认领 GOV-08 | in_progress | `e056b0f2` |

- 下一位协调者接手时，应先比对台账当前哈希与最近一份交接记录中的哈希；不一致说明有人改过，要先合并。
- 其他 AI 或成员（非协调者）只提交补丁和证据，由协调者写台账。

### 2.2 一次完整的认领→证据→交接示例

GOV-01 与 GOV-02 是本会话的真实示例，不是演示夹具：

1. 认领：`status: todo → in_progress`，填写 `owner`。
2. 执行，并在 `evidence/<task_id>/` 写证据 JSON：`task_spec_sha256` 取自 `show`，`inputs`/`artifacts` 绑定实际哈希，每条验收条件给出 finding。
3. 标 done：填写 `reviewer`、`review_mode=self_review`，`evidence` 数组只引用当前通过的证据。
4. 运行 `validate` 和 `render`。
5. 交接：`worklogs/GOV-01-claude-opus-5-5-2026-11-09.md`、`worklogs/GOV-02-claude-opus-5-5-2026-11-09.md`，按 `templates/HANDOFF.md` 写明台账版本、证据、未验证范围和下一步入口。

### 2.3 并行代理目录互斥

`evidence/GOV-08/scope_overlap.py` 统计了没有依赖先后关系、但 `allowed_scope` 有路径重叠的已选任务对，共 150 对（日志：`scope_overlap.log`）。重叠最多的目录是 `reports/ai`（51 对）、`docs`（34 对）、`src/retail_bi/ai`（29 对）、`src/retail_bi`（17 对）。

由此得出的规则：

- 只有 `allowed_scope` 不重叠的任务才能并行，分别交给不同代理，或者使用独立工作树或分支。
- 有重叠的任务串行执行，或者由协调者把写入路径细分到文件后再并行。例如 AI 各子任务在 `reports/ai/<task_id>/` 下各写各的。
- 当前可认领的三项中，GOV-03 与 GOV-08 在 `ops`、`reports/governance` 有重叠，所以本会话串行处理；GOV-05 只写 `docs`，可以与它们并行。
- 共享契约（`contracts/`）、台账、依赖锁文件只由协调者集成。
- 文字里写“我已认领”不是锁；没有可靠的协调机制时保持串行。

## 3. done 必须有真实证据（条件 3）

在台账的**临时副本**上制造违规，验证 `validate` 会拒绝（脚本：`evidence/GOV-08/negative_tests.py`；真实台账没有被修改，副本运行后已删除）：

| 用例 | 制造的违规 | validate 退出码 | 校验器给出的拒绝原因 |
|---|---|---|---|
| BASE | 未修改的副本 | 0 | 无 |
| NEG1 | GOV-05 标 done，但没有产物也没有证据 | 1 | 缺失产物、done 但无证据、验收条目 1–3 缺通过证据、产物未绑定 |
| NEG2 | GOV-01 登记证据后篡改产物 | 1 | 证据失效、文件已变更，应标 stale |
| NEG3 | GOV-03 标 in_progress 但没有 owner | 1 | 活动任务须记录 owner |
| NEG4 | GOV-08（execution_required）只用静态审阅证据标 done | 1 | 必须有实际运行证据，静态审阅不足 |
| NEG5 | 修改 GOV-01 的验收条件 | 1 | 规格哈希失配，旧证据须重验 |

同时要明确：

- 校验器只做机械检查。它确认证据文件存在、哈希匹配、每条条件都写了 passed 和 finding，但**不能判断 finding 是否真实、业务口径是否正确**。NEG4 中只要换成 `method: command` 并写上退出码 0，就能骗过机械检查。因此证据内容必须有人复核，自审要如实标为 `self_review`。
- 退出码 0、生成了文件、`render` 成功，都不等于业务任务完成。关卡通过也不等于已提交（`final-submitted` 需要真实回执）。

## 4. 发现与建议

1. 校验器没有限制 `review_mode=self_review` 的任务数量。目前全部 done 任务都是 AI 自审。建议在 DOC/REL 阶段前，让真实成员对关键任务（DATA-03、ML-09、AI-15 等）做 `human` 或 `mixed` 复核。
2. 证据只能引用项目内的文件，上级目录的数据包无法直接绑定。DATA-05 应把原始 ZIP 复制到 `data/raw/`（已被 `.gitignore` 排除），再在项目内登记哈希。
3. 项目没有 Git。C23 和 TEAM.md 需要真实提交历史，建议用户尽早初始化仓库（不可逆的远程推送另行确认）。

## 5. 本次未验证的范围

- 没有测试多个 AI 真正同时写台账的情况，也没有测试工作树或分支合并（本环境没有 Git）。
- 没有测试 `gate final-submitted` 和 `stale` 状态的流转。
- 校验器本身的源码只读过关键段落，没有做完整审计。
