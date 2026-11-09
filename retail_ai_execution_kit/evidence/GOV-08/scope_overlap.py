"""列出没有依赖先后关系、且 allowed_scope 有路径重叠的已选任务对；这些任务不能并行写。只读。"""
import json
from collections import defaultdict
T=[t for t in json.load(open('project/tasks.json',encoding='utf8'))['tasks'] if t['selected']]
by={t['id']:t for t in T}
anc=defaultdict(set)
def up(i,seen=None):
    if i in anc and anc[i]: return anc[i]
    s=set()
    for d in by[i]['depends_on']:
        if d in by: s|={d}|up(d)
    anc[i]=s; return s
for t in T: up(t['id'])
def ov(a,b): return a==b or a.startswith(b.rstrip('/')+'/') or b.startswith(a.rstrip('/')+'/')
pairs=[];shared=defaultdict(int)
for i,a in enumerate(T):
    for b in T[i+1:]:
        if a['id'] in anc[b['id']] or b['id'] in anc[a['id']]: continue
        hit=sorted({x for x in a['allowed_scope'] for y in b['allowed_scope'] if ov(x,y)})
        if hit:
            pairs.append((a['id'],b['id'],hit))
            for h in hit: shared[h]+=1
print('selected_tasks',len(T),'unordered_pairs_with_overlap',len(pairs))
print('most_shared_scopes',sorted(shared.items(),key=lambda x:-x[1])[:12])
now=['GOV-03','GOV-05','GOV-08']
print('currently_available',now)
for a,b,h in pairs:
    if a in now and b in now: print(' overlap',a,b,h)
