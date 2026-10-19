"""Which Shen runtime capcov starts, and how that runtime is named in evidence.

``CAPCOV_SHEN_IMPL`` selects one of ``IMPLS`` (unset or empty: ``shen-go``).
Each runtime is launched through bifrost's adapter of the same name, with the
binary named explicitly by that adapter's variable, so bifrost never falls
back to a default path.  Nothing here chooses a runtime on its own: an unknown
name, an unset variable or a missing support file is an error.

Evidence names the runtime by its files.  shen-go and shen-c are one
self-contained executable each.  shen-scheme is an executable plus the Chez
boot files and the compiled Shen runtime it loads from ``../lib/shen-scheme``;
all four are hashed, since the executable alone does not identify what runs.
For shen-go every record keeps the shape it had before this module existed.

Numbers are the same contract for every runtime: integers below 2**53 in
magnitude and no floats.  shen-go numbers are float64; shen-scheme and shen-c
are exact past 2**53 and print floats differently (``3.0``, digit counts), so
widening the contract for them would make an answer depend on the runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import Mapping

DEFAULT_IMPL = "shen-go"
SETTING = "CAPCOV_SHEN_IMPL"
# Variables a runtime reads to relocate itself or change mode; a child never
# inherits them, so the hashed files are the files that run.
SCRUBBED_ENV = ("SHEN_SCHEME_HOME", "SHEN_SCHEME_RUNTIME", "SHEN_C_HOME", "SHEN_RC_HOME")


@dataclass(frozen=True)
class Impl:
    name: str
    env: str  # the bifrost adapter's binary variable
    support: tuple[str, ...] = ()  # files the binary loads, relative to its resolved path

    def binary(self) -> str:
        return os.environ.get(self.env, "")


IMPLS: dict[str, Impl] = {impl.name: impl for impl in (
    Impl("shen-go", "BIFROST_SHEN_GO"),
    Impl("shen-scheme", "BIFROST_SHEN_SCHEME",
         ("../lib/shen-scheme/petite.boot", "../lib/shen-scheme/scheme.boot",
          "../lib/shen-scheme/shen-scheme/runtime.so")),
    Impl("shen-c", "BIFROST_SHEN_C"),
)}


class UnknownImpl(ValueError):
    pass


def selected() -> Impl:
    name = os.environ.get(SETTING, "") or DEFAULT_IMPL
    try:
        return IMPLS[name]
    except KeyError:
        raise UnknownImpl(f"{SETTING}={name!r} is not one of {', '.join(IMPLS)}") from None


def sha256_file(path: str | os.PathLike[str]) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def support_sha256(impl: Impl, binary: str) -> tuple[tuple[str, str], ...]:
    """Digests of the files ``binary`` loads, keyed by their name in the runtime
    home; raises FileNotFoundError when one is missing."""
    base = Path(binary).resolve().parent
    out = []
    for relative in impl.support:
        path = (base / relative).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"{impl.name} support file {path} is missing")
        out.append((relative.rsplit("/lib/shen-scheme/", 1)[-1], sha256_file(path)))
    return tuple(out)


def identity_sha256(binary_sha256: str, support: tuple[tuple[str, str], ...]) -> str:
    """The runtime's digest: the executable's own for a single-file runtime,
    else one digest over the executable and its sorted support files."""
    if not support:
        return binary_sha256
    lines = [f"binary {binary_sha256}"] + [f"{name} {digest}" for name, digest in sorted(support)]
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def child_env(impl: Impl, binary: str, base: Mapping[str, str] | None = None) -> dict[str, str]:
    env = {k: v for k, v in (os.environ if base is None else base).items() if k not in SCRUBBED_ENV}
    env[impl.env] = binary
    return env


def bifrost_argv(bifrost: str, impl: Impl, driver: str | os.PathLike[str]) -> list[str]:
    return [bifrost, "run", "--impl", impl.name, "--raw", str(driver)]


def direct_argv(binary: str, driver: str | os.PathLike[str]) -> list[str]:
    """What every one of the adapters runs for a script (``{bin} script {file}``)."""
    return [binary, "script", str(driver)]


def invocation(impl: Impl) -> list[str]:
    return ["bifrost", "run", "--impl", impl.name, "--raw", "<driver.shen>"]


def runtime_record(impl: Impl, binary: str) -> dict[str, object]:
    """The ``runtime`` object of the operations evidence.  For shen-go it is
    exactly ``{"shen": <sha256>}`` as before; other runtimes add their name
    and their support files, and ``shen`` is their identity digest."""
    binary_sha = sha256_file(binary)
    if impl.name == DEFAULT_IMPL:
        return {"shen": binary_sha}
    support = support_sha256(impl, binary)
    record: dict[str, object] = {"impl": impl.name, "shen": identity_sha256(binary_sha, support)}
    if support:
        record["binary"] = binary_sha
        record["support"] = dict(support)
    return record


__all__ = ["DEFAULT_IMPL", "IMPLS", "Impl", "SCRUBBED_ENV", "SETTING", "UnknownImpl", "bifrost_argv",
           "child_env", "direct_argv", "identity_sha256", "invocation", "runtime_record", "selected",
           "sha256_file", "support_sha256"]
