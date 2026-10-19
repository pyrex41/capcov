"""Pinned Shen runtime adapter and deterministic data transport (section 18).

The Shen workbench (``shen/*.shen`` in the source tree) elaborates a rule
pack, runs the structural authority checks, computes the stratified closure
of a bundle's ground facts, searches for a bounded derivation of one
conclusion row and renders it as a ``capcov-static-certificate-v1``
certificate.  This module only *translates*: it writes a validated Bundle as
deterministic Shen data, launches the pinned runtime through the bifrost
launcher with a hard timeout, closed stdin and captured output, and parses
the JSON the Shen side prints back.  Nothing here evaluates rules or decides
a semantic answer; ``evaluator.py`` is never consulted.

Named operational failures
--------------------------
* ``ShenUnavailable`` -- the launcher or the pinned binary is not present.
* ``ShenFailure(kind, ...)`` -- the run happened but did not yield a usable
  answer.  ``kind`` is one of ``timeout``, ``runtime-exit``,
  ``malformed-output``, ``invalid-input``, ``inconsistent-closure``,
  ``unsupported-construct``, ``resource-exhausted``, ``frozen-pack-mismatch``,
  ``elaborated-pack-mismatch``, ``rule-pack-mismatch``, ``internal`` or
  ``shen-error``.
* ``NotDerivable`` -- a semantic outcome, not a failure: the requested row is
  not in the closure; it carries the why-not report.

Recorded provenance (section 18): sha256 of the canonical JSON input, of the
generated Shen file, of the runtime binary and of the elaborated pack the
Shen side printed back, plus the Shen side's own checksum of that pack.

The runtime is shen-go unless ``CAPCOV_SHEN_IMPL`` names another one
(``capcov.shen_runtime``); the runtime record then names it and its files.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
from typing import Any, Mapping, Sequence

from .. import shen_runtime
from .ir import (Aggregation, Atom, Bundle, BundleIngestionError, Comparison, Constant,
                 Rule, Variable, bundle_from_json, canonical_dict, canonical_json, digest)
from .validation import ValidationError, assert_valid
from .static.certificate import DEFAULT_MAX_DEPTH, DEFAULT_MAX_NODES, rules_digest

DEFAULT_TIMEOUT = 60.0
# Compiling the typed-authority datatypes dominates a typed run (minutes on a
# loaded host); its default deadline is separate so ordinary runs keep theirs.
TYPED_TIMEOUT = 900.0
IMPL = shen_runtime.DEFAULT_IMPL
LIBRARY_FILES = ("claim-workbench.shen", "rule-authority.shen", "certificate-output.shen", "evidence-authority-v2.shen", "spec-elaborator.shen",
                 "spec-templates.shen")
# The typed authority (roadmap W2): its primitive predicates, one datatype per
# file (shen/modelcheck/prelude.shen explains why), then the reifier.  Loaded
# only for typed-authority requests, after LIBRARY_FILES.
TYPED_LIBRARY_FILES = tuple(f"claim-types/{name}.shen" for name in (
    "prelude", "telescope", "test", "zip", "remap", "arg-at", "same", "classify",
    "bind", "bound-terms", "declared", "typed", "conforms", "conclusion", "side", "linear",
    "authorized", "widening", "head", "closes", "complete", "promotion", "legacy-head",
    "legacy-widening", "contracts")) + ("typed-authority.shen",)
BEGIN_MARKER = "<<<CAPCOV-SHEN-JSON-BEGIN>>>"
END_MARKER = "<<<CAPCOV-SHEN-JSON-END>>>"
_EXACT_INT_LIMIT = 2 ** 53  # shen-go numbers are float64; the limit holds for every runtime

_ERROR_KINDS = (
    ("capcov-invalid-input", "invalid-input"),
    ("capcov-inconsistent", "inconsistent-closure"),
    ("capcov-unsupported-construct", "unsupported-construct"),
    ("capcov-resource-exhausted", "resource-exhausted"),
    ("capcov-frozen-mismatch", "frozen-pack-mismatch"),
    ("capcov-truncated", "truncated"),
    ("capcov-internal", "internal"),
)


class ShenUnavailable(RuntimeError):
    """The bifrost launcher or the selected runtime binary cannot be used."""

    operational_failure = "shen-unavailable"


class ShenFailure(RuntimeError):
    """A Shen run that did not produce a usable answer; ``kind`` names why."""

    def __init__(self, kind: str, message: str, *, stdout: str = "", stderr: str = "",
                 returncode: int | None = None, provenance: "Provenance | None" = None) -> None:
        super().__init__(f"{kind}: {message}")
        self.kind = kind
        self.message = message
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.provenance = provenance

    @property
    def operational_failure(self) -> str:
        return self.kind


class NotDerivable(Exception):
    """The requested row is not derivable; ``why_not`` explains the misses."""

    def __init__(self, relation: str, row: Sequence[Any], why_not: Mapping[str, Any],
                 provenance: "Provenance") -> None:
        super().__init__(f"{relation}{canonical_json(list(row))} is not derivable")
        self.relation = relation
        self.row = tuple(row)
        self.why_not = dict(why_not)
        self.provenance = provenance


# ---------------------------------------------------------------------------
# runtime resolution


@dataclass(frozen=True)
class Runtime:
    bifrost: str
    binary: str
    binary_sha256: str
    shen_dir: str
    library_sha256: tuple[tuple[str, str], ...]
    impl: str = IMPL
    support_sha256: tuple[tuple[str, str], ...] = ()

    @property
    def sha256(self) -> str:
        """The runtime's identity digest (the binary's own for shen-go)."""
        return shen_runtime.identity_sha256(self.binary_sha256, self.support_sha256)

    def as_dict(self) -> dict[str, Any]:
        if self.impl == IMPL:
            return {"bifrost": self.bifrost, "impl": IMPL, "shen_go": self.binary,
                    "shen_go_sha256": self.binary_sha256, "shen_dir": self.shen_dir,
                    "library_sha256": dict(self.library_sha256),
                    "invocation": shen_runtime.invocation(shen_runtime.IMPLS[IMPL])}
        return {"bifrost": self.bifrost, "impl": self.impl, "binary": self.binary,
                "binary_sha256": self.binary_sha256, "support_sha256": dict(self.support_sha256),
                "runtime_sha256": self.sha256, "shen_dir": self.shen_dir,
                "library_sha256": dict(self.library_sha256),
                "invocation": shen_runtime.invocation(shen_runtime.IMPLS[self.impl])}


_sha256_file = shen_runtime.sha256_file


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def shen_dir() -> Path:
    override = os.environ.get("CAPCOV_SHEN_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "shen"


def runtime(typed: bool = False) -> Runtime:
    """Resolve the selected runtime or raise ``ShenUnavailable``; never falls back.

    ``typed`` adds the typed-authority libraries (hashed like the others)."""
    try:
        impl = shen_runtime.selected()
    except shen_runtime.UnknownImpl as exc:
        raise ShenUnavailable(str(exc)) from None
    bifrost = shutil.which("bifrost")
    if not bifrost:
        raise ShenUnavailable("bifrost launcher is not on PATH")
    binary = impl.binary()
    if not binary:
        raise ShenUnavailable(f"{impl.env} is not set; the pinned {impl.name} binary must be named explicitly")
    if not (os.path.isfile(binary) and os.access(binary, os.X_OK)):
        raise ShenUnavailable(f"{impl.env}={binary!r} is not an executable file")
    try:
        support = shen_runtime.support_sha256(impl, binary)
    except FileNotFoundError as exc:
        raise ShenUnavailable(str(exc)) from None
    directory = shen_dir()
    libraries = []
    for name in LIBRARY_FILES + (TYPED_LIBRARY_FILES if typed else ()):
        path = directory / name
        if not path.is_file():
            raise ShenUnavailable(f"workbench source {path} is missing")
        libraries.append((name, _sha256_file(path)))
    return Runtime(bifrost, binary, _sha256_file(binary), str(directory), tuple(libraries), impl.name, support)


# ---------------------------------------------------------------------------
# translation: Bundle -> Shen data


def _string(value: str) -> str:
    # The Shen reader has no string escapes and a literal cannot contain a
    # double quote; such strings are rebuilt at load time from their parts.
    if '"' not in value:
        return '"' + value + '"'
    return "(capcov.dq [" + " ".join('"' + part + '"' for part in value.split('"')) + "])"


def _literal(value: Any) -> str:
    if value is None:
        return "capcov.null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        # shen-scheme and shen-c are exact past 2^53 but shen-go is not; one
        # limit for every runtime keeps an answer independent of the runtime.
        if abs(value) >= _EXACT_INT_LIMIT:
            raise ShenFailure("invalid-input", f"integer {value} exceeds the runtime's exact range (2^53)")
        return str(value)
    if isinstance(value, float):
        raise ShenFailure("invalid-input", "float values are not transported (shen-go prints 3.0 as 3 and "
                          "shen-c as 3.0, which would break canonical row keys)")
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, Mapping):
        pairs = " ".join(f"(@p {_string(k)} {_literal(v)})" for k, v in sorted(value.items()))
        return "(capcov.obj [" + pairs + "])"
    if isinstance(value, (list, tuple)):
        return "(capcov.arr [" + " ".join(_literal(v) for v in value) + "])"
    raise ShenFailure("invalid-input", f"value of type {type(value).__name__} is not transportable")


def _plain(value: Any) -> Any:
    return canonical_dict(value)


def _term(term: Any) -> str:
    if isinstance(term, Variable):
        return f"[capcov.v {_string(term.name)}]"
    if isinstance(term, Constant):
        type_name = _string(str(term.type)) if term.type is not None else "capcov.null"
        return f"[capcov.c {_literal(_plain(term.value))} {type_name}]"
    raise ShenFailure("invalid-input", "rule term is neither a variable nor a constant")


def _terms(terms: Sequence[Any]) -> str:
    return "[" + " ".join(_term(t) for t in terms) + "]"


def _body_item(item: Any) -> str:
    if isinstance(item, Atom):
        tag = "capcov.neg" if item.negated else "capcov.pos"
        return f"[{tag} {_string(item.relation)} {_terms(item.terms)}]"
    if isinstance(item, Comparison):
        return f"[capcov.cmp {_term(item.left)} {_string(item.operator)} {_term(item.right)}]"
    raise ShenFailure("invalid-input", "rule body item is neither an atom nor a comparison")


def _aggregation(agg: Aggregation | None) -> str:
    if agg is None:
        return "capcov.null"
    return ("[" + " ".join([_string(agg.name), _string(agg.relation),
                            "[" + " ".join(_string(g) for g in agg.group_by) + "]",
                            _string(agg.value_variable), _string(agg.operator),
                            _literal(agg.domain), _literal(agg.closure_witness)]) + "]")


def _rule(rule: Rule) -> str:
    head = f"[{_string(rule.head.relation)} {_terms(rule.head.terms)}]"
    body = "[" + " ".join(_body_item(item) for item in rule.body) + "]"
    return f"[{_string(rule.name)} {_string(digest(rule))} {head} {body} {_aggregation(rule.aggregation)}]"


def _decl(decl: Any) -> str:
    columns = "[" + " ".join(f"[{_string(c.name)} {_string(str(c.type))} {_literal(bool(c.context))}]"
                             for c in decl.columns) + "]"
    strings = lambda items: "[" + " ".join(_string(s) for s in items) + "]"  # noqa: E731
    return "[" + " ".join([
        _string(decl.name), _string(str(decl.modality)), _string(str(decl.polarity)),
        _string(str(decl.binding)), _literal(bool(decl.primitive)), columns,
        strings(decl.context_indices), _literal(decl.completes), _literal(bool(decl.finite)),
        _literal(bool(decl.nonempty)), strings(decl.compatibility_targets),
        strings(decl.compatibility_context_indices), strings(decl.producer_classes)]) + "]"


def _facts(bundle: Bundle) -> list[str]:
    evidence: dict[tuple[str, str], list[str]] = {}
    for record in bundle.evidence:
        row = [_plain(term.value) if isinstance(term, Constant) else None for term in record.atom.terms]
        evidence.setdefault((record.atom.relation, canonical_json(row)), []).append(record.id)
    out = []
    for atom in bundle.facts:
        if any(not isinstance(term, Constant) for term in atom.terms):
            raise ShenFailure("invalid-input", f"fact of {atom.relation} is not ground")
        row = [_plain(term.value) for term in atom.terms]
        ids = sorted(evidence.get((atom.relation, canonical_json(row)), []))
        out.append(f"[{_string(atom.relation)} [{' '.join(_literal(v) for v in row)}] "
                   f"[{' '.join(_string(i) for i in ids)}]]")
    return out


def _request_literal(request: Mapping[str, Any]) -> str:
    kind = request["kind"]
    if kind == "compile-spec":
        return "[capcov.compile-spec]"
    if kind == "authority":
        return "[capcov.authority]"
    if kind == "typed-authority":
        return "[capcov.typed-authority]"
    tag = {"derive": "capcov.derive", "why-not": "capcov.why-not"}[kind]
    row = "[" + " ".join(_literal(v) for v in request["row"]) + "]"
    return f"[{tag} {_string(request['relation'])} {row}]"


def _template_term(term: Mapping[str, Any]) -> str:
    if set(term) == {"name"}:
        return f"[capcov.v {_string(term['name'])}]"
    if set(term) == {"parameter", "type"}:
        return f"[capcov.param {_string(term['parameter'])} {_string(term['type'])}]"
    if set(term) == {"value", "type"}:
        return f"[capcov.c {_literal(term['value'])} {_string(term['type'])}]"
    raise ShenFailure("invalid-input", "template term is not a variable, constant or parameter")


def _template_item(item: Mapping[str, Any]) -> str:
    if set(item) == {"relation", "terms", "negated"}:
        tag = "capcov.neg" if item["negated"] is True else "capcov.pos"
        return f"[{tag} {_string(item['relation'])} [{' '.join(_template_term(t) for t in item['terms'])}]]"
    if set(item) == {"left", "operator", "right"}:
        return f"[capcov.cmp {_template_term(item['left'])} {_string(item['operator'])} {_template_term(item['right'])}]"
    raise ShenFailure("invalid-input", "template body item is neither an atom nor a comparison")


def _templates_literal(templates: Sequence[Any], instantiations: Sequence[Any]) -> str:
    """Raw, unexpanded template data for shen/spec-templates.shen.

    Template: [Name [Param ...] [[RuleName [HeadRel HeadTerms] Body] ...]];
    instantiation: [Name [Arg ...]]. Identifiers keep their ``$P`` text.
    """
    strings = lambda items: "[" + " ".join(_string(s) for s in items) + "]"  # noqa: E731
    rules = lambda items: "[" + " ".join(  # noqa: E731
        f"[{_string(r['name'])} [{_string(r['head']['relation'])} "
        f"[{' '.join(_template_term(t) for t in r['head']['terms'])}]] "
        f"[{' '.join(_template_item(i) for i in r['body'])}]]" for r in items) + "]"
    return ("[[" + " ".join(f"[{_string(n)} {strings(ps)} {rules(rs)}]" for n, ps, rs in templates) + "] ["
            + " ".join(f"[{_string(n)} {strings(args)}]" for n, args in instantiations) + "]]")


def render_driver(bundle: Bundle, request: Mapping[str, Any], *, frozen: str | None,
                  max_depth: int, max_nodes: int, directory: Path, bundle_digest: str,
                  rules_digest_value: str) -> str:
    """The complete Shen program for one request: libraries, data, entry point."""
    lines = [f"\\\\ generated by capcov.claims.shen for bundle {bundle_digest}; do not edit"]
    typed = request.get("kind") == "typed-authority"
    lines.extend(_library_lines(directory, typed))
    lines.extend(_data_lines(bundle, request, frozen=frozen, max_depth=max_depth, max_nodes=max_nodes,
                             bundle_digest=bundle_digest, rules_digest_value=rules_digest_value))
    if typed:
        # Every typed-authority unit is decided by the type checker (tc +).
        lines.append("(tc +)")
    lines.append("(capcov.main)")
    return "\n".join(lines) + "\n"


def _library_lines(directory: Path, typed: bool) -> list[str]:
    return [f"(load {_string(str(directory / name))})"
            for name in LIBRARY_FILES + (TYPED_LIBRARY_FILES if typed else ())]


def _data_lines(bundle: Bundle, request: Mapping[str, Any], *, frozen: str | None, max_depth: int,
                max_nodes: int, bundle_digest: str, rules_digest_value: str) -> list[str]:
    lines: list[str] = []
    # The runtime echoes the value of every top-level form it loads, so each
    # data form is wrapped to return the symbol ok instead of the data.
    lines.append("(do (set capcov.*in-decls* [" + "\n  ".join(_decl(d) for d in bundle.relations) + "]) ok)")
    lines.append("(do (set capcov.*in-facts* [" + "\n  ".join(_facts(bundle)) + "]) ok)")
    lines.append("(do (set capcov.*in-rules* [" + "\n  ".join(_rule(r) for r in bundle.rules) + "]) ok)")
    lines.append(f"(do (set capcov.*in-frozen* {_literal(frozen)}) ok)")
    lines.append(f"(do (set capcov.*in-bounds* [{int(max_depth)} {int(max_nodes)}]) ok)")
    lines.append(f"(do (set capcov.*in-digests* [{_string(bundle_digest)} {_string(rules_digest_value)}]) ok)")
    lines.append(f"(do (set capcov.*in-request* {_request_literal(request)}) ok)")
    if request.get("kind") == "compile-spec" and "templates" in request:
        lines.append(f"(do (set capcov.*spec-templates* "
                     f"{_templates_literal(request['templates'], request['instantiations'])}) ok)")
    lines.append(f"(do (set capcov.*schema-version* {bundle.schema_version}) ok)")
    capabilities = [[c.name, c.witness, c.left_dimension, c.right_dimension,
                     c.left_column, c.right_column, list(c.left_targets),
                     list(c.right_targets), c.symmetric] for c in bundle.compatibility_capabilities]
    scopes = [[s.relation, s.target, [list(p) for p in s.mapping]] for s in bundle.completeness_scopes]
    bridges = [[b.name, b.left_dimension, b.right_dimension, list(b.left_targets),
                list(b.right_targets)] for b in bundle.required_bridges]
    policies = [[p.name, p.rule, p.relation, p.rule_digest] for p in bundle.derived_completeness_policies]
    def data_literal(value):
        return "[" + " ".join(data_literal(v) for v in value) + "]" if isinstance(value, list) else _literal(value)

    for name, data in (("capabilities", capabilities), ("scopes", scopes), ("bridges", bridges), ("derived-policies", policies)):
        lines.append(f"(do (set capcov.*{name}* {data_literal(data)}) ok)")
    return lines


# ---------------------------------------------------------------------------
# the elaborated-pack checksum, recomputed in Python as an integrity cross-check


def pack_checksum(text: str) -> str:
    """The Shen side's two-lane checksum (claim-workbench.shen capcov.checksum-chunks)."""
    a, b = 7, 11
    for k in text.encode("utf-8"):
        a = (a * 4 + k + 1) % 2147483647
        b = (b * 3 + k + 1) % 2147483629
    return f"ck2-{a}-{b}"


# ---------------------------------------------------------------------------
# running


@dataclass(frozen=True)
class Provenance:
    runtime: Runtime
    request: dict[str, Any]
    bundle_digest: str
    rules_digest: str
    input_sha256: str
    generated_sha256: str
    generated_bytes: int
    elaborated_sha256: str | None
    elaborated_checksum: str | None
    elapsed_seconds: float
    returncode: int | None
    work: int | None
    bounds: dict[str, int]
    driver_path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "runtime": self.runtime.as_dict(), "request": self.request,
            "bundle_digest": self.bundle_digest, "rules_digest": self.rules_digest,
            "hashes": {"canonical_input_sha256": self.input_sha256,
                       "generated_shen_sha256": self.generated_sha256,
                       "runtime_binary_sha256": self.runtime.binary_sha256,
                       "elaborated_pack_sha256": self.elaborated_sha256,
                       "elaborated_pack_checksum": self.elaborated_checksum},
            "generated_bytes": self.generated_bytes, "elapsed_seconds": self.elapsed_seconds,
            "returncode": self.returncode, "work": self.work, "bounds": self.bounds,
            "driver_path": self.driver_path,
        }


@dataclass(frozen=True)
class ShenRun:
    payload: dict[str, Any]
    provenance: Provenance
    stdout: str
    stderr: str


def _classify(message: str) -> str:
    for prefix, kind in _ERROR_KINDS:
        if message.startswith(prefix):
            return kind
    return "shen-error"


def _extract(stdout: str) -> dict[str, Any]:
    # Markers are matched as whole lines: the runtime echoes loaded source
    # values (the quoted marker literal among them), which must not count.
    lines = stdout.splitlines()
    begins = [i for i, line in enumerate(lines) if line.strip() == BEGIN_MARKER]
    ends = [i for i, line in enumerate(lines) if line.strip() == END_MARKER]
    if len(begins) != 1 or len(ends) != 1 or ends[0] <= begins[0]:
        if not begins or not ends:
            raise ShenFailure("malformed-output", "no result block between the JSON markers")
        raise ShenFailure("malformed-output", "result block markers are not a single well-formed pair")
    return _parse_block(lines[begins[0] + 1:ends[0]])


def _parse_block(lines: Sequence[str]) -> dict[str, Any]:
    text = "\n".join(lines).strip()
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise ShenFailure("malformed-output", f"result block is not JSON: {exc}") from exc
    if not isinstance(payload, Mapping) or not isinstance(payload.get("kind"), str):
        raise ShenFailure("malformed-output", "result block is not an object with a kind")
    return dict(payload)


def _extract_blocks(stdout: str, count: int) -> list[dict[str, Any]]:
    """Exactly ``count`` alternating, well-formed result blocks, in order."""
    lines = stdout.splitlines()
    marks = [(i, line.strip()) for i, line in enumerate(lines) if line.strip() in (BEGIN_MARKER, END_MARKER)]
    expected = [BEGIN_MARKER, END_MARKER] * count
    if [m for _, m in marks] != expected:
        raise ShenFailure("malformed-output", f"expected {count} result blocks between the JSON markers")
    return [_parse_block(lines[marks[k][0] + 1:marks[k + 1][0]]) for k in range(0, len(marks), 2)]


def _argv(rt: Runtime, driver: Path, *, direct: bool) -> list[str]:
    """The launcher argv.  ``bifrost run`` kills the runtime after a fixed 60s,
    which a typed run (datatype compilation) or a batch exceeds on a loaded
    host, so those invoke the same pinned binary with the argv bifrost's
    adapter uses (``{bin} script {file}``) under the Python-side deadline."""
    if direct:
        return shen_runtime.direct_argv(rt.binary, driver)
    return shen_runtime.bifrost_argv(rt.bifrost, shen_runtime.IMPLS[rt.impl], driver)


def _env(rt: Runtime) -> dict[str, str]:
    return shen_runtime.child_env(shen_runtime.IMPLS[rt.impl], rt.binary)


def _timeout() -> float:
    raw = os.environ.get("CAPCOV_SHEN_TIMEOUT")
    return float(raw) if raw else DEFAULT_TIMEOUT


def run(bundle: Bundle, request: Mapping[str, Any], *, frozen: str | None = None,
        max_depth: int = DEFAULT_MAX_DEPTH, max_nodes: int = DEFAULT_MAX_NODES,
        timeout: float | None = None, keep: bool = False) -> ShenRun:
    """Translate, launch the pinned runtime once, and parse its answer.

    Raises ``ShenUnavailable`` when the runtime is missing and ``ShenFailure``
    for every run that does not yield a well-formed, non-error payload.
    """
    if bundle.schema_version == 2 and request.get("kind") not in {"authority", "typed-authority", "compile-spec"}:
        raise ShenFailure("unsupported-construct", "native v2 derivations require the versioned evaluation-basis protocol")
    rt = runtime(typed=request.get("kind") == "typed-authority")
    if max_depth < 1 or max_nodes < 1:
        raise ShenFailure("invalid-input", "max_depth and max_nodes must be positive")
    bundle_digest = digest(bundle)
    rules_digest_value = rules_digest(bundle)
    request = dict(request)
    canonical_input = canonical_json({"bundle": canonical_dict(bundle), "request": request,
                                      "bounds": {"max_depth": max_depth, "max_nodes": max_nodes},
                                      "frozen": frozen})
    workdir = Path(tempfile.mkdtemp(prefix="capcov-shen-"))
    driver = workdir / "driver.shen"
    program = render_driver(bundle, request, frozen=frozen, max_depth=max_depth, max_nodes=max_nodes,
                            directory=Path(rt.shen_dir), bundle_digest=bundle_digest,
                            rules_digest_value=rules_digest_value)
    driver.write_text(program, encoding="utf-8")
    generated_sha256 = _sha256_text(program)
    base = dict(runtime=rt, request=request, bundle_digest=bundle_digest, rules_digest=rules_digest_value,
                input_sha256=_sha256_text(canonical_input), generated_sha256=generated_sha256,
                generated_bytes=len(program.encode("utf-8")), elaborated_sha256=None,
                elaborated_checksum=None, elapsed_seconds=0.0, returncode=None, work=None,
                bounds={"max_depth": max_depth, "max_nodes": max_nodes},
                driver_path=str(driver) if keep else None)
    argv = _argv(rt, driver, direct=request.get("kind") == "typed-authority")
    env = _env(rt)
    limit = timeout if timeout is not None else (max(_timeout(), TYPED_TIMEOUT) if request.get("kind") == "typed-authority" else _timeout())
    started = time.monotonic()
    stdout = stderr = ""
    returncode: int | None = None
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=env, cwd=str(workdir), start_new_session=True)
        try:
            out, err = proc.communicate(timeout=limit)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            out, err = proc.communicate()
            elapsed = time.monotonic() - started
            raise ShenFailure("timeout", f"shen run exceeded {limit:g}s and was killed",
                              stdout=out.decode("utf-8", "replace"), stderr=err.decode("utf-8", "replace"),
                              returncode=proc.returncode,
                              provenance=Provenance(**{**base, "elapsed_seconds": elapsed,
                                                       "returncode": proc.returncode}))
        elapsed = time.monotonic() - started
        stdout = out.decode("utf-8", "replace")
        stderr = err.decode("utf-8", "replace")
        returncode = proc.returncode
        provenance = Provenance(**{**base, "elapsed_seconds": elapsed, "returncode": returncode})
        if returncode != 0:
            raise ShenFailure("runtime-exit", f"shen runtime exited with status {returncode}",
                              stdout=stdout, stderr=stderr, returncode=returncode, provenance=provenance)
        try:
            payload = _extract(stdout)
        except ShenFailure as exc:
            raise ShenFailure(exc.kind, exc.message, stdout=stdout, stderr=stderr, returncode=returncode,
                              provenance=provenance) from None
        if payload["kind"] == "error":
            message = str(payload.get("error", ""))
            raise ShenFailure(_classify(message), message, stdout=stdout, stderr=stderr,
                              returncode=returncode, provenance=provenance)
        elaborated_sha256 = None
        checksum = payload.get("elaborated_checksum")
        if "elaborated" in payload:
            text = canonical_json(payload["elaborated"])
            if pack_checksum(text) != checksum:
                raise ShenFailure("elaborated-pack-mismatch",
                                  "Python's re-serialisation of the printed-back elaborated pack does not "
                                  "reproduce the Shen checksum; the two canonical renderings disagree",
                                  stdout=stdout, stderr=stderr, returncode=returncode, provenance=provenance)
            elaborated_sha256 = _sha256_text(text)
        provenance = Provenance(**{**base, "elapsed_seconds": elapsed, "returncode": returncode,
                                   "elaborated_sha256": elaborated_sha256,
                                   "elaborated_checksum": checksum if isinstance(checksum, str) else None,
                                   "work": payload.get("work")})
        return ShenRun(payload, provenance, stdout, stderr)
    finally:
        if not keep:
            shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# rule packs


def _pack_bundle(rules: Any, *, validate: bool = True) -> Bundle:
    """A (by default validated) Bundle holding only a rule pack's declarations and rules."""
    if isinstance(rules, Bundle):
        return rules
    if not isinstance(rules, Mapping):
        raise ShenFailure("invalid-input", "rules must be a Bundle or a rule pack object")
    relations = [*rules.get("primitives", ()), *rules.get("supplementary_primitives", ()),
                 *rules.get("derived", ()), *rules.get("relations", ())]
    try:
        from .contracts import CONTRACT_FIELDS
        raw = {"schema_version": rules.get("schema_version", 1), "relations": relations,
               "rules": list(rules.get("rules", ()))}
        raw.update({key: rules[key] for key in CONTRACT_FIELDS if key in rules})
        return bundle_from_json(raw, validate=validate)
    except (BundleIngestionError, ValidationError) as exc:
        raise ShenFailure("invalid-input", f"rule pack is not a valid bundle: {exc}") from exc


def _check_pack_against(bundle: Bundle, rules: Any) -> None:
    """A rule pack supplied next to a bundle must be contained in it."""
    if rules is None:
        return
    pack = _pack_bundle(rules)
    from .contracts import CONTRACT_FIELDS
    if pack.schema_version != bundle.schema_version or any(
        not set(getattr(pack, key)).issubset(getattr(bundle, key)) for key in CONTRACT_FIELDS
    ):
        raise ShenFailure("rule-pack-mismatch", "rule pack schema or authority contracts differ from the bundle")
    have_rules = {digest(rule) for rule in bundle.rules}
    have_relations = {decl.name: digest(decl) for decl in bundle.relations}
    missing = [rule.name or digest(rule) for rule in pack.rules if digest(rule) not in have_rules]
    changed = [decl.name for decl in pack.relations if have_relations.get(decl.name) != digest(decl)]
    if missing or changed:
        raise ShenFailure("rule-pack-mismatch",
                          f"rule pack is not contained in the bundle (missing rules: {missing}; "
                          f"differing relations: {changed})")


# ---------------------------------------------------------------------------
# public API


@dataclass(frozen=True)
class AuthorityReport:
    ok: bool
    rules: tuple[dict[str, Any], ...]
    pack: tuple[dict[str, Any], ...]
    elaborated: dict[str, Any]
    elaborated_checksum: str
    provenance: Provenance

    def verdict(self, rule_name: str) -> dict[str, Any]:
        for verdict in self.rules:
            if verdict.get("rule") == rule_name:
                return verdict
        raise KeyError(rule_name)

    def failed_checks(self) -> list[tuple[str, str]]:
        out = [(v["rule"], c["id"]) for v in self.rules for c in v["checks"] if not c["ok"]]
        out.extend(("<pack>", c["id"]) for c in self.pack if not c["ok"])
        return out

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "rules": list(self.rules), "pack": list(self.pack),
                "elaborated_checksum": self.elaborated_checksum, "elaborated": self.elaborated,
                "provenance": self.provenance.as_dict()}


def _validated(bundle: Bundle) -> Bundle:
    try:
        assert_valid(bundle)
    except ValidationError as exc:
        raise ShenFailure("invalid-input", f"bundle does not validate: {exc}") from exc
    return bundle


def authority(bundle: Bundle | None = None, rules: Any = None, *, frozen: str | None = None,
              timeout: float | None = None, keep: bool = False, validate: bool = True) -> AuthorityReport:
    """Run the structural authority checks over a bundle's rules or a rule pack.

    ``rules`` (a rule pack object or a Bundle) takes precedence over ``bundle``;
    the checked pack is the declarations and rules of whichever is used.
    ``validate=False`` skips the Python validator so that rules it would
    already reject still reach the Shen authority checks (used by the planted
    bad-rule tests); production callers keep the default.
    """
    if rules is not None:
        source = _pack_bundle(rules, validate=validate)
    elif bundle is not None:
        source = _validated(bundle) if validate else bundle
    else:
        raise ShenFailure("invalid-input", "authority needs a bundle or a rule pack")
    result = run(source, {"kind": "authority"}, frozen=frozen, timeout=timeout, keep=keep)
    payload = result.payload
    if payload.get("kind") != "authority" or not isinstance(payload.get("rules"), list):
        raise ShenFailure("malformed-output", "authority payload has the wrong shape", stdout=result.stdout,
                          stderr=result.stderr, provenance=result.provenance)
    return AuthorityReport(bool(payload.get("ok")), tuple(payload["rules"]), tuple(payload.get("pack", ())),
                           dict(payload.get("elaborated") or {}), str(payload.get("elaborated_checksum")),
                           result.provenance)


@dataclass(frozen=True)
class TypedAuthorityReport(AuthorityReport):
    """``authority``'s report shape, decided by Shen's type checker.

    Each check carries ``basis``: ``typed`` (one sequent judgement unit),
    ``typed+contracts`` (that unit and the pack's ``cc-contracts`` judgement),
    ``trusted-elaborator`` (pack-level results taken from the workbench
    elaborator, not typed) or ``unsupported`` (a construct the typed IR does
    not represent; the check fails).  ``units`` counts typechecks run."""

    units: int = 0

    def bases(self) -> dict[tuple[str, str], str]:
        out = {(v["rule"], c["id"]): c["basis"] for v in self.rules for c in v["checks"]}
        out.update({("<pack>", c["id"]): c["basis"] for c in self.pack})
        return out


def typed_authority(bundle: Bundle | None = None, rules: Any = None, *, frozen: str | None = None,
                    timeout: float | None = None, keep: bool = False,
                    validate: bool = True) -> TypedAuthorityReport:
    """The typed third authority (roadmap W2): ``authority``'s checks, id for id,
    each decided by a typing judgement over the reified claim IR.

    Arguments are ``authority``'s.  It shares the elaboration and the frozen
    checksum (a mismatch is the same ``frozen-pack-mismatch`` refusal) but
    never reads the untyped verdicts.  See docs/typed-claim-authority.md for
    which semantic rules the judgements check and which functions are trusted.
    """
    if rules is not None:
        source = _pack_bundle(rules, validate=validate)
    elif bundle is not None:
        source = _validated(bundle) if validate else bundle
    else:
        raise ShenFailure("invalid-input", "typed authority needs a bundle or a rule pack")
    result = run(source, {"kind": "typed-authority"}, frozen=frozen, timeout=timeout, keep=keep)
    payload = result.payload
    if (payload.get("kind") != "typed-authority" or not isinstance(payload.get("rules"), list)
            or not isinstance(payload.get("units"), int)):
        raise ShenFailure("malformed-output", "typed authority payload has the wrong shape", stdout=result.stdout,
                          stderr=result.stderr, provenance=result.provenance)
    return TypedAuthorityReport(bool(payload.get("ok")), tuple(payload["rules"]), tuple(payload.get("pack", ())),
                                dict(payload.get("elaborated") or {}), str(payload.get("elaborated_checksum")),
                                result.provenance, int(payload["units"]))


def authority_batch(bundles: Sequence[Bundle], *, typed: bool = False, timeout: float | None = None,
                    validate: bool = True) -> list[AuthorityReport | ShenFailure]:
    """``authority`` (or, with ``typed``, ``typed_authority``) for several bundles
    in ONE runtime process, so the libraries load once.

    capcov.load-bundle resets all workbench state per bundle and the checksum
    cross-check applies per bundle.  Untyped verdicts equal a separate call's.
    Typed verdicts can only be STRICTER than a separate call's: an error that
    escapes a ``shen.typecheck`` unit poisons later units in the same process
    (docs/typed-claim-authority.md), which surfaces as refusals, never as
    admissions.  A bundle whose run reports an error yields its ``ShenFailure`` in
    place; an unusable process (timeout, exit, missing blocks) raises.  No
    frozen checksum is accepted: freezing is a per-pack identity decision.
    """
    kind = "typed-authority" if typed else "authority"
    sources = [_validated(b) if validate else b for b in bundles]
    if not sources:
        return []
    rt = runtime(typed=typed)
    directory = Path(rt.shen_dir)
    lines = [f"\\\\ generated by capcov.claims.shen for {len(sources)} bundles; do not edit"]
    lines.extend(_library_lines(directory, typed))
    bases = []
    for bundle in sources:
        bundle_digest, rules_digest_value = digest(bundle), rules_digest(bundle)
        request = {"kind": kind}
        bounds = {"max_depth": DEFAULT_MAX_DEPTH, "max_nodes": DEFAULT_MAX_NODES}
        lines.append("(tc -)")
        lines.extend(_data_lines(bundle, request, frozen=None, max_depth=DEFAULT_MAX_DEPTH,
                                 max_nodes=DEFAULT_MAX_NODES, bundle_digest=bundle_digest,
                                 rules_digest_value=rules_digest_value))
        if typed:
            lines.append("(tc +)")
        lines.append("(capcov.main)")
        canonical_input = canonical_json({"bundle": canonical_dict(bundle), "request": request,
                                          "bounds": bounds, "frozen": None})
        bases.append(dict(runtime=rt, request=request, bundle_digest=bundle_digest,
                          rules_digest=rules_digest_value, input_sha256=_sha256_text(canonical_input),
                          bounds=bounds))
    program = "\n".join(lines) + "\n"
    workdir = Path(tempfile.mkdtemp(prefix="capcov-shen-batch-"))
    try:
        driver = workdir / "driver.shen"
        driver.write_text(program, encoding="utf-8")
        argv = _argv(rt, driver, direct=True)
        env = _env(rt)
        limit = timeout if timeout is not None else (TYPED_TIMEOUT if typed else 0) + _timeout() * len(sources)
        started = time.monotonic()
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=env, cwd=str(workdir), start_new_session=True)
        try:
            out, err = proc.communicate(timeout=limit)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            out, err = proc.communicate()
            raise ShenFailure("timeout", f"shen batch exceeded {limit:g}s and was killed",
                              stdout=out.decode("utf-8", "replace"), stderr=err.decode("utf-8", "replace"))
        elapsed = time.monotonic() - started
        stdout, stderr = out.decode("utf-8", "replace"), err.decode("utf-8", "replace")
        if proc.returncode != 0:
            raise ShenFailure("runtime-exit", f"shen runtime exited with status {proc.returncode}",
                              stdout=stdout, stderr=stderr, returncode=proc.returncode)
        payloads = _extract_blocks(stdout, len(sources))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    generated_sha256 = _sha256_text(program)
    reports: list[AuthorityReport | ShenFailure] = []
    for base, payload in zip(bases, payloads):
        provenance = Provenance(**base, generated_sha256=generated_sha256,
                                generated_bytes=len(program.encode("utf-8")), elaborated_sha256=None,
                                elaborated_checksum=None, elapsed_seconds=elapsed,
                                returncode=proc.returncode, work=payload.get("work"))
        if payload.get("kind") == "error":
            message = str(payload.get("error", ""))
            reports.append(ShenFailure(_classify(message), message, provenance=provenance))
            continue
        checksum = payload.get("elaborated_checksum")
        text = canonical_json(payload.get("elaborated"))
        if payload.get("kind") != kind or not isinstance(payload.get("rules"), list) \
                or (typed and not isinstance(payload.get("units"), int)):
            reports.append(ShenFailure("malformed-output", f"{kind} payload has the wrong shape",
                                       provenance=provenance))
            continue
        if pack_checksum(text) != checksum:
            # Same refusal id as the single-bundle path in run().
            reports.append(ShenFailure("elaborated-pack-mismatch", f"{kind} elaborated pack checksum does not match",
                                       provenance=provenance))
            continue
        provenance = Provenance(**{**provenance.__dict__, "elaborated_sha256": _sha256_text(text),
                                   "elaborated_checksum": checksum})
        fields = (bool(payload.get("ok")), tuple(payload["rules"]), tuple(payload.get("pack", ())),
                  dict(payload.get("elaborated") or {}), str(checksum), provenance)
        reports.append(TypedAuthorityReport(*fields, payload["units"]) if typed
                       else AuthorityReport(*fields))
    return reports


@dataclass(frozen=True)
class DeriveResult:
    outcome: str  # positive | negative | truncated
    certificate: dict[str, Any] | None
    why_not: dict[str, Any] | None
    provenance: Provenance

    def as_dict(self) -> dict[str, Any]:
        return {"outcome": self.outcome, "certificate": self.certificate, "why_not": self.why_not,
                "provenance": self.provenance.as_dict()}


def evaluate(bundle: Bundle, rules: Any = None, relation: str = "", row: Sequence[Any] = (), *,
             frozen: str | None = None, max_depth: int = DEFAULT_MAX_DEPTH,
             max_nodes: int = DEFAULT_MAX_NODES, timeout: float | None = None,
             keep: bool = False) -> DeriveResult:
    """Search for a derivation of ``relation(row)`` and return the full envelope."""
    if not relation:
        raise ShenFailure("invalid-input", "a relation name is required")
    _validated(bundle)
    _check_pack_against(bundle, rules)
    request = {"kind": "derive", "relation": relation, "row": [_plain(v) for v in row]}
    result = run(bundle, request, frozen=frozen, max_depth=max_depth, max_nodes=max_nodes,
                 timeout=timeout, keep=keep)
    payload = result.payload
    outcome = payload.get("outcome")
    if payload.get("kind") != "derive" or outcome not in {"positive", "negative", "truncated"}:
        raise ShenFailure("malformed-output", "derive payload has the wrong shape", stdout=result.stdout,
                          stderr=result.stderr, provenance=result.provenance)
    certificate = payload.get("certificate")
    why_not = payload.get("why_not")
    if outcome == "negative" and (certificate is not None or not isinstance(why_not, Mapping)):
        raise ShenFailure("malformed-output", "negative outcome must carry a why-not report and no certificate",
                          stdout=result.stdout, stderr=result.stderr, provenance=result.provenance)
    if outcome != "negative" and not isinstance(certificate, Mapping):
        raise ShenFailure("malformed-output", "positive outcome must carry a certificate",
                          stdout=result.stdout, stderr=result.stderr, provenance=result.provenance)
    return DeriveResult(outcome, dict(certificate) if certificate else None,
                        dict(why_not) if why_not else None, result.provenance)


def derive(bundle: Bundle, rules: Any = None, relation: str = "", row: Sequence[Any] = (), *,
           frozen: str | None = None, max_depth: int = DEFAULT_MAX_DEPTH,
           max_nodes: int = DEFAULT_MAX_NODES, timeout: float | None = None,
           keep: bool = False) -> dict[str, Any]:
    """The certificate for ``relation(row)``; ``NotDerivable`` when the row is absent.

    A truncated search returns the truncated certificate (``truncated: true``),
    which ``certificate.recheck`` rejects by design.
    """
    result = evaluate(bundle, rules, relation, row, frozen=frozen, max_depth=max_depth,
                      max_nodes=max_nodes, timeout=timeout, keep=keep)
    if result.outcome == "negative":
        raise NotDerivable(relation, row, result.why_not or {}, result.provenance)
    assert result.certificate is not None
    return result.certificate


def why_not(bundle: Bundle, rules: Any = None, relation: str = "", row: Sequence[Any] = (), *,
            frozen: str | None = None, max_depth: int = DEFAULT_MAX_DEPTH,
            max_nodes: int = DEFAULT_MAX_NODES, timeout: float | None = None,
            keep: bool = False) -> dict[str, Any]:
    """Bounded missing-premise alternatives for ``relation(row)`` (plus provenance)."""
    if not relation:
        raise ShenFailure("invalid-input", "a relation name is required")
    _validated(bundle)
    _check_pack_against(bundle, rules)
    request = {"kind": "why-not", "relation": relation, "row": [_plain(v) for v in row]}
    result = run(bundle, request, frozen=frozen, max_depth=max_depth, max_nodes=max_nodes,
                 timeout=timeout, keep=keep)
    payload = result.payload
    report = payload.get("report")
    if payload.get("kind") != "why-not" or not isinstance(report, Mapping):
        raise ShenFailure("malformed-output", "why-not payload has the wrong shape", stdout=result.stdout,
                          stderr=result.stderr, provenance=result.provenance)
    return {**report, "provenance": result.provenance.as_dict()}


__all__ = ["DEFAULT_TIMEOUT", "IMPL", "LIBRARY_FILES", "TYPED_LIBRARY_FILES", "AuthorityReport", "TypedAuthorityReport", "DeriveResult", "NotDerivable",
           "Provenance", "Runtime", "ShenFailure", "ShenRun", "ShenUnavailable", "authority", "derive",
           "evaluate", "pack_checksum", "render_driver", "run", "runtime", "shen_dir", "typed_authority", "authority_batch", "why_not"]
