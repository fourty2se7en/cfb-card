"""Hub meta ncaam and standings ncaam for the Nov 7 run (reads extras outputs, rules_state_M.json, the season files)."""
import json, pathlib, glob, runpy, sys, datetime
D = pathlib.Path(__file__).parent; W = D.parent; OUT = W/'out'/'hubw'; import sys as _s; DATE = _s.argv[1] if len(_s.argv) > 1 else '2026-11-07'; YD = _s.argv[2] if len(_s.argv) > 2 else '20261106'; NOTE = _s.argv[3] if len(_s.argv) > 3 else ''
ST = json.loads((D/'rules_state_M.json').read_text())['rules']
meta = json.load(open(W/'hub'/'meta'/'ncaam.json')); meta = meta.get('data', meta)
LED = [json.load(open(f)) for f in glob.glob(str(W/'hub'/'ledger'/'sports'/'ncaam'/'picks'/'*.json'))]
import rules as R
def rs(s): return f"{s['w']}-{s['l']}" + (f"-{s['p']}" if s.get('p') else '') + f" {s['u'] + 0.0:+.2f}u"
for r in meta['rules']:
    if r['key'] not in ST: continue   # Nov 12 model rules keep their own meta records
    s = ST[r['key']]; r['on'] = s['on']; r['version'] = s['variant']
    r['season'] = {k: s['season'][k] + (0.0 if k == 'u' else 0) for k in 'wlpu'}
    r['month'] = (dict({k: s['month'][k] + (0.0 if k == 'u' else 0) for k in 'wlpu'}, label='Nov') if s['month']['n'] else None)
    r['every_game'] = rs(s['season'])
    rows = [(1 if x['result'] == 'win' else (-1 if x['result'] == 'loss' else 0), x['price']) for x in LED if not x.get('shadow') and x.get('rule') == r['key'] and x.get('result') in ('win', 'loss', 'push')]
    if rows or 'card' in r: r['card'] = rs(R.summarize(rows))
    if r['key'] in ('EARLY_UNDER_OPEN', 'EARLY_OVER_OPEN'): r['graded_at'] = 'closing line (Trina, Nov 7; was the opener)'
def _us(x):
    if isinstance(x, str): return x.replace('Favourite', 'Favorite').replace('favourite', 'favorite').replace('travelled', 'traveled')
    if isinstance(x, list): return [_us(v) for v in x]
    if isinstance(x, dict): return {k: (_us(v) if k not in ('tiers', 'retier', 'policy') else v) for k, v in x.items()}
    return x
meta['rules'] = [_us(r) for r in meta['rules']]; meta['how'] = _us(meta.get('how', []))   # B24, US English
meta['updated'] = DATE
meta['notes'] = meta['notes'] + ' ' + NOTE
json.dump(meta, open(OUT/'meta.json', 'w'), indent=1)
# standings
sd = json.load(open(W/'hub'/'standings'/'ncaam.json')); sd = sd.get('data', sd)
games = json.load(open(OUT/'games_today.json'))
REC, CONFT, NAME = {}, {}, {}
for g in games:
    for s in ('away', 'home'):
        t = g['data'][s]; REC[t['code']] = t.get('record'); CONFT[t['code']] = t['conference']; NAME[t['code']] = t.get('name', t['code'])
LOG = {}
for x in (D/'season'/'games_M.txt').read_text().strip().splitlines():
    r = json.loads(x); m = r[12] - r[13]
    LOG.setdefault(r[3], []).append((r[2], m)); LOG.setdefault(r[4], []).append((r[2], -m))
Y = {}
for l in (W/'data'/'raw'/f'y_{YD}.txt').read_text().strip().splitlines():
    f = l.split('|')
    if f[0] == 'M': Y[f[2]] = int(f[10]) > int(f[11]); Y[f[3]] = int(f[11]) > int(f[10])
def l5(c):
    L = sorted(LOG.get(c, []))[-5:]
    if not L: return None, None
    seq = ['W' if m > 0 else 'L' for _, m in L]; n = 0
    for v in reversed(seq):
        if v == seq[-1]: n += 1
        else: break
    return ''.join(seq), f"{seq[-1]}{n}"
def bump(rec, won):
    try: w, l = map(int, rec.split('-'))
    except Exception: return rec
    return f"{w + 1}-{l}" if won else f"{w}-{l + 1}"
seen = set()
for grp in sd['groups']:
    for row in grp['rows']:
        c = row['code']; v = row['values']; key = 'Overall' if grp['kind'] == 'conference' else 'Record'
        if c in REC and REC[c]: v[key] = REC[c]
        elif c in Y and v.get(key): v[key] = bump(v[key], Y[c])
        if grp['kind'] == 'conference':
            seen.add(c); a, b = l5(c)
            if a: v['Last 5'] = a; v['Streak'] = b
    if grp['kind'] == 'conference':
        for c, cf in CONFT.items():
            if cf == grp['name'] and c not in seen and c not in {r['code'] for r in grp['rows']}:
                a, b = l5(c); vals = {k: x for k, x in {'Overall': REC.get(c), 'Last 5': a, 'Streak': b}.items() if x}
                grp['rows'].append(dict(team=NAME[c], code=c, values=vals, mark=None)); seen.add(c)
        grp['rows'].sort(key=lambda r: r['team'])
sd['updated'] = DATE
json.dump(sd, open(OUT/'standings.json', 'w'))
print('meta and standings written', sum(len(g['rows']) for g in sd['groups']))
