"""Nov 11 post step for NCAAW hub docs: conflict reasons on would-be picks, market on every reason, summary {for, against},
no-pick market analysis, lineups/units/adjustments from ESPN box scores, line_source. Reads ../hub_out, writes ../post2."""
import json, pathlib, statistics
W = pathlib.Path(__file__).parent.parent; O = W/'post2'; O.mkdir(exist_ok=True)
P = json.load(open(W/'hub_out'/'picks.json')); G = json.load(open(W/'hub_out'/'games.json'))
META = {r['key']: r for r in json.load(open(W.parent/'hub'/'meta'/'ncaaw.json'))['rules']}
RN = {'SPREAD_MOVE': 'Line move spread', 'EFF_SPREAD': 'Efficiency spread', 'MODEL_EDGE': 'Model spread', 'UNDER_DROP': 'Falling total under',
      'EFF_OVER': 'Efficiency over', 'OVER': 'Signal over', 'EARLY_UNDER_OPEN': 'Early under vs open', 'EARLY_OVER_OPEN': 'Early over vs open',
      'NEUTRAL_UNDER': 'Neutral site under', 'DOG_ML': 'Underdog moneyline', 'FAV_ML': 'Favorite moneyline'}
SUM = {
 '2026-11-11_NCCU-UNC': {
  'UNC': ("Our margin model projects North Carolina 91, NC Central 43, a 48.3 point margin against a 46.5 point spread, and DraftKings has moved the line from 43.5 to 46.5. North Carolina plays its first home game after neutral site losses to Oklahoma (91-79) and No. 1 South Carolina (84-39). NC Central lost its two Division I road games by 46 at Virginia Tech and 34 at UNC Wilmington, scoring 43.5 points per game in them. No absences are reported for either team.",
          "The efficiency model makes it only North Carolina by 34.1, more than 12 points short of the spread. North Carolina has scored 79 and 39 in its two games and has not won yet, so a rout of this size is untested. NC Central guard Victoria Morris averages 16 points and 7.8 rebounds, and NC Central is 2-2 overall."),
  'total': ("The total slipped from 137.5 to 136.5 and our model total is 133.8. North Carolina's games totaled 170 and 123, and NC Central's Division I games totaled 124 and 130. A lopsided game tends to slow late, which points a little under the number.",)},
 '2026-11-11_UALB-MISS': {
  'MISS': ("Our margin model projects Ole Miss 81, UAlbany 49, a 32.4 point margin against a 30.5 point spread, and the line has moved a point toward Ole Miss since it opened at 29.5. Ole Miss won its two home games by 42 over Alcorn State and 21 over North Alabama, allowing 44.5 points per game, behind Jaida Civil (16 points) and Jada Richard (15.5). UAlbany is 3-0, but its wins came by 4, 1 and 20 against Northeastern, Manhattan and Mount St. Mary's. No absences are reported.",
           "The efficiency model has Ole Miss by only 19.4, 11 points short of the spread. UAlbany is unbeaten and rebounds well (Madison Roman 11.3 per game, Alexia Bujold 16.3 points and 6 rebounds), and Ole Miss won by only 21 against North Alabama. A 30.5 point spread leaves little room if Ole Miss empties its bench."),
  'total': ("The total has not moved from 128.5 and our model total is 129.9. Ole Miss games have totaled 118 and 123 and UAlbany's 126, 123 and 134, so both teams have played to this number.",)},
 '2026-11-11_WKU-VAN': {
  'WKU': ("Our efficiency model projects Vanderbilt 85, Western Kentucky 52, a 32.5 point margin, 14 points under the 46.5 point spread. Western Kentucky is 2-0 and held Chattanooga to 50 in a 61-50 win, while Vanderbilt's three wins came against Lipscomb, Queens and Morehead State. Jamila Ray scores 19.5 points per game off the bench and Josie Gilvin adds 10.5 points and 8.5 rebounds.",
          "Vanderbilt has won all three games by 52 or more while scoring 100 or more each time, with Mikayla Blakes averaging 25.3 points and Aubrey Galvan 9 assists. The line has climbed from 39.5 to 46.5 at DraftKings, against this side, and the margin model makes it Vanderbilt by 47.3."),
  'VAN': ("Vanderbilt has won all three games by 52 or more, scoring 104.7 points per game, and the line has moved from 39.5 to 46.5. Our margin model projects Vanderbilt by 47.3. Mikayla Blakes (25.3 points) and Mia Woolfolk (17) lead a deep rotation.",
          "Our efficiency model has Vanderbilt by only 32.5, and Western Kentucky is unbeaten after holding Chattanooga to 50."),
  'total': ("The total rose from 139.5 to 140.5 and our model total is 137.0. Vanderbilt's games have totaled 165, 142 and 152, mostly from its own scoring, while Western Kentucky's Division I game totaled 111. The total depends on how long Vanderbilt keeps its starters in.",)},
 '2026-11-11_SDST-TEX': {
  'TEX': ("Our margin model projects Texas 84, South Dakota State 51, a 32.9 point margin against a 27.5 point spread, and the line has moved 7 points toward Texas since a 20.5 opener at DraftKings. Texas beat FDU by 20 and Northern Colorado by 62 at home, with Madison Booker averaging 27 points and 5.5 assists and Breya Cunningham 15.5 points and 9.5 rebounds. South Dakota State lost at home to Creighton 73-71 before beating Northern Iowa by 22. No absences are reported.",
          "The efficiency model makes it only Texas by 19.2, more than 8 points short of the spread. South Dakota State is a perennial Summit League power and lost 70-51 at home to Texas last December, a 19 point margin. Brooklyn Meyer (15 points, 7 rebounds) and Emilee Fox (11 points, 5.5 assists) give the Jackrabbits scoring inside and out that can keep it inside the number."),
  'SDST': ("Our efficiency model has Texas by 19.2, well short of 27.5, and South Dakota State lost by only 19 when these teams met last December. The Jackrabbits have experienced guards and Brooklyn Meyer inside.",
           "Texas has moved from 20.5 to 27.5 and our margin model projects Texas by 32.9; Madison Booker averages 27 points."),
  'total': ("The total has held at 137.5 and our model total is 135.1. Texas games totaled 150 and 120, South Dakota State's 144 and 130. Texas held Northern Colorado to 29, and its defense sets the pace here.",)},
 '2026-11-11_EVAN-UK': {
  'EVAN': ("Our efficiency model projects Kentucky 89, Evansville 52, a 37.4 point margin, 13 points under the 50.5 point spread, and the margin model also has Kentucky by only 43.2. The line has jumped 9 points from a 41.5 opener. Evansville lost by 25 at DePaul and by 13 at Lindenwood, so it has not lost by anything close to 50.",
           "Kentucky has won by 43, 51 and 15 (the 15 against NC State), with Ajsa Sivka at 18.3 points and Clara Strack at 17.3 points, 9 rebounds and 4 blocks. Evansville is 0-2, scores 57 points per game and turns the ball over often (Avery Kelley 5.5 per game), the weakest offense Kentucky has faced."),
  'UK': ("Kentucky has won by 43 and 51 at home and beat NC State by 15, and the line has moved from 41.5 to 50.5. Ajsa Sivka and Clara Strack combine for 35.6 points per game and Strack blocks 4 shots a game.",
         "Both of our models project Kentucky well short of 50.5 (efficiency 37.4, margin 43.2), and Evansville has lost its two games by 25 and 13."),
  'total': ("The total dipped from 138.5 to 137.5 while our model total is 141.5. Kentucky's games totaled 127, 107 and 171, Evansville's 155 and 111. Kentucky's pace and Evansville's turnovers point to the Over, but two of Kentucky's three games stayed far under.",),
  'total_over': ("Our efficiency model total is 141.5 against 137.5. Kentucky scores 85.7 points per game and Evansville turns the ball over often, which feeds Kentucky's transition game.", "Two of Kentucky's three games stayed under 128, and Kentucky allows 49.3 points per game."),
  'total_under': ("The total fell a point from 138.5, and Kentucky allows 49.3 points per game; two of its three games totaled 127 and 107.", "Our model total is 141.5, four points over the number, and Kentucky averages 85.7 points.")}}
NONE_TOTAL = {
 '2026-11-11_NCCU-UNC': "The only total rule that fits is Falling total under, and it is turned off, so the Under is logged as a would-be pick and the card has no total.",
 '2026-11-11_UALB-MISS': "No total rule fits: the total has not moved since it opened and our model total sits right on the posted number.",
 '2026-11-11_WKU-VAN': "No total rule fits: the total rose only a point and our model total is close to the posted number.",
 '2026-11-11_SDST-TEX': "No total rule fits: the total has not moved since it opened and our model total is close to the posted number.",
 '2026-11-11_EVAN-UK': "Two total rules fit on opposite sides: Efficiency over, whose Solid tier is turned off, and Falling total under, which is turned off. Both are logged as would-be picks and the card has no total."}

def mkt(item, market):
    lab = (item.get('label', '') + ' ' + item.get('detail', '')).lower()
    if any(k in lab for k in ('injur', 'home court', 'rest', 'form', 'backtest', 'texas222', 'neutral', 'travel')): m = 'Game context'
    else: m = market
    item['market'] = m; return item

# lineups from ESPN box scores (this season, Division I games)
PL = {}
for l in open(W.parent/'pull'/'players.txt'):
    f = l.strip().split('|')
    if len(f) < 13: continue
    t, n, pos = f[0], f[1], f[2]; g, gs, ls, mn, pts, reb, ast, stl, blk, tov = map(int, f[3:13])
    PL.setdefault(t, []).append(dict(n=n, pos=pos, g=g, gs=gs, ls=ls, mn=mn, pts=pts, reb=reb, ast=ast, stl=stl, blk=blk, tov=tov))
allp = [p for v in PL.values() for p in v]
def per40(p, k): return 40 * p[k] / max(p['mn'], 1)
def pct(v, arr): return round(100 * sum(1 for x in arr if x <= v) / len(arr))
DIM = {k: sorted(per40(p, k) for p in allp) for k in ('pts', 'reb', 'ast', 'stl', 'blk', 'tov')}
def prod(p): return (p['pts'] + p['reb'] + p['ast'] + p['stl'] + p['blk'] - p['tov']) / max(p['mn'], 1)
PRODS = sorted(prod(p) for p in allp)
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
    d['model']['adjustments_note'] = 'No absences reported for either team (ESPN game summaries list no injuries); no adjustment applied.'
    d['line_history'] = [{'as_of': '2026-11-11', 'spread': d['lines']['spread']['home'].split()[0] + ' ' + H, 'total': d['lines']['total']['over'].split()[0], 'ml_away': (d['lines'].get('moneyline') or {}).get('away'), 'ml_home': (d['lines'].get('moneyline') or {}).get('home'), 'source': 'DraftKings'}]
    d['notes'] = [n for n in d['notes'] if not n.startswith('Signal score')]
    d['notes'].append('No ESPN, CBS Sports, Covers or Action Network preview found for this game; the write-up uses the run data.')
    out_g.append({'id': gid, 'data': d})
for p in P:
    d = p['data']; gid = f"{d['date']}_{d['away']}-{d['home']}"; S = SUM[gid]
    mk = 'Total' if d['market'] == 'Total' else 'Spread'
    d['reasons'] = [mkt(x, mk) for x in d['reasons']]; d['against'] = [mkt(x, mk) for x in d['against']]
    d['line_source'] = 'DraftKings (texas222 not posted)'
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
print(json.dumps(out_g[4]['data']['lineups']['home'][:2])); print(out_g[4]['data']['units'])
