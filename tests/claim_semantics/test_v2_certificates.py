import copy
from dataclasses import replace
import unittest
from capcov.claims.ir import (Atom, Bundle, Column, CompletenessScope, Constant,
                             Evidence, RelationDecl, Rule, Variable, Context)
from capcov.claims.static.certificate import certify, recheck, rules_digest
from capcov.claims.static.combine import combine, CombineError
from capcov.claims.evaluation_basis import evaluate_basis


def bundle():
    columns = (Column('run', 'symbol', True),)
    relations = (RelationDecl('seen', columns, context_indices=('run',)),
        RelationDecl('missing', columns, context_indices=('run',)),
        RelationDecl('closed', columns, modality='completeness', completes='missing', context_indices=('run',)),
        RelationDecl('result', columns, primitive=False, modality='derived', context_indices=('run',)))
    r = Variable('R')
    records = tuple(Evidence(name, Atom(name, (Constant('r', 'symbol'),)), Context.from_mapping({'run':'r'}), source='fixture')
                    for name in ('seen', 'closed'))
    return Bundle(relations, facts=tuple(e.atom for e in records), evidence=records, rules=(Rule(Atom('result', (r,)),
        (Atom('seen', (r,)), Atom('closed', (r,)), Atom('missing', (r,), True)), 'absence'),),
        schema_version=2, completeness_scopes=(CompletenessScope('closed','missing',(('run','run'),)),))


class V2CertificateTests(unittest.TestCase):
    def test_complete_basis_required_for_promotion(self):
        b = bundle()
        basis = evaluate_basis(b)
        cert = certify(b, basis.relations, 'result', ['r'])
        partial = recheck(b, cert)
        self.assertTrue(partial.ok, partial.problems)
        self.assertFalse(partial.fully_checked)
        self.assertTrue(partial.unchecked)
        checked = recheck(b, cert, evaluation_basis=basis)
        self.assertTrue(checked.fully_checked, checked)
        forged = replace(basis, relations=())
        self.assertFalse(recheck(b, cert, evaluation_basis=forged).fully_checked)
        changed = copy.deepcopy(cert)
        changed['closure_digest'] = 'wrong'
        self.assertFalse(recheck(b, changed, evaluation_basis=basis).ok)
        changed = copy.deepcopy(cert)
        changed['authority_witnesses'] = []
        self.assertFalse(recheck(b, changed, evaluation_basis=basis).ok)
        changed = copy.deepcopy(cert)
        changed['certificate_version'] = 'capcov-static-certificate-v1'
        self.assertFalse(recheck(b, changed, evaluation_basis=basis).ok)

    def test_composition_preserves_contracts_and_refuses_versions(self):
        b = bundle()
        merged = combine(b, b)
        self.assertEqual(merged.schema_version, 2)
        self.assertEqual(merged.completeness_scopes, b.completeness_scopes)
        with self.assertRaises(CombineError):
            combine(b, Bundle(()))
        bad = replace(b, completeness_scopes=(CompletenessScope('closed','seen',(('run','run'),)),))
        with self.assertRaises(CombineError):
            combine(b, bad, validate=False)
        self.assertNotEqual(rules_digest(b), rules_digest(bad))

    def test_named_closure_policy_is_bound_to_exact_premises(self):
        from capcov.claims.ir import DerivedCompletenessPolicy, digest
        from capcov.claims.authority import judge
        b=bundle()
        # Forward a primitive closure to a separately declared derived closure.
        source=next(d for d in b.relations if d.name=='closed')
        derived=replace(source,name='forwarded',primitive=False)
        rule=Rule(Atom('forwarded',(Variable('R'),)),(Atom('closed',(Variable('R'),)),),'forward-closure')
        b=replace(b,relations=(*b.relations,derived),rules=(rule,),
                  completeness_scopes=(*b.completeness_scopes,CompletenessScope('forwarded','missing',(('run','run'),))))
        self.assertFalse(judge(b).ok)
        policy=DerivedCompletenessPolicy('forward-policy','forward-closure','forwarded',digest(rule))
        b=replace(b,derived_completeness_policies=(policy,))
        self.assertTrue(judge(b).ok,judge(b).issues)
        mutated=replace(rule,body=(Atom('seen',(Variable('R'),)),))
        self.assertFalse(judge(replace(b,rules=(mutated,))).ok)
