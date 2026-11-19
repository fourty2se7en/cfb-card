"""NBA slate model. Reads raw pulls, produces per-game analysis dicts.
Ratings: last season's NBA.com offensive/defensive rating and pace, blended with this season by games played (weight gp/(gp+12)).
Points = possessions x efficiency vs opponent. Context layer (context.py, learned from game logs and updated daily): home edge
learned league-wide and nudged by each team's home/road split; fatigue (back-to-back with or without travel, 3 games in 4 nights,
2+ days rest) learned from margins and points vs the team's own average; division strength schedule credit. WNBA games keep
home court +1.4 / -1.4 and back-to-back -1.5. Injuries: OUT/DOUBTFUL starters subtract their listed impact (INJ_ADJ). Margin is normal, sd 12.5;
total is normal, sd 18."""
import re, math, pathlib
from context import game_context, DIVNAME
D = pathlib.Path(__file__).parent

def be(o): return -o/(-o+100) if o < 0 else 100/(o+100)
def amer(p):
    p = min(max(p, 0.01), 0.99)
    return round(-100*p/(1-p)) if p >= 0.5 else round(100*(1-p)/p)
def fmt(o): return f'+{o:g}' if o > 0 else f'{o:g}'
def novig(a, b):
    x, y = be(a), be(b); return x/(x+y), y/(x+y)
def Phi(z): return 0.5*(1+math.erf(z/math.sqrt(2)))
def pois(l, k): return math.exp(-l)*l**k/math.factorial(k)
def p_ge(l, k): return 1 - sum(pois(l, i) for i in range(k))
def wilson(k, n, z=1.96):
    if n == 0: return (0, 1)
    p = k/n; d = 1+z*z/n; c = p+z*z/(2*n); r = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))
    return ((c-r)/d, (c+r)/d)

SD_M, SD_T, HCA = 12.5, 18.0, 1.4
WNBA_KEYS = {'GSV','ATD'}  # WNBA games: league ratings/pace and tighter spreads (40-minute games)

def parse_teams():
    T = {}
    for ln in (D/'teams_raw.txt').read_text().strip().splitlines()[1:]:
        f = [x.strip() for x in ln.split('|')]
        t = f[0]; l = f[1].split(); n = f[2].split()
        T[t] = dict(last_rec=l[0], lo=float(l[1]), ld=float(l[2]), lnet=float(l[3]), lpace=float(l[4]),
                    gp=int(n[0]), rec=n[1], no=float(n[2]), nd=float(n[3]), nnet=float(n[4]), npace=float(n[5]),
                    last=f[3], rest=int(f[4]))
    return T

def parse_t222():
    L = {}
    for ln in (D/'t222.txt').read_text().strip().splitlines()[1:]:
        t, rest = ln.split(': ', 1)
        f = [x.strip() for x in rest.split('|')]
        sp = re.match(r'([+-][\d.]+) ([+-]\d+)', f[0]).groups()
        tot = re.match(r'([OU])([\d.]+) ([+-]\d+)', f[1]).groups()
        tt = None if f[3] == 'TT none' else re.match(r'TT O([\d.]+)([+-]\d+) U[\d.]+([+-]\d+)', f[3]).groups()   # 'TT none' = team totals not posted yet
        L[t] = dict(sp=(float(sp[0]), int(sp[1])), tot=(tot[0], float(tot[1]), int(tot[2])), ml=int(f[2]),
                    tt=(float(tt[0]), int(tt[1]), int(tt[2])) if tt else None, h1sp=None, h1tot=None, h1ml=None)
        if f[4] != '1H none':   # texas222 sometimes posts no 1st half line for a game
            h1 = re.match(r'1H ([+-][\d.]+) ([+-]\d+), ([OU])([\d.]+) ([+-]\d+), ([+-]\d+)', f[4]).groups()
            L[t].update(h1sp=(float(h1[0]), int(h1[1])), h1tot=(h1[2], float(h1[3]), int(h1[4])), h1ml=int(h1[5]))
    return L

def parse_players():
    P = {}
    for ln in (D/'players_raw.txt').read_text().strip().splitlines()[1:]:
        f = ln.split('|')
        arr = lambda s: [int(x) for x in s[1:].split(',') if x]
        P[f[0]] = dict(n=f[0], gp=int(f[1]), mins=float(f[2]), pts=arr(f[3]), reb=arr(f[4]), ast=arr(f[5]), thr=arr(f[6]), team=f[7], lastg=f[8])
        P[f[0]]['pra'] = [a+b+c for a, b, c in zip(P[f[0]]['pts'], P[f[0]]['reb'], P[f[0]]['ast'])]
    return P

def _nzp(s):
    import unicodedata, re as _re
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if not unicodedata.combining(c))
    return _re.sub(r"\s+", ' ', _re.sub(r"[.'\u2019]|\b(Jr|Sr|II|III|IV)\b", '', s)).strip().lower()
def out_players():
    """Players ruled Out (or suspended) in injuries_raw.txt (B87, Nov 14: props for them are never graded or logged)."""
    out = set()
    for t, L in parse_injuries().items():
        for x in L:
            if ' Out (' in x or ' Suspension' in x: out.add(_nzp(x.split(' Out (')[0].split(' Suspension')[0]))
    return out
def parse_props():
    R = []; OUT = out_players(); dropped = []
    for ln in (D/'props_raw.txt').read_text().strip().splitlines()[1:]:
        g, pl, st, line, o, u = ln.split('|')
        if _nzp(pl) in OUT: dropped.append(pl); continue
        R.append(dict(game=g, pl=pl, stat=st, line=float(line), over=int(o), under=int(u)))
    if dropped: print('PROPS DROPPED (player ruled Out):', sorted(set(dropped)))
    return R

def parse_injuries():
    I = {}
    for ln in (D/'injuries_raw.txt').read_text().strip().splitlines()[1:]:
        t, rest = ln.split(': ', 1); I[t] = [x.strip() for x in rest.split(';') if x.strip()]
    return I

# Daily inputs ------------------------------------------------------------
GAMES = [  # away, home, tip Phoenix, venue
 ('NYK', 'TOR', '5:30 PM', 'Scotiabank Arena'),
 ('POR', 'MIN', '6:00 PM', 'Target Center'),
 ('DET', 'SAS', '6:00 PM', 'Frost Bank Center'),
 ('UTA', 'LAC', '8:30 PM', 'Intuit Dome'),
 ('CHA', 'LAL', '9:00 PM', 'Crypto.com Arena'),
]
# Neutral-site games: a key here gets no home edge.
NEUTRAL = set()
SR = {}   # Sportradar not read Nov 17 (no browser in this run); the projection uses the model alone
# Starters (or last season's 28+ minute players) ruled OUT. Points of margin lost; star 4 to 6, starter 2 to 3. Shares from repo ESPN box scores.
INJ_ADJ = {'LAL':(5.0, 'Austin Reaves (heel, 17% of Lakers points, 35 minutes) and Walker Kessler (lower leg, starting center, 14 starts, 12% of points) out'),
 'MIN':(4.0, 'Jonathan Kuminga (shoulder, 14 starts, 11% of Timberwolves points) and Jaylen Clark (hamstring) out; Anthony Edwards (knee) out since Oct 26; Donte DiVincenzo (Achilles) out'),
 'DET':(3.0, 'Duncan Robinson (quadriceps, 12 starts, 15% of Pistons points) and Ronald Holland II (knee) out; Jalen Duren (hamstring), Isaiah Joe and Taurean Prince also out'),
 'UTA':(3.0, 'Jaxson Hayes (knee, 10 starts) and Lauri Markkanen (hand, out since Nov 6, 10% of Jazz points) out; Jaren Jackson Jr. and Jusuf Nurkic also out'),
 'CHA':(1.5, 'Dennis Schroder (hamstring, 7 starts, 7% of Hornets points) out; Kon Knueppel out'),
 'POR':(0.5, 'Ja Morant (hamstring) out since Oct 29; Shaedon Sharpe, Vit Krejci and Chris Youngblood out'),
 'TOR':(0.5, 'Kawhi Leonard (knee) out since Oct 23; Nate Bittle out'),
}
# Day-to-day starters: game grades LOW until confirmed at warmups.
QUESTIONABLE = {'NYK-TOR':'Scottie Barnes (illness) is day-to-day for Toronto (9 starts, 15% of Raptors points); he played Nov 15',
 'POR-MIN':'Deni Avdija (foot) is day-to-day for Portland (13 starts, 20% of Trail Blazers points); he played Nov 16'}
ROSTER = {}
TRAVEL = {
 'NYK':'One day off: won 112-108 on the road at TOR on 11-15; same arena tonight.',
 'TOR':'One day off: lost 112-108 at home vs NYK on 11-15; home tonight.',
 'DET':'Two days off: lost 137-117 at MIA on 11-14; away tonight.',
 'SAS':'One day off: won 110-102 at UTA on 11-15; home tonight.',
 'POR':'Back-to-back, no travel: lost 106-98 at MIN on 11-16; same arena tonight.',
 'MIN':'Back-to-back at home: beat POR 106-98 on 11-16; home tonight.',
 'UTA':'One day off: lost 110-102 at home vs SAS on 11-15; away tonight.',
 'LAC':'One day off: beat CHA 113-105 at home on 11-15; home tonight.',
 'CHA':'One day off: lost 113-105 at LAC on 11-15; short trip across town tonight.',
 'LAL':'One day off: won 131-123 at PHX on 11-15; home tonight.',
}
NAMES = None

def build():
    global NAMES
    from teams import FULL; NAMES = FULL
    T = parse_teams(); L = parse_t222(); P = parse_players(); PR = parse_props(); INJ = parse_injuries()
    # league averages from last season's 30 teams (stored in signals.LAST net only), use slate teams' pull + constants
    LG_RTG, LG_PACE = 115.0, 100.3
    out = []
    for (a, h, tm, venue) in GAMES:
        A, H = T[a], T[h]
        W_ = a in WNBA_KEYS
        LG_RTG, LG_PACE = (105.8, 95.3) if W_ else (115.0, 100.3)
        SD_M = 11.0 if W_ else 12.5; SD_T = 15.0 if W_ else 18.0
        def blend(X):
            w = X['gp']/(X['gp']+12)
            o = (1-w)*X['lo'] + w*(X['no'] if X['gp'] else X['lo'])
            d = (1-w)*X['ld'] + w*(X['nd'] if X['gp'] else X['ld'])
            p = (1-w)*X['lpace'] + w*(X['npace'] if X['gp'] else X['lpace'])
            return o, d, p, w
        oA, dA, pA_, wA = blend(A); oH, dH, pH_, wH = blend(H)
        pace = pA_ + pH_ - LG_PACE
        if W_: pace *= 40/48   # stats.wnba.com reports pace per 48 minutes; WNBA games are 40
        effA = oA + dH - LG_RTG; effH = oH + dA - LG_RTG
        adj = []
        CX = None if W_ else game_context(a, h)
        # base model (fixed home court, flat back-to-back), kept so props can see what the context layer adds
        bA = pace*effA/100 - HCA; bH = pace*effH/100 + HCA
        if A['rest'] == 0: bA -= 0.75; bH += 0.75
        if H['rest'] == 0: bH -= 0.75; bA += 0.75
        if CX:
            ptsA = pace*effA/100 + CX['dA']; ptsH = pace*effH/100 + CX['dH']
            if f'{a}-{h}' in NEUTRAL:   # neutral floor: remove the home edge from both sides
                ptsA += CX['adv']/2; ptsH -= CX['adv']/2; adj.append('neutral site: no home edge')
            adj.append(f"home edge {CX['adv']:.1f} (league {2*CX['lg_half']:.1f}, nudged by both teams' home/road splits)")
            for t, fz in ((a, CX['fA']), (h, CX['fH'])):
                if fz[3] and fz[0]: adj.append(f"{t} {fz[3]} {fz[0]:+.1f} margin")
            if not CX['sameDiv']: adj.append(f"division strength {DIVNAME[CX['divA']]} {CX['dsA']:+.1f}, {DIVNAME[CX['divH']]} {CX['dsH']:+.1f} (schedule credit {a} {CX['corrA']:+.1f}, {h} {CX['corrH']:+.1f})")
            if abs(CX['tot_venue']) >= 0.1: adj.append(f"venue scoring {CX['tot_venue']:+.1f} total")
        else:
            ptsA, ptsH = bA, bH
            if A['rest'] == 0: adj.append(f'{a} back-to-back -1.5')
            if H['rest'] == 0: adj.append(f'{h} back-to-back -1.5')
        for t, side in ((a, 'A'), (h, 'H')):
            if t in INJ_ADJ:
                v, note = INJ_ADJ[t]
                if side == 'A': ptsA -= v/2; ptsH += v/2; bA -= v/2; bH += v/2
                else: ptsH -= v/2; ptsA += v/2; bH -= v/2; bA += v/2
                adj.append(f'{t} injuries -{v:g} ({note})')
        margin = ptsH - ptsA; total = ptsA + ptsH
        pH = Phi(margin/SD_M); pA = 1 - pH
        la, lh = L[a], L[h]
        def cover(team_side, spread, margin=margin, SD_M=SD_M):   # P(team + spread > opponent); defaults bind this game's margin (fixed Nov 6: was late-bound to the last game on the slate)
            m = margin if team_side == 'H' else -margin
            return Phi((m + spread)/SD_M)
        def p_over(line, mu=total, sd=SD_T): return 1 - Phi((line - mu)/sd)
        out.append(dict(a=a, h=h, time=tm, venue=venue, A=A, H=H, la=la, lh=lh, oA=oA, dA=dA, oH=oH, dH=dH, wA=wA, wH=wH, pace=pace,
                        ptsA=ptsA, ptsH=ptsH, margin=margin, total=total, pA=pA, pH=pH, cover=cover, p_over=p_over, adj=adj,
                        sr=SR.get((a, h)), injA=INJ.get(a, []), injH=INJ.get(h, []), lg=dict(rtg=LG_RTG, pace=LG_PACE), sdm=SD_M, sdt=SD_T, wnba=W_, ctx=CX, ctxd={a: ptsA-bA, h: ptsH-bH}))
    return out, dict(rtg=LG_RTG, pace=LG_PACE), P, PR

if __name__ == '__main__':
    games, lg, P, PR = build()
    for g in games:
        mA, mH = novig(g['la']['ml'], g['lh']['ml'])
        print(f"{g['a']}@{g['h']} pts {g['ptsA']:.1f}-{g['ptsH']:.1f} margin H {g['margin']:+.1f} total {g['total']:.1f} pace {g['pace']:.1f} | model H {g['pH']:.3f} mkt {mH:.3f} SR {g['sr']}")
