"""Relation declarations and join rules for runtime causal-trace evidence.

The causal-trace primitives ``runtime_function_entered``, ``runtime_sql_executed``,
``runtime_tx_committed`` and ``runtime_route_completed`` declare the producer class
``target-go-runtime-trace-v2``; evidence whose ``source`` token is anything else is
rejected at ingestion (``evidence-producer``) and again by the ground checker.  A
consumer that retains runtime receipts supplies that producer; capcov ships the
declarations and the rules that join a run to an index.

Static and runtime certificates stay independent: ``index_describes_run`` joins a
run to an index, and ``runtime_route_reaches_sql_on_index`` requires agreeing
run/request/transaction/surface/index witnesses.  That is not one end-to-end proof
that a static call-graph path was the runtime stack.
"""
from __future__ import annotations

from importlib import resources
import hashlib
import json
from ..ir import bundle_from_json

# Authored in specs/claims/shared.claims. These installed data are generated
# by the native specification compiler; no source checkout or Shen is needed.
_data = resources.files(__package__).joinpath("runtime-shared-v1.json").read_bytes()
_manifest = json.loads(resources.files(__package__).joinpath("runtime-shared-v1.manifest.json").read_text(encoding="utf-8"))
if hashlib.sha256(_data).hexdigest() != _manifest["artifacts"]["bundle.json"]:
    raise ValueError("generated runtime bridge bundle does not match its manifest")
_bundle = bundle_from_json(_data)
_relations = {decl.name: decl for decl in _bundle.relations}
_rules = {rule.name: rule for rule in _bundle.rules}
TRACE_PRODUCER = "target-go-runtime-trace-v2"
RUNTIME_ROUTE_OBSERVED = _relations["runtime_route_observed"]
TRACE_PRIMITIVE_DECLS = tuple(_relations[name] for name in (
    "runtime_function_entered", "runtime_sql_executed", "runtime_tx_committed", "runtime_route_completed"))
RUNTIME_ROUTE_REACHES_SQL = _relations["runtime_route_reaches_sql_on_index"]
RUNTIME_ROUTE_ON_INDEX = _relations["runtime_route_observed_on_index"]
RUNTIME_ROUTE_ON_INDEX_RULE = _rules["runtime_route_matches_scip_index"]
RUNTIME_ROUTE_REACHES_SQL_RULE = _rules["runtime_route_executes_committed_sql_on_index"]
