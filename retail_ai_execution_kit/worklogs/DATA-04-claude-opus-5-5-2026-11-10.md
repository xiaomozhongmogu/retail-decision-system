# DATA-04 交接（claude-opus-5-5）

## 2026-11-10 14:45 +08:00

- 执行者：claude-opus-5-5，协调执行，自审；认领时台账 `e666ddbb…`，完成后 `cf9889ef…`；Git 基线 `a8018de`。
- 本对话仍是协调者，接着复核 DATA-05；没有后台作业。

### 实际完成

| 动作 | 文件 | 证据 |
|---|---|---|
| 生成合成交易契约 `synthetic-transaction-v1`（approved，依据 DATA-03 与 D012/D013，非教师确认） | `contracts/data_contract.json` | `evidence/DATA-04/2026-11-10-contract.json` |
| 逐列数据字典（与契约同源生成，勿手改） | `docs/data_dictionary.md` | 同上 |
| 生成脚本 / 独立核对 | `evidence/DATA-04/build_contract.py`、`verify_contract.py` | `build_run.log`、`verification_run.log`（含 1 次核对脚本自身失败） |
| business_scope.md 改为 v2，删去路线 A | `docs/business_scope.md` | 同上，及 GOV-05 复核 |
| 契约与范围变化的影响复核 | — | `evidence/{GOV-05,GOV-06,DATA-01,DATA-03}/2026-11-10-data04-recheck.json` |

### 关键事实

- 10 张表 101 列；主键零重复、10 条外键零孤儿；9 项一致性检查全为 0（含：每单只有一个卖家；订单运费=明细运费合计；支付合计=明细合计）。
- **订单最终状态与时间戳严格对应**：cancelled=无审批，processing=已审批未交承运，shipped=已交承运未送达，delivered=已送达。as_of 时的非取消状态可以由时间戳重建；取消发生时间未知。这对 DATA-08 定义有效购买很关键。
- 有效业务字段 17 个，与 DATA-03 相同。

### 留给下游

- DATA-05：对照新契约复核现有导入，出新证据。
- DATA-08：有效购买是否含 processing/shipped，取消处理，金额是否含运费；改写 `contracts/metrics.json`（仍为 UCI 草案）。
- DW-01：`docs/architecture.md`、`contracts/interfaces.md` 仍保留路线 A/GBP 的历史描述，设计数仓时收窄（会触发 GOV-06/GOV-07 证据复核）。
- 注意：改 `contracts/data_contract.json`、`docs/business_scope.md`、`ops/DECISIONS.md` 都会使多项已完成任务的证据失效，需要审阅后重出。
