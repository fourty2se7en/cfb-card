import json, glob, re, copy
from pathlib import Path
import rules as RU
HUB=Path('/home/claude/cfb/s8/hubL'); OUT=Path('/home/claude/cfb/s8/meta')
SIG=json.load(open('signals.json'))
def pay(r,p): return RU.payout(True if r=='win' else (False if r=='loss' else None), p or -110)
def rec(rows):
    w=sum(r['result']=='win' for r in rows); l=sum(r['result']=='loss' for r in rows); p=sum(r['result']=='push' for r in rows)
    return dict(w=w,l=l,p=p,u=round(sum(pay(r['result'],r.get('price')) for r in rows),2))
def L(div): return [json.load(open(f)) for f in glob.glob(str(HUB/'sports'/div/'picks'/'*.json'))]
rep={}
for div in ('fbs',):   # Nov 9 2026: FCS retired
    m=json.load(open(HUB/'meta'/f'{div}.json')); old={r['key']:r for r in m['rules']}
    RE=json.load(open(f'ruleeval_{div}.json')); RS=SIG['rules_'+div]
    l3=[p for p in RE['periods'] if p.startswith('Last 3')][0]
    led=L(div); new=[]; watch=[]; close=[]; sw=[]
    for r in m['rules']:
        if r['market']=='Prop': continue
        k=r['key']; R_=RS['total'][k] if k in RS['total'] else RS['side'][k]
        if k not in RE['rules']:   # rules the re-check does not cover (fbs_fav_vs_fcs): card ledger record only
            r=dict(r); r['on']=bool(R_['on']); r['tier']=R_.get('tier'); cr=rec([x for x in led if x.get('rule')==k and not x.get('shadow') and x['result'] in('win','loss','push')])
            r['season']=dict(w=cr['w'],l=cr['l'],p=cr['p'],u=cr['u']); r['card']=f"{cr['w']}-{cr['l']} {cr['u']:+.2f}u"; new.append(r); continue
        v=RE['rules'][k]['versions'][0]['rec']; s=v['Season']; mo=v.get('Nov')
        r=dict(r); was=r['on']; r['on']=bool(R_['on']); r['tier']=R_.get('tier')
        r['season']=dict(w=s['w'],l=s['l'],p=s['p'],u=s['units'])
        r['month']=dict(w=mo['w'],l=mo['l'],p=mo['p'],u=mo['units'],label='Nov') if mo and mo.get('n') else None
        r['every_game']=f"{s['w']}-{s['l']}"+(f"-{s['p']}" if s['p'] else '')+f" {s['units']:+.1f}u"
        L3=v[l3]; r['last_3_weeks']=f"{L3['w']}-{L3['l']} {L3['units']:+.1f}u" if L3['n'] else None
        cr=rec([x for x in led if x.get('rule')==k and not x.get('shadow') and x['result'] in('win','loss','push')])
        r['card']=f"{cr['w']}-{cr['l']}"+(f"-{cr['p']}" if cr['p'] else '')+f" {cr['u']:+.2f}u"
        if was and not r['on']:
            why=f"Nov {mo['w']}-{mo['l']} {mo['units']:+.1f}u" if mo and mo['n']>=5 and mo['units']<0 else f"season {s['w']}-{s['l']} {s['units']:+.1f}u"
            r['switched']=f"2026-11-08: off at season {s['w']}-{s['l']} {s['units']:+.1f}u, {why}"; sw.append(f"{r['label']} OFF ({why})")
        if not was and r['on']:
            r['switched']=f"2026-11-08: back on at season {s['units']:+.1f}u, Nov {mo['units'] if mo else 0:+.1f}u"; sw.append(f"{r['label']} ON")
        mu=r['month']['u'] if r['month'] else None; mn=(r['month']['w']+r['month']['l']) if r['month'] else 0
        if r['on']:
            if s['units']<1 or (mu is not None and mu<1): watch.append(f"{r['label']}: season {s['units']:+.1f}u, Nov {mo['w']}-{mo['l']} {mu:+.1f}u")
        else:
            need=[]
            if s['units']<0: need.append(-s['units'])
            if mu is not None and mn>=5 and mu<0: need.append(-mu)
            if need and max(need)<=1.5: close.append(f"{r['label']}: Nov {mo['w']}-{mo['l']} {mu:+.1f}u, season {s['units']:+.1f}u")
        r['back_on']='Back on when season and month (5+ picks) are both green.'
        new.append(r)
    if div=='fbs':
        rows=[x for x in led if x['market']=='Prop' and x['result'] in ('win','loss','push')]
        for st,sd in sorted({(x['stat'],x['side']) for x in rows}):
            rr=[x for x in rows if x['stat']==st and x['side']==sd]; s=rec(rr); mo=rec([x for x in rr if x['date']>='2026-11-01'])
            n=s['w']+s['l']; mn=mo['w']+mo['l']
            key=f"PROP_{re.sub('[^a-z]','',st)}_{sd}"; o=old.get(key,{})
            on=not (n>=20 and (s['u']<0 or (mn>=5 and mo['u']<0)))
            e=dict(key=key,keys=[],label=f"{st.capitalize()} · {sd}",market='Prop',desc=f"Every logged {st} {sd.lower()} prop (Play and tracking) in the hub ledger.",
                   on=on,season=s,month=dict(mo,label='Nov'),every_game=None,card=f"{s['w']}-{s['l']}"+(f"-{s['p']}" if s['p'] else '')+f" {s['u']:+.2f}u",
                   back_on='Back on when season and month (5+ picks) are both green.')
            if o.get('on',True) and not on: e['switched']=f"2026-11-08: off at season {s['w']}-{s['l']} {s['u']:+.2f}u, Nov {mo['u']:+.2f}u"; sw.append(f"{e['label']} props OFF")
            elif o and not o.get('on',True) and on: e['switched']=f"2026-11-08: back on"; sw.append(f"{e['label']} props ON")
            elif o.get('switched'): e['switched']=o['switched']
            if on and (s['u']<1 or (mn>=5 and mo['u']<1)): watch.append(f"{e['label']} props: season {s['w']}-{s['l']}-{s['p']} {s['u']:+.2f}u ({n} graded), Nov {mo['u']:+.2f}u")
            if not on and max(-s['u'],-mo['u'] if mn>=5 else 0)<=1.5: close.append(f"{e['label']} props: season {s['u']:+.2f}u, Nov {mo['u']:+.2f}u")
            new.append(e)
    m['rules']=new; m['updated']='2026-11-08'
    m['notes']=(f"Nov 8 Sunday re-check: {RE['games']} {div.upper()} games graded through week {RE['weeks'][1]}. "
                +('Switches: '+'; '.join(sw)+'. ' if sw else 'No switches. ')
                +('Watch: '+'; '.join(watch)+'. ' if watch else '')+('Close: '+'; '.join(close)+'.' if close else '')).strip()
    json.dump(m,open(OUT/f'{div}.json','w'),indent=1,ensure_ascii=False)
    json.dump(m,open(f'hub_meta_{div}.json','w'))
    rep[div]=dict(switches=sw,watch=watch,close=close)
print(json.dumps(rep,indent=1,ensure_ascii=False))
