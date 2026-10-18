"""Bounded data transport to native Shen; no host semantic fallback."""

import json
import math
import os
from pathlib import Path
import shutil
import tempfile
from importlib import resources

from . import OperationError, _sha, _string
from .process import run


def term(value, depth=0):
    if depth > 128:
        raise OperationError("native data nesting exceeds 128")
    if isinstance(value, str):
        return _string(value)
    if type(value) is int and 0 <= value <= 65536:
        return str(value)
    if isinstance(value, list):
        return "[" + " ".join(term(v, depth + 1) for v in value) + "]"
    raise OperationError("native data requires lists, strings or bounded integers")


def invoke(expression, libraries, *, timeout=60):
    """Expression is compiler-owned code, never unvalidated user text."""
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise OperationError("timeout must be finite and positive")
    if len(expression.encode()) > 8 * 1024 * 1024:
        raise OperationError("native expression exceeds 8 MiB")
    launcher = shutil.which("bifrost")
    binary = os.environ.get("BIFROST_SHEN_GO", "")
    if not launcher or not os.path.isfile(binary) or not os.access(binary, os.X_OK):
        raise OperationError(
            "native Shen unavailable: require bifrost and BIFROST_SHEN_GO"
        )
    root = resources.files("capcov.operations").joinpath("shen")
    libs = {n: root.joinpath(n).read_bytes() for n in libraries}
    identity = {
        "runtime": {
            "shen": _sha(Path(binary).read_bytes()),
            "bifrost": _sha(Path(launcher).read_bytes()),
        },
        "libraries": {n: _sha(b) for n, b in libs.items()},
    }
    with tempfile.TemporaryDirectory(prefix="capcov-native-") as tmp:
        directory = Path(tmp)
        for name, content in libs.items():
            (directory / name).write_bytes(content)
        driver = directory / "driver.shen"
        driver.write_text(
            "\n".join(f'(load "{directory / n}")' for n in libs)
            + "\n(tc -)\n(capop.print-result "
            + expression
            + ")\n"
        )
        code, stdout, stderr = run(
            [launcher, "run", "--impl", "shen-go", "--raw", str(driver)],
            cwd=directory,
            timeout=timeout,
        )
    marker = b"CAPCOV-OPERATION-RESULT "
    lines = [
        line[len(marker) :] for line in stdout.splitlines() if line.startswith(marker)
    ]
    if code or len(lines) != 1:
        raise OperationError(
            "native judgment failed: "
            + (stderr or stdout)[-2500:].decode(errors="replace")
        )
    try:
        return json.loads(lines[0]), identity
    except ValueError as exc:
        raise OperationError("malformed native judgment result") from exc
