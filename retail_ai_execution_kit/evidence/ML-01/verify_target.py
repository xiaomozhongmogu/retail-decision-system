"""ML-01 checks: numbers in docs/model_target.md equal the DW-05 label table; required statements present.
usage: .venv/bin/python evidence/ML-01/verify_target.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/retail_bi/warehouse'))
from runtime import open_current  # noqa: E402

doc = (ROOT / 'docs/model_target.md').read_text(encoding='utf-8')
con, ptr = open_current()
ok = []


def check(name, cond, detail=''):
    ok.append(bool(cond))
    print('PASS' if cond else 'FAIL', name, detail)


J = "dws.label_repurchase l JOIN dws.customer_snapshot s USING (customer_id, as_of) WHERE l.label_version = 'label-repurchase-v1' AND s.snapshot_version = 'snapshot-v1'"
for y, snaps, n, pos, rate, cust in con.execute(f"SELECT year(l.as_of), count(DISTINCT l.as_of), count(*), sum(l.y::INT), avg(l.y::INT), count(DISTINCT l.customer_id) FROM {J} AND s.frequency_90d >= 1 GROUP BY 1 ORDER BY 1").fetchall():
    check(f'{y} row in doc', f'| {snaps} | {n:,} | {pos:,} | {rate:.2%} | {cust:,} |' in doc)
tot = con.execute(f"SELECT count(DISTINCT l.as_of), count(*), sum(l.y::INT), avg(l.y::INT), count(DISTINCT l.customer_id) FROM {J} AND s.frequency_90d >= 1").fetchone()
check('total row in doc', f'| {tot[0]} | {tot[1]:,} | {tot[2]:,} | {tot[3]:.2%} | {tot[4]:,} |' in doc)
out = con.execute(f"SELECT count(*), avg(l.y::INT) FROM {J} AND s.frequency_90d = 0").fetchone()
check('out-of-population rows and rate quoted', f'{out[0]:,}' in doc and f'{out[1]:.1%}' in doc, out)
check('population = 90-day buyers, label window [t, t+30d), maturity +31d', '过去 90 天至少一次有效购买的已知客户' in doc and '[as_of, as_of + 30 天)' in doc and 'as_of + 31 天' in doc)
check('risk = 1 - probability, not a second label or permanent churn', '未复购风险 = 1 − 复购概率' in doc and '不另造标签' in doc and '不是永久流失' in doc)
check('dormant customers handled by rules; behaviour-route redefinition stated', '规则队列' in doc and '行为路线' in doc)
check('label window maturity matches the label table', con.execute(f"SELECT count(*) FROM {J} AND l.label_matured_at <> l.as_of + INTERVAL 31 DAY").fetchone()[0] == 0)
con.close()
print(f'{sum(ok)}/{len(ok)} passed')
sys.exit(0 if all(ok) else 1)
