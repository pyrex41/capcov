"""Transport for closed Shen Step programs and correlated first-order resumes.

The fragment deliberately accepts string-valued fields only. Domain codecs
must validate numeric/identifier/sentinel meanings at adapters. The type check
establishes phase/capability/continuation shape, not arbitrary domain invariants.
"""

import copy
import uuid

from capcov.operations.native import invoke, term
from capcov.operations.system import digest
from .registry import fields, names, require, text

LIBRARIES = ("kernel.shen", "behavior-step.shen")


def program_term(program):
    fields(program, {"format", "phase", "row", "operations", "nodes", "entry"})
    require(program["format"] == "capcov-step-program-v1", "unknown Step program")
    require(program["phase"] in {"route", "worker"}, "invalid phase")
    names(program["row"])
    text(program["entry"])
    require(isinstance(program["operations"], list) and len(program["operations"]) <= 128,
            "operation budget exceeded")
    require(isinstance(program["nodes"], list) and 0 < len(program["nodes"]) <= 256,
            "node budget exceeded")
    names([o.get("id") for o in program["operations"] if isinstance(o, dict)])
    names([n.get("id") for n in program["nodes"] if isinstance(n, dict)])
    ops, nodes = [], []
    for o in program["operations"]:
        fields(o, {"id", "kind", "inputs", "results"})
        require(o["kind"] in {"Ask", "Commit", "External"}, "invalid effect kind")
        names(o["inputs"])
        require(isinstance(o["results"], dict) and o["results"], "effect needs result alternatives")
        names(list(o["results"]))
        for fs in o["results"].values():
            names(fs)
        ops.append([o["id"], o["kind"], o["inputs"], [[k, v] for k, v in sorted(o["results"].items())]])
    for n in program["nodes"]:
        fields(n, {"id", "kind", "operation", "input", "next"})
        require(n["kind"] in {"Ask", "Commit", "External", "Done", "Failed"}, "invalid Step")
        require(isinstance(n["operation"], str), "invalid operation")
        require(isinstance(n["input"], dict) and isinstance(n["next"], dict), "invalid node fields")
        names(list(n["input"]))
        for expr in n["input"].values():
            require(isinstance(expr, list) and len(expr) == 2 and expr[0] in {"literal", "ref"}
                    and isinstance(expr[1], str) and len(expr[1]) <= 4096, "unsupported pure expression")
        names(list(n["next"]))
        for value in n["next"].values():
            text(value)
        nodes.append([n["id"], n["kind"], n["operation"], sorted(n["input"].items()), sorted(n["next"].items())])
    # Native transport supports lists, not host tuple values.
    nodes = [[i, k, o, [list(x) for x in ins], [list(x) for x in nxt]] for i, k, o, ins, nxt in nodes]
    return [program["phase"], program["row"], ops, nodes, program["entry"]]


def admit(program, *, timeout=60):
    p = program_term(program)
    accepted, identity = invoke("(bf.admit? " + term(p) + ")", LIBRARIES, timeout=timeout)
    require(accepted is True, "Shen rejected effect permissions, row or continuation closure")
    return {"format": "capcov-step-admission-v1", "program_sha256": digest(program),
            "checker": identity, "scope": "closed fragment phase, row and continuation typing"}


class Session:
    """Trusted host owns phase and cursor; clients supply only correlated results.

    Checkpoints are host-owned data, never unauthenticated client continuations.
    Restoring an outstanding effect requires reconciliation; next() does not
    silently dispatch it again.
    """

    def __init__(self, program, environment, *, timeout=60):
        self.program = copy.deepcopy(program)
        self.admission = admit(self.program, timeout=timeout)
        self.timeout = timeout
        self.env = self._environment(environment)
        self.pc = program["entry"]
        self.sequence = 0
        self.workflow = uuid.uuid4().hex
        self.pending = None
        self.finished = False
        self.history = []

    @staticmethod
    def _environment(value):
        require(isinstance(value, dict) and len(value) <= 256, "invalid environment")
        names(list(value))
        require(all(isinstance(x, str) and len(x) <= 4096 for x in value.values()), "environment fields must be strings")
        return copy.deepcopy(value)

    def _invoke(self, expression):
        result, identity = invoke(expression, LIBRARIES, timeout=self.timeout)
        require(identity == self.admission["checker"], "runtime or rule environment changed after admission")
        require(digest(self.program) == self.admission["program_sha256"], "program changed after admission")
        return result


    def advance(self):
        require(not self.finished and self.pending is None, "finished or outstanding effect requires a result")
        p = term(program_term(self.program))
        result = self._invoke("(bf.advance " + p + " " + term(self.pc) + " "
                              + term([list(x) for x in sorted(self.env.items())]) + ")")
        kind, operation, pairs = result
        request = {"workflow": self.workflow, "sequence": self.sequence,
                   "program_sha256": self.admission["program_sha256"],
                   "kind": kind, "operation": operation, "input": dict(pairs)}
        if kind in {"Done", "Failed"}:
            self.finished = True
        else:
            self.pending = copy.deepcopy(request)
        self.history.append({"step": copy.deepcopy(request)})
        return request

    def resume(self, response):
        fields(response, {"workflow", "sequence", "program_sha256", "outcome", "values"})
        require(self.pending is not None, "no outstanding effect")
        for key in ("workflow", "sequence", "program_sha256"):
            require(type(response[key]) is type(self.pending[key]) and response[key] == self.pending[key], "uncorrelated effect result")
        operation = next(o for o in self.program["operations"] if o["id"] == self.pending["operation"])
        require(response["outcome"] in operation["results"], "undeclared outcome")
        values = self._environment(response["values"])
        require(set(values) == set(operation["results"][response["outcome"]]), "effect result field mismatch")
        require(not any(k.startswith(("context.", "request.")) for k in values), "effect cannot overwrite trusted context or request")
        pc = self._invoke("(bf.resume " + term(program_term(self.program)) + " "
                          + term(self.pc) + " " + term(response["outcome"]) + ")")
        self.env.update(values)
        self.history.append({"result": copy.deepcopy(response)})
        self.pc, self.pending = pc, None
        self.sequence += 1

    def checkpoint(self):
        return {"program_sha256": self.admission["program_sha256"], "checker": self.admission["checker"],
                "workflow": self.workflow, "pc": self.pc, "env": copy.deepcopy(self.env),
                "sequence": self.sequence, "pending": copy.deepcopy(self.pending),
                "finished": self.finished, "history": copy.deepcopy(self.history)}

    @classmethod
    def restore(cls, program, checkpoint, *, timeout=60):
        fields(checkpoint, {"program_sha256", "checker", "workflow", "pc", "env", "sequence", "pending", "finished", "history"})
        result = cls(program, checkpoint["env"], timeout=timeout)
        require(result.admission["program_sha256"] == checkpoint["program_sha256"]
                and result.admission["checker"] == checkpoint["checker"], "checkpoint program/runtime mismatch")
        require(checkpoint["pc"] in {n["id"] for n in program["nodes"]}, "invalid checkpoint cursor")
        require(type(checkpoint["sequence"]) is int and checkpoint["sequence"] >= 0
                and type(checkpoint["finished"]) is bool, "invalid checkpoint state")
        for key in ("workflow", "pc", "env", "sequence", "pending", "finished", "history"):
            setattr(result, key, copy.deepcopy(checkpoint[key]))
        return result

def transcript(session):
    """Export a finished run at the semantic effect boundary, without host IDs."""
    require(session.finished, "cannot record an unfinished session")
    interactions = []
    for item in session.history:
        if "step" in item:
            step = item["step"]
            request = {k: copy.deepcopy(step[k]) for k in ("kind", "operation", "input")}
            if step["kind"] in {"Done", "Failed"}:
                final = request
            else:
                interactions.append({"request": request})
        else:
            interactions[-1]["result"] = {k: copy.deepcopy(item["result"][k]) for k in ("outcome", "values")}
    return {"format": "capcov-step-transcript-v1", "interactions": interactions, "final": final}


def replay(program, environment, recording, *, timeout=60):
    """Replay recorded replies only after matching each requested effect exactly.

    No adapters are invoked. This tests orchestration; stateful adapter and
    mixed-writer tests are separate obligations. Program identity may differ
    intentionally, but effect order, payloads, results and terminal output may not.
    """
    fields(recording, {"format", "interactions", "final"})
    require(recording["format"] == "capcov-step-transcript-v1", "invalid transcript")
    require(isinstance(recording["interactions"], list) and len(recording["interactions"]) <= 1024,
            "transcript budget exceeded")
    session = Session(program, environment, timeout=timeout)
    for interaction in recording["interactions"]:
        fields(interaction, {"request", "result"})
        step = session.advance()
        actual = {k: step[k] for k in ("kind", "operation", "input")}
        require(digest(actual) == digest(interaction["request"]), "replay effect request divergence")
        fields(interaction["result"], {"outcome", "values"})
        session.resume({k: step[k] for k in ("workflow", "sequence", "program_sha256")} | interaction["result"])
    final = session.advance()
    require(final["kind"] in {"Done", "Failed"}, "recording ended before handler")
    require(digest({k: final[k] for k in ("kind", "operation", "input")}) == digest(recording["final"]),
            "replay terminal divergence")
    return {"replayed": True, "effects": len(recording["interactions"]), "admission": session.admission}
