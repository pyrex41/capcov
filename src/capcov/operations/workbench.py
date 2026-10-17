"""Compose extraction, obligations, witness search, execution and evidence."""

from . import OperationError
from .compiler import compile_system
from .evidence import validate, invalidate
from .proofs import check
from .search import search
from .scenarios import run_scenario, minimize
from .system import digest


def verify(
    source,
    root,
    inventory,
    campaigns,
    *,
    adapter=None,
    timeout=60,
    fuel=1024,
    minimize_runs=16,
):
    validate(inventory)
    freshness = invalidate(root, inventory)
    compilation = compile_system(source, timeout=timeout)
    obligations = {
        o["id"]: o for c in compilation["commands"] for o in c["obligations"]
    }
    for claim in inventory["claims"]:
        if not set(claim["obligations"]) <= obligations.keys():
            raise OperationError("claim cites unknown model obligation")
    for o in obligations.values():
        if o["status"] == "proved" and not check(o["proof"], timeout=timeout):
            raise OperationError("independent proof checking failed")
    if not isinstance(campaigns, list) or len(campaigns) > 64:
        raise OperationError("provide at most 64 campaigns")
    reports = []
    for campaign in campaigns:
        if (
            not isinstance(campaign, dict)
            or set(campaign)
            - {"id", "claims", "initial", "calls", "goal", "depth", "budget"}
            or not {"id", "claims", "initial", "calls", "goal"} <= set(campaign)
        ):
            raise OperationError("invalid verification campaign")
        if not set(campaign["claims"]) <= {c["id"] for c in inventory["claims"]}:
            raise OperationError("campaign cites unknown claim")
        found = search(
            source,
            **{k: v for k, v in campaign.items() if k not in ("id", "claims")},
            fuel=fuel,
            timeout=timeout,
        )
        report = {"id": campaign["id"], "claims": campaign["claims"], "search": found}
        scenario = found["scenario"]
        if (
            adapter
            and scenario
            and scenario["steps"]
            and all(s["choice"] != "violation" for s in scenario["steps"])
        ):
            run = run_scenario(source, scenario, adapter, fuel=fuel, timeout=timeout)
            report["execution"] = run
            if run["mismatches"] and run["replay_matches"] is True:
                report["minimized"] = minimize(
                    source,
                    scenario,
                    adapter,
                    fuel=fuel,
                    timeout=timeout,
                    max_runs=minimize_runs,
                )
        reports.append(report)
    claims = []
    for c in inventory["claims"]:
        if not set(c["obligations"]) <= obligations.keys():
            raise OperationError("claim cites unknown model obligation")
        related = [r for r in reports if c["id"] in r["claims"]]
        claims.append(
            {
                "id": c["id"],
                "kind": c["kind"],
                "source_anchored": bool(c["anchors"]),
                "source_current": c["id"] not in freshness["stale_claims"],
                "proved_model_obligations": [
                    n for n in c["obligations"] if obligations[n]["status"] == "proved"
                ],
                "open_model_obligations": [
                    n for n in c["obligations"] if obligations[n]["status"] != "proved"
                ],
                "witnessed_campaigns": [
                    r["id"] for r in related if r["search"]["status"] == "witness"
                ],
                "refuted_campaigns": [
                    r["id"] for r in related if r.get("execution", {}).get("mismatches")
                ],
                "unstable_replays": [
                    r["id"]
                    for r in related
                    if r.get("execution", {}).get("replay_matches") is False
                ],
                "gaps": [g["id"] for g in inventory["gaps"] if c["id"] in g["claims"]],
            }
        )
    result = {
        "format": "capcov-verification-v1",
        "inventory": inventory["sha256"],
        "freshness": freshness,
        "compilation": compilation,
        "campaigns": reports,
        "claims": claims,
        "admission": "case evidence and scoped model proofs only; no automatic source-to-model equivalence or target approval",
    }
    result["sha256"] = digest(result)
    return result


def main(argv=None):
    import argparse
    import json
    import sys
    from pathlib import Path
    from .proofs import prove
    from .relations import compile_relation, solve
    from .evidence import extract, bind

    parser = argparse.ArgumentParser(
        description="Shen specifications, proofs, modes and source evidence"
    )
    parser.add_argument(
        "mode",
        choices=(
            "compile",
            "prove",
            "check",
            "relation",
            "solve",
            "extract",
            "bind",
            "invalidate",
            "search",
            "scenario",
            "minimize",
            "verify",
            "properties",
        ),
    )
    parser.add_argument("--input", type=Path)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path)
    parser.add_argument("--adapter", nargs="+")
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.input.read_text()) if args.input else {}
        source = args.spec.read_text() if args.spec else None
        if (
            args.mode
            in ("compile", "search", "scenario", "minimize", "verify", "properties")
            and source is None
        ):
            raise OperationError("mode requires --spec")
        code = 0
        if args.mode == "compile":
            result = compile_system(source, timeout=args.timeout)
            code = int(
                any(
                    o["status"] != "proved"
                    for c in result["commands"]
                    for o in c["obligations"]
                )
            )
        elif args.mode == "properties":
            from .properties import observe

            result = observe(source, **payload, timeout=args.timeout)
            code = int(
                any(
                    (
                        any(row[i] is False for row in result["observations"])
                        if p["kind"] == "always"
                        else not any(row[i] is True for row in result["observations"])
                    )
                    for i, p in enumerate(result["catalog"])
                )
            )
        elif args.mode == "prove":
            result = prove(**payload, timeout=args.timeout)
            code = int(result["answer"][0] != "proved")
        elif args.mode == "check":
            result = {"verified": check(payload, timeout=args.timeout)}
            code = int(not result["verified"])
        elif args.mode == "relation":
            result = compile_relation(payload, timeout=args.timeout)
        elif args.mode == "solve":
            result = solve(**payload, timeout=args.timeout)
        elif args.mode == "extract":
            result = extract(args.root, **payload)
        elif args.mode == "bind":
            result = bind(**payload)
        elif args.mode == "invalidate":
            result = invalidate(args.root, payload)
            code = int(bool(result["changed_sources"]))
        elif args.mode == "search":
            result = search(source, **payload, timeout=args.timeout)
            code = int(result["status"] != "witness")
        elif args.mode in ("scenario", "minimize"):
            fn = run_scenario if args.mode == "scenario" else minimize
            result = fn(source, payload, args.adapter, timeout=args.timeout)
            report = result if args.mode == "scenario" else result["report"]
            code = int(bool(report["mismatches"]) or report["replay_matches"] is False)
        else:
            result = verify(
                source, args.root, **payload, adapter=args.adapter, timeout=args.timeout
            )
            code = int(
                bool(
                    result["freshness"]["changed_sources"]
                    or result["freshness"]["open_gaps"]
                )
                or any(
                    c["open_model_obligations"]
                    or c["refuted_campaigns"]
                    or c["unstable_replays"]
                    for c in result["claims"]
                )
                or any(r["search"]["status"] != "witness" for r in result["campaigns"])
            )
        text = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.out:
            args.out.write_text(text)
        else:
            print(text, end="")
        return code
    except (ValueError, OSError, TypeError, KeyError, RecursionError) as exc:
        print(json.dumps({"operational_failure": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
