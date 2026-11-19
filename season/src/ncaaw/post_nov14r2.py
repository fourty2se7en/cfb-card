"""Nov 14 second run (about 7:50 AM Phoenix) post step: lines now posted for all 5 AP Top 25 games. Summaries, conflict text, rule keys and labels,
no-pick text, line history (keeps the early run entry), Odds API wording. Reads ../hub_out and the hub game docs (env HUB_GAMES), writes ../post2r2."""
import json, pathlib, os
W = pathlib.Path(__file__).parent.parent; O = W/'post2r2'; O.mkdir(exist_ok=True)
P = json.load(open(W/'hub_out'/'picks.json')); G = json.load(open(W/'hub_out'/'games.json'))
HG = pathlib.Path(os.environ['HUB_GAMES'])
META = {r['key']: r for r in json.load(open(os.environ['HUB_META']))['rules']}
LAB = lambda k: META[k].get('label', k)
FAM = {'SPREAD_MOVE_1': 'SPREAD_MOVE', 'SPREAD_MOVE_05': 'SPREAD_MOVE'}
NOW = '2026-11-14 07:50'
S = {
 '2026-11-14_TAR-TEX': {
  'TAR': ("Our efficiency model projects Texas by 33.5, 14 points short of the 47.5 point spread. Only one of Texas' three home wins (20, 62 and 30) cleared 47.5, and Tarleton State is 2-1.",
          "Our margin model has Texas by 54.7, and Tarleton State lost its only road game by 47. Texas scores 89.7 and allows 52.3 points per game."),
  'TEX': ("Our margin model has Texas by 54.7, above the 47.5 point spread, and Tarleton State lost its only road game by 47. Texas allows 52.3 points per game.",
          "Our efficiency model projects Texas by only 33.5, and two of Texas' three home wins came by 30 or less."),
  'total': "The total opened 131.5 and has held there; our efficiency model total is 132.9, right on the number. Texas allows 52.3 points per game and Tarleton State's games average 122."},
 '2026-11-14_DEP-ND': {
  'ND': ("The spread moved a point toward No. 13 Notre Dame, from 29.5 at the open to 30.5. Notre Dame has won its two Division I games by 83 and 48, scoring 115.5 points per game.",
         "Our efficiency model has Notre Dame by 26.5 and the margin model by 29.9, both under 30.5. DePaul is 4-0, winning each game by 20 to 32, and the game is at a neutral site."),
  'DEP': ("Our efficiency model has Notre Dame by 26.5 and the margin model by 29.9, both under 30.5. DePaul is 4-0, winning each game by 20 to 32, and the game is at a neutral site.",
          "The spread moved a point toward Notre Dame since the open, and Notre Dame has won its two Division I games by 83 and 48."),
  'total_under': ("Our efficiency model total is 149.5, 8 points under the 157.5 opener, and the game is at a neutral site. DePaul allows 63.8 points per game.",
                  "Notre Dame scores 115.5 and DePaul 89.2 points per game, and Notre Dame's two games totaled 163 and 168. The total has not dropped since it opened."),
  'total': "The total opened 157.5 and has held there; our efficiency model total is 149.5."},
 '2026-11-14_MINN-KSU': {
  'MINN': ("Our margin model has Minnesota by 14.4 and the efficiency model by 11.3, both above the 9.5 point spread. Minnesota has won by 20, 8 and 39, scoring 85.0 points per game.",
           "Kansas State is 4-0 and allows 47.2 points per game, the game is at a neutral site, and Action Network's opener (Minnesota 10.5) has come down a point."),
  'KSU': ("Kansas State is 4-0 and allows 47.2 points per game, the game is at a neutral site, and Action Network's opener (Minnesota 10.5) has come down a point.",
          "Our margin model has Minnesota by 14.4 and the efficiency model by 11.3, both above 9.5."),
  'total_under': ("Our efficiency model total is 129.3, 4.2 points under 133.5, at a neutral site. Kansas State plays slow and its games have totaled 102, 108, 107 and 129.",
                  "Minnesota's games have totaled 144, 166 and 133, and the total has not moved since it opened."),
  'total': "The total opened 133.5 and has held there; our efficiency model total is 129.3."},
 '2026-11-14_UNC-PENN': {
  'UNC': ("Our efficiency model has North Carolina by 19.7 and the margin model by 21.2, both above the 16.5 point spread. North Carolina won its other game by 69.",
          "North Carolina is 1-2, with losses by 12 and 45, and plays at Penn (The Palestra), which is 4-0 and allows 59.7 points per game."),
  'PENN': ("North Carolina is 1-2, with losses by 12 and 45, and Penn is 4-0 at The Palestra, allowing 59.7 points per game.",
           "Our efficiency model has North Carolina by 19.7 and the margin model by 21.2, both above 16.5."),
  'total_over': ("Our efficiency model total is 137.2, 6.7 points over 130.5. North Carolina allows 71.7 points per game and its games have totaled 170, 123 and 149.",
                 "Penn's last two games totaled 128 and 125, and the total has not moved from the 130.5 opener."),
  'total': "The total opened 130.5 and has held there; our efficiency model total is 137.2."},
 '2026-11-14_NEB-KU': {
  'NEB': ("Our margin model has Nebraska by 9.4 and the efficiency model by 7.0, both above the 5.5 point spread. Nebraska has won by 27, 63 and 41 and allows 41.3 points per game.",
          "Kansas is 3-0, winning by 18, 25 and 48, allows 49.3 points per game, and the game is at a neutral site."),
  'KU': ("Kansas is 3-0, winning by 18, 25 and 48, allows 49.3 points per game, and the game is at a neutral site.",
         "Our margin model has Nebraska by 9.4 and the efficiency model by 7.0, both above 5.5."),
  'total_under': ("Our efficiency model total is 135.7, just under 136.5, at a neutral site, and Action Network's opener was 137.5. Nebraska allows 41.3 and Kansas 49.3 points per game.",
                  "The model gap is under a point, and Nebraska's games have totaled 135 and 133 before a 111."),
  'total': "The total opened 136.5 at The Odds API (137.5 at Action Network); our efficiency model total is 135.7."},
}
NOFIT = {'side': "No spread rule fits: the line has not moved and neither model gap reaches a rule threshold.",
         'total': "No total rule fits: the total has not moved and our model total is close to the posted number."}

def mkt(item, market):
    lab = (item.get('label', '') + ' ' + item.get('detail', '')).lower()
    item['market'] = 'Game context' if any(k in lab for k in ('injur', 'home court', 'rest', 'form', 'backtest', 'neutral', 'travel')) else market
    return item

PD = {p['id']: p for p in P}
out_g = []
for g in G:
    gid, d = g['id'], g['data']; A, H = d['away']['code'], d['home']['code']; SM = S[gid]
    old = json.load(open(HG/f'{gid}.json')); old = old.get('data', old)
    for k in ('side', 'side_against'): d['reasons'][k] = [mkt(x, 'Spread') for x in d['reasons'].get(k, [])]
    for k in ('total', 'total_against'): d['reasons'][k] = [mkt(x, 'Total') for x in d['reasons'].get(k, [])]
    for kind, mk in (('side', 'Spread'), ('total', 'Total')):
        slot = d['picks'][kind]
        if slot.get('pick'):
            t = slot['pick'].split()[0]
            f, a = (SM[t] if kind == 'side' else SM.get('total_' + t.lower(), (SM['total'], '')))
            slot['summary'] = {'for': f, 'against': a}
        else:
            fits = [p['data'] for p in P if p['id'].startswith(gid + '_') and p['data']['market'] == mk and p['data'].get('shadow')]
            if fits:
                txt = '; '.join(f"{LAB(x['rule'])} ({x['pick']}, {x['tier']})" for x in fits)
                none = f"Rules that fit: {txt}. Each of those tiers is turned off, so they are logged as would-be picks and the card has no {'side' if kind == 'side' else 'total'}."
            else: none = NOFIT[kind]
            an = (SM[A][0] + ' Other side: ' + SM[H][0]) if kind == 'side' else SM['total']
            d['picks'][kind] = {'none': none, 'analysis': an}
    d['lines']['book'] = 'The Odds API median of books'
    d['lines']['openers'] = d['lines'].get('openers', '').replace('DraftKings', 'The Odds API open')
    d['moves'] = [m.replace('(DraftKings)', '(The Odds API median of books)') for m in d.get('moves', [])]
    ml = d['lines'].get('moneyline') or {}
    if any(abs(int(str(v).replace('+', ''))) > 5000 for v in ml.values() if v): d['lines'].pop('moneyline')
    d['notes'] = [n for n in d['notes'] if not n.startswith('Signal score') and 'texas222' not in n]
    d['notes'].append("Action Network lists openers for these games but no ticket or money splits yet, and its sharp report does not cover women's college games.")
    d['notes'].append('Injuries and lineups: ESPN lists no NCAAW injuries for either team; player box scores for these teams are not in the data feed yet, so no starter changes were found.')
    d['model']['adjustments'] = []; d['model']['adjustments_note'] = 'No absences reported for either team; no adjustment applied.'
    sp = d['lines']['spread']; tot = d['lines']['total']
    lh = list(old.get('line_history') or [])
    lh.append(dict(as_of=NOW, spread=f"{sp['home'].split()[0]} {H}", total=tot['over'].split()[0], ml_away=(d['lines'].get('moneyline') or {}).get('away'),
                   ml_home=(d['lines'].get('moneyline') or {}).get('home'), source='The Odds API median of books'))
    d['line_history'] = lh
    out_g.append({'id': gid, 'data': d})
GD = {g['id']: g['data'] for g in out_g}
for p in P:
    d = p['data']; gid = f"{d['date']}_{d['away']}-{d['home']}"; SM = S[gid]; mk = d['market']
    d['reasons'] = [mkt(x, mk) for x in d['reasons']]; d['against'] = [mkt(x, mk) for x in d['against']]
    d['line_source'] = 'The Odds API median of books'
    d['rule_key'] = d['rule']; d['rule_label'] = LAB(d['rule']); d['rule_family'] = FAM.get(d['rule'], d['rule'])
    if mk == 'Total':
        f, a = SM.get('total_' + d['pick'].split()[0].lower(), (SM['total'], 'Our model total and the line point different ways in this game.'))
    else:
        f, a = SM[d['pick'].split()[0]]
    d['summary'] = {'for': f, 'against': a}
    if d.get('shadow'):
        r = META[d['rule']]; on = r.get('on')
        c = (f"{LAB(d['rule'])} is turned off at the {d['tier']} tier (no green status record), so this fit is logged as a would-be pick." if not on else
             f"{LAB(d['rule'])} is on, but its {d['tier']} tier is turned off (real picks red), so this fit is a would-be pick.")
        slot = GD[gid]['picks']['side' if mk == 'Spread' else 'total']
        if slot.get('pick') and mk == 'Spread' and slot['pick'].split()[0] != d['pick'].split()[0]:
            c += f" The card pick in this game is {slot['pick']} ({slot.get('rule_label', '')}); this fit backs the other team."
        d['conflict'] = c
for p in P: json.dump(p['data'], open(O/f"p_{p['id']}.json", 'w'))
for g in out_g: json.dump(g['data'], open(O/f"g_{g['id']}.json", 'w'))
json.dump(P, open(O/'picks.json', 'w')); json.dump(out_g, open(O/'games.json', 'w'))
for p in P: print(p['id'], p['data']['pick'], p['data'].get('shadow'), p['data'].get('conflict', '')[:90])
for g in out_g: print(g['id'], {k: (v.get('pick') or v.get('none'))[:110] for k, v in g['data']['picks'].items()})
