"""Season Cards post step (folded into src Nov 8; on Nov 7 it lived in a session scratchpad as r2/post.py).
Run after hub_build.py. Usage: python3 post.py YYYY-MM-DD <hub_build out dir> <final out dir> '<logged-at text>' [existing.json]
1. Game picks: one tier scale (Trina, Nov 7): signal lead = reasons' points minus against points. Strong 4+, Solid 2 to 3, Lean 0 to 1 or behind.
   Writes tier, tier_basis and the card's old label as rule_tier, on the pick doc and on the game doc's picks.side / picks.total. Adds last5.
2. Props: season_log (every game this season in that stat, oldest to newest, from season_raw.txt) on each prop pick doc and game doc PROP.
3. Would-be picks: every candidate from an inactive game rule in shadow_raw.json becomes its own pick doc with shadow: true
   (never in the game doc picks). Doc id <date>_<AWAY-HOME>_side or _total.
4. existing.json (optional) = {doc_id: version} of docs already in the hub (a second run the same day): those are written with if_version."""
import json, pathlib, sys
D = pathlib.Path(__file__).parent
sys.path.insert(0, str(D))
DATE, SRC, OUT, LOGGED = sys.argv[1], pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3]), sys.argv[4]
EXIST = json.loads(pathlib.Path(sys.argv[5]).read_text()) if len(sys.argv) > 5 else {}
OUT.mkdir(parents=True, exist_ok=True)
for f in OUT.glob('*.json'): f.unlink()
W0 = json.loads((SRC/'writes.json').read_text()); TR = json.loads((D/'trends.json').read_text())
RS = json.loads((D/'rules_state.json').read_text()); SH = json.loads((D/'shadow_raw.json').read_text()); EXP = json.loads((D/'experts.json').read_text())
from teams import FULL
import model, signals
TIP = {f"{a}-{h}": t for a, h, t, v in model.GAMES}
SK = {'points': 'p', 'rebounds': 'r', 'assists': 'a', 'threes': 't'}
SEASON = {}
for ln in (D/'season_raw.txt').read_text().strip().splitlines()[1:]:
    f = ln.split('|')
    for tok in f[6].split(' '):
        k, v = tok.split(':'); cur = v.split('/')[3]
        SEASON[(f[0], k[0], float(k[1:]))] = [int(x) for x in cur.split('-') if x]
def slog(pl, stat, line):
    k = SK.get(stat)
    v = SEASON.get((pl, k, float(line)))
    if v is None: v = next((x for (p, kk, l), x in SEASON.items() if p == pl and kk == k), None)
    return v
def fm(o): return f'+{o:g}' if o > 0 else f'{o:g}'
def rec(s): return (f"{s['w']}-{s['l']}" + (f"-{s['p']}" if s.get('p') else '') + f" {s['u']:+.2f}u") if s else None
def tier_of(reasons, against):
    f = sum(r['points'] for r in reasons if isinstance(r.get('points'), (int, float)))
    a = sum(r['points'] for r in against if isinstance(r.get('points'), (int, float)))
    lead = f - a
    return ('Strong' if lead >= 4 else ('Solid' if lead >= 2 else 'Lean')), f"signal lead {lead:g} (for {f:g}, against {a:g})"
# B78 folded in (Nov 14, was fix13.py): side picks (spread, moneyline) are tiered on the pick side's signal lead in their own market.
# Betting signals read from the other side market (spread vs moneyline splits, sharp report) are dropped from the pick's reasons and against;
# team facts are game context and count in both markets. Totals keep the total signal lead.
BETMK = ('Spread', 'Moneyline')
def rmkt(r, default):
    lab, det = r.get('label', ''), r.get('detail', '')
    if '(spread)' in det or 'spread' in det.lower() and lab in ('Reverse line movement', 'Line move', 'Money % above ticket %', 'Fade the public'): return 'Spread'
    if '(moneyline)' in det or 'moneyline tickets' in det: return 'Moneyline'
    if lab.startswith('Action Network') or lab in ('Reverse line movement', 'Line move', 'Money % above ticket %', 'Fade the public'): return default
    return 'Game context'
def tier_mk(reasons, against, market):
    if market not in BETMK: return (*tier_of(reasons, against), reasons, against)
    keep = lambda r: rmkt(r, market) not in BETMK or rmkt(r, market) == market
    reasons = [r for r in reasons if keep(r)]; against = [r for r in against if keep(r)]
    t, basis = tier_of(reasons, against)
    return t, basis + f" in the {market.lower()} market", reasons, against
def last5(a, h, market, line):
    if market == 'Moneyline':
        z = lambda t: [dict(r=r_, pf=pf, pa=pa) for r_, pf, pa in zip(TR[t]['last5'], TR[t]['last5_scores'], TR[t]['last5_allowed'])]
        return dict(label='results, points for and against, oldest to newest', last5_away=z(a), last5_home=z(h), line=None)
    if market == 'Spread': return dict(label='margins, oldest to newest', last5_away=TR[a]['last5_margins'], last5_home=TR[h]['last5_margins'], line=line)
    return dict(label='game totals, oldest to newest', last5_away=TR[a]['last5_totals'], last5_home=TR[h]['last5_totals'], line=line)
SRCMAP = {'Action Network Sharp Action': 'Action Network', 'Action Network Big Money': 'Action Network', 'Action Network PRO Systems': 'Action Network',
          'Money % above ticket %': 'Action Network', 'Fade the public': 'Action Network', 'Reverse line movement': 'Action Network, DraftKings via ESPN',
          'Line move': 'Action Network, DraftKings via ESPN'}
writes, summary, newtiers = [], [], {}
def put(coll, did, data, op, ver=None):
    p = OUT/f"{coll.replace('/', '_')}__{did}.json"; p.write_text(json.dumps(data))
    e = dict(op=op, collection=coll, doc_id=did, file_path=str(p.resolve()))
    if ver: e['if_version'] = ver
    elif did in EXIST: e['if_version'] = EXIST[did]
    writes.append(e)
for e in W0:
    if e['collection'] != 'sports/nba/picks': put(e['collection'], e['doc_id'], json.load(open(e['file_path'])), e['op'], e.get('if_version')) if e['collection'] != 'sports/nba/games' or e['op'] == 'update' else None; continue
    x = json.load(open(e['file_path'])); did = e['doc_id']
    if x['market'] != 'Prop':
        t, basis, x['reasons'], x['against'] = tier_mk(x.get('reasons', []), x.get('against', []), x['market'])
        x['rule_tier'] = x.get('tier'); x['tier'] = t; x['tier_basis'] = basis; newtiers[did] = (t, basis)
        line = None
        if x['market'] != 'Moneyline':
            import re; m = re.search(r'([+-]?[\d.]+)\s*$', x['pick']); line = float(m.group(1)) if m else None
        x.setdefault('last5', last5(x['away'], x['home'], x['market'], line))
    else:
        x['season_log'] = slog(x['player'], x['stat'], x['line'])
    x['sport'] = 'nba'; x['logged_at'] = LOGGED
    put('sports/nba/picks', did, x, 'set'); summary.append(('pick', did, x['pick'], x['price'], x.get('tier')))
# would-be picks from inactive rules
for key, s in SH.items():
    a, h = key.split('-'); nm = {'A': a, 'H': h}
    for c in s['cands']:
        sd = c['side']; o = 'H' if sd == 'A' else 'A'
        rows = s['srows'] + s['prows']
        reasons = [dict(label=r[0], detail=r[4], points=r[3], source=SRCMAP.get(r[0], 'Card model')) for r in rows if r[3] and r[2] == sd]
        against = [dict(label=r[0], detail=r[4], points=r[3], source=SRCMAP.get(r[0], 'Card model')) for r in rows if r[3] and r[2] == o]
        if c['market'] == 'Total':
            rows = s['trows']
            reasons = [dict(label=r[0], detail=r[4], points=r[3], source=SRCMAP.get(r[0], 'Card model')) for r in rows if r[3] and r[2] == 'U']
            against = [dict(label=r[0], detail=r[4], points=r[3], source=SRCMAP.get(r[0], 'Card model')) for r in rows if r[3] and r[2] == 'O']
        t, basis, reasons, against = tier_mk(reasons, against, c['market'])
        team = nm.get(sd)
        if c['market'] == 'Moneyline': pick = f"{FULL[team]} moneyline"; line = None
        elif c['market'] == 'Spread': line = c['line']; pick = f"{FULL[team]} {fm(line)}"
        else: line = c['line']; pick = f"Under {line:g}"
        rs = RS['rules'][c['rule']]
        doc = dict(sport='nba', date=DATE, game=f"{a} @ {h}", away=a, home=h, time=TIP[key], market=c['market'], pick=pick, side=team if c['market'] != 'Total' else 'under',
                   price=c['price'], line=line, rule=c['rule'], rule_variant=rs.get('variant'), shadow=True, tier=t, tier_basis=basis, rule_tier=None, conflicting=False,
                   result='pending', final='', reasons=reasons, against=against, last5=last5(a, h, c['market'], line),
                   rule_record=dict(rule=signals.RULES[c['rule']]['label'], status='off', every_game=rec(rs.get('season')), month=rec(rs.get('month')), last_14_days=rec(rs.get('last14'))),
                   experts=[dict(name=x_['name'], platform=x_['platform'], pick=x_['pick'], market=x_['market'], side=x_.get('side'), line=x_.get('line'), price=x_.get('price'),
                                 units=x_.get('units'), record=x_.get('record'), card_record=None, url=x_.get('url'), list_url=x_.get('list_url')) for x_ in EXP if x_['game'] == key and x_['market'] == c['market']],
                   note=f"Would-be pick: {c['rule']} is switched off (season units negative); logged and graded, never a card pick.", logged_at=LOGGED)
        did = f"{DATE}_{key}_side" if c['market'] != 'Total' else f"{DATE}_{key}_total"
        if any(w['doc_id'] == did and w['collection'] == 'sports/nba/picks' for w in writes): did = f"{did}_{c['rule']}"   # Nov 9 fix: a live card pick already holds this id
        put('sports/nba/picks', did, doc, 'set'); summary.append(('shadow', did, pick, c['price'], t))
# today's game docs: overwrite pick tiers, add season_log to PROPs
for e in W0:
    if e['collection'] != 'sports/nba/games' or e['op'] != 'set': continue
    g = json.load(open(e['file_path']))
    for m in ('side', 'total'):
        p = g['picks'].get(m) or {}
        if p.get('doc_id') in newtiers: p['rule_tier'] = p.get('tier'); p['tier'], p['tier_basis'] = newtiers[p['doc_id']]
    for pr in g.get('props', []): pr['season_log'] = slog(pr['player'], pr['stat'], pr['line'])
    g['updated_at'] = LOGGED
    put('sports/nba/games', e['doc_id'], g, 'set', e.get('if_version'))
(OUT/'writes.json').write_text(json.dumps(writes, indent=0))
for s in summary: print(s)
print(len(writes), 'writes')
