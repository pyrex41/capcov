"""Real HTTP/SQLite boundary tests and independently checked induction proofs."""

import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import subprocess
import tempfile
import threading
import unittest

from capcov.operations import OperationError
from capcov.operations.adapters import HTTPBackend, execute
from capcov.operations.induction import obligations, prove_induction, check_induction
from capcov.operations.system import digest


class SQLiteBackend:
    """Synthetic consumer implementation; not a model interpreter."""

    def __init__(self):
        self.db = None
        self.released = 0
        self.bad_reset = False
        self.bad_outcome = False

    def describe(self):
        return {
            "identity": "synthetic-sqlite-build-1",
            "commands": ["set"],
            "outcomes": ["committed", "aborted"],
            "controls": ["sqlite-transaction"],
        }

    def acquire(self):
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.execute("create table item (id text primary key, value text)")
        return "session1"

    def reset(self, lease, initial):
        if not self.bad_reset:
            self.db.executemany(
                "insert into item values (?, ?)",
                [(r["key"], r["fields"]["value"]) for r in initial],
            )
        self.db.commit()

    def snapshot(self, lease):
        return [
            {"table": "item", "key": k, "fields": {"value": v}}
            for k, v in self.db.execute("select id, value from item order by id")
        ]

    def execute(self, lease, index, call, outcome):
        args = call["args"]
        self.db.execute(
            "update item set value=? where id=?", (args["value"], args["id"])
        )
        effects = []
        if outcome == "committed":
            self.db.commit()
            effects = [["put", "item", args["id"], "value", args["value"]]]
        else:
            self.db.rollback()
        return {
            "outcome": "lie" if self.bad_outcome else outcome,
            "observation": {"state": self.snapshot(lease), "effects": effects},
        }

    def release(self, lease):
        self.released += 1
        self.db.close()


def payload():
    return {
        "protocol": "capcov-scenario-adapter-v1",
        "initial": [{"table": "item", "key": "1", "fields": {"value": "old"}}],
        "steps": [
            {
                "call": {
                    "command": "set",
                    "args": {"id": "1", "value": "new"},
                    "outcome": "unknown",
                },
                "choice": c,
            }
            for c in ("0", "1")
        ],
    }


class AdapterTests(unittest.TestCase):
    def test_sql_transactions_and_release(self):
        backend = SQLiteBackend()
        result = execute(payload(), backend)
        self.assertEqual(result["observations"][0]["state"], payload()["initial"])
        self.assertEqual(result["observations"][0]["effects"], [])
        self.assertEqual(
            result["observations"][1]["state"][0]["fields"]["value"], "new"
        )
        self.assertEqual(backend.released, 1)

    def test_failure_cleanup_and_preflight(self):
        for fault in ("bad_reset", "bad_outcome"):
            backend = SQLiteBackend()
            setattr(backend, fault, True)
            with self.assertRaises(OperationError):
                execute(payload(), backend)
            self.assertEqual(backend.released, 1)
        backend = SQLiteBackend()
        data = payload()
        data["steps"][0]["call"]["command"] = "unsupported"
        with self.assertRaises(OperationError):
            execute(data, backend)
        self.assertIsNone(backend.db)
        data = payload()
        data["steps"][0]["result"] = []
        with self.assertRaises(OperationError):
            execute(data, backend)

    def test_http_control_plane_and_replay(self):
        self.http_roundtrip()

    def http_roundtrip(self, model=False):
        backend = SQLiteBackend()
        paths = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                paths.append(self.path)
                action = self.path.rsplit("/", 1)[-1]
                if action == "describe":
                    result = backend.describe()
                elif action == "sessions":
                    result = {"lease": backend.acquire()}
                elif action == "reset":
                    backend.reset("session1", data["initial"])
                    result = {"ok": True}
                elif action == "snapshot":
                    result = backend.snapshot("session1")
                elif action == "execute":
                    result = backend.execute("session1", **data)
                else:
                    backend.release("session1")
                    result = {"ok": True}
                raw = json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}"
            if model:
                source = '[system "test" [[table "item" ["value"] [] []]] [[command "set" ["id" "value"] [yes] [[named "set" [update "item" [argument "id"] "value" [argument "value"]]]] [yes]]] []]'
                scenario = {k: v for k, v in payload().items() if k != "protocol"}
                with tempfile.TemporaryDirectory() as directory:
                    spec = Path(directory) / "test.ops"
                    data = Path(directory) / "input.json"
                    spec.write_text(source)
                    data.write_text(json.dumps(scenario))
                    process = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "capcov.operations.workbench",
                            "scenario",
                            "--spec",
                            str(spec),
                            "--input",
                            str(data),
                            "--adapter",
                            sys.executable,
                            "-m",
                            "capcov.operations.adapters",
                            "--url",
                            url,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=90,
                    )
                    self.assertEqual(process.returncode, 0, process.stderr)
                    report = json.loads(process.stdout)
                self.assertTrue(report["replay_matches"])
                self.assertEqual(report["mismatches"], [])
                self.assertEqual(report["checked_steps"], 2)
                return
            a = execute(payload(), HTTPBackend(url))
            b = execute(payload(), HTTPBackend(url))
            self.assertEqual(a, b)
            self.assertEqual(paths.count("/sessions/session1/execute"), 4)
            self.assertEqual(backend.released, 2)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_identity_drift_and_cleanup_failure(self):
        class Drifting(SQLiteBackend):
            calls = 0

            def describe(self):
                self.calls += 1
                result = super().describe()
                result["identity"] = str(self.calls)
                return result

        backend = Drifting()
        with self.assertRaisesRegex(OperationError, "identity changed"):
            execute(payload(), backend)
        self.assertEqual(backend.released, 1)

        class BrokenRelease(SQLiteBackend):
            def release(self, lease):
                super().release(lease)
                raise OperationError("release failed")

        with self.assertRaisesRegex(OperationError, "release failed"):
            execute(payload(), BrokenRelease())

    def test_redirects_and_invalid_responses_are_not_retried(self):
        calls = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                calls.append(self.path)
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(302 if self.path == "/redirect" else 200)
                self.send_header("Location", "/unexpected")
                self.end_headers()
                self.wfile.write(b"not-json")

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            backend = HTTPBackend(f"http://127.0.0.1:{server.server_port}")
            for path in ("/redirect", "/malformed"):
                with self.assertRaises(OperationError):
                    backend._send(path, {})
            self.assertEqual(calls, ["/redirect", "/malformed"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_transport_validation(self):
        for url in (
            "file:///tmp/x",
            "http://user:pass@localhost",
            "https://example.invalid/?token=x",
        ):
            with self.assertRaises(OperationError):
                HTTPBackend(url)
        with self.assertRaises(OperationError):
            HTTPBackend("http://example.invalid", bearer="secret")
        with self.assertRaises(OperationError):
            HTTPBackend._path("../escape", "reset")
        backend = HTTPBackend("http://127.0.0.1", timeout=1)
        backend.deadline = 0
        with self.assertRaises(OperationError):
            backend.describe()


def system():
    # p initially holds; every transition preserves p. q is unconstrained.
    return {
        "variables": ["p", "q"],
        "initial": ["atom", "p"],
        "invariant": ["atom", "p"],
        "safety": ["atom", "p"],
        "transitions": {"keep": ["or", ["not", ["atom", "p"]], ["atom", "next:p"]]},
    }


class InductionSchemaTests(unittest.TestCase):
    def test_free_variables_and_next_state_rejected(self):
        for field in ("initial", "invariant", "safety"):
            bad = system()
            bad[field] = ["atom", "next:p"]
            with self.assertRaises(OperationError):
                obligations(bad)
        bad = system()
        bad["transitions"]["keep"] = ["atom", "undeclared"]
        with self.assertRaises(OperationError):
            obligations(bad)


NATIVE = bool(
    shutil.which("bifrost")
    and Path(os.environ.get("BIFROST_SHEN_GO", "/missing")).is_file()
)


@unittest.skipUnless(NATIVE, "requires native Shen")
class NativeInductionTests(unittest.TestCase):
    def test_http_model_conformance(self):
        AdapterTests().http_roundtrip(model=True)

    def test_protocol_with_cycles(self):
        spec = json.loads(
            (Path(__file__).parent / "fixtures/systems/lock-induction.json").read_text()
        )
        spec["transitions"] = dict(reversed(list(spec["transitions"].items())))
        report = prove_induction(spec)
        reloaded = json.loads(json.dumps(report, sort_keys=True))
        self.assertTrue(check_induction(reloaded, system=spec))
        self.assertEqual(report["status"], "proved")
        self.assertEqual(len(report["obligations"]), 6)

    def test_induction_and_forgery(self):
        report = prove_induction(system())
        self.assertEqual(report["status"], "proved")
        self.assertTrue(check_induction(report, system=system()))
        for change in ("drop", "replace", "rename"):
            bad = copy.deepcopy(report)
            if change == "drop":
                bad["obligations"].pop()
            elif change == "replace":
                bad["obligations"][-1]["proof"] = bad["obligations"][0]["proof"]
            else:
                bad["system"]["transitions"]["keep"] = ["true"]
            bad["sha256"] = digest({k: v for k, v in bad.items() if k != "sha256"})
            with self.assertRaises(OperationError):
                check_induction(bad)
        with self.assertRaises(OperationError):
            check_induction(report, system=dict(system(), safety=["false"]))

    def test_missing_frame_is_not_assumed(self):
        bad = system()
        bad["transitions"]["unconstrained"] = ["true"]
        report = prove_induction(bad)
        self.assertEqual(report["status"], "open")
        self.assertFalse(check_induction(report))
        self.assertEqual(
            report["obligations"][-1]["proof"]["answer"][0], "countermodel"
        )

    def test_base_and_safety_fail_independently(self):
        for field in ("initial", "safety"):
            bad = system()
            bad[field] = ["true"] if field == "initial" else ["false"]
            self.assertEqual(prove_induction(bad)["status"], "open")
