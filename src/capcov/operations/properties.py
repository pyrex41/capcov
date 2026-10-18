"""Model-derived properties and optional Antithesis assertion/catalog sink."""

from . import OperationError, _sha, _state
from .compiler import model
from .native import invoke
from .system import SYSTEM_LIBRARIES, _term, digest


def observe(source, states, goals=(), *, timeout=60):
    if not isinstance(states, list) or not 1 <= len(states) <= 256:
        raise OperationError("property observation requires 1..256 states")
    if not isinstance(goals, (list, tuple)) or len(goals) > 64:
        raise OperationError("provide at most 64 reachability goals")
    predicates, names = [], set()
    for g in goals:
        if (
            not isinstance(g, dict)
            or set(g) != {"id", "predicate"}
            or not isinstance(g["id"], str)
            or not g["id"]
            or g["id"] in names
        ):
            raise OperationError("reachability goals need distinct ids and predicates")
        names.add(g["id"])
        predicates.append(_term(g["predicate"]))
    m = model(source)
    if (
        not isinstance(m, list)
        or len(m) != 5
        or m[0] != "system"
        or not isinstance(m[4], list)
    ):
        raise OperationError("properties require a system specification")
    records = [
        ("schema", "always"),
        *[("invariant:" + n, "always") for n, _ in m[4]],
        *[("goal:" + g["id"], "sometimes") for g in goals],
    ]
    model_id = _sha(source.encode())
    catalog = [
        {
            "id": digest([model_id, name]),
            "name": name,
            "kind": kind,
            "message": "capcov:" + model_id + ":" + name,
        }
        for name, kind in records
    ]
    guard = "true"
    for p in predicates:
        guard = f"(and {guard} (and (= caps-pred (shen.typecheck (capop.syntax {p}) caps-pred)) (caps.scope-pred? {p} [] no-row (caps.tables M))))"
    rows = []
    for state in states:
        # A malformed schema is a safety failure, not a predicate success.
        values = [
            "Schema",
            *[
                f"(if Schema (caps.pred (nth 2 (nth {i + 1} (nth 5 M))) [] [] S) not-requested)"
                for i in range(len(m[4]))
            ],
            *[f"(if Schema (caps.pred {p} [] [] S) not-requested)" for p in predicates],
        ]
        rows.append(
            f"(let S {_state(state)} Schema (caps.state-ok? M S) [{' '.join(values)}])"
        )
    expression = f'(let M {_term(source)} (if (and (caps.typechecks? M) {guard}) [{" ".join(rows)}] (error "properties: invalid model or goal")))'
    values, identity = invoke(expression, SYSTEM_LIBRARIES, timeout=timeout)
    if len(values) != len(states) or any(len(row) != len(catalog) for row in values):
        raise OperationError("invalid property response")
    report = {
        "format": "capcov-properties-v1",
        "model": model_id,
        "states": digest(states),
        "identity": identity,
        "catalog": catalog,
        "observations": values,
    }
    report["sha256"] = digest(report)
    return report


def publish(report, *, sink=None):
    """Register catalog (hit=False) before runtime observations (hit=True).

    report must originate from trusted observe. Hashes establish integrity, not
    the honesty of an arbitrary observer. No SDK import or action occurs until
    this function is explicitly called. A sink supports other property backends.
    """
    if (
        not isinstance(report, dict)
        or report.get("format") != "capcov-properties-v1"
        or report.get("sha256")
        != digest({k: v for k, v in report.items() if k != "sha256"})
    ):
        raise OperationError("invalid property report")
    if sink is None:
        try:
            from antithesis.assertions import assert_raw

            sink = assert_raw
        except ImportError as exc:
            raise OperationError(
                "install the Antithesis Python SDK to publish properties"
            ) from exc
    catalog = report["catalog"]
    if any(
        len(row) != len(catalog)
        or any(type(v) is not bool and v is not None for v in row)
        for row in report["observations"]
    ):
        raise OperationError("invalid property observation values")
    for i, entry in enumerate(catalog):
        if entry["kind"] not in ("always", "sometimes"):
            raise OperationError("invalid property kind")
        common = dict(
            message=entry["message"],
            loc_filename="capcov-model:" + report["model"],
            loc_function=entry["name"],
            loc_class="",
            loc_begin_line=1,
            loc_begin_column=1,
            must_hit=True,
            assert_type=entry["kind"],
            display_type="Always" if entry["kind"] == "always" else "Sometimes",
            assert_id=entry["id"],
        )
        sink(condition=False, details=None, hit=False, **common)
        for step, row in enumerate(report["observations"]):
            if row[i] is not None:
                sink(
                    condition=row[i],
                    details={
                        "model": report["model"],
                        "state_index": step,
                        "report": report["sha256"],
                    },
                    hit=True,
                    **common,
                )
    return len(catalog)
