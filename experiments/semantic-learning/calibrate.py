"""Calibrate workflow observation contracts against the two native Shen models."""
import json
from pathlib import Path

from capcov.operations.system import digest, evaluate, json_state

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / 'tests/claim_semantics/fixtures/systems'
INITIAL = [{'table': 'job', 'key': 'j', 'fields': {'status': 'pending', 'payload': 'hello'}}]
CALL = {'command': 'send', 'args': {'id': 'j'}, 'outcome': 'committed'}


def calibrate(name):
    source = (MODELS / name).read_text()
    state, trace, steps, observations = INITIAL, [], [], []
    identity = None
    for _ in range(2):
        request = dict(CALL, state=state)
        receipt = evaluate(source, [request])
        current = {k: receipt[k] for k in ('model', 'libraries', 'runtime', 'fuel')}
        if identity is not None and current != identity:
            raise RuntimeError('executor or model changed during calibration')
        identity = current
        result = receipt['results'][0]
        if len(result['admissible']) != 1 or result['transition'][0] == 'rejected':
            raise RuntimeError('expected a single successful committed outcome')
        alt = result['admissible'][0]
        state = json_state(alt[1])
        # Database writes are observed through final state, not as deliveries.
        trace = trace + [effect for effect in alt[2] if effect[:1] == ['emit']]
        observations.append({'result': 'ok', 'state': state, 'effects': trace})
        steps.append({'request': request, 'receipt': receipt})
    once, twice = observations
    return {'fixture': name, 'identity': identity, 'steps': steps,
            'once': once, 'twice': twice, 'state_only_match': once['state'] == twice['state'],
            'workflow_match': once == twice}


def main():
    runs = [calibrate(name) for name in ('outbox.ops', 'outbox-intended.ops')]
    report = {'format': 'capcov-learning-calibration-v1', 'basis': 'native-model-execution',
              'assumptions': ['single pending job', 'committed calls only',
                              'workflow returns ok; intermediate responses hidden'], 'runs': runs}
    print(json.dumps(report, indent=2))
    expected = [(True, False, [1, 2]), (True, True, [1, 1])]
    actual = [(r['state_only_match'], r['workflow_match'],
               [len(r[k]['effects']) for k in ('once', 'twice')]) for r in runs]
    if actual != expected:
        raise SystemExit(f'calibration mismatch: {actual}; report {digest(report)}')


if __name__ == '__main__':
    main()
