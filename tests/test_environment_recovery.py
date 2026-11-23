"""Adversarial tests for the source-bound environment recovery adapter pass."""

import copy
import hashlib
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from capcov.adapters.environment import recover


class EnvironmentRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        source = "# synthetic handler / observer / worker declarations\n"
        (self.root / "app.py").write_text(source)
        self.anchor = {"file": "app.py", "line": 1,
                       "sha256": hashlib.sha256(source.encode()).hexdigest()}
        self.doc = {"schema": "capcov.environment.v1", "producer": "synthetic-test-v1",
                    "environment": "deployment.json", "nodes": [], "bindings": [],
                    "calls": [], "effects": []}
        self.raw = {
            "_calls": {"route": set()}, "_direct": {"route": set()}, "_ops": {},
            "entities": [{"name": "issues"}, {"name": "reports"}],
            "surfaces": [{"id": "http:POST /publish", "handler": "route"}],
            "blind_spots": [{"blind": True, "reason": "dynamic call"}],
            "unresolved": [{"kind": "original-gap", "reason": "retained"}],
        }
        self.env = {"publisher": "live"}
        for node in ("publish", "observer", "worker", "alternate"):
            self.add("nodes", node, node=node)
        self.add("bindings", "binding", slot="publisher", target="publish",
                 when={"publisher": "live"})
        self.add("bindings", "alias", slot="service", from_slot="publisher")
        self.add("calls", "dispatch", caller="route", slot="service")
        self.add("calls", "hook", caller="publish", target="observer", kind="callback")
        self.add("calls", "queue", caller="observer", target="worker", kind="worker")
        self.add("effects", "write-issue", node="publish", entity="issues", operation="update")
        self.add("effects", "write-report", node="worker", entity="reports", operation="create")

    def add(self, group, ident, **fields):
        record = {"id": ident, "source": dict(self.anchor), **fields}
        self.doc[group].append(record)
        return record

    def save(self):
        (self.root / "recovery.json").write_text(json.dumps(self.doc))
        (self.root / "deployment.json").write_text(json.dumps(self.env))

    def run_recovery(self):
        self.save()
        return recover(self.raw, self.root, "recovery.json")

    def test_chain_effects_and_provenance(self):
        before = copy.deepcopy(self.raw)
        result = self.run_recovery()
        self.assertEqual(result["_calls"]["route"], {"publish"})
        self.assertEqual(result["_calls"]["observer"], {"worker"})
        self.assertEqual(result["_ops"]["worker"]["reports"], {"create"})
        proof = next(e for e in result["environment_recovery"][0]["edges"]
                     if e["caller"] == "route")
        self.assertEqual(proof["fact_ids"], ["alias", "binding", "dispatch"])
        self.assertEqual(self.raw, before)
        self.assertEqual(result["blind_spots"], before["blind_spots"])
        self.assertEqual(result["unresolved"][0], before["unresolved"][0])
        self.assertEqual(result["unresolved"][-1]["kind"], "environment-extraction-boundary")

    def test_known_configuration_excludes_other_target(self):
        self.add("bindings", "other", slot="publisher", target="alternate",
                 when={"publisher": "dry"})
        result = self.run_recovery()
        self.assertEqual(result["_calls"]["route"], {"publish"})
        digest = result["environment_recovery"][0]["analysis_sha256"]
        self.env["publisher"] = "dry"
        result = self.run_recovery()
        self.assertEqual(result["_calls"]["route"], {"alternate"})
        self.assertNotEqual(digest, result["environment_recovery"][0]["analysis_sha256"])

    def test_unknown_configuration_keeps_all_candidates_and_gap(self):
        self.env = {}
        self.add("bindings", "other", slot="publisher", target="alternate",
                 when={"publisher": "dry"})
        result = self.run_recovery()
        self.assertEqual(result["_calls"]["route"], {"publish", "alternate"})
        self.assertTrue(any("unknown environment" in r["reason"] for r in result["unresolved"]))

    def test_false_boolean_is_not_zero(self):
        self.env["publisher"] = False
        self.doc["bindings"][0]["when"] = {"publisher": 0}
        self.assertEqual(self.run_recovery()["_calls"]["route"], set())

    def test_alias_cycle_with_seed_terminates_and_records_support(self):
        self.add("bindings", "back", slot="publisher", from_slot="service")
        self.add("calls", "recursive", caller="worker", target="publish")
        result = self.run_recovery()
        self.assertEqual(result["_calls"]["route"], {"publish"})
        self.assertEqual(result["_calls"]["worker"], {"publish"})

    def test_empty_cycle_stays_unresolved(self):
        self.doc["bindings"] = []
        self.add("bindings", "a", slot="service", from_slot="other")
        self.add("bindings", "b", slot="other", from_slot="service")
        result = self.run_recovery()
        self.assertEqual(result["_calls"]["route"], set())
        self.assertTrue(any("no known target" in r["reason"] for r in result["unresolved"]))

    def test_missing_body_never_invents_edge(self):
        self.doc["bindings"][0]["target"] = "missing"
        result = self.run_recovery()
        self.assertEqual(result["_calls"]["route"], set())
        self.assertTrue(any("no declared body" in r["reason"] for r in result["unresolved"]))

    def test_conditional_effects(self):
        self.doc["effects"][1]["when"] = {"publisher": "dry"}
        self.assertNotIn("worker", self.run_recovery()["_ops"])
        self.env = {}
        self.assertIn("worker", self.run_recovery()["_ops"])

    def test_unknown_entities_are_not_added(self):
        self.doc["effects"][1]["entity"] = "invented"
        result = self.run_recovery()
        self.assertNotIn("worker", result["_ops"])
        self.assertTrue(any("absent from discovery" in r["reason"] for r in result["unresolved"]))

    def test_stale_source_refused(self):
        self.save()
        (self.root / "app.py").write_text("# changed\n")
        with self.assertRaisesRegex(ValueError, "stale"):
            recover(self.raw, self.root, "recovery.json")

    def test_duplicate_ids_and_unknown_fields_refused(self):
        self.doc["calls"][0]["id"] = "alias"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.run_recovery()
        self.doc["calls"][0]["id"] = "dispatch"
        self.doc["calls"][0]["complete"] = True
        with self.assertRaisesRegex(ValueError, "fields"):
            self.run_recovery()

    def test_input_paths_cannot_escape(self):
        self.doc["environment"] = "../deployment.json"
        with self.assertRaisesRegex(ValueError, "outside|missing"):
            self.run_recovery()

    def test_duplicate_json_keys_refused(self):
        self.save()
        (self.root / "deployment.json").write_text('{"x": 1, "x": 2}')
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            recover(self.raw, self.root, "recovery.json")

    def test_budgets_fail_without_partial_result(self):
        with patch("capcov.adapters.environment.MAX_PAIRS", 1):
            with self.assertRaisesRegex(ValueError, "budget"):
                self.run_recovery()
        self.assertEqual(self.raw["_calls"]["route"], set())

    def test_deterministic_result(self):
        self.assertEqual(self.run_recovery(), self.run_recovery())

    def discover(self, *, inputs=True, enabled=True):
        from capcov import cli
        self.save()
        config = {"environment_facts": "recovery.json"} if enabled else {}
        if inputs:
            config["environment_inputs"] = ["deployment.json"]
        raw = copy.deepcopy(self.raw)
        raw["residue"] = []
        raw["residue_summary"] = dict.fromkeys(
            ["resolved_by_import", "resolved_by_name", "ambiguous", "external",
             "chained", "builtin_shadowed"], 0)
        args = Namespace(target=str(self.root), source=".", adapter=None,
                         no_name_match=False, resolver="ast", out=str(self.root / "out.json"),
                         check=False, quiet=True)
        with patch.object(cli, "_resolve", return_value=(
            self.root, [("python-fastapi-sqlalchemy", config)]
        )), patch.object(cli, "_run_adapter", return_value=raw):
            self.assertEqual(cli.cmd_discover(args), 0)
        return json.loads((self.root / "out.json").read_text())

    def test_discover_reconcile_gate_keeps_boundary(self):
        from capcov.core.gate import gate
        from capcov.core.reconcile import reconcile
        capabilities = self.discover()
        by_entity = {c["entity"]: c for c in capabilities["capabilities"]}
        self.assertEqual(by_entity["reports"]["operations"], ["create"])
        self.assertEqual(by_entity["reports"]["evidence"]["chain"],
                         ["route", "publish", "observer", "worker"])
        observed = {"bindings": [dict(c, tests=["publish-test"])
                                 for c in capabilities["capabilities"]]}
        coverage = reconcile(capabilities, observed)
        self.assertEqual(coverage["summary"]["both"], 2)
        self.assertEqual(coverage["environment_recovery"], capabilities["environment_recovery"])
        self.assertTrue(any(f.rule == "unresolved-obligation" and
                            f.subject == "environment:recovery.json:extraction"
                            for f in gate(coverage, None)))

    def test_missing_configuration_glob_refuses_publication(self):
        with self.assertRaisesRegex(SystemExit, "outside the source patterns"):
            self.discover(inputs=False)
        self.assertFalse((self.root / "out.json").exists())

    def test_changed_config_invalidates_source_identity(self):
        from capcov.artifacts import same_artifact
        first = self.discover()
        self.env["publisher"] = "dry"
        second = self.discover()
        same, _ = same_artifact(first, second)
        self.assertFalse(same)
        self.assertEqual(second["capabilities"], [])

    def test_disabled_pass_preserves_existing_shape(self):
        capabilities = self.discover(enabled=False)
        self.assertNotIn("environment_recovery", capabilities)
        self.assertEqual(capabilities["capabilities"], [])

    def test_support_budget(self):
        with patch("capcov.adapters.environment.MAX_SUPPORT", 1):
            with self.assertRaisesRegex(ValueError, "support budget"):
                self.run_recovery()

    def test_real_adapter_and_cli_without_executing_target(self):
        from capcov import cli
        source = '''from fastapi import FastAPI
app = FastAPI()
class Issue:
    __tablename__ = "issues"
class Report:
    __tablename__ = "reports"
def publish(item):
    Issue
    callbacks["updated"](item)
def observer(item):
    queue.enqueue("report", item)
def worker(item):
    Report
def alternate(item):
    return None
HANDLERS = {"live": publish, "dry": alternate}
@app.post("/publish")
def route(item):
    return HANDLERS[settings["publisher"]](item)
raise RuntimeError("source must never be executed by discovery")
'''
        (self.root / "app.py").write_text(source)
        digest = hashlib.sha256(source.encode()).hexdigest()
        for group in ("nodes", "bindings", "calls", "effects"):
            for record in self.doc[group]:
                record["source"]["sha256"] = digest
                for field in ("node", "caller", "target"):
                    if field in record:
                        record[field] = "app:" + record[field]
        self.save()
        (self.root / "capcov.toml").write_text('''[capcov]
source = "."
[[adapters]]
name = "python-fastapi-sqlalchemy"
environment_facts = "recovery.json"
environment_inputs = ["deployment.json"]
''')
        output = self.root / "capabilities.json"
        self.assertEqual(cli.main(["discover", "--target", str(self.root),
                                   "--out", str(output), "--quiet"]), 0)
        doc = json.loads(output.read_text())
        report = next(c for c in doc["capabilities"] if c["entity"] == "reports")
        self.assertEqual(report["evidence"]["chain"],
                         ["app:route", "app:publish", "app:observer", "app:worker"])


class PythonEnvironmentTests(unittest.TestCase):
    SOURCE = '''from fastapi import FastAPI
app = FastAPI()
class Report:
    __tablename__ = "reports"
def publish(item):
    return CALLBACKS["saved"](item)
def observer(item):
    return WORKERS["report"](item)
def worker(item):
    session.add(Report())
def dry(item):
    return None
CALLBACKS = {"saved": observer}
WORKERS = {"report": worker}
HANDLERS = {"live": publish, "dry": dry}
@app.post("/publish")
def route(item):
    return HANDLERS[settings["publisher"]](item)
raise RuntimeError("must not execute source")
'''

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "app.py").write_text(self.SOURCE)
        (self.root / "capcov.toml").write_text('''[capcov]
source = "."
[[adapters]]
name = "python-fastapi-sqlalchemy"
environment_python = {file = "deployment.json", variable = "settings"}
''')

    def discover(self, env):
        from capcov import cli
        (self.root / "deployment.json").write_text(json.dumps(env))
        output = self.root / "out.json"
        self.assertEqual(cli.main(["discover", "--target", str(self.root),
                                   "--out", str(output), "--quiet"]), 0)
        return json.loads(output.read_text())

    def test_automatic_registry_chain_and_config_invalidation(self):
        live = self.discover({"publisher": "live"})
        cap = next(c for c in live["capabilities"] if c["entity"] == "reports")
        self.assertEqual(cap["evidence"]["chain"],
                         ["app:route", "app:publish", "app:observer", "app:worker"])
        self.assertEqual(cap["operations"], ["create"])
        dry = self.discover({"publisher": "dry"})
        self.assertEqual(dry["capabilities"], [])
        self.assertNotEqual(live["derived_from"]["artifact_sha256"],
                            dry["derived_from"]["artifact_sha256"])
        self.assertTrue(any(r["kind"] == "environment-python-stability" for r in dry["unresolved"]))

    def test_unknown_config_keeps_both_targets(self):
        result = self.discover({})
        targets = {e["target"] for e in result["environment_recovery"][0]["edges"]
                   if e["caller"] == "app:route"}
        self.assertEqual(targets, {"app:publish", "app:dry"})
        self.assertTrue(any("unknown environment key" in r["reason"] for r in result["unresolved"]))

    def test_shadowed_registry_is_unresolved(self):
        (self.root / "app.py").write_text(self.SOURCE.replace("def route(item):", "def route(item, HANDLERS):"))
        result = self.discover({"publisher": "live"})
        self.assertEqual(result["capabilities"], [])
        self.assertTrue(any("no known target" in r["reason"] for r in result["unresolved"]))

    def test_unsupported_selector_keeps_candidates_and_gap(self):
        (self.root / "app.py").write_text(self.SOURCE.replace('settings["publisher"]', 'item.choice'))
        result = self.discover({"publisher": "live"})
        self.assertTrue(result["capabilities"])
        self.assertTrue(any("unsupported registry selector" in r["reason"] for r in result["unresolved"]))

    def test_nonliteral_registry_does_not_invent_candidates(self):
        (self.root / "app.py").write_text(self.SOURCE.replace(
            'HANDLERS = {"live": publish, "dry": dry}', 'HANDLERS = build_handlers()'))
        result = self.discover({"publisher": "live"})
        self.assertEqual(result["capabilities"], [])

    def test_empty_configuration_still_changes_analysis_when_source_changes(self):
        before = self.discover({})["environment_recovery"][0]["analysis_sha256"]
        (self.root / "extra.py").write_text("# new source, no calls\n")
        after = self.discover({})["environment_recovery"][0]["analysis_sha256"]
        self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()
