"""Unbounded safety induction over explicit Boolean transition relations.

Atoms name state predicates. Their interpretation in application code is a
separate refinement obligation; this module never infers that correspondence.
"""

import copy
from importlib import resources


from . import OperationError, _sha
from .native import invoke, term
from .proofs import KERNEL, _validate, prove_many, check
from .system import digest


def _rule_identity():
    return _sha(
        resources.files("capcov.operations")
        .joinpath("shen", "induction-check.shen")
        .read_bytes()
    )


def prime(formula):
    if formula[0] == "atom":
        return ["atom", "next:" + formula[1]]
    return [formula[0], *(prime(x) for x in formula[1:])]


def obligations(system):
    if not isinstance(system, dict) or set(system) != {
        "variables",
        "initial",
        "invariant",
        "safety",
        "transitions",
    }:
        raise OperationError(
            "induction requires variables, initial, invariant, safety, transitions"
        )
    variables = system["variables"]
    if (
        not isinstance(variables, list)
        or not 1 <= len(variables) <= 6
        or any(
            not isinstance(v, str) or not v or v.startswith("next:") for v in variables
        )
        or len(set(variables)) != len(variables)
    ):
        raise OperationError(
            "induction requires 1..6 distinct current-state variable names"
        )
    current = set(variables)

    def validate(formula, allowed):
        _validate([formula], [])

        def visit(f):
            if f[0] == "atom" and f[1] not in allowed:
                raise OperationError("undeclared or next-state atom in state predicate")
            for child in f[1:]:
                if isinstance(child, list):
                    visit(child)

        visit(formula)

    for name in ("initial", "invariant", "safety"):
        validate(system[name], current)
    transitions = system["transitions"]
    if not isinstance(transitions, dict) or not 1 <= len(transitions) <= 64:
        raise OperationError("induction requires 1..64 named transitions")
    initial, invariant, safety = (system[n] for n in ("initial", "invariant", "safety"))
    result = [("base", [initial], [invariant]), ("safety", [invariant], [safety])]
    if not all(isinstance(name, str) and name for name in transitions):
        raise OperationError("transition needs a nonempty name")
    for name, relation in sorted(transitions.items()):
        if not isinstance(name, str) or not name:
            raise OperationError("transition needs a nonempty name")
        validate(relation, current | {"next:" + v for v in variables})
        result.append(("step:" + name, [invariant, relation], [prime(invariant)]))
    for _, left, right in result:
        _validate(left, right)
    return result


def prove_induction(system, *, timeout=60):
    system = copy.deepcopy(system)
    sequents = obligations(system)
    proofs = prove_many([(l, r) for _, l, r in sequents], timeout=timeout)
    artifact = {
        "format": "capcov-induction-v1",
        "system": system,
        "rule": _rule_identity(),
        "obligations": [
            {"id": n, "proof": p} for (n, _, _), p in zip(sequents, proofs)
        ],
        "status": "proved"
        if all(p["answer"][0] == "proved" for p in proofs)
        else "open",
    }
    artifact["sha256"] = digest(artifact)
    if artifact["status"] == "proved" and not check_induction(
        artifact, system=system, timeout=timeout
    ):
        raise OperationError("induction composition failed")
    return artifact


def check_induction(artifact, *, system=None, timeout=60):
    if (
        not isinstance(artifact, dict)
        or set(artifact)
        != {"format", "system", "obligations", "status", "sha256", "rule"}
        or artifact["format"] != "capcov-induction-v1"
        or digest({k: v for k, v in artifact.items() if k != "sha256"})
        != artifact["sha256"]
    ):
        raise OperationError("invalid induction envelope")
    if artifact["rule"] != _rule_identity():
        raise OperationError("induction rule identity changed")
    if artifact["status"] not in ("open", "proved"):
        raise OperationError("invalid induction status")
    if system is not None and system != artifact["system"]:
        raise OperationError("induction theorem does not match requested system")
    system = artifact["system"]
    sequents = obligations(system)
    supplied = artifact["obligations"]
    if not isinstance(supplied, list) or len(supplied) != len(sequents):
        raise OperationError("missing induction obligations")
    derivations = []
    for item, (name, left, right) in zip(supplied, sequents):
        if (
            not isinstance(item, dict)
            or set(item) != {"id", "proof"}
            or item["id"] != name
        ):
            raise OperationError("substituted induction obligation")
        if not check(item["proof"], left=left, right=right, timeout=timeout):
            return False
        derivations.append(item["proof"]["answer"][1])
    # The Shen composition rule reconstructs priming and all sequents itself.
    valid, identity = invoke(
        f"(ci.check {term(system['initial'])} {term(system['invariant'])} "
        f"{term(system['safety'])} {term([system['transitions'][n] for n in sorted(system['transitions'])])} {term(derivations)})",
        (*KERNEL, "induction-check.shen"),
        timeout=timeout,
    )
    if identity["libraries"]["induction-check.shen"] != artifact["rule"]:
        raise OperationError("induction rule changed during checking")
    return valid is True
