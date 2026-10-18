"""Proof artifacts bind a sequent to an independently callable Shen kernel."""

from . import OperationError
from .native import invoke, term
from .system import digest

KERNEL = ("kernel.shen", "proof-check.shen")


def _validate(left, right):
    atoms, count = set(), 0

    def visit(f, depth=0):
        nonlocal count
        count += 1
        if count > 128 or depth > 32 or not isinstance(f, list) or not f:
            raise OperationError("formula structure or budget invalid")
        op = f[0]
        if op == "atom" and len(f) == 2 and isinstance(f[1], str):
            atoms.add(f[1])
        elif op in ("true", "false") and len(f) == 1:
            pass
        elif op == "not" and len(f) == 2:
            visit(f[1], depth + 1)
        elif op in ("and", "or") and len(f) == 3:
            visit(f[1], depth + 1)
            visit(f[2], depth + 1)
        else:
            raise OperationError("invalid propositional formula")

    if not isinstance(left, list) or not isinstance(right, list):
        raise OperationError("sequent contexts must be lists")
    for formula in left + right:
        visit(formula)
    if len(atoms) > 12:
        raise OperationError("proof search supports at most 12 distinct atoms")


def prove(left, right, *, timeout=60):
    return prove_many([(left, right)], timeout=timeout)[0]


def prove_many(sequents, *, timeout=60):
    if not 1 <= len(sequents) <= 256:
        raise OperationError("proof batch requires 1..256 sequents")
    for left, right in sequents:
        _validate(left, right)
    answers, identity = invoke(
        "[" + " ".join(f"(cv.prove {term(l)} {term(r)})" for l, r in sequents) + "]",
        (*KERNEL, "proof-search.shen"),
        timeout=timeout,
    )
    if len(answers) != len(sequents):
        raise OperationError("wrong proof count")
    return [
        _artifact(l, r, answer, identity) for (l, r), answer in zip(sequents, answers)
    ]


def _artifact(left, right, answer, identity):
    _validate(left, right)
    artifact = {
        "format": "capcov-sequent-v1",
        "left": left,
        "right": right,
        "answer": answer,
        "identity": identity,
    }
    artifact["sha256"] = digest(artifact)
    return artifact


def check(artifact, *, left=None, right=None, timeout=60):
    """Check supplied derivation without loading search or the system evaluator.

    Caller-supplied expected contexts prevent substituting another theorem.
    """
    if (
        not isinstance(artifact, dict)
        or set(artifact) != {"format", "left", "right", "answer", "identity", "sha256"}
        or artifact["format"] != "capcov-sequent-v1"
    ):
        raise OperationError("invalid proof envelope")
    if (
        digest({k: v for k, v in artifact.items() if k != "sha256"})
        != artifact["sha256"]
    ):
        raise OperationError("proof digest mismatch")
    if (
        left is not None
        and left != artifact["left"]
        or right is not None
        and right != artifact["right"]
    ):
        raise OperationError("proof sequent does not match obligation")
    _validate(artifact["left"], artifact["right"])
    answer = artifact["answer"]
    if not isinstance(answer, list) or len(answer) != 2 or answer[0] != "proved":
        return False
    valid, identity = invoke(
        f"(cv.checked? {term(artifact['left'])} {term(artifact['right'])} {term(answer[1])})",
        KERNEL,
        timeout=timeout,
    )
    if identity["runtime"] != artifact["identity"].get("runtime") or any(
        artifact["identity"].get("libraries", {}).get(k) != v
        for k, v in identity["libraries"].items()
    ):
        raise OperationError("proof kernel/runtime identity changed")
    return valid is True
