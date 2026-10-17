"""R10 probe: a worked outbox migration model on the CURRENT system IR.

Legacy model: fixtures/systems/outbox.ops. Intended model:
fixtures/systems/outbox-intended.ops (idempotent send). Decision record:
fixtures/systems/outbox-migration-decision.json (a probe fixture, not a schema).

Every result this module produces names its executor class: "model" (the Shen
system evaluator over a .ops model) or "fake" (scenario-adapter.py, a synthetic
Python stand-in). The fake is never a legacy implementation, and evidence from
it is never accepted as legacy evidence.

Outcomes use the capcov.faults vocabulary (ok / fail / info, docs/faults.md);
OUTCOME maps it onto the system IR's request alphabet (system.py:126-128),
where `info` is spelled `unknown`. Verdicts reuse the faults invariant names
(effect_applied_twice, unsettled_effect) and `unresolved`.

Cases the current IR cannot express are IR-gap tests: `unittest.expectedFailure`
methods of an `IRGapCase`. The expressible precondition of each runs in setUp
(a `given_*` method), where a failure or error is reported normally; only the
documented gap assertion runs under expectedFailure, and an OperationError
there is turned into a failure naming the gap. Docstrings name the missing IR
feature with file:line and what flips the test. They are the input to the IR
specification (plan PR-5); README.md, "R10 probe", tabulates them.
"""

from collections import Counter
from contextlib import contextmanager
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
SETTLED_CLAUSE = "outbox.send.every-sent-job-delivered"
DELIVERY = "delivery-attempt"
BOUNDED = "explicit-bounded-domain"
OBSERVED = "fake-observation"
GUARD_DROPPED_MODEL = DECISION["intended"]["model"] + "#guard-dropped"

# The intended model's idempotency guard. Dropping it is the target mutant.
GUARD = '[choose [equal [lookup "job" [argument "id"] "status"] [literal "attempted"]]'
GUARD_THEN = GUARD + "\n     []"
PUBLISH = '[publish "delivery-attempt" [lookup "job" [argument "id"] "payload"]]'
SEND_PRE = '[negate [equal [lookup "job" [argument "id"] "status"] [literal "sent"]]]'


def mutate(source, old, new):
    if source.count(old) != 1:
        raise AssertionError(f"mutation site must occur exactly once: {old!r}")
    return source.replace(old, new)


# Target mutant: the dedupe guard never fires, so a retry publishes again.
GUARD_DROPPED = mutate(INTENDED, GUARD, "[choose [no]")
# A target that rejects the retry instead of answering it idempotently.
RETRY_REJECTED = mutate(
    INTENDED,
    SEND_PRE,
    '[equal [lookup "job" [argument "id"] "status"] [literal "pending"]]',
)
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


def row(t, k, **fields):
    return {"table": t, "key": k, "fields": fields}


INITIAL = [row("job", "j", status="pending", payload="hello")]
ATTEMPTED = [row("job", "j", status="attempted", payload="hello")]
TWO_JOBS = INITIAL + [row("job", "k", status="pending", payload="hello")]
EMIT = ["emit", DELIVERY, "hello"]


def call(command, result=Result.OK, job="j"):
    return {"command": command, "args": {"id": job}, "outcome": OUTCOME[result]}


def result(executor, model, verdict, **detail):
    """One probe result. The executor class is mandatory and closed."""
    if executor not in EXECUTORS:
        raise ValueError(f"executor class must be model or fake, not {executor!r}")
    return {"executor": executor, "model": model, "verdict": verdict, **detail}


def histories(graph):
    """(complete, truncated) histories of an explore graph.

    complete: every full-depth history as per-step effect lists. truncated: the
    number of paths that end early, because a transition had no admissible
    alternative (edge "to" is empty) or because explore stopped when the
    frontier emptied (system.py:438-440). Truncated paths are never dropped
    silently: a verdict over them is reported, and a decision cannot accept.
    """
    by_from = {}
    for edge in graph["edges"]:
        by_from.setdefault(edge["from"], []).append(edge)
    complete, truncated = [], 0

    def walk(node, level, steps):
        nonlocal truncated
        if level == graph["depth"]:
            complete.append(steps)
            return
        edges = by_from.get(node, [])
        if not edges:
            truncated += 1
        for edge in edges:
            if not edge["to"]:
                truncated += 1
            for to, effects in zip(edge["to"], edge["effects"]):
                walk(to, level + 1, steps + [effects])

    walk(0, 0, [])
    return complete, truncated


def identity(effect):
    """The identity a delivery is counted by.

    An intent id when the effect carries one (the shape the IR-gap tests ask
    for); otherwise the payload, labelled as a fallback, because the current IR
    has no intent id on effects (system.py:100-104, system.shen:67).
    """
    if len(effect) > 3 and isinstance(effect[3], dict) and "intent" in effect[3]:
        return "intent", effect[3]["intent"]
    return "payload-fallback", effect[2]


def deliveries(history, kind=DELIVERY):
    return Counter(
        identity(e) for step in history for e in step if e[:2] == ["emit", kind]
    )


def at_most_once(
    executor, model, runs, *, truncated=0, scope=None, depth=None, basis=BOUNDED
):
    """INTENDED_CLAUSE over every history: no delivery identity counted twice.

    No complete history is "unresolved", never "satisfied".
    """
    twice = [h for h in runs if any(n > 1 for n in deliveries(h).values())]
    verdict = "unresolved" if not runs else "violated" if twice else "satisfied"
    keys = {k for h in runs for k, _ in deliveries(h)}
    return result(
        executor,
        model,
        verdict,
        clause=INTENDED_CLAUSE,
        invariant="effect_applied_twice" if twice else None,
        identity=sorted(keys),
        histories=len(runs),
        truncated=truncated,
        witness=twice[0] if twice else None,
        scope=scope,
        depth=depth,
        basis=basis,
    )


def every_send_delivered(executor, model, runs, jobs, *, truncated=0, depth=None):
    """SETTLED_CLAUSE: each sent job's delivery is attempted at least once.

    Counted as total deliveries against distinct jobs sent (payload fallback:
    no intent ids). A shortfall is the faults invariant unsettled_effect.
    """
    short = [h for h in runs if sum(deliveries(h).values()) < jobs]
    verdict = "unresolved" if not runs else "violated" if short else "satisfied"
    return result(
        executor,
        model,
        verdict,
        clause=SETTLED_CLAUSE,
        invariant="unsettled_effect" if short else None,
        histories=len(runs),
        truncated=truncated,
        witness=short[0] if short else None,
        depth=depth,
        basis=BOUNDED,
    )


def scope_key(initial, schedule):
    return digest({"initial": initial, "schedule": schedule})


def scope_schedule(scope):
    return [
        [
            dict(
                command=c["command"],
                args=c["args"],
                outcome=OUTCOME[Result(c["result"])],
            )
            for c in level
        ]
        for level in scope["schedule"]
    ]


def decision_scope_key(decision):
    return scope_key(decision["scope"]["initial"], scope_schedule(decision["scope"]))


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
    for side in ("legacy", "intended"):
        if not (decision.get(side) or {}).get("model"):
            problems.append(f"decision names no {side} model")
    scope = decision.get("scope")
    if (
        not isinstance(scope, dict)
        or not scope.get("schedule")
        or "initial" not in scope
    ):
        problems.append("decision has no observation scope")
    if (
        not isinstance(decision.get("rationale"), str)
        or not decision["rationale"].strip()
    ):
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
    if (
        not isinstance(obligation, dict)
        or not obligation.get("id")
        or not obligation.get("checks")
    ):
        problems.append("decision has no replacement obligation")
    return problems


def judge_difference(decision, legacy, target, mutant):
    """accepted | open | rejected for one legacy/target difference.

    A target that violates the intended clause is rejected, even when legacy
    violates it too: agreement on a violation is still reported. Acceptance
    needs an approved decision, and legacy, target and guard-dropped mutant
    evidence that each come from a model executor, evaluate the decision's
    intended clause on the model the decision names, cover the decision's
    observation scope (digest of the explored initial state and schedule) with
    at least one complete history and no truncated one. The obligation checks
    are computed here from that evidence, never supplied by the caller.
    """
    for evidence in (legacy, target, mutant):
        if evidence["executor"] not in EXECUTORS:
            raise ValueError("evidence without an executor class")
    if target["verdict"] == "violated":
        return {"status": "rejected", "legacy_agrees": legacy["verdict"] == "violated"}
    reasons = decision_problems(decision)
    if reasons:
        return {"status": "open", "reasons": reasons}
    scope = decision_scope_key(decision)
    expected = {
        "legacy": decision["legacy"]["model"],
        "target": decision["intended"]["model"],
        "mutant": decision["intended"]["model"] + "#guard-dropped",
    }
    for role, evidence in (("legacy", legacy), ("target", target), ("mutant", mutant)):
        if evidence["executor"] != "model":
            reasons.append(
                f"{role} evidence is from executor {evidence['executor']}, not model"
            )
        if evidence["clause"] != decision["intended"]["clause"]:
            reasons.append(f"{role} evidence evaluates another clause")
        if evidence["model"] != expected[role]:
            reasons.append(f"{role} evidence is not from {expected[role]}")
        if evidence["scope"] != scope:
            reasons.append(
                f"{role} evidence is outside the decision's observation scope"
            )
        if evidence["histories"] < 1 or evidence["truncated"]:
            reasons.append(
                f"{role} evidence does not cover the scope: {evidence['histories']} complete, "
                f"{evidence['truncated']} truncated histories"
            )
    if not reasons:
        computed = {
            "legacy-counterexample-violates-intended": legacy["verdict"] == "violated",
            "target-satisfies-intended": target["verdict"] == "satisfied",
            "guard-dropping-mutant-rejected": mutant["verdict"] == "violated",
        }
        for check in decision["obligation"]["checks"]:
            if computed.get(check) is not True:
                reasons.append(f"obligation check not passed: {check}")
    if reasons:
        return {"status": "open", "reasons": reasons}
    return {"status": "accepted", "decision": decision["id"]}


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


def fake_verdict(response, model):
    history = [o["effects"] for o in response["observations"]]
    return at_most_once("fake", model, [history], depth=len(history), basis=OBSERVED)


class IRGapCase(unittest.TestCase):
    """Base for IR-gap tests: preconditions in setUp, only the gap is expected to fail."""

    def setUp(self):
        name = self._testMethodName
        given = getattr(self, "given_" + name[len("test_") :], None)
        if given is None:
            raise AssertionError(f"IR-gap test {name} has no given_ precondition")
        try:
            self.given = given()
        except OperationError as exc:
            self.fail(
                f"expressible precondition failed (not the documented gap): {exc}"
            )

    @contextmanager
    def ir_gap(self, feature):
        try:
            yield
        except OperationError as exc:
            self.fail(f"IR gap, {feature}: {exc}")


class MigrationDecisionRecordTests(unittest.TestCase):
    """The decision record and the clause functions; no executor runs here."""

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
                    any(
                        p.startswith("approval provenance")
                        for p in decision_problems(d)
                    )
                )

    def test_decision_must_bind_kind_clauses_models_scope_and_obligation(self):
        self.assertEqual(decision_problems(None), ["no migration decision"])
        for key, value in (
            ("kind", "keep"),
            ("legacy", {"clause": "other", "model": "outbox.ops"}),
            ("legacy", {"clause": LEGACY_CLAUSE}),
            ("intended", {"clause": "other", "model": "outbox-intended.ops"}),
            ("scope", {}),
            ("obligation", {"id": "x", "checks": []}),
        ):
            d = dict(DECISION, **{key: value})
            with self.subTest(key=key, value=value):
                self.assertTrue(decision_problems(d))

    def test_every_result_names_a_model_or_fake_executor(self):
        self.assertEqual(result("fake", "s", "satisfied")["executor"], "fake")
        for wrong in ("legacy implementation", "real-service", None):
            with self.subTest(executor=wrong), self.assertRaises(ValueError):
                result(wrong, "s", "satisfied")

    def test_no_complete_history_is_unresolved_not_satisfied(self):
        verdict = at_most_once("model", "outbox-intended.ops", [], truncated=2, depth=3)
        self.assertEqual(verdict["verdict"], "unresolved")
        self.assertEqual(
            every_send_delivered("model", "m", [], 1)["verdict"], "unresolved"
        )

    def test_histories_report_truncated_paths(self):
        graph = {
            "depth": 2,
            "edges": [
                {"from": 0, "to": [1, 2], "effects": [[], [EMIT]]},
                {"from": 1, "to": [], "effects": []},
            ],
        }
        self.assertEqual(histories(graph), ([], 2))

    def test_delivery_identity_prefers_intent_and_labels_payload_fallback(self):
        self.assertEqual(identity(EMIT), ("payload-fallback", "hello"))
        self.assertEqual(identity(EMIT + [{"intent": "j"}]), ("intent", "j"))


class FakeExecutorTests(unittest.TestCase):
    """scenario-adapter.py is executor class "fake"; runs without Shen."""

    def test_m1_fake_double_delivery_on_ok_violates_the_intended_clause(self):
        steps = [{"call": call("send"), "choice": "0"}]
        _, honest = run_fake(steps)
        _, mutant = run_fake(steps, mutant=True)
        good = fake_verdict(honest, "scenario-adapter.py")
        bad = fake_verdict(mutant, "scenario-adapter.py --mutant")
        self.assertEqual((good["executor"], good["verdict"]), ("fake", "satisfied"))
        self.assertEqual((bad["executor"], bad["verdict"]), ("fake", "violated"))
        self.assertEqual(
            (bad["invariant"], bad["basis"]), ("effect_applied_twice", OBSERVED)
        )
        self.assertEqual(bad["witness"], [[EMIT, EMIT]])

    def test_h1_truth_two_deliveries_from_the_fake(self):
        """send->info (lands); send->ok; ack->ok: the fake delivers twice."""
        steps = [
            {"call": call("send", Result.INFO), "choice": "1"},
            {"call": call("send"), "choice": "0"},
            {"call": call("ack"), "choice": "0"},
        ]
        _, response = run_fake(steps)
        verdict = fake_verdict(response, "scenario-adapter.py")
        self.assertEqual(
            (verdict["executor"], verdict["verdict"]), ("fake", "violated")
        )
        self.assertEqual(verdict["depth"], 3)

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


class InexpressibleFrontEndTests(IRGapCase):
    """IR gaps visible at the Python front end (system.py); no Shen needed.

    The bodies prescribe one possible wire shape for the missing feature; the
    IR specification may choose another, and then these bodies change with it.
    """

    def given_h4_missing_journal_range_is_unresolved(self):
        complete = {"state": INITIAL, "effects": []}
        return _request(
            dict(call("send", Result.INFO), state=INITIAL, observed=complete), 1024
        )

    @unittest.expectedFailure
    def test_h4_missing_journal_range_is_unresolved(self):
        """H4: a missing journal range must make the step unresolved.

        Missing: a way to say "effects seq 2..3 were not observed". An
        observation is exactly {state, effects} (system.py:132, also
        scenarios.py:100) and caps.accepts? matches the whole effect list
        (system.shen:168-169). The only encodings are a complete list, or []
        which means "no effects" and so passes the aborted alternative of an
        info send (system.shen:164-166) instead of staying unresolved.
        Flips when _request accepts an observation with a journal gap.
        """
        gap = {"state": INITIAL, "effects": [], "journal": {"missing": [[2, 3]]}}
        with self.ir_gap("no partial observation / journal gap"):
            _request(dict(call("send", Result.INFO), state=INITIAL, observed=gap), 1024)

    def given_effects_carry_intent_and_attempt_identity(self):
        return _effect_terms([EMIT])

    @unittest.expectedFailure
    def test_effects_carry_intent_and_attempt_identity(self):
        """Effects must carry (intent-id, attempt-id, logical-effect).

        Missing: effect identity. An effect is [emit Kind Value] /
        [put T K F V] / [create ...] / [delete T K] with fixed arity
        (system.py:100-104; produced by system.shen:67 for publish). So a
        duplicate can only be "two equal payloads" (plan §2.2), not "two
        delivered attempts of one intent". Flips when _effect_terms accepts an
        emit carrying intent and attempt ids.
        """
        with self.ir_gap("no intent/attempt identity on effects"):
            _effect_terms([EMIT + [{"intent": "j", "attempt": "1"}]])

    def given_outbox_record_and_delivery_attempt_are_separate_constructors(self):
        return _term(INTENDED)

    @unittest.expectedFailure
    def test_outbox_record_and_delivery_attempt_are_separate_constructors(self):
        """publish must split into an outbox record and a delivery attempt.

        Missing: constructors for a transactional outbox record and an
        external, at-least-once delivery attempt. The only one is
        [publish Kind V] (system-types.shen:59-61), evaluated inside the
        command's transaction (system.shen:67), and the front end rejects any
        other tag (system.py:24-26). Flips when the front end accepts the two
        constructors (named outbox/deliver here only as a placeholder).
        """
        source = (
            '[system "split" [[table "job" ["payload"] [] []]]'
            ' [[command "send" ["id"] [exists "job" [argument "id"]]'
            ' [[named "record" [outbox "delivery-attempt" [argument "id"]]]'
            '  [named "deliver" [deliver "delivery-attempt" [argument "id"]]]]'
            " [yes]]] []]"
        )
        with self.ir_gap("no outbox-record / delivery-attempt split"):
            _term(source)


class ModelMixin:
    @classmethod
    def setUpClass(cls):
        from capcov.operations.system import evaluate, explore

        cls.evaluate = staticmethod(evaluate)
        cls.explore = staticmethod(explore)

    def model_runs(self, source, initial, schedule):
        calls = []
        for level in schedule:
            for c in level:
                if c not in calls:
                    calls.append(c)
        graph = self.explore(
            source, initial, calls, depth=len(schedule), schedule=schedule
        )
        runs, truncated = histories(graph)
        return graph, runs, truncated

    def evidence(self, source, model, schedule=None, initial=None):
        """at_most_once over explore's graph; scope digest taken from the graph."""
        scope = DECISION["scope"]
        graph, runs, truncated = self.model_runs(
            source,
            scope["initial"] if initial is None else initial,
            scope_schedule(scope) if schedule is None else schedule,
        )
        return at_most_once(
            "model",
            model,
            runs,
            truncated=truncated,
            scope=scope_key(graph["initial"], graph["schedule"]),
            depth=graph["depth"],
        )


@unittest.skipUnless(NATIVE, "real pinned Shen runtime required")
class MigrationProbeModelTests(ModelMixin, unittest.TestCase):
    """Executor class "model": the Shen system evaluator over .ops models."""

    OK_OK_ACK = [[call("send")], [call("send")], [call("ack")]]

    def decision_evidence(self):
        return (
            self.evidence(LEGACY, DECISION["legacy"]["model"]),
            self.evidence(INTENDED, DECISION["intended"]["model"]),
            self.evidence(GUARD_DROPPED, GUARD_DROPPED_MODEL),
        )

    def test_legacy_explores_to_duplicate_delivery_attempt(self):
        verdict = self.evidence(LEGACY, "outbox.ops", self.OK_OK_ACK)
        self.assertEqual(
            (verdict["executor"], verdict["verdict"]), ("model", "violated")
        )
        self.assertEqual(verdict["invariant"], "effect_applied_twice")
        self.assertEqual((verdict["depth"], verdict["basis"]), (3, BOUNDED))

    def test_intended_does_not_deliver_twice(self):
        _, runs, truncated = self.model_runs(INTENDED, INITIAL, self.OK_OK_ACK)
        self.assertEqual((len(runs), truncated), (1, 0))
        self.assertEqual(runs[0][1], [])
        verdict = self.evidence(INTENDED, "outbox-intended.ops", self.OK_OK_ACK)
        self.assertEqual(
            (verdict["executor"], verdict["verdict"]), ("model", "satisfied")
        )

    def test_intended_checker_refuses_observed_double_delivery(self):
        """The observation checker, not only explore, refuses a second delivery."""
        mark = ["put", "job", "j", "status", "attempted"]
        results = self.evaluate(
            INTENDED,
            [
                dict(
                    call("send"),
                    state=ATTEMPTED,
                    observed={"state": ATTEMPTED, "effects": [EMIT]},
                ),
                dict(
                    call("send"),
                    state=INITIAL,
                    observed={"state": ATTEMPTED, "effects": [EMIT, EMIT, mark]},
                ),
                dict(
                    call("send"),
                    state=INITIAL,
                    observed={"state": ATTEMPTED, "effects": [EMIT, mark]},
                ),
            ],
        )["results"]
        self.assertEqual([r["observed_matches"] for r in results], [False, False, True])

    def test_guard_dropping_target_mutant_is_rejected(self):
        legacy, _, mutant = self.decision_evidence()
        self.assertEqual(mutant["verdict"], "violated")
        judged = judge_difference(DECISION, legacy, mutant, mutant)
        self.assertEqual(judged, {"status": "rejected", "legacy_agrees": True})

    def test_difference_accepted_only_with_an_approved_decision(self):
        legacy, target, mutant = self.decision_evidence()
        self.assertEqual(
            [legacy["verdict"], target["verdict"]], ["violated", "satisfied"]
        )
        accepted = judge_difference(DECISION, legacy, target, mutant)
        self.assertEqual(accepted, {"status": "accepted", "decision": DECISION["id"]})
        self.assertEqual(
            judge_difference(None, legacy, target, mutant)["status"], "open"
        )
        unapproved = copy.deepcopy(DECISION)
        del unapproved["approval"]  # M5: missing approval provenance
        m5 = judge_difference(unapproved, legacy, target, mutant)
        self.assertEqual(m5["status"], "open")
        self.assertIn("approval provenance has no approver", m5["reasons"])

    def test_obligation_is_computed_from_evidence(self):
        legacy, target, _ = self.decision_evidence()
        # A "mutant" that is the intended model itself is not rejected.
        unkilled = self.evidence(INTENDED, GUARD_DROPPED_MODEL)
        judged = judge_difference(DECISION, legacy, target, unkilled)
        self.assertEqual(judged["status"], "open")
        self.assertIn(
            "obligation check not passed: guard-dropping-mutant-rejected",
            judged["reasons"],
        )

    def test_wrong_clause_is_not_accepted(self):
        legacy, target, mutant = self.decision_evidence()
        judged = judge_difference(
            DECISION, legacy, dict(target, clause=LEGACY_CLAUSE), mutant
        )
        self.assertEqual(judged["status"], "open")
        self.assertIn("target evidence evaluates another clause", judged["reasons"])

    def test_fake_as_legacy_is_not_accepted(self):
        _, target, mutant = self.decision_evidence()
        steps = [
            {"call": call("send", Result.INFO), "choice": "1"},
            {"call": call("send"), "choice": "0"},
            {"call": call("ack"), "choice": "0"},
        ]
        _, response = run_fake(steps)
        fake = fake_verdict(response, DECISION["legacy"]["model"])
        self.assertEqual(fake["verdict"], "violated")
        judged = judge_difference(DECISION, fake, target, mutant)
        self.assertEqual(judged["status"], "open")
        self.assertIn(
            "legacy evidence is from executor fake, not model", judged["reasons"]
        )

    def test_scope_mismatch_from_a_different_schedule_stays_open(self):
        legacy, target, mutant = self.decision_evidence()
        elsewhere = self.evidence(
            INTENDED, DECISION["intended"]["model"], self.OK_OK_ACK
        )
        self.assertEqual(elsewhere["verdict"], "satisfied")
        judged = judge_difference(DECISION, legacy, elsewhere, mutant)
        self.assertEqual(judged["status"], "open")
        self.assertIn(
            "target evidence is outside the decision's observation scope",
            judged["reasons"],
        )

    def test_target_that_rejects_the_retry_is_not_accepted(self):
        """No vacuous pass: a target whose retry is inadmissible does not cover the scope."""
        legacy, _, mutant = self.decision_evidence()
        rejecting = self.evidence(RETRY_REJECTED, DECISION["intended"]["model"])
        self.assertGreater(rejecting["truncated"], 0)
        judged = judge_difference(DECISION, legacy, rejecting, mutant)
        self.assertEqual(judged["status"], "open")
        self.assertTrue(any("does not cover the scope" in r for r in judged["reasons"]))
        dead = self.evidence(
            RETRY_REJECTED, DECISION["intended"]["model"], self.OK_OK_ACK
        )
        self.assertEqual((dead["verdict"], dead["histories"]), ("unresolved", 0))

    def test_h1_info_then_ok_retry_two_deliveries(self):
        """H1: send->info; send->ok; ack->ok, truth = 2 deliveries.

        Legacy admits the two-delivery history (a finding against the
        intended clause); intended admits no history with two deliveries, so
        that truth is a violation. Holds under the atomic-publish assumption
        (system.shen:165): an info send has two alternatives only.
        """
        schedule = scope_schedule(DECISION["scope"])
        truth = [[EMIT], [EMIT]]
        _, legacy, _ = self.model_runs(LEGACY, INITIAL, schedule)
        self.assertIn(truth, [h[:2] for h in legacy])
        self.assertEqual(
            at_most_once("model", "outbox.ops", legacy)["verdict"], "violated"
        )
        _, intended, truncated = self.model_runs(INTENDED, INITIAL, schedule)
        self.assertEqual((len(intended), truncated), (2, 0))
        self.assertEqual(
            {max(deliveries(h).values(), default=0) for h in intended}, {1}
        )
        emitted = [[[e for e in s if e[0] == "emit"] for s in h[:2]] for h in intended]
        self.assertNotIn(truth, emitted)

    def test_h2_info_then_ok_retry_one_delivery_keeps_alternatives(self):
        """H2: same calls, truth = 1 delivery: passes; both resolutions retained."""
        graph, runs, truncated = self.model_runs(
            INTENDED, INITIAL, scope_schedule(DECISION["scope"])
        )
        self.assertEqual(len(graph["edges"][0]["to"]), 2)
        self.assertEqual(len({n["id"] for n in graph["nodes"] if n["depth"] == 1}), 2)
        emits = sorted(
            [len([e for e in step if e[0] == "emit"]) for step in h[:2]] for h in runs
        )
        self.assertEqual(emits, [[0, 1], [1, 0]])
        verdict = at_most_once(
            "model", "outbox-intended.ops", runs, truncated=truncated
        )
        self.assertEqual(verdict["verdict"], "satisfied")

    def test_h5_same_idempotency_key_different_amount_conflicts_without_debit(self):
        from capcov.operations.system import wire_state

        after = [
            row("wallet", "a", balance="7"),
            row("wallet", "b", balance="5"),
            row("transfer", "r", **{"from": "a", "to": "b", "amount": "3"}),
        ]
        debited = copy.deepcopy(after)
        debited[0]["fields"]["balance"] = "3"
        args = {"from": "a", "to": "b", "amount": "4", "request": "r"}

        def transfer(outcome, observed=None):
            r = {
                "command": "transfer",
                "args": args,
                "state": after,
                "outcome": outcome,
            }
            if observed is not None:
                r["observed"] = {"state": observed, "effects": []}
            return r

        results = self.evaluate(
            LEDGER,
            [
                transfer("rejected", after),
                transfer("rejected", debited),
                transfer("committed"),
            ],
        )["results"]
        self.assertEqual(results[0]["transition"], ["rejected", "idempotency-conflict"])
        self.assertEqual(
            results[0]["admissible"], [["result", wire_state(after), [], []]]
        )
        self.assertEqual([r["observed_matches"] for r in results[:2]], [True, False])
        self.assertEqual(results[2]["admissible"], [])

    def test_m1_fake_double_delivery_is_rejected_by_the_legacy_model(self):
        from capcov.operations.scenarios import run_scenario

        scenario = {
            "initial": INITIAL,
            "steps": [{"call": call("send"), "choice": "0"}],
        }
        honest = run_scenario(LEGACY, scenario, [sys.executable, str(FAKE)])
        mutant = run_scenario(LEGACY, scenario, [sys.executable, str(FAKE), "--mutant"])
        self.assertEqual(honest["mismatches"], [])
        self.assertEqual(mutant["mismatches"], [0])

    def test_m2_payload_dedupe_leaves_an_unsettled_effect(self):
        schedule = [[call("send", job="j")], [call("send", job="k")]]
        verdicts = []
        for source, model in (
            (INTENDED, "outbox-intended.ops"),
            (PAYLOAD_DEDUPE, "payload-dedupe mutant"),
        ):
            graph, runs, truncated = self.model_runs(source, TWO_JOBS, schedule)
            self.assertEqual(truncated, 0)
            verdicts.append(
                every_send_delivered("model", model, runs, 2, depth=graph["depth"])
            )
        self.assertEqual([v["verdict"] for v in verdicts], ["satisfied", "violated"])
        self.assertEqual(verdicts[1]["invariant"], "unsettled_effect")

    def test_m3_reporting_ok_for_an_info_send_is_rejected(self):
        """An info send that never landed, recorded as ok, contradicts the model."""
        nothing = {"state": INITIAL, "effects": []}
        results = self.evaluate(
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

    def test_ledger_transfer_postcondition_is_a_bounded_per_transition_invariant_check(
        self,
    ):
        """Not a conservation proof (R12).

        Each committed transfer's postcondition (sum of balances equals its
        before-value, ledger.ops:23) is evaluated per transition over an
        explicit finite domain; a failure is reported by caps.finish as
        ["rejected", "invariant"] (system.shen:141-145).
        """
        from capcov.operations.system import argument_domain

        wallets = [row("wallet", "a", balance="10"), row("wallet", "b", balance="2")]
        calls = argument_domain(
            "transfer",
            {
                "from": ["a", "b"],
                "to": ["a", "b"],
                "amount": ["1", "3"],
                "request": ["r", "s"],
            },
        )
        graph = self.explore(LEDGER, wallets, calls, depth=2)
        checked = result(
            "model",
            "ledger.ops",
            "no-invariant-violation-within-bound"
            if not graph["invariant_violations"]
            else "violated",
            basis=graph["basis"],
            depth=graph["depth"],
            evidence="per-transition postcondition/invariant check; bounded; not a proof (R12)",
        )
        self.assertEqual(checked["basis"], BOUNDED)
        self.assertEqual(
            checked["verdict"],
            "no-invariant-violation-within-bound",
            graph["invariant_violations"],
        )
        self.assertTrue(any(e["transition"][0] == "result" for e in graph["edges"]))
        mutant = LEDGER.replace(
            '[int-add [lookup "wallet" [argument "to"] "balance"] [argument "amount"]]',
            '[lookup "wallet" [argument "to"] "balance"]',
        )
        broken = self.explore(mutant, wallets, calls, depth=2)
        self.assertTrue(
            broken["invariant_violations"],
            "bounded check missed a non-conserving transfer",
        )
        self.assertEqual(len(broken["shortest_invariant_witness"]), 1)


@unittest.skipUnless(NATIVE, "real pinned Shen runtime required")
class InexpressibleModelTests(ModelMixin, IRGapCase):
    """IR gaps that need the evaluator to show; each gap is an expected failure."""

    def given_info_send_has_at_least_three_alternatives(self):
        graph = self.explore(INTENDED, INITIAL, [call("send", Result.INFO)], depth=1)
        effects = graph["edges"][0]["effects"]
        self.assertIn([], effects)
        self.assertTrue(any(EMIT in e for e in effects))
        return graph

    @unittest.expectedFailure
    def test_info_send_has_at_least_three_alternatives(self):
        """An info send admits nothing / outbox-only / outbox+delivered.

        Missing: an outcome for info with more than two alternatives.
        caps.admissible maps unknown to exactly {before, after}
        (system.shen:165-166) because publish is part of the atomic
        transaction (system.shen:67), so "recorded in the outbox but not yet
        delivered" has no state. The tape choice is binary too
        (scenarios.py:56-57, adapters.py:63-64). Flips when an info send of
        the intended model explores to three or more alternatives.
        """
        self.assertGreaterEqual(len(self.given["edges"][0]["to"]), 3)

    def given_h3_delivery_after_final_read_is_unresolved(self):
        sent = [row("job", "j", status="sent", payload="hello")]
        results = self.evaluate(
            LEGACY,
            [
                dict(
                    call("send", Result.INFO),
                    state=INITIAL,
                    observed={"state": INITIAL, "effects": []},
                ),
                dict(
                    call("ack"),
                    state=INITIAL,
                    observed={
                        "state": sent,
                        "effects": [["put", "job", "j", "status", "sent"]],
                    },
                ),
            ],
        )["results"]
        self.assertEqual(
            results[0]["transition"][2], [EMIT], "the info send could land"
        )
        self.assertIs(results[1]["observed_matches"], True)
        return results

    @unittest.expectedFailure
    def test_h3_delivery_after_final_read_is_unresolved(self):
        """H3: send->info; ack->ok; final read; the delivery lands after it.

        Missing: info invocations that stay open until history close. An
        unknown outcome is resolved inside its own transition
        (system.shen:165-166; scenarios.py:125-126 fixes it to the tape
        branch), explore records no open invocations (system.py:451-466), and
        a request has no history-close/final-read marker (fields
        system.py:110-118, outcomes :126-128). So the observed prefix "nothing
        yet" matches the aborted alternative and the step passes, where it
        must stay unresolved. Flips when the info step's observed_matches is
        no longer True before history close.
        """
        self.assertIsNot(
            self.given[0]["observed_matches"], True, "info send judged before close"
        )

    def given_m2_delivery_effects_carry_intent_identity(self):
        schedule = [[call("send", job="j")], [call("send", job="k")]]
        _, runs, truncated = self.model_runs(INTENDED, TWO_JOBS, schedule)
        self.assertEqual((len(runs), truncated), (1, 0))
        emits = [e for step in runs[0] for e in step if e[:2] == ["emit", DELIVERY]]
        self.assertEqual(len(emits), 2)
        return emits

    @unittest.expectedFailure
    def test_m2_delivery_effects_carry_intent_identity(self):
        """M2 (the inexpressible half): dedupe must be by intent, not payload.

        Missing: intent identity on the effects the evaluator emits
        (system.py:100-104, system.shen:67). Two jobs with the same payload
        produce two identical [emit delivery-attempt hello] effects, so no
        checker can tell the correct model from one delivering job j twice and
        job k never, and at_most_once can only count by the payload fallback
        (identity()). The payload-dedupe mutant that drops a delivery IS
        caught (test_m2_payload_dedupe_leaves_an_unsettled_effect) only
        because the count falls. Flips when the intended model's two delivery
        effects differ by an intent id; at_most_once then counts per intent.
        """
        first, second = self.given
        self.assertNotEqual(
            first, second, "two intents' deliveries are indistinguishable"
        )

    def given_m4_adapter_that_normalizes_effects_to_a_set_is_rejected(self):
        from capcov.operations.scenarios import run_scenario

        scenario = {
            "initial": INITIAL,
            "steps": [{"call": call("send"), "choice": "0"}],
        }
        raw = run_scenario(LEGACY, scenario, [sys.executable, str(FAKE), "--mutant"])
        self.assertEqual(
            raw["mismatches"], [0], "the checker counts effect multiplicity"
        )
        return scenario

    @unittest.expectedFailure
    def test_m4_adapter_that_normalizes_effects_to_a_set_is_rejected(self):
        """M4: an adapter that reports effects as a set hides M1.

        Missing: attempt identity. Two delivery attempts are equal tuples
        [emit delivery-attempt hello] (system.py:100-104), so set
        normalization collapses them and the observation matches the model
        (caps.accepts?, system.shen:168-169). With per-attempt ids they would
        stay distinct and the normalized report would be refused. Flips when
        the set-normalized report of the double delivery mismatches.
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
            with self.ir_gap("no attempt identity"):
                report = run_scenario(
                    LEGACY, self.given, [sys.executable, str(wrapper)]
                )
        self.assertTrue(report["mismatches"], "set-normalized double delivery passed")


if __name__ == "__main__":
    unittest.main()
