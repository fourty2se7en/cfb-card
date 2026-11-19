import math, html, pathlib, json, datetime
from standings import panel as standings_panel
from badges import badge
from teams import URL
from model import build, be, amer, fmt, pois, p_ge, novig, wilson, NAMES

D = pathlib.Path(__file__).parent
games, LG = build()
LgS = LG['LgS']

COLORS = {  # light, dark
 'SJS':('#006d75','#3fc1c9'),'OTT':('#c8102e','#ff6b7d'),'NSH':('#b8860b','#ffc72c'),'BOS':('#8a6d00','#fcb514'),
 'NYR':('#0038a8','#6f9bff'),'TOR':('#00205b','#5d8dff'),'FLA':('#c8102e','#ff5a6e'),'PIT':('#7a6400','#fcb514'),
 'ANA':('#b9562a','#fc7a3b'),'NJD':('#ce1126','#ff5c6a'),'LAK':('#3a3a3a','#c7cdd3'),'NYI':('#00539b','#6fb0ff'),
 'VGK':('#8a7448','#c9ab6e'),'STL':('#002f87','#6f9bff'),'WPG':('#041e42','#7aa7e6'),'DAL':('#006847','#3ecf8e'),
 'MIN':('#154734','#4fbf8a'),'CGY':('#c8102e','#ff6b5e'),'CAR':('#cc0000','#ff5a5a'),'EDM':('#cf4520','#ff7a3d'),
 'UTA':('#4a7fa8','#71afe5'),'SEA':('#006d75','#68d2df'),'DET':('#ce1126','#ff5c6a'),'VAN':('#00205b','#5d8dff'),
 'MTL':('#af1e2d','#ff6b6b'),'CHI':('#cf0a2c','#ff5c6a'),'TBL':('#002868','#6f9bff'),'COL':('#6f263d','#d47a99'),
 'BUF':('#003087','#6f9bff'),'CBJ':('#002654','#6f9bff'),'PHI':('#d14905','#ff8a3d'),'WSH':('#c8102e','#ff6b7d'),
}

PRICED = [  # Nov 15 morning run (~7 AM): The Odds API player props post after 10:05 AM, none yet; the 10:35 AM props task adds them
]
EXPERTS = {}
PUBLIC = {'EDM': '94% of moneyline tickets and 98% of the money on Edmonton (7 AM read, 1,004 tickets)', 'VGK': '97% of moneyline tickets and 96% of the money on Vegas; 98% of puck line tickets on Vegas -1.5 but only 61% of the money', 'FLA': '93% of total tickets and 91% of the money on the Over in FLA @ DAL'}
NOTES = {
 'EDM-PHI': [('Backup goalie', 'Likely (Daily Faceoff Unconfirmed, RotoWire Expected)', 'Jarry projected for Edmonton, not No. 1 Levi (10 starts, 9-1-0, .906). Edmonton played in Toronto last night (Levi, 19 save shutout), so this is the second night of a back to back. Jarry: 9 starts, 5-1-3, 2.50 GAA, .908 save %, about even with Levi this season.'),
             ('Backup goalie', 'Confirmed (Daily Faceoff and RotoWire)', 'Vladar starts for Philadelphia. No. 1 by the starts tiebreak is Woll (11 starts each; saves in starts 293 to 262), who played in Columbus last night, so Philadelphia is also on a back to back. Vladar: 11 starts, 3-4-4, 3.24 GAA, .879 save %.')],
 'CGY-ANA': [('Backup goalie', 'Likely (Daily Faceoff Unconfirmed, RotoWire Expected)', 'Cooley projected for Calgary, not No. 1 Wolf (10 starts), who won in Los Angeles last night. Cooley: 9 starts, 5-4-0, 2.63 GAA, .914 save %, the better save % of the two.'),
             ('Third goalie', 'Likely (Daily Faceoff Unconfirmed, RotoWire Expected)', 'Husso projected for Anaheim. No. 1 Dostal (11 starts, .856) allowed 6 to the Islanders last night; Brossoit was sent to San Diego (AHL) on Nov 13, so Husso is the second goalie now. Husso: 4 starts, 2-3-0, 3.55 GAA, .868 save %. Huberdeau (Calgary, hip) is on injured reserve and did not travel.')],
 'FLA-DAL': [('Backup goalie', 'Likely (Daily Faceoff Unconfirmed, RotoWire Expected)', 'Schmid projected for Florida, not No. 1 Markstrom (11 starts), who beat St. Louis last night. Schmid: 9 starts, 6-3-1, 3.10 GAA, .883 save %.'),
             ('Backup goalie', 'Likely (Daily Faceoff Unconfirmed, RotoWire Expected)', 'DeSmith projected for Dallas, not No. 1 Oettinger (15 starts, 2.17 GAA), who shut out Buffalo last night. DeSmith: 4 starts, 1-2-1, 2.70 GAA, .894 save %. Both teams are on the second night of a back to back.'),
             ('Injury', 'ESPN injuries feed, Nov 15', 'Dallas defenseman Miro Heiskanen (upper body) is listed doubtful; Lian Bichsel went on injured reserve Saturday. Neither is in the pulled top scorers, so the model is unchanged; it thins the Dallas blue line.')],
 'NSH-SJS': [('Backup goalie', 'Likely (Daily Faceoff Unconfirmed, RotoWire Expected)', 'Nedeljkovic projected for San Jose, not No. 1 Askarov (15 starts), who played in Utah last night (6-5 shootout win). Nedeljkovic: 7 starts, 3-3-1, 3.23 GAA, .895 save %. San Jose is on a back to back; Nashville last played Friday in Vegas.'),
             ('Goalie', 'Likely (Daily Faceoff Unconfirmed, RotoWire Expected)', 'Saros (14 starts, 7-3-4, .921) projected for Nashville; No. 1 by starts. Marchessault is day to day; Wennberg (San Jose) is out.')],
 'VAN-VGK': [('Goalie conflict', 'Unconfirmed (sources differ)', 'Daily Faceoff lists Lankinen and RotoWire expects Meriläinen for Vancouver; neither is confirmed, so the card keeps Daily Faceoff (Lankinen). Meriläinen is No. 1 by starts (13, 2-9-1, .885); Lankinen: 8 starts, 1-8-0, 6.03 GAA, .808 save %. Vancouver last played Friday (lost 5-1 to the Rangers).'),
             ('Goalie', 'Likely (Daily Faceoff Unconfirmed, RotoWire Expected)', 'Hart (11 starts, 6-3-2, .896) projected for Vegas; No. 1 by starts.')],
}

def esc(s): return html.escape(str(s))
def pct(p): return f'{100*p:.1f}%'
def tag(conf): return {'HIGH':'t-a','MED':'t-b','LOW':'t-c','NULL':'t-d'}[conf]

def grade(est, price, conf):
    e = 100*(est - be(price))
    if e >= 3.0 and conf in ('MED','HIGH'): call = 'PLAY'
    elif e >= 1.5 or (e >= 3.0): call = 'LEAN'
    else: call = 'PASS'
    return call, e

def low_goalie(g):
    return any(s in ('Unconfirmed','Projected') for s in (g['gA'][1], g['gH'][1]))

ALLROWS = []  # slate-wide plays
PROPPICKS = []  # slate-wide prop picks

def analyse(g):
    a, h, la, lh = g['a'], g['h'], g['la'], g['lh']
    base_conf = 'LOW' if low_goalie(g) else 'MED'
    rows = []  # (group, market, price_str, est, price, conf, why, thesis)
    # moneyline
    mA, mH = novig(la['ml'], lh['ml'])
    modH = g['pH'] if g['sr'] is None else (g['pH'] + g['sr']/100)/2
    estH = 0.4*modH + 0.6*mH; estA = 1 - estH
    srtxt = f", Sportradar {g['sr']:.1f}%" if g['sr'] else ''
    rows.append(('GAME', f'Moneyline {a}', fmt(la['ml']), estA, la['ml'], base_conf, f"Model {pct(g['pA'])}{(', Sportradar '+pct(1-g['sr']/100)) if g['sr'] else ''}, texas222 no-vig {pct(mA)}. Blend {pct(estA)}.", 'A'))
    rows.append(('GAME', f'Moneyline {h}', fmt(lh['ml']), estH, lh['ml'], base_conf, f"Model {pct(g['pH'])}{srtxt}, texas222 no-vig {pct(mH)}. Blend {pct(estH)}.", 'H'))
    # puck line
    plA, plH = la['pl'], lh['pl']
    if plA[0] > 0:  # away +1.5
        mod_fav = g['pH2']; mk_dog, mk_fav = novig(plA[1], plH[1])
        estF = 0.4*mod_fav + 0.6*mk_fav
        rows.append(('GAME', f'Puck line {a} +1.5', fmt(plA[1]), 1-estF, plA[1], base_conf, f"{h} wins by 2+: model {pct(mod_fav)}, market {pct(mk_fav)}.", 'A'))
        rows.append(('GAME', f'Puck line {h} -1.5', fmt(plH[1]), estF, plH[1], base_conf, f"Includes an empty-net allowance on one-goal regulation leads.", 'H'))
    else:
        mod_fav = g['pA2']; mk_fav, mk_dog = novig(plA[1], plH[1])
        estF = 0.4*mod_fav + 0.6*mk_fav
        rows.append(('GAME', f'Puck line {a} -1.5', fmt(plA[1]), estF, plA[1], base_conf, f"{a} wins by 2+: model {pct(mod_fav)}, market {pct(mk_fav)}.", 'A'))
        rows.append(('GAME', f'Puck line {h} +1.5', fmt(plH[1]), 1-estF, plH[1], base_conf, "Mirror of the line above.", 'H'))
    # total
    ov = la['tot'] if la['tot'][0]=='O' else lh['tot']; un = lh['tot'] if lh['tot'][0]=='U' else la['tot']
    line = ov[1]; u, push = g['p_tot_under'](line)
    o_mod = 1 - u - push
    mo, mu = novig(ov[2], un[2])
    if push:  # condition on no push for whole-number lines
        o_c, u_c = o_mod/(1-push), u/(1-push)
    else: o_c, u_c = o_mod, u
    estO = 0.4*o_c + 0.6*mo
    pushtxt = f" Push on {int(line)} about {pct(push)}." if push else ''
    rows.append(('GAME', f'Total over {line:g}', fmt(ov[2]), estO, ov[2], base_conf, f"Projected total {g['lamT']:.2f}. Model over {pct(o_c)}, market {pct(mo)}.{pushtxt}", 'O'))
    rows.append(('GAME', f'Total under {line:g}', fmt(un[2]), 1-estO, un[2], base_conf, f"Model under {pct(u_c)}, market {pct(mu)}.", 'U'))
    # team totals
    for side, t, lam, L in (('A', a, g['lamA'], la), ('H', h, g['lamH'], lh)):
        if not L['tt']: continue
        ln, po, pu = L['tt']; k = math.floor(ln)
        lam_tt = lam + 0.06
        mo_, mu_ = novig(po, pu)
        mod_o = p_ge(lam_tt, k+1)
        est_o = 0.4*mod_o + 0.6*mo_
        rec = sum(1 for x in (g['A'] if side=='A' else g['H'])['gfl'] if x > ln)
        n = (g['A'] if side=='A' else g['H'])['gp']
        rows.append(('TEAM TOTALS', f'{t} team total over {ln:g}', fmt(po), est_o, po, base_conf, f"Proj {lam_tt:.2f}. Scored {k+1}+ in {rec} of {n}. Model {pct(mod_o)}, market {pct(mo_)}.", 'O'))
        rows.append(('TEAM TOTALS', f'{t} team total under {ln:g}', fmt(pu), 1-est_o, pu, base_conf, f"Mirror. Model {pct(1-mod_o)}.", 'U'))
    # 3-way
    if 'draw' in lh:
        imp = [be(la['w3']), be(lh['w3']), be(lh['draw'])]; s = sum(imp)
        mk = [x/s for x in imp]; mod = [g['pA_reg'], g['pH_reg'], g['pT']]
        for lab, i, pr, th in ((f'3-way {a} regulation win', 0, la['w3'], 'A'), (f'3-way {h} regulation win', 1, lh['w3'], 'H'), ('3-way draw (tied after 60)', 2, lh['draw'], 'D')):
            est = 0.4*mod[i] + 0.6*mk[i]
            rows.append(('PERIOD & SPECIALS', lab, fmt(pr), est, pr, base_conf, f"Model {pct(mod[i])}, market {pct(mk[i])}.", th))
    # first period total
    if la['p1tot'] and lh['p1tot']:
        p1 = g['la']['p1tot'] if g['la']['p1tot'][0]=='O' else g['lh']['p1tot']
        p1u = g['lh']['p1tot'] if g['lh']['p1tot'][0]=='U' else g['la']['p1tot']
        emp = ((g['A']['p1f'] + g['H']['p1a'])/2 + (g['H']['p1f'] + g['A']['p1a'])/2)
        lam1 = 0.5*(0.31*(g['lamA']+g['lamH'])) + 0.5*emp
        ln1 = p1[1]; k1 = math.floor(ln1)
        if ln1 == k1:
            pu1 = sum(pois(lam1, i) for i in range(k1)); pp1 = pois(lam1, k1); po1 = 1-pu1-pp1
            po1c = po1/(1-pp1)
        else:
            po1c = p_ge(lam1, k1+1); pp1 = 0
        mo1, mu1 = novig(p1[2], p1u[2])
        est1 = 0.4*po1c + 0.6*mo1
        rows.append(('PERIOD & SPECIALS', f'1st period over {ln1:g}', fmt(p1[2]), est1, p1[2], 'LOW', f"1P λ {lam1:.2f} (half model share, half teams' own 1P rates {emp:.2f}). Model {pct(po1c)}, market {pct(mo1)}.", 'O1'))
        rows.append(('PERIOD & SPECIALS', f'1st period under {ln1:g}', fmt(p1u[2]), 1-est1, p1u[2], 'LOW', f"Model {pct(1-po1c)}.", 'U1'))
    # score first
    if la['s1'] is not None and lh['s1'] is not None:
        sfA = g['lamA']/(g['lamA']+g['lamH']); m1, m2 = novig(la['s1'], lh['s1'])
        e = 0.4*sfA + 0.6*m1
        rows.append(('PERIOD & SPECIALS', f'{a} scores first', fmt(la['s1']), e, la['s1'], 'LOW', f"Model {pct(sfA)}, market {pct(m1)}.", 'A'))
        rows.append(('PERIOD & SPECIALS', f'{h} scores first', fmt(lh['s1']), 1-e, lh['s1'], 'LOW', f"Model {pct(1-sfA)}, market {pct(m2)}.", 'H'))
    graded = []
    for grp, m, ps, est, price, conf, why, th in rows:
        call, edge = grade(est, price, conf)
        graded.append(dict(grp=grp, m=m, ps=ps, est=est, price=price, conf=conf, why=why, th=th, call=call, edge=edge))
    # correlation: carry best per thesis family
    fam = lambda th: 'side' if th in ('A','H','D') else 'total'
    carried = {}
    for r in graded:
        if r['call'] in ('PLAY','LEAN'):
            f = fam(r['th'])
            if f not in carried or r['edge'] > carried[f]['edge']: carried[f] = r
    for r in graded:
        if r['call'] in ('PLAY','LEAN') and carried.get(fam(r['th'])) is not r:
            r['why'] += f" <b>Same thesis as {esc(carried[fam(r['th'])]['m'])}; not carried.</b>"
            r['corr'] = True
    return graded, carried

def props(g):
    out = []
    for side, team, opp, lam_team, SK in (('A', g['a'], g['h'], g['lamA'], g['SA']), ('H', g['h'], g['a'], g['lamH'], g['SH'])):
        T = g['A'] if side=='A' else g['H']; O = g['H'] if side=='A' else g['A']
        opp_sa = (O['sa']*O['gp'] + LgS*5)/(O['gp']+5)
        sf = opp_sa/LgS
        team_gf = (T['gf']*T['gp'] + LG['lg_g']*5)/(T['gp']+5)
        gf = lam_team/team_gf
        for s in SK:
            n = s['gp']
            ls = (s['sh'] + 2.6*3)/(n+3)*sf*(1.02 if side=='H' else 0.98)
            avg = s['sh']/n
            line = 3.5 if avg >= 3.6 else (2.5 if avg >= 2.6 else 1.5)
            k = int(line+0.5)
            rec = {2:s['s2'],3:s['s3'],4:s['s4']}[k]
            p_rate = p_ge(ls, k); p_rec = rec/n
            p_s = 0.5*p_rate + 0.5*p_rec
            lp = (s['p'] + 0.6*3)/(n+3)*gf
            p_pr = 1-math.exp(-lp); p_prec = s['p1']/n; p_p = 0.5*p_pr + 0.5*p_prec
            lg_ = (s['g'] + 0.25*3)/(n+3)*gf
            p_g = 0.5*(1-math.exp(-lg_)) + 0.5*(s['g1']/n)
            p_2p = p_ge(lp, 2)
            out.append(dict(team=team, opp=opp, side=side, s=s, n=n, line=line, k=k, rec=rec, ls=ls, p_rate=p_rate, p_rec=p_rec, p_s=p_s,
                            lp=lp, p_pr=p_pr, p_prec=p_prec, p_p=p_p, p_g=p_g, p_2p=p_2p, sf=sf, gf=gf))
    return out

def prop_grade(pr, market, line, price):
    s = pr['s']; n = pr['n']
    if market == 'sog':
        k = int(line+0.5)
        rec = {2:s['s2'],3:s['s3'],4:s['s4']}[k]
        p_rate = p_ge(pr['ls'], k); p_rec = rec/n
        blend = 0.5*p_rate + 0.5*p_rec; basis = f"{k}+ SOG in {rec} of {n} (Wilson {wilson(rec,n)[0]*100:.0f} to {wilson(rec,n)[1]*100:.0f}%). Rate {pr['ls']:.2f} SOG vs opp → {pct(p_rate)}."
        agree = abs(p_rate - p_rec) < 0.08
    elif market == 'pts':
        blend = pr['p_p']; basis = f"Point in {s['p1']} of {n}. Rate {pct(pr['p_pr'])}."; agree = abs(pr['p_pr']-pr['p_prec']) < 0.08
    elif market == 'pts2':
        blend = pr['p_2p']; basis = f"{s['p']} points in {n} games. Poisson 2+ from rate {pr['lp']:.2f}."; agree = False
    else:
        blend = pr['p_g']; basis = f"Goal in {s['g1']} of {n}. {s['g']} goals on {s['sh']} shots."; agree = False
    mk = be(price) - 0.025
    est = 0.6*blend + 0.4*mk
    conf = 'MED' if (agree and n >= 9) else 'LOW'
    call, edge = grade(est, price, conf)
    return dict(est=est, blend=blend, basis=basis, conf=conf, call=call, edge=edge)

CALLCLS = {'PLAY':'play','LEAN':'lean','PASS':'pass'}

PRICEL = {'PLAY':'Value','LEAN':'Slight value','PASS':'Fair price'}
def row_html(r, picked=()):
    corr = ' <span class="tag t-d">correlated</span>' if r.get('corr') else ''
    pk = r['m'] in picked
    lab = PRICEL[r['call']]
    return (f"<tr{' class=\'pickrow\'' if pk else ''}><td><b>{esc(r['m'])}</b>{' <span class=\'tag t-a\'>Card pick</span>' if pk else ''}</td><td class='num'>{r['ps']}</td><td class='num'>{pct(r['est'])}</td><td class='num'>{pct(be(r['price']))}</td>"
            f"<td class='num'>{r['edge']:+.1f}</td><td class='{CALLCLS[r['call']]}'>{lab}{corr}</td><td><span class='tag {tag(r['conf'])}'>{r['conf']}</span></td><td>{r['why']}</td></tr>")

def gl(g, side):
    n, st, data, svr, sa = g['gA'] if side=='A' else g['gH']
    return n, st, data, svr, sa

def last5(T):
    res = []
    for f, a in list(zip(T['gfl'], T['gal']))[-5:]:
        res.append(('W' if f > a else 'L') + f' {f}-{a}')
    return ', '.join(res)

def cmp_row(label, va, vh, better):  # better: 'hi'|'lo'|None, va/vh numeric for compare
    a_txt, h_txt, a_num, h_num = va[0], vh[0], va[1], vh[1]
    ca, ch = '', ''
    if better and a_num is not None and h_num is not None and abs(a_num-h_num) > 0.05*max(abs(a_num),abs(h_num),1e-9):
        a_better = (a_num > h_num) if better=='hi' else (a_num < h_num)
        if a_better: ca = ' bet'
        else: ch = ' bet'
    return f"<tr><td>{label}</td><td class='ca{ca}'>{a_txt}</td><td class='ch{ch}'>{h_txt}</td></tr>"

from signals import AN, WEIGHTS, LAST
from standings import load as _st_load
from divisions import signal as _div_signal
_ST, _FUT = _st_load(); _STB = {x['t']: x for x in _ST}
def _imp(o): return 100/(o+100) if o > 0 else -o/(-o+100)
PICKS = []
TIERCLS = {'All': 'tg-solid', 'Strong':'tg-strong','Solid':'tg-solid','Lean':'tg-lean'}

def tier(m): return 'Strong' if m >= 4 else ('Solid' if m >= 2 else 'Lean')

import rules as RL
from divisions import strength as _div_strength, DIVNAME as _DIVN
def _rec3(s):
    w, l, o = map(int, s.split('-')); return (w, l, o)
def _strk(s):
    code = s.rstrip('0123456789'); n = int(s[len(code):] or 0); return (code, n)
def _p1(la, lh):
    o = la['p1tot'] if la.get('p1tot') and la['p1tot'][0] == 'O' else lh.get('p1tot')
    u = lh['p1tot'] if lh.get('p1tot') and lh['p1tot'][0] == 'U' else la.get('p1tot')
    return (o[1], o[2], u[2]) if o and u else None
def ctx_from_card(g, graded):
    a, h = g['a'], g['h']; key = f'{a}-{h}'; S = AN[key]; A, H = g['A'], g['H']; stA, stH = _STB[a], _STB[h]
    la, lh = g['la'], g['lh']
    estH = next(r['est'] for r in graded if r['m'] == f'Moneyline {h}')
    import re as _re
    tot = la['tot'] if la['tot'][0] == 'O' else lh['tot']; und = lh['tot'] if la['tot'][0] == 'O' else la['tot']
    l5 = (sum(x+y for x, y in list(zip(A['gfl'], A['gal']))[-5:]) + sum(x+y for x, y in list(zip(H['gfl'], H['gal']))[-5:])) / 10
    return dict(a=a, h=h, mla=la['ml'], mlh=lh['ml'], ml_open=tuple(S['ml_open']), bets=S['bets'], money=S['money'],
                o_bets=S['o_bets'], o_money=S['o_money'], sig_ml=S['sig_ml'], sig_tot=S['sig_tot'], estH=estH,
                sv_a=g['gA'][3], sv_h=g['gH'][3], loss_a=g['lossA'], loss_h=g['lossH'], rest_a=A['rest'], rest_h=H['rest'],
                home_rec_h=_rec3(H['home']), road_rec_a=_rec3(A['road']), strk_a=_strk(stA['strk']), strk_h=_strk(stH['strk']),
                l10_a=_rec3(stA['l10']), l10_h=_rec3(stH['l10']), gd_a=stA['diff']/stA['gp'], gd_h=stH['diff']/stH['gp'],
                last_a=LAST[a][0], last_h=LAST[h][0], ppct_a=stA['ppct'], ppct_h=stH['ppct'], cup_a=_FUT['CUP'][a], cup_h=_FUT['CUP'][h],
                div_a=_DIVN[stA['div']], div_h=_DIVN[stH['div']], div_str={d: _div_strength(d) for d in _DIVN.values()},
                pl=dict(sp_a=la['pl'][0], price_a=la['pl'][1], price_h=lh['pl'][1]),
                line=tot[1], tprice=(tot[2], und[2]), tot_open=S['tot_open'], lamT=g['lamT'], last5=l5,
                neutral='neutral' in str(g.get('venue', '')).lower(),
                p1=_p1(la, lh))

SHORT = {'Action Network Sharp Action':'sharp money','Action Network PRO Systems':'PRO system match','Action Network Big Money':'big money',
         'Reverse line movement':'reverse line move','Money % above ticket %':'bigger bets than ticket share','Card projection':'projection',
         'Goalie edge':'goalie edge','Key absence':'key injury','Rest edge':'opponent on a back-to-back','Total moved down':'total dropped',
         'Home ice':'home ice','Cold streak':'opponent cold streak','Track record':'track record','Bounce-back candidate':'bounce-back',
         'Regression watch':'regression watch','Roster strength':'roster strength','Home/road split':'home/road split','Recent scoring':'recent scoring','Goaltending':'goaltending'}
def pl_score(key, c, sd, ln, price, prob, nm, ml_against=(), ml_for=()):
    """Puck line tier (Nov 3, Trina): scored on puck line evidence only, not the moneyline case.
    For: Sharp Action on the team's moneyline (the PL1 trigger, 2), Action Network puck line signals on that team (Sharp Action 2,
    Big Money 1, PRO Systems 1), puck line money 10+ points above tickets (1), card cover chance 3+ points above the price's break-even (1).
    Against: the same puck line signals for the other team, a card cover chance 3+ points below break-even (1), and the scored
    moneyline signals against the team (they hurt its chance to win, so they hurt its chance to cover too).
    +1.5 (Nov 3, Trina): a +1.5 wins whenever the moneyline wins, so the moneyline signals FOR the team count too.
    -1.5 counts only the trigger and puck line evidence for it, since winning by 2+ is a bigger ask than winning."""
    an = AN.get(key, {}); od = 'H' if sd == 'A' else 'A'; f, ag = [], []
    if ln == '+1.5' and ml_for:
        f.extend((p_, SHORT.get(s_, s_), n_) for p_, s_, n_ in ml_for)
    else:
        f.append((2, 'Sharp Action on its moneyline', 'The PL1 rule trigger.'))
    for n_, s_ in (an.get('sig_pl') or {}).items():
        (f if s_ == sd else ag).append((WEIGHTS[n_], f'Puck line {n_}', f"Action Network {n_} on {nm[s_]}'s puck line."))
    pb, pm = an.get('pl_bets'), an.get('pl_money')
    if pb is not None and pm is not None:
        tb, tm_ = (pb, pm) if sd == 'A' else (100 - pb, 100 - pm)
        if tm_ - tb >= 10: f.append((1, 'Puck line money over tickets', f'{tm_}% of puck line money on {tb}% of tickets.'))
        elif tb - tm_ >= 10: ag.append((1, 'Puck line money against', f'{100 - tm_}% of puck line money on the other side from {100 - tb}% of tickets.'))
    if prob is not None:
        need = be(price); gap = prob - need
        if gap >= 0.03: f.append((1, 'Cover chance above price', f'Card cover chance {100*prob:.1f}% vs {100*need:.1f}% needed at {fmt(price)}.'))
        elif gap <= -0.03: ag.append((1, 'Cover chance below price', f'Card cover chance {100*prob:.1f}% vs {100*need:.1f}% needed at {fmt(price)}.'))
        else: f.append((0, 'Cover chance about even with price', f'Card cover chance {100*prob:.1f}% vs {100*need:.1f}% needed at {fmt(price)} (0 points).'))
    for p_, s_, n_ in ml_against:
        ag.append((p_, SHORT.get(s_, s_), n_))
    return f, ag, sum(p for p, _, _ in f), sum(p for p, _, _ in ag)

RULE_REC = {}  # filled per page: rule -> baseline text
def rec_span(rule):
    """Two labeled records: Backtest = every game this season at closing prices (daily re-check);
    Live = the card's own logged picks under the current rules (Oct 30 on) at texas222 prices, filled from the ledger."""
    w, l, p, u = RL.RULES[rule].get('record') or (0, 0, 0, 0.0)
    uc = 'upos' if u > 0 else ('uneg' if u < 0 else '')
    return (f"Backtest {w}-{l}{('-'+str(p)) if p else ''}, <span class='{uc}'>{u:+.1f}u</span>"
            f" · Live <span class='rlive' data-rule='{rule}'>·</span>")

def _rnote():
    v = {k: RL.RULES[k] for k in RL.ORDER}
    st = lambda k: '' if v[k]['status'] == 'on' else ' (switched off by the daily re-check; tracked, not shown)'
    return (f"Pick rules (approved Oct 30 after the review of every game this season; the daily re-check keeps them honest): "
            f"<b>Moneyline</b>: {esc(v['ML1']['label'])}{st('ML1')} (favorite no longer than -200, underdog +100 to +200). "
            f"<b>Puck line</b>: {esc(v['PL1']['label'])}{st('PL1')}. <b>Total</b>: {esc(v['TOT1']['label'])}{st('TOT1')}. Otherwise No pick.")
RULES_NOTE = _rnote()

def picks(g, graded):
    a, h = g['a'], g['h']; key = f'{a}-{h}'; nm = {'A': a, 'H': h}
    c = ctx_from_card(g, graded); r = RL.score(c); rp = RL.apply_rules(c, r)
    def est_of(m): return next((x['est'] for x in graded if x['m'] == m), None)
    def rows_for(rows, side):
        f = sorted([(p, s, n) for s, m, sd, p, n in rows if p and sd == side], key=lambda x: -x[0])
        ag = sorted([(p, s, n) for s, m, sd, p, n in rows if p and sd != side], key=lambda x: -x[0])
        return f, ag
    def short(f, ag):
        x = ', '.join(dict.fromkeys(SHORT.get(s_, s_) for _, s_, _ in f[:3]))
        if ag: x += '. Against: ' + ', '.join(dict.fromkeys(SHORT.get(s_, s_) for _, s_, _ in ag[:2]))
        return x
    out = dict(key=key, ml=None, pl=None, tot=None, rp=rp, r=r, c=c)
    side = r['side']; s_for, s_ag = rows_for(r['S'], side)
    ml = next((p for p in rp if p['rule'] == 'ML1'), None)
    sp_ = c['mla'] if side == 'A' else c['mlh']
    if ml:
        ml['rule_status'] = ml['status']; ml['tier'] = r['ml_tier']; ml['status'] = RL.tier_status('ML1', ml['status'], r['ml_tier'])
    if ml and ml['status'] == 'on':
        out['ml'] = dict(rule='ML1', text=f"{NAMES[nm[side]]} moneyline", price=ml['price'], prob=est_of(f'Moneyline {nm[side]}'), tier=r['ml_tier'], conf=r['conf_ml'],
                         score=f"{r['sc'][side]}–{r['sc']['H' if side=='A' else 'A']}", m=f'Moneyline {nm[side]}', team=nm[side], side=side,
                         short=short(s_for, s_ag), for_=s_for, against=s_ag)
    else:
        why = ((f"The {ml['tier']} tier of this rule is turned off (its real picks are red, season to date); the would-be pick is tracked, not shown." if ml.get('rule_status') == 'on' else 'Rule is switched off (season to date is red); the would-be pick is still tracked.') if ml else RL.nopick_reason('ML1', c, r, nm))
        out['ml'] = dict(nopick=True, why=why, rule='ML1', side=side, team=nm[side], tier=r['ml_tier'], short=short(s_for, s_ag))
    pl = next((p for p in rp if p['rule'] == 'PL1'), None)
    if pl:
        _sd = pl['side']; _ln = '+1.5' if pl['line'] > 0 else '-1.5'; _mf0, _ma0 = rows_for(r['S'], _sd)
        _f0, _a0, _pf0, _pa0 = pl_score(key, c, _sd, _ln, pl['price'], est_of(f'Puck line {nm[_sd]} {_ln}'), nm, _ma0, _mf0)
        pl['rule_status'] = pl['status']; pl['tier'] = RL.tier(_pf0 - _pa0); pl['status'] = RL.tier_status('PL1', pl['status'], pl['tier'])
    if pl and pl['status'] == 'on':
        sd = pl['side']; ln = '+1.5' if pl['line'] > 0 else '-1.5'
        _mf, _ma = rows_for(r['S'], sd)
        f_, ag_, pf, pa = pl_score(key, c, sd, ln, pl['price'], est_of(f'Puck line {nm[sd]} {ln}'), nm, _ma, _mf)
        out['pl'] = dict(rule='PL1', text=f"{NAMES[nm[sd]]} {ln}", price=pl['price'], prob=est_of(f'Puck line {nm[sd]} {ln}'), tier=RL.tier(pf - pa), conf=False,
                         score=f"{pf}–{pa}", m=f'Puck line {nm[sd]} {ln}', team=nm[sd], side=sd, line=pl['line'],
                         short=', '.join(s_ for p_, s_, _ in f_ if p_) + ('. Against: ' + ', '.join(dict.fromkeys(s_ for _, s_, _ in ag_)) if ag_ else ''), for_=f_, against=ag_)
    else:
        lit = [sd for n_, sd in (c['sig_ml'] or {}).items() if n_ == 'Sharp Action']
        out['pl'] = dict(nopick=True, rule='PL1', why=((f"Sharp Action is on {NAMES[nm[pl['side']]]}, but the {pl['tier']} tier of this rule is turned off (its real picks are red, season to date); the would-be pick {NAMES[nm[pl['side']]]} {'+1.5' if pl['line'] > 0 else '-1.5'} {pl['price']:+d} is tracked, not shown." if pl.get('rule_status') == 'on' else 'Rule is switched off (season to date is red); the would-be pick is still tracked.') if pl else RL.nopick_reason('PL1', c, r, nm)))
    tp = next((p for p in rp if p['rule'] == 'TOT1'), None)
    tp2 = next((p for p in rp if p['rule'] == 'TOT2'), None)
    # Nov 12 (tested): when TOT1 and TOT2 both fit, TOT2 decides the total (overlap: same side 19-11, opposite 2-0 for TOT2;
    # TOT1 alone 3-3). TOT1 is then a would-be pick with a conflict note, so one total per game.
    if tp and tp2 and tp2['status'] == 'on':
        tp['status'] = 'off'; tp['conflict'] = 'card picked TOT2 for this total'
    if 'T' in r:
        t_for, t_ag = rows_for(r['T'], r['tside'])
        lean = f"Totals signals lean {'over' if r['tside']=='O' else 'under'} ({r['tc'][r['tside']]}–{r['tc']['U' if r['tside']=='O' else 'O']}); they lost on their own in the review, so they are information only."
        if tp:
            tp['rule_status'] = tp['status']; tp['tier'] = RL.tier(r['tc']['O'] + 2 - r['tc']['U'])
            if not tp.get('conflict'): tp['status'] = RL.tier_status('TOT1', tp['status'], tp['tier'])
        if tp and tp['status'] == 'on':
            dv = []
            if {c['div_a'], c['div_h']} == {'Atlantic', 'Pacific'}: dv.append((1, 'Atlantic vs Pacific', f"{c['div_a']} team vs {c['div_h']} team: the over went 17-10 in these games in the Sep 29 to Oct 28 review."))
            if r.get('div_pts') == 2: dv.append((1, 'Division signal 2 points', f"{c['div_a']} {c['div_str'][c['div_a']]:.3f} vs {c['div_h']} {c['div_str'][c['div_h']]:.3f} adjusted out-of-division points %."))
            out['tot'] = dict(rule='TOT1', text=f"Over {c['line']:g}", price=tp['price'], prob=est_of(f"Over {c['line']:g}"), tier=RL.tier(r['tc']['O'] + 2 - r['tc']['U']), conf=False,
                              score=f"{r['tc']['O'] + 2}–{r['tc']['U']}",
                              m=f"Over {c['line']:g}", team='Over', side='O', line=c['line'], short='division matchup', for_=dv,
                              against=[(p_, s_, n_ + ' (info only)') for p_, s_, n_ in rows_for(r['T'], 'O')[1]], note=lean)
        elif tp2 and tp2['status'] == 'on':
            sd2 = tp2['side']; t2_for, t2_ag = rows_for(r['T'], r['tside'])
            out['tot'] = dict(rule='TOT2', text=f"{'Over' if sd2 == 'O' else 'Under'} {c['line']:g}", price=tp2['price'], prob=est_of(f"{'Over' if sd2 == 'O' else 'Under'} {c['line']:g}"), tier=tp2['tier'], conf=False,
                              score=f"lead {r['t_lead']} the other way",
                              m=f"{'Over' if sd2 == 'O' else 'Under'} {c['line']:g}", team='Over' if sd2 == 'O' else 'Under', side=sd2, line=c['line'],
                              short=f"totals signals lean {'over' if r['tside'] == 'O' else 'under'} by {r['t_lead']}; this rule takes the other side",
                              for_=[(2, 'Contrarian totals rule', f"Totals signals lean {'over' if r['tside'] == 'O' else 'under'} {r['tc'][r['tside']]}–{r['tc']['U' if r['tside'] == 'O' else 'O']}; when they lean 2+ points one way, the other side went 122-92-3 (+21.6u) this season at the close.")],
                              against=[(p_, s_, n_) for p_, s_, n_ in t2_for], note=lean)
        else:
            why = ('Rule is switched off (season to date is red); the would-be pick is still tracked.' if tp else RL.nopick_reason('TOT1', c, r, nm))
            why2 = ('The totals rule (TOT2) fits but is switched off; the would-be pick is tracked.' if tp2 else RL.nopick_reason('TOT2', c, r, nm))
            out['tot'] = dict(nopick=True, rule='TOT1', why=why + ' ' + why2 + ' ' + lean, short=short(t_for, t_ag), line=c['line'])
    PICKS.append(out)
    # ---- HTML
    def box(title, p):
        if p is None: return ''
        if p.get('nopick'):
            return (f"<div class='pick nopick'><div class='lbl'>{title}</div><div class='pt'>No pick</div><div class='sub' style='margin:4px 0 0'>{esc(p['why'])}</div></div>")
        tg = f"<span class='tag {TIERCLS[p['tier']]}'>{p['tier']}</span>" if p.get('tier') else ''
        cf = " <span class='tag t-d'>conflicting signals</span>" if p.get('conf') else ''
        fl = ''.join(f"<li><b>{esc(s_)}</b>: {esc(n_)}</li>" for _, s_, n_ in p['for_']) or '<li>No scored signal on this side beyond the rule trigger.</li>'
        ag = ('<div class="lbl">Working against it</div><ul class="nl">' + ''.join(f"<li><b>{esc(s_)}</b>: {esc(n_)}</li>" for _, s_, n_ in p['against']) + '</ul>') if p['against'] else ''
        rl = RL.RULES[p['rule']]
        prob = f" · projected chance {pct(p['prob'])}" if p.get('prob') is not None else ''
        sc_ = f"<div class='num'>Signal score {p['score']}</div>" if p.get('score') else ''
        return (f"<div class='pick'><div class='lbl'>{title}</div><div class='pt'>{esc(p['text'])}</div>"
                f"<div class='num'>texas222 {fmt(p['price'])}{prob}</div>{sc_}<div>{tg}{cf}</div>"
                f"<div class='rule'><b>{esc(rl['short'])}:</b> {esc(rl['label'])}<br>{rec_span(p['rule'])}</div>"
                f"<div class='lbl'>Why</div><ul class='nl'>{fl}</ul>{ag}" + (f"<div class='sub' style='margin:6px 0 0'>{esc(p['note'])}</div>" if p.get('note') else '') + "</div>")
    wl = ''
    sig_tbl = ''.join(f"<tr><td>{esc(s)}</td><td>{m}</td><td><b>{esc(nm.get(sd, 'Over' if sd=='O' else 'Under'))}</b></td><td class='num'>{'+'+str(p) if p else 'info'}</td><td>{esc(n)}</td></tr>" for s, m, sd, p, n in r['S'] + r.get('T', []))
    return f"""
<h3 class='sh' id='{a.lower()}-{h.lower()}-picks'>Picks: moneyline, puck line and total</h3>
<div class='picks picks3'>
{box('Moneyline', out['ml'])}
{box('Puck line', out['pl'])}
{box('Total', out['tot'])}
</div>
{wl}
<div class='sub' style='margin-top:8px'><b>Check before betting:</b> {esc(g['gA'][0])} ({g['gA'][1]}) vs {esc(g['gH'][0])} ({g['gH'][1]}) in goal. A different starter changes these picks.</div>
<div class='scroll' style='margin-top:10px'><table><thead><tr><th>Signal</th><th>Market</th><th>Points to</th><th>Weight</th><th>Detail</th></tr></thead><tbody>{sig_tbl}</tbody></table></div>
<div class='sub' style='margin-top:8px'>{RULES_NOTE} Signal weights: Sharp Action 2, reverse line movement 2, key absence 2 (0.15+ goals) or 1, home/road split 2 (.30+ gap) or 1; one point each for PRO Systems, Big Money, money over tickets, projection, goalie edge, rest, home ice, opponent cold streak, track record, bounce-back, regression watch and roster strength. Division strength, fade the public, recent form, goal differential and hot streak show as info only (0 points): each lost on its own in the review. Strong = lead of 4+, Solid = 2 to 3, Lean = 0 to 1.</div>"""


def game_panel(gi, g):
    a, h = g['a'], g['h']; key = f'{a}-{h}'; tid = f'{a.lower()}-{h.lower()}'
    A, H = g['A'], g['H']
    graded, carried = analyse(g)
    pk_html = picks(g, graded)
    PICKED = {x['m'] for x in (PICKS[-1]['ml'], PICKS[-1]['pl']) if x and not x.get('nopick')}
    pr = props(g)
    # priced props
    priced = []
    for (team, pl, mkt, line, price, book, src) in PRICED:
        if team not in (a, h): continue
        p = next((x for x in pr if x['team']==team and x['s']['n']==pl), None)
        if not p: continue
        r = prop_grade(p, mkt, line, price)
        lab = {'sog':f'o{line:g} SOG','pts':'o0.5 points','pts2':'2+ points','goal':'anytime goal'}[mkt]
        priced.append(dict(team=team, pl=pl, lab=lab, price=price, book=book, src=src, mkt=mkt, **r))
    for r in graded:
        if r['call'] in ('PLAY','LEAN') and not r.get('corr'):
            ALLROWS.append((key, r['m'], r['ps'], r['est'], r['edge'], r['call'], r['conf'], tid, PRICEL[r['call']] + (' · card pick' if r['m'] in PICKED else '')))
    pp = [r for r in priced if r['call'] in ('PLAY','LEAN')]
    pp.sort(key=lambda r: (r['call'] != 'PLAY', -r['edge']))
    for r in pp: PROPPICKS.append((key, tid, g['time'], r))
    if pp:
        pk_html += ("<div class='card props-card'><div class='lbl'>Player prop picks</div><ul class='nl'>" +
            ''.join(f"<li><b>{esc(r['pl'])} {esc(r['lab'])}</b> {fmt(r['price'])} at {esc(r['book'])} · <span class='{CALLCLS[r['call']]}'>{r['call']}</span> · projected {pct(r['est'])} vs {pct(be(r['price']))} needed. {esc(r['basis'])}</li>" for r in pp) +
            "</ul><div class='sub' style='margin:6px 0 0'>Not offered at texas222; priced at the book shown. Details in sections 8 and 9.</div></div>")
    else:
        pk_html += "<div class='card props-card'><div class='lbl'>Player prop picks</div><div class='sub' style='margin:0'>No priced prop clears its break-even tonight. Fair prices to shop against are in sections 8 and 9.</div></div>"
    for r in priced:
        if r['call'] in ('PLAY','LEAN'):
            ALLROWS.append((key, f"{r['pl']} {r['lab']}", f"{fmt(r['price'])} {r['book']}", r['est'], r['edge'], r['call'], r['conf'], tid, r['call'] + ' · prop pick'))
    gA, gH = gl(g,'A'), gl(g,'H')
    def gdesc(gx, team):
        n, st, data, svr, sa = gx
        if data is None: return f"{n} · {st} · no NHL starts this season · card assumes {svr:.3f}"
        return f"{n} · {st} · {data['gs']} GS, {data['rec']}, {data['gaa']:.2f} GAA, {data['sv']:.3f} · regressed to {svr:.3f}"
    sec = lambda sid: f'{tid}-{sid}'
    nav = ''.join(f"<a href='#{sec(s)}'>{lbl}</a>" for s, lbl in (('picks','Picks'),('dec','Price check'),('audit','Audit'),('env','Venue'),('sp','Goalies'),('exit','Form'),('lineups','Team context'),('proj','Projection'),('tt','Team totals'),('first','1st period'),('pprops','Shot props'),('bprops','Point &amp; goal props'),('exp','Experts'),('frame','Framework')))
    groups = {}
    for r in graded: groups.setdefault(r['grp'], []).append(r)
    dec = ''
    for gname in ('GAME','TEAM TOTALS','PERIOD & SPECIALS'):
        if gname in groups:
            dec += f"<tr class='grp'><td colspan='8'>{gname} MARKETS</td></tr>" + ''.join(row_html(r, PICKED) for r in groups[gname])
    dec += "<tr class='grp'><td colspan='8'>SKATER PROPS · not offered at texas222, priced at the named book</td></tr>"
    if priced:
        for r in priced:
            dec += (f"<tr{' class=\'pickrow\'' if r['call'] in ('PLAY','LEAN') else ''}><td><b>{esc(r['pl'])} {r['lab']}</b>{' <span class=\'tag t-a\'>Card pick</span>' if r['call'] in ('PLAY','LEAN') else ''}</td><td class='num'>{fmt(r['price'])} · {esc(r['book'])}</td><td class='num'>{pct(r['est'])}</td><td class='num'>{pct(be(r['price']))}</td>"
                    f"<td class='num'>{r['edge']:+.1f}</td><td class='{CALLCLS[r['call']]}'>{r['call']}</td><td><span class='tag {tag(r['conf'])}'>{r['conf']}</span></td><td>{esc(r['basis'])}</td></tr>")
    else:
        dec += "<tr><td colspan='8' class='none'>No market prices found for this game's skaters. Fair prices are in sections 8 and 9: bet only at or better than fair.</td></tr>"
    carry = [r for r in graded if r['call'] in ('PLAY','LEAN') and not r.get('corr')] + [r for r in priced if r['call'] in ('PLAY','LEAN')]
    head = ' · '.join(f"<b>{esc(r.get('m') or (r['pl']+' '+r['lab']))}</b> {r['call']}" for r in carry) or 'No PLAY or LEAN. Every market is priced inside the noise.'
    corr_txt = 'Side markets (moneyline, puck line, 3-way, score first) are one thesis; totals markets (game, team, 1st period) are another. Only the best edge in each family is carried. A skater over on the team you fade works against that side read.'
    notes = NOTES.get(key, [])
    audit = ''.join(f"<tr><td>{esc(c)}</td><td>{esc(s)}</td><td>{esc(w)}</td></tr>" for c, s, w in notes) or "<tr><td colspan='3' class='none'>No published claim checked for this game changed a read.</td></tr>"
    flag = esc(notes[0][2]) if notes else 'Nothing in the previews changes the read.'
    # tables
    def tt_rows():
        rr = [r for r in graded if r['grp']=='TEAM TOTALS']
        return ''.join(row_html(r, PICKED) for r in rr)
    def p1_rows(): return ''.join(row_html(r, PICKED) for r in graded if r['grp']=='PERIOD & SPECIALS')
    # props tables
    def sog_table():
        rows = ''
        for side, team in (('A', a), ('H', h)):
            nm = NAMES[team]
            rows += f"<tr class='grp'><td colspan='7'><span class='{'tmA' if side=='A' else 'tmH'}'>{esc(nm)}</span> · opponent allows {(g['H'] if side=='A' else g['A'])['sa']:.1f} SOG per game</td></tr>"
            for p in [x for x in pr if x['team']==team]:
                s = p['s']; wl, wh = wilson(p['rec'], p['n'])
                fair = amer(p['p_s'])
                rows += (f"<tr><td>{esc(s['n'])}</td><td class='num'>o{p['line']:g}</td><td>{p['rec']} of {p['n']} <span class='num'>(Wilson {wl*100:.0f} to {wh*100:.0f}%)</span></td><td class='num'>{s['sh']/p['n']:.2f} → {p['ls']:.2f}</td>"
                         f"<td class='num'>{pct(p['p_rate'])}</td><td class='num'>{pct(p['p_s'])}</td><td class='num'>{fmt(fair)}</td></tr>")
        return rows
    def pts_table():
        rows = ''
        for side, team in (('A', a), ('H', h)):
            nm = NAMES[team]
            lam = g['lamA'] if side=='A' else g['lamH']
            rows += f"<tr class='grp'><td colspan='8'><span class='{'tmA' if side=='A' else 'tmH'}'>{esc(nm)}</span> · projected {lam:.2f} goals tonight</td></tr>"
            for p in [x for x in pr if x['team']==team]:
                s = p['s']
                rows += (f"<tr><td>{esc(s['n'])}</td><td class='num'>{s['g']}-{s['a']}-{s['p']}</td><td>{s['p1']} of {p['n']}</td><td class='num'>{pct(p['p_p'])}</td><td class='num'>{fmt(amer(p['p_p']))}</td>"
                         f"<td>{s['g1']} of {p['n']}</td><td class='num'>{pct(p['p_g'])} · {fmt(amer(p['p_g']))}</td><td class='num'>{s['ppp']}</td></tr>")
        return rows
    exp = ''.join(f"<tr><td>{esc(n)}</td><td>{esc(p)}</td><td class='num'>{esc(o)}</td></tr>" for n, p, o in EXPERTS.get(key, [])) or "<tr><td colspan='3' class='none'>No named expert pick found.</td></tr>"
    pub = '; '.join(v for k, v in PUBLIC.items() if k in (a, h)) or 'No split found.'
    mA, mH = novig(g['la']['ml'], g['lh']['ml'])
    estH = next(r['est'] for r in graded if r['m']==f'Moneyline {h}')
    bars = ''.join(f"<tr><td style='width:240px'>{lbl}</td><td><div class='bar'><i style='width:{100*v:.1f}%'></i></div></td><td class='num'>{pct(v)}</td></tr>" for lbl, v in (
        (f'{h} model', g['pH']), (f'{h} texas222 no-vig', mH), (f'{a} model', g['pA']), (f'{a} texas222 no-vig', mA)))
    tot_line = (g['la']['tot'] if g['la']['tot'][0]=='O' else g['lh']['tot'])[1]
    rest_txt = lambda T: 'back-to-back (played last night)' if T['rest']==0 else f"{T['rest']} day{'s' if T['rest']!=1 else ''} off"
    def rec_win(t):
        w,l,o = map(int, t.split('-')); return (w+0.5*o)/max(w+l+o,1)
    ctx = ''.join([
        cmp_row('Record', (A['rec'], rec_win(A['rec'])), (H['rec'], rec_win(H['rec'])), 'hi'),
        cmp_row('Home / road', (f"road {A['road']}", None), (f"home {H['home']}", None), None),
        cmp_row('Last 10', (A['l10'], rec_win(A['l10'])), (H['l10'], rec_win(H['l10'])), 'hi'),
        "<tr class='grp'><td>OFFENSE</td><td class='ca'></td><td class='ch'></td></tr>",
        cmp_row('Goals per game', (f"{A['gf']:.2f} · road {A['rgf']:.2f}", A['gf']), (f"{H['gf']:.2f} · home {H['hgf']:.2f}", H['gf']), 'hi'),
        cmp_row('Shots per game', (f"{A['sf']:.1f}", A['sf']), (f"{H['sf']:.1f}", H['sf']), 'hi'),
        cmp_row('Shooting %', (f"{100*A['gf']/A['sf']:.1f}%", A['gf']/A['sf']), (f"{100*H['gf']/H['sf']:.1f}%", H['gf']/H['sf']), 'hi'),
        cmp_row('Power play', (A['pp'], A['ppv']), (H['pp'], H['ppv']), 'hi'),
        cmp_row('1st period goals for', (f"{A['p1f']:.2f}", A['p1f']), (f"{H['p1f']:.2f}", H['p1f']), 'hi'),
        "<tr class='grp'><td>DEFENSE</td><td class='ca'></td><td class='ch'></td></tr>",
        cmp_row('Goals allowed per game', (f"{A['ga']:.2f} · road {A['rga']:.2f}", A['ga']), (f"{H['ga']:.2f} · home {H['hga']:.2f}", H['ga']), 'lo'),
        cmp_row('Shots allowed per game', (f"{A['sa']:.1f}", A['sa']), (f"{H['sa']:.1f}", H['sa']), 'lo'),
        cmp_row('Penalty kill', (A['pk'], A['pkv']), (H['pk'], H['pkv']), 'hi'),
        cmp_row('1st period goals against', (f"{A['p1a']:.2f}", A['p1a']), (f"{H['p1a']:.2f}", H['p1a']), 'lo'),
        "<tr class='grp'><td>TONIGHT</td><td class='ca'></td><td class='ch'></td></tr>",
        cmp_row('Starting goalie', (gA[0], None), (gH[0], None), None),
        cmp_row('Goalie used on card', (f"{gA[3]:.3f}", gA[3]), (f"{gH[3]:.3f}", gH[3]), 'hi'),
        cmp_row('Rest', (rest_txt(A), None), (rest_txt(H), None), None),
    ])
    shot_edge = (g['shotsA'], g['shotsH'])
    decider = f"Expected shots {a} {shot_edge[0]:.1f}, {h} {shot_edge[1]:.1f}. "
    decider += f"Goaltending on the card: {gA[0]} {gA[3]:.3f} vs {gH[0]} {gH[3]:.3f}. "
    if A['rest']==0 or H['rest']==0: decider += f"{a if A['rest']==0 else h} is on the second night of a back-to-back."
    calc = (f"{a} expected shots   {g['shotsA']:5.1f}   ({A['sf']:.1f} for vs {H['sa']:.1f} allowed, both regressed 5 games to {LgS:.1f})\n"
            f"{h} expected shots   {g['shotsH']:5.1f}   ({H['sf']:.1f} for vs {A['sa']:.1f} allowed)\n"
            f"{a} finishing        x{g['qA']:.2f}   (shooting % regressed 250 shots to league {100*LG['lg_sh']:.1f}%)\n"
            f"{h} finishing        x{g['qH']:.2f}\n"
            f"Goalies faced       {a} shoots on {gH[0]} {gH[3]:.3f} · {h} shoots on {gA[0]} {gA[3]:.3f}\n"
            f"Home ice            {h} x1.035, {a} x0.965{'   back-to-back x0.97' if (A['rest']==0 or H['rest']==0) else ''}\n"
            f"Venue splits        {h} x{g['vH']:.3f} at home, {a} x{g['vA']:.3f} on the road\n"
            "──────────────────────────────────────────────────────────\n"
            f"Projected goals     {a} {g['lamA']:.2f}   {h} {g['lamH']:.2f}   total {g['lamT']:.2f} (incl. empty-net allowance)\n"
            f"Regulation          {a} {pct(g['pA_reg'])}   tie {pct(g['pT'])}   {h} {pct(g['pH_reg'])}\n"
            f"Win incl. OT        {a} {pct(g['pA'])}   {h} {pct(g['pH'])}"
            + (f"   ·   Sportradar {h} {g['sr']:.1f}%" if g['sr'] else '') + "\n"
            f"texas222 no-vig     {a} {pct(mA)}   {h} {pct(mH)}   total {tot_line:g}")
    proj_score = f"{h} {round(g['lamH']):d}, {a} {round(g['lamA']):d}" if g['lamH'] >= g['lamA'] else f"{a} {round(g['lamA']):d}, {h} {round(g['lamH']):d}"
    gcard = lambda gx, team, side: f"""<div class='card'><h3><span class='{'tmA' if side=='A' else 'tmH'}'>{esc(gx[0])}</span>, {team} · {gx[1]}</h3>
<div class='scroll' style='margin-top:9px'><table><thead><tr><th>Window</th><th>Starts</th><th>Record</th><th>GAA</th><th>SV%</th></tr></thead><tbody>
{"<tr><td>Season</td><td class='num'>%d</td><td class='num'>%s</td><td class='num'>%.2f</td><td class='num'>%.3f</td></tr>" % (gx[2]['gs'], gx[2]['rec'], gx[2]['gaa'], gx[2]['sv']) if gx[2] else "<tr><td colspan='5' class='none'>No NHL starts this season. No sample: the card assumes a below-league save rate.</td></tr>"}
<tr><td>Used on card</td><td class='num'>regressed</td><td class='num'>·</td><td class='num'>·</td><td class='num'>{gx[3]:.3f}</td></tr>
</tbody></table></div>
<ul class='nl'><li><b>Sample:</b> about {gx[4]:.0f} shots faced this season, regressed with 900 shots at league {LG['lg_sv']:.3f}.</li>
<li><b>Doubt:</b> {'status is not confirmed; a goalie change re-prices the game.' if gx[1] in ('Unconfirmed','Projected','Likely') else 'confirmed starter; the regression is the main uncertainty.'}</li></ul></div>"""
    team_sv_line = lambda T: f"{T['ga']:.2f} GA on {T['sa']:.1f} SA"
    return f"""
<section class='panel' id='panel-{tid}' role='tabpanel' aria-labelledby='tab-{tid}' style='--AWAY:{COLORS[a][0]};--AWAYD:{COLORS[a][1]};--HOME:{COLORS[h][0]};--HOMED:{COLORS[h][1]}' hidden>
<div class='top'><h2 class='gh'><a class='tmA tl' href='{URL[a]}' target='_blank' rel='noopener'>{esc(NAMES[a])}</a> <span class='at'>at</span> <a class='tmH tl' href='{URL[h]}' target='_blank' rel='noopener'>{esc(NAMES[h])}</a></h2></div>
<div class='sub'>Sun Nov 15, 2026 · {g['time']} Phoenix · {esc(g['venue'])} · {a} {A['rec']}, {h} {H['rec']} · Goalies: {esc(gA[0])} ({gA[1]}) vs {esc(gH[0])} ({gH[1]}) · NHL API 6:30 AM pull, The Odds API read 6:38 AM Phoenix</div>
<div class='nav'>{nav}</div>
{pk_html}

<h3 class='sh' id='{sec('dec')}'>0 · Price check vs texas222</h3>
<div class='sub'>This table only asks whether texas222's price beats a fair price for each market. The card's picks, marked <span class='tag t-a'>Card pick</span>, come from the signal scoring above. "Fair price" means no extra edge in the number, not that the pick is wrong. Skater props are picked on price, so their PLAY or LEAN is the pick.</div>
<div class='scroll'><table>
<thead><tr><th>Market</th><th>texas222</th><th>Est.</th><th>Break-even</th><th>Edge pts</th><th>Price grade</th><th>Conf</th><th>Why</th></tr></thead><tbody>{dec}</tbody></table></div>
<div class='card' style='margin-top:12px'><b>Correlation flags.</b> {corr_txt}</div>

<h3 class='sh' id='{sec('audit')}'>⚠ · Preview audit</h3>
<div class='scroll'><table><thead><tr><th>Claim</th><th>Source</th><th>What the data says</th></tr></thead><tbody>{audit}</tbody></table></div>
<div class='card flag' style='margin-top:10px'><h4>The one that matters</h4>{flag}</div>

<h3 class='sh' id='{sec('env')}'>1 · Venue &amp; schedule</h3>
<div class='card'><table class='kv'><tbody>
<tr><td>Venue</td><td>{esc(g['venue'])}. Indoor; weather does not apply.</td></tr>
<tr><td>Puck drop</td><td>{g['time']} Phoenix</td></tr>
<tr><td>{a} rest</td><td>{rest_txt(A)} · last game {esc(A['last'])}</td></tr>
<tr><td>{h} rest</td><td>{rest_txt(H)} · last game {esc(H['last'])}</td></tr>
</tbody></table></div>

<h3 class='sh' id='{sec('sp')}'>2 · Goalie deep dive</h3>
{gcard(gA, a, 'A')}
{gcard(gH, h, 'H')}

<h3 class='sh' id='{sec('exit')}'>3 · Recent form</h3>
<div class='card'><div class='calc'>{a}   {A['rec']}   last 5: {last5(A)}
{h}   {H['rec']}   last 5: {last5(H)}
{a} goals by game  {' '.join(map(str,A['gfl']))}   (median {sorted(A['gfl'])[len(A['gfl'])//2]})
{h} goals by game  {' '.join(map(str,H['gfl']))}   (median {sorted(H['gfl'])[len(H['gfl'])//2]})</div>
<ul class='nl'><li>Early-season samples ({A['gp']} and {H['gp']} games). One blowout moves a per-game average by half a goal; the medians are printed for that reason.</li></ul></div>

<h3 class='sh' id='{sec('lineups')}'>4 · Team context</h3>
<div class='scroll'><table class='cmp'><thead><tr><th></th><th class='ca'><span class='tmA'>{esc(NAMES[a])}</span></th><th class='ch'><span class='tmH'>{esc(NAMES[h])}</span></th></tr></thead><tbody>{ctx}</tbody></table></div>
<div class='card' style='margin-top:10px'><b>The thing that decides it:</b> {decider}</div>

<h3 class='sh' id='{sec('proj')}'>5 · Projection &amp; total</h3>
<div class='card'><div class='calc'>{calc}</div>
<div class='lbl'>Win probability</div><table style='margin-top:6px'><tbody>{bars}</tbody></table>
<div class='lbl'>Projected score</div><ul class='nl'><li>{proj_score}</li></ul>
<div class='lbl'>Public split</div><ul class='nl'><li>{pub}</li></ul>
<div class='lbl'>What makes me doubt the read</div><ul class='nl'><li>Every team has 7 to 11 games. Shot and shooting rates are regressed, but an early sample still drives most of the gap from the market.</li><li>Goalie regression assumes everyone is a league-average goalie underneath. Elite or replacement-level talent breaks that.</li><li>Poisson team goals understate late empty-net goals, which matter most for puck lines and favorite team-total overs.</li></ul></div>

<h3 class='sh' id='{sec('tt')}'>6 · Team totals</h3>
<div class='scroll'><table><thead><tr><th>Market</th><th>texas222</th><th>Est.</th><th>Break-even</th><th>Edge pts</th><th>Price grade</th><th>Conf</th><th>Basis</th></tr></thead><tbody>{tt_rows()}</tbody></table></div>

<h3 class='sh' id='{sec('first')}'>7 · 1st period, 3-way &amp; score first</h3>
<div class='scroll'><table><thead><tr><th>Market</th><th>texas222</th><th>Est.</th><th>Break-even</th><th>Edge pts</th><th>Price grade</th><th>Conf</th><th>Basis</th></tr></thead><tbody>{p1_rows()}</tbody></table></div>
<div class='card' style='margin-top:10px'><ul class='nl'><li>1st period goals by game: {a} games {' '.join(map(str,A['p1l']))} · {h} games {' '.join(map(str,H['p1l']))} (both teams combined in each game).</li><li>texas222 also posts 1P moneyline and ±0.5 lines; they follow the same 1P rate and are not graded separately.</li></ul></div>

<h3 class='sh' id='{sec('pprops')}'>8 · Shot props: fair prices</h3>
<div class='card flag'><b>texas222 posts no NHL player props.</b> Its props builder lists Finland, Russia and AHL hockey only. Use these fair prices to shop other books: bet an over only at or better than the fair price shown. Graded prices found today are in section 0.</div>
<div class='scroll'><table><thead><tr><th>Player</th><th>Line</th><th>Record</th><th>SOG/g → tonight</th><th>Rate est.</th><th>Blend</th><th>Fair</th></tr></thead><tbody>{sog_table()}</tbody></table></div>

<h3 class='sh' id='{sec('bprops')}'>9 · Point &amp; goal props: fair prices</h3>
<div class='scroll'><table><thead><tr><th>Player</th><th>G-A-P</th><th>Point record</th><th>o0.5 pts</th><th>Fair</th><th>Goal record</th><th>Anytime goal · fair</th><th>PP pts</th></tr></thead><tbody>{pts_table()}</tbody></table></div>
<div class='card' style='margin-top:10px'><ul class='nl'><li>Points and assists on one player are nested markets. Take one per player.</li><li>Every record here is under 12 games. Below 10 games the record is shown without a rate, and nothing grades above MED.</li></ul></div>

<h3 class='sh' id='{sec('exp')}'>10 · Expert picks (named only)</h3>
<div class='scroll'><table><thead><tr><th>Expert</th><th>Pick</th><th>Price</th></tr></thead><tbody>{exp}</tbody></table></div>
<div class='card' style='margin-top:10px'><ul class='nl'><li>No published records for these writers; reported for information only, never as evidence. Picks credited only to a site or a model are excluded unless used purely as a price.</li></ul></div>

<h3 class='sh' id='{sec('frame')}'>11 · Correlation &amp; framework</h3>
<div class='card'><div class='lbl'>Carried</div><ul class='nl'>{''.join(f"<li>{esc(r.get('m') or (r['pl']+' '+r['lab']))} at {fmt(r['price'])}: {r['call']}, {r['edge']:+.1f} pts</li>" for r in carry) or '<li>Nothing. No bet is a valid output.</li>'}</ul>
<div class='lbl'>Phase &amp; gate</div><ul class='nl'><li>Hand-read NHL card. No NHL model backtest or promotion gate exists yet, so calibration is unmeasured: estimates are 40% model, 60% texas222 no-vig, and nothing grades HIGH.</li><li>Track in its own bucket, never pooled with the MLB or football ledgers.</li><li>Re-run if any goalie marked Likely, Unconfirmed or Projected changes.</li></ul></div>

<details><summary>What was left out, and why</summary><ul class='nl'>
<li>texas222 player props: not offered for NHL.</li>
<li>Per-player shots are total shots on goal from NHL game logs; time-on-ice and line deployment for tonight were not pulled.</li>
<li>Team ranks are not shown: only the 24 teams on tonight's slate were pulled, so a rank would be a slate rank, not a league rank.</li>
<li>Grand Salami, 2nd and 3rd period lines, alternate puck lines and score-last props were not graded.</li>
<li>Line movement: one texas222 read only; no opening number.</li>
</ul></details>
</section>"""

panels = ''.join(game_panel(i, g) for i, g in enumerate(games))

# ---------------- slate overview
order = {'PLAY':0,'LEAN':1}
ALLROWS.sort(key=lambda r: (order[r[5]], -r[4]))
GT2 = {f"{g['a']}-{g['h']}": g['time'] for g in games}
ov_rows = ''.join(f"<tr><td><a class='glink' href='#{tid}' data-tab='{tid}'>{esc(k.replace('-',' @ '))}</a></td><td class='num'>{GT2[k]}</td><td><b>{esc(m)}</b></td><td class='num'>{esc(ps)}</td><td class='num'>{pct(est)}</td><td class='num'>{edge:+.1f}</td><td class='{CALLCLS[c]}'>{lbl}</td><td><span class='tag {tag(cf)}'>{cf}</span></td></tr>" for k, m, ps, est, edge, c, cf, tid, lbl in ALLROWS)
slate_games = ''.join(f"<tr><td><a class='glink' href='#{g['a'].lower()}-{g['h'].lower()}' data-tab='{g['a'].lower()}-{g['h'].lower()}'>{g['a']} @ {g['h']}</a></td><td class='num'>{g['time']}</td><td>{esc(g['gA'][0])} ({g['gA'][1]}) vs {esc(g['gH'][0])} ({g['gH'][1]})</td><td class='num'>{fmt(g['la']['ml'])} / {fmt(g['lh']['ml'])}</td><td class='num'>{(g['la']['tot'] if g['la']['tot'][0]=='O' else g['lh']['tot'])[1]:g}</td><td class='num'>{g['lamA']:.2f} – {g['lamH']:.2f}</td><td class='num'>{pct(g['pH'])}</td></tr>" for g in games)
GT = {f"{g['a']}-{g['h']}": g['time'] for g in games}
def why_html(x):
    if '. Against: ' not in x: x = x + '. Against: none found'
    parts = x.split('. Against: ')
    return esc(parts[0]) + (f". <b class='ag'>Against:</b> <span class='agt'>{esc(parts[1])}</span>" if len(parts) > 1 else '')
def _cell(p, why=''):
    if not p or p.get('nopick'): return "<span class='np'>No pick</span>"
    tg = f" <span class='tag {TIERCLS[p['tier']]}'>{p['tier']}</span>" if p.get('tier') else ''
    cf = " <span class='tag t-d'>conflicting</span>" if p.get('conf') else ''
    return f"<b>{esc(p['text'])}</b> <span class='num'>{fmt(p['price'])}</span>{tg}{cf}<div class='rl'>{esc(RL.RULES[p['rule']]['short'])}</div>" + (f"<div class='cwhy'><b>Why:</b> {why}</div>" if why else '')
def _why(x):
    parts = []
    m, pl = x['ml'], x['pl']
    if m and not m.get('nopick'): parts.append(f"<b>{esc(m['team'])} ML:</b> {why_html(m['short'])}.")
    else: parts.append(f"<b>ML:</b> {esc(m['why'])}")
    if pl and not pl.get('nopick'): parts.append(f"<b>{esc(pl['team'])} {'+1.5' if pl['line'] > 0 else '-1.5'}:</b> sharp money on its moneyline.")
    t = x['tot']
    if t and not t.get('nopick'): parts.append(f"<b>{esc(t['text'])}:</b> division matchup.")
    return '<br>'.join(parts)
def _totwhy(x):
    c = x.get('c') or {}
    da, dh = c.get('div_a'), c.get('div_h')
    t = x['tot']; ag = ', '.join(dict.fromkeys(s_.replace(' (info only)', '') for _, s_, _ in (t.get('against') or [])))
    tl = (t.get('note') or '').split(';')[0]
    base = (f"{da} vs {dh} game; Overs in these matchups won in the season review" if {da, dh} == {'Atlantic', 'Pacific'} else "division strength signal is 2 points")
    return why_html(base + '. Against: ' + (ag if ag else 'none found')) + '.'
pk_rows = ''.join(f"<tr><td><a class='glink' href='#{x['key'].lower()}' data-tab='{x['key'].lower()}'>{esc(x['key'].replace('-',' @ '))}</a></td><td class='num'>{GT[x['key']]}</td><td>{_cell(x['ml'], why_html(x['ml'].get('short','')) + '.' if x['ml'] and not x['ml'].get('nopick') else '')}</td><td>{_cell(x['pl'], why_html(x['pl']['short']) + '.' if x['pl'] and not x['pl'].get('nopick') else '')}</td><td>{_cell(x['tot'], _totwhy(x) if x['tot'] and not x['tot'].get('nopick') else '')}</td></tr>" for x in PICKS)
pp_rows = ''.join(f"<tr><td><a class='glink' href='#{tid}' data-tab='{tid}'>{esc(k.replace('-',' @ '))}</a></td><td class='num'>{tm}</td><td><b>{esc(x['pl'])} {esc(x['lab'])}</b></td><td class='num'>{fmt(x['price'])} · {esc(x['book'])}</td><td class='{CALLCLS[x['call']]}'>{x['call']}</td><td class='num'>{pct(x['est'])} vs {pct(be(x['price']))}</td><td class='whyc'>{esc(x['basis'])}</td></tr>" for k, tid, tm, x in sorted(PROPPICKS, key=lambda z: (z[3]['call'] != 'PLAY', -z[3]['edge'])))
props_tbl = f"<h3 class='sh'>Player prop picks</h3><div class='scroll'><table><thead><tr><th>Game</th><th>Puck drop (Phoenix)</th><th>Prop</th><th>Price · book</th><th>Call</th><th>Projected vs needed</th><th>Why</th></tr></thead><tbody>{pp_rows or "<tr><td colspan='7' class='none'>No prop picks tonight.</td></tr>"}</tbody></table></div><div class='sub' style='margin-top:8px'>texas222 does not post NHL player props, so these are priced at the book shown from today's previews. PLAY clears break-even by 3+ points with record and rate agreeing; LEAN is a smaller or less certain edge.</div>"
READ_TIME = '7:00 AM'
_RCP = D/'review'/'recheck.json'
RC = json.loads(_RCP.read_text()) if _RCP.exists() else None
def _rc_cell(a):
    if not a or (not a['n'] and not a['p']): return '·'
    if not a['n']: return f"0-0-{a['p']}"
    return f"{a['w']}-{a['l']}" + (f"-{a['p']}" if a['p'] else '') + f" · {100*a['wp']:.0f}% · {a['u']:+.1f}u"
def _rc_td(a):
    cls = '' if not a or not a['n'] else (' pos' if a['u'] > 0 else (' neg' if a['u'] < 0 else ''))
    return f"<td class='num r{cls}'>{_rc_cell(a)}</td>"
if RC:
    RC_ASOF = datetime.date.fromisoformat(RC['as_of']).strftime('%b %-d')
    _bits = (['<b>Re-check changes:</b> ' + esc('; '.join(RC['changes']))] if RC['changes'] else []) + (['<b>Warnings:</b> ' + esc('; '.join(RC['warnings']))] if RC['warnings'] else [])
    RC_LINE = ' '.join(_bits) if _bits else 'Daily re-check: no rule changes and no warnings.'
    _M = RC['months']
    _rr = []
    for k in RL.ORDER:
        st = RC['state'][k]; v = st['version']; ov = 'strict' if v == 'base' else 'base'; a = RC['records'][k][v]; o = RC['records'][k][ov]; gk = RC['g'][k]
        _rr.append(f"<tr><td><b>{k}</b> {esc(st['market'])}: {esc(st['label'])}</td><td>{'On' if st['status']=='on' else 'Off (tracked)'}</td><td>{'Base' if v=='base' else 'Stricter'}</td>"
                   + _rc_td(a['season']) + ''.join(_rc_td(a.get(m)) for m in _M) + _rc_td(a['L14']) + _rc_td(a['since']) + _rc_td(o['since'])
                   + f"<td class='num'>DraftKings open {_rc_cell(gk['dk_open'])}<br>Card texas222 {_rc_cell(gk['card'])}</td></tr>")
    RC_RULES = (f"<h3 class='sh'>Rule records: backtest (daily re-check)</h3><div class='sub' style='margin-bottom:8px'>A backtest, not the card's own picks: every game this season through {RC_ASOF}, scored as if the rule always existed, with end-of-day Action Network signals and closing prices (SBR book medians). Rerun each morning before the card. "
                f"A rule switches off at 20+ picks with negative season units and back on when they turn positive. It moves to its other version only after that version has 30+ picks since approval (Oct 30), wins as often, makes more units, and is positive since approval and this month. "
                f"Pick-time check: the same picks at DraftKings opening prices and at the card's own texas222 prices.</div>"
                f"<div class='scroll'><table class='rt rcr'><thead><tr><th>Rule</th><th>Status</th><th>Version</th><th class='r'>Season</th>" + ''.join(f"<th class='r'>{esc(m)}</th>" for m in _M)
                + "<th class='r'>Last 14 days</th><th class='r'>Since approval</th><th class='r'>Other version since approval</th><th>Pick-time check</th></tr></thead><tbody>" + ''.join(_rr) + "</tbody></table></div>"
                + (f"<div class='sub' style='margin-top:6px'>{RC_LINE}</div>"))
    _sec = []
    for sec, lst in RC['tests'].items():
        trs = ''.join(f"<tr><td>{esc(n)}</td>" + _rc_td(o['season']) + (f"<td class='num r'>{(100*o['season']['be']):.1f}%</td>" if o['season']['be'] else "<td class='num r'>·</td>") + ''.join(_rc_td(o.get(m)) for m in _M) + _rc_td(o['L14']) + f"<td>{'Yes' if o['qual'] else 'No'}</td></tr>"
                      for n, o in lst if o['season']['n'] or o['season']['p'])
        _sec.append(f"<details class='rd'><summary>{esc(sec)} <span class='num'>({sum(1 for n, o in lst if o['qual'])} qualify)</span></summary><div class='scroll'><table class='rt rct'><thead><tr><th>Test</th><th class='r'>Season</th><th class='r'>Break-even</th>"
                    + ''.join(f"<th class='r'>{esc(m)}</th>" for m in _M) + "<th class='r'>Last 14 days</th><th>Qualifies</th></tr></thead><tbody>" + trs + "</tbody></table></div></details>")
    ck = RC['checks']
    RC_TESTS = (f"<h3 class='sh'>Re-check test tables</h3><div class='sub' style='margin-bottom:8px'>All tests a to f on every game through {RC_ASOF}. A test qualifies at 5+ picks with positive units and a win % above break-even. "
                f"Data: {ck['games']} games, DraftKings finals match {ck['dk_final_match']}/{ck['dk_join']}, opening lines agreed by Action Network and DraftKings in {ck['open_agree']}, card ledger finals match {ck['ledger_finals_match']}/{ck['ledger_rows']}. "
                f"Experts, injuries before Oct 22, morning splits and goalie confirmations cannot be rebuilt for past games; the card logs its pick-time inputs daily from Oct 30.</div>" + ''.join(_sec))
else:
    RC_ASOF, RC_LINE, RC_RULES, RC_TESTS = '·', '', '', ''
_TR = (RC or {}).get('trackers') or {}
if _TR:
    _M2 = RC['months']
    _trr = ''.join(f"<tr><td>{esc(k.split(' | ')[0])}</td><td>{esc(k.split(' | ')[1])}</td>" + _rc_td(v['season']) + ''.join(_rc_td(v.get(m)) for m in _M2) + _rc_td(v['L14']) + f"<td class='num r'>{v['season']['n']}/60</td></tr>" for k, v in _TR.items())
    RC_TRACK = (f"<h3 class='sh'>Fatigue trackers (tracking only)</h3><div class='sub' style='margin-bottom:8px'>Added Nov 3 at Trina's request after the fatigue test. These never make picks. The back the tired team line (Nov 11) is the reverse of the fade line, logged daily as would-be picks FATIGUE_BACK_ML and FATIGUE_BACK_PL. "
                f"Every game this season at closing prices through {RC_ASOF}. Each line is reviewed with Trina at 60 picks. The card's existing fatigue handling stays: a 3% goal adjustment for a team on a back-to-back and 1 Rest edge point for its opponent, home or away.</div>"
                f"<div class='scroll'><table class='rt rcr'><thead><tr><th>Tracker</th><th>Market</th><th class='r'>Season</th>" + ''.join(f"<th class='r'>{esc(m)}</th>" for m in _M2)
                + "<th class='r'>Last 14 days</th><th class='r'>Picks toward review</th></tr></thead><tbody>" + _trr + "</tbody></table></div>")
else:
    RC_TRACK = ''
PAGE_NOTE = ""  # clear on the next card run
_rr_cells = ''.join(f"<td><div class='rrc'><span class='rl'>{esc(RL.RULES[k]['short'])}</span><br>{rec_span(k).replace(' · Live', '<br>Live')}</div></td>" for k in RL.ORDER)
rule_row = (f"<tr class='rulerow'><td colspan='2'><b>Rule records</b><br><span class='dw' style='margin-left:0'>Same for every game. <b>Backtest</b>: every game this season at closing prices, through {RC_ASOF}. <b>Live</b>: the card's own graded picks since Oct 30 at texas222 prices.</span></td>{_rr_cells}</tr>")
picks_tbl = f"{PAGE_NOTE}<h3 class='sh'>Tonight's picks</h3><div class='scroll'><table><thead><tr><th>Game</th><th>Puck drop (Phoenix)</th><th>Moneyline</th><th>Puck line</th><th>Total</th></tr></thead><tbody>{rule_row}{pk_rows}</tbody></table></div><div class='sub' style='margin-top:8px'>{RULES_NOTE} The first row shows each rule's records; they are the same for every game. Every pick shows its tier: the pick side's lead in signal points, counting the signals that trigger the rule (Sharp Action is 2 points; the total rule's division matchup counts 2 points for the over). <span class='tag tg-strong'>Strong</span> 4+, <span class='tag tg-solid'>Solid</span> 2 to 3, <span class='tag tg-lean'>Lean</span> 0 to 1 or behind. The tier does not change whether a rule picks. {RC_LINE} Signals read about {READ_TIME} Phoenix. Season results by rule are in the Results tab.</div>"

results_panel = """
<section class='panel' id='panel-results' role='tabpanel' aria-labelledby='tab-results' hidden>
<div class='sub'>Season tracker for every card pick since Oct 22, 2026, graded from final scores and box scores each day. Picks before Oct 29 used one side-or-puck-line pick and one total per game (method: Before the rules). From Oct 29 the card follows the approved pick rules (method: Rules; the current rule set started Oct 30). Player prop picks (PLAY or LEAN) are method: Props. Tables below count card picks only; tracked picks for switched-off rules and Oct 29 watch-list picks appear only in By rule. Units assume 1 unit risked per pick at the texas222 price shown on the card.</div>
<div id='res-state' class='card'>Loading the pick ledger…</div>
<div id='res-body' hidden>
<div class='tiles' id='res-tiles'></div>
<dialog id='pend-dlg' class='pend-dlg' aria-labelledby='pend-h'><div class='pend-hd'><h3 id='pend-h'>Pending picks</h3><button type='button' class='pend-x' id='pend-x' aria-label='Close'>Close</button></div><ul id='pend-list' class='pend-list'></ul></dialog>
<h3 class='sh'>By rule: live card picks</h3><div class='sub' style='margin-bottom:8px'>The card's own logged picks at texas222 prices, by rule and month. These are the real picks; the backtest is further down. Current rules started Oct 30. Oct 29 picks used the first rule set (moneyline needed a lead of 3+) and have their own rows. Picks made before the rules are grouped as <b>Before the rules</b>. Tracked picks for a switched-off rule count here.</div><div class='scroll'><table class='rt byrule'><thead id='res-rule-h'></thead><tbody id='res-rule'></tbody></table></div>
<h3 class='sh'>By tier</h3><div class='scroll'><table class='rt'><thead><tr><th>Tier</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-tier'></tbody></table></div>
<h3 class='sh'>By market</h3><div class='scroll'><table class='rt'><thead><tr><th>Market</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-mkt'></tbody></table></div>
<h3 class='sh'>Market results by tier</h3><div class='sub' style='margin-bottom:8px'>Each market split by tier, with the market total on its first row. Follows the filters below.</div><div class='scroll'><table class='rt mxt'><thead><tr><th>Market · tier</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-mxt'></tbody></table></div>
<h3 class='sh'>Filter</h3>
<div class='filters' id='filters'>
<details class='ms' data-f='date'><summary><span class='fl'>Date</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='dow'><summary><span class='fl'>Day of week</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='team'><summary><span class='fl'>Team</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='method'><summary><span class='fl'>Method</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='market'><summary><span class='fl'>Market</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='tier'><summary><span class='fl'>Tier</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='result'><summary><span class='fl'>Result</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<button type='button' id='f-clear'>Clear filters</button>
</div>
<div class='card ftot' id='f-tot'></div>
<details class='rd' id='d-log'><summary>Every pick <span class='num' id='c-log'></span></summary><div class='scroll'><table class='rt log'><thead><tr><th>Date</th><th>Game</th><th>Market</th><th>Pick</th><th class='r'>Price</th><th>Tier</th><th>Final</th><th>Result</th><th class='r'>Units</th></tr></thead><tbody id='res-log'></tbody><tfoot id='res-log-tot'></tfoot></table></div></details>
</div>
""" + RC_RULES + RC_TRACK + RC_TESTS + """
</section>"""

tabs = "<button class='tab' role='tab' id='tab-slate' aria-controls='panel-slate' data-tab='slate'>Slate</button>" + "<button class='tab' role='tab' id='tab-standings' aria-controls='panel-standings' data-tab='standings'>Standings<span>Cup odds</span></button>" + ''.join(
    f"<button class='tab' role='tab' id='tab-{g['a'].lower()}-{g['h'].lower()}' aria-controls='panel-{g['a'].lower()}-{g['h'].lower()}' data-tab='{g['a'].lower()}-{g['h'].lower()}' aria-label='{g['a']} at {g['h']}'>{g['a']} @ {g['h']}<span>{g['time'].replace(' PM','')}</span></button>" for g in games) + "<button class='tab' role='tab' id='tab-results' aria-controls='panel-results' data-tab='results'>Results<span>Season tracker</span></button>"

RESULTS_JS = r'''
<script>
function labelTables(root){
  [].slice.call((root||document).querySelectorAll('.scroll > table')).forEach(function(t){
    if(t.classList.contains('cmp')||t.classList.contains('stand')||(t.classList.contains('rt')&&!t.classList.contains('log'))) return;
    t.classList.add('stack');
    var hs=[].slice.call(t.querySelectorAll('thead th')).map(function(th){return th.textContent.trim();});
    [].slice.call(t.querySelectorAll('tbody tr, tfoot tr')).forEach(function(tr){
      var i=0; [].slice.call(tr.children).forEach(function(td){ var span=+(td.getAttribute('colspan')||1); if(span===1&&hs[i]) td.setAttribute('data-label',hs[i]); if(!(td.children.length===1&&td.firstElementChild.classList.contains('cv'))&&td.childNodes.length){ var w=document.createElement('div'); w.className='cv'; while(td.firstChild) w.appendChild(td.firstChild); td.appendChild(w);} i+=span; });
    });
  });
}
labelTables();
</script>
<script>
(function(){
  var $=function(id){return document.getElementById(id)};
  var TCL={'Strong':'tg-strong','Solid':'tg-solid','Lean':'tg-lean'};
  function units(p){ if(p.result==='win') return p.price>0? p.price/100 : 100/(-p.price); if(p.result==='loss') return -1; return 0; }
  function agg(rows){ var o={w:0,l:0,p:0,u:0,pend:0,pr:[]}; rows.forEach(function(x){ if(x.result==='win')o.w++; else if(x.result==='loss')o.l++; else if(x.result==='push')o.p++; else {o.pend++; o.pr.push(x);} o.u+=units(x); }); return o; }
  var PS=[]; function pb(o,label){ if(!o.pend) return '0'; PS.push({rows:o.pr,label:label||''}); return '<button type="button" class="pendbtn" data-p="'+(PS.length-1)+'" aria-label="Show '+o.pend+' pending picks">'+o.pend+'</button>'; }
  function pct(o){ var n=o.w+o.l; return n? (100*o.w/n).toFixed(1)+'%' : '·'; }
  function u(v){ return (v>0?'+':'')+v.toFixed(2)+'u'; }
  function row(label,o){ var c=o.u>0?'pos':(o.u<0?'neg':''); return '<tr><td>'+label+'</td><td class="num r">'+o.w+'</td><td class="num r">'+o.l+'</td><td class="num r">'+o.p+'</td><td class="num r">'+pct(o)+'</td><td class="num r '+c+'">'+u(o.u)+'</td><td class="num r">'+pb(o,label.replace(/<[^>]+>/g,''))+'</td></tr>'; }
  function txt(s){ var d=document.createElement('span'); d.textContent=s==null?'':String(s); return d.innerHTML; }
  function group(rows,key,order){ var m={}; rows.forEach(function(x){ (m[x[key]]=m[x[key]]||[]).push(x); }); var ks=order||Object.keys(m).sort(); return ks.filter(function(k){return m[k]}).map(function(k){return row(txt(k),agg(m[k]));}).join(''); }
  function mxt(rows){ var TI={'Moneyline':['Strong','Solid','Lean'],'Puck line':['Strong','Solid','Lean'],'Total':['Strong','Solid','Lean'],'Prop':['PLAY','LEAN']}; var h='';
    Object.keys(TI).forEach(function(mk){ var mr=rows.filter(function(x){return x.market===mk;}); if(!mr.length) return;
      h+=row('<b>'+txt(mk)+'</b> · all',agg(mr)).replace('<tr>','<tr class="mxt-head">');
      TI[mk].forEach(function(t){ var tr=mr.filter(function(x){return x.tier===t;}); if(tr.length) h+=row('<span class="mxt-tier">'+txt(t)+'</span>',agg(tr)); }); });
    return h||'<tr><td colspan="7" class="none">No picks match these filters.</td></tr>'; }
  var RULEMETA=__RULEMETA__;
  function meth(x){ return x.rule? 'Rules' : (x.market==='Prop'?'Props':'Before the rules'); }
  function mon(d){ var M=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']; return M[+d.slice(5,7)-1]+' '+d.slice(0,4); }
  function recTxt(o){ return o.w+'-'+o.l+(o.p?'-'+o.p:'')+', '+u(o.u); }
  function rkey(x){ if(x.market==='Prop') return null; if(!x.rule) return 'Before the rules · '+x.market; if(x.watch) return 'Watch list (Oct 29 only)'; if(x.date<'2026-10-30') return x.rule+' · Oct 29 rule set'; return x.rule; }
  function byRule(rows){
    var rr=rows.filter(function(x){return rkey(x);}); var per=[]; rr.forEach(function(x){ var p=mon(x.date); if(per.indexOf(p)<0) per.push(p); });
    per.sort(function(a,b){ return new Date('1 '+a)-new Date('1 '+b); });
    var keys=RULEMETA.order.slice(); rr.forEach(function(x){ var k=rkey(x); if(keys.indexOf(k)<0) keys.push(k); });
    $('res-rule-h').innerHTML='<tr><th>Rule</th><th>Status</th>'+per.map(function(p){return '<th class="r">'+txt(p)+'</th>';}).join('')+'<th class="r">Season</th><th class="r">Pending</th></tr>';
    $('res-rule').innerHTML=keys.map(function(id){ var m=RULEMETA.rules[id]; var mine=rr.filter(function(x){return rkey(x)===id;});
      var cells=per.map(function(p){ var g=mine.filter(function(x){return mon(x.date)===p;}); var o=g.length?agg(g):null;
        return '<td class="num r '+(o&&o.u>0?'pos':(o&&o.u<0?'neg':''))+'">'+(o&&(o.w+o.l+o.p)?recTxt(o):'·')+'</td>'; }).join('');
      var s=agg(mine);
      var lab=m? '<b>'+txt(id)+'</b> '+txt(m.market)+': '+txt(m.label)+' <span class="dw">(current rules, from Oct 30)</span>' : '<b>'+txt(id)+'</b>';
      var stt=m? (m.status==='on'?'On':'Off (tracked)') : ((id.indexOf('Watch')===0||id.indexOf('Oct 29 rule set')>0)?'Retired Oct 30':'Retired Oct 29');
      return '<tr><td>'+lab+'</td><td>'+txt(stt)+'</td>'+cells+'<td class="num r '+(s.u>0?'pos':(s.u<0?'neg':''))+'"><b>'+(s.w+s.l+s.p?recTxt(s):'·')+'</b></td><td class="num r">'+pb(s,id)+'</td></tr>'; }).join('');
  }
  var ALL=[]; var SEL={date:[],dow:[],team:[],method:[],market:[],tier:[],result:[]};
  var DOWS=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  function dow(d){ return DOWS[new Date(d+'T12:00:00').getDay()]; }
  function val(x,f){ if(f==='dow') return dow(x.date); if(f==='result') return x.result||'pending'; if(f==='method') return meth(x); return x[f]; }
  function optsFor(f,rows){
    if(f==='method') return ['Rules','Before the rules','Props'];
    if(f==='market') return ['Moneyline','Puck line','Total','Prop'];
    if(f==='tier') return ['Strong','Solid','Lean','PLAY','LEAN'];
    if(f==='result') return ['win','loss','push','pending'];
    if(f==='dow') return DOWS.filter(function(d){ return rows.some(function(x){return dow(x.date)===d;}); });
    var m={}; rows.forEach(function(x){ if(f==='team'){m[x.away]=1;m[x.home]=1;} else m[x[f]]=1; });
    var k=Object.keys(m).sort(); return f==='date'?k.reverse():k;
  }
  function fillOpts(rows){
    [].slice.call(document.querySelectorAll('#filters details.ms')).forEach(function(d){
      var f=d.dataset.f, vals=optsFor(f,rows); SEL[f]=SEL[f].filter(function(v){return vals.indexOf(v)>=0;});
      d.querySelector('.opts').innerHTML=vals.map(function(v,i){ var id='o-'+f+'-'+i; return '<label for="'+id+'"><input type="checkbox" id="'+id+'" value="'+txt(v)+'"'+(SEL[f].indexOf(v)>=0?' checked':'')+'> '+txt(f==='result'?v.charAt(0).toUpperCase()+v.slice(1):v)+'</label>'; }).join('');
      setLabel(d);
    });
  }
  function setLabel(d){ var f=d.dataset.f, n=SEL[f].length; d.querySelector('.fv').textContent = n===0?'All':(n===1?(f==='result'?SEL[f][0].charAt(0).toUpperCase()+SEL[f][0].slice(1):SEL[f][0]):n+' selected'); d.classList.toggle('on',n>0); }
  function applyF(){
    var rows=ALL.filter(function(x){ return Object.keys(SEL).every(function(f){ var s=SEL[f]; if(!s.length) return true; if(f==='team') return s.indexOf(x.away)>=0||s.indexOf(x.home)>=0; return s.indexOf(val(x,f))>=0; }); });
    var on=Object.keys(SEL).some(function(f){return SEL[f].length;}); var o=agg(rows);
    $('f-tot').innerHTML='<b>'+(on?'Filtered total':'All picks')+':</b> '+rows.length+' picks · '+o.w+'-'+o.l+(o.p?'-'+o.p:'')+' · win '+pct(o)+' · <span class="'+(o.u>0?'pos':(o.u<0?'neg':''))+'">'+u(o.u)+'</span> · '+pb(o,on?'Filtered picks':'All picks')+' pending';
    var sorted=rows.slice().sort(function(x,y){ return y.date.localeCompare(x.date) || x.game.localeCompare(y.game) || x.market.localeCompare(y.market); });
    $('res-log').innerHTML=sorted.length?sorted.map(function(x){ var r=x.result||'pending'; var cls=r==='win'?'t-a':(r==='loss'?'t-c':'t-d'); var uv=units(x);
      return '<tr><td class="num">'+txt(x.date)+' <span class="dw">'+dow(x.date).slice(0,3)+'</span></td><td>'+txt(x.game)+'</td><td>'+txt(x.market)+'</td><td><b>'+txt(x.pick)+'</b></td><td class="num r">'+(x.price>0?'+':'')+txt(x.price)+'</td><td>'+(TCL[x.tier]?'<span class="tag '+TCL[x.tier]+'">'+txt(x.tier)+'</span>':txt(x.tier))+(x.conflicting?' <span class="tag t-d">conflicting</span>':'')+'</td><td class="num">'+txt(x.final||'')+'</td><td><span class="tag '+cls+'">'+txt(r)+'</span></td><td class="num r '+(uv>0?'pos':(uv<0?'neg':''))+'">'+(r==='pending'?'·':u(uv))+'</td></tr>'; }).join(''):'<tr><td colspan="9" class="none">No picks match these filters.</td></tr>';
    $('res-log-tot').innerHTML=rows.length?'<tr><td colspan="8"><b>Total</b> · '+o.w+'-'+o.l+(o.p?'-'+o.p:'')+' · win '+pct(o)+' · '+pb(o,'Every pick')+' pending</td><td class="num r '+(o.u>0?'pos':(o.u<0?'neg':''))+'"><b>'+u(o.u)+'</b></td></tr>':'';
    $('res-mxt').innerHTML=mxt(rows);
    $('c-log').textContent='('+rows.length+' pick'+(rows.length===1?'':'s')+')';
    labelTables($('panel-results'));
  }
  $('filters').addEventListener('change',function(e){ var cb=e.target; if(cb.type!=='checkbox') return; var d=cb.closest('details.ms'), f=d.dataset.f;
    SEL[f]=[].slice.call(d.querySelectorAll('input:checked')).map(function(i){return i.value;}); setLabel(d); applyF(); });
  document.addEventListener('click',function(e){ [].slice.call(document.querySelectorAll('#filters details.ms[open]')).forEach(function(d){ if(!d.contains(e.target)) d.open=false; }); });
  $('f-clear').addEventListener('click',function(){ Object.keys(SEL).forEach(function(f){SEL[f]=[];}); fillOpts(ALL); applyF(); });
  document.addEventListener('click',function(e){ var b=e.target.closest&&e.target.closest('.pendbtn'); if(!b) return; var s=PS[+b.dataset.p]; if(!s) return;
    var rs=s.rows.slice().sort(function(x,y){ return x.date.localeCompare(y.date)||(x.time||'').localeCompare(y.time||'')||x.game.localeCompare(y.game); });
    $('pend-h').textContent='Pending picks'+(s.label?' · '+s.label:'')+' ('+rs.length+')';
    $('pend-list').innerHTML=rs.map(function(x){ return '<li><span class="pg">'+txt(x.game)+'</span><b>'+txt(x.pick)+'</b> <span class="pp">'+(x.price>0?'+':'')+txt(x.price)+'</span></li>'; }).join('');
    var d=$('pend-dlg'); if(d.showModal) d.showModal(); else d.setAttribute('open',''); });
  $('pend-x').addEventListener('click',function(){ $('pend-dlg').close(); });
  $('pend-dlg').addEventListener('click',function(e){ if(e.target===this) this.close(); });
  function render(all){
    var rows=all.filter(function(x){return !x.shadow && !x.watch;});
    if(!all.length){ $('res-state').textContent='No picks logged yet. Tonight’s picks are added after the card publishes.'; $('res-state').hidden=false; $('res-body').hidden=true; return; }
    $('res-state').hidden=true; $('res-body').hidden=false;
    PS=[]; var a=agg(rows);
    var tiles=[['Record', a.w+'-'+a.l+(a.p?'-'+a.p:'')],['Win %',pct(a)],['Units',u(a.u)],['Pending',pb(a,'All picks')]];
    $('res-tiles').innerHTML=tiles.map(function(t){return '<div class="tile"><div class="lbl">'+t[0]+'</div><div class="tv">'+t[1]+'</div></div>';}).join('');
    $('res-tier').innerHTML=group(rows,'tier',['Strong','Solid','Lean','PLAY','LEAN']);
    $('res-mkt').innerHTML=group(rows,'market',['Moneyline','Puck line','Total','Prop']);
    byRule(all);
    [].slice.call(document.querySelectorAll('.rlive')).forEach(function(sp){ var g=all.filter(function(x){return x.rule===sp.dataset.rule && !x.watch && !x.shadow && x.date>='2026-10-30';}); var o=agg(g); sp.innerHTML=(o.w+o.l+o.p)?(o.w+'-'+o.l+(o.p?'-'+o.p:'')+', <span class="'+(o.u>0.0001?'upos':(o.u<-0.0001?'uneg':''))+'">'+u(o.u)+'</span>'):'no graded picks yet'; });
    ALL=rows; fillOpts(rows); applyF(); labelTables($('panel-results'));
  }
  (async function(){
    var db=null; try{ db = window.claude && window.claude.use ? await window.claude.use('db') : null; }catch(e){ db=null; }
    if(!db){ $('res-state').textContent='The pick ledger is not available in this view. Sign in to claude.ai and open the card from its link to see results.'; return; }
    db.collection('picks').onSnapshot(function(s){ render(s.docs.map(function(d){return d.data();})); },
      function(e){ $('res-state').textContent='The pick ledger could not be loaded right now. Reload the page to try again.'; $('res-state').hidden=false; });
  })();
})();
</script>
'''
import json as _json
RESULTS_JS = RESULTS_JS.replace('__RULEMETA__', _json.dumps(dict(order=RL.ORDER, rules={k: dict(market=v['market'], label=v['label'], status=v['status']) for k, v in RL.RULES.items()})))
CSS = open(D/'card.css').read()
page = f"""<title>NHL Slate Card · Nov 15</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>{CSS}</style>
<div class='wrap'>
<header class='mast'><div><div class='eyebrow'>NHL game cards · Sunday, November 15, 2026</div><h1>5-game slate</h1></div>
<button id='tt-btn' type='button'>Toggle theme</button></header>
<div class='tabs' role='tablist'>{tabs}</div>

<section class='panel' id='panel-slate' role='tabpanel' aria-labelledby='tab-slate'>
<div class='sub'>Morning run, about 7:00 AM Phoenix. Lines: The Odds API median of all books, read 6:38 AM Phoenix (opening lines post at 7:09; 1st period lines and team totals included). Goalies from Daily Faceoff and RotoWire at about 7 AM; Action Network splits and sharp report read at 6:55 AM. No player props yet (posted after 10 AM; the 10:35 AM task adds them). Each game tab has the full card.</div>
{picks_tbl}
{props_tbl}
<h3 class='sh'>Price check: markets priced better than fair</h3>
<div class='scroll'><table><thead><tr><th>Game</th><th>Puck drop (Phoenix)</th><th>Market</th><th>Price · book</th><th>Est.</th><th>Edge pts</th><th>Price grade</th><th>Conf</th></tr></thead><tbody>{ov_rows or "<tr><td colspan='8' class='none'>No market priced better than fair tonight.</td></tr>"}</tbody></table></div>
<div class='sub' style='margin-top:9px'>A second view, separate from Tonight's picks: game markets where texas222's number beats a fair price (<b>Value</b> 3+ points over break-even at MED, <b>Slight value</b> 1.5 to 3), plus the prop picks. · <b>MED</b> both goalies confirmed or likely and, for props, record and rate agree · <b>LOW</b> a goalie is unconfirmed, a period market, or record and rate disagree. Nothing grades HIGH: no NHL backtest exists.</div>
<h3 class='sh'>Board</h3>
<div class='scroll'><table><thead><tr><th>Game</th><th>Phoenix</th><th>Goalies</th><th>ML (away / home)</th><th>Total</th><th>Proj. goals</th><th>Home win (model)</th></tr></thead><tbody>{slate_games}</tbody></table></div>
<div class='card' style='margin-top:12px'><div class='lbl'>How the numbers are built</div><ul class='nl'>
<li>Expected shots from each team's shots for and against (NHL API, regressed 5 games to league {LgS:.1f}), times a finishing factor (shooting % regressed 250 shots), times the opposing starter's save rate regressed with 900 shots to league {LG['lg_sv']:.3f}. Home ice ±3.5%, then each team's own home or road scoring and goals allowed (regressed 10 games to its season rate, relative to the league's home/road split, capped ±15%). Back-to-back: the tired team −3% and its opponent +3%.</li>
<li>Goals are Poisson; ties go to OT/shootout weighted by goal rate. Puck lines get an empty-net allowance on one-goal regulation leads.</li>
<li>Calibration is unmeasured, so every estimate is 40% model and 60% texas222 no-vig. Props blend the player's record with a rate estimate, then 60/40 with the posted price.</li>
<li>Skater props are not on texas222. Graded props use prices found in published previews today; everything else shows a fair price to shop against.</li></ul></div>
<div class='card flag'><b>Before betting:</b> confirm goalies marked Likely, Unconfirmed or Projected at warmups (UTA/SEA and DET/VAN especially). A goalie change voids that game's grades.</div>
</section>
{results_panel}
{standings_panel()}
{panels}
</div>
<script>
(function(){{
  var tabs=[].slice.call(document.querySelectorAll('.tab'));
  function show(id){{
    if(!document.getElementById('panel-'+id)) id='slate';
    tabs.forEach(function(t){{var on=t.dataset.tab===id; t.setAttribute('aria-selected',on); t.tabIndex=on?0:-1;}});
    [].slice.call(document.querySelectorAll('.panel')).forEach(function(p){{p.hidden = p.id!=='panel-'+id;}});
    var b=document.getElementById('tab-'+id); if(b&&b.scrollIntoView) b.scrollIntoView({{block:'nearest',inline:'center'}});
  }}
  tabs.forEach(function(t,i){{
    t.addEventListener('click',function(){{show(t.dataset.tab); try{{history.replaceState(null,'','#'+t.dataset.tab);}}catch(e){{}} window.scrollTo(0,0);}});
    t.addEventListener('keydown',function(e){{var k=e.key==='ArrowRight'?1:e.key==='ArrowLeft'?-1:0; if(k){{var n=tabs[(i+k+tabs.length)%tabs.length]; n.focus(); n.click();}}}});
  }});
  [].slice.call(document.querySelectorAll('.glink')).forEach(function(a){{a.addEventListener('click',function(e){{e.preventDefault(); show(a.dataset.tab); window.scrollTo(0,0);}});}});
  var h=(location.hash||'').slice(1); var base=h.split('-').slice(0,2).join('-');
  show(document.getElementById('panel-'+h)?h:(document.getElementById('panel-'+base)?base:'slate'));
  if(h && h!==base && document.getElementById(h)) document.getElementById(h).scrollIntoView();
  document.getElementById('tt-btn').addEventListener('click',function(){{
    var r=document.documentElement,cur=r.getAttribute('data-theme');
    var dark=cur?cur==='dark':window.matchMedia('(prefers-color-scheme: dark)').matches;
    r.setAttribute('data-theme',dark?'light':'dark');}});
}})();
</script>

{RESULTS_JS}
"""
(D/'nhl-slate.html').write_text(page)
print('rows', len(ALLROWS))
for r in ALLROWS: print(r[:7])
