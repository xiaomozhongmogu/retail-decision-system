# 当前状态

> 自动生成；唯一动态任务台账是 project/tasks.json。

- 项目状态说明：DATA-01..12 done (2026-11-10): stage-1 synthetic data package released (reports/data/dataset_release.json, docs/data_readme.md), per D012 user authorization (no teacher confirmation). Next: DW-01 warehouse design, then DW-02..; EDA-01; UI-01; AI-01; DOC-04.
- 正式主数据：合成交易包 baseline_10000_seed42（SHA-256 d50ee64a…7a16），交易路线，经 DATA-05 engineering-import-v1 重建，截止 2026-11-08T00:00:00Z；依据 D012 用户授权的工作假设冻结（D013），非教师确认。
- 协调者：claude-opus-5-5（Claude Code 桌面端，对话“电商项目接力｜说继续即可”）；2026-11-10 14:30 起按用户“继续”接手，接手台账 fbff0147…。
- 已选 85 项；done 21 项；blocked 1 项；其他未验收 63 项。

## 可认领的下一步

- DW-04：实现DWS业务汇总
- DW-05：建立时点客户快照接口
- EDA-01：完成初步描述性统计
- ML-01：冻结预测目标与适用母体
- AI-01：实现LLM适配与配置边界
- UI-01：建立Streamlit多页骨架
- DOC-04：核验学术文献与综述引用

## 当前阻塞

- GOV-03：已从用户提供的选题报告登记 5 名成员姓名、学号与组长（ops/TEAM.md）；仍缺：各模块负责人与复核者、可投入时间、文档章节与演示分工，以及孙卓班级的确认，均需团队提供。恢复条件：用户提供分工表。

## 四个关卡

| 关卡 | 已验收/需验收任务 | 状态 |
| --- | --- | --- |
| proposal-ready | 18/23 | 未就绪 |
| midterm-ready | 21/56 | 未就绪 |
| final-ready | 21/84 | 未就绪 |
| final-submitted | 21/85 | 未就绪 |

状态勾选与结构校验不等于已满足教师要求。通过就绪关卡也不等于已提交或已答辩；最终以真实回执和实际结果记录。
