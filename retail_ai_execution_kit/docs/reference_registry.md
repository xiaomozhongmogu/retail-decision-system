# 参考文献种子清单

以下承接2026-11-05前期调研，含14篇条目。它们可作为DOC-04起点，不代表后续AI已阅读全文。正式引用须按引用的具体主张核验原始来源，并记录元数据/摘要/全文阅读层次。官方数据和技术文档另列。

[1] CHEN D, SAIN S L, GUO K. Data mining for the online retail industry: A case study of RFM model-based customer segmentation using data mining[J]. Journal of Database Marketing & Customer Strategy Management, 2012, 19(3): 197–208. DOI: 10.1057/dbm.2012.17. https://link.springer.com/article/10.1057/dbm.2012.17
贡献与用途：针对在线零售开展RFM与K-Means客户分群并解释各群特征，是本项目画像和业务建议的直接先例。

[2] FADER P S, HARDIE B G S, LEE K L. RFM and CLV: Using Iso-Value Curves for Customer Base Analysis[J]. Journal of Marketing Research, 2005, 42(4): 415–430. DOI: 10.1509/jmkr.2005.42.4.415. https://www.brucehardie.com/abstracts/abstract-fhl_rfm_clv_2005-02.html
贡献与用途：建立RFM历史行为与未来客户价值的模型联系，用于区分历史价值画像和严格CLV估计。

[3] FADER P S, HARDIE B G S, LEE K L. “Counting Your Customers” the Easy Way: An Alternative to the Pareto/NBD Model[J]. Marketing Science, 2005, 24(2): 275–284. DOI: 10.1287/mksc.1040.0098. https://www.brucehardie.com/papers/018/
贡献与用途：提出BG/NBD非契约型客户购买模型，可作为未来交易次数预测的理论背景及扩展基线。

[4] BUREZ J, VAN DEN POEL D. Handling class imbalance in customer churn prediction[J]. Expert Systems with Applications, 2009, 36(3, Part 1): 4626–4636. DOI: 10.1016/j.eswa.2008.05.027. https://biblio.ugent.be/publication/677499
贡献与用途：研究不平衡样本和模型评价，用于类别分布检查、训练集处理及AUC与Lift指标设计。

[5] ASCARZA E. Retention Futility: Targeting High-Risk Customers Might be Ineffective[J]. Journal of Marketing Research, 2018, 55(1): 80–98. DOI: 10.1509/jmr.16.0163. https://journals.sagepub.com/doi/10.1509/jmr.16.0163
贡献与用途：用干预实验说明高流失风险不必然对应高挽回响应，约束本项目营销Agent对增量效果的表述。

[6] CHEN T, GUESTRIN C. XGBoost: A Scalable Tree Boosting System[C]//Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining. 2016: 785–794. DOI: 10.1145/2939672.2939785. https://arxiv.org/abs/1603.02754
贡献与用途：提出可扩展树提升系统，可作为表格行为预测的备选实现；无需与LightGBM同时强制实现。

[7] KE G, MENG Q, FINLEY T, et al. LightGBM: A Highly Efficient Gradient Boosting Decision Tree[C]//Advances in Neural Information Processing Systems. 2017, 30. https://proceedings.neurips.cc/paper_files/paper/2017/hash/6449f44a102fde848669bdd9eb6b76fa-Abstract.html
贡献与用途：通过GOSS与EFB提高梯度提升树效率，用于客户复购预测主模型。

[8] LEWIS P, PEREZ E, PIKTUS A, et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks[C]//Advances in Neural Information Processing Systems. 2020, 33: 9459–9474. https://proceedings.neurips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html
贡献与用途：结合生成模型与外部检索知识，用于指标、规则和模型说明的证据检索，不代替SQL数值计算。

[9] YAO S, ZHAO J, YU D, et al. ReAct: Synergizing Reasoning and Acting in Language Models[C]//The Eleventh International Conference on Learning Representations. 2023. https://openreview.net/pdf?id=WE_vluYUL-X
贡献与用途：组织语言模型与工具的交互，用于读取画像、检索规则和检查策略的受限运营工作流。

[10] LI J, HUI B, QU G, et al. Can LLM Already Serve as A Database Interface? A BIg Bench for Large-Scale Database Grounded Text-to-SQLs[C]//Advances in Neural Information Processing Systems. 2023, 36. DOI: 10.52202/075280-1835. https://proceedings.neurips.cc/paper_files/paper/2023/hash/83fc8fab1710363050bbd1d4b8cc0021-Abstract-Datasets_and_Benchmarks.html
贡献与用途：BIRD考察真实数据库内容、知识和查询效率，支持本项目建立结果匹配和语义口径评估。

[11] LEI F, CHEN J, YE Y, et al. Spider 2.0: Evaluating Language Models on Real-World Enterprise Text-to-SQL Workflows[C]//The Thirteenth International Conference on Learning Representations. 2025. https://proceedings.iclr.cc/paper_files/paper/2025/hash/46c10f6c8ea5aa6f267bcdabcb123f97-Abstract-Conference.html
贡献与用途：将评估扩展到企业级多步骤数据库工作流，说明受限数据域、语义层和执行验证的必要性。

[12] 梁清源, 朱琪豪, 孙泽宇, 等. 基于深度学习的SQL生成研究综述[J]. 中国科学: 信息科学, 2022, 52(8): 1363–1392. DOI: 10.1360/SSI-2021-0316. https://scis.scichina.com/cn/2022/SSI-2021-0316.pdf
贡献与用途：从场景、数据集、模型结构与评价梳理SQL生成，提供国内研究背景及Schema理解方法框架。

[13] 郭先会, 张梦姣, 马军. 基于大语言模型的智能体构建综述[J]. 通信技术, 2024, 57(9): 873–879. https://txjs.cbpt.cnki.net/portal/journal/portal/client/paper/06992c3314e139bb3ea7b428c1f32688
贡献与用途：综述智能体组成、架构与评价，为受限工具调用和Agent验收提供中文文献背景。

[14] LIAKHNOVICH K, NIKIFOROVA A, MATVEEV N, et al. T-ECD: A Large-Scale Cross-Domain E-Commerce Dataset for Industrial Recommender Systems[C]//Proceedings of the 32nd ACM SIGKDD Conference on Knowledge Discovery and Data Mining V.2. 2026: 9382–9391. DOI: 10.1145/3770855.3817588. https://doi.org/10.1145/3770855.3817588
贡献与用途：提供跨电商域的工业推荐研究数据与基准。论文发表时间、数据版本时间和事件实际时间需分别核验，不能混用。
