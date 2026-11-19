"""Nov 12 post step (copied from post_nov11.py; summaries for Nov 12) for NCAAW hub docs: conflict reasons on would-be picks, market on every reason, summary {for, against},
no-pick market analysis, lineups/units/adjustments from ESPN box scores, line_source. Reads ../hub_out, writes ../post2."""
import json, pathlib, statistics, os as _o2
W = pathlib.Path(__file__).parent.parent; O = W/'post2'; O.mkdir(exist_ok=True)
P = json.load(open(W/'hub_out'/'picks.json')); G = json.load(open(W/'hub_out'/'games.json'))
META = {r['key']: r for r in json.load(open(_o2.environ.get('HUB_META')))['rules']}
RN = {'SPREAD_MOVE': 'Line move spread', 'EFF_SPREAD': 'Efficiency spread', 'MODEL_EDGE': 'Model spread', 'UNDER_DROP': 'Falling total under',
      'EFF_OVER': 'Efficiency over', 'OVER': 'Signal over', 'EARLY_UNDER_OPEN': 'Early under vs open', 'EARLY_OVER_OPEN': 'Early over vs open',
      'NEUTRAL_UNDER': 'Neutral site under', 'DOG_ML': 'Underdog moneyline', 'FAV_ML': 'Favorite moneyline'}
SUM = {
 '2026-11-12_LOU-BALL': {
  'BALL': ("Our margin model projects Louisville by 18.1, 4.4 points short of the 22.5 point spread, and Ball State is at home with five days of rest against Louisville's two. Ball State beat Arkansas State 84-74 at home before losing 78-71 to High Point, and its two games have totaled 158 and 149.",
           "Louisville is 4-0 and has won by 72, 52, 23 and 36, holding Lindenwood to 35 and Stetson to 35. The line opened at 22.5 at DraftKings and has not moved, and the efficiency model has Louisville by 20.0, close to the number."),
  'total': ("The total opened 148.5 at DraftKings and is now 146.5, and our efficiency model total is 146.0. Louisville's games have totaled 166, 122, 137 and 106; Ball State's 158 and 149.",),
  'total_under': ("The total has dropped two points since it opened at 148.5, and Louisville allows 44 points per game across four wins. Two of Louisville's last three games stayed under 140.", "Our efficiency model total of 146.0 is right on the posted number, and Ball State's two games both went over 148.")},
 '2026-11-12_OKST-TLSA': {
  'TLSA': ("Our efficiency model projects Oklahoma State by 17.3, 7.2 points short of the 24.5 point spread, and Tulsa is at home with nine days of rest against Oklahoma State's three. Tulsa has played one Division I game, a 63-57 home loss to Incarnate Word.",
           "Oklahoma State is 3-0 and has won by 42, 54 and 38, and the line has moved from 21.5 to 24.5 toward the Cowgirls. 67% of the spread tickets at Action Network are on Oklahoma State."),
  'total': ("The total has held at 139.5 and our efficiency model total is 137.0. Oklahoma State's games have totaled 120, 130 and 150; Tulsa's Division I game totaled 120.",)},
 '2026-11-12_CONN-OSU': {
  'CONN': ("Our margin model projects UConn by 16.8 against a 9.5 point spread, and the line has moved from 7.5 to 9.5 toward UConn at DraftKings. UConn beat Iowa 91-79 and Cornell 100-35, and 72% of the spread tickets are on UConn.",
           "Ohio State is 3-0 at home with wins by 47, 67 and 34, and the efficiency model has UConn by only 7.8, under the spread. UConn lost 77-66 at Michigan in its only true road game."),
  'total': ("The total moved from 145.5 to 146.5 and our efficiency model total is 143.6. UConn's games have totaled 135, 143 and 170; Ohio State's 115, 139 and 148.",)},
 '2026-11-12_ARIZ-UCLA': {
  'UCLA': ("The line has moved from 26.5 to 27.5 toward UCLA, our margin model projects UCLA by 46.0 and the efficiency model by 32.9, both past the spread. UCLA is 2-0, beating Lehigh by 20 and UC Irvine by 36, and has seven days of rest against Arizona's four.",
           "Arizona is 2-0, with a 15 point road win at Stanford and a 13 point win over Iona, and a 27.5 point spread is a lot to cover against a Power Four team. UCLA's two wins came by 20 and 36."),
  'total': ("The total has held at 140.5 and our efficiency model total is 139.2. UCLA's games have totaled 126 and 120; Arizona's 153 and 135.",)},
 '2026-11-12_SC-CLEM': {
  'CLEM': ("Our efficiency model projects South Carolina by 19.2 and the margin model by 26.0, both short of the 30 point spread, and Clemson is at home and 3-0. Clemson has won by 21, 19 and 28 and allowed 49.3 points per game.",
           "The line has jumped from 14.5 to 30 since it opened, and 80% of the spread tickets are on South Carolina. South Carolina is No. 1 and beat North Carolina 84-39."),
  'total': ("The total has held at 132.5 while our efficiency model total is 130.6. South Carolina's games have totaled 194 and 123; Clemson's 115, 133 and 116.",)},
 '2026-11-12_DUKE-NORF': {
  'DUKE': ("The line has moved from 31.5 at the DraftKings open to 38.5, a 7 point move toward Duke, and Duke is 2-0 with wins by 16 over Green Bay and 22 at Florida Atlantic. Norfolk State has played one Division I game, a 72-56 home loss to Penn.",
           "Our margin model has Duke by 34.0 and the efficiency model by 25.8, both short of 38.5. Duke has not won a game by more than 22 this season, and Norfolk State is at home."),
  'NORF': ("Our efficiency model projects Duke by 25.8 and the margin model by 34.0, both well short of the 38.5 point spread, and Norfolk State is at home. Duke's two wins came by 16 and 22.",
           "The line has moved 7 points toward Duke since the open, and Norfolk State lost by 16 at home to Penn in its only Division I game."),
  'total': ("The total opened 132.5 and has held there while our efficiency model total is 125.0. Duke's games have totaled 136 and 134; Norfolk State's 128.",),
  'total_under': ("Our efficiency model total is 125.0, 7.5 points under the 132.5 opener. Duke allowed 60 and 56 points in its two wins and Norfolk State scored 56 against Penn.", "Duke's two games totaled 136 and 134, both over this number.")},
 '2026-11-12_SELA-TCU': {
  'SELA': ("Our efficiency model projects TCU by 40.0, 15.5 points short of the 55.5 point spread, and Southeastern Louisiana has ten days of rest against TCU's two.",
           "TCU is 4-0 with wins by 56, 55, 47 and 25, and Southeastern Louisiana lost 129-35 at LSU, a 94 point margin."),
  'total': ("The total has held at 136.5 and our efficiency model total is 135.5. TCU's games have totaled 142, 137, 131 and 131.",)},
 '2026-11-12_MICH-COLU': {
  'COLU': ("Our efficiency model projects Michigan by 11.8, 6.7 points short of the 18.5 point spread, and Columbia is at home and 3-0, beating Davidson by 6, Rhode Island by 14 and Belmont by 20 on the road. Columbia has a veteran Ivy League core that has won the league the last two seasons.",
           "The line has moved from 15.5 to 18.5 toward Michigan, and 64% of the spread tickets are on Michigan. Michigan is No. 2, beat UConn 77-66 and Wright State 109-52."),
  'total': ("The total moved from 142.5 at DraftKings to 141.5 and our efficiency model total is 138.4. Michigan's games have totaled 143 and 161; Columbia's 136, 138 and 148.",)},
 '2026-11-12_UNI-IOWA': {
  'UNI': ("Our efficiency model projects Iowa by 26.8, 5.7 points short of the 32.5 point spread, and Northern Iowa has six days of rest against Iowa's four. Iowa's three games were decided by 28, 41 and 12.",
           "The line has moved from 30.5 to 32.5 toward Iowa at DraftKings, Iowa is at home, and Northern Iowa lost 76-54 at South Dakota State."),
  'total': ("The total has held at 135.5 and our efficiency model total is 132.6. Iowa's games have totaled 118, 119 and 170; Northern Iowa's 126 and 130.",)},
 '2026-11-12_CSUB-WASH': {
  'CSUB': ("Our efficiency model projects Washington by 28.7, 14.8 points short of the 43.5 point spread. Washington's two wins came by 16 over UC San Diego and 21 over Pacific.",
           "The line has moved from 42.5 to 43.5 toward Washington, Washington is at home, and Cal State Bakersfield has no Division I game this season to judge."),
  'WASH': ("The line has moved from 42.5 to 43.5 toward Washington, and Washington is 2-0 at home.",
           "Our efficiency model has Washington by 28.7, nearly 15 points short of the spread, and Washington's wins came by 16 and 21."),
  'total': ("The total has held at 131.5 and our efficiency model total is 130.7. Washington's games have totaled 142 and 129.",)},
}
NONE_TOTAL = {
 '2026-11-12_LOU-BALL': "The only total rule that fits is Falling total under, and it is turned off, so the Under is logged as a would-be pick and the card has no total.",
 '2026-11-12_OKST-TLSA': "No total rule fits: the total has not moved since it opened and our model total is close to the posted number.",
 '2026-11-12_CONN-OSU': "No total rule fits: the total rose only a point and our model total is within three points of the posted number.",
 '2026-11-12_ARIZ-UCLA': "No total rule fits: the total has not moved since it opened and our model total is close to the posted number.",
 '2026-11-12_SC-CLEM': "No total rule fits: the total has not moved since it opened and our model total is close to the posted number.",
 '2026-11-12_DUKE-NORF': "The only total rule that fits is Early under vs open, and it is turned off at this tier, so the Under is logged as a would-be pick and the card has no total.",
 '2026-11-12_SELA-TCU': "No total rule fits: the total has not moved since it opened and our model total is close to the posted number.",
 '2026-11-12_MICH-COLU': "No total rule fits: the total moved only a point and our model total is close to the posted number.",
 '2026-11-12_UNI-IOWA': "No total rule fits: the total has not moved since it opened and our model total is within three points of the posted number.",
 '2026-11-12_CSUB-WASH': "No total rule fits: the total has not moved since it opened and our model total is close to the posted number.",
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
    d['line_history'] = [{'as_of': '2026-11-12', 'spread': d['lines']['spread']['home'].split()[0] + ' ' + H, 'total': d['lines']['total']['over'].split()[0], 'ml_away': (d['lines'].get('moneyline') or {}).get('away'), 'ml_home': (d['lines'].get('moneyline') or {}).get('home'), 'source': 'The Odds API median of books'}]
    d['lines']['book'] = 'The Odds API median of books'
    d['notes'] = [n for n in d['notes'] if not n.startswith('Signal score')]
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

