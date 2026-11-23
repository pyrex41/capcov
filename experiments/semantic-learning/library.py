"""Pilot: does witness specialization beat filtering in a tiny rewrite grammar?"""
import json
from identify import MODELS_BY_NAME, predict

TRAIN = ('aa', 'bbb')
HELD_OUT = ('aabb', 'baab', 'abbba')


def rewrite(rule, history, repeat_emits):
    if rule == 'keep' or (rule == 'guarded' and repeat_emits):
        return history
    return ''.join(j for i, j in enumerate(history) if i == 0 or history[i - 1] != j)


def main():
    # Capability probe supplied equally to all arms, before candidate selection.
    # This is an empirical feature, not a proof for arbitrary initial states.
    feature = {m: predict(m, 'aa') != predict(m, 'a') for m in MODELS_BY_NAME}

    def assess(rule, histories):
        mismatches, calls = [], 0
        for model in MODELS_BY_NAME:
            for history in histories:
                replacement = rewrite(rule, history, feature[model])
                calls += len(replacement)
                if predict(model, history) != predict(model, replacement):
                    mismatches.append({'model': model, 'history': history, 'replacement': replacement})
        return {'mismatches': mismatches, 'rewritten_calls': calls}

    # Each evidence-using policy may assess at most three rules. The filter
    # sees the same grammar as feedback: don't manufacture an advantage by
    # withholding the useful guard from its baseline.
    costs = {'collapse': 1, 'guarded': 2, 'keep': 0}  # grammar tokens, not bytes
    order = sorted(costs, key=lambda r: costs[r] + sum(len(rewrite(r, h, feature[m]))
                   for h in TRAIN for m in MODELS_BY_NAME))
    training = {r: assess(r, TRAIN) for r in order}
    fixed = next(r for r in order if not training[r]['mismatches'])
    witnesses = training['collapse']['mismatches']
    feedback = 'collapse'
    if witnesses:
        feedback = ('guarded' if all(feature[w['model']] for w in witnesses) else 'keep')
        if training[feedback]['mismatches']:
            feedback = 'keep'
    selection = {'compression': order[0], 'filter': fixed, 'feedback': feedback}
    report = {'format': 'capcov-library-pilot-v1', 'contract': 'ordered emissions only',
              'repeat_emits_probe': feature, 'rule_costs': costs, 'training': training,
              'selection': selection, 'held_out': {a: assess(r, HELD_OUT) for a, r in selection.items()}}
    print(json.dumps(report, indent=2))
    if selection != {'compression': 'collapse', 'filter': 'guarded', 'feedback': 'guarded'}:
        raise SystemExit('unexpected selection; inspect training results')


if __name__ == '__main__':
    main()
