import json, subprocess
from pathlib import Path
from capcov.go_emit import emit

def test_emit_go_compiles_and_runs(tmp_path):
    report = {"library": {"library": {"invented_000": {"params": ["x"], "body": {"op": "not", "args": [{"var": "x"}]}}}},
              "evaluation": {"selected_candidate": {"op": "call", "name": "invented_000", "args": [{"var": "flag"}]}}}
    out = tmp_path / "synth.go"
    emit(report, out)
    (tmp_path / "go.mod").write_text("module example\n\ngo 1.20\n")
    (tmp_path / "main.go").write_text('package main\nimport "fmt"\nfunc main(){fmt.Println(Synthesized(true), Synthesized(false))}\n')
    subprocess.run(["gofmt", "-w", str(out), str(tmp_path / "main.go")], check=True)
    result = subprocess.run(["go", "run", "."], cwd=tmp_path, check=True, capture_output=True, text=True)
    assert result.stdout == "false true\n"

def test_emit_rejects_unknown_variable(tmp_path):
    report = {"library": {}, "evaluation": {"selected_candidate": {"var": "not-present"}}}
    try:
        emit(report, tmp_path / "x.go")
    except ValueError as error:
        assert "unknown variable" in str(error)
    else:
        raise AssertionError("expected invalid variable")
