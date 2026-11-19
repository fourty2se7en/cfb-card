"""NHL slate model (daily; Nov 11 2026 slate). Reads raw pulls, produces per-game analysis dicts."""
import re, math, json, pathlib
D = pathlib.Path(__file__).parent

# ---------------------------------------------------------------- parsing
def parse_teams():
    T = {}
    for ln in (D/'teams_raw.txt').read_text().strip().splitlines():
        t = ln.split()[0]
        m = lambda p: re.search(p, ln).group(1)
        T[t] = dict(
            rec=m(r'^\w+ (\S+)'), home=m(r' H(\S+)'), road=m(r' R(\S+)'), l10=m(r'L10 (\S+)'),
            gf=float(m(r'GF([\d.]+)')), ga=float(m(r'GA([\d.]+)')),
            hgf=float(m(r' h([\d.]+)/')), hga=float(m(r' h[\d.]+/([\d.]+)')),
            rgf=float(m(r' r([\d.]+)/')), rga=float(m(r' r[\d.]+/([\d.]+)')),
            sf=float(m(r'SF([\d.]+)')), sa=float(m(r'SA([\d.]+)')),
            pp=m(r'PP(\S+ \(\d+/\d+\))'), pk=m(r'PK(\S+ \(\d+/\d+\))'),
            ppv=float(m(r'PP([\d.]+)%')), pkv=float(m(r'PK([\d.]+)%')),
            p1f=float(m(r'1P([\d.]+)/')), p1a=float(m(r'1P[\d.]+/([\d.]+)')),
            last=m(r'last:(.+?) rest'), rest=int(m(r'rest(\d+)')),
            gfl=[int(c) for c in m(r'gf\[(\d+)\]')], gal=[int(c) for c in m(r'ga\[(\d+)\]')],
            p1l=[int(c) for c in m(r'1P\[(\d+)\]')],
        )
        T[t]['gp'] = len(T[t]['gfl'])
    return T

def parse_skaters():
    S, G = {}, {}
    txt = (D/'skaters_raw.txt').read_text()
    sk, go = txt.split('GOALIES')
    for ln in sk.strip().splitlines():
        t, rest = ln.split(': ', 1)
        S[t] = []
        for p in rest.split(' | '):
            m = re.match(r"(.+?) (\d+)g (\d+)-(\d+)-(\d+) (\d+)sh s2:(\d+) s3:(\d+) s4:(\d+) p(\d+) g(\d+) a(\d+) pp(\d+)", p)
            n, gp, g, a, pts, sh, s2, s3, s4, p1, g1, a1, ppp = m.groups()
            S[t].append(dict(n=n, gp=int(gp), g=int(g), a=int(a), p=int(pts), sh=int(sh), s2=int(s2), s3=int(s3), s4=int(s4), p1=int(p1), g1=int(g1), a1=int(a1), ppp=int(ppp)))
    for ln in go.strip().splitlines()[1:]:
        t, rest = ln.split(' ', 1)
        G[t] = {}
        for p in rest.split('; '):
            m = re.match(r"(\S+) (\d+)(?: (\d+-\d+-\d+))? ([\d.]+) (\.\d+)", p)
            n, gs, rec, gaa, sv = m.groups()
            G[t][n] = dict(gs=int(gs), rec=rec or '0-0-0', gaa=float(gaa), sv=float(sv))
    return S, G

def parse_t222():
    L = {}
    for ln in (D/'t222.txt').read_text().strip().splitlines()[1:]:
        t, rest = ln.split(': ', 1)
        f = [x.strip() for x in rest.split('|')]
        pl = re.match(r'([+-][\d.]+) ([+-]\d+)', f[0]).groups()
        tot = re.match(r'([OU])([\d.]+) ([+-]\d+)', f[1]).groups()
        tt = re.match(r'TT O([\d.½]+)([+-]\d+) U[\d.½]+([+-]\d+)', f[3]); tt = tt.groups() if tt else None  # TT n/a when not posted
        p1 = re.match(r'1P ([+-][\d.]+) ([+-]\d+), ([OU])([\d.]+) ([+-]\d+), ([+-]\d+)', f[4]); p1 = p1.groups() if p1 else None  # 1P n/a when not posted
        d = dict(pl=(float(pl[0]), int(pl[1])), tot=(tot[0], float(tot[1]), int(tot[2])), ml=int(f[2]),
                 tt=((float(tt[0].replace('½', '.5')), int(tt[1]), int(tt[2])) if tt else None),
                 p1pl=((float(p1[0]), int(p1[1])) if p1 else None), p1tot=((p1[2], float(p1[3]), int(p1[4])) if p1 else None), p1ml=(int(p1[5]) if p1 else None),
                 w3=(int(f[5].split()[1]) if re.match(r'3W [+-]\d+', f[5]) else None), s1=(int(f[6].split()[1]) if re.match(r'S1 [+-]\d+', f[6]) else None))  # S1 n/a when texas222 posts no game props
        if len(f) > 7: d['draw'] = int(f[7].split()[1])
        L[t] = d
    return L

# ---------------------------------------------------------------- math
def be(o): return -o/(-o+100) if o < 0 else 100/(o+100)
def amer(p):
    p = min(max(p, 0.01), 0.99)
    return round(-100*p/(1-p)) if p >= 0.5 else round(100*(1-p)/p)
def fmt(o): return f'+{o}' if o > 0 else f'{o}'
def pois(l, k): return math.exp(-l)*l**k/math.factorial(k)
def p_ge(l, k): return 1 - sum(pois(l, i) for i in range(k))
def novig(a, b):
    x, y = be(a), be(b); return x/(x+y), y/(x+y)
def wilson(k, n, z=1.96):
    if n == 0: return (0, 1)
    p = k/n; d = 1+z*z/n; c = p+z*z/(2*n); r = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))
    return ((c-r)/d, (c+r)/d)

GAMES = [  # away, home, puck drop Phoenix, venue, away goalie, status, home goalie, status (Daily Faceoff and RotoWire read Nov 15 ~7:00 AM Phoenix; same goalie in both = stronger status, RotoWire Expected = Likely; different goalies and neither confirmed = Daily Faceoff kept)
    ('EDM', 'PHI', '5:30 PM', 'Xfinity Mobile Arena', 'Jarry', 'Likely', 'Vladar', 'Confirmed'),
    ('CGY', 'ANA', '6:00 PM', 'Honda Center', 'Cooley', 'Likely', 'Husso', 'Likely'),
    ('FLA', 'DAL', '6:00 PM', 'American Airlines Center', 'Schmid', 'Likely', 'DeSmith', 'Likely'),
    ('NSH', 'SJS', '7:00 PM', 'SAP Center', 'Saros', 'Likely', 'Nedeljkovic', 'Likely'),
    ('VAN', 'VGK', '7:00 PM', 'T-Mobile Arena', 'Lankinen', 'Unconfirmed', 'Hart', 'Likely'),
]
T222KEY = {t:t for t in ['EDM','PHI','CGY','ANA','FLA','DAL','NSH','SJS','VAN','VGK']}
NAMES = {'EDM': 'Edmonton Oilers', 'PHI': 'Philadelphia Flyers', 'CGY': 'Calgary Flames', 'ANA': 'Anaheim Ducks', 'FLA': 'Florida Panthers', 'DAL': 'Dallas Stars', 'NSH': 'Nashville Predators', 'SJS': 'San Jose Sharks', 'VAN': 'Vancouver Canucks', 'VGK': 'Vegas Golden Knights'}
# Key absences (confirmed out tonight): team -> [(player, games played, points, note)]. Daily input from injury news.
OUT = {}  # Nov 15: no top 4 scorer or 0.6+ points per game skater confirmed out on tonight's teams (ESPN injuries feed, 6 AM read)
REPL_PPG = 0.40   # points per game a replacement skater produces
PTS_PER_GOAL = 2.6  # league average points credited per goal
def absence_loss(team):
    """Goals per game the team loses to absences: half of the player's points-per-game above replacement, converted to goals."""
    rows = []
    for (n, gp, pts, note) in OUT.get(team, []):
        ppg = pts/gp if gp else 0
        loss = max(0.0, 0.5*(ppg - REPL_PPG)/PTS_PER_GOAL)
        rows.append((n, gp, pts, note, loss))
    return sum(r[4] for r in rows), rows
SR = {('EDM','PHI'):42.3, ('CGY','ANA'):58.1, ('FLA','DAL'):55.0, ('NSH','SJS'):39.8, ('VAN','VGK'):79.6}  # Sportradar home win %, read Nov 15 ~7:05 AM Phoenix

def build():
    T = parse_teams(); S, G = parse_skaters(); L = parse_t222()
    LgS = sum(t['sf'] for t in T.values())/len(T)
    totGA = sum(t['ga']*t['gp'] for t in T.values()); totSA = sum(t['sa']*t['gp'] for t in T.values())
    totGF = sum(t['gf']*t['gp'] for t in T.values()); totSF = sum(t['sf']*t['gp'] for t in T.values())
    lg_sv = 1 - totGA/totSA; lg_sh = totGF/totSF
    lg_g = totGF/sum(t['gp'] for t in T.values())
    global LG_SV; LG_SV = lg_sv
    SCALE = (lg_g - 0.06)/(LgS*(1-lg_sv))

    def goalie_sv(team, name):
        g = G[team].get(name)
        if not g:   # call-up with no NHL games this season
            return LG_SV - 0.006, None, 0
        ga_tot = g['gaa']*g['gs']; sa = ga_tot/(1-g['sv']) if g['sv'] < 1 else 0
        prior = LG_SV
        reg = (g['sv']*sa + prior*900)/(sa+900)
        return reg, g, sa

    # Venue splits (added Oct 29): each team's home or road scoring and allowing, regressed 10 games to its own season rate,
    # relative to the league's average home/road split so league-wide home ice (already x1.035) is not counted twice.
    def nrec(s): return sum(map(int, s.split('-')))
    nh = {t: nrec(x['home']) for t, x in T.items()}; nr = {t: nrec(x['road']) for t, x in T.items()}
    LH = sum(x['hgf']*nh[t] for t, x in T.items())/max(sum(nh.values()), 1)/lg_g   # home goals per game vs league
    LR = sum(x['rgf']*nr[t] for t, x in T.items())/max(sum(nr.values()), 1)/lg_g
    def vf(split, n, season, base):
        if season <= 0: return 1.0
        r = (split*n + season*base*10)/(n + 10)/(season*base)  # regress toward the league-typical venue rate
        return min(1.15, max(0.85, r))
    def venue_factors(A, H, a, h):
        offH = vf(H['hgf'], nh[h], H['gf'], LH); defA = vf(A['rga'], nr[a], A['ga'], LH)
        offA = vf(A['rgf'], nr[a], A['gf'], LR); defH = vf(H['hga'], nh[h], H['ga'], LR)
        return (offH*defA)**0.5, (offA*defH)**0.5, dict(offH=offH, defA=defA, offA=offA, defH=defH)
    out = []
    for (a, h, tm, venue, ga_n, ga_s, gh_n, gh_s) in GAMES:
        A, H = T[a], T[h]
        def reg_shots(x, n): return (x*n + LgS*5)/(n+5)
        sfA, saA = reg_shots(A['sf'], A['gp']), reg_shots(A['sa'], A['gp'])
        sfH, saH = reg_shots(H['sf'], H['gp']), reg_shots(H['sa'], H['gp'])
        shotsA = sfA*saH/LgS; shotsH = sfH*saA/LgS
        def reg_sh(t):  # shooting % regressed with 250 shots of prior
            s = t['sf']*t['gp']; g = t['gf']*t['gp']
            return (g + lg_sh*250)/(s+250)
        qA, qH = reg_sh(A)/lg_sh, reg_sh(H)/lg_sh
        svA, gA, saFA = goalie_sv(a, ga_n); svH, gH, saFH = goalie_sv(h, gh_n)
        NEU = 'neutral' in str(venue).lower()   # Nov 12: neutral site (Global Series): no home ice, no venue splits
        lamA = shotsA*(1-svH)*qA*(1.0 if NEU else 0.965)*SCALE
        lamH = shotsH*(1-svA)*qH*(1.0 if NEU else 1.035)*SCALE
        # venue splits: home team at home, road team on the road
        vH, vA, vdet = venue_factors(A, H, a, h)
        if NEU: vH, vA = 1.0, 1.0
        lamH *= vH; lamA *= vA
        # schedule: back-to-back penalty (fatigue): tired team scores 3% less, its opponent scores 3% more
        if A['rest'] == 0: lamA *= 0.97; lamH *= 1.03
        if H['rest'] == 0: lamH *= 0.97; lamA *= 1.03
        # key absences: cut the team's goal rate by the goals lost per game
        lossA, outA = absence_loss(a); lossH, outH = absence_loss(h)
        if lossA: lamA *= max(0.5, 1 - lossA/A['gf'])
        if lossH: lamH *= max(0.5, 1 - lossH/H['gf'])
        # grid
        N = 12
        grid = [[pois(lamA, i)*pois(lamH, j) for j in range(N)] for i in range(N)]
        pA_reg = sum(grid[i][j] for i in range(N) for j in range(N) if i > j)
        pH_reg = sum(grid[i][j] for i in range(N) for j in range(N) if j > i)
        pT = 1 - pA_reg - pH_reg
        otH = 0.5 + 0.5*(lamH-lamA)/(lamH+lamA) + 0.02
        pH = pH_reg + pT*otH; pA = 1 - pH
        m1A = sum(grid[i][i-1] for i in range(1, N)); m1H = sum(grid[j-1][j] for j in range(1, N))
        pA2 = sum(grid[i][j] for i in range(N) for j in range(N) if i-j >= 2) + 0.22*m1A
        pH2 = sum(grid[i][j] for i in range(N) for j in range(N) if j-i >= 2) + 0.22*m1H
        lamT = lamA+lamH + 0.12  # empty-net allowance on totals
        def p_tot_under(line, lamT=lamT):  # P(total < line), half-lines and whole
            k = math.floor(line)
            if line == k:  # whole number: return (under, push)
                return sum(pois(lamT, i) for i in range(k)), pois(lamT, k)
            return sum(pois(lamT, i) for i in range(k+1)), 0.0
        la, lh = L[a], L[h]
        res = dict(a=a, h=h, time=tm, venue=venue, A=A, H=H, la=la, lh=lh,
                   gA=(ga_n, ga_s, gA, svA, saFA), gH=(gh_n, gh_s, gH, svH, saFH),
                   lamA=lamA, lamH=lamH, lamT=lamT, shotsA=shotsA, shotsH=shotsH, qA=qA, qH=qH,
                   pA=pA, pH=pH, pA_reg=pA_reg, pH_reg=pH_reg, pT=pT, pA2=pA2, pH2=pH2,
                   p_tot_under=p_tot_under, vH=vH, vA=vA, vdet=vdet, lossA=lossA, lossH=lossH, outA=outA, outH=outH, SA=S[a], SH=S[h], sr=SR.get((a, h)), lg=dict(S=LgS, sv=lg_sv, sh=lg_sh, g=lg_g))
        out.append(res)
    return out, dict(LgS=LgS, lg_sv=lg_sv, lg_sh=lg_sh, lg_g=lg_g)

if __name__ == '__main__':
    games, lg = build()
    print(lg)
    for g in games:
        la, lh = g['la'], g['lh']
        mA, mH = novig(la['ml'], lh['ml'])
        print(f"{g['a']}@{g['h']} lamA {g['lamA']:.2f} lamH {g['lamH']:.2f} T {g['lamT']:.2f} | model H {g['pH']:.3f} mkt H {mH:.3f} SR {g['sr']} | line {la['tot']} | svA {g['gA'][3]:.3f} svH {g['gH'][3]:.3f}")
