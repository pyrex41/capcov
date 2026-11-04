"""One workflow over recovery, execution and scoped qualification artifacts."""

import argparse
import json
import sys
from pathlib import Path

from .registry import read_json, validate, inspect, scope
from .qualification import execute_checks, qualify, compare
from .recovery import import_recovery, tasks, export_graph
from .target import admit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "inspect", "import-recovery", "graph",
                                            "check", "gate", "tasks", "compare", "admit",
                                            "environment-claims", "environment-check", "environment-search",
                                            "import-environment", "environment-plan"))
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--scope", action="append")
    parser.add_argument("--checks", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--cutover", action="store_true")
    parser.add_argument("--toolchain", type=Path, help="trusted ShenCheck/Vör/TLC locations; mandatory for enrolled engine checks")
    parser.add_argument("--mapping", help="source-node/Behavior and Shen search mapping, relative to --root")
    parser.add_argument("--surface", help="surface to target with the mapped Shen search")
    parser.add_argument("--engine", choices=("python", "souffle", "both"), default="both")
    args = parser.parse_args(argv)
    try:
        status = 0
        if args.command.startswith("environment-") or args.command == "import-environment":
            from . import environment
            from capcov.claims.environment import check as check_environment
            from capcov.claims.ir import canonical_dict
            if not args.input or not args.mapping:
                parser.error("environment commands require --input CAPABILITIES and --mapping")
            input_file = str(args.input)
            if args.command == "environment-search":
                if not args.surface:
                    parser.error("environment-search requires --surface")
                result = environment.search_environment(args.root, input_file, args.mapping, args.surface)
                status = int(result["search"]["status"] != "witness")
            elif args.command in {"import-environment", "environment-plan"}:
                if not args.registry:
                    parser.error("environment import/plan requires --registry")
                registry = read_json(args.registry)
                if args.command == "import-environment":
                    result = environment.import_environment(registry, args.root, input_file, args.mapping)
                else:
                    if not args.checks:
                        parser.error("environment-plan requires --checks")
                    result = environment.extend_plan(read_json(args.checks), registry, args.root,
                        input_file, args.mapping, engine=args.engine)
            else:
                caps, _, bundle, _, _ = environment.load(args.root, input_file, args.mapping)
                result = (canonical_dict(bundle) if args.command == "environment-claims"
                          else check_environment(caps, engine=args.engine))
        elif args.command == "admit":
            if not args.input:
                parser.error("admit requires --input PROGRAM.json")
            result = admit(read_json(args.input))
        else:
            if not args.registry:
                parser.error("--registry is required")
            registry = read_json(args.registry)
            validate(registry)
            selected = args.scope or [b["id"] for b in registry["behaviors"]]
            scope(registry, selected)
            if args.command == "validate":
                result = {"valid": True, "behaviors": selected}
            elif args.command == "inspect":
                result = inspect(registry, args.root, selected)
                status = int(bool(result["stale"] or result["gaps"] or result["ambiguities"]))
            elif args.command == "import-recovery":
                if not args.input:
                    parser.error("import-recovery requires --input")
                result = import_recovery(registry, read_json(args.input), args.root)
            elif args.command == "graph":
                if not args.out:
                    parser.error("graph requires --out DIRECTORY")
                result = export_graph(registry, args.root, selected, args.out)
                print(json.dumps(result, indent=2))
                return 0
            else:
                if not args.checks or not args.evidence:
                    parser.error("qualification requires --checks and --evidence")
                plan = read_json(args.checks)
                toolchain = read_json(args.toolchain) if args.toolchain else None
                if args.command == "check":
                    receipts = execute_checks(registry, plan, args.root, selected, args.evidence, toolchain=toolchain)
                else:
                    receipts = [read_json(p) for p in sorted(args.evidence.glob("*.json"))]
                result = qualify(registry, plan, args.root, selected, receipts, args.evidence, cutover=args.cutover, toolchain=toolchain)
                if args.command == "tasks":
                    result = tasks(registry, result)
                elif args.command == "compare":
                    if not args.input or len(selected) != 1:
                        parser.error("compare requires --input and exactly one --scope")
                    data = read_json(args.input)
                    result = compare(registry, selected[0], data["scenario"], data["legacy"], data["target"], result)
                    status = int(not result["compatible"])
                else:
                    status = int(not result["complete"])
        encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if args.out:
            args.out.write_text(encoded)
        else:
            print(encoded, end="")
        return status
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print("capcov behavior: " + str(exc), file=sys.stderr)
        return 2
