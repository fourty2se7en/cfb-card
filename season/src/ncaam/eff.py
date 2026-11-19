"""Possession-based efficiency ratings (adjusted offense, adjusted defense, tempo), same method as the Nov 2026 backtest (bt_run2.js).
Last season's final ratings, regressed 25% to the league mean, are blended with this season's ratings by games / (games + 8).
Possessions = FGA - ORB + TO + 0.475 x FTA, averaged over both teams. Home court is 1.4% of efficiency each way (about 3 points)."""
import pathlib
D = pathlib.Path(__file__).parent; DATA = D.parent/'data'
HC = 0.014

def load_prior(lg):
    p = DATA/f'eff_{lg.lower()}_2025-26.txt'
    if not p.exists(): return {}, dict(o=100.0, t=68.0)
    R, Lg = {}, dict(o=100.0, t=68.0)
    for tok in p.read_text().strip().split(';'):
        f = tok.split(',')
        if f[0] == 'LG': Lg = dict(o=float(f[1]), t=float(f[3])); continue
        R[f[0]] = dict(o=float(f[1]), d=float(f[2]), t=float(f[3]))
    return R, Lg

def poss(fga, orb, to, fta): return fga - orb + to + 0.475*fta

def solve(games):
    """games: list of dict(h, a, hs, as_, poss, nu). Returns (ratings, league, counts)."""
    rows = []
    for g in games:
        rows.append((g['h'], g['a'], g['hs'], g['as_'], g['poss'], 'N' if g['nu'] else 'H'))
        rows.append((g['a'], g['h'], g['as_'], g['hs'], g['poss'], 'N' if g['nu'] else 'A'))
    if not rows: return {}, None, {}
    Lg = dict(o=100*sum(r[2] for r in rows)/sum(r[4] for r in rows), t=sum(r[4] for r in rows)/len(rows))
    e = {r[0]: dict(o=Lg['o'], d=Lg['o'], t=Lg['t']) for r in rows}
    for _ in range(8):
        n = {t: [0.0, 0.0, 0.0, 0] for t in e}
        for t, o, pf, pa, ps, loc in rows:
            op = e[o]; hf = 1 + HC if loc == 'H' else (1 - HC if loc == 'A' else 1)
            n[t][0] += 100*pf/ps/hf*Lg['o']/op['d']; n[t][1] += 100*pa/ps*hf*Lg['o']/op['o']; n[t][2] += ps*Lg['t']/op['t']; n[t][3] += 1
        e = {t: dict(o=v[0]/v[3], d=v[1]/v[3], t=v[2]/v[3]) for t, v in n.items()}
    cnt = {}
    for r in rows: cnt[r[0]] = cnt.get(r[0], 0) + 1
    return e, Lg, cnt

def rate(t, prior, PLg, cur, CLg, cnt):
    Lg = CLg or PLg; n = cnt.get(t, 0); w = n/(n+8)
    p = prior.get(t); p = dict(o=0.75*p['o']+0.25*Lg['o'], d=0.75*p['d']+0.25*Lg['o'], t=0.75*p['t']+0.25*Lg['t']) if p else dict(o=Lg['o']-4, d=Lg['o']+4, t=Lg['t'])
    c = cur.get(t, p)
    return dict(o=w*c['o']+(1-w)*p['o'], d=w*c['d']+(1-w)*p['d'], t=w*c['t']+(1-w)*p['t']), Lg

def project(h, a, nu, prior, PLg, cur=None, CLg=None, cnt=None):
    """Returns (home margin, total, home pts, away pts)."""
    cur = cur or {}; cnt = cnt or {}
    H, Lg = rate(h, prior, PLg, cur, CLg, cnt); A, _ = rate(a, prior, PLg, cur, CLg, cnt)
    pace = H['t']*A['t']/Lg['t']; hf, af = (1, 1) if nu else (1 + HC, 1 - HC)
    pH = pace*(H['o']*A['d']/Lg['o'])/100*hf; pA = pace*(A['o']*H['d']/Lg['o'])/100*af
    return pH - pA, pH + pA, pH, pA
