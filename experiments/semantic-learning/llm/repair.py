"""Paired retrospective repair trial; diagnostic rivals never enter learner prompts."""
import itertools
import json
from hashlib import sha256

from luna_jev import LUNA, choose
from trial import ALPH, HERE, INSTRUCTIONS, SEED, TEST, learn, oracle, predict


def rivals():
    # Compare either field (or the pair) to first/last matching prior record,
    # selected by either field, the whole pair, or no key; also novelty laws.
    laws = {}
    for key, cols in [('global',()), ('x',(0,)), ('y',(1,)), ('xy',(0,1))]:
        slots = lambda a, cols=cols: tuple(a[i] for i in cols)
        for which in (0,-1):
            for field in ((0,), (1,), (0,1)):
                def signal(h, slots=slots, which=which, field=field):
                    past = [p for p in h[:-1] if slots(p)==slots(h[-1])]
                    return not past or any(past[which][i]!=h[-1][i] for i in field)
                laws[f'{key}:{which}:{field}'] = signal
    laws['always'] = lambda h: True
    laws['never'] = lambda h: False
    return laws


def main():
    previous = (HERE/'luna-jev-result.json').read_bytes()
    old = json.loads(previous)['rounds']
    train = list(SEED) + [tuple(map(tuple,r['witness'])) for r in old if r.get('witness')]
    failed = old[-1]['proposals'][0]
    label, identity = oracle()
    laws = rivals()
    def survivors(histories):
        return [n for n,law in laws.items() if all([int(law(h[:i])) for i in range(1,len(h)+1)]==label(h) for h in histories)]
    extended=train.copy(); pool=[h for n in range(1,5) for h in itertools.product(ALPH, repeat=n)]
    while True:
        before=survivors(extended)
        # Exclude already rejected laws before choosing the best additional probe.
        def left(h):
            bits=label(h)
            return sum(all(laws[n](h[:i])==b for i,b in enumerate(bits,1)) for n in before)
        probe=min(pool,key=lambda h:(left(h),len(h)))
        if left(probe)==len(before): break
        extended.append(probe)
    report={'parent_sha256':sha256(previous).hexdigest(),'identity':identity,'diagnostic_laws':list(laws),
            'surviving_original':survivors(train),'surviving_extended':survivors(extended),
            'added':extended[len(train):],'target_model':LUNA,'trials':[]}
    path=HERE/'repair-result.json'
    suites=[('original',train)] + ([('contrast',extended)] if extended!=train else [])
    for suite,hs in suites:
        obs=[dict(h=h,bits=label(h)) for h in hs]
        for repair in (False,True):
            prompt=INSTRUCTIONS+'\nReturn {"candidates":[...]} with four behaviorally distinct executable hypotheses, in preferred order. Check each against every observation. Observations: '+json.dumps(obs)
            if repair:
                prompt+='\nRepair your prior failed executable hypothesis: '+json.dumps(failed)+'\nTrace comparison: '+json.dumps([dict(h=h,predicted=predict(failed['expr'],h),observed=label(h)) for h in hs if predict(failed['expr'],h)!=label(h)])
            eligible={}; errors={}
            try: proposals=learn(prompt,LUNA)['candidates']
            except json.JSONDecodeError as err:
                proposals=[]; errors['response']={'reason':str(err),'raw':err.doc}
            for i,p in enumerate(proposals):
                try:
                    if all(predict(p['expr'],h)==label(h) for h in hs): eligible[f'h{i}']=p
                except (TypeError,IndexError,KeyError,ValueError) as err: errors[i]=type(err).__name__
            choice=choose(eligible,obs) if len(eligible)>1 else None
            winner=choice['choice'] if choice else next(iter(eligible),None)
            scores={k:sum(predict(p['expr'],h)==label(h) for h in TEST) for k,p in eligible.items()}
            bounded={k:sum(predict(p['expr'],h)==label(h) for h in pool) for k,p in eligible.items()}
            report['trials'].append(dict(suite=suite,repair=repair,prompt=prompt,proposals=proposals,errors=errors,jev=choice,winner=winner,held_out_96=scores,short_340=bounded))
            path.write_text(json.dumps(report,indent=2)+'\n'); print(suite,repair,winner,scores,flush=True)


if __name__=='__main__': main()
