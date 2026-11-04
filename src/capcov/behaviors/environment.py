"""Enroll environment evidence in existing Behavior dependencies and obligations."""
from __future__ import annotations

import copy
from pathlib import Path

from capcov import artifacts
from capcov.claims.environment import check, from_capabilities
from capcov.claims.evaluator import evaluate
from capcov.claims.ir import canonical_dict, digest
from .registry import validate, read_json, path, file_hash, fields, require


def load(root, capabilities_file, mapping_file):
    caps = read_json(path(root, capabilities_file))
    mapping = read_json(path(root, mapping_file))
    fields(mapping, {"format", "source_root", "nodes", "searches"})
    require(mapping["format"] == "capcov-environment-behaviors-v1", "unsupported environment mapping")
    require(isinstance(mapping["nodes"], dict) and all(isinstance(k, str) and isinstance(v, str)
            for k, v in mapping["nodes"].items()), "node mapping must name Behavior owners")
    require(isinstance(mapping["searches"], dict), "searches must map surfaces to model/query files")
    source = path(root, mapping["source_root"])
    snapshot = artifacts.source_snapshot_of(source, caps["derived_from"])
    bundle = from_capabilities(caps)
    require(dict(dict(canonical_dict(bundle)["metadata"])["source_manifest"]) == dict(snapshot.entries),
            "claims source manifest differs from the current snapshot")
    check(caps)
    for analysis in caps["environment_recovery"]:
        for name, sha in analysis["input_sha256"].items():
            require(dict(snapshot.entries).get(name) == sha, "recovery input differs from source snapshot")
    report = evaluate(bundle)
    require(report.status.value == "complete", "environment closure did not complete")
    reached = {node for _, _, node in report.relation_rows("env_reaches")}
    require(reached <= mapping["nodes"].keys(), "every reachable node needs an explicit Behavior owner")
    surfaces = {s for _, s, _ in report.relation_rows("env_entry")}
    require(mapping["searches"].keys() <= surfaces, "search mapping names an unknown surface")
    for query in mapping["searches"].values():
        fields(query, {"spec", "input"})
        for value in query.values(): file_hash(root, value)
    return caps, mapping, bundle, report, snapshot


def _id(kind, value):
    return "environment-" + kind + ":" + digest(value)[:24]


def _append(rows, row):
    old = next((x for x in rows if x["id"] == row["id"]), None)
    require(old is None or old == row, "environment import conflicts with existing identity; regenerate from reviewed baseline")
    if old is None: rows.append(row)


def import_environment(registry, root, capabilities_file, mapping_file):
    tables, _, _ = validate(registry)
    caps, mapping, bundle, report, snapshot = load(root, capabilities_file, mapping_file)
    require(set(mapping["nodes"].values()) <= tables["behaviors"].keys(), "unknown Behavior owner")
    result = copy.deepcopy(registry)
    behaviors = {b["id"]: b for b in result["behaviors"]}
    owners = mapping["nodes"]
    reached = {node for _, _, node in report.relation_rows("env_reaches")}
    selected = {owners[n] for n in reached}
    source = path(root, mapping["source_root"])
    files = {capabilities_file, mapping_file}
    files.update((source / name).relative_to(Path(root).resolve()).as_posix() for name, _ in snapshot.entries)
    files.update(value for query in mapping["searches"].values() for value in query.values())
    artifact_ids = []
    for name in sorted(files):
        existing = next((a for a in result["artifacts"] if a["path"] == name), None)
        sha = file_hash(root, name)
        if existing:
            require(existing["sha256"] == sha, "existing artifact is stale; do not silently rebaseline")
            artifact_ids.append(existing["id"])
        else:
            ident = _id("input", name)
            _append(result["artifacts"], {"id": ident, "path": name, "sha256": sha})
            artifact_ids.append(ident)
    snapshot_binding = {"root": mapping["source_root"], "derived_from": caps["derived_from"]}
    enrolled = next(a for a in result["artifacts"] if a["path"] == capabilities_file)
    require(enrolled.get("source_snapshot", snapshot_binding) == snapshot_binding,
            "existing source snapshot differs; do not silently rebaseline")
    enrolled["source_snapshot"] = snapshot_binding
    for owner in sorted(selected):
        b = behaviors[owner]
        b["artifacts"] = sorted(set(b["artifacts"]) | set(artifact_ids))
        for category, method, description in (
            ("projection", "static", "Check recovery graph projection with the existing claims evaluators."),
            ("extraction", "review", "Establish extraction completeness and runtime configuration correspondence; hashes are not proofs."),
        ):
            _append(b["obligations"], {"id": _id(category, owner), "category": "environment-" + category,
                                      "method": method, "description": description})
        for analysis in caps["environment_recovery"]:
            for gap in analysis["unresolved"]:
                _append(result["gaps"], {"id": _id("gap", [owner, gap["id"], gap["reason"]]),
                    "behavior": owner, "question": gap["reason"], "owner": "consumer-review",
                    "closure": "Supply reviewed extraction/configuration evidence and update this gap explicitly.",
                    "artifacts": artifact_ids})
    graph = dict(canonical_dict(bundle)["metadata"])["graph"]
    for caller, callee in graph["edges"]:
        if caller in reached:
            a, b = owners[caller], owners[callee]
            if a != b:
                behaviors[a]["depends_on"] = sorted(set(behaviors[a]["depends_on"]) | {b})
    entries = {s: owners[n] for _, s, n in report.relation_rows("env_entry")}
    effects = {(surface, entity, operation) for _, surface, entity, operation
               in report.relation_rows("env_capability_op")}
    classified = {(surface, entity) for surface, entity, _ in effects}
    effects.update((surface, entity, "touch (operation unknown)") for _, surface, entity
                   in report.relation_rows("env_capability") if (surface, entity) not in classified)
    for surface, entity, operation in sorted(effects):
        owner = entries[surface]
        row = [owner, surface, entity, operation]
        _append(result["claims"], {"id": _id("claim", row), "behavior": owner,
            "kind": "static", "statement": f"Graph-relative possibility: {surface} may {operation} {entity}; not execution evidence.",
            "artifacts": artifact_ids, "depends_on": []})
        _append(behaviors[owner]["obligations"], {"id": _id("execution", row),
            "category": "environment-effect", "method": "execution",
            "description": f"Exercise or resolve the candidate {surface} -> {operation} {entity}; preserve conditions and failure outcomes."})
    for surface, owner in sorted(entries.items()):
        if surface in mapping["searches"]:
            _append(behaviors[owner]["obligations"], {"id": _id("search", [owner, surface]),
                "category": "environment-scenario", "method": "model-check",
                "description": f"Run the mapped Shen search for {surface}; a witness is model-level evidence only."})
        else:
            _append(result["gaps"], {"id": _id("search-gap", [owner, surface]), "behavior": owner,
                "question": f"Which model, input domain and goal exercise {surface}?",
                "owner": "consumer-model", "closure": "Map the surface to existing Shen search inputs.",
                "artifacts": artifact_ids})
    validate(result)  # Refuse cycles: the consumer must consolidate cutover units.
    return result


def search_environment(root, capabilities_file, mapping_file, surface, *, timeout=60):
    from capcov.operations.search import search
    caps, mapping, bundle, _, _ = load(root, capabilities_file, mapping_file)
    require(surface in mapping["searches"], "surface has no reviewed model/search mapping")
    query = mapping["searches"][surface]
    payload = read_json(path(root, query["input"]))
    fields(payload, {"initial", "calls", "goal"}, {"depth", "budget", "fuel"})
    # This is the existing Shen Prolog search, with its native type/scope checks.
    result = search(path(root, query["spec"]).read_text(), **payload, timeout=timeout)
    return {"format": "capcov-environment-search-v1", "surface": surface,
            "bundle_sha256": digest(bundle), "search": result,
            "scope": "model witness; does not discharge execution or extraction obligations"}


def extend_plan(plan, registry, root, capabilities_file, mapping_file, *, python="python", engine="both"):
    """Generate only projection/search checks; never auto-approve review/execution."""
    from .qualification import check_plan
    _, mapping, _, report, _ = load(root, capabilities_file, mapping_file)
    result = copy.deepcopy(plan)
    tables, _, obligations = validate(registry)
    for owner in sorted({mapping["nodes"][n] for _, _, n in report.relation_rows("env_reaches")}):
        obligation = _id("projection", owner)
        require(obligation in obligations, "import environment obligations before extending checks")
        inputs = sorted({tables["artifacts"][a]["path"] for a in tables["behaviors"][owner]["artifacts"]})
        _append(result["checks"], {"id": _id("check", owner), "behavior": owner,
            "obligations": [obligation], "method": "static", "timeout": 120, "inputs": inputs,
            "argv": [python, "-m", "capcov", "behavior", "environment-check", "--input", capabilities_file,
                     "--mapping", mapping_file, "--engine", engine]})
        for _, surface, node in report.relation_rows("env_entry"):
            if mapping["nodes"][node] != owner or surface not in mapping["searches"]: continue
            _append(result["checks"], {"id": _id("search-check", [owner, surface]), "behavior": owner,
                "obligations": [_id("search", [owner, surface])], "method": "model-check", "timeout": 120,
                "inputs": inputs, "argv": [python, "-m", "capcov", "behavior", "environment-search",
                "--input", capabilities_file, "--mapping", mapping_file, "--surface", surface]})
    check_plan(result, registry)
    return result
