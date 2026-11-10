"""Rebuild isolated engineering data from the verified synthetic ZIP.

Standalone path entry point; formal dataset approval and metric contracts pending.
No source extraction/writes, no public package/dependency changes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import zipfile
import pandas as pd
from candidate_probe import TABLES, read_csv, dates, checks

VERSION = 'engineering-import-v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_existing(directory):
    manifest=json.loads((directory/'manifest.json').read_text())
    for item in manifest['outputs']:
        p=directory/item['path']
        if not p.is_file() or sha(p)!=item['sha256']:
            raise ValueError('Existing output changed: '+str(p))
    return manifest


def build(source, raw_root, work_root, cutoff, expected):
    source=source.resolve();raw_root=raw_root.resolve();work_root=work_root.resolve()
    pack=source.parent.parent
    for root in (raw_root,work_root):
        if root==pack or pack in root.parents:raise ValueError('Output must be outside source pack')
    cutoff=pd.Timestamp(cutoff)
    if cutoff.tzinfo is None:raise ValueError('Cutoff must include timezone')
    cutoff=cutoff.tz_convert('UTC')
    source_hash=sha(source)
    if source_hash!=expected:raise ValueError('Source checksum mismatch')
    key=source_hash[:16]+'-'+cutoff.strftime('%Y%m%dT%H%M%SZ')+'-'+VERSION
    work_root.mkdir(parents=True,exist_ok=True);raw_root.mkdir(parents=True,exist_ok=True)
    target=work_root/key;lock=work_root/(key+'.lock')
    lock.mkdir()  # exclusive writer; do not steal another writer's lock
    stage=None
    try:
        archive=raw_root/(source_hash+'.zip')
        if archive.exists():
            if sha(archive)!=source_hash:raise ValueError('Archive checksum mismatch')
        else:
            fd,tmp=tempfile.mkstemp(dir=raw_root,suffix='.tmp');os.close(fd)
            try:
                shutil.copyfile(source,tmp)
                if sha(tmp)!=source_hash:raise ValueError('Source changed while archiving')
                try:os.link(tmp,archive)
                except FileExistsError:
                    if sha(archive)!=source_hash:raise ValueError('Conflicting archive')
            finally:Path(tmp).unlink(missing_ok=True)
        if target.exists():
            manifest=verify_existing(target)
            if manifest['source_sha256']!=source_hash or manifest['as_of_exclusive']!=cutoff.isoformat():raise ValueError('Manifest identity mismatch')
            return target,manifest
        tables={};members=[]
        with zipfile.ZipFile(archive) as z:
            if z.testzip() is not None:raise ValueError('ZIP CRC failed')
            for n in z.namelist():
                if n.startswith('__MACOSX/') or not n.endswith('.csv'):continue
                name=Path(n).stem
                if name in tables:raise ValueError('Duplicate member table')
                blob=z.read(n);tables[name],encoding=read_csv(blob)
                members.append({'member':n,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'rows':len(tables[name]),'encoding':encoding})
        if set(tables)!=set(TABLES)|{'data_dictionary','simulation_metadata'}:raise ValueError('Missing/unexpected tables')
        issues=checks(tables)
        if any(issues.values()):raise ValueError('Raw integrity checks failed: '+str(issues))
        # Malformed dates fail rather than disappear under a cutoff.
        dictionary=tables['data_dictionary']
        for row in dictionary.to_dict('records'):
            if row['data_type'] not in ('date','datetime'):continue
            s=tables[row['table_name']][row['column_name']]
            if (s.notna()&dates(s).isna()).any():raise ValueError('Invalid source date')
        selected=tables['orders'].loc[dates(tables['orders'].order_purchase_timestamp)<cutoff].copy()
        if selected.empty:raise ValueError('No historical orders at cutoff')
        ids=set(selected.order_id);history={}
        for name in TABLES:
            df=tables[name]
            if name in ('orders','order_items','payments','shipping','reviews'):df=df.loc[df.order_id.isin(ids)]
            if name=='calendar':df=df.loc[dates(df.date)<cutoff]
            history[name]=df.copy()
        safe_orders=selected[['order_id','customer_id','order_purchase_timestamp','order_approved_at','order_delivered_carrier_date','order_delivered_customer_date']].copy()
        masked={}
        for col in ('order_approved_at','order_delivered_carrier_date','order_delivered_customer_date'):
            mask=dates(safe_orders[col])>=cutoff;masked['orders.'+col]=int(mask.sum());safe_orders.loc[mask,col]=pd.NA
        # Deliberately no valid_purchase/model label: final status history unavailable.
        reviews=history['reviews'];seen=dates(reviews.review_creation_date)<cutoff
        safe_reviews=reviews.loc[seen,['review_id','order_id','review_score','review_creation_date','review_answer_timestamp']].copy()
        mask=dates(safe_reviews.review_answer_timestamp)>=cutoff
        masked['reviews.review_answer_timestamp']=int(mask.sum());safe_reviews.loc[mask,'review_answer_timestamp']=pd.NA
        stage=Path(tempfile.mkdtemp(dir=work_root,prefix=key+'.partial-'))
        outputs=[]
        def write(relative,frame):
            p=stage/relative;p.parent.mkdir(parents=True,exist_ok=True)
            frame.to_csv(p,index=False,encoding='utf-8-sig')
            loaded=pd.read_csv(p,dtype='string',encoding='utf-8-sig')
            if not frame.reset_index(drop=True).equals(loaded):raise ValueError('Roundtrip changed strings: '+relative)
            outputs.append({'path':relative,'sha256':sha(p),'bytes':p.stat().st_size,'rows':len(frame),'columns':list(frame.columns)})
        for name,df in history.items():write('history_source/'+name+'.csv',df)
        write('observed/orders.csv',safe_orders);write('observed/reviews.csv',safe_reviews)
        manifest={'status':'engineering_verified_formal_approval_pending','version':VERSION,'source_sha256':source_hash,'archive':str(archive),'as_of_exclusive':cutoff.isoformat(),'source_timezone':'naive; UTC is explicit engineering assumption','synthetic':True,'currency':'USD','source_members':members,'outputs':outputs,'raw_integrity_exceptions':issues,'excluded_orders':len(tables['orders'])-len(selected),'masked_future_actual_dates':masked,'excluded_unobserved_reviews':int((~seen).sum()),'policy':{'history_source':'Order-cutoff reconstruction preserving ALL original strings. Retains final and future fields; NOT model features.','observed':'Minimal event-dated order/review view; actual dates >= cutoff null; reviews not created before cutoff removed. Score assumed available at review creation for engineering only.','unavailable_features':['final order_status','payments: payment time absent','shipping final outcomes','customer lifecycle/segment','seller/listing end-period flags','estimated delivery: availability time unknown'],'money':'item_price_usd is merchandise line amount, shipping_cost_usd shipping, item_total_usd sum; payment_value_usd reconciles source totals. Not realized revenue, profit or refunds. No quantity field or quantity=1 assumption.','valid_purchase':'Not frozen; no business label or RFM generated. Need synthetic metric draft before warehouse/model.','formal_gate':'D001/D006, DATA-03 and DATA-04 pending; this import is offline engineering preparation.'}}
        (stage/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        if sha(source)!=source_hash:raise ValueError('Source changed during import')
        stage.rename(target);stage=None
        return target,verify_existing(target)
    finally:
        if stage is not None:shutil.rmtree(stage)
        lock.rmdir()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--raw-root',type=Path,required=True);p.add_argument('--work-root',type=Path,required=True);p.add_argument('--cutoff',required=True);p.add_argument('--expected-sha256',required=True)
    a=p.parse_args();target,manifest=build(a.source,a.raw_root,a.work_root,a.cutoff,a.expected_sha256)
    print(json.dumps({'target':str(target),'manifest':manifest},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
