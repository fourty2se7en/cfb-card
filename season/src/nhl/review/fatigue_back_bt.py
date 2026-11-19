"""Backtest: BACK the team playing its 3rd game in 4 nights (reverse of the fade tracker). Trina, Nov 11, 2026. Analysis only.
Tired = 3rd (or later) game within 4 calendar days (fatigue.contexts n4 >= 3). Games where both teams are tired are skipped.
Seasons:
  2024-25, 2025-26: hist_fatigue.txt (regular season results and closing moneylines from the ESPN odds feed: ESPN BET for 2024-25
    and Oct to mid Dec 2025, DraftKings after; extracted from the public pchattani/the-quant-rink data/<season>/schedule.json).
    The feed has no puck line prices, so puck line picks are graded W-L on the real result and their units use an ESTIMATED
    price: the DraftKings close puck line price predicted from the closing moneyline (fit on 2026-27 dk.txt closes).
    Closing moneylines of -110/-110 whose opening line was more than 4 points off a pick'em are placeholders and are skipped.
  2026-27: games.json (SBR median close, the same data and prices as the fade tracker in fatigue.py).
Run: cd review && python3 build_data.py && python3 fatigue_back_bt.py"""
import json, sys, pathlib, datetime
from collections import defaultdict
R = pathlib.Path(__file__).parent; sys.path.insert(0, str(R.parent)); sys.path.insert(0, str(R))
import rules
from build_data import ok, ip
D = datetime.date.fromisoformat

def tired_flags(games):
    """games sorted by date: dicts with date, a, h. Returns {(i, team): n4}."""
    hist, out = defaultdict(list), {}
    for i, g in enumerate(games):
        d = D(g['date'])
        for t in (g['a'], g['h']):
            out[(i, t)] = sum(1 for p in hist[t] if (d - p).days <= 3) + 1
        for t in (g['a'], g['h']): hist[t].append(d)
    return out

# ---- puck line price fit from DraftKings closes (dk.txt): implied PL prob = a + b * ML no-vig prob, per role
def _fit():
    pts = {'fav': [], 'dog': []}
    for ln in (R/'dk.txt').read_text().splitlines():
        f = ln.split('|'); c = f[7].split(',')
        try: mla, mlh, sp, pla, plh = int(c[0]), int(c[1]), float(c[2]), int(c[3]), int(c[4])
        except Exception: continue
        if abs(sp) != 1.5: continue
        pa = ip(mla)/(ip(mla)+ip(mlh))
        for p, s, pr in ((pa, sp, pla), (1-pa, -sp, plh)):
            pts['fav' if s < 0 else 'dog'].append((p, ip(pr)))
    F = {}
    for k, v in pts.items():
        n = len(v); mx = sum(x for x, _ in v)/n; my = sum(y for _, y in v)/n
        b = sum((x-mx)*(y-my) for x, y in v)/sum((x-mx)**2 for x, _ in v); F[k] = (my - b*mx, b, n)
    return F
FIT = _fit()
def amer(p): return -round(100*p/(1-p)) if p >= 0.5 else round(100*(1-p)/p)
def est_pl_price(p_team, fav):
    a, b, _ = FIT['fav' if fav else 'dog']; return amer(min(0.9, max(0.1, a + b*p_team)))

def bets_hist(season):
    G = []
    for ln in (R/'hist_fatigue.txt').read_text().splitlines():
        if ln.startswith('#'): continue
        f = ln.split('|')
        if f[0] != season: continue
        G.append(dict(date=f[1], a=f[2], h=f[3], ag=int(f[4]), hg=int(f[5]), mla=int(f[6]), mlh=int(f[7]), oa=f[8], oh=f[9], src=f[10]))
    G.sort(key=lambda g: g['date']); n4 = tired_flags(G); ML, PL, skip = [], [], 0
    for i, g in enumerate(G):
        ta, th = n4[(i, g['a'])] >= 3, n4[(i, g['h'])] >= 3
        if ta == th: continue
        side = 'A' if ta else 'H'
        mla, mlh = g['mla'], g['mlh']
        if mla == -110 and mlh == -110 and g['oa'] and g['oh']:
            oa, oh = int(g['oa']), int(g['oh']); po = ip(oa)/(ip(oa)+ip(oh))
            if abs(po - 0.5) > 0.04: skip += 1; continue
        pr = mla if side == 'A' else mlh; opp = mlh if side == 'A' else mla
        p = ip(pr)/(ip(pr)+ip(opp)); fav = p > 0.5 or (p == 0.5 and side == 'H')
        m = (g['ag']-g['hg']) if side == 'A' else (g['hg']-g['ag'])
        tag = dict(fav='Favorite' if fav else 'Underdog', venue='Home' if side == 'H' else 'Away')
        ML.append((g['date'], 'W' if m > 0 else 'L', pr, tag))
        ln = -1.5 if fav else 1.5
        PL.append((g['date'], 'W' if m + ln > 0 else 'L', est_pl_price(p, fav), tag))
    return ML, PL, skip, len(G)

def bets_now():
    import tests as T, fatigue
    ctx = fatigue.contexts(); ML, PL = [], []
    for x in T.rows:
        g = x['g']; a, h = ctx[(g['id'], g['a'])], ctx[(g['id'], g['h'])]
        ta, th = a['n4'] >= 3, h['n4'] >= 3
        if ta == th: continue
        side = 'A' if ta else 'H'; mla, mlh = g['sb']['mlc']
        pr = mla if side == 'A' else mlh; opp = mlh if side == 'A' else mla
        fav = ip(pr) > ip(opp) or (pr == opp and side == 'H')
        tag = dict(fav='Favorite' if fav else 'Underdog', venue='Home' if side == 'H' else 'Away')
        b = fatigue.ml_bet(x, side)
        if b: ML.append(b + (tag,))
        b = fatigue.pl_bet(x, side)
        if b:
            pc = g['sb']['plc']; sp = pc['sp'] if side == 'A' else -pc['sp']
            PL.append(b + (dict(tag, fav='Favorite' if sp < 0 else 'Underdog'),))
    return ML, PL, len(T.GAMES)

def summ(b):
    a = rules.agg([x[:3] for x in b]); return a
def line(a): return f"{a['w']}-{a['l']} {a['u']:+.2f}u, win {100*(a['wp'] or 0):.1f}% vs break-even {100*(a['be'] or 0):.1f}%"

OUT = {}
def report(name, ML, PL, extra=''):
    print(f"\n== {name} {extra}")
    for mk, B in (('Moneyline', ML), ('Puck line', PL)):
        a = summ(B); OUT.setdefault(name, {})[mk] = dict(all=a); print(f"  {mk}: {line(a)}")
        for key in ('fav', 'venue'):
            for val in sorted({x[3][key] for x in B}):
                s = summ([x for x in B if x[3][key] == val]); OUT[name][mk][val] = s; print(f"     {val}: {line(s)}")
        for v1 in ('Favorite', 'Underdog'):
            for v2 in ('Home', 'Away'):
                s = summ([x for x in B if x[3]['fav'] == v1 and x[3]['venue'] == v2])
                if s['n']: OUT[name][mk][f'{v1} {v2}'] = s; print(f"       {v1} {v2}: {line(s)}")

if __name__ == '__main__':
    print('PL price fit (DraftKings closes 2026-27):', {k: (round(a, 3), round(b, 3), n) for k, (a, b, n) in FIT.items()})
    allML, allPL = [], []
    for s, nm in (('20242025', '2024-25'), ('20252026', '2025-26')):
        ML, PL, skip, n = bets_hist(s); allML += ML; allPL += PL
        report(nm, ML, PL, f'({n} games; {skip} placeholder closes skipped; puck line units at ESTIMATED prices)')
    ML, PL, n = bets_now(); allML += ML; allPL += PL
    report('2026-27 to date', ML, PL, f'({n} games, SBR median close)')
    report('All three seasons', allML, allPL, '(puck line units partly estimated)')
    json.dump(OUT, open(R/'fatigue_back_bt.json', 'w'), indent=1)
