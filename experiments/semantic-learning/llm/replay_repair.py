"""Re-score stored repair hypotheses against Shen. No provider calls or keys."""
import itertools
import json
from hashlib import sha256

from trial import ALPH, HERE, TEST, oracle, predict


def verify():
    report = json.loads((HERE / 'repair-result.json').read_text())
    if sha256((HERE / 'luna-jev-result.json').read_bytes()).hexdigest() != report['parent_sha256']:
        raise ValueError('parent transcript changed')
    label, identity = oracle()
    if identity != report['identity']:
        raise ValueError('oracle identity changed')
    short = [h for n in range(1, 5) for h in itertools.product(ALPH, repeat=n)]
    for row in report['trials']:
        for field, histories in [('short_340', short), ('held_out_96', TEST)]:
            for candidate, stored in row[field].items():
                expr = row['proposals'][int(candidate[1:])]['expr']
                actual = sum(predict(expr, h) == label(h) for h in histories)
                if actual != stored:
                    raise ValueError(f'{field}/{candidate}: replay {actual} != receipt {stored}')
    print('Parent, oracle identity, and recorded candidate scores match.')


if __name__ == '__main__': verify()
