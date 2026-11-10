# 原始 ZIP 重建工程工作数据（2026-11-10）

本阶段已实际实现并验证离线工程输入。正式课程数据资格、DATA-03/04 依赖仍未完成，DATA-05 不标 done。

## 结果

- 原始 ZIP SHA-256：`d50ee64a0478d8ae8df1b8b66521671a4911e19f911ae86196452a668f917a16`；原文件未改。只重建已选本地合成包，不采集其他候选。
- 独立复算确认10张历史表与原 ZIP 按截止筛选结果逐行一致；按文本保留全部邮编前导零，修复旧历史 CSV 的334个客户及75个商家邮编损失。
- 工作历史订单：9311；明细：15639；排除截止后订单：689。
- 观察订单视图：9311；观察评价视图：6096；未到创建时点评价排除：94。
- 实际日期留空计数：`{"orders.order_approved_at": 4, "orders.order_delivered_carrier_date": 28, "orders.order_delivered_customer_date": 94, "reviews.review_answer_timestamp": 7}`。日期窗左闭右开，以 `2026-11-08T00:00:00+00:00` 为排他端点；源无时区，UTC是工程假设。

## 可用边界

history_source 是忠实的下单截止重建层，仍包含期末状态和未来结果，不能整体当预测特征。observed 是有明确事件日期的最小视图，并不证明所有源字段的历史可得性。预计送达日期在未来不自动等于泄漏；本视图暂不开放它，等待确认生成时点。付款无时间字段，不能当已实现收入；物流最终结果、预置生命周期、期末客户/上架/商家标签暂不开放作预测特征。评分仅在评价创建时点可得是工程假设。

USD金额含义、无数量限制、暂不生成有效购买/复购真值见 source_manifest.json 的 policy，以及 D011。正式 contracts 仍为待切换的候选草案，尚不能用于本工作层的业务指标计算。

## 存储、复现与验证

- 数据目录：`data/processed/engineering/d50ee64a0478d8ae-20261108T000000Z-engineering-import-v1`。原始同哈希存档：`data/raw/archives/d50ee64a0478d8ae8df1b8b66521671a4911e19f911ae86196452a668f917a16.zip`。这两处均忽略Git；清单与实现代码提交私有远程，不能声称数据已远程同步。
- 命令：`.venv/bin/python src/retail_bi/data/ingest.py --source ../ecommerce-sample-database-100k/01_source/baseline_10000_seed42.zip --raw-root data/raw/archives --work-root data/processed/engineering --cutoff 2026-11-08T00:00:00Z --expected-sha256 d50ee64a0478d8ae8df1b8b66521671a4911e19f911ae86196452a668f917a16`
- 独立验证：`.venv/bin/python evidence/DATA-05/verify_import.py`，5组 PASS；全量逐行与标识比较、观察日期控制、幂等重跑、错误校验码/无时区截止/写回源目录/空范围/锁冲突/损坏输出拒绝、源未改。
- 每个工作文件的行数、列、字节数和SHA-256见 source_manifest.json；全部输出经文本回读核对。
- 目录锁不会自动夺取；异常中断留下锁时先核对真实作业与交接，再人工处理，不能通过超时强占。

## 下一步建议

先准备合成数据字段字典、有效购买/退款/金额与时间窗口的候选口径，明确缺少状态变更与付款时间造成的不可验证边界，再推进质量报告和数仓。与修改原目录相比，版本化工作层能兼顾复现、接力和回滚，本阶段采用此必要导入机制；未扩展业务功能。

## 补充：DATA-05 验收复核（2026-11-10，claude-opus-5-5）

- DATA-03 已冻结研究范围（截止前全部历史，D013），DATA-04 已批准契约 `synthetic-transaction-v1`。本次复核 Codex 的实现，没有改动 `ingest.py`。
- 实际重跑导入命令：退出码 0，命中已有版本目录，清单字节不变（幂等）；`verify_import.py` 5 组 PASS；新增 `evidence/DATA-05/verify_against_contract.py` 21/21 PASS（清单副本一致、源与存档哈希、12 个 ZIP 成员、10 张表行数与列对照契约、不读凭据、数据目录被 Git 忽略）。日志见 `evidence/DATA-05/review_run_2026-11-10_claude.log`。
- 来源版本与日期：生成器运行 `simulation_run_20260721_003414_baseline_seed42`（生成于 2026-07-21），源 ZIP SHA-256 `d50ee64a…7a16`，本地副本由 DATA-01 于 2026-11-09 与官网下载件逐文件比对一致。
- 清单中的 `status: engineering_verified_formal_approval_pending` 与 `policy.formal_gate` 是生成时的文字快照。修改它们需要提升导入版本并重建工作层，本次不做；当前批准状态以 `contracts/data_contract.json` 为准。上文“正式 contracts 仍为待切换的候选草案”同样是 2026-11-10 14:19 的快照。
