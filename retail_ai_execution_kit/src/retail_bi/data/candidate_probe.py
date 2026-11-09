"""Read-only, standalone probe for the supplied synthetic teaching dataset.

Run with .venv/bin/python; this is not an installed retail_bi API/package.
No source writes, extraction, network access or business label construction.
"""
from __future__ import annotations
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import zipfile
import pandas as pd

TABLES = ('customers', 'products', 'reviews', 'orders', 'calendar', 'payments',
          'sellers', 'order_items', 'seller_products', 'shipping')
CUTOFF = pd.Timestamp('2026-11-08T00:00:00Z')


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def read_csv(blob):
    for encoding in ('utf-8-sig', 'cp1252'):
        try:
            df = pd.read_csv(io.BytesIO(blob), encoding=encoding, dtype='string')
            if df.empty or not df.columns.is_unique:
                raise ValueError('Empty CSV or repeated column header')
            return df, encoding
        except UnicodeDecodeError:
            continue
    raise ValueError('Cannot decode CSV')


def dates(series):
    # Source timestamps have no timezone: UTC is inherited preparation convention,
    # not a claim that the generator supplied timezone-aware business events.
    return pd.to_datetime(series, format='mixed', utc=True, errors='coerce')


def scalar(value, typ):
    if pd.isna(value):
        return None
    if typ in ('float', 'integer'):
        return str(Decimal(str(value)).normalize())
    if typ == 'boolean':
        return str(value).lower()
    if typ in ('date', 'datetime'):
        return pd.Timestamp(dates(pd.Series([value])).iloc[0]).isoformat()
    return str(value)


def profile(df, blob, location, dictionary):
    cols = []
    for col in df:
        typ = dictionary.get(col, {}).get('data_type', 'string')
        s = df[col]; nonnull = s.dropna(); bad = 0
        entry = {'name': col, 'declared_type': typ, 'loaded_dtype': str(s.dtype),
                 'null_count': int(s.isna().sum()), 'distinct_nonnull': int(s.nunique())}
        if typ in ('integer', 'float'):
            for val in nonnull:
                try:
                    n = Decimal(val)
                    bad += int(not n.is_finite() or (typ == 'integer' and n != n.to_integral_value()))
                except InvalidOperation:
                    bad += 1
        elif typ == 'boolean':
            bad = int((~nonnull.str.lower().isin(['true', 'false'])).sum())
        elif typ in ('date', 'datetime'):
            dt = dates(s); bad = int((s.notna() & dt.isna()).sum())
            entry.update(minimum=dt.min().isoformat() if dt.notna().any() else None,
                         maximum=dt.max().isoformat() if dt.notna().any() else None,
                         samples=nonnull.head(3).tolist(),
                         timezone_in_source='naive_or_unspecified',
                         at_or_after_cutoff=int((dt >= CUTOFF).sum()))
        entry['invalid_declared_type_count'] = bad
        cols.append(entry)
    return {'location': location, 'bytes': len(blob), 'sha256': digest(blob),
            'encoding': 'see encoding field', 'rows': len(df), 'columns': cols,
            'scope': 'all_rows_all_columns'}


def checks(tables):
    out = {}
    def check(name, value):
        out[name] = int(value)
    keys = {'customers':['customer_id'], 'products':['product_id'], 'orders':['order_id'],
            'sellers':['seller_id'], 'seller_products':['seller_product_id'],
            'order_items':['order_id','order_item_id'], 'payments':['order_id','payment_sequential'],
            'shipping':['order_id'], 'reviews':['review_id'], 'calendar':['date']}
    for table, fields in keys.items():
        df=tables[table]
        check('duplicate_key:'+table, df.duplicated(fields).sum())
        check('null_key:'+table, df[fields].isna().any(axis=1).sum())
    links = [('orders','customer_id','customers','customer_id'),
             ('order_items','order_id','orders','order_id'),
             ('order_items','product_id','products','product_id'),
             ('order_items','seller_id','sellers','seller_id'),
             ('order_items','seller_product_id','seller_products','seller_product_id'),
             ('seller_products','seller_id','sellers','seller_id'),
             ('seller_products','product_id','products','product_id')]
    links += [(x,'order_id','orders','order_id') for x in ('payments','shipping','reviews')]
    for table, col, parent, key in links:
        check('orphan:'+table+'.'+col, (~tables[table][col].isin(tables[parent][key])).sum())
    items=tables['order_items']; payments=tables['payments']; orders=tables['orders']
    check('orders_without_items', (~orders.order_id.isin(items.order_id)).sum())
    check('orders_without_payments', (~orders.order_id.isin(payments.order_id)).sum())
    for col in ('item_price_usd','shipping_cost_usd','item_total_usd'):
        check('negative:'+col, items[col].map(Decimal).lt(0).sum())
    expected = items.item_price_usd.map(Decimal) + items.shipping_cost_usd.map(Decimal)
    check('item_total_mismatch_exact_decimal', (expected != items.item_total_usd.map(Decimal)).sum())
    subtotal=items.assign(value=items.item_total_usd.map(Decimal)).groupby('order_id').value.sum()
    paid=payments.assign(value=payments.payment_value_usd.map(Decimal)).groupby('order_id').value.sum()
    check('payment_total_mismatch_exact_decimal', sum(subtotal[k]!=paid.get(k,Decimal(0)) for k in subtotal.index))
    listing=tables['seller_products'].set_index('seller_product_id')
    for col in ('seller_id','product_id'):
        check('listing_link_mismatch:'+col, (items[col]!=items.seller_product_id.map(listing[col])).fillna(True).sum())
    purchase=orders.set_index('order_id').order_purchase_timestamp.map(lambda s: pd.Timestamp(s,tz='UTC'))
    customer_created=tables['customers'].set_index('customer_id').created_at
    check('purchase_before_customer_created', (dates(orders.order_purchase_timestamp)<dates(orders.customer_id.map(customer_created))).sum())
    for parent, key, field in [('products','product_id','created_at'),('seller_products','seller_product_id','listing_created_at')]:
        created=tables[parent].set_index(key)[field]
        check('purchase_before:'+parent, (items.order_id.map(purchase)<dates(items[key].map(created))).sum())
    return out


def normalized_rows(df, dictionary):
    normalized = df.copy()
    for col in df:
        typ = dictionary.get(col, {}).get('data_type', 'string')
        if typ in ('date', 'datetime'):
            parsed = dates(df[col])
            normalized[col] = parsed.map(lambda x: None if pd.isna(x) else x.isoformat())
        else:
            normalized[col] = df[col].map(lambda x: scalar(x, typ))
    return Counter(normalized.itertuples(index=False, name=None))


def probe(source):
    files={str(p.relative_to(source)):digest(p.read_bytes()) for p in sorted(source.rglob('*')) if p.is_file()}
    zip_path=source/'01_source/baseline_10000_seed42.zip'; raw={}; records={}; all_blobs={}
    with zipfile.ZipFile(zip_path) as z:
        if z.testzip() is not None: raise ValueError('ZIP CRC failure')
        for n in z.namelist():
            if n.startswith('__MACOSX/') or not n.endswith('.csv'):continue
            name=Path(n).stem
            if name in raw: raise ValueError('Duplicate table member: '+name)
            blob=z.read(n);raw[name],enc=read_csv(blob);all_blobs[name]=(blob,n,enc)
    if set(raw)!=set(TABLES)|{'data_dictionary','simulation_metadata'}:
        raise ValueError('Unexpected or missing ZIP tables')
    dictionary={}
    for row in raw['data_dictionary'].to_dict('records'):
        dictionary.setdefault(row['table_name'],{})[row['column_name']]=row
    hist={}
    for name,df in raw.items():
        blob,n,enc=all_blobs[name];rec=profile(df,blob,str(zip_path)+'::'+n,dictionary.get(name,{}));rec['encoding']=enc;records['raw:'+name]=rec
    for name in TABLES:
        p=source/'02_historical_utf8'/f'{name}.csv';blob=p.read_bytes();df,enc=read_csv(blob);hist[name]=df
        rec=profile(df,blob,str(p),dictionary[name]);rec['encoding']=enc;records['historical:'+name]=rec
    ids=set(raw['orders'].loc[dates(raw['orders'].order_purchase_timestamp)<CUTOFF,'order_id'])
    comparison={}
    for name in TABLES:
        df=raw[name]
        if name in ('orders','order_items','payments','reviews','shipping'):df=df.loc[df.order_id.isin(ids)]
        if name=='calendar':df=df.loc[dates(df.date)<CUTOFF]
        if list(df.columns)!=list(hist[name].columns):raise ValueError('Changed columns: '+name)
        a=normalized_rows(df,dictionary[name]);b=normalized_rows(hist[name],dictionary[name])
        comparison[name]={'expected_rows':len(df),'actual_rows':len(hist[name]),'missing_rows':sum((a-b).values()),'unexpected_rows':sum((b-a).values())}
    differences={}
    for name in TABLES:
        key = {'customers':'customer_id', 'sellers':'seller_id'}.get(name)
        if not key: continue
        a=raw[name].set_index(key); b=hist[name].set_index(key)
        details={}
        for col in a:
            mask=a[col].fillna('')!=b[col].fillna('')
            if mask.any():
                details[col]={'changed_rows':int(mask.sum()),'leading_zero_loss_rows':int((mask & a[col].str.startswith('0').fillna(False) & (a[col].str.lstrip('0')==b[col].str.lstrip('0')).fillna(False)).sum())}
        differences[name]=details
    raw_checks=checks(raw);hist_checks=checks(hist)
    assertions={'zip_crc_passed':True,'history_matches_declared_order_cutoff':all(v['missing_rows']==v['unexpected_rows']==0 for v in comparison.values()),'raw_keys_links_amounts_temporal_order_checks_zero':not any(raw_checks.values()),'historical_keys_links_amounts_temporal_order_checks_zero':not any(hist_checks.values()),'source_unchanged':files=={str(p.relative_to(source)):digest(p.read_bytes()) for p in sorted(source.rglob('*')) if p.is_file()}}
    return {'dataset':'Synthetic Dataset Generator baseline_10000_seed42','source_is_synthetic':True,'formal_course_approval':'pending_D001_D006','currency':'USD','scope':'complete_local_ZIP_12_CSV_and_historical_10_CSV; no UCI download or audit of other candidates; derived RFM and publisher validation prose not substantively verified','cutoff_exclusive_assumed_utc':CUTOFF.isoformat(),'source_timezone':'timestamps lack offset; UTC is preparation convention, not verified publisher timezone','source_inventory_sha256':files,'zip':{'bytes':zip_path.stat().st_size,'sha256':digest(zip_path.read_bytes())},'metadata':raw['simulation_metadata'].to_dict('records'),'profiles':records,'historical_source_differences':differences,'history_reconstruction':comparison,'raw_checks':raw_checks,'historical_checks':hist_checks,'assertions':assertions,'quantity_field_present':False,'quantity_policy':'order_item_id is line sequence, not quantity; do not assume quantity=1 or compute unit-price sales without frozen contract','limitations':['Synthetic fields do not prove real industry data or real model performance.','Historical order cutoff does not censor later approvals/deliveries/reviews or end-of-period customer/listing attributes; must enforce as_of availability downstream.','No clickstream/cart/ad attribution; preassigned lifecycle/segment labels cannot be prediction truth.','Website ZIP license remains unconfirmed per DATA-01.','Type checks apply generator dictionary to actual values; all values loaded as strings to preserve IDs and precision.']}


def markdown(result):
    p=result['profiles'];lines=['# DATA-02 本地合成数据实读核验','', '全量读取本地 ZIP 的 12 张 CSV 与历史目录的 10 张 CSV；未下载其他候选。数据完全合成，用户已授权先行开发，教师 D001/D006 仍待确认。','', '| 表 | 原始行数 | 历史行数 | 列数 |','|---|---:|---:|---:|']
    for n in TABLES:lines.append(f"| {n} | {p['raw:'+n]['rows']} | {p['historical:'+n]['rows']} | {len(p['historical:'+n]['columns'])} |")
    lines+=['','## 核验结果','',f"- 断言：`{json.dumps(result['assertions'],ensure_ascii=False)}`。",f"- 原始 ZIP：{result['zip']['bytes']} 字节；SHA-256 `{result['zip']['sha256']}`。",'- 主键、外键、明细与上架商品/商家一致性、金额（Decimal 精确对账）、购买不早于客户/商品/上架创建的异常计数见 JSON；不把脚本退出 0 当全部业务口径正确。','- 历史 CSV 与按既有下单截止时间从原包重建的记录逐行多重集比较，含重复次数；原始目录读取前后哈希一致。差异详情见下面，不能据此宣称历史目录无损。',f"- 已发现字段转换差异：`{json.dumps(result['historical_source_differences'],ensure_ascii=False)}`。客户/商家邮编前导零丢失，不能直接视为无损导入；后续从原始 ZIP 按字符串重新导入并重建历史层，不在本阶段修改原包。",'', '## 字段与时间','', '- 有订单/客户/商品/商家标识、商品金额/运费/支付金额；USD。没有独立数量列，order_item_id 是明细序号，不能把它当数量，也不擅自补 quantity=1。','- 不以日期拆列、scenario_name 或模拟生命周期标签凑有效业务字段。跨订单、客户、商品、明细有超过8个有意义的模拟源字段，是否满足课程“真实原始数据”仍待教师确认。','- 源时间戳没有时区；既有历史处理将其按 UTC 解释，本轮沿用以复算，不认定为发布者已声明时区。','- 历史下单截止不代表其他信息截至观察时点可得：实际审批、发货、收货、评价需按可得时点截断。预计送达日期是计划值，晚于截止本身不等于泄漏，还需验证其生成/可得时点。','', '| 表.字段 | 最早 | 最晚 | 空值 | 非空解析失败 | 截止后/含截止 |','|---|---|---|---:|---:|---:|']
    for name,rec in p.items():
        if not name.startswith('historical:'):continue
        for c in rec['columns']:
            if c['declared_type'] in ('date', 'datetime'):lines.append(f"| {name.split(':')[1]}.{c['name']} | {c['minimum']} | {c['maximum']} | {c['null_count']} | {c['invalid_declared_type_count']} | {c['at_or_after_cutoff']} |")
    lines+=['','## 范围和限制','']+['- '+v for v in result['limitations']]
    lines+=['','## 复现','', '`.venv/bin/python src/retail_bi/data/candidate_probe.py --source ../ecommerce-sample-database-100k --out reports/data`','', '脚本只读源文件；输出为 JSON 与本报告。字段逐列类型、缺失、不同值数量、日期样本、字节数与哈希均见 candidate_probe.json。读取/解析异常非零退出；默认退出0仅表示探查报告成功生成，数据问题仍保留在 assertions 中。--strict 在任何数据断言不通过时返回1；日志均保留。此脚本独立按路径执行，尚未建立可安装的 retail_bi 公共包，暂不改环境锁；在后续接口实现时再完成包安装与环境复核。']
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--strict',action='store_true');args=parser.parse_args()
    if args.source.resolve()==args.out.resolve() or args.source.resolve() in args.out.resolve().parents:raise ValueError('Output must be outside source pack')
    result=probe(args.source);args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'candidate_probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (args.out/'candidate_probe.md').write_text(markdown(result))
    print(json.dumps({'assertions':result['assertions'],'raw_rows':{k:v['rows'] for k,v in result['profiles'].items() if k.startswith('raw:')},'historical_rows':{k:v['rows'] for k,v in result['profiles'].items() if k.startswith('historical:')}},ensure_ascii=False,indent=2))
    raise SystemExit(1 if args.strict and not all(result['assertions'].values()) else 0)


if __name__=='__main__':main()
