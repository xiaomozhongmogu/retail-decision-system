"""Write reports/data/dataset_release.json: the stage-1 data package register.
Every path, version and hash is read from the files themselves.
usage: .venv/bin/python evidence/DATA-12/build_release.py
"""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rel(p):
    return str(Path(p).resolve().relative_to(ROOT))


contract = json.loads((ROOT / 'contracts/data_contract.json').read_text(encoding='utf-8'))
metrics = json.loads((ROOT / 'contracts/metrics.json').read_text(encoding='utf-8'))
src_zip = REPO / 'ecommerce-sample-database-100k/01_source/baseline_10000_seed42.zip'
eng = ROOT / 'data/processed/engineering/d50ee64a0478d8ae-20261108T000000Z-engineering-import-v1'
clean = next((ROOT / 'data/processed/clean').glob('*-clean-v2'))
integ = next((ROOT / 'data/processed/integrated').glob('*-integrate-v1'))
trans = next((ROOT / 'data/processed/transformed').glob('*-transform-v1'))
qc = json.loads((ROOT / 'reports/data/quality_checks.json').read_text(encoding='utf-8'))
pa = json.loads((ROOT / 'reports/data/profile_after.json').read_text(encoding='utf-8'))
src_manifest = json.loads((ROOT / 'reports/data/source_manifest.json').read_text(encoding='utf-8'))
tracked = subprocess.run(['git', 'ls-files', '--error-unmatch', str(src_zip)], cwd=REPO, capture_output=True).returncode == 0
ignored = {d: subprocess.run(['git', 'check-ignore', '-q', d], cwd=ROOT).returncode == 0 for d in ['data/raw/', 'data/processed/', 'data/quarantine/']}


def layer(d, kind):
    m = json.loads((d / 'manifest.json').read_text(encoding='utf-8'))
    return {'kind': kind, 'path': rel(d), 'manifest_sha256': sha(d / 'manifest.json'),
            'files': [{'path': o['path'], 'sha256': o['sha256'], 'rows': o.get('rows')} for o in m['outputs']]}


release = {
    'task_id': 'DATA-12', 'release': 'stage1-data-2026-11-10',
    'nature': '完全合成数据（生成器运行 simulation_run_20260721_003414_baseline_seed42）；不是真实企业或顾客',
    'eligibility': {'basis': 'D012 用户授权的工作假设（D013 冻结主数据）', 'teacher_confirmation': '无；不得写成教师已确认'},
    'formal_data': {
        'path': str(src_zip.relative_to(REPO)), 'sha256': sha(src_zip), 'bytes': src_zip.stat().st_size,
        'uncompressed_csv_bytes': sum(m['bytes'] for m in src_manifest['source_members']),
        'storage': '课程私有 GitHub 仓库（visibility=PRIVATE，2026-11-10 用 gh 查询）中的同一文件；本地派生数据被 Git 忽略，按下方命令重建',
        'git_tracked': tracked, 'derived_dirs_git_ignored': ignored,
        'license_note': contract['selected_dataset']['license_note'],
    },
    'versions': {'contract': contract['contract_version'], 'metrics_rules': metrics['rule_version'],
                 'engineering_import': src_manifest['version'], 'clean': clean.name, 'integrated': integ.name, 'transformed': trans.name,
                 'cutoff_exclusive': contract['as_of_exclusive']},
    'layers': [layer(eng, 'engineering import (DATA-05)'), layer(clean, 'clean typed (DATA-07)'),
               layer(integ, 'integrated (DATA-09)'), layer(trans, 'transformed (DATA-10)')],
    'documents': {p: sha(ROOT / p) for p in ['contracts/data_contract.json', 'docs/data_dictionary.md', 'contracts/metrics.json',
                                            'docs/transaction_rules.md', 'docs/preprocessing_methods.md', 'reports/data/dataset_selection.md',
                                            'reports/data/profile_before.md', 'reports/data/profile_after.json', 'reports/data/quality_checks.json',
                                            'reports/data/transaction_reconciliation.json', 'reports/data/integration_audit.json',
                                            'reports/data/transform_audit.json', 'docs/data_readme.md']},
    'course_thresholds': {
        'records': {'rule': '>= 10,000 条记录或 >= 10 MB', 'measured_order_items_rows': pa['rows']['order_items'],
                    'measured_uncompressed_bytes': sum(m['bytes'] for m in src_manifest['source_members']),
                    'satisfied_by': 'records（明细 15,639 行；字节数 7,974,631 未达 10 MB，不以字节数主张）'},
        'fields': {'rule': '>= 8 个有效字段', 'measured': contract['effective_business_field_count']},
        'time': {'field': 'orders.order_purchase_timestamp → purchase_ts', 'coverage': [pa['time']['purchase_first'], pa['time']['purchase_last']],
                 'months': pa['time']['months'], 'timezone': 'UTC 工程假设'},
        'freshness': {'rule': '课程：2026 年 1 月以后 / 2025 年 6 月以后', 'status': '按 D012 用户授权的工作假设视为已确认；模拟事件 2024-01 至 2026-11，生成于 2026-07-21；教师未答复'},
    },
    'quality_gate': {'result': qc['gate'], 'passed': qc['passed'], 'total': qc['total'], 'warnings': qc['warnings']},
    'scope': {'full_or_sample': '全量：冻结研究范围（截止前全部历史），未抽样', 'fixtures': 'tests/data 中的手工夹具只在测试临时目录使用，与正式数据分开'},
    'delivery': {
        'method': '代码、契约、文档、报告和原始 ZIP 在私有仓库中；派生数据不提交，接收者按 docs/data_readme.md 一条命令重建并用哈希核对',
        'public_release': '不公开发布原始或派生数据（C07）',
    },
    'unknowns': [
        '教师是否认可完全合成数据作为课程“原始数据”，以及时效按哪个日期判断（D001/D006，GOV-04）',
        '课程最终提交时的数据交付方式（压缩包、仓库链接或其他），教师没有规定',
        '网站下载件未标明数据许可（同作者同类样例为 CC0）',
        '源时间没有时区（UTC 是工程假设）',
        '其他成员的电脑（Windows 或 Intel）没有验证重建（REL-02）',
    ],
}
(ROOT / 'reports/data/dataset_release.json').write_text(json.dumps(release, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'versions': release['versions'], 'git_tracked': tracked, 'ignored': ignored, 'gate': release['quality_gate']['result']}, ensure_ascii=False))
