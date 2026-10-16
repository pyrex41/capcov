"""An authored corpus presented independently to Python and the native authority.

The Shen branch deliberately bypasses Python semantic validation. Native check
identifiers remain in failure messages; only comparison uses common categories.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import unittest
from dataclasses import replace

from capcov.claims.ir import Bundle, bundle_from_json, canonical_json, digest
from capcov.claims.authority import judge, check_witnesses
from capcov.claims.validation import validate_bundle
from capcov.claims import shen

ROOT = Path(__file__).parent / 'authority_v2'
NATIVE = bool(shutil.which('bifrost') and os.environ.get('BIFROST_SHEN_GO'))
if os.environ.get('CAPCOV_SHEN_REQUIRED') and not NATIVE:
    raise RuntimeError('native v2 authority requires bifrost and BIFROST_SHEN_GO')


def cases():
    for file in sorted(ROOT.glob('*.json')):
        corpus = json.loads(file.read_text())
        for case in corpus['cases']:
            raw = copy.deepcopy(corpus['base'])
            for change in case['changes']:
                keys = change['path'].strip('/').split('/')
                parent = raw
                for key in keys[:-1]:
                    parent = parent[int(key)] if isinstance(parent, list) else parent[key]
                key = int(keys[-1]) if isinstance(parent, list) else keys[-1]
                parent[key] = change['value']
            yield case['name'], bundle_from_json(raw, validate=False), set(case['categories'])


def categories(issues):
    result = set()
    for issue in issues:
        if issue.code in {'missing-compatibility', 'missing-required-bridge'}:
            result.add('compatibility')
        elif issue.code in {'missing-completeness','negative-compatibility'}:
            result.add('completeness')
        elif issue.code == 'declaration-promoted-to-effect':
            result.add('promotion')
        elif issue.code == 'head-context':
            result.add('head')
        else:
            result.add('contracts')
    return result


class AuthorityV2Tests(unittest.TestCase):
    def test_independent_python_authority(self):
        for name, bundle, expected in cases():
            with self.subTest(name=name):
                result = judge(bundle)
                self.assertEqual(categories(result.issues), expected, result.issues)
                self.assertEqual(not validate_bundle(bundle), not expected)

    def test_v1_canonical_bytes_do_not_gain_fields(self):
        b = Bundle(())
        self.assertNotIn('compatibility_capabilities', canonical_json(b))
        self.assertEqual(digest(b), digest(bundle_from_json(canonical_json(b))))
        self.assertNotEqual(digest(b), digest(replace(b, schema_version=2)))
        with self.assertRaises(ValueError):
            bundle_from_json({'schema_version': 1, 'compatibility_capabilities': []})

    def test_v2_roundtrip_and_witness_mutations(self):
        for name, bundle, expected in cases():
            with self.subTest(name=name):
                self.assertEqual(bundle, bundle_from_json(canonical_json(bundle), validate=False))
                judgment = judge(bundle)
                if judgment.ok:
                    self.assertTrue(check_witnesses(bundle, judgment.witnesses))
                    if judgment.witnesses:
                        witness = replace(judgment.witnesses[0], witness_occurrence=999)
                        self.assertFalse(check_witnesses(bundle, (witness, *judgment.witnesses[1:])))
                        self.assertFalse(check_witnesses(bundle, ()))


@unittest.skipUnless(NATIVE, 'real pinned Shen runtime required')
class NativeAuthorityV2Tests(unittest.TestCase):
    @unittest.skipUnless(NATIVE, 'real pinned Shen runtime required')
    def test_native_named_closure_policy(self):
        from capcov.claims.ir import Atom, Rule, CompletenessScope, DerivedCompletenessPolicy
        _, b, _ = next(case for case in cases() if case[0] == 'exact-mapped-closure')
        source = next(d for d in b.relations if d.name == 'closed')
        target = replace(source, name='forwarded', primitive=False)
        original = b.rules[0].body[1]
        rule = Rule(Atom('forwarded', original.terms), (original,), 'forward-closure')
        scope = replace(b.completeness_scopes[0], relation='forwarded')
        b = replace(b, relations=(*b.relations,target), rules=(rule,),
                    completeness_scopes=(*b.completeness_scopes,scope))
        self.assertFalse(shen.authority(b,validate=False).ok)
        policy = DerivedCompletenessPolicy('forward-policy','forward-closure','forwarded',digest(rule))
        b = replace(b,derived_completeness_policies=(policy,))
        self.assertTrue(shen.authority(b,validate=False).ok)
        bad = replace(b,derived_completeness_policies=(replace(policy,rule_digest='0'*64),))
        self.assertFalse(shen.authority(bad,validate=False).ok)

    @unittest.skipUnless(NATIVE, 'real pinned Shen runtime required')
    def test_native_type_constraints_are_independent(self):
        from capcov.claims.ir import Column
        _, b, _ = next((case for case in cases() if case[0] == 'exact-positive-endpoints'))
        relation = next(r for r in b.relations if r.name == 'other')
        altered = replace(relation, columns=(*relation.columns[:2], Column('item','unsigned')))
        bad = replace(b, relations=tuple(altered if r.name == 'other' else r for r in b.relations))
        self.assertIn('type-mismatch', {i.code for i in validate_bundle(bad)})
        report = shen.authority(bad, validate=False)
        self.assertIn(('join','typed-rule'), report.failed_checks())

    @unittest.skipUnless(NATIVE, 'real pinned Shen runtime required')
    def test_independent_native_authority(self):
        mapping = {'declaration-promoted-to-effect': 'promotion',
                   'unsupported-context-widening': 'compatibility',
                   'context-index-loss': 'head',
                   'negative-conclusion-without-completeness': 'completeness'}
        for name, bundle, expected in cases():
            with self.subTest(name=name):
                native = shen.authority(bundle, validate=False)
                failed = native.failed_checks()
                # A malformed contract blocks the dependent native judgments.
                actual = ({'contracts'} if any(c == 'evidence-contracts' for _, c in failed)
                          else {mapping.get(c, c) for _, c in failed})
                self.assertEqual(actual, expected, failed)
                self.assertEqual(native.ok, not expected)

    def test_mapping_api_and_frozen_contract_identity(self):
        from capcov.claims.ir import canonical_dict
        from capcov.claims.contracts import RequiredBridge, DerivedCompletenessPolicy
        _, bundle, _ = next(c for c in cases() if c[0] == 'exact-positive-endpoints')
        original = shen.authority(bundle, validate=False)
        mapped = shen.authority(rules=canonical_dict(bundle), validate=False)
        self.assertEqual(original.elaborated, mapped.elaborated)
        self.assertEqual(mapped.elaborated['schema_version'], 2)
        mutations = [replace(bundle, compatibility_capabilities=(replace(bundle.compatibility_capabilities[0], symmetric=True),)),
                     replace(bundle, required_bridges=(RequiredBridge('new', 'run', 'tenant'),)),
                     replace(bundle, derived_completeness_policies=(DerivedCompletenessPolicy('new','missing','missing','0'*64),))]
        _, scoped, _ = next(c for c in cases() if c[0] == 'exact-mapped-closure')
        frozen = shen.authority(scoped, validate=False).elaborated_checksum
        scope = scoped.completeness_scopes[0]
        with self.assertRaises(shen.ShenFailure) as ctx:
            shen.authority(replace(scoped, completeness_scopes=(replace(scope, mapping=scope.mapping[:-1]),)),
                           validate=False, frozen=frozen)
        self.assertEqual(ctx.exception.kind, 'frozen-pack-mismatch')
        for mutation in mutations:
            with self.subTest(bundle=mutation), self.assertRaises(shen.ShenFailure) as ctx:
                shen.authority(mutation, validate=False, frozen=original.elaborated_checksum)
            self.assertEqual(ctx.exception.kind, 'frozen-pack-mismatch')
