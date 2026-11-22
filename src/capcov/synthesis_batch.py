from __future__ import annotations
import argparse, hashlib, json
from collections import defaultdict
from pathlib import Path
from .boolean_search import search
from .synthesis import eval_program, learn_library

def _vector(example):
    value = example.get("input")
    if not isinstance(value, dict) or any(not isinstance(v, bool) for v in value.values()):
        raise ValueError("input must be a boolean feature object")
    return tuple(sorted(value.items()))

def build(document, *, max_families=100, max_terms=100000, max_cost=7):
    operations = document.get("operations") if isinstance(document, dict) else None
    if not isinstance(operations, dict): raise ValueError("input requires operations object")
    families = defaultdict(list); excluded = []
    for census_id, operation in sorted(operations.items()):
        if not isinstance(operation, dict) or not isinstance(operation.get("family"), str):
            excluded.append({"id": census_id, "reason": "missing family"}); continue
        try:
            examples = operation.get("examples", [])
            by_vector = {}
            contradictory = False
            for example in examples:
                vector = _vector(example); output = example.get("output")
                if not isinstance(output, bool): raise ValueError("output must be boolean")
                if vector in by_vector and by_vector[vector] != output: contradictory = True
                by_vector[vector] = output
            if contradictory: raise ValueError("contradictory repeated feature vector")
            if len(by_vector) < 2: raise ValueError("insufficient distinct feature vectors")
            if len(set(by_vector.values())) < 2: raise ValueError("constant-only evidence")
            families[operation["family"]].append((census_id, by_vector))
        except ValueError as error:
            excluded.append({"id": census_id, "reason": str(error)})
    report = {"schema": "capcov/synthesis-batch/v1", "bounds": {"max_families": max_families, "max_terms": max_terms, "max_cost": max_cost}, "families": [], "excluded": excluded}
    for family in sorted(families)[:max_families]:
        members = families[family][:max_terms]
        vectors = sorted({vector for _, rows in members for vector in rows})
        target_id, target_rows = members[-1]
        target_vectors = sorted(target_rows)
        target_vector = target_vectors[-1]
        target_examples = [{"input": dict(vector), "output": output} for vector, output in target_rows.items()]
        fit = [row for row in target_examples if _vector(row) != target_vector]
        sealed = [row for row in target_examples if _vector(row) == target_vector]
        solved = []
        failures = []
        for operation_id, rows in members[:-1]:
            examples = [{"input": dict(vector), "output": output} for vector, output in rows.items()]
            try:
                solution = search(examples, {}, max_terms=max_terms, max_cost=max_cost)
                if solution["program"] is None: raise ValueError(solution["stop"])
                if not all(eval_program(solution["program"], row["input"], {}) == row["output"] for row in examples): raise ValueError("fit interpreter disagreement")
                solved.append({"id": operation_id, "program": solution["program"], "examples": examples})
            except (ValueError, KeyError) as error:
                failures.append({"id": operation_id, "reason": str(error)})
        library = learn_library(solved)
        candidate = search(fit, library, max_terms=max_terms, max_cost=max_cost) if fit else {"program": None, "stop": "insufficient target fit"}
        baseline = search(fit, {}, max_terms=max_terms, max_cost=max_cost) if fit else {"program": None, "stop": "insufficient target fit"}
        candidate_ok = candidate.get("program") is not None and all(eval_program(candidate["program"], row["input"], library) == row["output"] for row in sealed)
        baseline_ok = baseline.get("program") is not None and all(eval_program(baseline["program"], row["input"], {}) == row["output"] for row in sealed)
        used = bool(candidate.get("program") and any(isinstance(part, dict) and part.get("op") == "call" for part in _walk(candidate["program"])))
        report["families"].append({"family": family, "operation_count": len(members), "target_operation": target_id, "distinct_vectors": len(vectors), "training_examples": len(fit), "sealed": len(sealed), "status": "evaluated", "invention_success": bool(used and candidate_ok), "candidate_heldout_pass": candidate_ok, "baseline_heldout_pass": baseline_ok, "used_invented_call": used, "candidate_search": candidate, "baseline_search": baseline, "library": library, "training_failures": failures})
    report["included_operations"] = sum(item["operation_count"] for item in report["families"])
    report["excluded_operations"] = len(excluded)
    return report

def _walk(node):
    yield node
    if isinstance(node, dict):
        for value in node.values(): yield from _walk(value)
    elif isinstance(node, list):
        for value in node: yield from _walk(value)

def main(argv=None):
    parser = argparse.ArgumentParser(prog="capcov synthesize-batch")
    parser.add_argument("input", type=Path); parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-families", type=int, default=100); parser.add_argument("--max-terms", type=int, default=100000); parser.add_argument("--max-cost", type=int, default=7)
    args = parser.parse_args(argv)
    args.out.write_text(json.dumps(build(json.loads(args.input.read_text()), max_families=args.max_families, max_terms=args.max_terms, max_cost=args.max_cost), indent=2, sort_keys=True) + "\n")
    return 0
