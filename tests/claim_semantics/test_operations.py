"""Independent expectations for the native operation semantics, never a mock.

The JSON corpus is authored by hand. Python only compares native results and
transports observations; it does not implement the operation interpreter.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from capcov.operations import execute, OperationError, _spec, _state

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / 'fixtures/operations'
SOURCE = (FIXTURE / 'delete-issue.op').read_text()
CASES = json.loads((FIXTURE / 'cases.json').read_text())['cases']
NATIVE = bool(shutil.which('bifrost') and os.environ.get('BIFROST_SHEN_GO'))
if os.environ.get('CAPCOV_SHEN_REQUIRED') and not NATIVE:
    raise RuntimeError('operation tests require bifrost and BIFROST_SHEN_GO')


def wire_state(rows):
    return [['row', r['table'], r['key'], [[k,v] for k,v in sorted(r['fields'].items())]] for r in rows]


class OperationTransportTests(unittest.TestCase):
    def test_only_data_is_accepted(self):
        for source in ('(system "bad")', '[operation foo]', '[eval "bad"]', '[] []'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                _spec(source)
        # Quotes and executable-looking strings become numbers, not source.
        self.assertNotIn('(system', _spec('[emit-target "(system evil)"]'))
        with self.assertRaises(OperationError):
            _state([{'table':'x','key':'y','fields':{},'hidden':'value'}])

    def test_bounds_and_missing_runtime_fail(self):
        from unittest.mock import patch
        request = CASES[0]['request']
        for timeout in (0, -1, float('nan'), True):
            with self.assertRaises(OperationError): execute(SOURCE, request, timeout=timeout)
        with self.assertRaises(OperationError): _state([request['state'][0]] * 257)
        with patch.dict(os.environ, {'PATH':''}):
            with self.assertRaisesRegex(OperationError, 'unavailable'):
                execute(SOURCE, request)


@unittest.skipUnless(NATIVE, 'real pinned Shen runtime required')
class NativeOperationTests(unittest.TestCase):
    def test_new_fields_keep_canonical_order(self):
        source = '[operation "add-field" [live "issue" "state" "active"] [[named "set" [set-target "issue" "added" "yes"]]]]'
        before = [{'table':'issue','key':'i1','fields':{'state':'active'}}]
        after = [{'table':'issue','key':'i1','fields':{'added':'yes','state':'active'}}]
        result = execute(source, {'state':before,'target':'i1','outcome':'committed',
            'observed':{'state':after,'effects':[['put','issue','i1','added','yes']]}})
        self.assertTrue(result['observed_matches'])

    def test_independent_transition_and_outcome_corpus(self):
        for case in CASES:
            with self.subTest(case=case['name']):
                request = copy.deepcopy(case['request'])
                if 'expected_state' in case:
                    request['observed'] = {'state':case['expected_state'],'effects':case['expected_effects']}
                result = execute(SOURCE, request)
                self.assertEqual(len(result['admissible']), case['alternatives'])
                self.assertEqual(result['basis'], 'bounded-operation-model')
                if 'expected_state' in case:
                    self.assertTrue(result['observed_matches'])
                    self.assertTrue(any(r[1:3] == [wire_state(case['expected_state']),case['expected_effects']]
                                        for r in result['admissible']))
                else:
                    self.assertEqual(result['transition'], ['refused','nonlive'])
                if request['outcome'] == 'unknown':
                    self.assertEqual(result['admissible'][0][1:3], [wire_state(request['state']),[]])

    def test_variant_does_not_authorize_intended_behavior(self):
        intended, deployed = CASES[:2]
        request = copy.deepcopy(intended['request'])
        request['observed'] = {'state':deployed['expected_state'],'effects':deployed['expected_effects']}
        self.assertFalse(execute(SOURCE, request)['observed_matches'])
        request['variant'] = deployed['request']['variant']
        self.assertTrue(execute(SOURCE, request)['observed_matches'])

    def test_order_extra_effect_and_wrong_state_rejected(self):
        case = CASES[0]
        for mutation in ('reordered', 'extra', 'wrong-state'):
            with self.subTest(mutation=mutation):
                request = copy.deepcopy(case['request'])
                request['observed'] = {'state':copy.deepcopy(case['expected_state']),
                                       'effects':copy.deepcopy(case['expected_effects'])}
                obs = request['observed']
                if mutation == 'reordered': obs['effects'].reverse()
                if mutation == 'extra': obs['effects'].append(['emit','unauthorized','i1'])
                if mutation == 'wrong-state': obs['state'][0]['fields']['state'] = 'active'
                self.assertFalse(execute(SOURCE, request)['observed_matches'])

    def test_real_typechecker_and_invalid_data(self):
        for source in (SOURCE.replace('"cascade-files"','"cascade-comments"'),
                       SOURCE.replace('[delete-related "file" "issue_id"]', '[delete-related "file"]')):
            with self.subTest(source=source), self.assertRaises(OperationError):
                execute(source, CASES[0]['request'])
        for change in ('unknown-omission','duplicate-row','missing-event-key'):
            request = copy.deepcopy(CASES[0]['request'])
            if change == 'unknown-omission': request['variant'] = {'divergence':'d-02','omit':['not-an-action']}
            if change == 'duplicate-row': request['state'].append(request['state'][0])
            if change == 'missing-event-key': del request['state'][-1]['fields']['equipment_id']
            with self.subTest(change=change), self.assertRaises(OperationError):
                execute(SOURCE, request)

    def test_may_write_is_an_upper_bound_not_observed_coverage(self):
        request = {'state':[CASES[0]['request']['state'][0]],'target':'i1','outcome':'committed'}
        result = execute(SOURCE, request)
        self.assertEqual(result['analysis'][2], ['may-write',['comment','file','issue']])
        self.assertEqual({e[1] for e in result['transition'][2] if e[0] in ('put','delete')}, {'issue'})
        request['variant'] = CASES[1]['request']['variant']
        deployed = execute(SOURCE, request)
        self.assertEqual(deployed['analysis'][2], ['may-write',['issue']])
        self.assertEqual(deployed['analysis'][3], ['may-emit',['stats-recompute','audit:issue-deleted']])

    def test_transport_unicode_quotes_and_determinism(self):
        key = 'issue-"\\\nλ雪'
        request = {'state':[{'table':'issue','key':key,'fields':{'state':'active'}}],
                   'target':key,'outcome':'committed'}
        a = execute(SOURCE, request)
        b = execute(SOURCE, request)
        self.assertEqual(a, b)
        self.assertEqual(a['transition'][1][0][2],key)
        self.assertEqual(a['transition'][2][-1],['emit','audit:issue-deleted',key])

    def test_trace_rechecks_and_binds_named_actions(self):
        case = CASES[0]
        request = copy.deepcopy(case['request'])
        expected = case['expected_effects']
        steps = [{'name':name,'effects':effects} for name,effects in (
            ('cascade-comments',expected[:1]),('cascade-files',expected[1:2]),
            ('mark-deleted',expected[2:3]),('statistics',expected[3:4]),('audit',expected[4:]))]
        request['trace'] = {'state':case['expected_state'],'effects':expected,'steps':steps}
        self.assertTrue(execute(SOURCE, request)['trace_valid'])
        request['trace']['steps'][0]['name'] = 'some-other-rule'
        self.assertFalse(execute(SOURCE, request)['trace_valid'])

    def test_prolog_finds_first_observable_disagreement(self):
        request = copy.deepcopy(CASES[0]['request'])
        childless = [request['state'][0]]
        request['search'] = {'variant':CASES[1]['request']['variant'],
                             'states':[childless,request['state']]}
        result = execute(SOURCE, request)
        self.assertEqual(result['counterexample'][0],'counterexample')
        self.assertEqual(result['counterexample'][1],wire_state(request['state']))
        request['search']['states'] = [childless]
        self.assertFalse(execute(SOURCE, request)['counterexample'])
        # Empty search is no witness, not a proof of equivalence.
        request['search']['states'] = []
        self.assertFalse(execute(SOURCE, request)['counterexample'])

    def test_cli_uses_exit_code_for_disagreement(self):
        request = copy.deepcopy(CASES[0]['request'])
        request['observed'] = {'state':request['state'],'effects':[]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'input.json'; path.write_text(json.dumps(request))
            proc = subprocess.run([os.sys.executable,'-m','capcov.operations','--spec',str(FIXTURE/'delete-issue.op'),
                                   '--request',str(path)],capture_output=True,text=True,timeout=40)
            self.assertEqual(proc.returncode,1,proc.stderr)
            self.assertFalse(json.loads(proc.stdout)['observed_matches'])
