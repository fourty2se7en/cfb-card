"""Nov 13 post step (copied from post_nov11.py; summaries for Nov 12) for NCAAW hub docs: conflict reasons on would-be picks, market on every reason, summary {for, against},
no-pick market analysis, lineups/units/adjustments from ESPN box scores, line_source. Reads ../hub_out, writes ../post2."""
import json, pathlib, statistics, os as _o2
W = pathlib.Path(__file__).parent.parent; O = W/'post2'; O.mkdir(exist_ok=True)
P = [p for p in json.load(open(W/'hub_out'/'picks.json')) if 'ORU-OU' not in p['id']]; G = [g for g in json.load(open(W/'hub_out'/'games.json')) if 'ORU-OU' not in g['id']]
META = {r['key']: r for r in json.load(open(_o2.environ.get('HUB_META')))['rules']}
RN = {'SPREAD_MOVE': 'Line move spread', 'EFF_SPREAD': 'Efficiency spread', 'MODEL_EDGE': 'Model spread', 'UNDER_DROP': 'Falling total under',
      'EFF_OVER': 'Efficiency over', 'OVER': 'Signal over', 'EARLY_UNDER_OPEN': 'Early under vs open', 'EARLY_OVER_OPEN': 'Early over vs open',
      'NEUTRAL_UNDER': 'Neutral site under', 'DOG_ML': 'Underdog moneyline', 'FAV_ML': 'Favorite moneyline'}
SUM = {
 '2026-11-13_NU-WVU': {
  'WVU': ("The spread has moved from West Virginia 20.5 at the Odds API open to 25, a 4.5 point move toward the No. 24 Mountaineers, and our margin model has West Virginia by 25.5. West Virginia is 3-0, winning by 18 at Georgia Tech, 12 over George Washington and 4 over Rhode Island, and allows 64.3 points per game.",
          "Our efficiency model has West Virginia by 22.2, under the 25 point spread, and the game is at a neutral site. Northwestern is 1-2 but lost by only 5 at UIC and beat Milwaukee, and West Virginia's last win came by 4."),
  'NU': ("Our efficiency model projects West Virginia by 22.2, short of the 25 point spread, and the game is at a neutral site with both teams on five days of rest. Northwestern scores 71 points per game, and West Virginia beat Rhode Island by only 4 last time out.",
         "The spread has moved 4.5 points toward West Virginia since the open, and our margin model has West Virginia by 25.5. Northwestern allows 75.7 points per game and lost 91-78 at home to Xavier."),
  'total': ("The total opened 144.5 and has held there, and our efficiency model total is 139.1. Northwestern's games have totaled 147, 169 and 124; West Virginia's 144, 144 and 132.",),
  'total_under': ("Our efficiency model total is 139.1, 5.4 points under the 144.5 opener, and the game is at a neutral site. West Virginia allows 64.3 points per game and its last game totaled 132.",
                  "Northwestern's defense allows 75.7 points per game, and two of its three games went over 144.5. The total has not dropped since it opened.")},
 '2026-11-13_DEN-LSU': {
  'DEN': ("Our efficiency model projects LSU by 53.4 and the margin model by 61.1, both well short of a 75.5 point spread, the biggest number on the women's board. Denver has played four Division I games and lost by 36 at Colorado State, its worst result, and it beat Lindenwood by 14.",
          "The spread has moved 11 points toward LSU since it opened at 64.5, and LSU has won its three home games by 57, 109 and 94 while scoring 120 points per game. Denver scores 53 points per game and has lost three of four."),
  'LSU': ("The spread has moved from 64.5 at the open to 75.5, an 11 point move toward the No. 9 Tigers. LSU has won by 57, 109 and 94 at home, scoring 120 and allowing 33.3 points per game, and Denver scores 53 points per game.",
          "Our efficiency model has LSU by 53.4 and the margin model by 61.1, both far short of 75.5. A 75.5 point spread needs LSU to beat a Division I team by more than its margin against McNeese."),
  'total': ("The total opened 146.5 and has held there, and our efficiency model total is 147.0, right on the number. LSU's games have totaled 143, 153 and 164; Denver's 136, 115, 118 and 111.",)},
}
NONE_TOTAL = {
 '2026-11-13_NU-WVU': "Two total rules fit the Under, Early under vs open at the Solid tier and Neutral site under at the Lean tier, and both are turned off, so the Under is logged as a would-be pick and the card has no total.",
 '2026-11-13_DEN-LSU': "No total rule fits: the total has not moved since it opened and our model total is right on the posted number.",
}

def mkt(item, market):
    lab = (item.get('label', '') + ' ' + item.get('detail', '')).lower()
    if any(k in lab for k in ('injur', 'home court', 'rest', 'form', 'backtest', 'texas222', 'neutral', 'travel')): m = 'Game context'
    else: m = market
    item['market'] = m; return item

# lineups from ESPN box scores (this season, Division I games)
PL = {}
import os as _o
for l in (open(W.parent/'pull'/'players.txt') if _o.path.exists(W.parent/'pull'/'players.txt') else []):
    f = l.strip().split('|')
    if len(f) < 13: continue
    t, n, pos = f[0], f[1], f[2]; g, gs, ls, mn, pts, reb, ast, stl, blk, tov = map(int, f[3:13])
    PL.setdefault(t, []).append(dict(n=n, pos=pos, g=g, gs=gs, ls=ls, mn=mn, pts=pts, reb=reb, ast=ast, stl=stl, blk=blk, tov=tov))
allp = [p for v in PL.values() for p in v]
def per40(p, k): return 40 * p[k] / max(p['mn'], 1)
def pct(v, arr): return round(100 * sum(1 for x in arr if x <= v) / len(arr))
DIM = {k: sorted(per40(p, k) for p in allp) or [0] for k in ('pts', 'reb', 'ast', 'stl', 'blk', 'tov')}
def prod(p): return (p['pts'] + p['reb'] + p['ast'] + p['stl'] + p['blk'] - p['tov']) / max(p['mn'], 1)
PRODS = sorted(prod(p) for p in allp) or [0]
def player(p, team):
    r = pct(prod(p), PRODS); s, w = [], []
    if pct(per40(p, 'pts'), DIM['pts']) >= 70: s.append('Scoring')
    if pct(per40(p, 'reb'), DIM['reb']) >= 70: s.append('Rebounding')
    if pct(per40(p, 'ast'), DIM['ast']) >= 70: s.append('Playmaking')
    if pct(per40(p, 'stl') + per40(p, 'blk'), sorted(per40(x, 'stl') + per40(x, 'blk') for x in allp)) >= 70: s.append('Steals and blocks')
    if pct(per40(p, 'tov'), DIM['tov']) >= 75: w.append('Turnovers')
    if pct(per40(p, 'pts'), DIM['pts']) <= 25: w.append('Low scoring')
    if pct(per40(p, 'reb'), DIM['reb']) <= 20 and p['pos'] in ('F', 'C'): w.append('Rebounding')
    mpg = p['mn'] / p['g']
    return dict(player=p['n'], pos=p['pos'], role='Starter' if p['ls'] else 'Rotation', starter=bool(p['ls']), status='Available',
                rating=r, strengths=s, weaknesses=w, mpg=round(mpg, 1), ppg=round(p['pts'] / p['g'], 1), rpg=round(p['reb'] / p['g'], 1), apg=round(p['ast'] / p['g'], 1),
                source='ESPN box scores, Division I games this season; no injury report posted')
def lineup(t):
    ps = sorted(PL.get(t, []), key=lambda p: (-p['ls'], -p['mn'] / p['g']))
    return [player(p, t) for p in ps if p['mn'] / p['g'] >= 6]
def units(t):
    ps = [p for p in PL.get(t, []) if p['ls']] or PL.get(t, [])
    if not ps: return {}
    agg = lambda k: sum(p[k] for p in ps); mn = agg('mn')
    def u(k, arr): return pct(40 * agg(k) / mn, arr)
    return {'Scoring': {'rating': u('pts', DIM['pts']), 'note': 'starters, points per 40 minutes'},
            'Rebounding': {'rating': u('reb', DIM['reb']), 'note': 'starters, rebounds per 40'},
            'Playmaking': {'rating': u('ast', DIM['ast']), 'note': 'starters, assists per 40'},
            'Ball security': {'rating': 100 - u('tov', DIM['tov']), 'note': 'starters, fewer turnovers per 40 is higher'},
            'Defense plays': {'rating': pct(40 * (agg('stl') + agg('blk')) / mn, sorted(per40(x, 'stl') + per40(x, 'blk') for x in allp)), 'note': 'starters, steals plus blocks per 40'}}

PD = {p['id']: p for p in P}
out_p, out_g = [], []
for g in G:
    gid, d = g['id'], g['data']; A, H = d['away']['code'], d['home']['code']; S = SUM[gid]
    side = d['picks']['side']
    for k in ('side', 'side_against'): d['reasons'][k] = [mkt(x, 'Spread') for x in d['reasons'].get(k, [])]
    for k in ('total', 'total_against'): d['reasons'][k] = [mkt(x, 'Total') for x in d['reasons'].get(k, [])]
    if side.get('pick'):
        team = side['pick'].split()[0]; f, a = S[team]; side['summary'] = {'for': f, 'against': a}
    d['picks']['total'] = {'none': NONE_TOTAL[gid], 'analysis': S['total'][0]}
    d['lineups'] = {'away': lineup(A), 'home': lineup(H)}; d['units'] = {'away': units(A), 'home': units(H)}
    d['model']['adjustments'] = []
    d['model']['adjustments_note'] = 'No absences reported for either team (ESPN injuries feed lists none for these teams); no adjustment applied.'
    d['line_history'] = [{'as_of': '2026-11-13', 'spread': d['lines']['spread']['home'].split()[0] + ' ' + H, 'total': d['lines']['total']['over'].split()[0], 'ml_away': (d['lines'].get('moneyline') or {}).get('away'), 'ml_home': (d['lines'].get('moneyline') or {}).get('home'), 'source': 'The Odds API median of books'}]
    d['lines']['book'] = 'The Odds API median of books'
    d['notes'] = [n for n in d['notes'] if not n.startswith('Signal score')]
    d['moves'] = [m.replace('(DraftKings)', '(The Odds API median of books)') for m in d.get('moves', [])]
    if d['lines'].get('moneyline') and any(abs(int(str(v).replace('+', ''))) > 5000 for v in d['lines']['moneyline'].values() if v): d['lines'].pop('moneyline')
    d['notes'].append('Write-up uses the run data (ESPN results, The Odds API and DraftKings lines, Action Network tickets); previews were not read this run.')
    if not d['lineups']['away'] or not d['lineups']['home']: d['notes'].append('Starting lineups not available this run: no player box scores saved for these teams yet.')
    out_g.append({'id': gid, 'data': d})
for p in P:
    d = p['data']; gid = f"{d['date']}_{d['away']}-{d['home']}"; S = SUM[gid]
    mk = 'Total' if d['market'] == 'Total' else 'Spread'
    d['reasons'] = [mkt(x, mk) for x in d['reasons']]; d['against'] = [mkt(x, mk) for x in d['against']]
    d['line_source'] = 'The Odds API median of books'
    if d['market'] == 'Total':
        key = 'total_over' if d['pick'].startswith('Over') else 'total_under'
        f, a = S.get(key, (S['total'][0], 'Our model total and the line move point different ways in this game.'))
    else:
        team = d['pick'].split()[0]; f, a = S[team] if team in S else (S[d['home']][0], S[d['home']][1])
    d['summary'] = {'for': f, 'against': a}
    if d.get('shadow'):
        t = (META[d['rule']].get('tiers') or {}).get(d['tier'], {}); on = META[d['rule']]['on']
        card = out_g[[x['id'] for x in out_g].index(gid)]['data']['picks']
        slot = card['side'] if mk == 'Spread' else card['total']
        if t.get('on') and slot.get('pick'):
            c = f"Card picked {slot['pick']} in this game with {RN.get([q for q in P if q['id']==slot['doc_id']][0]['data']['rule'], 'another rule')}; one side pick per game."
            if slot['pick'].split()[0] != d['pick'].split()[0]: c += ' This fit backs the other team.'
        elif not on:
            c = f"{RN[d['rule']]} is turned off at the {d['tier']} tier (real picks red), so this fit is logged as a would-be pick."
        else:
            c = f"{RN[d['rule']]} is on, but its {d['tier']} tier is turned off (real picks red), so this fit is a would-be pick."
        if slot.get('pick') and mk == 'Spread' and slot['pick'].split()[0] != d['pick'].split()[0] and 'other team' not in c:
            c += f" The card pick in this game is {slot['pick']}."
        d['conflict'] = c
    out_p.append(p)
for p in out_p: json.dump(p['data'], open(O/f"p_{p['id']}.json", 'w'))
for g in out_g: json.dump(g['data'], open(O/f"g_{g['id']}.json", 'w'))
json.dump(out_p, open(O/'picks.json', 'w')); json.dump(out_g, open(O/'games.json', 'w'))
for p in out_p: print(p['id'], p['data']['pick'], p['data'].get('shadow'), p['data'].get('conflict', ''))

