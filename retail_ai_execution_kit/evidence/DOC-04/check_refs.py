"""DOC-04 mechanical check of docs/reference_registry.md against the saved source records.
usage: python3 evidence/DOC-04/check_refs.py"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
reg = (ROOT / 'docs/reference_registry.md').read_text(encoding='utf-8')
src = ROOT / 'evidence/DOC-04/sources'
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, '' if cond else detail)


rows = re.findall(r'^\| \[(\d+)\] \| (.+?) \| (.+?) \|$', reg, re.M)
check('14 academic entries in the registry table', len(rows) == 14 and [int(r[0]) for r in rows] == list(range(1, 15)), len(rows))
check('at least 11 entries (course rule 10+, project 11+)', len(rows) >= 11)
levels = [r[2] for r in rows]
check('every entry has a reading level; none claims full text', all(l.startswith(('已读摘要', '已核元数据')) for l in levels) and '已读全文' not in ''.join(levels), levels)
dois = {int(n): re.search(r'DOI: (\S+?)\.?\s*$', t).group(1) for n, t, _ in rows if 'DOI:' in t}
check('DOIs only where a source record exists: [1]-[6], [10], [12], [14]', sorted(dois) == [1, 2, 3, 4, 5, 6, 10, 12, 14], sorted(dois))
norm = lambda s: re.sub(r'[^a-z0-9一-鿿]', '', s.lower())  # noqa: E731
for n, d in dois.items():
    f = src / (d.replace('/', '_') + '.json')
    if not f.exists():
        f = next(src.glob(d.split('/')[0] + '_*' + d.split('/')[1][-6:] + '*.json'), None) or f
    m = json.loads(f.read_text())['message'] if f.exists() else {}
    t = next(t for k, t, _ in rows if int(k) == n)
    yr = str((m.get('published-print') or m.get('published-online') or m.get('issued') or {'date-parts': [[0]]})['date-parts'][0][0])
    ttl = m.get('title', [''])[0]
    title_ok = norm(ttl)[:25] in norm(t) or (n == 12 and '基于深度学习的SQL生成研究综述' in t)
    check(f'[{n}] DOI {d}: Crossref record exists, title and year match', m.get('DOI', '').lower() == d.lower() and yr in t and title_ok, (yr, ttl[:50]))
meta = json.loads((src / 'page_metadata.json').read_text(encoding='utf-8'))
for n, key, pages in ((7, 'lightgbm', None), (8, 'rag', '9459-9474'), (10, 'bird', '42330-42357'), (11, 'spider2', '28691-28735')):
    t = next(t for k, t, _ in rows if int(k) == n)
    m = meta[key]
    check(f'[{n}] proceedings page: title matches; pages as recorded', norm(m['citation_title'][0])[:25] in norm(t) and
          (pages is None and not m['firstpage'] or pages == f"{m['firstpage'][0]}-{m['lastpage'][0]}" and pages in t))
check('[9] ReAct: ICLR 2023 from OpenReview', 'Eleventh International Conference on Learning Representations' in meta['react']['conference'][0] and 'ICLR' in rows[8][1])
check('[13] 郭先会 2024 57(9): 873-879 from the journal site', '57(09):873-879' in meta['guo2024']['shown'] and '57(9): 873-879' in rows[12][1])
check('[12] no unverified end page', '1363-.' in rows[11][1] and '1392' not in rows[11][1])
body = reg.split('## 2. 文献综述', 1)[1].split('## 3.', 1)[0]
cited = {int(x) for x in re.findall(r'\[(\d+)\]', body)}
check('every entry is cited in the review text', cited == set(range(1, 15)), sorted(set(range(1, 15)) - cited))
for theme in ('RFM 与客户价值', '复购预测、类别不平衡与挽回', '自然语言查询数据库（NL2SQL）', '检索增强与工具代理'):
    check(f'theme section present: {theme}', theme in body)
check('each theme states what the project adopted and its limits', body.count('**本项目采用**') >= 5 and body.count('**限制**') >= 5)
check('official docs and data cards listed separately, not counted', '## 3. 官方技术资料与数据卡（不计入学术文献）' in reg)
print(f'{sum(ok)}/{len(ok)} checks passed')
sys.exit(0 if all(ok) else 1)
