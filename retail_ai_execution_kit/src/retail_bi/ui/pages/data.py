"""UI page: data source, quality, coverage, units, limits, metric definitions and issue samples (UI-02).

Numbers come from the frozen data reports (reports/data/*.json, written by the DATA tasks) and, for the
cross-check, from the published release through the allowed view ads.kpi_monthly. Model sample rows
(customer x week) are shown separately from raw record counts. No keys or personal attributes are shown.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, banner, release_info, show, view  # noqa: E402


def report(rel):
    p = ROOT / rel
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


st.title('数据口径与质量')
info = banner()
rel = report('reports/data/dataset_release.json')
prof = report('reports/data/profile_after.json')
qc = report('reports/data/quality_checks.json')
rec = report('reports/data/transaction_reconciliation.json')
cln = report('reports/data/cleaning_missing_duplicates.json')
metrics = report('contracts/metrics.json')
issues = report('reports/ui/data_issue_samples.json')
if not all([rel, prof, qc, rec, cln, metrics]):
    st.error('数据报告缺失：请先按 docs/data_readme.md 重建数据层与报告。')
    st.stop()

t1, t2, t3, t4, t5, t6, t7 = st.tabs(['来源与版本', '规模与覆盖', '质量检查', '有效购买对账', '缺失与重复', '指标解释', '问题样本'])

with t1:
    st.markdown(f"**数据性质**：{rel['nature']}")
    st.markdown(f"**使用依据**：{rel['eligibility']['basis']}；教师确认：{rel['eligibility']['teacher_confirmation']}")
    fd = rel['formal_data']
    st.markdown(f"**原始数据包**：`{fd['path']}`，SHA-256 `{fd['sha256'][:16]}…`，{fd['bytes']:,} 字节（解压后 CSV {fd['uncompressed_csv_bytes']:,} 字节）")
    st.markdown(f"**许可说明**：{fd['license_note']}")
    st.dataframe(pd.DataFrame([{'层': k, '版本': v} for k, v in rel['versions'].items()]), hide_index=True)
    st.markdown('**尚未确定的事项**')
    for u in rel['unknowns']:
        st.markdown(f'- {u}')

with t2:
    st.subheader('原始记录（清洗后，截止前全部历史，未抽样）')
    rows = [{'表': t, '行数': n, '列数': prof['columns_per_table'][t]} for t, n in prof['rows'].items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True)
    tm = prof['time']
    c1, c2, c3 = st.columns(3)
    c1.metric('首笔下单', tm['purchase_first'][:10])
    c2.metric('末笔下单', tm['purchase_last'][:10])
    c3.metric('覆盖月数', tm['months'])
    st.caption(f"时区：{tm['timezone']}。有效业务字段 {prof['effective_business_fields']} 个。")
    v = prof['valid_orders_at_cutoff']
    st.subheader('截止时有效购买（已审批）')
    c1, c2, c3 = st.columns(3)
    c1.metric('有效订单', f"{v['orders']:,}")
    c2.metric('商品金额（USD，不含运费）', f"{float(v['merch_usd']):,.2f}")
    c3.metric('运费（USD）', f"{float(v['shipping_usd']):,.2f}")
    status, df, msg = view('ads.kpi_monthly', ['month', 'valid_orders', 'merchandise_sales_usd'])
    if show(status, df, msg, '发布版本中没有月度指标'):
        o, s = int(df.valid_orders.astype(int).sum()), df.merchandise_sales_usd.astype(float).sum()
        same = o == v['orders'] and abs(s - float(v['merch_usd'])) < 0.005
        (st.success if same else st.error)(f"核对：发布版本 ads.kpi_monthly 合计有效订单 {o:,}、商品金额 {s:,.2f} USD — " + ('与质量报告一致' if same else '与质量报告不一致'))
    lab = prof['label_30d_with_frozen_rule']
    st.subheader('模型样本（不是原始数据量）')
    st.markdown(f"客户×周快照 {lab['rows']:,} 行（{lab['weekly_snapshots']} 个周快照，{lab['first_as_of'][:10]} 至 {lab['last_as_of'][:10]}），"
                f"正例 {lab['positives']:,}、负例 {lab['negatives']:,}，正例率 {lab['positive_rate']:.1%}。同一客户在多个周出现，所以行数大于客户数；"
                f"有过有效购买的客户 {prof['model_usable_customers']['customers_with_valid_purchase']:,} 人。")

with t3:
    st.markdown(f"质量门槛：**{qc['gate']}**（{qc['passed']}/{qc['total']}）")
    st.dataframe(pd.DataFrame([{'检查': c['check'], '结果': c['status'], '值': str(c['value'])} for c in qc['checks']]), hide_index=True)
    for w in qc['warnings']:
        st.warning(f"{w['quarter']}：{w['message']}")
    st.caption(qc['note'])

with t4:
    keys = [('raw_all_orders', '原始全部订单'), ('cancelled_orders', '减：已取消（无审批）'), ('pending_approval_at_cutoff', '减：截止时尚未审批'), ('valid_orders_at_cutoff', '= 有效购买')]
    st.dataframe(pd.DataFrame([{'口径': name, '订单': rec[k]['orders'], '明细行': rec[k]['item_lines'], '商品金额 USD': float(rec[k]['merch_usd']),
                                '运费 USD': float(rec[k]['shipping_usd'])} for k, name in keys]), hide_index=True,
                 column_config={'商品金额 USD': st.column_config.NumberColumn(format='%.2f'), '运费 USD': st.column_config.NumberColumn(format='%.2f')})
    st.markdown(f"- {rec['difference_explained']}")
    st.markdown(f"- 只算已送达的敏感性对照：商品金额为有效口径的 {rec['delivered_only_sensitivity']['share_of_valid_merch']:.1%}；本项目采用“已审批”口径。")
    st.markdown(f"- 支付：{rec['payments']['note']}")

with t5:
    st.markdown(f"**插补**：{cln['imputation']}")
    st.dataframe(pd.DataFrame([{'字段': k, '空值': v['nulls'], '处理': v['rule']} for k, v in cln['missing_policy'].items()]), hide_index=True)
    d = cln['duplicates']
    st.markdown(f"- 完全重复行删除 {d['exact_duplicate_rows_removed']}；主键重复隔离 {d['primary_key_duplicates_quarantined']}。\n"
                f"- 同单重复商品 {d['same_product_repeated_lines_kept']} 行：{d['same_product_rule']}\n- 同客户同日多单：{d['same_customer_same_day_orders']}")
    cc = cln['customer_coverage']
    st.markdown(f"- 客户覆盖：未知客户的订单 {cc['unknown_customer_orders']}。{cc['rule']}")

with t6:
    names = {m['id']: f"{m['name']}（{m['id']}）" for m in metrics['metrics']}
    pick = st.selectbox('选择指标', list(names), format_func=names.get)
    m = next(x for x in metrics['metrics'] if x['id'] == pick)
    labels = {'definition': '定义', 'unit': '单位', 'population': '对象', 'inclusions': '包含', 'exclusions': '排除', 'numerator': '分子',
              'denominator': '分母', 'windows': '时间窗', 'zero_null_policy': '空值与零', 'supported_dimensions': '可用维度'}
    for k, lab in labels.items():
        if m.get(k) not in (None, '', []):
            st.markdown(f"**{lab}**：{', '.join(m[k]) if isinstance(m[k], list) else m[k]}")
    st.caption(f"口径版本 {metrics['rule_version']}（{metrics['status']}），唯一维护位置 contracts/metrics.json；详细规则见 docs/transaction_rules.md。")

with t7:
    if not issues:
        st.info('问题样本尚未生成：运行 `.venv/bin/python src/retail_bi/ui/issue_samples.py`。')
    else:
        if info and issues['release'] != info['version']:
            st.warning(f"问题样本来自发布 {issues['release']}，当前发布为 {info['version']}，请重新生成。")
        st.caption(f"样本来自发布 {issues['release']} 的只读离线抽取；不显示客户编号和客户属性。订单号为合成编号。")
        for k, v in issues['issues'].items():
            extra = f"（{v['extra_lines']} 行额外明细，{v['groups']} 组）" if 'extra_lines' in v else ''
            with st.expander(f"{v['label']} — {v['count']:,} 单{extra}"):
                st.dataframe(pd.DataFrame(v['samples']), hide_index=True)
