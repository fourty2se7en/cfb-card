"""parsed.json (T, V, A, LOG) for extra_hub.py from the cfb-card repo ESPN files plus earlier runs' LOG lines and box_W rows."""
import gzip, json, glob, sys
R = '/home/claude/cfb-card/season/data/espn/ncaaw'; W = '/home/claude/runs16/ncaaw'
ev = json.load(gzip.open(f'{R}/2026-11-16/scoreboard.json.gz'))['events']
T, V = [], []; scope = set()
ap = json.load(open(f'{W}/w/data/ap_poll.json'))['W']; AP = {x['team'] for x in ap}
for e in ev:
    c = e['competitions'][0]; C = {x['homeAway']: x for x in c['competitors']}
    ven = c.get('venue') or {}; ad = ven.get('address') or {}
    V.append(f"{e['id']}~{ven.get('fullName','')}~{ad.get('city','')} {ad.get('state','')}~{'Neutral site' if c.get('neutralSite') else ''}")
    rk = lambda x: (x.get('curatedRank') or {}).get('current', 99) or 99
    if rk(C['home']) <= 25 or rk(C['away']) <= 25: scope |= {C['home']['team']['abbreviation'], C['away']['team']['abbreviation']}
    for x in c['competitors']:
        t = x['team']; recs = {r.get('type') or r.get('name'): r.get('summary') for r in x.get('records', [])}
        T.append(f"{t['abbreviation']}~{t.get('displayName')}~{t.get('shortDisplayName')}~{t.get('color','')}~t:{recs.get('total','0-0')},h:{recs.get('home','0-0')},r:{recs.get('road', recs.get('away','0-0'))},v:0-0")
# LOG: earlier runs' lines (quarters) + Nov 11 from the repo final scoreboard + box_W fallback
L = {}
for f in glob.glob(f'{W}/r11*/pull/parsed.json') + glob.glob(f'{W}/pull/parsed.json'):
    for l in json.load(open(f)).get('LOG', []):
        if l.strip() and not l.split('|')[1].startswith('bx'): L[l.split('|')[1]] = l
for f in glob.glob(f'{W}/r11*/pull/LOG.txt') + glob.glob(f'{W}/pull/LOG.txt'):
    for l in open(f).read().split('\n'):
        if l.strip(): L[l.split('|')[1]] = l
for d in sorted(glob.glob(f'{R}/*/scoreboard_final.json.gz')):
    for e in json.load(gzip.open(d))['events']:
        c = e['competitions'][0]
        if not c['status']['type'].get('completed'): continue
        C = {x['homeAway']: x for x in c['competitors']}; h, a = C['home'], C['away']
        q = lambda x: ','.join(str(int(float(l['value']))) for l in x.get('linescores', []))
        rk = lambda x: str((x.get('curatedRank') or {}).get('current')) if (x.get('curatedRank') or {}).get('current', 99) < 99 else ''
        L[e['id']] = '|'.join([e['date'][:10].replace('-', '') if False else d.split('/')[-2].replace('-', ''), e['id'], h['team']['abbreviation'], a['team']['abbreviation'], str(h['score']), str(a['score']), '1' if c.get('neutralSite') else '0', q(h), q(a), rk(h), rk(a)])
have = {(l.split('|')[0], l.split('|')[2], l.split('|')[3]) for l in L.values()}
n_fb = 0
for l in open(f'{W}/w/src/season/box_W.txt'):
    r = json.loads(l); k = (r[1], r[2], r[3])
    if k in have or not (r[2] in scope or r[3] in scope): continue
    L[f'bx{r[1]}{r[2]}{r[3]}'] = '|'.join([r[1], f'bx{r[1]}{r[2]}{r[3]}', r[2], r[3], str(r[6]), str(r[7]), str(r[4]), '', '', '', '']); n_fb += 1
LOG = [l for l in L.values() if l.split('|')[2] in scope or l.split('|')[3] in scope]
A = [';'.join(f"{x['rank']}:{x['team']}" for x in ap)]
json.dump(dict(T=T, V=V, A=A, LOG=sorted(LOG)), open(sys.argv[1], 'w'))
print('T', len(T), 'V', len(V), 'LOG', len(LOG), 'box fallback', n_fb, 'scope teams', len(scope))
cnt = {t: sum(1 for l in LOG if t in l.split('|')[2:4]) for t in scope}; print(sorted(cnt.items(), key=lambda x: x[1])[:12])
