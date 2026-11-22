from __future__ import annotations
import json
from pathlib import Path

SCHEMA = "capcov/intent-packet/v1"
MISSING = object()

def prompt_packet(packet: dict) -> dict:
    if packet.get("schema") != SCHEMA: raise ValueError("unsupported evidence packet schema")
    evidence = packet.get("evidence", [])
    return {"schema": "capcov/intent-prompt/v1", "question": packet.get("question", "adjudicate intent"),
            "evidence": evidence, "alternatives": packet.get("alternatives", []), "cases": packet.get("cases", []),
            "packet_schema": SCHEMA,
            "instructions": ["cite source IDs", "identify discriminating cases", "retain unknowns", "recommendation is non-binding"]}

def adjudicate(packet: dict, recommendation: dict, accepted: dict | None = None) -> dict:
    if packet.get("schema") != SCHEMA: raise ValueError("unsupported evidence packet schema")
    evidence = packet.get("evidence", []); ids = {row.get("id") for row in evidence if isinstance(row, dict)}
    cited = recommendation.get("source_ids", [])
    if not isinstance(cited, list) or not cited or not set(cited) <= ids: raise ValueError("recommendation requires known advisory source IDs")
    cases = packet.get("cases", [])
    if accepted is not None and (not isinstance(accepted, dict) or accepted.get("accepted") is not True):
        raise ValueError("accepted decision must explicitly set accepted=true")
    if accepted is not None and (accepted.get("packet_schema") != SCHEMA or accepted.get("packet_id") != packet.get("packet_id") or not accepted.get("authority") or not accepted.get("source_ids") or not set(accepted["source_ids"]) <= ids):
        raise ValueError("accepted decision requires matching packet, authority, and pinned source IDs")
    decision = accepted if isinstance(accepted, dict) else None
    intended = decision.get("intended_outputs", {}) if decision else {}
    classifications = []
    for case in cases:
        cid = case.get("id"); php = case.get("php_output", MISSING); go = case.get("go_output", MISSING); ref = case.get("reference_output", MISSING)
        want = intended.get(cid, MISSING) if isinstance(intended, dict) else MISSING
        equal = lambda a,b: a is not MISSING and b is not MISSING and type(a) is type(b) and a == b
        if decision is None: relation = "unknown"
        elif equal(want, php) and equal(want, go): relation = "both"
        elif equal(want, php): relation = "php-only"
        elif equal(want, go): relation = "go-only"
        elif equal(want, ref): relation = "reference-only"
        else: relation = "neither"
        observed_agreement = "both" if equal(php, go) else "different"
        row = {"id": cid, "php": None if php is MISSING else php, "go": None if go is MISSING else go, "reference": None if ref is MISSING else ref, "intended": None if want is MISSING else want, "classification": relation, "observed_agreement": observed_agreement, "missing": [name for name, value in (("php",php),("go",go),("reference",ref),("intended",want)) if value is MISSING]}
        classifications.append(row)
    contracts = [{"case_id": cid, "input": next((case.get("input") for case in cases if case.get("id") == cid), None), "output": output} for cid, output in intended.items()] if decision and isinstance(intended, dict) else []
    return {"schema": "capcov/intent-adjudication/v1", "recommendation": recommendation,
            "binding": decision is not None, "accepted_by": decision.get("authority") if decision else None,
            "classifications": classifications, "synthesis_contracts": contracts,
            "unknown_evidence": [row.get("id") for row in evidence if row.get("status") in {"unknown", "conflict"}]}

def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(prog="capcov intent")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prompt"); p.add_argument("packet", type=Path); p.add_argument("--out", type=Path, required=True)
    a = sub.add_parser("adjudicate"); a.add_argument("packet", type=Path); a.add_argument("recommendation", type=Path); a.add_argument("--accepted", type=Path); a.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    packet = json.loads(args.packet.read_text())
    if args.command == "prompt": result = prompt_packet(packet)
    else: result = adjudicate(packet, json.loads(args.recommendation.read_text()), json.loads(args.accepted.read_text()) if args.accepted else None)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n"); return 0
