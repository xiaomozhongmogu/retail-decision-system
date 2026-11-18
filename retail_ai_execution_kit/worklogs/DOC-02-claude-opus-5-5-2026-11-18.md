# DOC-02 交接（claude-opus-5-5，2026-11-18）

## 1. 快照与接手范围

- 实际记录时间：2026-11-18 约 11:35 +08:00
- 任务 ID / 本轮执行者：DOC-02 / claude-opus-5-5（用户在本会话中指示“Start DOC-02”）
- 角色：起草与渲染核验；审阅、演练、提交由组员承担
- 台账：`project/tasks.json` SHA-256 `0fa647c1…e147`（本次更新后）；基线提交 `ea55ef1`
- 版本：发布 `wh-d3aaa559048c`，模型 `repurchase-logreg-v1`，数据完全合成
- 所有权：本轮结束即释放。DOC-02 为 `in_review`，剩余项由组员完成

## 2. 本次实际完成的工作

| 动作 | 文件 | 对应条件 | 证据 |
|---|---|---|---|
| 从结果文件生成 6 张图，含架构图 | `evidence/DOC-02/charts.py`、`chart_sources.json`、`lifecycle_latest.json` | 1、C28 | `evidence/DOC-02/2026-11-18-midterm-draft.json` |
| 生成中期检查报告，共 15 页 | `deliverables/midterm_report.docx`（生成脚本 `evidence/DOC-02/report.js`） | 1、2 | 同上；Word 渲染 `render_midterm_report_word.pdf` |
| 生成答辩 PPT，共 15 页，每页有演讲备注 | `deliverables/midterm_slides.pptx`（生成脚本 `evidence/DOC-02/deck.js`） | 1、2、3 | 同上；PowerPoint 渲染 `render_midterm_slides_powerpoint.pdf` |
| 编写演示脚本和 20 题问答 | `reports/submission/midterm_defense_prep.md` | 3 | 同上 |
| 编写提交清单，列出 6 项缺口 | `reports/submission/midterm_manifest.json` | 3 | 同上 |
| 更新台账：DOC-02 改为 in_review，写入 state_note | `project/tasks.json`；重新生成 `TASKS.md`、`STATUS.md` | — | `scripts/project.py validate`：ledger_valid |

## 3. 验证范围与真实结果

| 步骤 | 是否执行 | 结果 | 未覆盖 |
|---|---|---|---|
| pptx `validate.py` | 已执行 | All validations PASSED | PowerPoint 的修复提示只能靠实际打开来发现。已用 PowerPoint 16.115 打开，没有出现修复提示 |
| Word / PowerPoint 导出 PDF，逐页目视检查 | 已执行 | 第一轮发现并修正：架构图箭头穿过方框、命令折行、标题对齐、数据标签取整、几处换行。修正后复查改过的页 | 只在 macOS 上检查；Windows 的中文字体替换没有检查 |
| 扫描 undefined / NaN | 已执行 | 0 处 | — |
| 降级与回放模式的措辞与 `docs/ai_system_card.md` 核对 | 已执行 | 已修正：回放只适用于周报 | — |

数字在生成时读取以下文件：`eda_initial`、`cluster_metrics`、`test_metrics`、`model_selection`、`etl_run`、`tasks.json`、AI 评测文件、`test_summary`、ADS 视图 `lifecycle_mix_weekly`。另有几处数字引自已验收的报告正文：量价分解的 −11,689 / +11,546、cohort 6.7%–8.7%、180 天复购率约 35%、外部测试首测 80%–86%、周报 25/25 与 10/10，出处是 `decision_brief.md`、`reflection_and_roadmap.md` 和证据索引。

## 4. 尚未解决的事项

- 报告第十一节的分工标为【待团队填写】，包括技术负责人姓名、非技术分工和孙卓的班级（GOV-03）。AI 不代填。
- 尚未经组员审阅和演练；讲演人和答题人未定。
- 11-30 前需实际提交并现场答辩。之后在 `midterm_manifest.json` 的 `submitted` / `defense` 字段和 `midterm_defense_prep.md` 第 4 节登记凭证，再补一份通过的证据，DOC-02 才能标 done。DOC-02 的依赖 DOC-01 仍缺回执。
- 生成工具（docx、pptxgenjs、matplotlib）装在会话临时目录，没有写进项目锁文件。重新生成需要另装：`npm i docx@9.15.4 pptxgenjs@3.12.0`，以及 `matplotlib==3.11.2`。

## 5. 下一步

1. 组员在 Word 中打开报告（目录提示更新域时选“是”），填写第十一节，再审阅全文和 PPT。
2. 按 `midterm_defense_prep.md` 演练一次，并记录在第 4 节。
3. 提交、答辩，保存凭证。
4. 技术侧可以并行推进的下一项是 DOC-03 正式报告。它依赖 DOC-02 done，可以先写草稿，等 DOC-02 done 后再验收。
