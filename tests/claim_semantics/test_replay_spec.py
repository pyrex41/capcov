"""Replay specification migration against the independently frozen v1 corpus."""
from dataclasses import replace
from pathlib import Path
import unittest

from capcov.claims.ir import Context, digest
from capcov.claims.replay.pack import pack_bundle
from capcov.claims.replay import join
from capcov.claims.evaluator import evaluate
from capcov.claims.assumptions import withdraw
from capcov.claims.static.combine import combine, CombineError
from capcov.claims.static.certificate import normalize_relations, recheck
from capcov.claims.evaluation_basis import evaluate_basis
from .replay_rules.adapter import case_paths, load_case
from .test_evaluator_selection import admissions


class ReplaySpecTests(unittest.TestCase):
    def migrate_fixture(self, old):
        pack = pack_bundle(version=2)
        decls = {r.name:r for r in pack.relations}
        evidence = tuple(replace(e,context=Context.from_mapping({
            c.name:t.value for c,t in zip(decls[e.atom.relation].columns,e.atom.terms)
            if c.name in decls[e.atom.relation].context_indices})) for e in old.evidence)
        return replace(pack, facts=old.facts, evidence=evidence)

    def assert_same_rows(self, old, new):
        a,b=evaluate(old),evaluate(new)
        self.assertEqual(a.status.value,'complete')
        self.assertEqual(b.status.value,'complete')
        self.assertEqual(normalize_relations(a.relations),normalize_relations(b.relations))

    def test_all_frozen_replay_cases_and_closure_withdrawals(self):
        for path in case_paths():
            with self.subTest(case=path.name):
                old=load_case(path)
                # Reviewed corpus mappings describe reports, not executable rule rows.
                old=replace(old,claims=(),mappings=(),diagnostics=(),outputs=())
                new=self.migrate_fixture(old)
                self.assert_same_rows(old,new)
                decls={r.name:r for r in old.relations}
                ids=[e.id for e in old.evidence if decls[e.atom.relation].modality.value=='completeness'
                     or e.kind=='assumption']
                for eid in ids:
                    with self.subTest(withdraw=eid):
                        self.assert_same_rows(withdraw(old,[eid]),withdraw(new,[eid]))

    def test_installed_profile_rejects_manifest_drift(self):
        from unittest.mock import patch
        from capcov.claims import pack_resources
        directory=Path(__file__).resolve().parents[2]/'src/capcov/claims/replay'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for path in directory.glob('*v2*.json'):
                shutil.copy(path,root/path.name)
            with patch.object(pack_resources.resources,'files',return_value=root):
                self.assertEqual(pack_resources.resolve_profile('replay',2).version,2)
                path=root/'stubs-replay-v2.json'
                path.write_text(path.read_text()+' ')
                with self.assertRaises(ValueError):pack_resources.resolve_profile('replay',2)

    def test_receipt_to_checked_v2_certificates(self):
        receipt=Path(__file__).parent/'fixtures/replay_receipt_min'
        old=join.build(receipt,reviewer_admissions=admissions(receipt))
        new=join.build(receipt,reviewer_admissions=admissions(receipt),version=2)
        self.assertEqual(new.exported.status,'complete')
        self.assertEqual(new.bundle.schema_version,2)
        self.assert_same_rows(old.bundle,new.bundle)
        join.evaluate_join(new,str(receipt))
        basis=evaluate_basis(new.bundle)
        self.assertTrue(new.certificates)
        for cert in new.certificates.values():
            self.assertTrue(recheck(new.bundle,cert,evaluation_basis=basis).fully_checked)
            self.assertFalse(recheck(new.bundle,cert).fully_checked)
            self.assertFalse(recheck(old.bundle,cert).ok)
        self.assertNotEqual(digest(old.bundle),digest(new.bundle))
        self.assertEqual(join.summary(new)['status'],'complete')
        with self.assertRaises(CombineError):combine(old.exported.bundle,pack_bundle(version=2))


import os
import shutil
import tempfile


@unittest.skipUnless(shutil.which('souffle'), 'real pinned Souffle required')
class NativeReplaySpecTests(unittest.TestCase):
    def test_v2_receipt_agrees_in_all_three_backends(self):
        receipt=Path(__file__).parent/'fixtures/replay_receipt_min'
        result=join.build(receipt,reviewer_admissions=admissions(receipt),version=2)
        with tempfile.TemporaryDirectory() as tmp:
            join.evaluate_join(result,tmp,kernels='three',
                               cache_dir=os.environ.get('CAPCOV_SOUFFLE_CACHE_DIR',tmp))
        self.assertIsNone(result.mismatch)
        self.assertEqual(result.evaluators,('python','souffle','souffle-compiled'))
        self.assertTrue(result.certificates)
