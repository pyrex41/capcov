from __future__ import annotations
import json
from pathlib import Path

SCHEMA = "capcov/intent-packet/v1"

def prompt_packet(packet: dict) -> dict:
    if packet.get("schema") != SCHEMA: raise ValueError("unsupported evidence packet schema")
    evidence = packet.get("evidence", [])
    return {"schema": "capcov/intent-prompt/v1", "question": packet.get("question", "adjudicate intent"),
            "evidence": evidence, "alternatives": packet.get("alternatives", []),
            "instructions": ["cite source IDs", "identify discriminating cases", "retain unknowns", "recommendation is non-binding"]}

def adjudicate(packet: dict, recommendation: dict, accepted: dict | None = None) -> dict:
    if packet.get("schema") != SCHEMA: raise ValueError("unsupported evidence packet schema")
    evidence = packet.get("evidence", []); ids = {row.get("id") for row in evidence if isinstance(row, dict)}
    cited = recommendation.get("source_ids", [])
    if not isinstance(cited, list) or not set(cited) <= ids: raise ValueError("recommendation cites unknown source ID")
    cases = packet.get("cases", [])
    decision = accepted if isinstance(accepted, dict) and accepted.get("accepted") is True else None
    intended = decision.get("intended_outputs", {}) if decision else {}
    classifications = []
    for case in cases:
        cid = case.get("id"); php = case.get("php_output"); go = case.get("go_output"); ref = case.get("reference_output")
        want = intended.get(cid) if isinstance(intended, dict) else None
        if decision is None: relation = "unknown"
        elif want == php == go: relation = "both"
        elif want == php: relation = "php-only"
        elif want == go: relation = "go-only"
        elif want == ref: relation = "reference-only"
        else: relation = "neither"
        classifications.append({"id": cid, "php": php, "go": go, "reference": ref, "intended": want, "classification": relation})
    contracts = [{"case_id": row["id"], "expected": row["intended"]} for row in classifications if row["classification"] in {"both", "php-only", "go-only", "reference-only"}]
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
