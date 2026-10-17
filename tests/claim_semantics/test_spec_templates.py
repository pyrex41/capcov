"""Declaration templates: decode-time expansion checked by native re-expansion.

The oracle for replay is ``spec_fixtures/replay-pretemplate.claims``, a byte
copy of replay.claims before its php/go families were templated.
"""
import json
import os
from dataclasses import replace
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from capcov.claims import shen
from capcov.claims.ir import canonical_json, digest
from capcov.claims.spec import SpecError, compile_spec, decode_source
from capcov.claims.spec.parser import read_sources
from capcov.claims.spec.templates import expand_templates

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/claim_semantics/spec_fixtures'
REPLAY = ROOT / 'specs/claims/replay.claims'
NATIVE = bool(shutil.which('bifrost') and os.environ.get('BIFROST_SHEN_GO'))
if os.environ.get('CAPCOV_SHEN_REQUIRED') and not NATIVE:
    raise RuntimeError('template tests require the pinned Shen runtime')
SIDE_RULES = 13


class TemplateDecodeTests(unittest.TestCase):
    def test_templated_replay_decodes_to_byte_identical_canonical_ir(self):
        _, _, templated, source_map = decode_source(REPLAY)
        _, _, oracle, _ = decode_source(FIXTURES / 'replay-pretemplate.claims')
        self.assertEqual(canonical_json(templated), canonical_json(oracle))
        self.assertEqual(digest(templated), digest(oracle))
        program = expand_templates(read_sources(REPLAY).declarations)
        self.assertEqual([(e.template, e.arguments) for e in program.expansions],
                         [('side', ('php',)), ('side', ('go',))])
        self.assertEqual(len(program.expanded), 2 * SIDE_RULES)
        traced = {x['name']: x['ancestry'] for x in source_map if x['kind'] == 'rule' and x['ancestry']}
        self.assertEqual(len(traced), 2 * SIDE_RULES)
        site, definition = traced['post_state_gap_go']
        self.assertEqual((site['kind'], site['template'], site['arguments']),
                         ('template-instantiation', 'side', ['go']))
        self.assertEqual((definition['kind'], definition['name']), ('template', 'side'))

    def test_rule_emission_position_cannot_change_canonical_ir(self):
        # Bundle rules are a set: construction sorts them by canonical key.
        _, _, bundle, _ = decode_source(REPLAY)
        reordered = replace(bundle, rules=tuple(reversed(bundle.rules)))
        self.assertEqual(reordered.rules, bundle.rules)
        self.assertEqual(digest(reordered), digest(bundle))

    def test_small_fixture_matches_its_hand_written_expansion(self):
        _, _, templated, _ = decode_source(FIXTURES / 'templates/valid.claims')
        _, _, oracle, _ = decode_source(FIXTURES / 'templates/expanded.claims')
        self.assertEqual(canonical_json(templated), canonical_json(oracle))

    def test_negative_fixtures_are_named_refusals(self):
        for name, code in (('unbound', 'template-unbound-parameter'), ('arity', 'template-arity-mismatch'),
                           ('unknown', 'template-unknown'), ('collision', 'template-name-collision')):
            with self.subTest(fixture=name), self.assertRaises(SpecError) as caught:
                decode_source(FIXTURES / f'templates/{name}.claims')
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(caught.exception.location.source, f'{name}.claims')

    def test_inline_refusals(self):
        side = '.template side(Side) { $Side_ok: $Side_ok(R, X) :- $Side_seen(R, X). }\n'
        decls = ('.decl a_seen(run: symbol ctx, item: symbol) primitive observation runtime.\n'
                 '.decl a_ok(run: symbol ctx, item: symbol) derived derived runtime.\n')
        cases = {
            'forward reference': ('.instantiate side(a).\n' + side, 'template-unknown'),
            'expansion collides with expansion': (side + '.instantiate side(a).\n.instantiate side(a).\n',
                                                  'template-name-collision'),
            'duplicate template': (side + side, 'template-duplicate'),
            'parameter outside a template': ('$x: a_ok(R, X) :- a_seen(R, X).\n', 'template-syntax'),
            'malformed reference': ('.template t(P) { $p_ok: a_ok(R, X) :- a_seen(R, X). }\n', 'template-syntax'),
            'declaration inside a template': ('.template t(P) { .decl x(r: symbol) derived derived runtime. }\n',
                                              'template-syntax'),
            'unbound parameter term': ('.template t(P) { t_ok: a_ok(R, $Q) :- a_seen(R, X). }\n',
                                       'template-unbound-parameter'),
            'lowercase parameter': ('.template t(p) { t_ok: a_ok(R, X) :- a_seen(R, X). }\n', 'template-syntax'),
        }
        with tempfile.TemporaryDirectory() as tmp:
            for label, (body, code) in cases.items():
                with self.subTest(label):
                    path = Path(tmp) / 'case.claims'
                    path.write_text('.claims 2.\n.pack "t" schema 2.\n' + decls + body)
                    with self.assertRaises(SpecError) as caught:
                        decode_source(path)
                    self.assertEqual(caught.exception.code, code)
            path.write_text('.claims 2.\n.pack "t" schema 1.\n' + decls + side + '.instantiate side(a).\n')
            with self.assertRaises(SpecError) as caught:
                decode_source(path)
            self.assertEqual(caught.exception.code, 'template-unsupported-version')

    def test_packs_without_templates_have_unchanged_native_requests(self):
        program = expand_templates(read_sources(FIXTURES / 'scoped.claims').declarations)
        self.assertFalse(program.used)
        self.assertEqual(program.native_request(), {})


@unittest.skipUnless(NATIVE, 'real pinned Shen required')
class NativeTemplateTests(unittest.TestCase):
    def test_compile_records_and_checks_expansion(self):
        compiled = compile_spec(FIXTURES / 'templates/valid.claims')
        oracle = compile_spec(FIXTURES / 'templates/expanded.claims')
        artifacts, plain = dict(compiled.artifacts), dict(oracle.artifacts)
        for name in ('bundle.json', 'pack.json', 'rules.dl', 'schema.json', 'stubs.json', 'authority.json'):
            self.assertEqual(artifacts[name], plain[name], name)
        templates = json.loads(artifacts['obligations.json'])['templates']
        self.assertEqual([(t['template'], t['arguments']) for t in templates], [('side', ['a']), ('side', ['b'])])
        self.assertEqual([r['rule'] for r in templates[1]['rules']], ['b_ok', 'seen_by_b'])
        self.assertEqual(templates[1]['rules'][1]['template_rule'], 'seen_by_$Side')
        self.assertEqual(templates[1]['rules'][1]['source'], 'side.claims')
        self.assertNotIn('templates', json.loads(plain['obligations.json']))

    def test_templated_replay_obligations_trace_every_expansion(self):
        obligations = json.loads(dict(compile_spec(REPLAY).artifacts)['obligations.json'])
        self.assertEqual([len(t['rules']) for t in obligations['templates']], [SIDE_RULES, SIDE_RULES])
        self.assertEqual(sum(item['generated'] for item in obligations['generated']), 24)

    def test_native_disagreement_is_refused(self):
        real = shen.run

        def tampered(mutate):
            def run(bundle, request, **kw):
                result = real(bundle, request, **kw)
                return replace(result, payload={**result.payload,
                                                'template_rules': mutate(result.payload['template_rules'])})
            return run

        def constant(rules):
            rules = json.loads(json.dumps(rules))
            rules[1]['head']['terms'][2]['value'] = 'b'
            return rules

        for label, mutate in (('reordered', lambda r: list(reversed(r))), ('dropped', lambda r: r[:-1]),
                              ('substituted constant', constant), ('missing', lambda r: None)):
            with self.subTest(label), patch.object(shen, 'run', tampered(mutate)):
                with self.assertRaises(SpecError) as caught:
                    compile_spec(FIXTURES / 'templates/valid.claims')
                self.assertEqual(caught.exception.code, 'template-mismatch')

    def test_native_expander_refuses_independently(self):
        # Bypass Python's refusals: hand Shen malformed raw template data.
        _, _, bundle, _ = decode_source(FIXTURES / 'templates/expanded.claims')
        rule = dict(name='$Side_ok', head=dict(relation='$Side_ok', terms=[dict(name='R'), dict(name='X')], negated=False),
                    body=[dict(relation='$Other_seen', terms=[dict(name='R'), dict(name='X')], negated=False)])
        side = ['side', ['Side'], [rule]]
        bound = ['side', ['Side'], [{**rule, 'body': [{**rule['body'][0], 'relation': '$Side_seen'}]}]]
        for label, templates, instantiations, needle in (
                ('unbound', [side], [['side', ['a']]], 'unbound template parameter'),
                ('arity', [bound], [['side', ['a', 'b']]], 'takes 1 arguments'),
                ('unknown', [bound], [['sides', ['a']]], 'unknown or ambiguous template'),
                ('malformed reference', [['t', ['P'], [{**rule, 'name': '$p'}]]], [['t', ['a']]], 'malformed')):
            with self.subTest(label), self.assertRaises(shen.ShenFailure) as caught:
                shen.run(bundle, {'kind': 'compile-spec', 'templates': templates, 'instantiations': instantiations})
            self.assertEqual(caught.exception.kind, 'invalid-input')
            self.assertIn(needle, caught.exception.message)
