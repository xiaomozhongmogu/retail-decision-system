# 项目任务清单与逐项验收

> 生成文件：只修改 project/tasks.json，再运行 python3 scripts/project.py render。
> 文件内的日期是计划截止，勾选只表示任务经证据验收；不代表已经提交或教师评分。

共 92 项：已选核心 85 项；未启用扩展 7 项。

## 使用方法

按依赖认领最小可执行任务；每次一个实施者负责指定范围。验收结果写 evidence/<task_id>/，真实状态由协调者写入台账。需要执行的任务不能凭静态检查标done。

阶段：proposal=11月9日；midterm=11月30日；final=12月22日前材料就绪；submitted=实际提交及答辩记录。

## 总览

| ID | 任务 | 阶段 | 状态 | 依赖 |
| --- | --- | --- | --- | --- |
| GOV-01 | 核对课程原文并建立需求映射 | proposal | done | 无 |
| GOV-02 | 盘点现有仓库和AI运行能力 | proposal | done | GOV-01 |
| GOV-03 | 填写真实团队与责任矩阵 | proposal | blocked | GOV-01 |
| GOV-04 | 解决数据时效及课程口径歧义 | proposal | in_review | GOV-01 |
| GOV-05 | 冻结业务范围和可观测生命周期 | proposal | done | GOV-01 |
| GOV-06 | 冻结轻量架构和公共接口草案 | proposal | done | GOV-05, GOV-02 |
| GOV-07 | 建立环境、目录和命令入口 | proposal | done | GOV-02, GOV-06 |
| GOV-08 | 建立认领、证据和交接流程 | proposal | done | GOV-01, GOV-02 |
| DATA-01 | 核验候选数据来源与许可 | proposal | done | GOV-05 |
| DATA-02 | 实读候选文件并探查字段 | proposal | done | DATA-01, GOV-07 |
| DATA-03 | 确认唯一主数据路线 | proposal | done | DATA-02 |
| DATA-04 | 完成正式数据契约和字典 | proposal | done | DATA-03 |
| DATA-05 | 实现完整导入和原始数据登记 | proposal | done | DATA-04 |
| DATA-06 | 全量质量剖析与问题基线 | proposal | done | DATA-05 |
| DATA-07 | 处理缺失、类型与重复导入 | proposal | done | DATA-06 |
| DATA-08 | 统一购买、取消、退款与金额规则 | proposal | done | DATA-06 |
| DATA-09 | 完成集成与冲突处理 | proposal | done | DATA-07, DATA-08 |
| DATA-10 | 设计归约、转换与时间特征 | proposal | done | DATA-09 |
| DATA-11 | 执行清洗后质量门槛 | proposal | done | DATA-10 |
| DATA-12 | 发布阶段一数据包 | proposal | done | DATA-11 |
| DW-01 | 完成概念、逻辑和物理数仓设计 | midterm | done | DATA-04, GOV-06 |
| DW-02 | 实现ODS与加载审计 | midterm | done | DW-01, DATA-12 |
| DW-03 | 实现DWD事实及维表 | midterm | done | DW-02 |
| DW-04 | 实现DWS业务汇总 | midterm | done | DW-03 |
| DW-05 | 建立时点客户快照接口 | midterm | done | DW-03 |
| DW-06 | 实现ADS与指标语义 | midterm | done | DW-04, DW-05 |
| DW-07 | 实现可重跑ETL编排 | midterm | done | DW-06, GOV-07 |
| DW-08 | 完成OLAP标准查询集 | midterm | done | DW-06 |
| DW-09 | 校验数仓约束和对账 | midterm | done | DW-07, DW-08 |
| DW-10 | 发布只读查询快照 | midterm | done | DW-09 |
| EDA-01 | 完成初步描述性统计 | proposal | done | DATA-12 |
| EDA-02 | 分析经营趋势和结构 | midterm | todo | DW-08, EDA-01 |
| EDA-03 | 构建首观测购买cohort与留存 | midterm | todo | DW-06 |
| EDA-04 | 完成经营诊断与证据分解 | midterm | todo | EDA-02 |
| EDA-05 | 实现互斥生命周期规则 | midterm | todo | DW-05, GOV-05 |
| EDA-06 | 形成面向决策的分析结论 | midterm | todo | EDA-03, EDA-04, EDA-05 |
| ML-01 | 冻结预测目标与适用母体 | midterm | done | DATA-12, GOV-05 |
| ML-02 | 实现按时点构建监督样本 | midterm | done | ML-01, DW-05 |
| ML-03 | 实现历史特征与缺失策略 | midterm | done | ML-02 |
| ML-04 | 固定时间切分并审计泄漏 | midterm | done | ML-03 |
| ML-05 | 完成RFM规则与K-Means分群 | midterm | todo | EDA-05, ML-04 |
| ML-06 | 训练规则与逻辑回归基线 | midterm | done | ML-04 |
| ML-07 | 训练并有限调优LightGBM | midterm | done | ML-06 |
| ML-08 | 冻结模型、校准与阈值 | midterm | done | ML-07 |
| ML-09 | 完成最终时间外评估 | midterm | done | ML-08 |
| ML-10 | 解释误差与适用限制 | midterm | todo | ML-09, ML-05 |
| ML-11 | 实现评分服务与适用性输出 | midterm | todo | ML-10, DW-10 |
| ML-12 | 发布模型文件与模型卡 | midterm | todo | ML-11 |
| AI-01 | 实现LLM适配与配置边界 | final | todo | GOV-07, GOV-06 |
| AI-02 | 建立业务知识库与检索 | final | todo | DW-06, ML-12 |
| AI-03 | 评测知识检索和依据引用 | final | todo | AI-02, AI-01 |
| AI-04 | 实现查询意图与Schema约束 | final | todo | AI-01, DW-06 |
| AI-05 | 实现受限SQL执行器 | final | todo | AI-04, DW-10 |
| AI-06 | 实现查询回答与结果证据 | final | todo | AI-05 |
| AI-07 | 完成NL2SQL标准集验收 | final | todo | AI-06 |
| AI-08 | 实现周报事实计算 | final | todo | EDA-04, DW-06 |
| AI-09 | 实现周报生成与数值校验 | final | todo | AI-08, AI-01, AI-02 |
| AI-10 | 完成周报场景验收 | final | todo | AI-09 |
| AI-11 | 建立运营政策与预算规则 | final | todo | ML-11, GOV-05 |
| AI-12 | 实现有限步骤运营Agent | final | todo | AI-11, AI-01, AI-02 |
| AI-13 | 实现草稿存储和审阅状态 | final | todo | AI-12 |
| AI-14 | 完成Agent边界场景验收 | final | todo | AI-13 |
| AI-15 | 完成三模块联调与可观测性 | final | todo | AI-03, AI-07, AI-10, AI-14 |
| UI-01 | 建立Streamlit多页骨架 | midterm | todo | GOV-07, GOV-06 |
| UI-02 | 接入数据质量与口径页面 | midterm | todo | UI-01, DATA-12 |
| UI-03 | 接入经营指标与OLAP交互 | midterm | todo | UI-01, DW-10, EDA-02 |
| UI-04 | 接入客户生命周期与分群 | midterm | todo | UI-01, EDA-03, EDA-05, ML-05 |
| UI-05 | 接入预测评估与名单试算 | midterm | todo | UI-01, ML-12 |
| UI-06 | 接入AI工作台 | final | todo | UI-01, AI-15 |
| UI-07 | 完成可读性、缓存与异常交互验收 | final | todo | UI-02, UI-03, UI-04, UI-05, UI-06 |
| DOC-01 | 完成选题报告并形成阶段一材料 | proposal | in_review | GOV-03, GOV-06, DATA-12, EDA-01, DOC-04 |
| DOC-02 | 完成中期检查报告与答辩材料 | midterm | todo | DOC-01, DW-10, EDA-06, ML-12, UI-05 |
| DOC-03 | 完成正式报告六章及设计方案覆盖 | final | todo | DOC-02, AI-15, UI-07, DOC-05, DOC-08 |
| DOC-04 | 核验学术文献与综述引用 | proposal | todo | GOV-05 |
| DOC-05 | 整理实现证据、图表和复现说明 | final | todo | DW-10, ML-12, AI-15, UI-07 |
| DOC-06 | 整理个人贡献与答辩知识清单 | final | todo | GOV-03, DOC-05 |
| DOC-07 | 完成终期PPT与10分钟脚本 | final | todo | DOC-03, DOC-06 |
| DOC-08 | 完成问题分析、反思与应用前景 | final | todo | EDA-06, ML-10, AI-15 |
| REL-01 | 执行有针对性的集成与回归验证 | final | todo | UI-07, AI-15, ML-12, DW-10 |
| REL-02 | 完成干净环境或第二机器复现 | final | todo | REL-01, GOV-07, DOC-05 |
| REL-03 | 打包代码、数据、模型和配置 | final | todo | REL-02, DOC-03, DOC-07 |
| REL-04 | 核验运行资源与服务降级 | final | todo | REL-01 |
| REL-05 | 完成现场演练和个人问答 | final | todo | REL-03, REL-04, DOC-06, DOC-07 |
| REL-06 | 最终逐项核对课程与项目承诺 | final | todo | REL-05 |
| REL-07 | 记录真实提交和答辩结果 | submitted | todo | REL-06 |
| BON-01 | 可选：销量预测 | final | skipped | ML-12 |
| BON-02 | 可选：购物篮关联规则 | final | skipped | DW-10 |
| BON-03 | 可选：生产可用AI能力强化 | final | skipped | AI-15, REL-01 |
| BON-04 | 可选：LLM训练或微调 | final | skipped | AI-15, REL-01 |
| BON-05 | 可选：产品级Demo强化 | final | skipped | REL-05 |
| BON-06 | 可选：开源、发表或竞赛 | final | skipped | REL-06 |
| BON-07 | 可选：技术博客或教学视频 | final | skipped | DOC-08, REL-05 |

## GOV — 治理与需求

### GOV-01 核对课程原文并建立需求映射

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：C01, C06, C16, C18, C19, C24, C25, C26, C30, Q07。
- 前置：无。
- 允许修改：`project`, `docs`, `ops`, `reports/governance`；另可写本任务证据/交接。
- 输出：`reports/governance/requirements_review.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 核验sources/manifest.json中三份原件及哈希，区分原件、提取文本、既有规划。
2. 检查正文评分表、附录评分表、九类设计内容、六章报告和三阶段日期均有映射。
3. 歧义在ops/DECISIONS.md登记；不把算法示例或技术菜单全升级为必做。

证据：evidence/GOV-01/2026-11-09-review.json

### GOV-02 盘点现有仓库和AI运行能力

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：Q02, Q07。
- 前置：GOV-01。
- 允许修改：`reports/governance`；另可写本任务证据/交接。
- 输出：`reports/governance/workspace_inventory.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 记录仓库/文件、当前提交或文件快照、未提交修改、已有成果，优先复用。
2. 记录OS、CPU架构、Python、联网、文件读写和执行能力，不能声称已验证用户M1机器。
3. 说明可实际执行与只能提供待执行补丁的范围；不覆盖未知用户文件。

证据：evidence/GOV-02/2026-11-09-codex-recheck.json

### GOV-03 填写真实团队与责任矩阵

- [ ] 状态：`blocked`；阶段：`proposal`；范围：已选核心。
- 依据：C02, C22, C23。
- 前置：GOV-01。
- 允许修改：`ops`, `reports/governance`；另可写本任务证据/交接。
- 输出：`ops/TEAM.md`, `reports/governance/team_review.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 真实成员4至6名，姓名学号班级由用户提供，样例表信息不推断。
2. 每个模块有负责人及复核者，记录可投入时间与三个截止日期。
3. 分配文档章节、演示职责和个人贡献记录方式。

**当前阻塞：** 已从用户提供的选题报告登记 5 名成员姓名、学号与组长（ops/TEAM.md）；仍缺：各模块负责人与复核者、可投入时间、文档章节与演示分工，以及孙卓班级的确认，均需团队提供。恢复条件：用户提供分工表。

证据：尚无已登记验收证据。

### GOV-04 解决数据时效及课程口径歧义

- [ ] 状态：`in_review`；阶段：`proposal`；范围：已选核心。
- 依据：C06, C16, C30, B01, B05。
- 前置：GOV-01。
- 允许修改：`ops`, `reports/governance`；另可写本任务证据/交接。
- 输出：`reports/governance/course_clarifications.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 可用真实来源证据证明满足较严格数据时间条款，或保存教师对时间定义/历史数据例外的明确答复；两者均无则维持未解决。
2. AI数量按评分表至少2、本项目3执行；不以标题选做擅自删掉承诺模块。
3. 列出未答复的加分计算与生产可用口径；加分歧义可保留但不能据此保证分数。

证据：尚无已登记验收证据。

### GOV-05 冻结业务范围和可观测生命周期

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：C01, C12, C27, U01, Q01。
- 前置：GOV-01。
- 允许修改：`docs`；另可写本任务证据/交接。
- 输出：`docs/business_scope.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 为获客/首购、留存、价值维系、沉睡召回列出用户、问题、决策、所需数据和可支持边界。
2. 主路线若只有交易数据，明确从首次可观测购买开始，不编造浏览漏斗、真实首购或渠道归因。
3. 生命周期规则、价值聚类、未来未复购风险和营销增量效果分开定义。

证据：evidence/GOV-05/2026-11-10-dw06-recheck.json

### GOV-06 冻结轻量架构和公共接口草案

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：C09, C28, U02, U05, Q01。
- 前置：GOV-05, GOV-02。
- 允许修改：`docs`, `contracts`；另可写本任务证据/交接。
- 输出：`docs/architecture.md`, `contracts/interfaces.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 画出离线ETL/训练、只读查询、AI工具和Streamlit的数据流；明确每表/接口粒度。
2. 选择可运行的轻量技术栈，版本在安装验证后锁定；不为了工具数量增加集群。
3. 接口包含as_of、版本、单位、空结果与错误结构；此时允许契约草案，不能假称业务实现。

证据：evidence/GOV-06/2026-11-10-dw06-recheck.json

### GOV-07 建立环境、目录和命令入口

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：C20, Q02, Q07。
- 前置：GOV-02, GOV-06。
- 允许修改：`docs`, `scripts`, `pyproject.toml`, `requirements.lock`, `.gitignore`, `.env.example`；另可写本任务证据/交接。
- 输出：`docs/COMMANDS.md`, `pyproject.toml`, `requirements.lock`, `reports/governance/environment_smoke.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 选择并验证Python环境、依赖和启动方法，记录CPU与系统；锁文件来源可追溯。
2. Git忽略密钥和大数据，配置样例无真实秘钥；保留课程私有数据边界。
3. 区分当前已实现命令与计划命令；干净环境最小导入或帮助命令实际成功。

证据：evidence/GOV-07/2026-11-10-dw07-recheck.json

### GOV-08 建立认领、证据和交接流程

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：C23, Q02, Q07。
- 前置：GOV-01, GOV-02。
- 允许修改：`project`, `ops`, `worklogs`, `reports/governance`；另可写本任务证据/交接。
- 输出：`reports/governance/collaboration_smoke.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 运行治理脚本validate，查看next与阶段门槛；初始未完成不视为失败待修。
2. 任务台账单写者明确，完成一次任务认领和交接示例；并行代理目录互斥。
3. 检查done必须有真实证据，不能把生成文件或脚本退出0直接视为全部业务正确。

证据：evidence/GOV-08/2026-11-09-codex-recheck.json


## DATA — 数据准备

### DATA-01 核验候选数据来源与许可

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：C03, C04, C05, C06, C07。
- 前置：GOV-05。
- 允许修改：`docs`；另可写本任务证据/交接。
- 输出：`docs/data_candidates.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 列真实下载入口、发布者、许可、事件时间、首次发布/更新时间，并区分网页元数据与实读结果。
2. 至少核验主候选和备选的可下载性；账号或权限需求明确记录，不绕过访问控制。
3. UCI/Cosmetics只能在历史数据口径获准后正式采用；T-ECD不得凭2026更新直接认定合规。

证据：evidence/DATA-01/2026-11-10-data04-recheck.json

### DATA-02 实读候选文件并探查字段

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：C03, C04, C05, Q02。
- 前置：DATA-01, GOV-07。
- 允许修改：`src/retail_bi/data`, `reports/data`；另可写本任务证据/交接。
- 输出：`reports/data/candidate_probe.json`, `reports/data/candidate_probe.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 对真实文件记录行数、列名、类型、时间样本、文件字节数和哈希。
2. 明确读取的是单分片、样本还是全量，不能由单分片推断全期质量。
3. 核验客户、商品、交易或事件标识，金额与数量是否真实存在；不凑字段。

证据：evidence/DATA-02/2026-11-09-probe.json

### DATA-03 确认唯一主数据路线

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：C06, C07, U01, Q01。
- 前置：DATA-02。
- 允许修改：`reports/data`, `ops`, `contracts`；另可写本任务证据/交接。
- 输出：`reports/data/dataset_selection.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 依据D012用户明确授权，按合成数据与时间口径已确认的工作假设冻结工程主数据；注明授权来源，不伪称收到教师真实答复。
2. 确认采用交易路线还是行为路线，并列出被删除或调整的指标/模型/页面。
3. 不得拼接无关来源用户ID；核验至少8个有意义的源业务字段，不以拆日期或模拟补列凑数；D012工作假设允许工程验收，不冒称教师实际确认。

证据：evidence/DATA-03/2026-11-10-dw06-recheck.json

### DATA-04 完成正式数据契约和字典

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：C04, C05, C08, Q01。
- 前置：DATA-03。
- 允许修改：`contracts`, `docs`；另可写本任务证据/交接。
- 输出：`contracts/data_contract.json`, `docs/data_dictionary.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 逐列记录原始名、标准名、类型、含义、可空、单位、真实来源、主外键假设和时间语义。
2. 合同状态由candidate改为approved需要DATA-03证据；核验的有效业务字段至少8，并区分源字段与可验证的真实关联字段。
3. 交易数据不能虚构渠道/毛利；行为数据缺订单/金额时使用明确代理指标并同步规格。

证据：evidence/DATA-04/2026-11-10-contract.json

### DATA-05 实现完整导入和原始数据登记

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：C03, C07, C08, C20。
- 前置：DATA-04。
- 允许修改：`src/retail_bi/data`, `reports/data`, `data/raw`；另可写本任务证据/交接。
- 输出：`src/retail_bi/data/ingest.py`, `reports/data/source_manifest.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 已冻结正式研究范围内的数据完整获取并校验大小/哈希，保留来源版本与日期；不必下载发布者所有无关域或文件，不能声称审计过未读取部分。
2. 原始层只读保留，导入可重复执行；凭据不进入日志或仓库。
3. 采集受限时如实记录，不能用生成数据替代正式数据规模。

证据：evidence/DATA-05/2026-11-10-acceptance-review.json

### DATA-06 全量质量剖析与问题基线

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：C03, C04, C05, C08。
- 前置：DATA-05。
- 允许修改：`src/retail_bi/data`, `reports/data`；另可写本任务证据/交接。
- 输出：`reports/data/profile_before.json`, `reports/data/profile_before.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 对已冻结的正式研究范围完整统计行数、客户/商品数、缺失、重复候选、时间、取消负值和极端交易；抽样范围及完整历史保留规则写清。
2. 报告实际客户覆盖、时间覆盖与正类潜力；若跨度不足预测，回到选型处理。
3. 字段有效性和质量问题有样本证据，但不泄露不必要的个人信息。

证据：evidence/DATA-06/2026-11-10-profile.json

### DATA-07 处理缺失、类型与重复导入

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：C08, Q01。
- 前置：DATA-06。
- 允许修改：`src/retail_bi/data`, `reports/data`, `data/quarantine`；另可写本任务证据/交接。
- 输出：`src/retail_bi/data/clean.py`, `reports/data/cleaning_missing_duplicates.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. ID不均值插补；未知客户可保留汇总并排除客户建模，两种覆盖分开。
2. 解析失败进入隔离数据，保留来源行与原因，不能静默消失。
3. 文件哈希防重复导入；原始重复行是否删除有业务理由，不假定发票加商品唯一。

证据：evidence/DATA-07/2026-11-10-clean-v2.json

### DATA-08 统一购买、取消、退款与金额规则

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：C08, Q01。
- 前置：DATA-06。
- 允许修改：`docs`, `src/retail_bi/data`, `contracts`, `reports/data`；另可写本任务证据/交接。
- 输出：`docs/transaction_rules.md`, `reports/data/transaction_reconciliation.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 明确正向购买、冲销/退款、非商品收费与隔离规则，已知客户条件只作用于需要身份的指标。
2. 订单数使用有效交易标识去重，金额由精确数值计算；缺支付状态时不用支付成功GMV名称。
3. 原始与清洗净额差异逐项解释；无法关联退款原单时按实际发生时间统计。

证据：evidence/DATA-08/2026-11-10-dw06-recheck.json

### DATA-09 完成集成与冲突处理

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：C08, Q01。
- 前置：DATA-07, DATA-08。
- 允许修改：`src/retail_bi/data`, `reports/data`；另可写本任务证据/交接。
- 输出：`reports/data/integration_audit.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 同一来源多文件/工作表统一列名和类型，校验时间重叠与重复。
2. 商品属性等关联须验证主键、覆盖率和连接前后行数金额，不产生事实放大。
3. 不需要跨来源集成时说明来源内整合方式与适用性，不人工拼接无关用户。

证据：evidence/DATA-09/2026-11-10-integration-v2.json

### DATA-10 设计归约、转换与时间特征

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：C08, Q03。
- 前置：DATA-09。
- 允许修改：`docs`, `src/retail_bi/data`, `reports/data`；另可写本任务证据/交接。
- 输出：`docs/preprocessing_methods.md`, `reports/data/transform_audit.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 清理/集成/归约/转换四类逐一给处理或合理不适用说明，不能仅列算法名。
2. 数值变换、编码、时间派生可复现；模型相关拟合参数只从训练部分获得。
3. 大数据抽样按用户保留完整历史，开发小样本明确标记；不以取文件前N行代替最终建模样本。

证据：evidence/DATA-10/2026-11-10-transform-v2.json

### DATA-11 执行清洗后质量门槛

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：C03, C04, C05, C08, Q02。
- 前置：DATA-10。
- 允许修改：`reports/data`, `tests/data`；另可写本任务证据/交接。
- 输出：`reports/data/profile_after.json`, `reports/data/quality_checks.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 清洗后数据规模、字段、时间和模型可用客户覆盖实际测量；正负类不足不能继续宣称分类有效。
2. 测试异常行隔离、重复导入、退款分类、金额差异和时间解析，给明确通过/失败结果。
3. 每条关键规则有输入例和期望输出，测试夹具与正式数据物理分开。

证据：evidence/DATA-11/2026-11-10-dw06-recheck.json

### DATA-12 发布阶段一数据包

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：C03, C04, C05, C07, C20, C24。
- 前置：DATA-11。
- 允许修改：`reports/data`, `docs`；另可写本任务证据/交接。
- 输出：`reports/data/dataset_release.json`, `docs/data_readme.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 登记正式数据路径/私有存放方式、版本、哈希、字典、质量报告和一键导入步骤。
2. 至少10000条或10MB、至少8字段、明确时间及已确认的时效口径全部有证据。
3. 提供课程允许的数据交付方式；样本不能冒充全量，未知事项明确列出。

证据：evidence/DATA-12/2026-11-10-dw06-recheck.json


## DW — 数仓与OLAP

### DW-01 完成概念、逻辑和物理数仓设计

- [x] 状态：`done`；阶段：`midterm`；范围：已选核心。
- 依据：C09, C28, U02, Q01。
- 前置：DATA-04, GOV-06。
- 允许修改：`docs`, `sql`；另可写本任务证据/交接。
- 输出：`docs/warehouse_design.md`, `sql/ddl.sql`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 解释ODS/DWD/DWS/ADS责任、事实粒度、维度键和星型关系。
2. 源缺品类/城市时不画未经来源支持的层级，动态分群不永久覆盖客户静态属性。
3. 图、DDL、契约字段一致，设计含血缘和刷新顺序。

证据：evidence/DW-01/2026-11-10-dw06-recheck.json

### DW-02 实现ODS与加载审计

- [x] 状态：`done`；阶段：`midterm`；范围：已选核心。
- 依据：C09, U02, Q02。
- 前置：DW-01, DATA-12。
- 允许修改：`sql`, `src/retail_bi/warehouse`, `reports/warehouse`；另可写本任务证据/交接。
- 输出：`sql/ods.sql`, `reports/warehouse/ods_audit.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 保留原始值、文件哈希、行号、批次与导入时间，原始行可定位。
2. 重跑不重复加载同一批次，失败不留下假成功状态。
3. ODS行数与来源清单一致，缺失文件有清晰错误。

证据：evidence/DW-02/2026-11-10-ods-v2.json

### DW-03 实现DWD事实及维表

- [x] 状态：`done`；阶段：`midterm`；范围：已选核心。
- 依据：C09, U02, Q01。
- 前置：DW-02。
- 允许修改：`sql`, `src/retail_bi/warehouse`, `reports/warehouse`；另可写本任务证据/交接。
- 输出：`sql/dwd.sql`, `reports/warehouse/dwd_audit.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 按照清洗规则创建事实表与日期/客户/商品/国家维表，类型与单位正确。
2. 维度键唯一或版本规则明确，事实关联保持原有粒度。
3. 取消/退款、匿名客户和隔离记录的处理与数据报告一致。

证据：evidence/DW-03/2026-11-10-dwd-v2.json

### DW-04 实现DWS业务汇总

- [x] 状态：`done`；阶段：`midterm`；范围：已选核心。
- 依据：C09, C10, U02。
- 前置：DW-03。
- 允许修改：`sql`, `reports/warehouse`；另可写本任务证据/交接。
- 输出：`sql/dws.sql`, `reports/warehouse/dws_audit.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 构建客户日、商品日、国家日等合适汇总表并说明粒度。
2. 可加与不可加指标分开，月独立客户不由日独立客户相加。
3. 抽取多个时间和维度切片与DWD明细独立重算一致。

证据：evidence/DW-04/2026-11-10-dw06-recheck.json

### DW-05 建立时点客户快照接口

- [x] 状态：`done`；阶段：`midterm`；范围：已选核心。
- 依据：U02, U03, Q03。
- 前置：DW-03。
- 允许修改：`sql`, `src/retail_bi/features`, `reports/warehouse`；另可写本任务证据/交接。
- 输出：`sql/customer_snapshot.sql`, `reports/warehouse/snapshot_contract.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 一行是客户与as_of；特征截止、观察窗和数据覆盖可查询。
2. 快照只使用当时可得的交易/退货/属性，不混入未来标签。
3. 标签数据单独管理，接入建模层时有明确主键与版本。

证据：evidence/DW-05/2026-11-10-snapshot.json

### DW-06 实现ADS与指标语义

- [x] 状态：`done`；阶段：`midterm`；范围：已选核心。
- 依据：C10, U02, Q01。
- 前置：DW-04, DW-05。
- 允许修改：`sql`, `contracts`, `reports/warehouse`；另可写本任务证据/交接。
- 输出：`sql/ads.sql`, `contracts/metrics.json`, `reports/warehouse/metric_checks.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 指标词典含单位、分子分母、窗口、纳入/排除、空值、粒度和SQL映射。
2. 经营总览、cohort、分群与风险的ADS视图职责明确，AI仅查询允许视图。
3. 订单、客单价、净额和复购指标的样例与手算/独立SQL一致。

证据：evidence/DW-06/2026-11-10-ads.json

### DW-07 实现可重跑ETL编排

- [x] 状态：`done`；阶段：`midterm`；范围：已选核心。
- 依据：C09, C20, U02, Q02。
- 前置：DW-06, GOV-07。
- 允许修改：`src/retail_bi`, `reports/warehouse`, `docs/COMMANDS.md`；另可写本任务证据/交接。
- 输出：`src/retail_bi/pipeline.py`, `reports/warehouse/etl_run.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 一个明确命令可从原始数据重建到ADS，阶段失败可定位。
2. 重跑幂等，临时产物完成后原子发布；应用不读取半成品。
3. 记录每层行数、金额、耗时、输入输出版本和异常。

证据：evidence/DW-07/2026-11-10-pipeline.json

### DW-08 完成OLAP标准查询集

- [x] 状态：`done`；阶段：`midterm`；范围：已选核心。
- 依据：C10, C28, U02。
- 前置：DW-06。
- 允许修改：`sql`, `reports/warehouse`；另可写本任务证据/交接。
- 输出：`sql/olap_examples.sql`, `reports/warehouse/olap_checks.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 至少6个项目示例覆盖切片、切块、上下钻、旋转，问题和结果对应。
2. 月到日到发票/明细下钻可回溯总量，维度组合不产生重复计算。
3. 无订单号的行为路线使用事件层下钻并明确单位，不能伪造订单。

证据：evidence/DW-08/2026-11-10-olap.json

### DW-09 校验数仓约束和对账

- [x] 状态：`done`；阶段：`midterm`；范围：已选核心。
- 依据：C09, U02, Q02。
- 前置：DW-07, DW-08。
- 允许修改：`tests/warehouse`, `reports/warehouse`；另可写本任务证据/交接。
- 输出：`tests/warehouse/test_reconciliation.py`, `reports/warehouse/reconciliation.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 核验维度键唯一、事实孤儿键策略、连接前后行数与金额不意外膨胀。
2. 原始→隔离/排除/纳入→事实→聚合差异可解释。
3. 故意注入重复维键、空日期和错误粒度夹具应使检查失败。

证据：evidence/DW-09/2026-11-10-reconciliation.json

### DW-10 发布只读查询快照

- [x] 状态：`done`；阶段：`midterm`；范围：已选核心。
- 依据：C20, U02, Q06。
- 前置：DW-09。
- 允许修改：`reports/warehouse`, `docs`, `src/retail_bi/warehouse`；另可写本任务证据/交接。
- 输出：`reports/warehouse/published_snapshot.json`, `docs/query_runtime.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 离线进程单写，应用读取版本化只读快照；ETL与UI生命周期分离。
2. 只读访问、允许视图和缓存失效机制实际验证。
3. 记录数据库文件身份和恢复方法，发布中断不破坏上一可用版本。

证据：evidence/DW-10/2026-11-10-release.json


## EDA — 业务分析

### EDA-01 完成初步描述性统计

- [x] 状态：`done`；阶段：`proposal`；范围：已选核心。
- 依据：C11, C24。
- 前置：DATA-12。
- 允许修改：`reports/analysis`, `src/retail_bi/analysis`；另可写本任务证据/交接。
- 输出：`reports/analysis/eda_initial.md`, `reports/analysis/eda_initial.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 统计数量、金额、客户和时间分布，标清样本范围、单位和未知覆盖。
2. 至少展示有业务意义的分布/趋势/异常，不能只有describe截图。
3. 报告数字由可重跑程序产生，不把历史数据写成2026实时经营。

证据：evidence/EDA-01/2026-11-10-eda.json

### EDA-02 分析经营趋势和结构

- [ ] 状态：`todo`；阶段：`midterm`；范围：已选核心。
- 依据：C11, C14, U01。
- 前置：DW-08, EDA-01。
- 允许修改：`reports/analysis`, `src/retail_bi/analysis`；另可写本任务证据/交接。
- 输出：`reports/analysis/business_trends.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 分析完整可比周期的趋势、商品和国家贡献，注明退款和非商品项规则。
2. 分母为0、不完整月或小样本给明确状态，不生成无意义百分比。
3. 至少3个实际发现可追溯到查询与结果文件，不预设发现方向。

证据：尚无已登记验收证据。

### EDA-03 构建首观测购买cohort与留存

- [ ] 状态：`todo`；阶段：`midterm`；范围：已选核心。
- 依据：C11, U01, Q03。
- 前置：DW-06。
- 允许修改：`reports/analysis`, `sql`；另可写本任务证据/交接。
- 输出：`reports/analysis/cohort.md`, `reports/analysis/cohort_checks.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. cohort按首次可观测有效购买定义，解释左截断，不冒称终身首次购买。
2. 年龄、留存分子分母和购买口径明确，只比较成熟窗口。
3. 尚未观察到的未来格子显示缺失状态，不填0。

证据：尚无已登记验收证据。

### EDA-04 完成经营诊断与证据分解

- [ ] 状态：`todo`；阶段：`midterm`；范围：已选核心。
- 依据：C12, C27。
- 前置：EDA-02。
- 允许修改：`reports/analysis`；另可写本任务证据/交接。
- 输出：`reports/analysis/diagnosis.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 用国家/商品/客户结构或量价等实际可支持因素分解指标变化。
2. 相关性和贡献分解不写成因果；缺渠道、成本或竞争信息的解释标待验证。
3. 每条运营建议注明触发条件、负责人或执行步骤、评价方式和数据限制。

证据：尚无已登记验收证据。

### EDA-05 实现互斥生命周期规则

- [ ] 状态：`todo`；阶段：`midterm`；范围：已选核心。
- 依据：U01, U03, Q01。
- 前置：DW-05, GOV-05。
- 允许修改：`docs`, `src/retail_bi/analysis`, `reports/analysis`；另可写本任务证据/交接。
- 输出：`docs/lifecycle_rules.md`, `reports/analysis/lifecycle_checks.json`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 明确新客、活跃、预警、沉睡和未知状态的优先级及时间边界。
2. 最近购买间隔阈值由分布和业务假设说明，规则独立于K-Means编号。
3. 测试边界时刻、匿名客户、首次观测不足和长期无购买用户；规则不重叠且覆盖母体。

证据：尚无已登记验收证据。

### EDA-06 形成面向决策的分析结论

- [ ] 状态：`todo`；阶段：`midterm`；范围：已选核心。
- 依据：C01, C12, C27, C30。
- 前置：EDA-03, EDA-04, EDA-05。
- 允许修改：`reports/analysis`；另可写本任务证据/交接。
- 输出：`reports/analysis/decision_brief.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 把问题→指标→证据→结论→行动→验证方式串起来，包含不能回答的问题。
2. 至少覆盖价值维系、留存预警、沉睡召回；获客只能在真实数据范围内讨论。
3. 业务价值先评价效率/名单质量/报告一致性，收入增长只作明确假设或未来实验。

证据：尚无已登记验收证据。


## ML — 分群与预测

### ML-01 冻结预测目标与适用母体

- [x] 状态：`done`；阶段：`midterm`；范围：已选核心。
- 依据：C13, U03, Q03。
- 前置：DATA-12, GOV-05。
- 允许修改：`docs`, `contracts`；另可写本任务证据/交接。
- 输出：`docs/model_target.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 交易主路线：过去90天至少一次有效购买的已知客户；未来[t,t+30天)有购买为1。
2. 未复购风险=1-复购概率，不能当作第二套独立标签或永久流失事实。
3. 更久沉睡用户规则处理；数据改为行为路线时重新定义事件/购买日、窗口与标题。

证据：evidence/ML-01/2026-11-10-target.json

### ML-02 实现按时点构建监督样本

- [x] 状态：`done`；阶段：`midterm`；范围：已选核心。
- 依据：U03, Q03。
- 前置：ML-01, DW-05。
- 允许修改：`src/retail_bi/features`, `reports/model`, `tests/model`；另可写本任务证据/交接。
- 输出：`src/retail_bi/features/build_samples.py`, `reports/model/sample_audit.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 样本主键客户+as_of唯一，特征与标签使用明确左闭右开窗口。
2. 标签窗口完整成熟，右截断样本排除；记录母体筛选、快照数和独立客户数。
3. 用边界时间夹具验证刚好落在起止时刻的事件归属。

证据：evidence/ML-02/2026-11-10-samples.json

### ML-03 实现历史特征与缺失策略

- [x] 状态：`done`；阶段：`midterm`；范围：已选核心。
- 依据：C08, C13, U03, Q03。
- 前置：ML-02。
- 允许修改：`src/retail_bi/features`, `docs`, `tests/model`；另可写本任务证据/交接。
- 输出：`src/retail_bi/features/customer_features.py`, `docs/feature_dictionary.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 实现过去7/30/90天RFM、购买间隔、活跃日、商品多样性、已发生退货等可用特征。
2. 禁止客户ID、未来总额/退款/聚类及后验状态；商品属性也要检查时点可得性。
3. 每个特征有公式、窗口、空值和数据来源，单次购买无法计算的间隔明确处理。

证据：evidence/ML-03/2026-11-10-features.json

### ML-04 固定时间切分并审计泄漏

- [x] 状态：`done`；阶段：`midterm`；范围：已选核心。
- 依据：C13, Q03, Q04。
- 前置：ML-03。
- 允许修改：`reports/model`, `src/retail_bi/model`, `tests/model`；另可写本任务证据/交接。
- 输出：`reports/model/split_manifest.json`, `reports/model/leakage_audit.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 训练、验证、测试按预测时间排列，前一阶段标签在下一阶段预测前成熟。
2. UCI可采用2010-04至2011-03训练、2011-04至07验证、2011-08至11测试的月初快照，实际覆盖先核验。
3. 归一化、编码、截尾、特征选择只拟合允许数据；同客多快照场景及非独立性披露。

证据：evidence/ML-04/2026-11-10-split.json

### ML-05 完成RFM规则与K-Means分群

- [ ] 状态：`todo`；阶段：`midterm`；范围：已选核心。
- 依据：C13, U03, Q03。
- 前置：EDA-05, ML-04。
- 允许修改：`src/retail_bi/model`, `reports/model`；另可写本任务证据/交接。
- 输出：`reports/model/rfm_segments.md`, `reports/model/cluster_metrics.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. R、F、M同一as_of与窗口，F按订单去重，M为明确正向消费；长期未购用户单独规则管理。
2. 先给可解释规则分群，再比较log变换/缩放后k=3至6聚类的轮廓、规模、稳定性。
3. 根据实际群体特征命名，历史M不称严格CLV；若用于预测特征，聚类只能训练期拟合。

证据：尚无已登记验收证据。

### ML-06 训练规则与逻辑回归基线

- [x] 状态：`done`；阶段：`midterm`；范围：已选核心。
- 依据：C13, U03, Q04。
- 前置：ML-04。
- 允许修改：`src/retail_bi/model`, `reports/model`；另可写本任务证据/交接。
- 输出：`reports/model/baselines.json`, `reports/model/baselines.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 规则、逻辑回归与后续模型共享母体、标签、时间切分和指标定义。
2. 缺失/不平衡处理限定训练数据并保留参数。
3. 保存实际验证结果和运行记录，不只描述算法。

证据：evidence/ML-06/2026-11-10-baselines.json

### ML-07 训练并有限调优LightGBM

- [x] 状态：`done`；阶段：`midterm`；范围：已选核心。
- 依据：C13, U03, Q04。
- 前置：ML-06。
- 允许修改：`src/retail_bi/model`, `reports/model`；另可写本任务证据/交接。
- 输出：`reports/model/training_runs.json`, `reports/model/boosting_validation.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 实际训练LightGBM或记录合理替代原因，保存随机种子、特征、参数、依赖和数据身份。
2. 调参/早停只使用训练验证数据，限制试验数量和资源。
3. 不以测试集调参；若提升不明显，允许最终保留更简单模型并解释。

证据：evidence/ML-07/2026-11-10-boosting.json

### ML-08 冻结模型、校准与阈值

- [x] 状态：`done`；阶段：`midterm`；范围：已选核心。
- 依据：U03, Q04。
- 前置：ML-07。
- 允许修改：`reports/model`, `src/retail_bi/model`；另可写本任务证据/交接。
- 输出：`reports/model/model_selection.json`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 在验证阶段确定模型、超参数、校准方法、阈值和触达容量K，记录冻结时间。
2. 考虑概率校准及业务容量，不使用固定0.5替代所有场景判断。
3. 不得在看到最终测试后悄悄换冠军；改变需新实验记录与新的诚实评估方案。

证据：evidence/ML-08/2026-11-10-selection.json

### ML-09 完成最终时间外评估

- [x] 状态：`done`；阶段：`midterm`；范围：已选核心。
- 依据：C13, Q04。
- 前置：ML-08。
- 允许修改：`reports/model`, `src/retail_bi/model`；另可写本任务证据/交接。
- 输出：`reports/model/test_metrics.json`, `reports/model/evaluation.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 报告ROC-AUC、PR-AUC、KS、F1、Recall/Lift@K、校准/Brier及基线，明确正类和阈值。
2. 实际样本量、独立客户数、类别比例和时间范围完整；单类分段指标不可算时说明。
3. 不承诺分数；若计算区间估计应按客户/时间分块，不把相关快照视为独立。

证据：evidence/ML-09/2026-11-10-evaluation.json

### ML-10 解释误差与适用限制

- [ ] 状态：`todo`；阶段：`midterm`；范围：已选核心。
- 依据：C12, C13, C27, Q04。
- 前置：ML-09, ML-05。
- 允许修改：`reports/model`；另可写本任务证据/交接。
- 输出：`reports/model/error_analysis.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 分析误报/漏报、不同时间/国家/价值群表现，避免暴露不必要身份。
2. 特征重要性或SHAP是模型解释，不解释成可干预因果效果。
3. 说明历史客户跨时间测试不证明能泛化到全新客户或当代中国市场。

证据：尚无已登记验收证据。

### ML-11 实现评分服务与适用性输出

- [ ] 状态：`todo`；阶段：`midterm`；范围：已选核心。
- 依据：U03, Q01, Q06。
- 前置：ML-10, DW-10。
- 允许修改：`src/retail_bi/model`, `sql`, `reports/model`；另可写本任务证据/交接。
- 输出：`src/retail_bi/model/scoring.py`, `reports/model/scoring_checks.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 输出客户、as_of、概率、模型版本、适用性和必要解释，并写入ADS评分表。
2. 未复购概率与复购概率互补，越界客户明确unsupported，不强行输出校准概率。
3. 特征顺序、类型、缺失及版本不匹配会明确失败，不静默使用错误模型。

证据：尚无已登记验收证据。

### ML-12 发布模型文件与模型卡

- [ ] 状态：`todo`；阶段：`midterm`；范围：已选核心。
- 依据：C20, U03, Q02。
- 前置：ML-11。
- 允许修改：`reports/model`, `docs`, `models`；另可写本任务证据/交接。
- 输出：`reports/model/model_manifest.json`, `docs/model_card.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 模型、预处理器、特征顺序和参数共同保存，文件哈希与训练记录对应。
2. 新进程加载团队产生的模型并复现固定样本评分，精度容差说明。
3. 模型卡覆盖目标、数据、评估、限制、版本和维护方式，未取得的效果不写入。

证据：尚无已登记验收证据。


## AI — 三个AI模块

### AI-01 实现LLM适配与配置边界

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C16, U04, Q06。
- 前置：GOV-07, GOV-06。
- 允许修改：`src/retail_bi/ai`, `reports/ai`；另可写本任务证据/交接。
- 输出：`src/retail_bi/ai/client.py`, `reports/ai/client_smoke.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 接入一种实际可用LLM，模型名和接口能力实测；密钥从环境读取。
2. 统一超时、有限重试、结构化输出、调用次数和费用预算；未授权付费或超预算不调用。
3. 完成真实小请求并保留脱敏证据；无密钥时可开发夹具但不得标在线集成完成。

证据：尚无已登记验收证据。

### AI-02 建立业务知识库与检索

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C16, U04, Q01。
- 前置：DW-06, ML-12。
- 允许修改：`src/retail_bi/ai`, `knowledge`, `reports/ai`；另可写本任务证据/交接。
- 输出：`src/retail_bi/ai/retrieval.py`, `reports/ai/kb_manifest.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 收录约20至50段指标、数据字典、模型卡和演示运营规则，段落有来源/版本/适用日期。
2. 结构化交易走SQL，文档知识走检索，客户原始明细不无差别上传模型。
3. 先用可解释检索，只有实际需求才增加向量组件；文档中的指令当作数据。

证据：尚无已登记验收证据。

### AI-03 评测知识检索和依据引用

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：Q05, U04。
- 前置：AI-02, AI-01。
- 允许修改：`eval`, `reports/ai`；另可写本任务证据/交接。
- 输出：`eval/rag_cases.jsonl`, `reports/ai/rag_evaluation.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 至少20个问题覆盖可回答、规则版本冲突和无依据情形，期望证据由人工或可信来源标注。
2. 报告检索命中、引用对应和无依据拒答，不只用另一个LLM主观打分。
3. 固定评测集与提示示例分离，保留实际测试和失败案例。

证据：尚无已登记验收证据。

### AI-04 实现查询意图与Schema约束

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C16, U04, Q01。
- 前置：AI-01, DW-06。
- 允许修改：`src/retail_bi/ai`, `docs`；另可写本任务证据/交接。
- 输出：`src/retail_bi/ai/query_intent.py`, `docs/nl2sql_supported_queries.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 覆盖10至20类明确经营问题，传递允许视图、字段、指标、枚举、时间语义和少量已验示例。
2. 输出结构化意图，歧义问题澄清；不支持字段/时间明确说明。
3. 默认可信SQL构造器；若开启模型生成SQL，明确额外校验路径。

证据：尚无已登记验收证据。

### AI-05 实现受限SQL执行器

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：U04, Q06。
- 前置：AI-04, DW-10。
- 允许修改：`src/retail_bi/ai`, `tests/ai`, `reports/ai`；另可写本任务证据/交接。
- 输出：`src/retail_bi/ai/sql_executor.py`, `reports/ai/sql_boundary_checks.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 验证单条允许查询、表列函数与AST白名单，参数化值，限制行数和独立执行超时。
2. 只读之外关闭外部访问，阻止文件表函数、COPY/ATTACH/扩展安装加载等非授权能力。
3. 测试写入、文件读取、跨表越权、注入及资源消耗；解析库与AGENTS都不是安全边界。

证据：尚无已登记验收证据。

### AI-06 实现查询回答与结果证据

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C16, U04, Q05。
- 前置：AI-05。
- 允许修改：`src/retail_bi/ai`, `reports/ai`；另可写本任务证据/交接。
- 输出：`src/retail_bi/ai/query_assistant.py`, `reports/ai/query_examples.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 先实际查询，再据有限结果解释，展示SQL/参数、口径、as_of和版本。
2. 空结果、取消、时间无覆盖、执行错误有明确状态，不让模型补造数据。
3. 多轮会话筛选和上下文隔离，不把其他客户/会话状态混入回答。

证据：尚无已登记验收证据。

### AI-07 完成NL2SQL标准集验收

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C16, U04, Q05, Q06。
- 前置：AI-06。
- 允许修改：`eval`, `reports/ai`, `tests/ai`；另可写本任务证据/交接。
- 输出：`eval/nl2sql_cases.jsonl`, `reports/ai/nl2sql_evaluation.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 至少40个未直接塞进few-shot的固定测例，其中至少24个可回答，并含歧义、无数据和越权。
2. 可回答问题按结果语义比较，目标正确率≥90%；报告分子分母，不只算SQL执行率。
3. 已声明拒绝测例全部拦截；失败案例与修复重测记录保留，不宣称普遍100%安全。

证据：尚无已登记验收证据。

### AI-08 实现周报事实计算

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C12, C16, U04, Q01。
- 前置：EDA-04, DW-06。
- 允许修改：`src/retail_bi/ai`, `reports/ai`；另可写本任务证据/交接。
- 输出：`src/retail_bi/ai/report_facts.py`, `reports/ai/report_facts_example.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. SQL/数值程序生成完整可比周期、环比、贡献拆解、异常候选和样本数。
2. 每项事实有evidence_id、单位、时间窗口、查询版本，分母为0或周期不全给状态。
3. LLM不承担金额求和或比例计算；与经营页面同一指标口径。

证据：尚无已登记验收证据。

### AI-09 实现周报生成与数值校验

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C16, U04, Q05。
- 前置：AI-08, AI-01, AI-02。
- 允许修改：`src/retail_bi/ai`, `reports/ai`；另可写本任务证据/交接。
- 输出：`src/retail_bi/ai/report_generator.py`, `reports/ai/weekly_report_example.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 数字和关键事实由模板/证据字段插入，模型组织解释与行动，不能新增未知数字。
2. 可能原因标为待验证假设；最终文本的数字、单位、窗口、引用再次检查。
3. 修复次数有上限，仍失败回退可信模板；输出标真实LLM或回放模式。

证据：尚无已登记验收证据。

### AI-10 完成周报场景验收

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C16, U04, Q05。
- 前置：AI-09。
- 允许修改：`eval`, `tests/ai`, `reports/ai`；另可写本任务证据/交接。
- 输出：`eval/report_cases.jsonl`, `reports/ai/report_evaluation.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 至少20个正常/异常场景，覆盖0分母、负净额、小样本和不完整周期。
2. 声明测例中可核对数字、单位和引用一致，违规数字或无依据因果结论被检测。
3. 分别保存确定性校验和人工抽查，不把有限测试写成所有输入永不出错。

证据：尚无已登记验收证据。

### AI-11 建立运营政策与预算规则

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C12, U04, Q01, Q06。
- 前置：ML-11, GOV-05。
- 允许修改：`knowledge`, `src/retail_bi/ai`, `reports/ai`；另可写本任务证据/交接。
- 输出：`knowledge/retention_policy.md`, `src/retail_bi/ai/policy_engine.py`, `reports/ai/policy_checks.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 价值、风险、模型适用性、退货和预算共同参与策略，不按风险直接最大折扣。
2. 公开数据缺触达/投诉/同意/库存/毛利/优惠时明确演示配置，与事实字段分开。
3. 资格、折扣上限、频率和预算用确定性代码检查，有边界夹具。

证据：尚无已登记验收证据。

### AI-12 实现有限步骤运营Agent

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C16, U04, Q06。
- 前置：AI-11, AI-01, AI-02。
- 允许修改：`src/retail_bi/ai`, `reports/ai`；另可写本任务证据/交接。
- 输出：`src/retail_bi/ai/retention_agent.py`, `reports/ai/agent_trace_example.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 按画像→风险→政策→约束→草稿工作流执行，有最大步骤和失败状态。
2. 只开放读取画像/风险、检索政策、预算检查、保存草稿等工具。
3. 无真实营销发送/发券权限；引用事实和政策，不从数据内容接收新系统指令。

证据：尚无已登记验收证据。

### AI-13 实现草稿存储和审阅状态

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：U04, Q01, Q06。
- 前置：AI-12。
- 允许修改：`src/retail_bi/ai`, `sql`, `reports/ai`；另可写本任务证据/交接。
- 输出：`src/retail_bi/ai/drafts.py`, `reports/ai/draft_examples.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 保存建议、理由、证据、规则版本、预算结果、文案及待审状态。
2. 同一请求可追踪不重复创建不可控副作用，修改/撤回草稿行为明确。
3. 保存草稿不等于消息已发送，UI和日志不得混淆。

证据：尚无已登记验收证据。

### AI-14 完成Agent边界场景验收

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C16, U04, Q05, Q06。
- 前置：AI-13。
- 允许修改：`eval`, `tests/ai`, `reports/ai`；另可写本任务证据/交接。
- 输出：`eval/agent_cases.jsonl`, `reports/ai/agent_evaluation.json`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 至少30个案例覆盖未知用户、无优惠、预算不足、频率限制、缺字段、模型不适用和工具失败。
2. 检查工作流完成、工具参数、约束和证据，已声明的关键违规场景均被阻止。
3. 保留真实LLM调用的代表性完整轨迹，不能只用静态预置文案冒充Agent。

证据：尚无已登记验收证据。

### AI-15 完成三模块联调与可观测性

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C16, U04, Q02, Q05, Q06。
- 前置：AI-03, AI-07, AI-10, AI-14。
- 允许修改：`reports/ai`, `docs`, `src/retail_bi/ai`；另可写本任务证据/交接。
- 输出：`reports/ai/integration_evaluation.json`, `docs/ai_system_card.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 三模块分别完成真实业务输入到结果的运行，并共享指标/数据版本与检索规则。
2. 日志记录耗时、调用/令牌或可得费用信息、工具、证据和错误，敏感值脱敏。
3. 在线、无密钥、超时、限流和回放模式可区分；系统卡列实际通过与未覆盖边界。

证据：尚无已登记验收证据。


## UI — Streamlit

### UI-01 建立Streamlit多页骨架

- [ ] 状态：`todo`；阶段：`midterm`；范围：已选核心。
- 依据：C15, U05。
- 前置：GOV-07, GOV-06。
- 允许修改：`app.py`, `src/retail_bi/ui`, `reports/ui`；另可写本任务证据/交接。
- 输出：`app.py`, `reports/ui/navigation_smoke.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 提供数据口径、经营、客户、预测、AI工作台五类页面入口。
2. 全局显示数据版本、数据时间和as_of，历史数据不标实时2026。
3. 应用实际启动，空数据状态可理解，不能只交静态截图。

证据：尚无已登记验收证据。

### UI-02 接入数据质量与口径页面

- [ ] 状态：`todo`；阶段：`midterm`；范围：已选核心。
- 依据：C14, U05, Q01。
- 前置：UI-01, DATA-12。
- 允许修改：`src/retail_bi/ui`, `reports/ui`；另可写本任务证据/交接。
- 输出：`reports/ui/data_page_review.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 展示来源、质量、覆盖、单位与限制，能打开指标解释和问题样本。
2. 页面统计与质量报告一致，不把模型样本量当原始数据量。
3. 不展示密钥或不必要个人信息。

证据：尚无已登记验收证据。

### UI-03 接入经营指标与OLAP交互

- [ ] 状态：`todo`；阶段：`midterm`；范围：已选核心。
- 依据：C10, C14, U05。
- 前置：UI-01, DW-10, EDA-02。
- 允许修改：`src/retail_bi/ui`, `reports/ui`；另可写本任务证据/交接。
- 输出：`reports/ui/business_page_review.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 筛选时间、国家等真实维度，完成切片/切块/下钻/旋转演示。
2. 图表数字与ADS一致，筛选后的分母和单位正确，不连接放大或重复累计。
3. 空结果、未知维度、不完整周期有明确提示。

证据：尚无已登记验收证据。

### UI-04 接入客户生命周期与分群

- [ ] 状态：`todo`；阶段：`midterm`；范围：已选核心。
- 依据：C14, U01, U05。
- 前置：UI-01, EDA-03, EDA-05, ML-05。
- 允许修改：`src/retail_bi/ui`, `reports/ui`；另可写本任务证据/交接。
- 输出：`reports/ui/customer_page_review.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 阶段、价值群、风险概念分别展示，可查看客户特征与规则依据。
2. cohort未成熟格子、匿名客户与长期沉睡客户显示正确状态。
3. 展示的是可观测历史，不编造年龄、渠道或真实身份。

证据：尚无已登记验收证据。

### UI-05 接入预测评估与名单试算

- [ ] 状态：`todo`；阶段：`midterm`；范围：已选核心。
- 依据：C14, U03, U05。
- 前置：UI-01, ML-12。
- 允许修改：`src/retail_bi/ui`, `reports/ui`；另可写本任务证据/交接。
- 输出：`reports/ui/model_page_review.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 展示基线、测试指标、样本范围、校准与误差，以及评分名单。
2. K或阈值交互作为试算，不覆盖冻结的最终测试结果或选模记录。
3. 超出模型母体明确不适用；特征变化不表述为因果效果。

证据：尚无已登记验收证据。

### UI-06 接入AI工作台

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C14, C16, U04, U05。
- 前置：UI-01, AI-15。
- 允许修改：`src/retail_bi/ui`, `reports/ui`；另可写本任务证据/交接。
- 输出：`reports/ui/ai_page_review.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 三个模块可分别使用，展示SQL/证据、周报引用、策略预算和草稿状态。
2. 加载、取消、失败、重试和导出体验完整，模型请求不重复无界触发。
3. 各会话状态隔离，回放输出有醒目标识且不能替代真实调用验收。

证据：尚无已登记验收证据。

### UI-07 完成可读性、缓存与异常交互验收

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C14, C29, U05, Q06。
- 前置：UI-02, UI-03, UI-04, UI-05, UI-06。
- 允许修改：`src/retail_bi/ui`, `reports/ui`；另可写本任务证据/交接。
- 输出：`reports/ui/full_ui_review.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 检查字体、对比、坐标、单位、布局和目标展示屏幕，无裁切或误导图形。
2. query cache包含版本和筛选，数据库连接遵守线程/会话边界；页面不执行全量ETL/训练。
3. 数据缺失、API失败、模型版本不匹配可恢复，错误提示不泄露内部秘钥。

证据：尚无已登记验收证据。


## DOC — 报告与材料

### DOC-01 完成选题报告并形成阶段一材料

- [ ] 状态：`in_review`；阶段：`proposal`；范围：已选核心。
- 依据：C17, C24, C27。
- 前置：GOV-03, GOV-06, DATA-12, EDA-01, DOC-04。
- 允许修改：`deliverables`, `reports/submission`；另可写本任务证据/交接。
- 输出：`deliverables/proposal.docx`, `reports/submission/proposal_manifest.json`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 按官方五部分：目的意义、背景综述参考、内容、方法主要问题、实习计划。
2. 团队真实信息、数据选择/预处理证据、架构分工与三个截止日完整；不写未完成模型结果。
3. Word/PDF实际打开或渲染核验，提交就绪与已收到分别记录；当期实际提交立即保存回执，不等待REL-07终期汇总。

证据：尚无已登记验收证据。

### DOC-02 完成中期检查报告与答辩材料

- [ ] 状态：`todo`；阶段：`midterm`；范围：已选核心。
- 依据：C25, C28。
- 前置：DOC-01, DW-10, EDA-06, ML-12, UI-05。
- 允许修改：`deliverables`, `reports/submission`；另可写本任务证据/交接。
- 输出：`deliverables/midterm_report.docx`, `deliverables/midterm_slides.pptx`, `reports/submission/midterm_manifest.json`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 展示已完成的数仓、EDA、聚类、基线与预测及真实评估，区分AI已完成和计划。
2. 列当前问题、未完成工作、风险和终期排期，不能用计划截图冒充系统。
3. 报告与PPT可读，准备现场问答和实际演示；当期实际提交/答辩立即留凭证，不等待REL-07终期汇总。

证据：尚无已登记验收证据。

### DOC-03 完成正式报告六章及设计方案覆盖

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C18, C19, C26, C30。
- 前置：DOC-02, AI-15, UI-07, DOC-05, DOC-08。
- 允许修改：`deliverables`, `reports/submission`；另可写本任务证据/交接。
- 输出：`deliverables/final_report.docx`, `reports/submission/report_compliance.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 按附录封面和六章组织，并通过映射表覆盖五(一)九类设计内容。
2. 步骤有真实截图或关键代码，环境、数据、算法、AI评价、限制与结果一致。
3. 引用和图表编号一致，渲染逐页检查，无占位成绩或待填结论混入正式稿。

证据：尚无已登记验收证据。

### DOC-04 核验学术文献与综述引用

- [ ] 状态：`todo`；阶段：`proposal`；范围：已选核心。
- 依据：C17。
- 前置：GOV-05。
- 允许修改：`docs`, `reports/references`；另可写本任务证据/交接。
- 输出：`docs/reference_registry.md`, `reports/references/reference_audit.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 教师原文为查阅10篇以上文献；本项目按至少11篇真实学术文献验收，建议12至14篇，核对作者、年份、题目、刊会及原始来源。
2. 按RFM/价值、复购/流失、NL2SQL、RAG/Agent组织综述，写采用方法与限制。
3. 区分已核元数据/已读摘要/已读全文；官方技术资料和数据卡另列，不编造DOI或贡献。

证据：尚无已登记验收证据。

### DOC-05 整理实现证据、图表和复现说明

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C18, C19, C20, C28, Q02。
- 前置：DW-10, ML-12, AI-15, UI-07。
- 允许修改：`docs`, `reports/submission`；另可写本任务证据/交接。
- 输出：`docs/runbook.md`, `reports/submission/evidence_index.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 每个主要实验步骤对应实际代码/截图/运行结果，能从结论定位证据。
2. 提供环境安装、数据放置、ETL、训练、应用启动和异常恢复方法。
3. 图表与报告使用相同数据和模型版本，证据不包含密钥或不必要个人信息。

证据：尚无已登记验收证据。

### DOC-06 整理个人贡献与答辩知识清单

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C02, C22, C23。
- 前置：GOV-03, DOC-05。
- 允许修改：`reports/team`, `ops`；另可写本任务证据/交接。
- 输出：`reports/team/contributions.md`, `reports/team/defense_qa.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 按真实任务、Git提交/文件审查和文档分工说明成员贡献，不倒造历史。
2. 每人至少准备1至2个本人模块问题及关键全流程问题。
3. 成员能复现或解释关键模块，AI生成成果与人的审阅/集成工作如实记录。

证据：尚无已登记验收证据。

### DOC-07 完成终期PPT与10分钟脚本

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C21, C26, C30。
- 前置：DOC-03, DOC-06。
- 允许修改：`deliverables`, `docs`；另可写本任务证据/交接。
- 输出：`deliverables/final_slides.pptx`, `docs/demo_script.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 建议业务1分、数据数仓2分、模型2分、AI3分、异常1分、复现贡献1分，按实际调整。
2. PPT上的数据、指标和界面与冻结版本一致，明确局限。
3. 关键操作可现场完成，演示脚本含失败恢复和明确标记回放。

证据：尚无已登记验收证据。

### DOC-08 完成问题分析、反思与应用前景

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C12, C18, C19, C27, C30。
- 前置：EDA-06, ML-10, AI-15。
- 允许修改：`reports/analysis`；另可写本任务证据/交接。
- 输出：`reports/analysis/reflection_and_roadmap.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 记录实际遇到的问题、定位、方案比较、解决效果与未解决限制，不能虚构故障经历。
2. 商业价值用效率/名单质量/数字正确率等可测实验支持，真实留存和ROI须有干预数据。
3. 说明后续数据、部署、评估与运营实验需求，不把课程演示称已商用。

证据：尚无已登记验收证据。


## REL — 复现与交付

### REL-01 执行有针对性的集成与回归验证

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C20, C29, Q02, Q05, Q06。
- 前置：UI-07, AI-15, ML-12, DW-10。
- 允许修改：`tests`, `reports/release`；另可写本任务证据/交接。
- 输出：`reports/release/test_summary.json`, `reports/release/critical_paths.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 关键测试覆盖数据规则、指标对账、时间边界、模型加载、SQL约束、AI证据和主要页面路径。
2. 测试针对真实风险，不只检查函数自己返回的常数或模板字段。
3. 保留命令、环境、实际退出码、失败与修复结果，未运行项不能标passed。

证据：尚无已登记验收证据。

### REL-02 完成干净环境或第二机器复现

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C20, C29, Q02。
- 前置：REL-01, GOV-07, DOC-05。
- 允许修改：`reports/release`, `docs`；另可写本任务证据/交接。
- 输出：`reports/release/reproduction.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 在干净环境或第二机器按文档从允许数据重建，记录实际系统与架构。
2. 无需开发者未记录的手工步骤即可运行ETL、模型加载/训练和Web核心路径。
3. 不能只因Linux容器通过就声称M1已验证；跨平台差异记录并处理目标展示机器。

证据：尚无已登记验收证据。

### REL-03 打包代码、数据、模型和配置

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C07, C20, C26。
- 前置：REL-02, DOC-03, DOC-07。
- 允许修改：`deliverables`, `docs`；另可写本任务证据/交接。
- 输出：`deliverables/submission_manifest.json`, `docs/submission_readme.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 清单列代码版本、依赖、允许的数据及哈希、模型、报告、PPT、演示和贡献证据。
2. 教师要求的数据交付有实际文件或获准替代方式；不把公开数据许可自动当课程允许对外发布。
3. 无真实API key、个人隐私或无关文件；解包路径不依赖开发者绝对目录。

证据：尚无已登记验收证据。

### REL-04 核验运行资源与服务降级

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C29, Q06。
- 前置：REL-01。
- 允许修改：`reports/release`, `src/retail_bi`；另可写本任务证据/交接。
- 输出：`reports/release/performance_and_budget.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 记录实际硬件、数据规模、冷/热查询、主要交互和AI耗时与成本估算方法。
2. 性能目标先基线测量再冻结；若不达约定目标，优化或显式记录变更，不隐藏修改。
3. 断网、缺key、超时/限流和预算耗尽有明确降级；回放不能冒充在线调用。

证据：尚无已登记验收证据。

### REL-05 完成现场演练和个人问答

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C21, C22, C29。
- 前置：REL-03, REL-04, DOC-06, DOC-07。
- 允许修改：`reports/release`；另可写本任务证据/交接。
- 输出：`reports/release/rehearsal.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 至少一次完整计时演示，建议两次；教师要求10分钟，不以录屏代替全部现场能力。
2. 每位成员实际解释所负责工作和1至2个问题，记录发现的阻断点。
3. 演示数据、机器、模型和网络模式固定，恢复步骤实际验证。

证据：尚无已登记验收证据。

### REL-06 最终逐项核对课程与项目承诺

- [ ] 状态：`todo`；阶段：`final`；范围：已选核心。
- 依据：C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23, C24, C25, C26, C27, C28, C29, C30, U01, U02, U03, U04, U05, Q02。
- 前置：REL-05。
- 允许修改：`reports/release`, `project`；另可写本任务证据/交接。
- 输出：`reports/release/final_requirements_review.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 正文/附录评分项、报告内容、阶段材料和用户承诺逐项列证据、结果和未满足项。
2. 除本项与实际提交项外，所有已选核心工作完成；数据时效等硬条件未解决则不能宣称全要求满足。
3. 自查是证据覆盖检查，不伪造教师评分；可选加分只列已实施且有证据的项目。

证据：尚无已登记验收证据。

### REL-07 记录真实提交和答辩结果

- [ ] 状态：`todo`；阶段：`submitted`；范围：已选核心。
- 依据：C24, C25, C26。
- 前置：REL-06。
- 允许修改：`reports/submission`；另可写本任务证据/交接。
- 输出：`reports/submission/receipts.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 汇总已在每阶段实际发生时保存的回执，核对选题、中期、终期渠道、时间和版本；未知/迟交/缺交如实记录，不能伪称按时。
2. 记录实际现场答辩完成情况，材料就绪不能自动转成已提交/已答辩。
3. 实际发送/提交遵循已有用户授权；无权限时交付包并等待用户提供回执，不伪造签名或成绩。

证据：尚无已登记验收证据。


## BON — 可选扩展

### BON-01 可选：销量预测

- [ ] 状态：`skipped`；阶段：`final`；范围：默认关闭的可选项。
- 依据：X01。
- 前置：ML-12。
- 允许修改：`src/retail_bi/extensions`, `reports/extensions`；另可写本任务证据/交接。
- 输出：`reports/extensions/sales_forecast.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 以总量或前20个稳定商品为对象，建立周季节朴素基线及合理模型。
2. 滚动回测MAE/WAPE，零分母处理，特征只用过去。
3. 无库存时不把销量当真实需求或宣称库存优化收益。

**未启用原因：** 可选项默认未启用，不计核心完成率。

证据：尚无已登记验收证据。

### BON-02 可选：购物篮关联规则

- [ ] 状态：`skipped`；阶段：`final`；范围：默认关闭的可选项。
- 依据：X02。
- 前置：DW-10。
- 允许修改：`src/retail_bi/extensions`, `reports/extensions`；另可写本任务证据/交接。
- 输出：`reports/extensions/association_rules.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 仅对真实可定义订单篮子执行，取消退款和非商品项规则明确。
2. 支持度、置信度、提升度、最小样本和时间稳定性有证据。
3. 不把共现当因果，也不为推荐算法伪造订单号。

**未启用原因：** 可选项默认未启用，不计核心完成率。

证据：尚无已登记验收证据。

### BON-03 可选：生产可用AI能力强化

- [ ] 状态：`skipped`；阶段：`final`；范围：默认关闭的可选项。
- 依据：B01。
- 前置：AI-15, REL-01。
- 允许修改：`src/retail_bi`, `reports/extensions`；另可写本任务证据/交接。
- 输出：`reports/extensions/ai_readiness.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 先确认教师对3个以上和生产可用的具体判据，逐项列认证/权限、运行可靠性与监控证据。
2. 限额、恢复、升级/回滚和操作说明按实际需求实现，不能只换名称即称生产级。
3. 加分由教师评定，不因三个按钮或有限测例通过就保证+3。

**未启用原因：** 可选项默认未启用，不计核心完成率。

证据：尚无已登记验收证据。

### BON-04 可选：LLM训练或微调

- [ ] 状态：`skipped`；阶段：`final`；范围：默认关闭的可选项。
- 依据：B02。
- 前置：AI-15, REL-01。
- 允许修改：`src/retail_bi/extensions`, `reports/extensions`；另可写本任务证据/交接。
- 输出：`reports/extensions/finetuning.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 有真实必要性、授权训练数据、资源预算和独立评测集，核心交付已稳定。
2. 保存基座、训练方法参数、检查点、成本与微调前后真实比较。
3. 不把Prompt或RAG称为微调，不虚构GPU运行和提升。

**未启用原因：** 可选项默认未启用，不计核心完成率。

证据：尚无已登记验收证据。

### BON-05 可选：产品级Demo强化

- [ ] 状态：`skipped`；阶段：`final`；范围：默认关闭的可选项。
- 依据：B03。
- 前置：REL-05。
- 允许修改：`src/retail_bi`, `reports/extensions`；另可写本任务证据/交接。
- 输出：`reports/extensions/product_readiness.md`。
- 实际执行要求：必须有运行或交互证据。

**验收条件**

1. 先确认商业可用要求，按真实场景增加权限、运行维护、恢复和使用者验收。
2. 普通Streamlit课程演示与生产部署分开，公开部署需授权及课程数据范围确认。
3. 有独立用户试用和缺陷闭环证据，无法验证的项目明确保留。

**未启用原因：** 可选项默认未启用，不计核心完成率。

证据：尚无已登记验收证据。

### BON-06 可选：开源、发表或竞赛

- [ ] 状态：`skipped`；阶段：`final`；范围：默认关闭的可选项。
- 依据：B04, C07。
- 前置：REL-06。
- 允许修改：`reports/extensions`, `docs`；另可写本任务证据/交接。
- 输出：`reports/extensions/publication_or_competition.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 确认用户授权、教师数据发布限制和目标平台条款，决定代码/文档/样例公开范围。
2. 保存真实仓库、竞赛或发表证据；不得伪造Star、刷量或生成虚假名次。
3. 不能公开的课程原件、原始数据、模型敏感产物和密钥先排除。

**未启用原因：** 可选项默认未启用，不计核心完成率。

证据：尚无已登记验收证据。

### BON-07 可选：技术博客或教学视频

- [ ] 状态：`skipped`；阶段：`final`；范围：默认关闭的可选项。
- 依据：B05。
- 前置：DOC-08, REL-05。
- 允许修改：`reports/extensions`；另可写本任务证据/交接。
- 输出：`reports/extensions/tutorial.md`。
- 实际执行要求：以相应来源核验/文档审阅为主，必要运行另记录。

**验收条件**

1. 内容基于真实项目，讲清业务、方法、运行和限制，引用完整。
2. 图表、代码、数据和成员信息发布范围已获授权。
3. 保存真实成稿或视频及发布证据，未发布不称已发表。

**未启用原因：** 可选项默认未启用，不计核心完成率。

证据：尚无已登记验收证据。
