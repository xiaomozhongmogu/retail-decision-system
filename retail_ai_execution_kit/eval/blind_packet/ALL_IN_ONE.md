# 周报盲测材料（合并版，便于一次上传）

# 审查任务说明

你是一名独立的数据报告审查员。附件里有若干份电商经营周报（R01–R24）、每个场景的事实表（facts_*.json）和口径规则摘录（knowledge.md）。数据是完全合成的模拟数据。

请逐份检查每份周报，**只以事实表和口径规则为依据**，不要用常识或外部知识补充事实。检查项：

1. 每个数字是否能在对应事实表中找到，数值和单位是否一致（允许千分位和保留两位小数的格式差异）；
2. 时间窗口和对比期间是否与事实表一致；
3. 引用的 evidence_id 是否存在于事实表中，且对应的就是它所说的指标；
4. 是否有没有标“待验证”的因果结论；
5. 是否提到数据中没有的字段（以 knowledge.md 为准）；
6. 分母为 0、小样本、不完整周期是否被正确处理（不给出不可信的增长率，不与完整期间直接比较）；
7. 解释的语义是否与数字矛盾（例如数字下降却写成增长）。

对每份报告输出一行 JSON，不要输出其他内容：
`{"report": "R01", "publishable": true/false, "issues": [{"type": "数字|单位|窗口|引用|因果|不存在字段|特殊情况处理|语义", "quote": "报告原文片段", "evidence": "事实表中的依据或缺失说明", "severity": "高|中|低"}]}`

没有问题的报告输出 `"issues": []`。不确定时写入 issues，severity 写“低”，并在 evidence 中说明不确定的原因。

文件清单：knowledge.md、facts_S01.json 至 facts_S05.json、reports/R01.md 至 R24.md。


# 口径规则摘录（审查依据）

数据是完全合成的模拟电商数据，截止 2026-11-08（不含），金额单位 USD。

1. 有效购买 = 截止前已审批的订单（approved_ts < as_of）；已取消订单没有审批，不计入；下单到审批最长 24 小时，所以截止前最后一天的订单可能尚未审批，该日单独列出，不参与比较。（docs/transaction_rules.md §1–§2）
2. 商品金额 = 有效订单的商品金额，不含运费；运费单列。客单价 = 商品金额合计 ÷ 有效订单数，不对各期客单价取平均。（contracts/metrics.json）
3. 比较期间：环比 = 上一个 7 天；同比 = 52 周前的同星期；分母为 0 时比率为空并标 zero_denominator，基期订单少于 30 单时增长率不给出（small_sample）；不完整期间（partial_period / incomplete_period）不与完整期间直接比较。（AI-08 事实规则）
4. 数据中没有的字段：渠道与营销投放、毛利与成本、库存、优惠券、广告、浏览与加购、客户年龄与性别。涉及这些的分析或建议都没有依据。（docs/data_dictionary.md §4、docs/business_scope.md §4）
5. 原因推测必须标为“待验证”，数据只支持相关与分解，不支持因果结论。（docs/business_scope.md）

每份周报头部写明对应的事实表文件；周报中的每个数字都应能在该事实表中找到（允许千分位与两位小数的格式差异，比例以百分数显示）。


## facts_S01.json

```json
{
 "scenario_note": "完全合成的模拟数据；本文件是该场景周报唯一的数字依据",
 "periods": {
  "report_week": {
   "start": "2026-10-31",
   "end": "2026-11-07",
   "closed": "left"
  },
  "previous_week": {
   "start": "2026-10-24",
   "end": "2026-10-31",
   "closed": "left"
  },
  "same_week_last_year": {
   "start": "2025-11-01",
   "end": "2025-11-08",
   "closed": "left"
  },
  "open_tail": {
   "start": "2026-11-07",
   "end": "2026-11-08",
   "closed": "left"
  },
  "report_month": {
   "start": "2026-10-01",
   "end": "2026-11-01",
   "closed": "left"
  },
  "previous_month": {
   "start": "2026-09-01",
   "end": "2026-10-01",
   "closed": "left"
  },
  "same_month_last_year": {
   "start": "2025-10-01",
   "end": "2025-11-01",
   "closed": "left"
  }
 },
 "warnings": [
  {
   "code": "partial_period",
   "message": "2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比"
  },
  {
   "code": "partial_period",
   "message": "2026-11 为不完整月，月度比较使用 2026-10"
  }
 ],
 "facts": [
  {
   "evidence_id": "fact:ab7e9a82",
   "metric": "report_week.orders",
   "label": "有效订单",
   "value": 86,
   "unit": "count",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 86
  },
  {
   "evidence_id": "fact:a31927a7",
   "metric": "report_week.sales",
   "label": "商品金额",
   "value": 13306.01,
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 86
  },
  {
   "evidence_id": "fact:5145708c",
   "metric": "report_week.shipping",
   "label": "运费",
   "value": 1146.52,
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 86
  },
  {
   "evidence_id": "fact:afdd8b01",
   "metric": "report_week.aov",
   "label": "客单价",
   "value": 154.72,
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 86
  },
  {
   "evidence_id": "fact:5cc00ca8",
   "metric": "previous_week.orders",
   "label": "有效订单",
   "value": 63,
   "unit": "count",
   "window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 63
  },
  {
   "evidence_id": "fact:cb0d536f",
   "metric": "previous_week.sales",
   "label": "商品金额",
   "value": 9229.99,
   "unit": "USD",
   "window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 63
  },
  {
   "evidence_id": "fact:5654d982",
   "metric": "previous_week.shipping",
   "label": "运费",
   "value": 820.43,
   "unit": "USD",
   "window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 63
  },
  {
   "evidence_id": "fact:d0bd98df",
   "metric": "previous_week.aov",
   "label": "客单价",
   "value": 146.51,
   "unit": "USD",
   "window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 63
  },
  {
   "evidence_id": "fact:0d0e3430",
   "metric": "same_week_last_year.orders",
   "label": "有效订单",
   "value": 96,
   "unit": "count",
   "window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:26704d20",
   "metric": "same_week_last_year.sales",
   "label": "商品金额",
   "value": 13353.3,
   "unit": "USD",
   "window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:92c54205",
   "metric": "same_week_last_year.shipping",
   "label": "运费",
   "value": 1515.93,
   "unit": "USD",
   "window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:90e89ab1",
   "metric": "same_week_last_year.aov",
   "label": "客单价",
   "value": 139.1,
   "unit": "USD",
   "window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:0e8603be",
   "metric": "change_vs_previous_week.orders",
   "label": "有效订单环比变化率",
   "value": 0.3651,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 63
  },
  {
   "evidence_id": "fact:31cf2f70",
   "metric": "change_vs_previous_week.sales",
   "label": "商品金额环比变化率",
   "value": 0.4416,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 63
  },
  {
   "evidence_id": "fact:efdd31dc",
   "metric": "change_vs_previous_week.aov",
   "label": "客单价环比变化率",
   "value": 0.0561,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 63
  },
  {
   "evidence_id": "fact:b99bf8fb",
   "metric": "split_vs_previous_week",
   "label": "商品金额环比变化 = 订单数影响 + 客单价影响",
   "value": {
    "orders": 3468.17,
    "aov": 607.85
   },
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 63,
   "total_change": 4076.02
  },
  {
   "evidence_id": "fact:b6fbc9c2",
   "metric": "change_vs_same_week_last_year.orders",
   "label": "有效订单同比（52 周前同星期）变化率",
   "value": -0.1042,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:56489918",
   "metric": "change_vs_same_week_last_year.sales",
   "label": "商品金额同比（52 周前同星期）变化率",
   "value": -0.0035,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:7662b477",
   "metric": "change_vs_same_week_last_year.aov",
   "label": "客单价同比（52 周前同星期）变化率",
   "value": 0.1123,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:ff4f4365",
   "metric": "split_vs_same_week_last_year",
   "label": "商品金额同比（52 周前同星期）变化 = 订单数影响 + 客单价影响",
   "value": {
    "orders": -1466.27,
    "aov": 1418.98
   },
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96,
   "total_change": -47.29
  },
  {
   "evidence_id": "fact:a4d93360",
   "metric": "trailing_8w_mean.orders",
   "label": "前 8 周周均有效订单",
   "value": 65.5,
   "unit": "count",
   "window": {
    "start": "2026-09-05",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 524
  },
  {
   "evidence_id": "fact:083e6330",
   "metric": "report_week_z.orders",
   "label": "本周有效订单相对前 8 周的 z 值",
   "value": 1.4,
   "unit": "z-score",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-09-05",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 8
  },
  {
   "evidence_id": "fact:b9ed6ccc",
   "metric": "trailing_8w_mean.sales",
   "label": "前 8 周周均商品金额",
   "value": 9651.64,
   "unit": "USD",
   "window": {
    "start": "2026-09-05",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 524
  },
  {
   "evidence_id": "fact:f42e59c4",
   "metric": "report_week_z.sales",
   "label": "本周商品金额相对前 8 周的 z 值",
   "value": 2.07,
   "unit": "z-score",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-09-05",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 8
  },
  {
   "evidence_id": "fact:81a0bd95",
   "metric": "open_tail.orders",
   "label": "截止前最后一天的有效订单（审批未落定，不参与比较）",
   "value": 2,
   "unit": "count",
   "window": {
    "start": "2026-11-07",
    "end": "2026-11-08",
    "closed": "left"
   },
   "status": "partial_period",
   "sample_size": 2
  },
  {
   "evidence_id": "fact:609c663a",
   "metric": "report_month.orders",
   "label": "2026-10 有效订单",
   "value": 336,
   "unit": "count",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 336
  },
  {
   "evidence_id": "fact:e09fbf31",
   "metric": "report_month.buyers",
   "label": "2026-10 购买客户（月内去重）",
   "value": 326,
   "unit": "customers",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 326
  },
  {
   "evidence_id": "fact:fa543b7c",
   "metric": "report_month.sales",
   "label": "2026-10 商品金额",
   "value": 47590.59,
   "unit": "USD",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 336
  },
  {
   "evidence_id": "fact:edd7f2ca",
   "metric": "report_month.aov",
   "label": "2026-10 客单价",
   "value": 141.64,
   "unit": "USD",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 336
  },
  {
   "evidence_id": "fact:f9570b98",
   "metric": "report_month.orders_per_buyer",
   "label": "2026-10 人均订单",
   "value": 1.0307,
   "unit": "ratio",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 326
  },
  {
   "evidence_id": "fact:2204cf19",
   "metric": "previous_month.orders",
   "label": "2026-09 有效订单",
   "value": 240,
   "unit": "count",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 240
  },
  {
   "evidence_id": "fact:ce162a3d",
   "metric": "previous_month.buyers",
   "label": "2026-09 购买客户（月内去重）",
   "value": 232,
   "unit": "customers",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 232
  },
  {
   "evidence_id": "fact:972e8b52",
   "metric": "previous_month.sales",
   "label": "2026-09 商品金额",
   "value": 39190.7,
   "unit": "USD",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 240
  },
  {
   "evidence_id": "fact:8e0bbd3e",
   "metric": "previous_month.aov",
   "label": "2026-09 客单价",
   "value": 163.29,
   "unit": "USD",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 240
  },
  {
   "evidence_id": "fact:6d2bd630",
   "metric": "previous_month.orders_per_buyer",
   "label": "2026-09 人均订单",
   "value": 1.0345,
   "unit": "ratio",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 232
  },
  {
   "evidence_id": "fact:cb8678bd",
   "metric": "same_month_last_year.orders",
   "label": "2025-10 有效订单",
   "value": 329,
   "unit": "count",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 329
  },
  {
   "evidence_id": "fact:0109cf07",
   "metric": "same_month_last_year.buyers",
   "label": "2025-10 购买客户（月内去重）",
   "value": 321,
   "unit": "customers",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 321
  },
  {
   "evidence_id": "fact:997d5d67",
   "metric": "same_month_last_year.sales",
   "label": "2025-10 商品金额",
   "value": 49547.36,
   "unit": "USD",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 329
  },
  {
   "evidence_id": "fact:05a53592",
   "metric": "same_month_last_year.aov",
   "label": "2025-10 客单价",
   "value": 150.6,
   "unit": "USD",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 329
  },
  {
   "evidence_id": "fact:5e5c7010",
   "metric": "same_month_last_year.orders_per_buyer",
   "label": "2025-10 人均订单",
   "value": 1.0249,
   "unit": "ratio",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 321
  },
  {
   "evidence_id": "fact:6aaec672",
   "metric": "repurchase_rate_30d.latest_matured",
   "label": "最近已成熟的 30 天复购率（as_of 2026-10-05，标签窗到 2026-11-04）",
   "value": 0.112,
   "unit": "ratio",
   "window": {
    "start": "2026-10-05",
    "end": "2026-11-04",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 643
  }
 ]
}
```

## facts_S02.json

```json
{
 "scenario_note": "完全合成的模拟数据；本文件是该场景周报唯一的数字依据",
 "periods": {
  "report_week": {
   "start": "2026-10-31",
   "end": "2026-11-07",
   "closed": "left"
  },
  "previous_week": {
   "start": "2026-10-24",
   "end": "2026-10-31",
   "closed": "left"
  },
  "same_week_last_year": {
   "start": "2025-11-01",
   "end": "2025-11-08",
   "closed": "left"
  },
  "open_tail": {
   "start": "2026-11-07",
   "end": "2026-11-08",
   "closed": "left"
  },
  "report_month": {
   "start": "2026-10-01",
   "end": "2026-11-01",
   "closed": "left"
  },
  "previous_month": {
   "start": "2026-09-01",
   "end": "2026-10-01",
   "closed": "left"
  },
  "same_month_last_year": {
   "start": "2025-10-01",
   "end": "2025-11-01",
   "closed": "left"
  }
 },
 "warnings": [
  {
   "code": "partial_period",
   "message": "2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比"
  },
  {
   "code": "partial_period",
   "message": "2026-11 为不完整月，月度比较使用 2026-10"
  }
 ],
 "facts": [
  {
   "evidence_id": "fact:ab7e9a82",
   "metric": "report_week.orders",
   "label": "有效订单",
   "value": 49,
   "unit": "count",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 49
  },
  {
   "evidence_id": "fact:a31927a7",
   "metric": "report_week.sales",
   "label": "商品金额",
   "value": 7630.93,
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 49
  },
  {
   "evidence_id": "fact:5145708c",
   "metric": "report_week.shipping",
   "label": "运费",
   "value": 653.46,
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 49
  },
  {
   "evidence_id": "fact:afdd8b01",
   "metric": "report_week.aov",
   "label": "客单价",
   "value": 155.73,
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 49
  },
  {
   "evidence_id": "fact:5cc00ca8",
   "metric": "previous_week.orders",
   "label": "有效订单",
   "value": 63,
   "unit": "count",
   "window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 63
  },
  {
   "evidence_id": "fact:cb0d536f",
   "metric": "previous_week.sales",
   "label": "商品金额",
   "value": 9229.99,
   "unit": "USD",
   "window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 63
  },
  {
   "evidence_id": "fact:5654d982",
   "metric": "previous_week.shipping",
   "label": "运费",
   "value": 820.43,
   "unit": "USD",
   "window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 63
  },
  {
   "evidence_id": "fact:d0bd98df",
   "metric": "previous_week.aov",
   "label": "客单价",
   "value": 146.51,
   "unit": "USD",
   "window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 63
  },
  {
   "evidence_id": "fact:0d0e3430",
   "metric": "same_week_last_year.orders",
   "label": "有效订单",
   "value": 96,
   "unit": "count",
   "window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:26704d20",
   "metric": "same_week_last_year.sales",
   "label": "商品金额",
   "value": 13353.3,
   "unit": "USD",
   "window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:92c54205",
   "metric": "same_week_last_year.shipping",
   "label": "运费",
   "value": 1515.93,
   "unit": "USD",
   "window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:90e89ab1",
   "metric": "same_week_last_year.aov",
   "label": "客单价",
   "value": 139.1,
   "unit": "USD",
   "window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:0e8603be",
   "metric": "change_vs_previous_week.orders",
   "label": "有效订单环比变化率",
   "value": -0.2222,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 63
  },
  {
   "evidence_id": "fact:31cf2f70",
   "metric": "change_vs_previous_week.sales",
   "label": "商品金额环比变化率",
   "value": -0.1732,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 63
  },
  {
   "evidence_id": "fact:efdd31dc",
   "metric": "change_vs_previous_week.aov",
   "label": "客单价环比变化率",
   "value": 0.063,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 63
  },
  {
   "evidence_id": "fact:b99bf8fb",
   "metric": "split_vs_previous_week",
   "label": "商品金额环比变化 = 订单数影响 + 客单价影响",
   "value": {
    "orders": -2112.33,
    "aov": 513.27
   },
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 63,
   "total_change": -1599.06
  },
  {
   "evidence_id": "fact:b6fbc9c2",
   "metric": "change_vs_same_week_last_year.orders",
   "label": "有效订单同比（52 周前同星期）变化率",
   "value": -0.4896,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:56489918",
   "metric": "change_vs_same_week_last_year.sales",
   "label": "商品金额同比（52 周前同星期）变化率",
   "value": -0.4285,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:7662b477",
   "metric": "change_vs_same_week_last_year.aov",
   "label": "客单价同比（52 周前同星期）变化率",
   "value": 0.1196,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:ff4f4365",
   "metric": "split_vs_same_week_last_year",
   "label": "商品金额同比（52 周前同星期）变化 = 订单数影响 + 客单价影响",
   "value": {
    "orders": -6877.72,
    "aov": 1155.35
   },
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96,
   "total_change": -5722.37
  },
  {
   "evidence_id": "fact:a4d93360",
   "metric": "trailing_8w_mean.orders",
   "label": "前 8 周周均有效订单",
   "value": 65.5,
   "unit": "count",
   "window": {
    "start": "2026-09-05",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 524
  },
  {
   "evidence_id": "fact:083e6330",
   "metric": "report_week_z.orders",
   "label": "本周有效订单相对前 8 周的 z 值",
   "value": -1.13,
   "unit": "z-score",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-09-05",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 8
  },
  {
   "evidence_id": "fact:b9ed6ccc",
   "metric": "trailing_8w_mean.sales",
   "label": "前 8 周周均商品金额",
   "value": 9651.64,
   "unit": "USD",
   "window": {
    "start": "2026-09-05",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 524
  },
  {
   "evidence_id": "fact:f42e59c4",
   "metric": "report_week_z.sales",
   "label": "本周商品金额相对前 8 周的 z 值",
   "value": -1.15,
   "unit": "z-score",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-09-05",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 8
  },
  {
   "evidence_id": "fact:81a0bd95",
   "metric": "open_tail.orders",
   "label": "截止前最后一天的有效订单（审批未落定，不参与比较）",
   "value": 2,
   "unit": "count",
   "window": {
    "start": "2026-11-07",
    "end": "2026-11-08",
    "closed": "left"
   },
   "status": "partial_period",
   "sample_size": 2
  },
  {
   "evidence_id": "fact:609c663a",
   "metric": "report_month.orders",
   "label": "2026-10 有效订单",
   "value": 336,
   "unit": "count",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 336
  },
  {
   "evidence_id": "fact:e09fbf31",
   "metric": "report_month.buyers",
   "label": "2026-10 购买客户（月内去重）",
   "value": 326,
   "unit": "customers",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 326
  },
  {
   "evidence_id": "fact:fa543b7c",
   "metric": "report_month.sales",
   "label": "2026-10 商品金额",
   "value": 47590.59,
   "unit": "USD",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 336
  },
  {
   "evidence_id": "fact:edd7f2ca",
   "metric": "report_month.aov",
   "label": "2026-10 客单价",
   "value": 141.64,
   "unit": "USD",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 336
  },
  {
   "evidence_id": "fact:f9570b98",
   "metric": "report_month.orders_per_buyer",
   "label": "2026-10 人均订单",
   "value": 1.0307,
   "unit": "ratio",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 326
  },
  {
   "evidence_id": "fact:2204cf19",
   "metric": "previous_month.orders",
   "label": "2026-09 有效订单",
   "value": 240,
   "unit": "count",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 240
  },
  {
   "evidence_id": "fact:ce162a3d",
   "metric": "previous_month.buyers",
   "label": "2026-09 购买客户（月内去重）",
   "value": 232,
   "unit": "customers",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 232
  },
  {
   "evidence_id": "fact:972e8b52",
   "metric": "previous_month.sales",
   "label": "2026-09 商品金额",
   "value": 39190.7,
   "unit": "USD",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 240
  },
  {
   "evidence_id": "fact:8e0bbd3e",
   "metric": "previous_month.aov",
   "label": "2026-09 客单价",
   "value": 163.29,
   "unit": "USD",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 240
  },
  {
   "evidence_id": "fact:6d2bd630",
   "metric": "previous_month.orders_per_buyer",
   "label": "2026-09 人均订单",
   "value": 1.0345,
   "unit": "ratio",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 232
  },
  {
   "evidence_id": "fact:cb8678bd",
   "metric": "same_month_last_year.orders",
   "label": "2025-10 有效订单",
   "value": 329,
   "unit": "count",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 329
  },
  {
   "evidence_id": "fact:0109cf07",
   "metric": "same_month_last_year.buyers",
   "label": "2025-10 购买客户（月内去重）",
   "value": 321,
   "unit": "customers",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 321
  },
  {
   "evidence_id": "fact:997d5d67",
   "metric": "same_month_last_year.sales",
   "label": "2025-10 商品金额",
   "value": 49547.36,
   "unit": "USD",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 329
  },
  {
   "evidence_id": "fact:05a53592",
   "metric": "same_month_last_year.aov",
   "label": "2025-10 客单价",
   "value": 150.6,
   "unit": "USD",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 329
  },
  {
   "evidence_id": "fact:5e5c7010",
   "metric": "same_month_last_year.orders_per_buyer",
   "label": "2025-10 人均订单",
   "value": 1.0249,
   "unit": "ratio",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 321
  },
  {
   "evidence_id": "fact:6aaec672",
   "metric": "repurchase_rate_30d.latest_matured",
   "label": "最近已成熟的 30 天复购率（as_of 2026-10-05，标签窗到 2026-11-04）",
   "value": 0.112,
   "unit": "ratio",
   "window": {
    "start": "2026-10-05",
    "end": "2026-11-04",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 643
  }
 ]
}
```

## facts_S03.json

```json
{
 "scenario_note": "完全合成的模拟数据；本文件是该场景周报唯一的数字依据",
 "periods": {
  "report_week": {
   "start": "2026-10-31",
   "end": "2026-11-07",
   "closed": "left"
  },
  "previous_week": {
   "start": "2026-10-24",
   "end": "2026-10-31",
   "closed": "left"
  },
  "same_week_last_year": {
   "start": "2025-11-01",
   "end": "2025-11-08",
   "closed": "left"
  },
  "open_tail": {
   "start": "2026-11-07",
   "end": "2026-11-08",
   "closed": "left"
  },
  "report_month": {
   "start": "2026-10-01",
   "end": "2026-11-01",
   "closed": "left"
  },
  "previous_month": {
   "start": "2026-09-01",
   "end": "2026-10-01",
   "closed": "left"
  },
  "same_month_last_year": {
   "start": "2025-10-01",
   "end": "2025-11-01",
   "closed": "left"
  }
 },
 "warnings": [
  {
   "code": "partial_period",
   "message": "2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比"
  },
  {
   "code": "partial_period",
   "message": "2026-11 为不完整月，月度比较使用 2026-10"
  }
 ],
 "facts": [
  {
   "evidence_id": "fact:ab7e9a82",
   "metric": "report_week.orders",
   "label": "有效订单",
   "value": 86,
   "unit": "count",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 86
  },
  {
   "evidence_id": "fact:a31927a7",
   "metric": "report_week.sales",
   "label": "商品金额",
   "value": 13306.01,
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 86
  },
  {
   "evidence_id": "fact:5145708c",
   "metric": "report_week.shipping",
   "label": "运费",
   "value": 1146.52,
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 86
  },
  {
   "evidence_id": "fact:afdd8b01",
   "metric": "report_week.aov",
   "label": "客单价",
   "value": 154.72,
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 86
  },
  {
   "evidence_id": "fact:5cc00ca8",
   "metric": "previous_week.orders",
   "label": "有效订单",
   "value": 0,
   "unit": "count",
   "window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 0
  },
  {
   "evidence_id": "fact:cb0d536f",
   "metric": "previous_week.sales",
   "label": "商品金额",
   "value": 0.0,
   "unit": "USD",
   "window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 0
  },
  {
   "evidence_id": "fact:5654d982",
   "metric": "previous_week.shipping",
   "label": "运费",
   "value": 0.0,
   "unit": "USD",
   "window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 0
  },
  {
   "evidence_id": "fact:d0bd98df",
   "metric": "previous_week.aov",
   "label": "客单价",
   "value": null,
   "unit": "USD",
   "window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "zero_denominator",
   "sample_size": 0
  },
  {
   "evidence_id": "fact:0d0e3430",
   "metric": "same_week_last_year.orders",
   "label": "有效订单",
   "value": 96,
   "unit": "count",
   "window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:26704d20",
   "metric": "same_week_last_year.sales",
   "label": "商品金额",
   "value": 13353.3,
   "unit": "USD",
   "window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:92c54205",
   "metric": "same_week_last_year.shipping",
   "label": "运费",
   "value": 1515.93,
   "unit": "USD",
   "window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:90e89ab1",
   "metric": "same_week_last_year.aov",
   "label": "客单价",
   "value": 139.1,
   "unit": "USD",
   "window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:0e8603be",
   "metric": "change_vs_previous_week.orders",
   "label": "有效订单环比",
   "value": null,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "zero_denominator",
   "sample_size": 0
  },
  {
   "evidence_id": "fact:31cf2f70",
   "metric": "change_vs_previous_week.sales",
   "label": "商品金额环比",
   "value": null,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "zero_denominator",
   "sample_size": 0
  },
  {
   "evidence_id": "fact:efdd31dc",
   "metric": "change_vs_previous_week.aov",
   "label": "客单价环比",
   "value": null,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "zero_denominator",
   "sample_size": 0
  },
  {
   "evidence_id": "fact:b99bf8fb",
   "metric": "split_vs_previous_week",
   "label": "商品金额环比变化 = 订单数影响 + 客单价影响",
   "value": null,
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "zero_denominator",
   "sample_size": 0,
   "total_change": null
  },
  {
   "evidence_id": "fact:b6fbc9c2",
   "metric": "change_vs_same_week_last_year.orders",
   "label": "有效订单同比（52 周前同星期）变化率",
   "value": -0.1042,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:56489918",
   "metric": "change_vs_same_week_last_year.sales",
   "label": "商品金额同比（52 周前同星期）变化率",
   "value": -0.0035,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:7662b477",
   "metric": "change_vs_same_week_last_year.aov",
   "label": "客单价同比（52 周前同星期）变化率",
   "value": 0.1123,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96
  },
  {
   "evidence_id": "fact:ff4f4365",
   "metric": "split_vs_same_week_last_year",
   "label": "商品金额同比（52 周前同星期）变化 = 订单数影响 + 客单价影响",
   "value": {
    "orders": -1466.27,
    "aov": 1418.98
   },
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 96,
   "total_change": -47.29
  },
  {
   "evidence_id": "fact:a4d93360",
   "metric": "trailing_8w_mean.orders",
   "label": "前 8 周周均有效订单",
   "value": 57.62,
   "unit": "count",
   "window": {
    "start": "2026-09-05",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 461
  },
  {
   "evidence_id": "fact:083e6330",
   "metric": "report_week_z.orders",
   "label": "本周有效订单相对前 8 周的 z 值",
   "value": 1.03,
   "unit": "z-score",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-09-05",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 8
  },
  {
   "evidence_id": "fact:b9ed6ccc",
   "metric": "trailing_8w_mean.sales",
   "label": "前 8 周周均商品金额",
   "value": 8497.89,
   "unit": "USD",
   "window": {
    "start": "2026-09-05",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 461
  },
  {
   "evidence_id": "fact:f42e59c4",
   "metric": "report_week_z.sales",
   "label": "本周商品金额相对前 8 周的 z 值",
   "value": 1.25,
   "unit": "z-score",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-09-05",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 8
  },
  {
   "evidence_id": "fact:81a0bd95",
   "metric": "open_tail.orders",
   "label": "截止前最后一天的有效订单（审批未落定，不参与比较）",
   "value": 2,
   "unit": "count",
   "window": {
    "start": "2026-11-07",
    "end": "2026-11-08",
    "closed": "left"
   },
   "status": "partial_period",
   "sample_size": 2
  },
  {
   "evidence_id": "fact:609c663a",
   "metric": "report_month.orders",
   "label": "2026-10 有效订单",
   "value": 336,
   "unit": "count",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 336
  },
  {
   "evidence_id": "fact:e09fbf31",
   "metric": "report_month.buyers",
   "label": "2026-10 购买客户（月内去重）",
   "value": 326,
   "unit": "customers",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 326
  },
  {
   "evidence_id": "fact:fa543b7c",
   "metric": "report_month.sales",
   "label": "2026-10 商品金额",
   "value": 47590.59,
   "unit": "USD",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 336
  },
  {
   "evidence_id": "fact:edd7f2ca",
   "metric": "report_month.aov",
   "label": "2026-10 客单价",
   "value": 141.64,
   "unit": "USD",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 336
  },
  {
   "evidence_id": "fact:f9570b98",
   "metric": "report_month.orders_per_buyer",
   "label": "2026-10 人均订单",
   "value": 1.0307,
   "unit": "ratio",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 326
  },
  {
   "evidence_id": "fact:2204cf19",
   "metric": "previous_month.orders",
   "label": "2026-09 有效订单",
   "value": 240,
   "unit": "count",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 240
  },
  {
   "evidence_id": "fact:ce162a3d",
   "metric": "previous_month.buyers",
   "label": "2026-09 购买客户（月内去重）",
   "value": 232,
   "unit": "customers",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 232
  },
  {
   "evidence_id": "fact:972e8b52",
   "metric": "previous_month.sales",
   "label": "2026-09 商品金额",
   "value": 39190.7,
   "unit": "USD",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 240
  },
  {
   "evidence_id": "fact:8e0bbd3e",
   "metric": "previous_month.aov",
   "label": "2026-09 客单价",
   "value": 163.29,
   "unit": "USD",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 240
  },
  {
   "evidence_id": "fact:6d2bd630",
   "metric": "previous_month.orders_per_buyer",
   "label": "2026-09 人均订单",
   "value": 1.0345,
   "unit": "ratio",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 232
  },
  {
   "evidence_id": "fact:cb8678bd",
   "metric": "same_month_last_year.orders",
   "label": "2025-10 有效订单",
   "value": 329,
   "unit": "count",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 329
  },
  {
   "evidence_id": "fact:0109cf07",
   "metric": "same_month_last_year.buyers",
   "label": "2025-10 购买客户（月内去重）",
   "value": 321,
   "unit": "customers",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 321
  },
  {
   "evidence_id": "fact:997d5d67",
   "metric": "same_month_last_year.sales",
   "label": "2025-10 商品金额",
   "value": 49547.36,
   "unit": "USD",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 329
  },
  {
   "evidence_id": "fact:05a53592",
   "metric": "same_month_last_year.aov",
   "label": "2025-10 客单价",
   "value": 150.6,
   "unit": "USD",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 329
  },
  {
   "evidence_id": "fact:5e5c7010",
   "metric": "same_month_last_year.orders_per_buyer",
   "label": "2025-10 人均订单",
   "value": 1.0249,
   "unit": "ratio",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 321
  },
  {
   "evidence_id": "fact:6aaec672",
   "metric": "repurchase_rate_30d.latest_matured",
   "label": "最近已成熟的 30 天复购率（as_of 2026-10-05，标签窗到 2026-11-04）",
   "value": 0.112,
   "unit": "ratio",
   "window": {
    "start": "2026-10-05",
    "end": "2026-11-04",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 643
  }
 ]
}
```

## facts_S04.json

```json
{
 "scenario_note": "完全合成的模拟数据；本文件是该场景周报唯一的数字依据",
 "periods": {
  "report_week": {
   "start": "2026-10-31",
   "end": "2026-11-07",
   "closed": "left"
  },
  "previous_week": {
   "start": "2026-10-24",
   "end": "2026-10-31",
   "closed": "left"
  },
  "same_week_last_year": {
   "start": "2025-11-01",
   "end": "2025-11-08",
   "closed": "left"
  },
  "open_tail": {
   "start": "2026-11-07",
   "end": "2026-11-08",
   "closed": "left"
  },
  "report_month": {
   "start": "2026-10-01",
   "end": "2026-11-01",
   "closed": "left"
  },
  "previous_month": {
   "start": "2026-09-01",
   "end": "2026-10-01",
   "closed": "left"
  },
  "same_month_last_year": {
   "start": "2025-10-01",
   "end": "2025-11-01",
   "closed": "left"
  }
 },
 "warnings": [
  {
   "code": "partial_period",
   "message": "2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比"
  },
  {
   "code": "partial_period",
   "message": "2026-11 为不完整月，月度比较使用 2026-10"
  }
 ],
 "facts": [
  {
   "evidence_id": "fact:ab7e9a82",
   "metric": "report_week.orders",
   "label": "有效订单",
   "value": 14,
   "unit": "count",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 14
  },
  {
   "evidence_id": "fact:a31927a7",
   "metric": "report_week.sales",
   "label": "商品金额",
   "value": 2212.36,
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 14
  },
  {
   "evidence_id": "fact:5145708c",
   "metric": "report_week.shipping",
   "label": "运费",
   "value": 185.36,
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 14
  },
  {
   "evidence_id": "fact:afdd8b01",
   "metric": "report_week.aov",
   "label": "客单价",
   "value": 158.03,
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 14
  },
  {
   "evidence_id": "fact:5cc00ca8",
   "metric": "previous_week.orders",
   "label": "有效订单",
   "value": 9,
   "unit": "count",
   "window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 9
  },
  {
   "evidence_id": "fact:cb0d536f",
   "metric": "previous_week.sales",
   "label": "商品金额",
   "value": 1280.19,
   "unit": "USD",
   "window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 9
  },
  {
   "evidence_id": "fact:5654d982",
   "metric": "previous_week.shipping",
   "label": "运费",
   "value": 115.55,
   "unit": "USD",
   "window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 9
  },
  {
   "evidence_id": "fact:d0bd98df",
   "metric": "previous_week.aov",
   "label": "客单价",
   "value": 142.24,
   "unit": "USD",
   "window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 9
  },
  {
   "evidence_id": "fact:0d0e3430",
   "metric": "same_week_last_year.orders",
   "label": "有效订单",
   "value": 14,
   "unit": "count",
   "window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 14
  },
  {
   "evidence_id": "fact:26704d20",
   "metric": "same_week_last_year.sales",
   "label": "商品金额",
   "value": 2014.86,
   "unit": "USD",
   "window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 14
  },
  {
   "evidence_id": "fact:92c54205",
   "metric": "same_week_last_year.shipping",
   "label": "运费",
   "value": 223.76,
   "unit": "USD",
   "window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 14
  },
  {
   "evidence_id": "fact:90e89ab1",
   "metric": "same_week_last_year.aov",
   "label": "客单价",
   "value": 143.92,
   "unit": "USD",
   "window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 14
  },
  {
   "evidence_id": "fact:0e8603be",
   "metric": "change_vs_previous_week.orders",
   "label": "有效订单环比变化率",
   "value": null,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "small_sample",
   "sample_size": 9
  },
  {
   "evidence_id": "fact:31cf2f70",
   "metric": "change_vs_previous_week.sales",
   "label": "商品金额环比变化率",
   "value": null,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "small_sample",
   "sample_size": 9
  },
  {
   "evidence_id": "fact:efdd31dc",
   "metric": "change_vs_previous_week.aov",
   "label": "客单价环比变化率",
   "value": null,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "small_sample",
   "sample_size": 9
  },
  {
   "evidence_id": "fact:b99bf8fb",
   "metric": "split_vs_previous_week",
   "label": "商品金额环比变化 = 订单数影响 + 客单价影响",
   "value": {
    "orders": 752.88,
    "aov": 179.29
   },
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-10-24",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 9,
   "total_change": 932.17
  },
  {
   "evidence_id": "fact:b6fbc9c2",
   "metric": "change_vs_same_week_last_year.orders",
   "label": "有效订单同比（52 周前同星期）变化率",
   "value": null,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "small_sample",
   "sample_size": 14
  },
  {
   "evidence_id": "fact:56489918",
   "metric": "change_vs_same_week_last_year.sales",
   "label": "商品金额同比（52 周前同星期）变化率",
   "value": null,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "small_sample",
   "sample_size": 14
  },
  {
   "evidence_id": "fact:7662b477",
   "metric": "change_vs_same_week_last_year.aov",
   "label": "客单价同比（52 周前同星期）变化率",
   "value": null,
   "unit": "ratio",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "small_sample",
   "sample_size": 14
  },
  {
   "evidence_id": "fact:ff4f4365",
   "metric": "split_vs_same_week_last_year",
   "label": "商品金额同比（52 周前同星期）变化 = 订单数影响 + 客单价影响",
   "value": {
    "orders": 0.0,
    "aov": 197.5
   },
   "unit": "USD",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-11-01",
    "end": "2025-11-08",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 14,
   "total_change": 197.5
  },
  {
   "evidence_id": "fact:a4d93360",
   "metric": "trailing_8w_mean.orders",
   "label": "前 8 周周均有效订单",
   "value": 9.75,
   "unit": "count",
   "window": {
    "start": "2026-09-05",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 78
  },
  {
   "evidence_id": "fact:083e6330",
   "metric": "report_week_z.orders",
   "label": "本周有效订单相对前 8 周的 z 值",
   "value": 1.63,
   "unit": "z-score",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-09-05",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 8
  },
  {
   "evidence_id": "fact:b9ed6ccc",
   "metric": "trailing_8w_mean.sales",
   "label": "前 8 周周均商品金额",
   "value": 1440.64,
   "unit": "USD",
   "window": {
    "start": "2026-09-05",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 78
  },
  {
   "evidence_id": "fact:f42e59c4",
   "metric": "report_week_z.sales",
   "label": "本周商品金额相对前 8 周的 z 值",
   "value": 2.32,
   "unit": "z-score",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-07",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-09-05",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 8
  },
  {
   "evidence_id": "fact:6a5ddee7",
   "metric": "daily_z.sales.2026-10-31",
   "label": "2026-10-31 日商品金额的稳健 z 值",
   "value": 3.07,
   "unit": "z-score",
   "window": {
    "start": "2026-10-31",
    "end": "2026-11-01",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-09-05",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 56
  },
  {
   "evidence_id": "fact:f9ea56c1",
   "metric": "daily_z.sales.2026-11-03",
   "label": "2026-11-03 日商品金额的稳健 z 值",
   "value": 3.7,
   "unit": "z-score",
   "window": {
    "start": "2026-11-03",
    "end": "2026-11-04",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-09-05",
    "end": "2026-10-31",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 56
  },
  {
   "evidence_id": "fact:81a0bd95",
   "metric": "open_tail.orders",
   "label": "截止前最后一天的有效订单（审批未落定，不参与比较）",
   "value": 0,
   "unit": "count",
   "window": {
    "start": "2026-11-07",
    "end": "2026-11-08",
    "closed": "left"
   },
   "status": "partial_period",
   "sample_size": 0
  },
  {
   "evidence_id": "fact:609c663a",
   "metric": "report_month.orders",
   "label": "2026-10 有效订单",
   "value": 336,
   "unit": "count",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 336
  },
  {
   "evidence_id": "fact:e09fbf31",
   "metric": "report_month.buyers",
   "label": "2026-10 购买客户（月内去重）",
   "value": 326,
   "unit": "customers",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 326
  },
  {
   "evidence_id": "fact:fa543b7c",
   "metric": "report_month.sales",
   "label": "2026-10 商品金额",
   "value": 47590.59,
   "unit": "USD",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 336
  },
  {
   "evidence_id": "fact:edd7f2ca",
   "metric": "report_month.aov",
   "label": "2026-10 客单价",
   "value": 141.64,
   "unit": "USD",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 336
  },
  {
   "evidence_id": "fact:f9570b98",
   "metric": "report_month.orders_per_buyer",
   "label": "2026-10 人均订单",
   "value": 1.0307,
   "unit": "ratio",
   "window": {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 326
  },
  {
   "evidence_id": "fact:2204cf19",
   "metric": "previous_month.orders",
   "label": "2026-09 有效订单",
   "value": 240,
   "unit": "count",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 240
  },
  {
   "evidence_id": "fact:ce162a3d",
   "metric": "previous_month.buyers",
   "label": "2026-09 购买客户（月内去重）",
   "value": 232,
   "unit": "customers",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 232
  },
  {
   "evidence_id": "fact:972e8b52",
   "metric": "previous_month.sales",
   "label": "2026-09 商品金额",
   "value": 39190.7,
   "unit": "USD",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 240
  },
  {
   "evidence_id": "fact:8e0bbd3e",
   "metric": "previous_month.aov",
   "label": "2026-09 客单价",
   "value": 163.29,
   "unit": "USD",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 240
  },
  {
   "evidence_id": "fact:6d2bd630",
   "metric": "previous_month.orders_per_buyer",
   "label": "2026-09 人均订单",
   "value": 1.0345,
   "unit": "ratio",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 232
  },
  {
   "evidence_id": "fact:cb8678bd",
   "metric": "same_month_last_year.orders",
   "label": "2025-10 有效订单",
   "value": 329,
   "unit": "count",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 329
  },
  {
   "evidence_id": "fact:0109cf07",
   "metric": "same_month_last_year.buyers",
   "label": "2025-10 购买客户（月内去重）",
   "value": 321,
   "unit": "customers",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 321
  },
  {
   "evidence_id": "fact:997d5d67",
   "metric": "same_month_last_year.sales",
   "label": "2025-10 商品金额",
   "value": 49547.36,
   "unit": "USD",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 329
  },
  {
   "evidence_id": "fact:05a53592",
   "metric": "same_month_last_year.aov",
   "label": "2025-10 客单价",
   "value": 150.6,
   "unit": "USD",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 329
  },
  {
   "evidence_id": "fact:5e5c7010",
   "metric": "same_month_last_year.orders_per_buyer",
   "label": "2025-10 人均订单",
   "value": 1.0249,
   "unit": "ratio",
   "window": {
    "start": "2025-10-01",
    "end": "2025-11-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 321
  },
  {
   "evidence_id": "fact:6aaec672",
   "metric": "repurchase_rate_30d.latest_matured",
   "label": "最近已成熟的 30 天复购率（as_of 2026-10-05，标签窗到 2026-11-04）",
   "value": 0.112,
   "unit": "ratio",
   "window": {
    "start": "2026-10-05",
    "end": "2026-11-04",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 643
  }
 ]
}
```

## facts_S05.json

```json
{
 "scenario_note": "完全合成的模拟数据；本文件是该场景周报唯一的数字依据",
 "periods": {
  "report_week": {
   "start": "2026-10-07",
   "end": "2026-10-14",
   "closed": "left"
  },
  "previous_week": {
   "start": "2026-09-30",
   "end": "2026-10-07",
   "closed": "left"
  },
  "same_week_last_year": {
   "start": "2025-10-08",
   "end": "2025-10-15",
   "closed": "left"
  },
  "open_tail": {
   "start": "2026-10-14",
   "end": "2026-10-15",
   "closed": "left"
  },
  "report_month": {
   "start": "2026-09-01",
   "end": "2026-10-01",
   "closed": "left"
  },
  "previous_month": {
   "start": "2026-08-01",
   "end": "2026-09-01",
   "closed": "left"
  },
  "same_month_last_year": {
   "start": "2025-09-01",
   "end": "2025-10-01",
   "closed": "left"
  }
 },
 "warnings": [
  {
   "code": "partial_period",
   "message": "2026-10-14 当天的订单可能尚未审批，只单独列出，不参与环比/同比"
  },
  {
   "code": "partial_period",
   "message": "2026-10 为不完整月，月度比较使用 2026-09"
  }
 ],
 "facts": [
  {
   "evidence_id": "fact:ba2f2da2",
   "metric": "report_week.orders",
   "label": "有效订单",
   "value": 86,
   "unit": "count",
   "window": {
    "start": "2026-10-07",
    "end": "2026-10-14",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 86
  },
  {
   "evidence_id": "fact:b7638db0",
   "metric": "report_week.sales",
   "label": "商品金额",
   "value": 11473.34,
   "unit": "USD",
   "window": {
    "start": "2026-10-07",
    "end": "2026-10-14",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 86
  },
  {
   "evidence_id": "fact:d0db30df",
   "metric": "report_week.shipping",
   "label": "运费",
   "value": 1123.73,
   "unit": "USD",
   "window": {
    "start": "2026-10-07",
    "end": "2026-10-14",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 86
  },
  {
   "evidence_id": "fact:7e562fce",
   "metric": "report_week.aov",
   "label": "客单价",
   "value": 133.41,
   "unit": "USD",
   "window": {
    "start": "2026-10-07",
    "end": "2026-10-14",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 86
  },
  {
   "evidence_id": "fact:85340cb6",
   "metric": "previous_week.orders",
   "label": "有效订单",
   "value": 69,
   "unit": "count",
   "window": {
    "start": "2026-09-30",
    "end": "2026-10-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 69
  },
  {
   "evidence_id": "fact:ca8b65be",
   "metric": "previous_week.sales",
   "label": "商品金额",
   "value": 8972.21,
   "unit": "USD",
   "window": {
    "start": "2026-09-30",
    "end": "2026-10-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 69
  },
  {
   "evidence_id": "fact:e82624ba",
   "metric": "previous_week.shipping",
   "label": "运费",
   "value": 1007.93,
   "unit": "USD",
   "window": {
    "start": "2026-09-30",
    "end": "2026-10-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 69
  },
  {
   "evidence_id": "fact:45473df6",
   "metric": "previous_week.aov",
   "label": "客单价",
   "value": 130.03,
   "unit": "USD",
   "window": {
    "start": "2026-09-30",
    "end": "2026-10-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 69
  },
  {
   "evidence_id": "fact:ad875cfc",
   "metric": "same_week_last_year.orders",
   "label": "有效订单",
   "value": 67,
   "unit": "count",
   "window": {
    "start": "2025-10-08",
    "end": "2025-10-15",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 67
  },
  {
   "evidence_id": "fact:f31c255e",
   "metric": "same_week_last_year.sales",
   "label": "商品金额",
   "value": 11760.55,
   "unit": "USD",
   "window": {
    "start": "2025-10-08",
    "end": "2025-10-15",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 67
  },
  {
   "evidence_id": "fact:59865e85",
   "metric": "same_week_last_year.shipping",
   "label": "运费",
   "value": 980.61,
   "unit": "USD",
   "window": {
    "start": "2025-10-08",
    "end": "2025-10-15",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 67
  },
  {
   "evidence_id": "fact:9f2a1d34",
   "metric": "same_week_last_year.aov",
   "label": "客单价",
   "value": 175.53,
   "unit": "USD",
   "window": {
    "start": "2025-10-08",
    "end": "2025-10-15",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 67
  },
  {
   "evidence_id": "fact:b7f5e679",
   "metric": "change_vs_previous_week.orders",
   "label": "有效订单环比变化率",
   "value": 0.2464,
   "unit": "ratio",
   "window": {
    "start": "2026-10-07",
    "end": "2026-10-14",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-09-30",
    "end": "2026-10-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 69
  },
  {
   "evidence_id": "fact:3bfbd078",
   "metric": "change_vs_previous_week.sales",
   "label": "商品金额环比变化率",
   "value": 0.2788,
   "unit": "ratio",
   "window": {
    "start": "2026-10-07",
    "end": "2026-10-14",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-09-30",
    "end": "2026-10-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 69
  },
  {
   "evidence_id": "fact:16967e2b",
   "metric": "change_vs_previous_week.aov",
   "label": "客单价环比变化率",
   "value": 0.026,
   "unit": "ratio",
   "window": {
    "start": "2026-10-07",
    "end": "2026-10-14",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-09-30",
    "end": "2026-10-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 69
  },
  {
   "evidence_id": "fact:327ecb58",
   "metric": "split_vs_previous_week",
   "label": "商品金额环比变化 = 订单数影响 + 客单价影响",
   "value": {
    "orders": 2240.2,
    "aov": 260.93
   },
   "unit": "USD",
   "window": {
    "start": "2026-10-07",
    "end": "2026-10-14",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-09-30",
    "end": "2026-10-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 69,
   "total_change": 2501.13
  },
  {
   "evidence_id": "fact:d4f22c80",
   "metric": "change_vs_same_week_last_year.orders",
   "label": "有效订单同比（52 周前同星期）变化率",
   "value": 0.2836,
   "unit": "ratio",
   "window": {
    "start": "2026-10-07",
    "end": "2026-10-14",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-10-08",
    "end": "2025-10-15",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 67
  },
  {
   "evidence_id": "fact:c20c4db9",
   "metric": "change_vs_same_week_last_year.sales",
   "label": "商品金额同比（52 周前同星期）变化率",
   "value": -0.0244,
   "unit": "ratio",
   "window": {
    "start": "2026-10-07",
    "end": "2026-10-14",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-10-08",
    "end": "2025-10-15",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 67
  },
  {
   "evidence_id": "fact:6ab5fea8",
   "metric": "change_vs_same_week_last_year.aov",
   "label": "客单价同比（52 周前同星期）变化率",
   "value": -0.24,
   "unit": "ratio",
   "window": {
    "start": "2026-10-07",
    "end": "2026-10-14",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-10-08",
    "end": "2025-10-15",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 67
  },
  {
   "evidence_id": "fact:ac54dede",
   "metric": "split_vs_same_week_last_year",
   "label": "商品金额同比（52 周前同星期）变化 = 订单数影响 + 客单价影响",
   "value": {
    "orders": 2900.08,
    "aov": -3187.29
   },
   "unit": "USD",
   "window": {
    "start": "2026-10-07",
    "end": "2026-10-14",
    "closed": "left"
   },
   "compare_window": {
    "start": "2025-10-08",
    "end": "2025-10-15",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 67,
   "total_change": -287.21
  },
  {
   "evidence_id": "fact:a9350cc3",
   "metric": "trailing_8w_mean.orders",
   "label": "前 8 周周均有效订单",
   "value": 57.75,
   "unit": "count",
   "window": {
    "start": "2026-08-12",
    "end": "2026-10-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 462
  },
  {
   "evidence_id": "fact:598b70aa",
   "metric": "report_week_z.orders",
   "label": "本周有效订单相对前 8 周的 z 值",
   "value": 3.37,
   "unit": "z-score",
   "window": {
    "start": "2026-10-07",
    "end": "2026-10-14",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-08-12",
    "end": "2026-10-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 8
  },
  {
   "evidence_id": "fact:784f6214",
   "metric": "trailing_8w_mean.sales",
   "label": "前 8 周周均商品金额",
   "value": 9037.8,
   "unit": "USD",
   "window": {
    "start": "2026-08-12",
    "end": "2026-10-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 462
  },
  {
   "evidence_id": "fact:9214f30f",
   "metric": "report_week_z.sales",
   "label": "本周商品金额相对前 8 周的 z 值",
   "value": 1.89,
   "unit": "z-score",
   "window": {
    "start": "2026-10-07",
    "end": "2026-10-14",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-08-12",
    "end": "2026-10-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 8
  },
  {
   "evidence_id": "fact:904656b1",
   "metric": "daily_z.orders.2026-10-10",
   "label": "2026-10-10 日有效订单的稳健 z 值",
   "value": 4.05,
   "unit": "z-score",
   "window": {
    "start": "2026-10-10",
    "end": "2026-10-11",
    "closed": "left"
   },
   "compare_window": {
    "start": "2026-08-12",
    "end": "2026-10-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 56
  },
  {
   "evidence_id": "fact:350a8f86",
   "metric": "open_tail.orders",
   "label": "截止前最后一天的有效订单（审批未落定，不参与比较）",
   "value": 15,
   "unit": "count",
   "window": {
    "start": "2026-10-14",
    "end": "2026-10-15",
    "closed": "left"
   },
   "status": "partial_period",
   "sample_size": 15
  },
  {
   "evidence_id": "fact:630cbbff",
   "metric": "report_month.orders",
   "label": "2026-09 有效订单",
   "value": 240,
   "unit": "count",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 240
  },
  {
   "evidence_id": "fact:81ba9d34",
   "metric": "report_month.buyers",
   "label": "2026-09 购买客户（月内去重）",
   "value": 232,
   "unit": "customers",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 232
  },
  {
   "evidence_id": "fact:108298a0",
   "metric": "report_month.sales",
   "label": "2026-09 商品金额",
   "value": 39190.7,
   "unit": "USD",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 240
  },
  {
   "evidence_id": "fact:e4130e40",
   "metric": "report_month.aov",
   "label": "2026-09 客单价",
   "value": 163.29,
   "unit": "USD",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 240
  },
  {
   "evidence_id": "fact:2968538a",
   "metric": "report_month.orders_per_buyer",
   "label": "2026-09 人均订单",
   "value": 1.0345,
   "unit": "ratio",
   "window": {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 232
  },
  {
   "evidence_id": "fact:abecf087",
   "metric": "previous_month.orders",
   "label": "2026-08 有效订单",
   "value": 243,
   "unit": "count",
   "window": {
    "start": "2026-08-01",
    "end": "2026-09-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 243
  },
  {
   "evidence_id": "fact:76c42a19",
   "metric": "previous_month.buyers",
   "label": "2026-08 购买客户（月内去重）",
   "value": 233,
   "unit": "customers",
   "window": {
    "start": "2026-08-01",
    "end": "2026-09-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 233
  },
  {
   "evidence_id": "fact:c4aecfe1",
   "metric": "previous_month.sales",
   "label": "2026-08 商品金额",
   "value": 37247.83,
   "unit": "USD",
   "window": {
    "start": "2026-08-01",
    "end": "2026-09-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 243
  },
  {
   "evidence_id": "fact:3b33f8e8",
   "metric": "previous_month.aov",
   "label": "2026-08 客单价",
   "value": 153.28,
   "unit": "USD",
   "window": {
    "start": "2026-08-01",
    "end": "2026-09-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 243
  },
  {
   "evidence_id": "fact:ccefd6cf",
   "metric": "previous_month.orders_per_buyer",
   "label": "2026-08 人均订单",
   "value": 1.0429,
   "unit": "ratio",
   "window": {
    "start": "2026-08-01",
    "end": "2026-09-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 233
  },
  {
   "evidence_id": "fact:3e8f3f8b",
   "metric": "same_month_last_year.orders",
   "label": "2025-09 有效订单",
   "value": 233,
   "unit": "count",
   "window": {
    "start": "2025-09-01",
    "end": "2025-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 233
  },
  {
   "evidence_id": "fact:f4a3e6f9",
   "metric": "same_month_last_year.buyers",
   "label": "2025-09 购买客户（月内去重）",
   "value": 227,
   "unit": "customers",
   "window": {
    "start": "2025-09-01",
    "end": "2025-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 227
  },
  {
   "evidence_id": "fact:568d671f",
   "metric": "same_month_last_year.sales",
   "label": "2025-09 商品金额",
   "value": 34936.66,
   "unit": "USD",
   "window": {
    "start": "2025-09-01",
    "end": "2025-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 233
  },
  {
   "evidence_id": "fact:8deb7135",
   "metric": "same_month_last_year.aov",
   "label": "2025-09 客单价",
   "value": 149.94,
   "unit": "USD",
   "window": {
    "start": "2025-09-01",
    "end": "2025-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 233
  },
  {
   "evidence_id": "fact:afef6c8e",
   "metric": "same_month_last_year.orders_per_buyer",
   "label": "2025-09 人均订单",
   "value": 1.0264,
   "unit": "ratio",
   "window": {
    "start": "2025-09-01",
    "end": "2025-10-01",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 227
  },
  {
   "evidence_id": "fact:98941ecb",
   "metric": "repurchase_rate_30d.latest_matured",
   "label": "最近已成熟的 30 天复购率（as_of 2026-09-07，标签窗到 2026-10-07）",
   "value": 0.0852,
   "unit": "ratio",
   "window": {
    "start": "2026-09-07",
    "end": "2026-10-07",
    "closed": "left"
   },
   "status": "ok",
   "sample_size": 657
  }
 ]
}
```

## 周报 R01

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S01.json
- 数据：src=synthetic;rel=wh-d3aaa559048c，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 13,306.01 元 | `fact:a31927a7` |
| 本周有效订单 | 86 | `fact:ab7e9a82` |
| 本周客单价 | 154.72 USD | `fact:afdd8b01` |
| 商品金额环比 | +44.2% | `fact:31cf2f70` |
| 订单环比 | +36.5% | `fact:0e8603be` |
| 客单价环比 | +5.6% | `fact:efdd31dc` |
| 商品金额同比（去年同期同星期） | -0.4% | `fact:56489918` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | 2.07 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 2 | `fact:81a0bd95` |
| 环比金额变化中订单数的影响 | 3,468.17 USD | `fact:b99bf8fb` |
| 环比金额变化中客单价的影响 | 607.85 USD | `fact:b99bf8fb` |

## 解释

本周商品金额为 13,306.01 USD，有效订单为 86，客单价为 154.72 USD。口径上，有效购买按已审批订单计，金额与订单数均按下单时间归属到报告周；报告周为完整可比的一周，环比对比上一周，同比对比去年同期的同星期。商品金额环比为 +44.2%，订单环比为 +36.5%，客单价环比为 +5.6%；商品金额同比为 -0.4%。本周商品金额相对近期周基线的 z 值为 2.07。截止前最后一天的有效订单为 2，该日审批尚未落定，单独列出且不参与比较。

## 行动建议

- 对本周商品金额与订单数的环比变化做拆解复核，分别核对订单数影响与客单价影响的口径是否与审批落定时间一致。
- 对本周商品金额相对近期周基线的偏离，按商品品类与客户地区做下钻，定位偏离集中在哪些品类和地区。
- 将截止前最后一天的单列数据在审批落定后重新核对，确认其不并入报告周比较。

## 待验证假设

- 待验证：本周商品金额环比变化中，订单数影响 3,468.17 USD 与客单价影响 607.85 USD 的相对大小，可能反映订单量变化与单笔金额变化的不同贡献。
- 待验证：本周商品金额相对近期周基线的偏离，可能集中在少数商品品类或客户地区。
- 待验证：本周客单价的变化可能与订单在品类间的构成变化有关。

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:31cf2f70, fact:0e8603be, fact:efdd31dc, fact:56489918, fact:f42e59c4, fact:81a0bd95, fact:b99bf8fb

## 周报 R02

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S02.json
- 数据：src=synthetic;rel=wh-d3aaa559048c;scenario=S02，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 7,630.93 USD | `fact:a31927a7` |
| 本周有效订单 | 49 | `fact:ab7e9a82` |
| 本周客单价 | 155.73 USD | `fact:afdd8b01` |
| 商品金额环比 | -17.3% | `fact:31cf2f70` |
| 订单环比 | -22.2% | `fact:0e8603be` |
| 客单价环比 | +6.3% | `fact:efdd31dc` |
| 商品金额同比（去年同期同星期） | -42.9% | `fact:56489918` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | -1.15 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 2 | `fact:81a0bd95` |
| 环比金额变化中订单数的影响 | -2,112.33 USD | `fact:b99bf8fb` |
| 环比金额变化中客单价的影响 | 513.27 USD | `fact:b99bf8fb` |

## 解释

本周商品金额 7,630.93 USD，有效订单 49，客单价 155.73 USD；商品金额环比 -17.3%，同比 -42.9%。环比变化中订单数影响 -2,112.33 USD、客单价影响 513.27 USD。

## 行动建议

- 在周报中分开跟踪订单数与客单价两项变化，下周确认变化是否持续
- 截止前最后一天的订单审批未落定，下周数据稳定后再比较

## 待验证假设

- 待验证：变化的原因需要结合价格、促销与触达记录核实（数据中没有这些字段）

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:31cf2f70, fact:56489918, fact:b99bf8fb

## 周报 R03

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S02.json
- 数据：src=synthetic;rel=wh-d3aaa559048c;scenario=S02，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 7,630.93 USD | `fact:a31927a7` |
| 本周有效订单 | 49 | `fact:0badc0de` |
| 本周客单价 | 155.73 USD | `fact:afdd8b01` |
| 商品金额环比 | -17.3% | `fact:31cf2f70` |
| 订单环比 | -22.2% | `fact:0e8603be` |
| 客单价环比 | +6.3% | `fact:efdd31dc` |
| 商品金额同比（去年同期同星期） | -42.9% | `fact:56489918` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | -1.15 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 2 | `fact:81a0bd95` |
| 环比金额变化中订单数的影响 | -2,112.33 USD | `fact:b99bf8fb` |
| 环比金额变化中客单价的影响 | 513.27 USD | `fact:b99bf8fb` |

## 解释

报告周为完整可比的一周，所有订单审批均已落定；截止前最后一天单独列出，不参与环比与同比比较。本周商品金额为 7,630.93 USD，有效订单为 49，客单价为 155.73 USD。商品金额环比为 -17.3%，订单环比为 -22.2%，客单价环比为 +6.3%；商品金额同比（去年同期同星期）为 -42.9%。本周商品金额相对近期周基线的 z 值为 -1.15，环比金额变化中订单数的影响为 -2,112.33 USD，客单价的影响为 513.27 USD。有效购买按已审批订单口径统计，金额与订单数均按下单时间归属；截止前最后一天的有效订单为 2，审批尚未落定，仅作单独列示。

## 行动建议

- 对本周商品金额与订单数的环比、同比方向做交叉核对，确认金额变化中订单数与客单价两项影响的相对大小，并据此确定下周跟踪重点。
- 按商品品类与客户地区拆分本周有效订单与商品金额，定位环比变化集中的品类和地区，形成下周重点跟进清单。
- 将截止前最后一天单独列示的未落定审批订单在审批完成后并入对应下单日口径复核，避免与报告周数据混用。

## 待验证假设

- 待验证：本周商品金额环比变化主要由订单数变化贡献，客单价变化的影响相对较小。
- 待验证：本周商品金额相对近期周基线的偏离，集中在少数商品品类或客户地区。
- 待验证：截止前最后一天审批未落定的订单在落定后，会改变该日所属周的有效订单与商品金额口径。

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:31cf2f70, fact:0e8603be, fact:efdd31dc, fact:56489918, fact:f42e59c4, fact:81a0bd95, fact:b99bf8fb

## 周报 R04

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S04.json
- 数据：src=synthetic;rel=wh-d3aaa559048c;scenario=S04，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 2,212.36 USD | `fact:a31927a7` |
| 本周有效订单 | 14 | `fact:ab7e9a82` |
| 本周客单价 | 158.03 USD | `fact:afdd8b01` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | 2.32 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 0 | `fact:81a0bd95` |
| 环比金额变化中订单数的影响 | 752.88 USD | `fact:b99bf8fb` |
| 环比金额变化中客单价的影响 | 179.29 USD | `fact:b99bf8fb` |

## 解释

本周商品金额 2,212.36 USD，有效订单 14，客单价 158.03 USD；商品金额环比 —，同比 —。环比变化中订单数影响 752.88 USD、客单价影响 179.29 USD。

## 行动建议

- 在周报中分开跟踪订单数与客单价两项变化，下周确认变化是否持续
- 截止前最后一天的订单审批未落定，下周数据稳定后再比较

## 待验证假设

- 待验证：变化的原因需要结合价格、促销与触达记录核实（数据中没有这些字段）

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:b99bf8fb

## 周报 R05

# 经营周报（2026-10-30 至 2026-11-07，不含结束日）

- 对应事实表：facts_S02.json
- 数据：src=synthetic;rel=wh-d3aaa559048c;scenario=S02，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 7,630.93 USD | `fact:a31927a7` |
| 本周有效订单 | 49 | `fact:ab7e9a82` |
| 本周客单价 | 155.73 USD | `fact:afdd8b01` |
| 商品金额环比 | -17.3% | `fact:31cf2f70` |
| 订单环比 | -22.2% | `fact:0e8603be` |
| 客单价环比 | +6.3% | `fact:efdd31dc` |
| 商品金额同比（去年同期同星期） | -42.9% | `fact:56489918` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | -1.15 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 2 | `fact:81a0bd95` |
| 环比金额变化中订单数的影响 | -2,112.33 USD | `fact:b99bf8fb` |
| 环比金额变化中客单价的影响 | 513.27 USD | `fact:b99bf8fb` |

## 解释

报告周为完整可比的一周，所有订单审批均已落定；截止前最后一天单独列出，不参与环比与同比比较。本周商品金额为 7,630.93 USD，有效订单为 49，客单价为 155.73 USD。商品金额环比为 -17.3%，订单环比为 -22.2%，客单价环比为 +6.3%；商品金额同比（去年同期同星期）为 -42.9%。本周商品金额相对近期周基线的 z 值为 -1.15，环比金额变化中订单数的影响为 -2,112.33 USD，客单价的影响为 513.27 USD。有效购买按已审批订单口径统计，金额与订单数均按下单时间归属；截止前最后一天的有效订单为 2，审批尚未落定，仅作单独列示。

## 行动建议

- 对本周商品金额与订单数的环比、同比方向做交叉核对，确认金额变化中订单数与客单价两项影响的相对大小，并据此确定下周跟踪重点。
- 按商品品类与客户地区拆分本周有效订单与商品金额，定位环比变化集中的品类和地区，形成下周重点跟进清单。
- 将截止前最后一天单独列示的未落定审批订单在审批完成后并入对应下单日口径复核，避免与报告周数据混用。

## 待验证假设

- 待验证：本周商品金额环比变化主要由订单数变化贡献，客单价变化的影响相对较小。
- 待验证：本周商品金额相对近期周基线的偏离，集中在少数商品品类或客户地区。
- 待验证：截止前最后一天审批未落定的订单在落定后，会改变该日所属周的有效订单与商品金额口径。

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:31cf2f70, fact:0e8603be, fact:efdd31dc, fact:56489918, fact:f42e59c4, fact:81a0bd95, fact:b99bf8fb

## 周报 R06

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S03.json
- 数据：src=synthetic;rel=wh-d3aaa559048c;scenario=S03，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 13,306.01 USD | `fact:a31927a7` |
| 本周有效订单 | 86 | `fact:ab7e9a82` |
| 本周客单价 | 154.72 USD | `fact:afdd8b01` |
| 商品金额同比（去年同期同星期） | -0.4% | `fact:56489918` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | 1.25 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 2 | `fact:81a0bd95` |

## 解释

本周商品金额 13,306.01 USD，有效订单 86，客单价 154.72 USD；商品金额环比 —，同比 -0.4%。环比变化中订单数影响 —、客单价影响 —。

## 行动建议

- 在周报中分开跟踪订单数与客单价两项变化，下周确认变化是否持续
- 截止前最后一天的订单审批未落定，下周数据稳定后再比较

## 待验证假设

- 待验证：变化的原因需要结合价格、促销与触达记录核实（数据中没有这些字段）

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:56489918

## 周报 R07

# 经营周报（2026-10-07 至 2026-10-14，不含结束日）

- 对应事实表：facts_S05.json
- 数据：src=synthetic;rel=wh-d3aaa559048c;scenario=S05，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 11,473.34 USD | `fact:b7638db0` |
| 本周有效订单 | 86 | `fact:ba2f2da2` |
| 本周客单价 | 133.41 USD | `fact:7e562fce` |
| 商品金额环比 | +27.9% | `fact:3bfbd078` |
| 订单环比 | +24.6% | `fact:b7f5e679` |
| 客单价环比 | +2.6% | `fact:16967e2b` |
| 商品金额同比（去年同期同星期） | -2.4% | `fact:c20c4db9` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | 1.89 | `fact:9214f30f` |
| 截止前最后一天的有效订单（审批未落定） | 15 | `fact:350a8f86` |
| 环比金额变化中订单数的影响 | 2,240.20 USD | `fact:327ecb58` |
| 环比金额变化中客单价的影响 | 260.93 USD | `fact:327ecb58` |

## 解释

报告周为完整可比的一周，所有订单审批均已落定；环比对比上一周，同比对比去年同期的同星期。本周商品金额为 11,473.34 USD，有效订单为 86，客单价为 133.41 USD。商品金额环比 +27.9%，订单环比 +24.6%，客单价环比 +2.6%；商品金额同比（去年同期同星期）为 -2.4%。本周商品金额相对近期周基线的 z 值为 1.89，环比金额变化中订单数的影响为 2,240.20 USD，客单价的影响为 260.93 USD。截止前最后一天的有效订单为 15，该日审批未落定，单独列出且不参与比较。有效购买按已审批订单口径统计，金额与订单数均按下单时间归属。

本月商品金额已经低于上月全月，月度业绩明显下滑。

## 行动建议

- 按商品品类汇总本周与上一周的商品金额和有效订单，定位金额变化集中的品类，并安排运营跟进。
- 按客户地区汇总本周与上一周的有效订单和客单价，对订单数或客单价走弱的地区制定下周的客户触达计划。
- 整理本周评价内容，按商品品类归类反馈要点，作为下周商品页与客服话术调整的输入。

## 待验证假设

- 待验证：本周商品金额的环比变化主要由订单数变动带来，客单价的贡献相对较小。
- 待验证：本周商品金额相对近期周基线的偏离，集中在少数商品品类上。
- 待验证：本周客单价的变化与客户地区结构的变化有关。
- 待验证：本周评价中反映的问题集中在特定商品品类，并与该品类的订单变化方向一致。

## 提示

- 2026-10-14 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-10 为不完整月，月度比较使用 2026-09
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:b7638db0, fact:ba2f2da2, fact:7e562fce, fact:3bfbd078, fact:b7f5e679, fact:16967e2b, fact:c20c4db9, fact:9214f30f, fact:350a8f86, fact:327ecb58

## 周报 R08

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S01.json
- 数据：src=synthetic;rel=wh-d3aaa559048c，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 13,306.01 USD | `fact:a31927a7` |
| 本周有效订单 | 86 | `fact:ab7e9a82` |
| 本周客单价 | 154.72 USD | `fact:afdd8b01` |
| 商品金额环比 | +44.2% | `fact:31cf2f70` |
| 订单环比 | +36.5% | `fact:0e8603be` |
| 客单价环比 | +5.6% | `fact:efdd31dc` |
| 商品金额同比（去年同期同星期） | -0.4% | `fact:56489918` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | 2.07 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 2 | `fact:81a0bd95` |
| 环比金额变化中订单数的影响 | 3,468.17 USD | `fact:b99bf8fb` |
| 环比金额变化中客单价的影响 | 607.85 USD | `fact:b99bf8fb` |

## 解释

报告周为完整可比的一周，所有订单审批均已落定；截止前最后一天单独列出，不参与环比与同比比较。本周商品金额为 13,306.01 USD，有效订单为 86，客单价为 154.72 USD。环比看，商品金额变化 +44.2%，订单数变化 +36.5%，客单价变化 +5.6%；同比去年同期同星期，商品金额变化 -0.4%。本周商品金额相对近期周基线的 z 值为 2.07，环比金额变化中订单数的影响为 3,468.17 USD，客单价的影响为 607.85 USD。有效购买按已审批订单口径统计，金额与订单数均按下单时间归属到周。

## 行动建议

- 按商品品类拆分本周与上周的订单数和商品金额，定位环比变化集中的品类并安排跟进。
- 按客户地区对比本周与上周的有效订单与客单价，对下滑地区制定下周的客户回访与复购引导计划。
- 整理本周评价内容，按品类与地区归类反馈要点，作为下周商品与履约改进的输入。

## 待验证假设

- 待验证：本周商品金额环比变化主要由订单数变动贡献，客单价变动的影响相对较小。
- 待验证：本周商品金额相对近期周基线的偏离，与部分品类订单集中变化有关。
- 待验证：本周客单价环比变化与客户地区结构变化有关。

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:31cf2f70, fact:0e8603be, fact:efdd31dc, fact:56489918, fact:f42e59c4, fact:b99bf8fb

## 周报 R09

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S01.json
- 数据：src=synthetic;rel=wh-d3aaa559048c，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 16,306.01 USD | `fact:a31927a7` |
| 本周有效订单 | 86 | `fact:ab7e9a82` |
| 本周客单价 | 154.72 USD | `fact:afdd8b01` |
| 商品金额环比 | +44.2% | `fact:31cf2f70` |
| 订单环比 | +36.5% | `fact:0e8603be` |
| 客单价环比 | +5.6% | `fact:efdd31dc` |
| 商品金额同比（去年同期同星期） | -0.4% | `fact:56489918` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | 2.07 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 2 | `fact:81a0bd95` |
| 环比金额变化中订单数的影响 | 3,468.17 USD | `fact:b99bf8fb` |
| 环比金额变化中客单价的影响 | 607.85 USD | `fact:b99bf8fb` |

## 解释

本周商品金额为 13,306.01 USD，有效订单为 86，客单价为 154.72 USD。口径上，有效购买按已审批订单计，金额与订单数均按下单时间归属到报告周；报告周为完整可比的一周，环比对比上一周，同比对比去年同期的同星期。商品金额环比为 +44.2%，订单环比为 +36.5%，客单价环比为 +5.6%；商品金额同比为 -0.4%。本周商品金额相对近期周基线的 z 值为 2.07。截止前最后一天的有效订单为 2，该日审批尚未落定，单独列出且不参与比较。

## 行动建议

- 对本周商品金额与订单数的环比变化做拆解复核，分别核对订单数影响与客单价影响的口径是否与审批落定时间一致。
- 对本周商品金额相对近期周基线的偏离，按商品品类与客户地区做下钻，定位偏离集中在哪些品类和地区。
- 将截止前最后一天的单列数据在审批落定后重新核对，确认其不并入报告周比较。

## 待验证假设

- 待验证：本周商品金额环比变化中，订单数影响 3,468.17 USD 与客单价影响 607.85 USD 的相对大小，可能反映订单量变化与单笔金额变化的不同贡献。
- 待验证：本周商品金额相对近期周基线的偏离，可能集中在少数商品品类或客户地区。
- 待验证：本周客单价的变化可能与订单在品类间的构成变化有关。

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:31cf2f70, fact:0e8603be, fact:efdd31dc, fact:56489918, fact:f42e59c4, fact:81a0bd95, fact:b99bf8fb

## 周报 R10

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S02.json
- 数据：src=synthetic;rel=wh-d3aaa559048c;scenario=S02，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 7,630.93 USD | `fact:a31927a7` |
| 本周有效订单 | 49 | `fact:ab7e9a82` |
| 本周客单价 | 155.73 USD | `fact:afdd8b01` |
| 商品金额环比 | -17.3% | `fact:31cf2f70` |
| 订单环比 | -22.2% | `fact:0e8603be` |
| 客单价环比 | +6.3% | `fact:efdd31dc` |
| 商品金额同比（去年同期同星期） | -42.9% | `fact:56489918` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | -1.15 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 2 | `fact:81a0bd95` |
| 环比金额变化中订单数的影响 | -2,112.33 USD | `fact:b99bf8fb` |
| 环比金额变化中客单价的影响 | 513.27 USD | `fact:b99bf8fb` |

## 解释

报告周为完整可比的一周，所有订单审批均已落定；截止前最后一天单独列出，不参与环比与同比比较。本周商品金额为 7,630.93 USD，有效订单为 49，客单价为 155.73 USD。商品金额环比为 -17.3%，订单环比为 -22.2%，客单价环比为 +6.3%；商品金额同比（去年同期同星期）为 -42.9%。本周商品金额相对近期周基线的 z 值为 -1.15，环比金额变化中订单数的影响为 -2,112.33 USD，客单价的影响为 513.27 USD。有效购买按已审批订单口径统计，金额与订单数均按下单时间归属；截止前最后一天的有效订单为 2，审批尚未落定，仅作单独列示。

## 行动建议

- 对本周商品金额与订单数的环比、同比方向做交叉核对，确认金额变化中订单数与客单价两项影响的相对大小，并据此确定下周跟踪重点。
- 按商品品类与客户地区拆分本周有效订单与商品金额，定位环比变化集中的品类和地区，形成下周重点跟进清单。
- 将截止前最后一天单独列示的未落定审批订单在审批完成后并入对应下单日口径复核，避免与报告周数据混用。

- 建议按渠道拆分本周订单，找出贡献最大的投放渠道。

## 待验证假设

- 待验证：本周商品金额环比变化主要由订单数变化贡献，客单价变化的影响相对较小。
- 待验证：本周商品金额相对近期周基线的偏离，集中在少数商品品类或客户地区。
- 待验证：截止前最后一天审批未落定的订单在落定后，会改变该日所属周的有效订单与商品金额口径。

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:31cf2f70, fact:0e8603be, fact:efdd31dc, fact:56489918, fact:f42e59c4, fact:81a0bd95, fact:b99bf8fb

## 周报 R11

# 经营周报（2026-10-07 至 2026-10-14，不含结束日）

- 对应事实表：facts_S05.json
- 数据：src=synthetic;rel=wh-d3aaa559048c;scenario=S05，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 11,473.34 USD | `fact:b7638db0` |
| 本周有效订单 | 86 | `fact:ba2f2da2` |
| 本周客单价 | 133.41 USD | `fact:7e562fce` |
| 商品金额环比 | +27.9% | `fact:3bfbd078` |
| 订单环比 | +24.6% | `fact:b7f5e679` |
| 客单价环比 | +2.6% | `fact:16967e2b` |
| 商品金额同比（去年同期同星期） | -2.4% | `fact:c20c4db9` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | 1.89 | `fact:9214f30f` |
| 截止前最后一天的有效订单（审批未落定） | 15 | `fact:350a8f86` |
| 环比金额变化中订单数的影响 | 2,240.20 USD | `fact:327ecb58` |
| 环比金额变化中客单价的影响 | 260.93 USD | `fact:327ecb58` |

## 解释

本周商品金额 11,473.34 USD，有效订单 86，客单价 133.41 USD；商品金额环比 +27.9%，同比 -2.4%。环比变化中订单数影响 2,240.20 USD、客单价影响 260.93 USD。

## 行动建议

- 在周报中分开跟踪订单数与客单价两项变化，下周确认变化是否持续
- 截止前最后一天的订单审批未落定，下周数据稳定后再比较

## 待验证假设

- 待验证：变化的原因需要结合价格、促销与触达记录核实（数据中没有这些字段）

## 提示

- 2026-10-14 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-10 为不完整月，月度比较使用 2026-09
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:b7638db0, fact:ba2f2da2, fact:7e562fce, fact:3bfbd078, fact:c20c4db9, fact:327ecb58

## 周报 R12

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S02.json
- 数据：src=synthetic;rel=wh-d3aaa559048c;scenario=S02，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 7,630.93 USD | `fact:a31927a7` |
| 本周有效订单 | 49 | `fact:ab7e9a82` |
| 本周客单价 | 155.73 USD | `fact:afdd8b01` |
| 商品金额环比 | -17.3% | `fact:31cf2f70` |
| 订单环比 | -22.2% | `fact:0e8603be` |
| 客单价环比 | +6.3% | `fact:efdd31dc` |
| 商品金额同比（去年同期同星期） | -42.9% | `fact:56489918` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | -1.15 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 2 | `fact:81a0bd95` |
| 环比金额变化中订单数的影响 | -2,112.33 USD | `fact:b99bf8fb` |
| 环比金额变化中客单价的影响 | 513.27 USD | `fact:b99bf8fb` |

## 解释

报告周为完整可比的一周，所有订单审批均已落定；截止前最后一天单独列出，不参与环比与同比比较。本周商品金额为 7,630.93 USD，有效订单为 49，客单价为 155.73 USD。商品金额环比为 -17.3%，订单环比为 -22.2%，客单价环比为 +6.3%；商品金额同比（去年同期同星期）为 -42.9%。本周商品金额相对近期周基线的 z 值为 -1.15，环比金额变化中订单数的影响为 -2,112.33 USD，客单价的影响为 513.27 USD。有效购买按已审批订单口径统计，金额与订单数均按下单时间归属；截止前最后一天的有效订单为 2，审批尚未落定，仅作单独列示。

## 行动建议

- 对本周商品金额与订单数的环比、同比方向做交叉核对，确认金额变化中订单数与客单价两项影响的相对大小，并据此确定下周跟踪重点。
- 按商品品类与客户地区拆分本周有效订单与商品金额，定位环比变化集中的品类和地区，形成下周重点跟进清单。
- 将截止前最后一天单独列示的未落定审批订单在审批完成后并入对应下单日口径复核，避免与报告周数据混用。

## 待验证假设

- 待验证：本周商品金额环比变化主要由订单数变化贡献，客单价变化的影响相对较小。
- 待验证：本周商品金额相对近期周基线的偏离，集中在少数商品品类或客户地区。
- 待验证：截止前最后一天审批未落定的订单在落定后，会改变该日所属周的有效订单与商品金额口径。

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:31cf2f70, fact:0e8603be, fact:efdd31dc, fact:56489918, fact:f42e59c4, fact:81a0bd95, fact:b99bf8fb

## 周报 R13

# 经营周报（2026-10-07 至 2026-10-14，不含结束日）

- 对应事实表：facts_S05.json
- 数据：src=synthetic;rel=wh-d3aaa559048c;scenario=S05，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 11,473.34 USD | `fact:b7638db0` |
| 本周有效订单 | 86 | `fact:ba2f2da2` |
| 本周客单价 | 133.41 USD | `fact:7e562fce` |
| 商品金额环比 | +27.9% | `fact:3bfbd078` |
| 订单环比 | +24.6% | `fact:b7f5e679` |
| 客单价环比 | +2.6% | `fact:16967e2b` |
| 商品金额同比（去年同期同星期） | -2.4% | `fact:c20c4db9` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | 1.89 | `fact:9214f30f` |
| 截止前最后一天的有效订单（审批未落定） | 15 | `fact:350a8f86` |
| 环比金额变化中订单数的影响 | 2,240.20 USD | `fact:327ecb58` |
| 环比金额变化中客单价的影响 | 260.93 USD | `fact:327ecb58` |

## 解释

报告周为完整可比的一周，所有订单审批均已落定；环比对比上一周，同比对比去年同期的同星期。本周商品金额为 11,473.34 USD，有效订单为 86，客单价为 133.41 USD。商品金额环比 +27.9%，订单环比 +24.6%，客单价环比 +2.6%；商品金额同比（去年同期同星期）为 -2.4%。本周商品金额相对近期周基线的 z 值为 1.89，环比金额变化中订单数的影响为 2,240.20 USD，客单价的影响为 260.93 USD。截止前最后一天的有效订单为 15，该日审批未落定，单独列出且不参与比较。有效购买按已审批订单口径统计，金额与订单数均按下单时间归属。

## 行动建议

- 按商品品类汇总本周与上一周的商品金额和有效订单，定位金额变化集中的品类，并安排运营跟进。
- 按客户地区汇总本周与上一周的有效订单和客单价，对订单数或客单价走弱的地区制定下周的客户触达计划。
- 整理本周评价内容，按商品品类归类反馈要点，作为下周商品页与客服话术调整的输入。

## 待验证假设

- 待验证：本周商品金额的环比变化主要由订单数变动带来，客单价的贡献相对较小。
- 待验证：本周商品金额相对近期周基线的偏离，集中在少数商品品类上。
- 待验证：本周客单价的变化与客户地区结构的变化有关。
- 待验证：本周评价中反映的问题集中在特定商品品类，并与该品类的订单变化方向一致。

## 提示

- 2026-10-14 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-10 为不完整月，月度比较使用 2026-09
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:b7638db0, fact:ba2f2da2, fact:7e562fce, fact:3bfbd078, fact:b7f5e679, fact:16967e2b, fact:c20c4db9, fact:9214f30f, fact:350a8f86, fact:327ecb58

## 周报 R14

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S03.json
- 数据：src=synthetic;rel=wh-d3aaa559048c;scenario=S03，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 13,306.01 USD | `fact:a31927a7` |
| 本周有效订单 | 86 | `fact:ab7e9a82` |
| 本周客单价 | 154.72 USD | `fact:afdd8b01` |
| 商品金额同比（去年同期同星期） | -0.4% | `fact:56489918` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | 1.25 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 2 | `fact:81a0bd95` |

## 解释

本报告周为完整可比的一周，所有订单审批均已落定；环比对比上一周，同比对比去年同期同星期。本周商品金额为 13,306.01 USD，本周有效订单为 86，本周客单价为 154.72 USD。商品金额同比（去年同期同星期）为 -0.4%，本周商品金额相对近期周基线的 z 值为 1.25。截止前最后一天的有效订单为 2，该日审批未落定，单独列出且不参与比较。有效购买按已审批订单口径统计，金额与订单数均按下单时间归属到周。

## 行动建议

- 按商品品类与客户地区拆分本周商品金额、有效订单与客单价，定位同比与基线偏离主要落在哪些品类和地区。
- 对本周评价内容做归类整理，结合订单与品类维度核对金额变化与评价反馈是否指向同一批商品。
- 对截止前最后一天的单列数据保持观察，待审批落定后再纳入下一周比较，不并入本周口径。

## 待验证假设

- 待验证：本周商品金额相对近期周基线的偏离，可能集中在少数商品品类上。
- 待验证：同比变化可能主要由客单价与有效订单量的不同方向变动共同形成。
- 待验证：本周评价中反映的问题可能与商品金额变动较大的品类存在对应关系。

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:56489918, fact:f42e59c4, fact:81a0bd95

## 周报 R15

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S01.json
- 数据：src=synthetic;rel=wh-d3aaa559048c，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 13,306.01 USD | `fact:a31927a7` |
| 本周有效订单 | 86 | `fact:ab7e9a82` |
| 本周客单价 | 154.72 USD | `fact:afdd8b01` |
| 商品金额环比 | +44.2% | `fact:31cf2f70` |
| 订单环比 | +36.5% | `fact:0e8603be` |
| 客单价环比 | +5.6% | `fact:efdd31dc` |
| 商品金额同比（去年同期同星期） | -0.4% | `fact:56489918` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | 2.07 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 2 | `fact:81a0bd95` |
| 环比金额变化中订单数的影响 | 3,468.17 USD | `fact:b99bf8fb` |
| 环比金额变化中客单价的影响 | 607.85 USD | `fact:b99bf8fb` |

## 解释

本周商品金额为 13,306.01 USD，有效订单为 86，客单价为 154.72 USD。口径上，有效购买按已审批订单计，金额与订单数均按下单时间归属到报告周；报告周为完整可比的一周，环比对比上一周，同比对比去年同期的同星期。商品金额环比为 +44.2%，订单环比为 +36.5%，客单价环比为 +5.6%；商品金额同比为 -0.4%。本周商品金额相对近期周基线的 z 值为 2.07。截止前最后一天的有效订单为 2，该日审批尚未落定，单独列出且不参与比较。

## 行动建议

- 对本周商品金额与订单数的环比变化做拆解复核，分别核对订单数影响与客单价影响的口径是否与审批落定时间一致。
- 对本周商品金额相对近期周基线的偏离，按商品品类与客户地区做下钻，定位偏离集中在哪些品类和地区。
- 将截止前最后一天的单列数据在审批落定后重新核对，确认其不并入报告周比较。

## 待验证假设

- 待验证：本周商品金额环比变化中，订单数影响 3,468.17 USD 与客单价影响 607.85 USD 的相对大小，可能反映订单量变化与单笔金额变化的不同贡献。
- 待验证：本周商品金额相对近期周基线的偏离，可能集中在少数商品品类或客户地区。
- 待验证：本周客单价的变化可能与订单在品类间的构成变化有关。

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:31cf2f70, fact:0e8603be, fact:efdd31dc, fact:56489918, fact:f42e59c4, fact:81a0bd95, fact:b99bf8fb

## 周报 R16

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S01.json
- 数据：src=synthetic;rel=wh-d3aaa559048c，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 13,306.01 USD | `fact:a31927a7` |
| 本周有效订单 | 86 | `fact:ab7e9a82` |
| 本周客单价 | 154.72 USD | `fact:afdd8b01` |
| 商品金额环比 | +44.2% | `fact:31cf2f70` |
| 订单环比 | +36.5% | `fact:0e8603be` |
| 客单价环比 | +5.6% | `fact:efdd31dc` |
| 商品金额同比（去年同期同星期） | -0.4% | `fact:56489918` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | 2.07 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 2 | `fact:81a0bd95` |
| 环比金额变化中订单数的影响 | 3,468.17 USD | `fact:b99bf8fb` |
| 环比金额变化中客单价的影响 | 607.85 USD | `fact:b99bf8fb` |

## 解释

本周商品金额 13,306.01 USD，有效订单 86，客单价 154.72 USD；商品金额环比 +44.2%，同比 -0.4%。环比变化中订单数影响 3,468.17 USD、客单价影响 607.85 USD。

## 行动建议

- 在周报中分开跟踪订单数与客单价两项变化，下周确认变化是否持续
- 截止前最后一天的订单审批未落定，下周数据稳定后再比较

## 待验证假设

- 待验证：变化的原因需要结合价格、促销与触达记录核实（数据中没有这些字段）

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:31cf2f70, fact:56489918, fact:b99bf8fb

## 周报 R17

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S01.json
- 数据：src=synthetic;rel=wh-d3aaa559048c，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 13,306.01 USD | `fact:a31927a7` |
| 本周有效订单 | 86 | `fact:ab7e9a82` |
| 本周客单价 | 154.72 USD | `fact:afdd8b01` |
| 商品金额环比 | +44.2% | `fact:31cf2f70` |
| 订单环比 | +36.5% | `fact:0e8603be` |
| 客单价环比 | +5.6% | `fact:efdd31dc` |
| 商品金额同比（去年同期同星期） | -0.4% | `fact:56489918` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | 2.07 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 2 | `fact:81a0bd95` |
| 环比金额变化中订单数的影响 | 3,468.17 USD | `fact:b99bf8fb` |
| 环比金额变化中客单价的影响 | 607.85 USD | `fact:b99bf8fb` |

## 解释

本周商品金额为 13,306.01 USD，有效订单为 86，客单价为 154.72 USD。口径上，有效购买按已审批订单计，金额与订单数均按下单时间归属到报告周；报告周为完整可比的一周，环比对比上一周，同比对比去年同期的同星期。商品金额环比为 +44.2%，订单环比为 +36.5%，客单价环比为 +5.6%；商品金额同比为 -0.4%。本周商品金额相对近期周基线的 z 值为 2.07。截止前最后一天的有效订单为 2，该日审批尚未落定，单独列出且不参与比较。

本周金额上升是因为促销活动效果显著。

## 行动建议

- 对本周商品金额与订单数的环比变化做拆解复核，分别核对订单数影响与客单价影响的口径是否与审批落定时间一致。
- 对本周商品金额相对近期周基线的偏离，按商品品类与客户地区做下钻，定位偏离集中在哪些品类和地区。
- 将截止前最后一天的单列数据在审批落定后重新核对，确认其不并入报告周比较。

## 待验证假设

- 待验证：本周商品金额环比变化中，订单数影响 3,468.17 USD 与客单价影响 607.85 USD 的相对大小，可能反映订单量变化与单笔金额变化的不同贡献。
- 待验证：本周商品金额相对近期周基线的偏离，可能集中在少数商品品类或客户地区。
- 待验证：本周客单价的变化可能与订单在品类间的构成变化有关。

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:31cf2f70, fact:0e8603be, fact:efdd31dc, fact:56489918, fact:f42e59c4, fact:81a0bd95, fact:b99bf8fb

## 周报 R18

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S01.json
- 数据：src=synthetic;rel=wh-d3aaa559048c，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 13,306.01 USD | `fact:a31927a7` |
| 本周有效订单 | 86 | `fact:ab7e9a82` |
| 本周客单价 | 154.72 USD | `fact:afdd8b01` |
| 商品金额环比 | +44.2% | `fact:31cf2f70` |
| 订单环比 | +36.5% | `fact:0e8603be` |
| 客单价环比 | +5.6% | `fact:efdd31dc` |
| 商品金额同比（去年同期同星期） | -0.4% | `fact:56489918` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | 2.07 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 2 | `fact:81a0bd95` |
| 环比金额变化中订单数的影响 | 3,468.17 USD | `fact:b99bf8fb` |
| 环比金额变化中客单价的影响 | 607.85 USD | `fact:b99bf8fb` |

## 解释

本周商品金额为 13,306.01 USD，有效订单为 86，客单价为 154.72 USD；口径为已审批订单按下单时间归属到报告周，报告周为完整可比的一周。环比看，商品金额变化 +44.2%，订单变化 +36.5%，客单价变化 +5.6%；同比去年同期同星期，商品金额变化 -0.4%。本周商品金额相对近期完整周基线的 z 值为 2.07。环比金额变化中，订单数的影响为 3,468.17 USD，客单价的影响为 607.85 USD。截止前最后一天的有效订单为 2，该日审批尚未落定，单独列出且不参与比较。

## 行动建议

- 按商品品类与客户地区拆分本周商品金额、有效订单与客单价，定位环比变化集中的品类和地区，作为下周跟进重点。
- 对本周评价内容做逐条归类，标记与商品描述、配送时效、包装相关的反馈，交由对应品类负责人跟进处理。
- 在下一周报告中沿用同一口径（已审批订单按下单时间归属），并保持截止前最后一天单独列示、不参与比较的做法。

## 待验证假设

- 待验证：本周商品金额环比变化主要由订单数变化贡献，客单价变化贡献较小，需结合品类结构进一步确认。
- 待验证：本周商品金额相对近期周基线的偏离，可能集中在少数品类或地区，需按品类与地区拆分后确认。
- 待验证：本周评价中的负面反馈可能与部分品类的商品或履约体验相关，需逐条核对评价内容后确认。

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:31cf2f70, fact:0e8603be, fact:efdd31dc, fact:56489918, fact:f42e59c4, fact:81a0bd95, fact:b99bf8fb

## 周报 R19

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S04.json
- 数据：src=synthetic;rel=wh-d3aaa559048c;scenario=S04，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 2,212.36 USD | `fact:a31927a7` |
| 本周有效订单 | 14 | `fact:ab7e9a82` |
| 本周客单价 | 158.03 USD | `fact:afdd8b01` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | 2.32 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 0 | `fact:81a0bd95` |
| 环比金额变化中订单数的影响 | 752.88 USD | `fact:b99bf8fb` |
| 环比金额变化中客单价的影响 | 179.29 USD | `fact:b99bf8fb` |

## 解释

本周商品金额为 2,212.36 USD，有效订单为 14，客单价为 158.03 USD；有效购买按已审批订单口径统计，金额与订单数均按下单时间归属到报告周。本周商品金额相对近期完整周基线的 z 值为 2.32。环比金额变化可拆为订单数影响 752.88 USD 与客单价影响 179.29 USD。截止前最后一天的有效订单为 0，该日审批尚未落定，单独列出且不参与本周比较。

## 行动建议

- 按商品品类与客户地区拆分本周商品金额和有效订单，定位金额变化集中的品类与地区，作为下周跟进重点。
- 复核本周订单从下单到审批的时长分布，确认报告周内审批均已落定，并保持截止日单独列示的口径。
- 对本周评价内容按品类与地区归类整理，与订单和金额变化对照，形成下周运营跟进清单。

## 待验证假设

- 待验证：本周金额环比变化中订单数影响与客单价影响的相对大小，可能反映下单客户结构或购买件数的变化，需按品类与地区拆分核实。
- 待验证：本周商品金额相对基线的偏离，可能集中在少数品类或地区，需用分品类、分地区数据确认。
- 待验证：截止前最后一天审批未落定的订单，可能在审批落定后改变该日口径下的订单与金额，需在下一报告周期复核。

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:f42e59c4, fact:81a0bd95, fact:b99bf8fb

## 周报 R20

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S03.json
- 数据：src=synthetic;rel=wh-d3aaa559048c;scenario=S03，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 13,306.01 USD | `fact:a31927a7` |
| 本周有效订单 | 86 | `fact:ab7e9a82` |
| 本周客单价 | 154.72 USD | `fact:afdd8b01` |
| 商品金额同比（去年同期同星期） | -0.4% | `fact:56489918` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | 1.25 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 2 | `fact:81a0bd95` |

## 解释

本报告周为完整可比的一周，所有订单审批均已落定；环比对比上一周，同比对比去年同期同星期。本周商品金额为 13,306.01 USD，本周有效订单为 86，本周客单价为 154.72 USD。商品金额同比（去年同期同星期）为 -0.4%，本周商品金额相对近期周基线的 z 值为 1.25。截止前最后一天的有效订单为 2，该日审批未落定，单独列出且不参与比较。有效购买按已审批订单口径统计，金额与订单数均按下单时间归属到周。

商品金额环比增长 0%，与上周持平。

## 行动建议

- 按商品品类与客户地区拆分本周商品金额、有效订单与客单价，定位同比与基线偏离主要落在哪些品类和地区。
- 对本周评价内容做归类整理，结合订单与品类维度核对金额变化与评价反馈是否指向同一批商品。
- 对截止前最后一天的单列数据保持观察，待审批落定后再纳入下一周比较，不并入本周口径。

## 待验证假设

- 待验证：本周商品金额相对近期周基线的偏离，可能集中在少数商品品类上。
- 待验证：同比变化可能主要由客单价与有效订单量的不同方向变动共同形成。
- 待验证：本周评价中反映的问题可能与商品金额变动较大的品类存在对应关系。

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:56489918, fact:f42e59c4, fact:81a0bd95

## 周报 R21

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S02.json
- 数据：src=synthetic;rel=wh-d3aaa559048c;scenario=S02，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 7,630.93 USD | `fact:a31927a7` |
| 本周有效订单 | 49 | `fact:ab7e9a82` |
| 本周客单价 | 155.73 USD | `fact:afdd8b01` |
| 商品金额环比 | -17.3% | `fact:31cf2f70` |
| 订单环比 | -22.2% | `fact:0e8603be` |
| 客单价环比 | +6.3% | `fact:efdd31dc` |
| 商品金额同比（去年同期同星期） | -42.9% | `fact:56489918` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | -1.15 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 2 | `fact:81a0bd95` |
| 环比金额变化中订单数的影响 | -2,112.33 USD | `fact:b99bf8fb` |
| 环比金额变化中客单价的影响 | 513.27 USD | `fact:b99bf8fb` |

## 解释

报告周内所有订单审批均已落定，报告周为完整可比的一周；截止前最后一天不在报告周内，单独列出且不参与比较。本周商品金额为 7,630.93 USD，有效订单为 49，客单价为 155.73 USD。环比看，商品金额变化 -17.3%，订单数变化 -22.2%，客单价变化 +6.3%；同比去年同期同星期，商品金额变化 -42.9%。本周商品金额相对近期周基线的 z 值为 -1.15，环比金额变化中订单数的影响为 -2,112.33 USD，客单价的影响为 513.27 USD。口径上，有效购买按已审批订单计，金额与订单数按下单时间归属；截止前最后一天的有效订单为 2，审批未落定，仅单独列出。

## 行动建议

- 按商品品类拆分本周商品金额与有效订单的环比变化，定位金额波动集中的品类并安排跟进。
- 按客户地区查看本周有效订单与客单价的分布，对环比走弱的地区制定下周的客户回访与复购引导计划。
- 汇总本周评价内容，按品类与地区归类反馈要点，作为下周商品与履约改进的输入。

## 待验证假设

- 待验证：本周商品金额的环比变化主要由订单数变化贡献，客单价变化的影响相对较小。
- 待验证：本周商品金额相对近期周基线的偏离，与部分品类的订单集中度上升有关。
- 待验证：本周客单价的环比变化与客户地区结构的变化有关。

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:31cf2f70, fact:0e8603be, fact:efdd31dc, fact:56489918, fact:f42e59c4, fact:81a0bd95, fact:b99bf8fb

## 周报 R22

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S04.json
- 数据：src=synthetic;rel=wh-d3aaa559048c;scenario=S04，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 2,212.36 USD | `fact:a31927a7` |
| 本周有效订单 | 14 | `fact:ab7e9a82` |
| 本周客单价 | 158.03 USD | `fact:afdd8b01` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | 2.32 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 0 | `fact:81a0bd95` |
| 环比金额变化中订单数的影响 | 752.88 USD | `fact:b99bf8fb` |
| 环比金额变化中客单价的影响 | 179.29 USD | `fact:b99bf8fb` |

## 解释

本周商品金额为 2,212.36 USD，有效订单为 14，客单价为 158.03 USD；有效购买按已审批订单口径统计，金额与订单数均按下单时间归属到报告周。本周商品金额相对近期完整周基线的 z 值为 2.32。环比金额变化可拆为订单数影响 752.88 USD 与客单价影响 179.29 USD。截止前最后一天的有效订单为 0，该日审批尚未落定，单独列出且不参与本周比较。

## 行动建议

- 按商品品类汇总本周与上一周的有效订单数和商品金额，定位金额变化主要落在哪些品类，并对变化明显的品类安排运营跟进。
- 按客户地区对比本周与去年同期的同星期有效订单数和客单价，筛出波动较大的地区作为下周重点跟进对象。
- 整理本周评价内容，按商品品类归类反馈要点，作为下周商品与页面调整的输入。

## 待验证假设

- 待验证：本周金额环比变化主要由订单数变动带来，客单价变动的影响相对较小。
- 待验证：本周商品金额相对基线的偏离集中在少数商品品类，而非全部品类普遍变化。
- 待验证：截止前最后一天审批落定后，该日订单会使本周有效订单口径的金额进一步上升。

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:f42e59c4, fact:81a0bd95, fact:b99bf8fb

## 周报 R23

# 经营周报（2026-10-31 至 2026-11-07，不含结束日）

- 对应事实表：facts_S03.json
- 数据：src=synthetic;rel=wh-d3aaa559048c;scenario=S03，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 13,306.01 USD | `fact:a31927a7` |
| 本周有效订单 | 86 | `fact:ab7e9a82` |
| 本周客单价 | 154.72 USD | `fact:afdd8b01` |
| 商品金额同比（去年同期同星期） | -0.4% | `fact:56489918` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | 1.25 | `fact:f42e59c4` |
| 截止前最后一天的有效订单（审批未落定） | 2 | `fact:81a0bd95` |

## 解释

本报告周为完整可比的一周，周内订单审批均已落定；截止前最后一天不在报告周内，单独列出且不参与比较。本周商品金额为 13,306.01 USD，有效订单为 86，客单价为 154.72 USD；有效购买按已审批订单口径统计，金额与订单数均按下单时间归属。同比口径为去年同期同星期，本周商品金额同比为 -0.4%；相对报告周之前若干完整周的基线，本周商品金额的 z 值为 1.25。截止前最后一天的有效订单为 2，该日审批尚未落定，仅作单独列示。以上均为合成模拟数据，仅用于口径演示。

## 行动建议

- 按周固定复核有效购买口径：确认报告周内订单审批均已落定，并将截止前最后一天单独列示、不纳入环比与同比比较。
- 对本周商品金额与有效订单做同比与基线 z 值双口径跟踪，在下一周报告中沿用同一口径复算，保持可比性。
- 针对客单价与订单数的周度变化，按商品品类与客户地区拆分查看结构，评价数据仅作辅助参考。

## 待验证假设

- 待验证：本周商品金额同比变化可能来自去年同期同星期与本周在品类结构上的差异。
- 待验证：本周商品金额相对近期周基线的偏离可能由少数品类或少数地区订单集中所致。
- 待验证：客单价的变化可能来自订单内商品组合的变化，而非订单数量的变化。

## 提示

- 2026-11-07 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-11 为不完整月，月度比较使用 2026-10
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:a31927a7, fact:ab7e9a82, fact:afdd8b01, fact:56489918, fact:f42e59c4, fact:81a0bd95

## 周报 R24

# 经营周报（2026-10-07 至 2026-10-14，不含结束日）

- 对应事实表：facts_S05.json
- 数据：src=synthetic;rel=wh-d3aaa559048c;scenario=S05，metrics@e84d17c3；完全合成的模拟数据，不是真实企业

## 关键数字

| 指标 | 值 | 依据 |
|---|---:|---|
| 本周商品金额 | 11,473.34 USD | `fact:b7638db0` |
| 本周有效订单 | 86 | `fact:ba2f2da2` |
| 本周客单价 | 133.41 USD | `fact:7e562fce` |
| 商品金额环比 | +27.9% | `fact:3bfbd078` |
| 订单环比 | +24.6% | `fact:b7f5e679` |
| 客单价环比 | +2.6% | `fact:16967e2b` |
| 商品金额同比（去年同期同星期） | -2.4% | `fact:c20c4db9` |
| 本周商品金额相对近期周基线的 z 值（基线为报告周之前的若干完整周） | 1.89 | `fact:9214f30f` |
| 截止前最后一天的有效订单（审批未落定） | 15 | `fact:350a8f86` |
| 环比金额变化中订单数的影响 | 2,240.20 USD | `fact:327ecb58` |
| 环比金额变化中客单价的影响 | 260.93 USD | `fact:327ecb58` |

## 解释

报告周为完整可比的一周，所有订单审批均已落定；环比对比上一周，同比对比去年同期的同星期。本周商品金额为 11,473.34 USD，有效订单为 86，客单价为 133.41 USD。商品金额环比为 +27.9%，订单环比为 +24.6%，客单价环比为 +2.6%；商品金额同比（去年同期同星期）为 -2.4%。本周商品金额相对近期周基线的 z 值为 1.89，环比金额变化中订单数的影响为 2,240.20 USD，客单价的影响为 260.93 USD。截止前最后一天的有效订单为 15，该日审批未落定，单独列出且不参与比较。有效购买按已审批订单口径统计，金额与订单数均按下单时间归属。

## 行动建议

- 按商品品类汇总本周与上周的订单数和商品金额，定位金额环比变化主要落在哪些品类，并对变化最大的品类做逐日跟踪。
- 按客户地区拆分本周与上周的有效订单和客单价，对订单数或客单价回落明显的地区安排客户回访与评价跟进。
- 整理本周评价内容，按品类和地区归类反馈要点，作为下一周商品与页面调整的输入。

## 待验证假设

- 待验证：本周商品金额环比变化主要由订单数变动贡献，客单价变动的影响相对较小。
- 待验证：本周商品金额相对近期周基线的偏离，集中在少数品类或少数地区。
- 待验证：截止前最后一天审批未落定的订单在审批落定后，会改变该日与本周的订单口径结果。

## 提示

- 2026-10-14 当天的订单可能尚未审批，只单独列出，不参与环比/同比
- 2026-10 为不完整月，月度比较使用 2026-09
- 引用资料：doc:transaction_rules#1-有效购买@transaction-rules-v1, doc:transaction_rules#2-时间归属与可观察性@transaction-rules-v1
- 解释部分引用的事实：fact:b7638db0, fact:ba2f2da2, fact:7e562fce, fact:3bfbd078, fact:b7f5e679, fact:16967e2b, fact:c20c4db9, fact:9214f30f, fact:350a8f86, fact:327ecb58
