"""Recovery uses the existing claim kernels, Behavior graph and Shen search."""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from capcov.claims.environment import check, from_capabilities
from capcov.claims.ir import canonical_dict, bundle_from_json
from capcov.claims.evaluator import evaluate
from capcov.behaviors.environment import import_environment, extend_plan, search_environment
from capcov.behaviors.registry import inspect, validate
from capcov.behaviors.qualification import execute_checks, qualify
from capcov.behaviors.recovery import tasks, export_graph
from tests import test_environment_recovery as recovery_fixture
from tests.test_behaviors import fixture


class EnvironmentIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.producer = recovery_fixture.PythonEnvironmentTests()
        self.producer.setUp()
        self.addCleanup(self.producer.doCleanups)
        self.root = self.producer.root
        self.caps = self.producer.discover({"publisher": "live"})
        self.registry, self.plan = fixture(self.root)
        # fixture adds no Python files before source re-snapshotting.
        self.caps = self.producer.discover({"publisher": "live"})
        self.mapping = {"format": "capcov-environment-behaviors-v1", "source_root": ".",
            "nodes": {"app:" + n: "publish" for n in ("route", "publish", "observer", "worker", "dry")},
            "searches": {}}
        self.save()

    def save(self):
        (self.root / "caps.json").write_text(json.dumps(self.caps))
        (self.root / "mapping.json").write_text(json.dumps(self.mapping))

    def enroll(self):
        self.save()
        return import_environment(self.registry, self.root, "caps.json", "mapping.json")

    def test_claim_bundle_roundtrip_and_existing_evaluator(self):
        bundle = from_capabilities(self.caps)
        self.assertEqual(bundle, bundle_from_json(canonical_dict(bundle)))
        result = check(self.caps)
        self.assertEqual(result["operations"], 1)
        self.assertTrue(result["unresolved"])
        self.assertFalse(any(r.modality.value == "completeness" for r in bundle.relations))
        self.assertTrue(all(e.depends_on for e in bundle.evidence))

    def test_forged_rule_pack_and_projection_rejected(self):
        bad = copy.deepcopy(self.caps)
        bad["environment_claims"]["rules"] = []
        with self.assertRaises(ValueError): check(bad)
        bad = copy.deepcopy(self.caps)
        bad["capabilities"] = []
        with self.assertRaisesRegex(ValueError, "projection"): check(bad)

    def test_configurations_have_disjoint_contexts(self):
        before = from_capabilities(self.caps)
        after = from_capabilities(self.producer.discover({"publisher": "dry"}))
        self.assertNotEqual(dict(before.metadata)["environment_analysis"],
                            dict(after.metadata)["environment_analysis"])
        self.assertFalse(evaluate(after).relation_rows("env_capability_op"))

    def test_unknown_candidates_are_not_completeness_evidence(self):
        result = check(self.producer.discover({}))
        self.assertTrue(any("unknown environment" in row[-1] for row in result["unresolved"]))

    def test_import_idempotence_and_existing_stale_graph(self):
        registry = self.enroll()
        self.assertEqual(registry, import_environment(registry, self.root, "caps.json", "mapping.json"))
        self.assertTrue(registry["claims"])
        self.assertFalse(inspect(registry, self.root, ["publish"])["stale"])
        (self.root / "deployment.json").write_text('{"publisher":"dry"}')
        self.assertIn("publish", inspect(registry, self.root, ["publish"])["stale"])
        with tempfile.TemporaryDirectory() as d:
            export_graph(registry, self.root, ["publish"], d)
            self.assertTrue(Path(d, "changed.facts").read_text())
            self.assertTrue(Path(d, "depends.facts").read_text())
        with self.assertRaisesRegex(ValueError, "current tree"):
            self.enroll()

    def test_added_source_file_invalidates_existing_qualification(self):
        registry = self.enroll()
        (self.root / "new_handler.py").write_text("def hidden(): pass\n")
        self.assertIn("publish", inspect(registry, self.root, ["publish"])["stale"])

    def test_unclassified_touch_still_gets_execution_obligation(self):
        (self.root / "app.py").write_text(self.producer.SOURCE.replace("session.add(Report())", "Report"))
        self.caps = self.producer.discover({"publisher": "live"})
        registry = self.enroll()
        self.assertTrue(any("operation unknown" in c["statement"] for c in registry["claims"]))

    def test_cli_exports_checks_imports_and_plans(self):
        from capcov.behaviors.cli import main
        registry_file = self.root / "registry.json"
        registry_file.write_text(json.dumps(self.registry))
        plan_file = self.root / "plan.json"
        plan_file.write_text(json.dumps(self.plan))
        output = self.root / "result.json"
        common = ["--root", str(self.root), "--input", "caps.json", "--mapping", "mapping.json",
                  "--engine", "python", "--out", str(output)]
        self.assertEqual(main(["environment-claims", *common]), 0)
        self.assertEqual(bundle_from_json(json.loads(output.read_text())), from_capabilities(self.caps))
        self.assertEqual(main(["environment-check", *common]), 0)
        self.assertEqual(main(["import-environment", "--registry", str(registry_file), *common]), 0)
        registry_file.write_text(output.read_text())
        self.assertEqual(main(["environment-plan", "--registry", str(registry_file),
                               "--checks", str(plan_file), *common]), 0)
        self.assertTrue(any("environment-check" in c["argv"] for c in json.loads(output.read_text())["checks"]))

    def test_missing_owner_refused(self):
        del self.mapping["nodes"]["app:worker"]
        with self.assertRaisesRegex(ValueError, "every reachable node"):
            self.enroll()

    def test_cross_behavior_edges_and_cycle_refusal(self):
        worker = copy.deepcopy(self.registry["behaviors"][0])
        worker.update(id="worker-behavior", depends_on=[], obligations=[{
            "id": "worker-proof", "category": "safety", "method": "proof", "description": "worker safety"}])
        self.registry["behaviors"].append(worker)
        self.mapping["nodes"]["app:worker"] = "worker-behavior"
        result = self.enroll()
        self.assertIn("worker-behavior", result["behaviors"][0]["depends_on"])
        self.registry["behaviors"][1]["depends_on"] = ["publish"]
        with self.assertRaisesRegex(ValueError, "cyclic"):
            self.enroll()

    def test_generated_checks_run_and_do_not_close_other_obligations(self):
        registry = self.enroll()
        plan = extend_plan(self.plan, registry, self.root, "caps.json", "mapping.json",
                           python=sys.executable, engine="python")
        receipts = execute_checks(registry, plan, self.root, ["publish"], self.root / "receipts")
        report = qualify(registry, plan, self.root, ["publish"], receipts, self.root / "receipts")
        projection = [o for o in report["obligations"] if o["category"] == "environment-projection"]
        self.assertEqual(projection[0]["status"], "supported")
        self.assertFalse(report["complete"])
        pending = tasks(registry, report)["tasks"]
        self.assertTrue(any(t["role"] == "Implementer" for t in pending))
        self.assertTrue(any(t["role"] == "Curator" for t in pending))
        (self.root / "deployment.json").write_text('{"publisher":"dry"}')
        stale = qualify(registry, plan, self.root, ["publish"], receipts, self.root / "receipts")
        self.assertTrue(stale["invalid_evidence"])

    def test_existing_shen_search_receives_reviewed_inputs(self):
        (self.root / "model.ops").write_text("model placeholder for dispatcher unit test")
        payload = {"initial": {}, "calls": [], "goal": {"violation": True}, "depth": 2}
        (self.root / "query.json").write_text(json.dumps(payload))
        self.mapping["searches"] = {"POST /publish": {"spec": "model.ops", "input": "query.json"}}
        registry = self.enroll()
        with patch("capcov.operations.search.search", return_value={"status": "exhausted", "scenario": None}) as native:
            result = search_environment(self.root, "caps.json", "mapping.json", "POST /publish")
        native.assert_called_once_with("model placeholder for dispatcher unit test", **payload, timeout=60)
        self.assertEqual(result["search"]["status"], "exhausted")
        self.assertTrue(any(o["method"] == "model-check" for o in registry["behaviors"][0]["obligations"]))

    def test_unavailable_souffle_is_failure_not_python_fallback(self):
        with patch("capcov.claims.differential.run_souffle") as runner:
            from capcov.claims.differential import KernelReport
            runner.return_value = KernelReport("souffle", (), (), "unavailable", "test unavailable")
            with self.assertRaisesRegex(ValueError, "unavailable"):
                check(self.caps, engine="both")


@unittest.skipUnless(shutil.which("souffle"), "requires pinned Souffle")
class EnvironmentSouffleTests(unittest.TestCase):
    def test_real_interpreted_and_compiled_kernels(self):
        from capcov.claims.differential import compare_three
        fixture = recovery_fixture.PythonEnvironmentTests(); fixture.setUp()
        try:
            for environment in ({"publisher": "live"}, {"publisher": "dry"}, {}):
                bundle = from_capabilities(fixture.discover(environment))
                with tempfile.TemporaryDirectory() as d:
                    compare_three(bundle, cache_dir=d, replay_root=Path(d) / "replays")
        finally:
            fixture.doCleanups()
