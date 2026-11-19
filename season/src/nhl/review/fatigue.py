"""Fatigue trackers (added Nov 3 at Trina's request; TRACKING ONLY, never a pick rule).
1. Back the rested home team vs a road team on the second night of a back-to-back.
2. Fade a team playing its 3rd game in 4 nights (back its opponent when the opponent is not also 3-in-4).
3. Back a team playing its 3rd game in 4 nights (the reverse of 2, Trina Nov 11; same games, other side). Its daily would-be picks
   are logged by ../fatigue_back.py (FATIGUE_BACK_ML, FATIGUE_BACK_PL); its three season backtest is review/fatigue_back_bt.py.
Graded at closing prices (SBR medians), moneyline and puck line, every game this season. Both already had 30+ picks when added; review with Trina at 60 picks each."""
import json, datetime, pathlib
R = pathlib.Path(__file__).parent
from build_data import ok
D = lambda s: datetime.date.fromisoformat(s)
def contexts():
    G = sorted(json.load(open(R/'games.json')), key=lambda g: (g['date'], g['id'])); hist, ctx = {}, {}
    for g in G:
        for t, venue in ((g['a'], g['h']), (g['h'], g['h'])):
            prev = hist.get(t, []); d = D(g['date']); last = prev[-1] if prev else None
            ctx[(g['id'], t)] = dict(rest=(d - D(last[0])).days - 1 if last else 9, n4=sum(1 for p in prev if (d - D(p[0])).days <= 3) + 1)
            hist.setdefault(t, []).append((g['date'], venue))
    return ctx
def ml_bet(x, side):
    g = x['g']; p = g['sb']['mlc'][0 if side == 'A' else 1]
    if not ok(p): return None
    return (g['date'], 'W' if ((g['ag'] > g['hg']) if side == 'A' else (g['hg'] > g['ag'])) else 'L', p)
def pl_bet(x, side):
    g = x['g']; pc = g['sb'].get('plc')
    if not pc or pc['sp'] is None: return None
    sp = pc['sp'] if side == 'A' else -pc['sp']; p = pc['a'][0 if side == 'A' else 1]
    if not ok(p): return None
    m = (g['ag'] - g['hg']) if side == 'A' else (g['hg'] - g['ag'])
    return (g['date'], 'W' if m + sp > 0 else 'L', p)
TRACKERS = {
 'Rested home team vs road team on a back-to-back': lambda a, h: 'H' if a['rest'] == 0 and h['rest'] >= 1 else None,
 'Fade a team playing 3 games in 4 nights': lambda a, h: 'H' if a['n4'] >= 3 and h['n4'] < 3 else ('A' if h['n4'] >= 3 and a['n4'] < 3 else None),
 'Back a team playing 3 games in 4 nights': lambda a, h: 'A' if a['n4'] >= 3 and h['n4'] < 3 else ('H' if h['n4'] >= 3 and a['n4'] < 3 else None),
}
def run(rows, block):
    ctx = contexts(); out = {}
    for name, fn in TRACKERS.items():
        for mk, bf in (('Moneyline', ml_bet), ('Puck line', pl_bet)):
            bets = []
            for x in rows:
                g = x['g']; s = fn(ctx[(g['id'], g['a'])], ctx[(g['id'], g['h'])])
                b = bf(x, s) if s else None
                if b: bets.append(b)
            out[f'{name} | {mk}'] = block(bets)
    return out
