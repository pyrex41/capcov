"""Synthetic inventories only; progress reports do not qualify a product."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from capcov.behaviors.progress import build_progress


PIN = "a" * 40
OTHER_PIN = "b" * 40


def unit(uid, **changes):
    return {"id": uid, "label": uid, "area": "workspace", "disposition": "retain",
            "scope_basis": "reviewed retained product capability", **changes}


def cell(uid="create", candidate="one", **changes):
    return {"unit": uid, "candidate": candidate, "source_pin": PIN,
            "stage": "implemented", "owner": "product-owner", "blocker": None,
            "evidence": ["receipts/create.json"], "depth": {"auth": "pass", "integrity": "pass"}, **changes}


def plan():
    return {"format": "capcov-progress-plan-v1", "unit_namespace": "synthetic/product-capabilities",
            "candidates": [{"id": cid, "source_pin": PIN} for cid in ("one", "two", "three")],
            "units": [unit("create"), unit("delete")], "cells": [],
            "depth_dimensions": ["auth", "integrity"]}


class ProgressTests(unittest.TestCase):
    def test_omissions_materialize_all_candidates_and_dimensions(self):
        report = build_progress(plan())
        self.assertEqual(len(report["cells"]), 6)
        self.assertTrue(all(c["omitted"] and c["stage"] == "unknown" for c in report["cells"]))
        self.assertTrue(all(c["depth"] == {"auth": "unknown", "integrity": "unknown"} for c in report["cells"]))
        self.assertEqual(set(report["summary"]), {"one", "two", "three"})
        self.assertEqual(report["summary"]["one"]["reported_breadth_percent"], 0)
        self.assertEqual(report["targets"], {"breadth": 100, "depth": 80})
        self.assertFalse(report["targets_met"])

    def test_duplicate_ids_cells_and_dimensions_are_rejected(self):
        for name in ("units", "candidates", "depth_dimensions"):
            with self.subTest(name=name):
                p = plan()
                p[name].append(copy.deepcopy(p[name][0]))
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    build_progress(p)
        p = plan()
        p["cells"] = [cell(), cell()]
        with self.assertRaisesRegex(ValueError, "duplicate cell"):
            build_progress(p)

    def test_unknown_ids_status_and_dimensions_are_rejected(self):
        for changes in ({"unit": "absent"}, {"candidate": "absent"}, {"stage": "tested"},
                        {"depth": {"unknown-dimension": "pass"}}, {"depth": {"auth": "maybe"}}):
            with self.subTest(changes=changes):
                p = plan()
                p["cells"] = [cell(**changes)]
                with self.assertRaisesRegex(ValueError, "unknown"):
                    build_progress(p)

    def test_pins_must_be_full_shas(self):
        for value in (None, "abc123", "x" * 40):
            with self.subTest(value=value):
                p = plan()
                p["candidates"][0]["source_pin"] = value
                with self.assertRaisesRegex(ValueError, "40-character"):
                    build_progress(p)
                p = plan()
                p["cells"] = [cell(source_pin=value)]
                with self.assertRaisesRegex(ValueError, "40-character"):
                    build_progress(p)

    def test_stale_pin_loses_stage_and_depth_credit_without_losing_claims(self):
        p = plan()
        p["cells"] = [cell()]
        before = build_progress(p)
        p["candidates"][0]["source_pin"] = OTHER_PIN
        report = build_progress(p, before)
        current = report["cells"][0]
        self.assertTrue(current["stale"])
        self.assertEqual(current["reported_stage"], "implemented")
        self.assertEqual(current["stage"], "unknown")
        self.assertIn("source_pin", current["unknown_reason"])
        self.assertEqual(set(current["depth"].values()), {"unknown"})
        self.assertEqual(report["summary"]["one"]["reported_breadth_percent"], 0)
        self.assertEqual(len(report["delta"]["pin_changes"]), 1)
        self.assertEqual(len(report["delta"]["regressions"]), 1)
        self.assertTrue(report["review_required"])
        self.assertTrue(any(i["code"] == "source-pin-changed" for i in report["delta"]["review_issues"]))

    def test_implemented_requires_evidence_not_test_count(self):
        p = plan()
        p["cells"] = [cell(evidence=[])]
        with self.assertRaisesRegex(ValueError, "requires evidence"):
            build_progress(p)
        p["cells"] = [cell(stage="partial", passed_checks=10000)]
        report = build_progress(p)
        self.assertEqual(report["summary"]["one"]["implemented_units"], 0)
        self.assertEqual(report["evidence_status"], "reported-not-verified")
        self.assertEqual(report["cells"][0]["stage"], "partial")

    def test_depth_denominator_includes_missing_units(self):
        p = plan()
        p["cells"] = [cell(), cell("delete", stage="missing", evidence=[], depth={})]
        report = build_progress(p)
        summary = report["summary"]["one"]
        self.assertEqual(summary["eligible_units"], 2)
        self.assertEqual(summary["depth_denominator"], 4)
        self.assertEqual(summary["reported_breadth_percent"], 50)
        self.assertEqual(summary["reported_depth_percent"], 50)

    def test_replacement_aliases_do_not_multiply_capability_denominator(self):
        p = plan()
        p["units"] += [unit(f"old-route-{i}", disposition="replace", replacement_id="create") for i in range(33)]
        p["cells"] = [cell()]
        report = build_progress(p)
        summary = report["summary"]["one"]
        self.assertEqual(summary["eligible_units"], 2)
        self.assertEqual(summary["replacement_aliases"], 33)
        self.assertEqual(summary["reported_breadth_percent"], 50)
        self.assertEqual(len(report["cells"]), 35 * 3)
        self.assertFalse(any(t["unit"].startswith("old-route") for t in report["work_queue"]))

    def test_alias_evidence_cannot_cover_target(self):
        p = plan()
        p["units"].append(unit("legacy", disposition="replace", replacement_id="create"))
        p["cells"] = [cell("legacy")]
        self.assertEqual(build_progress(p)["summary"]["one"]["implemented_units"], 0)

    def test_replacement_targets_must_be_direct_retained_units(self):
        for target in ("absent", "legacy", "excluded", "other-alias"):
            with self.subTest(target=target):
                p = plan()
                p["units"] += [unit("legacy", disposition="replace", replacement_id=target),
                               unit("excluded", disposition="exclude"),
                               unit("other-alias", disposition="replace", replacement_id="create")]
                with self.assertRaisesRegex(ValueError, "retained"):
                    build_progress(p)
        p = plan()
        p["units"] += [unit("a", disposition="replace", replacement_id="b"),
                       unit("b", disposition="replace", replacement_id="a")]
        with self.assertRaisesRegex(ValueError, "cycles"):
            build_progress(p)

    def test_scope_basis_and_namespace_are_required(self):
        for disposition in ("retain", "replace", "exclude"):
            p = plan()
            p["units"][0].update(disposition=disposition, scope_basis=" ")
            with self.assertRaisesRegex(ValueError, "scope_basis"):
                build_progress(p)
        p = plan()
        del p["unit_namespace"]
        with self.assertRaisesRegex(ValueError, "unit_namespace"):
            build_progress(p)

    def test_unresolved_scope_prevents_completion_even_if_all_retained_are_implemented(self):
        p = plan()
        p["units"].append(unit("decide", disposition="unresolved", scope_basis=""))
        p["cells"] = [cell(uid, cid) for uid in ("create", "delete") for cid in ("one", "two", "three")]
        report = build_progress(p)
        self.assertFalse(report["breadth_complete"])
        self.assertFalse(report["targets_met"])
        self.assertLess(report["summary"]["one"]["inventory_breadth_floor_percent"], 100)
        self.assertFalse(any(t["kind"] == "depth" for t in report["work_queue"]))
        self.assertEqual(report["next_work"]["kind"], "scope")

    def test_excluded_units_stay_visible_with_basis(self):
        p = plan()
        p["units"].append(unit("removed", disposition="exclude", scope_basis="approved product decision"))
        report = build_progress(p)
        self.assertEqual(len(report["cells"]), 9)
        self.assertEqual(report["summary"]["two"]["excluded_units"], 1)
        self.assertEqual(report["units"][-1]["scope_basis"], "approved product decision")

    def test_denominator_shrink_is_review_not_positive_progress(self):
        p = plan()
        p["cells"] = [cell()]
        previous = build_progress(p)
        p["units"].pop()
        report = build_progress(p, previous)
        self.assertTrue(report["review_required"])
        self.assertIn({"code": "inventory-unit-removed", "unit": "delete"}, report["delta"]["review_issues"])
        self.assertEqual(report["delta"]["denominators"]["one"], {"before": 2, "after": 1})
        self.assertEqual(report["delta"]["cell_movements"], [])
        self.assertFalse(report["targets_met"])

    def test_exclusion_change_is_review_required(self):
        p = plan()
        previous = build_progress(p)
        p["units"][1].update(disposition="exclude", scope_basis="proposal, not progress")
        report = build_progress(p, previous)
        self.assertTrue(report["review_required"])
        self.assertTrue(any(c["field"] == "disposition" for c in report["delta"]["scope_changes"]))
        self.assertEqual(report["delta"]["cell_movements"], [])

    def test_new_exclusion_is_also_reviewed(self):
        p = plan()
        previous = build_progress(p)
        p["units"].append(unit("legacy", disposition="exclude", scope_basis="review this exclusion"))
        report = build_progress(p, previous)
        self.assertTrue(report["review_required"])
        self.assertIn({"code": "excluded-unit-added", "unit": "legacy", "scope_basis": "review this exclusion"},
                      report["delta"]["review_issues"])

    def test_regression_and_positive_movement_are_not_netted(self):
        p = plan()
        p["cells"] = [cell(), cell("delete", stage="missing", depth={})]
        previous = build_progress(p)
        p["cells"] = [cell(stage="partial", depth={"auth": "fail"}), cell("delete")]
        report = build_progress(p, previous)
        self.assertEqual(len(report["delta"]["cell_movements"]), 2)
        self.assertEqual(len(report["delta"]["regressions"]), 1)
        self.assertEqual(report["delta"]["regressions"][0]["unit"], "create")

    def test_depth_only_regression_is_visible(self):
        p = plan()
        p["cells"] = [cell()]
        previous = build_progress(p)
        p["cells"][0]["depth"]["auth"] = "fail"
        self.assertEqual(len(build_progress(p, previous)["delta"]["regressions"]), 1)

    def test_omitting_previous_implemented_cell_is_regression(self):
        p = plan()
        p["cells"] = [cell()]
        previous = build_progress(p)
        p["cells"] = []
        report = build_progress(p, previous)
        self.assertEqual(report["delta"]["regressions"][0]["changes"]["stage"]["after"], "unknown")

    def test_dimension_scope_namespace_and_candidate_loss_are_reviewed(self):
        for edit, expected in ((lambda p: p["depth_dimensions"].pop(), "policy-changed"),
                               (lambda p: p.update(unit_namespace="different/granularity"), "unit-namespace-changed"),
                               (lambda p: p["candidates"].pop(), "candidate-removed")):
            p = plan()
            previous = build_progress(p)
            edit(p)
            report = build_progress(p, previous)
            self.assertTrue(any(i["code"] == expected for i in report["delta"]["review_issues"]))

    def test_work_interleaves_candidates_and_breadth_precedes_polish(self):
        p = plan()
        p["cells"] = [cell(stage="partial", depth={})]
        report = build_progress(p)
        self.assertEqual([t["candidate"] for t in report["work_queue"][:3]], ["one", "two", "three"])
        self.assertTrue(all(t["kind"] == "breadth" for t in report["work_queue"]))
        self.assertEqual(report["next_work"]["unit"], "delete")

    def test_lagging_candidate_cannot_be_masked_by_other_ports(self):
        p = plan()
        p["cells"] = [cell(uid, cid) for uid in ("create", "delete") for cid in ("one", "two")]
        report = build_progress(p)
        self.assertEqual(report["summary"]["one"]["reported_breadth_percent"], 100)
        self.assertEqual(report["summary"]["three"]["reported_breadth_percent"], 0)
        self.assertFalse(report["targets_met"])
        self.assertEqual(report["next_work"]["candidate"], "three")
        self.assertEqual(report["by_area"]["three"]["workspace"]["eligible_units"], 2)

    def test_depth_unlocked_only_after_all_candidate_breadth(self):
        p = plan()
        p["cells"] = [cell(uid, cid, depth={}) for uid in ("create", "delete") for cid in ("one", "two", "three")]
        report = build_progress(p)
        self.assertTrue(report["breadth_complete"])
        self.assertTrue(all(t["kind"] == "depth" for t in report["work_queue"]))
        self.assertEqual([t["candidate"] for t in report["work_queue"][:3]], ["one", "two", "three"])
        self.assertFalse(report["targets_met"])

    def test_explicit_security_or_critical_unblock_is_exception_not_blanket_polish(self):
        p = plan()
        p["cells"] = [cell(depth={}, depth_unblock_reason={"kind": "security", "reason": "tenant isolation blocks safe delivery"})]
        report = build_progress(p)
        self.assertEqual(report["next_work"]["kind"], "depth")
        self.assertEqual(report["next_work"]["reason"]["kind"], "security")
        self.assertEqual(sum(t["kind"] == "depth" for t in report["work_queue"]), 1)
        p["cells"][0]["depth_unblock_reason"] = {"kind": "polish", "reason": "nice to have"}
        with self.assertRaisesRegex(ValueError, "security/critical"):
            build_progress(p)

    def test_empty_inventory_never_claims_success(self):
        p = plan()
        p["units"] = []
        report = build_progress(p)
        self.assertFalse(report["targets_met"])
        self.assertFalse(report["breadth_complete"])
        self.assertIsNone(report["summary"]["one"]["reported_breadth_percent"])

    def test_determinism_no_mutation_and_previous_summary_is_not_trusted(self):
        p = plan()
        original = copy.deepcopy(p)
        report = build_progress(p)
        report["summary"]["one"]["reported_breadth_percent"] = 100
        current = build_progress(p, report)
        self.assertEqual(current["delta"]["cell_movements"], [])
        self.assertEqual(p, original)
        self.assertEqual(build_progress(p), build_progress(p))

    def test_cli_isolated_stdlib_subprocess_persistence_and_errors(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source, output = directory / "plan.json", directory / "report.json"
            source.write_text(json.dumps(plan()))
            # -S deliberately excludes site-packages and installed pytest plugins.
            command = [sys.executable, "-S", "-m", "capcov.behaviors", "progress",
                       "--plan", str(source), "--out", str(output)]
            result = subprocess.run(command, cwd=root / "src", capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            first = json.loads(output.read_text())
            self.assertEqual(first["format"], "capcov-progress-v1")
            result = subprocess.run(command + ["--previous", str(output)], cwd=root / "src", capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text())["delta"]["cell_movements"], [])
            source.write_text("{}")
            result = subprocess.run(command, cwd=root / "src", capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("capcov-progress-plan-v1", result.stderr)


if __name__ == "__main__":
    unittest.main()
