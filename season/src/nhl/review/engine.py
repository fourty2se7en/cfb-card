"""Point-in-time rebuild of the NHL card's model and signal scoring for every game played.
Mirrors render.picks() and model.build(); every input uses only games before the game date,
except: futures (one snapshot, Oct 29) and key absences (card days only, MTL Suzuki Oct 23 on)."""
import json, math, pathlib, sys
from collections import defaultdict
R = pathlib.Path(__file__).parent
sys.path.insert(0, str(R.parent))
import signals
from build_data import ip, dec, novig_home, ok, DIVNAME
LAST = signals.LAST; WEIGHTS = signals.WEIGHTS
FUT = {}
for ln in (R.parent/'standings_raw.txt').read_text().splitlines():
    if ln.startswith('CUP '): FUT = {x.split()[0]: int(x.split()[1]) for x in ln[4:].split(',')}
OUT = {('MTL', d) for d in ['2026-10-23','2026-10-25','2026-10-27']}  # Suzuki out (card OUT dict), MTL games after Oct 22
SUZ_LOSS = 0.5*(12/9 - 0.40)/2.6

def pois(l, k): return math.exp(-l)*l**k/math.factorial(k)
def tier(m): return 'Strong' if m >= 5 else ('Solid' if m >= 3 else 'Thin')

def team_state(prev, t, date):
    """prev: list of games before date. Returns team features as of date."""
    gs = [g for g in prev if t in (g['a'], g['h'])]
    rows = []
    for g in gs:
        home = g['h'] == t
        gf, ga = (g['hg'], g['ag']) if home else (g['ag'], g['hg'])
        sf, sa = (g['hsog'], g['asog']) if home else (g['asog'], g['hsog'])
        rows.append(dict(date=g['date'], home=home, gf=gf, ga=ga, sf=sf, sa=sa, win=gf > ga, lp=g['lp'], opp=g['a'] if home else g['h']))
    def rec(rr):
        w = sum(r['win'] for r in rr); l = sum((not r['win']) and r['lp'] == 'REG' for r in rr); o = len(rr) - w - l
        return w, l, o
    n = len(rows)
    S = dict(gp=n, rows=rows)
    S['rec'] = rec(rows); S['home'] = rec([r for r in rows if r['home']]); S['road'] = rec([r for r in rows if not r['home']])
    S['l10'] = rec(rows[-10:])
    w, l, o = S['rec']; S['ppct'] = (2*w+o)/(2*n) if n else 0.5
    S['diff'] = sum(r['gf']-r['ga'] for r in rows)
    st = ''
    for r in reversed(rows):
        c = 'W' if r['win'] else ('L' if r['lp'] == 'REG' else 'OT')
        if not st: st, k = c, 1
        elif c == st: k += 1
        else: break
    S['strk'] = (st, k if st else 0)
    from datetime import date as D
    if rows:
        d0 = D.fromisoformat(rows[-1]['date']); d1 = D.fromisoformat(date); S['rest'] = (d1-d0).days - 1
    else: S['rest'] = 5
    avg = lambda k, rr: sum(r[k] for r in rr)/len(rr) if rr else 0
    S['gf'] = avg('gf', rows); S['ga'] = avg('ga', rows); S['sf'] = avg('sf', rows); S['sa'] = avg('sa', rows)
    H = [r for r in rows if r['home']]; Rd = [r for r in rows if not r['home']]
    S['hgf'], S['hga'], S['rgf'], S['rga'] = avg('gf', H), avg('ga', H), avg('gf', Rd), avg('ga', Rd)
    S['nh'], S['nr'] = len(H), len(Rd)
    S['last5'] = [r['gf']+r['ga'] for r in rows[-5:]]
    return S

def goalie_state(prev, name):
    sa = ga = 0
    for g in prev:
        for side in ('agl', 'hgl'):
            if g[side]['n'] == name: sa += g[side]['sa']; ga += g[side]['ga']
    return sa, ga

def div_strength(prev):
    acc = defaultdict(lambda: [0, 0, 0])
    for g in prev:
        da, dh = DIVNAME[g['div_a']], DIVNAME[g['div_h']]
        if da == dh: continue
        aw = g['ag'] > g['hg']; ot = g['lp'] != 'REG'
        for d, won in ((da, aw), (dh, not aw)):
            x = acc[d]
            if won: x[0] += 1
            elif ot: x[2] += 1
            else: x[1] += 1
    st = {}
    for d in DIVNAME.values():
        w, l, o = acc[d]; gp = w+l+o
        st[d] = ((2*w+o) + 20) / (2*gp + 40)
    return st

def build_all(games):
    out = []
    for i, g in enumerate(games):
        prev = [x for x in games if x['date'] < g['date']]
        A, H = team_state(prev, g['a'], g['date']), team_state(prev, g['h'], g['date'])
        # league averages from prior games (fallback to whole-season constants on opening days)
        if len(prev) >= 10:
            LgS = sum(x['asog']+x['hsog'] for x in prev)/(2*len(prev)); totG = sum(x['ag']+x['hg'] for x in prev)
            totSA = sum(x['agl']['sa']+x['hgl']['sa'] for x in prev); totGAg = sum(x['agl']['ga']+x['hgl']['ga'] for x in prev)
            lg_sv = 1 - totGAg/totSA if totSA else 0.895; lg_g = totG/(2*len(prev)); lg_sh = totG/(2*len(prev)*LgS)
            hgoals = sum(x['hg'] for x in prev)/len(prev); rgoals = sum(x['ag'] for x in prev)/len(prev)
            LH, LR = hgoals/lg_g, rgoals/lg_g
        else:
            LgS, lg_sv, lg_g, lg_sh, LH, LR = 27.5, 0.895, 3.0, 0.109, 1.035, 0.965
        SCALE = (lg_g - 0.06)/(LgS*(1-lg_sv))
        def reg_shots(x, n): return (x*n + LgS*5)/(n+5)
        sfA, saA = reg_shots(A['sf'], A['gp']), reg_shots(A['sa'], A['gp'])
        sfH, saH = reg_shots(H['sf'], H['gp']), reg_shots(H['sa'], H['gp'])
        shotsA = sfA*saH/LgS; shotsH = sfH*saA/LgS
        def reg_sh(S): s = S['sf']*S['gp']; gg = S['gf']*S['gp']; return (gg + lg_sh*250)/(s+250)
        qA, qH = reg_sh(A)/lg_sh, reg_sh(H)/lg_sh
        def gsv(name):
            sa, ga = goalie_state(prev, name)
            return ((1-ga/sa)*sa + lg_sv*900)/(sa+900) if sa else lg_sv - 0.006
        svA, svH = gsv(g['agl']['n']), gsv(g['hgl']['n'])
        lamA = shotsA*(1-svH)*qA*0.965*SCALE; lamH = shotsH*(1-svA)*qH*1.035*SCALE
        def vf(split, n, season, base):
            if season <= 0: return 1.0
            r = (split*n + season*base*10)/(n + 10)/(season*base); return min(1.15, max(0.85, r))
        vH = (vf(H['hgf'], H['nh'], H['gf'], LH)*vf(A['rga'], A['nr'], A['ga'], LH))**0.5
        vA = (vf(A['rgf'], A['nr'], A['gf'], LR)*vf(H['hga'], H['nh'], H['ga'], LR))**0.5
        lamH *= vH; lamA *= vA
        if A['rest'] == 0: lamA *= 0.97; lamH *= 1.03
        if H['rest'] == 0: lamH *= 0.97; lamA *= 1.03
        lossA = SUZ_LOSS if (g['a'], g['date']) in OUT else 0; lossH = SUZ_LOSS if (g['h'], g['date']) in OUT else 0
        if lossA and A['gf']: lamA *= max(0.5, 1 - lossA/A['gf'])
        if lossH and H['gf']: lamH *= max(0.5, 1 - lossH/H['gf'])
        N = 12; grid = [[pois(lamA, a)*pois(lamH, h) for h in range(N)] for a in range(N)]
        pA_reg = sum(grid[a][h] for a in range(N) for h in range(N) if a > h); pH_reg = sum(grid[a][h] for a in range(N) for h in range(N) if h > a)
        pT = 1 - pA_reg - pH_reg; otH = 0.5 + 0.5*(lamH-lamA)/(lamH+lamA) + 0.02
        pH = pH_reg + pT*otH
        m1A = sum(grid[a][a-1] for a in range(1, N)); m1H = sum(grid[h-1][h] for h in range(1, N))
        pA2 = sum(grid[a][h] for a in range(N) for h in range(N) if a-h >= 2) + 0.22*m1A
        pH2 = sum(grid[a][h] for a in range(N) for h in range(N) if h-a >= 2) + 0.22*m1H
        lamT = lamA + lamH + 0.12
        g2 = dict(g); g2.update(A=A, H=H, lamA=lamA, lamH=lamH, lamT=lamT, pH_model=pH, pA2=pA2, pH2=pH2, svA=svA, svH=svH,
                                vA=vA, vH=vH, lossA=lossA, lossH=lossH, div=div_strength(prev), lg_sv=lg_sv)
        out.append(g2)
    return out
