"""Append yesterday's finished games to the season dataset (Nov 14 version, parameterized).
python3 season_add.py <YYYY-MM-DD> <espn compact file> <action network rows file> <cfb-card clone>
espn compact: F|id|date|AWAY|score|linescores|HOME|score|linescores|status|state and O|id|{"o":[...],"c":[...]} (ESPN core odds, DraftKings).
Period lines: Odds API close_periods median line, else the latest pre-tip now_periods read."""
import json, gzip, csv, glob, collections, sys, os
D = os.path.dirname(os.path.abspath(__file__)); S = D + '/season/'
day, ef, af, repo = sys.argv[1:5]; md = day[5:7] + day[8:10]
sys.path.insert(0, D); from teams import FULL
MAP = {'NY': 'NYK', 'SA': 'SAS', 'UTAH': 'UTA', 'NO': 'NOP', 'GS': 'GSW', 'WSH': 'WAS'}
E = [l.split('|') for l in open(ef).read().splitlines()]
OD = {f[1]: json.loads(f[2]) for f in E if f[0] == 'O'}
rows = []
for kind in ('close_periods', 'now_periods'):
    for f in glob.glob(f'{repo}/odds/data/nba/{day}/{kind}*.csv.gz'):
        rows += [dict(r, kind=kind) for r in csv.DictReader(gzip.open(f, 'rt')) if r['snap'] <= r['commence']]
last = {}
for r in rows:
    k = (r['kind'], r['away'], r['home'], r['book'], r['market'], r['outcome'])
    if k not in last or r['snap'] > last[k]['snap']: last[k] = r
def medpt(a, h, mk, oc):
    for kind in ('close_periods', 'now_periods'):
        L = [float(r['point']) for k, r in last.items() if k[0] == kind and k[1] == a and k[2] == h and k[4] == mk and k[5] == oc and r['point']]
        if L: return '%g' % collections.Counter(L).most_common(1)[0][0]
    return ''
eo, ls, pl, an = (open(S + f).read() for f in ('espn_odds.txt', 'linescores.txt', 'plines.txt', 'an_odds.txt'))
add_eo, add_ls, add_pl = [], [], []
for f in E:
    if f[0] != 'F' or f[10] != 'post': continue
    _, i, d, A, ap, al, H, hp, hl, st, state = f
    j = OD.get(i)
    if j: add_eo.append(f"{day}|{A}|{H}|{ap}|{hp}|{i}|100~{','.join(j['o'])}~{','.join(j['c'])}")
    qa = [int(float(x)) for x in al.split(',')]; qh = [int(float(x)) for x in hl.split(',')]
    add_ls.append(f"{md}|{A}|{H}|{ap}|{hp}|{','.join(map(str, qa))}|{','.join(map(str, qh))}")
    a, h = MAP.get(A, A), MAP.get(H, H); fa, fh = FULL[a], FULL[h]
    add_pl.append(f"{day[5:]}|{a}|{h}|{medpt(fa, fh, 'spreads_h1', fa)},{medpt(fa, fh, 'totals_h1', 'Over')}|{medpt(fa, fh, 'spreads_q1', fa)},{medpt(fa, fh, 'totals_q1', 'Over')}|{qa[0]},{qh[0]};{qa[0]+qa[1]},{qh[0]+qh[1]}")
def app(fn, txt, new):
    have = {'|'.join(l.split('|')[:3]) for l in txt.splitlines() if '|' in l}
    lines = [x for x in new if '|'.join(x.split('|')[:3]) not in have]
    if lines: open(S + fn, 'a').write(('' if txt.endswith('\n') else '\n') + '\n'.join(lines) + '\n')
    print(fn, len(lines))
app('espn_odds.txt', eo, add_eo); app('linescores.txt', ls, add_ls); app('plines.txt', pl, add_pl); app('an_odds.txt', an, open(af).read().strip().splitlines())
print(add_pl)
