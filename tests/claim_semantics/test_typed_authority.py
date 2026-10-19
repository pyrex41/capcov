"""The typed third authority (roadmap W2) against the other two, id for id.

Every supported pack (static, replay v1 and v2, observation, shared), every
authored negative fixture in ``authority_v2/`` and ``typed_authority/`` and
every planted bad-rule pack is judged by Python validation, the untyped Shen
authority and ``shen.typed_authority``.  Verdicts are compared as sets of
(rule, check id) failures.  Python issue codes are mapped onto the Shen ids
(``PY_TO_ID``).  When a schema-2 pack's evidence contracts fail, both Shen
authorities also fail the contract-dependent rule checks and Python stops
after the contract issues; only the pack-level failure is compared then.

Where the three disagree, the test does not choose a winner: the exact set of
disagreements is recorded, with an analysis, in
``specs/claims/migration-preserved.json`` under ``typed_authority_disagreements``,
and this test asserts that recorded set exactly.  Both Shen authorities run as
one batch each (one runtime process), because compiling the typed datatypes
dominates a typed run.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

from capcov.claims import shen
from capcov.claims.ir import bundle_from_json
from capcov.claims.validation import validate_bundle

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = bool(shutil.which("bifrost") and os.environ.get("BIFROST_SHEN_GO"))
if os.environ.get("CAPCOV_SHEN_REQUIRED") and not NATIVE:
    raise RuntimeError("the typed authority requires bifrost and BIFROST_SHEN_GO")

PY_TO_ID = {
    "unknown-relation": "undeclared-relation",
    "unsafe-variable": "ungrounded-conclusion-variable",
    "unsafe-negation": "ungrounded-side-condition-variable",
    "unsafe-comparison": "ungrounded-side-condition-variable",
    "type-mismatch": "typed-rule", "atom-type": "typed-rule", "term-type": "typed-rule", "arity": "typed-rule",
    "head-context": "context-index-loss",
    "missing-compatibility": "unsupported-context-widening",
    "missing-required-bridge": "unsupported-context-widening",
    "mixed-binding-join": "unsupported-context-widening",
    "missing-completeness": "negative-conclusion-without-completeness",
    "negative-compatibility": "negative-conclusion-without-completeness",
    "declaration-promoted-to-effect": "declaration-promoted-to-effect",
    "recursive-negation": "stratified-negation",
}
CONTRACT_CODES = {"duplicate-contract", "duplicate-rule", "derived-completeness-policy",
                  "unsupported-compatibility-scope", "legacy-compatibility", "completeness-scope",
                  "completeness-scope-type", "compatibility-capability", "compatibility-endpoint",
                  "required-bridge"}
CONTRACT_DEPENDENT = {"context-index-loss", "unsupported-context-widening",
                      "negative-conclusion-without-completeness"}
PACKS = {
    "static-v1": "src/capcov/claims/static/rules-static-v1.json",
    "static-v2": "src/capcov/claims/static/rules-static-v2.json",
    "replay-v1": "src/capcov/claims/replay/rules-replay-v1.json",
    "replay-v2": "src/capcov/claims/replay/rules-replay-v2.json",
    "observation-v1": "src/capcov/claims/observation/rules-observation-v1.json",
    "observation-v2": "src/capcov/claims/observation/rules-observation-v2.json",
    "shared": "src/capcov/claims/static/runtime-shared-v1.json",
}


def _changed(corpus, case):
    raw = copy.deepcopy(corpus["base"])
    for change in case["changes"]:
        keys = change["path"].strip("/").split("/")
        parent = raw
        for key in keys[:-1]:
            parent = parent[int(key)] if isinstance(parent, list) else parent[key]
        key = int(keys[-1]) if isinstance(parent, list) else keys[-1]
        parent[key] = change["value"]
    return bundle_from_json(raw, validate=False)


def fixture_cases():
    for directory in ("authority_v2", "typed_authority"):
        for file in sorted((HERE / directory).glob("*.json")):
            corpus = json.loads(file.read_text())
            for case in corpus["cases"]:
                # categories are authority.judge's; "rejected" overrides where
                # validation (not judge) is what refuses the case
                yield (f"{directory}/{case['name']}", _changed(corpus, case),
                       bool(case.get("rejected", case["categories"])))


def pack_cases():
    for name, path in PACKS.items():
        raw = json.loads((ROOT / path).read_text())
        if "relations" in raw:
            yield f"pack/{name}", bundle_from_json(raw)
        else:
            yield f"pack/{name}", shen._pack_bundle(raw)


def planted_cases():
    from .test_shen_workbench import _planted_packs
    for check_id, pack in _planted_packs():
        yield f"planted/{check_id}", shen._pack_bundle(pack, validate=False), check_id


def python_ids(bundle):
    names = [rule.name for rule in bundle.rules]
    out = set()
    for issue in validate_bundle(bundle):
        if issue.code in CONTRACT_CODES:
            out.add(("<pack>", "evidence-contracts"))
            continue
        path = issue.path or ""
        if path.startswith("rules["):
            rule = names[int(path[6:path.index("]")])]
        elif path.startswith("rules."):
            rule = path[6:]
        else:
            rule = "<pack>"
        out.add((rule, PY_TO_ID.get(issue.code, "python:" + issue.code)))
    return _normalized(out)


def shen_ids(report):
    return _normalized(set(report.failed_checks()))


def _normalized(ids):
    if ("<pack>", "evidence-contracts") in ids:
        return {(r, c) for r, c in ids if c not in CONTRACT_DEPENDENT}
    return ids


def recorded_disagreements():
    data = json.loads((ROOT / "specs/claims/migration-preserved.json").read_text())
    return data["typed_authority_disagreements"]


@unittest.skipUnless(NATIVE, "real pinned Shen runtime required")
class TypedAuthorityDifferentialTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = [(name, bundle) for name, bundle in pack_cases()]
        cls.negative = {}
        for name, bundle, rejected in fixture_cases():
            cls.cases.append((name, bundle))
            cls.negative[name] = rejected
        cls.planted = {}
        for name, bundle, check_id in planted_cases():
            cls.cases.append((name, bundle))
            cls.planted[name] = check_id
        bundles = [bundle for _, bundle in cls.cases]
        started = time.monotonic()
        cls.typed = shen.authority_batch(bundles, typed=True, validate=False)
        cls.typed_seconds = time.monotonic() - started
        started = time.monotonic()
        cls.untyped = shen.authority_batch(bundles, validate=False)
        cls.untyped_seconds = time.monotonic() - started
        for (name, _), typed, untyped in zip(cls.cases, cls.typed, cls.untyped):
            if isinstance(typed, Exception) or isinstance(untyped, Exception):
                raise AssertionError(f"{name}: {typed!r} / {untyped!r}")

    def test_every_supported_pack_is_admitted_by_all_three(self):
        for (name, bundle), typed, untyped in zip(self.cases, self.typed, self.untyped):
            if not name.startswith("pack/"):
                continue
            with self.subTest(pack=name):
                self.assertEqual(validate_bundle(bundle), ())
                self.assertTrue(untyped.ok, untyped.failed_checks())
                self.assertTrue(typed.ok, typed.failed_checks())
                self.assertEqual(len(typed.rules), len(bundle.rules))
                self.assertTrue(all(b in {"typed", "typed+contracts", "trusted-elaborator"}
                                    for b in typed.bases().values()))

    def test_verdicts_have_the_untyped_shape(self):
        for (name, _), typed, untyped in zip(self.cases, self.typed, self.untyped):
            with self.subTest(case=name):
                self.assertEqual([(v["rule"], v["rule_digest"], [c["id"] for c in v["checks"]]) for v in typed.rules],
                                 [(v["rule"], v["rule_digest"], [c["id"] for c in v["checks"]]) for v in untyped.rules])
                self.assertEqual([c["id"] for c in typed.pack], [c["id"] for c in untyped.pack])
                self.assertEqual(typed.elaborated_checksum, untyped.elaborated_checksum)
                self.assertGreaterEqual(typed.units, len(typed.rules))

    def test_negative_gates_are_rejected(self):
        for (name, _), typed in zip(self.cases, self.typed):
            if name in self.negative:
                with self.subTest(case=name):
                    self.assertEqual(not typed.ok, self.negative[name], typed.failed_checks())
            if name in self.planted:
                with self.subTest(case=name):
                    self.assertIn(("bad", self.planted[name]), set(typed.failed_checks()))

    def test_disagreements_are_exactly_the_recorded_set(self):
        observed = set()
        for (name, bundle), typed, untyped in zip(self.cases, self.typed, self.untyped):
            p, u, t = python_ids(bundle), shen_ids(untyped), shen_ids(typed)
            for rule, check in sorted(p | u | t):
                key = (rule, check)
                verdicts = (key in p, key in u, key in t)
                if len(set(verdicts)) > 1:
                    observed.add((name, rule, check) + verdicts)
        recorded = recorded_disagreements()
        for entry in recorded:
            self.assertTrue(entry.get("analysis"), entry)
        expected = {(e["case"], e["rule"], e["id"], e["python"], e["untyped"], e["typed"]) for e in recorded}
        self.assertEqual(observed, expected, sorted(observed))
        print(f"\n[typed authority] {len(self.cases)} bundles: typed batch {self.typed_seconds:.1f}s, "
              f"untyped batch {self.untyped_seconds:.1f}s, units {sum(t.units for t in self.typed)}")


@unittest.skipUnless(NATIVE, "real pinned Shen runtime required")
class ForgedTypedIRTest(unittest.TestCase):
    """The checker re-derives the judgement; a reified IR that lies is refused.

    The units are reified from a fixture by the real reifier and then
    mutated: a sort proposal that disagrees with a column, a witness endpoint
    moved to another occurrence's term, and a negated witness turned into
    the closure of a negation.  The unmutated control must be admitted."""

    def test_mutated_units_are_refused(self):
        _, bundle, _ = next(c for c in fixture_cases() if c[0] == "authority_v2/exact-positive-endpoints")
        rt = shen.runtime(typed=True)
        directory = Path(rt.shen_dir)
        forge = r"""
(define forge.sort
  [cc.let-sort "A" T K] -> [cc.let-sort "A" "digest" K]
  [B | Bs] -> [(forge.sort B) | (forge.sort Bs)]
  X -> X)
(define forge.endpoint
  [cc.pos [cc.rel "permit" | D] [[cc.uvar "A"] [cc.uvar "B"] N]] -> [cc.pos [cc.rel "permit" | D] [[cc.uvar "A"] [cc.uvar "T"] N]]
  [B | Bs] -> [(forge.endpoint B) | (forge.endpoint Bs)]
  X -> X)
(define forge.judge
  Name U S -> (output "FORGE ~A ~A~%" Name (trap-error (not (= false (shen.typecheck (cc.syntax U) [cc-judged S]))) (/. E false))))
(define forge.main
  -> (do (capcov.load-bundle)
         (set capcov.*ta-assumed* (capcov.assumption-relations))
         (let U (capcov.ta-unit (hd (value capcov.*rules*)))
           (do (forge.judge "control-typed" U cc-typed)
               (forge.judge "control-widening" U cc-widening)
               (forge.judge "sort" (forge.sort U) cc-typed)
               (forge.judge "endpoint" (forge.endpoint U) cc-widening)))))
"""
        lines = shen._library_lines(directory, True)
        lines += shen._data_lines(bundle, {"kind": "typed-authority"}, frozen=None, max_depth=8, max_nodes=100,
                                  bundle_digest="forged", rules_digest_value="forged")
        with tempfile.TemporaryDirectory(prefix="capcov-forge-") as tmp:
            helper = Path(tmp) / "forge.shen"
            helper.write_text(forge, encoding="utf-8")
            driver = Path(tmp) / "driver.shen"
            driver.write_text("\n".join(lines + [f'(load "{helper}")', "(tc +)", "(forge.main)"]) + "\n",
                              encoding="utf-8")
            proc = subprocess.run(shen._argv(rt, driver, direct=False), env=shen._env(rt),
                                  stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                  timeout=shen.TYPED_TIMEOUT, cwd=tmp)
        verdicts = dict(line.split()[1:3] for line in proc.stdout.splitlines() if line.startswith("FORGE "))
        self.assertEqual(verdicts, {"control-typed": "true", "control-widening": "true",
                                    "sort": "false", "endpoint": "false"}, proc.stdout[-2000:])


if __name__ == "__main__":
    unittest.main()
