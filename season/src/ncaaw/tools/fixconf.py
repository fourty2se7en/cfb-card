import json
W='/home/claude/runs16/ncaaw/w/'
M={r['key']:r for r in json.load(open('/home/claude/runs16/ncaaw/rt/m_ncaaw.json'))['rules']}
P=json.load(open(W+'post16/picks.json'))
for p in P:
    d=p['data']
    if not d.get('shadow'): continue
    r=M[d['rule']]; t=r['tiers'][d['tier']]; re=t.get('real') or {}
    lab=r.get('label',d['rule'])
    if re.get('w') is None and re.get('l') is None: why='no status record yet'
    elif t.get('pending_on'): why=f"status record {re['w']}-{re['l']} {re['u']:+.2f}u, {t['pending_on'][0].lower()+t['pending_on'][1:]}"
    else: why=f"status record red, {re['w']}-{re['l']} {re['u']:+.2f}u"
    c=f"{lab} {d['tier']} tier is turned off ({why}), so this fit is logged as a would-be pick."
    if 'The card pick in this game' in d.get('conflict',''): c+=' The card pick in this game'+d['conflict'].split('The card pick in this game')[1]
    d['conflict']=c; json.dump(d,open(f"{W}post16/p_{p['id']}.json",'w'))
json.dump(P,open(W+'post16/picks.json','w')); print('ok')
