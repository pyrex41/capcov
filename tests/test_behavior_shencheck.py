"""Negative admission controls for the integrated ShenCheck evidence lane."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from capcov.behaviors import BehaviorError
from capcov.behaviors import shencheck
from capcov.behaviors.qualification import check_plan, execute_checks, qualify
from tests.test_behaviors import fixture


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class ShenCheckIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.identity = {'tlc_sha256':'jar', 'java_sha256':'java'}
        self.sources = {'model':'pinned'}
        self.runner = {'run.py':'runner'}
        for target, value in [('tool_identity', self.identity), ('model_sources', self.sources),
                              ('pins', {'shencheck':{'files':{'formal/effects/run.py':'runner'}}})]:
            mock = patch.object(shencheck, target, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        (self.root/'vor-tests.log').write_text('checked controls')
        report = {'schema':'effects-qualification-v1', 'status':'FINITE_PROTOCOL_VALIDATED',
                  'claims':copy.deepcopy(shencheck.OPEN), 'cases':[], 'model_sources':self.sources,
                  'sources':self.runner, 'vor_tests':{'exit_code':0,'reason':None,'status':'TESTED'},
                  'vor_tests_log_sha256':shencheck.sha(self.root/'vor-tests.log')}
        for mode in shencheck.MODES:
            directory = self.root/mode
            directory.mkdir()
            for name in ['model.json','Effects.tla','Effects.cfg','names.json','tlc.log']:
                (directory/name).write_text('fixture artifact')
            expected = 'FINITE_MODEL_CHECKED' if mode == 'healthy' else 'VIOLATION'
            result = {'schema':'effects-validation-v1','status':expected,'mode':mode,
                'claims':copy.deepcopy(shencheck.OPEN),'sources':self.runner,'model_sources':self.sources,
                'tlc':{'status':expected,'tool_sha256':'jar','java_sha256':'java','violated_property':'Inv0'},
                'properties':{'Inv0':['lit',False]},'model_sha256':'model',
                'reference':{'status':'FINITE_REFERENCE_CHECKED','states':15} if mode=='healthy' else
                  {'status':'VIOLATION','trace':[{'initial':[False]}],'violated_properties':['Inv0']},
                'artifacts':{p.name:shencheck.sha(p) for p in directory.iterdir()}}
            write(directory/'results.json',result)
            report['cases'].append({'mode':mode,'expected':expected,'actual':expected,'matched':True,
                'result_sha256':shencheck.sha(directory/'results.json'),'violated_property':'Inv0'})
        write(self.root/'results.json',report)

    def test_finite_cohort_keeps_counterexamples_and_open_proof_claims(self):
        result = shencheck.assess(self.root, {})
        self.assertEqual(len(result['counterexamples']),4)
        self.assertEqual(result['open_claims'],shencheck.OPEN)
        self.assertIsNone(result['history'])

    def test_unknown_missing_control_and_closed_general_claims_refused(self):
        original = json.loads((self.root/'results.json').read_text())
        variants = [dict(original,status='UNKNOWN'),dict(original,status='FAILED'),
                    dict(original,cases=original['cases'][:-1]),dict(original,claims={})]
        for variant in variants:
            write(self.root/'results.json',variant)
            with self.assertRaises(BehaviorError):
                shencheck.assess(self.root,{})

    def test_wrong_property_is_not_a_successful_mutant(self):
        report = json.loads((self.root/'results.json').read_text())
        mutant = self.root/'mutant-commit/results.json'
        result = json.loads(mutant.read_text())
        result['tlc']['violated_property']='unrelated'
        write(mutant,result)
        report['cases'][1]['violated_property']='unrelated'
        report['cases'][1]['result_sha256']=shencheck.sha(mutant)
        write(self.root/'results.json',report)
        with self.assertRaisesRegex(BehaviorError,'wrong-property'):
            shencheck.assess(self.root,{})

    def test_retained_artifacts_and_observation_are_required(self):
        with self.assertRaises((BehaviorError,OSError)):
            shencheck.assess(self.root,{},require_history=True)
        (self.root/'healthy/tlc.log').write_text('different log')
        with self.assertRaisesRegex(BehaviorError,'modified protocol'):
            shencheck.assess(self.root,{})


class ShenCheckPlanTests(unittest.TestCase):
    def test_enrolled_engine_has_no_silent_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            registry,plan=fixture(root)
            registry['behaviors'][0]['obligations'][0]['method']='model-check'
            c=plan['checks'][0]
            del c['argv']
            c.update(engine=shencheck.ENGINE,method='model-check')
            receipts=execute_checks(registry,plan,root,['publish'],root/'evidence')
            report=qualify(registry,plan,root,['publish'],receipts,root/'evidence')
            self.assertFalse(report['complete'])
            self.assertEqual(receipts[0]['operational'],'operational-failure')
            self.assertTrue(report['invalid_evidence'])
            self.assertEqual(report['engine_evidence'],[])
            c['method']='execution'
            with self.assertRaises(BehaviorError):
                check_plan(plan,registry)

    def test_missing_or_unpinned_source_refused_before_execution(self):
        with self.assertRaises(BehaviorError):
            shencheck.tool_identity(None)
        with tempfile.TemporaryDirectory() as tmp:
            toolchain={'format':'capcov-behavior-toolchain-v1','shencheck_root':tmp,'vor_root':tmp,
                       'tlc_jar':str(Path(tmp)/'jar'),'java':str(Path(tmp)/'java')}
            with self.assertRaises(BehaviorError):
                shencheck.tool_identity(toolchain)
