# 参考文献登记与文献综述

- 版本：v2，2026-11-11，claude-opus-5-5（DOC-04）。v1 是 2026-11-05 前期调研留下的 14 条种子清单。
- v2 对 14 条逐条核对了作者、年份、题目、刊物或会议以及原始来源。核对方法和每条依据见 `reports/references/reference_audit.md`。
- 阅读层次分三级：**已核元数据**（作者、年份、题目、出处与 DOI 已对照原始来源）、**已读摘要**（另外读过出版方页面上的摘要）、**已读全文**。本次没有通读任何一篇的全文，所以没有条目标为“已读全文”。正文中的引用只用于摘要能支持的主张。
- 学术文献共 14 篇，全部已核元数据，其中 12 篇已读摘要。官方技术资料和数据卡另列在第 3 节，不计入学术文献数量。

## 1. 文献清单（GB/T 7714-2015 格式）

| 编号 | 文献 | 阅读层次 |
|---|---|---|
| [1] | CHEN D, SAIN S L, GUO K. Data mining for the online retail industry: A case study of RFM model-based customer segmentation using data mining[J]. Journal of Database Marketing & Customer Strategy Management, 2012, 19(3): 197-208. DOI: 10.1057/dbm.2012.17. | 已读摘要 |
| [2] | FADER P S, HARDIE B G S, LEE K L. RFM and CLV: Using iso-value curves for customer base analysis[J]. Journal of Marketing Research, 2005, 42(4): 415-430. DOI: 10.1509/jmkr.2005.42.4.415. | 已读摘要 |
| [3] | FADER P S, HARDIE B G S, LEE K L. "Counting your customers" the easy way: An alternative to the Pareto/NBD model[J]. Marketing Science, 2005, 24(2): 275-284. DOI: 10.1287/mksc.1040.0098. | 已读摘要 |
| [4] | BUREZ J, VAN DEN POEL D. Handling class imbalance in customer churn prediction[J]. Expert Systems with Applications, 2009, 36(3): 4626-4636. DOI: 10.1016/j.eswa.2008.05.027. | 已核元数据（含关键词） |
| [5] | ASCARZA E. Retention futility: Targeting high-risk customers might be ineffective[J]. Journal of Marketing Research, 2018, 55(1): 80-98. DOI: 10.1509/jmr.16.0163. | 已读摘要 |
| [6] | CHEN T, GUESTRIN C. XGBoost: A scalable tree boosting system[C]//Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining. New York: ACM, 2016: 785-794. DOI: 10.1145/2939672.2939785. | 已读摘要 |
| [7] | KE G, MENG Q, FINLEY T, et al. LightGBM: A highly efficient gradient boosting decision tree[C]//Advances in Neural Information Processing Systems 30. 2017. | 已读摘要 |
| [8] | LEWIS P, PEREZ E, PIKTUS A, et al. Retrieval-augmented generation for knowledge-intensive NLP tasks[C]//Advances in Neural Information Processing Systems 33. 2020: 9459-9474. | 已读摘要 |
| [9] | YAO S, ZHAO J, YU D, et al. ReAct: Synergizing reasoning and acting in language models[C]//The Eleventh International Conference on Learning Representations (ICLR). 2023. | 已读摘要 |
| [10] | LI J, HUI B, QU G, et al. Can LLM already serve as a database interface? A BIg bench for large-scale database grounded text-to-SQLs[C]//Advances in Neural Information Processing Systems 36. 2023: 42330-42357. DOI: 10.52202/075280-1835. | 已读摘要 |
| [11] | LEI F, CHEN J, YE Y, et al. Spider 2.0: Evaluating language models on real-world enterprise text-to-SQL workflows[C]//The Thirteenth International Conference on Learning Representations (ICLR). 2025: 28691-28735. | 已读摘要 |
| [12] | 梁清源, 朱琪豪, 孙泽宇, 等. 基于深度学习的SQL生成研究综述[J]. 中国科学: 信息科学, 2022, 52(8): 1363-. DOI: 10.1360/SSI-2021-0316. | 已核元数据（另读目录） |
| [13] | 郭先会, 张梦姣, 马军. 基于大语言模型的智能体构建综述[J]. 通信技术, 2024, 57(9): 873-879. | 已读摘要 |
| [14] | LIAKHNOVICH K, NIKIFOROVA A, MATVEEV N, et al. T-ECD: A large-scale cross-domain e-commerce dataset for industrial recommender systems[C]//Proceedings of the 32nd ACM SIGKDD Conference on Knowledge Discovery and Data Mining V.2. New York: ACM, 2026: 9382-9391. DOI: 10.1145/3770855.3817588. | 已读摘要 |

与 v1 相比的更正：

- [4] 卷期写为 36(3)，Crossref 没有记录 “Part 1”。
- [7] 出版方页面没有页码，因此删去页码。
- [10] 补上页码 42330-42357。
- [11] 补上页码 28691-28735。
- [12] 出版方只给出起始页 1363。v1 写的结束页 1392 没有找到原始依据，所以不写。
- [14] 摘要显示数据来自一个银行生态中的匿名化真实数据，涵盖五个电商相关领域。本项目没有使用这份数据（见第 2.5 节）。

## 2. 文献综述（按主题）

### 2.1 RFM 与客户价值

Chen 等人对一家在线零售商的交易数据按 RFM（最近一次购买、购买频率、消费金额）分群：先用 K-Means，再用决策树归纳，得到有意义的客户群并据此提出营销建议 [1]。Fader、Hardie 和 Lee 把 RFM 与客户终身价值（CLV）用一个随机模型正式联系起来（Pareto/NBD 加 gamma-gamma 消费子模型），提出“等价值曲线”：购买历史不同的客户，未来价值可能相同 [2]。

**本项目采用**：ML-05 先做可解释的 RFM 规则分群，再用 K-Means 作探索对照，与 [1] 的做法一致；切分点在训练期拟合，再用于最新快照。

**限制**：本项目的 M 是近 90 天商品金额，是对历史消费的描述，不是 [2] 意义上的 CLV 估计。页面和报告都不把价值群称为“终身价值”。

### 2.2 复购预测、类别不平衡与挽回

BG/NBD 模型是 Pareto/NBD 的一个容易实现的替代：两者结果相近，但 BG/NBD 的参数估计简单得多，适合预测非契约型客户未来的购买次数 [3]。Burez 与 Van den Poel 研究了流失预测中的类别不平衡问题，涉及欠采样、过采样、随机森林与 boosting 等处理方式（据关键词与题目，未读摘要全文）[4]。Ascarza 结合两项现场实验与机器学习，发现流失风险最高的客户不一定是挽回活动的最佳对象。她主张按“对干预的响应差异”选择目标客户，而不是按风险选择 [5]。

**本项目采用**：

- 正例率约 7%，所以评估以 PR-AUC、Lift 和校准为主，并比较了类别加权版本（ML-06、ML-08）。这与 [4] 关注的问题一致。
- 挽回政策（AI-11）不按风险加大折扣。没有随机对照试验之前，不报告挽回金额。效果只能用试验检验。这条约束直接来自 [5]。

**限制**：

- 没有实现 BG/NBD [3]，它只作为可扩展的基线背景。
- 本项目模型的测试 ROC-AUC 为 0.515，个体区分接近随机，所以名单排序采用规则。
- 数据中没有任何干预或响应记录，无法做 [5] 建议的响应建模。

### 2.3 梯度提升树

XGBoost 提出了稀疏感知的分裂算法、加权分位数草图，并在缓存访问、压缩和分片上做了系统优化，使树提升能扩展到很大规模 [6]。LightGBM 用基于梯度的单侧采样（GOSS）和互斥特征捆绑（EFB）减少需要扫描的样本和特征，从而提高梯度提升决策树的效率 [7]。

**本项目采用**：ML-07 在验证集上比较了 LightGBM 与逻辑回归。LightGBM 的验证 PR-AUC 为 0.0882，逻辑回归为 0.0897，最终选择更简单的逻辑回归（ML-08）。XGBoost 没有实现。

**限制**：数据规模（约 9 万条客户×周样本）远小于 [6][7] 针对的场景，提升树的效率优势在这里不起作用。

### 2.4 自然语言查询数据库（NL2SQL）

梁清源等人从应用场景、数据集、模型结构（编码、解码、模式链接）和评估方法几方面梳理了基于深度学习的 SQL 生成研究（据目录，未读正文）[12]。BIRD 基准强调真实数据库内容：脏数据、问题与数据之间所需的外部知识、查询效率。论文报告 GPT-4 的执行准确率为 54.89%，远低于人类的 92.96%（数字据摘要）[10]。Spider 2.0 把评估扩展到企业级工作流：多数据库系统、上千列的模式、多条 SQL 和方言文档。论文报告基于 o1-preview 的代码代理框架只解决 21.3% 的任务，而同一方法在 Spider 1.0 上为 91.2%、在 BIRD 上为 73.0% [11]。

**本项目采用**：

- 不开放任意 SQL，只允许查询登记过的 ADS 视图。
- 数字只来自视图查询，口径来自指标契约。
- 知识检索先判断问题该走查询还是走文档（AI-02 的 route）。

这些做法回应了 [10][11] 指出的难点：在受限的语义层上执行并核验结果，而不是让模型自由生成复杂 SQL。

**限制**：问答模块（AI-04 至 AI-07）要等 LLM 凭据。截至本文没有任何 NL2SQL 评测结果，不能引用 [10][11] 的数字来说明本项目的效果。

### 2.5 检索增强与工具代理

RAG 把预训练的生成模型（参数记忆）与通过神经检索器访问的维基百科向量索引（非参数记忆）结合起来。论文在三个开放域问答任务上取得当时最好的结果，优于只用参数记忆的 seq2seq 模型和任务专用的检索-抽取架构；在生成任务上，RAG 的输出比只用参数记忆的基线更具体、更多样、更符合事实 [8]。ReAct 让语言模型交替生成推理过程和动作：推理帮助制定和更新计划，动作用来访问知识库等外部来源。它在问答和交互式决策任务上减少了幻觉与错误传播 [9]。郭先会等人综述了基于大语言模型的智能体：分类、基本组成（任务规划、执行）、典型案例与有效性评估方法 [13]。

**本项目采用**：

- 知识库（AI-02）采用检索后引用的思路，但用可解释的 BM25 关键字检索代替 [8] 的稠密向量检索。原因是只有 44 段文档，并且需要能解释为什么命中。
- 检索到的文字只作为数据，不作为指令。
- 挽回 Agent（AI-12 起）计划采用 [9][13] 的“规划—调用工具—检查”流程，但所有资格、折扣与预算判定都由确定性代码完成（AI-11）。

**限制**：

- 关键字检索对同义词敏感，固定 20 题中前 3 名命中 17 题。
- Agent 还没有实现，暂无效果证据。

T-ECD 是一份公开的大规模跨领域电商推荐数据集，来自一个银行生态的匿名化真实数据，涵盖市场、零售、支付、优惠与评价五个领域，并提供了推荐模型基准 [14]。它在数据选型时作为候选列出（`docs/data_candidates.md`），但主数据最终选定为完全合成的交易数据（D013）。因此 [14] 只作为“真实工业数据可得性”的背景，不支持本项目的任何结论。

## 3. 官方技术资料与数据卡（不计入学术文献）

| 资料 | 用途 | 地址 |
|---|---|---|
| 合成电商交易数据包 `baseline_10000_seed42.zip`（下载页未标明数据许可） | 本项目主数据（D013） | https://www.andresblancog.com/downloads/synthetic-dataset-generator/baseline_10000_seed42.zip |
| DuckDB 文档（本机 2.0.0） | 数仓与只读发布 | https://duckdb.org/docs/ |
| Streamlit 文档（本机 1.67.0） | 多页应用、AppTest 测试 | https://docs.streamlit.io/ |
| scikit-learn 文档（本机 1.9.1） | 逻辑回归、K-Means、评估指标 | https://scikit-learn.org/stable/ |
| LightGBM 文档（本机 4.7.0） | 提升树对照模型 | https://lightgbm.readthedocs.io/ |
| UCI Online Retail II、T-ECD 数据卡 | 数据选型时的候选，未采用 | 见 `docs/data_candidates.md` |

这些资料只说明工具和数据的出处，不能作为学术观点引用。版本号是本机实际安装的版本。
