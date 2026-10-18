"""Gate G5 (docs/ir-specification.md, section 7): v1 output stays byte-identical.

Every v1 `.ops` fixture is run through the `evaluate` and `explore` command
line on fixed inputs (built from INPUTS below at test time; the goldens pin
them too, by the request digest and the recorded calls). The output must
equal, byte for byte, the golden JSON in fixtures/systems/g5. The goldens were
written by `--regenerate` at the R02 base commit, before any R02 code existed.
BASE_LIBRARIES, a constant here and not something a run writes, holds that
commit's engine digests: every golden must carry them, and `--regenerate`
refuses to run on any other engine, so an R02 PR cannot regenerate them.

Two values are excluded from the comparison, and only those: `libraries`
(the digests of the engine's own Shen sources, which an R02 PR changes by
definition) and `runtime` (the digests of the host's bifrost and shen
binaries). Both are replaced by a fixed marker on both sides; every other byte,
including the request digests, the model digest and every transition, effect
and alternative, is compared, and so is the process exit code.

Regenerate (base commit only):
    python -m tests.claim_semantics.test_v1_compatibility --regenerate 7f41822
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
from importlib import resources
import io
import itertools
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from capcov.operations.system import SYSTEM_LIBRARIES, V1_OUTCOMES

FIXTURE = Path(__file__).parent / "fixtures/systems"
G5 = FIXTURE / "g5"
MANIFEST = G5 / "manifest.json"
NATIVE = bool(shutil.which("bifrost") and os.environ.get("BIFROST_SHEN_GO"))
if os.environ.get("CAPCOV_SHEN_REQUIRED") and not NATIVE:
    raise RuntimeError("the v1 compatibility gate requires native Shen")


# sha256 of kernel.shen, system-types.shen and system.shen at 7f41822, the R02
# base: `git show 7f41822:src/capcov/operations/shen/<file> | sha256sum`.
BASE = "7f41822"
BASE_LIBRARIES = {
    "kernel.shen": "a6cb3eeb7755c030d413f65b5acedad53f86a64cf8cf6fb8cf468d59964c6480",
    "system-types.shen": "4ee4317089b40a5a0b4abbf9c4ebe59d4075f99f3c9519aa6483a39adea4eac6",
    "system.shen": "ded4508d579c588c6a1e7a25ec15fbabf1ac0e3e5868f50e2855aac3c298ac05",
}
EXPLORE_OUTCOMES = ("committed", "unknown")
EXCLUDED = "<excluded from G5: engine source or host binary digest>"


def row(t, k, **fields):
    return {"table": t, "key": k, "fields": fields}


JOB = [row("job", "j", status="pending", payload="hello")]
WALLETS = [row("wallet", "a", balance="10"), row("wallet", "b", balance="2")]
ACCOUNTS = [row("account", "a", name="Alice"), row("account", "b", name="Bob")]
ITEMS = [row("item", "x", status="open"), row("item", "y", status="closed")]

# Per fixture: states to evaluate in (the first is the exploration's initial
# state) and the finite argument domain of each command.
OUTBOX_DOMAINS = {
    "enqueue": {"id": ["j", "k"], "payload": ["hello"]},
    "send": {"id": ["j", "k"]},
    "ack": {"id": ["j", "k"]},
}
INPUTS = {
    "ledger.ops": {
        "states": [
            WALLETS,
            [
                row("wallet", "a", balance="7"),
                row("wallet", "b", balance="5"),
                row("transfer", "r", **{"from": "a", "to": "b", "amount": "3"}),
            ],
        ],
        "domains": {
            "transfer": {
                "from": ["a", "b"],
                "to": ["a", "b"],
                "amount": ["3", "20"],
                "request": ["r"],
            }
        },
    },
    "loop-completion.ops": {
        "states": [ITEMS, []],
        "domains": {"close-all": {}},
    },
    "loop-induction.ops": {
        "states": [ITEMS, []],
        "domains": {"close-all": {}},
    },
    "outbox.ops": {
        "states": [JOB, [row("job", "j", status="sent", payload="hello")]],
        "domains": OUTBOX_DOMAINS,
    },
    "outbox-intended.ops": {
        "states": [JOB, [row("job", "j", status="attempted", payload="hello")]],
        "domains": OUTBOX_DOMAINS,
    },
    "workspace.ops": {
        "states": [
            ACCOUNTS + [row("item", "i", owner="a", status="open", title="t")],
            ACCOUNTS + [row("item", "i", owner="a", status="closed", title="t")],
        ],
        "domains": {
            "create": {"actor": ["a", "b"], "id": ["i", "n"], "title": ["t"]},
            "rename": {"actor": ["a", "b"], "id": ["i"], "title": ["u"]},
            "close": {"actor": ["a", "b"], "id": ["i"]},
            "delete-account": {"actor": ["a", "b"]},
        },
    },
}
# Inputs that already exist beside the fixtures, run as further cases.
EXISTING = {
    "ledger.ops": [("evaluate", "ledger-requests.json")],
    "outbox.ops": [("explore", "outbox-campaign.json")],
    "outbox-intended.ops": [("explore", "outbox-campaign.json")],
}


def combos(domains):
    names = sorted(domains)
    return [
        dict(zip(names, values))
        for values in itertools.product(*(domains[n] for n in names))
    ]


def evaluate_input(spec):
    requests = []
    for state in spec["states"]:
        for command, domains in spec["domains"].items():
            for args in combos(domains):
                for outcome in V1_OUTCOMES:
                    base = {
                        "command": command,
                        "args": args,
                        "state": copy.deepcopy(state),
                        "outcome": outcome,
                    }
                    requests.append(base)
                    if outcome in ("unknown", "aborted"):
                        nothing = {"state": copy.deepcopy(state), "effects": []}
                        requests.append(dict(copy.deepcopy(base), observed=nothing))
    first = copy.deepcopy(requests[0])
    first["trace"] = {"state": first["state"], "effects": [], "steps": []}
    requests.append(first)
    return requests


def explore_input(spec):
    calls = [
        {"command": command, "args": args, "outcome": outcome}
        for command, domains in spec["domains"].items()
        for args in combos(domains)
        for outcome in EXPLORE_OUTCOMES
    ]
    return {
        "initial": copy.deepcopy(spec["states"][0]),
        "calls": calls,
        "depth": 2,
        "max_nodes": 4096,
    }


def cases():
    """(name, fixture, mode, input, golden path) of every G5 case.

    input is the input document, built from INPUTS or read from an existing
    fixture beside the .ops files.
    """
    found = []
    for fixture in sorted(INPUTS):
        stem = fixture[: -len(".ops")]
        for mode, build in (("evaluate", evaluate_input), ("explore", explore_input)):
            found.append(
                (
                    f"{stem}.{mode}",
                    fixture,
                    mode,
                    build(INPUTS[fixture]),
                    G5 / f"{stem}.{mode}.json",
                )
            )
        for mode, existing in EXISTING.get(fixture, []):
            other = existing[: -len(".json")]
            found.append(
                (
                    f"{stem}.{other}",
                    fixture,
                    mode,
                    json.loads((FIXTURE / existing).read_text()),
                    G5 / f"{stem}.{other}.json",
                )
            )
    return found


def live_libraries():
    """sha256 of the engine's Shen libraries as installed now."""
    root = resources.files("capcov.operations").joinpath("shen")
    return {
        n: hashlib.sha256(root.joinpath(n).read_bytes()).hexdigest()
        for n in SYSTEM_LIBRARIES
    }


def run_cli(fixture, mode, document):
    """(exit code, output bytes) of `python -m capcov.operations.system`."""
    from capcov.operations.system import main

    with tempfile.TemporaryDirectory(prefix="capcov-g5-") as tmp:
        out = Path(tmp) / "out.json"
        input_path = Path(tmp) / "input.json"
        input_path.write_text(json.dumps(document, indent=2) + "\n")
        with contextlib.redirect_stderr(io.StringIO()):
            code = main(
                [
                    mode,
                    "--spec",
                    str(FIXTURE / fixture),
                    "--input",
                    str(input_path),
                    "--out",
                    str(out),
                ]
            )
        return code, out.read_bytes() if out.exists() else b""


def environment_digests(document):
    """The excluded values: engine library digests and host binary digests."""
    holder = document.get("identity", document)
    return {"libraries": holder["libraries"], "runtime": holder["runtime"]}


def normalized(text: bytes) -> bytes:
    """The output with only `libraries` and `runtime` replaced, same formatting."""
    document = json.loads(text)
    holder = document.get("identity", document)
    holder["libraries"] = EXCLUDED
    holder["runtime"] = EXCLUDED
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()


@unittest.skipUnless(NATIVE, "real pinned Shen runtime required")
class V1CompatibilityGateTest(unittest.TestCase):
    """Executor class "model": every v1 fixture's evaluate/explore JSON is unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text())

    def test_the_cases_are_exactly_the_manifest_and_cover_every_v1_fixture(self):
        names = [c[0] for c in cases()]
        self.assertEqual(names, sorted(self.manifest["cases"]))
        fixtures = sorted(p.name for p in FIXTURE.glob("*.ops"))
        self.assertEqual(sorted(INPUTS), fixtures)
        for fixture in fixtures:
            modes = {c[2] for c in cases() if c[1] == fixture}
            self.assertEqual(modes, {"evaluate", "explore"}, fixture)

    def test_every_golden_comes_from_the_base_libraries(self):
        self.assertEqual(self.manifest["base"], BASE)
        self.assertEqual(self.manifest["libraries"], BASE_LIBRARIES)
        for name, _, _, _, golden in cases():
            with self.subTest(case=name):
                digests = environment_digests(json.loads(golden.read_bytes()))
                self.assertEqual(digests["libraries"], BASE_LIBRARIES)

    def test_the_goldens_pin_their_inputs(self):
        from capcov.operations.system import digest

        for name, _, mode, document, golden in cases():
            with self.subTest(case=name):
                recorded = json.loads(golden.read_bytes())
                if mode == "evaluate":
                    self.assertEqual(recorded["requests"], digest(document))
                else:
                    for key in ("initial", "calls", "depth", "schedule"):
                        self.assertEqual(recorded[key], document.get(key))

    def test_evaluate_and_explore_output_is_byte_identical(self):
        for name, fixture, mode, document, golden in cases():
            with self.subTest(case=name):
                code, output = run_cli(fixture, mode, document)
                self.assertTrue(output, f"{name}: no output, exit code {code}")
                self.assertEqual(code, self.manifest["cases"][name]["exit"])
                expected = golden.read_bytes()
                # Re-serializing reproduces both texts exactly, so replacing
                # the two excluded values loses nothing else: the rest is
                # compared byte for byte.
                for text in (output, expected):
                    reserialized = json.dumps(json.loads(text), indent=2, sort_keys=True)
                    self.assertEqual((reserialized + "\n").encode(), text)
                self.assertEqual(normalized(output), normalized(expected))


def regenerate(base: str) -> None:
    """Write the goldens and the manifest. Refused on any engine but the base's."""
    if base != BASE or live_libraries() != BASE_LIBRARIES:
        raise SystemExit(
            f"refused: goldens are written only by the engine of {BASE} "
            f"(BASE_LIBRARIES); this engine is {live_libraries()}"
        )
    G5.mkdir(exist_ok=True)
    manifest = {
        "_note": "Gate G5 goldens (docs/ir-specification.md section 7). Written by "
        "--regenerate at the base commit below, before any R02 code; "
        "libraries are that commit's engine digests.",
        "base": base,
        "libraries": None,
        "cases": {},
    }
    for name, fixture, mode, document, golden in cases():
        code, output = run_cli(fixture, mode, document)
        if not output:
            raise SystemExit(f"{name}: no output (exit {code})")
        golden.write_bytes(output)
        libraries = environment_digests(json.loads(output))["libraries"]
        if libraries != BASE_LIBRARIES:
            raise SystemExit("library digests changed during regeneration")
        manifest["libraries"] = libraries
        manifest["cases"][name] = {"exit": code}
        print(f"{name}: exit {code}, {len(output)} bytes")
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--regenerate":
        regenerate(sys.argv[2])
    else:
        unittest.main()
