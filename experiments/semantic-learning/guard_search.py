"""Bounded witness-guided guard discovery; run from the documented Shen shell."""
import itertools
import json
import random
import sqlite3
from functools import lru_cache

from identify import MODELS_BY_NAME, predict

PROBES = ('a', 'b', 'ab', 'aa', 'aba')
TRAIN = ('aa', 'bbb')
TEST = ('aabbaa', 'baabba', 'abbbaba')
BUDGET = 4
WORLDS = ('repeat', 'once', 'mixed')


@lru_cache(None)
def adapter(world, history):
    """Independent SQLite implementation. Mixed deduplicates a but not b."""
    db = sqlite3.connect(':memory:')
    try:
        db.executescript('create table seen(job text primary key); create table delivery(job text);')
        for job in history:
            with db:
                fresh = db.execute('insert or ignore into seen values (?)', (job,)).rowcount
                if fresh or world == 'repeat' or (world == 'mixed' and job == 'b'):
                    db.execute('insert into delivery values (?)', (job,))
        return tuple(row[0] for row in db.execute('select job from delivery order by rowid'))
    finally:
        db.close()


def grammar():
    # Generic predicates over counts from fixed black-box probes. No named
    # deduplication flag or fixture identity is available to a guard.
    atoms = [(i, op, n) for i in range(len(PROBES)) for op in ('=', '!=') for n in range(4)]
    return [(a,) for a in atoms] + list(itertools.combinations(atoms, 2))


def enabled(rule, counts):
    return all((counts[i] == n) == (op == '=') for i, op, n in rule)


def rewrite(h, yes):
    return ''.join(k for i, k in enumerate(h) if not yes or not i or h[i-1] != k)


def discover(order, features, mode, observe):
    seen, witnesses, checks = set(), {}, []
    scans = 0
    for rule in order:
        scans += 1
        sig = tuple(enabled(rule, f) for f in features)
        if not any(sig):  # no compression on any training workflow
            continue
        if mode == 'signature-filter' and sig in seen:
            continue
        seen.add(sig)
        if mode == 'feedback' and any(sig[i] for i in witnesses):
            continue  # same rewrite on the exact failed input
        failures = [(i, h) for i in range(len(features)) for h in TRAIN
                    if observe(i, h) != observe(i, rewrite(h, sig[i]))]
        checks.append({'rule': rule, 'failures': failures})
        if not failures:
            return rule, checks, scans
        witnesses.update(failures)
        if len(checks) == BUDGET:
            break
    return None, checks, scans


def main():
    @lru_cache(None)
    def observe(i, h):
        return tuple(e[2] for e in predict(MODELS_BY_NAME[i], h))

    features = [tuple(len(observe(i, h)) for h in PROBES) for i in range(2)]
    transfer = [tuple(len(adapter(w, h)) for h in PROBES) for w in WORLDS]
    # Positive control: on these histories the independent pure policies must
    # agree with native outputs. Mixed is deliberately outside the training class.
    for i, w in enumerate(WORLDS[:2]):
        for h in PROBES + TRAIN + TEST:
            if observe(i, h) != adapter(w, h):
                raise RuntimeError(f'adapter/model disagreement: {w} {h}')
    rows = []
    for seed in range(32):
        order = grammar()
        random.Random(seed).shuffle(order)
        order.sort(key=len)  # complexity first, seeded tie breaks
        for mode in ('filter', 'signature-filter', 'feedback'):
            rule, checks, scans = discover(order, features, mode, observe)
            by_world = {}
            for w, f in zip(WORLDS, transfer):
                yes = rule is not None and enabled(rule, f)
                by_world[w] = {'saved': sum(len(h)-len(rewrite(h, yes)) for h in TEST),
                               'mismatches': [h for h in TEST if adapter(w, h) != adapter(w, rewrite(h, yes))]}
            # Post-hoc diagnostic, not part of discovery: bind the probe's
            # focal key to the key whose retry is being removed.
            local = {k: tuple(len(adapter('mixed', h if k == 'a' else h.translate(str.maketrans('ab', 'ba'))))
                              for h in PROBES) for k in 'ab'}
            local_runs = []
            for h in TEST:
                rewritten = ''.join(k for i, k in enumerate(h) if not (i and k == h[i-1] and
                                    rule is not None and enabled(rule, local[k])))
                local_runs.append({'history': h, 'rewrite': rewritten,
                                   'match': adapter('mixed', h) == adapter('mixed', rewritten)})
            rows.append(dict(seed=seed, mode=mode, selected=rule, checks=checks, scanned=scans,
                             transfer=by_world, mixed_key_local_diagnostic=local_runs))
    summary = {m: {'selected': sum(r['selected'] is not None for r in rows if r['mode'] == m),
                   'mixed_unsafe_selections': sum(bool(r['transfer']['mixed']['mismatches']) for r in rows if r['mode'] == m),
                   'candidate_checks': sum(len(r['checks']) for r in rows if r['mode'] == m),
                   'predicates_scanned': sum(r['scanned'] for r in rows if r['mode'] == m)}
               for m in ('filter', 'signature-filter', 'feedback')}
    print(json.dumps(dict(format='guard-search-v1', budget=BUDGET, features=features, transfer_features=transfer,
                          train=TRAIN, held_out=TEST, probes=PROBES, summary=summary, trials=rows), separators=(',', ':')))


if __name__ == '__main__':
    main()
