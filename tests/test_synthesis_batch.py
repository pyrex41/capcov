import json, subprocess

def test_batch_cli_rejects_contradictions_and_bounds(tmp_path):
    doc = {"operations": {"a": {"family": "docs", "examples": [{"input": {"x": True}, "output": True}, {"input": {"x": False}, "output": False}]}, "bad": {"family": "docs", "examples": [{"input": {"x": True}, "output": True}, {"input": {"x": True}, "output": False}]}}}
    source = tmp_path / "in.json"; out = tmp_path / "out.json"; source.write_text(json.dumps(doc))
    subprocess.run([".venv/bin/python", "-m", "capcov", "synthesize-batch", str(source), "--out", str(out)], check=True)
    report = json.loads(out.read_text()); assert report["included_operations"] == 1; assert report["excluded_operations"] == 1
    assert report["families"][0]["invention_success"] is False
