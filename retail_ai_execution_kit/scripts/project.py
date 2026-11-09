#!/usr/bin/env python3
"""Read-only checks plus generated Markdown views for the project task ledger.

This checks records, dependencies and evidence integrity, not business truth.
It never runs command strings contained in task or evidence records.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

STATUSES = {'todo', 'in_progress', 'in_review', 'done', 'blocked', 'stale', 'skipped'}
PHASES = {'proposal': 1, 'midterm': 2, 'final': 3, 'submitted': 4}
GATES = {'proposal-ready': 1, 'midterm-ready': 2, 'final-ready': 3, 'final-submitted': 4}
LABELS = {'GOV':'治理与需求','DATA':'数据准备','DW':'数仓与OLAP','EDA':'业务分析',
          'ML':'分群与预测','AI':'三个AI模块','UI':'Streamlit','DOC':'报告与材料',
          'REL':'复现与交付','BON':'可选扩展'}
SHA_RE = re.compile(r'^[0-9a-f]{64}$')


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def safe_path(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError('路径必须是非空项目相对路径')
    path = (root / value).resolve()
    path.relative_to(root.resolve())
    return path


def file_hash(path: Path, cache: dict) -> str:
    if path not in cache:
        h = hashlib.sha256()
        with path.open('rb') as f:
            for part in iter(lambda: f.read(1024 * 1024), b''):
                h.update(part)
        cache[path] = h.hexdigest()
    return cache[path]


def task_spec_hash(task: dict, requirements: dict) -> str:
    """Bind evidence to task semantics, not mutable owner/status fields."""
    keys=('id','title','phase','requirements','depends_on','outputs','acceptance','execution_required')
    payload={'task':{k:task.get(k) for k in keys},
             'requirements':[requirements[rid] for rid in task.get('requirements',[]) if rid in requirements]}
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def validate(root: Path):
    errors, warnings = [], []
    try:
        ledger = load_json(root / 'project/tasks.json')
        reqdoc = load_json(root / 'project/requirements.json')
        tasks, reqs = ledger['tasks'], reqdoc['requirements']
        if not isinstance(tasks, list) or not isinstance(reqs, list):
            raise ValueError('tasks和requirements必须为数组')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return None, None, [f'无法读取权威台账：{exc}'], warnings
    if not all(isinstance(t, dict) and isinstance(t.get('id'), str) for t in tasks):
        return None, None, ['任务必须为带字符串id的对象'], warnings
    if not all(isinstance(r, dict) and isinstance(r.get('id'), str) for r in reqs):
        return None, None, ['需求必须为带字符串id的对象'], warnings
    counts = Counter(t['id'] for t in tasks)
    errors += [f'重复任务ID：{k}' for k,v in counts.items() if v > 1]
    rcounts = Counter(r['id'] for r in reqs)
    errors += [f'重复需求ID：{k}' for k,v in rcounts.items() if v > 1]
    byid = {t['id']:t for t in tasks}
    rbyid = {r['id']:r for r in reqs}
    coverage = defaultdict(list)
    cache = {}

    for t in tasks:
        tid=t['id']
        if t.get('status') not in STATUSES:
            errors.append(f'{tid}: 未知状态')
        if t.get('phase') not in PHASES:
            errors.append(f'{tid}: 未知阶段')
        if not isinstance(t.get('selected'), bool):
            errors.append(f'{tid}: selected必须为布尔值')
        if type(t.get('execution_required')) is not bool:
            errors.append(f'{tid}: execution_required必须存在且为布尔值')
        for key in ('requirements','depends_on','outputs','acceptance','evidence'):
            if not isinstance(t.get(key), list):
                errors.append(f'{tid}: {key}必须为数组')
        if any(not isinstance(t.get(k),list) for k in ('requirements','depends_on','outputs','acceptance','evidence')):
            continue
        bad_items=False
        for key in ('requirements','depends_on','outputs','acceptance','evidence'):
            if not all(isinstance(v,str) and v.strip() for v in t[key]):
                errors.append(f'{tid}: {key}须为非空字符串数组')
                bad_items=True
        if bad_items:
            continue
        if not t['requirements'] or not t['outputs'] or not t['acceptance']:
            errors.append(f'{tid}: 需求、产物和验收条件不能为空')
        for rid in t['requirements']:
            if rid not in rbyid: errors.append(f'{tid}: 不存在的需求 {rid}')
            else: coverage[rid].append(tid)
        for dep in t['depends_on']:
            if dep not in byid: errors.append(f'{tid}: 不存在的依赖 {dep}')
            elif t.get('selected') and not byid[dep].get('selected'):
                errors.append(f'{tid}: 已选任务依赖未启用任务 {dep}')
            elif dep in byid and PHASES.get(byid[dep].get('phase'),99) > PHASES.get(t.get('phase'),0):
                errors.append(f'{tid}: 依赖 {dep} 的阶段比本任务晚')
        if t.get('priority') == 'core' and (not t.get('selected') or t.get('status') == 'skipped'):
            errors.append(f'{tid}: 核心任务不能直接跳过后仍宣称范围已完成')
        if t.get('status') == 'skipped' and not t.get('skip_reason'):
            errors.append(f'{tid}: skipped须记录原因')
        if t.get('status') == 'blocked' and not t.get('blocker'):
            errors.append(f'{tid}: blocked须记录具体阻塞')
        if t.get('status') in {'in_progress','in_review','done'} and not t.get('owner'):
            errors.append(f'{tid}: 活动/完成任务须记录owner')
        for out in t['outputs']:
            try: safe_path(root,out)
            except (ValueError, TypeError): errors.append(f'{tid}: 非法输出路径 {out!r}')
        if t.get('status') != 'done':
            continue
        if not t.get('reviewer') or t.get('review_mode') not in {'independent','self_review','human','mixed'}:
            errors.append(f'{tid}: done须记录实际reviewer和review_mode；自审不得称独立审查')
        for dep in t['depends_on']:
            if dep in byid and byid[dep].get('status') != 'done':
                errors.append(f'{tid}: 依赖 {dep} 尚未done')
        for out in t['outputs']:
            try:
                p=safe_path(root,out)
                if not p.exists() or (p.is_file() and p.stat().st_size == 0):
                    errors.append(f'{tid}: 缺失或空产物 {out}')
            except (ValueError, TypeError, OSError):
                pass
        if not t['evidence']:
            errors.append(f'{tid}: done但无证据')
        passed=set()
        execution_seen=False
        bound_outputs=set()
        for ref in t['evidence']:
            try:
                p=safe_path(root,ref)
                expected=(root/'evidence'/tid).resolve()
                p.relative_to(expected)
                e=load_json(p)
                if not isinstance(e,dict): raise ValueError('证据须为JSON对象')
            except (ValueError, OSError, TypeError) as exc:
                errors.append(f'{tid}: 证据 {ref} 无法读取或不在指定目录：{exc}')
                continue
            if e.get('task_id') != tid:
                errors.append(f'{tid}: 证据任务ID不匹配 {ref}')
            if e.get('task_spec_sha256') != task_spec_hash(t,rbyid):
                errors.append(f'{tid}: 验收规格已变化或缺少task_spec_sha256，旧证据须重验 {ref}')
            if e.get('verification_status') != 'passed':
                errors.append(f'{tid}: 引用证据不是passed {ref}')
            for field in ('performed_at','actor','summary','environment'):
                if not e.get(field): errors.append(f'{tid}: 证据缺少 {field}: {ref}')
            method=e.get('method')
            if method not in {'command','inspection','interactive','hybrid'}:
                errors.append(f'{tid}: 证据method未知 {ref}')
            if method in {'command','hybrid'}:
                if not e.get('command') or type(e.get('exit_code')) is not int or e['exit_code'] != 0:
                    errors.append(f'{tid}: 执行证据缺实际命令或成功退出码 {ref}')
                else: execution_seen=True
            elif method == 'interactive':
                if not isinstance(e.get('steps'),list) or not e['steps']:
                    errors.append(f'{tid}: 交互证据缺实际步骤 {ref}')
                else: execution_seen=True
            elif method == 'inspection' and (not isinstance(e.get('steps'),list) or not e['steps']):
                errors.append(f'{tid}: 审阅证据缺核验步骤 {ref}')
            for section in ('inputs','artifacts'):
                entries=e.get(section)
                if not isinstance(entries,list) or not entries:
                    errors.append(f'{tid}: 证据 {section} 不能为空 {ref}')
                    continue
                for entry in entries:
                    try:
                        ep=safe_path(root,entry['path']); digest=entry['sha256']
                        if not isinstance(digest,str) or not SHA_RE.fullmatch(digest):
                            raise ValueError('sha256不是实际64位小写十六进制')
                        if not ep.is_file(): raise ValueError('文件不存在')
                        if file_hash(ep,cache) != digest:
                            errors.append(f'{tid}: 证据失效，文件已变更 {entry["path"]}；应审查并标stale')
                        elif section == 'artifacts':
                            bound_outputs.add(ep)
                    except (KeyError, ValueError, TypeError, OSError) as exc:
                        errors.append(f'{tid}: {section}记录无效 {ref}: {exc}')
            results=e.get('acceptance_results',[])
            if not isinstance(results,list):
                errors.append(f'{tid}: acceptance_results必须为数组 {ref}')
                continue
            for row in results:
                if not isinstance(row,dict):
                    errors.append(f'{tid}: 验收结果必须为对象 {ref}'); continue
                index=row.get('criterion')
                if type(index) is not int or not 1 <= index <= len(t['acceptance']):
                    errors.append(f'{tid}: criterion须是1至验收条数的整数 {ref}')
                elif row.get('status') == 'passed' and row.get('finding'):
                    passed.add(index)
                else:
                    errors.append(f'{tid}: 验收条目未通过或无实际finding {ref}')
        missing=set(range(1,len(t['acceptance'])+1))-passed
        if missing: errors.append(f'{tid}: 缺少通过证据的验收条目 {sorted(missing)}')
        for out in t['outputs']:
            try:
                if safe_path(root,out) not in bound_outputs:
                    errors.append(f'{tid}: 任务产物未被当前证据哈希绑定 {out}')
            except (ValueError,TypeError):
                pass
        if t.get('execution_required') and not execution_seen:
            errors.append(f'{tid}: 该任务必须有实际运行/交互证据，静态审阅不足')

    for rid,r in rbyid.items():
        if not coverage[rid]: errors.append(f'需求{rid}没有任何任务覆盖')
        elif r.get('kind') not in {'optional_bonus','optional_extension'} and not any(byid[x].get('selected') for x in coverage[rid]):
            errors.append(f'非可选需求{rid}没有已选任务覆盖')
    visiting,seen=set(),set()
    def dfs(tid):
        if tid in visiting: errors.append(f'依赖环包含 {tid}'); return
        if tid in seen: return
        visiting.add(tid)
        deps=byid[tid].get('depends_on',[])
        if isinstance(deps,list):
            for dep in deps:
                if isinstance(dep,str) and dep in byid: dfs(dep)
        visiting.remove(tid);seen.add(tid)
    for tid in byid: dfs(tid)
    manifest_path=root/'sources/manifest.json'
    if manifest_path.exists():
        try:
            for item in load_json(manifest_path)['files']:
                p=safe_path(root,item['path'])
                if file_hash(p,cache)!=item['sha256']:
                    errors.append(f'课程原件哈希变化：{item["path"]}，需重新核验要求')
        except (ValueError,KeyError,TypeError,OSError) as exc:
            errors.append(f'来源清单无效：{exc}')
    done=sum(t.get('selected') and t.get('status')=='done' for t in tasks)
    if done == 0: warnings.append('当前没有已验收业务任务；计划结构有效不表示课程或系统已完成。')
    warnings.append('机械检查不证明教师答复、原始结果或业务判断真实；必须复核证据内容。')
    return ledger,reqdoc,errors,warnings


def next_tasks(tasks):
    byid={t['id']:t for t in tasks}
    return [t for t in tasks if t['selected'] and t['status'] in {'todo','stale'}
            and not t.get('owner') and all(byid[d]['status']=='done' for d in t['depends_on'])]


def render(root, ledger, reqdoc):
    tasks=ledger['tasks']; reqs=reqdoc['requirements']
    groups=defaultdict(list)
    for t in tasks: groups[t['category']].append(t)
    lines=['# 项目任务清单与逐项验收','',
           '> 生成文件：只修改 project/tasks.json，再运行 python3 scripts/project.py render。',
           '> 文件内的日期是计划截止，勾选只表示任务经证据验收；不代表已经提交或教师评分。','',
           f'共 {len(tasks)} 项：已选核心 {sum(t["selected"] for t in tasks)} 项；未启用扩展 {sum(not t["selected"] for t in tasks)} 项。',
           '', '## 使用方法','',
           '按依赖认领最小可执行任务；每次一个实施者负责指定范围。验收结果写 evidence/<task_id>/，真实状态由协调者写入台账。需要执行的任务不能凭静态检查标done。',
           '', '阶段：proposal=11月9日；midterm=11月30日；final=12月22日前材料就绪；submitted=实际提交及答辩记录。',
           '', '## 总览','', '| ID | 任务 | 阶段 | 状态 | 依赖 |','| --- | --- | --- | --- | --- |']
    for t in tasks:
        lines.append(f'| {t["id"]} | {t["title"]} | {t["phase"]} | {t["status"]} | {", ".join(t["depends_on"]) or "无"} |')
    for category,items in groups.items():
        lines+=['',f'## {category} — {LABELS.get(category,category)}','']
        for t in items:
            lines += [f'### {t["id"]} {t["title"]}','',
                      f'- [{"x" if t["status"]=="done" else " "}] 状态：`{t["status"]}`；阶段：`{t["phase"]}`；范围：{"已选核心" if t["selected"] else "默认关闭的可选项"}。',
                      f'- 依据：{", ".join(t["requirements"])}。',
                      f'- 前置：{", ".join(t["depends_on"]) or "无"}。',
                      f'- 允许修改：{", ".join("`"+p+"`" for p in t["allowed_scope"])}；另可写本任务证据/交接。',
                      f'- 输出：{", ".join("`"+p+"`" for p in t["outputs"])}。',
                      f'- 实际执行要求：{"必须有运行或交互证据" if t.get("execution_required") else "以相应来源核验/文档审阅为主，必要运行另记录"}。',
                      '', '**验收条件**','']
            for i,c in enumerate(t['acceptance'],1): lines.append(f'{i}. {c}')
            if t.get('blocker'): lines += ['',f'**当前阻塞：** {t["blocker"]}']
            if t.get('skip_reason'): lines += ['',f'**未启用原因：** {t["skip_reason"]}']
            lines += ['',f'证据：{", ".join(t["evidence"]) if t["evidence"] else "尚无已登记验收证据。"}','']
    (root/'TASKS.md').write_text('\n'.join(lines).strip()+'\n',encoding='utf-8')
    lines=['# 要求与任务追溯矩阵','',
           '> 生成文件：权威数据为 project/requirements.json；任务状态为 project/tasks.json。',
           '', 'C类来自课程；U类为用户承诺；Q类为项目质量约定；B类为可选加分；X类为可选扩展。teacher_framework按场景选适用方法，teacher_ambiguous保留待解释事项，不能伪称全部为教师硬数值。',
           '', '来源：COURSE=sources/course_guide_2026.docx；TOPIC=sources/topic_report_template.doc。原件哈希见sources/manifest.json。']
    for r in reqs:
        matched=[t for t in tasks if r['id'] in t['requirements']]
        lines+=['',f'## {r["id"]} {r["title"]}','',f'- 分类：`{r["kind"]}`。',f'- 原始依据：{r["source"]}。',
                f'- 要求/解释：{r["rule"]}', f'- 对应任务：{", ".join(t["id"] for t in matched)}。',
                f'- 已验收覆盖任务：{", ".join(t["id"] for t in matched if t["status"]=="done") or "无"}。']
        if r.get('notes'):lines.append(f'- 注意：{r["notes"]}')
    (root/'REQUIREMENTS.md').write_text('\n'.join(lines).strip()+'\n',encoding='utf-8')
    selected=[t for t in tasks if t['selected']]
    counts=Counter(t['status'] for t in selected)
    lines=['# 当前状态','', '> 自动生成；唯一动态任务台账是 project/tasks.json。','',
           f'- 项目状态说明：{ledger.get("state_note", "")}',
           f'- 正式主数据：{ledger.get("active_dataset") or "尚未选定/核验"}。',
           f'- 协调者：{ledger.get("coordinator") or "待本轮实际指定"}。',
           f'- 已选 {len(selected)} 项；done {counts["done"]} 项；blocked {counts["blocked"]} 项；其他未验收 {len(selected)-counts["done"]-counts["blocked"]} 项。',
           '', '## 可认领的下一步','']
    for t in next_tasks(tasks):lines.append(f'- {t["id"]}：{t["title"]}')
    if not next_tasks(tasks):lines.append('无可直接认领项。检查活动任务、阻塞和依赖，不自动启用BON。')
    lines+=['','## 当前阻塞','']
    for t in selected:
        if t['status']=='blocked':lines.append(f'- {t["id"]}：{t.get("blocker")}')
    lines+=['','## 四个关卡','', '| 关卡 | 已验收/需验收任务 | 状态 |','| --- | --- | --- |']
    for gate,rank in GATES.items():
        group=[t for t in selected if PHASES[t['phase']]<=rank]
        complete=sum(t['status']=='done' for t in group)
        lines.append(f'| {gate} | {complete}/{len(group)} | {"仍需运行gate核验当前证据" if complete==len(group) else "未就绪"} |')
    lines+=['', '状态勾选与结构校验不等于已满足教师要求。通过就绪关卡也不等于已提交或已答辩；最终以真实回执和实际结果记录。','']
    (root/'STATUS.md').write_text('\n'.join(lines),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('validate');sub.add_parser('render');sub.add_parser('next')
    sp=sub.add_parser('show');sp.add_argument('task_id')
    gp=sub.add_parser('gate');gp.add_argument('name',choices=GATES)
    args=parser.parse_args()
    root=args.root.resolve()
    ledger,reqdoc,errors,warnings=validate(root)
    if errors:
        print(json.dumps({'result':'invalid','errors':errors,'warnings':warnings},ensure_ascii=False,indent=2))
        return 1
    tasks=ledger['tasks']
    if args.action=='validate':
        result={'result':'ledger_valid','tasks':len(tasks),'requirements':len(reqdoc['requirements']),
                'selected':sum(t['selected'] for t in tasks),'accepted':sum(t['selected'] and t['status']=='done' for t in tasks),'warnings':warnings}
    elif args.action=='render':
        render(root,ledger,reqdoc)
        result={'result':'generated','files':['TASKS.md','REQUIREMENTS.md','STATUS.md'],'warnings':warnings}
    elif args.action=='next':
        result={'result':'available_tasks','tasks':[{k:t[k] for k in ('id','title','phase','depends_on','outputs')} for t in next_tasks(tasks)],
                'active':[t['id'] for t in tasks if t['selected'] and t['status'] in {'in_progress','in_review'}],
                'blocked':[{'id':t['id'],'reason':t['blocker']} for t in tasks if t['selected'] and t['status']=='blocked']}
    elif args.action=='show':
        task=next((t for t in tasks if t['id']==args.task_id),None)
        if task is None:
            print(json.dumps({'result':'unknown_task','task_id':args.task_id},ensure_ascii=False))
            return 1
        rbyid={r['id']:r for r in reqdoc['requirements']}
        result={'task':task,'task_spec_sha256':task_spec_hash(task,rbyid),
                'requirements':[rbyid[rid] for rid in task['requirements']]}
    else:
        group=[t for t in tasks if t['selected'] and PHASES[t['phase']]<=GATES[args.name]]
        unmet=[{'id':t['id'],'status':t['status'],'blocker':t.get('blocker')} for t in group if t['status']!='done']
        result={'result':'blocked' if unmet else 'evidence_records_complete','gate':args.name,'required_tasks':len(group),
                'accepted_tasks':len(group)-len(unmet),'unmet':unmet,
                'note':'完整证据记录仍需业务内容审阅；ready不等于已提交/答辩，也不保证教师评分。'}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if unmet else 0
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    sys.exit(main())
