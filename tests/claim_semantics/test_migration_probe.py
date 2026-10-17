"""R10 probe: a worked outbox migration model on the CURRENT system IR.

Legacy model: fixtures/systems/outbox.ops. Intended model:
fixtures/systems/outbox-intended.ops (idempotent send). Decision record:
fixtures/systems/outbox-migration-decision.json (a probe fixture, not a schema).

Every result this module produces names its executor class: "model" (the Shen
system evaluator over a .ops model) or "fake" (scenario-adapter.py, a synthetic
Python stand-in). The fake is never a legacy implementation.

Outcomes use the capcov.faults vocabulary (ok / fail / info, docs/faults.md);
OUTCOME maps it onto the system IR's request alphabet (system.py:127), where
`info` is spelled `unknown`. Violations reuse the faults invariant names
(effect_applied_twice, unresolved).

Cases the current IR cannot express are `unittest.expectedFailure` tests whose
docstrings name the missing IR feature with file:line. They are the input to
the IR specification (plan PR-5); each flips to an unexpected success, which
fails the run, when its constructor lands. README.md, "R10 probe", tabulates
them.
"""

from collections import Counter
import copy
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from capcov.faults.history import Result
from capcov.operations import OperationError
from capcov.operations.scenarios import _payload
from capcov.operations.system import _effect_terms, _request, _term, digest

FIXTURE = Path(__file__).parent / "fixtures/systems"
LEGACY = (FIXTURE / "outbox.ops").read_text()
INTENDED = (FIXTURE / "outbox-intended.ops").read_text()
LEDGER = (FIXTURE / "ledger.ops").read_text()
DECISION = json.loads((FIXTURE / "outbox-migration-decision.json").read_text())
FAKE = FIXTURE / "scenario-adapter.py"
NATIVE = bool(shutil.which("bifrost") and os.environ.get("BIFROST_SHEN_GO"))
if os.environ.get("CAPCOV_SHEN_REQUIRED") and not NATIVE:
    raise RuntimeError("migration probe model tests require native Shen")

OUTCOME = {Result.OK: "committed", Result.FAIL: "aborted", Result.INFO: "unknown"}
EXECUTORS = frozenset({"model", "fake"})
LEGACY_CLAUSE = "outbox.send.redelivers-while-pending"
INTENDED_CLAUSE = "outbox.send.at-most-once-delivery-per-job"
DELIVERY = "delivery-attempt"

# The intended model's idempotency guard. Dropping it is the target mutant.
GUARD = '[choose [equal [lookup "job" [argument "id"] "status"] [literal "attempted"]]'
GUARD_THEN = GUARD + "\n     []"
PUBLISH = '[publish "delivery-attempt" [lookup "job" [argument "id"] "payload"]]'


def mutate(source, old, new):
    if source.count(old) != 1:
        raise AssertionError(f"mutation site must occur exactly once: {old!r}")
    return source.replace(old, new)


# Target mutant: the dedupe guard never fires, so a retry publishes again.
GUARD_DROPPED = mutate(INTENDED, GUARD, "[choose [no]")
# M2: dedupe by payload instead of by job (intent): a second job whose payload
# equals an attempted job's is marked attempted without being delivered.
PAYLOAD_DEDUPE = mutate(
    INTENDED,
    GUARD_THEN,
    '[choose [some-row "job" [both [equal [row-field "payload"] '
    '[lookup "job" [argument "id"] "payload"]] '
    '[equal [row-field "status"] [literal "attempted"]]]]\n'
    '     [[named "mark-duplicate" [update "job" [argument "id"] "status" '
    '[literal "attempted"]]]]',
)
# Delivers job j's message for whichever job is sent: j twice, k never.
WRONG_INTENT = mutate(
    INTENDED, PUBLISH, '[publish "delivery-attempt" [lookup "job" [literal "j"] "payload"]]'
)


def row(t, k, **fields):
    return {"table": t, "key": k, "fields": fields}


INITIAL = [row("job", "j", status="pending", payload="hello")]
TWO_JOBS = INITIAL + [row("job", "k", status="pending", payload="hello")]


def call(command, result=Result.OK, job="j"):
    return {"command": command, "args": {"id": job}, "outcome": OUTCOME[result]}


def result(executor, subject, verdict, **detail):
    """One probe result. The executor class is mandatory and closed."""
    if executor not in EXECUTORS:
        raise ValueError(f"executor class must be model or fake, not {executor!r}")
    return {"executor": executor, "subject": subject, "verdict": verdict, **detail}


def histories(graph):
    """Every admissible full-depth history of an explore graph, as per-step effects."""
    by_from = {}
    for edge in graph["edges"]:
        by_from.setdefault(edge["from"], []).append(edge)
    found = []

    def walk(node, level, steps):
        if level == graph["depth"]:
            found.append(steps)
            return
        for edge in by_from.get(node, []):
            for to, effects in zip(edge["to"], edge["effects"]):
                walk(to, level + 1, steps + [effects])

    walk(0, 0, [])
    return found


def deliveries(history, kind=DELIVERY):
    """Delivery attempts per payload. The IR has no intent id (system.py:100)."""
    return Counter(e[2] for step in history for e in step if e[:2] == ["emit", kind])


def at_most_once(executor, subject, runs, scope=None):
    """Clause INTENDED_CLAUSE over every history: no payload delivered twice."""
    counts = [deliveries(h) for h in runs]
    twice = [h for h, c in zip(runs, counts) if any(n > 1 for n in c.values())]
    return result(
        executor,
        subject,
        "violated" if twice else "satisfied",
        clause=INTENDED_CLAUSE,
        invariant="effect_applied_twice" if twice else None,
        histories=len(runs),
        witness=twice[0] if twice else None,
        scope=scope,
    )


def decision_problems(decision):
    """Why a decision record cannot accept a difference; [] when it can."""
    if not isinstance(decision, dict):
        return ["no migration decision"]
    problems = []
    if decision.get("kind") != "change":
        problems.append("decision kind is not change")
    if (decision.get("legacy") or {}).get("clause") != LEGACY_CLAUSE:
        problems.append("decision is not bound to the legacy clause")
    if (decision.get("intended") or {}).get("clause") != INTENDED_CLAUSE:
        problems.append("decision is not bound to the intended clause")
    if not isinstance(decision.get("scope"), dict) or not decision["scope"].get("schedule"):
        problems.append("decision has no observation scope")
    if not isinstance(decision.get("rationale"), str) or not decision["rationale"].strip():
        problems.append("decision has no rationale")
    approval = decision.get("approval")
    approver = approval.get("approver") if isinstance(approval, dict) else None
    date = approval.get("date") if isinstance(approval, dict) else None
    if not isinstance(approver, str) or not approver.strip():
        problems.append("approval provenance has no approver")
    try:
        datetime.date.fromisoformat(date)
    except (TypeError, ValueError):
        problems.append("approval provenance has no ISO date")
    obligation = decision.get("obligation")
    if not isinstance(obligation, dict) or not obligation.get("id") or not obligation.get("checks"):
        problems.append("decision has no replacement obligation")
    return problems


def judge_difference(decision, legacy, target, checks):
    """accepted | open | rejected | no-difference for one legacy/target pair.

    A target that violates the intended clause is rejected even when legacy
    violates it too: agreement on a violation is still reported.
    """
    for evidence in (legacy, target):
        if evidence["executor"] not in EXECUTORS:
            raise ValueError("evidence without an executor class")
    if target["verdict"] != "satisfied":
        return {"status": "rejected", "legacy_agrees": legacy["verdict"] != "satisfied"}
    if legacy["verdict"] == "satisfied":
        return {"status": "no-difference"}
    reasons = decision_problems(decision)
    if not reasons:
        scope = digest(decision["scope"])
        if legacy["scope"] != scope or target["scope"] != scope:
            reasons.append("evidence is outside the decision's observation scope")
        for check in decision["obligation"]["checks"]:
            if checks.get(check) is not True:
                reasons.append(f"obligation check not passed: {check}")
    if reasons:
        return {"status": "open", "reasons": reasons}
    return {"status": "accepted", "decision": decision["id"]}


def scope_schedule(scope):
    return [
        [dict(command=c["command"], args=c["args"], outcome=OUTCOME[Result(c["result"])])
         for c in level]
        for level in scope["schedule"]
    ]


def run_fake(steps, mutant=False, initial=INITIAL):
    """Run scenario-adapter.py (executor class: fake) on a choice tape."""
    payload = _payload({"initial": initial, "steps": steps}, 1024)
    done = subprocess.run(
        [sys.executable, str(FAKE)] + (["--mutant"] if mutant else []),
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return payload, json.loads(done.stdout)


def fake_history(response):
    return [o["effects"] for o in response["observations"]]


class MigrationDecisionRecordTests(unittest.TestCase):
    """The decision record alone; no executor runs here."""

    def test_fixture_is_bound_and_approved(self):
        self.assertEqual(decision_problems(DECISION), [])
        self.assertIn("NOT a schema commitment", DECISION["_note"])
        self.assertEqual(DECISION["legacy"]["model"], "outbox.ops")
        self.assertEqual(DECISION["intended"]["model"], "outbox-intended.ops")
        self.assertEqual(
            [[c["result"] for c in level] for level in DECISION["scope"]["schedule"]],
            [["info"], ["ok"], ["ok"]],
        )

    def test_m5_missing_approval_provenance_keeps_the_decision_open(self):
        variants = []
        for edit in (
            lambda d: d.pop("approval"),
            lambda d: d["approval"].pop("approver"),
            lambda d: d["approval"].update(approver="  "),
            lambda d: d["approval"].pop("date"),
            lambda d: d["approval"].update(date="last week"),
        ):
            d = copy.deepcopy(DECISION)
            edit(d)
            variants.append(d)
        for d in variants:
            with self.subTest(approval=d.get("approval")):
                self.assertTrue(
                    any(p.startswith("approval provenance") for p in decision_problems(d))
                )

    def test_decision_must_bind_kind_clauses_scope_and_obligation(self):
        self.assertEqual(decision_problems(None), ["no migration decision"])
        for key, value in (
            ("kind", "keep"),
            ("legacy", {"clause": "other"}),
            ("intended", {"clause": "other"}),
            ("scope", {}),
            ("obligation", {"id": "x", "checks": []}),
        ):
            d = dict(DECISION, **{key: value})
            with self.subTest(key=key):
                self.assertTrue(decision_problems(d))

    def test_every_result_names_a_model_or_fake_executor(self):
        self.assertEqual(result("fake", "s", "satisfied")["executor"], "fake")
        for wrong in ("legacy implementation", "real-service", None):
            with self.subTest(executor=wrong), self.assertRaises(ValueError):
                result(wrong, "s", "satisfied")


class FakeExecutorTests(unittest.TestCase):
    """scenario-adapter.py is executor class "fake"; runs without Shen."""

    def test_m1_fake_double_delivery_on_ok_violates_the_intended_clause(self):
        steps = [{"call": call("send"), "choice": "0"}]
        _, honest = run_fake(steps)
        _, mutant = run_fake(steps, mutant=True)
        good = at_most_once("fake", "scenario-adapter.py", [fake_history(honest)])
        bad = at_most_once("fake", "scenario-adapter.py --mutant", [fake_history(mutant)])
        self.assertEqual((good["executor"], good["verdict"]), ("fake", "satisfied"))
        self.assertEqual((bad["executor"], bad["verdict"]), ("fake", "violated"))
        self.assertEqual(bad["invariant"], "effect_applied_twice")
        self.assertEqual(bad["witness"], [[["emit", DELIVERY, "hello"]] * 2])

    def test_h1_truth_two_deliveries_from_the_fake(self):
        """send->info (lands); send->ok; ack->ok: the fake delivers twice."""
        steps = [
            {"call": call("send", Result.INFO), "choice": "1"},
            {"call": call("send"), "choice": "0"},
            {"call": call("ack"), "choice": "0"},
        ]
        _, response = run_fake(steps)
        verdict = at_most_once("fake", "scenario-adapter.py", [fake_history(response)])
        self.assertEqual(verdict["verdict"], "violated")
        self.assertEqual(verdict["executor"], "fake")

    def test_harness_negative_info_resolution_is_part_of_the_history_input(self):
        """Same calls, different info resolution: different input, different history."""
        steps = [
            {"call": call("send", Result.INFO), "choice": "0"},
            {"call": call("send"), "choice": "0"},
        ]
        landed = copy.deepcopy(steps)
        landed[0]["choice"] = "1"
        a, ra = run_fake(steps)
        b, rb = run_fake(landed)
        self.assertNotEqual(digest(a), digest(b))
        self.assertNotEqual(ra["observations"], rb["observations"])
        self.assertEqual(ra["choices"], ["0", "0"])
        self.assertEqual(rb["choices"], ["1", "0"])


class InexpressibleFrontEndTests(unittest.TestCase):
    """IR gaps visible at the Python front end (system.py); no Shen needed."""

    @unittest.expectedFailure
    def test_h4_missing_journal_range_is_unresolved(self):
        """H4: a missing journal range must make the step unresolved.

        Missing: a way to say "effects seq 2..3 were not observed". An
        observation is exactly {state, effects} (system.py:132, also
        scenarios.py:100) and caps.accepts? matches the whole effect list
        (system.shen:168-169). The only encodings are a complete list, or []
        which means "no effects" and so passes the aborted alternative of an
        info send (system.shen:164-166) instead of staying unresolved.
        """
        observed = {
            "state": INITIAL,
            "effects": [],
            "journal": {"missing": [[2, 3]]},
        }
        try:
            _request(dict(call("send", Result.INFO), state=INITIAL, observed=observed), 1024)
        except OperationError as exc:
            self.fail(f"IR cannot express a missing journal range: {exc}")

    @unittest.expectedFailure
    def test_effects_carry_intent_and_attempt_identity(self):
        """Effects must carry (intent-id, attempt-id, logical-effect).

        Missing: effect identity. An effect is [emit Kind Value] /
        [put T K F V] / [create ...] / [delete T K] with fixed arity
        (system.py:100-104; produced by system.shen:67 for publish). So a
        duplicate can only be "two equal payloads" (plan §2.2), not "two
        delivered attempts of one intent".
        """
        effect = ["emit", DELIVERY, "hello", {"intent": "j", "attempt": "1"}]
        try:
            _effect_terms([effect])
        except OperationError as exc:
            self.fail(f"IR cannot express intent/attempt identity: {exc}")

    @unittest.expectedFailure
    def test_outbox_record_and_delivery_attempt_are_separate_constructors(self):
        """publish must split into an outbox record and a delivery attempt.

        Missing: constructors for a transactional outbox record and an
        external, at-least-once delivery attempt. The only one is
        [publish Kind V] (system-types.shen:59-61), evaluated inside the
        command's transaction (system.shen:67), and the front end rejects any
        other tag (system.py:24-26).
        """
        source = (
            '[system "split" [[table "job" ["payload"] [] []]]'
            ' [[command "send" ["id"] [exists "job" [argument "id"]]'
            ' [[named "record" [outbox "delivery-attempt" [argument "id"]]]'
            '  [named "deliver" [deliver "delivery-attempt" [argument "id"]]]]'
            ' [yes]]] []]'
        )
        try:
            _term(source)
        except OperationError as exc:
            self.fail(f"IR cannot express the outbox/delivery split: {exc}")


@unittest.skipUnless(NATIVE, "real pinned Shen runtime required")
class MigrationProbeModelTests(unittest.TestCase):
    """Executor class "model": the Shen system evaluator over .ops models."""

    @classmethod
    def setUpClass(cls):
        from capcov.operations.system import explore

        cls.explore = staticmethod(explore)

    def model_runs(self, source, initial, schedule):
        calls = []
        for level in schedule:
            for c in level:
                if c not in calls:
                    calls.append(c)
        graph = self.explore(source, initial, calls, depth=len(schedule), schedule=schedule)
        return graph, histories(graph)

    def scope_evidence(self, source, subject):
        scope = DECISION["scope"]
        _, runs = self.model_runs(source, scope["initial"], scope_schedule(scope))
        return at_most_once("model", subject, runs, scope=digest(scope))

    def test_legacy_explores_to_duplicate_delivery_attempt(self):
        schedule = [[call("send")], [call("send")], [call("ack")]]
        _, runs = self.model_runs(LEGACY, INITIAL, schedule)
        verdict = at_most_once("model", "outbox.ops", runs)
        self.assertEqual((verdict["executor"], verdict["verdict"]), ("model", "violated"))
        self.assertEqual(verdict["invariant"], "effect_applied_twice")

    def test_intended_does_not_deliver_twice(self):
        schedule = [[call("send")], [call("send")], [call("ack")]]
        _, runs = self.model_runs(INTENDED, INITIAL, schedule)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0][1], [])
        verdict = at_most_once("model", "outbox-intended.ops", runs)
        self.assertEqual((verdict["executor"], verdict["verdict"]), ("model", "satisfied"))

    def test_guard_dropping_target_mutant_is_rejected(self):
        legacy = self.scope_evidence(LEGACY, "outbox.ops")
        mutant = self.scope_evidence(GUARD_DROPPED, "outbox-intended.ops guard dropped")
        self.assertEqual(mutant["verdict"], "violated")
        judged = judge_difference(DECISION, legacy, mutant, {})
        self.assertEqual(judged, {"status": "rejected", "legacy_agrees": True})

    def test_difference_accepted_only_with_an_approved_decision(self):
        legacy = self.scope_evidence(LEGACY, "outbox.ops")
        target = self.scope_evidence(INTENDED, "outbox-intended.ops")
        mutant = self.scope_evidence(GUARD_DROPPED, "outbox-intended.ops guard dropped")
        self.assertEqual([legacy["verdict"], target["verdict"]], ["violated", "satisfied"])
        checks = {
            "legacy-counterexample-violates-intended": legacy["verdict"] == "violated",
            "target-satisfies-intended": target["verdict"] == "satisfied",
            "guard-dropping-mutant-rejected": mutant["verdict"] == "violated",
        }
        accepted = judge_difference(DECISION, legacy, target, checks)
        self.assertEqual(accepted, {"status": "accepted", "decision": DECISION["id"]})
        self.assertEqual(judge_difference(None, legacy, target, checks)["status"], "open")
        unapproved = copy.deepcopy(DECISION)
        del unapproved["approval"]  # M5
        m5 = judge_difference(unapproved, legacy, target, checks)
        self.assertEqual(m5["status"], "open")
        self.assertIn("approval provenance has no approver", m5["reasons"])
        unchecked = dict(checks, **{"guard-dropping-mutant-rejected": False})
        self.assertEqual(judge_difference(DECISION, legacy, target, unchecked)["status"], "open")
        elsewhere = dict(target, scope=digest({"other": "scope"}))
        self.assertEqual(judge_difference(DECISION, legacy, elsewhere, checks)["status"], "open")

    def test_h1_info_then_ok_retry_two_deliveries(self):
        """H1: send->info; send->ok; ack->ok, truth = 2 deliveries.

        Legacy admits the two-delivery history (a finding against the
        intended clause); intended admits no history with two deliveries, so
        that truth is a violation. Holds under the atomic-publish assumption
        (system.shen:165): an info send has two alternatives only.
        """
        schedule = scope_schedule(DECISION["scope"])
        truth = [[["emit", DELIVERY, "hello"]], [["emit", DELIVERY, "hello"]]]
        _, legacy = self.model_runs(LEGACY, INITIAL, schedule)
        self.assertIn(truth, [h[:2] for h in legacy])
        self.assertEqual(at_most_once("model", "outbox.ops", legacy)["verdict"], "violated")
        _, intended = self.model_runs(INTENDED, INITIAL, schedule)
        self.assertTrue(intended)
        self.assertEqual(
            {max(deliveries(h).values(), default=0) for h in intended}, {1}
        )
        self.assertNotIn(truth, [[[e for e in s if e[0] == "emit"] for s in h[:2]] for h in intended])

    def test_h2_info_then_ok_retry_one_delivery_keeps_alternatives(self):
        """H2: same calls, truth = 1 delivery: passes; both resolutions retained."""
        schedule = scope_schedule(DECISION["scope"])
        graph, runs = self.model_runs(INTENDED, INITIAL, schedule)
        self.assertEqual(len(graph["edges"][0]["to"]), 2)
        self.assertEqual(len({n["id"] for n in graph["nodes"] if n["depth"] == 1}), 2)
        emits = sorted(
            [len([e for e in step if e[0] == "emit"]) for step in h[:2]] for h in runs
        )
        self.assertEqual(emits, [[0, 1], [1, 0]])
        verdict = at_most_once("model", "outbox-intended.ops", runs)
        self.assertEqual(verdict["verdict"], "satisfied")

    def test_h5_same_idempotency_key_different_amount_conflicts_without_debit(self):
        from capcov.operations.system import evaluate, wire_state

        after = [
            row("wallet", "a", balance="7"),
            row("wallet", "b", balance="5"),
            row("transfer", "r", **{"from": "a", "to": "b", "amount": "3"}),
        ]
        debited = copy.deepcopy(after)
        debited[0]["fields"]["balance"] = "3"
        args = {"from": "a", "to": "b", "amount": "4", "request": "r"}

        def transfer(outcome, observed=None):
            r = {"command": "transfer", "args": args, "state": after, "outcome": outcome}
            if observed is not None:
                r["observed"] = {"state": observed, "effects": []}
            return r

        results = evaluate(
            LEDGER,
            [transfer("rejected", after), transfer("rejected", debited), transfer("committed")],
        )["results"]
        self.assertEqual(results[0]["transition"], ["rejected", "idempotency-conflict"])
        self.assertEqual(results[0]["admissible"], [["result", wire_state(after), [], []]])
        self.assertEqual([r["observed_matches"] for r in results[:2]], [True, False])
        self.assertEqual(results[2]["admissible"], [])

    def test_m1_fake_double_delivery_is_rejected_by_the_legacy_model(self):
        from capcov.operations.scenarios import run_scenario

        scenario = {"initial": INITIAL, "steps": [{"call": call("send"), "choice": "0"}]}
        honest = run_scenario(LEGACY, scenario, [sys.executable, str(FAKE)])
        mutant = run_scenario(LEGACY, scenario, [sys.executable, str(FAKE), "--mutant"])
        self.assertEqual(honest["mismatches"], [])
        self.assertEqual(mutant["mismatches"], [0])

    def test_m2_payload_dedupe_loses_an_effect(self):
        schedule = [[call("send", job="j")], [call("send", job="k")]]
        _, good = self.model_runs(INTENDED, TWO_JOBS, schedule)
        _, bad = self.model_runs(PAYLOAD_DEDUPE, TWO_JOBS, schedule)
        self.assertEqual([sum(deliveries(h).values()) for h in good], [2])
        self.assertEqual([sum(deliveries(h).values()) for h in bad], [1])
        lost = result("model", "payload-dedupe mutant", "violated", invariant="lost_effect")
        self.assertEqual(lost["executor"], "model")

    def test_m3_reporting_ok_for_an_info_send_is_rejected(self):
        """An info send that never landed, recorded as ok, contradicts the model."""
        from capcov.operations.system import evaluate

        nothing = {"state": INITIAL, "effects": []}
        results = evaluate(
            LEGACY,
            [
                dict(call("send", Result.OK), state=INITIAL, observed=nothing),
                dict(call("send", Result.INFO), state=INITIAL, observed=nothing),
            ],
        )["results"]
        self.assertEqual([r["observed_matches"] for r in results], [False, True])

    def test_harness_negative_different_info_resolution_is_a_different_history(self):
        from capcov.operations.scenarios import run_scenario

        steps = [
            {"call": call("send", Result.INFO), "choice": "0"},
            {"call": call("send"), "choice": "0"},
        ]
        landed = copy.deepcopy(steps)
        landed[0]["choice"] = "1"
        fake = [sys.executable, str(FAKE)]
        a = run_scenario(LEGACY, {"initial": INITIAL, "steps": steps}, fake)
        b = run_scenario(LEGACY, {"initial": INITIAL, "steps": landed}, fake)
        self.assertEqual((a["mismatches"], b["mismatches"]), ([], []))
        self.assertNotEqual(a["sha256"], b["sha256"])
        # Each run's replay is of its own tape; one never stands as the other's replay.
        self.assertTrue(a["replay_matches"] and b["replay_matches"])
        self.assertEqual(a["replayed"]["choices"], ["0", "0"])
        self.assertEqual(b["replayed"]["choices"], ["1", "0"])
        self.assertNotEqual(a["observed"], b["replayed"])

    def test_ledger_conservation_is_a_per_transition_bounded_check_not_a_proof(self):
        from capcov.operations.system import argument_domain

        wallets = [row("wallet", "a", balance="10"), row("wallet", "b", balance="2")]
        calls = argument_domain(
            "transfer",
            {"from": ["a", "b"], "to": ["a", "b"], "amount": ["1", "3"], "request": ["r", "s"]},
        )
        graph = self.explore(LEDGER, wallets, calls, depth=2)
        checked = result(
            "model",
            "ledger.ops",
            "no-violation-within-bound" if not graph["invariant_violations"] else "violated",
            basis=graph["basis"],
            evidence="per-transition bounded check of the transfer postcondition; not a proof (R12)",
        )
        self.assertEqual(checked["basis"], "explicit-bounded-domain")
        self.assertEqual(checked["verdict"], "no-violation-within-bound", graph["invariant_violations"])
        self.assertTrue(any(e["transition"][0] == "result" for e in graph["edges"]))
        mutant = LEDGER.replace(
            '[int-add [lookup "wallet" [argument "to"] "balance"] [argument "amount"]]',
            '[lookup "wallet" [argument "to"] "balance"]',
        )
        broken = self.explore(mutant, wallets, calls, depth=2)
        self.assertTrue(broken["invariant_violations"], "bounded check missed a non-conserving transfer")
        self.assertEqual(len(broken["shortest_invariant_witness"]), 1)


@unittest.skipUnless(NATIVE, "real pinned Shen runtime required")
class InexpressibleModelTests(unittest.TestCase):
    """IR gaps that need the evaluator to show; each is an expected failure."""

    @classmethod
    def setUpClass(cls):
        from capcov.operations.system import evaluate, explore

        cls.evaluate = staticmethod(evaluate)
        cls.explore = staticmethod(explore)

    @unittest.expectedFailure
    def test_info_send_has_at_least_three_alternatives(self):
        """An info send admits nothing / outbox-only / outbox+delivered.

        Missing: an outcome for info with more than two alternatives.
        caps.admissible maps unknown to exactly {before, after}
        (system.shen:165-166) because publish is part of the atomic
        transaction (system.shen:67), so "recorded in the outbox but not yet
        delivered" has no state. The tape choice is binary too
        (scenarios.py:56-57, adapters.py:63-64).
        """
        graph = self.explore(INTENDED, INITIAL, [call("send", Result.INFO)], depth=1)
        self.assertGreaterEqual(len(graph["edges"][0]["to"]), 3)

    @unittest.expectedFailure
    def test_h3_delivery_after_final_read_is_unresolved(self):
        """H3: send->info; ack->ok; final read; the delivery lands after it.

        Missing: info invocations that stay open until history close. An
        unknown outcome is resolved inside its own transition
        (system.shen:165-166; scenarios.py:125-126 fixes it to the tape
        branch), explore records no open invocations (system.py:451-466), and
        a request has no history-close/final-read marker (system.py:113-127).
        So the observed prefix "nothing yet" matches the aborted alternative
        and the step passes, where it must stay unresolved.
        """
        sent = [row("job", "j", status="sent", payload="hello")]
        results = self.evaluate(
            LEGACY,
            [
                dict(call("send", Result.INFO), state=INITIAL,
                     observed={"state": INITIAL, "effects": []}),
                dict(call("ack"), state=INITIAL,
                     observed={"state": sent, "effects": [["put", "job", "j", "status", "sent"]]}),
            ],
        )["results"]
        self.assertIsNot(results[0]["observed_matches"], True, "info send judged before close")

    @unittest.expectedFailure
    def test_m2_dedupe_by_intent_not_payload(self):
        """M2 (the inexpressible half): the clause must count per intent.

        Missing: intent identity on effects (system.py:100-104,
        system.shen:67). With two jobs carrying the same payload, the correct
        model's journal is two emits of "hello" -- indistinguishable from a
        mutant delivering job j twice and job k never. The payload-dedupe
        mutant that drops a delivery IS caught (MigrationProbeModelTests.
        test_m2_payload_dedupe_loses_an_effect) only because the count drops.
        """
        schedule = [[call("send", job="j")], [call("send", job="k")]]
        verdicts = []
        for source in (INTENDED, WRONG_INTENT):
            graph = self.explore(
                source, TWO_JOBS, [c for level in schedule for c in level],
                depth=2, schedule=schedule,
            )
            verdicts.append(at_most_once("model", "two jobs", histories(graph))["verdict"])
        self.assertEqual(verdicts, ["satisfied", "violated"])

    @unittest.expectedFailure
    def test_m4_adapter_that_normalizes_effects_to_a_set_is_rejected(self):
        """M4: an adapter that reports effects as a set hides M1.

        Missing: attempt identity. Two delivery attempts are equal tuples
        [emit delivery-attempt hello] (system.py:100-104), so set
        normalization collapses them and the observation matches the model
        (caps.accepts?, system.shen:168-169). With per-attempt ids they would
        stay distinct and the normalized report would be refused.
        """
        from capcov.operations.scenarios import run_scenario

        with tempfile.TemporaryDirectory() as tmp:
            wrapper = Path(tmp) / "set-adapter.py"
            wrapper.write_text(
                "import json, subprocess, sys\n"
                f"out = subprocess.run([sys.executable, {str(FAKE)!r}, '--mutant'],"
                " input=sys.stdin.read(), capture_output=True, text=True, check=True).stdout\n"
                "r = json.loads(out)\n"
                "for o in r['observations']:\n"
                "    seen = []\n"
                "    [seen.append(e) for e in o['effects'] if e not in seen]\n"
                "    o['effects'] = seen\n"
                "print(json.dumps(r))\n"
            )
            scenario = {"initial": INITIAL, "steps": [{"call": call("send"), "choice": "0"}]}
            report = run_scenario(LEGACY, scenario, [sys.executable, str(wrapper)])
        self.assertTrue(report["mismatches"], "set-normalized double delivery passed")


if __name__ == "__main__":
    unittest.main()
