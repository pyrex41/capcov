"""Goal-directed bounded relational search in Shen Prolog."""

import copy
from . import OperationError, _state, _string, _sha
from .native import invoke, term
from .system import (
    _term,
    _pairs,
    _request,
    SYSTEM_LIBRARIES,
    digest,
    json_state,
    evaluate,
)


def search(
    source, initial, calls, goal, *, depth=4, budget=10000, fuel=1024, timeout=60
):
    generator = None
    if isinstance(calls, dict):
        from .relations import solve

        if set(calls) != {
            "relation",
            "inputs",
            "command",
            "outcome",
            "arguments",
        } or not isinstance(calls["arguments"], dict):
            raise OperationError(
                "call generator requires relation, inputs, command, outcome, arguments"
            )
        generator = {"specification": copy.deepcopy(calls)}
        solved = solve(
            calls["relation"], calls["inputs"], budget=budget, timeout=timeout
        )
        generator["evaluation"] = solved
        if not set(calls["arguments"].values()) <= set(calls["relation"]["outputs"]):
            raise OperationError("call argument mapping references non-output variable")
        calls = [
            {
                "command": calls["command"],
                "outcome": calls["outcome"],
                "args": {
                    name: solution["outputs"][variable]
                    for name, variable in calls["arguments"].items()
                },
            }
            for solution in solved["solutions"]
        ]
    if type(depth) is not int or not 0 <= depth <= 16:
        raise OperationError("search depth must be 0..16")
    if type(budget) is not int or not 1 <= budget <= 65536:
        raise OperationError("search budget must be 1..65536")
    if type(fuel) is not int or not 1 <= fuel <= 4096:
        raise OperationError("fuel must be 1..4096")
    if not isinstance(calls, list) or not 1 <= len(calls) <= 64:
        raise OperationError("search requires 1..64 calls")
    call_terms = []
    for c in calls:
        if not isinstance(c, dict) or set(c) != {"command", "args", "outcome"}:
            raise OperationError("search calls require command, args and outcome")
        _request(dict(c, state=initial), fuel)
        call_terms.append(
            f"[{_string(c['command'])} {_pairs(c['args'])} {c['outcome']}]"
        )
    if not isinstance(goal, dict):
        raise OperationError("goal must be a tagged object")
    if set(goal) == {"state"} and isinstance(goal["state"], str):
        # Reuse the restricted reader; native type/scope judgment follows below.
        pred = _term(goal["state"])
        goal_term = f"[{_string('state')} {pred}]"
        guard = f"(and (= caps-pred (shen.typecheck (capop.syntax {pred}) caps-pred)) (caps.scope-pred? {pred} [] no-row (caps.tables M)))"
    elif (
        set(goal) == {"emitted", "count"}
        and isinstance(goal["emitted"], str)
        and type(goal["count"]) is int
        and 1 <= goal["count"] <= 4096
    ):
        goal_term, guard = term(["emitted", goal["emitted"], goal["count"]]), "true"
    elif goal == {"violation": True}:
        goal_term, guard = term(["violation"]), "true"
    else:
        raise OperationError(
            "goal requires state predicate, emitted/count, or violation=true"
        )
    expr = (
        f"(let M {_term(source)} (if {guard} "
        f"(cv.find M {_state(initial)} [{' '.join(call_terms)}] {goal_term} {depth} {fuel} {budget}) "
        '(error "search: invalid goal scope")))'
    )
    answer, identity = invoke(expr, (*SYSTEM_LIBRARIES, "search.shen"), timeout=timeout)
    scenario = None
    if answer[0] == "witness":
        scenario = {"initial": copy.deepcopy(initial), "steps": []}
        for call, index, result in answer[1]:
            scenario["steps"].append(
                {
                    "call": {
                        "command": call[0],
                        "args": dict(call[1]),
                        "outcome": call[2],
                    },
                    "choice": index,
                    "result": result,
                }
            )
        verify_witness(source, scenario, fuel=fuel, timeout=timeout)
    report = {
        "format": "capcov-relational-search-v1",
        "model": _sha(source.encode()),
        "identity": identity,
        "generator": generator,
        "domain": {
            "initial": initial,
            "calls": calls,
            "goal": goal,
            "depth": depth,
            "budget": budget,
            "fuel": fuel,
        },
        "status": "witness" if scenario is not None else "exhausted-within-bounds",
        "scenario": scenario,
    }
    report["sha256"] = digest(report)
    return report


def verify_witness(source, scenario, *, fuel=1024, timeout=60):
    """Reexecute every selected branch, including edges with equal successor states."""
    state = scenario["initial"]
    for i, step in enumerate(scenario["steps"]):
        result = evaluate(
            source, [dict(step["call"], state=state)], fuel=fuel, timeout=timeout
        )["results"][0]
        if step["choice"] == "violation":
            if (
                i != len(scenario["steps"]) - 1
                or step["result"] != ["rejected", "invariant"]
                or result["transition"] != step["result"]
            ):
                raise OperationError("invalid invariant witness")
        else:
            try:
                n = int(step["choice"])
                if (
                    str(n) != step["choice"]
                    or n < 0
                    or result["admissible"][n] != step["result"]
                ):
                    raise ValueError()
            except (ValueError, IndexError, TypeError) as exc:
                raise OperationError("invalid witness choice") from exc
            state = json_state(step["result"][1])
    return True
