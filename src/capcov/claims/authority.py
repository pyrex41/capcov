"""Schema-v2 evidence judgments, independent of elaboration and evaluation.

Premise occurrences, not relation names, are the units of authorization. A
completeness premise carries its target's context through its explicit map;
a compatibility witness never acts as an ordinary context carrier.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations

from .ir import Atom, Bundle, Constant, Variable, canonical_json, digest
from .validation import ValidationIssue


@dataclass(frozen=True)
class AuthorityWitness:
    rule: str
    left_occurrence: int  # -1 denotes the head
    right_occurrence: int
    left_dimension: str
    right_dimension: str
    capability: str
    witness_occurrence: int
    left_term: Variable | Constant
    right_term: Variable | Constant
    closure_mappings: tuple[tuple[int, tuple[tuple[str, str], ...]], ...] = ()


@dataclass(frozen=True)
class CompletenessWitness:
    rule: str
    negated_occurrence: int
    witness_occurrence: int
    closure_relation: str
    target_relation: str
    mapping: tuple[tuple[str, str], ...]
    assignments: tuple[tuple[str, Variable | Constant], ...]


@dataclass(frozen=True)
class AuthorityJudgment:
    issues: tuple[ValidationIssue, ...]
    witnesses: tuple[AuthorityWitness | CompletenessWitness, ...]

    @property
    def ok(self):
        return not self.issues


@dataclass(frozen=True)
class _Carrier:
    occurrence: int
    relation: str
    positive: bool
    # name, type, term
    columns: tuple
    context: tuple[str, ...]
    mapping: tuple = ()

    def endpoint(self, name):
        return next(((t, v) for n, t, v in self.columns if n == name), None)


def _same(left, right):
    if left is None or right is None or left[0] != right[0]:
        return False
    a, b = left[1], right[1]
    if isinstance(a, Variable) and isinstance(b, Variable):
        return a.name == b.name
    return (isinstance(a, Constant) and isinstance(b, Constant)
            and a.type == b.type == left[0]
            and canonical_json(a.value) == canonical_json(b.value))


def contract_issues(bundle: Bundle):
    """Check declaration graphs before rule judgments dereference them."""
    issues = []
    relations = {r.name: r for r in bundle.relations}

    def fail(code, message, path):
        issues.append(ValidationIssue(code, message, path))

    for field in ('compatibility_capabilities', 'required_bridges', 'completeness_scopes', 'derived_completeness_policies'):
        records = getattr(bundle, field)
        names = [getattr(r, 'name', getattr(r, 'relation', None)) for r in records]
        if len(names) != len(set(names)):
            fail('duplicate-contract', 'contract identities must be unique', field)
    rules = {r.name: r for r in bundle.rules}
    if len(rules) != len(bundle.rules):
        fail('duplicate-rule', 'rule names must be unique', 'rules')
    policy_rules = set()
    for policy in bundle.derived_completeness_policies:
        rule = rules.get(policy.rule)
        if policy.rule in policy_rules:
            fail('derived-completeness-policy', 'one named policy per closure rule', policy.name)
        policy_rules.add(policy.rule)
        target = relations.get(policy.relation)
        if (rule is None or target is None or target.modality.value != 'completeness'
            or target.primitive or rule.head.relation != policy.relation or digest(rule) != policy.rule_digest):
            fail('derived-completeness-policy', 'policy must bind an exact derived closure rule', policy.name)
    for rule in bundle.rules:
        target = relations.get(rule.head.relation)
        if target and target.modality.value == 'completeness' and rule.name not in policy_rules:
            fail('derived-completeness-policy', 'derived completeness requires an explicit named policy', rule.name)
    for r in relations.values():
        if r.modality.value == 'compatibility' and r.context_indices:
            fail('unsupported-compatibility-scope',
                 'scoped compatibility witnesses are not yet supported', r.name)
        if r.compatibility_targets or r.compatibility_context_indices:
            fail('legacy-compatibility', 'v2 requires explicit capabilities, not legacy metadata', r.name)
        if r.modality.value == 'completeness' and not any(s.relation == r.name for s in bundle.completeness_scopes):
            fail('completeness-scope', 'completeness relation requires an explicit scope', r.name)
    for scope in bundle.completeness_scopes:
        path = f'completeness_scopes.{scope.relation}'
        closure, target = relations.get(scope.relation), relations.get(scope.target)
        if closure is None or target is None:
            fail('completeness-scope', 'unknown closure or target', path)
            continue
        if closure.modality.value != 'completeness' or closure.completes != target.name:
            fail('completeness-scope', 'mapping must name the declared completed relation', path)
        cols, dest = {c.name: c for c in closure.columns}, {c.name: c for c in target.columns}
        mapping = dict(scope.mapping)
        if set(mapping) != set(cols) or len(set(mapping.values())) != len(mapping):
            fail('completeness-scope', 'map every closure column exactly once to a distinct target column', path)
        if not set(target.context_indices).issubset(mapping.values()):
            fail('completeness-scope', 'scope must cover all target context columns', path)
        for left, right in scope.mapping:
            if left not in cols or right not in dest or cols[left].type != dest[right].type:
                fail('completeness-scope-type', 'scope endpoints must exist and have identical types', path)
    for cap in bundle.compatibility_capabilities:
        path = f'compatibility_capabilities.{cap.name}'
        witness = relations.get(cap.witness)
        if witness is None or witness.modality.value != 'compatibility':
            fail('compatibility-capability', 'witness must be a compatibility relation', path)
            continue
        cols = {c.name: c for c in witness.columns}
        if cap.left_column == cap.right_column:
            fail('compatibility-capability', 'endpoint payload columns must be distinct', path)
        for dim, column, targets in ((cap.left_dimension, cap.left_column, cap.left_targets),
                                     (cap.right_dimension, cap.right_column, cap.right_targets)):
            if column not in cols:
                fail('compatibility-endpoint', 'unknown witness endpoint column', path)
                continue
            for name in targets:
                target = relations.get(name)
                context = {c.name: c for c in target.columns if c.name in target.context_indices} if target else {}
                if dim not in context or cols[column].type != context[dim].type:
                    fail('compatibility-endpoint', 'target context and witness endpoint must have identical types', path)
    for bridge in bundle.required_bridges:
        for dim, targets in ((bridge.left_dimension, bridge.left_targets), (bridge.right_dimension, bridge.right_targets)):
            for target in targets:
                if target not in relations or dim not in relations[target].context_indices:
                    fail('required-bridge', 'bridge target must carry its dimension', bridge.name)
    return tuple(issues)


def judge_rule(bundle: Bundle, rule) -> AuthorityJudgment:
    relations = {r.name: r for r in bundle.relations}
    scopes = {s.relation: s for s in bundle.completeness_scopes}
    issues, witnesses = [], []
    path = f'rules.{rule.name}'

    def fail(code, message):
        issues.append(ValidationIssue(code, message, path))

    def carrier(atom, occurrence):
        decl = relations.get(atom.relation)
        if decl is None or len(atom.terms) != len(decl.columns) or decl.modality.value == 'compatibility':
            return None
        cols = tuple((c.name, c.type, t) for c, t in zip(decl.columns, atom.terms))
        if decl.modality.value == 'completeness':
            scope = scopes.get(decl.name)
            if scope is None or scope.target not in relations:
                return None
            mapping = dict(scope.mapping)
            return _Carrier(occurrence, scope.target, not atom.negated,
                            tuple((mapping[n], t, v) for n, t, v in cols if n in mapping),
                            relations[scope.target].context_indices, scope.mapping)
        return _Carrier(occurrence, decl.name, not atom.negated, cols, decl.context_indices)

    if rule.head.negated:
        fail('negative-rule-head', 'rule conclusions must be positive')
    atoms = [(i, a) for i, a in enumerate(rule.body) if isinstance(a, Atom)]
    carriers = [c for i, a in atoms if (c := carrier(a, i)) is not None]
    positive_witnesses = [(i, a) for i, a in atoms if not a.negated
                          and a.relation in relations and relations[a.relation].modality.value == 'compatibility']

    def authorize(left, ld, right, rd):
        le, re = left.endpoint(ld), right.endpoint(rd)
        if le is None or re is None:
            return False
        for cap in bundle.compatibility_capabilities:
            orientations = [(cap.left_dimension, cap.right_dimension, cap.left_targets,
                             cap.right_targets, cap.left_column, cap.right_column)]
            if cap.symmetric:
                orientations.append((cap.right_dimension, cap.left_dimension, cap.right_targets,
                                     cap.left_targets, cap.right_column, cap.left_column))
            for cd1, cd2, targets1, targets2, wc1, wc2 in orientations:
                if (ld, rd) != (cd1, cd2) or left.relation not in targets1 or right.relation not in targets2:
                    continue
                for wi, atom in positive_witnesses:
                    if atom.relation != cap.witness:
                        continue
                    decl = relations[atom.relation]
                    values = {c.name: (c.type, t) for c, t in zip(decl.columns, atom.terms)}
                    if _same(le, values.get(wc1)) and _same(re, values.get(wc2)):
                        witnesses.append(AuthorityWitness(rule.name, left.occurrence, right.occurrence,
                            ld, rd, cap.name, wi, le[1], re[1],
                            tuple((c.occurrence, c.mapping) for c in (left, right) if c.mapping)))
                        return True
        return False

    def bridges(left, right):
        for policy in bundle.required_bridges:
            for a, b in ((left, right), (right, left)):
                if (policy.left_dimension in a.context and policy.right_dimension in b.context
                    and (not policy.left_targets or a.relation in policy.left_targets)
                    and (not policy.right_targets or b.relation in policy.right_targets)):
                    yield a, policy.left_dimension, b, policy.right_dimension

    for left, right in combinations(carriers, 2):
        for dim in sorted(set(left.context) & set(right.context)):
            if not _same(left.endpoint(dim), right.endpoint(dim)) and not authorize(left, dim, right, dim):
                fail('missing-compatibility', f'premises {left.occurrence}/{right.occurrence} require exact {dim} authorization')
        for a, ad, b, bd in bridges(left, right):
            if not authorize(a, ad, b, bd):
                fail('missing-required-bridge', f'premises {a.occurrence}/{b.occurrence} require {ad}/{bd} authorization')

    # All mapped scope positions must match, even non-context request/path/window.
    for negated_occurrence, atom in atoms:
        if not atom.negated:
            continue
        if atom.relation in relations and relations[atom.relation].modality.value == 'compatibility':
            fail('negative-compatibility', 'authorization witnesses must be positive')
        target = carrier(atom, -2)
        matches = []
        if target:
            for index, positive in atoms:
                scope = scopes.get(positive.relation)
                if positive.negated or scope is None or scope.target != atom.relation:
                    continue
                c = carrier(positive, index)
                if c and all(_same(c.endpoint(dest), target.endpoint(dest)) for _, dest in scope.mapping):
                    matches.append(c)
        if not matches:
            fail('missing-completeness', f'negation of {atom.relation} needs an exact mapped completeness premise')
        else:
            match = matches[0]
            closure_atom = rule.body[match.occurrence]
            witnesses.append(CompletenessWitness(rule.name, negated_occurrence, match.occurrence,
                closure_atom.relation, atom.relation, match.mapping,
                tuple((dest, match.endpoint(dest)[1]) for _, dest in match.mapping)))

    # Projection is allowed only while retaining assumption authority. A later
    # rule cannot turn an assumption into observed support by adding a wrapper.
    assumption_relations = {d.name for d in relations.values() if d.modality.value == 'assumption'}
    while True:
        more = {r.head.relation for r in bundle.rules
                if len(r.body) == 1 and isinstance(r.body[0], Atom) and not r.body[0].negated
                and r.body[0].relation in assumption_relations
                and r.head.relation in relations and relations[r.head.relation].modality.value == 'derived'}
        if more <= assumption_relations:
            break
        assumption_relations.update(more)
    conclusion = relations.get(rule.head.relation)
    if conclusion and conclusion.binding.value == 'runtime' and conclusion.modality.value in ('derived', 'claim'):
        positives = [(a, relations[a.relation]) for _, a in atoms
                     if not a.negated and a.relation in relations]
        observed = any(d.name not in assumption_relations and d.binding.value == 'runtime' and d.modality.value not in
                       ('compatibility', 'completeness', 'assumption') for _, d in positives)
        projection = (conclusion.modality.value == 'derived' and len(rule.body) == 1
                      and len(positives) == 1 and positives[0][1].name in assumption_relations)
        negations = [i for i,a in atoms if a.negated]
        absence = (bool(negations) and bool(positives)
                   and all(d.modality.value == 'completeness' and d.binding.value == 'runtime' for _,d in positives)
                   and all(any(isinstance(w, CompletenessWitness) and w.negated_occurrence == i
                               for w in witnesses) for i in negations))
        if not (observed or projection or absence):
            fail('declaration-promoted-to-effect', 'runtime conclusion lacks observed support, an assumption projection, or scoped absence evidence')

    head = carrier(rule.head, -1)
    if head:
        positive = [c for c in carriers if c.positive]
        for dim in head.context:
            if any(dim in c.context and _same(head.endpoint(dim), c.endpoint(dim)) for c in positive):
                continue
            candidates = [c for c in positive if dim in c.context]
            carried = any(authorize(head, dim, c, dim) for c in candidates)
            bridge_candidates = [b for c in positive for b in bridges(head, c)]
            for a, ad, b, bd in bridge_candidates:
                if (a.occurrence == -1 and ad == dim) or (b.occurrence == -1 and bd == dim):
                    carried = authorize(a, ad, b, bd) or carried
            endpoint = head.endpoint(dim)
            if not carried and endpoint is not None and isinstance(endpoint[1], Constant) and not any(dim in c.context for c in carriers) and not any(list(bridges(head, c)) for c in carriers):
                continue  # explicit, unconflicted constant construction
            if not carried:
                fail('head-context', f'head {dim} must come from a positive carrier or an exact authorized endpoint')
    return AuthorityJudgment(tuple(issues), tuple(witnesses))


def judge(bundle: Bundle) -> AuthorityJudgment:
    if bundle.schema_version != 2:
        raise ValueError('explicit evidence judgments require Bundle schema 2')
    issues = contract_issues(bundle)
    if issues:
        return AuthorityJudgment(issues, ())
    judgments = [judge_rule(bundle, rule) for rule in bundle.rules]
    return AuthorityJudgment(tuple(i for j in judgments for i in j.issues),
                             tuple(w for j in judgments for w in j.witnesses))


def check_witnesses(bundle, witnesses):
    """Reconstruct obligations; an emitted witness cannot authorize itself."""
    result = judge(bundle)
    return result.ok and tuple(witnesses) == result.witnesses
