# DOC-01 登记与 DATA-01 交接记录

## 2026-11-09 20:25 +08:00（claude-opus-5-5）

### 1. 快照

- 执行者：claude-opus-5-5（Claude Code 桌面端），协调执行，自审
- 台账版本：DATA-01 done 后为 `e3abb72d958ece24313870189614abc3738362c18d4bd289e13ec8969d450f7b`
- 用户本轮指示：选题报告已完成，请核验登记，不要重写；`proposal-ready` 不得在缺数据准备证据时放行；前 4 项 GOV 任务保留；Intent Lens 暂时不作为阻断条件。

### 2. 实际完成

| 任务 | 动作 | 产物 | 证据 | 状态 |
|---|---|---|---|---|
| DOC-01 | 把用户的选题报告复制为 `deliverables/proposal.docx`（字节相同，原件未改）；抽取全文、pandoc 解析、Quick Look 渲染第 1 页；逐项对照规格 | `reports/submission/proposal_review.md`、`proposal_manifest.json` | `evidence/DOC-01/2026-11-09-proposal-review.json`（partial，不是通过证据） | in_review |
| GOV-03 | 把报告中的 5 名成员、学号、组长登记到 `ops/TEAM.md`，没有分配职责 | `ops/TEAM.md` | — | blocked（等待分工表） |
| DATA-01 | 联网核验 4 个候选；下载官网合成 ZIP，逐文件比对 | `docs/data_candidates.md` | `evidence/DATA-01/2026-11-09-source-review.json` | done |

### 3. 关键发现

1. 选题报告与项目规格基本一致，但缺少阶段一的数据预处理证据和成员分工（G1、G3）；孙卓学号的前缀与其他人不同（G4）。
2. 本地合成数据的 14 个文件与官网 baseline 逐一哈希相同，只是 ZIP 被重新打包过。网站下载件没有标明许可，仓库中 CC0 覆盖的是另一次运行（20260717）的样例；数据包自带 `DATA_SOURCE.md` 中的 CC0 说法不准确（该文件归属未知，没有修改）。
3. T-ECD 的 README 写明有 `price`/`count` 字段，与 PROJECT_SPEC 早先“零售分片仅 6 列、无金额”的结论不一致，需要 DATA-02 实读确认。

### 4. 未验证

- 选题报告第 2～4 页没有逐页渲染；参考文献没有核验原文。
- A、C、D 没有全量下载。
- 选题报告的提交状态未知。

### 5. 下一步精确入口

1. **GOV-06**（可做）：`python3 scripts/project.py show GOV-06`，冻结轻量架构和公共接口草案；产出可以作为选题报告的架构附图。
2. **DOC-04**（可做）：从 `docs/reference_registry.md` 的 [1]–[12] 开始，按主张逐条核验。
3. **GOV-07**（依赖 GOV-06）：用 `uv` 和 Python 3.12 建立环境。之后 **DATA-02** 实读 B 和 A。
4. 需要用户：分工表（GOV-03）、孙卓班级、教师对 D001/D006 的答复、选题报告是否已提交及回执。
