"""Signal scoring, same rules as render.picks(), applied to a rebuilt game record (engine.build_all).
Returns per game: side signals (with points), puck line rows, totals signals, the card's pick, and grading fields."""
import math
from build_data import ip, dec, novig_home, ok
from engine import LAST, WEIGHTS, FUT, tier

def imp(o): return 100/(o+100) if o > 0 else -o/(-o+100)

def open_check(g):
    """ML open counts only when Action Network and DraftKings (ESPN) agree: no-vig home within 3 points. Returns the average."""
    dk = g.get('dk')
    if not dk or not dk.get('open'): return None
    a1, h1 = g['an']['mlo']; a2, h2 = dk['open']['ml']
    if not (ok(a1) and ok(h1) and ok(a2) and ok(h2)): return None
    p1, p2 = novig_home(a1, h1), novig_home(a2, h2)
    return (p1 + p2)/2 if abs(p1 - p2) <= 0.03 else None

def tot_open_check(g):
    """Total open counts only when Action Network and DraftKings opened the same line."""
    dk = g.get('dk')
    if not dk or not dk.get('open'): return None
    t1, t2 = g['an']['tot_open'], dk['open']['tot']
    return t1 if (t1 is not None and t1 == t2) else None

def score(g):
    a, h = g['a'], g['h']; A, H = g['A'], g['H']; an = g['an']
    mla, mlh = g['sb']['mlc']
    if not (ok(mla) and ok(mlh)) or (mla == -110 and mlh == -110 and g['sb']['mlo'][0] is not None and abs(novig_home(*g['sb']['mlo']) - 0.5) > 0.04):
        return None  # no trustworthy closing moneyline
    S = []  # (signal, side, pts)
    def add(sig, side, pts): S.append((sig, side, pts))
    for name, side in (g['sh_ml'] or {}).items(): add('AN ' + name, side, WEIGHTS[name])
    ba, ma = an['bets'], an['money']
    if ba is not None and ma is not None:
        if ma - ba >= 10: add('Money vs tickets', 'A', 1)
        elif ba - ma >= 10: add('Money vs tickets', 'H', 1)
        if ba <= 35: add('Fade the public', 'A', 1)
        elif ba >= 65: add('Fade the public', 'H', 1)
    pHo = open_check(g); pHn = novig_home(mla, mlh)
    rlm = None
    if pHo is not None and ba is not None and abs(pHn - pHo) >= 0.02:
        tw = 'H' if pHn > pHo else 'A'; tb = (100-ba) if tw == 'H' else ba
        if tb < 50: add('Reverse line movement', tw, 2); rlm = tw
    estH = 0.4*g['pH_model'] + 0.6*pHn
    ms = 'H' if estH > 0.5 else 'A'
    add('Card projection', ms, 1)
    if g['svA'] - g['svH'] >= 0.004: add('Goalie edge', 'A', 1)
    elif g['svH'] - g['svA'] >= 0.004: add('Goalie edge', 'H', 1)
    for loss, side_for in ((g['lossA'], 'H'), (g['lossH'], 'A')):
        if loss >= 0.08: add('Key absence', side_for, 2 if loss >= 0.15 else 1)
    if A['rest'] == 0 and H['rest'] > 0: add('Rest edge', 'H', 1)
    if H['rest'] == 0 and A['rest'] > 0: add('Rest edge', 'A', 1)
    def vp(r):
        w, l, o = r; n = w+l+o
        return ((2*w+o)/(2*n) if n else 0.5)*n/(n+10) + 0.5*10/(n+10)
    vgap = vp(H['home']) - vp(A['road'])
    if abs(vgap) >= 0.15: add('Home/road split', 'H' if vgap > 0 else 'A', 2 if abs(vgap) >= 0.30 else 1)
    add('Home ice', 'H', 1)
    for sd, T in (('A', A), ('H', H)):
        c, k = T['strk']
        if c == 'W' and k >= 3: add('Hot streak', sd, 1)
        if c in ('L', 'OT') and k >= 3: add('Cold streak', 'H' if sd == 'A' else 'A', 1)
    def l10p(r):
        w, l, o = r; return (2*w+o)/max(2*(w+l+o), 1)
    if A['gp'] and H['gp']:
        fa, fh = l10p(A['l10']), l10p(H['l10'])
        if abs(fa-fh) >= 0.20: add('Recent form', 'A' if fa > fh else 'H', 1)
        gda, gdh = A['diff']/A['gp'], H['diff']/H['gp']
        if abs(gda-gdh) >= 0.6: add('Goal differential', 'A' if gda > gdh else 'H', 1)
    la_, lh_ = LAST[a][0], LAST[h][0]
    if abs(la_-lh_) >= 0.08: add('Track record', 'A' if la_ > lh_ else 'H', 1)
    for sd, nmx, T in (('A', a, A), ('H', h, H)):
        if not T['gp']: continue
        now_p, last_p = T['ppct'], LAST[nmx][0]
        if last_p - now_p >= 0.12 and last_p >= 0.58: add('Bounce-back', sd, 1)
        if now_p - last_p >= 0.15 and last_p <= 0.53: add('Regression watch', 'H' if sd == 'A' else 'A', 1)
    ca, ch = imp(FUT[a]), imp(FUT[h])
    if max(ca, ch)/min(ca, ch) >= 2: add('Roster strength', 'A' if ca > ch else 'H', 1)
    from build_data import DIVNAME
    da, dh = DIVNAME[g['div_a']], DIVNAME[g['div_h']]
    if da != dh:
        gap = g['div'][da] - g['div'][dh]
        pts = 2 if abs(gap) >= 0.10 else (1 if abs(gap) >= 0.05 else 0)
        if pts: add('Division strength', 'A' if gap > 0 else 'H', pts)
    sc = {'A': sum(p for s, sd, p in S if sd == 'A'), 'H': sum(p for s, sd, p in S if sd == 'H')}
    side = 'A' if sc['A'] > sc['H'] else ('H' if sc['H'] > sc['A'] else ms)
    other = 'H' if side == 'A' else 'A'
    conf_ml = any(s in ('AN Sharp Action', 'Reverse line movement') and sd == other for s, sd, p in S)
    # puck line
    plc = g['sb']['plc']
    res = dict(g=g, S=S, sc=sc, side=side, ml_lead=sc[side]-sc[other], ml_tier=tier(sc[side]-sc[other]), conf_ml=conf_ml,
               estH=estH, pHn=pHn, rlm=rlm, mla=mla, mlh=mlh)
    if plc and abs(plc['sp']) == 1.5 and ok(plc['a'][0]) and ok(plc['a'][1]):
        fav = 'A' if plc['sp'] < 0 else 'H'
        is_dog = side != fav
        p_fav = g['pA2'] if fav == 'A' else g['pH2']
        p_pl = 1 - p_fav if is_dog else p_fav
        pl_price = plc['a'][0] if side == 'A' else plc['a'][1]
        pl_sc, pl_ot = sc[side], sc[other]; P = []
        for name, v in (g['sh_pl'] or {}).items():
            if v == side: pl_sc += WEIGHTS[name]; P.append(('PL AN ' + name, 'mine'))
            else: pl_ot += WEIGHTS[name]; P.append(('PL AN ' + name, 'other'))
        pb0, pm0 = an['pl_bets'], an['pl_money']
        if pb0 is not None and pm0 is not None:
            pb = pb0 if side == 'A' else 100-pb0; pm = pm0 if side == 'A' else 100-pm0
            if pm - pb >= 10: pl_sc += 1; P.append(('PL money vs tickets', 'mine'))
            elif pb - pm >= 10: pl_ot += 1; P.append(('PL money vs tickets', 'other'))
            if pb <= 35: pl_sc += 1; P.append(('PL fade', 'mine'))
            elif pb >= 65: pl_ot += 1; P.append(('PL fade', 'other'))
        if is_dog and p_pl >= 0.60: pl_sc += 1; P.append(('+1.5 cushion', 'mine'))
        if (not is_dog) and p_pl < 0.42: pl_ot += 2; P.append(('Needs 2-goal win', 'other'))
        pl_ok = is_dog or p_pl >= 0.38
        RANK = {'Strong': 3, 'Solid': 2, 'Thin': 1}
        ml_price = mla if side == 'A' else mlh
        pl_tier = tier(pl_sc - pl_ot)
        pay = lambda o: o/100 if o > 0 else 100/(-o)
        if not pl_ok: use_pl = False
        elif RANK[pl_tier] != RANK[res['ml_tier']]: use_pl = RANK[pl_tier] > RANK[res['ml_tier']]
        else: use_pl = pay(pl_price) > pay(ml_price)
        res.update(fav=fav, is_dog=is_dog, p_pl=p_pl, pl_price=pl_price, pl_lead=pl_sc-pl_ot, pl_tier=pl_tier, P=P, use_pl=use_pl, pl_ok=pl_ok)
    else:
        res.update(fav=('H' if mlh < mla else 'A'), use_pl=False, pl_price=None)
    # totals
    tc = g['sb']['tc']
    if tc and ok(tc['ou'][0]) and ok(tc['ou'][1]):
        line = tc['line']; T = []
        for name, v in (g['sh_tot'] or {}).items(): T.append(('AN ' + name, v, WEIGHTS[name]))
        ob, om = an['o_bets'], an['o_money']
        if ob is not None:
            if ob >= 75: T.append(('Fade the public', 'U', 1))
            elif ob <= 25: T.append(('Fade the public', 'O', 1))
            if om is not None:
                if om - ob >= 10: T.append(('Money vs tickets', 'O', 1))
                elif ob - om >= 10: T.append(('Money vs tickets', 'U', 1))
        topen = tot_open_check(g)
        if topen is not None and ob is not None and line < topen: T.append(('Total moved down', 'U', 2 if ob >= 50 else 1))
        d = g['lamT'] - line
        if abs(d) >= 0.25: T.append(('Card projection', 'O' if d > 0 else 'U', 1))
        A5, H5 = g['A']['last5'], g['H']['last5']
        if len(A5) == 5 and len(H5) == 5:
            l5 = (sum(A5) + sum(H5))/10
            if l5 >= line + 0.5: T.append(('Recent scoring', 'O', 1))
            elif l5 <= line - 0.5: T.append(('Recent scoring', 'U', 1))
        gsv = (g['svA'] + g['svH'])/2
        if gsv >= 0.891: T.append(('Goaltending', 'U', 1))
        elif gsv <= 0.884: T.append(('Goaltending', 'O', 1))
        tcs = {'O': sum(p for s, sd, p in T if sd == 'O'), 'U': sum(p for s, sd, p in T if sd == 'U')}
        tside = 'O' if tcs['O'] > tcs['U'] else ('U' if tcs['U'] > tcs['O'] else ('O' if d > 0 else 'U'))
        tot = g['ag'] + g['hg']
        res.update(T=T, tline=line, tside=tside, t_lead=tcs[tside]-tcs['U' if tside == 'O' else 'O'], tprice=tc['ou'], ttot=tot, topen=topen)
    return res
