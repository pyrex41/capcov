"""Frozen single-target LLM induction trial. No model-generated code execution."""
import itertools
import json
import random
import subprocess
import tempfile
from pathlib import Path

from capcov.operations.system import evaluate, json_state

HERE = Path(__file__).resolve().parent
MODEL = 'openai-codex/gpt-6.2-astra'
INSTRUCTIONS = '''Infer an executable behavioral concept for a hidden deterministic device. Each input event is a pair of strings. For each event predict one bit: does it signal? A history starts from reset. Return only JSON {"concept":"your explanation", "expr": E}. Invent the expression yourself. The generic history-query language is:
"x","y": current pair's first and second fields. "px","py": fields of the record bound inside a selection. null: missing. ["field",record,0 or 1]: project a field (null for missing). ["last",sequence] or ["first",sequence]: record or null. "past": sequence of earlier input pairs, in order. ["filter",sequence,predicate]: select records, binding px,py for predicate. ["eq",a,b], ["not",a], ["and",a,b], ["or",a,b], true, false. Top expression must produce a boolean. Prefer simple laws consistent with observations. You cannot query the device directly. Examples list {h:input history, bits:observed bits}.'''
ALPH = list(itertools.product('ab', '01'))
SEED = [(ALPH[0],), (ALPH[0], ALPH[0]), (ALPH[0], ALPH[3])]
POOL = [h for n in (1, 2, 3, 4) for h in itertools.product(ALPH, repeat=n) if h not in SEED]
rng = random.Random(7919)
TEST = [tuple(rng.choices(ALPH, k=n)) for n in range(5, 11) for _ in range(16)]


def oracle():
    req = [dict(state=[dict(table='cell', key=k, fields={'value':v}) for k,v in zip('ab',s)],
                command='tick', args=dict(x=x,y=y), outcome='committed')
           for s in itertools.product('-01', repeat=2) for x,y in ALPH]
    receipt = evaluate((HERE/'target.ops').read_text(), req)
    table = {}
    for q,r in zip(req,receipt['results'], strict=True):
        alt, = r['admissible']
        rows = sorted(json_state(alt[1]), key=lambda row:row['key'])
        table[tuple(i['fields']['value'] for i in q['state']),tuple(q['args'].values())] = (
            tuple(i['fields']['value'] for i in rows), any(e[0]=='emit' for e in alt[2]))
    def label(h):
        s, bits = ('-','-'), []
        for p in h:
            s,b = table[s,p]; bits.append(int(b))
        return bits
    return label, {k:receipt[k] for k in ('runtime','model','libraries','requests')}


def interp(e,h,p=None):
    if isinstance(e,str):
        return {'past':h[:-1], 'x':h[-1][0], 'y':h[-1][1], 'px':p and p[0], 'py':p and p[1]}[e]
    if not isinstance(e,list): return e
    op,*args=e
    if op=='filter': return tuple(i for i in interp(args[0],h,p) if interp(args[1],h,i))
    v=[interp(a,h,p) for a in args]
    if op=='field': return None if v[0] is None else v[0][v[1]]
    if op in ('first','last'): return v[0][0 if op=='first' else -1] if v[0] else None
    if op=='eq': return v[0]==v[1]
    if op=='not': return not v[0]
    if op=='and': return v[0] and v[1]
    if op=='or': return v[0] or v[1]
    raise ValueError(op)


def predict(e,h):
    bits=[interp(e,h[:i]) for i in range(1,len(h)+1)]
    if not all(type(b) is bool for b in bits): raise ValueError('nonboolean prediction')
    return list(map(int,bits))


def learn(prompt, model=MODEL):
    with tempfile.TemporaryDirectory() as tmp:
        raw=subprocess.check_output(['pi','-p','--model',model,'--no-session','--no-tools','--no-mcp',
            '--no-extensions','--no-skills','--no-context-files','--no-prompt-templates','--system-prompt',
            'You are a behavioral model induction engine. Respond only with JSON.',prompt], cwd=tmp,text=True,timeout=120)
    return json.loads(raw.strip().removeprefix('```json').removesuffix('```').strip())


def main():
    label,identity=oracle()
    def ex(h): return {'h':h,'bits':label(h)}
    prompt=INSTRUCTIONS+'\n'+json.dumps(list(map(ex,SEED)))
    first=learn(prompt)
    report=dict(model=MODEL, identity=identity,seed=7919, held_out=len(TEST), rounds=[])
    def record(arm,answer,p):
        e=answer['expr']; misses=[h for h in TEST if predict(e,h)!=label(h)]
        report['rounds'].append(dict(arm=arm,prompt=p,answer=answer,held_out_pass=len(TEST)-len(misses),first_miss=next(iter(misses),None)))
        (HERE/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    record('initial',first,prompt)
    answer=first; p=prompt
    for i in range(3):
        e=answer['expr']; w=next((h for h in POOL if predict(e,h)!=label(h)),None)
        if w is None: break
        prefix=p+'\nYour previous answer: '+json.dumps(answer)+'\nAdditional observation: '
        p=prefix+json.dumps(ex(w)); answer=learn(p); record('counterexample',answer,p)
        control=prefix+json.dumps(ex(random.Random(100+i).choice([h for h in POOL if len(h)==len(w)])))
        record('matched_random_from_same_parent',learn(control),control)
    print([(r['arm'],r['held_out_pass']) for r in report['rounds']])


if __name__=='__main__': main()
