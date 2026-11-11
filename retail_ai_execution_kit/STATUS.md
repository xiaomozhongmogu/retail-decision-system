# 当前状态

> 自动生成；唯一动态任务台账是 project/tasks.json。

- 项目状态说明：Done through ML-06 (2026-11-10, claude-opus-5-5): data, warehouse release wh-db316daf8021, EDA-01, ML-01..04, ML-06 baselines (weak signal: logreg val ROC-AUC 0.556). Next: ML-07 LightGBM, ML-08, ML-09; EDA-05 then ML-05; UI-01; AI-01; DOC-04. Coordinator released at usage limit.
- 正式主数据：合成交易包 baseline_10000_seed42（SHA-256 d50ee64a…7a16），交易路线，经 DATA-05 engineering-import-v1 重建，截止 2026-11-08T00:00:00Z；依据 D012 用户授权的工作假设冻结（D013），非教师确认。
- 协调者：claude-opus-5-5（对话“电商项目接力｜说继续即可”）；2026-11-11 14:18 按用户再次继续，台账 4420cb35…。
- 已选 85 项；done 54 项；blocked 2 项；其他未验收 29 项。

## 可认领的下一步

- DOC-04：核验学术文献与综述引用

## 当前阻塞

- GOV-03：已从用户提供的选题报告登记 5 名成员姓名、学号与组长（ops/TEAM.md）；仍缺：各模块负责人与复核者、可投入时间、文档章节与演示分工，以及孙卓班级的确认，均需团队提供。恢复条件：用户提供分工表。
- AI-01：缺少 LLM 凭据：适配层与夹具检查已完成（13/13，见 evidence/AI-01/2026-11-11-client-fixture.json），但本机没有 LLM_API_KEY/LLM_BASE_URL/LLM_MODEL，真实小请求无法完成。已尝试：读取环境与 .env，真实调用返回 llm_unavailable。恢复条件：用户自行在执行根目录 .env 填写 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL、LLM_PRICE_IN_PER_1K、LLM_PRICE_OUT_PER_1K，并设 LLM_ALLOW_PAID=1（预算默认 50 次 / 0.5 USD）。下一步：重跑 evidence/AI-01/client_smoke.py，确认真实请求成功后补证据并验收。只阻塞依赖 AI-01 的 AI 任务。

## 四个关卡

| 关卡 | 已验收/需验收任务 | 状态 |
| --- | --- | --- |
| proposal-ready | 19/23 | 未就绪 |
| midterm-ready | 51/56 | 未就绪 |
| final-ready | 54/84 | 未就绪 |
| final-submitted | 54/85 | 未就绪 |

状态勾选与结构校验不等于已满足教师要求。通过就绪关卡也不等于已提交或已答辩；最终以真实回执和实际结果记录。
