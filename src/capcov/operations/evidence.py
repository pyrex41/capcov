"""Deterministic source inventory, candidate claims, and transitive invalidation.

Syntax facts are evidence of source text, never inferred business correctness.
Behavioral claims and mappings are supplied explicitly by the consumer.
"""

import ast
import copy
from pathlib import Path, PurePosixPath

from . import OperationError, _sha, MAX_BYTES
from .system import digest


def _path(root, relative):
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise OperationError("source path must be relative POSIX text")
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or str(path) != relative:
        raise OperationError("source path escapes root or is noncanonical")
    base = Path(root).resolve()
    p = (base / relative).resolve()
    if not p.is_relative_to(base):
        raise OperationError("source symlink escapes root")
    return p


def _read(root, relative):
    p = _path(root, relative)
    if p.stat().st_size > 4 * MAX_BYTES:
        raise OperationError("source exceeds 4 MiB")
    return p.read_bytes()


def extract(root, files, *, revision="working-tree"):
    """Inventory exact Python AST and Go/PHP Tree-sitter syntax occurrences."""
    if (
        not isinstance(files, list)
        or not 1 <= len(files) <= 512
        or len(set(files)) != len(files)
    ):
        raise OperationError("inventory needs 1..512 distinct explicit source paths")
    sources, anchors = {}, []
    total = 0
    for name in sorted(files):
        raw = _read(root, name)
        total += len(raw)
        if total > 32 * MAX_BYTES:
            raise OperationError("inventory exceeds 32 MiB")
        text = raw.decode("utf8")
        sources[name] = _sha(raw)

        def add(kind, symbol, start, end, snippet):
            anchor = {
                "path": name,
                "source_sha256": sources[name],
                "kind": kind,
                "symbol": symbol,
                "start_line": start,
                "end_line": end,
                "text_sha256": _sha(snippet.encode()),
                "text": snippet,
            }
            anchor["id"] = digest(anchor)
            anchors.append(anchor)
            if len(anchors) > 8192:
                raise OperationError("inventory anchor budget exhausted")

        suffix = Path(name).suffix
        if suffix == ".py":
            tree = ast.parse(text, filename=name)

            def walk(node, scope):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    scope = ".".join(filter(None, (scope, node.name)))
                if isinstance(
                    node,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                        ast.If,
                        ast.Assert,
                        ast.Raise,
                        ast.Return,
                        ast.Assign,
                        ast.Call,
                    ),
                ):
                    add(
                        type(node).__name__,
                        scope,
                        node.lineno,
                        node.end_lineno,
                        ast.get_source_segment(text, node) or "",
                    )
                for child in ast.iter_child_nodes(node):
                    walk(child, scope)

            walk(tree, "<module>")
        elif suffix in (".go", ".php"):
            try:
                from tree_sitter import Language, Parser

                try:
                    if suffix == ".go":
                        from tree_sitter_go import language
                    else:
                        from tree_sitter_php import language_php as language
                    grammar = Language(language())
                except ImportError:
                    # The Nix withTreesitter package supplies the language pack.
                    # uv's locked extra instead supplies direct grammar wheels.
                    from tree_sitter_language_pack import get_language

                    grammar = get_language("go" if suffix == ".go" else "php")
                parser = Parser(grammar)
                tree = parser.parse(raw)
            except (ImportError, RuntimeError) as exc:
                raise OperationError(
                    "Go/PHP extraction requires installed Tree-sitter grammars"
                ) from exc
            if tree.root_node.has_error:
                raise OperationError("source has parse errors: " + name)
            kinds = {
                "function_declaration",
                "method_declaration",
                "function_definition",
                "if_statement",
                "return_statement",
                "throw_expression",
                "assignment_expression",
                "assignment_statement",
                "call_expression",
            }

            def walk(node, scope):
                if node.type in (
                    "function_declaration",
                    "method_declaration",
                    "function_definition",
                ):
                    child = node.child_by_field_name("name")
                    if child:
                        scope = raw[child.start_byte : child.end_byte].decode()
                if node.type in kinds:
                    add(
                        node.type,
                        scope,
                        node.start_point.row + 1,
                        node.end_point.row + 1,
                        raw[node.start_byte : node.end_byte].decode(),
                    )
                for child in node.named_children:
                    walk(child, scope)

            walk(tree.root_node, "<module>")
        else:
            raise OperationError("supported source languages: Python, Go, PHP")
    result = {
        "format": "capcov-source-inventory-v1",
        "revision": revision,
        "sources": sources,
        "anchors": anchors,
        "claims": [],
        "gaps": [],
    }
    result["sha256"] = digest(result)
    return result


def validate(bundle):
    if (
        not isinstance(bundle, dict)
        or set(bundle)
        != {"format", "revision", "sources", "anchors", "claims", "gaps", "sha256"}
        or bundle["format"] != "capcov-source-inventory-v1"
    ):
        raise OperationError("invalid source evidence envelope")
    if digest({k: v for k, v in bundle.items() if k != "sha256"}) != bundle["sha256"]:
        raise OperationError("source evidence digest mismatch")
    ids = set()
    for a in bundle["anchors"]:
        if a["id"] in ids or a["id"] != digest(
            {k: v for k, v in a.items() if k != "id"}
        ):
            raise OperationError("invalid or duplicate source anchor")
        if (
            bundle["sources"].get(a["path"]) != a["source_sha256"]
            or _sha(a["text"].encode()) != a["text_sha256"]
        ):
            raise OperationError("anchor source identity mismatch")
        ids.add(a["id"])
    claims = {}
    for c in bundle["claims"]:
        if (
            set(c)
            != {"id", "statement", "kind", "anchors", "depends_on", "obligations"}
            or not isinstance(c["id"], str)
            or not c["id"]
            or c["id"] in claims
        ):
            raise OperationError("invalid or duplicate candidate claim")
        if (
            c["kind"] not in ("legacy", "target")
            or not isinstance(c["statement"], str)
            or not c["statement"]
        ):
            raise OperationError("claim needs statement and legacy/target kind")
        if not isinstance(c["anchors"], list) or not set(c["anchors"]) <= ids:
            raise OperationError("claim cites unknown source anchor")
        if not isinstance(c["depends_on"], list) or not isinstance(
            c["obligations"], list
        ):
            raise OperationError("claim dependencies and obligations must be lists")
        claims[c["id"]] = c
    active, done = set(), set()

    def visit(name):
        if name in active or name not in claims:
            raise OperationError("cyclic or unknown claim dependency")
        if name in done:
            return
        active.add(name)
        for parent in claims[name]["depends_on"]:
            visit(parent)
        active.remove(name)
        done.add(name)

    for name in claims:
        visit(name)
    gap_ids = set()
    for g in bundle["gaps"]:
        if (
            set(g) != {"id", "question", "claims"}
            or not isinstance(g["question"], str)
            or not g["question"]
            or g["id"] in gap_ids
            or not set(g["claims"]) <= claims.keys()
        ):
            raise OperationError("invalid gap or gap claim references")
        gap_ids.add(g["id"])
    return True


def bind(inventory, claims, gaps=()):
    validate(inventory)
    result = copy.deepcopy(inventory)
    result.update(claims=copy.deepcopy(claims), gaps=copy.deepcopy(list(gaps)))
    result["sha256"] = digest({k: v for k, v in result.items() if k != "sha256"})
    validate(result)
    return result


def invalidate(root, bundle, *, engine="python", timeout=60):
    validate(bundle)
    changed = []
    for path, expected in bundle["sources"].items():
        try:
            current = _sha(_read(root, path))
        except FileNotFoundError:
            current = None
        if current != expected:
            changed.append(path)
    unchanged = [p for p in bundle["sources"] if p not in changed]
    if unchanged:
        fresh = extract(root, unchanged, revision=bundle["revision"])
        if any(fresh["sources"][p] != bundle["sources"][p] for p in unchanged):
            raise OperationError("source changed during anchor verification")
        actual_anchors = {a["id"] for a in fresh["anchors"]}
        if any(
            a["path"] in unchanged and a["id"] not in actual_anchors
            for a in bundle["anchors"]
        ):
            raise OperationError("source anchor cannot be reproduced")
    stale_anchors = {a["id"] for a in bundle["anchors"] if a["path"] in changed}
    stale = {
        c["id"] for c in bundle["claims"] if stale_anchors.intersection(c["anchors"])
    }
    while True:
        next_stale = stale | {
            c["id"] for c in bundle["claims"] if stale.intersection(c["depends_on"])
        }
        if next_stale == stale:
            break
        stale = next_stale
    if engine == "souffle":
        native_stale = _souffle(bundle, changed, timeout)
        if native_stale != stale:
            raise OperationError("Souffle/Python invalidation disagreement")
    elif engine != "python":
        raise OperationError("invalidation engine must be python or souffle")
    return {
        "format": "capcov-source-invalidation-v1",
        "basis": bundle["sha256"],
        "engine": engine,
        "changed_sources": changed,
        "stale_claims": sorted(stale),
        "remaining_claims": sorted(
            c["id"] for c in bundle["claims"] if c["id"] not in stale
        ),
        "open_gaps": copy.deepcopy(bundle["gaps"]),
    }


def _souffle(bundle, changed, timeout):
    import shutil
    import tempfile
    from importlib import resources
    from .process import run

    binary = shutil.which("souffle")
    if not binary:
        raise OperationError("Souffle invalidation requires souffle executable")
    # Content-derived identifiers avoid fact-file quoting ambiguities entirely.
    anchor_paths = {a["id"]: a["path"] for a in bundle["anchors"]}
    names = {digest(c["id"]): c["id"] for c in bundle["claims"]}
    facts = {
        "cited": [
            (digest(c["id"]), digest(anchor_paths[a]))
            for c in bundle["claims"]
            for a in c["anchors"]
        ],
        "depends": [
            (digest(c["id"]), digest(p))
            for c in bundle["claims"]
            for p in c["depends_on"]
        ],
        "changed": [(digest(p),) for p in changed],
    }
    with tempfile.TemporaryDirectory(prefix="capcov-impact-") as tmp:
        root = Path(tmp)
        rules = root / "evidence.dl"
        rules.write_bytes(
            resources.files("capcov.operations").joinpath("evidence.dl").read_bytes()
        )
        for name, rows in facts.items():
            (root / (name + ".facts")).write_text(
                "".join("\t".join(r) + "\n" for r in rows)
            )
        code, _, stderr = run(
            [binary, "-F", tmp, "-D", tmp, str(rules)], timeout=timeout
        )
        if code:
            raise OperationError(
                "Souffle invalidation failed: "
                + stderr[-1000:].decode(errors="replace")
            )
        return {names[x] for x in (root / "stale.csv").read_text().splitlines()}
