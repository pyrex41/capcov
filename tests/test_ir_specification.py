"""docs/ir-specification.md stays tied to the code, the draft and the fixtures.

Base family: no Shen. Nothing here checks v2 semantics (none is implemented);
it checks that the specification's tables are generated or cross-checked, not
hand-copied, and that the v2 draft stays out of the engine.
"""
from __future__ import annotations

import ast
import contextlib
import io
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from capcov.claims.spec.parser import Symbol, parse
from capcov.operations import OperationError
from capcov.operations.system import SYSTEM_LIBRARIES, _term

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ir-constructors.py"
DOC = ROOT / "docs" / "ir-specification.md"
SHEN = ROOT / "src" / "capcov" / "operations" / "shen"
V1 = SHEN / "system-types.shen"
DRAFT = SHEN / "system-types-v2-draft.shen"
SYSTEMS = ROOT / "tests" / "claim_semantics" / "fixtures" / "systems"
V2 = SYSTEMS / "v2-draft"
POSITIVE = ("transfer-outbox.ops-v2", "histories.ops-v2")
PROBE = ROOT / "tests" / "claim_semantics" / "test_migration_probe.py"

_spec = importlib.util.spec_from_file_location("ir_constructors", SCRIPT)
ir = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ir)


def section(number: int) -> str:
    """Text of '## <number>. ...' up to the next level-2 heading."""
    text = DOC.read_text(encoding="utf-8")
    match = re.search(rf"^## {number}\. .*?(?=^## |\Z)", text, re.M | re.S)
    if not match:
        raise AssertionError(f"docs/ir-specification.md has no section {number}")
    return match.group()


def rows(text: str) -> list[list[str]]:
    """Body rows of every markdown table in text, as stripped cells."""
    found = []
    for line in text.splitlines():
        if line.startswith("|") and not re.match(r"^\|[-| ]+\|$", line):
            found.append([c.strip() for c in line.strip().strip("|").split("|")])
    return found


def ticks(cell: str) -> list[str]:
    return re.findall(r"`([^`]+)`", cell)


def symbols(path: Path) -> set[str]:
    found = set()

    def walk(node):
        if isinstance(node.value, Symbol):
            found.add(node.value.text)
        elif isinstance(node.value, tuple):
            for child in node.value:
                walk(child)

    for term in parse(path.read_text(encoding="utf-8"), str(path)):
        walk(term)
    return found


class ConstructorTableTest(unittest.TestCase):
    def test_generated_regions_are_current(self) -> None:
        done = subprocess.run(
            [sys.executable, str(SCRIPT), "--check"], cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_a_datatype_edit_makes_the_check_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in (DOC, V1, DRAFT, ROOT / ir.SYSTEM_PY):
                target = root / path.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(path, target)
            shen = root / V1.relative_to(ROOT)
            shen.write_text(shen.read_text().replace("[row-key] : caps-expr;", "[row-id] : caps-expr;"))
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(ir.main(["--check", "--root", str(root)]), 1)
            self.assertEqual(ir.main(["--root", str(root)]), 0)
            self.assertIn("`[row-id] : caps-expr`", (root / DOC.relative_to(ROOT)).read_text())
            self.assertEqual(ir.main(["--check", "--root", str(root)]), 0)

    def test_every_typing_rule_becomes_one_row(self) -> None:
        for path in (V1, DRAFT):
            with self.subTest(path=path.name):
                source = path.read_text()
                underlines = len(re.findall(r"^\s*_{3,}\s*$", source, re.M))
                self.assertEqual(len(ir.rules(source)), underlines)

    def test_unreadable_datatypes_are_refused(self) -> None:
        for source in (
            "(datatype t\n  X : string;\n  ____\n  [a X] : t)",
            "(datatype t\n  X : string\n  ____\n  [a X] : t;)",
            "(datatype t)",
            "(define f X -> X)",
        ):
            with self.subTest(source=source), self.assertRaises(ir.DatatypeError):
                ir.rules(source)

    def test_side_conditions_and_comments(self) -> None:
        (rule,) = ir.rules(
            "\\\\ a comment ____ with an underline\n(datatype t\n  if (ok? X)\n  X : u;\n  ___\n  X : t;)"
        )
        self.assertEqual((rule["premises"], rule["conditions"], rule["line"]), (["X : u"], ["(ok? X)"], 6))

    def test_the_draft_is_not_loaded_by_the_engine(self) -> None:
        self.assertNotIn(DRAFT.name, SYSTEM_LIBRARIES)
        for path in (ROOT / "src").rglob("*"):
            if path.is_file() and path != DRAFT and path.suffix in {".py", ".shen", ".dl", ".json"}:
                with self.subTest(path=path):
                    self.assertNotIn(DRAFT.stem, path.read_text(encoding="utf-8", errors="replace"))


class DraftFixtureTest(unittest.TestCase):
    def test_every_fixture_parses(self) -> None:
        files = sorted(V2.glob("*.ops-v2"))
        self.assertGreaterEqual(len(files), 2 + 5)
        for path in files:
            with self.subTest(path=path.name):
                self.assertTrue(parse(path.read_text(encoding="utf-8"), str(path)))

    def test_positive_fixtures_use_only_declared_constructors(self) -> None:
        declared = ir.tags(V1.read_text()) | ir.tags(DRAFT.read_text())
        for name in POSITIVE:
            with self.subTest(fixture=name):
                self.assertEqual(symbols(V2 / name) - declared, set())

    def test_the_v1_front_end_refuses_the_draft_model(self) -> None:
        with self.assertRaisesRegex(OperationError, "unsupported system constructor"):
            _term((V2 / "transfer-outbox.ops-v2").read_text())

    def test_each_rejected_fixture_names_a_rule_of_the_specification(self) -> None:
        rules = {ticks(r[0])[0] for r in rows(section(4)) if r and re.fullmatch(r"`[TR]-[A-Za-z0-9-]+`", r[0])}
        listed = {ticks(r[0])[0]: ticks(r[1])[0] for r in rows(section(6)) if r[0].startswith("`rejected-")}
        files = sorted(p.name for p in V2.glob("rejected-*.ops-v2"))
        self.assertEqual(sorted(listed), files)
        for name in files:
            with self.subTest(fixture=name):
                first = (V2 / name).read_text(encoding="utf-8").splitlines()[0]
                match = re.fullmatch(r"; rejected-by: ([TR]-[A-Za-z0-9-]+)", first)
                self.assertIsNotNone(match, first)
                self.assertIn(match.group(1), rules)
                self.assertEqual(listed[name], match.group(1))

    def test_every_new_constructor_has_a_negative_example(self) -> None:
        new = ir.tags(DRAFT.read_text()) - ir.tags(V1.read_text())
        covered, fixtures = set(), set()
        for row in rows(section(9)):
            covered.update(ticks(row[0]))
            fixtures.update(t for t in ticks(row[-1]) if t.endswith(".ops-v2"))
        self.assertEqual(new - covered, set())
        for name in fixtures:
            with self.subTest(fixture=name):
                self.assertTrue((V2 / name).is_file())


class CompatibilityTableTest(unittest.TestCase):
    def test_every_v1_fixture_has_a_row_matching_its_commands(self) -> None:
        table = {ticks(r[0])[0]: r for r in rows(section(7)) if r[0].startswith("`") and r[0].endswith(".ops`")}
        self.assertEqual(sorted(table), sorted(p.name for p in SYSTEMS.glob("*.ops")))
        for name, row in table.items():
            with self.subTest(fixture=name):
                (system,) = parse((SYSTEMS / name).read_text(encoding="utf-8"), name)
                commands, publishing = [], []
                for command in system.value[3].value:
                    command_name = command.value[1].value
                    commands.append(command_name)
                    if "publish" in symbols_of(command):
                        publishing.append(command_name)
                self.assertEqual(ticks(row[1]), commands)
                self.assertEqual(ticks(row[2]), publishing)
                self.assertEqual(row[3], "identical")
                self.assertEqual("A1" in row[4], bool(publishing))
                self.assertIn("A2", row[4])


def symbols_of(node) -> set[str]:
    if isinstance(node.value, Symbol):
        return {node.value.text}
    if isinstance(node.value, tuple):
        return set().union(*(symbols_of(c) for c in node.value)) if node.value else set()
    return set()


class ProbeMappingTest(unittest.TestCase):
    def test_every_probe_ir_gap_test_is_mapped(self) -> None:
        tree = ast.parse(PROBE.read_text(encoding="utf-8"))
        gaps = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and any(ast.unparse(d) == "unittest.expectedFailure" for d in node.decorator_list)
        }
        self.assertTrue(gaps)
        mapped = {ticks(r[0])[0] for r in rows(section(8)) if r[0].startswith("`test_")}
        self.assertEqual(mapped, gaps)
        delta = {t for r in rows(section(3)) for t in ticks(r[2]) if t.startswith("test_")}
        self.assertEqual(delta, gaps)


if __name__ == "__main__":
    unittest.main()
