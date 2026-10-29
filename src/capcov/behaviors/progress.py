"""Persistent, reported product breadth/depth accounting (not qualification)."""

from copy import deepcopy
from itertools import zip_longest
import re


STAGES = ("unknown", "missing", "partial", "implemented")
DISPOSITIONS = ("retain", "replace", "exclude", "unresolved")
DEPTH = ("unknown", "pass", "fail")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _pin(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{40}", value) is not None


def _index(items, name):
    _require(isinstance(items, list), f"{name} must be an array")
    result = {}
    for item in items:
        _require(isinstance(item, dict) and _text(item.get("id")), f"{name} needs nonempty id")
        key = item["id"]
        _require(key not in result, f"duplicate {name} id: {key}")
        result[key] = deepcopy(item)
    return result


def _normalize(plan):
    _require(isinstance(plan, dict), "plan must be an object")
    _require(plan.get("format") == "capcov-progress-plan-v1", "expected capcov-progress-plan-v1 format")
    _require(_text(plan.get("unit_namespace")), "unit_namespace must explicitly name one capability inventory")
    candidates = _index(plan.get("candidates"), "candidates")
    _require(candidates, "at least one candidate is required")
    for candidate in candidates.values():
        _require(_pin(candidate.get("source_pin")), f"candidate {candidate['id']} needs full 40-character SHA")
    units = _index(plan.get("units"), "units")
    dimensions = plan.get("depth_dimensions")
    _require(isinstance(dimensions, list) and dimensions and all(_text(d) for d in dimensions),
             "depth_dimensions must be a nonempty array of names")
    _require(len(set(dimensions)) == len(dimensions), "duplicate depth_dimensions")
    for unit in units.values():
        uid = unit["id"]
        _require(_text(unit.get("label")) and _text(unit.get("area")), f"unit {uid} needs label and area")
        disposition = unit.get("disposition")
        _require(disposition in DISPOSITIONS, f"unknown disposition for {uid}")
        _require(isinstance(unit.get("scope_basis"), str), f"unit {uid} needs scope_basis")
        if disposition != "unresolved":
            _require(_text(unit["scope_basis"]), f"unit {uid} requires nonempty scope_basis")
        if disposition == "replace":
            target = unit.get("replacement_id")
            _require(isinstance(target, str) and target in units, f"replacement {uid} must reference an existing retained unit")
            _require(target != uid and units[target].get("disposition") == "retain",
                     f"replacement {uid} must directly reference a retained unit (no chains or cycles)")
        else:
            _require("replacement_id" not in unit, f"replacement_id only valid on replace unit {uid}")
    targets = deepcopy(plan.get("targets", {"breadth": 100, "depth": 80}))
    _require(isinstance(targets, dict) and set(targets) == {"breadth", "depth"}, "targets requires breadth and depth")
    for name, value in targets.items():
        _require(type(value) in (int, float) and 0 <= value <= 100, f"invalid target {name}")
    raw_cells = plan.get("cells")
    _require(isinstance(raw_cells, list), "cells must be an array")
    supplied = {}
    for cell in raw_cells:
        _require(isinstance(cell, dict), "cell must be an object")
        uid, cid = cell.get("unit"), cell.get("candidate")
        _require(isinstance(uid, str) and uid in units, f"unknown cell unit: {uid}")
        _require(isinstance(cid, str) and cid in candidates, f"unknown cell candidate: {cid}")
        key = uid, cid
        _require(key not in supplied, f"duplicate cell: {uid}/{cid}")
        _require(_pin(cell.get("source_pin")), f"cell {uid}/{cid} needs full 40-character SHA")
        _require(cell.get("stage") in STAGES, f"unknown stage: {uid}/{cid}")
        for name in ("owner", "blocker"):
            _require(name in cell and (cell[name] is None or _text(cell[name])), f"{uid}/{cid}: {name} must be nonempty string or null")
        evidence = cell.get("evidence")
        _require(isinstance(evidence, list) and all(_text(e) for e in evidence), f"invalid evidence: {uid}/{cid}")
        if cell["stage"] == "implemented":
            _require(evidence, f"implemented cell {uid}/{cid} requires evidence references")
        depth = cell.get("depth")
        _require(isinstance(depth, dict), f"depth must be an object: {uid}/{cid}")
        _require(set(depth) <= set(dimensions), f"unknown depth dimension: {uid}/{cid}")
        _require(all(s in DEPTH for s in depth.values()), f"unknown depth status: {uid}/{cid}")
        if "depth_unblock_reason" in cell:
            exception = cell["depth_unblock_reason"]
            _require(isinstance(exception, dict) and exception.get("kind") in ("security", "critical")
                     and _text(exception.get("reason")), f"{uid}/{cid}: depth_unblock_reason needs security/critical kind and explicit reason")
        supplied[key] = cell
    cells = []
    for uid in units:
        for cid, candidate in candidates.items():
            raw = supplied.get((uid, cid))
            cell = deepcopy(raw) if raw is not None else {
                "unit": uid, "candidate": cid, "source_pin": candidate["source_pin"],
                "stage": "unknown", "owner": None, "blocker": None, "evidence": [], "depth": {},
            }
            cell["reported_stage"] = cell["stage"]
            cell["reported_depth"] = deepcopy(cell["depth"])
            cell["omitted"] = raw is None
            cell["stale"] = cell["source_pin"].lower() != candidate["source_pin"].lower()
            cell["unknown_reason"] = "omitted cell" if raw is None else None
            if cell["stale"]:
                cell["stage"] = "unknown"
                cell["depth"] = {}
                cell["unknown_reason"] = "source_pin differs from candidate source_pin; historical claims receive no credit"
            cell["depth"] = {d: cell["depth"].get(d, "unknown") for d in dimensions}
            cell["evidence_status"] = "reported-not-verified"
            cell["eligible"] = units[uid]["disposition"] == "retain"
            cell["capability_unit"] = units[uid].get("replacement_id", uid)
            cells.append(cell)
    return candidates, units, dimensions, targets, cells


def _percent(numerator, denominator):
    return round(100 * numerator / denominator, 6) if denominator else None


def _summary(cells, units, dimensions, targets):
    eligible = [c for c in cells if c["eligible"]]
    unresolved = sum(u["disposition"] == "unresolved" for u in units.values())
    implemented = sum(c["stage"] == "implemented" for c in eligible)
    passed = sum(s == "pass" for c in eligible for s in c["depth"].values())
    breadth = _percent(implemented, len(eligible))
    depth = _percent(passed, len(eligible) * len(dimensions))
    complete = bool(eligible) and implemented == len(eligible) and unresolved == 0
    return {
        "eligible_units": len(eligible), "implemented_units": implemented,
        "unresolved_scope_units": unresolved,
        "replacement_aliases": sum(u["disposition"] == "replace" for u in units.values()),
        "excluded_units": sum(u["disposition"] == "exclude" for u in units.values()),
        "reported_breadth_percent": breadth,
        "inventory_breadth_floor_percent": _percent(implemented, len(eligible) + unresolved),
        "depth_passed": passed, "depth_denominator": len(eligible) * len(dimensions),
        "reported_depth_percent": depth,
        "stages": {stage: sum(c["stage"] == stage for c in eligible) for stage in STAGES},
        "unowned": [c["unit"] for c in cells if c["owner"] is None],
        "blockers": [{"unit": c["unit"], "reason": c["blocker"]} for c in cells if c["blocker"]],
        "stale": [c["unit"] for c in cells if c["stale"]],
        "breadth_complete": complete,
        "targets_met": bool(eligible) and unresolved == 0 and breadth >= targets["breadth"] and depth >= targets["depth"],
    }


def _delta(previous, current):
    result = {"cell_movements": [], "regressions": [], "inventory_changes": [],
              "scope_changes": [], "pin_changes": [], "policy_changes": [], "review_issues": []}
    if previous is None:
        return result
    _require(isinstance(previous, dict) and previous.get("format") == "capcov-progress-v1",
             "previous must be a capcov-progress-v1 report")
    # Recompute the saved input instead of trusting mutable summary numbers.
    old = build_progress(previous.get("plan"))
    def issue(code, **detail):
        result["review_issues"].append({"code": code, **detail})
    if old["unit_namespace"] != current["unit_namespace"]:
        issue("unit-namespace-changed", before=old["unit_namespace"], after=current["unit_namespace"])
    old_units = {u["id"]: u for u in old["units"]}
    new_units = {u["id"]: u for u in current["units"]}
    for uid in sorted(set(old_units) | set(new_units)):
        before, after = old_units.get(uid), new_units.get(uid)
        if before is None or after is None:
            result["inventory_changes"].append({"unit": uid, "change": "added" if before is None else "removed"})
            if after is None:
                issue("inventory-unit-removed", unit=uid)
            elif after["disposition"] == "exclude":
                issue("excluded-unit-added", unit=uid, scope_basis=after["scope_basis"])
            continue
        for field in ("disposition", "scope_basis", "replacement_id", "area", "label"):
            if before.get(field) != after.get(field):
                change = {"unit": uid, "field": field, "before": before.get(field), "after": after.get(field)}
                result["scope_changes"].append(change)
                issue("scope-changed", **change)
    old_candidates = {c["id"]: c for c in old["candidates"]}
    new_candidates = {c["id"]: c for c in current["candidates"]}
    for cid in sorted(set(old_candidates) | set(new_candidates)):
        before, after = old_candidates.get(cid), new_candidates.get(cid)
        if before is None or after is None:
            result["inventory_changes"].append({"candidate": cid, "change": "added" if before is None else "removed"})
            if after is None:
                issue("candidate-removed", candidate=cid)
        elif before["source_pin"].lower() != after["source_pin"].lower():
            change = {"candidate": cid, "before": before["source_pin"], "after": after["source_pin"]}
            result["pin_changes"].append(change)
            issue("source-pin-changed", **change)
    for field in ("depth_dimensions", "targets"):
        if old[field] != current[field]:
            change = {"field": field, "before": old[field], "after": current[field]}
            result["policy_changes"].append(change)
            issue("policy-changed", **change)
    result["denominators"] = {
        cid: {"before": old["summary"][cid]["eligible_units"] if cid in old_candidates else None,
              "after": current["summary"][cid]["eligible_units"] if cid in new_candidates else None}
        for cid in sorted(set(old_candidates) | set(new_candidates))
    }
    old_cells = {(c["unit"], c["candidate"]): c for c in old["cells"]}
    for cell in current["cells"]:
        before = old_cells.get((cell["unit"], cell["candidate"]))
        if before is None:
            continue
        changes = {}
        for field in ("stage", "depth", "reported_stage", "reported_depth", "owner", "blocker",
                      "source_pin", "evidence", "stale", "omitted", "depth_unblock_reason"):
            if before.get(field) != cell.get(field):
                changes[field] = {"before": before.get(field), "after": cell.get(field)}
        if changes:
            movement = {"unit": cell["unit"], "candidate": cell["candidate"], "changes": changes}
            result["cell_movements"].append(movement)
            regressed = STAGES.index(cell["stage"]) < STAGES.index(before["stage"])
            regressed |= any(s == "pass" and cell["depth"].get(d) != "pass" for d, s in before["depth"].items())
            if regressed:
                result["regressions"].append(movement)
    return result


def _queue(candidates, units, cells, breadth_complete):
    queues = {cid: [] for cid in candidates}
    depth_queues = {cid: [] for cid in candidates}
    priority = {"missing": 0, "unknown": 1, "partial": 2, "implemented": 3}
    for cell in sorted(cells, key=lambda c: priority[c["stage"]]):
        uid, cid = cell["unit"], cell["candidate"]
        if not cell["eligible"]:
            continue
        base = {"unit": uid, "candidate": cid, "area": units[uid]["area"],
                "owner": cell["owner"], "blocker": cell["blocker"], "stage": cell["stage"]}
        if cell["stage"] != "implemented":
            queues[cid].append({**base, "kind": "breadth", "reason": cell["unknown_reason"] or f"product capability {cell['stage']}"})
        pending = [d for d, status in cell["depth"].items() if status != "pass"]
        exception = cell.get("depth_unblock_reason")
        if pending and (breadth_complete or exception):
            task = {**base, "kind": "depth", "dimensions": pending,
                    "reason": exception if exception else "all candidates have complete product breadth"}
            # Explicit baseline/security unblock precedes ordinary product work.
            if exception:
                queues[cid].insert(0, task)
            else:
                depth_queues[cid].append(task)
    def interleave(groups):
        return [item for row in zip_longest(*groups.values()) for item in row if item is not None]
    scope = [{"kind": "scope", "unit": uid, "area": u["area"], "reason": "unresolved product scope"}
             for uid, u in units.items() if u["disposition"] == "unresolved"]
    return interleave(queues) + scope + interleave(depth_queues)


def build_progress(plan: dict, previous: dict | None = None) -> dict:
    """Build a deterministic report; persist it and pass it as ``previous`` next time.

    Evidence strings are reported references, never executed or adjudicated here.
    Replacement rows are aliases; their explicit retained target counts once.
    """
    candidates, units, dimensions, targets, cells = _normalize(plan)
    summary = {}
    by_area = {}
    for cid in candidates:
        selected = [c for c in cells if c["candidate"] == cid]
        summary[cid] = _summary(selected, units, dimensions, targets)
        by_area[cid] = {}
        for area in dict.fromkeys(u["area"] for u in units.values()):
            area_units = {uid: u for uid, u in units.items() if u["area"] == area}
            by_area[cid][area] = _summary([c for c in selected if c["unit"] in area_units], area_units, dimensions, targets)
    report = {
        "format": "capcov-progress-v1", "unit_namespace": plan["unit_namespace"],
        "evidence_status": "reported-not-verified", "targets": targets,
        "candidates": list(candidates.values()), "units": list(units.values()),
        "depth_dimensions": deepcopy(dimensions), "cells": cells,
        "summary": summary, "by_area": by_area, "plan": deepcopy(plan),
    }
    report["delta"] = _delta(previous, report)
    report["review_required"] = bool(report["delta"]["review_issues"])
    report["breadth_complete"] = all(s["breadth_complete"] for s in summary.values())
    report["targets_met"] = not report["review_required"] and all(s["targets_met"] for s in summary.values())
    report["work_queue"] = _queue(candidates, units, cells, report["breadth_complete"])
    report["next_work"] = report["work_queue"][0] if report["work_queue"] else None
    return report
