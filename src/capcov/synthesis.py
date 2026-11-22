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


def _canonical(node: Any, names: dict[str, str] | None = None) -> Any:
    names = {} if names is None else names
    if isinstance(node, dict) and isinstance(node.get("var"), str):
        name = node["var"]
        names.setdefault(name, f"$p{len(names)}")
        return {"var": names[name]}
    if isinstance(node, dict): return {key: _canonical(value, names) for key, value in node.items()}
    if isinstance(node, list): return [_canonical(value, names) for value in node]
    return node


def _instantiate(node: Any, mapping: dict[str, Any]) -> Any:
    if isinstance(node, dict) and isinstance(node.get("var"), str) and node["var"].startswith("$p"):
        return mapping[node["var"]]
    if isinstance(node, dict): return {key: _instantiate(value, mapping) for key, value in node.items()}
    if isinstance(node, list): return [_instantiate(value, mapping) for value in node]
    return node


def _match(node: Any, pattern: Any, mapping: dict[str, Any]) -> bool:
    if isinstance(pattern, dict) and isinstance(pattern.get("var"), str) and pattern["var"].startswith("$p"):
        prior = mapping.setdefault(pattern["var"], node)
        return _key(prior) == _key(node)
    if isinstance(node, dict) and isinstance(pattern, dict):
        return node.keys() == pattern.keys() and all(_match(node[key], pattern[key], mapping) for key in node)
    if isinstance(node, list) and isinstance(pattern, list):
        return len(node) == len(pattern) and all(_match(left, right, mapping) for left, right in zip(node, pattern))
    return node == pattern


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
    counts = Counter(_key(_canonical(part)) for task in tasks for part in _walk(task["program"]) if isinstance(part, dict) and ("op" in part))
    candidates = [(count, key) for key, count in counts.items() if count >= 2]
    candidates.sort(key=lambda item: (-item[0], item[1]))
    library: dict[str, dict[str, Any]] = {}
    inventions = []
    current_programs = [task["program"] for task in tasks]
    current_total = sum(size(program) for program in current_programs)
    for index, (count, key) in enumerate(candidates):
        body = json.loads(key)
        params = _variables(body)
        name = f"invented_{index:03d}"
        before = current_total
        rewritten = []
        for original in current_programs:
            program, changed = original, False
            for part in list(_walk(original)):
                mapping: dict[str, Any] = {}
                if _match(part, body, mapping):
                    call = {"op": "call", "name": name, "args": [mapping[param] for param in params]}
                    program, changed = _replace(original, part, call)
                    break
            rewritten.append(program)
        after = sum(size(program) for program in rewritten) + size(body) + 2
        if after >= before: continue
        if len(library) >= max_defs: break
        current_programs = rewritten
        current_total = after
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
            changed = False
            for part in list(_walk(candidate)):
                mapping: dict[str, Any] = {}
                if _match(part, definition["body"], mapping):
                    call = {"op": "call", "name": name, "args": [mapping[param] for param in definition["params"]]}
                    candidate, changed = _replace(candidate, part, call)
                    break
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


def enumerate_programs(examples: list[dict[str, Any]], variables: list[str], library: dict[str, dict[str, Any]],
                       *, max_terms: int = 100000, max_cost: int = 7) -> list[dict[str, Any]]:
    """Enumerate pure programs bottom-up, deduplicating by training outputs."""
    by_cost: dict[int, list[Any]] = {1: [{"var": name} for name in variables] + [{"lit": value} for value in (True, False)]}
    seen: dict[tuple[Any, ...], int] = {}
    out: list[Any] = []
    def add(node: Any):
        if sum(len(v) for v in by_cost.values()) + len(out) >= max_terms: return
        signature = tuple(eval_program(node, ex["input"], library) for ex in examples)
        if signature in seen:
            old = out[seen[signature]]
            if any(isinstance(part, dict) and part.get("op") == "call" for part in _walk(node)) and not any(isinstance(part, dict) and part.get("op") == "call" for part in _walk(old)):
                out[seen[signature]] = node
            return
        seen[signature] = len(out); out.append(node)
    for cost in range(1, max_cost + 1):
        for node in by_cost.get(cost, []): add(node)
        for left_cost in range(1, cost - 1):
            right_cost = cost - 1 - left_cost
            for left in by_cost.get(left_cost, []):
                for right in by_cost.get(right_cost, []):
                    for op in ("and", "or", "eq"):
                        node = {"op": op, "args": [left, right]}
                        if sum(size(v) for v in node["args"]) + 1 == cost: add(node)
        if cost > 1:
            for child in by_cost.get(cost - 1, []): add({"op": "not", "args": [child]})
        for name, definition in library.items():
            args = [{"var": variable} for variable in variables[:len(definition["params"])] ]
            node = {"op": "call", "name": name, "args": args}
            if size(node) == cost: add(node)
        by_cost[cost] = [node for node in out if size(node) == cost]
    return out


def synthesize_target(target: dict[str, Any], library_doc: dict[str, Any], *, max_terms: int = 100000,
                      max_cost: int = 7) -> dict[str, Any]:
    train = target.get("train_examples", [])
    sealed = target.get("heldout_examples", [])
    variables = sorted({key for ex in train for key in ex.get("input", {})})
    library = library_doc.get("library", {})
    candidate = enumerate_programs(train, variables, library, max_terms=max_terms, max_cost=max_cost)
    baseline = enumerate_programs(train, variables, {}, max_terms=max_terms, max_cost=max_cost)
    def heldout(program, lib):
        return bool(sealed) and all(eval_program(program, ex["input"], lib) == ex["output"] for ex in sealed)
    chosen = next((p for p in candidate if any(part.get("op") == "call" for part in _walk(p) if isinstance(part, dict))), None)
    base = baseline[0] if baseline else None
    return {"schema": "capcov/synthesis-target-evaluation/v1", "target_id": target.get("id"),
            "selected_candidate": chosen, "baseline_candidate": base,
            "candidate_heldout_pass": chosen is not None and heldout(chosen, library),
            "baseline_heldout_pass": base is not None and heldout(base, {}),
            "candidate_search_count": len(candidate), "baseline_search_count": len(baseline),
            "sealed_count": len(sealed)}


def run_synthesis(input_path: Path, output_path: Path, *, max_defs: int = 16, max_tasks: int = 100) -> None:
    document = json.loads(input_path.read_text())
    tasks = document.get("tasks", [])
    library = learn_library(tasks, max_defs=max_defs)
    target = document.get("target")
    result = synthesize_target(target, library) if isinstance(target, dict) else synthesize(tasks, library, max_tasks=max_tasks)
    output_path.write_text(json.dumps({"library": library, "evaluation": result}, indent=2, sort_keys=True) + "\n")
