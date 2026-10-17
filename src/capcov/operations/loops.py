"""Invariant induction for snapshot loops in executable system specifications.

The existing weakest-precondition compiler remains a trusted transformation.
Shen checks the resulting sequents and loop-rule composition, without assuming
runtime postcondition checks or equality between captured and current rows.
"""

import copy
from importlib import resources
from pathlib import Path

from . import OperationError, _sha
from . import completion
from .compiler import model, wp, formula, _distinct, _instances, _unfreeze, Unresolved
from .native import invoke, term
from .proofs import KERNEL, _validate, prove_many, check
from .system import _term, SYSTEM_LIBRARIES, digest


def _compiler_identity():
    from . import compiler

    return {
        "loops": _sha(Path(__file__).read_bytes()),
        "wp": _sha(Path(compiler.__file__).read_bytes()),
        "completion": _sha(Path(completion.__file__).read_bytes()),
        "completion_types": _sha(
            resources.files("capcov.operations")
            .joinpath("shen", "completion-types.shen")
            .read_bytes()
        ),
        "rule": _sha(
            resources.files("capcov.operations")
            .joinpath("shen", "loop-check.shen")
            .read_bytes()
        ),
    }


def _loops(actions):
    result = {}
    for _, name, action in actions:
        if action[0] == "for-each":
            result[name] = action
            result.update(_loops(action[3]))
        elif action[0] == "choose":
            result.update(_loops(action[2]))
            result.update(_loops(action[3]))
    return result


def _captured(node, names):
    """Replace only free references to the current captured row.

    Quantifiers and inner loops introduce their own row binding. Never substitute
    through them, even when they use the same table or field names.
    """
    if not isinstance(node, list) or not node:
        return node
    if node == ["row-key"]:
        return ["argument", names["key"]]
    if node[0] == "row-field":
        return ["argument", names["fields"][node[1]]]
    if isinstance(node[0], str) and node[0] in ("every-row", "some-row", "for-each"):
        return copy.deepcopy(node)
    return [_captured(x, names) for x in node]


def _prepare(source, invariants, timeout):
    m = model(source)
    if not isinstance(invariants, dict) or not invariants:
        raise OperationError("provide a nonempty command-to-loop invariant mapping")
    commands = {c[1]: c for c in m[3]}
    predicates, judgments = {}, ["(caps.typechecks? M)"]
    for command, contracts in sorted(invariants.items()):
        if command not in commands or not isinstance(contracts, dict) or not contracts:
            raise OperationError(
                "invariants reference an unknown command or empty mapping"
            )
        loops = _loops(commands[command][4])
        predicates[command] = {}
        for name, contract in sorted(contracts.items()):
            if name not in loops:
                raise OperationError("invariant references an unknown loop")
            if isinstance(contract, str):
                contract = {"invariant": contract}
            if (
                not isinstance(contract, dict)
                or not {"invariant"} <= set(contract)
                or set(contract) - {"invariant", "completes"}
            ):
                raise OperationError(
                    "loop contract requires invariant and optional completes"
                )
            predicates[command][name] = {}
            for kind, predicate in sorted(contract.items()):
                p = _term(predicate)
                predicates[command][name][kind] = model(predicate)
                row = "no-row" if kind == "invariant" else term(loops[name][1])
                args = term(commands[command][2])
                if kind == "invariant":
                    args = "[caps.before | " + args + "]"
                judgments.append(
                    f"(and (= caps-pred (shen.typecheck (capop.syntax {p}) caps-pred)) "
                    f"(caps.scope-pred? {p} {args} {row} (nth 3 M)))"
                )
    valid, identity = invoke(
        f"(let M {_term(source)} [" + " ".join(judgments) + "])",
        SYSTEM_LIBRARIES,
        timeout=timeout,
    )
    if not all(v is True for v in valid):
        raise OperationError(
            "model or loop invariant failed Shen construction judgment"
        )
    return m, predicates, identity


def _derive(source, invariants, timeout):
    m, predicates, identity = _prepare(source, invariants, timeout)
    obligations, rules = [], []

    def add(identifier, left, right):
        if len(obligations) >= 256:
            raise OperationError("loop proof exceeds 256 obligations")
        _validate(left, right)
        obligations.append({"id": identifier, "left": left, "right": right})
        return len(obligations) - 1

    for _, command, args, pre, actions, post in m[3]:
        if command not in predicates:
            continue
        loops = _loops(actions)
        contracts = predicates[command]
        # Fresh rigid parameters stand for arbitrary immutable snapshot values.
        # They cannot collide with any source parameter or one another.
        used, bindings = set(args), {}
        for name, action in loops.items():
            fields = next(t[2] for t in m[2] if t[1] == action[1])
            fields = [f if isinstance(f, str) else f[1] for f in fields]

            def fresh():
                index = len(used)
                while f"$snapshot:{index}" in used:
                    index += 1
                value = f"$snapshot:{index}"
                used.add(value)
                return value

            bindings[name] = {"key": fresh(), "fields": {f: fresh() for f in fields}}
        preservation, completions = {}, {}

        def loop(name, action, continuation):
            if name not in contracts:
                # Existing frame/deletion rules remain available. A loop that
                # needs induction and lacks a contract remains unresolved.
                return wp([["named", name, action]], continuation)
            invariant = contracts[name]["invariant"]
            completed = None
            if "completes" in contracts[name]:
                if name not in completions:
                    completed = completion.derive(
                        action, contracts[name]["completes"], bindings[name], _captured
                    )
                    completed["step"] = add(
                        f"{command}:loop:{name}:complete",
                        completed["left"],
                        completed["right"],
                    )
                    completions[name] = completed
                completed = completions[name]
            if name not in preservation:
                body = _captured(action[3], bindings[name])
                body_wp = wp(body, invariant, _distinct(invariant), loop=loop)
                # No global invariant or command precondition is assumed at
                # intermediate states unless the loop invariant entails it.
                instances = _instances([("loop", invariant)], body)
                left = [
                    formula(invariant),
                    *[formula(i["predicate"]) for i in instances],
                ]
                step = add(f"{command}:loop:{name}:preserve", left, [formula(body_wp)])
                preservation[name] = (step, left, formula(body_wp))
            step, left, body_formula = preservation[name]
            exit_index = add(
                f"{command}:loop:{name}:exit:{len(obligations)}",
                [formula(invariant)]
                + ([formula(completed["established"])] if completed else []),
                [formula(continuation)],
            )
            rules.append(
                {
                    "invariant": formula(invariant),
                    "body_wp": body_formula,
                    "premises": left,
                    "continuation": formula(continuation),
                    "preservation": step,
                    "exit": exit_index,
                    **({"completion": completed} if completed else {}),
                }
            )
            if completed and completed["coverage"] != ["yes"]:
                return ["both", invariant, completed["coverage"]]
            return invariant

        goals = [("postcondition", post), *[("invariant:" + n, p) for n, p in m[4]]]
        for label, goal in goals:
            try:
                weakest = _unfreeze(wp(actions, goal, _distinct(pre), loop=loop))
                instances = _instances(m[4], [pre, actions, post])
                left = [
                    formula(pre),
                    *[formula(p) for _, p in m[4]],
                    *[formula(i["predicate"]) for i in instances],
                ]
                add(f"{command}:{label}:initiation", left, [formula(weakest)])
            except (Unresolved, OperationError) as exc:
                obligations.append(
                    {"id": f"{command}:{label}:unresolved", "reason": str(exc)}
                )
    return obligations, rules, identity


def prove_loops(source, invariants, *, timeout=60):
    invariants = copy.deepcopy(invariants)
    obligations, rules, identity = _derive(source, invariants, timeout)
    pending = [o for o in obligations if "reason" not in o]
    if pending:
        for item, proof in zip(
            pending,
            prove_many([(o["left"], o["right"]) for o in pending], timeout=timeout),
        ):
            item["proof"] = proof
            item["status"] = "proved" if proof["answer"][0] == "proved" else "open"
    for item in obligations:
        if "reason" in item:
            item["status"] = "open"
    artifact = {
        "format": "capcov-loop-induction-v1",
        "model": _sha(source.encode()),
        "invariants": invariants,
        "compiler": _compiler_identity(),
        "identity": identity,
        "obligations": obligations,
        "rules": rules,
        "status": "proved"
        if all(o["status"] == "proved" for o in obligations)
        else "open",
        "scope": "partial correctness of annotated commands over finite snapshot loops; expression totality, fuel sufficiency and implementation refinement are separate",
    }
    artifact["sha256"] = digest(artifact)
    return artifact


def check_loops(source, artifact, *, invariants=None, timeout=60):
    """Regenerate obligations from source and check proofs without proof search."""
    if (
        not isinstance(artifact, dict)
        or set(artifact)
        != {
            "format",
            "model",
            "invariants",
            "compiler",
            "identity",
            "obligations",
            "rules",
            "status",
            "scope",
            "sha256",
        }
        or artifact["format"] != "capcov-loop-induction-v1"
        or digest({k: v for k, v in artifact.items() if k != "sha256"})
        != artifact["sha256"]
    ):
        raise OperationError("invalid loop certificate")
    if (
        artifact["model"] != _sha(source.encode())
        or artifact["compiler"] != _compiler_identity()
    ):
        raise OperationError("loop model or compiler identity changed")
    if invariants is not None and invariants != artifact["invariants"]:
        raise OperationError("loop invariants do not match requested theorem")
    expected, rules, identity = _derive(source, artifact["invariants"], timeout)
    if identity != artifact["identity"] or rules != artifact["rules"]:
        raise OperationError("loop rule or native identity changed")
    supplied = artifact["obligations"]
    if not isinstance(supplied, list) or len(expected) != len(supplied):
        raise OperationError("missing loop obligations")
    valid = True
    for obligation, item in zip(expected, supplied):
        if (
            not isinstance(item, dict)
            or {k: v for k, v in item.items() if k not in ("proof", "status")}
            != obligation
        ):
            raise OperationError("substituted loop obligation")
        if "reason" in obligation:
            valid = False
        elif not check(
            item["proof"],
            left=obligation["left"],
            right=obligation["right"],
            timeout=timeout,
        ):
            valid = False
    if not valid:
        return False
    expressions = []
    for rule in rules:
        step = supplied[rule["preservation"]]["proof"]["answer"][1]
        exit_proof = supplied[rule["exit"]]["proof"]["answer"][1]
        if "completion" in rule:
            c = rule["completion"]
            completion_proof = supplied[c["step"]]["proof"]["answer"][1]
            # This judgment has an actual Shen sequent-calculus datatype.
            judgment = [
                "snapshot-partition",
                rule["invariant"],
                formula(c["established"]),
                c["left"],
                c["right"][0],
                rule["continuation"],
            ]
            expressions.append(
                f"(cl.completed {term(judgment)} {term(c['table'])} {term(c['body'])} "
                f"{term(rule['premises'])} {term(rule['body_wp'])} "
                f"{term(step)} {term(completion_proof)} {term(exit_proof)})"
            )
        else:
            expressions.append(
                f"(cl.loop {term(rule['premises'])} {term(rule['invariant'])} "
                f"{term(rule['body_wp'])} {term(rule['continuation'])} {term(step)} {term(exit_proof)})"
            )
    results, native = invoke(
        "[" + " ".join(expressions) + "]",
        (*KERNEL, "completion-types.shen", "loop-check.shen"),
        timeout=timeout,
    )
    if native["libraries"]["loop-check.shen"] != artifact["compiler"]["rule"]:
        raise OperationError("loop composition rule changed")
    if (
        native["libraries"]["completion-types.shen"]
        != artifact["compiler"]["completion_types"]
    ):
        raise OperationError("completion datatype identity changed")
    return all(result is True for result in results)
