"""Generate independently with `generate ARM`; local executable replay with `score`."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from suites import UNIT, CHALLENGE, HOLDOUT

D=Path(__file__).resolve().parent
ROOT=D.parents[1]; CAS=ROOT/'src/capcov/cas.py'; MODEL='openai-codex/gpt-6.2-astra'
BASE='''Rewrite the complete source.py batch publication service in standard Node.js CommonJS. Return ONLY complete JavaScript source. Input stdin JSON list of histories, output JSON list of traces. Compatibility of results including exact canonical JSON strings and digests matters. The observable contract is sequential operations within each isolated history, no crashes or concurrent filesystem users. In-memory storage is fine. Inputs are valid JSON, paths/references strings, well formed commands. No dependencies, network, subprocesses, or filesystem except stdin. Here are the service and underlying library:\n'''


def traces(arm, hs):
    cmd=[sys.executable,str(D/'source.py')] if arm=='source' else ['node','--permission',str(D/(arm+'.cjs'))]
    p=subprocess.run(cmd,input=json.dumps(hs),text=True,capture_output=True,timeout=20,
                     env={'PATH':os.environ['PATH'],'PYTHONPATH':str(ROOT/'src')},check=True)
    out=json.loads(p.stdout)
    if len(out)!=len(hs) or any(len(h)!=len(t) for h,t in zip(hs,out)): raise ValueError('invalid trace size')
    return out


def differences(arm,hs):
    a,b=traces('source',hs),traces(arm,hs)
    return [dict(history=h,source=s,target=t) for h,s,t in zip(hs,a,b) if s!=t]


def minimize(w):
    h=w['history']; pos=next(i for i,(a,b) in enumerate(zip(w['source'],w['target'])) if a!=b)
    h=h[:pos+1]; end=h[-1]; kind=lambda x: tuple((list(t[-1])[0],t[-1].get('error')) for t in (x['source'],x['target']))
    mismatch=differences('initial',[h])[0]; signature=kind(mismatch)
    for i in reversed(range(len(h)-1)):
        test=h[:i]+h[i+1:]; diff=differences('initial',[test]);
        if diff and kind(diff[0])==signature and diff[0]['source'][-1]!=diff[0]['target'][-1]: h=test
    return differences('initial',[h])[0]


def generate(arm):
    prompt=BASE+(D/'source.py').read_text()+'\n'+CAS.read_text()
    if arm!='initial':
        prompt+='\nCurrent rewrite:\n'+(D/'initial.cjs').read_text()+'\nRepair it if necessary. Ordinary unit tests with source expectations:\n'+json.dumps(list(zip(UNIT,traces('source',UNIT))))
        if arm=='feedback':
            observed=[]
            for w in differences('initial',CHALLENGE):
                m=minimize(w)
                if m not in observed: observed.append(m)
                if len(observed)==3: break
            prompt+='\nReduced distinguishing workflows with old and new outputs:\n'+json.dumps(observed)
    sample(arm,prompt)


def sample(arm,prompt):
    with tempfile.TemporaryDirectory() as tmp:
        raw=subprocess.check_output(['pi','-p','--model',MODEL,'--no-session','--no-tools','--no-context-files','--no-mcp','--no-skills','--no-extensions','--no-prompt-templates','--system-prompt','Return only JavaScript code.',prompt],text=True,cwd=tmp,timeout=240)
    code=raw.strip(); code='\n'.join(code.splitlines()[1:-1]) if code.startswith('```') and code.endswith('```') else code
    (D/(arm+'.cjs')).write_text(code+'\n')
    (D/(arm+'-input.json')).write_text(json.dumps({'model':MODEL,'prompt':prompt},indent=2)+'\n')


def score():
    files=[CAS,D/'source.py',D/'experiment.py',D/'suites.py',*(D.glob('*.cjs'))]
    report={'files':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'node':subprocess.check_output(['node','--version'],text=True).strip(),'python':sys.version,'arms':{}}
    for arm in ('initial','unit','feedback'):
        report['arms'][arm]={}
        for name,hs in [('unit',UNIT),('challenge',CHALLENGE),('holdout',HOLDOUT)]:
            misses=differences(arm,hs); report['arms'][arm][name]=dict(passed=len(hs)-len(misses),total=len(hs),misses=misses)
    (D/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print({a:{s:v['passed'] for s,v in suites.items()} for a,suites in report['arms'].items()})


if __name__=='__main__':
    if sys.argv[1:] == ['score']: score()
    elif len(sys.argv)==3 and sys.argv[1]=='generate' and sys.argv[2] in ('initial','unit','feedback'): generate(sys.argv[2])
    else: raise SystemExit('score | generate {initial,unit,feedback}')
