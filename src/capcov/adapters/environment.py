"""Finite environment-sensitive call recovery over source-bound adapter facts.

Inspired by Afonin, Nock Compilation (Subject Knowledge Analysis II), sections
2.2--2.4. This is a may-call analysis, not an interpreter or completeness proof.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import deque
from pathlib import Path

SCHEMA = "capcov.environment.v1"
MAX_RECORDS = 10000
MAX_PAIRS = 100000
MAX_SUPPORT = 1000000


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _path(root: Path, name: object) -> Path:
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError("environment paths must be relative to the source root")
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"environment input is outside source root or missing: {name}")
    if path.relative_to(root.resolve()).as_posix() != name:
        raise ValueError(f"environment input must use its canonical path: {name}")
    return path


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _json(path: Path, digests: dict[str, str], name: str) -> dict:
    def reject_constant(value):
        raise ValueError(f"invalid JSON constant: {value}")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    data = path.read_bytes()
    digests[name] = hashlib.sha256(data).hexdigest()
    value = json.loads(data, object_pairs_hook=unique, parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path.name}")
    return value


def recover(raw: dict, source_root: Path, facts_path: str, *, document: dict | None = None) -> dict:
    """Augment the existing discovery graph; never erase prior blind spots.

    A fact export declares nodes, bindings, calls and direct effects. Every
    record has a stable id and an exact source anchor. Environment values come
    from a separate JSON object; missing keys are unknown, not false. All facts
    remain producer assertions, with an explicit extraction-boundary obligation.
    """
    root = source_root.resolve()
    input_digests: dict[str, str] = {}
    if document is None:
        document = _json(_path(root, facts_path), input_digests, facts_path)
    else:
        document = copy.deepcopy(document)
    if set(document) != {"schema", "producer", "environment", "nodes", "bindings",
                         "calls", "effects"} or document["schema"] != SCHEMA:
        raise ValueError("invalid environment fact document or schema")
    producer = _text(document["producer"], "producer")
    environment_path = _text(document["environment"], "environment")
    environment = _json(_path(root, environment_path), input_digests, environment_path)
    # Scalar configuration only. No ambient process environment or target code
    # is executed, and unknown is represented by an absent key (null is known).
    if any(type(v) not in (str, int, bool, type(None)) for v in environment.values()):
        raise ValueError("environment values must be strings, integers, booleans or null")
    groups = ("nodes", "bindings", "calls", "effects")
    if any(not isinstance(document[g], list) for g in groups):
        raise ValueError("environment fact groups must be lists")
    if sum(len(document[g]) for g in groups) > MAX_RECORDS:
        raise ValueError("environment fact record budget exceeded")
    records = [r for g in groups for r in document[g]]
    ids: set[str] = set()
    source_digests: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("environment fact must be an object")
        ident = _text(record.get("id"), "fact id")
        if ident in ids:
            raise ValueError(f"duplicate environment fact id: {ident}")
        ids.add(ident)
        anchor = record.get("source")
        if not isinstance(anchor, dict) or set(anchor) != {"file", "line", "sha256"}:
            raise ValueError(f"missing exact source anchor: {ident}")
        file = _text(anchor["file"], "source file")
        data = _path(root, file).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != anchor["sha256"]:
            raise ValueError(f"stale environment source: {file} ({ident})")
        if type(anchor["line"]) is not int or not 1 <= anchor["line"] <= len(data.splitlines()):
            raise ValueError(f"invalid source line: {ident}")
        source_digests[file] = digest
        input_digests[file] = digest

    result = copy.deepcopy(raw)
    calls = result["_calls"]
    direct = result["_direct"]
    ops = result["_ops"]
    nodes = set(calls) | set(direct)
    for record in document["nodes"]:
        if set(record) != {"id", "node", "source"}:
            raise ValueError("invalid environment node fields")
        node = _text(record["node"], "node")
        nodes.add(node)
        calls.setdefault(node, set())
        direct.setdefault(node, set())

    unresolved = result.setdefault("unresolved", [])
    diagnostics: list[dict] = []

    def gap(record: dict, reason: str) -> None:
        diagnostics.append({"kind": "environment-unresolved",
                            "id": f"environment:{facts_path}:{record['id']}",
                            "reason": reason, "source": record["source"]})

    def enabled(record: dict) -> bool:
        conditions = record.get("when", {})
        if not isinstance(conditions, dict) or any(
            type(v) not in (str, int, bool, type(None)) for v in conditions.values()
        ):
            raise ValueError(f"invalid conditions: {record['id']}")
        # A definitely false conjunct excludes this candidate. Unknown conjuncts
        # retain it and are reported even when another conjunct is false.
        active = True
        for key, expected in sorted(conditions.items()):
            if key not in environment:
                gap(record, f"unknown environment key: {key}")
            elif type(environment[key]) is not type(expected) or environment[key] != expected:
                active = False
        return active

    # Only finite declared slots and target nodes enter this abstract domain.
    # Each (slot,target) pair is inserted once. Alias cycles terminate naturally.
    values: dict[str, set[str]] = {}
    aliases: dict[str, set[str]] = {}
    witnesses: dict[tuple[str, str], set[str]] = {}
    queue: deque[tuple[str, str]] = deque()
    pairs = 0
    support = 0

    def insert(slot: str, target: str, proof: set[str]) -> None:
        nonlocal pairs, support
        key = (slot, target)
        previous = witnesses.setdefault(key, set())
        changed = not proof <= previous
        support += len(proof - previous)
        if support > MAX_SUPPORT:
            raise ValueError("environment provenance support budget exceeded")
        previous.update(proof)
        if target not in values.setdefault(slot, set()):
            pairs += 1
            if pairs > MAX_PAIRS:
                raise ValueError("environment slot/target budget exceeded")
            values[slot].add(target)
            changed = True
        if changed:
            queue.append(key)

    active_bindings = []
    for record in document["bindings"]:
        if set(record) - {"id", "source", "slot", "target", "from_slot", "when"}:
            raise ValueError("invalid environment binding fields")
        slot = _text(record.get("slot"), "slot")
        if ("target" in record) == ("from_slot" in record):
            raise ValueError("binding requires exactly one of target/from_slot")
        name = _text(record.get("target", record.get("from_slot")), "binding value")
        values.setdefault(slot, set())
        if not enabled(record):
            continue
        active_bindings.append(record)
        if "target" in record:
            if name not in nodes:
                gap(record, f"target has no declared body: {name}")
            else:
                insert(slot, name, {record["id"]})
        else:
            aliases.setdefault(name, set()).add(slot)
    alias_proofs: dict[tuple[str, str], set[str]] = {}
    for record in active_bindings:
        if "from_slot" in record:
            alias_proofs.setdefault((record["from_slot"], record["slot"]), set()).add(record["id"])
    while queue:
        slot, target = queue.popleft()
        for destination in sorted(aliases.get(slot, ())):
            insert(destination, target, witnesses[(slot, target)] |
                   alias_proofs[(slot, destination)])

    edges = []
    for record in document["calls"]:
        if set(record) - {"id", "source", "caller", "slot", "target", "when", "kind"}:
            raise ValueError("invalid environment call fields")
        caller = _text(record.get("caller"), "caller")
        if ("target" in record) == ("slot" in record):
            raise ValueError("call requires exactly one of target/slot")
        name = _text(record.get("target", record.get("slot")), "call value")
        kind = record.get("kind", "call")
        if kind not in {"call", "callback", "worker"}:
            raise ValueError("call kind must be call, callback or worker")
        if not enabled(record):
            continue
        if caller not in nodes:
            gap(record, f"caller has no declared body: {caller}")
            continue
        targets = {name} if "target" in record else values.get(name, set())
        if not targets:
            gap(record, f"no known target for slot: {name}")
        for target in sorted(targets):
            if target not in nodes:
                gap(record, f"target has no declared body: {target}")
                continue
            proof = {record["id"]}
            if "slot" in record:
                proof |= witnesses[(name, target)]
            calls.setdefault(caller, set()).add(target)
            edges.append({"caller": caller, "target": target, "kind": kind,
                          "fact_ids": sorted(proof), "source": record["source"],
                          "when": record.get("when", {})})

    entities = {entity["name"] for entity in result["entities"]}
    effects = []
    for record in document["effects"]:
        if set(record) - {"id", "source", "node", "entity", "operation", "when"}:
            raise ValueError("invalid environment effect fields")
        node = _text(record.get("node"), "effect node")
        entity = _text(record.get("entity"), "effect entity")
        operation = _text(record.get("operation"), "effect operation")
        if operation not in {"read", "create", "update", "delete"}:
            raise ValueError("environment effect operation must be CRUD")
        if not enabled(record):
            continue
        if node not in nodes or entity not in entities:
            gap(record, "effect node or entity absent from discovery inventory")
            continue
        direct.setdefault(node, set()).add(entity)
        ops.setdefault(node, {}).setdefault(entity, set()).add(operation)
        effects.append(record)

    # Hashes establish identity, not truth of extracted facts. Do not manufacture
    # a completeness certificate or suppress the adapter's original blind spots.
    diagnostics.append({"kind": "environment-extraction-boundary",
                        "id": f"environment:{facts_path}:extraction",
                        "reason": "source-bound facts are producer assertions; extraction "
                                  "completeness and runtime environment correspondence remain open"})
    unresolved.extend(diagnostics)
    analysis = {
        "schema": SCHEMA, "producer": producer, "facts": facts_path,
        "facts_sha256": _digest(document), "environment_file": environment_path,
        "environment_sha256": _digest(environment), "sources": source_digests,
        "input_sha256": input_digests,
        "semantics": "may-reach; no path feasibility, ordering or delivery guarantee",
        "bindings": {key: sorted(value) for key, value in sorted(values.items())},
        "edges": sorted(edges, key=lambda e: (e["caller"], e["target"], e["fact_ids"])),
        "effects": effects, "unresolved": diagnostics,
        # Retain all premises, including conditional binding facts, for audit.
        "premises": document,
    }
    analysis["analysis_sha256"] = _digest(analysis)
    result.setdefault("environment_recovery", []).append(analysis)
    return result
