"""Native compositional-system tests with hand-authored semantic expectations."""

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from capcov.operations import OperationError
from capcov.operations.system import (
    evaluate,
    explore,
    argument_domain,
    certify,
    recheck,
    claim_bundle,
    compare_models,
    verify_effects,
    digest,
    json_state,
    wire_state,
    _term,
    run_adapter,
)

FIXTURE = Path(__file__).parent / "fixtures/systems"
WORKSPACE = (FIXTURE / "workspace.ops").read_text()
LEDGER = (FIXTURE / "ledger.ops").read_text()
NATIVE = bool(shutil.which("bifrost") and os.environ.get("BIFROST_SHEN_GO"))
if os.environ.get("CAPCOV_SHEN_REQUIRED") and not NATIVE:
    raise RuntimeError("system tests require native Shen")


def row(t, k, **fields):
    return {"table": t, "key": k, "fields": fields}


ACCOUNTS = [row("account", "a", name="Alice"), row("account", "b", name="Bob")]
ITEMS = ACCOUNTS + [
    row("item", "i", owner="a", status="open", title="old"),
    row("item", "j", owner="b", status="open", title="other"),
]
WALLETS = [row("wallet", "a", balance="10"), row("wallet", "b", balance="2")]


def req(command, args, state, outcome="committed", **extra):
    return dict(
        command=command, args=args, state=copy.deepcopy(state), outcome=outcome, **extra
    )


def transfer(amount="3", request="r", state=None, outcome="committed"):
    return req(
        "transfer",
        {"from": "a", "to": "b", "amount": amount, "request": request},
        WALLETS if state is None else state,
        outcome,
    )


class SystemTransportTests(unittest.TestCase):
    def test_process_timeout_and_output_budget(self):
        from capcov.operations.process import run

        with self.assertRaisesRegex(OperationError, "timeout"):
            run([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.05)
        with self.assertRaisesRegex(OperationError, "output budget"):
            run([sys.executable, "-c", 'print("x"*10000)'], timeout=5, max_output=100)

    def test_domains_are_exhaustive_and_bounded(self):
        calls = argument_domain("op", {"b": ["x", "y"], "a": ["1", "2"]})
        self.assertEqual(
            [c["args"] for c in calls],
            [
                {"a": "1", "b": "x"},
                {"a": "1", "b": "y"},
                {"a": "2", "b": "x"},
                {"a": "2", "b": "y"},
            ],
        )
        for d in ({"x": []}, {"x": ["a", "a"]}, {"x": ["a", "b"], "y": ["1", "2"]}):
            with self.assertRaises(OperationError):
                argument_domain("op", d, limit=3)

    def test_data_only_and_bounds(self):
        for source in ('(system "evil")', '[eval "evil"]', "[] []"):
            with self.assertRaises(ValueError):
                _term(source)
        for kw in ({"fuel": 0}, {"fuel": True}, {"timeout": float("nan")}):
            with self.assertRaises(OperationError):
                evaluate(WORKSPACE, [{}], **kw)

    def test_independent_checker_rejects_forged_patch(self):
        result = {
            "analysis": [[], ["wallet"], []],
            "transition": [
                "result",
                wire_state(WALLETS),
                [["put", "wallet", "a", "balance", "0"]],
                [["action", "debit", [["put", "wallet", "a", "balance", "0"]]]],
            ],
            "admissible": [],
        }
        with self.assertRaisesRegex(OperationError, "reconstruct"):
            verify_effects(WALLETS, result)
        result["transition"][3] = []
        with self.assertRaisesRegex(OperationError, "trace/effect"):
            verify_effects(WALLETS, result)


@unittest.skipUnless(NATIVE, "real pinned Shen runtime required")
class NativeSystemTests(unittest.TestCase):
    def test_create_update_authorization_delete_and_preservation(self):
        created = ACCOUNTS + [row("item", "i", owner="a", status="open", title="new")]
        renamed = copy.deepcopy(ITEMS)
        renamed[2]["fields"]["title"] = "new"
        deleted = [ACCOUNTS[1], ITEMS[3]]
        requests = [
            req(
                "create",
                {"actor": "a", "id": "i", "title": "new"},
                ACCOUNTS,
                observed={
                    "state": created,
                    "effects": [
                        [
                            "create",
                            "item",
                            "i",
                            [["owner", "a"], ["status", "open"], ["title", "new"]],
                        ],
                        ["emit", "item-created", "i"],
                    ],
                },
            ),
            req(
                "rename",
                {"actor": "a", "id": "i", "title": "new"},
                ITEMS,
                observed={
                    "state": renamed,
                    "effects": [["put", "item", "i", "title", "new"]],
                },
            ),
            req("rename", {"actor": "b", "id": "i", "title": "new"}, ITEMS),
            req(
                "delete-account",
                {"actor": "a"},
                ITEMS,
                observed={
                    "state": deleted,
                    "effects": [["delete", "item", "i"], ["delete", "account", "a"]],
                },
            ),
        ]
        results = evaluate(WORKSPACE, requests)["results"]
        self.assertEqual(
            [r["observed_matches"] for r in results], [True, True, None, True]
        )
        self.assertEqual(results[2]["transition"], ["rejected", "precondition"])
        self.assertEqual(results[2]["admissible"], [])

    def test_idempotency_outcomes_and_retry(self):
        closed = copy.deepcopy(ITEMS)
        closed[2]["fields"]["status"] = "closed"
        calls = [
            req("close", {"actor": "a", "id": "i"}, ITEMS, o)
            for o in ("committed", "aborted", "unknown")
        ]
        calls.append(
            req(
                "close",
                {"actor": "a", "id": "i"},
                closed,
                observed={"state": closed, "effects": []},
            )
        )
        results = evaluate(WORKSPACE, calls)["results"]
        self.assertEqual([len(r["admissible"]) for r in results], [1, 1, 2, 1])
        self.assertEqual(results[1]["admissible"][0][1:3], [wire_state(ITEMS), []])
        self.assertTrue(results[3]["observed_matches"])
        self.assertEqual(
            results[0]["transition"][2],
            [["put", "item", "i", "status", "closed"], ["emit", "item-closed", "i"]],
        )

    def test_ledger_atomic_arithmetic_and_idempotency_conflicts(self):
        after = [
            row("wallet", "a", balance="7"),
            row("wallet", "b", balance="5"),
            row("transfer", "r", **{"from": "a", "to": "b", "amount": "3"}),
        ]
        first = transfer()
        first["observed"] = {
            "state": after,
            "effects": [
                ["put", "wallet", "a", "balance", "7"],
                ["put", "wallet", "b", "balance", "5"],
                [
                    "create",
                    "transfer",
                    "r",
                    [["from", "a"], ["to", "b"], ["amount", "3"]],
                ],
                ["emit", "transfer-completed", "r"],
            ],
        }
        results = evaluate(
            LEDGER,
            [
                first,
                transfer("3", "r", after),
                transfer("4", "r", after),
                transfer("11"),
            ],
        )["results"]
        self.assertTrue(results[0]["observed_matches"])
        self.assertEqual(results[1]["transition"][2], [])
        self.assertEqual(results[2]["transition"], ["rejected", "idempotency-conflict"])
        self.assertEqual(results[3]["transition"], ["rejected", "insufficient-funds"])

    def test_schema_constraints_and_invariant_rollback(self):
        mutant = WORKSPACE.replace(
            '[update "item" [argument "id"] "status" [literal "closed"]]',
            '[update "item" [argument "id"] "status" [literal "illegal"]]',
        )
        result = evaluate(mutant, [req("close", {"actor": "a", "id": "i"}, ITEMS)])[
            "results"
        ][0]
        self.assertEqual(result["transition"], ["rejected", "invariant"])
        self.assertEqual(result["admissible"], [])
        bads = [
            ACCOUNTS + [row("account", "c", name="Alice")],
            ACCOUNTS + [row("item", "i", owner="missing", status="open", title="x")],
            ACCOUNTS + [row("item", "i", owner="a", status="broken", title="x")],
        ]
        for state in bads:
            with self.subTest(state=state), self.assertRaises(OperationError):
                evaluate(
                    WORKSPACE,
                    [req("create", {"actor": "a", "id": "new", "title": "x"}, state)],
                )
        for value in ("01", "-0", "2147483648", "x"):
            with self.subTest(value=value), self.assertRaises(OperationError):
                evaluate(
                    LEDGER,
                    [transfer(state=[row("wallet", "a", balance=value), WALLETS[1]])],
                )

    def test_contextual_type_judgments_and_fuel(self):
        mutants = [
            WORKSPACE.replace('[argument "title"]', '[argument "undeclared"]'),
            WORKSPACE.replace('[update "item"', '[update "absent"'),
            WORKSPACE.replace(
                '"title" [argument "title"]', '"bad-field" [argument "title"]'
            ),
            WORKSPACE.replace('[literal "open"]', "[row-key]"),
            WORKSPACE.replace('[named "created"', '[named "insert"'),
        ]
        for source in mutants:
            with self.subTest(source=source), self.assertRaises(OperationError):
                evaluate(
                    source,
                    [
                        req(
                            "create",
                            {"actor": "a", "id": "i", "title": "new"},
                            ACCOUNTS,
                        )
                    ],
                )
        with self.assertRaisesRegex(OperationError, "fuel"):
            evaluate(WORKSPACE, [req("delete-account", {"actor": "a"}, ITEMS)], fuel=1)

    def test_unknown_workflow_exhausts_declared_choices(self):
        calls = [
            {
                "command": "close",
                "args": {"actor": "a", "id": "i"},
                "outcome": "unknown",
            }
        ]
        graph = explore(WORKSPACE, ITEMS, calls, depth=2)
        self.assertEqual(len(graph["nodes"]), 5)
        self.assertEqual(len(graph["edges"]), 3)
        self.assertEqual(graph["edges"][0]["to"], [1, 2])
        self.assertEqual(graph["edges"][2]["effects"], [[], []])
        with self.assertRaisesRegex(OperationError, "budget"):
            explore(WORKSPACE, ITEMS, calls, depth=2, max_nodes=2)

    def test_certificate_recheck_and_claim_judge(self):
        from capcov.claims.validation import validate_bundle
        from capcov.claims.evaluator import evaluate as judge

        good = req(
            "close",
            {"actor": "a", "id": "i"},
            ITEMS,
            "aborted",
            observed={"state": ITEMS, "effects": []},
        )
        bad = copy.deepcopy(good)
        bad["observed"]["effects"] = [["emit", "invented", "i"]]
        unknown = copy.deepcopy(good)
        del unknown["observed"]
        cert = certify(WORKSPACE, [good, bad, unknown])
        self.assertTrue(recheck(WORKSPACE, cert))
        bundle = claim_bundle(WORKSPACE, cert)
        self.assertFalse(validate_bundle(bundle), validate_bundle(bundle))
        answer = judge(bundle)
        self.assertEqual(answer.status.value, "complete")
        self.assertTrue(answer.claims[0].result.support)
        self.assertTrue(answer.claims[1].result.refutation)
        self.assertFalse(answer.claims[2].result.support)
        forged = copy.deepcopy(cert)
        forged["evaluation"]["results"][1]["observed_matches"] = True
        forged["sha256"] = digest({k: v for k, v in forged.items() if k != "sha256"})
        with self.assertRaisesRegex(OperationError, "reproduction"):
            recheck(WORKSPACE, forged)

    def test_model_comparison_and_trace_tampering(self):
        call = req("close", {"actor": "a", "id": "i"}, ITEMS)
        mutant = WORKSPACE.replace('"item-closed"', '"wrong-event"')
        difference = compare_models(WORKSPACE, mutant, [call])
        self.assertEqual(len(difference["differences"]), 1)
        r = difference["left"]["results"][0]["transition"]
        call["trace"] = {
            "state": json_state(r[1]),
            "effects": r[2],
            "steps": [{"name": s[1], "effects": s[2]} for s in r[3]],
        }
        good = copy.deepcopy(call)
        call["trace"]["steps"][0]["name"] = "forged"
        results = evaluate(WORKSPACE, [good, call])["results"]
        self.assertEqual([r["trace_valid"] for r in results], [True, False])

    def test_postcondition_conservation_and_integer_overflow(self):
        mutant = LEDGER.replace(
            '[int-add [lookup "wallet" [argument "to"] "balance"] [argument "amount"]]',
            '[lookup "wallet" [argument "to"] "balance"]',
        )
        result = evaluate(mutant, [transfer()])["results"][0]
        self.assertEqual(result["transition"], ["rejected", "invariant"])
        with self.assertRaisesRegex(OperationError, "overflow"):
            evaluate(
                LEDGER,
                [
                    transfer(
                        state=[WALLETS[0], row("wallet", "b", balance="2147483647")]
                    )
                ],
            )

    def test_split_workflow_exposes_duplicate_send_after_missing_ack(self):
        source = (FIXTURE / "outbox.ops").read_text()
        state = [row("job", "j", status="pending", payload="hello")]
        send = {"command": "send", "args": {"id": "j"}, "outcome": "committed"}
        ack = {"command": "ack", "args": {"id": "j"}, "outcome": "committed"}
        graph = explore(
            source, state, [send, ack], depth=3, schedule=[[send], [send], [ack]]
        )
        self.assertEqual(
            [e["effects"] for e in graph["edges"]],
            [
                [[["emit", "delivery-attempt", "hello"]]],
                [[["emit", "delivery-attempt", "hello"]]],
                [[["put", "job", "j", "status", "sent"]]],
            ],
        )
        self.assertEqual(graph["nodes"][-1]["state"][0]["fields"]["status"], "sent")
        denied = req(
            "send",
            {"id": "j"},
            graph["nodes"][-1]["state"],
            "rejected",
            observed={"state": graph["nodes"][-1]["state"], "effects": []},
        )
        self.assertTrue(evaluate(source, [denied])["results"][0]["observed_matches"])

    def test_external_adapter_passes_and_mutant_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = Path(tmp) / "adapter.py"
            adapter.write_text(
                'import json,sys\nr=json.load(sys.stdin)["request"]\nprint(json.dumps({"state":r["state"],"effects":[]}))\n'
            )
            call = req("close", {"actor": "a", "id": "i"}, ITEMS, "aborted")
            report = run_adapter(WORKSPACE, [call], [sys.executable, str(adapter)])
            self.assertTrue(report["matches"])
            call["outcome"] = "committed"
            self.assertFalse(
                run_adapter(WORKSPACE, [call], [sys.executable, str(adapter)])[
                    "matches"
                ]
            )

    def test_cli_returns_nonzero_on_disagreement(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "requests.json"
            p.write_text(
                json.dumps(
                    [
                        req(
                            "close",
                            {"actor": "a", "id": "i"},
                            ITEMS,
                            "aborted",
                            observed={
                                "state": ITEMS,
                                "effects": [["emit", "bad", "i"]],
                            },
                        )
                    ]
                )
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "capcov.operations.system",
                    "evaluate",
                    "--spec",
                    str(FIXTURE / "workspace.ops"),
                    "--input",
                    str(p),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertFalse(
                json.loads(result.stdout)["results"][0]["observed_matches"]
            )
