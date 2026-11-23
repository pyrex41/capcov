"""Frozen, disjoint workflows. No target-generated outputs used as expectations."""
B=['blob','b','café']; P=['publish','s',[['x','b']],None,{}]; R=['read','s']
UNIT=[[B],[B,P,R],[R],[B,['publish','s',[['z','absent']],None,{}]]]
CHALLENGE=[[B,P,['publish','s',[[p,'b'] for p in paths],None,meta],R]
           for paths in (['./x'],['x','./x'],['d','d/f'],['a','a-','a/b'],['C:f'])
           for meta in ({'2':1,'11':0}, {'cost':1e-7}, {'\ue000':'é','😀':'x'})]
HOLDOUT=[]
for paths in (['data//x'],['x','x/.'],['d','d/x'],['o','o!','o/f'],['C:foo'],['valid']):
    for meta in ({'nested':[{'8':'eight','70':'70'}]}, {'rate':[1e-6,1e-8]}, {'labels':{'\uf001':1,'😁':2}}, None):
        HOLDOUT.append([B,P,['publish','child',[[p,'b'] for p in paths],'s',meta],['read','child'],R])
