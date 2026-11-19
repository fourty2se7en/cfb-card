"""Schedule and venue context, learned from NBA.com game logs and updated every day as games are played.

1. Home and road: league home edge is learned from both seasons' home and road margins (prior 2.8 margin points,
   weight 600 team games). Each team's own home/road split moves its edge 30% of the way off the league number
   (team splits are noisy). Venue scoring: each team's home or road game totals vs its average, 30% weight.
2. Fatigue: back-to-back, back-to-back with or without travel, 3 games in 4 nights and 2+ days rest are measured
   from game logs as the team's margin, points scored and points allowed vs its own home or road average.
   Each is shrunk toward a prior (back-to-back -1.5 margin, weight 200 games; subtypes toward the back-to-back
   number, weight 300). Player props use the learned minutes and per-minute ratios on back-to-backs.
3. Division strength: each division's average margin in games against other divisions, this season blended
   with last season by games / (games + 60). A team's rating gains its share of division games times its
   division's strength (its rating was earned partly against those teams). Division gap of 2+ points between
   two teams from different divisions is a 1-point side signal."""
import pathlib
D = pathlib.Path(__file__).parent
DIV = dict(ATL='SE',CHA='SE',MIA='SE',ORL='SE',WAS='SE',BOS='AT',BKN='AT',NYK='AT',PHI='AT',TOR='AT',CHI='CE',CLE='CE',DET='CE',IND='CE',MIL='CE',
           DEN='NW',MIN='NW',OKC='NW',POR='NW',UTA='NW',GSW='PA',LAC='PA',LAL='PA',PHX='PA',SAC='PA',DAL='SW',HOU='SW',MEM='SW',NOP='SW',SAS='SW')
DIVNAME = dict(SE='Southeast',AT='Atlantic',CE='Central',NW='Northwest',PA='Pacific',SW='Southwest')
LAST_S, THIS_S = '2025-26', '2026-27'
HCA_PRIOR, HCA_K, TEAM_W = 2.8, 600, 0.30
FAT_PRIOR = {'b2b': (-1.5, -1.0, 0.5)}   # margin, own pts, opp pts
FAT_K, SUB_K = 200, 300
DIV_K = 60

def _load():
    T, Dv, C, S = {}, {}, {}, {}
    p = D/'context_raw.txt'
    if not p.exists(): return T, Dv, C, S
    for ln in p.read_text().strip().splitlines()[1:]:
        f = ln.split('|')
        if f[0] == 'T':
            T[(f[1], f[2])] = dict(hn=int(f[3]), hm=float(f[4]), hp=float(f[5]), ho=float(f[6]), rn=int(f[7]), rm=float(f[8]), rp=float(f[9]), ro=float(f[10]), dg=int(f[11]), n=int(f[12]))
        elif f[0] == 'D': Dv[(f[1], f[2])] = dict(n=int(f[3]), m=float(f[4]), w=int(f[5]))
        elif f[0] == 'C': C[(f[1], f[2])] = dict(n=int(f[3]), m=float(f[4]), p=float(f[5]), o=float(f[6]))
        elif f[0] == 'S': S[f[1]] = dict(rest=int(f[2]), last=f[3], from_=f[4], to=f[5], travel=f[6] == '1', n3=int(f[7]))
    return T, Dv, C, S
T, DV, CS, SLATE = _load()

def _pool(cat):
    rows = [CS[(s, cat)] for s in (LAST_S, THIS_S) if (s, cat) in CS]
    n = sum(r['n'] for r in rows)
    if not n: return 0, 0, 0, 0
    return n, sum(r['m']*r['n'] for r in rows)/n, sum(r['p']*r['n'] for r in rows)/n, sum(r['o']*r['n'] for r in rows)/n

def _shrink(prior, k, cat):
    n, m, p, o = _pool(cat)
    return tuple((pr*k + v*n)/(k+n) for pr, v in zip(prior, (m, p, o))) + (n,)

FAT = {}
FAT['b2b'] = _shrink(FAT_PRIOR['b2b'], FAT_K, 'b2b')
FAT['b2b_travel'] = _shrink(FAT['b2b'][:3], SUB_K, 'b2b_travel')
FAT['b2b_stay'] = _shrink(FAT['b2b'][:3], SUB_K, 'b2b_stay')
FAT['3in4'] = _shrink((-0.5, -0.3, 0.2), SUB_K, '3in4')
FAT['rest2'] = _shrink((0.0, 0.0, 0.0), SUB_K, 'rest2')

def _league_half():
    ss = [T[k] for k in T]
    tot = sum(x['hn']+x['rn'] for x in ss)
    if not tot: return HCA_PRIOR/2, 0
    gap = sum((x['hm']-x['rm'])*(x['hn']+x['rn']) for x in ss)/tot   # home margin minus road margin = 2 x home edge
    edge = (HCA_PRIOR*HCA_K + (gap/2)*tot)/(HCA_K+tot)
    return edge/2, tot   # per side
LG_HALF, LG_HCA_N = _league_half()   # per-side points (home team +, road team -)
HCA_MARGIN = 2*LG_HALF

def _blend_team(t):
    l, n = T.get((LAST_S, t)), T.get((THIS_S, t))
    def half(x): return (x['hm']-x['rm'])/2   # team's own home edge in margin points
    def tot_home(x): return (x['hp']+x['ho']) - ((x['hp']+x['ho'])*x['hn'] + (x['rp']+x['ro'])*x['rn'])/max(x['hn']+x['rn'], 1)
    def tot_road(x): return (x['rp']+x['ro']) - ((x['hp']+x['ho'])*x['hn'] + (x['rp']+x['ro'])*x['rn'])/max(x['hn']+x['rn'], 1)
    if not l and not n: return None
    gpn = (n['hn']+n['rn']) if n else 0
    w = gpn/(gpn+30) if l else 1.0
    pick = lambda f: (w*f(n) if n else 0) + ((1-w)*f(l) if l else 0)
    share = pick(lambda x: x['dg']/max(x['n'], 1))
    return dict(half=pick(half), th=pick(tot_home), tr=pick(tot_road), share=share, w=w,
                hm_l=l['hm'] if l else None, rm_l=l['rm'] if l else None, hm_n=n['hm'] if n else None, rm_n=n['rm'] if n else None,
                hn_n=n['hn'] if n else 0, rn_n=n['rn'] if n else 0)

def _lg_half_raw():
    ss = [T[k] for k in T if k[0] == LAST_S]
    return sum((x['hm']-x['rm'])/2 for x in ss)/len(ss) if ss else LG_HALF

def div_strength(dv):
    l, n = DV.get((LAST_S, dv)), DV.get((THIS_S, dv))
    w = (n['n']/(n['n']+DIV_K)) if n else 0
    return w*(n['m'] if n else 0) + (1-w)*(l['m'] if l else 0), (n or {}), (l or {})

def fatigue(t):
    """(margin, own pts, opp pts, label) for tonight's schedule spot."""
    s = SLATE.get(t)
    if not s: return 0, 0, 0, ''
    if s['rest'] == 0:
        k = 'b2b_travel' if s['travel'] else 'b2b_stay'
        m, p, o, n = FAT[k]
        lab = f"back-to-back {'after travel' if s['travel'] else 'without travel'}"
        if s['n3'] >= 2:
            m3, p3, o3, _ = FAT['3in4']
            if m3 < m: m, p, o, lab = m3, p3, o3, lab + ', 3rd game in 4 nights'
        return m, p, o, lab
    if s['n3'] >= 2:
        m, p, o, n = FAT['3in4']; return m, p, o, '3rd game in 4 nights'
    if s['rest'] >= 2 and s['rest'] < 99:
        m, p, o, n = FAT['rest2']; return m, p, o, f"{s['rest']} days rest"
    return 0, 0, 0, '1 day rest (baseline)'

def game_context(a, h):
    """Points adjustments for away a at home h. Returns dict with dA, dH (points added to each team) and notes."""
    if a not in DIV or h not in DIV or not T: return None
    A, H = _blend_team(a), _blend_team(h)
    lg = _lg_half_raw()
    # 1. home edge: league learned, nudged by each team's own split
    adv = HCA_MARGIN + TEAM_W*(((H['half']-lg) if H else 0) + ((A['half']-lg) if A else 0))/2
    tot_venue = TEAM_W*(((H['th']) if H else 0) + ((A['tr']) if A else 0))/2
    # 2. fatigue
    fA, fH = fatigue(a), fatigue(h)
    # 3. division strength (schedule correction)
    dA_, nA_, lA_ = div_strength(DIV[a]); dH_, nH_, lH_ = div_strength(DIV[h])
    corrA = (A['share'] if A else 0.2)*dA_; corrH = (H['share'] if H else 0.2)*dH_
    dA = -adv/2 + corrA/2 - corrH/2 + fA[1] + fH[2] + tot_venue/2
    dH = adv/2 + corrH/2 - corrA/2 + fH[1] + fA[2] + tot_venue/2
    return dict(adv=adv, tot_venue=tot_venue, fA=fA, fH=fH, divA=DIV[a], divH=DIV[h], dsA=dA_, dsH=dH_, corrA=corrA, corrH=corrH,
                dA=dA, dH=dH, A=A, H=H, lg_half=LG_HALF, sameDiv=DIV[a] == DIV[h], nA=nA_, nH=nH_, lA=lA_, lH=lH_)

# Player context -----------------------------------------------------------------
SPL, B2BP = {}, {}
_p = D/'splits_raw.txt'
if _p.exists():
    import re
    for ln in _p.read_text().strip().splitlines()[1:]:
        f = ln.split('|')
        if f[0] == 'B2B':
            v = [float(x) for x in f[2].split(',')]
            B2BP[f[1]] = dict(nb=v[0], mb=v[1], rb=v[2], no=v[3], mo=v[4], ro=v[5])
            continue
        d = {}
        for tok in f[1].split(' '):
            k, v = tok.split(':')
            m = re.match(r'h([\d.]+)x(\d+)a([\d.]+)x(\d+)', v)
            d[(k[0], float(k[1:]))] = dict(h=float(m.group(1)), hn=int(m.group(2)), a=float(m.group(3)), an=int(m.group(4)))
        SPL[f[0]] = d

def loc_factor(pl, k, line, home):
    """Player's last-season home or road average vs his overall, weight games / (games + 40)."""
    s = SPL.get(pl, {}).get((k, line))
    if not s or s['hn'] + s['an'] == 0: return 1.0, None
    ov = (s['h']*s['hn'] + s['a']*s['an'])/(s['hn']+s['an'])
    if ov <= 0: return 1.0, None
    v, n = (s['h'], s['hn']) if home else (s['a'], s['an'])
    if n == 0: return 1.0, None
    f = 1 + (v/ov - 1)*n/(n+40)
    return f, (v, n, ov)

def b2b_factor(starter):
    """Learned league minutes and per-minute production ratios on back-to-backs, half weight."""
    g = B2BP.get('S' if starter else 'O')
    if not g: return 1.0, 1.0
    return 1 + 0.5*(g['mb']/g['mo'] - 1), 1 + 0.5*(g['rb']/g['ro'] - 1)
