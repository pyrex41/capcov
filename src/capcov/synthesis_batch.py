from __future__ import annotations
import argparse, hashlib, json
from collections import defaultdict
from pathlib import Path

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
        target_vector = vectors[-1]
        train = []
        for _, rows in members:
            if target_vector not in rows: train.extend({"input": dict(vector), "output": output} for vector, output in rows.items())
        sealed = [{"input": dict(target_vector), "output": next(rows[target_vector] for _, rows in members if target_vector in rows)}]
        report["families"].append({"family": family, "operation_count": len(members), "distinct_vectors": len(vectors), "target_vector": dict(target_vector), "training_examples": len(train), "sealed": sealed, "status": "observation-only", "invention_success": False})
    report["included_operations"] = sum(item["operation_count"] for item in report["families"])
    report["excluded_operations"] = len(excluded)
    return report

def main(argv=None):
    parser = argparse.ArgumentParser(prog="capcov synthesize-batch")
    parser.add_argument("input", type=Path); parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-families", type=int, default=100); parser.add_argument("--max-terms", type=int, default=100000); parser.add_argument("--max-cost", type=int, default=7)
    args = parser.parse_args(argv)
    args.out.write_text(json.dumps(build(json.loads(args.input.read_text()), max_families=args.max_families, max_terms=args.max_terms, max_cost=args.max_cost), indent=2, sort_keys=True) + "\n")
    return 0
