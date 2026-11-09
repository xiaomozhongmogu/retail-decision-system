"""GOV-08 反例：在台账副本上制造违规，检查 validate 是否拒绝。只修改传入的副本目录。"""
import json,sys,hashlib,subprocess,shutil,os
kit,work=sys.argv[1],sys.argv[2]
def fresh():
    if os.path.exists(work): shutil.rmtree(work)
    shutil.copytree(kit,work,ignore=shutil.ignore_patterns('GOV-08','.DS_Store'))
def ledger(fn):
    p=os.path.join(work,'project/tasks.json');d=json.load(open(p,encoding='utf8'))
    fn({t['id']:t for t in d['tasks']});json.dump(d,open(p,'w',encoding='utf8'),ensure_ascii=False,indent=2)
def validate(label):
    r=subprocess.run([sys.executable,os.path.join(kit,'scripts/project.py'),'--root',work,'validate'],capture_output=True,text=True)
    out=json.loads(r.stdout); errs=out.get('errors',[])
    print(f'## {label}\nexit={r.returncode} result={out["result"]} errors={len(errs)}')
    for e in errs: print('  -',e)
    return r.returncode
codes={}
fresh(); codes['BASE']=validate('BASE 未修改的副本')
fresh(); ledger(lambda t:t['GOV-05'].update(status='done',owner='x',reviewer='x',review_mode='self_review'))
codes['NEG1']=validate('NEG1 GOV-05 标 done 但无产物、无证据')
fresh(); open(os.path.join(work,'reports/governance/requirements_review.md'),'a').write('\ntamper\n')
codes['NEG2']=validate('NEG2 GOV-01 证据登记后篡改产物')
fresh(); ledger(lambda t:t['GOV-03'].update(status='in_progress',owner=None))
codes['NEG3']=validate('NEG3 GOV-03 标 in_progress 但无 owner')
fresh()
spec=json.loads(subprocess.run([sys.executable,os.path.join(kit,'scripts/project.py'),'--root',work,'show','GOV-08'],capture_output=True,text=True).stdout)['task_spec_sha256']
out=os.path.join(work,'reports/governance/collaboration_smoke.md');open(out,'w').write('stub\n')
h=hashlib.sha256(open(out,'rb').read()).hexdigest()
os.makedirs(os.path.join(work,'evidence/GOV-08'),exist_ok=True)
ev={"task_id":"GOV-08","verification_status":"passed","method":"inspection","performed_at":"x","actor":"x","summary":"x","environment":{"a":1},"steps":["x"],
 "inputs":[{"path":"AGENTS.md","sha256":hashlib.sha256(open(os.path.join(work,'AGENTS.md'),'rb').read()).hexdigest()}],
 "artifacts":[{"path":"reports/governance/collaboration_smoke.md","sha256":h}],
 "acceptance_results":[{"criterion":i,"status":"passed","finding":"x"} for i in (1,2,3)],"task_spec_sha256":spec}
json.dump(ev,open(os.path.join(work,'evidence/GOV-08/fake.json'),'w'))
ledger(lambda t:t['GOV-08'].update(status='done',owner='x',reviewer='x',review_mode='self_review',evidence=['evidence/GOV-08/fake.json']))
codes['NEG4']=validate('NEG4 GOV-08（execution_required）只用静态审阅证据标 done')
fresh(); ledger(lambda t:t['GOV-01'].update(acceptance=t['GOV-01']['acceptance']+['新增条件']))
codes['NEG5']=validate('NEG5 GOV-01 验收条件被修改，旧证据规格哈希失配')
shutil.rmtree(work)
print(json.dumps(codes))
ok = codes['BASE']==0 and all(codes[k]!=0 for k in codes if k!='BASE')
print('ALL_EXPECTED' if ok else 'UNEXPECTED')
sys.exit(0 if ok else 1)
