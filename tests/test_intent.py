import json, subprocess, sys

def packet():
    return {"schema":"capcov/intent-packet/v1", "packet_id":"p1", "question":"which output is intended?", "evidence":[{"id":"php-1","status":"confirmed"},{"id":"go-1","status":"unknown"}], "cases":[{"id":"c1","input":{"x":True},"php_output":1,"go_output":2,"reference_output":1}], "alternatives":[{"id":"a","condition":"x"}]}

def test_adjudication_cannot_self_promote(tmp_path):
    p=tmp_path/"p.json"; r=tmp_path/"r.json"; o=tmp_path/"o.json"; p.write_text(json.dumps(packet())); r.write_text(json.dumps({"source_ids":["php-1"],"recommendation":{"c1":1},"binding":True}))
    subprocess.run([sys.executable,"-m","capcov","intent","adjudicate",str(p),str(r),"--out",str(o)],check=True)
    x=json.loads(o.read_text()); assert x["binding"] is False and x["classifications"][0]["classification"]=="unknown"

def test_prompt_and_explicit_acceptance(tmp_path):
    p=tmp_path/"p.json"; r=tmp_path/"r.json"; a=tmp_path/"a.json"; o=tmp_path/"o.json"; p.write_text(json.dumps(packet())); r.write_text(json.dumps({"source_ids":["php-1"]})); a.write_text(json.dumps({"accepted":True,"packet_schema":"capcov/intent-packet/v1","packet_id":"p1","authority":"review-board","source_ids":["php-1"],"intended_outputs":{"c1":1}}))
    subprocess.run([sys.executable,"-m","capcov","intent","prompt",str(p),"--out",str(tmp_path/"prompt.json")],check=True)
    subprocess.run([sys.executable,"-m","capcov","intent","adjudicate",str(p),str(r),"--accepted",str(a),"--out",str(o)],check=True)
    assert json.loads(o.read_text())["binding"] is True
