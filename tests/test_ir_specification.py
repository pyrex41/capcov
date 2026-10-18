"""docs/ir-specification.md stays tied to the code, the overlay and the fixtures.

The base-family classes run the table generator and cross-reference the
hand-written tables against the fixtures and the probe; a cross-reference is
not a semantic check. DraftTypecheckTest (shen family) is the only class that
runs Shen: it types the v1 fixtures, the overlay's fixtures and the rejected
fixtures under the real typechecker. No R02 semantics is implemented, so none
is tested here.
"""
from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from importlib import resources
from pathlib import Path

from capcov.claims.spec.parser import Symbol, parse
from capcov.operations import OperationError, _string
from capcov.operations.process import run as run_process
from capcov.operations.system import _term

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ir-constructors.py"
DOC = ROOT / "docs" / "ir-specification.md"
V1 = ROOT / "src" / "capcov" / "operations" / "shen" / "system-types.shen"
SYSTEMS = ROOT / "tests" / "claim_semantics" / "fixtures" / "systems"
V2 = SYSTEMS / "v2-draft"
OVERLAY = V2 / "system-types.shen"
POSITIVE = ("transfer-outbox.ops-v2", "histories.ops-v2")
UNTAGGED = V2 / "rejected-untagged-effect.ops-v2"
UNTAGGED_ENTRY = '[entry "2" [emit "delivery-attempt" "hello"]]'
TAGGED_ENTRY = '[entry "2" [effect "j" "i2/publish" [emit "delivery-attempt" "hello"]]]'
PROBE = ROOT / "tests" / "claim_semantics" / "test_migration_probe.py"
NATIVE = bool(shutil.which("bifrost") and os.environ.get("BIFROST_SHEN_GO"))
if os.environ.get("CAPCOV_SHEN_REQUIRED") and not NATIVE:
    raise RuntimeError("the draft typecheck requires native Shen")

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


def symbols(node) -> set[str]:
    if isinstance(node.value, Symbol):
        return {node.value.text}
    if isinstance(node.value, tuple):
        return set().union(set(), *(symbols(c) for c in node.value))
    return set()


def file_symbols(path: Path) -> set[str]:
    return set().union(set(), *(symbols(t) for t in parse(path.read_text(encoding="utf-8"), str(path))))


def rejected_by(path: Path) -> str:
    first = path.read_text(encoding="utf-8").splitlines()[0]
    match = re.fullmatch(r"; rejected-by: ([TR]-[A-Za-z0-9-]+)", first)
    if not match:
        raise AssertionError(f"{path.name}: first line must be '; rejected-by: <rule>', not {first!r}")
    return match.group(1)


class ConstructorTableTest(unittest.TestCase):
    def test_generated_regions_are_current(self) -> None:
        done = subprocess.run(
            [sys.executable, str(SCRIPT), "--check"], cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_a_datatype_edit_makes_the_check_fail(self) -> None:
        for source, old, new in (
            (V1, "[row-key] : caps-expr;", "[row-id] : caps-expr;"),
            (OVERLAY, "[on-info Info]]", "[on-unknown Info]]"),
        ):
            with self.subTest(source=source.name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for path in (DOC, V1, OVERLAY, ROOT / ir.SYSTEM_PY):
                    target = root / path.relative_to(ROOT)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(path, target)
                shen = root / source.relative_to(ROOT)
                self.assertEqual(shen.read_text().count(old), 1)
                shen.write_text(shen.read_text().replace(old, new))
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(ir.main(["--check", "--root", str(root)]), 1)
                self.assertEqual(ir.main(["--root", str(root)]), 0)
                self.assertIn(new.split("]")[0].strip("["), (root / DOC.relative_to(ROOT)).read_text())
                self.assertEqual(ir.main(["--check", "--root", str(root)]), 0)

    def test_every_typing_rule_becomes_one_row(self) -> None:
        for path in (V1, OVERLAY):
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

    def test_the_overlay_is_outside_the_package(self) -> None:
        self.assertFalse(OVERLAY.is_relative_to(ROOT / "src"))
        for path in (ROOT / "src").rglob("*"):
            if path.is_file() and path.suffix in {".py", ".shen", ".dl", ".json"}:
                with self.subTest(path=path):
                    self.assertNotIn("v2-draft", path.read_text(encoding="utf-8", errors="replace"))
        def whole(rule):
            return rule["conclusion"], tuple(rule["premises"]), tuple(rule["conditions"])

        overlay_rules = {whole(r) for r in ir.rules(OVERLAY.read_text())}
        v1_rules = {whole(r) for r in ir.rules(V1.read_text())}
        self.assertEqual(overlay_rules & v1_rules, set(), "the overlay adds rules, it repeats none")


class DraftFixtureCrossReferenceTest(unittest.TestCase):
    """Cross-references between fixtures and the document's tables."""

    def test_the_fixture_directory_is_exactly_what_the_tables_list(self) -> None:
        listed = {ticks(r[0])[0] for r in rows(section(6)) if r[0].startswith("`rejected-")}
        for name in POSITIVE:
            self.assertIn(name, section(5))
        files = {p.name for p in V2.glob("*.ops-v2")}
        self.assertEqual(files, listed | set(POSITIVE))
        for name in sorted(files):
            with self.subTest(fixture=name):
                self.assertTrue(parse((V2 / name).read_text(encoding="utf-8"), name))

    def test_positive_fixtures_use_only_declared_constructors(self) -> None:
        declared = ir.tags(V1.read_text()) | ir.tags(OVERLAY.read_text())
        for name in POSITIVE:
            with self.subTest(fixture=name):
                self.assertEqual(file_symbols(V2 / name) - declared, set())

    def test_the_v1_front_end_refuses_the_draft_model(self) -> None:
        with self.assertRaisesRegex(OperationError, "unsupported system constructor"):
            _term((V2 / "transfer-outbox.ops-v2").read_text())

    def test_each_rejected_fixture_names_a_rule_of_the_rule_table(self) -> None:
        rules = {ticks(r[0])[0] for r in rows(section(4)) if r and re.fullmatch(r"`[TR]-[A-Za-z0-9-]+`", r[0])}
        listed = {ticks(r[0])[0]: ticks(r[1])[0] for r in rows(section(6)) if r[0].startswith("`rejected-")}
        for name, rule in sorted(listed.items()):
            with self.subTest(fixture=name):
                self.assertEqual(rejected_by(V2 / name), rule)
                self.assertIn(rule, rules)

    def test_every_new_tag_occurs_in_a_negative_fixture_of_its_row(self) -> None:
        new = ir.tags(OVERLAY.read_text()) - ir.tags(V1.read_text())
        covered = set()
        for row in rows(section(9)):
            tags = ticks(row[0])
            if not tags:
                continue
            fixtures = [t for t in ticks(row[-1]) if t.endswith(".ops-v2")]
            self.assertTrue(fixtures, f"row {tags} cites no rejected fixture")
            present = set().union(*(file_symbols(V2 / f) for f in fixtures))
            for tag in tags:
                with self.subTest(tag=tag):
                    self.assertIn(tag, present)
            covered.update(tags)
        self.assertEqual(new - covered, set())


class CompatibilityTableTextTest(unittest.TestCase):
    """Cross-checks the hand-written section 7 table only; G5 is the real gate."""

    def test_every_v1_fixture_has_a_row_matching_its_commands(self) -> None:
        table = {ticks(r[0])[0]: r for r in rows(section(7)) if r[0].startswith("`") and r[0].endswith(".ops`")}
        self.assertEqual(sorted(table), sorted(p.name for p in SYSTEMS.glob("*.ops")))
        for name, row in table.items():
            with self.subTest(fixture=name):
                (system,) = parse((SYSTEMS / name).read_text(encoding="utf-8"), name)
                commands = [c.value[1].value for c in system.value[3].value]
                publishing = [c.value[1].value for c in system.value[3].value if "publish" in symbols(c)]
                self.assertEqual(ticks(row[1]), commands)
                self.assertEqual(ticks(row[2]), publishing)
                self.assertEqual(row[3], "identical")
                self.assertEqual("atomic-publish-v1" in row[4], bool(publishing))
                self.assertIn("info-in-place-v1", row[4])


class ProbeMappingTest(unittest.TestCase):
    def test_every_probe_ir_gap_test_is_mapped(self) -> None:
        """Every IR-gap test is mapped; a flipped one is marked and no longer xfails."""
        tree = ast.parse(PROBE.read_text(encoding="utf-8"))
        functions = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        gaps = {
            name
            for name, node in functions.items()
            if any(ast.unparse(d) == "unittest.expectedFailure" for d in node.decorator_list)
        }
        self.assertTrue(gaps)
        table = {ticks(r[0])[0]: r[2] for r in rows(section(8)) if r[0].startswith("`test_")}
        flipped = {name for name, flips in table.items() if "(flipped)" in flips}
        self.assertEqual(set(table) - flipped, gaps)
        for name in flipped:
            with self.subTest(flipped=name):
                self.assertIn(name, functions)
                self.assertNotIn(name, gaps)
        delta = {t for r in rows(section(3)) for t in ticks(r[2]) if t.startswith("test_")}
        self.assertEqual(delta, set(table))


def shen_term(node) -> str:
    """A parsed fixture term as Shen source, strings via the engine's encoder."""
    value = node.value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Symbol):
        return value.text
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, tuple):
        return "[" + " ".join(shen_term(c) for c in value) + "]"
    raise AssertionError(f"unsupported fixture value {value!r}")


@unittest.skipUnless(NATIVE, "real pinned Shen runtime required")
class DraftTypecheckTest(unittest.TestCase):
    """Executor class "model": the overlay under the real Shen typechecker.

    Expected: every v1 .ops fixture still types as caps-system with the overlay
    loaded; the positive fixtures and every R-* rejected fixture type
    structurally (caps-system-shape or caps-history); every T-* rejected
    fixture does not.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cases = []
        for path in sorted(SYSTEMS.glob("*.ops")):
            (term,) = parse(path.read_text(encoding="utf-8"), path.name)
            cases.append((path.name, "caps-system", True, shen_term(term)))
        for path in sorted(V2.glob("*.ops-v2")):
            expected = not path.name.startswith("rejected-") or rejected_by(path).startswith("R-")
            for index, term in enumerate(parse(path.read_text(encoding="utf-8"), path.name)):
                head = term.value[0].value.text
                kind = {"system": "caps-system-shape", "history": "caps-history"}[head]
                cases.append((f"{path.name}#{index}", kind, expected, shen_term(term)))
        # Control for T-effect: tagging the one bare entry makes the history type,
        # so the untagged effect, and nothing else, is what rejects the fixture.
        source = UNTAGGED.read_text(encoding="utf-8")
        assert source.count(UNTAGGED_ENTRY) == 1
        (term,) = parse(source.replace(UNTAGGED_ENTRY, TAGGED_ENTRY), UNTAGGED.name)
        cases.append((f"{UNTAGGED.name}#tagged", "caps-history", True, shen_term(term)))
        root =resources.files("capcov.operations").joinpath("shen")
        with tempfile.TemporaryDirectory(prefix="capcov-draft-") as tmp:
            directory = Path(tmp)
            loads = []
            for name in ("kernel.shen", "system.shen", "system-types.shen"):
                (directory / name).write_bytes(root.joinpath(name).read_bytes())
                loads.append(directory / name)
            (directory / "overlay.shen").write_bytes(OVERLAY.read_bytes())
            loads.append(directory / "overlay.shen")
            driver = directory / "driver.shen"
            driver.write_text(
                "\n".join(f'(load "{p}")' for p in loads)
                + "\n(define capsdraft.types? M T -> (= T (shen.typecheck (capop.syntax M) T)))"
                + "\n(tc +)\n(capop.print-result ["
                + " ".join(f"(capsdraft.types? {term} {kind})" for _, kind, _, term in cases)
                + "])\n"
            )
            code, stdout, stderr = run_process(
                [shutil.which("bifrost"), "run", "--impl", "shen-go", "--raw", str(driver)],
                cwd=directory,
                timeout=600,
            )
        marker = b"CAPCOV-OPERATION-RESULT "
        lines = [line[len(marker):] for line in stdout.splitlines() if line.startswith(marker)]
        if code or len(lines) != 1:
            raise AssertionError("draft typecheck driver failed: " + (stderr or stdout)[-2500:].decode(errors="replace"))
        cls.results = json.loads(lines[0])
        cls.cases = cases

    def test_one_result_per_case(self) -> None:
        self.assertEqual(len(self.results), len(self.cases))

    def test_v1_fixtures_still_type_with_the_overlay_loaded(self) -> None:
        for (name, kind, _, _), typed in zip(self.cases, self.results):
            if kind == "caps-system":
                with self.subTest(fixture=name):
                    self.assertIs(typed, True)

    def test_an_untagged_effect_is_what_rejects_its_fixture(self) -> None:
        typed = {name: result for (name, _, _, _), result in zip(self.cases, self.results)}
        self.assertIs(typed[f"{UNTAGGED.name}#0"], False)
        self.assertIs(typed[f"{UNTAGGED.name}#tagged"], True)

    def test_draft_fixtures_type_as_specified(self) -> None:
        for (name, kind, expected, _), typed in zip(self.cases, self.results):
            if kind != "caps-system":
                with self.subTest(fixture=name, kind=kind):
                    self.assertIs(typed, expected)


if __name__ == "__main__":
    unittest.main()
