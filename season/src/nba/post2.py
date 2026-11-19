"""Season Cards Nov 11 additions (run after post.py). Usage:
python3 post2.py YYYY-MM-DD <post.py out dir> <hub meta nba json> <lineups txt> <out dir>
1. Tier gate: a game pick whose rule tier is off in hub meta (tiers[t].on false) becomes a would-be pick (shadow, conflict).
2. Every rule fit gets its own doc id <date>_<AWAY-HOME>_<side|total>_<RULE_KEY> (card picks keep _side / _total).
3. line_source, market on every reason and against item, summary {for, against} on pick docs and game doc picks,
   no pick markets {none, analysis}; tier_record from hub meta.
4. Game docs: lineups (rotation from NBA.com game logs, ratings 0 to 100 league percentile of a per 36 composite),
   units, model.adjustments (INJ_ADJ). Prop docs and game doc PROPs: matchup and lineup check."""
import json, pathlib, sys, re
D = pathlib.Path(__file__).parent; sys.path.insert(0, str(D))
DATE, SRC, METAF, LUF, OUT = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3], sys.argv[4], pathlib.Path(sys.argv[5])
OUT.mkdir(parents=True, exist_ok=True)
for f in OUT.glob('*.json'): f.unlink()
import model, signals
from teams import FULL
META = json.load(open(METAF)); META = META.get('data', META)
TIERS = {r['key']: (r.get('tiers') or {}) for r in META['rules']}
META_ON = {r['key']: r.get('on') for r in META['rules']}
games, LG, P, PR = model.build()
G = {f"{g['a']}-{g['h']}": g for g in games}
TR = json.loads((D/'trends.json').read_text())
TEAMS = {}
for ln in (D/'teams_raw.txt').read_text().strip().splitlines()[1:]:
    f = [x.strip() for x in ln.split('|')]; n = f[2].split(); TEAMS[f[0]] = dict(rec=n[1], net=float(n[4]), o=float(n[2]), d=float(n[3]), rest=int(f[4]), last=f[3])
INJ = model.parse_injuries()
def nick(t): return FULL[t].split()[-1] if t != 'POR' else 'Trail Blazers'
def city(t): return ' '.join(FULL[t].split()[:-1]) if t != 'POR' else 'Portland'
SL = {}  # signal labels -> market
def mkt(r, default):
    lab, det = r.get('label', ''), r.get('detail', '')
    if '(spread)' in det or 'spread' in det.lower() and lab in ('Reverse line movement', 'Line move', 'Money % above ticket %', 'Fade the public'): return 'Spread'
    if '(moneyline)' in det or 'moneyline tickets' in det: return 'Moneyline'
    if default == 'Total': return 'Total'
    if lab.startswith('Action Network') or lab in ('Reverse line movement', 'Line move', 'Money % above ticket %', 'Fade the public'): return default
    return 'Game context'
# ------------------------------------------------------------- lineups
LU = {}
OUTP = {t: [x.split(' Out')[0].strip() for x in v if ' Out (' in x] for t, v in INJ.items()}
QP = {t: [x.split(' Day-To-Day')[0].strip() for x in v if 'Day-To-Day' in x] for t, v in INJ.items()}
STR = dict(S='scoring', R='rebounding', P='playmaking', T='3-point shooting', D='steals and blocks')
WK = dict(s='low scoring volume', o='turnovers', f='low field goal %')
def nz(s): return re.sub(r"[.'’]", '', s).replace('ć', 'c').replace('č', 'c').lower()
for ln in pathlib.Path(LUF).read_text().strip().splitlines():
    t, rest = ln.split('#'); rows = []
    for x in rest.split(';'):
        if not x: continue
        n, m, rt, s, w, o = x.split('~')
        out = o == 'X' or any(nz(n) == nz(p) for p in OUTP.get(t, []))
        q = any(nz(n) == nz(p) for p in QP.get(t, []))
        rows.append(dict(player=n, mpg=int(m), rating=int(rt) if rt else None, strengths=[STR[c] for c in s], weaknesses=[WK[c] for c in w],
                         status='Out' if out else ('Questionable' if q else 'Available')))
    avail = [r for r in rows if r['status'] != 'Out']
    starters = sorted(avail, key=lambda r: -r['mpg'])[:5]
    L = []
    for r in rows:
        st = r in starters
        role = 'Starter' if st else ('Out' if r['status'] == 'Out' else 'Rotation')
        e = dict(player=r['player'], pos=None, role=role, starter=st, status=r['status'], rating=r['rating'], strengths=r['strengths'], weaknesses=r['weaknesses'],
                 mpg_last5=r['mpg'], source='NBA.com game logs (last 5 team games), ESPN injury report; starters estimated by minutes')
        if r['status'] == 'Out':
            bk = next((b for b in sorted(avail, key=lambda z: -z['mpg']) if b not in starters), None)
            if bk: e['backup'] = bk['player']; e['backup_rating'] = bk['rating']
        L.append(e)
    LU[t] = L
def units_of(t):
    L = LU.get(t, []); st = [x for x in L if x['starter'] and x['rating'] is not None]; bn = [x for x in L if not x['starter'] and x['status'] != 'Out' and x['rating'] is not None]
    av = lambda a: round(sum(x['rating'] for x in a)/len(a)) if a else None
    def cnt(k): return sum(1 for x in L if x['status'] != 'Out' and k in x['strengths'])
    return {'Starting five': dict(rating=av(st), note=', '.join(x['player'] for x in st)),
            'Bench': dict(rating=av(bn), note=f"{len(bn)} rotation players"),
            'Shooting': dict(rating=None, note=f"{cnt('3-point shooting')} rotation player(s) in the top quarter for threes per 36"),
            'Rebounding': dict(rating=None, note=f"{cnt('rebounding')} rotation player(s) in the top quarter for rebounds per 36"),
            'Defense': dict(rating=None, note=f"{cnt('steals and blocks')} rotation player(s) in the top quarter for steals plus blocks per 36")}
# ------------------------------------------------------------- write-ups
def proj_line(g):
    a, h = g['a'], g['h']; mg = g['margin']; fav = h if mg > 0 else a
    sp = g['lh']['sp'][0]; tot = (g['la']['tot'] if g['la']['tot'][0] == 'O' else g['lh']['tot'])[1]
    mkt_fav = h if sp < 0 else a
    return (f"Our model projects {nick(a)} {g['ptsA']:.0f}, {nick(h)} {g['ptsH']:.0f} ({nick(fav)} by {abs(mg):.1f}, total {g['total']:.1f}) "
            f"against {nick(mkt_fav)} {-abs(sp):g} and a {tot:g} total.")
def team_line(t):
    T = TEAMS[t]; tr = TR.get(t, {})
    s = f"{city(t)} is {T['rec']} with a {T['net']:+.1f} net rating this season"
    if tr.get('last5'): s += f", {''.join(tr['last5']).count('W')}-{''.join(tr['last5']).count('L')} in its last five ({tr.get('streak')})"
    return s + '.'
def rest_line(t):
    T = TEAMS[t]
    if T['rest'] == 0: return f"{city(t)} is on the second night of a back-to-back ({T['last']})."
    return f"{city(t)} has {T['rest']} day{'s' if T['rest'] != 1 else ''} of rest."
def inj_line(t):
    if t in model.INJ_ADJ: v, note = model.INJ_ADJ[t]; return f"{city(t)} is without {re.sub(r' out.*$', '', note.split(' (')[0])} (worth about {v:g} point{'s' if v != 1 else ''} of margin in our numbers)."
    return ''
def side_summary(g, team, line=None):
    a, h = g['a'], g['h']; o = h if team == a else a
    tm = g['margin'] if team == h else -g['margin']
    sup = (tm + line > 0) if line is not None else (tm > 0)
    pl = proj_line(g)
    f = ' '.join(x for x in [pl if sup else '', team_line(team), inj_line(o), rest_line(o) if TEAMS[o]['rest'] == 0 else '', 'The line moved toward this side against the ticket count at both opening sources.' if line is not None else ''] if x)
    ag = ' '.join(x for x in [pl if not sup else '', team_line(o), inj_line(team), rest_line(team) if TEAMS[team]['rest'] == 0 else '',
                              f"The market makes {nick(o)} the stronger side at {g['lh']['ml'] if o == h else g['la']['ml']:+d}." if (g['lh']['ml'] if o == h else g['la']['ml']) < 0 else ''] if x)
    return dict(**{'for': f, 'against': ag})
def total_summary(g, side='U'):
    a, h = g['a'], g['h']; tot = (g['la']['tot'] if g['la']['tot'][0] == 'O' else g['lh']['tot'])[1]
    b2b = [city(t) for t in (a, h) if TEAMS[t]['rest'] == 0]
    outs = [inj_line(t) for t in (a, h) if t in model.INJ_ADJ]
    pace = f"Projected pace is {g['pace']:.1f} possessions (league about 100.3)."
    dfn = f"Defensive ratings this season: {city(a)} {TEAMS[a]['d']:.1f}, {city(h)} {TEAMS[h]['d']:.1f}."
    off = f"Offensive ratings this season: {city(a)} {TEAMS[a]['o']:.1f}, {city(h)} {TEAMS[h]['o']:.1f}."
    l5 = f"Last five game totals: {city(a)} {TR[a]['last5_totals']}, {city(h)} {TR[h]['last5_totals']}." if TR.get(a, {}).get('last5_totals') and TR.get(h, {}).get('last5_totals') else ''
    under = ' '.join(x for x in [proj_line(g), pace, dfn, (' and '.join(b2b) + (' is' if len(b2b) == 1 else ' are') + ' on a back-to-back.') if b2b else ''] + outs[:1] if x)
    over = ' '.join(x for x in [off, l5, f"Our total of {g['total']:.1f} is {'above' if g['total'] > tot else 'below'} the {tot:g} posted."] if x)
    return dict(**{'for': under, 'against': over}) if side == 'U' else dict(**{'for': over, 'against': under})
# ------------------------------------------------------------- props matchup
from render import MATCH
DR = sorted(TEAMS.items(), key=lambda kv: kv[1]['d'])
def drank(t):
    allr = {}
    for ln in (D/'season/ratings.txt').read_text().strip().splitlines():
        if ln.startswith('11/10/2026'):
            for x in ln.split('|')[1].split(';'):
                f = x.split(','); allr[f[0]] = float(f[3])
    order = sorted(allr, key=lambda k: allr[k]); return order.index(t) + 1 if t in order else None, allr.get(t)
def matchup(team, opp, stat, side, proj):
    idx = {'rebounds': 0, 'assists': 1, 'threes': 2}.get(stat)
    if idx is not None and opp in MATCH:
        fct = MATCH[opp][idx]; nm = {0: 'rebounds', 1: 'assists', 2: '3-pointers'}[idx]
        vs = f"{city(opp)} allow {fct*100:.0f}% of league average {nm} per 100 possessions (this season blended with last)"
        adj = round(0.5*(fct-1)*proj, 2); src = 'NBA.com opponent stats per 100 possessions (in the prop model at half weight)'
    else:
        rk, dr = drank(opp); fct = None
        vs = f"{city(opp)} defensive rating {dr} ({rk} of 30, 1 = best)" if rk else 'no opponent data'
        adj = 0.0 if rk is None else round((15.5 - rk)/14.5*-0.03*proj, 2); src = 'NBA.com team defensive rating this season (display only for points)'
        fct = 1 - (15.5 - rk)/14.5*0.03 if rk else 1
    eff = 'neutral' if abs(fct-1) < 0.03 else (('supports Over' if fct > 1 else 'supports Under'))
    if eff != 'neutral' and ((side.lower() == 'over') != (fct > 1)): eff = 'works against'
    return dict(opp=opp, vs=vs, effect=eff, adj=adj, source=src)
def on_lineup(team, player):
    for x in LU.get(team, []):
        if nz(x['player']) == nz(player) or nz(x['player']).split()[-1] == nz(player).split()[-1] and nz(x['player'])[0] == nz(player)[0]: return x
    return None
# ------------------------------------------------------------- go
W = json.loads((SRC/'writes.json').read_text()); out = []; summ = []
docs = {(e['collection'], e['doc_id']): (e, json.load(open(e['file_path']))) for e in W}
RULELAB = {k: v['label'] for k, v in signals.RULES.items()}
RULELAB['FAV_ML'] = 'Favorite moneyline'
def trec(rule, tier):
    t = TIERS.get(rule, {}).get(tier) or {}
    f = lambda s: (f"{s['w']}-{s['l']}" + (f"-{s['p']}" if s.get('p') else '') + f" {s['u']:+.2f}u") if s else None
    return dict(tier=tier, on=t.get('on'), real=f(t.get('real')), replay=f(t.get('season')), pending_on=t.get('pending_on'))
gamepicks = {}
for (coll, did), (e, x) in list(docs.items()):
    if coll != 'sports/nba/picks': continue
    key = f"{x['away']}-{x['home']}"; g = G[key]
    if x['market'] == 'Prop':
        opp = x['home'] if x['team'] == x['away'] else x['away']
        x['matchup'] = matchup(x['team'], opp, x['stat'], x['side'], x.get('line') or 0)
        lu = on_lineup(x['team'], x['player']); x['lineup'] = dict(on_lineup=bool(lu), role=lu['role'] if lu else None, status=lu['status'] if lu else None)
        for r in x.get('reasons', []) + x.get('against', []): r.setdefault('market', 'Game context')
        continue
    dflt = x['market']
    for r in x.get('reasons', []) + x.get('against', []): r['market'] = mkt(r, 'Total' if dflt == 'Total' else dflt)
    x['line_source'] = 'texas222'
    if x['market'] == 'Total':
        m = re.search(r'([\d.]+)', x['pick']); x['line'] = float(m.group(1)); x['summary'] = total_summary(g, 'U' if x['pick'].startswith('Under') else 'O')
    else:
        team = x['away'] if x['pick'].startswith(FULL[x['away']]) else x['home']; x['summary'] = side_summary(g, team, x.get('line') if x['market'] == 'Spread' else None)
    tier = x['tier']; x['tier_record'] = trec(x['rule'], tier)
    kind = 'total' if x['market'] == 'Total' else 'side'
    newid = did
    if not x.get('shadow'):
        ton = (TIERS.get(x['rule'], {}).get(tier) or {}).get('on')
        if ton is False:
            x['shadow'] = True; x['conflict'] = f"The {tier} tier of {RULELAB[x['rule']]} is turned off (its real picks are {x['tier_record']['real'] or 'red'}), so this fit is a would-be pick."
            x['note'] = 'Would-be pick: rule tier turned off; logged and graded, never a card pick.'
            newid = f"{DATE}_{key}_{kind}_{x['rule']}"
    else:
        if (TIERS.get(x['rule'], {}).get(tier) or {}).get('on') is False and META_ON.get(x['rule']):
            x['conflict'] = f"The {tier} tier of {RULELAB[x['rule']]} is turned off (its real picks are {x['tier_record']['real'] or 'red'}), so this fit is a would-be pick."
            x['note'] = 'Would-be pick: rule tier turned off; logged and graded, never a card pick.'
            if isinstance(x.get('rule_record'), dict): x['rule_record']['status'] = 'on, this tier off'
        else:
            x['conflict'] = x.get('conflict') or f"{RULELAB[x['rule']]} is switched off (its real picks are red), so this fit is a would-be pick."
        newid = f"{DATE}_{key}_{kind}_{x['rule']}"
    docs.pop((coll, did)); docs[(coll, newid)] = (dict(e, doc_id=newid), x)
    gamepicks.setdefault(key, []).append((newid, x))
    summ.append((newid, x['pick'], x['price'], tier, x['rule'], 'would-be' if x.get('shadow') else 'CARD'))
# opposing card picks check
for key, L in gamepicks.items():
    card = [(i, x) for i, x in L if not x.get('shadow')]
    if len(card) > 1: print('CHECK OPPOSING', key, [i for i, _ in card])
# game docs
for (coll, did), (e, g) in list(docs.items()):
    if coll != 'sports/nba/games' or not did.startswith(DATE): continue
    key = did.split('_')[1]; gm = G[key]; a, h = key.split('-')
    for m in ('side', 'total'):
        p = g['picks'].get(m) or {}
        cardp = [x for i, x in gamepicks.get(key, []) if not x.get('shadow') and ((x['market'] == 'Total') == (m == 'total'))]
        if p.get('doc_id') and not cardp:
            wb = next((x for i, x in gamepicks.get(key, []) if ((x['market'] == 'Total') == (m == 'total'))), None)
            reason = wb['conflict'] if wb else 'No rule fits.'
            g['picks'][m] = dict(none=f"No card pick. {wb['pick']} fits {RULELAB[wb['rule']]}, but {reason[0].lower() + reason[1:]}" if wb else 'No rule fits.',
                                 analysis=(total_summary(gm, 'U')['for'] if m == 'total' else proj_line(gm)), signal_score=p.get('signal_score'))
        elif p.get('doc_id'):
            p['summary'] = cardp[0]['summary']; p['line_source'] = 'texas222'
        else:
            wbs = [x for i, x in gamepicks.get(key, []) if ((x['market'] == 'Total') == (m == 'total'))]
            if wbs:
                p['none'] = 'No card pick. ' + ' '.join(f"{x['pick']} fits {RULELAB[x['rule']]}, but {x['conflict'][0].lower() + x['conflict'][1:]}" for x in wbs[:2])
            elif m == 'total':
                p['none'] = 'No total rule fits: the under rule needs the total to drop at both opening sources with 75% or more of tickets on the over, and no over rule is active.'
            else:
                p['none'] = 'No side rule fits: the favorite moneyline rule needs a favorite of -200 to -100 with the signals clearly on it, and the line move and underdog rules did not fire on an active rule.'
            p['analysis'] = (' '.join([proj_line(gm), team_line(a), team_line(h)] + [inj_line(t) for t in (a, h) if inj_line(t)]) if m == 'side'
                             else ' '.join([total_summary(gm, 'U')['for'], total_summary(gm, 'U')['against']]))
    for k in ('side', 'total', 'side_against', 'total_against'):
        for r in (g.get('reasons') or {}).get(k, []) or []:
            r['market'] = 'Total' if k.startswith('total') else (r.get('source') if r.get('source') in ('Spread', 'Moneyline') and r['label'].startswith(('Action Network', 'Reverse', 'Line', 'Money', 'Fade')) else 'Game context')
    g['lineups'] = dict(away=LU.get(a, []), home=LU.get(h, []))
    g['units'] = dict(away=units_of(a), home=units_of(h))
    g.setdefault('model', {})['adjustments'] = [dict(team=t, out=[re.sub(r'^and ', '', s).strip() for s in re.split(r', | and ', model.INJ_ADJ[t][1].split(' out')[0])],
                                                     effect=f"-{model.INJ_ADJ[t][0]:g} pts margin", reason=model.INJ_ADJ[t][1]) for t in (a, h) if t in model.INJ_ADJ]
    g['lines']['line_source'] = 'texas222'
    for pr in g.get('props', []):
        opp = h if pr['team'] == a else a
        pr['matchup'] = matchup(pr['team'], opp, pr['stat'], pr['side'], pr.get('proj') or pr.get('line') or 0)
        lu = on_lineup(pr['team'], pr['player']); pr['lineup'] = dict(on_lineup=bool(lu), role=lu['role'] if lu else None, status=lu['status'] if lu else None)
    # picks.*.doc_id renamed for would-be
    docs[(coll, did)] = (e, g)
writes = []
for (coll, did), (e, x) in docs.items():
    p = OUT/f"{coll.replace('/', '_')}__{did}.json"; p.write_text(json.dumps(x))
    ne = dict(op=e['op'], collection=coll, doc_id=did, file_path=str(p.resolve()))
    if e.get('if_version'): ne['if_version'] = e['if_version']
    writes.append(ne)
(OUT/'writes.json').write_text(json.dumps(writes, indent=0))
for s in summ: print(s)
print(len(writes), 'writes')
