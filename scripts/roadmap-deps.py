#!/usr/bin/env python3
"""Validate docs/roadmap-deps.json and regenerate the roadmap's dependency tables.

The JSON file is the single source of the R-series dependencies. This script
checks it and rewrites three kinds of generated text in docs/production-roadmap.md:
the dependency table of section 4, the R-table of section 17, and the
"Changes" line under each B/W work-package heading. Prose outside those regions
is never touched.

Usage: python scripts/roadmap-deps.py [--check] [--deps FILE] [--roadmap FILE]

Without --check the roadmap is rewritten in place. With --check nothing is
written and the exit status is 1 when the data is invalid or the roadmap differs
from what the data generates. Run it from the project root.

Validation:
* ids are unique and every referenced R-id, work package, condition and
  executor class is declared;
* an entry depends only on entries listed before it, which makes the graph
  acyclic, and no dependency is implied by another of the same entry's, so each
  graph has one spelling;
* every capability is delivered by exactly one entry, and every required
  capability is delivered by an entry listed before the one that needs it;
* an unconditional requirement is delivered within the entry's own dependency
  closure, and every direct dependency supplies at least one requirement, so
  `depends` and `requires_capabilities` cannot disagree.

Dependency closure: depending on an entry means depending on its completion, so
the closure includes that entry's `qualification_depends`. An entry's own
`qualification_depends` gates only its qualification stage, not its start.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

DEFAULT_DEPS = Path("docs") / "roadmap-deps.json"
DEFAULT_ROADMAP = Path("docs") / "production-roadmap.md"
STAGES = ("start", "qualification")
TESTS = {"count_gt", "gt", "true", "any_flag"}

BEGIN = "<!-- generated: roadmap-deps section={} -->"
END = "<!-- end generated: roadmap-deps -->"
WP_MARK = "<!-- generated: roadmap-deps wp={} -->"
WP_HEADING = re.compile(r"^#{2,3} (?:\d+\. )?(B\d+|W\d+) — ")


class DepsError(ValueError):
    """The dependency data is not usable."""


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DepsError(f"{path}: {exc}") from exc


def _closure(by_id: dict[str, dict], roots: list[str]) -> set[str]:
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        rid = stack.pop()
        if rid in seen or rid not in by_id:
            continue
        seen.add(rid)
        entry = by_id[rid]
        stack.extend(entry.get("depends", []))
        stack.extend(entry.get("qualification_depends", []))
    return seen


def _requirements(entry: dict) -> list[dict]:
    return entry.get("requires_capabilities", [])


def validate(data: dict) -> list[str]:
    """Return every problem found; an empty list means the data is consistent."""
    errors: list[str] = []
    if not isinstance(data, dict) or data.get("version") != 1:
        return ["expected an object with \"version\": 1"]
    packages = data.get("work_packages", {})
    conditions = data.get("conditions", {})
    executors = data.get("executor_classes", {})
    changes = data.get("changes", [])

    for name, condition in conditions.items():
        tests = condition.get("any_of") if isinstance(condition, dict) else None
        if not tests or not condition.get("description"):
            errors.append(f"condition {name}: needs a description and a non-empty any_of")
            continue
        for test in tests:
            if test.get("test") not in TESTS or not test.get("field"):
                errors.append(f"condition {name}: unsupported test {test!r}")
            elif test["test"] in ("gt", "count_gt") and not _is_number(test.get("value")):
                errors.append(f"condition {name}: {test['test']} on {test['field']} needs a numeric value")
            elif test["test"] == "any_flag" and not test.get("flag"):
                errors.append(f"condition {name}: any_flag on {test['field']} needs a flag")

    if not isinstance(data.get("conditions_about"), str):
        errors.append("conditions_about must say whose schema the condition fields belong to")

    order: dict[str, int] = {}
    for index, entry in enumerate(changes):
        rid = entry.get("id")
        if not isinstance(rid, str) or not re.fullmatch(r"R\d\d[a-z]?", rid):
            errors.append(f"changes[{index}]: bad id {rid!r}")
            continue
        if rid in order:
            errors.append(f"{rid}: duplicate id")
        order[rid] = index
    by_id = {entry["id"]: entry for entry in changes if entry.get("id") in order}

    deliverer: dict[str, str] = {}
    for entry in changes:
        for capability in entry.get("delivers", []):
            if capability in deliverer:
                errors.append(f"{capability}: delivered by both {deliverer[capability]} and {entry['id']}")
            deliverer.setdefault(capability, entry["id"])

    for entry in changes:
        rid = entry.get("id")
        if rid not in order:
            continue
        for field in ("title", "gate"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                errors.append(f"{rid}: missing {field}")
        if entry.get("work_package") not in packages:
            errors.append(f"{rid}: unknown work package {entry.get('work_package')!r}")
        classes = entry.get("executor_classes", [])
        if not classes or any(c not in executors for c in classes):
            errors.append(f"{rid}: executor classes {classes!r} are empty or undeclared")
        if "none" in classes and len(classes) > 1:
            errors.append(f"{rid}: executor class none cannot be combined")
        if not entry.get("delivers"):
            errors.append(f"{rid}: delivers no capability")
        for field in ("depends", "qualification_depends"):
            for dep in entry.get(field, []):
                if dep not in order:
                    errors.append(f"{rid}: {field} names unknown id {dep}")
                elif dep == rid:
                    errors.append(f"{rid}: {field} names itself")
                elif order[dep] > order[rid]:
                    errors.append(f"{rid}: {field} names {dep}, which is listed later")

        direct = list(entry.get("depends", [])) + list(entry.get("qualification_depends", []))
        for dep in direct:
            via = [other for other in direct if other != dep and dep in _closure(by_id, [other]) - {other}]
            if via:
                errors.append(f"{rid}: dependency on {dep} is redundant; it is implied by {via[0]}")
        start_closure = _closure(by_id, entry.get("depends", []))
        full_closure = start_closure | _closure(by_id, entry.get("qualification_depends", []))
        supplied: set[str] = set()
        for requirement in _requirements(entry):
            capability = requirement.get("capability")
            stage = requirement.get("stage", "start")
            when = requirement.get("when")
            if stage not in STAGES:
                errors.append(f"{rid}: {capability}: unknown stage {stage!r}")
            if when is not None and when not in conditions:
                errors.append(f"{rid}: {capability}: unknown condition {when!r}")
            source = deliverer.get(capability)
            if source is None:
                errors.append(f"{rid}: requires {capability}, which no change delivers")
                continue
            if source == rid or order[source] > order[rid]:
                errors.append(f"{rid}: requires {capability}, delivered by {source}, which is not listed before it")
                continue
            if when is None:
                closure = start_closure if stage == "start" else full_closure
                if source not in closure:
                    errors.append(f"{rid}: requires {capability} at {stage} but {source} is not in its dependencies")
                supplied.add(source)
        for dep in sorted(set(direct)):
            if dep in by_id and dep not in supplied:
                errors.append(f"{rid}: depends on {dep} but requires none of the capabilities it supplies")

    return errors


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def holds(data: dict, condition: str, record: dict) -> bool:
    """Evaluate a declared condition against one record (e.g. an R19 inventory entry).

    A field of the wrong type is a DepsError naming the field, not a guess.
    """
    for test in data["conditions"][condition]["any_of"]:
        field, kind = test["field"], test["test"]
        value = record.get(field)
        if kind in ("count_gt", "any_flag"):
            if value is None:
                value = []
            if not isinstance(value, list) or (kind == "any_flag" and not all(isinstance(i, dict) for i in value)):
                raise DepsError(f"{condition}: field {field} must be a list" + (" of objects" if kind == "any_flag" else ""))
            if kind == "count_gt" and len(value) > test["value"]:
                return True
            if kind == "any_flag" and any(item.get(test["flag"]) is True for item in value):
                return True
        elif kind == "gt":
            if value is None:
                continue
            if not _is_number(value):
                raise DepsError(f"{condition}: field {field} must be a number, got {value!r}")
            if value > test["value"]:
                return True
        elif kind == "true":
            if value is not None and not isinstance(value, bool):
                raise DepsError(f"{condition}: field {field} must be true or false, got {value!r}")
            if value is True:
                return True
    return False


# ---- rendering -------------------------------------------------------------


def _ids(ids) -> str:
    return ", ".join(ids) if ids else "—"


def _deliverers(data: dict) -> dict[str, str]:
    return {cap: entry["id"] for entry in data["changes"] for cap in entry["delivers"]}


def _conditional(entry: dict, deliverer: dict[str, str]) -> str:
    grouped: dict[tuple[str, str], list[str]] = {}
    for requirement in _requirements(entry):
        if requirement.get("when"):
            key = (requirement.get("stage", "start"), requirement["when"])
            grouped.setdefault(key, []).append(deliverer[requirement["capability"]])
    parts = []
    for (stage, when), ids in grouped.items():
        prefix = "to qualify, " if stage == "qualification" else ""
        parts.append(f"{prefix}{_ids(ids)} if `{when}`")
    return "; ".join(parts) or "—"


def _depends(entry: dict) -> str:
    qualification = entry.get("qualification_depends", [])
    if not qualification:
        return _ids(entry["depends"])
    start = _ids(entry["depends"]) if entry["depends"] else "none to start"
    return f"{start}; {_ids(qualification)} to qualify"


def render_section4(data: dict) -> list[str]:
    deliverer = _deliverers(data)
    groups: dict[str, list[dict]] = {}
    for entry in data["changes"]:
        groups.setdefault(entry["work_package"], []).append(entry)
    lines = ["| Work package | Changes | Depends on | Conditional requirements |",
             "| --- | --- | --- | --- |"]
    for wp, entries in groups.items():
        if len(entries) == 1:
            depends = _depends(entries[0])
        else:
            depends = "; ".join(f"{e['id']} ← {_depends(e)}" for e in entries)
        conditional = "; ".join(
            f"{e['id']}: {c}" if len(entries) > 1 else c
            for e, c in ((e, _conditional(e, deliverer)) for e in entries) if c != "—") or "—"
        lines.append(f"| {wp}: {data['work_packages'][wp]} | {_ids([e['id'] for e in entries])} | {depends} | {conditional} |")
    lines += ["", f"Conditions are evaluated per record, not by judgment. {data['conditions_about']}", ""]
    for name, condition in data["conditions"].items():
        lines.append(f"* `{name}` (per {condition['applies_to']}): {condition['description']}")
    return lines


def render_section17(data: dict) -> list[str]:
    deliverer = _deliverers(data)
    lines = ["| ID | Change | Depends on | Conditional | Executors | Exit evidence |",
             "| --- | --- | --- | --- | --- | --- |"]
    for entry in data["changes"]:
        lines.append(
            f"| {entry['id']} | {entry['title']} ({entry['work_package']}) | {_depends(entry)} | "
            f"{_conditional(entry, deliverer)} | {', '.join(entry['executor_classes'])} | {entry['gate']} |")
    lines += ["", "Executors name what an exit artifact executes:", ""]
    for name, description in data["executor_classes"].items():
        lines.append(f"* `{name}`: {description}.")
    return lines


def _replace_region(lines: list[str], section: str, body: list[str]) -> list[str]:
    begin = BEGIN.format(section)
    try:
        start = lines.index(begin)
        stop = lines.index(END, start)
    except ValueError as exc:
        raise DepsError(f"roadmap has no generated region for section {section}") from exc
    return lines[:start + 1] + [""] + body + [""] + lines[stop:]


def regenerate(data: dict, text: str) -> str:
    lines = text.split("\n")
    lines = _replace_region(lines, "4", render_section4(data))
    lines = _replace_region(lines, "17", render_section17(data))
    by_wp: dict[str, list[str]] = {}
    for entry in data["changes"]:
        by_wp.setdefault(entry["work_package"], []).append(entry["id"])
    out: list[str] = []
    seen: set[str] = set()
    index = 0
    while index < len(lines):
        line = lines[index]
        out.append(line)
        index += 1
        match = WP_HEADING.match(line)
        if not match:
            continue
        wp = match.group(1)
        if wp not in by_wp:
            raise DepsError(f"heading for undeclared work package {wp}")
        if wp in seen:
            raise DepsError(f"work package {wp} has more than one heading")
        seen.add(wp)
        mark = WP_MARK.format(wp)
        # Drop an existing generated line (and its blank separator) under the heading.
        if index + 1 < len(lines) and lines[index] == "" and lines[index + 1].endswith(mark):
            index += 2
        out += ["", f"**Changes:** {_ids(by_wp[wp])} (§17). {mark}"]
    missing = set(by_wp) - seen
    if missing:
        raise DepsError(f"no heading for work package(s) {', '.join(sorted(missing))}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail instead of rewriting on mismatch")
    parser.add_argument("--deps", type=Path, default=DEFAULT_DEPS)
    parser.add_argument("--roadmap", type=Path, default=DEFAULT_ROADMAP)
    args = parser.parse_args(argv)
    try:
        data = load(args.deps)
        errors = validate(data)
        if errors:
            for error in errors:
                print(f"{args.deps}: {error}", file=sys.stderr)
            return 1
        current = args.roadmap.read_text(encoding="utf-8")
        expected = regenerate(data, current)
    except (DepsError, OSError) as exc:
        print(f"roadmap-deps: {exc}", file=sys.stderr)
        return 1
    if current == expected:
        return 0
    if args.check:
        sys.stderr.writelines(difflib.unified_diff(
            current.splitlines(keepends=True), expected.splitlines(keepends=True),
            str(args.roadmap), f"{args.roadmap} (generated from {args.deps})"))
        print(f"roadmap-deps: {args.roadmap} is out of date; run python scripts/roadmap-deps.py",
              file=sys.stderr)
        return 1
    args.roadmap.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
