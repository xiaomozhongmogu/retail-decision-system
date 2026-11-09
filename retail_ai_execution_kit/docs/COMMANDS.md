# 命令登记表

## 已提供：治理检查（Python标准库）

在包的根目录执行，macOS可用`python3`：

```bash
python3 scripts/project.py validate
python3 scripts/project.py next
python3 scripts/project.py show DATA-02
python3 scripts/project.py render
python3 scripts/project.py gate proposal-ready
python3 scripts/project.py gate midterm-ready
python3 scripts/project.py gate final-ready
python3 scripts/project.py gate final-submitted
```

`validate`只验证台账结构、引用、依赖与声明完成项的证据。初始所有业务任务未验收，`gate`返回非0是预期阻断，不能修改脚本绕过。
`render`重建TASKS.md、REQUIREMENTS.md、STATUS.md；其他代理不要直接编辑这些视图。
`show <task_id>`输出该任务及相关要求，并给出验收证据所需的task_spec_sha256。规格或要求变化后旧哈希失效；重新核验后生成新的证据，不只替换哈希冒充重验。

## 计划中：业务命令

当前包不包含业务应用，以下入口需GOV-07及对应实现任务实际建立后才能登记为可用：

| 目的 | 拟定形式 | 当前状态 |
| --- | --- | --- |
| 数据探查/导入 | `python -m retail_bi.cli ingest --config ...` | 未实现 |
| 清洗和建仓 | `python -m retail_bi.cli build --config ...` | 未实现 |
| 构建样本/训练 | `python -m retail_bi.cli train --config ...` | 未实现 |
| 数据/模型/AI验证 | `python -m retail_bi.cli verify --suite ...` | 未实现 |
| Web | `streamlit run app.py` | 未实现 |

实现后填写精确命令、工作目录、输入配置、输出路径、成功条件、预期耗时和真实运行证据。不能因为本文列出命令就写“已运行”。
