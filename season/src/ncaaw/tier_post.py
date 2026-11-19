import json, math, pathlib
W = pathlib.Path('/home/claude/w/work'); O = pathlib.Path('/home/claude/w/post')
P = json.load(open(W/'hub_out/picks.json')); G = json.load(open(W/'hub_out/games.json'))
def gp(g): return min(4, int(g // 2))
def tierof(l): return 'Strong' if l >= 4 else ('Solid' if l >= 2 else 'Lean')
TRIG = {'MODEL_EDGE': 'Projection beats the spread', 'EFF_SPREAD': 'Efficiency model edge', 'EARLY_UNDER_OPEN': 'Model vs opening total', 'EARLY_OVER_OPEN': 'Model vs opening total', 'EFF_OVER': 'Efficiency model total'}
def retier(d):
    rule = d['rule']; gap = None
    m = d.get('model', {})
    if rule in ('EARLY_UNDER_OPEN', 'EARLY_OVER_OPEN'): gap = m.get('edge_vs_open')
    elif rule in TRIG: gap = m.get('edge')
    for it in d['reasons']:
        if rule in TRIG and it['label'].startswith(TRIG[rule]) and gap is not None:
            it['points'] = gp(abs(gap)); it['detail'] += f" (model gap {abs(gap):.1f} = {gp(abs(gap))} points)"
    f = sum(x['points'] or 0 for x in d['reasons']); a = sum(x['points'] or 0 for x in d['against'])
    d['rule_tier'] = d.get('tier', 'Thin'); d['tier'] = tierof(f - a)
    d['tier_basis'] = f"signal lead {f - a} (for {f}, against {a})"
    return d
picks = []
for p in P:
    d = retier(p['data'])
    sp = d['pick'].split()[-1]; d['line'] = float(sp) if d['market'] != 'Moneyline' else None
    d['sport'] = 'ncaaw'; d['shadow'] = False
    picks.append(dict(id=p['id'], data=d))
PD = {p['id']: p['data'] for p in picks}
# shadow: SPREAD_MOVE (off) fits MINN -10
base = PD['2026-11-07_MINN-MARQ_side']
sh = {k: base[k] for k in ('date', 'game', 'away', 'home', 'time', 'day', 'conference', 'line_source', 'last5', 'experts')}
sh.update(market='Spread', pick='MINN -10', line=-10.0, price=-115, rule='SPREAD_MOVE', rule_variant='strict', result='pending', final='', conflicting=False, projected=None,
          shadow=True, sport='ncaaw',
          note='Shadow pick: SPREAD_MOVE is off (rules frozen through Nov 8; it turns on Nov 9 if still green). Logged and graded, not shown as a pick.',
          reasons=[dict(label='Line moved toward it at both books', detail='DraftKings MINN -8.5 open to -9.5; Action Network open MINN -8.5, texas222 now MINN -10 (SPREAD_MOVE trigger)', points=2, source='Card signal score'),
                   dict(label='Projection beats the spread by 5.5', detail='rating model MINN by 15.5 vs MINN -10', points=1, source='Card signal score'),
                   dict(label='Tickets unknown', detail='Action Network posts no women\'s ticket split, so the under 50% ticket gate passes as live', points=None, source='Action Network')],
          against=[dict(label='Home court', detail='home court', points=1, source='Card signal score'),
                   dict(label='Injuries unconfirmed', detail='college injury reporting is thin; no confirmed absences pulled (LOW)', points=None, source='Card')],
          rule_record=dict(rule='SPREAD_MOVE', every_game='16-9 +5.55u', card='0-0', last_3_weeks='16-9 +5.55u', status='off'),
          model=dict(projection='MINN by 15.5 (rating model)', edge=5.5))
f = 3; a = 1; sh.update(tier=tierof(f - a), tier_basis=f'signal lead {f-a} (for {f}, against {a})', rule_tier='strict')
picks.append(dict(id='2026-11-07_MINN-MARQ_side_SPREADMOVE', data=sh))
# game docs
games = []
for g in G:
    d = g['data']
    for k in ('side', 'total'):
        pk = d['picks'].get(k, {})
        if pk.get('doc_id') in PD:
            x = PD[pk['doc_id']]; pk['tier'] = x['tier']; pk['tier_basis'] = x['tier_basis']; pk['rule_tier'] = 'Thin'
            if k in d['reasons']: d['reasons'][k] = x['reasons']; d['reasons'][k + '_against'] = x['against']
    if d.get('lines', {}).get('spread') or d.get('lines', {}).get('total'):
        d['notes'].append('No period lines (1H, 2H, quarters) posted at texas222 for women\'s games; DraftKings via ESPN has none either.')
    if g['id'].endswith('MINN-MARQ'):
        d['moves'].append('texas222 now MINN -10 (Action Network open MINN -8.5)')
        d['lines']['openers'] = 'Action Network MINN -8.5; DraftKings MARQ +8.5 / total 134.5'
        d['splits'] = [dict(market='Spread', opener='MINN -8.5', away_or_over=dict(tickets=None, money=None, tags=[]), home_or_under=dict(tickets=None, money=None, tags=[]))]
        d['notes'].append('Action Network lists no ticket or money split for this game.')
    if g['id'].endswith('SOU-ILL'):
        d['lines']['openers'] = 'Action Network SOU +34.5; DraftKings ILL -34.5 / total 129.5'
        d['splits'] = [dict(market='Spread', opener='SOU +34.5', away_or_over=dict(tickets=None, money=None, tags=[]), home_or_under=dict(tickets=None, money=None, tags=[]))]
    games.append(g)
(O/'picks').mkdir(exist_ok=True); (O/'games').mkdir(exist_ok=True)
for p in picks: json.dump(p['data'], open(O/'picks'/f"{p['id']}.json", 'w'), indent=1)
for g in games: json.dump(g['data'], open(O/'games'/f"{g['id']}.json", 'w'), indent=1)
for p in picks: print(p['id'], p['data']['pick'], p['data']['price'], p['data']['tier'], p['data']['tier_basis'], p['data']['rule'], 'shadow' if p['data']['shadow'] else '')
