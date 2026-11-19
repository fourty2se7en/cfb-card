"""Back review, Nov 7 2026: apply every current rule (on or off) to every 2026 game it fits, as if live from Week 0,
graded at the CFBD consensus close (rules.consensus; moneylines cleaned, spreads/totals at -110).
Writes one JSON doc per rule pick to out/<div>/ for the hub collection sports/<div>/backtest. Changes nothing else."""
import json, sys, copy, re
from pathlib import Path
import pandas as pd
import rules as RU, cfbdata
D = Path(__file__).parent
SIG = json.load(open(D / 'signals.json'))
import unicodedata
def slug(s): return re.sub(r'[^A-Za-z0-9]', '', unicodedata.normalize('NFKD', s))  # Nov 10: NFKD so San José State is SanJoseState, same as the ledger (B11)
def fl(v): return None if v is None else (int(v) if float(v).is_integer() else float(v))
# Usage: python3 backtest_nov7.py [fbs] [fcs] [--late finals.json]
#   --late finals.json: grade only the games listed there ({"<cfbd id>": [away_pts, home_pts], ...}) after injecting their
#   finals into repo/games.csv and repo/lines.csv copies; writes out_late/<div>/ and leaves out/ alone.
args = sys.argv[1:]; LATE = None
if '--late' in args:
    i = args.index('--late'); LATE = {int(k): v for k, v in json.load(open(args[i + 1])).items()}; del args[i:i + 2]
    import tempfile, shutil
    T = Path(tempfile.mkdtemp())
    for f in (D / 'repo').iterdir(): shutil.copy(f, T / f.name)
    g = pd.read_csv(T / 'games.csv'); l = pd.read_csv(T / 'lines.csv')
    for gid, (pa, ph) in LATE.items():
        g.loc[g.id == gid, ['awayPoints', 'homePoints', 'completed']] = [pa, ph, True]
        l.loc[l.id == gid, ['awayScore', 'homeScore']] = [pa, ph]
    g.to_csv(T / 'games.csv', index=False); l.to_csv(T / 'lines.csv', index=False)
    cfbdata.R = T
G = pd.read_csv(cfbdata.R / 'games.csv'); G = G[G.season == 2026].set_index('id')
summary = {}
for div in args or ['fbs', 'fcs']:
    META = json.load(open(D / f'hub_meta_{div}.json')); META = META.get('data', META)
    ON = {r['key']: r['on'] for r in META['rules']}
    TIER = {r['key']: r.get('tier') for r in META['rules']}
    LABEL = {r['key']: r['label'] for r in META['rules']}
    RULES = SIG['rules_' + div]
    names = [k for k in ON if k in RULES['side'] or k in RULES['total']]
    rows = [r for r in cfbdata.load(div, SIG) if r['y'] == 2026 and (LATE is None or r['id'] in LATE)]
    out = D / ('out_late' if LATE else 'out') / div; out.mkdir(parents=True, exist_ok=True)
    for f in out.glob('*.json'): f.unlink()
    recs = {}
    for name in names:
        Q = copy.deepcopy(RULES)
        for k in Q['side']: Q['side'][k]['on'] = (k == name)
        for k in Q['total']: Q['total'][k]['on'] = (k == name)
        for r in rows:
            side, tot, info = RU.decide(r, r['sideS'], r['totS'], Q)
            p = tot if name in RULES['total'] else side
            if not p or p['rule'] != name: continue
            if p['market'] == 'Moneyline' and r.get('ml_' + p['k']) is None: continue
            if p['market'] == 'Spread' and r.get('spread_h') is None: continue
            if p['market'] == 'Total' and r.get('total') is None: continue
            w, price = RU.grade(r, p)
            res = 'push' if w is None else ('win' if w else 'loss')
            units = round(RU.payout(w, price), 2)
            g = G.loc[r['id']]
            date = pd.Timestamp(g.startDate).tz_convert('America/Phoenix').strftime('%Y-%m-%d')
            a, h = r['a'], r['h']
            if p['market'] == 'Total':
                pick = f"{p['k']} {fl(r['total'])}"; line = fl(r['total']); team = None
            else:
                team = a if p['k'] == 'a' else h
                line = fl(-r['spread_h'] if p['k'] == 'a' else r['spread_h']) if r.get('spread_h') is not None else None
                pick = f"{team} ML" if p['market'] == 'Moneyline' else f"{team} {RU.fmt_line(line)}"
            sig_side = (r['totS'][p['k']] if p['market'] == 'Total' else r['sideS'][team])
            sig_other = (r['totS']['Under' if p['k'] == 'Over' else 'Over'] if p['market'] == 'Total' else r['sideS'][h if team == a else a])
            inputs = dict(spread_home_close=fl(r.get('spread_h')), spread_home_open=fl(r.get('open_h')), total_close=fl(r.get('total')),
                          total_open=fl(r.get('tot_open')), ml_away=r.get('ml_a'), ml_home=r.get('ml_h'),
                          signal_points_away=info['score_a'], signal_points_home=info['score_h'], lead=info['lead'],
                          favourite=(a if info['fav'] == 'a' else h) if info['fav'] else None,
                          signals_on_pick=[f"{s['key']} ({s['pts']})" for s in sig_side],
                          signals_against=[f"{s['key']} ({s['pts']})" for s in sig_other],
                          move_toward_away=fl(r.get('move_a')), reasons=p.get('reasons'),
                          rest_days=dict(away=r.get('rest_a'), home=r.get('rest_h')),
                          last_season=dict(away=list(r['last_a'][1:]) if r.get('last_a') else None, home=list(r['last_h'][1:]) if r.get('last_h') else None),
                          win_pct_this_season=dict(away=round(r['wp_a'], 3) if r.get('wp_a') is not None else None, home=round(r['wp_h'], 3) if r.get('wp_h') is not None else None),
                          action_network=bool(r.get('an')), line_source='CFBD consensus close')
            doc = dict(date=date, week=r['wk'], game=f'{a} @ {h}', away=a, home=h, market=p['market'], rule_key=name, rule=LABEL[name],
                       rule_on_now=ON[name], pick=pick, line=line, price=price, tier=TIER[name], final=f"{a} {int(r['pts_a'])}, {h} {int(r['pts_h'])}",
                       result=res, units=units, inputs=inputs, source='backtest Nov 7')
            did = f'{date}_{slug(a)}-{slug(h)}_{name}'
            json.dump(doc, open(out / f'{did}.json', 'w'), default=str)
            recs.setdefault(name, []).append(doc)
    S = {}
    for name in names:
        L = recs.get(name, [])
        def rr(x):
            w = sum(d['result'] == 'win' for d in x); l = sum(d['result'] == 'loss' for d in x); pu = sum(d['result'] == 'push' for d in x)
            return f"{w}-{l}" + (f"-{pu}" if pu else '') + f" {sum(d['units'] for d in x):+.2f}u"
        S[name] = dict(on=ON[name], season=rr(L), nov=rr([d for d in L if d['date'] >= '2026-11-01']), n=len(L))
    summary[div] = dict(games_played=len(rows), rules=S, docs=sum(len(v) for v in recs.values()))
print(json.dumps(summary, indent=1))
json.dump(summary, open(D / ('backtest_summary_late.json' if LATE else 'backtest_summary.json'), 'w'), indent=1)
