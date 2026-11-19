"""NBA rule backtest (Nov 6, 2026). Applies every game rule in signals.RULES, on or off, to every game played, as if live
from the first game, and grades each pick at the closing median price (Action Network individual books).
Usage (run in a folder holding the src/ code files without .txt, plus season/):  python3 backtest.py [out_dir]
Inputs: season/espn_odds.txt, season/an_odds.txt, season/card_inputs.json, season/ratings.txt, season/plines.txt, standings_raw.txt
        (via season_build.py and pickrules.py; signals.py supplies RULES and the locked price limits).
Outputs in out_dir (default bt_out): bt_docs.json (list of [doc_id, doc]), docs/<doc_id>.json, batch0.json.. (ArtifactData batch
entries for Season Cards collection sports/nba/backtest, 50 per batch; add if_version for docs that already exist), and a record summary.
META below = each rule's variant and on/off at the time of the run (read from the hub meta doc nba); edit before rerunning."""
import json, pathlib, collections, sys, os
import season_build as SB, pickrules as P
SRC_DATE = os.environ.get('BT_DATE', 'Nov 7')
META = {'FAV_ML': ('lowered', True), 'DOG_ML': ('lowered', False), 'SPREAD_MOVE': ('lowered', False), 'UNDER_DROP': ('strict', True), 'OVER': ('lowered', False)}
LABEL = {'FAV_ML': 'Favorite moneyline', 'DOG_ML': 'Underdog moneyline', 'SPREAD_MOVE': 'Spread line move', 'UNDER_DROP': 'Under on a dropping total', 'OVER': 'Overs'}
PL = {}
for ln in open('season/plines.txt').read().split('\n'):
    if not ln or not (ln[:2].isdigit() and ln[2:3] == '-'): continue
    d, a, h, h1, q1, sc = ln.split('|')
    s1, t1 = h1.split(','); s2, t2 = q1.split(',')
    q, hh = sc.split(';')
    PL[('2026-' + d, a, h)] = {'1H': {'spread_away': float(s1), 'total': float(t1), 'score': hh}, 'Q1': {'spread_away': float(s2), 'total': float(t2), 'score': q}}
def tier(l): return 'Strong' if l >= 5 else ('Solid' if l >= 3 else 'Thin')
state = {k: dict(on=True, variant=v[0]) for k, v in META.items()}
G = SB.build(); out = []
for g in G:
    inp = g['inp']; S = P.score_game(inp)
    for c in P.candidates(inp, S, state):
        r = P.grade_side(c, g['as_'], g['hs']) if c['market'] != 'Total' else P.grade_total(c, g['as_'], g['hs'])
        u = round(P.units(r, c['price']), 3)
        a, h = g['a'], g['h']; team = a if c['side'] == 'A' else h
        if c['market'] == 'Moneyline': pick = f"{team} ML"; line = None; lead = S['ml_lead']
        elif c['market'] == 'Spread': pick = f"{team} {P.sp(c['line'])}"; line = c['line']; lead = S['sp_lead'] if S['side'] == c['side'] else S['ml_lead']
        else: pick = f"Under {c['line']:g}"; line = c['line']; lead = S['t_lead'] if S['tside'] == 'U' else 0
        ins = dict(close_ml_away=inp['ml_a'], close_ml_home=inp['ml_h'], close_spread_away=inp['sp_a'], close_total=inp['tot'],
                   an_open_spread_away=inp['open_sp_a'], an_open_total=inp['open_tot'], an_open_ml=[inp['open_ml_a'], inp['open_ml_h']],
                   dk_spread_away=[inp['src2']['sp_open_a'], inp['src2']['sp_now_a']], dk_total=[inp['src2']['tot_open'], inp['src2']['tot_now']],
                   ml_tickets_away=inp['ml_bets_a'], ml_money_away=inp['ml_money_a'], spread_tickets_away=inp['sp_bets_a'], spread_money_away=inp['sp_money_a'],
                   over_tickets=inp['o_bets'], over_money=inp['o_money'], sig_ml=inp['sig_ml'], sig_sp=inp['sig_sp'], sig_tot=inp['sig_tot'],
                   pro_codes=g['has_codes'], signal_side=team if c['market'] != 'Total' else None,
                   side_scores={a: S['sc']['A'], h: S['sc']['H']}, ml_lead=S['ml_lead'], total_scores=S['tc'],
                   model_home_margin=round(inp['margin'], 2), model_total=round(inp['ptotal'], 1), model_pace=round(inp['pace'], 1), blended_home_win=round(S['estH'], 3))
        doc = dict(date=g['d'], game=f"{a} @ {h}", away=a, home=h, market=c['market'], rule_key=c['rule'], rule=LABEL[c['rule']],
                   rule_on_now=META[c['rule']][1], variant=META[c['rule']][0], pick=pick, line=line, price=int(c['price']), tier=tier(lead),
                   final=f"{a} {g['as_']}, {h} {g['hs']}", result=r, units=u, inputs=ins, source=f'backtest {SRC_DATE}', priced_at='closing median of individual books (Action Network)')
        pl = PL.get((g['d'], a, h))
        if pl: doc['plines'] = pl
        out.append((f"{g['d']}_{a}-{h}_{c['rule']}", doc))
OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'bt_out'); (OUT/'docs').mkdir(parents=True, exist_ok=True)
json.dump(out, open(OUT/'bt_docs.json', 'w'))
W = []
for k, d in out:
    p = OUT/'docs'/f'{k}.json'; json.dump(d, open(p, 'w'))
    W.append(dict(op='set', collection='sports/nba/backtest', doc_id=k, file_path=str(p.resolve())))
for i in range(0, len(W), 50): json.dump(W[i:i+50], open(OUT/f'batch{i//50}.json', 'w'))
R = collections.defaultdict(list)
for k, d in out:
    R[(d['rule_key'], 'season')].append((d['result'], d['price']))
    if d['date'] >= '2026-11-01': R[(d['rule_key'], 'nov')].append((d['result'], d['price']))
    if d['date'] >= '2026-10-24': R[(d['rule_key'], 'codes')].append((d['result'], d['price']))
for k in sorted(R): print(k, P.rec_txt(P.summarize(R[k])))
print(len(out), 'docs', len(G), 'games', sum(1 for g in G if (g['d'], g['a'], g['h']) in PL), 'with plines')
