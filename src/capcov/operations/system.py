"""Complete finite system execution, campaigns and reproducible certificates.

Python bounds and enumerates requests. Shen owns construction judgments,
operation semantics, invariants, outcome alternatives and observation matching.
"""

from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path
import shutil
import tempfile
import math
from importlib import resources

from capcov.claims.spec.parser import parse, Symbol
from capcov import shen_runtime
from . import OperationError, _native_shen, _sha, _string, _state, MAX_BYTES
from .process import run as run_process

SYSTEM_LIBRARIES = ("kernel.shen", "system.shen", "system-types.shen")
SYSTEM_TAGS = frozenset(
    "system table foreign command literal argument row-key row-field lookup yes no equal negate both either exists some-row every-row insert update remove publish require choose for-each named column text int32 enum int-add int-sub less-than before count-rows sum-field".split()
)
# R02 PR 1: tags a request carries outside the model, in its outcome (the
# capcov.faults alphabet) and in observed effect records
# (docs/ir-specification.md, sections 4.1, 4.2 and 7). The front end refuses
# any other head tag there, as _term does with SYSTEM_TAGS.
REQUEST_TAGS = frozenset(
    "ok fail info rejected aborted effect create put delete emit".split()
)
V1_OUTCOMES = ("committed", "rejected", "aborted", "unknown")
# The assumption a result carries when its request names a fail outcome: the
# request API forces outcomes, so the request itself is the classifier.
DEFINITE_FAIL = "definite-fail-v1:request"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return _sha(canonical(value).encode())


def _term(source):
    if not isinstance(source, str) or len(source.encode()) > MAX_BYTES:
        raise OperationError("system specification exceeds 1 MiB")
    terms = parse(source, "<system>")
    if len(terms) != 1:
        raise OperationError("system requires one data term")

    def emit(node, depth=0):
        if depth > 32:
            raise OperationError("system nesting exceeds 32")
        v = node.value
        if isinstance(v, Symbol):
            if v.text not in SYSTEM_TAGS:
                raise OperationError(f"unsupported system constructor: {v.text}")
            return v.text
        if isinstance(v, str):
            return _string(v)
        if isinstance(v, tuple):
            return "[" + " ".join(emit(n, depth + 1) for n in v) + "]"
        raise OperationError("system terms must be strings, constructors or lists")

    return emit(terms[0])


def _pairs(values):
    if (
        not isinstance(values, dict)
        or len(values) > 64
        or not all(isinstance(k, str) for k in values)
    ):
        raise OperationError("arguments require at most 64 named strings")
    return (
        "["
        + " ".join(
            "[" + _string(k) + " " + _string(v) + "]" for k, v in sorted(values.items())
        )
        + "]"
    )


def _logical_effect(e):
    if not isinstance(e, list) or not e:
        raise OperationError("malformed effect")
    if not isinstance(e[0], str) or e[0] not in REQUEST_TAGS - {"effect"}:
        raise OperationError("unsupported effect")
    if e[0] == "create" and len(e) == 4:
        if not isinstance(e[3], list) or any(
            not isinstance(f, list) or len(f) != 2 for f in e[3]
        ):
            raise OperationError("create fields require pairs")
        if len({f[0] for f in e[3]}) != len(e[3]):
            raise OperationError("duplicate create field")
        return (
            "[create "
            + _string(e[1])
            + " "
            + _string(e[2])
            + " "
            + _pairs(dict(e[3]))
            + "]"
        )
    if isinstance(e[0], str) and len(e) == {"put": 5, "delete": 3, "emit": 3}.get(
        e[0]
    ):
        return "[" + e[0] + " " + " ".join(_string(v) for v in e[1:]) + "]"
    raise OperationError("unsupported effect")


def _identity_string(value, what):
    if not isinstance(value, str) or not value or len(value.encode()) > 256:
        raise OperationError(f"{what} must be a nonempty string of at most 256 bytes")
    return _string(value)


def _invocation(value):
    """An invocation id. Attempt ids are Inv/step, so "/" would let two differ
    only in where the step name starts; it is refused."""
    term = _identity_string(value, "invocation id")
    if "/" in value:
        raise OperationError("invocation id must not contain '/'")
    return term


def _is_record(effect):
    return isinstance(effect, list) and bool(effect) and effect[0] == "effect"


def _effect_terms(effects, identified):
    """Logical effects, or effect records [effect I A L] (R02 PR 1, section 4.2).

    identified=True requires every effect to be a record (an observation of a
    request that names its invocation); identified=False refuses records.
    """
    if type(identified) is not bool:
        raise TypeError("identified must be a bool")
    if not isinstance(effects, list) or len(effects) > 4096:
        raise OperationError("at most 4096 effects required")
    records = [_is_record(e) for e in effects]
    if identified and not all(records):
        raise OperationError(
            "untagged effect: an identified observation needs [effect I A L]"
        )
    if not identified and any(records):
        raise OperationError("effect records require the request's invocation id")
    result = []
    for e, record in zip(effects, records):
        if not record:
            result.append(_logical_effect(e))
            continue
        if len(e) != 4:
            raise OperationError("effect record requires intent, attempt and effect")
        result.append(
            "[effect "
            + _identity_string(e[1], "intent id")
            + " "
            + _identity_string(e[2], "attempt id")
            + " "
            + _logical_effect(e[3])
            + "]"
        )
    return "[" + " ".join(result) + "]"


def _outcome(out):
    """A v1 outcome symbol, or an R02 outcome as its JSON array (section 11).

    A rejection label is nonempty: the bridge binds the empty label internally
    for a v1 `rejected` request the model commits, never from the wire.
    """
    if isinstance(out, str) and out in V1_OUTCOMES:
        return out
    if (
        not isinstance(out, list)
        or not out
        or not isinstance(out[0], str)
        or out[0] not in REQUEST_TAGS
    ):
        raise OperationError("invalid outcome")
    if out == ["ok"]:
        return "[ok]"
    if out == ["info"]:
        return "[info]"
    if out == ["fail", ["aborted"]]:
        return "[fail [aborted]]"
    if (
        isinstance(out, list)
        and len(out) == 2
        and out[0] == "fail"
        and isinstance(out[1], list)
        and len(out[1]) == 2
        and out[1][0] == "rejected"
        and isinstance(out[1][1], str)
        and out[1][1]
    ):
        return "[fail [rejected " + _string(out[1][1]) + "]]"
    raise OperationError("invalid outcome")


def bridged(request):
    """True when a request uses R02 PR 1: an R02 outcome or an invocation id.

    Only such results carry `assumptions`. A v1 request's result is unchanged
    (gate G5): capcov-system-evaluation-v1 implies the bridge's assumptions.
    """
    return "invocation" in request or not isinstance(request.get("outcome"), str)


def _fails(request):
    outcome = request.get("outcome")
    return isinstance(outcome, list) and bool(outcome) and outcome[0] == "fail"


def _request(request, fuel):
    if not isinstance(request, dict) or set(request) - {
        "command",
        "args",
        "state",
        "outcome",
        "observed",
        "trace",
        "invocation",
    }:
        raise OperationError("unknown system request fields")
    if not {"command", "args", "state", "outcome"} <= set(request):
        raise OperationError("request requires command, args, state and outcome")
    n, e, s = (
        _string(request["command"]),
        _pairs(request["args"]),
        _state(request["state"]),
    )
    out = _outcome(request["outcome"])
    invocation = None
    if "invocation" in request:
        invocation = _invocation(request["invocation"])
    observed = "not-requested"
    if "observed" in request:
        obs = request["observed"]
        if not isinstance(obs, dict) or set(obs) != {"state", "effects"}:
            raise OperationError("observation requires state and effects")
        observed = (
            "(caps.accepts? Alternatives "
            + _state(obs["state"])
            + " "
            + _effect_terms(obs["effects"], identified=invocation is not None)
            + ")"
        )
    trace = "not-requested"
    if "trace" in request:
        t = request["trace"]
        if (
            not isinstance(t, dict)
            or set(t) != {"state", "effects", "steps"}
            or not isinstance(t["steps"], list)
            or len(t["steps"]) > fuel
        ):
            raise OperationError("trace requires state, effects and bounded steps")
        steps = []
        for step in t["steps"]:
            if not isinstance(step, dict) or set(step) != {"name", "effects"}:
                raise OperationError("trace step requires name and effects")
            steps.append(
                "[action "
                + _string(step["name"])
                + " "
                + _effect_terms(step["effects"], identified=False)
                + "]"
            )
        trace = (
            "(= R [result "
            + _state(t["state"])
            + " "
            + _effect_terms(t["effects"], identified=False)
            + " ["
            + " ".join(steps)
            + "]])"
        )
    alternatives = f"(caps.admissible {s} R {out})"
    if invocation is not None:
        alternatives = f"(caps.identify {invocation} {alternatives})"
    extra = " (caps.assumptions M)" if bridged(request) else ""
    return (
        f"(let R (caps.run M {n} {e} {s} {fuel}) Alternatives {alternatives} "
        f"[(caps.analyze M {n}) R Alternatives {observed} {trace}{extra}])"
    )


def evaluate(source, requests, *, fuel=1024, timeout=60):
    """Evaluate up to 256 independent requests in one native process, fail closed."""
    if type(fuel) is not int or not 1 <= fuel <= 4096:
        raise OperationError("fuel must be an integer in 1..4096")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise OperationError("timeout must be finite and positive")
    if not isinstance(requests, list) or not 1 <= len(requests) <= 256:
        raise OperationError("evaluate requires 1..256 requests")
    if len(canonical(requests).encode()) > 4 * MAX_BYTES:
        raise OperationError("request batch exceeds 4 MiB")
    program = _term(source)
    terms = [_request(r, fuel) for r in requests]
    impl, launcher, binary = _native_shen()
    root = resources.files("capcov.operations").joinpath("shen")
    libs = {n: root.joinpath(n).read_bytes() for n in SYSTEM_LIBRARIES}
    with tempfile.TemporaryDirectory(prefix="capcov-system-") as tmp:
        directory = Path(tmp)
        for n, b in libs.items():
            (directory / n).write_bytes(b)
        # Paths are generated by tempfile, never spec data.
        loads = "\n".join(f'(load "{directory / n}")' for n in libs)
        driver = directory / "driver.shen"
        driver.write_text(
            loads
            + "\n(tc +)\n(let M "
            + program
            + "\n"
            + "(if (caps.typechecks? M) (capop.print-result ["
            + " ".join(terms)
            + "]) "
            + '(error "system: schema, scope or construction judgment failed")))\n'
        )
        code, stdout, stderr = run_process(
            shen_runtime.bifrost_argv(launcher, impl, driver),
            cwd=directory,
            timeout=timeout,
            env=shen_runtime.child_env(impl, binary),
        )
        marker = b"CAPCOV-OPERATION-RESULT "
        lines = [
            line[len(marker) :]
            for line in stdout.splitlines()
            if line.startswith(marker)
        ]
        if code or len(lines) != 1:
            raise OperationError(
                "native system rejected input: "
                + (stderr or stdout)[-2500:].decode(errors="replace")
            )
        try:
            values = json.loads(lines[0])
            if len(values) != len(requests):
                raise ValueError("wrong result count")
            keys = (
                "analysis",
                "transition",
                "admissible",
                "observed_matches",
                "trace_valid",
            )
            results = [
                dict(
                    zip(
                        keys + (("assumptions",) if bridged(request) else ()),
                        row,
                        strict=True,
                    )
                )
                for request, row in zip(requests, values)
            ]
            for request, result in zip(requests, results):
                if _fails(request):
                    # A fail outcome means "nothing happened" only under
                    # definite-fail-v1 (section 4.1); say so.
                    result["assumptions"] = [*result["assumptions"], DEFINITE_FAIL]
        except (ValueError, TypeError) as exc:
            raise OperationError("malformed native system response") from exc
    for request, result in zip(requests, results):
        verify_effects(request["state"], result, request.get("invocation"))
    return {
        "format": "capcov-system-evaluation-v1",
        "basis": "finite-system-model",
        "model": _sha(source.encode()),
        "requests": digest(requests),
        "fuel": fuel,
        "runtime": {
            **shen_runtime.runtime_record(impl, binary),
            "bifrost": _sha(Path(launcher).read_bytes()),
        },
        "libraries": {n: _sha(b) for n, b in libs.items()},
        "results": results,
    }


def wire_state(rows):
    return [
        ["row", r["table"], r["key"], [[k, v] for k, v in sorted(r["fields"].items())]]
        for r in rows
    ]


def json_state(rows):
    return [{"table": r[1], "key": r[2], "fields": dict(r[3])} for r in rows]


def project(effect):
    """pi([effect I A L]) = L; a logical effect is its own projection."""
    return effect[3] if _is_record(effect) else effect


def verify_effects(before, result, invocation=None):
    """Independent patch/trace checker; does not claim to prove predicates.

    With an invocation id every admissible effect must be the bridge's record
    [effect Inv Inv/body L], and the patch is checked on the projections L.
    """
    for index, transition in enumerate(
        [result["transition"], *result["admissible"]]
    ):
        if transition[0] == "rejected":
            continue
        if len(transition) != 4 or transition[0] != "result":
            raise OperationError("invalid transition")
        _, after, effects, trace = transition
        # Index 0 is the model's own run (caps.run), whose effects are always
        # logical; only the admissible alternatives carry records.
        if invocation is not None and index > 0:
            identity = ["effect", invocation, invocation + "/body"]
            if any(
                not isinstance(e, list) or len(e) != 4 or e[:3] != identity
                for e in effects
            ):
                raise OperationError("effect record lacks the bridge identity")
            effects = [project(e) for e in effects]
        if [e for step in trace for e in step[2]] != effects:
            raise OperationError("trace/effect disagreement")
        rows = copy.deepcopy(before)
        for effect in effects:
            tag = effect[0]
            if tag == "emit":
                if effect[1] not in result["analysis"][2]:
                    raise OperationError("effect exceeds declared may-emit summary")
                continue
            if effect[1] not in result["analysis"][1]:
                raise OperationError("effect exceeds declared may-write summary")
            table, key = effect[1:3]
            matches = [
                i for i, r in enumerate(rows) if (r["table"], r["key"]) == (table, key)
            ]
            if tag == "create":
                if matches:
                    raise OperationError("certificate creates duplicate row")
                rows.append({"table": table, "key": key, "fields": dict(effect[3])})
            elif tag == "delete":
                if len(matches) != 1:
                    raise OperationError("certificate deletes missing row")
                rows.pop(matches[0])
            elif tag == "put":
                if len(matches) != 1:
                    raise OperationError("certificate updates missing row")
                rows[matches[0]]["fields"][effect[3]] = effect[4]
            else:
                raise OperationError("unknown certificate effect")
        if wire_state(rows) != after:
            raise OperationError("certificate patch does not reconstruct state")
    return True


def argument_domain(command, domains, *, outcome="committed", limit=256):
    """Cartesian product of caller-declared finite argument domains, never samples."""
    if not isinstance(domains, dict) or len(domains) > 64:
        raise OperationError("provide at most 64 finite argument domains")
    size = 1
    for values in domains.values():
        if (
            not isinstance(values, list)
            or not values
            or not all(isinstance(v, str) for v in values)
            or len(set(values)) != len(values)
        ):
            raise OperationError("domains require nonempty distinct strings")
        size *= len(values)
        if size > limit:
            raise OperationError("argument domain exceeds budget")
    names = sorted(domains)
    return [
        {"command": command, "args": dict(zip(names, vs)), "outcome": outcome}
        for vs in itertools.product(*(domains[n] for n in names))
    ]


def explore(
    source,
    initial,
    calls,
    *,
    depth=3,
    max_nodes=256,
    fuel=1024,
    timeout=60,
    schedule=None,
):
    """Breadth-first exhaustive exploration within explicit depth/domain bounds.

    Unknown outcomes fork. States merge only at the same depth; edge effects and
    histories remain recorded. A node-budget exhaustion raises, never 'passes'.
    """
    if (
        type(depth) is not int
        or not 1 <= depth <= 16
        or type(max_nodes) is not int
        or not 1 <= max_nodes <= 4096
    ):
        raise OperationError("depth must be 1..16 and max_nodes 1..4096")
    if not isinstance(calls, list) or not 1 <= len(calls) <= 64:
        raise OperationError("exploration requires 1..64 calls")
    if schedule is not None:
        if (
            not isinstance(schedule, list)
            or len(schedule) != depth
            or any(
                not isinstance(level, list) or not 1 <= len(level) <= 64
                for level in schedule
            )
        ):
            raise OperationError(
                "schedule requires one nonempty call-choice list per depth"
            )
    for c in calls if schedule is None else [c for level in schedule for c in level]:
        if not isinstance(c, dict) or set(c) != {"command", "args", "outcome"}:
            raise OperationError("campaign calls require command, args and outcome")
    assumptions = None
    nodes = [{"id": 0, "depth": 0, "state": copy.deepcopy(initial), "via": None}]
    graph_bytes = len(canonical(nodes).encode())
    frontier = [nodes[0]]
    edges = []
    provenance = None
    for level in range(depth):
        pending = [
            (node, c)
            for node in frontier
            for c in (calls if schedule is None else schedule[level])
        ]
        next_by_state = {}
        for start in range(0, len(pending), 256):
            part = pending[start : start + 256]
            requests = [dict(c, state=n["state"]) for n, c in part]
            evaluation = evaluate(source, requests, fuel=fuel, timeout=timeout)
            identity = {
                k: evaluation[k] for k in ("model", "runtime", "libraries", "fuel")
            }
            if provenance is not None and provenance != identity:
                raise OperationError("runtime changed during campaign")
            provenance = identity
            for (node, call), result in zip(part, evaluation["results"]):
                # Every bridged result carries the model's list; a fail call
                # adds definite-fail-v1. The campaign carries their union, in
                # first-seen order, and none when every call is v1.
                for name in result.get("assumptions", []):
                    assumptions = [] if assumptions is None else assumptions
                    if name not in assumptions:
                        assumptions.append(name)
                edge = {
                    "from": node["id"],
                    "call": copy.deepcopy(call),
                    "transition": result["transition"],
                    "to": [],
                    "effects": [],
                }
                for alt in result["admissible"]:
                    state = json_state(alt[1])
                    key = digest(state)
                    if key not in next_by_state:
                        if len(nodes) >= max_nodes:
                            raise OperationError("campaign node budget exhausted")
                        child = {
                            "id": len(nodes),
                            "depth": level + 1,
                            "state": state,
                            "via": len(edges),
                        }
                        nodes.append(child)
                        graph_bytes += len(canonical(child).encode())
                        next_by_state[key] = child
                    edge["to"].append(next_by_state[key]["id"])
                    edge["effects"].append(alt[2])
                edges.append(edge)
                graph_bytes += len(canonical(edge).encode())
                if len(edges) > 16384 or graph_bytes > 32 * MAX_BYTES:
                    raise OperationError(
                        "campaign edge or serialized-size budget exhausted"
                    )
        frontier = list(next_by_state.values())
        if not frontier:
            break
    violations = [
        i for i, e in enumerate(edges) if e["transition"] == ["rejected", "invariant"]
    ]
    witness = []
    if violations:
        edge_id = violations[0]
        while edge_id is not None:
            witness.append(edge_id)
            edge_id = nodes[edges[edge_id]["from"]]["via"]
        witness.reverse()
    campaign = {
        "format": "capcov-system-campaign-v1",
        "basis": "explicit-bounded-domain",
        "depth": depth,
        "calls": copy.deepcopy(calls),
        "schedule": copy.deepcopy(schedule),
        "initial": copy.deepcopy(initial),
        "identity": provenance,
        "nodes": nodes,
        "edges": edges,
        "rejections": sum(e["transition"][0] == "rejected" for e in edges),
        "invariant_violations": violations,
        "shortest_invariant_witness": witness,
    }
    if assumptions is not None:
        # An R02 outcome was explored: the campaign carries the assumptions.
        campaign["assumptions"] = assumptions
    return campaign


def certify(source, requests, *, fuel=1024, timeout=60):
    result = evaluate(source, requests, fuel=fuel, timeout=timeout)
    payload = {
        "format": "capcov-system-certificate-v1",
        "requests": copy.deepcopy(requests),
        "evaluation": result,
    }
    payload["sha256"] = digest(payload)
    return payload


def recheck(source, certificate, *, timeout=60):
    if (
        not isinstance(certificate, dict)
        or set(certificate) != {"format", "requests", "evaluation", "sha256"}
        or certificate["format"] != "capcov-system-certificate-v1"
    ):
        raise OperationError("invalid certificate envelope")
    if (
        digest({k: v for k, v in certificate.items() if k != "sha256"})
        != certificate["sha256"]
    ):
        raise OperationError("certificate digest mismatch")
    fresh = evaluate(
        source,
        certificate["requests"],
        fuel=certificate["evaluation"]["fuel"],
        timeout=timeout,
    )
    if fresh != certificate["evaluation"]:
        raise OperationError("certificate reproduction mismatch")
    return True


def claim_bundle(source, certificate, *, timeout=60):
    """Export rechecked, case-scoped conformance evidence to capcov's judge.

    No operation-wide qualification, closure, reviewer admission or replay ABI
    compatibility is asserted by a finite collection of normalized cases.

    A result that carries `assumptions` (an R02 outcome or effect identity)
    supports or refutes its case only through assumption-kind evidence, one
    record per named assumption, so the verdict is conditional (spec 4.6) and
    withdrawing any one assumption leaves the case unresolved. Results without
    assumptions export exactly as before.
    """
    recheck(source, certificate, timeout=timeout)
    from capcov.claims.ir import (
        Atom,
        Bundle,
        Claim,
        Column,
        Constant,
        Evidence,
        EvidenceMapping,
        RelationDecl,
        Rule,
        Variable,
    )

    columns = (Column("model", "digest"), Column("case", "symbol"))
    relations = tuple(
        RelationDecl(n, columns, producer_classes=("systemcheck",))
        for n in ("system_case_matches", "system_case_differs")
    ) + (
        RelationDecl(
            "system_case_conforms", columns, modality="claim", primitive=False
        ),
    )
    terms = (Variable("M"), Variable("C"))
    rules = (
        Rule(
            Atom("system_case_conforms", terms),
            (Atom("system_case_matches", terms),),
            "system-case-match",
        ),
    )
    facts = []
    evidence = []
    claims = []
    assumed = set()
    source = "systemcheck native-reproduction " + certificate["sha256"]
    for index, (request, result) in enumerate(
        zip(certificate["requests"], certificate["evaluation"]["results"])
    ):
        case = f"{index}:{digest(request)}"
        constants = (
            Constant(certificate["evaluation"]["model"], "digest"),
            Constant(case, "symbol"),
        )
        claims.append(Claim("system_case_conforms", constants, id=case))
        verdict = (
            False if result["trace_valid"] is False else result["observed_matches"]
        )
        if verdict is None:
            continue
        names = tuple(sorted(set(result.get("assumptions", ()))))
        relation = "system_case_matches" if verdict else "system_case_differs"
        if names:
            assumed.add(names)
            relation += "_assuming"
            constants += (Constant(_assumption_set(names), "symbol"),)
            for name in names:
                row = constants[:2] + (Constant(name, "symbol"),)
                atom = Atom("system_case_assumes", row)
                facts.append(atom)
                evidence.append(
                    Evidence(
                        f"systemcheck:{certificate['sha256']}:{index}:{name}",
                        atom,
                        source=source,
                        kind="assumption",
                    )
                )
        atom = Atom(relation, constants)
        facts.append(atom)
        evidence.append(
            Evidence(
                "systemcheck:" + certificate["sha256"] + ":" + str(index),
                atom,
                source=source,
            )
        )
    refuting = ("system_case_differs",)
    if assumed:
        relations, rules, refuting = _conditional_rules(
            relations, rules, terms, sorted(assumed)
        )
    return Bundle(
        relations,
        facts=tuple(facts),
        rules=rules,
        claims=tuple(claims),
        evidence=tuple(evidence),
        mappings=tuple(
            EvidenceMapping(
                "system_case_conforms",
                refuted,
                "refutation",
                bindings=(("model", "model"), ("case", "case")),
                claim_id=c.id,
            )
            for c in claims
            for refuted in refuting
        ),
        metadata=(
            ("basis", "normalized-finite-cases"),
            ("certificate", certificate["sha256"]),
        ),
    )


def _assumption_set(names):
    return "+".join(names)


def _conditional_rules(relations, rules, terms, assumption_sets):
    """Relations and rules for verdicts that hold only under named assumptions.

    One rule per distinct assumption set, its body naming every assumption as
    a constant, so a case is decided only while all of its assumptions stand.
    """
    from capcov.claims.ir import Atom, Column, Constant, RelationDecl, Rule, Variable

    columns = (Column("model", "digest"), Column("case", "symbol"))
    under = columns + (Column("assumptions", "symbol"),)
    relations = relations + (
        RelationDecl(
            "system_case_assumes",
            columns + (Column("assumption", "symbol"),),
            producer_classes=("systemcheck",),
        ),
        RelationDecl(
            "system_case_matches_assuming", under, producer_classes=("systemcheck",)
        ),
        RelationDecl(
            "system_case_differs_assuming", under, producer_classes=("systemcheck",)
        ),
        RelationDecl(
            "system_case_differs_conditionally",
            columns,
            modality="derived",
            primitive=False,
        ),
    )
    extra = []
    for names in assumption_sets:
        key = _assumption_set(names)
        body = tuple(
            Atom("system_case_assumes", terms + (Constant(name, "symbol"),))
            for name in names
        )
        for verdict, head, label in (
            ("matches", "system_case_conforms", "system-case-match-assuming"),
            ("differs", "system_case_differs_conditionally", "system-case-differ-assuming"),
        ):
            extra.append(
                Rule(
                    Atom(head, terms),
                    (
                        Atom(
                            f"system_case_{verdict}_assuming",
                            terms + (Constant(key, "symbol"),),
                        ),
                    )
                    + body,
                    f"{label}:{key}",
                )
            )
    return (
        relations,
        rules + tuple(extra),
        ("system_case_differs", "system_case_differs_conditionally"),
    )


def compare_models(left, right, requests, *, fuel=1024, timeout=60):
    """Return observable discrepancies on every supplied case, not trace names."""
    a = evaluate(left, requests, fuel=fuel, timeout=timeout)
    b = evaluate(right, requests, fuel=fuel, timeout=timeout)
    differences = []
    for i, (x, y) in enumerate(zip(a["results"], b["results"])):
        # Admissibility is outcome-sensitive; diagnostics are not observations.
        ax = [r[1:3] for r in x["admissible"]]
        by = [r[1:3] for r in y["admissible"]]
        # The same admissible set under different assumptions is a different
        # answer (spec 4.6); v1 results carry none and compare as before.
        assumed = (x.get("assumptions"), y.get("assumptions"))
        if ax != by or assumed[0] != assumed[1]:
            difference = {"case": i, "request": requests[i], "left": ax, "right": by}
            if assumed != (None, None):
                difference["assumptions"] = {"left": assumed[0], "right": assumed[1]}
            differences.append(difference)
    return {
        "format": "capcov-system-comparison-v1",
        "basis": "supplied-cases",
        "left": a,
        "right": b,
        "differences": differences,
    }


def run_adapter(source, requests, command, *, fuel=1024, timeout=60):
    """Drive a caller-selected JSON adapter; compare its observations in Shen.

    Each process receives one case including the initial state. The adapter is
    responsible for resetting/abstracting the target; no isolation is inferred.
    """
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(x, str) for x in command)
    ):
        raise OperationError("adapter requires an executable argument vector")
    if any("observed" in r or "trace" in r for r in requests):
        raise OperationError("adapter requests cannot prepopulate observations")
    if any(isinstance(r, dict) and bridged(r) for r in requests):
        raise OperationError(
            "capcov-system-adapter-v1 carries v1 requests only, no R02 outcome or invocation"
        )
    evaluate(source, requests, fuel=fuel, timeout=timeout)
    executable = shutil.which(command[0])
    if executable is None:
        raise OperationError("adapter executable unavailable")
    identity = {
        "command": command,
        "executable_sha256": _sha(Path(executable).read_bytes()),
        "file_arguments": {
            str(i): _sha(Path(p).read_bytes())
            for i, p in enumerate(command[1:], 1)
            if Path(p).is_file()
        },
    }
    observed = []
    for request in requests:
        code, stdout, stderr = run_process(
            command,
            input_bytes=canonical(
                {"protocol": "capcov-system-adapter-v1", "request": request}
            ).encode(),
            timeout=timeout,
            max_output=MAX_BYTES,
        )
        if code:
            raise OperationError("adapter process failed")
        try:
            observation = json.loads(stdout)
        except ValueError as exc:
            raise OperationError("adapter returned invalid JSON") from exc
        if not isinstance(observation, dict) or set(observation) != {
            "state",
            "effects",
        }:
            raise OperationError("adapter response requires state and effects")
        observed.append(dict(request, observed=observation))
    certificate = certify(source, observed, fuel=fuel, timeout=timeout)
    return {
        "format": "capcov-system-harness-v1",
        "adapter": identity,
        "certificate": certificate,
        "matches": all(
            r["observed_matches"] is True for r in certificate["evaluation"]["results"]
        ),
    }


def main(argv=None):
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Execute, explore, certify and judge finite Shen systems"
    )
    parser.add_argument(
        "mode",
        choices=(
            "evaluate",
            "explore",
            "certify",
            "recheck",
            "claims",
            "compare",
            "harness",
        ),
    )
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--other", type=Path)
    parser.add_argument("--adapter", nargs="+")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--fuel", type=int, default=1024)
    args = parser.parse_args(argv)
    try:
        source = args.spec.read_text()
        payload = json.loads(args.input.read_text())
        code = 0
        if args.mode == "evaluate":
            result = evaluate(source, payload, fuel=args.fuel, timeout=args.timeout)
            code = int(
                any(
                    r["observed_matches"] is False or r["trace_valid"] is False
                    for r in result["results"]
                )
            )
        elif args.mode == "harness":
            result = run_adapter(
                source, payload, args.adapter, fuel=args.fuel, timeout=args.timeout
            )
            code = int(not result["matches"])
        elif args.mode == "certify":
            result = certify(source, payload, fuel=args.fuel, timeout=args.timeout)
            code = int(
                any(
                    r["observed_matches"] is False or r["trace_valid"] is False
                    for r in result["evaluation"]["results"]
                )
            )
        elif args.mode == "recheck":
            result = {"verified": recheck(source, payload, timeout=args.timeout)}
        elif args.mode == "explore":
            if not isinstance(payload, dict) or set(payload) - {
                "initial",
                "calls",
                "depth",
                "max_nodes",
                "schedule",
            }:
                raise OperationError(
                    "campaign requires initial, calls and optional depth/max_nodes"
                )
            result = explore(source, **payload, fuel=args.fuel, timeout=args.timeout)
            code = int(bool(result["invariant_violations"]))
        elif args.mode == "claims":
            from capcov.claims.ir import canonical_dict
            from capcov.claims.evaluator import evaluate as judge

            bundle = claim_bundle(source, payload, timeout=args.timeout)
            answer = judge(bundle)
            result = {"bundle": canonical_dict(bundle), "evaluation": answer.as_dict()}
            code = int(
                answer.status.value != "complete"
                or any(
                    not c.result.support or c.result.refutation for c in answer.claims
                )
            )
        else:
            if args.other is None:
                raise OperationError("compare requires --other specification")
            result = compare_models(
                source,
                args.other.read_text(),
                payload,
                fuel=args.fuel,
                timeout=args.timeout,
            )
            code = int(bool(result["differences"]))
        text = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.out:
            args.out.write_text(text)
        else:
            print(text, end="")
        return code
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(json.dumps({"operational_failure": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
