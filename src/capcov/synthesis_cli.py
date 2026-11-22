from __future__ import annotations
import argparse
from pathlib import Path
from .synthesis import run_synthesis

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="capcov synthesize")
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, default=Path("synthesis-evaluation.json"))
    parser.add_argument("--max-defs", type=int, default=16)
    parser.add_argument("--max-tasks", type=int, default=100)
    parser.add_argument("--max-terms", type=int, default=100000)
    parser.add_argument("--max-cost", type=int, default=7)
    parser.add_argument("--library-in", type=Path, default=None)
    parser.add_argument("--library-out", type=Path, default=None)
    parser.add_argument("--emit-go", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.library_in is not None:
        import json
        document = json.loads(args.input.read_text())
        library = json.loads(args.library_in.read_text())
        from .synthesis import synthesize_target, synthesize
        target = document.get("target")
        result = synthesize_target(target, library, max_terms=args.max_terms, max_cost=args.max_cost) if isinstance(target, dict) else synthesize(document.get("tasks", []), library, max_tasks=args.max_tasks)
        args.out.write_text(json.dumps({"library": library, "evaluation": result}, indent=2, sort_keys=True) + "\n")
    else:
        run_synthesis(args.input, args.out, max_defs=args.max_defs, max_tasks=args.max_tasks,
                      max_terms=args.max_terms, max_cost=args.max_cost)
    if args.library_out is not None:
        import json
        generated = json.loads(args.out.read_text())["library"]
        args.library_out.write_text(json.dumps(generated, indent=2, sort_keys=True) + "\n")
    if args.emit_go is not None:
        from .go_emit import emit
        import json
        emit(json.loads(args.out.read_text()), args.emit_go)
    return 0
