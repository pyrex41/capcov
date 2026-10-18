import copy
import json
import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from capcov.operations import OperationError
from capcov.operations.compiler import compile_system, wp, formula
from capcov.operations.loops import _captured, prove_loops, check_loops
from capcov.operations.system import digest, evaluate, json_state

FIXTURES = Path(__file__).parent / "fixtures/systems"
SOURCE = (FIXTURES / "loop-induction.ops").read_text()
INVARIANTS = json.loads((FIXTURES / "loop-invariants.json").read_text())
NATIVE = bool(
    shutil.which("bifrost")
    and Path(os.environ.get("BIFROST_SHEN_GO", "/missing")).is_file()
)


class SnapshotBindingTests(unittest.TestCase):
    def test_capture_avoids_inner_binders(self):
        names = {"key": "snapshot-key", "fields": {"status": "snapshot-status"}}
        nested = [
            "for-each",
            "item",
            ["yes"],
            [["named", "inner", ["remove", "item", ["row-key"]]]],
        ]
        predicate = [
            "every-row",
            "item",
            ["equal", ["row-field", "status"], ["literal", "closed"]],
        ]
        self.assertEqual(_captured(nested, names), nested)
        self.assertEqual(_captured(predicate, names), predicate)
        self.assertEqual(
            _captured(
                ["update", "item", ["row-key"], "status", ["row-field", "status"]],
                names,
            ),
            [
                "update",
                "item",
                ["argument", "snapshot-key"],
                "status",
                ["argument", "snapshot-status"],
            ],
        )

    def test_captured_field_does_not_follow_live_updates(self):
        names = {"key": "key", "fields": {"status": "old-status"}}
        body = _captured(
            [
                [
                    "named",
                    "first",
                    ["update", "item", ["row-key"], "status", ["literal", "closed"]],
                ],
                [
                    "named",
                    "restore",
                    ["update", "item", ["row-key"], "status", ["row-field", "status"]],
                ],
            ],
            names,
        )
        target = [
            "equal",
            ["lookup", "item", ["argument", "key"], "status"],
            ["literal", "closed"],
        ]
        result = wp(body, target)
        self.assertEqual(
            result, ["equal", ["argument", "old-status"], ["literal", "closed"]]
        )
        self.assertNotEqual(formula(result), ["true"])


@unittest.skipUnless(NATIVE, "requires native Shen")
class NativeLoopTests(unittest.TestCase):
    def test_proof_recheck_serialization_and_execution(self):
        original = compile_system(SOURCE)
        self.assertEqual(original["commands"][0]["obligations"][1]["status"], "open")
        report = prove_loops(SOURCE, INVARIANTS)
        self.assertEqual(report["status"], "proved")
        report = json.loads(json.dumps(report, sort_keys=True))
        with patch(
            "capcov.operations.loops.prove_many",
            side_effect=AssertionError("checker invoked search"),
        ):
            self.assertTrue(check_loops(SOURCE, report, invariants=INVARIANTS))
        requests = [
            {
                "command": "close-all",
                "args": {},
                "outcome": "committed",
                "state": [
                    {"table": "item", "key": str(i), "fields": {"status": "open"}}
                    for i in range(count)
                ],
            }
            for count in (0, 1, 12)
        ]
        result = evaluate(SOURCE, requests)
        for row in result["results"]:
            self.assertEqual(row["admissible"][0][0], "result")

    def test_invalid_body_and_unestablished_invariant_stay_open(self):
        mutated = SOURCE.replace('[literal "closed"]]]]]]]', '[literal "broken"]]]]]]]')
        self.assertNotEqual(mutated, SOURCE)
        report = prove_loops(mutated, INVARIANTS)
        self.assertEqual(report["status"], "open")
        self.assertTrue(
            any(
                o["status"] == "open" and ":preserve" in o["id"]
                for o in report["obligations"]
            )
        )
        self.assertFalse(check_loops(mutated, report))
        report = prove_loops(SOURCE, {"close-all": {"items": "[no]"}})
        self.assertEqual(report["status"], "open")
        self.assertTrue(
            any(
                o["status"] == "open" and o["id"].endswith(":initiation")
                for o in report["obligations"]
            )
        )

    def test_nested_loops(self):
        body = '[named "close" [update "item" [row-key] "status" [literal "closed"]]]'
        nested = SOURCE.replace(
            body, '[named "inner" [for-each "item" [yes] [' + body + "]]]"
        )
        invariants = copy.deepcopy(INVARIANTS)
        invariants["close-all"]["inner"] = invariants["close-all"]["items"]
        report = prove_loops(nested, invariants)
        self.assertEqual(report["status"], "proved")
        self.assertTrue(check_loops(nested, report))
        self.assertEqual(sum(":preserve" in o["id"] for o in report["obligations"]), 2)

    def test_forged_missing_and_substituted_obligations(self):
        report = prove_loops(SOURCE, INVARIANTS)
        for kind in ("missing", "proof", "sequent", "rule"):
            bad = copy.deepcopy(report)
            if kind == "missing":
                bad["obligations"].pop(0)
            elif kind == "proof":
                bad["obligations"][0]["proof"] = bad["obligations"][1]["proof"]
            elif kind == "sequent":
                bad["obligations"][0]["left"] = [["false"]]
            else:
                bad["rules"] = []
            bad["sha256"] = digest({k: v for k, v in bad.items() if k != "sha256"})
            with self.assertRaises(OperationError):
                check_loops(SOURCE, bad)
        with self.assertRaises(OperationError):
            check_loops(SOURCE + "\n", report)
        with self.assertRaises(OperationError):
            check_loops(SOURCE, report, invariants={})

    def test_snapshot_execution_and_unproved_continuation(self):
        body = '[named "close" [update "item" [row-key] "status" [literal "closed"]]]'
        restore = (
            '[named "restore" [update "item" [row-key] "status" [row-field "status"]]]'
        )
        source = SOURCE.replace(body, body + " " + restore)
        initial = [{"table": "item", "key": "1", "fields": {"status": "open"}}]
        result = evaluate(
            source,
            [
                {
                    "command": "close-all",
                    "args": {},
                    "state": initial,
                    "outcome": "committed",
                }
            ],
        )
        self.assertEqual(json_state(result["results"][0]["admissible"][0][1]), initial)
        stronger_post = SOURCE.replace(
            "   [yes]]]",
            '   [every-row "item" [equal [row-field "status"] [literal "closed"]]]]]',
        )
        report = prove_loops(stronger_post, INVARIANTS)
        self.assertEqual(report["status"], "open")
        self.assertTrue(
            any(
                ":exit:" in o["id"] and o["status"] == "open"
                for o in report["obligations"]
            )
        )

    def test_verification_pipeline_retains_provenance(self):
        from capcov.operations.evidence import extract, bind
        from capcov.operations.workbench import verify

        inventory = extract(FIXTURES, ["scenario-adapter.py"])
        obligation = "close-all:invariant:legal-status"
        inventory = bind(
            inventory,
            [
                {
                    "id": "legal",
                    "kind": "target",
                    "statement": "status remains legal",
                    "anchors": [inventory["anchors"][0]["id"]],
                    "depends_on": [],
                    "obligations": [obligation],
                }
            ],
            [],
        )
        result = verify(SOURCE, FIXTURES, inventory, [], loop_invariants=INVARIANTS)
        self.assertEqual(result["claims"][0]["open_model_obligations"], [])
        self.assertEqual(
            result["claims"][0]["loop_proved_model_obligations"], [obligation]
        )
        self.assertEqual(
            result["compilation"]["commands"][0]["obligations"][1]["status"], "open"
        )
        self.assertEqual(result["loop_induction"]["status"], "proved")

    def test_entry_snapshot_and_conjunctive_invariant(self):
        count = '[equal [count-rows "item"] [before [count-rows "item"]]]'
        source = SOURCE.replace("   [yes]]]", "   " + count + "]]")
        invariant = "[both " + INVARIANTS["close-all"]["items"] + " " + count + "]"
        report = prove_loops(source, {"close-all": {"items": invariant}})
        self.assertEqual(report["status"], "proved")
        self.assertTrue(check_loops(source, report))

    def test_contract_scope_and_names_checked_by_shen(self):
        for invariants in (
            {"absent": {"items": "[yes]"}},
            {"close-all": {"absent": "[yes]"}},
            {"close-all": {"items": '[equal [row-field "status"] [literal "open"]]'}},
        ):
            with self.assertRaises(OperationError):
                prove_loops(SOURCE, invariants)
