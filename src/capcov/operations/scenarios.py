"""Stateful scenario transport, explicit choice tapes, replay and minimization.

The adapter executes the entire history in one process. Reported control scope
is an adapter declaration, not a claim of hypervisor-level determinism.
"""

import copy
import json
from pathlib import Path
import shutil

from . import OperationError, _sha, MAX_BYTES, _state
from .process import run
from .system import canonical, digest, certify, evaluate, _request


def _identity(command):
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(x, str) for x in command)
    ):
        raise OperationError("adapter requires executable argument vector")
    executable = shutil.which(command[0])
    if not executable:
        raise OperationError("adapter executable unavailable")
    return {
        "command": command,
        "executable": _sha(Path(executable).read_bytes()),
        "file_arguments": {
            str(i): _sha(Path(p).read_bytes())
            for i, p in enumerate(command[1:], 1)
            if Path(p).is_file()
        },
    }


def _payload(scenario, fuel):
    if not isinstance(scenario, dict) or set(scenario) != {"initial", "steps"}:
        raise OperationError("scenario requires initial and steps")
    _state(scenario["initial"])
    if not isinstance(scenario["steps"], list) or not 1 <= len(scenario["steps"]) <= 64:
        raise OperationError("scenario needs 1..64 steps")
    steps = []
    for step in scenario["steps"]:
        if (
            not isinstance(step, dict)
            or set(step) - {"call", "choice", "result"}
            or not {"call", "choice"} <= set(step)
        ):
            raise OperationError("scenario step requires call and choice")
        call = step["call"]
        if not isinstance(call, dict) or set(call) != {"command", "args", "outcome"}:
            raise OperationError("scenario call requires command, args, outcome")
        _request(dict(call, state=scenario["initial"]), fuel)
        if step["choice"] not in ("0", "1"):
            raise OperationError("executable scenario choice must be 0 or 1")
        if step["choice"] == "1" and call["outcome"] != "unknown":
            raise OperationError("choice 1 requires unknown outcome")
        # Expected model results never cross the observation boundary.
        steps.append({"call": copy.deepcopy(call), "choice": step["choice"]})
    return {
        "protocol": "capcov-scenario-adapter-v1",
        "initial": copy.deepcopy(scenario["initial"]),
        "steps": steps,
    }


def _observe(command, payload, timeout):
    code, stdout, _ = run(
        command,
        input_bytes=canonical(payload).encode(),
        timeout=timeout,
        max_output=4 * MAX_BYTES,
    )
    if code:
        raise OperationError("scenario adapter process failed")
    try:
        response = json.loads(stdout)
    except ValueError as exc:
        raise OperationError("scenario adapter returned invalid JSON") from exc
    if (
        not isinstance(response, dict)
        or set(response) != {"protocol", "observations", "choices", "controls"}
        or response["protocol"] != payload["protocol"]
    ):
        raise OperationError("invalid scenario adapter response")
    if response["choices"] != [s["choice"] for s in payload["steps"]]:
        raise OperationError("adapter did not acknowledge exact choice tape")
    if (
        not isinstance(response["controls"], list)
        or not all(isinstance(c, str) for c in response["controls"])
        or len(set(response["controls"])) != len(response["controls"])
    ):
        raise OperationError("adapter controls must be distinct names")
    observations = response["observations"]
    if not isinstance(observations, list) or len(observations) != len(payload["steps"]):
        raise OperationError("adapter must return one observation per step")
    for obs in observations:
        if not isinstance(obs, dict) or set(obs) != {"state", "effects"}:
            raise OperationError("observation requires state and effects")
        _state(obs["state"])
    return response


def run_scenario(source, scenario, command, *, fuel=1024, timeout=60, replay=True):
    payload = _payload(scenario, fuel)
    identity = _identity(command)
    # Validate construction before invoking consumer code. Subsequent model
    # checks use observed predecessor states, not oracle-generated successors.
    evaluate(
        source,
        [dict(payload["steps"][0]["call"], state=payload["initial"])],
        fuel=fuel,
        timeout=timeout,
    )
    observation = _observe(command, payload, timeout)
    repeat = _observe(command, payload, timeout) if replay else None
    if _identity(command) != identity:
        raise OperationError("adapter changed during scenario")
    state, requests = payload["initial"], []
    for step, obs in zip(payload["steps"], observation["observations"]):
        call = dict(step["call"])
        # Fix the modeled uncertainty to the selected tape branch.
        if call["outcome"] == "unknown":
            call["outcome"] = "aborted" if step["choice"] == "0" else "committed"
        requests.append(dict(call, state=state, observed=obs))
        checked = evaluate(source, [requests[-1]], fuel=fuel, timeout=timeout)[
            "results"
        ][0]
        if checked["observed_matches"] is not True:
            break
        state = obs["state"]
    certificate = certify(source, requests, fuel=fuel, timeout=timeout)
    mismatches = [
        i
        for i, r in enumerate(certificate["evaluation"]["results"])
        if r["observed_matches"] is not True
    ]
    result = {
        "format": "capcov-scenario-run-v1",
        "adapter": identity,
        "input": payload,
        "observed": observation,
        "replayed": repeat,
        "replay_matches": None if repeat is None else observation == repeat,
        "mismatches": mismatches,
        "checked_steps": len(requests),
        "certificate": certificate,
        "scope": "adapter-declared controls; equality of two observed histories does not prove environmental determinism",
    }
    result["sha256"] = digest(result)
    return result


def minimize(source, scenario, command, *, fuel=1024, timeout=60, max_runs=64):
    """Deletion-minimal deterministic conformance discrepancy within run budget.

    Operational failures do not count as reproducing the target discrepancy.
    The first mismatching command must remain the same, preventing bug switching
    to a different operation. Domain-specific failure equivalence remains a
    consumer responsibility.
    """
    if type(max_runs) is not int or not 1 <= max_runs <= 256:
        raise OperationError("minimization budget must be 1..256")
    best = copy.deepcopy(scenario)
    report = run_scenario(source, best, command, fuel=fuel, timeout=timeout)
    if report["replay_matches"] is not True or not report["mismatches"]:
        raise OperationError(
            "minimization requires a reproducible conformance mismatch"
        )
    target = report["input"]["steps"][report["mismatches"][0]]["call"]["command"]
    runs, changed, exhausted = 1, True, False
    while changed and len(best["steps"]) > 1:
        changed = False
        for i in range(len(best["steps"])):
            if runs >= max_runs:
                exhausted = True
                break
            candidate = copy.deepcopy(best)
            candidate["steps"].pop(i)
            runs += 1
            try:
                trial = run_scenario(
                    source, candidate, command, fuel=fuel, timeout=timeout
                )
            except OperationError:
                continue
            if trial["adapter"] != report["adapter"] or any(
                trial["certificate"]["evaluation"][k]
                != report["certificate"]["evaluation"][k]
                for k in ("model", "runtime", "libraries")
            ):
                raise OperationError("execution identity changed during minimization")
            if (
                trial["replay_matches"] is True
                and trial["mismatches"]
                and trial["input"]["steps"][trial["mismatches"][0]]["call"]["command"]
                == target
            ):
                best, report, changed = candidate, trial, True
                break
        if exhausted:
            break
    return {
        "format": "capcov-scenario-minimization-v1",
        "scenario": best,
        "report": report,
        "runs": runs,
        "minimal_under_single_step_deletion": not exhausted,
        "budget_exhausted": exhausted,
        "failure_command": target,
    }
