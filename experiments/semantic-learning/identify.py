"""Finite-hypothesis identification control, not unrestricted model induction."""
import json
from functools import lru_cache

from calibrate import CALL, INITIAL, MODELS, evaluate, json_state

MODELS_BY_NAME = ('outbox.ops', 'outbox-intended.ops')
TRAIN = ('a', 'ab', 'aa')
TEST = ('aba', 'abba', 'baab')  # withheld interleavings, two pending jobs


@lru_cache(None)
def step(model, encoded_state, job):
    receipt = evaluate((MODELS / model).read_text(),
                       [dict(CALL, state=json.loads(encoded_state), args={'id': job})])
    result = receipt['results'][0]
    if len(result['admissible']) != 1:
        raise RuntimeError('expected one committed successor')
    _, rows, effects, _ = result['admissible'][0]
    return json.dumps(json_state(rows), sort_keys=True), [e for e in effects if e[0] == 'emit']


def predict(model, history):
    state = json.dumps([dict(INITIAL[0], key=j, fields={'status': 'pending', 'payload': j})
                        for j in 'ab'], sort_keys=True)
    emissions = []
    for job in history:
        state, effects = step(model, state, job)
        emissions.extend(effects)
    return emissions


def trial(target, challenge):
    observed = predict(target, challenge)
    survivors = [m for m in MODELS_BY_NAME if predict(m, challenge) == observed]
    # No arbitrary tie-break: ambiguous hypotheses must agree before predicting.
    scores = {}
    for h in TEST:
        predictions = [predict(m, h) for m in survivors]
        scores[h] = ('abstain' if any(p != predictions[0] for p in predictions)
                     else 'correct' if predictions[0] == predict(target, h) else 'wrong')
    return {'target': target, 'challenge': challenge, 'survivors': survivors, 'held_out': scores}


def main():
    active = next(h for h in TRAIN if predict(MODELS_BY_NAME[0], h) != predict(MODELS_BY_NAME[1], h))
    # Enumerating all three passive selections gives the exact uniform baseline.
    runs = [trial(m, h) for m in MODELS_BY_NAME for h in TRAIN]
    print(json.dumps({'format': 'capcov-finite-identification-v1', 'active_choice': active,
                      'observation': 'ordered emissions only', 'trials': runs}, indent=2))
    if active != 'aa' or any(set(r['held_out'].values()) !=
                             ({'correct'} if r['challenge'] == active else {'abstain'}) for r in runs):
        raise SystemExit('finite hypothesis calibration failed')


if __name__ == '__main__':
    main()
