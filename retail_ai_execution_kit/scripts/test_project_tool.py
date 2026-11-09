"""Regression checks for governance only; fixtures are not course evidence."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT=Path(__file__).with_name('project.py')
spec=importlib.util.spec_from_file_location('project_tool',SCRIPT)
tool=importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class GovernanceChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        (self.root/'project').mkdir()
        self.task={'id':'GOV-01','title':'synthetic fixture','phase':'proposal','category':'GOV',
          'selected':True,'priority':'core','status':'todo','owner':None,'reviewer':None,'review_mode':None,
          'requirements':['C01'],'depends_on':[],'outputs':['out.txt'],'acceptance':['Fixture check'],
          'allowed_scope':['.'],'evidence':[],'blocker':None,'skip_reason':None,'execution_required':False}
        self.ledger={'tasks':[self.task]}
        self.write('project/requirements.json',{'requirements':[{'id':'C01','kind':'teacher_required'}]})
        self.save()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self,path,value):
        p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(value),encoding='utf-8')

    def save(self):
        self.write('project/tasks.json',self.ledger)

    def errors(self):
        return tool.validate(self.root)[2]

    def complete_fixture(self):
        for name in ('in.txt','out.txt'):
            (self.root/name).write_text('synthetic governance regression fixture',encoding='utf-8')
        def record(name):
            return {'path':name,'sha256':hashlib.sha256((self.root/name).read_bytes()).hexdigest()}
        self.proof={'task_id':'GOV-01','verification_status':'passed','method':'inspection',
          'performed_at':'synthetic fixture timestamp','actor':'unittest fixture','environment':{'test_only':True},
          'summary':'Synthetic fixture for checker behavior, not actual course work',
          'steps':['Construct fixture and inspect its content'], 'inputs':[record('in.txt')],
          'artifacts':[record('out.txt')], 'acceptance_results':[{'criterion':1,'status':'passed','finding':'Fixture matches'}]}
        rdoc=json.loads((self.root/'project/requirements.json').read_text())
        self.proof['task_spec_sha256']=tool.task_spec_hash(self.task,{r['id']:r for r in rdoc['requirements']})
        self.write('evidence/GOV-01/run.json',self.proof)
        self.task.update(status='done',owner='fixture',reviewer='fixture',review_mode='self_review',evidence=['evidence/GOV-01/run.json'])
        self.save()

    def test_initial_ledger_valid_but_not_done(self):
        self.assertEqual([],self.errors())
        self.assertEqual(['GOV-01'],[t['id'] for t in tool.next_tasks(self.ledger['tasks'])])

    def test_done_without_evidence_rejected(self):
        self.task.update(status='done',owner='fixture',reviewer='fixture',review_mode='self_review')
        self.save()
        self.assertTrue(any('无证据' in e for e in self.errors()))

    def test_real_file_hash_fixture_accepted(self):
        self.complete_fixture()
        self.assertEqual([],self.errors())

    def test_changed_input_invalidates_evidence(self):
        self.complete_fixture()
        (self.root/'in.txt').write_text('changed')
        self.assertTrue(any('证据失效' in e for e in self.errors()))

    def test_not_run_cannot_pass(self):
        self.complete_fixture()
        self.proof['verification_status']='not_run'
        self.write('evidence/GOV-01/run.json',self.proof)
        self.assertTrue(any('不是passed' in e for e in self.errors()))

    def test_runtime_task_cannot_use_only_inspection(self):
        self.complete_fixture()
        self.task['execution_required']=True;self.save()
        self.assertTrue(any('静态审阅不足' in e for e in self.errors()))

    def test_missing_acceptance_result_rejected(self):
        self.complete_fixture()
        self.proof['acceptance_results']=[]
        self.write('evidence/GOV-01/run.json',self.proof)
        self.assertTrue(any('缺少通过证据' in e for e in self.errors()))

    def test_dependency_cycle_rejected(self):
        other=deepcopy(self.task);other['id']='GOV-02';other['depends_on']=['GOV-01']
        self.task['depends_on']=['GOV-02'];self.ledger['tasks'].append(other);self.save()
        self.assertTrue(any('依赖环' in e for e in self.errors()))

    def test_rewording_acceptance_invalidates_old_evidence(self):
        self.complete_fixture()
        self.task['acceptance'][0]='Different required behavior';self.save()
        self.assertTrue(any('验收规格已变化' in e for e in self.errors()))

    def test_output_must_be_bound_not_just_log(self):
        self.complete_fixture()
        self.proof['artifacts']=deepcopy(self.proof['inputs'])
        self.write('evidence/GOV-01/run.json',self.proof)
        self.assertTrue(any('产物未被当前证据哈希绑定' in e for e in self.errors()))

    def test_execution_requirement_cannot_be_omitted(self):
        del self.task['execution_required'];self.save()
        self.assertTrue(any('execution_required必须存在' in e for e in self.errors()))

    def test_outside_evidence_path_rejected(self):
        self.complete_fixture();self.task['evidence']=['../not-allowed.json'];self.save()
        self.assertTrue(any('不在指定目录' in e for e in self.errors()))

    def test_gate_reports_initial_blocked(self):
        r=subprocess.run([sys.executable,str(SCRIPT),'--root',str(self.root),'gate','proposal-ready'],capture_output=True,text=True)
        self.assertEqual(2,r.returncode)
        self.assertEqual('blocked',json.loads(r.stdout)['result'])


if __name__=='__main__':
    unittest.main()
