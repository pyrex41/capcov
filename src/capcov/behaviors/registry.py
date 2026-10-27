"""Versioned links between existing artifacts, access contracts and obligations.

This is a consumer-authored index, not a second claim evaluator. Facts retain
their evidence kind; no source inference is promoted to runtime observation.
"""

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

from capcov.operations.system import digest
from . import BehaviorError

FORMAT = "capcov-behaviors-v1"
KINDS = {"static", "observed", "derived", "assumed", "decided", "validated"}
METHODS = {"static", "execution", "proof", "model-check", "review"}
CRITICAL = {"authorization", "tenant-isolation", "representation", "durable-effects",
            "coexistence", "recovery", "compatibility", "target-contract"}
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}$")


def require(ok, message):
    if not ok:
        raise BehaviorError(message)


def fields(value, required, optional=()):
    require(isinstance(value, dict) and set(required) <= value.keys()
            and not value.keys() - set(required) - set(optional), "invalid fields")


def names(values):
    require(isinstance(values, list) and all(isinstance(v, str) and ID.fullmatch(v)
            for v in values) and len(values) == len(set(values)), "invalid or duplicate IDs")
    return set(values)


def text(value):
    require(isinstance(value, str) and 0 < len(value) <= 8192, "expected nonempty text")


def path(root, relative):
    require(isinstance(relative, str) and relative and "\\" not in relative,
            "expected relative POSIX path")
    p = PurePosixPath(relative)
    require(not p.is_absolute() and ".." not in p.parts and str(p) == relative,
            "noncanonical or escaping path")
    base = Path(root).resolve()
    result = (base / relative).resolve()
    require(result.is_relative_to(base), "source symlink escapes root")
    return result


def file_hash(root, relative):
    p = path(root, relative)
    require(p.is_file() and p.stat().st_size <= 16 * 1024 * 1024,
            "missing or oversized artifact: " + relative)
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read_json(filename):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result
    p = Path(filename)
    require(p.stat().st_size <= 16 * 1024 * 1024, "JSON exceeds 16 MiB")
    return json.loads(p.read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(BehaviorError("nonfinite JSON")))


def index(rows, required, optional=()):
    require(isinstance(rows, list) and len(rows) <= 8192, "invalid registry collection")
    names([r.get("id") for r in rows if isinstance(r, dict)])
    result = {}
    for row in rows:
        fields(row, {"id", *required}, optional)
        require(isinstance(row["id"], str) and ID.fullmatch(row["id"]), "invalid ID")
        require(row["id"] not in result, "duplicate ID")
        result[row["id"]] = row
    return result


def validate(registry):
    fields(registry, {"format", "baseline", "artifacts", "stores", "access_paths",
                      "behaviors", "claims", "decisions", "gaps"})
    require(registry["format"] == FORMAT, "unsupported behavior registry")
    text(registry["baseline"])
    tables = {
        "artifacts": index(registry["artifacts"], {"path", "sha256"}),
        "stores": index(registry["stores"], {"physical", "representation", "access", "domain", "ambiguities"}),
        "access_paths": index(registry["access_paths"], {"store", "mode", "writer", "hooks", "scopes", "bypasses", "artifacts"}),
        "behaviors": index(registry["behaviors"], {"purpose", "priority", "entries", "depends_on", "access_paths", "artifacts", "legacy", "target", "obligations"}),
        "claims": index(registry["claims"], {"behavior", "statement", "kind", "artifacts", "depends_on"}),
        "decisions": index(registry["decisions"], {"behavior", "disposition", "rationale", "status", "owner", "artifacts", "obligations", "differences"}),
        "gaps": index(registry["gaps"], {"behavior", "question", "owner", "closure", "artifacts"}),
    }
    all_ids = [n for table in tables.values() for n in table]
    require(len(all_ids) == len(set(all_ids)), "IDs must be unique across registry kinds")
    require(tables["behaviors"], "registry needs at least one Behavior")
    edges = {n: set() for n in all_ids}

    def refs(owner, values, kind):
        selected = names(values)
        require(selected <= tables[kind].keys(), owner + ": unresolved " + kind)
        edges[owner].update(selected)

    for a in tables["artifacts"].values():
        path(".", a["path"])
        require(isinstance(a["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", a["sha256"]), "invalid artifact digest")
    for s in tables["stores"].values():
        for layer in ("physical", "representation", "access", "domain"):
            require(s[layer], "store layer must name at least one artifact")
            refs(s["id"], s[layer], "artifacts")
        require(isinstance(s["ambiguities"], list), "ambiguities must be a list")
        for ambiguity in s["ambiguities"]:
            text(ambiguity)
    for a in tables["access_paths"].values():
        refs(a["id"], [a["store"]], "stores")
        refs(a["id"], a["artifacts"], "artifacts")
        require(a["mode"] in {"read", "write", "read-write"}, "invalid access mode")
        text(a["writer"])
        for field in ("hooks", "scopes", "bypasses"):
            require(isinstance(a[field], list), "access contract must list " + field)
            for item in a[field]:
                text(item)
    obligations = {}
    for b in tables["behaviors"].values():
        text(b["purpose"])
        require(type(b["priority"]) is int and 1 <= b["priority"] <= 100, "priority must be 1..100")
        require(isinstance(b["entries"], list) and b["entries"], "Behavior needs entry points")
        for entry in b["entries"]:
            text(entry)
        for k in ("access_paths", "artifacts"):
            refs(b["id"], b[k], k)
        refs(b["id"], b["depends_on"], "behaviors")
        refs(b["id"], [b["legacy"]], "artifacts")
        refs(b["id"], [b["target"]], "artifacts")
        local = index(b["obligations"], {"category", "method", "description"})
        require(local, "Behavior needs obligations")
        require(not local.keys() & obligations.keys(), "duplicate obligation ID")
        for o in local.values():
            text(o["description"])
            text(o["category"])
            require(o["method"] in METHODS, "invalid evidence method")
        obligations.update({n: (b["id"], o) for n, o in local.items()})
    for c in tables["claims"].values():
        refs(c["id"], [c["behavior"]], "behaviors")
        refs(c["id"], c["artifacts"], "artifacts")
        refs(c["id"], c["depends_on"], "claims")
        text(c["statement"])
        require(c["kind"] in KINDS, "invalid claim evidence kind")
    for d in tables["decisions"].values():
        refs(d["id"], [d["behavior"]], "behaviors")
        refs(d["id"], d["artifacts"], "artifacts")
        require(d["status"] in {"proposed", "approved", "rejected"}, "invalid decision status")
        require(d["disposition"] in {"preserve", "select", "correct", "representation", "remove"}, "invalid disposition")
        for f in ("rationale", "owner"):
            text(d[f])
        required = names(d["obligations"])
        require(required and required <= obligations.keys(), "decision needs known replacement obligations")
        require(all(obligations[o][0] == d["behavior"] for o in required), "decision obligation belongs to another Behavior")
        require(isinstance(d["differences"], list), "invalid differences")
        for diff in d["differences"]:
            fields(diff, {"scenario", "path", "legacy", "target"})
            text(diff["scenario"])
            require(isinstance(diff["path"], list) and all(isinstance(x, str) or type(x) is int for x in diff["path"]), "invalid difference path")
            require(digest(diff["legacy"]) != digest(diff["target"]), "decision difference must change a value")
    for g in tables["gaps"].values():
        refs(g["id"], [g["behavior"]], "behaviors")
        refs(g["id"], g["artifacts"], "artifacts")
        for f in ("question", "owner", "closure"):
            text(g[f])
    # Dependencies are a DAG; cycles must be modeled as a single cutover unit,
    # not silently treated as an already-qualified recursive premise.
    visiting, visited = set(), set()
    def visit(n):
        require(n not in visiting, "cyclic dependency: " + n)
        if n in visited:
            return
        visiting.add(n)
        for p in edges[n]:
            visit(p)
        visiting.remove(n)
        visited.add(n)
    for n in edges:
        visit(n)
    return tables, edges, obligations


def closure(edges, roots):
    selected, pending = set(), list(roots)
    while pending:
        n = pending.pop()
        require(n in edges, "unknown dependency: " + str(n))
        if n not in selected:
            selected.add(n)
            pending.extend(edges[n])
    return selected


def scope(registry, behaviors):
    tables, edges, _ = validate(registry)
    require(names(behaviors) <= tables["behaviors"].keys() and behaviors, "unknown or empty Behavior scope")
    selected = closure(edges, behaviors)
    # Attach reverse-owned evidence and all writers of shared stores. A changed
    # legacy bypass must invalidate coexistence even when no target route uses it.
    while True:
        selected_behaviors = selected & tables["behaviors"].keys()
        attached = [x["id"] for k in ("claims", "gaps", "decisions") for x in tables[k].values()
                    if x["behavior"] in selected_behaviors]
        attached += [a["id"] for a in tables["access_paths"].values()
                     if a["store"] in selected and a["mode"] != "read"]
        expanded = selected | closure(edges, attached)
        if expanded == selected:
            break
        selected = expanded
    rows = {k: [v for n, v in sorted(table.items()) if n in selected]
            for k, table in tables.items()}
    return {"baseline": registry["baseline"], **rows}


def inspect(registry, root, behaviors):
    tables, edges, _ = validate(registry)
    selected = scope(registry, behaviors)
    changed = []
    for a in tables["artifacts"].values():
        try:
            current = file_hash(root, a["path"])
        except (OSError, BehaviorError):
            current = None
        if current != a["sha256"]:
            changed.append(a["id"])
    stale = set(changed)
    while True:
        more = stale | {n for n, deps in edges.items() if deps & stale}
        if more == stale:
            break
        stale = more
    selected_ids = {x["id"] for k in tables for x in selected[k]}
    return {"format": "capcov-behavior-inspection-v1", "scope_sha256": digest(selected),
            "behaviors": [b["id"] for b in selected["behaviors"]],
            "changed_artifacts": sorted(changed), "stale": sorted(stale & selected_ids),
            "shared_writers": {s["id"]: sorted({a["writer"] for a in tables["access_paths"].values()
                if a["store"] == s["id"] and a["mode"] != "read"}) for s in selected["stores"]},
            "gaps": selected["gaps"],
            "ambiguities": {s["id"]: s["ambiguities"] for s in selected["stores"] if s["ambiguities"]}}
