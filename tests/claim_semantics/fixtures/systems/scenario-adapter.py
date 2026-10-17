"""Synthetic independently written stateful application, with an explicit mutant.

No capcov imports or expected results: this is an observation producer.
"""
import copy
import json
import sys


def run(request, mutant=False):
    state = copy.deepcopy(request["initial"])
    observations = []
    for step in request["steps"]:
        call, choice = step["call"], step["choice"]
        effects = []
        if call["outcome"] == "committed" or call["outcome"] == "unknown" and choice == "1":
            job = next(r for r in state if r["table"] == "job" and r["key"] == call["args"]["id"])
            if call["command"] == "send" and job["fields"]["status"] == "pending":
                effects.append(["emit", "delivery-attempt", job["fields"]["payload"]])
                if mutant:
                    effects.append(["emit", "delivery-attempt", job["fields"]["payload"]])
            elif call["command"] == "ack":
                job["fields"]["status"] = "sent"
                effects.append(["put", "job", job["key"], "status", "sent"])
        observations.append({"state": copy.deepcopy(state), "effects": effects})
    return {"protocol": request["protocol"], "choices": [s["choice"] for s in request["steps"]],
            "controls": ["commit-outcome", "in-memory-state"], "observations": observations}


if __name__ == "__main__":
    print(json.dumps(run(json.load(sys.stdin), "--mutant" in sys.argv)))
