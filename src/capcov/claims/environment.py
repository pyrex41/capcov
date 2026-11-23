"""Environment discovery exported into the existing, validated claims IR.

All conclusions are graph-relative possibilities. No completeness relations or
negative facts are manufactured from an absent edge or a successful hash check.
"""
from __future__ import annotations

from .ir import (Atom, Bundle, Column, Constant, Context, Evidence,
                 RelationDecl, Rule, Variable, canonical_dict, digest)
from .validation import assert_valid


def export(raw: dict, *, manifest=()) -> Bundle:
    analyses = raw.get("environment_recovery", [])
    if not analyses:
        raise ValueError("environment recovery is required")
    graph = {
        "edges": sorted([a, b] for a, bs in raw["_calls"].items() for b in bs),
        "effects": sorted([n, e, op] for n, es in raw["_ops"].items()
                          for e, ops in es.items() for op in ops),
        "touches": sorted([n, e] for n, es in raw["_direct"].items() for e in es),
        "entries": sorted([s["id"], s["handler"]] for s in raw["surfaces"]),
    }
    manifest = sorted([name, sha] for name, sha in manifest)
    context = digest({"analyses": analyses, "graph": graph, "manifest": manifest})
    def decl(name, cols, derived=False):
        return RelationDecl(name, (Column("index", "digest", context=True),
                            *(Column(c, "symbol") for c in cols)),
                            modality="derived" if derived else "observation",
                            binding="static", primitive=not derived,
                            context_indices=("index",))
    relations = (
        decl("env_edge", ("caller", "callee")),
        decl("env_effect", ("node", "entity", "operation")),
        decl("env_touch", ("node", "entity")),
        decl("env_entry", ("surface", "node")),
        decl("env_unknown", ("obligation", "reason")),
        decl("env_reaches", ("surface", "node"), True),
        decl("env_capability", ("surface", "entity"), True),
        decl("env_capability_op", ("surface", "entity", "operation"), True),
    )
    a, s, n, m, e, o = [Variable(x) for x in ("A", "S", "N", "M", "E", "O")]
    def atom(name, *terms): return Atom(name, tuple(terms))
    rules = (
        Rule(atom("env_reaches", a, s, n), (atom("env_entry", a, s, n),), "environment.entry"),
        Rule(atom("env_reaches", a, s, m),
             (atom("env_reaches", a, s, n), atom("env_edge", a, n, m)), "environment.reach"),
        Rule(atom("env_capability", a, s, e),
             (atom("env_reaches", a, s, n), atom("env_touch", a, n, e)), "environment.touch"),
        Rule(atom("env_capability_op", a, s, e, o),
             (atom("env_reaches", a, s, n), atom("env_effect", a, n, e, o)), "environment.effect"),
    )
    rows = {"env_edge": graph["edges"], "env_effect": graph["effects"],
            "env_touch": graph["touches"], "env_entry": graph["entries"],
            "env_unknown": [[x["id"], x["reason"]] for analysis in analyses for x in analysis["unresolved"]]}
    dependencies = tuple(sorted({"external:environment:" + analysis["analysis_sha256"]
                                 for analysis in analyses} |
                                {"external:source:" + sha for analysis in analyses
                                 for sha in analysis["input_sha256"].values()} |
                                {"external:source:" + sha for _, sha in manifest}))
    facts, evidence = [], []
    for name, values in rows.items():
        for row in sorted(set(tuple(v) for v in values)):
            fact = atom(name, Constant(context), *(Constant(v) for v in row))
            facts.append(fact)
            evidence.append(Evidence("environment:" + digest(canonical_dict(fact)), fact,
                Context.from_mapping({"index": context}), "capcov.environment-export.v1",
                dependencies))
    bundle = Bundle(relations, tuple(facts), rules, evidence=tuple(evidence), metadata=(
        ("environment_analysis", context), ("graph", graph), ("recovery", analyses),
        ("source_manifest", manifest),
        ("semantics", "graph-relative may-reach; no extraction completeness or runtime proof")))
    assert_valid(bundle)
    return bundle


def from_capabilities(capabilities: dict) -> Bundle:
    from .ir import bundle_from_json
    bundle = bundle_from_json(capabilities["environment_claims"])
    # Rebuild the pack from its retained primitive graph and premises. Do not
    # accept a caller-modified rule pack just because its JSON is well formed.
    metadata = dict(canonical_dict(bundle)["metadata"])
    graph = metadata["graph"]
    raw = {"_calls": {}, "_direct": {}, "_ops": {},
           "surfaces": [{"id": s, "handler": n} for s, n in graph["entries"]],
           "environment_recovery": capabilities["environment_recovery"]}
    for caller, callee in graph["edges"]: raw["_calls"].setdefault(caller, set()).add(callee)
    for node, entity in graph["touches"]: raw["_direct"].setdefault(node, set()).add(entity)
    for node, entity, op in graph["effects"]:
        raw["_ops"].setdefault(node, {}).setdefault(entity, set()).add(op)
    expected = export(raw, manifest=metadata["source_manifest"])
    if expected != bundle:
        raise ValueError("environment claims pack or evidence differs from canonical export")
    return bundle


def check(capabilities: dict, *, engine="python") -> dict:
    from .differential import run_python, run_souffle, reports_match
    bundle = from_capabilities(capabilities)
    if engine not in {"python", "souffle", "both"}:
        raise ValueError("unknown environment evaluator")
    reports = [run_python(bundle)] if engine == "python" else [run_souffle(bundle)]
    if engine == "both": reports.insert(0, run_python(bundle))
    for report in reports:
        if report.operational_failure:
            raise ValueError(f"{report.backend}: {report.operational_failure}: {report.message}")
    if len(reports) == 2 and not reports_match(*reports):
        raise ValueError("environment Python/Souffle disagreement")
    rows = dict(reports[0].relations)
    actual = {(s, e) for _, s, e in rows["env_capability"]}
    wanted = {(c["surface"], c["entity"]) for c in capabilities["capabilities"]}
    actual_ops = {(s, e, o) for _, s, e, o in rows["env_capability_op"]}
    wanted_ops = {(c["surface"], c["entity"], o) for c in capabilities["capabilities"] for o in c["operations"]}
    if (actual, actual_ops) != (wanted, wanted_ops):
        raise ValueError("environment claims disagree with capability projection")
    return {"format": "capcov-environment-check-v1", "bundle_sha256": digest(bundle),
            "engines": [r.backend for r in reports], "capabilities": len(actual),
            "operations": len(actual_ops), "unresolved": list(rows["env_unknown"]),
            "scope": "projection agreement only; extraction and execution obligations remain open"}
