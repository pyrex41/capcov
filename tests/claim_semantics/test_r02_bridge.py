"""R02 PR 1: outcomes, effect identity and the v1 bridge (docs/ir-specification.md).

Sections 4.1, 4.2 and 7. A request may name its outcome in the capcov.faults
alphabet (`["ok"]`, `["fail", ["rejected", L]]`, `["fail", ["aborted"]]`,
`["info"]`) and may name its invocation id; its result then carries the
model's assumptions, and with an invocation id its admissible effects are
effect records `[effect Inv Inv/body L]`. A v1 request is unchanged (gate G5,
test_v1_compatibility).
"""

import copy
import json
import os
from pathlib import Path
import re
import shutil
import unittest

from capcov.operations import OperationError
from capcov.operations.scenarios import _payload
from capcov.operations.system import (
    _effect_terms,
    _request,
    bridged,
    run_adapter,
    verify_effects,
)

FIXTURE = Path(__file__).parent / "fixtures/systems"
G5 = FIXTURE / "g5"
V2 = FIXTURE / "v2-draft"
OUTBOX = (FIXTURE / "outbox.ops").read_text()
NATIVE = bool(shutil.which("bifrost") and os.environ.get("BIFROST_SHEN_GO"))
if os.environ.get("CAPCOV_SHEN_REQUIRED") and not NATIVE:
    raise RuntimeError("the R02 bridge tests require native Shen")

JOB = [{"table": "job", "key": "j", "fields": {"status": "pending", "payload": "hello"}}]
EMIT = ["emit", "delivery-attempt", "hello"]
REFUSED = "schema, scope or construction judgment failed"


def send(outcome, **extra):
    return dict(
        command="send", args={"id": "j"}, state=copy.deepcopy(JOB), outcome=outcome, **extra
    )


def record(intent, attempt, effect=EMIT):
    return ["effect", intent, attempt, effect]


def bridge(outcome, transition):
    """Section 7: a v1 outcome as an R02 outcome; rejected takes the model's label."""
    if outcome == "rejected":
        label = transition[1] if transition[0] == "rejected" else "no-such-label"
        return ["fail", ["rejected", label]]
    return {"committed": ["ok"], "aborted": ["fail", ["aborted"]], "unknown": ["info"]}[
        outcome
    ]


def declared(assumptions):
    names = " ".join(json.dumps(a) for a in assumptions)
    return OUTBOX.replace('[system "outbox"', f'[system "outbox" [{names}]', 1)


class BridgeFrontEndTests(unittest.TestCase):
    """The front end (system.py) alone; no Shen."""

    def test_r02_outcomes_are_accepted_and_carry_assumptions(self):
        for outcome, term in (
            (["ok"], "[ok]"),
            (["info"], "[info]"),
            (["fail", ["aborted"]], "[fail [aborted]]"),
            (["fail", ["rejected", "precondition"]], "[fail [rejected (capop.string"),
        ):
            with self.subTest(outcome=outcome):
                program = _request(send(outcome), 1024)
                self.assertIn(term, program)
                self.assertTrue(program.endswith(" (caps.assumptions M)])"))

    def test_v1_outcomes_are_unchanged_and_carry_no_assumptions(self):
        for outcome in ("committed", "rejected", "aborted", "unknown"):
            with self.subTest(outcome=outcome):
                program = _request(send(outcome), 1024)
                self.assertFalse(bridged(send(outcome)))
                self.assertIn(f" R {outcome}) [(caps.analyze M ", program)
                self.assertNotIn("caps.assumptions", program)
                self.assertNotIn("caps.identify", program)

    def test_malformed_outcomes_are_refused(self):
        for outcome in (
            "ok",
            ["unknown"],
            ["fail"],
            ["fail", "aborted"],
            ["fail", ["rejected"]],
            ["fail", ["rejected", 3]],
            ["fail", ["aborted"], "x"],
            ["ok", "extra"],
            None,
        ):
            with self.subTest(outcome=outcome), self.assertRaisesRegex(
                OperationError, "invalid outcome"
            ):
                _request(send(outcome), 1024)

    def test_an_invocation_tags_the_admissible_alternatives(self):
        program = _request(send("committed", invocation="i1"), 1024)
        self.assertIn("(caps.identify (capop.string", program)
        self.assertTrue(bridged(send("committed", invocation="i1")))
        for bad in ("", 7, "x" * 257):
            with self.subTest(invocation=bad), self.assertRaises(OperationError):
                _request(send("committed", invocation=bad), 1024)

    def test_an_identified_observation_refuses_an_untagged_effect(self):
        """The negative of section 4.2 at the engine's front end (cf. T-effect)."""
        for effects in ([EMIT], [record("i1", "i1/body"), EMIT]):
            with self.subTest(effects=effects), self.assertRaisesRegex(
                OperationError, "untagged effect"
            ):
                _request(
                    send(
                        "committed",
                        invocation="i1",
                        observed={"state": JOB, "effects": effects},
                    ),
                    1024,
                )
        _request(
            send(
                "committed",
                invocation="i1",
                observed={"state": JOB, "effects": [record("i1", "i1/body")]},
            ),
            1024,
        )

    def test_effect_records_need_an_invocation_and_stay_out_of_traces(self):
        observed = {"state": JOB, "effects": [record("i1", "i1/body")]}
        with self.assertRaisesRegex(OperationError, "invocation id"):
            _request(send("committed", observed=observed), 1024)
        trace = {"state": JOB, "effects": [record("i1", "i1/body")], "steps": []}
        with self.assertRaisesRegex(OperationError, "invocation id"):
            _request(send("committed", invocation="i1", trace=trace), 1024)

    def test_malformed_records_and_mixed_lists_are_refused(self):
        for effects in (
            [["effect", "j", EMIT]],
            [["effect", "", "a", EMIT]],
            [["effect", "j", "a", record("j", "a")]],
            [["effect", "j", "a", ["emit", "k"]]],
            [record("j", "a"), EMIT],
        ):
            with self.subTest(effects=effects), self.assertRaises(OperationError):
                _effect_terms(effects)

    def test_the_checker_projects_records_and_checks_their_identity(self):
        wire =[["row", "job", "j", [["payload", "hello"], ["status", "sent"]]]]
        put = ["put", "job", "j", "status", "sent"]
        trace = [["action", "ack", [put]]]
        result = {
            "analysis": [["job"], ["job"], []],
            "transition": ["result", wire, [put], trace],
            "admissible": [["result", wire, [record("i1", "i1/body", put)], trace]],
        }
        self.assertTrue(verify_effects(JOB, result, "i1"))
        for wrong in (record("i2", "i1/body", put), record("i1", "i1/x", put), put):
            forged = copy.deepcopy(result)
            forged["admissible"][0][2] = [wrong]
            with self.subTest(effect=wrong), self.assertRaisesRegex(
                OperationError, "bridge identity"
            ):
                verify_effects(JOB, forged, "i1")

    def test_v1_adapter_protocols_carry_v1_requests_only(self):
        for request in (send(["ok"]), send("committed", invocation="i1")):
            with self.subTest(request=request), self.assertRaisesRegex(
                OperationError, "v1 requests only"
            ):
                run_adapter(OUTBOX, [request], ["true"])
        step = {"call": {"command": "send", "args": {"id": "j"}, "outcome": ["info"]}, "choice": "0"}
        with self.assertRaisesRegex(OperationError, "v1 outcome alphabet"):
            _payload({"initial": JOB, "steps": [step]}, 1024)


@unittest.skipUnless(NATIVE, "real pinned Shen runtime required")
class BridgeTests(unittest.TestCase):
    """Executor class "model": the bridge and R-ASSUME in the Shen evaluator."""

    @classmethod
    def setUpClass(cls):
        from capcov.operations.system import evaluate, explore

        cls.evaluate = staticmethod(evaluate)
        cls.explore = staticmethod(explore)

    def test_the_bridge_reproduces_every_v1_answer_and_names_its_assumptions(self):
        """Section 7, claim: pi(Adm(bridge(req))) = caps.admissible(req), per fixture."""
        for path in sorted(FIXTURE.glob("*.ops")):
            stem = path.name[: -len(".ops")]
            requests = json.loads((G5 / f"{stem}.evaluate-input.json").read_text())
            golden = json.loads((G5 / f"{stem}.evaluate.json").read_text())["results"]
            bridged_requests = [
                dict(r, outcome=bridge(r["outcome"], g["transition"]))
                for r, g in zip(requests, golden)
            ]
            source = path.read_text()
            expected = ["info-in-place-v1"] + (
                ["atomic-publish-v1"] if "[publish " in source else []
            )
            results = self.evaluate(source, bridged_requests)["results"]
            with self.subTest(fixture=path.name):
                self.assertEqual(len(results), len(golden))
                for r, g in zip(results, golden):
                    self.assertEqual(r.pop("assumptions"), expected)
                    self.assertEqual(r, g)

    def test_outcomes_identity_and_labels(self):
        reject = dict(send(["fail", ["rejected", "precondition"]]), args={"id": "k"})
        wrong_label = dict(reject, outcome=["fail", ["rejected", "invariant"]])
        good = {"state": JOB, "effects": [record("i1", "i1/body")]}
        requests = [
            send(["info"]),
            reject,
            wrong_label,
            send(["ok"], invocation="i1", observed=good),
            send(["ok"], invocation="i1", observed={"state": JOB, "effects": [record("i1", "i2/body")]}),
            send(["ok"], invocation="i1", observed={"state": JOB, "effects": [record("j", "i1/body")]}),
            send("unknown", invocation="i1", observed={"state": JOB, "effects": []}),
            send("committed"),
        ]
        info, rejected, mislabelled, ok, wrong_attempt, wrong_intent, unknown, v1 = (
            self.evaluate(OUTBOX, requests)["results"]
        )
        assumptions = ["info-in-place-v1", "atomic-publish-v1"]
        self.assertEqual(info["assumptions"], assumptions)
        self.assertEqual(len(info["admissible"]), 2)
        self.assertEqual(rejected["admissible"], [["result", v1["transition"][1], [], []]])
        self.assertEqual(mislabelled["admissible"], [])
        self.assertIs(ok["observed_matches"], True)
        self.assertEqual(
            [alt[2] for alt in ok["admissible"]], [[record("i1", "i1/body")]]
        )
        self.assertEqual(
            [[e[3] for e in alt[2]] for alt in ok["admissible"]],
            [alt[2] for alt in v1["admissible"]],
        )
        self.assertIs(wrong_attempt["observed_matches"], False)
        self.assertIs(wrong_intent["observed_matches"], False)
        self.assertIs(unknown["observed_matches"], True)
        self.assertEqual(unknown["assumptions"], assumptions)
        self.assertNotIn("assumptions", v1)

    def test_r_assume_rejects_the_fixture_and_accepts_its_repair(self):
        fixture = (V2 / "rejected-command-without-assumption.ops-v2").read_text()
        self.assertTrue(fixture.startswith("; rejected-by: R-ASSUME"))
        request = dict(send(["info"]), state=[])
        request["args"] = {"id": "j"}
        with self.assertRaisesRegex(OperationError, re.escape(REFUSED)):
            self.evaluate(fixture, [request])
        repaired = fixture.replace(
            '["info-in-place-v1"]', '["info-in-place-v1" "atomic-publish-v1"]', 1
        )
        self.assertNotEqual(repaired, fixture)
        (result,) = self.evaluate(repaired, [request])["results"]
        self.assertEqual(result["assumptions"], ["info-in-place-v1", "atomic-publish-v1"])

    def test_r_assume_refuses_unknown_and_repeated_names(self):
        for names in (
            ["info-in-place-v1", "atomic-publish-v1", "retry-v1"],
            ["info-in-place-v1", "atomic-publish-v1", "atomic-publish-v1"],
            ["atomic-publish-v1"],
            ["info-in-place-v1", "atomic-publish-v1", "definite-fail-v1:faults"],
        ):
            with self.subTest(names=names), self.assertRaisesRegex(
                OperationError, re.escape(REFUSED)
            ):
                self.evaluate(declared(names), [send(["info"])])

    def test_a_declaring_system_answers_as_its_v1_form(self):
        names = ["info-in-place-v1", "atomic-publish-v1", "single-landing-v1"]
        requests = [send(o) for o in ("committed", "rejected", "aborted", "unknown")]
        v1 = self.evaluate(OUTBOX, requests)["results"]
        mine = self.evaluate(declared(names), requests + [send(["info"])])["results"]
        self.assertEqual(mine[:4], v1)
        self.assertEqual(mine[4]["assumptions"], names)

    def test_explore_with_r02_outcomes_matches_v1_and_carries_assumptions(self):
        calls = [
            {"command": "send", "args": {"id": "j"}, "outcome": "unknown"},
            {"command": "ack", "args": {"id": "j"}, "outcome": "committed"},
        ]
        r02 = [dict(calls[0], outcome=["info"]), dict(calls[1], outcome=["ok"])]
        v1 = self.explore(OUTBOX, JOB, calls, depth=2)
        mine = self.explore(OUTBOX, JOB, r02, depth=2)
        self.assertEqual(mine.pop("assumptions"), ["info-in-place-v1", "atomic-publish-v1"])
        self.assertNotIn("assumptions", v1)
        for graph in (v1, mine):
            graph.pop("calls")
            for edge in graph["edges"]:
                edge.pop("call")
        self.assertEqual(mine, v1)


if __name__ == "__main__":
    unittest.main()
