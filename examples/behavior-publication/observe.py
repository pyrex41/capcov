"""Project an actual request commit/response prefix into Vör's effects model.

Only two boundaries are observed. Worker leases/fencing are deliberately absent:
this is finite prefix conformance, not worker refinement or a production observer.
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

from backend import Backend
from capcov.behaviors.target import Session

model_file, destination = map(Path, sys.argv[1:])
envelope = json.loads(model_file.read_text())
model = envelope['model']
variables = model[2]
expected = {'accepted','mutation','obligation','responded','lease','expired','effect','ack','completed','duplicate'}
assert set(variables) == expected
model_hash = hashlib.sha256(json.dumps(model, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
with tempfile.TemporaryDirectory() as tmp:
    store = Backend(Path(tmp) / 'db.sqlite')
    try:
        store.seed()
        def observe(responded=False):
            state = dict.fromkeys(variables, False)
            issue = store.db.execute('SELECT status,version,identifier FROM issue').fetchone()
            state['accepted'] = store.db.execute('SELECT count(*) FROM request').fetchone()[0] == 1
            state['mutation'] = issue == ('published', 1, 'ISSUE-i1')
            state['obligation'] = store.db.execute("SELECT count(*) FROM outbox WHERE state='pending'").fetchone()[0] == 1
            state['responded'] = responded
            return state
        history = {'schema': 'effects-history-v1', 'model_sha256': model_hash, 'initial': observe(), 'steps': []}
        program = json.loads(Path(__file__).with_name('route.json').read_text())
        session = Session(program, {'context.tenant':'tenant-a','context.principal':'alice',
            'request.issue':'i1','request.version':'0','request.id':'r1'})
        for _ in range(16):
            step = session.advance()
            if step['kind'] in {'Done','Failed'}:
                assert step['input'] == {'status':'200'}
                history['steps'].append({'action':'respond','observed':observe(True)})
                break
            outcome, values = store.effect(step)
            if step['kind'] == 'Commit':
                history['steps'].append({'action':'request-commit','observed':observe()})
            session.resume({k:step[k] for k in ('workflow','sequence','program_sha256')} | {'outcome':outcome,'values':values})
        else:
            raise RuntimeError('observer budget exhausted')
        with destination.open('x') as out:
            json.dump(history, out, sort_keys=True, separators=(',', ':'))
    finally:
        store.close()
