"""Declaration templates: syntactic, total, non-recursive expansion at decode.

``.template side(Side) { rule ... }`` names a parameterised block of rules;
``.instantiate side(php).`` emits its rules, in template order, at the point
of the instantiation. A reference ``$P`` (``P`` is ``[A-Z][A-Za-z0-9]*``,
taken maximally) substitutes the argument text into rule names and relation
names (``$Side_post_state`` -> ``php_post_state``); a whole term ``$P`` or
``$P::type`` becomes the constant ``"php"::type`` (default ``symbol``).
Variables, quoted strings and comparison operators are never substituted.

Expansion happens once, here, before any decoding: the kernels and the
elaborator only ever see the expanded, ordinary rules. Bundle rules are a
set (``Bundle`` sorts them by canonical key), so emission position changes
neither canonical IR nor digest; it changes only source-map order. Premise
order inside each rule is preserved verbatim.

Refusals (``SpecError.code``): ``template-unbound-parameter`` (a ``$P`` not
declared by its template, checked at definition and again at expansion),
``template-arity-mismatch``, ``template-unknown`` (no earlier definition;
forward references are refused), ``template-name-collision`` (an expanded
rule name equals a hand-written or another expanded rule's name),
``template-duplicate``, ``template-syntax`` (malformed header, parameter
reference or substituted identifier) and ``template-mismatch`` (native Shen
re-expansion disagrees). Templates contain rules only; no template may
instantiate another, so expansion is a single finite pass.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

from .parser import Location, Node, SpecError, Symbol, data, form
from .logic import _node

PARAMETER = re.compile(r'[A-Z][A-Za-z0-9]*')
IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z_0-9-]*')
REFERENCE = re.compile(r'\$([A-Za-z0-9]*)')


@dataclass(frozen=True)
class Template:
    name: str
    parameters: tuple[str, ...]
    rules: tuple[tuple[dict, Location], ...]
    location: Location


@dataclass(frozen=True)
class Expansion:
    template: str
    arguments: tuple[str, ...]
    location: Location
    rules: tuple[tuple[str, str, Location], ...]  # (expanded name, template rule name, rule location)


@dataclass(frozen=True)
class TemplateProgram:
    """Declarations with templates removed and instantiations replaced."""
    declarations: tuple[Node, ...]
    templates: tuple[Template, ...]
    expansions: tuple[Expansion, ...]
    expanded: tuple[dict, ...]  # raw rule wire dicts, in emission order

    @property
    def used(self):
        return bool(self.templates or self.expansions)

    def ancestry(self):
        """Expanded rule name -> [instantiation site, template definition]."""
        out = {}
        for expansion in self.expansions:
            template = next(t for t in self.templates if t.name == expansion.template)
            for name, _, _ in expansion.rules:
                out[name] = [
                    dict(kind='template-instantiation', template=expansion.template,
                         arguments=list(expansion.arguments), **_where(expansion.location)),
                    dict(kind='template', name=template.name, parameters=list(template.parameters),
                         **_where(template.location))]
        return out

    def obligations(self):
        return [dict(template=e.template, arguments=list(e.arguments), instantiation=_where(e.location),
                     rules=[dict(rule=name, template_rule=origin, **_where(loc)) for name, origin, loc in e.rules])
                for e in self.expansions]

    def native_request(self):
        """Raw template data for the native re-expansion; empty when unused."""
        if not self.used:
            return {}
        return dict(templates=[[t.name, list(t.parameters), [rule for rule, _ in t.rules]] for t in self.templates],
                    instantiations=[[e.template, list(e.arguments)] for e in self.expansions])


def _where(location):
    return dict(source=location.source, line=location.line, column=location.column)


def _substitute(text, env, location):
    def replace(match):
        parameter = match.group(1)
        if not PARAMETER.fullmatch(parameter):
            raise SpecError(f'malformed template parameter reference in {text!r}', location, 'template-syntax')
        if parameter not in env:
            raise SpecError(f'unbound template parameter ${parameter}', location, 'template-unbound-parameter')
        return env[parameter]
    result = REFERENCE.sub(replace, text)
    if not IDENTIFIER.fullmatch(result):
        raise SpecError(f'substituted identifier {result!r} is not an identifier', location, 'template-syntax')
    return result


def _term(term, env, location):
    if 'parameter' not in term:
        return dict(term)
    if term['parameter'] not in env:
        raise SpecError(f"unbound template parameter ${term['parameter']}", location, 'template-unbound-parameter')
    return dict(value=env[term['parameter']], type=term['type'])


def _rule(rule, env, location):
    def atom(item):
        return dict(relation=_substitute(item['relation'], env, location),
                    terms=[_term(t, env, location) for t in item['terms']], negated=item['negated'])

    body = [atom(item) if 'relation' in item else
            dict(left=_term(item['left'], env, location), operator=item['operator'],
                 right=_term(item['right'], env, location)) for item in rule['body']]
    return dict(name=_substitute(rule['name'], env, location), head=atom(rule['head']), body=body)


def _template(declaration):
    _, args = form(declaration)
    header = data(args[0])
    name, parameters = header['name'], tuple(header['parameters'])
    if not parameters or len(set(parameters)) != len(parameters) or not all(PARAMETER.fullmatch(p) for p in parameters):
        raise SpecError('template parameters are distinct names matching [A-Z][A-Za-z0-9]*',
                        declaration.location, 'template-syntax')
    if len(args) == 1:
        raise SpecError(f'template {name} declares no rules', declaration.location, 'template-syntax')
    rules = []
    for node in args[1:]:
        rule = data(form(node, 'rule')[1][0])
        # Definition-time totality: every reference names a declared parameter.
        _rule(rule, {p: p for p in parameters}, node.location)
        rules.append((rule, node.location))
    return Template(name, parameters, tuple(rules), declaration.location)


def expand_templates(declarations) -> TemplateProgram:
    """One ordered pass; refuses rather than passing anything through."""
    written = set()
    for declaration in declarations:
        tag, args = form(declaration)
        if tag == 'rule':
            value = data(args[0])
            if isinstance(value, dict) and isinstance(value.get('name'), str):
                written.add(value['name'])
    templates, expansions, expanded, out, emitted = {}, [], [], [], set()
    for declaration in declarations:
        tag, args = form(declaration)
        if tag == 'template':
            template = _template(declaration)
            if template.name in templates:
                raise SpecError(f'duplicate template {template.name}', declaration.location, 'template-duplicate')
            templates[template.name] = template
        elif tag == 'instantiate':
            request = data(args[0])
            template = templates.get(request['template'])
            if template is None:
                raise SpecError(f"instantiation of unknown template {request['template']}",
                                declaration.location, 'template-unknown')
            arguments = tuple(request['arguments'])
            if len(arguments) != len(template.parameters):
                raise SpecError(f'template {template.name} takes {len(template.parameters)} arguments, '
                                f'given {len(arguments)}', declaration.location, 'template-arity-mismatch')
            env = dict(zip(template.parameters, arguments))
            records = []
            for rule, location in template.rules:
                value = _rule(rule, env, location)
                if value['name'] in written or value['name'] in emitted:
                    raise SpecError(f"expanded rule {value['name']} collides with an existing rule name",
                                    declaration.location, 'template-name-collision')
                emitted.add(value['name'])
                expanded.append(value)
                records.append((value['name'], rule['name'], location))
                out.append(Node((Node(Symbol('rule'), location), _node(value, location)), location))
            expansions.append(Expansion(template.name, arguments, declaration.location, tuple(records)))
        else:
            out.append(declaration)
    return TemplateProgram(tuple(out), tuple(templates.values()), tuple(expansions), tuple(expanded))


def check_native_expansion(program, native_rules):
    """Compare Shen's independent re-expansion with ours, rule by rule, in order."""
    from ..ir import BundleIngestionError, bundle_from_json

    def decode(raw):
        try:
            return bundle_from_json(dict(schema_version=1, relations=[], rules=[raw]), validate=False).rules[0]
        except (BundleIngestionError, TypeError, ValueError, KeyError) as exc:
            raise SpecError(f'native template expansion is malformed: {exc}', code='template-mismatch') from None

    if not isinstance(native_rules, list):
        raise SpecError('native elaborator returned no template expansion', code='template-mismatch')
    if [decode(r) for r in native_rules] != [decode(r) for r in program.expanded]:
        raise SpecError('native template expansion disagrees with independent expansion', code='template-mismatch')
