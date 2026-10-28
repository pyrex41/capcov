"""Reversa-style reviewed extraction import and queries over the shared index."""

import copy
from pathlib import Path
from importlib import resources

from capcov.operations.system import digest
from .registry import validate, fields, require, names, file_hash, inspect


def import_recovery(registry, payload, root):
    """Import explicit source mappings; never guess semantics from prose labels.

    The recovery artifact is consumer-owned. CONFIRMED and INFERRED both remain
    static claims; their confidence label is retained in the statement.
    """
    fields(payload, {"format", "claims", "gaps"})
    require(payload["format"] == "capcov-recovery-v1", "unsupported recovery exchange")
    result = copy.deepcopy(registry)
    tables, _, _ = validate(registry)
    require(isinstance(payload["claims"], list), "claims must be a list")
    for c in payload["claims"]:
        fields(c, {"id", "behavior", "statement", "confidence", "artifacts", "depends_on"})
        require(c["confidence"] in {"confirmed", "inferred"}, "recovery confidence is not runtime observation")
        require(names(c["artifacts"]) and set(c["artifacts"]) <= tables["artifacts"].keys(), "recovery needs source artifacts")
        for name in c["artifacts"]:
            a = tables["artifacts"][name]
            require(file_hash(root, a["path"]) == a["sha256"], "stale recovery source")
        result["claims"].append({k: v for k, v in c.items() if k != "confidence"} | {
            "kind": "static", "statement": c["confidence"] + ": " + c["statement"]})
    require(isinstance(payload["gaps"], list), "gaps must be a list")
    result["gaps"].extend(payload["gaps"])
    validate(result)
    return result


def tasks(registry, report):
    """Plan work from open obligations; planning does not execute agent commands."""
    validate(registry)
    roles = {"static": "Archaeologist", "execution": "Implementer",
             "proof": "Verifier", "model-check": "Protocol reviewer", "review": "Curator"}
    priorities = {b["id"]: b["priority"] for b in registry["behaviors"]}
    pending = [{"behavior": o["behavior"], "obligation": o["obligation"],
                "role": roles[o["method"]], "priority": priorities[o["behavior"]]}
               for o in report["obligations"] if o["status"] != "supported"]
    return {"tasks": sorted(pending, key=lambda t: (-t["priority"], t["behavior"], t["obligation"])),
            "blockers": report["blockers"], "invalid_evidence": report["invalid_evidence"]}


def export_graph(registry, root, behaviors, output):
    """Use capcov's existing Souffle invalidation rules, with hashed IDs."""
    tables, edges, _ = validate(registry)
    report = inspect(registry, root, behaviors)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    require(not list(output.iterdir()), "graph output must be empty")
    ids = {digest(n): n for n in edges}
    (output / "ids.json").write_text(__import__("json").dumps(ids, indent=2) + "\n")
    (output / "evidence.dl").write_bytes(resources.files("capcov.operations").joinpath("evidence.dl").read_bytes())
    facts = {
        "cited": [(digest(n), digest(n)) for n in tables["artifacts"]],
        "depends": [(digest(n), digest(p)) for n, deps in edges.items() for p in deps],
        "changed": [(digest(n),) for n in report["changed_artifacts"]],
    }
    for name, rows in facts.items():
        (output / (name + ".facts")).write_text("".join("\t".join(r) + "\n" for r in sorted(rows)))
    return report
