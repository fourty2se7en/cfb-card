"""Nov 15 run (6:38 AM read). Based on the Nov 14 second run (about 7:50 AM Phoenix) post step: lines now posted for all 5 AP Top 25 games. Summaries, conflict text, rule keys and labels,
no-pick text, line history (keeps the early run entry), Odds API wording. Reads ../hub_out and the hub game docs (env HUB_GAMES), writes ../post2r2."""
import json, pathlib, os
W = pathlib.Path(__file__).parent.parent; O = W/'post16'; O.mkdir(exist_ok=True)
P = json.load(open(W/'hub_out'/'picks.json')); G = json.load(open(W/'hub_out'/'games.json'))
HG = pathlib.Path(os.environ['HUB_GAMES'])
META = {r['key']: r for r in json.load(open(os.environ['HUB_META']))['rules']}
LAB = lambda k: META[k].get('label', k)
FAM = {'SPREAD_MOVE_1': 'SPREAD_MOVE', 'SPREAD_MOVE_05': 'SPREAD_MOVE', 'OVER_2': 'OVER', 'OVER_05': 'OVER'}
NOW = '2026-11-16 13:20'
S = {
 '2026-11-16_MICH-CMU': {
  'CMU': ("Our margin model has Michigan by 30.8 and the efficiency model by 32.9, both well short of the 43.5 point spread. Central Michigan is home at McGuirk Arena on 8 days of rest to Michigan's 4, and Michigan's only road game so far was a 23 point win at Columbia.",
          "Central Michigan is 0-3, scores 45.3 points per game (359th of 363) and shoots 26.1% from the field (362nd), with losses by 67 at Ohio State and 32 at home to Butler. No. 2 Michigan beat UConn by 11 and Wright State by 57 and shoots 51.0% (10th), and the spread has moved 5 points toward Michigan since the 38.5 open."),
  'MICH': ("The spread has moved 5 points toward Michigan, from 38.5 at the open to 43.5. Central Michigan is 0-3, scores 45.3 points per game (359th of 363) and lost by 67 at Ohio State; No. 2 Michigan scores 89.0 and beat Wright State by 57.",
           "Our margin model has Michigan by 30.8 and the efficiency model by 32.9, both well short of 43.5, and Michigan's only road game was a 23 point win at Columbia."),
  'total_over': ("The total has risen 2 points since the open, from 142.5 to 144.5. Michigan scores 89.0 points per game (18th of 363) and its games have totaled 143, 161 and 139, and Central Michigan allows 79.7 (337th).",
                 "Our efficiency model total is 138.8, 5.7 points under 144.5. Central Michigan scores 45.3 points per game and its games have totaled 120, 139 and 116."),
  'total': "The total is 144.5 after opening at 142.5; our efficiency model total is 138.8."},
 '2026-11-16_TROY-LSU': {
  'LSU': ("The spread has moved 6 points toward LSU, from 46.5 at the open to 52.5. No. 9 LSU is 4-0 at home, winning by 94, 109, 57 and 64, leads the country in scoring (115.2) and points allowed (34.2), and Troy lost its last two road games by 22 and 26.",
          "Our efficiency model has LSU by 41.2 and the margin model by 39.0, both more than 11 points short of 52.5, and LSU's last win came by 64."),
  'TROY': ("Our efficiency model has LSU by 41.2 and the margin model by 39.0, both more than 11 points short of the 52.5 point spread. Troy rebounds well (45.8 per game, 33rd of 363) and scored 89 in its opener at Kent State.",
           "The spread has moved 6 points toward LSU since the open, LSU has won every home game by 57 or more and leads the country in scoring and points allowed, and Troy lost at Mississippi State by 22 and at Belmont by 26."),
  'total_under': ("Our efficiency model total is 154.3, 11.2 points under the 165.5 opening total. LSU allows 34.2 points per game (1st of 363) and its last two games totaled 143 and 138; Troy shoots 37.3% and its last two games totaled 136 and 118.",
                  "LSU scores 115.2 points per game and scored 129 and 131 in its first two games, which totaled 164 and 153."),
  'total_over': ("The total has risen 1 point since the open, from 165.5 to 166.5. LSU scores 115.2 points per game (1st of 363) and its first two games totaled 164 and 153.",
                 "Our efficiency model total is 154.3, 12.2 points under 166.5, and LSU allows 34.2 points per game, fewest in the country."),
  'total': "The total is 166.5 after opening at 165.5; our efficiency model total is 154.3."},
}
NOLINE = "No pick (no line yet)."
NOFIT = {'side': "No spread rule fits: the line has not moved and neither model gap reaches a rule threshold.",
         'total': "No total rule fits: the total has not moved and our model total is close to the posted number."}

def mkt(item, market):
    lab = (item.get('label', '') + ' ' + item.get('detail', '')).lower()
    item['market'] = 'Game context' if any(k in lab for k in ('injur', 'home court', 'rest', 'form', 'backtest', 'neutral', 'travel')) else market
    return item

PD = {p['id']: p for p in P}
import gzip
TS = json.load(gzip.open('/home/claude/cfb-card/season/data/espn/ncaaw/2026-11-16/team_stats.json.gz'))
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
    d['notes'].append("No Action Network read this run (cloud run, no browser); no splits or sharp report for these games. Lines: The Odds API median of books, read 1:20 PM Phoenix.")
    d['notes'].append('Injuries and lineups: ESPN lists no NCAAW injuries for either team and a web search found no new injury news; no starter changes were found in the data feed.')
    d['model']['adjustments'] = []; d['model']['adjustments_note'] = 'No absences reported for either team; no adjustment applied.'
    if NL:
        d['lines'] = {'book': 'none posted', 'note': 'No line at the 6:38 AM read'}; lh = list(old.get('line_history') or [])
    else:
        sp = d['lines']['spread']; tot = d['lines']['total']
        lh = list(old.get('line_history') or [])
        lh.append(dict(as_of=NOW, spread=f"{sp['home'].split()[0]} {H}", total=tot['over'].split()[0], ml_away=(d['lines'].get('moneyline') or {}).get('away'),
                       ml_home=(d['lines'].get('moneyline') or {}).get('home'), source='The Odds API median of books'))
    d['line_history'] = lh
    for sd in ('away', 'home'):
        ts = TS['teams'].get(TS['index'].get(d[sd]['code']))
        if ts: d[sd]['stats'] = ts['stats']
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
