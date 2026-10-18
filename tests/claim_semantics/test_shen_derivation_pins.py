"""Byte pins for the Shen workbench's top-down derivation and why-not search.

The search in ``shen/claim-workbench.shen`` is written as Shen Prolog
(``defprolog``) clauses.  The pinned result blocks in
``fixtures/shen_derivation_pins.json`` were recorded from the list-recursive
search those clauses replaced, so they hold the output contract fixed byte
for byte: derivation trees, alternative order, ``work``/``nodes`` counters,
truncation reasons and named refusals.  The authored pack covers what the
go_app fixture leaves thin: linear recursion (``path``), mutual recursion
through one SCC (``ra``/``rb``), negation under a completeness witness with
symbol and number comparisons (``clean``), a constant in a body atom
(``hub``), bounds that truncate, why-not alternatives that are nested one
level and truncated at ``max_alternatives``, and the non-linear recursion
refusal.  Positive certificates are also re-derived by the Python extractor
and rechecked, so a pin can never freeze a wrong answer.

Re-record (only when the contract deliberately changes):
``python3 tests/claim_semantics/test_shen_derivation_pins.py --record``.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import unittest
from pathlib import Path

from capcov.claims import bundle_from_json, canonical_json, shen
from capcov.claims.evaluator import evaluate
from capcov.claims.static import certificate

HERE = Path(__file__).resolve().parent
PINS = HERE / "fixtures" / "shen_derivation_pins.json"
RUNTIME_PRESENT = bool(shutil.which("bifrost") and os.environ.get("BIFROST_SHEN_GO"))
SKIP_REASON = "bifrost on PATH and BIFROST_SHEN_GO are required; the Shen runtime is never mocked"
if os.environ.get("CAPCOV_SHEN_REQUIRED") and not RUNTIME_PRESENT:
    raise RuntimeError("CAPCOV_SHEN_REQUIRED is set but " + SKIP_REASON)

IX = hashlib.sha256(b"capcov shen derivation pins").hexdigest()


def _rel(name, cols, *, primitive=True, modality="observation", completes=None):
    columns = [{"name": "index", "type": "digest", "context": True}]
    columns += [{"name": n, "type": t, "context": False} for n, t in cols]
    return {"name": name, "columns": columns, "modality": modality if primitive else "derived",
            "polarity": "positive", "binding": "static", "primitive": primitive, "producer_classes": [],
            "context_indices": ["index"], "completes": completes, "finite": False, "nonempty": False,
            "compatibility_targets": [], "compatibility_context_indices": []}


def _v(name):
    return {"name": name}


def _c(value, type_name="symbol"):
    return {"value": value, "type": type_name}


def _atom(relation, *terms, negated=False):
    return {"relation": relation, "terms": [_v("IX"), *terms], "negated": negated}


def _rule(name, head, *body):
    return {"name": name, "head": head, "body": list(body), "aggregation": None}


SYM = [("a", "symbol")]
PAIR = [("a", "symbol"), ("b", "symbol")]
RELATIONS = [
    _rel("edge", PAIR), _rel("blocked", SYM), _rel("weight", [("a", "symbol"), ("w", "unsigned")]),
    _rel("start", SYM), _rel("blocked_closed", [], modality="completeness", completes="blocked"),
    _rel("path", PAIR, primitive=False), _rel("clean", PAIR, primitive=False),
    _rel("hub", SYM, primitive=False), _rel("ra", SYM, primitive=False), _rel("rb", SYM, primitive=False),
    _rel("far", SYM, primitive=False), _rel("deep", SYM, primitive=False),
]
RULES = [
    _rule("path_base", _atom("path", _v("A"), _v("B")), _atom("edge", _v("A"), _v("B"))),
    _rule("path_step", _atom("path", _v("A"), _v("C")), _atom("path", _v("A"), _v("B")), _atom("edge", _v("B"), _v("C"))),
    _rule("clean", _atom("clean", _v("A"), _v("B")), _atom("path", _v("A"), _v("B")),
          {"relation": "blocked_closed", "terms": [_v("IX")], "negated": False},
          _atom("blocked", _v("B"), negated=True), _atom("weight", _v("B"), _v("W")),
          {"left": _v("W"), "operator": "<", "right": _c(10, "unsigned")},
          {"left": _v("A"), "operator": "!=", "right": _v("B")}),
    _rule("hub", _atom("hub", _v("A")), _atom("edge", _v("A"), _c("hub"))),
    _rule("ra_base", _atom("ra", _v("X")), _atom("start", _v("X"))),
    _rule("rb_step", _atom("rb", _v("Y")), _atom("ra", _v("X")), _atom("edge", _v("X"), _v("Y"))),
    _rule("ra_step", _atom("ra", _v("Y")), _atom("rb", _v("X")), _atom("edge", _v("X"), _v("Y"))),
    *[_rule(f"far{i}", _atom("far", _v("A")), _atom("path", _v("A"), _v("B")), _atom("edge", _v("B"), _c(f"x{i}")))
      for i in range(6)],
    _rule("deep", _atom("deep", _v("A")), _atom("far", _v("A"))),
]
NODES = ["n0", "n1", "n2", "n3", "n4", "n5", "hub"]
EDGES = [("n0", "n1"), ("n1", "n2"), ("n2", "n3"), ("n3", "n4"), ("n0", "n2"), ("n2", "hub"),
         ("hub", "n5"), ("n4", "n0"), ("n5", "n5")]
FACTS = ([("edge", list(e)) for e in EDGES] + [("blocked", ["n3"]), ("blocked_closed", [])]
         + [("weight", [n, 3 * i]) for i, n in enumerate(NODES)] + [("start", ["n0"])])
NON_LINEAR = [_rule("tc_base", _atom("tc", _v("A"), _v("B")), _atom("edge", _v("A"), _v("B"))),
              _rule("tc_join", _atom("tc", _v("A"), _v("C")), _atom("tc", _v("A"), _v("B")), _atom("tc", _v("B"), _v("C")))]


def pin_bundle(*, non_linear: bool = False):
    facts, evidence = [], []
    for i, (relation, row) in enumerate(FACTS):
        terms = [_c(IX, "digest")] + [_c(x, "unsigned") if isinstance(x, int) else _c(x) for x in row]
        atom = {"relation": relation, "terms": terms, "negated": False}
        facts.append(atom)
        evidence.append({"id": f"pin:{i:02d}:{relation}", "atom": atom, "context": {"index": IX},
                         "source": "authored derivation pin", "depends_on": [], "kind": "fact"})
    relations = RELATIONS + ([_rel("tc", PAIR, primitive=False)] if non_linear else [])
    rules = RULES + (NON_LINEAR if non_linear else [])
    return bundle_from_json({"schema_version": 1, "relations": relations, "facts": facts, "rules": rules,
                             "claims": [], "metadata": [], "evidence": evidence, "mappings": [],
                             "diagnostic_policy": {}, "diagnostics": [], "outputs": []},
                            validate=not non_linear)


# (id, kind, relation, row without the index, max_depth, max_nodes, non_linear pack)
CASES = [
    ("path-recursive", "derive", "path", ["n0", "n4"], 64, 10000, False),
    ("path-cycle", "derive", "path", ["n4", "n4"], 64, 10000, False),
    ("clean-negation-comparisons", "derive", "clean", ["n0", "n2"], 64, 10000, False),
    ("hub-constant", "derive", "hub", ["n2"], 64, 10000, False),
    ("ra-mutual-recursion", "derive", "ra", ["n5"], 64, 10000, False),
    ("path-truncated-nodes", "derive", "path", ["n0", "n4"], 64, 5, False),
    ("ra-truncated-depth", "derive", "ra", ["n5"], 1, 10000, False),
    ("clean-blocked-why-not", "why-not", "clean", ["n0", "n3"], 64, 10000, False),
    ("clean-comparison-derive-negative", "derive", "clean", ["n0", "hub"], 64, 10000, False),
    ("deep-nested-truncated-why-not", "why-not", "deep", ["n0"], 64, 10000, False),
    ("far-why-not", "why-not", "far", ["n5"], 64, 10000, False),
    ("tc-non-linear-refused", "derive", "tc", ["n0", "n4"], 64, 10000, True),
]


def block(stdout: str) -> str:
    lines = stdout.splitlines()
    return "\n".join(lines[lines.index(shen.BEGIN_MARKER) + 1:lines.index(shen.END_MARKER)])


def run_case(case) -> str:
    _, kind, relation, row, max_depth, max_nodes, non_linear = case
    request = {"kind": kind, "relation": relation, "row": [IX, *row]}
    try:
        return block(shen.run(pin_bundle(non_linear=non_linear), request, max_depth=max_depth,
                              max_nodes=max_nodes).stdout)
    except shen.ShenFailure as exc:
        return f"refused {exc.kind}: {exc.message}"


@unittest.skipUnless(RUNTIME_PRESENT, SKIP_REASON)
class ShenDerivationPinTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pins = json.loads(PINS.read_text(encoding="utf-8"))
        cls.bundle = pin_bundle()
        cls.relations = certificate.normalize_relations(evaluate(cls.bundle).relations)

    def test_pins_cover_every_case(self) -> None:
        self.assertEqual(sorted(self.pins), sorted(case[0] for case in CASES))

    def test_search_output_is_byte_identical_to_the_pins(self) -> None:
        for case in CASES:
            with self.subTest(case=case[0]):
                text = run_case(case)
                self.assertEqual(text, self.pins[case[0]])
                if text.startswith("refused"):
                    continue
                payload = json.loads(text)
                cert = payload.get("certificate")
                if payload.get("outcome") == "positive":
                    row = [IX, *case[3]]
                    self.assertEqual(cert, certificate.certify(self.bundle, self.relations, case[2], row))
                    self.assertTrue(certificate.recheck(self.bundle, cert, self.relations).ok)

    def test_pins_exercise_the_intended_paths(self) -> None:
        pins = {k: (v if v.startswith("refused") else json.loads(v)) for k, v in self.pins.items()}
        self.assertEqual(pins["path-recursive"]["certificate"]["steps"], 2)
        self.assertGreater(pins["ra-mutual-recursion"]["certificate"]["steps"], 0)
        self.assertTrue(pins["clean-negation-comparisons"]["certificate"]["absent"])
        self.assertTrue(pins["path-truncated-nodes"]["certificate"]["truncated"])
        self.assertTrue(pins["ra-truncated-depth"]["certificate"]["truncated"])
        self.assertEqual(pins["clean-comparison-derive-negative"]["outcome"], "negative")
        deep = pins["deep-nested-truncated-why-not"]["report"]
        self.assertTrue(deep["truncated"])
        self.assertIn("max_alternatives", deep["truncation"])
        self.assertTrue(pins["tc-non-linear-refused"].startswith("refused unsupported-construct"))

    def test_search_is_stated_as_horn_clauses(self) -> None:
        source = (shen.shen_dir() / "claim-workbench.shen").read_text(encoding="utf-8")
        for name in ("derivation", "application", "satisfies", "premises", "attempt", "blocked"):
            self.assertIn(f"(defprolog capcov.{name}\n", source)


if __name__ == "__main__":
    if "--record" in sys.argv:
        PINS.write_text(json.dumps({case[0]: run_case(case) for case in CASES}, indent=1, sort_keys=True) + "\n",
                        encoding="utf-8")
    else:
        unittest.main()
