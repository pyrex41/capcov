import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from capcov.behaviors import BehaviorError
from capcov.behaviors.registry import validate, inspect, file_hash, scope
from capcov.behaviors.qualification import execute_checks, qualify, compare, check_plan
from capcov.behaviors.recovery import import_recovery, tasks, export_graph
from capcov.behaviors.target import Session, admit, transcript, replay
from capcov.operations.system import digest, evaluate

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/behavior-publication"
spec = importlib.util.spec_from_file_location("publication_backend", EXAMPLE / "backend.py")
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


def fixture(root):
    Path(root, "source.txt").write_text("reviewed representation and source")
    Path(root, "check.py").write_text("print('assertions passed')\n")
    registry = {
        "format": "capcov-behaviors-v1", "baseline": "synthetic-v1",
        "artifacts": [{"id": "source", "path": "source.txt", "sha256": file_hash(root, "source.txt")}],
        "stores": [{"id": "store", **{k: ["source"] for k in ("physical", "representation", "access", "domain")}, "ambiguities": []}],
        "access_paths": [{"id": "writer", "store": "store", "mode": "write", "writer": "target",
                          "hooks": [], "scopes": ["tenant"], "bypasses": [], "artifacts": ["source"]}],
        "behaviors": [{"id": "publish", "purpose": "Publish a draft", "priority": 100, "entries": ["POST /publish"],
                       "depends_on": [], "access_paths": ["writer"], "artifacts": ["source"], "legacy": "source", "target": "source",
                       "obligations": [{"id": "parity", "category": "compatibility", "method": "execution", "description": "Declared scenario agrees"}]}],
        "claims": [], "decisions": [], "gaps": [],
    }
    plan = {"format": "capcov-behavior-checks-v1", "checks": [{"id": "test", "behavior": "publish", "obligations": ["parity"],
            "method": "execution", "argv": [sys.executable, "check.py"], "timeout": 5, "inputs": ["check.py"]}]}
    return registry, plan


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.registry, self.plan = fixture(self.root)

    def run_checks(self):
        directory = self.root / "evidence"
        receipts = execute_checks(self.registry, self.plan, self.root, ["publish"], directory)
        return qualify(self.registry, self.plan, self.root, ["publish"], receipts, directory), receipts, directory

    def test_fresh_execution_and_exact_binding(self):
        report, receipts, directory = self.run_checks()
        self.assertTrue(report["complete"])
        self.assertEqual(report["obligations"][0]["method"], "execution")
        self.assertFalse(qualify(self.registry, self.plan, self.root, ["publish"], [], directory)["complete"])
        self.assertFalse(qualify(self.registry, self.plan, self.root, ["publish"], receipts * 2, directory)["complete"])
        self.assertFalse(qualify(self.registry, self.plan, self.root, ["publish"], receipts, directory, cutover=True)["complete"])

    def test_changed_test_or_log_cannot_reuse_evidence(self):
        _, receipts, directory = self.run_checks()
        Path(directory, receipts[0]["logs"]["stdout"]["path"]).write_text("forged")
        self.assertFalse(qualify(self.registry, self.plan, self.root, ["publish"], receipts, directory)["complete"])
        Path(self.root, "check.py").write_text("raise Exception('broken')")
        self.assertFalse(qualify(self.registry, self.plan, self.root, ["publish"], receipts, directory)["complete"])

    def test_failed_check_cannot_be_hidden_by_passing_check(self):
        self.plan["checks"].append(dict(self.plan["checks"][0], id="fails", argv=[sys.executable, "-c", "raise SystemExit(1)"]))
        report, _, _ = self.run_checks()
        self.assertFalse(report["complete"])
        self.assertTrue(report["invalid_evidence"])

    def test_timeout_is_operational_failure(self):
        self.plan["checks"][0].update(argv=[sys.executable, "-c", "while True: pass"], timeout=0.05)
        report, receipts, _ = self.run_checks()
        self.assertFalse(report["complete"])
        self.assertEqual(receipts[0]["operational"], "operational-failure")

    def test_transitive_invalidation_and_shared_writers(self):
        r = self.registry
        r["behaviors"].append(dict(copy.deepcopy(r["behaviors"][0]), id="report", depends_on=["publish"],
            obligations=[{"id": "report-test", "category": "compatibility", "method": "execution", "description": "reads publication"}]))
        r["access_paths"].append(dict(r["access_paths"][0], id="legacy-writer", writer="legacy"))
        before = inspect(r, self.root, ["report"])
        self.assertEqual(before["shared_writers"]["store"], ["legacy", "target"])
        Path(self.root, "source.txt").write_text("changed")
        after = inspect(r, self.root, ["report"])
        self.assertTrue({"publish", "report", "writer", "store"} <= set(after["stale"]))

    def test_other_writer_source_is_in_coexistence_scope(self):
        (self.root / "legacy.php").write_text("legacy writer")
        self.registry["artifacts"].append({"id": "legacy-code", "path": "legacy.php", "sha256": file_hash(self.root, "legacy.php")})
        self.registry["access_paths"].append(dict(self.registry["access_paths"][0], id="legacy-write", writer="legacy", artifacts=["legacy-code"]))
        report, receipts, directory = self.run_checks()
        self.assertTrue(report["complete"])
        (self.root / "legacy.php").write_text("bypasses version update")
        self.assertFalse(qualify(self.registry, self.plan, self.root, ["publish"], receipts, directory)["complete"])

    def test_ambiguity_and_gap_block_even_passing_checks(self):
        self.registry["stores"][0]["ambiguities"] = ["t is not classified"]
        self.registry["gaps"] = [{"id": "draft", "behavior": "publish", "question": "scope?", "owner": "reviewer",
                                  "closure": "capture draft publication", "artifacts": ["source"]}]
        report, _, _ = self.run_checks()
        self.assertFalse(report["complete"])
        self.assertEqual({b["kind"] for b in report["blockers"]}, {"gap", "representation"})

    def test_static_extraction_cannot_satisfy_observation(self):
        self.plan["checks"][0]["method"] = "static"
        with self.assertRaisesRegex(BehaviorError, "method mismatch"):
            check_plan(self.plan, self.registry)

    def test_recovery_preserves_kind_and_detects_stale_source(self):
        payload = {"format": "capcov-recovery-v1", "claims": [{"id": "hook", "behavior": "publish", "statement": "hook registered",
            "confidence": "confirmed", "artifacts": ["source"], "depends_on": []}], "gaps": []}
        recovered = import_recovery(self.registry, payload, self.root)
        self.assertEqual(recovered["claims"][0]["kind"], "static")
        Path(self.root, "source.txt").write_text("different source")
        with self.assertRaisesRegex(BehaviorError, "stale"):
            import_recovery(self.registry, payload, self.root)

    def test_decision_cannot_mask_an_unrelated_difference(self):
        self.registry["decisions"] = [{"id": "fix", "behavior": "publish", "disposition": "correct", "rationale": "durable outbox",
            "status": "approved", "owner": "reviewer", "artifacts": ["source"], "obligations": ["parity"],
            "differences": [{"scenario": "publish", "path": ["intent"], "legacy": False, "target": True}]}]
        report, _, _ = self.run_checks()
        self.assertTrue(compare(self.registry, "publish", "publish", {"intent": False}, {"intent": True}, report)["compatible"])
        self.assertFalse(compare(self.registry, "publish", "publish", {"intent": False,"tenant":"a"}, {"intent": True,"tenant":"b"}, report)["compatible"])
        self.assertFalse(compare(self.registry, "publish", "other", {"intent": False}, {"intent": True}, report)["compatible"])

    def test_missing_presence_is_not_null(self):
        report, _, _ = self.run_checks()
        self.assertFalse(compare(self.registry, "publish", "s", {}, {"x": None}, report)["compatible"])

    def test_tasks_and_graph_preserve_missing_obligations(self):
        report = qualify(self.registry, self.plan, self.root, ["publish"], [], self.root)
        self.assertEqual(tasks(self.registry, report)["tasks"][0]["obligation"], "parity")
        export_graph(self.registry, self.root, ["publish"], self.root / "graph")
        self.assertIn("stale(C)", (self.root / "graph/evidence.dl").read_text())

    def test_cycles_and_escaping_artifacts_refused(self):
        self.registry["behaviors"][0]["depends_on"] = ["publish"]
        with self.assertRaisesRegex(BehaviorError, "cyclic"):
            validate(self.registry)
        self.registry["behaviors"][0]["depends_on"] = []
        self.registry["artifacts"][0]["path"] = "../secret"
        with self.assertRaises(BehaviorError):
            validate(self.registry)


NATIVE = bool(shutil.which("bifrost") and os.environ.get("BIFROST_SHEN_SCHEME"))


@unittest.skipUnless(NATIVE, "requires native Shen-Scheme and bifrost")
class NativeBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.backend = backend.Backend(Path(self.tmp.name) / "db.sqlite")
        self.addCleanup(self.backend.close)
        self.backend.seed()
        self.route = json.loads((EXAMPLE / "route.json").read_text())
        self.worker = json.loads((EXAMPLE / "worker.json").read_text())
        self.env = {"context.tenant": "tenant-a", "context.principal": "alice",
                    "request.issue": "i1", "request.version": "0", "request.id": "r1"}

    def publish(self, **overrides):
        return backend.drive(Session(self.route, self.env | overrides), self.backend)

    def test_publish_and_idempotent_retry(self):
        self.assertEqual(self.publish()["status"], "200")
        self.assertEqual(self.publish()["status"], "200")
        self.assertEqual(self.backend.db.execute("SELECT status,version,identifier FROM issue").fetchone(), ("published",1,"ISSUE-i1"))
        self.assertEqual(self.backend.db.execute("SELECT count(*) FROM outbox").fetchone()[0], 1)

    def test_wrong_tenant_and_denied_have_no_effect(self):
        self.assertEqual(self.publish(**{"context.tenant": "tenant-b"})["status"], "404")
        self.assertEqual(self.publish(**{"context.principal": "mallory"})["status"], "403")
        self.assertEqual(self.backend.db.execute("SELECT count(*) FROM outbox").fetchone()[0], 0)

    def test_unknown_commit_reconciles_through_retry(self):
        self.backend.lose_commit = True
        self.assertEqual(self.publish()["status"], "unknown")
        self.assertEqual(self.publish()["status"], "200")
        self.assertEqual(self.backend.db.execute("SELECT count(*) FROM request").fetchone()[0], 1)

    def test_payload_reuse_and_unknown_representation_refused(self):
        self.publish()
        self.assertEqual(self.publish(**{"request.version": "1"})["status"], "409")
        self.backend.db.execute("UPDATE issue SET identifier='t'")
        self.assertEqual(self.publish()["status"], "representation-gap")

    def test_authorization_revoked_between_ask_and_commit(self):
        session = Session(self.route, self.env)
        for _ in range(2):
            step = session.advance()
            outcome, values = self.backend.effect(step)
            session.resume({k: step[k] for k in ("workflow","sequence","program_sha256")} | {"outcome":outcome,"values":values})
        self.backend.db.execute("DELETE FROM permission")
        self.assertEqual(backend.drive(session, self.backend)["status"], "403")
        self.assertEqual(self.backend.db.execute("SELECT count(*) FROM outbox").fetchone()[0], 0)

    def test_cooperating_legacy_writer_causes_version_conflict(self):
        self.backend.db.execute("UPDATE issue SET version=version+1")
        self.assertEqual(self.publish()["status"], "409")

    def test_worker_unknown_then_retry_uses_provider_deduplication(self):
        self.publish()
        intent = self.backend.db.execute("SELECT id FROM outbox").fetchone()[0]
        env = {"context.tenant":"tenant-a", "request.intent":intent}
        self.backend.lose_delivery = True
        self.assertEqual(backend.drive(Session(self.worker, env), self.backend)["status"], "unknown")
        self.assertEqual(backend.drive(Session(self.worker, env), self.backend)["status"], "success")
        self.assertEqual(self.backend.db.execute("SELECT count(*) FROM provider").fetchone()[0], 1)
        self.assertEqual(self.backend.db.execute("SELECT state FROM outbox").fetchone()[0], "sent")

    def test_phase_row_and_missing_outcome_rejected_in_unreachable_nodes_too(self):
        wrong = copy.deepcopy(self.worker)
        wrong["phase"] = "route"
        with self.assertRaises(BehaviorError):
            admit(wrong)
        wrong = copy.deepcopy(self.route)
        wrong["operations"].append({"id": "unused-external", "kind": "External", "inputs": [], "results": {"ok": []}})
        wrong["row"].append("unused-external")
        with self.assertRaises(BehaviorError):
            admit(wrong)
        wrong = copy.deepcopy(self.route)
        wrong["row"].remove("publish")
        with self.assertRaises(BehaviorError):
            admit(wrong)
        wrong = copy.deepcopy(self.route)
        del wrong["nodes"][2]["next"]["unknown"]
        with self.assertRaises(BehaviorError):
            admit(wrong)

    def test_resume_correlation_checkpoint_and_no_automatic_resend(self):
        session = Session(self.route, self.env)
        step = session.advance()
        resumed = Session.restore(self.route, session.checkpoint())
        with self.assertRaises(BehaviorError):
            resumed.advance()
        response = {k: step[k] for k in ("workflow","sequence","program_sha256")} | {"outcome":"absent","values":{}}
        with self.assertRaises(BehaviorError):
            resumed.resume(response | {"sequence": 50})
        resumed.resume(response)
        with self.assertRaises(BehaviorError):
            resumed.resume(response)
        self.assertEqual(resumed.advance()["input"]["status"], "404")

    def test_legacy_model_runs_in_existing_system_engine(self):
        result = evaluate((EXAMPLE / "legacy.ops").read_text(), [{
            "command":"publish", "args":{"id":"i1"}, "state":[{"table":"issue","key":"i1","fields":{"status":"draft"}}], "outcome":"committed"}])
        self.assertTrue(result["results"])

    def test_record_replay_matches_requests_before_reusing_replies(self):
        session = Session(self.route, self.env)
        backend.drive(session, self.backend)
        recording = transcript(session)
        self.assertTrue(replay(self.route, self.env, recording)["replayed"])
        changed = copy.deepcopy(recording)
        changed["interactions"][0]["request"]["input"]["tenant"] = "tenant-b"
        with self.assertRaisesRegex(BehaviorError, "request divergence"):
            replay(self.route, self.env, changed)


@unittest.skipUnless(shutil.which("souffle"), "requires Souffle")
class SouffleBehaviorTests(unittest.TestCase):
    def test_graph_matches_transitive_invalidation(self):
        from capcov.operations.process import run

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = fixture(root)
            (root / "source.txt").write_text("changed source")
            graph = root / "graph"
            report = export_graph(registry, root, ["publish"], graph)
            code, _, stderr = run([shutil.which("souffle"), "-F", str(graph), "-D", str(graph), str(graph / "evidence.dl")], timeout=30)
            self.assertEqual(code, 0, stderr.decode())
            ids = json.loads((graph / "ids.json").read_text())
            actual = {ids[line.strip().strip('"')] for line in (graph / "stale.csv").read_text().splitlines()}
            self.assertEqual(actual, set(report["stale"]))
