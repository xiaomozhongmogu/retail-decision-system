# 验收证据目录

按`evidence/<task_id>/<run>.json`登记真实证据，格式参见templates/EVIDENCE.json。
记录命令或人工/AI文件审阅、时间、环境、输入身份、输出/日志哈希、逐条验收结果与限制。截图和图表是佐证，不能取代重建命令、指标口径或实际评估结果。
不得复制模板后直接把not_run改成passed。只有真实执行或审阅才可以填写通过；不能运行的工作保留in_review并交给下一执行者。

从`python3 scripts/project.py show <task_id>`取得task_spec_sha256，绑定当前任务条件与关联要求。每个任务声明输出都需出现在artifacts并记录实际SHA256；输入也记录相关文件哈希。任务evidence数组只指向当前有效通过证据，历史失败/旧结果保留在目录及交接中。
