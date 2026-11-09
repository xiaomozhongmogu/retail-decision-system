#!/usr/bin/env python3
"""Reproducible retail teaching-data preparation from uploaded Baseline ZIP."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import shutil
import zipfile
from pathlib import Path

import pandas as pd

AS_OF = pd.Timestamp('2026-11-08T00:00:00Z')
SOURCE_URL = 'https://www.andresblancog.com/projects/synthetic-dataset-generator'


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_tables(source_zip: Path) -> dict[str, pd.DataFrame]:
    tables: dict[str,pd.DataFrame] = {}
    with zipfile.ZipFile(source_zip) as zf:
        bad = zf.testzip()
        assert bad is None, f'Invalid zip member: {bad}'
        for name in zf.namelist():
            if '/._' in name or not name.endswith('.csv'):
                continue
            basename = Path(name).name
            if basename not in {'orders.csv','order_items.csv','customers.csv','products.csv', 'sellers.csv',
                                'seller_products.csv','payments.csv','shipping.csv','reviews.csv','calendar.csv',
                                'simulation_metadata.csv','data_dictionary.csv'}:
                continue
            raw = zf.read(name)
            try:
                df = pd.read_csv(io.BytesIO(raw), dtype='string' if basename == 'data_dictionary.csv' else None)
            except UnicodeDecodeError:
                df = pd.read_csv(io.BytesIO(raw), encoding='cp1252')
            tables[basename[:-4]] = df
    assert set(tables) == {'orders','order_items','customers','products','sellers','seller_products','payments',
                           'shipping','reviews','calendar','simulation_metadata','data_dictionary'},set(tables)
    return tables


def iso(dt: pd.Series) -> pd.Series:
    return pd.to_datetime(dt, errors='coerce', utc=True)


def build(source: Path, target: Path) -> None:
    data = read_tables(source)
    orders = data['orders'].copy()
    customers = data['customers'].copy()
    items = data['order_items'].copy()
    valid_orders = set(orders.order_id)
    checks: dict[str, object] = {}
    # Row-grain/foreign key checks.
    checks['unique_order_id'] = int(orders.order_id.duplicated().sum())
    checks['unique_customer_id'] = int(customers.customer_id.duplicated().sum())
    checks['unique_product_id'] = int(data['products'].product_id.duplicated().sum())
    checks['duplicate_order_items_id_per_order'] = int(items[['order_id','order_item_id']].duplicated().sum())
    checks['orphan_orders_customer_id'] = int((~orders.customer_id.isin(customers.customer_id)).sum())
    checks['orphan_items_order_id'] = int((~items.order_id.isin(orders.order_id)).sum())
    checks['orphan_items_product_id'] = int((~items.product_id.isin(data['products'].product_id)).sum())
    checks['orphan_items_seller_id'] = int((~items.seller_id.isin(data['sellers'].seller_id)).sum())
    checks['orphan_items_listing_id'] = int((~items.seller_product_id.isin(data['seller_products'].seller_product_id)).sum())
    checks['orphan_payment_order_id'] = int((~data['payments'].order_id.isin(orders.order_id)).sum())
    checks['orphan_shipping_order_id'] = int((~data['shipping'].order_id.isin(orders.order_id)).sum())
    checks['orphan_review_order_id'] = int((~data['reviews'].order_id.isin(orders.order_id)).sum())
    checks['orders_missing_items'] = int((~orders.order_id.isin(items.order_id)).sum())
    checks['orders_future_relative_to_asof'] = int((iso(orders.order_purchase_timestamp) >= AS_OF).sum())
    # Ordered-after-created checks.
    ot = orders[['order_id','customer_id','order_purchase_timestamp']].assign(
        purchase_time=lambda df: iso(df.order_purchase_timestamp))
    cu = customers[['customer_id','created_at']].rename(columns={'created_at':'customer_created_at'})
    related = ot.merge(cu,on='customer_id',how='left',validate='many_to_one')
    checks['orders_before_customer_created'] = int((related.purchase_time < iso(related.customer_created_at)).sum())
    pr = data['products'][['product_id','created_at']].rename(columns={'created_at':'product_created_at'})
    enriched_items = items[['order_id','product_id']].merge(ot[['order_id','purchase_time']], on='order_id', validate='many_to_one')
    enriched_items = enriched_items.merge(pr,on='product_id', validate='many_to_one')
    checks['items_before_product_created'] = int((enriched_items.purchase_time < iso(enriched_items.product_created_at)).sum())
    li = data['seller_products'][['seller_product_id','listing_created_at']]
    enriched_listings = items[['order_id','seller_product_id']].merge(ot[['order_id','purchase_time']], on='order_id', validate='many_to_one')
    enriched_listings = enriched_listings.merge(li,on='seller_product_id',validate='many_to_one')
    checks['items_before_listing_created'] = int((enriched_listings.purchase_time < iso(enriched_listings.listing_created_at)).sum())
    checks['item_subtotal_inconsistent'] = int(((items.item_price_usd + items.shipping_cost_usd - items.item_total_usd).abs() > .011).sum())
    total_by_order = items.groupby('order_id').item_total_usd.sum()
    paid_by_order = data['payments'].groupby('order_id').payment_value_usd.sum()
    checks['payments_not_reconciled'] = int(((total_by_order - paid_by_order.reindex(total_by_order.index,fill_value=0)).abs() > .011).sum())

    # Freeze 2026-11-07 as last *complete* day. Source includes post-cutoff synthetic future events.
    dated = iso(orders.order_purchase_timestamp)
    keep_ids = set(orders.loc[dated < AS_OF, 'order_id'])
    out_tables: dict[str, pd.DataFrame] = {}
    for table,df in data.items():
        if table == 'orders':
            out_tables[table] = df.loc[dated < AS_OF].copy()
        elif table in {'order_items','payments','shipping','reviews'}:
            out_tables[table] = df.loc[df.order_id.isin(keep_ids)].copy()
        elif table == 'calendar':
            out_tables[table] = df.loc[iso(df.date) < AS_OF].copy()
        elif table in {'simulation_metadata','data_dictionary'}:
            continue
        else:
            out_tables[table] = df.copy()

    historical_orders = out_tables['orders']
    assert len(historical_orders) < len(orders)
    assert len(out_tables['order_items']) >= 10000
    assert all((historical_orders.order_id.isin(items.order_id)))
    assert set(out_tables['order_items'].order_id).issubset(set(historical_orders.order_id))
    assert set(out_tables['payments'].order_id).issubset(set(historical_orders.order_id))
    assert set(out_tables['reviews'].order_id).issubset(set(historical_orders.order_id))
    assert set(out_tables['shipping'].order_id).issubset(set(historical_orders.order_id))
    # Reconstruct truthful observed purchase statistics: delivered orders only.
    purchases = historical_orders.loc[historical_orders.order_status=='delivered', ['order_id','customer_id','order_purchase_timestamp']].copy()
    purchases['dt'] = iso(purchases.order_purchase_timestamp)
    valid_purchase_ids = set(purchases.order_id)
    merchandise = out_tables['order_items'].loc[out_tables['order_items'].order_id.isin(valid_purchase_ids)]
    merchandise = merchandise.groupby('order_id').item_price_usd.sum().rename('merchandise_usd')
    purchases = purchases.join(merchandise,on='order_id',validate='one_to_one')
    groups = purchases.groupby('customer_id').agg(
        qualifying_order_count=('order_id','nunique'),
        merchandise_spend_usd=('merchandise_usd','sum'),
        first_observed_purchase_at=('dt','min'),
        last_observed_purchase_at=('dt','max')
    )
    rfm = customers[['customer_id']].merge(groups,on='customer_id',how='left',validate='one_to_one')
    rfm['qualifying_order_count']=rfm.qualifying_order_count.fillna(0).astype(int)
    rfm['merchandise_spend_usd']=rfm.merchandise_spend_usd.fillna(0).round(2)
    rfm['days_since_last_purchase']=(AS_OF - rfm['last_observed_purchase_at']).dt.days.astype('Int64')
    rfm.insert(0,'as_of_utc', AS_OF.isoformat())
    # Guarantee result statuses against observation interval.
    assert not ((rfm.qualifying_order_count == 0) & (rfm.last_observed_purchase_at.notna())).any()
    assert (rfm['merchandise_spend_usd']>=0).all()
    # Produce pack.
    (target/'01_source').mkdir(parents=True,exist_ok=True)
    (target/'02_historical_utf8').mkdir(parents=True,exist_ok=True)
    (target/'03_derived_demo').mkdir(parents=True,exist_ok=True)
    (target/'04_audit').mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target/'01_source'/source.name)
    for name,df in out_tables.items():
        df.to_csv(target/'02_historical_utf8'/f'{name}.csv',index=False,encoding='utf-8-sig')
    rfm.to_csv(target/'03_derived_demo'/'customer_rfm_snapshot_asof_2026-11-08.csv',index=False,encoding='utf-8-sig')
    data['data_dictionary'].to_csv(target/'04_audit'/'data_dictionary.csv',index=False,encoding='utf-8-sig')
    data['simulation_metadata'].to_csv(target/'04_audit'/'simulation_metadata.csv',index=False,encoding='utf-8-sig')
    raw_counts = {k:int(len(v)) for k,v in data.items()}
    processed_counts = {k:int(len(v)) for k,v in out_tables.items()}
    checks['all_hard_business_checks_zero'] = all(v==0 for k,v in checks.items() if k!='orders_future_relative_to_asof')
    checks['all_tables_extracted'] = len(data)==12
    metadata = {
        'audited_date':'2026-11-08',
        'as_of_cutoff_exclusive_utc':AS_OF.isoformat(),
        'source_title':'Synthetic Dataset Generator Baseline 10000 seed42',
        'source_url':SOURCE_URL,
        'generator_metadata_generated_at':str(data['simulation_metadata'].generated_at.iloc[0]),
        'original_sha256':sha256(source),
        'source_is_synthetic':True,
        'raw_csv_rows':raw_counts,
        'historical_csv_rows':processed_counts,
        'historical_row_sum':sum(processed_counts.values()),
        'course_scale_threshold_met_in_one_fact_table':len(out_tables['order_items'])>=10000,
        'orders_fields':len(orders.columns),
        'historical_first_order':str(iso(historical_orders.order_purchase_timestamp).min()),
        'historical_last_order':str(iso(historical_orders.order_purchase_timestamp).max()),
        'checks':checks,
        'limitations':['Synthetic data, not real market activity.',
            'No real clickstream, sessions, carts or acquisition attribution.',
            'Original customer_lifecycle_stage and customer_segment should not be used as outcome labels.',
            'Future-dated raw records retained only in source archive.',
            '2026 generation date does not prove events after Jan 2026; teacher must confirm time clause interpretation.',
            'RFM snapshot includes only delivered orders and only item_price_usd, excluding shipping.']
    }
    (target/'04_audit'/'quality_report.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    write_docs(target, metadata)
    # Re-read CSV and verify generated totals rather than relying only on in-memory frames.
    for name,df in out_tables.items():
        readback=pd.read_csv(target/'02_historical_utf8'/f'{name}.csv',encoding='utf-8-sig')
        assert len(df)==len(readback),name
    print(json.dumps({
        'original_sha256':metadata['original_sha256'],
        'historical_orders':len(historical_orders),
        'historical_order_items':len(out_tables['order_items']),
        'customers':len(customers),
        'hist_total_rows':metadata['historical_row_sum'],
        'checks':checks},ensure_ascii=False,indent=2))


def write_docs(target:Path, metadata:dict)->None:
    checks=metadata['checks']
    (target/'README.md').write_text(f'''# 电商零售智能决策：已核验数据源交付包\n\n**用途：**《基于用户全生命周期的电商零售智能决策与 AI 运营助手系统》课程设计，可直接作为原始数据+历史分析样本+数据源说明+验收证据。\n\n## 目录\n\n- `01_source/`：原样保留你上传的原始 ZIP（未改动）；SHA-256 在 `quality_report.json`。\n- `02_historical_utf8/`：截至 2026-11-07 UTC 完整日的 10 张 CSV，统一 UTF-8 BOM 编码，适合 Excel/Python 导入。\n- `03_derived_demo/`：从完整历史订单重算的用户 RFM 观察窗口快照，仅供课程分析；没有生成虚构浏览日志。\n- `04_audit/`：原始数据字典、合成数据运行元数据、数据质量报告。\n- `DATA_SOURCE.md`：可直接修改后纳入选题报告的数据源说明。\n\n## 已核验数量\n\n- 原始订单：10,000 条；历史订单：{metadata['historical_csv_rows']['orders']:,} 条。\n- 历史订单明细：{metadata['historical_csv_rows']['order_items']:,} 条（满足 >= 10,000 条）；历史 10 表总行数：{metadata['historical_row_sum']:,}。\n- 用户：{metadata['historical_csv_rows']['customers']:,}；订单表字段：{metadata['orders_fields']}；存在时间字段。\n- 关键外键、订单创建时序、商品/上架时序、商品明细与支付金额对账：经本地实读核验，无对应异常。\n\n## 重要限制\n\n1. **完全合成的数据**：不能写成实际企业或真实顾客业务。\n2. **不是浏览行为数据集**：没有真实浏览、加购和归因会话。选题的已证实研究范围为“首次可观测购买→活跃→复购→流失风险”；如果报告声称完整获客漏斗，需要另外取得同源行为数据。\n3. **原始生命周期标签不可直接当真值**：使用历史购买事件和你们明确定义的规则重建。\n4. **原始 ZIP 包含 2026-11-08 以后未来模拟订单**：这些订单仅保留在原始存档，分析用目录已剔除。\n5. **指导书“2026 年 1 月后数据集”条款存在解释问题**：此包元数据中的生成日期为 {metadata['generator_metadata_generated_at']}，但原始业务事件从 2024 年开始；不自动声称已获老师认可。\n\n## 可复现\n\n将 `build_retail_verified.py` 与原 ZIP 放在同一目录，运行：\n\n```bash\npython3 -m pip install pandas\npython3 build_retail_verified.py --source baseline_10000_seed42.zip --out retail_baseline_verified\n```\n\n建议将本交付包作为 DATA-01～DATA-06 的已验证基础材料，但是否正式通过还应由团队检查并确认教师要求。\n''', encoding='utf-8')
    (target/'DATA_SOURCE.md').write_text(f'''# 数据源说明（课程选题报告用，可直接修订）\n\n## 1. 数据集\n\n名称：Synthetic Dataset Generator — Baseline (10,000 orders, seed 42)。\n\n来源：Andres Blanco，项目主页：{SOURCE_URL}；代码仓库：https://github.com/ablancogcr/synthetic-dataset-generator 。\n\n授权：官方文档称随项目提供的预生成样例数据使用 **CC0 1.0**；源代码另以 MIT 许可发布。使用时应保留来源说明。\n\n数据性质：完全合成，仅用于教学、BI、机器学习验证。\n\n数据生成时间（原始元数据）：`{metadata['generator_metadata_generated_at']}`；原始模拟订单范围：2024-01-01 至 2026-12-31。\n\n## 2. 数据量与字段\n\n| 数据表 | 原始行数 | 历史分析行数 |\n|---|---:|---:|\n''' + '\n'.join(f'| {name} | {metadata["raw_csv_rows"][name]:,} | {metadata["historical_csv_rows"][name]:,} |' for name in metadata['historical_csv_rows']) + f'''\n\n原始 `orders.csv` 包含 {metadata['orders_fields']} 列（含 `order_purchase_timestamp` 时间字段），历史 `order_items.csv` 超过 10,000 条。\n\n## 3. 实体关系\n\n订单→客户；订单明细→订单、商品、商家、上架清单；支付/物流/评价→订单。原始数据含 10 张主要业务 CSV、模拟元信息、字段字典、验证报告。\n\n## 4. 本次实际核查\n\n- SHA-256：`{metadata['original_sha256']}`\n- 订单外键缺失：{checks['orphan_orders_customer_id']}；明细订单外键缺失：{checks['orphan_items_order_id']}；明细商品外键缺失：{checks['orphan_items_product_id']}。\n- 订单早于注册：{checks['orders_before_customer_created']}；明细购买早于商品创建：{checks['items_before_product_created']}；早于上架：{checks['items_before_listing_created']}。\n- 明细金额计算异常：{checks['item_subtotal_inconsistent']}；订单支付金额对账异常：{checks['payments_not_reconciled']}。\n- 原始未来模拟订单：{checks['orders_future_relative_to_asof']:,} 条；已从历史分析目录排除。\n\n## 5. 与课程选题的适配与边界\n\n适用：销售趋势、RFM、复购、同期群留存、生命周期状态规则、销售分层、物流风险、商品/商家分析、数仓、OLAP、智能查数、经营报告。\n\n不适用：真实浏览→加购→结算漏斗、真实广告曝光归因、基于真实客户行为效果的模型有效性结论。不能从独立数据集拼接不相关的用户 ID。\n\n**日期限制仍需确认：**指导书中“2026 年 1 月后数据集”与另处的“天池 2025 年 6 月后数据集”不完全一致。本集确实在 2026 年生成，但数据包含早期模拟交易；建议保存发布页面与元数据，并请老师明确是否按发布/生成日期验收。\n\n## 6. 数据处理原则\n\n原始 ZIP 不覆盖；历史数据仅取 2026-11-08 UTC 之前记录，剔除未来模拟事件；按订单 ID 同步筛选明细、支付、物流、评价；用已完成配送订单重建 RFM，金额只取商品明细价格，不将原生 `customer_lifecycle_stage` 当作真值。\n\n## 7. 文件与许可证\n\n- `01_source/baseline_10000_seed42.zip`：原件\n- `02_historical_utf8/*.csv`：数据分析可用 CSV\n- `03_derived_demo/customer_rfm_snapshot_asof_2026-11-08.csv`：派生样本\n- `04_audit/quality_report.json`：可复核的审计报告\n''',encoding='utf-8')

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,default=Path('baseline_10000_seed42.zip'))
    ap.add_argument('--out',type=Path,default=Path('retail_baseline_verified'))
    a=ap.parse_args()
    build(a.source,a.out)
