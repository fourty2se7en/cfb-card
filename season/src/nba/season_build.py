"""Season dataset for the daily re-check: every regular season game played, as pickrules inputs, from
  season/espn_odds.txt   ESPN core odds (DraftKings open and close) + finals
  season/an_odds.txt     Action Network scoreboard: book 30 open, consensus splits, closing median of individual books
  season/ratings.txt     NBA.com team ratings, last season (L row) and this season through each date (DateTo)
  season/card_inputs.json  the card's morning Action Network PRO codes and injury adjustments by date
Moneylines are cleaned (quotes under 100 or over 5000 dropped) and medians are taken in decimal odds before this file sees them."""
import json, pathlib
from collections import defaultdict
from datetime import date as _D
D = pathlib.Path(__file__).parent; S_ = D/'season'
MAP = {'NY':'NYK','SA':'SAS','UTAH':'UTA','NO':'NOP','GS':'GSW','WSH':'WAS'}
fix = lambda t: MAP.get(t, t)
num = lambda x: float(x) if x not in ('', None) else None
okml = lambda a: a is not None and 100 <= abs(a) <= 5000
DIV = dict(ATL='SE',CHA='SE',MIA='SE',ORL='SE',WAS='SE',BOS='AT',BKN='AT',NYK='AT',PHI='AT',TOR='AT',CHI='CE',CLE='CE',DET='CE',IND='CE',MIL='CE',
           DEN='NW',MIN='NW',OKC='NW',POR='NW',UTA='NW',GSW='PA',LAC='PA',LAL='PA',PHX='PA',SAC='PA',DAL='SW',HOU='SW',MEM='SW',NOP='SW',SAS='SW')
DIV_LAST = dict(NW=2.72, SW=-0.62, AT=1.67, CE=-1.77, SE=-0.44, PA=-1.55)   # 2025-26 avg margin vs other divisions
LASTW = dict(ATL=46,BOS=56,BKN=20,CHA=44,CHI=31,CLE=52,DAL=26,DEN=54,DET=60,GSW=37,HOU=52,IND=19,LAC=42,LAL=53,MEM=25,MIA=43,MIL=32,MIN=49,NOP=26,NYK=53,
             OKC=64,ORL=45,PHI=45,PHX=45,POR=42,SAC=22,SAS=62,TOR=46,UTA=22,WAS=17)

def load():
    ESP = {}
    for ln in (S_/'espn_odds.txt').read_text().strip().splitlines():
        f = ln.split('|'); k = (f[0], fix(f[1]), fix(f[2]))
        _, op, cl = f[6].split('~')
        ESP[k] = dict(as_=int(f[3]), hs=int(f[4]), open=[num(x) for x in op.split(',')], close=[num(x) for x in cl.split(',')])
    AN = {}
    for ln in (S_/'an_odds.txt').read_text().strip().splitlines():
        f = ln.split('|'); k = (f[0], f[1], f[2])
        parts = {x[0]: x[1:] for x in f[6].split(';')}
        pr = lambda s: tuple(int(v) for v in s.split('/'))
        blk = {x.split('~')[0]: [num(y) for y in x.split('~')[1].split(',')] for x in f[7:]}
        med = blk[[b for b in blk if b.startswith('MED')][0]]
        AN[k] = dict(as_=int(f[3]), hs=int(f[4]), sp_h=pr(parts['S']), ml_h=pr(parts['M']), ov=pr(parts['O']), open=blk['O'], close=med)
    RT = {}
    for ln in (S_/'ratings.txt').read_text().strip().splitlines():
        k, v = ln.split('|', 1)
        RT[k] = {x.split(',')[0]: [float(y) for y in x.split(',')[1:]] for x in v.split(';')}
    CI = json.loads((S_/'card_inputs.json').read_text())
    CUP = {}
    for ln in (D/'standings_raw.txt').read_text().splitlines():
        if ln.startswith('CUP '):
            for x in ln[4:].split(','): t, o = x.split(); CUP[t] = int(o)
    return ESP, AN, RT, CI, CUP

def dn(s): return _D(int(s[:4]), int(s[5:7]), int(s[8:])).toordinal()

def build():
    ESP, AN, RT, CI, CUP = load()
    LAST = RT.pop('L')
    games = []
    for k, e in ESP.items():
        a_ = AN.get(k)
        if not a_ or (a_['as_'], a_['hs']) != (e['as_'], e['hs']): continue   # finals must agree between sources
        games.append(dict(d=k[0], a=k[1], h=k[2], as_=e['as_'], hs=e['hs'], E=e, A=a_))
    games.sort(key=lambda g: (g['d'], g['a']))
    hist = defaultdict(list)
    for g in games:
        hist[g['a']].append((g['d'], g['as_'], g['hs'], g['h'])); hist[g['h']].append((g['d'], g['hs'], g['as_'], g['a']))
    def state(t, d):
        H = [x for x in hist[t] if x[0] < d]; gp = len(H); w = sum(1 for x in H if x[1] > x[2])
        strk = ''
        if H:
            last = H[-1][1] > H[-1][2]; n = 0
            for x in reversed(H):
                if (x[1] > x[2]) == last: n += 1
                else: break
            strk = ('W' if last else 'L') + str(n)
        l10 = H[-10:]
        ppg = sum(x[1] for x in H)/gp if gp else 0; opp = sum(x[2] for x in H)/gp if gp else 0
        return dict(gp=gp, pct=w/gp if gp else 0, strk=strk, l10w=sum(1 for x in l10 if x[1] > x[2]), l10n=len(l10), diff=ppg-opp, ppg=ppg, oppg=opp,
                    rest=(dn(d) - dn(H[-1][0]) - 1) if H else 99)
    def ds(dv, d):
        n = m = 0
        for g in games:
            if g['d'] >= d: continue
            for t, o, pf, pa in ((g['a'], g['h'], g['as_'], g['hs']), (g['h'], g['a'], g['hs'], g['as_'])):
                if DIV[t] == dv and DIV[o] != dv: n += 1; m += pf - pa
        w = n/(n+60); return w*(m/n if n else 0) + (1-w)*DIV_LAST[dv]
    def rate(d, t):
        pd = _D.fromordinal(dn(d)-1); key = f"{pd.month:02d}/{pd.day:02d}/{pd.year}"
        n = RT.get(key, {}).get(t); l = LAST[t]
        if not n: return l[2], l[3], l[4]
        w = n[0]/(n[0]+12); return (1-w)*l[2]+w*n[1], (1-w)*l[3]+w*n[2], (1-w)*l[4]+w*n[3]
    out = []
    for g in games:
        a, h, d = g['a'], g['h'], g['d']
        A, H = state(a, d), state(h, d)
        oA, dA, pA = rate(d, a); oH, dH, pH = rate(d, h)
        pace = pA + pH - 100.3
        ptsA = pace*(oA+dH-115)/100 - 1.4; ptsH = pace*(oH+dA-115)/100 + 1.4
        if A['rest'] == 0: ptsA -= .75; ptsH += .75
        if H['rest'] == 0: ptsH -= .75; ptsA += .75
        ci = CI.get(d, {}); inj = ci.get('inj', {})
        for t in (a, h):
            if t in inj:
                if t == a: ptsA -= inj[t]/2; ptsH += inj[t]/2
                else: ptsH -= inj[t]/2; ptsA += inj[t]/2
        codes = ci.get('an', {}).get(f'{a}-{h}', {})
        c, o, ec, eo = g['A']['close'], g['A']['open'], g['E']['close'], g['E']['open']
        mla, mlh = c[6], c[7]
        if not (okml(mla) and okml(mlh)): continue
        inp = dict(a=a, h=h, ml_a=mla, ml_h=mlh, sp_a=-c[0], sp_pa=c[2] or -110, sp_ph=c[1] or -110, tot=c[3], tot_po=c[4] or -110, tot_pu=c[5] or -110,
                   open_sp_a=-o[0], open_tot=o[3], open_ml_a=o[6], open_ml_h=o[7],
                   src2=dict(sp_open_a=-eo[0], sp_now_a=-ec[0], tot_open=eo[3], tot_now=ec[3]),
                   ml_bets_a=100-g['A']['ml_h'][0], ml_money_a=100-g['A']['ml_h'][1], sp_bets_a=100-g['A']['sp_h'][0], sp_money_a=100-g['A']['sp_h'][1],
                   o_bets=g['A']['ov'][0], o_money=g['A']['ov'][1],
                   sig_ml=codes.get('sig_ml', {}), sig_sp=codes.get('sig_sp', {}), sig_tot=codes.get('sig_tot', {}),
                   margin=ptsH-ptsA, ptotal=ptsA+ptsH, pace=pace, sdm=12.5, sr=None,
                   stA=A, stH=H, restA=A['rest'], restH=H['rest'], inj={t: (inj[t], 'card injury adjustment') for t in (a, h) if t in inj},
                   dsA=ds(DIV[a], d), dsH=ds(DIV[h], d), same_div=DIV[a] == DIV[h], divA=DIV[a], divH=DIV[h],
                   lastA=LASTW[a]/82, lastH=LASTW[h]/82, cupA=CUP.get(a), cupH=CUP.get(h), lg_pace=100.3)
        out.append(dict(d=d, a=a, h=h, as_=g['as_'], hs=g['hs'], inp=inp, has_codes=bool(codes)))
    return out

if __name__ == '__main__':
    G = build(); print(len(G), 'games', sum(g['has_codes'] for g in G), 'with card PRO codes')
