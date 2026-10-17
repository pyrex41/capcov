"""Static specification migration against the independently frozen v1 corpus.

The v2 pack is the installed, manifest-checked profile generated from
``specs/claims/static.claims``; v1 is the reviewed experiment pack. Both must
derive identical closures over every reviewed case, under every individual
completeness or assumption withdrawal, and over the exported go_app golden.
"""
from dataclasses import replace
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from capcov.claims.ir import Context, digest
from capcov.claims.static.pack import pack_bundle
from capcov.claims.static.combine import combine, CombineError
from capcov.claims.static.certificate import certify, normalize_relations, recheck
from capcov.claims.evaluator import evaluate
from capcov.claims.assumptions import withdraw
from capcov.claims.evaluation_basis import evaluate_basis
from capcov.claims.authority import judge

try:
    from .static_rules.adapter import case_paths, load_case
    from .static_rules import go_app
except ImportError:  # unittest discover -s imports this directory as top-level
    from static_rules.adapter import case_paths, load_case
    from static_rules import go_app


class StaticSpecTests(unittest.TestCase):
    def migrate_fixture(self, old):
        pack = pack_bundle(version=2)
        decls = {r.name: r for r in pack.relations}
        evidence = tuple(replace(e, context=Context.from_mapping({
            c.name: t.value for c, t in zip(decls[e.atom.relation].columns, e.atom.terms)
            if c.name in decls[e.atom.relation].context_indices})) for e in old.evidence)
        return replace(pack, facts=old.facts, evidence=evidence)

    def assert_same_rows(self, old, new):
        a, b = evaluate(old), evaluate(new)
        self.assertEqual(a.status.value, 'complete')
        self.assertEqual(b.status.value, 'complete')
        self.assertEqual(normalize_relations(a.relations), normalize_relations(b.relations))

    def test_all_frozen_static_cases_and_closure_withdrawals(self):
        paths = case_paths()
        self.assertEqual(len(paths), 14)
        for path in paths:
            with self.subTest(case=path.name):
                old = load_case(path)
                # Reviewed corpus claims and reports are not executable rule rows;
                # v2 universal-domain admission is still pending.
                old = replace(old, claims=(), mappings=(), diagnostics=(), outputs=())
                new = self.migrate_fixture(old)
                self.assertTrue(judge(new).ok)
                self.assert_same_rows(old, new)
                decls = {r.name: r for r in old.relations}
                ids = [e.id for e in old.evidence if decls[e.atom.relation].modality.value == 'completeness'
                       or e.kind == 'assumption']
                for eid in ids:
                    with self.subTest(withdraw=eid):
                        self.assert_same_rows(withdraw(old, [eid]), withdraw(new, [eid]))

    def test_installed_profile_rejects_manifest_drift(self):
        from unittest.mock import patch
        from capcov.claims import pack_resources
        directory = Path(__file__).resolve().parents[2] / 'src/capcov/claims/static'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in directory.glob('*v2*.json'):
                shutil.copy(path, root / path.name)
            with patch.object(pack_resources.resources, 'files', return_value=root):
                self.assertEqual(pack_resources.resolve_profile('static', 2).version, 2)
                path = root / 'schema_static_v2.json'
                path.write_text(path.read_text() + ' ')
                with self.assertRaises(ValueError):
                    pack_resources.resolve_profile('static', 2)

    def test_v1_remains_the_default_profile(self):
        self.assertEqual(pack_bundle().schema_version, 1)
        exported = go_app.scip_facts.export_bundle(
            go_app.normalized(), ast_raw=go_app.ast_raw(), source_root=go_app.GO_APP,
            language=go_app.LANGUAGE, index_digest=go_app.json_file_digest(go_app.golden_raw()),
            index_digest_kind=go_app.runner.INDEX_DIGEST_JSON)
        self.assertEqual(exported.bundle.schema_version, 1)
        self.assertEqual(exported.bundle, go_app.export().bundle)

    def test_export_to_checked_v2_certificates(self):
        old, old_export = go_app.go_app_bundle(with_claims=False)
        new, new_export = go_app.go_app_bundle(with_claims=False, version=2)
        self.assertEqual(new.schema_version, 2)
        self.assertEqual(dict(new_export.bundle.metadata)['pack_profile'], 'rules-static-v2')
        # One index has one content identity under either profile.
        self.assertEqual(dict(old_export.bundle.metadata)['index_digest'],
                         dict(new_export.bundle.metadata)['index_digest'])
        self.assertEqual(old_export.bundle.facts, new_export.bundle.facts)
        self.assertTrue(judge(new).ok)
        self.assert_same_rows(old, new)
        closure = evaluate(new)
        rows = normalize_relations(closure.relations)
        basis = evaluate_basis(new)
        checked = 0
        for relation in ('static_capability', 'runtime_route_without_static', 'static_route_authorization_gap'):
            self.assertTrue(rows[relation], relation)
            for row in rows[relation]:
                with self.subTest(relation=relation, row=row):
                    cert = certify(new, closure.relations, relation, row)
                    self.assertTrue(recheck(new, cert, evaluation_basis=basis).fully_checked)
                    self.assertFalse(recheck(new, cert).fully_checked)
                    self.assertFalse(recheck(old, cert).ok)
                    checked += 1
        self.assertEqual(checked, 4)
        self.assertNotEqual(digest(old), digest(new))
        with self.assertRaises(CombineError):
            combine(old_export.bundle, pack_bundle(version=2))


@unittest.skipUnless(shutil.which('souffle'), 'real pinned Souffle required')
class NativeStaticSpecTests(unittest.TestCase):
    def test_v2_export_agrees_in_all_three_backends(self):
        from capcov.claims.differential import compare_three
        bundle, _ = go_app.go_app_bundle(with_claims=False, version=2)
        with tempfile.TemporaryDirectory() as tmp:
            result = compare_three(bundle, replay_root=tmp,
                                   cache_dir=os.environ.get('CAPCOV_SOUFFLE_CACHE_DIR', tmp))
        self.assertTrue(result.matched)
        self.assertTrue(result.closure_digest_equal)
        self.assertEqual(normalize_relations(result.python.relations),
                         normalize_relations(evaluate(bundle).relations))
