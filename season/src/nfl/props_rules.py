"""Player prop rules (Trina, Nov 2 2026). One shared home for the prop evaluation, the prop categories and their
records, imported by model.py (live picks), props_bt.py (walk-forward backtest) and recheck.py (weekly switching).
Never copy this logic elsewhere (project 4.3n).

A prop pick belongs to a category = stat x side (PASS/RUSH/REC, Over/Under) and a tier (PLAY or LEAN, from the
edge thresholds below). Each category-tier is a rule with its own season record. Only rules that are ON are shown
on the card and logged to the picks ledger; every other pick is tracked in the background (ledger collection
picks_bg) so a rule can be promoted later. Switching is judged on the whole season (min_n picks), and the last
3 weeks only raise a monitor flag (trending up: watch for promotion; trending down: watch for demotion)."""
import math, re
import numpy as np
from rules import grade

COL = {'PASS': 'passing_yards', 'RUSH': 'rushing_yards', 'REC': 'receiving_yards'}
STATS = ('PASS', 'RUSH', 'REC'); SIDES = ('Over', 'Under'); TIERS = ('PLAY', 'LEAN')
CATS = [f'{s} {d}' for s in STATS for d in SIDES]

_SUF = re.compile(r"\s+(JR|SR|II|III|IV|V)$")
PALIAS = {'KENNETH GAINWELL': 'KENNY GAINWELL', 'JOSHUA PALMER': 'JOSH PALMER', 'HOLLYWOOD BROWN': 'MARQUISE BROWN',
          'CAMERON WARD': 'CAM WARD', 'ZONOVAN KNIGHT': 'BAM KNIGHT', 'CHIGOZIEM OKONKWO': 'CHIG OKONKWO'}   # book name -> nflverse name
def pnorm(x):
    n = _SUF.sub('', re.sub(r"[.']", '', str(x).upper()).strip()); return PALIAS.get(n, n)

def Phi(z): return 0.5*(1+math.erf(z/math.sqrt(2)))
def implied(o): return None if o is None else (100/(o+100) if o > 0 else -o/(-o+100))
def novig(a, b):
    x, y = implied(a), implied(b); return x/(x+y), y/(x+y)

def evaluate(cur, prev, allv, stat, line, po, pu, imp_pts, ppg, fav):
    """cur: this season's game values before the game; prev: last season's; allv: the last 17 games (both seasons).
    imp_pts: the team's implied points from the market spread and total; ppg: its points per game; fav: points it
    is favored by. Returns the better side as a dict (tier PLAY / LEAN / None)."""
    cur = np.asarray(cur, float); prev = np.asarray(prev, float); allv = np.asarray(allv, float)
    n = len(cur); base = prev.mean() if len(prev) else (cur.mean() if n else 0.0)
    m = (cur.sum() + base*4)/(n+4) if n else base   # last season is the base, this season's games take over (4-game prior)
    ratio = imp_pts/max(ppg, 10)
    tilt = 1 + 0.006*fav if stat == 'RUSH' else 1 - 0.004*fav   # favorites run more, underdogs throw more
    mean = m*(ratio**0.5)*tilt
    sd = max(float(np.std(allv, ddof=1)) if len(allv) > 2 else mean*0.5, 12.0 if stat != 'PASS' else 35.0)
    rate_p = 1 - Phi((line - mean)/sd)
    recv = cur if n >= 3 else allv[-8:]
    rec_p = float((recv > line).mean()) if len(recv) else rate_p
    model_over = 0.5*rate_p + 0.5*rec_p
    nvo, nvu = novig(po, pu)
    best = None
    for side, mp, price, mkp, rp_, rcp in (('Over', model_over, po, nvo, rate_p, rec_p), ('Under', 1-model_over, pu, nvu, 1-rate_p, 1-rec_p)):
        est = 0.6*mp + 0.4*(mkp - 0.025)
        be = implied(price); edge = 100*(est - be)
        agree = abs(rp_ - rcp) <= 0.08
        onside = (mean > line) if side == 'Over' else (mean < line)   # the game-script projection must agree with the side
        t = ('PLAY' if (edge >= 3 and agree and n >= 4) else ('LEAN' if edge >= 1.5 else None)) if onside else None
        hits = int((recv > line).sum()) if side == 'Over' else int((recv < line).sum())
        p = dict(side=side, price=price, line=line, est=est, be=be, edge=edge, tier=t, rate=rp_, rec=rcp, n=n,
                 hit=f'{hits}/{len(recv)}', proj=round(mean, 1), avg=round(float(cur.mean()) if n else (float(allv.mean()) if len(allv) else 0.0), 1))
        if best is None or edge > best['edge']: best = p
    return best

def category(stat, side): return f'{stat} {side}'

def default_rules():
    return dict(demote_n=20, promote_n=30, note='Category = stat x side; tier PLAY (edge 3+, record and rate within 8 points, 4+ games) or LEAN (edge 1.5+). '
                'Only rules that are on are shown and logged to picks; the rest go to picks_bg. PLAY rules start on and LEAN rules start off; '
                'a rule turns off at demote_n+ season picks with negative units and turns on at promote_n+ picks when it qualifies for the season '
                'and its last 3 weeks are not losing. The last 3 weeks only raise a watch flag.',
                cats={c: {t: dict(on=(t == 'PLAY')) for t in TIERS} for c in CATS}, records={}, flags={}, changelog=[])

def is_shown(p, PR):
    if not p.get('tier') or p.get('blocked'): return False
    return bool(PR['cats'].get(category(p['stat'], p['side']), {}).get(p['tier'], {}).get('on'))

def records(picks, MW, last3):
    """picks: iterable of dicts with week, stat, side, tier, res (+1/0/-1), price. Returns {cat: {tier: grade}}."""
    by = {c: {t: [] for t in TIERS} for c in CATS}
    for p in picks:
        if p.get('tier') in TIERS: by[category(p['stat'], p['side'])][p['tier']].append((p['week'], p['res'], p['price']))
    return {c: {t: grade(v, MW, last3) for t, v in d.items()} for c, d in by.items()}

MONTHS = ['Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb']

def switch(PR, recs, today):
    """Season to date switching (Trina, Nov 9 policy, mirrors the game rules): off when season units are negative once the rule has
    the league pick minimum (NFL 4); on at that minimum when the season qualifies (positive units, win % above break-even) and the
    last 3 weeks are not losing. The current month is a watch only. Returns the list of changes."""
    nd, npr = PR.get('demote_n', 4), PR.get('promote_n', 4); changes = []; flags = {}
    for c in CATS:
        for t in TIERS:
            g = recs[c][t]; s = g['season']; l3 = g['last3']; on = PR['cats'][c][t]['on']
            if not on and s['n'] >= npr and s['units'] > 0 and (s['W'] + s['L']) and s['pct'] > s['be'] and (not l3['n'] or l3['units'] >= 0):
                PR['cats'][c][t]['on'] = True; PR['cats'][c][t].pop('off_by_month_rule', None); changes.append(f'{today}: {c} {t} promoted ({s["W"]}-{s["L"]}, {s["units"]:+.1f}u)')
            elif on and s['n'] >= nd and s['units'] < 0:
                PR['cats'][c][t]['on'] = False; changes.append(f'{today}: {c} {t} demoted ({s["W"]}-{s["L"]}, {s["units"]:+.1f}u)')
            on = PR['cats'][c][t]['on']
            if l3['n'] >= 5:
                if on and l3['units'] < 0: flags[f'{c} {t}'] = 'trending down: watch for demotion'
                elif not on and l3['units'] > 0 and s['n']: flags[f'{c} {t}'] = 'trending up: watch for promotion'
    PR['flags'] = flags; PR['changelog'] = PR.get('changelog', []) + changes
    return changes
