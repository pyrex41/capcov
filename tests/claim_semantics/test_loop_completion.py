import copy
import json
import os
from pathlib import Path
import shutil
import unittest

from capcov.operations import OperationError
from capcov.operations.completion import local_actions, snapshot_reads
from capcov.operations.loops import prove_loops, check_loops
from capcov.operations.native import invoke, term
from capcov.operations.proofs import KERNEL
from capcov.operations.system import evaluate, json_state, digest

FIXTURE = Path(__file__).parent / "fixtures/systems"
SOURCE = (FIXTURE / "loop-completion.ops").read_text()
CONTRACT = json.loads((FIXTURE / "loop-completion.json").read_text())
BODY = '[named "close" [update "item" [row-key] "status" [literal "closed"]]]'
NATIVE = bool(
    shutil.which("bifrost")
    and Path(os.environ.get("BIFROST_SHEN_GO", "/missing")).is_file()
)


class CompletionTransformTests(unittest.TestCase):
    def test_frame_rejects_domain_changes_and_other_keys(self):
        for action in (
            ["remove", "item", ["row-key"]],
            ["insert", "item", ["row-key"], []],
            ["update", "item", ["argument", "other"], "status", ["literal", "closed"]],
            ["update", "other", ["row-key"], "status", ["literal", "closed"]],
        ):
            self.assertFalse(local_actions("item", [["named", "bad", action]]))
        self.assertTrue(
            local_actions(
                "item",
                [
                    [
                        "named",
                        "good",
                        [
                            "update",
                            "item",
                            ["row-key"],
                            "status",
                            ["literal", "closed"],
                        ],
                    ]
                ],
            )
        )

    def test_head_snapshot_link_is_scoped(self):
        key = ["argument", "head"]
        frozen = ["before", ["lookup", "item", key, "status"]]
        other = ["lookup", "item", ["argument", "other"], "status"]
        expr = [
            "both",
            ["equal", ["lookup", "item", key, "status"], ["literal", "closed"]],
            ["equal", frozen, other],
        ]
        actual = snapshot_reads(expr, "item", key, {"status": "captured-status"})
        self.assertEqual(actual[1][1], ["argument", "captured-status"])
        self.assertEqual(actual[2], expr[2])


@unittest.skipUnless(NATIVE, "requires native Shen")
class NativeCompletionTests(unittest.TestCase):
    def test_completes_all_rows_and_executes(self):
        report = prove_loops(SOURCE, CONTRACT)
        self.assertEqual(report["status"], "proved")
        self.assertTrue(
            check_loops(SOURCE, json.loads(json.dumps(report, sort_keys=True)))
        )
        self.assertTrue(
            any(o["id"].endswith(":complete") for o in report["obligations"])
        )
        requests = [
            {
                "command": "close-all",
                "args": {},
                "outcome": "committed",
                "state": [
                    {
                        "table": "item",
                        "key": str(i),
                        "fields": {"status": "open" if i % 2 else "closed"},
                    }
                    for i in range(count)
                ],
            }
            for count in (0, 1, 17)
        ]
        results = evaluate(SOURCE, requests)["results"]
        for result in results:
            state = json_state(result["admissible"][0][1])
            self.assertTrue(all(r["fields"]["status"] == "closed" for r in state))

    def test_filtered_snapshot_and_mutated_selector(self):
        selector = '[equal [row-field "status"] [literal "open"]]'
        source = SOURCE.replace(
            '[for-each "item" [yes]', '[for-each "item" ' + selector
        )
        report = prove_loops(source, CONTRACT)
        self.assertEqual(report["status"], "proved")
        self.assertTrue(check_loops(source, report))
        completion = report["rules"][0]["completion"]
        self.assertNotEqual(completion["coverage"], ["yes"])
        initial = [
            {"table": "item", "key": "a", "fields": {"status": "open"}},
            {"table": "item", "key": "b", "fields": {"status": "closed"}},
        ]
        result = evaluate(
            source,
            [
                {
                    "command": "close-all",
                    "args": {},
                    "outcome": "committed",
                    "state": initial,
                }
            ],
        )
        self.assertTrue(
            all(
                r["fields"]["status"] == "closed"
                for r in json_state(result["results"][0]["admissible"][0][1])
            )
        )

    def test_unselected_rows_need_entry_coverage(self):
        source = SOURCE.replace('[for-each "item" [yes]', '[for-each "item" [no]')
        report = prove_loops(source, CONTRACT)
        self.assertEqual(report["status"], "open")
        self.assertTrue(
            any(
                o["status"] == "open" and o["id"].endswith(":initiation")
                for o in report["obligations"]
            )
        )
        self.assertFalse(check_loops(source, report))

    def test_missing_work_and_stale_restore_rejected(self):
        mutations = [
            SOURCE.replace(BODY, '[named "noop" [publish "noop" [literal "x"]]]'),
            SOURCE.replace(
                BODY,
                BODY
                + ' [named "restore" [update "item" [row-key] "status" [row-field "status"]]]',
            ),
        ]
        for source in mutations:
            report = prove_loops(source, CONTRACT)
            self.assertEqual(report["status"], "open")
            self.assertTrue(
                any(
                    o["status"] == "open" and o["id"].endswith(":complete")
                    for o in report["obligations"]
                )
            )

    def test_cross_row_mutation_and_stateful_selector_open(self):
        cross = SOURCE.replace(
            '[command "close-all" []', '[command "close-all" ["other"]'
        )
        cross = cross.replace(
            '[update "item" [row-key]', '[update "item" [argument "other"]'
        )
        stateful = SOURCE.replace(
            '[for-each "item" [yes]',
            '[for-each "item" [equal [count-rows "item"] [literal "1"]]',
        )
        for source in (cross, stateful):
            report = prove_loops(source, CONTRACT)
            self.assertEqual(report["status"], "open")
            self.assertTrue(any("reason" in o for o in report["obligations"]))

    def test_shen_datatype_and_frame_judgments(self):
        judgment = [
            "snapshot-partition",
            ["true"],
            ["atom", "all-done"],
            [["true"]],
            ["true"],
            ["atom", "all-done"],
        ]
        good = [
            [
                "named",
                "set",
                ["update", "item", ["row-key"], "status", ["literal", "closed"]],
            ]
        ]
        bad = copy.deepcopy(good)
        bad[0][2][2] = ["argument", "other"]
        expressions = f"[(cl.partition-typechecks? {term(judgment)}) (cl.local-actions? {term('item')} {term(good)}) (cl.local-actions? {term('item')} {term(bad)})]"
        answer, _ = invoke(
            expressions, (*KERNEL, "completion-types.shen", "loop-check.shen")
        )
        self.assertEqual(answer, [True, True, False])
        judgment[1] = ["unknown-formula"]
        answer, _ = invoke(
            f"(cl.partition-typechecks? {term(judgment)})",
            (*KERNEL, "completion-types.shen"),
        )
        self.assertIs(answer, False)

    def test_completion_reaches_claim_pipeline(self):
        from capcov.operations.evidence import extract, bind
        from capcov.operations.workbench import verify

        inventory = extract(FIXTURE, ["scenario-adapter.py"])
        obligation = "close-all:postcondition"
        inventory = bind(
            inventory,
            [
                {
                    "id": "closed",
                    "kind": "target",
                    "statement": "all items are closed",
                    "anchors": [inventory["anchors"][0]["id"]],
                    "depends_on": [],
                    "obligations": [obligation],
                }
            ],
            [],
        )
        report = verify(SOURCE, FIXTURE, inventory, [], loop_invariants=CONTRACT)
        self.assertEqual(report["claims"][0]["open_model_obligations"], [])
        self.assertEqual(
            report["claims"][0]["loop_proved_model_obligations"], [obligation]
        )
        self.assertEqual(report["loop_induction"]["status"], "proved")

    def test_forged_completion_and_frame_rejected(self):
        report = prove_loops(SOURCE, CONTRACT)
        for kind in ("coverage", "body", "step"):
            bad = copy.deepcopy(report)
            c = bad["rules"][0]["completion"]
            if kind == "coverage":
                c["coverage"] = ["no"]
            elif kind == "body":
                c["body"] = []
            else:
                bad["obligations"].pop(c["step"])
            bad["sha256"] = digest({k: v for k, v in bad.items() if k != "sha256"})
            with self.assertRaises(OperationError):
                check_loops(SOURCE, bad)
