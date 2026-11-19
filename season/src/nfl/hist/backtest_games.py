"""Season backtest of every game rule (Nov 7, 2026). Each rule, on or off, applied on its own to every 2026 game played and
graded at the close; docs also carry first_in_rule_order (card order: fav_ml, spread, dog_ml, dog_spread; total_one_sided, over).
Run from the card folder (code files without .txt):
  python3 hist/backtest_games.py [meta_nfl.json] [out.json]
meta_nfl.json = a saved copy of the Season Cards hub doc meta/nfl (labels and on/off now); default: labels and on/off from signals.json.
out.json defaults to hist/backtest_game_docs.json. Inputs: everything recheck.games() reads (hist/games.csv, hist/rebuilt.csv,
hist/openers2.csv, hist/snap.csv, hist/dk_parts.txt, hist/wx_archive.txt) plus nflverse schedules for finals and closing lines.
Each doc is written to hub collection sports/nfl/backtest with doc id = its 'id' (ArtifactData batch, 50 per call)."""
import sys, json, math, pathlib
D = pathlib.Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D))
import os; os.chdir(D)
args = [a for a in sys.argv[1:] if not a.startswith('--')]; sys.argv = ['x', '--no-props']
import numpy as np, pandas as pd
import recheck as RC, rules as RU
T = RC.games(); T['wx_src'] = ['forecast or nflverse' if not pd.isna(w) else 'none' for w in T.wind]
SIG = RU.load_sig(); G = RU.score_all(T, RC.LOG, SIG); RL = SIG['rules']
if args:
    META = json.load(open(args[0])); META = META.get('data', META)
    ON = {r['key']: r['on'] for r in META['rules']}; LBL = {r['key']: r['label'] for r in META['rules']}
else:
    ON = {r['id']: r['on'] for r in RL['side'] + RL['total']}; LBL = {r['id']: RU.active(r)['label'] for r in RL['side'] + RL['total']}
OUT = args[1] if len(args) > 1 else str(D/'hist'/'backtest_game_docs.json')
FAV = RU.active(next(r for r in RL['side'] if r['id'] == 'fav_ml')); SPR = RU.active(next(r for r in RL['side'] if r['id'] == 'spread'))
TOT = RU.active(next(r for r in RL['total'] if r['id'] == 'total_one_sided'))
TESTED = ('rlm', 'div_dog', 'pr_fade', 'expert_follow')
def dog(g): return (g['away'] if g['fav'] == g['home'] else g['home']) if g['fav'] else None
def reason(g, d): return [k for k in g['side_keys'][d] if k in TESTED and g['side_pts'][d].get(k, 0) > 0]
info = {(int(r.week), r.game): r for _, r in T.iterrows()}; rows = []
for g in G:
    r = info[(int(g['week']), g['game'])]
    base_inp = dict(signal_team=g['team'], signal_lead=g['lead'], favourite=g['fav'], side_points={t: g['side_pts'][t] for t in (g['away'], g['home'])},
                    total_over=g['so'], total_under=g['su'], total_keys=g['tot_keys'], open_spread_home=g.get('open_sp'), open_spread_src=g.get('open_sp_src'),
                    open_total=g.get('open_tot'), close_spread_home=g['spread_h'], close_total=g['total'], close_ml_away=g['ml_a'], close_ml_home=g['ml_h'],
                    wind=None if pd.isna(r.get('wind')) else float(r['wind']))
    cand = []
    z = RU.side_rule(g, dict(FAV, on=True))
    if z: cand.append(('fav_ml', z[0], 'Moneyline'))
    z = RU.side_rule(g, dict(SPR, on=True))
    if z: cand.append(('spread', z[0], 'Spread'))
    d = dog(g)
    if d and g['team'] == d and g['lead'] >= 1 and reason(g, d):
        pr = RU.ml_price(g, d)
        if not RU.isna(pr) and 100 <= pr <= 200: cand.append(('dog_ml', d, 'Moneyline'))
        cand.append(('dog_spread', d, 'Spread'))
    for key, t, mk in cand:
        res, price = RU.side_res(g, t, mk)
        line = None if mk == 'Moneyline' else (-g['spread_h'] if t == g['away'] else g['spread_h'])
        rows.append(dict(g=g, r=r, key=key, market=mk, pick=f"{t} ML" if mk == 'Moneyline' else f"{t} {RU.fl(line)}", line=line, price=price, res=res,
                         inp=dict(base_inp, reasons=reason(g, t) if key.startswith('dog') else None)))
    sd = RU.total_rule(g, dict(TOT, on=True))
    if sd: res, price = RU.tot_res(g, sd); rows.append(dict(g=g, r=r, key='total_one_sided', market='Total', pick=f"{sd.upper()} {g['total']:g}", line=g['total'], price=price, res=res, inp=base_inp))
    if g['so'] - g['su'] >= 3:
        res, price = RU.tot_res(g, 'Over'); rows.append(dict(g=g, r=r, key='over', market='Total', pick=f"OVER {g['total']:g}", line=g['total'], price=price, res=res, inp=base_inp))
ORD = {'fav_ml': 0, 'spread': 1, 'dog_ml': 2, 'dog_spread': 3, 'total_one_sided': 0, 'over': 1}; first = {}
for x in rows:
    k = (x['g']['week'], x['g']['game'], x['market'] == 'Total')
    if k not in first or ORD[x['key']] < ORD[first[k]]: first[k] = x['key']
def clean(o):
    if isinstance(o, dict): return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (float, np.floating)): return None if math.isnan(o) else round(float(o), 3)
    return o
docs = []
for x in rows:
    g, r = x['g'], x['r']; res = {1: 'win', -1: 'loss', 0: 'push'}[x['res']]
    date = str(RC.s26[(RC.s26.week == g['week']) & (RC.s26.game == g['game'])].gameday.iloc[0])
    docs.append(dict(id=f"{date}_{g['away']}-{g['home']}_{x['key']}", date=date, week=int(g['week']), game=f"{g['away']} @ {g['home']}", away=g['away'], home=g['home'],
                     market=x['market'], rule_key=x['key'], rule=LBL[x['key']], rule_on_now=bool(ON[x['key']]), pick=x['pick'], line=clean(x['line']),
                     price=clean(x['price']), tier='Strong' if x['key'] in ('fav_ml', 'spread') else ('Solid' if x['key'] == 'total_one_sided' else 'Off-rule'),
                     final=f"{g['away']} {int(r.away_score)}, {g['home']} {int(r.home_score)}", result=res, units=round(RU.payout(x['price'], x['res']), 3),
                     inputs=clean(x['inp']), first_in_rule_order=first[(g['week'], g['game'], x['market'] == 'Total')] == x['key'], source='backtest Nov 7'))
json.dump(docs, open(OUT, 'w')); MW = RC.MW
print(len(G), 'games scored;', len(docs), 'rule picks ->', OUT)
df = pd.DataFrame([dict(k=d['rule_key'], m=MW[d['week']], res=d['result'], u=d['units'], o=d['first_in_rule_order']) for d in docs])
s = lambda y: f"{(y.res=='win').sum()}-{(y.res=='loss').sum()}-{(y.res=='push').sum()} {y.u.sum():+.2f}u"
print('--- each rule on every game it fits ---')
for k, x in df.groupby('k'): print(k, 'season', s(x), '| Nov', s(x[x.m == 'Nov']))
print('--- first in rule order (all rules on) ---')
for k, x in df[df.o].groupby('k'): print(k, 'season', s(x), '| Nov', s(x[x.m == 'Nov']))
