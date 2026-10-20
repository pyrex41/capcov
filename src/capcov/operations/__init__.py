"""Typed finite operation specifications, executed by Shen.

Python transports data and records provenance; it implements no operation
semantics. Results never admit external evidence or establish completeness.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
from importlib import resources

from capcov.claims import shen_runtime
from capcov.claims.spec.parser import parse, Symbol

TAGS = frozenset({'operation', 'live', 'named', 'delete-related', 'set-target',
                  'emit-related', 'emit-target'})
LIBRARIES = ('kernel.shen', 'types/action.shen', 'types/named.shen',
             'types/actions.shen', 'types/program.shen')
MAX_BYTES = 1024 * 1024


class OperationError(ValueError):
    """Malformed data, unsupported constructs, or a failed native execution."""


def _native_shen():
    """The selected Shen runtime (``capcov.claims.shen_runtime``), its launcher and binary."""
    try:
        impl = shen_runtime.selected()
    except shen_runtime.UnknownImpl as exc:
        raise OperationError(f'native Shen unavailable: {exc}') from None
    launcher = shutil.which('bifrost')
    binary = impl.binary()
    if not launcher or not os.path.isfile(binary) or not os.access(binary, os.X_OK):
        raise OperationError(f'native Shen unavailable: require bifrost and {impl.env}')
    try:
        shen_runtime.support_sha256(impl, binary)
    except FileNotFoundError as exc:
        raise OperationError(f'native Shen unavailable: {exc}') from None
    return impl, launcher, binary


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _string(value):
    if not isinstance(value, str) or len(value.encode('utf-8')) > 4096:
        raise OperationError('expected a string of at most 4096 UTF-8 bytes')
    # No executable interpolation: Shen strings do not use JSON escapes.
    return '(capop.string [' + ' '.join(str(c) for c in value.encode('utf-8')) + '])'


def _spec(source):
    if len(source.encode('utf-8')) > MAX_BYTES:
        raise OperationError('specification exceeds 1 MiB')
    nodes = parse(source, '<operation>')
    if len(nodes) != 1:
        raise OperationError('specification must contain one data term')

    def emit(node, depth=0):
        if depth > 16:
            raise OperationError('specification nesting exceeds 16')
        value = node.value
        if isinstance(value, Symbol):
            if value.text not in TAGS:
                raise OperationError(f'unsupported operation constructor: {value.text}')
            return value.text
        if isinstance(value, str):
            return _string(value)
        if isinstance(value, tuple):
            return '[' + ' '.join(emit(n, depth+1) for n in value) + ']'
        raise OperationError('operation values must be strings, lists or constructors')

    return emit(nodes[0])


def _strings(values):
    if not isinstance(values, list):
        raise OperationError('expected an array')
    return '[' + ' '.join(_string(v) for v in values) + ']'


def _state(rows):
    if not isinstance(rows, list) or len(rows) > 256:
        raise OperationError('state must contain at most 256 rows')
    output = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'table', 'key', 'fields'}:
            raise OperationError('row requires exactly table, key and fields')
        fields = row['fields']
        if not isinstance(fields, dict) or len(fields) > 64:
            raise OperationError('row must contain at most 64 fields')
        pairs = '[' + ' '.join('[' + _string(k) + ' ' + _string(v) + ']'
                              for k,v in sorted(fields.items())) + ']'
        output.append('[row ' + _string(row['table']) + ' ' + _string(row['key']) + ' ' + pairs + ']')
    return '[' + ' '.join(output) + ']'


def _effects(effects):
    if not isinstance(effects, list) or len(effects) > 16384:
        raise OperationError('expected at most 16384 ordered effects')
    arities = {'put': 5, 'delete': 3, 'emit': 3}
    output = []
    for e in effects:
        if not isinstance(e, list) or not e or not isinstance(e[0], str) or len(e) != arities.get(e[0]):
            raise OperationError('invalid observed effect')
        output.append('[' + e[0] + ' ' + ' '.join(_string(v) for v in e[1:]) + ']')
    return '[' + ' '.join(output) + ']'


def execute(source: str, request: dict, *, timeout: float = 30) -> dict:
    """Typecheck the spec, analyze, simulate and optionally judge observations.

    Row order is significant in this finite model (including child effect order).
    Fields are canonicalized by name; observed effects retain their exact order.
    """
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise OperationError('timeout must be finite and positive')
    if not isinstance(request, dict) or set(request) - {'state','target','outcome','variant','observed','trace','search'}:
        raise OperationError('unknown request fields')
    if not {'state','target','outcome'} <= set(request):
        raise OperationError('request requires state, target and outcome')
    raw = json.dumps(request, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    if len(raw) > MAX_BYTES:
        raise OperationError('request exceeds 1 MiB')
    program, state, target = _spec(source), _state(request['state']), _string(request['target'])
    outcome = request['outcome']
    if outcome not in ('committed','aborted','unknown'):
        raise OperationError('unsupported outcome')
    variant = request.get('variant', 'intended')
    if variant == 'intended':
        variant_term = 'intended'
    elif isinstance(variant, dict) and set(variant) == {'divergence','omit'}:
        variant_term = '[omit ' + _string(variant['divergence']) + ' ' + _strings(variant['omit']) + ']'
    else:
        raise OperationError('variant must be intended or a named omission')
    observed = request.get('observed')
    observation = 'not-requested'
    if observed is not None:
        if not isinstance(observed, dict) or set(observed) != {'state','effects'}:
            raise OperationError('observation requires state and effects')
        observation = ('(capop.accepts? P V S I ' + outcome + ' ' +
                       _state(observed['state']) + ' ' + _effects(observed['effects']) + ')')
    trace_check = 'not-requested'
    if 'trace' in request:
        trace = request['trace']
        if not isinstance(trace, dict) or set(trace) != {'state','effects','steps'} or not isinstance(trace['steps'], list) or len(trace['steps']) > 64:
            raise OperationError('trace requires state, effects and at most 64 steps')
        steps = []
        for step in trace['steps']:
            if not isinstance(step, dict) or set(step) != {'name','effects'}:
                raise OperationError('trace step requires name and effects')
            steps.append('[action ' + _string(step['name']) + ' ' + _effects(step['effects']) + ']')
        trace_check = ('(capop.check-trace? P V S I [result ' + _state(trace['state']) + ' ' +
                       _effects(trace['effects']) + ' [' + ' '.join(steps) + ']])')
    search_term = 'not-requested'
    if 'search' in request:
        search = request['search']
        if not isinstance(search, dict) or set(search) != {'variant','states'} or not isinstance(search['states'], list) or len(search['states']) > 16:
            raise OperationError('search requires a variant and at most 16 candidate states')
        other = search['variant']
        if other == 'intended':
            other_term = 'intended'
        elif isinstance(other, dict) and set(other) == {'divergence','omit'}:
            other_term = '[omit ' + _string(other['divergence']) + ' ' + _strings(other['omit']) + ']'
        else:
            raise OperationError('search variant must be intended or a named omission')
        search_term = '(capop.find-disagreement P V ' + other_term + ' [' + ' '.join(_state(s) for s in search['states']) + '] I)'
    impl, launcher, binary = _native_shen()
    root = resources.files(__package__).joinpath('shen')
    libs = {name: root.joinpath(name).read_bytes() for name in LIBRARIES}
    # Materialize resources: installed wheels need no source checkout.
    with tempfile.TemporaryDirectory(prefix='capcov-operation-') as tmp:
        directory = Path(tmp)
        for name, content in libs.items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        # Generated resource paths contain no quotes. Spec/request strings are
        # emitted only as code points, never raw Shen syntax.
        loads = '\n'.join(f'(load "{directory / name}")' for name in LIBRARIES)
        driver = directory / 'driver.shen'
        driver.write_text(loads + '\n(tc +)\n' +
            f'(let P {program} V {variant_term} S {state} I {target}\n'
            f'  (if (capop.typechecks? P)\n'
            f'      (capop.print-result [(capop.analyze P V) (capop.run P V S I)\n'
            f'                           (capop.admissible P V S I {outcome}) {observation} {trace_check} {search_term}])\n'
            f'      (error "operation: specification does not inhabit capop-program")))\n', encoding='utf-8')
        proc = subprocess.Popen(shen_runtime.bifrost_argv(launcher, impl, driver),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=directory, env=shen_runtime.child_env(impl, binary), start_new_session=True)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            raise OperationError('native operation timeout') from None
        marker = b'CAPCOV-OPERATION-RESULT '
        lines = [line[len(marker):] for line in stdout.splitlines() if line.startswith(marker)]
        if proc.returncode or len(lines) != 1:
            raise OperationError('native operation rejected input: ' + (stderr or stdout)[-2000:].decode('utf-8', errors='replace'))
        try:
            analysis, result, alternatives, matches, trace_valid, counterexample = json.loads(lines[0])
        except (ValueError, TypeError) as exc:
            raise OperationError('malformed native operation response') from exc
    # For shen-go exactly the binary's digest; another runtime is named, with
    # its identity digest (capcov.claims.shen_runtime.runtime_record).
    record = shen_runtime.runtime_record(impl, binary)
    return {'format':'capcov-operation-result-v1', 'basis':'bounded-operation-model',
            'spec_sha256':_sha(source.encode('utf-8')), 'request_sha256':_sha(raw),
            **({'runtime_impl':impl.name} if impl.name != shen_runtime.LEGACY_SHAPE_IMPL else {}),
            'runtime_sha256':record['shen'], 'launcher_sha256':_sha(Path(launcher).read_bytes()),
            'libraries':{n:_sha(b) for n,b in libs.items()},
            'analysis':analysis, 'transition':result, 'admissible':alternatives,
            'observed_matches':matches, 'trace_valid':trace_valid,
            'counterexample':counterexample}
