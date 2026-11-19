"""Roster move adjustments for the NFL card (Trina, Nov 11: trades called out on every game card and factored into the analysis).
Input: transactions.json (researched moves, each with a dated source), injuries.json (QB changes), lineups.py (player ratings).
Output: roster_adj.json {team: {pts, tot, items}} read by model.py (pts move our spread, tot moves our total) and build_preview.py.
Usage: NFL_DIR=. python3 transactions.py

Method (non-QB moves; QB changes stay in injuries.json, 3.0 points by the fitted qb_out_pts, Minnesota by pts_off):
- Position value V = points per game for a 100 point rating gap: WR 1.2, TE 0.8, RB 0.6, OL 0.6, DL 1.0, LB 0.6, CB 1.0, S 0.8
  (QB 6.0, so a typical 50 point starter to backup gap equals the fitted 3.0).
- A starter traded away or put on IR (he started at his slot in the team's last 3 games): loss = V x (his rating - the rating of
  the player who now starts at his slot) / 100. A non-starter leaving costs 0.
- A player acquired who Starts: gain = 0.5 x V x (his rating - the rating of the starter he displaces) / 100 (half credit in his
  first week with a new team); Rotation: 0.25 credit against the lowest rated starter at his slot; Backup: 0.
- Moves already in the data (the player has played for his new team, already_in_data) cost 0: the ratings carry them.
- Each move is capped at 1.0 point. Offensive moves move the team's points (total moves the same way); defensive moves move the
  opponent's points (total moves the other way). Missing ratings count as 50.
"""
import json, os, pathlib
D = pathlib.Path(os.environ.get('NFL_DIR', '.'))
import lineups as LU

T = json.load(open(D/'transactions.json'))['moves']
INJ = json.load(open(D/'injuries.json'))
SIG = json.load(open(D/'signals.json'))
V = {'QB': 6.0, 'WR': 1.2, 'TE': 0.8, 'RB': 0.6, 'OL': 0.6, 'DL': 1.0, 'LB': 0.6, 'CB': 1.0, 'S': 0.8}
OFF = {'QB', 'WR', 'TE', 'RB', 'OL'}
CAP = 1.0

def r50(x): return 50 if x is None else x

def team_moves(t): return [m for m in T if m['team'] == t]

def qb_start(t):
    q = INJ.get(t, {})
    return q.get('starter') if q.get('qb1_out') else None

out = {}
for t in sorted({m['team'] for m in T}):
    mv = team_moves(t)
    lineup, _ = LU.build(t, qb_start(t), None, mv)
    base, _ = LU.build(t, None, None, [])
    items = []
    for m in mv:
        sl = m['slot']; it = dict(player=m['player'], pos=m['pos'], slot=sl, move=m['move'], date=m['date'], role_now=m['role_now'])
        if sl == 'QB':
            q = INJ.get(t, {})
            if q.get('qb1_out') and (m['player'] in (q.get('qb1'), q.get('starter')) or m['move'].startswith('Traded')):
                p_off = q.get('pts_off', SIG['qb_out_pts'])
                it.update(effect_pts=0.0, effect_tot=0.0, in_qb_model=True,
                          reason=f"QB change in injuries.json: {q.get('starter')} starts for {q.get('qb1')}, {(-p_off):+.1f} points to {t} in the model")
            else:
                it.update(effect_pts=0.0, effect_tot=0.0, reason='QB not starting this week either way')
            items.append(it); continue
        if m.get('already_in_data'):
            it.update(effect_pts=0.0, effect_tot=0.0, reason='already in the ratings (he has played for his new team)')
            items.append(it); continue
        r = LU.rating_of(m['player'], sl)
        it['rating'] = r
        if m['role_now'] == 'Out':
            was = any(z['player'] == m['player'] and z['pos'] == sl for z in base)
            if not was:
                it.update(effect_pts=0.0, effect_tot=0.0, reason=f"not a starter in {t}'s last 3 games, no change to the starting lineup")
                items.append(it); continue
            rep = next((z for z in lineup if z.get('replaces') == m['player']), None)
            rr = rep['rating'] if rep else None
            loss = min(CAP, V[sl] * max(0, r50(r) - (30 if rr is None else rr)) / 100)
            it.update(replaced_by=rep['player'] if rep else None, replaced_by_rating=rr, effect_pts=-round(loss, 2),
                      effect_tot=round(-loss if sl in OFF else loss, 2),
                      reason=f"{m['player']} ({r50(r)}) out, {rep['player'] if rep else 'next man up'} ({30 if rr is None else rr}) starts")
        elif m['move'].startswith('Acquired') and m['role_now'] in ('Starts', 'Rotation'):
            row = next((z for z in lineup if z['player'] == m['player']), None)
            if m['role_now'] == 'Starts' and row and row.get('replaces'):
                vs = row['replaces']; vr = LU.rating_of(vs, sl, t); cr = 0.5
            else:
                st = [z for z in lineup if z['pos'] == sl and z['player'] != m['player']]
                low = min(st, key=lambda z: r50(z['rating'])) if st else None
                vs = low['player'] if low else None; vr = low['rating'] if low else None; cr = 0.5 if m['role_now'] == 'Starts' else 0.25
            gain = min(CAP, cr * V[sl] * max(0, r50(r) - r50(vr)) / 100)
            it.update(vs=vs, vs_rating=vr, credit=cr, effect_pts=round(gain, 2), effect_tot=round(gain if sl in OFF else -gain, 2),
                      reason=f"{m['player']} ({r50(r)}) over {vs} ({r50(vr)}) at {int(cr*100)}% credit in his first week")
        else:
            it.update(effect_pts=0.0, effect_tot=0.0, reason='depth only this week')
        items.append(it)
    out[t] = dict(pts=round(sum(i['effect_pts'] for i in items), 2), tot=round(sum(i['effect_tot'] for i in items), 2), items=items)

json.dump(dict(_about=__doc__.strip().split('\n')[0] + ' See transactions.py for the method.', built_from='transactions.json, injuries.json, lineups.py', teams=out),
          open(D/'roster_adj.json', 'w'), indent=1, default=str)
for t, v in out.items():
    print(t, v['pts'], v['tot'], '; '.join(f"{i['player']} {i['effect_pts']:+.2f}" for i in v['items']))
