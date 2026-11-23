"""Blind proposal/choice trial. Replay is authoritative, never the selector."""
import json
import os
from urllib.request import Request, urlopen

from trial import HERE, INSTRUCTIONS, POOL, SEED, TEST, learn, oracle, predict

LUNA = 'openai-codex/gpt-6-luna'
ENDPOINT = 'https://api.typesafe.ai/v1/systemone'


def choose(candidates, observations):
    body = {'model': 'jev-latest', 'state': {'observations': observations, 'hypotheses': candidates},
            'questions': {'hypothesis': {'type': 'choice', 'instructions':
                'Choose the simplest plausible behavioral law most likely to predict unseen histories. Each observation starts from reset. Only known-consistent candidates are offered.',
                'criteria': {k: v['concept'] for k, v in candidates.items()}}}}
    req = Request(ENDPOINT, data=json.dumps(body).encode(), headers={'Content-Type':'application/json',
                  'Authorization':'Bearer '+os.environ['JEV_API_KEY']})
    with urlopen(req, timeout=60) as response:
        answer = json.load(response)['answers']['hypothesis']
    if answer['choice'] not in candidates: raise ValueError('out-of-set selection')
    return answer


def main():
    label, identity = oracle()
    train = list(SEED)
    report = dict(proposer=LUNA, selector='jev-latest', identity=identity, held_out=len(TEST), rounds=[])
    path = HERE/'luna-jev-result.json'
    save = lambda: path.write_text(json.dumps(report, indent=2)+'\n')
    for _ in range(5):
        observations = [dict(h=h,bits=label(h)) for h in train]
        prompt = INSTRUCTIONS + '\nInstead of one hypothesis, return {"candidates":[...]} with four distinct hypotheses in your preferred order, each with concept and expr. Observations: '+json.dumps(observations)
        proposals = learn(prompt, LUNA)['candidates']
        candidates = {}
        for i, p in enumerate(proposals):
            try:
                if all(predict(p['expr'],h)==label(h) for h in train): candidates[f'h{i}']=p
            except (TypeError, IndexError, KeyError, ValueError): pass
        row = dict(prompt=prompt,proposals=proposals, eligible=list(candidates)); report['rounds'].append(row); save()
        if not candidates: break
        if len(candidates)>1:
            row['jev']=choose(candidates,observations); winner=row['jev']['choice']
        else: winner=next(iter(candidates))  # forced, not a Jev judgment
        row['selected']=winner
        row['held_out_by_candidate']={k:sum(predict(p['expr'],h)==label(h) for h in TEST) for k,p in candidates.items()}
        w=next((h for h in POOL if predict(candidates[winner]['expr'],h)!=label(h)),None)
        row['witness']=w; save()
        print(winner,row['held_out_by_candidate'],flush=True)
        if w is None: break
        train.append(w)


if __name__=='__main__': main()
