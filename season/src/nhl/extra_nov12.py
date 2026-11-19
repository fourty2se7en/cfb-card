"""Nov 12 evening: new NHL rules not yet in hubdocs (B56, B61): NHL_REST_ML, NHL_BACKUP_G_ML (on), TT1 (off, would-be),
MODEL_ONLY_MONEYLINE / PUCK_LINE / TOTAL (off, would-be). Then the opposing picks rule across every card pick tonight.
Appends to hub_writes.json."""
import json, os, re, math, glob, collections
import render as R, model as M, rules as RL
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'hub')
D = '2026-11-12'
META = json.load(open('/home/claude/season/nhl12w/meta_now/meta/nhl.json')); META = META.get('data', META)
MR = {r['key']: r for r in META['rules']}
W = json.load(open(os.path.join(HERE, 'hub_writes.json')))
def be(o): return -o/(-o+100) if o < 0 else 100/(o+100)
def fmt(o): return f'+{o}' if o > 0 else f'{o}'
def pois_over(lam, line):  # P(X > line) for half lines
    k = int(math.floor(line)); return 1 - sum(math.exp(-lam) * lam**i / math.factorial(i) for i in range(k + 1))
GS = collections.defaultdict(dict)
txt = open(os.path.join(HERE, 'skaters_raw.txt')).read().split('GOALIES')[1]
for ln in txt.strip().splitlines()[1:]:
    t, rest = ln.split(' ', 1)
    for part in rest.split(';'):
        m = re.match(r'\s*(\S+) (\d+) ', part)
        if m: GS[t][m.group(1)] = int(m.group(2))
def no1(t, g):
    gs = GS.get(t, {}); mx = max(gs.values()) if gs else 0
    mine = gs.get(g, 0); top = [x for x, v in gs.items() if v == mx]
    return 'no1' if (mine == mx and len(top) == 1) else ('backup' if mine < mx else 'tie')
docs = []
def doc(k, g, rid, market, pick, side, price, line=None, prob=None, reasons=(), against=(), extra=None):
    a, h = k.split('-'); r = MR.get(rid, {})
    d = dict(sport='nhl', date=D, game=f'{a} @ {h}', away=a, home=h, time=g[2], result='pending', final='', conflicting=False, experts=[],
             line_source='The Odds API median of books', logged_at=f'{D} ~2:05 PM Phoenix', market=market, rule=rid, version='base', pick=pick,
             side=side, price=price, tier='All', strength='All', reasons=list(reasons), against=list(against),
             rule_record=dict(rule=r.get('label', rid), every_game=(f"{r['season']['w']}-{r['season']['l']} {r['season']['u']:+.2f}u" if r.get('season') else None)))
    if line is not None: d['line'] = line
    if prob is not None: d['model'] = dict(hit_pct=round(100*prob, 1), needed_pct=round(100*be(price), 1), edge=round(100*(prob - be(price)), 1))
    if not r.get('on'):
        d['shadow'] = True; d['conflict'] = dict(reason=f"{r.get('label', rid)} is off (status record red or not yet 2 positive pick days); logged as a would-be pick.", kept=None, **{'with': None})
    if extra: d.update(extra)
    docs.append((f"{D}_{k}_{ {'Moneyline':'ml','Puck line':'pl','Total':'total','Team total':'tt'}[market] }_{rid}" + (f'_{side}' if market == 'Team total' else ''), d))
for x in R.PICKS:
    k = x['key']
    if k == 'CAR-SEA': continue
    g = next(y for y in R.games if f"{y['a']}-{y['h']}" == k); G = next(y for y in M.GAMES if f'{y[0]}-{y[1]}' == k)
    a, h = k.split('-'); la, lh = g['la'], g['lh']; nm = {a: M.NAMES[a], h: M.NAMES[h]}
    # REST
    ra, rh = g['A']['rest'], g['H']['rest']
    for t, mine, opp, pr in ((a, ra, rh, la['ml']), (h, rh, ra, lh['ml'])):
        if opp == 0 and mine >= 1:
            doc(k, G, 'NHL_REST_ML', 'Moneyline', f'{nm[t]} moneyline', t, pr, prob=(g['pA'] if t == a else g['pH']),
                reasons=[dict(label='Rest edge', detail=f"{nm[t]} had {mine} days off; the opponent played yesterday", points=None, source='NHL schedule', market='Moneyline')])
    # BACKUP goalie
    sa, sh = no1(a, G[4]), no1(h, G[6])
    for t, me, other, gme, gother, pr in ((a, sa, sh, G[4], G[6], la['ml']), (h, sh, sa, G[6], G[4], lh['ml'])):
        if me == 'backup' and other == 'no1':
            doc(k, G, 'NHL_BACKUP_G_ML', 'Moneyline', f'{nm[t]} moneyline', t, pr, prob=(g['pA'] if t == a else g['pH']),
                reasons=[dict(label='Backup goalie vs No. 1', detail=f"{gme} ({GS[t].get(gme, 0)} starts) vs {gother} ({GS[k.split('-')[1] if t == a else a].get(gother, 0)} starts, No. 1); the market overprices the No. 1", points=None, source='Daily Faceoff, RotoWire, NHL API', market='Moneyline')],
                extra=dict(goalies=dict(this_team=gme, status=G[5] if t == a else G[7], opponent=gother)))
    # TT1 (off): model 3+ points over the no-vig break-even
    for t, L, lam in ((a, la, g['lamA']), (h, lh, g['lamH'])):
        tt = L.get('tt')
        if not tt: continue
        line, po, pu = tt; pov = pois_over(lam, line); q = be(po) / (be(po) + be(pu))
        for side, p, price, qq in (('Over', pov, po, q), ('Under', 1 - pov, pu, 1 - q)):
            if 100 * (p - qq) >= 3:
                doc(k, G, 'TT1', 'Team total', f"{nm[t]} team total {side} {line:g}", t, price, line=line, prob=p,
                    reasons=[dict(label='Model edge', detail=f"Model {lam:.2f} goals, {100*p:.1f}% vs {100*qq:.1f}% no-vig", points=None, source='Card model', market='Team total')],
                    extra=dict(category='Game prop', sub_market='Team total'))
    # MODEL_ONLY (off): model side with 1%+ edge at the price
    mlA, mlH = la['ml'], lh['ml']
    for t, p, pr in ((a, g['pA'], mlA), (h, g['pH'], mlH)):
        if p - be(pr) >= 0.01: doc(k, G, 'MODEL_ONLY_MONEYLINE', 'Moneyline', f'{nm[t]} moneyline', t, pr, prob=p)
    fav_home = lh['pl'][0] < 0
    cov_h = g['pH2'] if fav_home else 1 - g['pA2']
    for t, p, L in ((h, cov_h, lh), (a, 1 - cov_h, la)):
        if p - be(L['pl'][1]) >= 0.01:
            ln = L['pl'][0]; doc(k, G, 'MODEL_ONLY_PUCK_LINE', 'Puck line', f"{nm[t]} {'+' if ln > 0 else ''}{ln:g}", t, L['pl'][1], line=ln, prob=p)
    c = x['c']; un, pu_ = g['p_tot_under'](c['line']); ov = 1 - un - pu_
    for side, p, pr in (('Over', ov, c['tprice'][0]), ('Under', un, c['tprice'][1])):
        if p - be(pr) >= 0.01: doc(k, G, 'MODEL_ONLY_TOTAL', 'Total', f"{side} {c['line']:g}", side, pr, line=c['line'], prob=p)
# opposing picks rule across tonight's card picks (sides: moneyline and puck line; totals: Over vs Under)
cur = {}
for w in W:
    if w['collection'] == 'sports/nhl/picks' and w['doc_id'].startswith(D):
        cur[w['doc_id']] = (w, json.load(open(w['file_path'])))
def units(d):
    if d['tier'] == 'All': return (MR.get(d['rule'], {}).get('season') or {}).get('u', 0)
    t = ((MR.get(d['rule'], {}).get('tiers') or {}).get(d['tier']) or {}); return (t.get('season') or {}).get('u', 0)
RANK = {'Strong': 3, 'Solid': 2, 'Lean': 1}
allp = {i: d for i, (w, d) in cur.items()}; allp.update({i: d for i, d in docs})
byg = collections.defaultdict(list)
for i, d in allp.items():
    if not d.get('shadow') and d['market'] in ('Moneyline', 'Puck line', 'Total'): byg[(d['game'], 'tot' if d['market'] == 'Total' else 'side')].append((i, d))
changed = set()
for (gm, grp), L in byg.items():
    if len({d['side'] for i, d in L}) < 2: continue
    # higher tier stays; an 'All' tier (single tier rule) compares on season units
    mixed = any(y[1]['tier'] == 'All' for y in L)
    L.sort(key=lambda z: (0 if mixed else RANK.get(z[1]['tier'], 0), units(z[1])), reverse=True)
    keep = L[0]
    for i, d in L[1:]:
        if d['side'] != keep[1]['side']:
            d['shadow'] = True; d['conflict'] = {'reason': f"The card already backs {keep[1]['pick']} ({keep[1]['rule']} {keep[1]['tier']}, {units(keep[1]):+.2f}u season) in this game; opposing picks rule.", 'kept': keep[1]['pick'], 'with': keep[0]}
            changed.add(i); print('opposing:', gm, 'kept', keep[1]['rule'], keep[1]['pick'], '| would-be', d['rule'], d['pick'])
for i in changed:
    if i in cur: json.dump(cur[i][1], open(cur[i][0]['file_path'], 'w'))
for i, d in docs:
    p = os.path.join(OUT, ('sports/nhl/picks__' + i).replace('/', '_') + '.json'); json.dump(d, open(p, 'w'))
    W.append(dict(op='set', collection='sports/nhl/picks', doc_id=i, file_path=p))
json.dump(W, open(os.path.join(HERE, 'hub_writes.json'), 'w'), indent=0)
for i, d in docs: print(i[11:], '|', d['pick'], fmt(d['price']), '| card' if not d.get('shadow') else '| would-be', d.get('model', {}).get('edge'))
