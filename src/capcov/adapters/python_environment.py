"""Extract a deliberately small Python registry-dispatch fragment without eval.

Literal module dictionaries of local functions, called by literal keys or keys
read from a named configuration object. General Python mutation/alias semantics
are not established; the common recovery extraction boundary remains mandatory.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from .environment import SCHEMA, recover
from .python_fastapi_sqlalchemy import _dotted, _walk_scoped


def recover_python(raw: dict, root: Path, config: dict) -> dict:
    if not isinstance(config, dict) or set(config) != {"file", "variable"}:
        raise ValueError("environment_python requires exactly file and variable")
    variable = config["variable"]
    if not isinstance(variable, str) or not variable.isidentifier():
        raise ValueError("environment_python.variable must be a Python identifier")
    document = {"schema": SCHEMA, "producer": "capcov.python-literal-registry.v1",
                "environment": config["file"], "nodes": [], "bindings": [],
                "calls": [], "effects": []}
    gaps = [{"kind": "environment-python-stability", "id": "python-registry-stability",
             "reason": "literal registries and function bindings must remain unchanged; "
                       "the named configuration object must correspond to the configuration file"}]
    inputs = {}
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        data = path.read_bytes()
        file = path.relative_to(root).as_posix()
        digest = hashlib.sha256(data).hexdigest()
        inputs[file] = digest
        tree = ast.parse(data, filename=file)
        module = _dotted(root, path)
        functions = {n.name for n in tree.body
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

        def anchor(node):
            return {"file": file, "line": node.lineno, "sha256": digest}

        def identity(node, suffix):
            return f"python-env:{file}:{node.lineno}:{node.col_offset}:{suffix}"

        # Only uniquely assigned literal registries are candidates. Mutations or
        # escapes still require the explicitly retained extraction obligation.
        assignments = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                assignments.setdefault(node.targets[0].id, []).append(node)
        registries = {}
        for name, declarations in assignments.items():
            if len(declarations) != 1 or not isinstance(declarations[0].value, ast.Dict):
                continue
            literal = declarations[0].value
            entries = []
            keys = set()
            for key, value in zip(literal.keys, literal.values):
                if not isinstance(key, ast.Constant) or type(key.value) is not str or key.value in keys:
                    break
                if not isinstance(value, ast.Name) or value.id not in functions:
                    break
                keys.add(key.value)
                entries.append((key.value, f"{module}:{value.id}"))
            else:
                registries[name] = entries

        for fn, qualname in _walk_scoped(tree, []):
            # Do not attribute nested function/class bodies to their parents.
            body_nodes = []
            pending = list(fn.body)
            while pending:
                node = pending.pop()
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                    continue
                body_nodes.append(node)
                pending.extend(ast.iter_child_nodes(node))
            local_names = {n.id for n in body_nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
            local_names.update(arg.arg for arg in [*fn.args.posonlyargs, *fn.args.args,
                                                   *fn.args.kwonlyargs])
            local_names.update(arg.arg for arg in (fn.args.vararg, fn.args.kwarg) if arg)
            for node in body_nodes:
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Subscript):
                    continue
                sub = node.func
                call_id = identity(node, "call")
                slot = call_id + ":targets"
                document["calls"].append({"id": call_id, "caller": f"{module}:{qualname}",
                                           "slot": slot, "source": anchor(node)})
                entries = registries.get(sub.value.id) if isinstance(sub.value, ast.Name) else None
                if entries is None or sub.value.id in local_names or "." in qualname:
                    continue  # Empty slot is reported as unresolved by recovery.
                selector = sub.slice
                key = None
                if isinstance(selector, ast.Constant) and type(selector.value) is str:
                    entries = [(k, target) for k, target in entries if k == selector.value]
                elif (isinstance(selector, ast.Subscript) and
                      isinstance(selector.value, ast.Name) and selector.value.id == variable and
                      variable not in local_names and isinstance(selector.slice, ast.Constant) and
                      type(selector.slice.value) is str):
                    key = selector.slice.value
                else:
                    gaps.append({"kind": "environment-unresolved", "id": call_id,
                                 "source": anchor(node),
                                 "reason": "unsupported registry selector; all literal candidates retained"})
                for index, (value, target) in enumerate(entries):
                    document["bindings"].append({"id": identity(node, f"binding:{index}"),
                        "source": anchor(node), "slot": slot, "target": target,
                        "when": {key: value} if key is not None else {}})
    result = recover(raw, root, "python-literal-registry", document=document)
    # All parsed files, including negative results, contribute to invalidation.
    analysis = result["environment_recovery"][-1]
    analysis["input_sha256"].update(inputs)
    analysis["unresolved"].extend(gaps)
    result["unresolved"].extend(gaps)
    from .environment import _digest
    analysis.pop("analysis_sha256")
    analysis["analysis_sha256"] = _digest(analysis)
    return result
