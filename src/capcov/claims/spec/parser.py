"""A data reader, not a Shen evaluator. All syntax nodes retain source spans."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


@dataclass(frozen=True)
class Location:
    source: str
    line: int
    column: int
    offset: int


class SpecError(ValueError):
    def __init__(self, message, location=None, code='spec-syntax'):
        self.code, self.location, self.message = code, location, message
        prefix = f'{location.source}:{location.line}:{location.column}: ' if location else ''
        super().__init__(prefix + message)


@dataclass(frozen=True)
class Symbol:
    text: str


@dataclass(frozen=True)
class Node:
    value: object
    location: Location


@dataclass(frozen=True)
class SourceClosure:
    declarations: tuple[Node, ...]
    digests: tuple[tuple[str, str], ...]


def parse(text: str, source='<spec>') -> tuple[Node, ...]:
    """Read bracket lists, identifiers, JSON strings, integers and booleans.

    Semicolon comments end at newline. Parentheses, executable imports and
    arbitrary Shen reader forms are intentionally not part of this language.
    """
    if len(text.encode('utf-8')) > 16 * 1024 * 1024:
        raise SpecError('source exceeds 16 MiB', code='spec-resource')
    index, line, col = 0, 1, 1
    stack = [[]]
    starts = []
    decoder = json.JSONDecoder()
    while index < len(text):
        c = text[index]
        start = Location(source, line, col, index)
        if c.isspace():
            end = index + 1
        elif c == ';':
            end = text.find('\n', index)
            if end == -1:
                end = len(text)
        elif c == '[':
            if len(stack) >= 128:
                raise SpecError('nesting exceeds 128', start, 'spec-resource')
            stack.append([]); starts.append(start); end = index + 1
        elif c == ']':
            if len(stack) == 1:
                raise SpecError('unexpected closing bracket', start)
            value = tuple(stack.pop())
            stack[-1].append(Node(value, starts.pop())); end = index + 1
        elif c == '"':
            try:
                value, length = decoder.raw_decode(text[index:])
            except ValueError as exc:
                raise SpecError('invalid quoted string', start) from exc
            if not isinstance(value, str):
                raise SpecError('expected string', start)
            stack[-1].append(Node(value, start)); end = index + length
        else:
            match = re.match(r'[A-Za-z0-9_+./:=!?<>*-]+', text[index:])
            if not match:
                raise SpecError(f'unsupported character {c!r}', start)
            token = match.group()
            value = {'true': True, 'false': False, 'null': None}.get(token, Symbol(token))
            if re.fullmatch(r'-?(0|[1-9][0-9]*)', token):
                value = int(token)
            stack[-1].append(Node(value, start)); end = index + len(token)
        consumed = text[index:end]
        count = consumed.count('\n')
        col = len(consumed.rsplit('\n', 1)[1]) + 1 if count else col + len(consumed)
        line += count
        index = end
    if len(stack) != 1:
        raise SpecError('unclosed bracket', starts[-1])
    return tuple(stack[0])


def form(node, name=None):
    if (not isinstance(node.value, tuple) or not node.value
            or not isinstance(node.value[0].value, Symbol)):
        raise SpecError('expected a named declaration', node.location)
    tag = node.value[0].value.text
    if name is not None and tag != name:
        raise SpecError(f'expected {name}, found {tag}', node.location)
    return tag, node.value[1:]


def data(node):
    """Mechanical decoding of immutable data into the strict IR wire format."""
    if not isinstance(node.value, tuple):
        if isinstance(node.value, Symbol):
            raise SpecError('data names must be quoted strings', node.location)
        return node.value
    tag, args = form(node)
    if tag == 'array':
        return [data(arg) for arg in args]
    if tag == 'object':
        result = {}
        for pair in args:
            if not isinstance(pair.value, tuple) or len(pair.value) != 2:
                raise SpecError('object fields are [name value] pairs', pair.location)
            key = pair.value[0].value
            key = key.text if isinstance(key, Symbol) else key
            if not isinstance(key, str) or key in result:
                raise SpecError('duplicate or invalid object field', pair.location)
            result[key] = data(pair.value[1])
        return result
    raise SpecError(f'unsupported data form {tag}', node.location)


def read_sources(source) -> SourceClosure:
    source = Path(source).resolve()
    root = source.parent
    declarations, digests, active, visited = [], {}, set(), set()

    def visit(path):
        relative = path.relative_to(root).as_posix()
        if relative in active:
            raise SpecError(f'cyclic import: {relative}', code='spec-import')
        if relative in visited:
            return
        if len(visited) + len(active) >= 256:
            raise SpecError('import closure exceeds 256 files', code='spec-resource')
        active.add(relative)
        raw = path.read_bytes()
        digests[relative] = hashlib.sha256(raw).hexdigest()
        nodes = parse(raw.decode('utf-8'), relative)
        if len(nodes) != 1:
            raise SpecError('one claims-spec declaration is required')
        _, body = form(nodes[0], 'claims-spec')
        if not body or type(body[0].value) is not int or body[0].value != 1:
            raise SpecError('unsupported declaration language version', nodes[0].location)
        for decl in body[1:]:
            tag, args = form(decl)
            if tag == 'import':
                if len(args) != 1 or not isinstance(args[0].value, str):
                    raise SpecError('import requires a literal relative path', decl.location, 'spec-import')
                name = PurePosixPath(args[0].value)
                if name.is_absolute() or '..' in name.parts or '\\' in args[0].value:
                    raise SpecError('imports are source-root-relative paths', decl.location, 'spec-import')
                target = (root / name).resolve()
                if not target.is_relative_to(root):
                    raise SpecError('import escapes source root', decl.location, 'spec-import')
                visit(target)
            else:
                declarations.append(decl)
        active.remove(relative); visited.add(relative)
    visit(source)
    return SourceClosure(tuple(declarations), tuple(sorted(digests.items())))
