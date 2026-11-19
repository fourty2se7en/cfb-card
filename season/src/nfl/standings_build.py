import json, sys
S = json.load(open('slate.json')); O = json.load(open(sys.argv[1]))
from hub_build import NAMES
g = {x['name']: x for x in O['groups']}
dt = sorted(S['divt'].items(), key=lambda kv: -kv[1]['adj'])
g['Division strength']['rows'] = [dict(team=d, values={'#': str(i+1), 'Out of div.': v['rec'], 'Win %': f"{v['pct']:.3f}", 'Adjusted': f"{v['adj']:.3f}",
    'PF/G': f"{v['pf']:.1f}", 'PA/G': f"{v['pa']:.1f}", 'Record vs each division': ', '.join(f'{k}: {r}' for k, r in sorted(v['vs'].items()))}) for i, (d, v) in enumerate(dt)]
g['AFC vs NFC']['rows'] = [dict(team=c, values={'Record': v['rec'], 'Win %': f"{v['pct']:.3f}", 'Adjusted': f"{v['adj']:.3f}", 'PF/G': f"{v['pf']:.1f}", 'PA/G': f"{v['pa']:.1f}"}) for c, v in S['conft'].items()]
for dv in sorted(set(v['div'] for v in S['stand'].values())):
    rows = sorted([v for v in S['stand'].values() if v['div'] == dv], key=lambda v: (-v['pct'], -(v['pf'] - v['pa'])))
    g[dv]['rows'] = [dict(code=v['team'], team=NAMES[v['team']], values={'#': i+1, 'W-L': f"{v['w']}-{v['l']}" + (f"-{v['t']}" if v['t'] else ''), 'Pct': round(v['pct'], 3),
        'PF': v['pf'], 'PA': v['pa'], 'Diff': f"{v['pf']-v['pa']:+d}", 'Home': v['home'], 'Road': v['road'], 'Div': v['divrec'], 'Conf': v['confrec'],
        'Strk': (f"W{v['strk']}" if v['strk'] > 0 else f"L{-v['strk']}" if v['strk'] < 0 else '-'), 'Last 5': v['last5'], 'Rating': f"{v['rating']:+.1f}", 'Rank': v['rank'], 'Elo': v['elo']}) for i, v in enumerate(rows)]
ex = sorted([e for e in S['exrec'] if e['n'] >= 1], key=lambda e: (-e['weight'], -e['shr'], -e['n']))
g['Expert leaderboard']['rows'] = [dict(team=e['name'], values={'W': str(e['w']), 'L': str(e['l']), 'Graded': str(e['n']), 'Shrunk': f"{e['shr']:.3f}", 'Weight': f"{e['weight']:.3f}"}) for e in ex]
O['groups'] = [g[x['name']] for x in O['groups']]; import datetime as _dt; O['updated'] = _dt.date.today().isoformat(); O['week'] = S['week']
json.dump(O, open('hub_out/standings/nfl.json', 'w')); print('ok', len(O['groups']), [r['values']['W-L'] for r in g['AFC North']['rows']])
