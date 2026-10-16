import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from dataclasses import replace

from capcov.claims.ir import canonical_json, digest
from capcov.claims.spec import (compile_spec, check_spec, decode_source, check_elaboration, SpecError)
from capcov.claims.spec.parser import parse, read_sources, data
from capcov.claims import shen

ROOT = Path(__file__).resolve().parents[2]
NATIVE = bool(shutil.which('bifrost') and os.environ.get('BIFROST_SHEN_GO'))
if os.environ.get('CAPCOV_SHEN_REQUIRED') and not NATIVE:
    raise RuntimeError('spec compiler tests require the pinned Shen runtime')


class SpecParserTests(unittest.TestCase):
    def test_location_and_immutable_data(self):
        node = parse('; comment\n[object [value "quoted \\" text"] [items [array true 17 null]]]', 'x')[0]
        self.assertEqual((node.location.line,node.location.column),(2,1))
        self.assertEqual(data(node),{'value':'quoted " text','items':[True,17,None]})
        self.assertIsInstance(node.value,tuple)

    def test_executable_and_malformed_forms_refused(self):
        for text in ('(system "bad")','[object [x 1] [x 2]]','[array foo]','[array 1',']'):
            with self.subTest(text=text),self.assertRaises(SpecError):
                nodes=parse(text)
                for node in nodes:data(node)

    def test_import_closure_cycles_and_escapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            main=root/'main.claims'; shared=root/'shared.claims'
            shared.write_text('[claims-spec 1]')
            main.write_text('[claims-spec 1 [import "shared.claims"] [import "shared.claims"]]')
            self.assertEqual(len(read_sources(main).digests),2)
            shared.write_text('[claims-spec 1 [import "main.claims"]]')
            with self.assertRaises(SpecError):read_sources(main)
            main.write_text('[claims-spec 1 [import "../outside"]]')
            with self.assertRaises(SpecError):read_sources(main)
            link=root/'escape'; link.symlink_to(root.parent)
            main.write_text('[claims-spec 1 [import "escape/other"]]')
            with self.assertRaises(SpecError):read_sources(main)

    def test_all_154_rules_have_lossless_source_baselines(self):
        baseline=json.loads((ROOT/'specs/claims/baseline-v1.json').read_text())
        self.assertEqual(sum(p['rule_count'] for p in baseline['packs']),154)
        for pack in baseline['packs']:
            with self.subTest(domain=pack['domain']):
                raw=(ROOT/pack['path']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(),pack['file_sha256'])
                _,_,bundle,_=decode_source(ROOT/f"specs/claims/{pack['domain']}.claims")
                self.assertEqual(digest(bundle),pack['bundle_digest'])
                self.assertEqual(len(bundle.rules),pack['rule_count'])
        fixture=ROOT/'tests/claim_semantics/fixtures/model_min'
        for name,expected in baseline['model_min'].items():
            self.assertEqual(hashlib.sha256((fixture/name).read_bytes()).hexdigest(),expected)

    def test_compilation_never_falls_back_without_native_runtime(self):
        from unittest.mock import patch
        with patch.dict(os.environ,{'PATH':''},clear=False):
            with self.assertRaises(shen.ShenUnavailable):
                compile_spec(ROOT/'specs/claims/static.claims')


@unittest.skipUnless(NATIVE,'real pinned Shen required')
class NativeSpecTests(unittest.TestCase):
    def test_deterministic_build_and_read_only_drift_check(self):
        source=ROOT/'specs/claims/static.claims'
        first=compile_spec(source)
        second=compile_spec(source)
        self.assertEqual(first.artifacts,second.artifacts)
        with tempfile.TemporaryDirectory() as tmp:
            first.write(tmp)
            self.assertTrue(check_spec(source,tmp).ok)
            path=Path(tmp)/'obligations.json'
            path.write_text('mutated\n')
            report=check_spec(source,tmp)
            self.assertEqual(report.changed,('obligations.json',))
            self.assertEqual(path.read_text(),'mutated\n')
            manifest=json.loads(dict(first.artifacts)['manifest.json'])
            self.assertNotIn(str(ROOT),json.dumps(manifest))

    def test_native_closure_elaboration_independently_checked(self):
        source=ROOT/'tests/claim_semantics/spec_fixtures/scoped.claims'
        _,_,before,_=decode_source(source)
        compiled=compile_spec(source)
        self.assertEqual(len(before.rules[0].body),2)
        self.assertEqual(len(compiled.bundle.rules[0].body),3)
        from capcov.claims.evaluator import evaluate
        self.assertEqual(compiled.bundle.facts, ())
        self.assertEqual(evaluate(compiled.bundle).relation_rows('result'), ())
        obligations=check_elaboration(before,compiled.bundle)
        self.assertTrue(obligations[0]['generated'])
        rule=compiled.bundle.rules[0]
        mutation=replace(compiled.bundle,rules=(replace(rule,body=rule.body[1:]),))
        with self.assertRaises(SpecError):check_elaboration(before,mutation)
