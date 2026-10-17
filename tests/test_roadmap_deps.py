"""scripts/roadmap-deps.py: the roadmap's dependency tables are generated from docs/roadmap-deps.json."""
from __future__ import annotations

import copy
import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "roadmap-deps.py"
DEPS = ROOT / "docs" / "roadmap-deps.json"
ROADMAP = ROOT / "docs" / "production-roadmap.md"

_spec = importlib.util.spec_from_file_location("roadmap_deps", SCRIPT)
roadmap_deps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(roadmap_deps)


def _entry(data: dict, rid: str) -> dict:
    return next(entry for entry in data["changes"] if entry["id"] == rid)


class CommittedRoadmapTest(unittest.TestCase):
    def test_the_committed_data_is_consistent(self) -> None:
        self.assertEqual(roadmap_deps.validate(roadmap_deps.load(DEPS)), [])

    def test_the_committed_roadmap_matches_the_data(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            status = roadmap_deps.main(["--check", "--deps", str(DEPS), "--roadmap", str(ROADMAP)])
        self.assertEqual(status, 0, stderr.getvalue())

    def test_r10_needs_no_real_service_and_r10q_needs_the_proof_and_replay_changes(self) -> None:
        data = roadmap_deps.load(DEPS)
        r10, r10q = _entry(data, "R10"), _entry(data, "R10q")
        self.assertEqual(set(r10["executor_classes"]), {"model", "fake"})
        self.assertNotIn("R09", roadmap_deps._closure({e["id"]: e for e in data["changes"]}, r10["depends"]))
        self.assertLessEqual({"R12", "R15", "R16"}, set(r10q["depends"]))


class ValidateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data = copy.deepcopy(roadmap_deps.load(DEPS))

    def _errors(self) -> str:
        return "\n".join(roadmap_deps.validate(self.data))

    def test_an_unknown_dependency_is_reported(self) -> None:
        _entry(self.data, "R04")["depends"].append("R99")
        self.assertIn("unknown id R99", self._errors())

    def test_a_dependency_on_a_later_change_is_reported(self) -> None:
        _entry(self.data, "R02")["depends"].append("R03")
        self.assertIn("R02: depends names R03, which is listed later", self._errors())

    def test_a_cycle_is_reported(self) -> None:
        _entry(self.data, "R02")["depends"].append("R03")
        self.assertIn("cycle:", self._errors())

    def test_a_capability_nobody_delivers_is_reported(self) -> None:
        _entry(self.data, "R10")["requires_capabilities"].append({"capability": "cap.nowhere"})
        self.assertIn("R10: requires cap.nowhere, which no change delivers", self._errors())

    def test_a_requirement_outside_the_dependencies_is_reported(self) -> None:
        _entry(self.data, "R10")["requires_capabilities"].append({"capability": "cap.sql-journal"})
        self.assertIn("R10: requires cap.sql-journal at start but R09 is not in its dependencies", self._errors())

    def test_a_dependency_that_supplies_nothing_is_reported(self) -> None:
        _entry(self.data, "R13")["depends"].append("R08")
        self.assertIn("R13: depends on R08 but requires none of the capabilities it supplies", self._errors())

    def test_an_undeclared_condition_is_reported(self) -> None:
        _entry(self.data, "R15")["requires_capabilities"][-1]["when"] = "sometimes"
        self.assertIn("unknown condition 'sometimes'", self._errors())


class ConditionTest(unittest.TestCase):
    """The criterion that decides whether an inventory entry's qualification needs R14 or R17."""

    def setUp(self) -> None:
        self.data = roadmap_deps.load(DEPS)

    def test_one_plain_store_needs_no_observation_cut(self) -> None:
        entry = {"observation_stores": [{"name": "mysql"}]}
        self.assertFalse(roadmap_deps.holds(self.data, "multi-store-observation", entry))

    def test_two_stores_or_an_async_store_need_an_observation_cut(self) -> None:
        for entry in ({"observation_stores": [{"name": "mysql"}, {"name": "redis"}]},
                      {"observation_stores": [{"name": "redis", "async_or_ttl": True}]}):
            with self.subTest(entry=entry):
                self.assertTrue(roadmap_deps.holds(self.data, "multi-store-observation", entry))

    def test_concurrency_or_retry_after_info_needs_concurrent_histories(self) -> None:
        self.assertFalse(roadmap_deps.holds(self.data, "concurrent-or-retry", {"max_concurrent_commands": 1}))
        self.assertTrue(roadmap_deps.holds(self.data, "concurrent-or-retry", {"max_concurrent_commands": 2}))
        self.assertTrue(roadmap_deps.holds(self.data, "concurrent-or-retry", {"info_step_then_retry": True}))


class RegenerateTest(unittest.TestCase):
    def test_a_hand_edit_inside_a_generated_region_fails_the_check(self) -> None:
        text = ROADMAP.read_text(encoding="utf-8").replace("| R10 ← R03, R07;", "| R10 ← R03, R07, R09;", 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roadmap.md"
            path.write_text(text, encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(roadmap_deps.main(["--check", "--deps", str(DEPS), "--roadmap", str(path)]), 1)
                self.assertEqual(roadmap_deps.main(["--deps", str(DEPS), "--roadmap", str(path)]), 0)
            self.assertEqual(path.read_text(encoding="utf-8"), ROADMAP.read_text(encoding="utf-8"))

    def test_regeneration_is_idempotent(self) -> None:
        data = roadmap_deps.load(DEPS)
        text = ROADMAP.read_text(encoding="utf-8")
        self.assertEqual(roadmap_deps.regenerate(data, roadmap_deps.regenerate(data, text)), text)


if __name__ == "__main__":
    unittest.main()
