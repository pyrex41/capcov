"""Small, deterministic DreamCoder-style pure-program experiment.

This is deliberately a research lane. Programs are JSON ASTs over variables,
literal values, boolean predicates, conditionals, and learned calls. Effects
and source execution are outside this DSL.
"""
from __future__ import annotations
from collections import Counter
import hashlib, json
from pathlib import Path
from typing import Any


def size(node: Any) -> int:
    return 1 + sum(size(v) for v in node.values()) if isinstance(node, dict) else (sum(size(v) for v in node) if isinstance(node, list) else 1)


def eval_program(node: Any, env: dict[str, Any], library: dict[str, dict[str, Any]] | None = None) -> Any:
    if isinstance(node, (str, int, float, bool)) or node is None:
        return node
    if "var" in node:
        return env[node["var"]]
    if "lit" in node:
        return node["lit"]
    op = node.get("op")
    args = node.get("args", [])
    if op == "and": return bool(eval_program(args[0], env, library)) and bool(eval_program(args[1], env, library))
    if op == "or": return bool(eval_program(args[0], env, library)) or bool(eval_program(args[1], env, library))
    if op == "not": return not bool(eval_program(args[0], env, library))
    if op == "eq": return eval_program(args[0], env, library) == eval_program(args[1], env, library)
    if op == "if": return eval_program(node["then"], env, library) if eval_program(node["cond"], env, library) else eval_program(node["else"], env, library)
    if op == "call":
        definition = (library or {})[node["name"]]
        local = {name: eval_program(arg, env, library) for name, arg in zip(definition["params"], args)}
        return eval_program(definition["body"], local, library)
    raise ValueError(f"unsupported AST node: {node}")


def _key(node: Any) -> str:
    return json.dumps(node, sort_keys=True, separators=(",", ":"))


def _walk(node: Any):
    yield node
    if isinstance(node, dict):
        for value in node.values(): yield from _walk(value)
    elif isinstance(node, list):
        for value in node: yield from _walk(value)


def _variables(node: Any) -> list[str]:
    return sorted({part["var"] for part in _walk(node) if isinstance(part, dict) and isinstance(part.get("var"), str)})


def _replace(node: Any, target: Any, replacement: Any) -> tuple[Any, bool]:
    if _key(node) == _key(target): return replacement, True
    if isinstance(node, dict):
        for key, value in node.items():
            new, changed = _replace(value, target, replacement)
            if changed:
                out = dict(node); out[key] = new; return out, True
    if isinstance(node, list):
        for index, value in enumerate(node):
            new, changed = _replace(value, target, replacement)
            if changed:
                out = list(node); out[index] = new; return out, True
    return node, False


def learn_library(tasks: list[dict[str, Any]], *, max_defs: int = 16) -> dict[str, Any]:
    counts = Counter(_key(part) for task in tasks for part in _walk(task["program"]) if isinstance(part, dict) and ("op" in part))
    candidates = [(count, key) for key, count in counts.items() if count >= 2]
    candidates.sort(key=lambda item: (-item[0], item[1]))
    library: dict[str, dict[str, Any]] = {}
    inventions = []
    for index, (count, key) in enumerate(candidates[:max_defs]):
        body = json.loads(key)
        params = _variables(body)
        name = f"invented_{index:03d}"
        before = sum(size(task["program"]) for task in tasks)
        rewritten = []
        for task in tasks:
            program, changed = _replace(task["program"], body, {"op": "call", "name": name,
                                                                  "args": [{"var": param} for param in params]})
            rewritten.append(program)
        after = sum(size(program) for program in rewritten) + size(body) + 2
        if after >= before: continue
        library[name] = {"params": params, "body": body, "support": count}
        inventions.append({"name": name, "support": count, "body": body, "params": params, "compression": before - after})
    return {"schema": "capcov/synthesis-library/v1", "library": library, "inventions": inventions}


def synthesize(tasks: list[dict[str, Any]], library_doc: dict[str, Any], *, max_tasks: int = 100) -> dict[str, Any]:
    library = library_doc.get("library", {})
    results = []
    for task in sorted(tasks, key=lambda item: item["id"])[:max_tasks]:
        baseline = task["program"]
        candidate = baseline
        used = []
        for name, definition in sorted(library.items()):
            candidate, changed = _replace(candidate, definition["body"], {"op": "call", "name": name,
                                                                              "args": [{"var": param} for param in definition["params"]]})
            if changed: used.append(name)
        train_ok = all(eval_program(candidate, ex["input"], library) == ex["output"] for ex in task.get("examples", []))
        sealed = task.get("heldout_examples", [])
        candidate_ok = train_ok and bool(used) and all(eval_program(candidate, ex["input"], library) == ex["output"] for ex in sealed)
        baseline_ok = all(eval_program(baseline, ex["input"], {}) == ex["output"] for ex in sealed)
        results.append({"id": task["id"], "used_invented": used, "training_pass": train_ok,
                        "candidate_heldout_pass": candidate_ok, "baseline_heldout_pass": baseline_ok,
                        "heldout_count": len(sealed)})
    return {"schema": "capcov/synthesis-evaluation/v1", "results": results,
            "counts": {"candidate_pass": sum(r["candidate_heldout_pass"] for r in results),
                       "baseline_pass": sum(r["baseline_heldout_pass"] for r in results)}}


def run_synthesis(input_path: Path, output_path: Path, *, max_defs: int = 16, max_tasks: int = 100) -> None:
    document = json.loads(input_path.read_text())
    tasks = document.get("tasks", [])
    library = learn_library(tasks, max_defs=max_defs)
    result = synthesize(tasks, library, max_tasks=max_tasks)
    output_path.write_text(json.dumps({"library": library, "evaluation": result}, indent=2, sort_keys=True) + "\n")
