"""Post-pilot scoped replication on a new, explicitly targeted path corpus."""
import json
import experiment as e
from suites import B,P,R,UNIT

# Fixed before asking for the second pair of repairs. Include accepted paths
# too, so rejecting everything containing a colon cannot pass.
PROBES=[[B,P,['publish','s',[[p,'b']],None,{}],R] for p in ('1:test','é:x','_:foo')]
TEST=[[B,P,['publish','child',[[p,'b']],'s',{'keep':True}],['read','child'],R]
      for p in ('9:abc','😀:ok','!:','\n:abc','xx:ok','😀z:foo','folder/x:y','name','7','x::y','::x','./8:k')]


def main(replay=False):
    witnesses=[e.minimize(w) for w in e.differences('initial',PROBES)]
    report={'design':'targeted after inspection of pilot; not a blind new domain','witnesses':witnesses,'scores':{}}
    for arm in (() if replay else ('path-unit','path-feedback')):
        base=json.loads((e.D/'unit-input.json').read_text())['prompt']
        prompt=base if arm=='path-unit' else base+'\nReduced distinguishing workflows from native reference vs candidate: '+json.dumps(witnesses)
        # Same provider, isolation, decoding, candidate, and one repair call per arm.
        e.sample(arm,prompt)
    for arm in ('initial','path-unit','path-feedback'):
        report['scores'][arm]={}
        for name,hs in [('unit',UNIT),('targeted',TEST),('old_holdout',e.HOLDOUT)]:
            misses=e.differences(arm,hs); report['scores'][arm][name]=dict(passed=len(hs)-len(misses),total=len(hs),misses=misses)
    (e.D/'path-result.json').write_text(json.dumps(report,indent=2)+'\n')
    print({a:{k:v['passed'] for k,v in s.items()} for a,s in report['scores'].items()})


if __name__=='__main__':
    import sys
    if sys.argv[1:] not in (['replay'], ['sample']): raise SystemExit('replay | sample')
    main(replay=sys.argv[1:] == ['replay'])
