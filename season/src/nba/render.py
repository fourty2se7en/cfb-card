import math, html, pathlib, re, json
from standings import panel as standings_panel, load as _st_load
from teams import URL, FULL
from context import loc_factor, b2b_factor, DIVNAME, FAT, HCA_MARGIN
from model import build, be, amer, fmt, novig, Phi, pois, p_ge, wilson, ROSTER, TRAVEL, INJ_ADJ, QUESTIONABLE
from signals import AN, WEIGHTS, LAST, MODELPROJ
import pickrules as PR
LOCKED_DOCS = json.loads((pathlib.Path(__file__).parent/'locked_picks.json').read_text()) if (pathlib.Path(__file__).parent/'locked_picks.json').exists() else {}
RSTATE = json.loads((pathlib.Path(__file__).parent/'rules_state.json').read_text()) if (pathlib.Path(__file__).parent/'rules_state.json').exists() else {}
DK = {}   # second opening source (DraftKings via ESPN core odds): AWAY-HOME|away spread open|away spread now|total open|total now
if (pathlib.Path(__file__).parent/'dk_raw.txt').exists():
    for _ln in (pathlib.Path(__file__).parent/'dk_raw.txt').read_text().strip().splitlines()[1:]:
        _f = _ln.split('|'); DK[_f[0]] = dict(sp_open_a=float(_f[1]), sp_now_a=float(_f[2]), tot_open=float(_f[3]), tot_now=float(_f[4]))

D = pathlib.Path(__file__).parent
DATE, DATE_S, DATE_L, DOW = '2026-11-17', 'Nov 17', 'Tuesday, November 17, 2026', 'Tue'
READ = 'Read Nov 17 about 4:45 PM Phoenix: The Odds API median of all books (opening read 7:13 AM for picks and prices, latest read 4:45 PM for line moves). No Action Network read today (no browser): splits neutral, no PRO signals.'
games, LG, PLAYERS, PROPS = build()
NAMES = FULL
NEWTEAM = set()
for _ln in (D/'players_raw.txt').read_text().strip().splitlines()[1:]:
    _f = _ln.split('|')
    if len(_f) > 9 and _f[9] not in ('-', _f[7]): NEWTEAM.add(_f[0])
for _pl, _P in PLAYERS.items():
    ROSTER.setdefault(_P['team'], []).append(_pl)

COLORS = {  # light, dark (text accents only, not logos)
 'GSV':('#3c1361','#b18be0'),'ATD':('#c8102e','#ff6b81'),
 'ATL':('#c8102e','#ff6b7a'),'BOS':('#007a33','#3ccf7a'),'BKN':('#2b2b2b','#c9c9c9'),'CHA':('#00788c','#38c6d9'),'CHI':('#ce1141','#ff5c7d'),
 'CLE':('#860038','#e05a8a'),'DAL':('#00538c','#5aa9ff'),'DEN':('#0e2240','#fec524'),'DET':('#c8102e','#ff6b7a'),'GSW':('#1d428a','#ffc72c'),
 'HOU':('#ce1141','#ff5c7d'),'IND':('#002d62','#fdbb30'),'LAC':('#c8102e','#6fa8ff'),'LAL':('#552583','#fdb927'),'MEM':('#5d76a9','#8fb3ff'),
 'MIA':('#98002e','#ff6b8a'),'MIL':('#00471b','#4fcf7f'),'MIN':('#0c2340','#78be20'),'NOP':('#0c2340','#c8a96e'),'NYK':('#006bb6','#f58426'),
 'OKC':('#007ac1','#5cc1ff'),'ORL':('#0077c0','#5cc1ff'),'PHI':('#006bb6','#5aa9ff'),'PHX':('#1d1160','#e56020'),'POR':('#c8102e','#ff6b7a'),
 'SAC':('#5a2d81','#b98bec'),'SAS':('#3a3a3a','#c4ced4'),'TOR':('#ce1141','#ff5c7d'),'UTA':('#4b2a7b','#a98be8'),'WAS':('#002b5c','#e31837'),
}

# Daily inputs: expert picks (named authors only), public handle notes, preview audit
EXPERTS = {}
for _x in json.loads((pathlib.Path(__file__).parent/'experts.json').read_text()):
    EXPERTS.setdefault(_x['game'], []).append((f"{_x['name']} ({_x['platform']})", _x['pick'] + (f", {_x['units']}" if _x.get('units') else ''), _x['price'] + (f" · {_x['record']}" if _x.get('record') else '')))
def _pub(k):
    S = AN[k]; a, h = k.split('-')
    sp_side = a if S['sp_bets'] >= 50 else h; sp_b = max(S['sp_bets'], 100-S['sp_bets'])
    ml_side = a if S['bets'] >= 50 else h; ml_b = max(S['bets'], 100-S['bets'])
    return (f"{sp_b}% of spread tickets on {sp_side}; {ml_b}% of moneyline tickets on {ml_side}; "
            f"{S['o_bets']}% of total tickets and {S['o_money']}% of total money on the over ({S['n_bets']:,} bets, Action Network).")
PUBLIC = {k: _pub(k) for k in AN}
NOTES = {
 'NYK-TOR':[('Same matchup two nights apart','ESPN schedule, injury report','New York won 112-108 in Toronto on Nov 15; Scottie Barnes (illness) is day-to-day and Kawhi Leonard (knee) is out for Toronto.')],
 'POR-MIN':[('Back-to-back in Minneapolis','ESPN schedule, injury report','Minnesota beat Portland 106-98 on Nov 16; both teams stay in Minneapolis. Minnesota is without Anthony Edwards, Jonathan Kuminga and Donte DiVincenzo; Deni Avdija (foot) is day-to-day for Portland.')],
 'DET-SAS':[('Detroit thin on the wing','ESPN injury report','Duncan Robinson, Jalen Duren, Ronald Holland II, Isaiah Joe and Taurean Prince are out for Detroit; San Antonio is without Tobias Harris.')],
 'UTA-LAC':[('Utah short handed','ESPN injury report','Lauri Markkanen, Jaxson Hayes, Jaren Jackson Jr. and Jusuf Nurkic are out for Utah; the Clippers are without Brandon Ingram and Bradley Beal.')],
 'CHA-LAL':[('Lakers without Reaves and Kessler','ESPN injury report','Austin Reaves (heel) and Walker Kessler (lower leg) are out for the Lakers; Charlotte is without Dennis Schroder and Kon Knueppel.')],
}

def esc(s): return html.escape(str(s))
def pct(p): return f'{100*p:.1f}%'
def tag(conf): return {'HIGH':'t-a','MED':'t-b','LOW':'t-c','NULL':'t-d'}[conf]
def grade(est, price, conf):
    e = 100*(est - be(price))
    if e >= 3.0 and conf in ('MED','HIGH'): call = 'PLAY'
    elif e >= 1.5: call = 'LEAN'
    else: call = 'PASS'
    return call, e
def sp(x): return f'{x:+g}'

ALLROWS, PROPPICKS, PICKS, LEDGER = [], [], [], []
HELDPROPS, PRICED_ALL, SCORES = [], {}, {}
SHADOW = {}
_PRS = json.loads((pathlib.Path(__file__).parent/'prop_rules_state.json').read_text()) if (pathlib.Path(__file__).parent/'prop_rules_state.json').exists() else {}
PROP_RULES_ON = {k: v['on'] for k, v in _PRS.get('rules', {}).items()}
CALLCLS = {'PLAY':'play','LEAN':'lean','PASS':'pass','HELD':'pass'}
PRICEL = {'PLAY':'Value','LEAN':'Slight value','PASS':'Fair price'}
TIERCLS = {'Strong':'t-a','Solid':'t-b','Thin':'t-c'}
_ST, _FUT = _st_load(); _STB = {x['t']: x for x in _ST}
# WNBA Finals teams: 2026 playoff record stands in for "this season" (stats.wnba.com playoff game log). Series price replaces title odds.
_STB.update({
 'GSV': dict(t='GSV', conf='W', div='WNBA Finals', w=8, l=3, gp=11, pct=8/11, rank=1, home='6-1', road='2-2', l10='7-3', strk='W2', ppg=77.9, oppg=76.0, diff=1.9),
 'ATD': dict(t='ATD', conf='E', div='WNBA Finals', w=7, l=3, gp=10, pct=0.7, rank=1, home='4-1', road='3-2', l10='7-3', strk='L2', ppg=82.0, oppg=75.0, diff=7.0)})
_SERIES = {'GSV': -250, 'ATD': 210}   # texas222 WNBA Finals series price (GSV leads 3-2)
def _cup(t): return _FUT['CUP'].get(t, _SERIES.get(t))
def _imp(o): return 100/(o+100) if o > 0 else -o/(-o+100)
def tier(m): return 'Strong' if m >= 5 else ('Solid' if m >= 3 else 'Thin')

def analyse(g):
    a, h, la, lh = g['a'], g['h'], g['la'], g['lh']
    conf = 'LOW' if f'{a}-{h}' in QUESTIONABLE else 'MED'
    rows = []
    mA, mH = novig(la['ml'], lh['ml'])
    modH = g['pH'] if g['sr'] is None else (g['pH'] + g['sr']/100)/2
    estH = 0.4*modH + 0.6*mH; estA = 1 - estH
    rows.append(('GAME', f'Moneyline {a}', fmt(la['ml']), estA, la['ml'], conf, f"Model {pct(g['pA'])}{(', Sportradar '+pct(1-g['sr']/100)) if g['sr'] else ''}, texas222 no-vig {pct(mA)}. Blend {pct(estA)}.", 'A'))
    rows.append(('GAME', f'Moneyline {h}', fmt(lh['ml']), estH, lh['ml'], conf, f"Model {pct(g['pH'])}{(', Sportradar '+str(g['sr'])+'%') if g['sr'] else ''}, texas222 no-vig {pct(mH)}. Blend {pct(estH)}.", 'H'))
    sA, sH = la['sp'], lh['sp']
    cA = g['cover']('A', sA[0]); mcA, mcH = novig(sA[1], sH[1])
    eA = 0.4*cA + 0.6*mcA
    rows.append(('GAME', f'Spread {a} {sp(sA[0])}', fmt(sA[1]), eA, sA[1], conf, f"Projected margin {h} {g['margin']:+.1f}. {a} covers {sp(sA[0])}: model {pct(cA)}, market {pct(mcA)}.", 'A'))
    rows.append(('GAME', f'Spread {h} {sp(sH[0])}', fmt(sH[1]), 1-eA, sH[1], conf, f"Model {pct(1-cA)}, market {pct(mcH)}.", 'H'))
    ov = la['tot'] if la['tot'][0]=='O' else lh['tot']; un = lh['tot'] if lh['tot'][0]=='U' else la['tot']
    line = ov[1]; po = g['p_over'](line); mo, mu = novig(ov[2], un[2]); estO = 0.4*po + 0.6*mo
    rows.append(('GAME', f'Total over {line:g}', fmt(ov[2]), estO, ov[2], conf, f"Projected total {g['total']:.1f}. Model over {pct(po)}, market {pct(mo)}.", 'O'))
    rows.append(('GAME', f'Total under {line:g}', fmt(un[2]), 1-estO, un[2], conf, f"Model under {pct(1-po)}, market {pct(mu)}.", 'U'))
    for side, t, mu_, L in (('A', a, g['ptsA'], la), ('H', h, g['ptsH'], lh)):
        if not L['tt']: continue   # team totals not posted at texas222 yet
        ln, pov, pun = L['tt']; m_o, m_u = novig(pov, pun)
        mod_o = 1 - Phi((ln - mu_)/12.0); est_o = 0.4*mod_o + 0.6*m_o
        rows.append(('TEAM TOTALS', f'{t} team total over {ln:g}', fmt(pov), est_o, pov, conf, f"Projected {mu_:.1f}. Model {pct(mod_o)}, market {pct(m_o)}.", 'O'))
        rows.append(('TEAM TOTALS', f'{t} team total under {ln:g}', fmt(pun), 1-est_o, pun, conf, f"Model {pct(1-mod_o)}.", 'U'))
    # first half: half the margin and 49% of the total, tighter spreads
    if la['h1sp'] and lh['h1sp']:
        m1, t1 = g['margin']/2, g['total']*0.49
        h1A = la['h1sp']; h1H = lh['h1sp']
        c1A = Phi(((-m1) + h1A[0])/9.0); mk1A, mk1H = novig(h1A[1], h1H[1]); e1 = 0.4*c1A + 0.6*mk1A
        rows.append(('FIRST HALF', f'1st half {a} {sp(h1A[0])}', fmt(h1A[1]), e1, h1A[1], 'LOW', f"1H margin {h} {m1:+.1f}. Model {pct(c1A)}, market {pct(mk1A)}.", 'A'))
        rows.append(('FIRST HALF', f'1st half {h} {sp(h1H[0])}', fmt(h1H[1]), 1-e1, h1H[1], 'LOW', f"Model {pct(1-c1A)}, market {pct(mk1H)}.", 'H'))
        o1 = la['h1tot'] if la['h1tot'][0]=='O' else lh['h1tot']; u1 = lh['h1tot'] if lh['h1tot'][0]=='U' else la['h1tot']
        po1 = 1 - Phi((o1[1]-t1)/12.5); mo1, mu1 = novig(o1[2], u1[2]); e1t = 0.4*po1 + 0.6*mo1
        rows.append(('FIRST HALF', f'1st half over {o1[1]:g}', fmt(o1[2]), e1t, o1[2], 'LOW', f"1H total {t1:.1f}. Model {pct(po1)}, market {pct(mo1)}.", 'O1'))
        rows.append(('FIRST HALF', f'1st half under {o1[1]:g}', fmt(u1[2]), 1-e1t, u1[2], 'LOW', f"Model {pct(1-po1)}.", 'U1'))
        pm1 = Phi(m1/9.0); n1A, n1H = novig(la['h1ml'], lh['h1ml']); e1m = 0.4*pm1 + 0.6*n1H
        rows.append(('FIRST HALF', f'1st half moneyline {a}', fmt(la['h1ml']), 1-e1m, la['h1ml'], 'LOW', f"Model {pct(1-pm1)}, market {pct(n1A)}. A tied half voids or loses depending on house rules.", 'A'))
        rows.append(('FIRST HALF', f'1st half moneyline {h}', fmt(lh['h1ml']), e1m, lh['h1ml'], 'LOW', f"Model {pct(pm1)}, market {pct(n1H)}.", 'H'))
    graded = []
    for grp, m, ps, est, price, cf, why, th in rows:
        call, edge = grade(est, price, cf)
        graded.append(dict(grp=grp, m=m, ps=ps, est=est, price=price, conf=cf, why=why, th=th, call=call, edge=edge))
    fam = lambda th: 'side' if th in ('A','H') else 'total'
    carried = {}
    for r in graded:
        if r['call'] in ('PLAY','LEAN'):
            f = fam(r['th'])
            if f not in carried or r['edge'] > carried[f]['edge']: carried[f] = r
    for r in graded:
        if r['call'] in ('PLAY','LEAN') and carried.get(fam(r['th'])) is not r:
            r['why'] += f" <b>Same thesis as {esc(carried[fam(r['th'])]['m'])}; not carried.</b>"; r['corr'] = True
    return graded

# ---------------------------------------------------------------- props
# Baseline = last season (2025-26 full season, NBA.com). Trend = this season's games only (shown, lightly weighted on minutes).
# Projection is built on the GAME SCRIPT the card picks: texas222 team total shifted toward the picked total, blowout minutes on big spreads.
LOCKED = set()
# Nov 12 (A27/A28/A32): t222.txt holds the Odds API OPENING line (picks and prices); t222_now.txt the latest read (line moves, CLV)
def _now():
    import model as _M, shutil
    p = pathlib.Path(__file__).parent/'t222_now.txt'
    if not p.exists(): return {}
    src = pathlib.Path(__file__).parent/'t222.txt'; tmp = src.read_text(); src.write_text(p.read_text())
    try: return _M.parse_t222()
    finally: src.write_text(tmp)
NOW = _now()
TODAY_INP = {}
TIER_OFF = {}   # (game key, 'side'|'total') -> reason: the pick's rule tier is turned off in Season Cards meta (logged as a would-be pick)
NO_T222 = set()   # games with no texas222 game line at the read (DraftKings stand-in for the model only): no game pick, no would-be pick
STATK = {'points':'p','rebounds':'r','assists':'a','threes':'t','pra':'pra'}
STATL = {'points':'points','rebounds':'rebounds','assists':'assists','threes':'3-pointers made','pra':'pts + reb + ast'}
STATT = {'points':'Points','rebounds':'Rebounds','assists':'Assists','threes':'3-pointers','pra':'PRA'}
SDFLOOR = {'points':5.0,'rebounds':2.2,'assists':1.8,'pra':6.5}
SEASON = {}
for _ln in (D/'season_raw.txt').read_text().strip().splitlines()[1:]:
    _f = _ln.split('|')
    _d = dict(team=_f[1], lt=_f[2], gp=int(_f[3]), mpg=float(_f[4]), cmin=[int(x) for x in _f[5].split('-') if x], st={})
    for _tok in _f[6].split(' '):
        _k, _v = _tok.split(':')
        _av, _sd, _hits, _cur = _v.split('/')
        _d['st'][(_k[0], float(_k[1:]))] = dict(avg=float(_av), sd=float(_sd), hits=int(_hits), cur=[int(x) for x in _cur.split('-') if x])
    SEASON[_f[0]] = _d
SHIFT = {'Thin':1.5, 'Solid':3.0, 'Strong':4.5}
# Prop model v2 (Nov 2): this season's per-minute rates and hit rates blended in by games/(games+10); opponent rebounds, assists and 3PM
# allowed per 100 possessions (half weight); usage boost when teammates are Out; PLAY needs a price of -150 or better.
CUR_K, MATCH_W, USG_W, USG_CAP, PLAY_JUICE = 10, 0.5, 0.5, 1.10, -150
_AB = {v.split()[-1]: k for k, v in FULL.items()}
_MT = {}
for _ln in (D/'matchup_raw.txt').read_text().strip().splitlines()[1:]:
    _ss = _ln.split(' ', 2)
    for _r in _ss[2].split(';'):
        _f = _r.split(','); _MT.setdefault(_AB[_f[0]], {})[_ss[1]] = (int(_f[1]), [float(x) for x in _f[2:5]])
def _mbl(t):
    (g0, v0), (g1, v1) = _MT[t]['2025-26'], _MT[t]['2026-27']; w = g1/(g1+12)
    return [(1-w)*a + w*b for a, b in zip(v0, v1)]
_LGM = [sum(_mbl(t)[i] for t in _MT)/len(_MT) for i in range(3)]
MATCH = {t: [_mbl(t)[i]/_LGM[i] for i in range(3)] for t in _MT}   # opponent allowed: rebounds, assists, 3PM vs league
USAGE = {}
for _ln in (D/'usage_raw.txt').read_text().strip().splitlines()[1:]:
    _t, _m, _who = _ln.split('|'); USAGE[_t] = ([float(x) for x in _m.split(',')], _who)
SCRIPT = {}   # game key -> script dict, filled after picks()

def make_script(g, pick_side, pick_tot):
    a, h = g['a'], g['h']
    tside = None if pick_tot.get('nopick') else ('O' if pick_tot['text'].startswith('Over') else 'U')
    sh = 0 if tside is None else SHIFT[pick_tot['tier']] * (1 if tside == 'O' else -1)
    cd = g.get('ctxd') or {a: 0, h: 0}   # what the context layer (venue, fatigue, division) adds beyond the base model, half weight
    def _tt0(L, other):   # posted team total, or the split implied by the texas222 spread and total when team totals are not posted
        if L['tt']: return L['tt'][0]
        return L['tot'][1]/2 - L['sp'][0]/2
    tt = {a: _tt0(g['la'], g['lh']) + sh/2 + 0.5*cd[a], h: _tt0(g['lh'], g['la']) + sh/2 + 0.5*cd[h]}
    spread = abs(g['lh']['sp'][0])
    fav = h if g['lh']['sp'][0] < 0 else a
    return dict(tside=tside, ttier=pick_tot['tier'] or 'No pick', tline=(pick_tot['text'] if not pick_tot.get('nopick') else 'no total pick'), side=pick_side['text'], tt=tt, spread=spread, fav=fav,
                blowout=spread >= 8, cd=cd, mkt_total=(g['la']['tot'] if g['la']['tot'][0]=='O' else g['lh']['tot'])[1], pace=g['pace'])

def _spot_txt(g):
    CX = g.get('ctx')
    if not CX:
        return ('Neither team is on a back-to-back.' if g['A']['rest'] and g['H']['rest'] else 'Back-to-back in play: -1.5 points to the tired team.')
    parts = []
    for t, fz in ((g['a'], CX['fA']), (g['h'], CX['fH'])):
        if fz[3]: parts.append(f"{t}: {fz[3]}" + (f", {fz[0]:+.1f} margin ({fz[1]:+.1f} own points, {fz[2]:+.1f} allowed)" if fz[0] else ''))
    n = FAT['b2b'][3]
    return '; '.join(parts) + f". Fatigue is learned from {n:.0f} back-to-back games across both seasons (margin and points vs the team's own home or road average), shrunk toward -1.5, and updates every day."

def _venue_rows(g):
    CX = g.get('ctx')
    if not CX: return ''
    a, h = g['a'], g['h']; A, H = CX['A'], CX['H']
    def split(t, X):
        if not X: return 'no split yet'
        s = f"last season home {X['hm_l']:+.1f}, road {X['rm_l']:+.1f}"
        if X['hn_n'] or X['rn_n']: s += f"; this season home {X['hm_n']:+.1f} ({X['hn_n']} g), road {X['rm_n']:+.1f} ({X['rn_n']} g)"
        return s + f"; own home edge {X['half']:+.1f}"
    def dv(t, key, ds, n, l):
        s = f"{DIVNAME[key]} {ds:+.1f} per game vs other divisions"
        if n: s += f" (this season {n['m']:+.1f} in {n['n']} g, {n['w']}-{n['n']-n['w']}; last season {l.get('m',0):+.1f})"
        return s
    return (f"<tr><td>Home/road margins</td><td>{a} {split(a, A)}. {h} {split(h, H)}. Home edge tonight {CX['adv']:.1f} points "
            f"(league {HCA_MARGIN:.1f} learned from both seasons, each team's split counts 30%). Venue scoring {CX['tot_venue']:+.1f} total.</td></tr>"
            f"<tr><td>Division strength</td><td>{a}: {dv(a, CX['divA'], CX['dsA'], CX['nA'], CX['lA'])}. {h}: {dv(h, CX['divH'], CX['dsH'], CX['nH'], CX['lH'])}. "
            + ('Same division, no adjustment.' if CX['sameDiv'] else f"Schedule credit {a} {CX['corrA']:+.1f}, {h} {CX['corrH']:+.1f}" + (" and a 1-point Division strength signal (gap 2+)." if abs(CX['dsA']-CX['dsH']) >= 2 else " (gap under 2, no signal).")) + "</td></tr>")

def _team_ls_pts(t):
    for gg in games:
        for side, X in (('a', gg['A']), ('h', gg['H'])):
            if gg[side] == t: return X['lo']*X['lpace']/100
    return 115.0

def prop_model(g, team, pl, stat, line):
    S = SEASON.get(pl); sc = SCRIPT[f"{g['a']}-{g['h']}"]
    if not S: return None
    k = STATK[stat]
    if stat == 'pra':
        parts = [S['st'].get((x, l)) for (x, l) in S['st'] if x in 'pra']
        keys = {}
        for (x, l), v in S['st'].items():
            if x in 'pra' and x not in keys: keys[x] = v
        if len(keys) < 3: return None
        st = dict(avg=sum(v['avg'] for v in keys.values()), sd=math.sqrt(sum(v['sd']**2 for v in keys.values()))*1.15, hits=None,
                  cur=[sum(z) for z in zip(*(v['cur'] for v in keys.values()))] if all(v['cur'] for v in keys.values()) else [])
    else:
        st = S['st'].get((k, line))
        if not st: return None
    ls_gp, ls_mpg = S['gp'], S['mpg']
    cm = S['cmin']; cw = len(cm)/(len(cm)+4)
    if ls_gp >= 10 and ls_mpg > 0:
        mins = (1-cw)*ls_mpg + cw*(sum(cm)/len(cm) if cm else ls_mpg)
        per_min = st['avg']/ls_mpg; base = 'last season'
    elif cm and st['cur']:
        mins = sum(cm)/len(cm); per_min = (sum(st['cur'])/len(st['cur']))/max(mins, 1); base = 'season to date only'
    else:
        return None
    ngp = sum(1 for x in cm if x > 0); cw2 = 0.0; cur_pm = None
    if base == 'last season' and ngp and st['cur'] and sum(cm) > 0:
        cw2 = ngp/(ngp + CUR_K); cur_pm = sum(st['cur'])/sum(cm)
        per_min = (1-cw2)*per_min + cw2*cur_pm
    starter = mins >= 28
    if sc['blowout']: mins *= 0.95 if starter else 1.04
    home = team == g['h']
    TT = g['A'] if team == g['a'] else g['H']
    b2b = (not g.get('wnba')) and TT['rest'] == 0
    bm, br = b2b_factor(starter) if b2b else (1.0, 1.0)
    mins *= bm
    lf, linfo = (1.0, None) if g.get('wnba') else loc_factor(pl, k if stat != 'pra' else 'p', line if stat != 'pra' else None, home)
    if stat == 'pra': lf, linfo = 1.0, None
    tpts = sc['tt'][team]; lsp = _team_ls_pts(team)
    if stat in ('points', 'threes', 'pra'): f = tpts/lsp
    elif stat == 'assists': f = math.sqrt(tpts/lsp)
    else: f = sc['pace']/LG['pace']
    opp = g['h'] if team == g['a'] else g['a']
    mi = {'rebounds':0, 'assists':1, 'threes':2}.get(stat)
    mf = 1 + MATCH_W*(MATCH[opp][mi] - 1) if (mi is not None and opp in MATCH) else 1.0
    ui = {'points':[0], 'rebounds':[1], 'assists':[2], 'threes':[3], 'pra':[0,1,2]}[stat]
    um = sum(USAGE[team][0][i] for i in ui)/len(ui) if team in USAGE else 0.0
    uf = min(USG_CAP, 1 + USG_W*um/(1-um)) if um else 1.0
    raw = per_min*mins*f*br*lf*mf*uf
    mu = 0.7*raw + 0.3*line
    ls_avg = st['avg'] if base == 'last season' else raw
    sd = max(st['sd']*math.sqrt(max(mu, 0.5)/max(ls_avg, 0.5)) if st['sd'] else SDFLOOR.get(stat, 1.5), SDFLOOR.get(stat, 1.0))
    if stat == 'threes': p_rate = p_ge(max(mu, 0.05), int(line+0.5))
    else: p_rate = 1 - Phi((line - mu)/sd)
    p_rec = (st['hits']/ls_gp) if (st['hits'] is not None and ls_gp) else None
    played = [v for v, mn in zip(st['cur'], cm) if mn > 0] if st['cur'] else []
    if p_rec is not None and played and cw2:   # hit rates are noisier than per-minute rates, so this season's record gets games/(games+20)
        rw = len(played)/(len(played) + 2*CUR_K)
        p_rec = (1-rw)*p_rec + rw*(sum(1 for v in played if v > line)/len(played))
    blend = 0.5*p_rate + 0.5*p_rec if p_rec is not None else p_rate
    return dict(S=S, st=st, base=base, ls_gp=ls_gp, ls_mpg=ls_mpg, ls_avg=st['avg'], cur=st['cur'], cmin=cm, mins=mins, f=f, tpts=tpts,
                raw=raw, mu=mu, sd=sd, p_rate=p_rate, p_rec=p_rec, blend=blend, starter=starter, sc=sc,
                home=home, b2b=b2b, bm=bm, br=br, lf=lf, linfo=linfo, cw2=cw2, cur_pm=cur_pm, opp=opp, mf=mf, uf=uf, um=um)

def _script_fit(stat, side, sc):
    """+1 fits the picked game script, -1 works against it, 0 neutral."""
    if stat in ('points', 'threes', 'assists', 'pra'):
        if sc['tside'] is None: return 0
        want = 'over' if sc['tside'] == 'O' else 'under'
        return 1 if side == want else -1
    return 0

def prop_grade(g, team, pr):
    m = prop_model(g, team, pr['pl'], pr['stat'], pr['line'])
    if not m: return None, None
    out = []
    key = f"{g['a']}-{g['h']}"
    for side_, price in (('over', pr['over']), ('under', pr['under'])):
        bl = m['blend'] if side_ == 'over' else 1 - m['blend']
        est = 0.4*bl + 0.6*(be(price) - 0.025)
        prate = m['p_rate'] if side_ == 'over' else 1 - m['p_rate']
        prec = None if m['p_rec'] is None else (m['p_rec'] if side_ == 'over' else 1 - m['p_rec'])
        agree = prec is not None and abs(prate - prec) < 0.08
        newteam = m['S']['lt'] not in ('-', m['S']['team'])
        conf = 'MED' if (agree and m['ls_gp'] >= 20 and not newteam and key not in QUESTIONABLE) else 'LOW'
        call, edge = grade(est, price, conf)
        if call == 'LEAN' and conf == 'LOW' and edge < 3.0: call = 'PASS'
        if m['ls_gp'] < 9 or m['base'] != 'last season': call = 'PASS'
        juiced = call == 'PLAY' and price < PLAY_JUICE
        if juiced: call = 'LEAN'
        fit = _script_fit(pr['stat'], side_, m['sc'])
        held_reason = None
        if fit < 0 and call != 'PASS':   # Season Cards, Nov 6: a prop against the card's total pick is held back (any tier), never a Play, hidden on the card
            held_reason = f"against {m['sc']['tline']}"; call = 'HELD'
        # Nov 2 rule changes (Trina): LEAN points unders count as PLAYs at -150 or better; plus-money props are never PLAYs
        promo = call == 'LEAN' and pr['stat'] == 'points' and side_ == 'under' and fit >= 0 and PLAY_JUICE <= price < 0
        if promo: call = 'PLAY'
        plusblk = call == 'PLAY' and price > 0
        if plusblk: call = 'LEAN'
        # reasons
        line = pr['line']; lab = STATL[pr['stat']]
        hits = None if m['st']['hits'] is None else (m['st']['hits'] if side_ == 'over' else m['ls_gp'] - m['st']['hits'])
        fr, ag = [], []
        if m['base'] == 'last season':
            fr_txt = f"{m['ls_avg']:.1f} {lab} per game in {m['ls_mpg']:.0f} minutes over {m['ls_gp']} games"
            if hits is not None: fr_txt += f"; {side_} {line:g} in {hits} of {m['ls_gp']} ({100*hits/m['ls_gp']:.0f}%)"
            (fr if (hits is None or hits/m['ls_gp'] >= 0.5) else ag).append(('Last season', fr_txt + '.'))
        else:
            ag.append(('Last season', 'No NBA games last season; season to date only, so no pick.'))
        proj = f"{m['mu']:.1f} {lab} in about {m['mins']:.0f} minutes vs the {line:g} line"
        ((fr if (m['mu'] > line) == (side_ == 'over') else ag)).append(('Tonight\'s projection', proj + '.'))
        sc = m['sc']
        script = f"Card picks {sc['tline']} ({sc['ttier']}) and {sc['side']}; {team} scripted for {m['tpts']:.0f} points"
        if fit > 0: fr.append(('Game script', script + f", which supports the {side_}."))
        elif fit < 0: ag.append(('Game script', script + f", which points the other way."))
        else: fr.append(('Game script', script + f"; rebounds follow pace ({sc['pace']:.1f} possessions)."))
        if m['linfo']:
            v_, n_, ov_ = m['linfo']; where = 'home' if m['home'] else 'road'
            if abs(m['lf'] - 1) >= 0.01:
                txt = f"{v_:.1f} {lab} in {n_} {where} games last season vs {ov_:.1f} overall; projection x{m['lf']:.2f}."
                ((fr if (m['lf'] > 1) == (side_ == 'over') else ag)).append(('Home/road split', txt))
        if m['b2b']:
            txt = f"{team} on a back-to-back: league {'starters' if m['starter'] else 'bench players'} play x{m['bm']:.3f} minutes with x{m['br']:.3f} output per minute on back-to-backs."
            ((fr if ((m['bm']*m['br']) > 1) == (side_ == 'over') else ag)).append(('Back-to-back', txt))
        if abs(sc['cd'].get(team, 0)) >= 0.3:
            txt = f"Venue, fatigue and division strength move {team} {sc['cd'][team]:+.1f} points vs the base model; half of that is in the scripted team total."
            ((fr if (sc['cd'][team] > 0) == (side_ == 'over') else ag) if pr['stat'] != 'rebounds' else fr).append(('Schedule context', txt))
        if sc['blowout'] and m['starter']:
            (ag if side_ == 'over' else fr).append(('Blowout minutes', f"Spread is {sc['spread']:g}, so starters' minutes are cut 5%."))
        if abs(m['mf'] - 1) >= 0.02:
            mt = ['rebounds','assists','3-pointers'][{'rebounds':0,'assists':1,'threes':2}[pr['stat']]]
            ((fr if (m['mf'] > 1) == (side_ == 'over') else ag)).append(('Matchup', f"{m['opp']} allow {100*(MATCH[m['opp']][{'rebounds':0,'assists':1,'threes':2}[pr['stat']]]-1):+.0f}% {mt} per 100 possessions vs league; projection x{m['mf']:.2f}."))
        if m['uf'] > 1.005:
            ((fr if side_ == 'over' else ag)).append(('Teammates out', f"{USAGE[team][1]} out: {100*m['um']:.0f}% of {team}'s {lab} this season is missing; projection x{m['uf']:.2f}."))
        if promo: fr.append(('Points under rule', "LEAN-level points unders were 21-11 (+6.7u) through Nov 1, so they count as PLAYs at -150 or better."))
        if plusblk: ag.append(('Plus money', f"Plus-money props were 20-33 (-9.1u) through Nov 1, so {fmt(price)} is logged as LEAN (tracking), not a PLAY."))
        if juiced: ag.append(('Price', f"{fmt(price)} is worse than {PLAY_JUICE}, so a PLAY-level edge is logged as LEAN (tracking)."))
        cur = m['cur']
        if cur:
            cv = sum(cur)/len(cur); tr = f"{len(cur)} game{'s' if len(cur) != 1 else ''} this season: {', '.join(map(str, cur))} {lab}" + (f" in {', '.join(map(str, m['cmin']))} minutes" if m['cmin'] else '')
            ((fr if (cv > line) == (side_ == 'over') else ag)).append(('Season to date', tr + '.' + (f" Rate weighted {100*m['cw2']:.0f}% to this season ({m['cur_pm']*m['mins']:.1f} at tonight's minutes)." if m['cw2'] else '')))
        else:
            ag.append(('Season to date', 'Has not played this season yet.'))
        if newteam: ag.append(('New team', f"Played for {m['S']['lt']} last season; role on {team} is still settling."))
        if prec is not None and not agree: ag.append(('Record vs rate', f"Last season's record ({100*prec:.0f}%) and the rate model ({100*prate:.0f}%) disagree."))
        if key in QUESTIONABLE: ag.append(('Injury watch', QUESTIONABLE[key] + '.'))
        short_for = ', '.join(dict.fromkeys(t for t, _ in fr[:3])).lower()
        short_ag = ', '.join(dict.fromkeys(t for t, _ in ag[:2])).lower()
        short = (f"Last season {m['ls_avg']:.1f} avg" + (f", {side_} in {hits} of {m['ls_gp']}" if hits is not None else '') +
                 f"; projects {m['mu']:.1f}. Script: {sc['tline']}" + (f". Against: {short_ag}" if ag else ''))
        out.append(dict(side=side_, price=price, est=est, conf=conf, call=call, edge=edge, fit=fit, fr=fr, ag=ag, short=short, held_reason=held_reason, hits=hits, ls_gp=m['ls_gp'], ls_avg=m['ls_avg'], cur=cur,
                        basis=f"Last season {m['ls_avg']:.1f}, projects {m['mu']:.1f}", ls=f"{m['ls_avg']:.1f} avg · {('%s %d/%d' % (side_, hits, m['ls_gp'])) if hits is not None else 'n/a'}",
                        cur_txt=(', '.join(map(str, cur)) if cur else 'no games'), mu=m['mu'], mins=m['mins'], n=m['ls_gp']))
    return max(out, key=lambda x: (x['call'] == 'PLAY', x['edge'])), m

def prop_box(r):
    tg = f"<span class='tag {'t-a' if r['call']=='PLAY' else 't-c'}'>{r['call']}</span> <span class='tag {tag(r['conf'])}'>{r['conf']}</span>"
    fl = ''.join(f"<li><b>{esc(t)}</b>: {esc(n)}</li>" for t, n in r['fr']) or '<li>Price edge only.</li>'
    ag = ('<div class="lbl">Working against it</div><ul class="nl">' + ''.join(f"<li><b>{esc(t)}</b>: {esc(n)}</li>" for t, n in r['ag']) + '</ul>') if r['ag'] else ''
    return (f"<div class='pick'><div class='lbl'>Player prop · {STATT[r['stat']]} · {esc(r['team'])}</div>"
            f"<div class='pt'>{esc(r['pl'])} {esc(r['side'])} {r['line']:g}</div>"
            f"<div class='num'>texas222 {fmt(r['price'])} · projected chance {pct(r['est'])} vs {pct(be(r['price']))} needed</div>"
            f"<div class='num'>Edge {r['edge']:+.1f} pts · projects {r['mu']:.1f}</div><div>{tg}</div>"
            f"<div class='lbl'>Why</div><ul class='nl'>{fl}</ul>{ag}</div>")

def injnote(a, h, key):
    p = [f"{t}: {INJ_ADJ[t][1]}, {INJ_ADJ[t][0]:g} points taken off the margin" for t in (a, h) if t in INJ_ADJ]
    if key in QUESTIONABLE: p.append(QUESTIONABLE[key] + '; grades LOW until confirmed')
    return ('. '.join(p) + '.') if p else 'No starter or 28+ minute player is out for either team, so no injury adjustment is applied.'

def team_of(pl, g):
    for t in (g['a'], g['h']):
        if pl in ROSTER.get(t, []): return t
    return PLAYERS[pl]['team']

# ---------------------------------------------------------------- picks (signal scoring)
def _inp(g):
    """Normalized pickrules input from the card's own data (texas222 lines, Action Network morning read, model)."""
    a, h = g['a'], g['h']; key = f'{a}-{h}'; S = AN[key]; A, H = g['A'], g['H']
    la, lh = g['la'], g['lh']
    tl = la['tot'] if la['tot'][0] == 'O' else lh['tot']; ul = lh['tot'] if lh['tot'][0] == 'U' else la['tot']
    stA, stH = _STB[a], _STB[h]
    def st(x):
        w, l = (map(int, x['l10'].split('-')) if x.get('l10') else (0, 0))
        return dict(gp=x['gp'], pct=x['pct'], strk=x['strk'], l10w=w, l10n=w+l, diff=x['diff'], ppg=x['ppg'], oppg=x['oppg'])
    CX = g.get('ctx')
    _d = dict(a=a, h=h, ml_a=la['ml'], ml_h=lh['ml'], sp_a=la['sp'][0], sp_pa=la['sp'][1], sp_ph=lh['sp'][1], tot=tl[1], tot_po=tl[2], tot_pu=ul[2],
                open_sp_a=S['sp_open'], open_tot=S['tot_open'], open_ml_a=S['ml_open'][0], open_ml_h=S['ml_open'][1], src2=DK.get(key),
                ml_bets_a=S['bets'], ml_money_a=S['money'], sp_bets_a=S['sp_bets'], sp_money_a=S['sp_money'], o_bets=S['o_bets'], o_money=S['o_money'],
                sig_ml=S['sig_ml'], sig_sp=S['sig_sp'], sig_tot=S['sig_tot'], margin=g['margin'], ptotal=g['total'], pace=g['pace'], sdm=g['sdm'], sr=g['sr'],
                stA=st(stA), stH=st(stH), restA=A['rest'], restH=H['rest'], inj=INJ_ADJ,
                dsA=CX['dsA'] if CX else None, dsH=CX['dsH'] if CX else None, same_div=CX['sameDiv'] if CX else True, divA=CX['divA'] if CX else None, divH=CX['divH'] if CX else None,
                lastA=LAST[a][0], lastH=LAST[h][0], cupA=_cup(a), cupH=_cup(h), lg_pace=LG['pace'],
                **({'sp_now_a': NOW[a]['sp'][0], 'tot_now_v': NOW[a]['tot'][1]} if a in NOW else {}))
    TODAY_INP[key] = dict(_d, h1=dict(sp_a=g['la'].get('h1sp'), sp_h=g['lh'].get('h1sp')), ml_now=(NOW[a]['ml'], NOW[h]['ml']) if a in NOW else None,
                          sp_now_prices=(NOW[a]['sp'][1], NOW[h]['sp'][1]) if a in NOW else None, tot_now_prices=None)
    (pathlib.Path(__file__).parent/'today_inp.json').write_text(json.dumps(TODAY_INP, default=str))
    return _d

def picks(g, graded):
    a, h = g['a'], g['h']; key = f'{a}-{h}'
    nm = {'A':a, 'H':h}
    labS = lambda s: nm[s]
    labT = lambda s: 'Over' if s == 'O' else 'Under'
    inp = _inp(g); SC = PR.score_game(inp)
    SCORES[key] = dict(srows=SC['srows'], trows=SC['trows'], prows=SC.get('prows', []), sc=SC['sc'], tc=SC['tc'], side=SC['side'], tside=SC['tside'], estH=SC.get('estH'))
    srows = [(s_, m_, labS(sd) if p_ or s_ not in ('Line move',) else 'Neither', p_, n_) for s_, m_, sd, p_, n_ in SC['srows']]
    sc, side, other = SC['sc'], SC['side'], SC['other']
    prows = [(s_, m_, f"{nm[sd]} {sp(inp['sp_a'] if sd == 'A' else -inp['sp_a'])}", p_, n_) for s_, m_, sd, p_, n_ in SC['prows']]
    srows += prows
    trows = [(s_, m_, labT(sd) if p_ else 'Neither', p_, n_) for s_, m_, sd, p_, n_ in SC['trows']]
    tc, tside = SC['tc'], SC['tside']; t_other = 'U' if tside == 'O' else 'O'
    side_c, tot_c, CANDS = PR.apply_rules(inp, SC, RSTATE.get('rules'), {k: (v.get('season') or {}) for k, v in RSTATE.get('rules', {}).items()})
    SHADOW[key] = dict(cands=[c for c in PR.candidates(inp, SC, RSTATE.get('rules')) if not PR._st(RSTATE.get('rules'), c['rule'])['on']], sc=dict(SC['sc']), tc=dict(SC['tc']), srows=SC['srows'], trows=SC['trows'], prows=SC.get('prows', []))
    if key in NO_T222:   # no texas222 line: no pick and no would-be pick
        side_c = tot_c = None; SHADOW[key]['cands'] = []
    estH = SC['estH']
    conflS = lambda sd: any(rw[0] in ('Action Network Sharp Action','Reverse line movement') and rw[2].startswith(nm['H' if sd == 'A' else 'A']) and rw[3] for rw in srows)
    def rule_info(rid):
        s = RSTATE.get('rules', {}).get(rid, {})
        return dict(rule=rid, rule_label=PR.RULES[rid]['label'], rule_desc=s.get('desc') or PR.rule_desc(rid, RSTATE.get('rules')), rule_variant=s.get('variant', 'lowered'),
                    rule_rec=PR.rec_txt(s.get('season')), rule_live=PR.rec_txt(s.get('live')))
    if side_c:
        sd = side_c['side']; o_ = 'H' if sd == 'A' else 'A'
        if side_c['market'] == 'Moneyline':
            row = next(r for r in graded if r['m'] == f'Moneyline {nm[sd]}')
            pick_side = dict(text=f"{NAMES[nm[sd]]} moneyline", price=side_c['price'], prob=row['est'], market='Moneyline', m=row['m'])
        else:
            row = next(r for r in graded if r['m'] == f"Spread {nm[sd]} {sp(side_c['line'])}")
            pick_side = dict(text=f"{NAMES[nm[sd]]} {sp(side_c['line'])}", price=side_c['price'], prob=row['est'], market='Spread', m=row['m'])
        lead = sc[sd] - sc[o_]
        pick_side.update(tier=tier(lead), conf=conflS(sd), score=f"{sc[sd]}–{sc[o_]}", nopick=False, **rule_info(side_c['rule']))
        pick_side['why'] = f"Rule: {pick_side['rule_desc']}. Rule season to date {pick_side['rule_rec']}."
        side = sd; other = o_
    else:
        pick_side = dict(text='No pick', price=None, prob=None, market='Side', m=None, tier=None, conf=False, score=f"{sc[side]}–{sc[other]}", nopick=True, rule=None,
                         why=f"No rule fits. Signals lean {nm[side]} ({sc[side]}–{sc[other]}); the side rules need a favorite -200 to -100 with a 2+ lead, an underdog +100 to +200 with the signals on it, or a spread line move at both sources against the tickets.")
    use_sp = bool(side_c and side_c['market'] == 'Spread')
    line = inp['tot']
    LKD = LOCKED_DOCS.get(key) if key in LOCKED else None
    if tot_c:
        t_row = next(r for r in graded if r['m'] == f"Total under {line:g}")
        tside = 'U'; t_other = 'O'
        pick_tot = dict(text=f"Under {line:g}", price=tot_c['price'], prob=t_row['est'], tier=tier(tc['U']-tc['O']), conf=any(rw[0] == 'Action Network Sharp Action' and rw[2] == 'Over' and rw[3] for rw in trows),
                        score=f"{tc['U']}–{tc['O']}", market='Total', m=t_row['m'], nopick=False, **rule_info('UNDER_DROP'))
        pick_tot['why'] = f"Rule: {pick_tot['rule_desc']}. Rule season to date {pick_tot['rule_rec']}."
    else:
        pick_tot = dict(text='No pick', price=None, prob=None, tier=None, conf=False, score=f"{tc[tside]}–{tc[t_other]}", market='Total', m=None, nopick=True, rule=None,
                        why=("No rule fits. Overs are No pick (no over test has a winning record). " if tside == 'O' else "No rule fits. ") + "The under rule needs the total to drop from the open at both sources.")
    for _m in ('side', 'total'):
        if (key, _m) in TIER_OFF:
            _p = pick_side if _m == 'side' else pick_tot
            if not _p.get('nopick'):
                SHADOW[key]['cands'].append(side_c if _m == 'side' else tot_c)
                _np = dict(text='No pick', price=None, prob=None, tier=None, conf=False, score=_p['score'], market=_p['market'], m=None, nopick=True, rule=None,
                           why=f"No card pick: {_p['text']} fits {_p['rule_label']}, but {TIER_OFF[(key, _m)]}")
                if _m == 'side': pick_side = _np
                else: pick_tot = _np; tside = SC['tside']
    if key in NO_T222:
        pick_side['why'] = pick_tot['why'] = 'No pick: texas222 had no game line posted at the read (DraftKings via ESPN stand-in for the projection only).'
    if LKD:   # tipped before the Oct 30 rules: show the picks the tracker logged
        def old(dc, kind):
            return dict(text=dc['pick'], price=dc['price'], prob=dc['projected'], market=dc['market'], m=None, tier=dc['tier'], conf=dc['conflicting'], score='logged', nopick=False,
                        rule=None, rule_label='Logged before the rules', rule_desc='', rule_variant='', rule_rec='old method', rule_live='old method', locked=True,
                        why='Logged before tip under the old method (before the Oct 30 rule set); the tracker keeps this pick.')
        pick_side, pick_tot = old(LKD['side'], 'side'), old(LKD['total'], 'total')
        use_sp = pick_side['market'] == 'Spread'
        tside = 'O' if pick_tot['text'].startswith('Over') else 'U'; t_other = 'U' if tside == 'O' else 'O'
        side = 'A' if pick_side['text'].startswith(NAMES[a]) else 'H'; other = 'H' if side == 'A' else 'A'
    PICKS.append((key, pick_side, pick_tot))
    SHORT = {'Action Network Sharp Action':'sharp money','Action Network PRO Systems':'PRO system match','Action Network Big Money':'big money',
             'Reverse line movement':'reverse line move','Money % above ticket %':'bigger bets than ticket share','Fade the public':'fading the public',
             'Card projection':'projection','Rest edge':'opponent on a back-to-back','Injury edge':'opponent missing starters','Points cushion':'points cushion',
             'Needs to win by the number':'must win by the number','Total moved down':'total dropped','Home court':'home court','Hot streak':'hot streak',
             'Cold streak':'opponent cold streak','Recent form':'recent form','Point differential':'point differential','Track record':'track record',
             'Bounce-back candidate':'bounce-back','Regression watch':'regression watch','Roster strength':'roster strength','Recent scoring':'recent scoring','Pace':'pace'}
    pick_is_sp = use_sp
    def split(rows, mine):
        f, ag = [], []
        for s_, m_, to, p_, n_ in rows:
            if not p_: continue
            if s_ in ('Points cushion','Needs to win by the number') and not pick_is_sp: continue
            if m_ == 'Spread' and s_ in ('Money % above ticket %','Fade the public') and not pick_is_sp: continue
            (f if mine(to) else ag).append((p_, s_, n_))
        f.sort(key=lambda x: -x[0]); ag.sort(key=lambda x: -x[0]); return f, ag
    s_for, s_ag = split(srows, lambda to: to.startswith(nm[side]))
    t_for, t_ag = split(trows, lambda to: to == labT(tside))
    def short(f, ag):
        x = ', '.join(dict.fromkeys(SHORT.get(s_, s_) for _, s_, _ in f[:3])) or 'projection side'
        if ag: x += '. Against: ' + ', '.join(dict.fromkeys(SHORT.get(s_, s_) for _, s_, _ in ag[:2]))
        return x
    pick_side['short'] = short(s_for, s_ag); pick_tot['short'] = short(t_for, t_ag)
    pick_side['for'], pick_side['against'] = s_for, s_ag; pick_tot['for'], pick_tot['against'] = t_for, t_ag
    for p in (pick_side, pick_tot): p['team_side'] = nm[side]
    def box(title, p, extra=''):
        if p.get('nopick'):
            return (f"<div class='pick nopick'><div class='lbl'>{title}</div><div class='pt'>No pick</div><div class='num'>Signal score {p['score']}</div>"
                    f"<div class='why'>{esc(p['why'])}</div></div>")
        tg = f"<span class='tag {TIERCLS[p['tier']]}'>{p['tier']}</span> <span class='tag t-rule'>Rule: {esc(p['rule_label'])}</span>"
        cf = " <span class='tag t-d'>conflicting signals</span>" if p.get('conf') else ''
        fl = ''.join(f"<li><b>{esc(s_)}</b>: {esc(n_)}</li>" for _, s_, n_ in p['for']) or '<li>No signal leans clearly; this is the projection side.</li>'
        ag = ('<div class="lbl">Working against it</div><ul class="nl">' + ''.join(f"<li><b>{esc(s_)}</b>: {esc(n_)}</li>" for _, s_, n_ in p['against']) + '</ul>') if p['against'] else ''
        return (f"<div class='pick'><div class='lbl'>{title}</div><div class='pt'>{esc(p['text'])}</div>"
                f"<div class='num'>texas222 {fmt(p['price'])} · projected chance {pct(p['prob'])}</div><div class='num'>Signal score {p['score']}</div><div class='num'>Rule season to date {esc(p['rule_rec'])} · card picks {esc(p['rule_live'])}</div><div>{tg}{cf}</div>{extra}"
                f"<div class='lbl'>Why</div><ul class='nl'>{fl}</ul>{ag}</div>")
    sig_tbl = ''.join(f"<tr><td>{esc(s)}</td><td>{m}</td><td><b>{esc(to)}</b></td><td class='num'>{'+'+str(p) if p else 'info'}</td><td>{esc(n)}</td></tr>" for s, m, to, p, n in srows + trows)
    outs = [x for x in g['injA'] + g['injH'] if re.search(r'Out|Doubtful|Questionable', x)]
    parts = [f"{t} adjusted for {INJ_ADJ[t][1]} (-{INJ_ADJ[t][0]:g})" for t in (a, h) if t in INJ_ADJ]
    if key in QUESTIONABLE: parts.append(QUESTIONABLE[key] + ', so this game grades LOW')
    injline = ('; '.join(parts) + '.') if parts else 'No starter is listed out, doubtful or questionable for either team at read time.'
    return f"""
<h3 class='sh' id='{a.lower()}-{h.lower()}-picks'>Picks: side or spread, and total</h3>
<div class='picks'>
{box('Side &amp; spread', pick_side, f"<div class='why'>{esc(pick_side['why'])}</div>")}
{box('Total', pick_tot, f"<div class='why'>{esc(pick_tot['why'])}</div>" if not pick_tot.get('nopick') else '')}
</div>
<div class='sub' style='margin-top:8px'><b>Check before betting:</b> {esc(injline)} A late scratch of a starter changes these picks.</div>
<div class='scroll' style='margin-top:10px'><table><thead><tr><th>Signal</th><th>Market</th><th>Points to</th><th>Weight</th><th>Detail</th></tr></thead><tbody>{sig_tbl}</tbody></table></div>
<div class='sub' style='margin-top:8px'><b>Pick rules (from Oct 30):</b> a pick is made only when a rule fits, otherwise No pick. Side: favorite moneyline -200 to -100 with a signal lead of 2+; underdog moneyline +100 to +200 with the signals on it; or the spread on the side the line moved toward at both opening sources against the ticket majority. Total: the under when the total dropped from the open at both sources; overs are No pick. Rules are re-checked daily on every game played and switch off when they lose. Signal weights: Action Network Sharp Action 2 (spread or moneyline, counted once), reverse line movement 2 (spread moved a point or more toward the side with under half the spread tickets; the moneyline move counts only when the spread moved less than a point). One point each: PRO Systems, Big Money, money over tickets, fade the public, projection, rest (opponent on a back-to-back), injuries (opponent missing a starter), division strength (gap of 2+ points per game vs other divisions), home court, hot or cold streak (3+ games), last-10 form gap and point differential gap (from 5 games played), last season's track record, bounce-back or regression flags, and NBA title odds (roster strength). Totals add pace and season scoring. Strong = lead of 5+, Solid = 3 to 4, Thin = 0 to 2. Conflicting means sharp money or reverse line movement sits on the other side. The side pick takes the team's moneyline or its spread, whichever grades higher, and the better price when both grade the same; the spread adds its own splits, a points cushion bonus for underdogs that cover 55%+, and a 2-point penalty when a favorite covers less than 45%. A favorite's spread is eligible only if it covers 42%+.</div>"""

def row_html(r, picked=()):
    corr = ' <span class="tag t-d">correlated</span>' if r.get('corr') else ''
    pk = r['m'] in picked
    return (f"<tr{' class=\'pickrow\'' if pk else ''}><td><b>{esc(r['m'])}</b>{' <span class=\'tag t-a\'>Card pick</span>' if pk else ''}</td><td class='num'>{r['ps']}</td><td class='num'>{pct(r['est'])}</td><td class='num'>{pct(be(r['price']))}</td>"
            f"<td class='num'>{r['edge']:+.1f}</td><td class='{CALLCLS[r['call']]}'>{PRICEL[r['call']]}{corr}</td><td><span class='tag {tag(r['conf'])}'>{r['conf']}</span></td><td>{r['why']}</td></tr>")

def cmp_row(label, va, vh, better):
    a_txt, h_txt, a_num, h_num = va[0], vh[0], va[1], vh[1]
    ca, ch = '', ''
    if better and a_num is not None and h_num is not None and abs(a_num-h_num) > 0.01*max(abs(a_num),abs(h_num),1e-9):
        a_better = (a_num > h_num) if better=='hi' else (a_num < h_num)
        if a_better: ca = ' bet'
        else: ch = ' bet'
    return f"<tr><td>{label}</td><td class='ca{ca}'>{a_txt}</td><td class='ch{ch}'>{h_txt}</td></tr>"

def game_panel(g):
    a, h = g['a'], g['h']; key = f'{a}-{h}'; tid = f'{a.lower()}-{h.lower()}'
    A, H = g['A'], g['H']
    graded = analyse(g)
    pk_html = picks(g, graded)
    PICKED = {PICKS[-1][1]['m'], PICKS[-1][2]['m']}
    SCRIPT[key] = make_script(g, PICKS[-1][1], PICKS[-1][2])
    # texas222 props, both sides graded on the card's game script; one pick per player (best edge)
    priced = []
    for pr in [x for x in PROPS if x['game'] == key]:
        if pr['pl'] not in SEASON: continue
        team = SEASON[pr['pl']]['team']
        r, m = prop_grade(g, team, pr)
        if not r: continue
        priced.append(dict(team=team, pl=pr['pl'], stat=pr['stat'], line=pr['line'], lab=f"{r['side']} {pr['line']:g} {STATL[pr['stat']]}", book='texas222', **r))
    best = {}
    for r in priced:
        if r['call'] in ('PLAY','LEAN') and (r['pl'] not in best or (r['call'] == 'PLAY', r['edge']) > (best[r['pl']]['call'] == 'PLAY', best[r['pl']]['edge'])): best[r['pl']] = r
    pp = sorted(best.values(), key=lambda r: (r['call'] != 'PLAY', -r['edge']))
    for r in priced:
        if r['call'] in ('PLAY','LEAN') and best.get(r['pl']) is not r: r['nested'] = True
    for r in pp:
        r['rule_key'] = f"{r['stat']}|{r['side']}"; r['inactive'] = not PROP_RULES_ON.get(r['rule_key'], True)
        PROPPICKS.append((key, tid, g['time'], r))   # every PLAY and LEAN goes to the ledger; LEAN and props in an inactive Category · Side rule are tracking only
    hb = {}
    for r in priced:
        if r['call'] == 'HELD' and r['pl'] not in best and (r['pl'] not in hb or r['edge'] > hb[r['pl']]['edge']): hb[r['pl']] = r
    for r in hb.values(): HELDPROPS.append((key, r))
    PRICED_ALL[key] = priced
    pp_all, pp = pp, [r for r in pp if r['call'] == 'PLAY' and not r['inactive']]
    for r in graded:
        if r['call'] in ('PLAY','LEAN') and not r.get('corr'):
            ALLROWS.append((key, r['m'], r['ps'], r['est'], r['edge'], r['call'], r['conf'], tid, PRICEL[r['call']] + (' · card pick' if r['m'] in PICKED else '')))
    for r in pp:
        ALLROWS.append((key, f"{r['pl']} {r['lab']}", f"{fmt(r['price'])} texas222", r['est'], r['edge'], r['call'], r['conf'], tid, r['call'] + ' · prop pick'))
    scx = SCRIPT[key]
    script_txt = f"Game script: {scx['tline']} ({scx['ttier']}) and {scx['side']}. Team totals used: {a} {scx['tt'][a]:.0f}, {h} {scx['tt'][h]:.0f}" + (f"; spread {scx['spread']:g}, so starters lose about 5% of minutes." if scx['blowout'] else '.')
    locked = "<div class='sub' style='margin:6px 0 0'><b>Logged before tip:</b> this game tipped before today's model update (schedule, venue and division context), so the tracker keeps the picks logged before tip.</div>" if key in LOCKED else ''
    if pp:
        pk_html += (f"<h3 class='sh' id='{tid}-pprops'>Player prop picks</h3><div class='sub'>{esc(script_txt)} Props that work against the card's total pick are held back and not shown.</div>"
                    "<div class='picks'>" + ''.join(prop_box(r) for r in pp) + "</div>" + locked)
    else:
        pk_html += (f"<h3 class='sh' id='{tid}-pprops'>Player prop picks</h3><div class='card props-card'><div class='sub' style='margin:0'>{esc(script_txt)} No texas222 prop reaches PLAY tonight. Every line is graded in section 8; LEANs are logged for tracking only.</div></div>" + locked)
    sec = lambda sid: f'{tid}-{sid}'
    nav = ''.join(f"<a href='#{sec(s)}'>{lbl}</a>" for s, lbl in (('picks','Picks'),('dec','Price check'),('audit','Audit'),('env','Rest &amp; travel'),('inj','Injuries'),('exit','Form'),('lineups','Team context'),('proj','Projection'),('tt','Team totals'),('first','1st half'),('props','Player props'),('pra','PRA &amp; fair prices'),('exp','Experts'),('frame','Framework')))
    groups = {}
    for r in graded: groups.setdefault(r['grp'], []).append(r)
    dec = ''
    for gname in ('GAME','TEAM TOTALS','FIRST HALF'):
        dec += f"<tr class='grp'><td colspan='8'>{gname} MARKETS</td></tr>" + ''.join(row_html(r, PICKED) for r in groups.get(gname, []))
    dec += "<tr class='grp'><td colspan='8'>PLAYER PROPS · texas222, better side of each line</td></tr>"
    for r in sorted(priced, key=lambda r: -r['edge']):
        pk = best.get(r['pl']) is r and r['call'] == 'PLAY'
        dec += (f"<tr{' class=\'pickrow\'' if pk else ''}><td><b>{esc(r['pl'])} {esc(r['lab'])}</b>{' <span class=\'tag t-a\'>Card pick</span>' if pk else ''}{' <span class=\'tag t-d\'>same player</span>' if r.get('nested') else ''}</td><td class='num'>{fmt(r['price'])}</td><td class='num'>{pct(r['est'])}</td><td class='num'>{pct(be(r['price']))}</td>"
                f"<td class='num'>{r['edge']:+.1f}</td><td class='{CALLCLS[r['call']]}'>{r['call'] + (' · tracking' if r['call'] == 'LEAN' else '')}</td><td><span class='tag {tag(r['conf'])}'>{r['conf']}</span></td><td>{esc(r['basis'])}</td></tr>")
    notes = NOTES.get(key, [])
    audit = ''.join(f"<tr><td>{esc(c)}</td><td>{esc(s)}</td><td>{esc(w)}</td></tr>" for c, s, w in notes) or "<tr><td colspan='3' class='none'>No published claim checked for this game changed a read.</td></tr>"
    flag = esc(notes[0][2]) if notes else 'Nothing in the previews changes the read.'
    rest_txt = lambda T: 'season opener (no games yet)' if T['rest'] >= 99 else ('back-to-back (played last night)' if T['rest'] == 0 else f"{T['rest']} day{'s' if T['rest']!=1 else ''} off")
    inj_rows = ''.join(f"<tr><td>{esc(t)}</td><td>{esc(x)}</td></tr>" for t, L_ in ((a, g['injA']), (h, g['injH'])) for x in L_) or "<tr><td colspan='2' class='none'>No one listed.</td></tr>"
    mA, mH = novig(g['la']['ml'], g['lh']['ml'])
    bars = ''.join(f"<tr><td style='width:240px'>{lbl}</td><td><div class='bar'><i style='width:{100*v:.1f}%'></i></div></td><td class='num'>{pct(v)}</td></tr>" for lbl, v in (
        (f'{h} model', g['pH']), (f'{h} texas222 no-vig', mH), (f'{a} model', g['pA']), (f'{a} texas222 no-vig', mA)))
    tot_line = (g['la']['tot'] if g['la']['tot'][0]=='O' else g['lh']['tot'])[1]
    stA, stH = _STB[a], _STB[h]
    ctx = ''.join([
        cmp_row('Record this season', (A['rec'] if A['gp'] else 'no games', stA['pct'] if A['gp'] else None), (H['rec'] if H['gp'] else 'no games', stH['pct'] if H['gp'] else None), 'hi'),
        cmp_row('Last season', (f"{A['last_rec']} · net {A['lnet']:+.1f}", A['lnet']), (f"{H['last_rec']} · net {H['lnet']:+.1f}", H['lnet']), 'hi'),
        "<tr class='grp'><td>LAST SEASON (NBA.com)</td><td class='ca'></td><td class='ch'></td></tr>",
        cmp_row('Offensive rating', (f"{A['lo']:.1f}", A['lo']), (f"{H['lo']:.1f}", H['lo']), 'hi'),
        cmp_row('Defensive rating', (f"{A['ld']:.1f}", A['ld']), (f"{H['ld']:.1f}", H['ld']), 'lo'),
        cmp_row('Pace', (f"{A['lpace']:.1f}", None), (f"{H['lpace']:.1f}", None), None),
        "<tr class='grp'><td>THIS SEASON</td><td class='ca'></td><td class='ch'></td></tr>",
        cmp_row('Offensive rating', (f"{A['no']:.1f}" if A['gp'] else '·', A['no'] if A['gp'] else None), (f"{H['no']:.1f}" if H['gp'] else '·', H['no'] if H['gp'] else None), 'hi'),
        cmp_row('Defensive rating', (f"{A['nd']:.1f}" if A['gp'] else '·', A['nd'] if A['gp'] else None), (f"{H['nd']:.1f}" if H['gp'] else '·', H['nd'] if H['gp'] else None), 'lo'),
        cmp_row('Pace', (f"{A['npace']:.1f}" if A['gp'] else '·', None), (f"{H['npace']:.1f}" if H['gp'] else '·', None), None),
        "<tr class='grp'><td>USED ON CARD</td><td class='ca'></td><td class='ch'></td></tr>",
        cmp_row('Offense (blend)', (f"{g['oA']:.1f}", g['oA']), (f"{g['oH']:.1f}", g['oH']), 'hi'),
        cmp_row('Defense (blend)', (f"{g['dA']:.1f}", g['dA']), (f"{g['dH']:.1f}", g['dH']), 'lo'),
        cmp_row('Rest', (rest_txt(A), None), (rest_txt(H), None), None),
        cmp_row('Series price' if a in _SERIES else 'Title odds', (fmt(_cup(a)), -_imp(_cup(a)) * -1), (fmt(_cup(h)), _imp(_cup(h))), 'hi'),
    ])
    calc = (f"Possessions        {g['pace']:5.1f}   ({A['lpace']:.1f} and {H['lpace']:.1f} pace, blended with this season, vs league {LG['pace']:.1f})\n"
            f"{a} efficiency     {g['oA']:.1f} off vs {h} {g['dH']:.1f} def → {g['oA']+g['dH']-LG['rtg']:.1f} per 100\n"
            f"{h} efficiency     {g['oH']:.1f} off vs {a} {g['dA']:.1f} def → {g['oH']+g['dA']-LG['rtg']:.1f} per 100\n"
            + (f"Home court         {h} +{1.4:.1f}, {a} -{1.4:.1f}" if not g.get('ctx') else f"Context            {a} {g['ctx']['dA']:+.1f}, {h} {g['ctx']['dH']:+.1f} points") + (f"   ·   {'; '.join(g['adj'])}" if g['adj'] else '') + "\n"
            f"Weights            this season {g['wA']*100:.0f}% {a}, {g['wH']*100:.0f}% {h} (games / (games + 12))\n"
            "──────────────────────────────────────────────────────────\n"
            f"Projected points   {a} {g['ptsA']:.1f}   {h} {g['ptsH']:.1f}   total {g['total']:.1f}\n"
            f"Margin             {h} {g['margin']:+.1f}   (sd 12.5)\n"
            f"Win                {a} {pct(g['pA'])}   {h} {pct(g['pH'])}" + (f"   ·   Sportradar {h} {g['sr']:.1f}%" if g['sr'] else '') + "\n"
            f"texas222 no-vig    {a} {pct(mA)}   {h} {pct(mH)}   spread {h} {sp(g['lh']['sp'][0])}   total {tot_line:g}")
    proj_score = f"{h} {round(g['ptsH'])}, {a} {round(g['ptsA'])}" if g['ptsH'] >= g['ptsA'] else f"{a} {round(g['ptsA'])}, {h} {round(g['ptsH'])}"
    # fair prices for priced and PRA lines
    def fair_rows():
        rows = ''
        for side, team in (('A', a), ('H', h)):
            rows += f"<tr class='grp'><td colspan='6'><span class='{'tmA' if side=='A' else 'tmH'}'>{esc(NAMES[team])}</span> · scripted for {SCRIPT[key]['tt'][team]:.0f} points</td></tr>"
            for pl in sorted({x['pl'] for x in PROPS if x['game']==key and x['pl'] in SEASON and SEASON[x['pl']]['team']==team}):
                tmp = prop_model(g, team, pl, 'pra', 0)
                if not tmp or tmp['base'] != 'last season': continue
                line = math.floor(tmp['raw']) + 0.5
                m = prop_model(g, team, pl, 'pra', line)
                rows += (f"<tr><td>{esc(pl)}</td><td class='num'>{m['ls_avg']:.1f}</td><td class='num'>{', '.join(map(str, m['cur'])) or 'no games'}</td><td class='num'>{line:g}</td>"
                         f"<td class='num'>{m['mu']:.1f}</td><td class='num'>o {fmt(amer(m['blend']))} · u {fmt(amer(1-m['blend']))}</td></tr>")
        return rows
    exp = ''.join(f"<tr><td>{esc(n)}</td><td>{esc(p)}</td><td class='num'>{esc(o)}</td></tr>" for n, p, o in EXPERTS.get(key, [])) or "<tr><td colspan='3' class='none'>No named expert pick pulled for this game.</td></tr>"
    carry = [r for r in graded if r['call'] in ('PLAY','LEAN') and not r.get('corr')] + pp
    return f"""
<section class='panel' id='panel-{tid}' role='tabpanel' aria-labelledby='tab-{tid}' style='--AWAY:{COLORS[a][0]};--AWAYD:{COLORS[a][1]};--HOME:{COLORS[h][0]};--HOMED:{COLORS[h][1]}' hidden>
<div class='top'><h2 class='gh'><a class='tmA tl' href='{URL[a]}' target='_blank' rel='noopener'>{esc(NAMES[a])}</a> <span class='at'>at</span> <a class='tmH tl' href='{URL[h]}' target='_blank' rel='noopener'>{esc(NAMES[h])}</a></h2></div>
<div class='sub'>{DOW} {DATE_S}, 2026 · {g['time']} Phoenix tip · {esc(g['venue'])} · {a} {A['rec'] if A['gp'] else '0-0'}, {h} {H['rec'] if H['gp'] else '0-0'} · {READ}</div>
<div class='nav'>{nav}</div>
{pk_html}

<h3 class='sh' id='{sec('dec')}'>0 · Price check vs texas222</h3>
<div class='sub'>This table only asks whether texas222's price beats a fair price for each market. The card's picks, marked <span class='tag t-a'>Card pick</span>, come from the signal scoring above. "Fair price" means no extra edge in the number, not that the pick is wrong. Player props are picked on price, so their PLAY or LEAN is the pick.</div>
<div class='scroll'><table>
<thead><tr><th>Market</th><th>texas222</th><th>Est.</th><th>Break-even</th><th>Edge pts</th><th>Price grade</th><th>Conf</th><th>Why</th></tr></thead><tbody>{dec}</tbody></table></div>
<div class='card' style='margin-top:12px'><b>Correlation flags.</b> Side markets (moneyline, spread, 1st half side) are one thesis; totals markets (game, team, 1st half) are another. Only the best edge in each family is carried. Props are one per player; a big over on a player from the team you fade works against that side read.</div>

<h3 class='sh' id='{sec('audit')}'>⚠ · Preview audit</h3>
<div class='scroll'><table><thead><tr><th>Claim</th><th>Source</th><th>What the data says</th></tr></thead><tbody>{audit}</tbody></table></div>
<div class='card flag' style='margin-top:10px'><h4>The one that matters</h4>{flag}</div>

<h3 class='sh' id='{sec('env')}'>1 · Rest, travel &amp; venue</h3>
<div class='card'><table class='kv'><tbody>
<tr><td>Venue</td><td>{esc(g['venue'])}</td></tr>
<tr><td>Tip</td><td>{g['time']} Phoenix</td></tr>
<tr><td>{a} rest</td><td>{rest_txt(A)} · last game {esc(A['last'])} · {esc(TRAVEL.get(a,''))}</td></tr>
<tr><td>{h} rest</td><td>{rest_txt(H)} · last game {esc(H['last'])} · {esc(TRAVEL.get(h,''))}</td></tr>
<tr><td>Schedule spot</td><td>{_spot_txt(g)}</td></tr>
{_venue_rows(g)}
</tbody></table></div>

<h3 class='sh' id='{sec('inj')}'>2 · Injury report</h3>
<div class='scroll'><table><thead><tr><th>Team</th><th>Player · status (injury)</th></tr></thead><tbody>{inj_rows}</tbody></table></div>
<div class='card' style='margin-top:10px'><ul class='nl'><li>Source: ESPN injuries feed, which carries the NBA's official report designations (out, doubtful, questionable, day-to-day). Read about 9:05 AM Phoenix.</li><li>{esc(injnote(a, h, key))}</li><li>A starter ruled out changes the projection by his impact (about 2 to 6 points for a star). Recheck at warmups.</li></ul></div>

<h3 class='sh' id='{sec('exit')}'>3 · Form</h3>
<div class='card'><div class='calc'>{a}   this season {A['rec'] if A['gp'] else '0-0'}   last game {A['last']}
{h}   this season {H['rec'] if H['gp'] else '0-0'}   last game {H['last']}
{a}   last season {A['last_rec']}   net rating {A['lnet']:+.1f}
{h}   last season {H['last_rec']}   net rating {H['lnet']:+.1f}</div>
<ul class='nl'><li>Opening week: one game or none, so last season's ratings carry almost all of the projection (this season weighs games / (games + 12)).</li><li>Roster changes since last season are not in last season's numbers. Title odds stand in for the roster read.</li></ul></div>

<h3 class='sh' id='{sec('lineups')}'>4 · Team context</h3>
<div class='scroll'><table class='cmp'><thead><tr><th></th><th class='ca'><span class='tmA'>{esc(NAMES[a])}</span></th><th class='ch'><span class='tmH'>{esc(NAMES[h])}</span></th></tr></thead><tbody>{ctx}</tbody></table></div>

<h3 class='sh' id='{sec('proj')}'>5 · Projection &amp; total</h3>
<div class='card'><div class='calc'>{calc}</div>
<div class='lbl'>Win probability</div><table style='margin-top:6px'><tbody>{bars}</tbody></table>
<div class='lbl'>Projected score</div><ul class='nl'><li>{proj_score}</li></ul>
<div class='lbl'>Public split</div><ul class='nl'><li>{esc(PUBLIC.get(key, 'No split found.'))}</li></ul>
<div class='lbl'>What makes me doubt the read</div><ul class='nl'><li>Ratings are mostly last season's. Offseason trades and signings are only in the market price and title odds.</li><li>Normal margin with sd 12.5 is a league-wide spread; star-heavy or blowout-prone matchups can be wider.</li></ul></div>

<h3 class='sh' id='{sec('tt')}'>6 · Team totals</h3>
<div class='scroll'><table><thead><tr><th>Market</th><th>texas222</th><th>Est.</th><th>Break-even</th><th>Edge pts</th><th>Price grade</th><th>Conf</th><th>Basis</th></tr></thead><tbody>{''.join(row_html(r, PICKED) for r in groups.get('TEAM TOTALS', [])) or "<tr><td colspan='8'>texas222 had not posted team totals at this read.</td></tr>"}</tbody></table></div>

<h3 class='sh' id='{sec('first')}'>7 · 1st half</h3>
<div class='scroll'><table><thead><tr><th>Market</th><th>texas222</th><th>Est.</th><th>Break-even</th><th>Edge pts</th><th>Price grade</th><th>Conf</th><th>Basis</th></tr></thead><tbody>{''.join(row_html(r, PICKED) for r in groups.get('FIRST HALF', []))}</tbody></table></div>
<div class='card' style='margin-top:10px'><ul class='nl'><li>1st half projection uses half the game margin and 49% of the game total. Period markets grade LOW at most.</li></ul></div>

<h3 class='sh' id='{sec('props')}'>8 · Player props at texas222</h3>
<div class='sub'>Every posted texas222 prop, better side shown. Baseline is last season's full NBA.com game log (per-minute rate and record against tonight's line). This season's games are shown as a trend only and move the minutes estimate slightly. The projection uses the card's game script: texas222 team totals shifted toward the picked total, and 5% fewer starter minutes when the spread is 8 or more. Estimate = 40% model (half rate, half last-season record) and 60% the posted price. Rows marked Card pick are the props taken.</div>
<div class='scroll'><table><thead><tr><th>Player</th><th>Prop</th><th>Price</th><th>Call</th><th>Last season</th><th>This season</th><th>Tonight</th><th>Est. vs needed</th><th>Script</th></tr></thead><tbody>{''.join(f"<tr{' class=\'pickrow\'' if best.get(r['pl']) is r else ''}><td>{esc(r['pl'])}<div class='num'>{esc(r['team'])}</div></td><td><b>{esc(r['lab'])}</b>{' <span class=\'tag t-a\'>Card pick</span>' if best.get(r['pl']) is r else ''}</td><td class='num'>{fmt(r['price'])}</td><td class='{CALLCLS[r['call']]}'>{r['call']}</td><td class='num'>{esc(r['ls'])}</td><td class='num'>{esc(r['cur_txt'])}</td><td class='num'>{r['mu']:.1f} in {r['mins']:.0f} min</td><td class='num'>{pct(r['est'])} vs {pct(be(r['price']))}</td><td>{'fits' if r['fit']>0 else ('against' if r['fit']<0 else 'neutral')}</td></tr>" for r in sorted(priced, key=lambda r: (r['team'], r['pl'], r['stat'])))}</tbody></table></div>

<h3 class='sh' id='{sec('pra')}'>9 · PRA and fair prices</h3>
<div class='card flag'><b>texas222 posts no PRA (points + rebounds + assists) props tonight.</b> Fair lines below are built the same way as section 8 (last season baseline, tonight's game script), for shopping elsewhere. Bet only at or better than the fair price.</div>
<div class='scroll'><table><thead><tr><th>Player</th><th>Last season PRA</th><th>This season</th><th>Fair line</th><th>Tonight</th><th>Fair price</th></tr></thead><tbody>{fair_rows()}</tbody></table></div>

<h3 class='sh' id='{sec('exp')}'>10 · Expert picks (named only)</h3>
<div class='scroll'><table><thead><tr><th>Expert</th><th>Pick</th><th>Price</th></tr></thead><tbody>{exp}</tbody></table></div>

<h3 class='sh' id='{sec('frame')}'>11 · Correlation &amp; framework</h3>
<div class='card'><div class='lbl'>Carried on price</div><ul class='nl'>{''.join(f"<li>{esc(r.get('m') or (r['pl']+' '+r['lab']))} at {fmt(r['price'])}: {r['call']}, {r['edge']:+.1f} pts</li>" for r in carry) or '<li>Nothing. No bet is a valid output.</li>'}</ul>
<div class='lbl'>Phase &amp; gate</div><ul class='nl'><li>Hand-read NBA card, first night. No backtest, so calibration is unmeasured: estimates are 40% model, 60% texas222 no-vig, and nothing grades HIGH.</li><li>Tracked in its own ledger, never pooled with the NHL, MLB or football cards.</li><li>Re-run if a starter is ruled out.</li></ul></div>
<details><summary>What was left out, and why</summary><ul class='nl'>
<li>PRA, steals and blocks: PRA is not posted at texas222 (fair prices in section 9); steals and blocks are posted for Denver and Oklahoma City but not graded.</li>
<li>Quarter lines and 2nd half lines were not graded.</li>
<li>Line movement uses Action Network's open and texas222's current number; one texas222 read only.</li>
<li>Player minutes and lineup data for tonight were not pulled; game logs carry the role.</li>
</ul></details>
</section>"""

panels = ''.join(game_panel(g) for g in games)

# ---------------- slate overview
order = {'PLAY':0,'LEAN':1}
ALLROWS.sort(key=lambda r: (order[r[5]], -r[4]))
GT = {f"{g['a']}-{g['h']}": g['time'] for g in games}
ov_rows = ''.join(f"<tr><td><a class='glink' href='#{tid}' data-tab='{tid}'>{esc(k.replace('-',' @ '))}</a></td><td class='num'>{GT[k]}</td><td><b>{esc(m)}</b></td><td class='num'>{esc(ps)}</td><td class='num'>{pct(est)}</td><td class='num'>{edge:+.1f}</td><td class='{CALLCLS[c]}'>{lbl}</td><td><span class='tag {tag(cf)}'>{cf}</span></td></tr>" for k, m, ps, est, edge, c, cf, tid, lbl in ALLROWS)
slate_games = ''.join(f"<tr><td><a class='glink' href='#{g['a'].lower()}-{g['h'].lower()}' data-tab='{g['a'].lower()}-{g['h'].lower()}'>{g['a']} @ {g['h']}</a></td><td class='num'>{g['time']}</td><td class='num'>{fmt(g['la']['ml'])} / {fmt(g['lh']['ml'])}</td><td class='num'>{g['h']} {sp(g['lh']['sp'][0])}</td><td class='num'>{(g['la']['tot'] if g['la']['tot'][0]=='O' else g['lh']['tot'])[1]:g}</td><td class='num'>{g['ptsA']:.1f} – {g['ptsH']:.1f}</td><td class='num'>{pct(g['pH'])}</td></tr>" for g in games)
def why_html(x):
    parts = x.split('. Against: ')
    return esc(parts[0]) + (f". <b class='ag'>Against:</b> <span class='agt'>{esc(parts[1])}</span>" if len(parts) > 1 else '')
def _tg(p):
    if p.get('nopick'): return "<span class='tag t-np'>No pick</span>"
    return f"<span class='tag t-rule'>{esc(p['rule_label'])}</span> <span class='num'>{esc(p['rule_rec'])}</span>" + (" <span class='tag t-d'>conflicting</span>" if p['conf'] else '')
def _pt(p): return "<b>No pick</b>" if p.get('nopick') else f"<b>{esc(p['text'])}</b> <span class='num'>{fmt(p['price'])}</span>"
def _pw(p, lab): return f"<b>{esc(lab)}:</b> " + (esc(p['why']) if p.get('nopick') else why_html(p['short']) + '.')
pk_rows = ''.join(f"<tr><td><a class='glink' href='#{k.lower()}' data-tab='{k.lower()}'>{esc(k.replace('-',' @ '))}</a></td><td class='num'>{GT[k]}</td><td>{_pt(s)}</td><td>{_tg(s)}</td><td>{_pt(t)}</td><td>{_tg(t)}</td><td class='whyc'>{_pw(s, 'Side' if s.get('nopick') else s['team_side'])}<br>{_pw(t, 'Total')}</td></tr>" for k, s, t in PICKS)
pp_rows = ''.join(f"<tr><td><a class='glink' href='#{tid}' data-tab='{tid}'>{esc(k.replace('-',' @ '))}</a></td><td class='num'>{tm}</td><td><b>{esc(x['pl'])}</b> {esc(x['lab'])}<div class='num'>{esc(x['team'])}</div></td><td class='num'>{fmt(x['price'])}</td><td><span class='tag {'t-a' if x['call']=='PLAY' else 't-c'}'>{x['call']}</span> <span class='tag {tag(x['conf'])}'>{x['conf']}</span></td><td class='num'>{pct(x['est'])} vs {pct(be(x['price']))}</td><td class='whyc'>{why_html(x['short'])}.</td></tr>" for k, tid, tm, x in sorted([z for z in PROPPICKS if z[3]['call'] == 'PLAY'], key=lambda z: -z[3]['edge']))
props_tbl = f"<h3 class='sh'>Player prop picks</h3><div class='scroll'><table><thead><tr><th>Game</th><th>Tip (Phoenix)</th><th>Prop</th><th>texas222</th><th>Call</th><th>Projected vs needed</th><th>Why</th></tr></thead><tbody>{pp_rows or "<tr><td colspan='7' class='none'>No prop picks tonight.</td></tr>"}</tbody></table></div><div class='sub' style='margin-top:8px'>Only PLAYs are card picks. Graded on last season's per-minute rate blended with this season's (games / (games + 10); hit rates games / (games + 20)), tonight's game script, the opponent's rebounds, assists and 3PM allowed (half weight) and a usage boost when teammates are out. PLAY clears break-even by 3+ points at MED (same team, 20+ games last season, record and rate agree) at a price of -150 or better, never plus money. Points unders at LEAN level (1.5+ at MED, 3+ at LOW) also count as PLAYs at -150 or better. Other LEANs, and PLAY edges at plus money or worse than -150, are logged for tracking only. Props that fight a Solid or Strong total pick are not taken. One prop per player.</div>"
picks_tbl = f"<h3 class='sh'>Tonight's picks</h3><div class='scroll'><table><thead><tr><th>Game</th><th>Tip (Phoenix)</th><th>Side or spread</th><th>Rule · season</th><th>Total</th><th>Rule · season</th><th>Why</th></tr></thead><tbody>{pk_rows}</tbody></table></div><div class='sub' style='margin-top:8px'>Picks use the card's projection plus Action Network betting signals (sharp action, reverse line movement, fade the public, money vs tickets, PRO systems, big money). They say which side the data favors, not whether the price is good. Open a game for its signal checklist.</div>"

def _rule_tbl():
    R_ = RSTATE.get('rules', {})
    if not R_: return ''
    rows = ''
    for rid, s in R_.items():
        if rid == 'OVER':
            rows += "<tr><td>Over</td><td>off</td><td colspan='4'>No over test has a winning record yet, so overs are No pick.</td></tr>"; continue
        rows += (f"<tr><td>{esc(PR.RULES[rid]['label'])}<div class='num'>{esc(s.get('desc',''))}</div></td><td>{'on' if s.get('on') else 'off'}{' · warning' if s.get('warn') else ''}</td>"
                 f"<td class='num'>{esc(PR.rec_txt(s.get('season')))}</td><td class='num'>{esc(PR.rec_txt(s.get('month')))}</td><td class='num'>{esc(PR.rec_txt(s.get('last14')))}</td>"
                 f"<td class='num'>{esc(s['other']['variant'])}: {esc(PR.rec_txt(s['other']['season']))}</td></tr>")
    log = RSTATE.get('log') or []
    return (f"<h3 class='sh'>Rule records (re-check {esc(RSTATE.get('updated',''))}, every game played)</h3><div class='scroll'><table class='rt'><thead><tr><th>Rule</th><th>Status</th><th class='r'>Season</th><th class='r'>This month</th><th class='r'>Last 14 days</th><th class='r'>Other version</th></tr></thead><tbody>{rows}</tbody></table></div>"
            f"<div class='sub'>Re-checked daily on every game played: moneylines at the cleaned closing median, spreads and totals at -110. A rule switches off at 20+ picks with negative season units and back on when positive; a rule moves to its other version only after 30+ picks when that version wins as often, makes more units, and is positive for the season and the month. Price limits are locked: favorite no longer than -200, underdog +100 to +200."
            + (f" Recent changes: {esc('; '.join(log[-3:]))}." if log else '') + "</div>")

def _recheck_html():
    """The daily re-check's full test battery (recheck_report.md), one collapsible table per test group."""
    f = D/'recheck_report.md'
    if not f.exists(): return ''
    out, cur, rows = [], None, []
    def flush():
        if cur and rows:
            hd = rows[0]; body = rows[2:]
            th = ''.join(f"<th{' class=\'r\'' if i else ''}>{esc(c)}</th>" for i, c in enumerate(hd))
            tb = ''.join('<tr>' + ''.join(f"<td{' class=\'num r\'' if i else ''}>{esc(c)}</td>" for i, c in enumerate(rw)) + '</tr>' for rw in body)
            out.append(f"<details class='rc'><summary>{esc(cur)}</summary><div class='scroll'><table class='rt'><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div></details>")
    for ln in f.read_text().splitlines():
        if ln.startswith('### '):
            flush(); cur, rows = ln[4:], []
        elif ln.startswith('|') and cur:
            rows.append([c.strip() for c in ln.strip().strip('|').split('|')])
    flush()
    if not out: return ''
    return (f"<h3 class='sh'>Re-check: every test, every game played</h3><div class='sub'>Rerun daily before the card: all games played this season, not only the card's picks. "
            f"Season to date, then each month. Moneylines at the cleaned closing median, spreads and totals at -110. Tap a group to open it.</div>" + ''.join(out))

results_panel = """
<section class='panel' id='panel-results' role='tabpanel' aria-labelledby='tab-results' hidden>
<div class='sub'>Season tracker for every card pick since Oct 22, 2026: one side-or-spread pick and one total per game, plus the player prop PLAYs, graded from final scores and box scores each day. Prop LEANs are logged and graded for tracking only: they are left out of the record, units and filters unless you pick LEAN in the Tier filter, and shown separately in the tier tables. Units assume 1 unit risked per pick at the texas222 price shown on the card.</div>
<div id='res-state' class='card'>Loading the pick ledger…</div>
<div id='res-body' hidden>
<div class='tiles' id='res-tiles'></div>
<h3 class='sh'>By rule</h3><div class='scroll'><table class='rt'><thead><tr><th>Rule (card picks)</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-rule'></tbody></table></div>
@@RULE_TBL@@
<h3 class='sh'>By tier</h3><div class='scroll'><table class='rt'><thead><tr><th>Tier</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-tier'></tbody></table></div>
<h3 class='sh'>By market</h3><div class='scroll'><table class='rt'><thead><tr><th>Market</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-mkt'></tbody></table></div>
<h3 class='sh'>By market and tier</h3><div class='scroll'><table class='rt mt'><thead><tr><th>Market · tier</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-mt'></tbody></table></div>
<h3 class='sh'>Filter</h3>
<div class='filters' id='filters'>
<details class='ms' data-f='date'><summary><span class='fl'>Date</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='dow'><summary><span class='fl'>Day of week</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='team'><summary><span class='fl'>Team</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='market'><summary><span class='fl'>Market</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='tier'><summary><span class='fl'>Tier</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='result'><summary><span class='fl'>Result</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<button type='button' id='f-clear'>Clear filters</button>
</div>
<div class='card ftot' id='f-tot'></div>
<details class='rd' id='d-log'><summary>Every pick <span class='num' id='c-log'></span></summary><div class='scroll'><table class='rt log'><thead><tr><th>Date</th><th>Game</th><th>Market</th><th>Pick</th><th class='r'>Price</th><th>Tier</th><th>Final</th><th>Result</th><th class='r'>Units</th></tr></thead><tbody id='res-log'></tbody><tfoot id='res-log-tot'></tfoot></table></div></details>
</div>
</section>"""

tabs = ("<button class='tab' role='tab' id='tab-slate' aria-controls='panel-slate' data-tab='slate'>Slate</button>"
        "<button class='tab' role='tab' id='tab-standings' aria-controls='panel-standings' data-tab='standings'>Standings<span>Title odds</span></button>"
        + ''.join(f"<button class='tab' role='tab' id='tab-{g['a'].lower()}-{g['h'].lower()}' aria-controls='panel-{g['a'].lower()}-{g['h'].lower()}' data-tab='{g['a'].lower()}-{g['h'].lower()}' aria-label='{g['a']} at {g['h']}'>{g['a']} @ {g['h']}<span>{g['time'].replace(' PM','')}</span></button>" for g in games)
        + "<button class='tab' role='tab' id='tab-results' aria-controls='panel-results' data-tab='results'>Results<span>Season tracker</span></button>")

RESULTS_JS = (D/'results.js').read_text()
CSS = (D/'card.css').read_text()
page = f"""<title>NBA Slate Card · {DATE_S}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>{CSS}</style>
<div class='wrap'>
<header class='mast'><div><div class='eyebrow'>NBA game cards · {DATE_L}</div><h1>{len(games)}-game slate</h1></div>
<button id='tt-btn' type='button'>Toggle theme</button></header>
<div class='tabs' role='tablist'>{tabs}</div>

<section class='panel' id='panel-slate' role='tabpanel' aria-labelledby='tab-slate'>
<div class='sub'>texas222 is the book of record. {READ}. Each game tab has the full card: price check, audit, rest and travel, injuries, team context, projection, team totals, 1st half, and player props.</div>
{picks_tbl}
{props_tbl}
<h3 class='sh'>Price check: markets priced better than fair</h3>
<div class='scroll'><table><thead><tr><th>Game</th><th>Tip (Phoenix)</th><th>Market</th><th>Price · book</th><th>Est.</th><th>Edge pts</th><th>Price grade</th><th>Conf</th></tr></thead><tbody>{ov_rows or "<tr><td colspan='8' class='none'>No market priced better than fair tonight.</td></tr>"}</tbody></table></div>
<div class='sub' style='margin-top:9px'>A second view, separate from Tonight's picks: game markets where texas222's number beats a fair price (<b>Value</b> 3+ points over break-even at MED, <b>Slight value</b> 1.5 to 3), plus the prop picks. · <b>MED</b> no starter in doubt and, for props, record and rate agree over 9+ games with the same team · <b>LOW</b> 1st half markets, or a prop where record and rate disagree or the player changed teams. Nothing grades HIGH: no NBA backtest exists.</div>
<h3 class='sh'>Board</h3>
<div class='scroll'><table><thead><tr><th>Game</th><th>Phoenix</th><th>ML (away / home)</th><th>Spread</th><th>Total</th><th>Proj. points</th><th>Home win (model)</th></tr></thead><tbody>{slate_games}</tbody></table></div>
<div class='card' style='margin-top:12px'><div class='lbl'>How the numbers are built</div><ul class='nl'>
<li>Offensive and defensive rating and pace from NBA.com, last season blended with this season by games played (weight games / (games + 12)). Each team's points = possessions x (its offense + opponent defense - league {LG['rtg']:.0f}) / 100.</li>
<li>Context layer, learned from NBA.com game logs and refreshed daily: home edge (league number from both seasons, each team's home/road split counts 30%), venue scoring, fatigue (back-to-back with or without travel, 3 games in 4 nights, 2+ days rest; measured vs each team's own home or road average and shrunk toward -1.5), and division strength (schedule credit plus a 1-point signal at a 2+ point gap). A starter ruled out subtracts his impact. Margin is normal with sd 12.5, total with sd 18.</li><li>Props carry the same context: half of what venue, fatigue and division add goes into the scripted team total; each player's home or road average moves his projection by games / (games + 40); back-to-backs apply the league's learned minutes and per-minute ratios.</li>
<li>Calibration is unmeasured, so every estimate is 40% model and 60% texas222 no-vig (moneyline model is averaged with Sportradar first).</li>
<li>Props blend the player's last 20 games with a rate estimate (average shrunk 30% toward the posted line), then 40/60 with texas222's posted price.</li></ul></div>
<div class='card flag'><b>Before betting:</b> recheck the injury report at warmups. A starter ruled out voids that game's grades.</div>
</section>
{results_panel.replace('@@RULE_TBL@@', _rule_tbl() + _recheck_html())}
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
(D/'nba-slate.html').write_text(page)

# ---------------- ledger docs for the tracker
docs = []
for (k, s, t) in PICKS:
    a, h = k.split('-'); gm = next(g for g in games if g['a']==a)
    for kind, p in (('side', s), ('total', t)):
        if p.get('nopick') or p.get('locked'): continue
        docs.append({'id': f'{DATE}_{k}_{kind}', 'data': dict(date=DATE, game=f'{a} @ {h}', away=a, home=h, time=gm['time'], market=p['market'], pick=p['text'],
                     price=int(p['price']), tier=p['tier'], conflicting=bool(p['conf']), projected=round(p['prob'], 4), result='pending', final='',
                     rule=p['rule'], rule_variant=p['rule_variant'])})
for (k, tid, tm, r) in PROPPICKS:
    a, h = k.split('-')
    docs.append({'id': f"{DATE}_{k}_prop_{re.sub(r'[^A-Za-z0-9]', '', r['pl'])}", 'data': dict(date=DATE, game=f'{a} @ {h}', away=a, home=h, time=tm, market='Prop',
                 pick=f"{r['pl']} {r['lab']}", player=r['pl'], team=r['team'], stat=r['stat'], side=r['side'], line=r['line'], price=int(r['price']), book='texas222',
                 tier=r['call'], conflicting=False, projected=round(r['est'], 4), result='pending', final='',
                 conf=r['conf'], edge=round(r['edge'], 2), model='v2', tracking=(r['call'] == 'LEAN' or r['inactive']), prop_rule=r['rule_key'])})
(D/'ledger_today.json').write_text(json.dumps(docs, indent=1))
(D/'shadow_raw.json').write_text(json.dumps(SHADOW, indent=1, default=str))
# log today's pick-time inputs for the season re-check (Action Network codes and splits, injuries, second source, texas222 lines)
_ci_p = D/'season'/'card_inputs.json'
_ci = json.loads(_ci_p.read_text()) if _ci_p.exists() else {}
_ci[DATE] = dict(an={k: v for k, v in AN.items()}, inj={t: v[0] for t, v in INJ_ADJ.items()}, dk=DK,
                 t222={g['a']+'-'+g['h']: dict(sp_a=g['la']['sp'][0], tot=(g['la']['tot'] if g['la']['tot'][0]=='O' else g['lh']['tot'])[1], ml_a=g['la']['ml'], ml_h=g['lh']['ml']) for g in games},
                 # card model numbers at pick time (Trina, Nov 6): home margin, total, pace, model and blended home win, injury adjustments
                 model={g['a']+'-'+g['h']: dict(home_margin=round(g['margin'], 2), total=round(g['total'], 1), pace=round(g['pace'], 1), model_home_win=round(g['pH'], 3), sr_home_win=g['sr'],
                        blended_home_win=round(0.4*(g['pH'] if g['sr'] is None else (g['pH'] + g['sr']/100)/2) + 0.6*novig(g['la']['ml'], g['lh']['ml'])[1], 3),
                        inj={t: INJ_ADJ[t][0] for t in (g['a'], g['h']) if t in INJ_ADJ}) for g in games})
_ci_p.write_text(json.dumps(_ci, indent=0))
for k, s, t in PICKS: print(k, '|', s['text'], '' if s.get('nopick') else fmt(s['price']), s.get('rule') or '', s['score'], '|', t['text'], '' if t.get('nopick') else fmt(t['price']), t.get('rule') or '', t['score'])
for k, tid, tm, r in PROPPICKS: print('PROP', k, r['pl'], r['lab'], fmt(r['price']), r['call'], f"{r['edge']:+.1f}", r['conf'], 'INACTIVE' if r['inactive'] else '')
for k, r in HELDPROPS: print('HELD', k, r['pl'], r['side'], r['line'], r['stat'], r['held_reason'])
print('rows', len(ALLROWS))

# ---------------- hub data dump (Season Cards game docs and pick details)
def _j(x):
    if isinstance(x, dict): return {str(k): _j(v) for k, v in x.items() if not callable(v)}
    if isinstance(x, (list, tuple)): return [_j(v) for v in x]
    if isinstance(x, float): return round(x, 4)
    return x if isinstance(x, (int, str, bool, type(None))) else str(x)
HUB = dict(scores=SCORES, picks={k: dict(side={kk: vv for kk, vv in s.items()}, total={kk: vv for kk, vv in t.items()}) for k, s, t in PICKS},
           games={f"{g['a']}-{g['h']}": dict(a=g['a'], h=g['h'], time=g['time'], venue=g['venue'], margin=g['margin'], total=g['total'], pA=g['pA'], pH=g['pH'], ptsA=g['ptsA'], ptsH=g['ptsH'], pace=g['pace'], sr=g['sr'],
                     cover_h=g['cover']('H', g['lh']['sp'][0]), p_over=g['p_over']((g['la']['tot'] if g['la']['tot'][0]=='O' else g['lh']['tot'])[1]), la=g['la'], lh=g['lh'], adj=g['adj']) for g in games},
           props={k: [dict(pl=r['pl'], team=r['team'], stat=r['stat'], line=r['line'], side=r['side'], price=r['price'], est=r['est'], edge=r['edge'], call=r['call'], conf=r['conf'], mu=r['mu'],
                           held_reason=r.get('held_reason'), cur=r.get('cur'), ls_avg=r.get('ls_avg'), hits=r.get('hits'), ls_gp=r.get('ls_gp'), fr=r['fr'], ag=r['ag'], inactive=r.get('inactive', False)) for r in v] for k, v in PRICED_ALL.items()},
           logged=[(k, r['pl'], r['stat'], r['side']) for k, _, _, r in PROPPICKS], held=[(k, r['pl'], r['stat'], r['side']) for k, r in HELDPROPS])
(D/'hub_data.json').write_text(json.dumps(_j(HUB), indent=0))
