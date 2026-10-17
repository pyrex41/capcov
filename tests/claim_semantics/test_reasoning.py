import copy
import itertools
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from capcov.operations import OperationError
from capcov.operations.compiler import compile_system, wp, Unresolved
from capcov.operations.evidence import extract, bind, invalidate, validate
from capcov.operations.native import invoke, term
from capcov.operations.proofs import prove, check, KERNEL
from capcov.operations.relations import compile_relation, solve
from capcov.operations.search import search
from capcov.operations.scenarios import run_scenario, minimize
from capcov.operations.system import digest
from capcov.operations.workbench import verify

FIXTURE = Path(__file__).parent / "fixtures/systems"
OUTBOX = (FIXTURE / "outbox.ops").read_text()
WORKSPACE = (FIXTURE / "workspace.ops").read_text()
ADAPTER = [sys.executable, str(FIXTURE / "scenario-adapter.py")]
INITIAL = [
    {"table": "job", "key": "j", "fields": {"status": "pending", "payload": "hello"}}
]
SEND = {"command": "send", "args": {"id": "j"}, "outcome": "committed"}
NATIVE = bool(shutil.which("bifrost") and os.environ.get("BIFROST_SHEN_GO"))
if os.environ.get("CAPCOV_SHEN_REQUIRED") and not NATIVE:
    raise RuntimeError("reasoning tests require native Shen")


def relation():
    return {
        "variables": {"x": "int32", "y": "int32", "z": "int32"},
        "inputs": ["x"],
        "outputs": ["y", "z"],
        "capabilities": ["tx"],
        "determinism": "multi",
        "body": [
            "all",
            [["domain", "y", ["1", "2"]], ["add", "x", "y", "z"], ["consume", "tx"]],
        ],
    }


class SourceEvidenceTests(unittest.TestCase):
    def test_go_and_php_source_anchors_use_bundled_grammars(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "app.go").write_text(
                "package app\nfunc Check(x int) bool { if x > 0 { return true }; return false }\n"
            )
            Path(tmp, "app.php").write_text(
                "<?php function check($x) { if ($x > 0) { return true; } return false; }"
            )
            inventory = extract(tmp, ["app.go", "app.php"])
            self.assertTrue(
                any(
                    a["kind"] == "if_statement" and a["path"] == "app.go"
                    for a in inventory["anchors"]
                )
            )
            self.assertTrue(
                any(
                    a["kind"] == "if_statement" and a["path"] == "app.php"
                    for a in inventory["anchors"]
                )
            )
            self.assertEqual(invalidate(tmp, inventory)["changed_sources"], [])

    def test_rehashed_fabricated_anchor_is_rejected_against_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.py").write_text("x = 1\n")
            inv = extract(tmp, ["a.py"])
            inv["anchors"][0]["kind"] = "Assert"
            inv["anchors"][0]["id"] = digest(
                {k: v for k, v in inv["anchors"][0].items() if k != "id"}
            )
            inv["sha256"] = digest({k: v for k, v in inv.items() if k != "sha256"})
            with self.assertRaisesRegex(OperationError, "reproduced"):
                invalidate(tmp, inv)

    def test_extraction_invalidation_dependency_closure_and_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.py"
            path.write_text("def transfer(x):\n    assert x > 0\n    return x\n")
            inv = extract(tmp, ["app.py"], revision="fixture")
            anchor = next(a for a in inv["anchors"] if a["kind"] == "Assert")
            self.assertEqual(anchor["start_line"], 2)
            claims = [
                {
                    "id": "guard",
                    "statement": "positive input",
                    "kind": "legacy",
                    "anchors": [anchor["id"]],
                    "depends_on": [],
                    "obligations": [],
                },
                {
                    "id": "caller",
                    "statement": "caller relies on guard",
                    "kind": "target",
                    "anchors": [],
                    "depends_on": ["guard"],
                    "obligations": [],
                },
            ]
            bundle = bind(
                inv,
                claims,
                [
                    {
                        "id": "g",
                        "question": "Should zero be accepted?",
                        "claims": ["guard"],
                    }
                ],
            )
            self.assertTrue(validate(bundle))
            self.assertEqual(invalidate(tmp, bundle)["stale_claims"], [])
            path.write_text(path.read_text().replace("> 0", ">= 0"))
            report = invalidate(tmp, bundle)
            self.assertEqual(report["stale_claims"], ["caller", "guard"])
            self.assertEqual(len(report["open_gaps"]), 1)
            claims[0]["depends_on"] = ["caller"]
            with self.assertRaisesRegex(OperationError, "cyclic"):
                bind(inv, claims)

    def test_path_escape_and_forged_anchor_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for p in ("../a.py", "/a.py", "a/../b.py"):
                with self.assertRaises(OperationError):
                    extract(tmp, [p])
            Path(tmp, "a.py").write_text("x = 1\n")
            inv = extract(tmp, ["a.py"])
            inv["anchors"][0]["text"] = "x = 2"
            inv["sha256"] = digest({k: v for k, v in inv.items() if k != "sha256"})
            with self.assertRaises(OperationError):
                validate(inv)

    def test_wp_refuses_mutable_keys_and_quantified_mutations(self):
        with self.assertRaises(Unresolved):
            wp(
                [
                    [
                        "named",
                        "x",
                        [
                            "update",
                            "t",
                            ["lookup", "t", ["argument", "k"], "id"],
                            "x",
                            ["literal", "1"],
                        ],
                    ]
                ],
                ["equal", ["lookup", "t", ["argument", "k"], "x"], ["literal", "1"]],
            )


@unittest.skipUnless(NATIVE, "requires native Shen")
class NativeReasoningTests(unittest.TestCase):
    def test_safety_reachability_and_antithesis_catalog_emission(self):
        from capcov.operations.properties import observe, publish

        malformed = [{"table": "unknown", "key": "x", "fields": {}}]
        report = observe(
            OUTBOX,
            [INITIAL, malformed],
            [{"id": "pending", "predicate": '[exists "job" [literal "j"]]'}],
        )
        self.assertEqual(report["observations"], [[True, True], [False, None]])
        events = []
        publish(report, sink=lambda **event: events.append(event))
        catalogs = [e for e in events if not e["hit"]]
        self.assertEqual(len(catalogs), 2)
        self.assertEqual({e["assert_type"] for e in catalogs}, {"always", "sometimes"})
        self.assertEqual(sum(e["hit"] for e in events), 3)
        for declaration in catalogs:
            self.assertTrue(
                all(
                    e["message"] == declaration["message"]
                    for e in events
                    if e["assert_id"] == declaration["assert_id"]
                )
            )

    def test_cli_exit_codes_preserve_open_and_operational_results(self):
        import contextlib
        import io
        from capcov.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "query.json")
            p.write_text(json.dumps({"left": [], "right": [["atom", "unproved"]]}))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["reason", "prove", "--input", str(p)]), 1)
            p.write_text(json.dumps({"left": [], "right": [["bogus"]]}))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["reason", "prove", "--input", str(p)]), 2)

    def test_typed_relation_generates_campaign_calls(self):
        program = {
            "variables": {"id": "text"},
            "inputs": [],
            "outputs": ["id"],
            "capabilities": [],
            "determinism": "det",
            "body": ["domain", "id", ["j"]],
        }
        calls = {
            "relation": program,
            "inputs": {},
            "command": "send",
            "outcome": "committed",
            "arguments": {"id": "id"},
        }
        report = search(
            OUTBOX, INITIAL, calls, {"emitted": "delivery-attempt", "count": 2}, depth=2
        )
        self.assertEqual(len(report["scenario"]["steps"]), 2)
        self.assertIsNotNone(report["generator"])

    def test_replay_detects_uncontrolled_state_and_adapter_receives_no_oracle(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = Path(tmp, "adapter.py")
            counter = Path(tmp, "counter")
            adapter.write_text(
                "import json,sys,pathlib\nr=json.load(sys.stdin)\n"
                'assert all(set(s)=={"call","choice"} for s in r["steps"])\n'
                f"p=pathlib.Path({str(counter)!r});n=int(p.read_text()) if p.exists() else 0;p.write_text(str(n+1))\n"
                'print(json.dumps({"protocol":r["protocol"],"choices":[s["choice"] for s in r["steps"]],'
                '"controls":[],"observations":[{"state":r["initial"],"effects":[["emit","delivery-attempt",str(n)]]} for s in r["steps"]]}))\n'
            )
            scenario = {
                "initial": INITIAL,
                "steps": [{"call": SEND, "choice": "0", "result": ["secret-oracle"]}],
            }
            report = run_scenario(OUTBOX, scenario, [sys.executable, str(adapter)])
            self.assertFalse(report["replay_matches"])

    def test_sequent_proofs_and_mutation_rejection(self):
        p, q = ["atom", "p"], ["atom", "q"]
        cases = [
            ([p], [p]),
            ([["and", p, q]], [p]),
            ([p], [["or", p, q]]),
            ([["or", p, q]], [["or", q, p]]),
            ([], [["or", p, ["not", p]]]),
            ([p, ["not", p]], [q]),
            ([["false"]], []),
            ([], [["true"]]),
        ]
        # Batch native queries keeps the entire logic corpus in one process.
        answers, _ = invoke(
            "[" + " ".join(f"(cv.prove {term(l)} {term(r)})" for l, r in cases) + "]",
            (*KERNEL, "proof-search.shen"),
        )
        self.assertTrue(all(a[0] == "proved" for a in answers))
        cert = prove([["and", p, q]], [p])
        self.assertTrue(check(cert, left=[["and", p, q]], right=[p]))
        cert["answer"][1][-1] = ["identity", q]
        cert["sha256"] = digest({k: v for k, v in cert.items() if k != "sha256"})
        self.assertFalse(check(cert))
        with self.assertRaisesRegex(OperationError, "obligation"):
            check(cert, right=[q])

    def test_search_agrees_with_independent_boolean_truth_tables(self):
        p, q = ["atom", "p"], ["atom", "q"]
        formulas = [
            p,
            q,
            ["not", p],
            ["and", p, q],
            ["or", p, q],
            ["or", ["not", p], q],
        ]

        def value(f, env):
            if f[0] == "atom":
                return env[f[1]]
            if f[0] == "not":
                return not value(f[1], env)
            if f[0] == "and":
                return value(f[1], env) and value(f[2], env)
            return value(f[1], env) or value(f[2], env)

        pairs = list(itertools.product(formulas, repeat=2))
        answers, _ = invoke(
            "["
            + " ".join(f"(cv.prove {term([a])} {term([b])})" for a, b in pairs)
            + "]",
            (*KERNEL, "proof-search.shen"),
        )
        for (a, b), answer in zip(pairs, answers):
            tautology = all(
                not value(a, dict(zip(("p", "q"), vs)))
                or value(b, dict(zip(("p", "q"), vs)))
                for vs in itertools.product((False, True), repeat=2)
            )
            self.assertEqual(answer[0] == "proved", tautology, (a, b))

    def test_compiler_proves_updates_but_preserves_open_obligations(self):
        result = compile_system(WORKSPACE)
        commands = {c["command"]: c for c in result["commands"]}
        self.assertTrue(
            all(o["status"] == "proved" for o in commands["rename"]["obligations"])
        )
        self.assertTrue(
            all(
                o["status"] == "proved"
                for c in result["commands"]
                for o in c["obligations"]
            )
        )
        ledger = compile_system((FIXTURE / "ledger.ops").read_text())
        self.assertEqual(ledger["commands"][0]["obligations"][0]["status"], "proved")
        self.assertEqual(ledger["commands"][0]["obligations"][1]["status"], "open")
        broken_ledger = (
            (FIXTURE / "ledger.ops")
            .read_text()
            .replace(
                '[int-add [lookup "wallet" [argument "to"] "balance"] [argument "amount"]]',
                '[lookup "wallet" [argument "to"] "balance"]',
            )
        )
        broken = compile_system(broken_ledger)
        self.assertEqual(broken["commands"][0]["obligations"][0]["status"], "open")
        mutant = WORKSPACE.replace(
            '["title" [argument "title"]]', '["title" [literal "wrong"]]'
        )
        result = compile_system(mutant)
        # Create only promises row existence; changing its title cannot refute it.
        self.assertEqual(result["commands"][0]["obligations"][0]["status"], "proved")
        mutant = WORKSPACE.replace(
            '"title" [argument "title"]]]]', '"title" [literal "wrong"]]]]'
        )
        result = compile_system(mutant)
        rename = next(c for c in result["commands"] if c["command"] == "rename")
        self.assertEqual(rename["obligations"][0]["status"], "open")

    def test_modes_cardinality_generation_and_capability_consumption(self):
        p = relation()
        c = compile_relation(p)
        self.assertEqual(c["remaining_capabilities"], [])
        self.assertEqual(c["minimum_solutions"], 2)
        r = solve(p, {"x": "3"})
        self.assertEqual([s["outputs"]["z"] for s in r["solutions"]], ["4", "5"])
        p["determinism"] = "det"
        with self.assertRaisesRegex(OperationError, "determinism"):
            compile_relation(p)
        p = relation()
        p["body"][1].append(["consume", "tx"])
        with self.assertRaisesRegex(OperationError, "consumed twice"):
            compile_relation(p)
        p = relation()
        p["body"][1][0], p["body"][1][1] = p["body"][1][1], p["body"][1][0]
        with self.assertRaisesRegex(OperationError, "ground"):
            compile_relation(p)

    def test_mode_branch_outputs_resources_and_numeric_sorts(self):
        p = relation()
        p["body"] = ["any", [["literal", "y", "1"], ["literal", "z", "2"]]]
        with self.assertRaisesRegex(OperationError, "ground"):
            compile_relation(p)
        p["body"] = ["any", [["consume", "tx"], ["all", []]]]
        with self.assertRaisesRegex(OperationError, "different capabilities"):
            compile_relation(p)
        p = relation()
        p["variables"]["x"] = "text"
        with self.assertRaisesRegex(OperationError, "int32"):
            compile_relation(p)
        with self.assertRaisesRegex(OperationError, "int32"):
            solve(relation(), {"x": "01"})

    def test_relational_search_reachability_history_and_budget(self):
        found = search(
            OUTBOX,
            INITIAL,
            [SEND],
            {"emitted": "delivery-attempt", "count": 2},
            depth=2,
        )
        self.assertEqual(len(found["scenario"]["steps"]), 2)
        self.assertEqual(
            search(
                OUTBOX,
                INITIAL,
                [SEND],
                {"emitted": "delivery-attempt", "count": 2},
                depth=1,
            )["status"],
            "exhausted-within-bounds",
        )
        with self.assertRaisesRegex(OperationError, "budget"):
            search(
                OUTBOX,
                INITIAL,
                [SEND],
                {"emitted": "delivery-attempt", "count": 3},
                depth=3,
                budget=1,
            )
        ack = {"command": "ack", "args": {"id": "j"}, "outcome": "committed"}
        reached = search(
            OUTBOX,
            INITIAL,
            [SEND, ack],
            {"state": '[equal [lookup "job" [literal "j"] "status"] [literal "sent"]]'},
            depth=2,
        )
        self.assertEqual(reached["scenario"]["steps"][0]["call"]["command"], "ack")

    def test_stateful_execution_replay_minimization_and_unknown_choice(self):
        scenario = {"initial": INITIAL, "steps": [{"call": SEND, "choice": "0"}] * 2}
        report = run_scenario(OUTBOX, scenario, ADAPTER)
        self.assertEqual(report["mismatches"], [])
        self.assertTrue(report["replay_matches"])
        mutant = minimize(OUTBOX, scenario, ADAPTER + ["--mutant"], max_runs=4)
        self.assertEqual(len(mutant["scenario"]["steps"]), 1)
        self.assertTrue(mutant["minimal_under_single_step_deletion"])
        unknown = copy.deepcopy(scenario)
        unknown["steps"][0] = {"call": dict(SEND, outcome="unknown"), "choice": "0"}
        report = run_scenario(OUTBOX, unknown, ADAPTER)
        self.assertEqual(report["observed"]["observations"][0]["effects"], [])
        self.assertEqual(report["mismatches"], [])

    def test_full_evidence_to_counterexample_pipeline(self):
        inv = extract(FIXTURE, ["scenario-adapter.py"])
        anchor = next(a for a in inv["anchors"] if a["kind"] == "FunctionDef")
        inv = bind(
            inv,
            [
                {
                    "id": "send",
                    "statement": "one intent per send",
                    "kind": "target",
                    "anchors": [anchor["id"]],
                    "depends_on": [],
                    "obligations": ["send:postcondition"],
                }
            ],
            [
                {
                    "id": "duplicate",
                    "question": "Can retry repeat delivery?",
                    "claims": ["send"],
                }
            ],
        )
        report = verify(
            OUTBOX,
            FIXTURE,
            inv,
            [
                {
                    "id": "retry",
                    "claims": ["send"],
                    "initial": INITIAL,
                    "calls": [SEND],
                    "goal": {"emitted": "delivery-attempt", "count": 2},
                    "depth": 2,
                }
            ],
            adapter=ADAPTER + ["--mutant"],
            minimize_runs=3,
        )
        self.assertEqual(report["claims"][0]["refuted_campaigns"], ["retry"])
        self.assertEqual(report["claims"][0]["gaps"], ["duplicate"])
        self.assertEqual(
            len(report["campaigns"][0]["minimized"]["scenario"]["steps"]), 1
        )


@unittest.skipUnless(shutil.which("souffle"), "requires Souffle")
class SouffleSourceTests(unittest.TestCase):
    def test_transitive_invalidation_agrees_with_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "app.py")
            path.write_text("x = 1\n")
            inventory = extract(tmp, ["app.py"])
            inventory = bind(
                inventory,
                [
                    {
                        "id": "root",
                        "statement": "assignment",
                        "kind": "legacy",
                        "anchors": [inventory["anchors"][0]["id"]],
                        "depends_on": [],
                        "obligations": [],
                    },
                    {
                        "id": "dependent",
                        "statement": "caller",
                        "kind": "target",
                        "anchors": [],
                        "depends_on": ["root"],
                        "obligations": [],
                    },
                ],
            )
            path.write_text("x = 2\n")
            self.assertEqual(
                invalidate(tmp, inventory, engine="souffle")["stale_claims"],
                ["dependent", "root"],
            )
