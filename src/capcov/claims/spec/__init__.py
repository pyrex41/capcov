"""Restricted declaration compilation and deterministic artifact verification.

Installed evaluation consumes JSON. Compilation is deliberately native-Shen
only: an unavailable runtime is an operational failure, never a Python fallback.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import math
import sys
from pathlib import Path

from .parser import SpecError, read_sources, form, data
from .templates import expand_templates, check_native_expansion
from ..ir import bundle_from_json, canonical_dict, canonical_json, digest
from ..validation import assert_valid
from ..authority import judge
from .. import shen

LANGUAGE_VERSION = 2


def _json(value):
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n'


def _sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class CompiledSpec:
    bundle: object
    artifacts: tuple[tuple[str, str], ...]

    def write(self, directory):
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        for name, text in self.artifacts:
            (target / name).write_text(text, encoding='utf-8')


@dataclass(frozen=True)
class SpecCheckReport:
    ok: bool
    missing: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()
    unexpected: tuple[str, ...] = ()

    def as_dict(self):
        return dict(ok=self.ok, missing=list(self.missing), changed=list(self.changed), unexpected=list(self.unexpected))


def decode_source(source):
    closure = read_sources(source)
    templates = expand_templates(closure.declarations)
    ancestry = templates.ancestry()
    pack = dict(primitives=[], supplementary_primitives=[], derived=[], rules=[])
    contracts = dict(compatibility_capabilities=[], completeness_scopes=[], required_bridges=[], derived_completeness_policies=[])
    source_map = []
    seen = set()
    sections = {'primitive': 'primitives', 'supplementary-primitive': 'supplementary_primitives',
                'derived': 'derived', 'rule': 'rules', 'capability': 'compatibility_capabilities',
                'completeness-scope': 'completeness_scopes', 'required-bridge': 'required_bridges',
                'derived-completeness-policy': 'derived_completeness_policies'}
    for declaration in templates.declarations:
        tag, args = form(declaration)
        if len(args) != 1:
            raise SpecError(f'{tag} requires one data object', declaration.location)
        value = data(args[0])
        if not isinstance(value, dict):
            raise SpecError('declaration payload must be an object', declaration.location)
        if tag == 'pack':
            if 'pack' in seen:
                raise SpecError('duplicate pack declaration', declaration.location)
            seen.add('pack')
            if set(value) - {'schema_version','id','description','primitives_source'}:
                raise SpecError('unknown pack metadata field', declaration.location)
            pack.update(value)
        elif tag in sections:
            section = sections[tag]
            identity = value.get('name', value.get('relation'))
            key = ('relation' if section in ('primitives','supplementary_primitives','derived') else section, identity)
            if not isinstance(identity, str) or not identity or key in seen:
                raise SpecError('missing or duplicate declaration name', declaration.location)
            seen.add(key)
            (contracts if section in contracts else pack)[section].append(value)
            source_map.append(dict(kind=tag, name=identity,
                source=declaration.location.source, line=declaration.location.line,
                column=declaration.location.column,
                ancestry=ancestry.get(identity, []) if tag == 'rule' else []))
        else:
            raise SpecError(f'unsupported declaration {tag}', declaration.location, 'unsupported-construct')
    if 'pack' not in seen or 'id' not in pack or pack.get('schema_version') not in (1,2):
        raise SpecError('pack must declare its id and Bundle schema version')
    if pack['schema_version'] == 1 and any(contracts.values()):
        raise SpecError('v1 cannot declare explicit evidence contracts')
    if pack['schema_version'] == 1 and templates.used:
        # Native re-expansion runs in the v2 compile path only.
        raise SpecError('v1 cannot declare templates', code='template-unsupported-version')
    raw = dict(schema_version=pack['schema_version'], relations=[*pack['primitives'],*pack['supplementary_primitives'],*pack['derived']], rules=pack['rules'])
    if pack['schema_version'] == 2:
        raw.update(contracts)
        pack.update(contracts)
    # Decode shape only. The first semantic authority is Shen, independently
    # followed by Python; parser acceptance cannot preempt native rejection.
    return closure, pack, bundle_from_json(raw, validate=False), source_map


def compile_spec(source, timeout=60) -> CompiledSpec:
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be finite and positive')
    closure, pack, bundle, source_map = decode_source(source)
    # Deterministic recomputation of decode's expansion, for its raw data.
    templates = expand_templates(closure.declarations)
    generated = []
    if bundle.schema_version == 2:
        native = shen.run(bundle, {"kind": "compile-spec", **templates.native_request()}, timeout=timeout)
        if native.payload.get("kind") != "spec-elaboration":
            raise SpecError("native elaborator returned an invalid envelope")
        check_native_expansion(templates, native.payload.get("template_rules"))
        raw = canonical_dict(bundle)
        raw["rules"] = native.payload.get("rules")
        elaborated = bundle_from_json(raw, validate=False)
        generated = check_elaboration(bundle, elaborated)
        locations = {item['name']: item for item in source_map if item['kind'] == 'rule'}
        generated = [{**item, 'source_location': locations[item['rule']]} for item in generated]
        bundle = elaborated
        pack["rules"] = [canonical_dict(rule) for rule in bundle.rules]
    report = shen.authority(bundle, validate=False, timeout=timeout)
    if not report.ok:
        raise SpecError(f'native authority rejected specification: {report.failed_checks()}', code='spec-authority')
    assert_valid(bundle)
    from ..souffle import program_for_pack
    program = program_for_pack(bundle)
    # Include supplementary primitives as well as derived targets, so schema
    # plus stubs contains every referenced declaration with exact equality.
    schema = dict(schema_version=bundle.schema_version, relations=pack['primitives'])
    if bundle.schema_version == 2:
        for key in ('compatibility_capabilities', 'required_bridges', 'completeness_scopes'):
            schema[key] = canonical_dict(bundle)[key]
    artifacts = {
        'pack.json': _json(pack),
        'bundle.json': canonical_json(bundle) + '\n',
        'schema.json': _json(schema),
        'stubs.json': _json(dict(schema_version=bundle.schema_version, relations=[*pack['supplementary_primitives'], *pack['derived']])),
        'rules.dl': program.program,
        'source-map.json': _json(source_map),
        'obligations.json': _json({'schema_version':bundle.schema_version, 'generated':generated,
                                  'authority':[canonical_dict(w) for w in judge(bundle).witnesses] if bundle.schema_version == 2 else [],
                                  **({'templates': templates.obligations()} if templates.used else {})}),
        'authority.json': _json(dict(ok=report.ok, rules=report.rules, pack=report.pack,
                                    elaborated_checksum=report.elaborated_checksum)),
    }
    # No timestamps, absolute paths, temporary driver paths, or wall-clock data.
    compiler_root = Path(__file__).parents[1]
    compiler = {p.relative_to(compiler_root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(compiler_root.rglob("*.py"))}
    rt = report.provenance.runtime
    manifest = dict(format='capcov-spec-manifest-v1', language_version=LANGUAGE_VERSION,
        bundle_schema_version=bundle.schema_version, pack_id=pack['id'], bundle_digest=digest(bundle),
        sources=dict(closure.digests), compiler=compiler,
        runtime=dict(implementation=shen.IMPL, sha256=rt.shen_go_sha256, libraries=dict(rt.library_sha256),
                     launcher_sha256=hashlib.sha256(Path(rt.bifrost).read_bytes()).hexdigest(),
                     python=dict(implementation=sys.implementation.name, version=list(sys.version_info[:3]))),
        artifacts={name:_sha(text) for name,text in sorted(artifacts.items())})
    artifacts['manifest.json'] = _json(manifest)
    return CompiledSpec(bundle, tuple(sorted(artifacts.items())))


def check_spec(source, artifacts, *, timeout=60) -> SpecCheckReport:
    """Regenerate in memory and compare every byte; never rewrite the directory."""
    expected = dict(compile_spec(source, timeout=timeout).artifacts)
    directory = Path(artifacts)
    missing, changed = [], []
    for name, text in expected.items():
        path = directory / name
        if not path.is_file():
            missing.append(name)
        elif path.read_bytes() != text.encode('utf-8'):
            changed.append(name)
    unexpected = tuple(sorted(p.name for p in directory.iterdir() if p.name not in expected)) if directory.is_dir() else ()
    return SpecCheckReport(not (missing or changed or unexpected), tuple(missing), tuple(changed), unexpected)


def check_elaboration(source, output):
    """Independently reconstruct scoped insertions, without trusting witnesses."""
    from dataclasses import replace
    from ..ir import Atom, Variable
    from ..authority import contract_issues
    if contract_issues(source):
        raise SpecError("invalid source evidence contracts")
    declarations = {d.name: d for d in source.relations}
    expected, obligations = [], []
    for rule in source.rules:
        body = []
        bound = set()
        for index, atom in enumerate(rule.body):
            if not isinstance(atom, Atom) or not atom.negated:
                if isinstance(atom, Atom):
                    bound.update(t.name for t in atom.terms if isinstance(t, Variable))
                body.append(atom)
                continue
            if not {t.name for t in atom.terms if isinstance(t, Variable)}.issubset(bound):
                raise SpecError("negation variables must be bound before elaboration")
            target = declarations.get(atom.relation)
            if target is None:
                raise SpecError("negation names an undeclared relation")
            target_terms = dict(zip((c.name for c in target.columns), atom.terms))
            candidates = []
            for scope in source.completeness_scopes:
                if scope.target == atom.relation:
                    mapping = dict(scope.mapping)
                    closure = declarations[scope.relation]
                    witness = Atom(scope.relation, tuple(target_terms[mapping[c.name]] for c in closure.columns))
                    candidates.append((scope, witness))
            exact = [(s,w) for s,w in candidates if w in rule.body or w in body]
            if exact:
                scope, witness = exact[0]
                inserted = False
            elif len(candidates) == 1:
                scope, witness = candidates[0]
                body.append(witness)
                inserted = True
            else:
                raise SpecError("missing or ambiguous completeness policy")
            obligations.append(dict(rule=rule.name, occurrence=index, closure=scope.relation,
                                    mapping=[list(p) for p in scope.mapping], generated=inserted,
                                    premise=canonical_dict(witness)))
            body.append(atom)
        expected.append(replace(rule, body=tuple(body)))
    reconstructed = replace(source, rules=tuple(expected))
    if reconstructed != output:
        raise SpecError("native elaboration disagrees with independent reconstruction", code="elaboration-mismatch")
    return obligations
