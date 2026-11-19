"""B85: first half lines from odds/read.py periods_now into t222_1h.txt (1000+rot), matched to t222_fbs.txt rows by name."""
import json, sys, difflib, re, unicodedata
rd = json.load(open(sys.argv[1])); rows = [r.split(',') for r in open(sys.argv[2]).read().split(';') if r.count(',') > 5]
def n(s): return re.sub(r'[^a-z ]', '', unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower().replace('state', 'st').replace("'", ''))
AL = {'app st': 'appalachian st'}
def m(c, f):
    c, f = n(c), n(f); c = AL.get(c, c)
    return 1.0 if f.startswith(c + ' ') else difflib.SequenceMatcher(None, c, f[:len(c) + 3]).ratio()
def p(x): return f'+{x:g}' if x > 0 else (f'{x:g}' if x else 'PK')
def pr(x): return f'+{int(x)}' if x > 0 else str(int(x))
out = []; miss = []
pairs = [(rows[i], rows[i + 1]) for i in range(0, len(rows) - 1, 2)]
for a, h in pairs:
    best = None
    for k, g in rd.items():
        s = m(a[3], g['away']) + m(h[3], g['home'])
        if not best or s > best[0]: best = (s, g)
    if not best or best[0] < 1.5: miss.append(a[3] + '@' + h[3]); continue
    h1 = (best[1].get('periods_now') or {}).get('h1')
    if not h1 or h1.get('spread_home') is None: miss.append(a[3] + '@' + h[3] + ' (no 1H)'); continue
    ra, rh = 1000 + int(a[2]), 1000 + int(h[2])
    out.append(f"{ra},1H,{p(-h1['spread_home'])}{pr(h1['spread_away_price'])},Ov{h1['total']:g}{pr(h1['over_price'])},{pr(h1['ml_away']) if h1.get('ml_away') else ''}")
    out.append(f"{rh},1H,{p(h1['spread_home'])}{pr(h1['spread_home_price'])},Un{h1['total']:g}{pr(h1['under_price'])},{pr(h1['ml_home']) if h1.get('ml_home') else ''}")
open(sys.argv[3], 'w').write(';'.join(out)); print(len(out) // 2, 'games with 1H;', 'missing:', miss)
