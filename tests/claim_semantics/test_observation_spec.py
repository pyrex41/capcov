"""Observation specification migration against the frozen v1 pack and receipts.

V2 is selected explicitly; v1 stays the default. The four committed receipts
(agree, disagree, gap, masked) and the admitted-mask control must close to the
same relations under both profiles, and so must every individual completeness
or assumption withdrawal -- the v2 scopes and policies re-derive the v1 rules
exactly, so any closure difference is a migration error, not a tightening.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from capcov.claims.ir import digest
from capcov.claims.evaluator import evaluate
from capcov.claims.assumptions import withdraw
from capcov.claims.evaluation_basis import evaluate_basis
from capcov.claims.static.combine import combine, CombineError
from capcov.claims.static.certificate import normalize_relations, recheck
from capcov.claims.observation import join as observation_join
from capcov.claims.observation import judge
from capcov.claims.observation.pack import pack_bundle
from capcov.claims import pack_resources

from .test_observation_join import AGREE, DISAGREE, GAP, MASKED, _Variant
from .test_observation_judge import _valid_invocation_record, _write_record, AGREE as JUDGE_AGREE

RECEIPTS = {"agree": AGREE, "disagree": DISAGREE, "gap": GAP, "masked": MASKED}
#: Claim verdicts the v1 suite pins for the committed receipts
#: (test_observation_join.CommittedReceiptVerdictTest); v2 must reproduce them.
VERDICTS = {"agree": ("supported", "supported"), "disagree": ("unresolved", "supported"),
            "gap": ("unresolved", "supported"), "masked": ("unresolved", "supported")}


def _admit_mask(document: dict) -> None:
    document["rows"].append({"relation": "masked_difference_admitted",
                             "normalization": "sort-roles", "field_path": "body:/roles"})


class ObservationSpecTests(unittest.TestCase):
    def assert_same_rows(self, old, new):
        a, b = evaluate(old), evaluate(new)
        self.assertEqual(a.status.value, "complete")
        self.assertEqual(b.status.value, "complete")
        self.assertEqual(normalize_relations(a.relations), normalize_relations(b.relations))
        return a, b

    def assert_profiles_agree(self, directory, name):
        old = observation_join.build(directory, fixture=True)
        new = observation_join.build(directory, fixture=True, version=2)
        self.assertEqual(old.bundle.schema_version, 1)
        self.assertEqual(new.bundle.schema_version, 2)
        # The exported rows, their evidence ids and the observation identity
        # are profile-independent; only the declarations and contracts differ.
        self.assertEqual(old.exported.bundle.facts, new.exported.bundle.facts)
        self.assertEqual(old.exported.bundle.evidence, new.exported.bundle.evidence)
        self.assertEqual(dict(old.exported.bundle.metadata)["observation_digest"],
                         dict(new.exported.bundle.metadata)["observation_digest"])
        self.assertEqual(dict(new.exported.bundle.metadata)["pack_profile"], "rules-observation-v2")
        a, b = self.assert_same_rows(old.bundle, new.bundle)
        for join, report in ((old, a), (new, b)):
            verdicts = {r.claim.id: r.semantic.value for r in report.claims}
            self.assertEqual((verdicts[join.agree_claim], verdicts[join.stable_claim]), VERDICTS[name])
        self.assertEqual(observation_join.blocking_premise(dict(a.relations), old.run),
                         observation_join.blocking_premise(dict(b.relations), new.run))
        decls = {r.name: r for r in old.bundle.relations}
        ids = [e.id for e in old.bundle.evidence
               if decls[e.atom.relation].modality.value == "completeness" or e.kind == "assumption"]
        self.assertTrue(ids)
        for eid in ids:
            with self.subTest(receipt=name, withdraw=eid):
                self.assert_same_rows(withdraw(old.bundle, [eid]), withdraw(new.bundle, [eid]))
        return old, new

    def test_committed_receipts_and_withdrawals_close_identically_under_v1_and_v2(self):
        for name, directory in RECEIPTS.items():
            with self.subTest(receipt=name):
                self.assert_profiles_agree(directory, name)

    def test_admitted_mask_control_closes_identically_under_v1_and_v2(self):
        with _Variant(MASKED, ledger=_admit_mask) as root:
            old, new = self.assert_profiles_agree(root, "agree")
        # masked_admitted is a single-premise assumption projection: under v2 it
        # still rests on the reviewer's admission, never on observed support.
        report = evaluate(new.bundle)
        self.assertTrue(any(row for row in dict(report.relations).get("masked_admitted", ())))

    def test_v2_declares_no_compatibility_and_v1_remains_default(self):
        v2 = pack_bundle(version=2)
        self.assertEqual(v2.compatibility_capabilities, ())
        self.assertEqual(v2.required_bridges, ())
        self.assertEqual(len(v2.completeness_scopes), 28)
        self.assertEqual(len(v2.derived_completeness_policies), 14)
        self.assertFalse(any(r.modality.value == "compatibility" for r in v2.relations))
        self.assertEqual(pack_bundle().schema_version, 1)
        self.assertEqual(pack_bundle(), pack_bundle(version=1))
        self.assertEqual(v2.rules, pack_bundle().rules)

    def test_installed_profile_rejects_manifest_drift(self):
        directory = Path(__file__).resolve().parents[2] / "src/capcov/claims/observation"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in directory.glob("*v2*.json"):
                shutil.copy(path, root / path.name)
            with patch.object(pack_resources.resources, "files", return_value=root):
                self.assertEqual(pack_resources.resolve_profile("observation", 2).version, 2)
                path = root / "stubs-observation-v2.json"
                path.write_text(path.read_text() + " ")
                with self.assertRaises(ValueError):
                    pack_resources.resolve_profile("observation", 2)

    def test_receipt_to_checked_v2_certificates(self):
        old = observation_join.build(AGREE, fixture=True)
        new = observation_join.build(AGREE, fixture=True, version=2)
        observation_join.evaluate_python(new)
        self.assertIsNone(new.python_report.operational_failure)
        basis = evaluate_basis(new.bundle)
        self.assertTrue(new.certificates)
        for cert in new.certificates.values():
            self.assertTrue(recheck(new.bundle, cert, evaluation_basis=basis).fully_checked)
            self.assertFalse(recheck(new.bundle, cert).fully_checked)
            self.assertFalse(recheck(old.bundle, cert).ok)
        self.assertNotEqual(digest(old.bundle), digest(new.bundle))
        self.assertEqual(observation_join.summary(new)["status"], "complete")
        with self.assertRaises(CombineError):
            combine(old.exported.bundle, pack_bundle(version=2))

    def test_judge_cli_selects_v2_and_reports_the_same_decision(self):
        with tempfile.TemporaryDirectory(prefix="capcov-observation-spec-") as tmp:
            # One candidate tree and invocation record for both runs: the
            # source binding is then identical and only the profile varies.
            root = Path(tmp)
            shutil.copytree(JUDGE_AGREE, root / "receipt")
            record = _valid_invocation_record(root / "candidate", root / "manifest.json")
            record_digest = _write_record(root / "invocation.json", record)
            receipt = json.loads((JUDGE_AGREE / "receipt.json").read_text(encoding="utf-8"))

            def run(version, out):
                args = ["--receipt", str(root / "receipt"), "--candidate-root", str(root / "candidate"),
                        "--incumbent-manifest", str(root / "manifest.json"),
                        "--expected-nonce", receipt["run"]["nonce"],
                        "--expected-fixture-digest", receipt["fixture"]["digest"],
                        "--invocation-record", str(root / "invocation.json"),
                        "--expected-invocation-digest", record_digest,
                        "--out-dir", str(root / out)]
                if version is not None:
                    args += ["--pack-version", str(version)]
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    code = judge.main(args)
                return code, json.loads(stdout.getvalue())

            code1, v1 = run(None, "out-v1")
            code2, v2 = run(2, "out-v2")
        self.assertEqual(code1, code2)
        self.assertEqual(v1["kernel_execution"], "complete")
        self.assertEqual(v2["kernel_execution"], "complete")
        self.assertNotIn("pack_profile", v1)
        self.assertEqual(v2.pop("pack_profile"), "rules-observation-v2")
        # The bundles differ by design (schema, declarations, contracts), so
        # their digests and the certificates bound to them do; every
        # decision, finding and disclosure is identical.
        unbound = ("combined_bundle_digest", "observation_bundle_digest", "certificates")
        self.assertNotEqual(v1["combined_bundle_digest"], v2["combined_bundle_digest"])
        self.assertEqual({k: v for k, v in v1.items() if k not in unbound},
                         {k: v for k, v in v2.items() if k not in unbound})


@unittest.skipUnless(shutil.which("souffle"), "real pinned Souffle required")
class NativeObservationSpecTests(unittest.TestCase):
    def test_v2_receipts_agree_in_all_three_backends(self):
        from capcov.claims.souffle import program_for_pack
        from capcov.claims.souffle.compile import compile_program
        # The checker depends only on the pack program, so one compile serves
        # all four receipts.
        with tempfile.TemporaryDirectory() as cache:
            checker = compile_program(program_for_pack(pack_bundle(version=2)),
                                      cache_dir=os.environ.get("CAPCOV_SOUFFLE_CACHE_DIR", cache))
            for name, directory in RECEIPTS.items():
                with self.subTest(receipt=name), tempfile.TemporaryDirectory() as tmp:
                    result = observation_join.build(directory, fixture=True, version=2)
                    observation_join.evaluate_join(result, tmp, kernels="three", checker=checker)
                    self.assertIsNone(result.mismatch)
                    self.assertTrue(result.result.matched)
                    self.assertEqual([r.backend for r in result.closures()],
                                     ["python", "souffle", "souffle-compiled"])
                    self.assertTrue(result.certificates)
                    summary = observation_join.summary(result)
                    self.assertEqual(summary["status"], "complete")
                    self.assertEqual(summary["observations_agree"],
                                     "supported" if name == "agree" else "unresolved")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
