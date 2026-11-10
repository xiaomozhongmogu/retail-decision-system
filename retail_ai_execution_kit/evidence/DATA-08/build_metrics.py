"""Write contracts/metrics.json from the executable rule module (single source of SQL).
usage: .venv/bin/python evidence/DATA-08/build_metrics.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/data'))
from transactions import METRIC_SQL, RULE_VERSION, VIEWS, APPROVAL_MAX_LAG_HOURS, LABEL_MATURITY_DAYS  # noqa: E402

rec = json.loads((ROOT / 'reports/data/transaction_reconciliation.json').read_text(encoding='utf-8'))
ex = rec['metric_examples']
DIMS = ['purchase date/week/month', 'customer_state', 'customer_region', 'product_category', 'seller_id', 'payment_type']
VALID = '有效购买：approved_ts 非空且 approved_ts < as_of（已审批）；按 purchase_ts 归属窗口'
COMMON = {
    'windows': '左闭右开 [start, end)，按 purchase_ts（UTC 工程假设）；as_of 默认等于数据截止 2026-11-08T00:00:00Z',
    'zero_null_policy': '计数和金额在空窗口返回 0；比率分母为 0 返回 null 并附 zero_denominator 警告',
    'supported_dimensions': DIMS,
}


def m(id_, name, unit, definition, numerator, denominator, population, inclusions, exclusions, sql_key=None, **kw):
    d = {'id': id_, 'name': name, 'unit': unit, 'definition': definition, 'population': population,
         'inclusions': inclusions, 'exclusions': exclusions, 'numerator': numerator, 'denominator': denominator, **COMMON}
    if sql_key:
        d['sql'] = METRIC_SQL[sql_key]
        d['sql_mapping'] = f'src/retail_bi/data/transactions.py METRIC_SQL["{sql_key}"]（参数 $start, $end, $as_of；视图见 VIEWS）'
        d['examples_and_checks'] = {k: v[sql_key] for k, v in ex.items()}
    d.update(kw)
    return d


metrics = [
    m('valid_orders', '有效订单数', 'orders', '窗口内下单且截至 as_of 已审批的订单去重数', 'count(distinct order_id)', None,
      '全部订单', VALID, '已取消（无审批）；截至 as_of 尚未审批', 'valid_orders'),
    m('merchandise_sales_usd', '有效订单商品金额', 'USD', '有效订单明细 item_price_usd 之和；不含运费，不是已支付 GMV、净收入或利润', 'sum(item_price_usd)', None,
      '有效订单的全部明细行', VALID, '已取消与未审批订单；运费', 'merchandise_sales_usd'),
    m('shipping_usd', '有效订单运费', 'USD', '有效订单明细运费之和，单独报告', 'sum(item_shipping_usd)', None, '有效订单的全部明细行', VALID, '已取消与未审批订单', 'shipping_usd'),
    m('order_value_usd', '有效订单金额（含运费）', 'USD', '商品金额＋运费；与支付记录逐单相等，只用于对账展示', 'sum(item_total_usd)', None, '有效订单', VALID, '已取消与未审批订单', 'order_value_usd'),
    m('buyers', '购买客户数', 'customers', '窗口内至少一单有效订单的已知客户去重；不同窗口不能相加', 'count(distinct customer_id)', None,
      '已知 customer_id 的有效订单（本数据全部已知）', VALID, '未知客户（本数据为 0）', 'buyers'),
    m('aov_usd', '客单价（每单商品金额）', 'USD/order', '有效订单商品金额 / 有效订单数；分子分母同一范围', 'merchandise_sales_usd', 'valid_orders',
      '有效订单', VALID, '已取消与未审批订单；运费', 'aov_usd'),
    m('cancelled_orders', '取消订单数', 'orders', '窗口内下单、最终无审批的订单；取消发生时间未知，按下单时间归属', 'count(distinct order_id)', None,
      '全部订单', 'approved_ts 为空且 purchase_ts < as_of', '有效订单', 'cancelled_orders',
      caveat='最终状态含截止后信息；as_of 早于截止时，尚未审批的订单无法区分“待审批”和“将取消”，只在完整历史期间使用'),
    m('cancelled_merchandise_usd', '取消订单商品金额', 'USD', '取消订单的 item_price_usd 之和；没有退款记录，不称退款金额', 'sum(item_price_usd)', None,
      '取消订单', 'approved_ts 为空', '有效订单', 'cancelled_merchandise_usd'),
    m('repurchase_30d', '未来30天复购概率', 'probability', '对 as_of 时母体客户，P([as_of, as_of+30d) 至少一单有效购买)', '模型输出', None,
      '默认母体：as_of 前 90 天有有效购买的已知客户（PROJECT_SPEC §5）；ML-01 冻结', '标签按本文件有效购买规则；标签窗结束后再等 1 天让审批落定',
      '生成器标签、最终状态、截止后信息不作特征', None, sql='由 ML-02 样本构建实现', label_maturity_days=LABEL_MATURITY_DAYS, owner='ML-01/ML-02'),
    m('non_repurchase_30d', '未来30天未复购风险', 'probability', '1 - repurchase_30d；不是永久流失，也不是营销增量', '1 - repurchase_30d', None,
      '同 repurchase_30d', '同上', '同上', None, sql='由 ML-11 评分服务输出', owner='ML-11'),
    m('rfm', 'RFM 画像', 'days / orders / USD', 'R：as_of 距最近一次有效购买的天数；F：[as_of-90d, as_of) 有效订单数；M：同窗有效订单商品金额（不含运费）；非严格 CLV', 'R/F/M', None,
      '至少一次有效购买的已知客户', VALID, '已取消订单；运费', None, sql='由 DW-05 客户快照实现', owner='DW-05/ML-05'),
]

doc = {
    'status': 'frozen_v1',
    'rule_version': RULE_VERSION,
    'applies_to': 'contracts/data_contract.json synthetic-transaction-v1（完全合成数据，USD）',
    'superseded': 'UCI 草案（GBP、invoice、quantity×unit_price）已作废（D013）',
    'rules_doc': 'docs/transaction_rules.md',
    'reconciliation': 'reports/data/transaction_reconciliation.json',
    'views': VIEWS,
    'observability': {'approval_max_lag_hours': APPROVAL_MAX_LAG_HOURS, 'label_maturity_days': LABEL_MATURITY_DAYS,
                      'rule': '任何 as_of 时点只计 approved_ts < as_of 的订单；最终 order_status 不在 as_of 计算中使用'},
    'forbidden_names': ['已支付 GMV', '净收入', '退款金额', '利润', '毛利', '销量（件数）'],
    'metrics': metrics,
    'required_for_approval': ['windows', 'population', 'inclusions', 'exclusions', 'numerator', 'denominator',
                              'zero_null_policy', 'supported_dimensions', 'sql_mapping', 'examples_and_checks'],
    'approval_note': '可执行 SQL 的 8 个指标在 DATA-08 对账中实际运行；模型与快照类指标的 SQL 由所属任务实现后补齐',
}
(ROOT / 'contracts/metrics.json').write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(len(metrics), 'metrics written')
