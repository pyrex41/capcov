#!/usr/bin/env python3
"""Generate the IR constructor tables in docs/ir-specification.md from Shen datatypes.

Each generated region of the document names the .shen file it is generated from:

    <!-- BEGIN GENERATED ir-constructors src/capcov/operations/shen/system-types.shen -->
    ...
    <!-- END GENERATED ir-constructors -->

Every typing rule of every (datatype ...) in that file becomes one table row:
the datatype, the conclusion, the premises, the side condition, the source line,
and whether capcov.operations.system accepts the conclusion's head tag today
(its SYSTEM_TAGS). Nothing in a region is written by hand.

Usage: python scripts/ir-constructors.py [--check] [--doc FILE]

Without --check the regions are rewritten in place. With --check nothing is
written and the exit status is 1 when any region differs from what the .shen
file generates. Run from the project root. Standard library only.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import re
import sys
from pathlib import Path

DEFAULT_DOC = Path("docs") / "ir-specification.md"
SYSTEM_PY = Path("src") / "capcov" / "operations" / "system.py"
BEGIN = re.compile(r"^<!-- BEGIN GENERATED ir-constructors (\S+) -->$", re.M)
END = "<!-- END GENERATED ir-constructors -->"
UNDERLINE = re.compile(r"_{3,}")


class DatatypeError(ValueError):
    """The .shen source is not in the datatype subset this script reads."""


def _blank_comments(text: str) -> str:
    """Replace Shen comments with spaces, keeping every newline (line numbers hold)."""
    def blank(match: re.Match) -> str:
        return re.sub(r"[^\n]", " ", match.group())
    text = re.sub(r"\\\*.*?\*\\", blank, text, flags=re.S)
    return re.sub(r"\\\\[^\n]*", blank, text)


def _close(text: str, start: int, opener: str, closer: str) -> int:
    """Index just past the closer matching text[start] == opener."""
    depth = 0
    for index in range(start, len(text)):
        if text[index] == opener:
            depth += 1
        elif text[index] == closer:
            depth -= 1
            if depth == 0:
                return index + 1
    raise DatatypeError(f"unbalanced {opener} at offset {start}")


def _until_semicolon(text: str, start: int) -> int:
    """Index of the first ';' at bracket depth 0 from start, or -1."""
    depth = 0
    for index in range(start, len(text)):
        c = text[index]
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        elif c == ";" and depth == 0:
            return index
    return -1


def _squash(text: str) -> str:
    return " ".join(text.split())


def _premises(text: str, offset: int) -> tuple[list[str], list[str]]:
    premises, conditions = [], []
    index = 0
    while True:
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            return premises, conditions
        if re.match(r"if\s*\(", text[index:]):
            opening = text.index("(", index)
            end = _close(text, opening, "(", ")")
            conditions.append(_squash(text[opening:end]))
            index = end
            continue
        end = _until_semicolon(text, index)
        if end == -1:
            raise DatatypeError(f"premise without ';' at offset {offset + index}")
        premises.append(_squash(text[index:end]))
        index = end + 1


def rules(source: str) -> list[dict]:
    """Every typing rule of every datatype in a .shen source, in source order."""
    text = _blank_comments(source)
    found = []
    for match in re.finditer(r"\(datatype\s+([^\s()]+)", text):
        end = _close(text, match.start(), "(", ")")
        body_start = match.end()
        body = text[body_start:end - 1]
        position = 0
        lines = 0
        for line in UNDERLINE.finditer(body):
            premise_text = body[position:line.start()]
            stop = _until_semicolon(body, line.end())
            if stop == -1:
                raise DatatypeError(f"{match.group(1)}: conclusion without ';'")
            conclusion = _squash(body[line.end():stop])
            if ":" not in conclusion:
                raise DatatypeError(f"{match.group(1)}: conclusion is not a typing: {conclusion}")
            premises, conditions = _premises(premise_text, body_start + position)
            found.append({
                "datatype": match.group(1),
                "conclusion": conclusion,
                "premises": premises,
                "conditions": conditions,
                "line": text.count("\n", 0, body_start + line.end() + 1) + 1,
            })
            position = stop + 1
            lines += 1
        if lines == 0:
            raise DatatypeError(f"{match.group(1)}: datatype without rules")
        if body[position:].strip():
            raise DatatypeError(f"{match.group(1)}: text after the last rule: {_squash(body[position:])}")
    if not found:
        raise DatatypeError("no datatype found")
    return found


def head_tag(conclusion: str) -> str | None:
    """The constructor tag of a conclusion '[tag ...] : type', if it has one."""
    term = conclusion.rsplit(":", 1)[0].strip()
    m = re.match(r"\[([a-z][A-Za-z0-9_.?!+*<>=/-]*)[\s\]]", term)
    return m.group(1) if m else None


def tags(source: str) -> set[str]:
    """Head tags of every rule, plus nested lowercase tags in conclusions (e.g. per-attempt, ok)."""
    found = set()
    for rule in rules(source):
        term = rule["conclusion"].rsplit(":", 1)[0]
        found.update(re.findall(r"\[([a-z][A-Za-z0-9_.?!+*<>=/-]*)", term))
    return found


def system_tags(path: Path = SYSTEM_PY) -> frozenset[str]:
    """SYSTEM_TAGS of capcov.operations.system, read from its source without importing it."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "SYSTEM_TAGS" for t in node.targets
        ):
            for inner in ast.walk(node.value):
                if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                    return frozenset(inner.value.split())
    raise DatatypeError(f"{path}: SYSTEM_TAGS not found")


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def table(source: str, accepted: frozenset[str]) -> str:
    out = [
        "| Datatype | Conclusion | Premises | Side condition | Line | `system.py` accepts tag |",
        "|---|---|---|---|---|---|",
    ]
    for rule in rules(source):
        tag = head_tag(rule["conclusion"])
        status = "—" if tag is None else ("yes" if tag in accepted else "no")
        out.append("| {} | `{}` | {} | {} | {} | {} |".format(
            f"`{rule['datatype']}`",
            _cell(rule["conclusion"]),
            _cell("; ".join(f"`{p}`" for p in rule["premises"])) or "—",
            _cell("; ".join(f"`{c}`" for c in rule["conditions"])) or "—",
            rule["line"],
            status,
        ))
    return "\n".join(out)


def regenerate(document: str, root: Path) -> str:
    accepted = system_tags(root / SYSTEM_PY)
    pieces, position = [], 0
    matches = list(BEGIN.finditer(document))
    if not matches:
        raise DatatypeError("document has no generated region")
    for match in matches:
        end = document.find(END, match.end())
        if end == -1:
            raise DatatypeError(f"region for {match.group(1)} has no end marker")
        source = (root / match.group(1)).read_text(encoding="utf-8")
        pieces.append(document[position:match.end()])
        pieces.append("\n" + table(source, accepted) + "\n")
        position = end
    pieces.append(document[position:])
    return "".join(pieces)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail instead of rewriting")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    path = args.root / args.doc
    current = path.read_text(encoding="utf-8")
    try:
        fresh = regenerate(current, args.root)
    except (DatatypeError, OSError) as exc:
        print(f"ir-constructors: {exc}", file=sys.stderr)
        return 2
    if fresh == current:
        return 0
    if args.check:
        sys.stdout.writelines(difflib.unified_diff(
            current.splitlines(True), fresh.splitlines(True), str(path), "generated"))
        print(f"ir-constructors: {path} is out of date; run scripts/ir-constructors.py", file=sys.stderr)
        return 1
    path.write_text(fresh, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
