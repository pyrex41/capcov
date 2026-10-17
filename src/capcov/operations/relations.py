"""Typed finite relational plans with checked modes and solution cardinality."""

from . import OperationError
from .native import invoke, term
from .system import SYSTEM_LIBRARIES, digest

LIBRARIES = (*SYSTEM_LIBRARIES, "proof-check.shen", "search.shen", "relations.shen")


def validate(program):
    if not isinstance(program, dict) or set(program) != {
        "variables",
        "inputs",
        "outputs",
        "capabilities",
        "determinism",
        "body",
    }:
        raise OperationError(
            "relational program needs variables, inputs, outputs, capabilities, determinism, body"
        )
    types = program["variables"]
    if (
        not isinstance(types, dict)
        or len(types) > 64
        or any(
            not isinstance(k, str) or v not in ("text", "int32")
            for k, v in types.items()
        )
    ):
        raise OperationError("variables require text/int32 sorts")
    for key in ("inputs", "outputs", "capabilities"):
        xs = program[key]
        if (
            not isinstance(xs, list)
            or not all(isinstance(x, str) for x in xs)
            or len(set(xs)) != len(xs)
        ):
            raise OperationError("mode names must be distinct strings")
        if key != "capabilities" and not set(xs) <= types.keys():
            raise OperationError("mode names undeclared variables")
    if program["determinism"] not in ("det", "semidet", "multi", "nondet"):
        raise OperationError("unknown determinism category")
    count = 0

    def walk(g, depth=0):
        nonlocal count
        count += 1
        if count > 128 or depth > 24 or not isinstance(g, list) or not g:
            raise OperationError("invalid or oversized relational goal")
        tag = g[0]
        arities = {
            "literal": 3,
            "domain": 3,
            "equal": 3,
            "less": 3,
            "add": 4,
            "consume": 2,
            "all": 2,
            "any": 2,
        }
        if tag not in arities or len(g) != arities[tag]:
            raise OperationError("unknown relational goal")
        if tag in ("all", "any"):
            if not isinstance(g[1], list):
                raise OperationError("goal composition needs a list")
            for child in g[1]:
                walk(child, depth + 1)
        elif tag == "consume":
            if g[1] not in program["capabilities"]:
                raise OperationError("undeclared capability")
        else:
            names = g[1:] if tag in ("equal", "less", "add") else g[1:2]
            if any(not isinstance(n, str) or n not in types for n in names):
                raise OperationError("undeclared relational variable")
            if tag in ("less", "add") and any(types[n] != "int32" for n in names):
                raise OperationError("numeric goal requires int32 variables")
            if tag == "equal" and types[g[1]] != types[g[2]]:
                raise OperationError("equality sort mismatch")
            if tag == "literal":
                value_ok(g[2], types[g[1]])
            if tag == "domain":
                if not isinstance(g[2], list) or len(g[2]) > 64:
                    raise OperationError("domain requires at most 64 values")
                for value in g[2]:
                    value_ok(value, types[g[1]])
                if len(set(g[2])) != len(g[2]):
                    raise OperationError("duplicate domain value")

    walk(program["body"])


def value_ok(value, sort):
    if not isinstance(value, str) or len(value.encode()) > 4096:
        raise OperationError("relational values require bounded strings")
    if sort == "int32":
        try:
            n = int(value)
            if str(n) != value or not -2147483648 <= n <= 2147483647:
                raise ValueError()
        except ValueError as exc:
            raise OperationError("noncanonical int32 relational value") from exc


def _args(program):
    return " ".join(
        term(program[k])
        for k in ("body", "inputs", "outputs", "capabilities", "determinism")
    )


def compile_relation(program, *, timeout=60):
    validate(program)
    analysis, identity = invoke(
        f"(cr.compile {_args(program)})", LIBRARIES, timeout=timeout
    )
    return {
        "format": "capcov-relation-compilation-v1",
        "program": digest(program),
        "ground": analysis[0],
        "remaining_capabilities": analysis[1],
        "minimum_solutions": int(analysis[2]),
        "maximum_solutions": int(analysis[3]),
        "cardinality_encoding": "2 means two or more",
        "identity": identity,
    }


def solve(program, inputs, *, budget=10000, timeout=60):
    validate(program)
    if not isinstance(inputs, dict) or set(inputs) != set(program["inputs"]):
        raise OperationError("relation input names do not match mode")
    if type(budget) is not int or not 1 <= budget <= 65536:
        raise OperationError("relation budget must be 1..65536")
    for name, value in inputs.items():
        value_ok(value, program["variables"][name])
    answers, identity = invoke(
        f"(cr.run {_args(program)} {term([[k, v] for k, v in sorted(inputs.items())])} {budget})",
        LIBRARIES,
        timeout=timeout,
    )
    solutions = [
        {
            "outputs": {k: dict(env)[k] for k in program["outputs"]},
            "remaining_capabilities": caps,
        }
        for env, caps in answers
    ]
    return {
        "format": "capcov-relation-solutions-v1",
        "program": digest(program),
        "inputs": inputs,
        "solutions": solutions,
        "identity": identity,
    }
