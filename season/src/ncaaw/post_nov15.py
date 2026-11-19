"""Nov 15 run (6:38 AM read). Based on the Nov 14 second run (about 7:50 AM Phoenix) post step: lines now posted for all 5 AP Top 25 games. Summaries, conflict text, rule keys and labels,
no-pick text, line history (keeps the early run entry), Odds API wording. Reads ../hub_out and the hub game docs (env HUB_GAMES), writes ../post2r2."""
import json, pathlib, os
W = pathlib.Path(__file__).parent.parent; O = W/'post3'; O.mkdir(exist_ok=True)
P = json.load(open(W/'hub_out'/'picks.json')); G = json.load(open(W/'hub_out'/'games.json'))
HG = pathlib.Path(os.environ['HUB_GAMES'])
META = {r['key']: r for r in json.load(open(os.environ['HUB_META']))['rules']}
LAB = lambda k: META[k].get('label', k)
FAM = {'SPREAD_MOVE_1': 'SPREAD_MOVE', 'SPREAD_MOVE_05': 'SPREAD_MOVE'}
NOW = '2026-11-15 06:38'
S = {
 '2026-11-15_EMU-UK': {
  'EMU': ("Our efficiency model has Kentucky by 35.0 and the margin model by 36.2, both well short of the 47.5 point spread. Two of Kentucky's four wins (by 43 and 15) fell short of 47.5.",
          "Eastern Michigan is 0-3, losing by 12, 10 and 18, and No. 12 Kentucky allows 44.5 points per game."),
  'UK': ("Eastern Michigan is 0-3 and scores 62.0 points per game, while No. 12 Kentucky allows 44.5 and beat its last opponent by 68.",
         "Our efficiency model has Kentucky by 35.0 and the margin model by 36.2, both well under 47.5, and two of Kentucky's four wins came by 43 and 15."),
  'total_under': ("Our efficiency model total is 135.5, 7 points under 142.5. Kentucky allows 44.5 points per game and three of its four games totaled 128 or less.",
                  "Kentucky's opener totaled 171, and Eastern Michigan's games have totaled 136, 156 and 120."),
  'total': "The total is 142.5; our efficiency model total is 135.5."},
 '2026-11-15_USC-SC': {
  'SC': ("Our margin model has South Carolina by 22.1 and the efficiency model by 9.7, both above the 6.5 point spread, and the game is in Greenville, South Carolina. No. 1 South Carolina beat North Carolina by 45 and won both meetings last season.",
         "No. 3 USC has JuJu Watkins back from her ACL injury (26.5 points and 10.5 rebounds a game in her first two) and has won by 32, 78 and 61, scoring 107.7 points per game."),
  'USC': ("No. 3 USC has JuJu Watkins back from her ACL injury (26.5 points and 10.5 rebounds a game in her first two) and has won by 32, 78 and 61, scoring 107.7 points per game.",
          "Our margin model has South Carolina by 22.1 and the efficiency model by 9.7, both above 6.5, in a building two hours from Columbia."),
  'total_under': ("Our efficiency model total is 137.2, 6.3 points under 143.5, at a neutral site. South Carolina allows 58.7 points per game and its last two games totaled 123 and 109.",
                  "USC scores 107.7 points per game and its games have totaled 168, 158 and 149; South Carolina's opener totaled 194."),
  'total': "The total is 143.5; our efficiency model total is 137.2."},
 '2026-11-15_VAN-IOWA': {
  'VAN': ("No. 8 Vanderbilt is 4-0, winning every game by 42 or more, and scores 103.8 points per game; our efficiency model has Vanderbilt by 2.3.",
          "Our efficiency model has Vanderbilt by only 2.3, just under the 2.5 point spread, and No. 10 Iowa plays this one in Sioux City, Iowa."),
  'IOWA': ("No. 10 Iowa allows 53.8 points per game, plays in Sioux City, Iowa, and our efficiency model has Vanderbilt by only 2.3, just under the 2.5 point spread.",
           "Vanderbilt is 4-0, winning every game by 42 or more, and scores 103.8 points per game."),
  'total_under': ("Our efficiency model total is 146.6, 2.9 points under 149.5, at a neutral site. Three of Iowa's four games totaled 119 or less.",
                  "Vanderbilt scores 103.8 points per game and its games have totaled 165, 142, 152 and 160."),
  'total': "The total is 149.5; our efficiency model total is 146.6."},
 '2026-11-15_OKST-SDST': {
  'SDST': ("Our efficiency model has this game even at South Dakota State's First Bank & Trust Arena, 3.5 points better for the Jackrabbits than the spread. No. 19 Oklahoma State lost its last game by 2.",
           "South Dakota State is 1-2 and allows 73.3 points per game, with losses by 2 and 30; Oklahoma State allows 49.2 and won its first three by 42, 54 and 38."),
  'OKST': ("South Dakota State is 1-2 and allows 73.3 points per game, with losses by 2 and 30; No. 19 Oklahoma State allows 49.2 and won its first three by 42, 54 and 38.",
           "Our efficiency model has this game even on South Dakota State's home floor, and Oklahoma State lost its last game by 2."),
  'total': "The total is 143.5; our efficiency model total is 144.2, right on the number."},
 '2026-11-15_MRSH-DUKE': {
  'MRSH': ("Our efficiency model has Duke by 24.0 and the margin model by 28.9, both under the 33.5 point spread. Marshall is 4-0 and allows 60.3 points per game, and two of Duke's three wins came by 22 or less.",
           "No. 5 Duke allows 46.3 points per game at Cameron Indoor and beat its last opponent by 62."),
  'DUKE': ("No. 5 Duke allows 46.3 points per game at Cameron Indoor and beat its last opponent by 62.",
           "Our efficiency model has Duke by 24.0 and the margin model by 28.9, both under 33.5, and Marshall is 4-0."),
  'total': "The total is 133.5; our efficiency model total is 132.9."},
 '2026-11-15_CONN-LOU': {
  'CONN': ("Our efficiency model has UConn by 15.8, right at the 15 point spread. No. 4 UConn is 3-1 and scores 86.0 points per game.",
           "No. 7 Louisville is 5-0 at home, winning every game by 21 or more and allowing 49.4 points per game."),
  'LOU': ("No. 7 Louisville is 5-0 at the KFC Yum! Center, winning every game by 21 or more and allowing 49.4 points per game; UConn lost one of its four games by 11.",
          "Our efficiency model has UConn by 15.8, right at the spread."),
  'total': "The total is 143.5; our efficiency model total is 141.0."},
 '2026-11-15_PRIN-UCLA': {
  'UCLA': ("Our margin model has UCLA by 33.7, 11 points over the 22.5 point spread, and No. 10 UCLA won its three games by 20, 36 and 32, allowing 46.3 points per game.",
           "Our efficiency model has UCLA by 22.3, right on the spread, and Princeton is 5-0 with every game decided by 11 or less."),
  'PRIN': ("Our efficiency model has UCLA by 22.3, right on the 22.5 point spread, and Princeton is 5-0 with every game decided by 11 or less.",
           "Our margin model has UCLA by 33.7, and UCLA won its three games by 20, 36 and 32."),
  'total_under': ("Our efficiency model total is 127.3, 4.2 points under 131.5. UCLA's three games totaled 126, 120 and 120, and Princeton allows 59.6 points per game.",
                  "Two of Princeton's last three games totaled 150 and 155, and UCLA scores 75.7 points per game."),
  'total': "The total is 131.5; our efficiency model total is 127.3."},
 '2026-11-15_COLU-MD': {'COLU': ("Our efficiency model has Maryland by 12.4 with a 150.4 total. No. 19 Maryland is 1-1 and allows 81.5 points per game; Columbia is 3-1.", ''), 'MD': ('', ''),
  'total': "Our efficiency model total is 150.4; Maryland's two games totaled 194 and 143."},
 '2026-11-15_FDU-OSU': {'FDU': ("Our efficiency model has Ohio State by 19.2 with a 135.9 total. No. 17 Ohio State is 3-1 and allows 53.5 points per game; Fairleigh Dickinson is 2-2.", ''), 'OSU': ('', ''),
  'total': "Our efficiency model total is 135.9."},
 '2026-11-15_ACU-TCU': {'ACU': ("Our efficiency model has TCU by 18.7 with a 130.8 total. No. 15 TCU is 5-0, winning every game by 25 or more and allowing 45.2 points per game; Abilene Christian is 3-0.", ''), 'TCU': ('', ''),
  'total': "Our efficiency model total is 130.8."},
 '2026-11-15_LT-MISS': {'LT': ("Our efficiency model has Ole Miss by 14.8 with a 134.1 total. No. 21 Ole Miss allows 43.3 points per game; Louisiana Tech is 4-0.", ''), 'MISS': ('', ''),
  'total': "Our efficiency model total is 134.1."},
 '2026-11-15_SEMO-ILL': {'SEMO': ("Our efficiency model has Illinois by 32.3 with a 135.3 total. Southeast Missouri State is 0-4 with every loss by 23 or more; No. 22 Illinois allows 39.0 points per game.", ''), 'ILL': ('', ''),
  'total': "Our efficiency model total is 135.3."},
}
NOLINE = "No pick (no line yet): no book had posted a line for this game at the 6:38 AM read. The 10:35 AM task or a rerun picks it up."
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
    op = HG/f'{gid}.json'; old = json.load(open(op)) if op.exists() else {}; old = old.get('data', old)
    NL = not (d.get('lines') or {}).get('spread')
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
            an = ((SM[A][0] + (' Other side: ' + SM[H][0] if SM[H][0] else '')) if kind == 'side' else SM['total'])
            if NL: none = NOLINE
            d['picks'][kind] = {'none': none, 'analysis': an}
    if NL or not d.get('lines'): d['lines'] = {}
    d['lines']['book'] = 'The Odds API median of books'
    d['lines']['openers'] = d['lines'].get('openers', '').replace('DraftKings', 'The Odds API open')
    d['moves'] = [m.replace('(DraftKings)', '(The Odds API median of books)') for m in d.get('moves', [])]
    ml = d['lines'].get('moneyline') or {}
    if any(abs(int(str(v).replace('+', ''))) > 5000 for v in ml.values() if v): d['lines'].pop('moneyline')
    d['notes'] = [n for n in d['notes'] if not n.startswith('Signal score') and 'texas222' not in n]
    d['notes'].append("Action Network had not posted today's women's games at the 6:45 AM check (no openers or splits), and its sharp report does not cover women's college games.")
    d['notes'].append('Injuries and lineups: ESPN lists no NCAAW injuries for either team; no starter changes were found in the data feed.')
    d['model']['adjustments'] = []; d['model']['adjustments_note'] = 'No absences reported for either team; no adjustment applied.'
    if NL:
        d['lines'] = {'book': 'none posted', 'note': 'No line at the 6:38 AM read'}; lh = list(old.get('line_history') or [])
    else:
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
