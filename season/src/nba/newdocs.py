import json, glob, os, sys, re
sys.path.insert(0, 'w')
import pickrules as P
DATE = sys.argv[1] if len(sys.argv) > 1 else '2026-11-13'
METAF = sys.argv[2] if len(sys.argv) > 2 else 'meta_new.json'
from teams import FULL
import harness as H
F = json.load(open('newrules_today.json')); SH = json.load(open('w/shadow_raw.json')); TI = json.load(open('w/today_inp.json'))
M = json.load(open(METAF)); RULES = {r['key']: r for r in M['rules'] if r.get('key')}
AN = json.load(open('w/season/card_inputs.json'))[DATE]['an']
FD = 'final'; LOGGED = os.environ.get('LOGGED', '3:40 PM'); SRC = 'The Odds API median of books'
def fr(r): return f"{r['w']}-{r['l']}" + (f"-{r['p']}" if r.get('p') else '') + f" {r['u']:+.2f}u"
def gdoc(k): return f"{FD}/sports_nba_games__{DATE}_{k}.json"
LABEL = {'NBA_TOT_CAL': 'Model total, blended and calibrated', 'NBA_TOT_MOVE': 'Model total with the line move', 'MODEL_ONLY_SPREAD': 'Model only · Spread',
         'MODEL_ONLY_TOTAL': 'Model only · Total', 'MODEL_ONLY_MONEYLINE': 'Model only · Moneyline', 'NBA_1H_FAV': 'Favorite 1st half spread'}
# card choice: tier on; one side pick per game (more season units in its tier wins); one total per game
fits = []
for f in F:
    f = dict(f); k = f['game']; a, h = f['a'], f['h']; i = TI[k]
    if f['market'] == 'Total': f['pick'] = f"{'Over' if f['side'] == 'A' else 'Under'} {f['line']:g}"; f['team'] = 'Over' if f['side'] == 'A' else 'Under'; f['slot'] = 'total'
    elif f['market'] == '1st half spread':
        team = a if f['side'] == 'A' else h; f['team'] = team; f['pick'] = f"{FULL[team]} 1st half {f['line']:+g}"; f['slot'] = 'h1'
    else:
        team = h if f['side'] == 'A' else a; f['team'] = team
        if f['market'] == 'Spread':
            ln = -i['sp_a'] if team == h else i['sp_a']; f['line'] = ln; f['pick'] = f"{FULL[team]} {ln:+g}"; f['slot'] = 'side'
        else: f['line'] = None; f['pick'] = f"{FULL[team]} moneyline"; f['slot'] = 'ml'
    t = (RULES[f['rule']].get('tiers') or {}).get(f['tier'], {}); f['on'] = bool(t.get('on')); f['trec'] = t
    fits.append(f)
for k in TI:
    for slot in ('side', 'total'):
        C = [f for f in fits if f['game'] == k and (f['slot'] == slot or (slot == 'side' and f['slot'] == 'ml')) and f['on']]
        C.sort(key=lambda f: -(f['trec'].get('season') or {}).get('u', 0))
        for j, f in enumerate(C):
            f['card'] = j == 0
            if j: f['conflict'] = f"Card picked another rule in this game ({C[0]['pick']}, {LABEL[C[0]['rule']]}, more season units in its tier)"
for f in fits:
    if not f['on']: f['card'] = False; f['conflict'] = (f"Its {f['tier']} tier is turned off (status record {fr(f['trec']['real'])}), so it is logged as a would-be pick." if f['trec'].get('real') else f"Its {f['tier']} tier has no status record yet, so it is turned off and logged as a would-be pick.")
W = []; H1 = []
for f in fits:
    k = f['game']; a, h = f['a'], f['h']; i = TI[k]; S = P.score_game(i); an = AN[k]
    pm = 'Spread' if f['market'] in ('Spread', '1st half spread') else f['market']
    if f['market'] == 'Total': rows = S['trows']
    else:   # B78: betting signals count only in their own market; team facts are game context
        rows = [r for r in S['srows'] if not (r[0].startswith(P.BETTING) and r[1] != pm)] + (list(S.get('prows', [])) if pm == 'Spread' else [])
    me = ('U' if f['side'] == 'B' else 'O') if f['market'] == 'Total' else (f['side'] if f['market'] == '1st half spread' else ('H' if f['side'] == 'A' else 'A'))
    def item(r): return dict(label=r[0], detail=r[4], points=r[3] if r[3] else None, source='Action Network' if 'Action' in r[0] or r[1] in ('Spread', 'Total') and r[0] in ('Fade the public', 'Money % above ticket %', 'Reverse line movement') else 'Card model',
                             market=r[1] if r[0].startswith('Action Network') or r[0] in ('Reverse line movement', 'Fade the public', 'Money % above ticket %', 'Total moved down', 'Total moved up', 'Line move') else ('Total' if f['market'] == 'Total' else 'Game context'))
    reasons = [item(r) for r in rows if r[2] == me and r[3]]
    against = [item(r) for r in rows if r[2] != me and r[3]]
    if f['market'] == '1st half spread':
        H1.append((f, reasons, against)); continue
    p = f['p'] if f['side'] == 'A' else 1 - f['p']; be = H.imp(f['price'])
    mlabel = {'Total': 'Model total', 'Spread': 'Model spread', 'Moneyline': 'Model win chance'}.get(f['market'], 'Model')
    reasons.insert(0, dict(label=mlabel, detail=f"{LABEL[f['rule']]}: {100*p:.1f}% at {f['price']:+d} (break-even {100*be:.1f}%, edge {f['edge']:+.1f} points)", points=None, source='Card model', market=f['market']))
    lead = f['lead']; fp = sum(x['points'] or 0 for x in reasons); ap = sum(x['points'] or 0 for x in against)
    gm = json.load(open(gdoc(k))); an_txt = (gm['picks'].get('total' if f['market'] == 'Total' else 'side') or {}).get('analysis', '')
    proj = re.search(r'Our model projects [^()]*\([^)]*\)[^()]*?\.(?=\s|$)', an_txt); proj = proj.group(0) if proj else ''
    if f['market'] == 'Total':
        mt = i['ptotal']; tnow = i.get('tot_now_v', i['tot'])
        why = [f"Our model total is {mt:.1f} against the {f['line']:g} opener; blended with the opener and calibrated on this season's games it gives the Under {100*p:.0f}% at {f['price']:+d}, against {100*be:.0f}% needed."]
        if any(r[0] == 'Action Network Sharp Action' and r[2] == 'U' for r in S['trows']): why.insert(0, "Action Network's sharp report shows sharp money on the Under.")
        dr = re.search(r'Defensive ratings this season: .*?\d\.(?=\s|$)', an_txt)
        if dr: why.append(dr.group(0))
        inj = re.findall(r'[A-Z][a-z]+ is without .*?numbers\)\.', an_txt); why += inj[:1]
        ag = [f"{an['o_bets']}% of the tickets and {an['o_money']}% of the money are on the Over."]
        if tnow > f['line']: ag.append(f"The total has moved up since the open, from {f['line']:g} to {tnow:g}, toward the Over.")
        orr = re.search(r'Offensive ratings this season: .*?\d\.(?=\s|$)', an_txt)
        if orr: ag.append(orr.group(0))
        lf = re.search(r'Last five game totals: [^\]]+\], [^\]]+\]\.', an_txt)
        if lf: ag.append(lf.group(0))
    else:
        team = f['team']; opp = a if team == h else h; mm = i['margin'] if team == h else -i['margin']
        why = [(f"Our model has {FULL[team]} by {mm:.1f}" if mm >= 0 else f"Our model has {FULL[team]} losing by only {-mm:.1f}") + (f" against the {f['line']:+g} opener" if f['line'] is not None else '') + f", which gives {100*p:.0f}% at {f['price']:+d} against {100*be:.0f}% needed."]
        if any(r[0] == 'Action Network Sharp Action' and r[2] == me for r in S['srows']): why.insert(0, f"Action Network's sharp report shows sharp money on {FULL[team]} against the spread.")
        INJ = re.findall(r'[A-Z][a-z]+(?: [A-Z][a-z]+)? is without .*?numbers\)\.', an_txt)
        why += [x for x in INJ if x.startswith(FULL[opp].rsplit(' ', 1)[0])][:1]
        ag = [x for x in INJ if x.startswith(FULL[team].rsplit(' ', 1)[0])][:1] + [f"{x['label']}: {x['detail']}" for x in against[:3] if x['label'] != 'Injury edge']
        if not ag: ag = ['The market prices this side short of our number; the risk is the price.']
        if f['market'] == 'Moneyline' and f['price'] < -200: ag.append(f"The price is {f['price']:+d}, longer than the -200 limit on the favorite moneyline rule.")
    did = f"{DATE}_{k}_{f['slot']}_{f['rule']}"
    tr = f['trec']; R = RULES[f['rule']]
    doc = dict(sport='nba', date=DATE, game=f"{a} @ {h}", game_id=f"{DATE}_{k}", away=a, home=h, time=gm['time'], market=f['market'], pick=f['pick'],
               side=f['team'], price=int(f['price']), line=f['line'], rule=f['rule'], rule_label=LABEL[f['rule']], rule_variant='base', shadow=not f['card'],
               tier=f['tier'], tier_basis=f"signal lead {lead} (for {fp}, against {ap}) in the {f['market'].lower()} market", rule_tier=None, conflicting=False,
               result='pending', final='', reasons=reasons, against=against, last5=None, experts=[],
               rule_record=dict(rule=LABEL[f['rule']], status='on' if f['on'] else 'off', every_game=R.get('every_game'), tier=f['tier'], tier_replay=fr(tr.get('season', {'w':0,'l':0,'u':0})),
                                tier_month=fr(tr['month']) if tr.get('month') else None),
               tier_record=dict(tier=f['tier'], on=f['on'], real=None, replay=fr(tr.get('season', {'w':0,'l':0,'u':0})), pending_on=tr.get('pending_on')),
               model=dict(projection=(round(i['ptotal'], 1) if f['market'] == 'Total' else round(i['margin'], 1)), hit_pct=round(100*p, 1), needed_pct=round(100*be, 1), edge=f['edge'],
                          calibrated=f['rule'] == 'NBA_TOT_CAL', raw_pct=round(100*(f['praw'] if f['side'] == 'A' else 1 - f['praw']), 1)),
               summary={'for': ' '.join(x for x in [w for w in why if w.startswith('Our model')] + [proj] + [w for w in why if not w.startswith('Our model')] if x), 'against': ' '.join(ag)},
               note=('Card pick.' if f['card'] else 'Would-be pick: logged and graded, never a card pick.') + ' Priced at the Odds API opening line (median of books, A32).',
               logged_at=LOGGED, line_source=SRC, opening_line=True)
    if f.get('conflict'): doc['conflict'] = f['conflict']
    tt = gm['trends']
    if f['market'] == 'Total': doc['last5'] = dict(label='game totals, oldest to newest', last5_away=tt['away'].get('last5_totals'), last5_home=tt['home'].get('last5_totals'), line=f['line'])
    else: doc['last5'] = dict(label='margins, oldest to newest', last5_away=tt['away'].get('last5_margins'), last5_home=tt['home'].get('last5_margins'), line=f['line'])
    fn = f"{FD}/sports_nba_picks__{did}.json"; json.dump(doc, open(fn, 'w'), indent=1)
    W.append(dict(op='set', collection='sports/nba/picks', doc_id=did, file_path=os.path.abspath(fn)))
    print(('CARD ' if f['card'] else 'WB   '), did, f['pick'], f['price'], f['tier'], f.get('conflict', '')[:60])
    if f['card']:
        slot = 'total' if f['market'] == 'Total' else 'side'
        gm['picks'][slot] = dict(pick=f['pick'], price=int(f['price']), tier=f['tier'], rule_label=LABEL[f['rule']], rule=f['rule'], doc_id=did, summary=doc['summary'], market=f['market'], line=f['line'])
        gm.setdefault('reasons', {})[slot] = reasons; gm['reasons'][slot + '_against'] = against
        json.dump(gm, open(gdoc(k), 'w'), indent=1)
for f, reasons, against in H1:
    k = f['game']; a, h = f['a'], f['h']; gm = json.load(open(gdoc(k))); tr = f['trec']; R = RULES[f['rule']]
    fp = sum(x['points'] or 0 for x in reasons); ap = sum(x['points'] or 0 for x in against); team = f['team']
    did = f"{DATE}_{k}_h1_{f['rule']}"
    doc = dict(sport='nba', date=DATE, game=f"{a} @ {h}", game_id=f"{DATE}_{k}", away=a, home=h, time=gm['time'], market='Game prop', sub_market='1st half spread', pick=f['pick'],
               side=team, price=int(f['price']), line=f['line'], rule=f['rule'], rule_label=LABEL[f['rule']], rule_variant='base', shadow=not f['card'],
               tier=f['tier'], tier_basis=f"signal lead {fp - ap} (for {fp}, against {ap}) in the spread market", rule_tier=None, conflicting=False,
               result='pending', final='', reasons=reasons, against=against, last5=None, experts=[],
               rule_record=dict(rule=LABEL[f['rule']], status='on' if f['on'] else 'off', every_game=R.get('every_game'), tier=f['tier']),
               tier_record=dict(tier=f['tier'], on=f['on'], real=tr.get('real'), pending_on=tr.get('pending_on')),
               summary={'for': f"The favorite moneyline rule fits {FULL[team]}, and this rule takes the same team on the 1st half spread ({f['line']:+g}).", 'against': 'Half lines carry more variance than the full game, and the moneyline rule only needs a win.'},
               note='Would-be pick: logged and graded, never a card pick. Priced at the Odds API opening line (median of books, A32).', logged_at=LOGGED, line_source=SRC, opening_line=True)
    if f.get('conflict'): doc['conflict'] = f['conflict']
    fn = f"{FD}/sports_nba_picks__{did}.json"; json.dump(doc, open(fn, 'w'), indent=1)
    W.append(dict(op='set', collection='sports/nba/picks', doc_id=did, file_path=os.path.abspath(fn)))
    print('WB   ', did, f['pick'], f['price'], f['tier'], f.get('conflict', '')[:60])
json.dump(W, open('newdocs_writes.json', 'w'), indent=1)
