import json, glob
TOT = {}
for f in glob.glob('final/sports_nba_picks__2026-11-12_*_total_*.json'):
    d = json.load(open(f))
    if not d.get('shadow'): TOT[d['away'] + '-' + d['home']] = d['pick']
GATE = {'points', 'threes', 'assists', 'pra'}
held = []
for f in glob.glob('final/sports_nba_picks__2026-11-12_*_prop_*.json'):
    d = json.load(open(f)); k = d['away'] + '-' + d['home'] if d.get('away') else f.split('__2026-11-12_')[1].split('_')[0]
    t = TOT.get(k)
    if not t or d.get('stat') not in GATE: continue
    if (d['side'] == 'over') == t.startswith('Under'):
        d['held'] = True; d['held_reason'] = f"against {t} (card total pick)"; d['tracking'] = True
        if d.get('tier') == 'PLAY': d['original_tier'] = 'PLAY'; d['tier'] = 'LEAN'
        json.dump(d, open(f, 'w'), indent=1); held.append((d['pick'], d['held_reason']))
for f in glob.glob('final/sports_nba_games__2026-11-12_*.json'):
    g = json.load(open(f)); k = f.split('_')[-1][:-5]; t = TOT.get(k)
    for pr in g.get('props', []):
        if t and str(pr.get('stat', '')).lower() in GATE and str(pr.get('side', '')).lower() == ('over' if t.startswith('Under') else 'under'):
            pr['grade'] = 'held'; pr['held_reason'] = f"against {t} (card total pick)"
    for slot in ('side', 'total'):
        p = g['picks'].get(slot) or {}
        if p.get('doc_id'):
            pf = f"final/sports_nba_picks__{p['doc_id']}.json"
            try: p['summary'] = json.load(open(pf))['summary']
            except FileNotFoundError: pass
    json.dump(g, open(f, 'w'), indent=1)
print(held)
