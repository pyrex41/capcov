import json
from capcov.synthesis import learn_library, synthesize


def _task(i, heldout):
    body = {"op": "eq", "args": [{"var": "x"}, {"lit": True}]}
    return {"id": f"t{i}", "program": {"op": "and", "args": [body, body]},
            "examples": [{"input": {"x": True}, "output": True}],
            "heldout_examples": [{"input": {"x": heldout}, "output": heldout}]}


def test_invention_is_used_and_compresses():
    tasks = [_task(i, bool(i % 2)) for i in range(4)]
    library = learn_library(tasks)
    assert library["inventions"]
    result = synthesize(tasks, library)
    assert all(row["used_invented"] for row in result["results"])
    assert result["counts"]["candidate_pass"] == 4


def test_negative_heldout_control_does_not_pass():
    tasks = [_task(i, True) for i in range(4)]
    tasks[0]["heldout_examples"] = [{"input": {"x": False}, "output": True}]
    library = learn_library(tasks)
    result = synthesize(tasks, library)
    assert not result["results"][0]["candidate_heldout_pass"]
    json.dumps(result)
