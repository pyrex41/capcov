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
    args = parser.parse_args(argv)
    run_synthesis(args.input, args.out, max_defs=args.max_defs, max_tasks=args.max_tasks)
    return 0
