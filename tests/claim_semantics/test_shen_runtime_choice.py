"""Selecting the Shen runtime (CAPCOV_SHEN_IMPL) and the numeric contract.

``RuntimeSelectionTest`` needs no runtime: it pins how a runtime is chosen,
named and hashed, that shen-go records keep their earlier shape, and that the
transport refuses integers past 2**53 and floats whatever runtime is selected.
``NumericContractTest`` runs the selected runtime on integers at the edge of
that contract, and ``TextContractTest`` on non-ASCII and quoted strings; both
require the certificate Python computes, so running them under each runtime
shows whether the runtimes agree there.  (shen-scheme d037ae6 does not on
text: its ``pr`` UTF-8-encodes strings its reader built byte by byte, so every
byte above 127 comes back double-encoded; docs/shen-runtime-choice.md.)
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from capcov import shen_runtime
from capcov.claims import bundle_from_json, modelcheck, shen
from capcov.claims.evaluator import evaluate
from capcov.claims.static import certificate
from capcov.operations import OperationError, _native_shen

RUNTIME_PRESENT = bool(shutil.which("bifrost") and shen_runtime.selected().binary())
SKIP_REASON = "bifrost on PATH and the selected runtime's binary variable are required"
if os.environ.get("CAPCOV_SHEN_REQUIRED") and not RUNTIME_PRESENT:
    raise RuntimeError("CAPCOV_SHEN_REQUIRED is set but " + SKIP_REASON)

LIMIT = 2 ** 53 - 1
INDEX = "sha256:" + "0" * 64
THRESHOLD = 2 ** 52
ROWS = (LIMIT, -LIMIT, THRESHOLD, THRESHOLD - 1, 0, -1, 123456789012)


def _decl(name, columns, **kw):
    base = {"name": name, "columns": [{"name": c, "type": t, "context": c == "index"} for c, t in columns],
            "modality": "observation", "polarity": "positive", "binding": "static", "primitive": True,
            "producer_classes": [], "context_indices": ["index"], "completes": None, "finite": False,
            "nonempty": False, "compatibility_targets": [], "compatibility_context_indices": []}
    base.update(kw)
    return base


def _num(value):
    return {"relation": "num", "terms": [{"value": INDEX, "type": "digest"}, {"value": value, "type": "integer"}],
            "negated": False}


def numeric_bundle():
    """``big(IX, N) <- num(IX, N), N >= 2^52`` over integers up to 2^53 - 1."""
    return bundle_from_json({
        "schema_version": 1,
        "relations": [_decl("num", [("index", "digest"), ("n", "integer")]),
                      _decl("big", [("index", "digest"), ("n", "integer")], modality="derived", primitive=False)],
        "rules": [{"name": "big-if-large",
                   "head": {"relation": "big", "terms": [{"variable": "IX"}, {"variable": "N"}], "negated": False},
                   "body": [{"relation": "num", "terms": [{"variable": "IX"}, {"variable": "N"}], "negated": False},
                            {"left": {"variable": "N"}, "operator": ">=",
                             "right": {"value": THRESHOLD, "type": "integer"}}]}],
        "facts": [_num(n) for n in ROWS],
        "evidence": [{"id": f"num-{i}", "atom": _num(n), "context": {"index": INDEX},
                      "source": "numeric contract fixture", "depends_on": [], "kind": "fact"}
                     for i, n in enumerate(ROWS)],
        "claims": [],
    })


TEXTS = ("plain", "λ雪", 'quote " and \\ backslash', "naïve café")


def text_bundle():
    """``named(IX, S) <- tag(IX, S)`` over strings outside ASCII."""
    def tag(value):
        return {"relation": "tag", "terms": [{"value": INDEX, "type": "digest"}, {"value": value, "type": "symbol"}],
                "negated": False}
    return bundle_from_json({
        "schema_version": 1,
        "relations": [_decl("tag", [("index", "digest"), ("s", "symbol")]),
                      _decl("named", [("index", "digest"), ("s", "symbol")], modality="derived", primitive=False)],
        "rules": [{"name": "named-if-tagged",
                   "head": {"relation": "named", "terms": [{"variable": "IX"}, {"variable": "S"}], "negated": False},
                   "body": [{"relation": "tag", "terms": [{"variable": "IX"}, {"variable": "S"}], "negated": False}]}],
        "facts": [tag(t) for t in TEXTS],
        "evidence": [{"id": f"tag-{i}", "atom": tag(t), "context": {"index": INDEX},
                      "source": "text contract fixture", "depends_on": [], "kind": "fact"}
                     for i, t in enumerate(TEXTS)],
        "claims": [],
    })


def _executable(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xcf\xfa\xed\xfe" + b"fixture")
    path.chmod(0o755)
    return str(path)


class RuntimeSelectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="capcov-runtime-choice-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _scheme_tree(self) -> str:
        binary = _executable(self.tmp / "scheme" / "bin" / "shen-scheme")
        home = self.tmp / "scheme" / "lib" / "shen-scheme"
        (home / "shen-scheme").mkdir(parents=True)
        for name in ("petite.boot", "scheme.boot", "shen-scheme/runtime.so"):
            (home / name).write_bytes(name.encode())
        return binary

    def test_shen_go_is_the_default_and_unknown_names_are_refused(self) -> None:
        for value in (None, ""):
            env = {k: v for k, v in os.environ.items() if k != shen_runtime.SETTING}
            if value is not None:
                env[shen_runtime.SETTING] = value
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(shen_runtime.selected().name, "shen-go")
        with mock.patch.dict(os.environ, {shen_runtime.SETTING: "shen-cobol"}):
            with self.assertRaisesRegex(shen.ShenUnavailable, "CAPCOV_SHEN_IMPL='shen-cobol'"):
                shen.runtime()
            with self.assertRaisesRegex(modelcheck.ModelcheckUnavailable, "CAPCOV_SHEN_IMPL"):
                modelcheck.runtime()
            with self.assertRaisesRegex(OperationError, "CAPCOV_SHEN_IMPL"):
                _native_shen()

    def test_each_runtime_names_its_bifrost_adapter_and_variable(self) -> None:
        self.assertEqual({name: impl.env for name, impl in shen_runtime.IMPLS.items()},
                         {"shen-go": "BIFROST_SHEN_GO", "shen-scheme": "BIFROST_SHEN_SCHEME",
                          "shen-c": "BIFROST_SHEN_C"})
        for impl in shen_runtime.IMPLS.values():
            self.assertEqual(shen_runtime.bifrost_argv("/b", impl, "/d.shen"),
                             ["/b", "run", "--impl", impl.name, "--raw", "/d.shen"])
        self.assertEqual(shen_runtime.direct_argv("/x", "/d.shen"), ["/x", "script", "/d.shen"])

    def test_the_selected_runtime_is_the_one_resolved_and_its_variable_is_required(self) -> None:
        binary = _executable(self.tmp / "c" / "shen-c")
        bifrost = _executable(self.tmp / "bin" / "bifrost")
        with mock.patch.dict(os.environ, {shen_runtime.SETTING: "shen-c", "BIFROST_SHEN_C": ""}), \
                mock.patch("shutil.which", return_value=bifrost):
            with self.assertRaisesRegex(shen.ShenUnavailable, "BIFROST_SHEN_C is not set"):
                shen.runtime()
        with mock.patch.dict(os.environ, {shen_runtime.SETTING: "shen-c", "BIFROST_SHEN_C": binary,
                                          "BIFROST_SHEN_GO": "/must/not/be/used"}), \
                mock.patch("shutil.which", return_value=bifrost):
            rt = shen.runtime()
        self.assertEqual((rt.impl, rt.binary, rt.support_sha256), ("shen-c", binary, ()))
        self.assertEqual(rt.sha256, shen_runtime.sha256_file(binary))
        record = rt.as_dict()
        self.assertEqual(record["impl"], "shen-c")
        self.assertEqual(record["invocation"], ["bifrost", "run", "--impl", "shen-c", "--raw", "<driver.shen>"])
        self.assertNotIn("shen_go", record)

    def test_shen_scheme_identity_covers_its_boot_files_and_runtime_object(self) -> None:
        binary = self._scheme_tree()
        impl = shen_runtime.IMPLS["shen-scheme"]
        support = dict(shen_runtime.support_sha256(impl, binary))
        self.assertEqual(sorted(support), ["petite.boot", "scheme.boot", "shen-scheme/runtime.so"])
        before = shen_runtime.identity_sha256(shen_runtime.sha256_file(binary), tuple(support.items()))
        self.assertNotEqual(before, shen_runtime.sha256_file(binary))
        (Path(binary).parents[1] / "lib" / "shen-scheme" / "scheme.boot").write_bytes(b"another heap")
        after = shen_runtime.identity_sha256(shen_runtime.sha256_file(binary),
                                             shen_runtime.support_sha256(impl, binary))
        self.assertNotEqual(before, after)
        (Path(binary).parents[1] / "lib" / "shen-scheme" / "petite.boot").unlink()
        bifrost = _executable(self.tmp / "bin" / "bifrost")
        with mock.patch.dict(os.environ, {shen_runtime.SETTING: "shen-scheme", "BIFROST_SHEN_SCHEME": binary}), \
                mock.patch("shutil.which", return_value=bifrost):
            with self.assertRaisesRegex(shen.ShenUnavailable, "petite.boot is missing"):
                shen.runtime()

    def test_shen_go_records_keep_their_shape(self) -> None:
        rt = shen.Runtime("/b", "/go", "a" * 64, "/shen", (("x.shen", "c" * 64),))
        self.assertEqual(list(rt.as_dict()), ["bifrost", "impl", "shen_go", "shen_go_sha256", "shen_dir",
                                              "library_sha256", "invocation"])
        self.assertEqual(rt.sha256, "a" * 64)
        mc = modelcheck.Runtime("/b", "b" * 64, "/go", "a" * 64, "/mc", ())
        self.assertEqual(mc.as_dict(), {"impl": "shen-go", "bifrost_sha256": "b" * 64, "shen_go_sha256": "a" * 64,
                                        "checker_binary": "a" * 64,
                                        "invocation": ["bifrost", "run", "--impl", "shen-go", "--raw",
                                                       "<driver.shen>"]})
        binary = _executable(self.tmp / "go" / "shen")
        self.assertEqual(shen_runtime.runtime_record(shen_runtime.IMPLS["shen-go"], binary),
                         {"shen": shen_runtime.sha256_file(binary)})

    def test_modelcheck_certificate_runtime_keys_follow_the_recorded_runtime(self) -> None:
        support = (("petite.boot", "1" * 64), ("scheme.boot", "2" * 64), ("shen-scheme/runtime.so", "3" * 64))
        for impl, extra in (("shen-go", ()), ("shen-c", ()), ("shen-scheme", support)):
            with self.subTest(impl=impl):
                doc = modelcheck.Runtime("/b", "b" * 64, "/x", "a" * 64, "/mc", (), impl, extra).as_dict()
                self.assertEqual(set(doc), modelcheck._runtime_keys(impl))
        self.assertIsNone(modelcheck._runtime_keys("shen-cobol"))

    def test_children_never_inherit_runtime_relocation_variables(self) -> None:
        impl = shen_runtime.IMPLS["shen-scheme"]
        env = shen_runtime.child_env(impl, "/s", {"PATH": "/bin", "SHEN_SCHEME_HOME": "/elsewhere",
                                                  "SHEN_SCHEME_RUNTIME": "petite", "SHEN_C_HOME": "/c"})
        self.assertEqual(env, {"PATH": "/bin", "BIFROST_SHEN_SCHEME": "/s"})

    def test_the_numeric_contract_does_not_depend_on_the_runtime(self) -> None:
        for name in shen_runtime.IMPLS:
            with self.subTest(impl=name), mock.patch.dict(os.environ, {shen_runtime.SETTING: name}):
                self.assertEqual(shen._literal(LIMIT), str(LIMIT))
                self.assertEqual(shen._literal(-LIMIT), str(-LIMIT))
                for value in (2 ** 53, -(2 ** 53), 10 ** 30):
                    with self.assertRaises(shen.ShenFailure) as ctx:
                        shen._literal(value)
                    self.assertEqual(ctx.exception.kind, "invalid-input")
                with self.assertRaisesRegex(shen.ShenFailure, "float values are not transported"):
                    shen._literal(3.0)


@unittest.skipUnless(RUNTIME_PRESENT, SKIP_REASON)
class NumericContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = numeric_bundle()
        cls.relations = certificate.normalize_relations(evaluate(cls.bundle).relations)

    def test_integers_at_the_contract_edge_derive_the_python_certificate(self) -> None:
        self.assertEqual(sorted(n for _, n in self.relations["big"]), [THRESHOLD, LIMIT])
        for row in self.relations["big"]:
            with self.subTest(n=row[1]):
                result = shen.evaluate(self.bundle, None, "big", row)
                self.assertEqual(result.outcome, "positive")
                self.assertEqual(result.certificate, certificate.certify(self.bundle, self.relations, "big", row))
                self.assertEqual(result.provenance.runtime.impl, shen_runtime.selected().name)

    def test_rows_below_the_threshold_are_not_derivable(self) -> None:
        for n in (THRESHOLD - 1, -LIMIT):
            with self.subTest(n=n), self.assertRaises(shen.NotDerivable):
                shen.derive(self.bundle, None, "big", [INDEX, n])

    def test_the_provenance_names_the_runtime_that_ran(self) -> None:
        result = shen.evaluate(self.bundle, None, "big", [INDEX, LIMIT])
        rt = result.provenance.runtime
        impl = shen_runtime.selected()
        self.assertEqual(rt.binary, impl.binary())
        self.assertEqual(rt.binary_sha256, hashlib.sha256(Path(impl.binary()).read_bytes()).hexdigest())
        self.assertEqual(rt.support_sha256, shen_runtime.support_sha256(impl, impl.binary()))
        self.assertEqual(result.provenance.as_dict()["runtime"]["impl"], impl.name)


@unittest.skipUnless(RUNTIME_PRESENT, SKIP_REASON)
class TextContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = text_bundle()
        cls.relations = certificate.normalize_relations(evaluate(cls.bundle).relations)

    def test_strings_outside_ascii_derive_the_python_certificate(self) -> None:
        self.assertEqual(sorted(s for _, s in self.relations["named"]), sorted(TEXTS))
        for row in self.relations["named"]:
            with self.subTest(s=row[1]):
                result = shen.evaluate(self.bundle, None, "named", row)
                self.assertEqual(result.outcome, "positive")
                self.assertEqual(result.certificate, certificate.certify(self.bundle, self.relations, "named", row))


if __name__ == "__main__":
    unittest.main()
