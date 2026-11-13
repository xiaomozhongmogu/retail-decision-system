# 外部独立测试（2026-11-13 准备，尚未执行）

| 文件 | 测试者 | 方式 | 看得到什么 |
|---|---|---|---|
| `gemini_code_test_prompt.md` | Gemini | 在仓库里写自己的测试脚本，做对抗式代码测试 | 代码与文档（不改动任何已有文件） |
| `gpt_ui_test_prompt.md` | GPT（可选，需要能操作本机浏览器） | 扮演经理、分析师、答辩老师三个角色，像真人一样使用网页 | 只看网页（盲测） |

- 结果放置：Gemini 写入 `reports/external_test/gemini/`（`findings.jsonl` + `summary.md` + `tests/`）。GPT 的输出请原样保存为 `reports/external_test/gpt_ui/report.md`，或者直接贴回对话。
- 收到结果后，由开发方逐条复现。确认的问题进入修复，修复后重跑相关任务的检查。没能复现的问题如实标注，不删除。
- **这两项都是 AI 测试，不是人工测试**，不能代替 AI-10 的人工抽查（`eval/human_spot_check.md`）。在报告和答辩中分别写为“AI 独立代码测试”和“AI 模拟用户测试”。
- 两者的价值在于“独立”：测试者不是写代码的 AI，而且使用新的测例。不要把已有测例或答案（`eval/blind_key/` 等）交给 GPT。
