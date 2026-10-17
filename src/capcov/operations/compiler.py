"""Conservative symbolic obligations for the existing system language.

The transformation is a trusted compiler, separately identified from proof
checking. Unsupported aliasing/quantification remains an explicit obligation.
Proofs concern prospective successful action paths, before runtime postchecks;
they never use those postchecks as premises to prove themselves.
"""

from . import OperationError, _sha
from .native import invoke
from .system import _term, SYSTEM_LIBRARIES, canonical, digest
from .proofs import prove_many, _validate
from capcov.claims.spec.parser import parse, Symbol


def model(source):
    _term(source)

    def data(n):
        v = n.value
        return (
            [data(x) for x in v]
            if isinstance(v, tuple)
            else v.text
            if isinstance(v, Symbol)
            else v
        )

    return data(parse(source)[0])


def formula(p):
    if p == ["yes"]:
        return ["true"]
    if p == ["no"]:
        return ["false"]
    if p[0] in ("both", "either"):
        return [{"both": "and", "either": "or"}[p[0]], formula(p[1]), formula(p[2])]
    if p[0] == "negate":
        return ["not", formula(p[1])]
    if p[0] == "equal":
        if p[1] == p[2]:
            return ["true"]
        if p[1][0] == p[2][0] == "literal":
            return ["false"]
        if _affine(p[1]) == _affine(p[2]):
            return ["true"]
    return ["atom", canonical(p)]


def _affine(x):
    """Exact additive normalization; no floating arithmetic or solver oracle."""
    if x[0] in ("int-add", "int-sub"):
        a, b = _affine(x[1]), _affine(x[2])
        sign = 1 if x[0] == "int-add" else -1
        out = dict(a)
        for key, value in b.items():
            out[key] = out.get(key, 0) + sign * value
        return {k: v for k, v in out.items() if v}
    if x[0] == "literal":
        try:
            n = int(x[1])
            if str(n) == x[1]:
                return {"constant": n} if n else {}
        except ValueError:
            pass
    return {canonical(x): 1}


def _row_local(p):
    if not isinstance(p, list) or not p:
        return True
    return p[0] in (
        "yes",
        "no",
        "literal",
        "row-field",
        "row-key",
        "equal",
        "less-than",
        "negate",
        "both",
        "either",
        "int-add",
        "int-sub",
    ) and all(_row_local(x) for x in p[1:] if isinstance(x, list))


def _instance(p, table, key, fields=None):
    if not isinstance(p, list) or not p:
        return p
    if p[0] == "row-key":
        return key
    if p[0] == "row-field":
        return (fields or {}).get(p[1], ["lookup", table, key, p[1]])
    return [_instance(x, table, key, fields) for x in p]


def _distinct(pre):
    if pre[0] == "both":
        return _distinct(pre[1]) + _distinct(pre[2])
    if (
        pre[0] == "negate"
        and pre[1][0] == "equal"
        and all(x[0] in ("argument", "literal") for x in pre[1][1:])
    ):
        return [pre[1][1:]]
    return []


def _instances(invariants, syntax):
    keys = []

    def walk(p):
        if not isinstance(p, list) or not p:
            return
        if (
            p[0] == "lookup"
            and p[2][0] in ("argument", "literal")
            and [p[1], p[2]] not in keys
        ):
            keys.append([p[1], p[2]])
        for x in p:
            if isinstance(x, list):
                walk(x)

    walk(syntax)
    return [
        {
            "rule": "initial-universal-elimination",
            "invariant": name,
            "key": key,
            "predicate": [
                "either",
                ["negate", ["exists", table, key]],
                _instance(p[2], table, key),
            ],
        }
        for name, p in invariants
        if p[0] == "every-row" and _row_local(p[2])
        for table, key in keys
        if table == p[1]
    ]


def _reads(p, table, field=None):
    if not isinstance(p, list) or not p:
        return False
    tag = p[0]
    if tag in ("before", "old"):
        return False
    if tag in ("lookup", "sum-field") and p[1] == table:
        if field is None or p[-1] == field:
            return True
    if tag in ("exists", "count-rows", "some-row", "every-row") and p[1] == table:
        if field is None:
            return True
        if tag in ("some-row", "every-row") and _row_reads(p[2], field):
            return True
    return any(_reads(x, table, field) for x in p[1:] if isinstance(x, list))


def _row_reads(p, field):
    return isinstance(p, list) and (
        p == ["row-field", field] or any(_row_reads(x, field) for x in p)
    )


class Unresolved(Exception):
    pass


def _rewrite(p, a, distinct=()):
    """Substitution for exact keys; preserve disjoint tables/fields, refuse may-alias."""
    if not isinstance(p, list) or not p:
        return p
    if p[0] in ("before", "old"):
        return p
    tag, table, key = a[:3]
    if not _reads(p, table, a[3] if tag == "update" else None):
        return p
    if key[0] not in ("literal", "argument"):
        raise Unresolved("mutation key depends on mutable state")
    if p[0] in ("lookup", "exists") and _reads(
        p[2], table, a[3] if tag == "update" else None
    ):
        raise Unresolved("lookup key depends on mutated state")
    if p[0] == "exists" and p[1] == table:
        if tag == "update":
            return p
        if p[2] == key:
            return ["yes"] if tag == "insert" else ["no"]
        if (
            (p[2][0] == key[0] == "literal" and p[2] != key)
            or [p[2], key] in distinct
            or [key, p[2]] in distinct
        ):
            return p
        raise Unresolved("row keys may alias")
    if p[0] == "lookup" and p[1] == table:
        if p[2] == key:
            if tag == "update":
                return a[4] if p[3] == a[3] else p
            if tag == "insert":
                return dict(a[3])[p[3]]
            raise Unresolved("postcondition reads removed row")
        if (
            (p[2][0] == key[0] == "literal" and p[2] != key)
            or [p[2], key] in distinct
            or [key, p[2]] in distinct
        ):
            return p
        raise Unresolved("lookup keys may alias")
    if p[0] == "sum-field" and tag == "update" and p[1] == table and p[2] == a[3]:
        return ["int-add", ["int-sub", p, ["lookup", table, key, a[3]]], a[4]]
    if p[0] == "every-row" and p[1] == table and _row_local(p[2]):
        if tag == "remove":
            return p
        fields = dict(a[3]) if tag == "insert" else {a[3]: a[4]}
        return ["both", p, _instance(p[2], table, key, fields)]
    if p[0] in ("every-row", "some-row", "count-rows", "sum-field"):
        raise Unresolved(
            "affected quantified/aggregate predicate needs an induction or arithmetic lemma"
        )
    return [
        p[0],
        *[_rewrite(x, a, distinct) if isinstance(x, list) else x for x in p[1:]],
    ]


def wp(actions, post, distinct=(), *, loop=None):
    result = post
    for _, name, a in reversed(actions):
        if a[0] == "publish":
            continue
        if a[0] == "require":
            result = ["either", ["negate", a[2]], result]
        elif a[0] == "choose":
            result = [
                "both",
                ["either", ["negate", a[1]], wp(a[2], result, distinct, loop=loop)],
                ["either", a[1], wp(a[3], result, distinct, loop=loop)],
            ]
        elif a[0] == "for-each":
            if loop is not None:
                result = loop(name, a, result)
                continue
            deletion_preserves = (
                result[0] == "every-row"
                and _row_local(result[2])
                and all(child[2][0] == "remove" for child in a[3])
            )
            if not deletion_preserves and any(
                _reads(result, t) for t in effects(a[3])[0]
            ):
                raise Unresolved("loop needs an invariant and induction derivation")
        else:
            result = _rewrite(result, a, distinct)
    return result


def effects(actions):
    writes, emits = set(), set()
    for _, _, a in actions:
        if a[0] in ("insert", "update", "remove"):
            writes.add(a[1])
        elif a[0] == "publish":
            emits.add(a[1])
        elif a[0] in ("choose", "for-each"):
            for branch in a[2:4] if a[0] == "choose" else [a[3]]:
                w, e = effects(branch)
                writes.update(w)
                emits.update(e)
    return sorted(writes), sorted(emits)


def _unfreeze(p):
    if not isinstance(p, list) or not p:
        return p
    if p[0] == "before":
        return _unfreeze(p[1])
    return [_unfreeze(x) for x in p]


def compile_system(source, *, timeout=60):
    valid, native = invoke(
        f"(caps.typechecks? {_term(source)})", SYSTEM_LIBRARIES, timeout=timeout
    )
    if valid is not True:
        raise OperationError("system construction judgment failed")
    m = model(source)
    reports, pending = [], []
    for _, name, args, pre, actions, post in m[3]:
        obligations = []
        instances = _instances(m[4], [pre, actions, post])
        for label, predicate in [
            ("postcondition", post),
            *[("invariant:" + n, p) for n, p in m[4]],
        ]:
            obligation = {"id": name + ":" + label, "predicate": predicate}
            try:
                weakest = _unfreeze(wp(actions, predicate, _distinct(pre)))
                left = [formula(pre), *[formula(p) for _, p in m[4]]]
                left.extend(formula(i["predicate"]) for i in instances)
                right = [formula(weakest)]
                _validate(left, right)
                obligation.update(weakest_precondition=weakest)
                pending.append((obligation, left, right))
            except (Unresolved, OperationError) as exc:
                obligation.update(status="open", reason=str(exc))
            obligations.append(obligation)
        writes, emits = effects(actions)
        reports.append(
            {
                "command": name,
                "arguments": args,
                "mode": "ground-inputs",
                "determinism": "at-most-one-result-or-operational-error",
                "may_write": writes,
                "may_emit": emits,
                "initial_instances": instances,
                "obligations": obligations,
            }
        )
    for start in range(0, len(pending), 256):
        batch = pending[start : start + 256]
        proofs = prove_many([(l, r) for _, l, r in batch], timeout=timeout)
        for (obligation, _, _), proof in zip(batch, proofs):
            obligation.update(
                proof=proof,
                status="proved" if proof["answer"][0] == "proved" else "open",
            )
    result = {
        "format": "capcov-system-compilation-v1",
        "model": _sha(source.encode()),
        "compiler": _sha(__import__("pathlib").Path(__file__).read_bytes()),
        "identity": native,
        "commands": reports,
        "scope": "partial-correctness-of-prospective-actions; schema and expression totality remain runtime checks",
    }
    result["sha256"] = digest(result)
    return result
