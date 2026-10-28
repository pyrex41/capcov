"""Fresh, scoped check execution and fail-closed cutover qualification.

The checked-in check plan is trusted consumer policy, just like capcov's exact
outcome/test mapping. Digests detect drift; they do not authenticate a producer
or turn a test into a universal proof. No execution occurs during gate/report.
"""

import copy
import json
import math
import uuid
from pathlib import Path

from capcov.operations.process import run
from capcov.operations.system import digest
from .registry import (fields, names, require, text, scope, inspect, validate,
                       file_hash, path, CRITICAL, METHODS)


def check_plan(plan, registry):
    fields(plan, {"format", "checks"})
    require(plan["format"] == "capcov-behavior-checks-v1", "unsupported check plan")
    require(isinstance(plan["checks"], list) and plan["checks"], "empty check plan")
    names([c.get("id") for c in plan["checks"] if isinstance(c, dict)])
    _, _, obligations = validate(registry)
    for c in plan["checks"]:
        fields(c, {"id", "behavior", "obligations", "method", "timeout", "inputs"}, {"argv", "engine", "observe"})
        selected = names(c["obligations"])
        require(selected and selected <= obligations.keys(), "unknown or empty check obligations")
        require(c["method"] in METHODS, "unknown check method")
        require(all(obligations[o][0] == c["behavior"] and obligations[o][1]["method"] == c["method"]
                    for o in selected), "check scope or evidence method mismatch")
        if "engine" in c:
            require(c["engine"] == "shencheck-effects-v1" and "argv" not in c and c["method"] == "model-check",
                    "unsupported engine or evidence method")
        else:
            require("observe" not in c, "observer requires ShenCheck engine")
            require(isinstance(c.get("argv"), list) and c["argv"], "check needs argv")
            for arg in c["argv"]:
                text(arg)
                require("\0" not in arg, "NUL in argv")
        if "observe" in c:
            require(isinstance(c["observe"], list) and c["observe"], "observer needs argv")
            for arg in c["observe"]:
                text(arg)
                require("\0" not in arg, "NUL in observer argv")
        require(type(c["timeout"]) in (int, float) and math.isfinite(c["timeout"])
                and 0 < c["timeout"] <= 3600, "invalid check timeout")
        require(isinstance(c["inputs"], list) and c["inputs"]
                and len(c["inputs"]) == len(set(c["inputs"])), "enroll check inputs")
        for p in c["inputs"]:
            path(".", p)
    return True


def seal(record):
    result = copy.deepcopy(record)
    result["sha256"] = digest(record)
    return result


def inputs_identity(check, root):
    return {p: file_hash(root, p) for p in check["inputs"]}


def execute_checks(registry, plan, root, behaviors, output, *, toolchain=None):
    check_plan(plan, registry)
    selected = scope(registry, behaviors)
    before = inspect(registry, root, behaviors)
    require(not before["stale"], "cannot execute checks against stale artifacts")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    require(not list(output.iterdir()), "evidence directory must be empty")
    allowed = {b["id"] for b in selected["behaviors"]}
    receipts = []
    for c in plan["checks"]:
        if c["behavior"] not in allowed:
            continue
        nonce = uuid.uuid4().hex
        inputs = inputs_identity(c, root)
        check_scope = digest(scope(registry, [c["behavior"]]))
        status, error = "complete", None
        engine_result = None
        try:
            if "engine" in c:
                from .shencheck import execute
                code, stdout, stderr, engine_result = execute(output / (nonce + ".engine"), toolchain,
                    timeout=c["timeout"], observer=c.get("observe"), cwd=root)
            else:
                code, stdout, stderr = run(c["argv"], cwd=Path(root).resolve(), timeout=c["timeout"])
        except (OSError, ValueError) as exc:
            code, stdout, stderr = None, b"", b""
            status, error = "operational-failure", type(exc).__name__
        # Fresh execution is distinct from semantic interpretation of its check.
        if inputs != inputs_identity(c, root) or inspect(registry, root, [c["behavior"]])["stale"]:
            status = "stale"
        logs = {}
        for label, data in (("stdout", stdout), ("stderr", stderr)):
            dest = output / (nonce + "." + label)
            dest.write_bytes(data)
            dest.chmod(0o600)
            logs[label] = {"path": dest.name, "sha256": file_hash(output, dest.name)}
        receipt = seal({"format": "capcov-behavior-check-v1", "run": nonce,
                        "check": c["id"], "check_sha256": digest(c),
                        "behavior": c["behavior"], "scope_sha256": check_scope,
                        "method": c["method"], "obligations": c["obligations"],
                        "inputs": inputs, "operational": status, "exit_code": code,
                        "error": error, "logs": logs,
                        **({"engine_result": engine_result, "engine_directory": nonce + ".engine"} if "engine" in c else {})})
        dest = output / (nonce + ".json")
        dest.write_text(json.dumps(receipt, indent=2) + "\n")
        dest.chmod(0o600)
        receipts.append(receipt)
    return receipts


def qualify(registry, plan, root, behaviors, receipts, evidence_root, *, cutover=False, toolchain=None):
    check_plan(plan, registry)
    selected = scope(registry, behaviors)
    freshness = inspect(registry, root, behaviors)
    checks = {c["id"]: c for c in plan["checks"]}
    selected_ids = {b["id"] for b in selected["behaviors"]}
    evidence = {}
    invalid = []
    seen = set()
    for r in receipts:
        try:
            fields(r, {"format", "run", "check", "check_sha256", "behavior", "scope_sha256",
                       "method", "obligations", "inputs", "operational", "exit_code", "error", "logs", "sha256"},
                   {"engine_result", "engine_directory"})
            require(r["format"] == "capcov-behavior-check-v1", "unknown receipt format")
            require(r["sha256"] == digest({k: v for k, v in r.items() if k != "sha256"}), "receipt digest mismatch")
            require(r["check"] in checks and r["check"] not in seen, "unknown or duplicate check receipt")
            seen.add(r["check"])
            c = checks[r["check"]]
            require(c["behavior"] in selected_ids, "receipt outside requested scope")
            require(r["behavior"] == c["behavior"] and r["check_sha256"] == digest(c)
                    and r["method"] == c["method"] and r["obligations"] == c["obligations"], "receipt binding mismatch")
            require(r["scope_sha256"] == digest(scope(registry, [c["behavior"]]))
                    and r["inputs"] == inputs_identity(c, root), "stale check receipt")
            fields(r["logs"], {"stdout", "stderr"})
            for log in r["logs"].values():
                fields(log, {"path", "sha256"})
                require(file_hash(evidence_root, log["path"]) == log["sha256"], "missing or modified execution log")
            require(r["operational"] == "complete" and type(r["exit_code"]) is int
                    and r["exit_code"] == 0, "check failed or did not complete")
            if "engine" in c:
                from .shencheck import assess
                require(r.get("engine_result") is not None, "missing native engine qualification")
                current = assess(path(evidence_root, r["engine_directory"]), toolchain, require_history="observe" in c)
                require(current == r["engine_result"], "stale or changed ShenCheck/Vör evidence")
            else:
                require("engine_result" not in r and "engine_directory" not in r, "engine receipt on ordinary check")
            evidence[c["id"]] = r["sha256"]
        except (ValueError, OSError, TypeError, KeyError) as exc:
            invalid.append(str(exc))
    rows = []
    for b in selected["behaviors"]:
        for o in b["obligations"]:
            matching = [c for c in plan["checks"] if o["id"] in c["obligations"]]
            passed = bool(matching) and all(c["id"] in evidence for c in matching)
            rows.append({"behavior": b["id"], "obligation": o["id"], "category": o["category"],
                         "method": o["method"], "status": "supported" if passed else "unresolved",
                         "evidence": [evidence[c["id"]] for c in matching if c["id"] in evidence]})
    blockers = []
    if freshness["stale"]:
        blockers.append({"kind": "stale", "subjects": freshness["stale"]})
    for g in selected["gaps"]:
        blockers.append({"kind": "gap", "subject": g["id"]})
    for s in selected["stores"]:
        if s["ambiguities"]:
            blockers.append({"kind": "representation", "subject": s["id"]})
    for d in selected["decisions"]:
        if d["status"] != "approved":
            blockers.append({"kind": "decision", "subject": d["id"]})
    if cutover:
        for b in selected["behaviors"]:
            missing = CRITICAL - {o["category"] for o in b["obligations"]}
            if missing:
                blockers.append({"kind": "cutover-policy", "subject": b["id"], "missing": sorted(missing)})
    complete = bool(rows) and not (invalid or blockers) and all(r["status"] == "supported" for r in rows)
    return seal({"format": "capcov-behavior-qualification-v1", "scope_sha256": digest(selected),
                 "level": "cutover-checks" if cutover else "authored-checks", "complete": complete,
                 "obligations": rows, "blockers": blockers, "invalid_evidence": invalid,
                 "engine_evidence": [{"check": r["check"], "directory": r["engine_directory"],
                                      "counterexamples": r["engine_result"]["counterexamples"],
                                      "open_claims": r["engine_result"]["open_claims"]}
                                     for r in receipts if r.get("check") in evidence and r.get("engine_result")],
                 "trust": "Consumer-reviewed checks and observers; no automatic proof of model or adapter soundness."})


def differences(old, new, prefix=()):
    # Presence matters: absent is not JSON null. Such changes require a distinct
    # reviewed scenario/contract rather than a wildcard suppression.
    if type(old) is dict and type(new) is dict:
        result = []
        for key in sorted(old.keys() | new.keys()):
            if key not in old or key not in new:
                result.append({"path": list(prefix + (key,)), "presence_change": True})
            else:
                result.extend(differences(old[key], new[key], prefix + (key,)))
        return result
    if type(old) is list and type(new) is list and len(old) == len(new):
        return [d for i, (a, b) in enumerate(zip(old, new)) for d in differences(a, b, prefix + (i,))]
    if type(old) is type(new) and old == new:
        return []
    return [{"path": list(prefix), "legacy": old, "target": new}]


def compare(registry, behavior, scenario, old, new, qualification):
    selected = scope(registry, [behavior])
    require(qualification["scope_sha256"] == digest(selected), "qualification belongs to different scope")
    # Caller obtains this report by qualify(), not from an unverified disk flag.
    require(qualification["sha256"] == digest({k: v for k, v in qualification.items() if k != "sha256"}), "invalid qualification digest")
    supported = {r["obligation"] for r in qualification["obligations"] if r["status"] == "supported"}
    rows = []
    for diff in differences(old, new):
        matching = []
        for d in selected["decisions"]:
            if (d["behavior"] == behavior and d["status"] == "approved"
                    and qualification["complete"] and set(d["obligations"]) <= supported):
                for allowed in d["differences"]:
                    if allowed["scenario"] == scenario and digest({k: v for k, v in allowed.items() if k != "scenario"}) == digest(diff):
                        matching.append(d["id"])
        rows.append({**diff, "decisions": matching, "status": "approved-change" if matching else "unexplained"})
    return {"format": "capcov-behavior-comparison-v1", "behavior": behavior,
            "scenario": scenario, "differences": rows,
            "compatible": qualification["complete"] and all(r["status"] == "approved-change" for r in rows)}
