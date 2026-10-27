"""One automatic evidence producer: pinned ShenCheck -> Vor -> generated TLA+.

No second protocol model, verdict UI, or acceptance of exported verification flags.
The upstream checked cohort is a finite protocol obligation, never refinement.
"""

import hashlib
import json
import platform
import shutil
import sys
import tempfile
import time
from importlib import resources
from pathlib import Path

from capcov.operations.process import run
from capcov.operations.system import digest
from .registry import fields, require, read_json, path

ENGINE = "shencheck-effects-v1"
MODES = ("healthy", "mutant-commit", "mutant-finish", "mutant-duplicate", "mutant-lost-work")
OPEN = {"general_protocol_proof": "OPEN", "liveness": "OPEN",
        "implementation_refinement": "OPEN", "translation_proof": "OPEN"}


def sha(filename):
    p = Path(filename)
    require(p.is_file() and p.stat().st_size <= 64 * 1024 * 1024, "missing or oversized engine artifact")
    return hashlib.sha256(p.read_bytes()).hexdigest()


def pins():
    return json.loads(resources.files(__package__).joinpath("shencheck-effects-pins.json").read_text())


def tool_identity(toolchain):
    require(toolchain is not None, "ShenCheck obligation requires --toolchain; no fallback")
    fields(toolchain, {"format", "shencheck_root", "vor_root", "tlc_jar", "java"}, {"runtime_root"})
    require(toolchain["format"] == "capcov-behavior-toolchain-v1", "unsupported toolchain configuration")
    require(all(isinstance(v, str) and Path(v).is_absolute() for k, v in toolchain.items() if k != "format"),
            "toolchain locations must be absolute trusted operator paths")
    p = pins()
    sources = {}
    for project in ("shencheck", "vor"):
        root = Path(toolchain[project + "_root"])
        sources[project] = {n: sha(path(root, n)) for n in p[project]["files"]}
        require(sources[project] == p[project]["files"], project + " source differs from reviewed integration pin")
    require(sha(toolchain["tlc_jar"]) == p["tlc_sha256"], "ShenCheck TLC pin mismatch")
    return {"pin_sha256": digest(p), "sources": sources,
            "tlc_sha256": p["tlc_sha256"], "java_sha256": sha(toolchain["java"]),
            "python_sha256": sha(sys.executable), "locations_sha256": digest(toolchain)}


def model_sources(toolchain, manifest):
    require(isinstance(manifest, dict) and 0 < len(manifest) <= 128, "missing Vör source/runtime identity")
    root = Path(toolchain["vor_root"]).resolve()
    runtime = Path(toolchain.get("runtime_root", root / ".tools")).resolve()
    result = {}
    for name, expected in manifest.items():
        # Only .tools entries may resolve into an explicitly selected runtime root.
        if isinstance(name, str) and name.startswith(".tools/"):
            candidate = path(runtime, name[len(".tools/"):])
        else:
            candidate = path(root, name)
        result[name] = sha(candidate)
        require(result[name] == expected, "stale Vör runtime/model: " + name)
    required = {"examples/effects-protocol.shen", "vor.shen", "scripts/shen", "scripts/host.sh",
                "scripts/export-effects-model", "toolchain.lock.json", ".tools/t-star-pr117.shen"}
    suffix = platform.system() + "-" + platform.machine()
    required |= {".tools/host-path-" + suffix, ".tools/host-identity-" + suffix}
    require(required <= manifest.keys(), "incomplete Vör source/runtime manifest")
    require(any(n.endswith("/bin/shen-scheme") for n in manifest), "missing executed Shen binary identity")
    return result


def artifact_manifest(directory):
    root = Path(directory)
    files = sorted(p for p in root.rglob("*") if p.is_file())
    require(len(files) <= 4096, "engine evidence file budget exceeded")
    require(sum(p.stat().st_size for p in files) <= 128 * 1024 * 1024, "engine evidence byte budget exceeded")
    return {str(p.relative_to(root)): sha(path(root, str(p.relative_to(root)))) for p in files}


def assess(directory, toolchain, *, require_history=False):
    """Revalidate the actual cohort and all retained artifacts in the same gate."""
    root = Path(directory)
    identity = tool_identity(toolchain)
    report = read_json(root / "results.json")
    require(report.get("schema") == "effects-qualification-v1" and report.get("status") == "FINITE_PROTOCOL_VALIDATED",
            "ShenCheck protocol is not qualified (UNKNOWN/FAILED/REJECTED never pass)")
    require(report.get("claims") == OPEN, "finite evidence cannot close general/refinement obligations")
    require(report.get("vor_tests") == {"exit_code": 0, "reason": None, "status": "TESTED"}, "Vör control tests did not pass")
    require(sha(root / "vor-tests.log") == report.get("vor_tests_log_sha256"), "Vör control log mismatch")
    cases = report.get("cases")
    require(isinstance(cases, list) and [c.get("mode") for c in cases] == list(MODES), "missing or duplicate required defect control")
    sources = model_sources(toolchain, report.get("model_sources"))
    expected_runner = {Path(n).name: h for n, h in pins()["shencheck"]["files"].items() if n.startswith("formal/effects/")}
    require(report.get("sources") == expected_runner, "unexpected ShenCheck runner modules")
    witnesses = []
    for c in cases:
        mode = c["mode"]
        wanted = "FINITE_MODEL_CHECKED" if mode == "healthy" else "VIOLATION"
        result_file = root / mode / "results.json"
        require(c.get("expected") == wanted and c.get("actual") == wanted and c.get("matched") is True,
                "required defect control did not match")
        require(sha(result_file) == c.get("result_sha256"), "cohort result digest mismatch")
        result = read_json(result_file)
        require(result.get("schema") == "effects-validation-v1" and result.get("status") == wanted
                and result.get("mode") == mode and result.get("claims") == OPEN,
                "invalid finite validation result")
        require(result.get("model_sources") == sources and result.get("sources") == expected_runner,
                "source identity drift inside cohort")
        require(result.get("tlc", {}).get("status") == wanted and result["tlc"].get("tool_sha256") == identity["tlc_sha256"]
                and result["tlc"].get("java_sha256") == identity["java_sha256"], "TLC identity/status mismatch")
        artifacts = result.get("artifacts")
        require(isinstance(artifacts, dict) and {"model.json", "Effects.tla", "Effects.cfg", "names.json", "tlc.log"} <= artifacts.keys(),
                "missing generated protocol evidence")
        for name, expected in artifacts.items():
            require(sha(path(root / mode, name)) == expected, "modified protocol artifact")
        if mode == "healthy":
            require(result.get("reference", {}).get("status") == "FINITE_REFERENCE_CHECKED"
                    and result["reference"].get("states", 0) > 0, "reference exploration incomplete")
        else:
            reference = result.get("reference", {})
            prop = result["tlc"].get("violated_property")
            require(reference.get("status") == "VIOLATION" and reference.get("trace")
                    and prop in result.get("properties", {}) and prop in reference.get("violated_properties", [])
                    and c.get("violated_property") == prop, "unrechecked or wrong-property counterexample")
            witnesses.append({"mode": mode, "property": prop, "trace": str(Path(mode) / "results.json")})
    history = None
    if require_history:
        observed = read_json(root / "history/results.json")
        require(observed.get("schema") == "effects-validation-v1" and observed.get("status") == "FINITE_MODEL_CHECKED"
                and observed.get("history", {}).get("status") == "TRACE_REFERENCE_CHECKED"
                and observed["history"].get("steps", 0) > 0, "target history incomplete or incompatible")
        require(observed.get("model_sources") == sources and observed.get("sources") == expected_runner,
                "target history checked under a different source identity")
        healthy = read_json(root / "healthy/results.json")
        require(observed.get("model_sha256") == healthy["model_sha256"], "target history model mismatch")
        for name, expected in observed.get("artifacts", {}).items():
            require(sha(path(root / "history", name)) == expected, "modified target history evidence")
        require(sha(root / "observed-history.json") == sha(root / "history/history.json"), "observer history substitution")
        history = {"status": "TRACE_REFERENCE_CHECKED", "steps": observed["history"]["steps"],
                   "artifact": "history/results.json", "model_sha256": observed["model_sha256"]}
    return {"engine": ENGINE, "status": "FINITE_PROTOCOL_VALIDATED", "identity": identity,
            "model_sources": sources, "artifacts": artifact_manifest(root),
            "counterexamples": witnesses, "history": history, "open_claims": OPEN}


def execute(directory, toolchain, *, timeout, observer=None, cwd=None):
    """Stage checksum-pinned ShenCheck code, run its cohort, then admit evidence."""
    identity = tool_identity(toolchain)
    deadline = time.monotonic() + timeout
    def remaining(limit):
        seconds = min(limit, deadline - time.monotonic())
        require(seconds > 0, "ShenCheck obligation deadline exhausted")
        return seconds
    output = Path(directory).resolve()
    require(not output.exists(), "engine output already exists")
    with tempfile.TemporaryDirectory(prefix="capcov-shencheck-") as tmp:
        stage = Path(tmp)
        for name, expected in pins()["shencheck"]["files"].items():
            destination = stage / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path(toolchain["shencheck_root"], name), destination)
            require(sha(destination) == expected, "ShenCheck source changed during staging")
        command = [sys.executable, "-I", str(stage / "formal/effects/qualify.py"),
                   "--vor-root", toolchain["vor_root"], "--tlc-jar", toolchain["tlc_jar"],
                   "--java", toolchain["java"], "--out", str(output)]
        if "runtime_root" in toolchain:
            command += ["--runtime-root", toolchain["runtime_root"]]
        code, stdout, stderr = run(command, timeout=remaining(timeout))
        if code == 0 and observer:
            code, out, err = run(observer + [str(output / "healthy/model.json"), str(output / "observed-history.json")],
                                 cwd=cwd, timeout=remaining(120))
            stdout, stderr = stdout + out, stderr + err
            if code == 0:
                history_command = [sys.executable, "-I", str(stage / "formal/effects/run.py"),
                    "--vor-root", toolchain["vor_root"], "--tlc-jar", toolchain["tlc_jar"], "--java", toolchain["java"],
                    "--out", str(output / "history"), "--history", str(output / "observed-history.json")]
                if "runtime_root" in toolchain:
                    history_command += ["--runtime-root", toolchain["runtime_root"]]
                code, out, err = run(history_command, timeout=remaining(180))
                stdout, stderr = stdout + out, stderr + err
    if code != 0:
        return code, stdout, stderr, None
    result = assess(output, toolchain, require_history=bool(observer))
    require(result["identity"] == identity, "toolchain changed during cohort")
    return code, stdout, stderr, result
