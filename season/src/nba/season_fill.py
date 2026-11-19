"""Append finished days to the NBA season files from the repo only (no Chrome): ESPN finals + Odds API open/close (median of books).
an_odds rows get neutral splits (no Action Network read), marked N0. espn_odds O/C = Odds API open/close (second source label 'OddsAPI')."""
import sys, gzip, json, os
repo, W = sys.argv[1], sys.argv[2]; days = sys.argv[3:]
sys.path.insert(0, repo + '/odds'); import read as R
sys.path.insert(0, W); from teams import FULL
INV = {v: k for k, v in FULL.items()}
MAP = {'NY': 'NYK', 'SA': 'SAS', 'UTAH': 'UTA', 'NO': 'NOP', 'GS': 'GSW', 'WSH': 'WAS'}
S = W + '/season/'
def pr(x): return ('+%d' % x) if x > 0 else '%d' % x
def blk(g, home_ml_sign=True):
    return f"{-g['spread_home']:g},{pr(g['spread_away_price'])},{pr(g['spread_home_price'])},{g['total']:g},{pr(g['over_price'])},{pr(g['under_price'])},{pr(g['ml_away'])},{pr(g['ml_home'])}"
for day in days:
    md = day[5:7] + day[8:10]
    j = json.load(gzip.open(f'{repo}/season/data/espn/nba/{day}/scoreboard_final.json.gz'))
    G = R.build('nba', day); nick = {v.split()[-1]: k for k, v in FULL.items()}; byteam = {(nick.get(e['away'].split()[-1]), nick.get(e['home'].split()[-1])): e for e in G.values()}
    eo, ls, an = [], [], []
    for e in j['events']:
        c = e['competitions'][0]
        if c['status']['type']['state'] != 'post': continue
        t = {x['homeAway']: x for x in c['competitors']}
        A, H = t['away']['team']['abbreviation'], t['home']['team']['abbreviation']
        a, h = MAP.get(A, A), MAP.get(H, H); ap, hp = int(t['away']['score']), int(t['home']['score'])
        qa = [int(l['value']) for l in t['away'].get('linescores', [])]; qh = [int(l['value']) for l in t['home'].get('linescores', [])]
        ls.append(f"{md}|{A}|{H}|{ap}|{hp}|{','.join(map(str, qa))}|{','.join(map(str, qh))}")
        o = byteam.get((a, h))
        if o and o.get('open') and (o.get('close') or o.get('now')):
            cl = o.get('close') or o.get('now')
            try:
                eo.append(f"{day}|{A}|{H}|{ap}|{hp}|{e['id']}|100~{blk(o['open'])}~{blk(cl)}")
                an.append(f"{day}|{a}|{h}|{ap}|{hp}|complete|S50/50;M50/50;O50/50;N0|O~{blk(o['open'])}|MED7~{blk(cl)}")
            except Exception as ex: print('odds skip', a, h, ex)
        else: print('no odds', day, a, h)
    def app(fn, new):
        txt = open(S + fn).read(); have = {'|'.join(l.split('|')[:3]) for l in txt.splitlines() if '|' in l}
        lines = [x for x in new if '|'.join(x.split('|')[:3]) not in have]
        if lines: open(S + fn, 'a').write(('' if txt.endswith('\n') else '\n') + '\n'.join(lines) + '\n')
        print(day, fn, len(lines))
    app('espn_odds.txt', eo); app('linescores.txt', ls); app('an_odds.txt', an)
