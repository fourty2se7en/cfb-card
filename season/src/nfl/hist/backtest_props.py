"""Season backtest of every prop rule (Nov 7, 2026): props_bt.run() walk-forward on every stored DraftKings line (hist/props_lines.csv),
then one doc per PLAY or LEAN pick, rule key 'STAT Side TIER', graded from nflverse player stats and snap counts.
Run from the card folder:  python3 hist/backtest_props.py [meta_nfl.json] [out.json]
meta_nfl.json = saved hub meta/nfl (labels, on/off now); default: signals.json prop_rules. out.json defaults to hist/backtest_prop_docs.json.
Doc id <date>_<AWAY>-<HOME>_<STAT-Side-TIER>_<PlayerKey>; duplicates (same player, line read twice) keep the first."""
import sys, os, json, re, pathlib
D = pathlib.Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D)); os.chdir(D)
args = [a for a in sys.argv[1:] if not a.startswith('--')]
import pandas as pd, nflreadpy as nfl
import props_bt, props_rules as PRR, rules as RU
B, recs, MW, last3 = props_bt.run(out=lambda s: None)
if args:
    META = json.load(open(args[0])); META = META.get('data', META)
    ON = {r['key']: r['on'] for r in META['rules']}; LBL = {r['key']: r['label'] for r in META['rules']}
else:
    PR = json.load(open('signals.json'))['prop_rules']['cats']
    ON = {f'{c} {t}': PR[c][t]['on'] for c in PRR.CATS for t in PRR.TIERS}; LBL = {k: f'Prop: {k}' for k in ON}
OUT = args[1] if len(args) > 1 else 'hist/backtest_prop_docs.json'
s = nfl.load_schedules([2026]).to_pandas(); s = s[s.season == 2026]
DT = {(int(r.week), f'{r.away_team} @ {r.home_team}'): r.gameday for r in s.itertuples()}
docs, seen = [], set()
for r in B[B.tier.notna()].itertuples():
    key = f'{r.stat} {r.side} {r.tier}'; a, h = r.game.split(' @ '); d = DT[(int(r.week), r.game)]
    pk = re.sub('[^A-Za-z]', '', PRR.pnorm(r.player).title()); did = f"{d}_{a}-{h}_{key.replace(' ', '-')}_{pk}"
    if did in seen: continue
    seen.add(did)
    docs.append(dict(id=did, date=d, week=int(r.week), game=r.game, away=a, home=h, market='Prop', rule_key=key, rule=LBL[key], rule_on_now=bool(ON[key]),
                     pick=f"{r.player} {r.side.lower()} {r.line:g} {r.stat.lower()} yds", player=r.player, team=r.team, stat=r.stat, side=r.side,
                     line=float(r.line), price=float(r.price), tier=r.tier, book='DraftKings', final=f"{r.actual:g} {r.stat.lower()} yds",
                     result={1: 'win', -1: 'loss', 0: 'push'}[int(r.res)], units=round(RU.payout(r.price, int(r.res)), 3),
                     inputs=dict(edge_pts=round(float(r.edge), 2), games_this_season=int(r.n), projection=float(r.proj)), source='backtest Nov 7'))
json.dump(docs, open(OUT, 'w')); print(len(docs), 'prop rule picks ->', OUT)
df = pd.DataFrame([dict(k=d['rule_key'], m=MW[d['week']], res=d['result'], u=d['units']) for d in docs])
f = lambda y: f"{(y.res=='win').sum()}-{(y.res=='loss').sum()}-{(y.res=='push').sum()} {y.u.sum():+.2f}u"
for k in [f'{c} {t}' for c in PRR.CATS for t in PRR.TIERS]:
    x = df[df.k == k]; print(k, 'ON' if ON[k] else 'off', '| season', f(x), '| Nov', f(x[x.m == 'Nov']))
