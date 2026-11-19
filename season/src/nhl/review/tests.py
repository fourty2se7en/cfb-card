"""Pick-method tests a to f on every game played this season (season to date, each month, last 14 days), used by the
daily re-check. Same signal scoring as the card (../rules.py). Imported by recheck.py; run alone to print the tables."""
import json, sys, pathlib, datetime
from collections import OrderedDict
R = pathlib.Path(__file__).parent; sys.path.insert(0, str(R.parent)); sys.path.insert(0, str(R))
import rules
from build_data import ok, dec, novig_home
from engine import build_all
import rscore

GAMES = build_all(json.load(open(R/'games.json')))
AS_OF = max(g['date'] for g in GAMES)
L14 = (datetime.date.fromisoformat(AS_OF) - datetime.timedelta(days=13)).isoformat()
rows = []
for g in GAMES:
    c = rscore.ctx_from_rebuild(g)
    if c: rows.append(dict(g=g, c=c, r=rules.score(c)))
CHECKS = {}

def month(d): return rules.month_of(d)
MONTHS = []
for x in rows:
    m = month(x['g']['date'])
    if m not in MONTHS: MONTHS.append(m)

def res_side(g, side):
    return (g['ag'] > g['hg']) if side == 'A' else (g['hg'] > g['ag'])
def ML(x, side, price=None):
    c = x['c']; p = price if price is not None else (c['mla'] if side == 'A' else c['mlh'])
    return dict(date=x['g']['date'], price=p, res='W' if res_side(x['g'], side) else 'L', key=(x['g']['date'], x['g']['a'], x['g']['h']), mk='ML', side=side)
def PL(x, side, price=None, sp=None):
    c = x['c']; pl = c.get('pl')
    if not pl: return None
    s = sp if sp is not None else (pl['sp_a'] if side == 'A' else -pl['sp_a'])
    p = price if price is not None else (pl['price_a'] if side == 'A' else pl['price_h'])
    g = x['g']; m = (g['ag']-g['hg']) if side == 'A' else (g['hg']-g['ag'])
    return dict(date=g['date'], price=p if ok(p) else -110, res='W' if m + s > 0 else 'L', key=(g['date'], g['a'], g['h']), mk='PL', side=side, sp=s)
def TOT(x, side, line=None, price=None):
    c = x['c']
    if c.get('line') is None: return None
    ln = line if line is not None else c['line']
    p = price if price is not None else (c['tprice'][0] if side == 'O' else c['tprice'][1])
    t = x['g']['ag'] + x['g']['hg']
    r = 'P' if t == ln else ('W' if (t > ln) == (side == 'O') else 'L')
    return dict(date=x['g']['date'], price=p if ok(p) else -110, res=r, key=(x['g']['date'], x['g']['a'], x['g']['h']), mk='TOT', side=side)

def agg(bb):
    w = sum(b['res'] == 'W' for b in bb); l = sum(b['res'] == 'L' for b in bb); p = sum(b['res'] == 'P' for b in bb)
    u = sum((dec(b['price'])-1) if b['res'] == 'W' else (-1 if b['res'] == 'L' else 0) for b in bb)
    gr = [b for b in bb if b['res'] != 'P']
    be = len(gr)/sum(dec(b['price']) for b in gr) if gr else None
    return dict(w=w, l=l, p=p, n=w+l, wp=(w/(w+l)) if w+l else None, u=round(u, 2), be=be)
def summ(bb):
    bb = [b for b in bb if b]
    o = OrderedDict(season=agg(bb))
    for m in MONTHS: o[m] = agg([b for b in bb if month(b['date']) == m])
    o['L14'] = agg([b for b in bb if b['date'] >= L14])
    s = o['season']
    o['qual'] = bool(s['n'] >= 5 and s['u'] > 0 and s['wp'] > s['be'])
    o['strict'] = bool(s['n'] >= 30 and s['u'] > 0 and s['wp'] > s['be'] and all(o[m]['u'] >= 0 for m in MONTHS if o[m]['n'] >= 5))
    return o

RES = OrderedDict(); BETS = {}
def T(sec, name, bb):
    bb = [b for b in bb if b]; o = summ(bb); RES.setdefault(sec, []).append((name, o)); BETS[(sec, name)] = bb; return o

def fav_of(c):
    if c['mlh'] < c['mla']: return 'H'
    if c['mla'] < c['mlh']: return 'A'
    return None
def other(s): return {'A': 'H', 'H': 'A', 'O': 'U', 'U': 'O'}[s]
def sigs_on(x, side):
    return sorted({s for s, m, sd, p, n in x['r']['S'] if sd == side and s not in ('Line move with the public',)})

# ---------- a. favorite moneyline
FB = [('shorter than -500', -10**6, -501), ('-500 to -301', -500, -301), ('-300 to -201', -300, -201), ('-200 to -100', -200, -100)]
for lab, lo, hi in FB:
    ev, ag = [], []
    for x in rows:
        f = fav_of(x['c'])
        if not f: continue
        p = x['c']['mlh'] if f == 'H' else x['c']['mla']
        if not lo <= p <= hi: continue
        ev.append(ML(x, f))
        if x['r']['side'] == f: ag.append(ML(x, f))
    T('a. Favorite moneyline', f'{lab}: every favorite', ev)
    T('a. Favorite moneyline', f'{lab}: signals agree', ag)
for k, lab in ((1, 'lead 1'), (2, 'lead 2'), (3, 'lead 3+')):
    bb = []
    for x in rows:
        f = fav_of(x['c']); r = x['r']
        if not f or r['side'] != f: continue
        p = x['c']['mlh'] if f == 'H' else x['c']['mla']
        if not -200 <= p <= -100: continue
        if (r['ml_lead'] == k) if k < 3 else (r['ml_lead'] >= 3): bb.append(ML(x, f))
    T('a. Favorite moneyline', f'-200 to -100, signals agree, {lab}', bb)

# ---------- b. underdog moneyline
DB = [('+100 to +150', 100, 150), ('+151 to +200', 151, 200), ('+201 to +300', 201, 300), ('+301 to +500', 301, 500), ('+501 and up', 501, 10**6),
      ('+100 to +200', 100, 200), ('+100 to +300', 100, 300), ('+100 and up', 100, 10**6)]
def dog_of(c):
    f = fav_of(c)
    if not f: return None
    d = other(f); p = c['mla'] if d == 'A' else c['mlh']
    return d if p >= 100 else None
for lab, lo, hi in DB:
    ev, on, onr = [], [], []
    for x in rows:
        d = dog_of(x['c'])
        if not d: continue
        p = x['c']['mla'] if d == 'A' else x['c']['mlh']
        if not lo <= p <= hi: continue
        ev.append(ML(x, d))
        if x['r']['side'] == d:
            on.append(ML(x, d))
            if x['r']['rlm'] == d: onr.append(ML(x, d))
    T('b. Underdog moneyline', f'{lab}: every underdog', ev)
    T('b. Underdog moneyline', f'{lab}: signals on the dog', on)
    T('b. Underdog moneyline', f'{lab}: signals on the dog + line moved to it against the tickets', onr)
# lead split for the locked band
for k, lab in ((1, 'lead 1'), (2, 'lead 2'), (3, 'lead 3+')):
    bb = []
    for x in rows:
        d = dog_of(x['c']); r = x['r']
        if not d or r['side'] != d: continue
        p = x['c']['mla'] if d == 'A' else x['c']['mlh']
        if not 100 <= p <= 200: continue
        if (r['ml_lead'] == k) if k < 3 else (r['ml_lead'] >= 3): bb.append(ML(x, d))
    T('b. Underdog moneyline', f'+100 to +200, signals on the dog, {lab}', bb)

# ---------- c. underdog puck line (+1.5)
NAMES = set()
for x in rows:
    for s, m, sd, p, n in x['r']['S']: NAMES.add(s)
NAMES.discard('Line move with the public')
pc = {}
allc = []
for x in rows:
    d = dog_of(x['c'])
    if not d or x['r']['side'] != d: continue
    b = PL(x, d); allc.append(b)
    for s in sigs_on(x, d): pc.setdefault(s, []).append(b)
T('c. Underdog puck line +1.5', 'signals on the dog', allc)
for s in sorted(pc): T('c. Underdog puck line +1.5', f'signals on the dog, with {s}', pc[s])

# ---------- d. puck line on the signal side
def favsize(c):
    f = fav_of(c)
    if not f: return 'pick em'
    p = c['mlh'] if f == 'H' else c['mla']
    return '-100 to -150' if p >= -150 else ('-151 to -200' if p >= -200 else 'shorter than -200')
for k in range(1, 7):
    bb = [PL(x, x['r']['side']) for x in rows if (x['r']['ml_lead'] == k if k < 6 else x['r']['ml_lead'] >= 6)]
    T('d. Puck line on the signal side', f'lead {k}{"+" if k == 6 else ""}', bb)
for k in (1, 2, 3, 4, 5):
    bb = [PL(x, x['r']['side']) for x in rows if x['r']['ml_lead'] >= k]
    T('d. Puck line on the signal side', f'lead {k}+', bb)
for role in ('favorite -1.5', 'underdog +1.5'):
    for k in (1, 3, 5):
        bb = []
        for x in rows:
            f = fav_of(x['c']); s = x['r']['side']
            if not f or x['r']['ml_lead'] < k: continue
            if (s == f) == (role.startswith('fav')): bb.append(PL(x, s))
        T('d. Puck line on the signal side', f'{role}, lead {k}+', bb)
for sz in ('-100 to -150', '-151 to -200', 'shorter than -200'):
    for role in ('favorite -1.5', 'underdog +1.5'):
        bb = []
        for x in rows:
            f = fav_of(x['c']); s = x['r']['side']
            if not f or favsize(x['c']) != sz or x['r']['ml_lead'] < 1: continue
            if (s == f) == role.startswith('fav'): bb.append(PL(x, s))
        T('d. Puck line on the signal side', f'favorite {sz}: {role}, lead 1+', bb)

# ---------- e. totals
tr = [x for x in rows if x['c'].get('line') is not None and 'T' in x['r']]
T('e. Totals', 'always over', [TOT(x, 'O') for x in tr])
T('e. Totals', 'always under', [TOT(x, 'U') for x in tr])
TN = sorted({s for x in tr for s, m, sd, p, n in x['r']['T']})
for s in TN:
    for sd in ('O', 'U'):
        bb = [TOT(x, sd) for x in tr if any(a == s and b == sd for a, m, b, p, n in x['r']['T'])]
        if bb: T('e. Totals', f'{s} on the {"over" if sd == "O" else "under"}', bb)
for k in (1, 2, 3):
    T('e. Totals', f'over, signal lead {k}+', [TOT(x, 'O') for x in tr if x['r']['tside'] == 'O' and x['r']['t_lead'] >= k])
    T('e. Totals', f'under, signal lead {k}+', [TOT(x, 'U') for x in tr if x['r']['tside'] == 'U' and x['r']['t_lead'] >= k])
for s in ('Money % above ticket %', 'Action Network PRO Systems', 'Action Network Sharp Action'):
    alone, withx = [], []
    for x in tr:
        hit = [b for a, m, b, p, n in x['r']['T'] if a == s]
        if not hit: continue
        sd = hit[0]; others = [a for a, m, b, p, n in x['r']['T'] if a != s and b == sd]; against = [a for a, m, b, p, n in x['r']['T'] if b != sd]
        if not others and not against: alone.append(TOT(x, sd))
        if others: withx.append(TOT(x, sd))
    T('e. Totals', f'{s} alone (no other totals signal)', alone)
    T('e. Totals', f'{s} with another signal on the same side', withx)

# ---------- f. every signal on its own (moneyline and puck line on that side)
for s in sorted(NAMES):
    mlb, plb = [], []
    for x in rows:
        sd = [b for a, m, b, p, n in x['r']['S'] if a == s]
        if not sd: continue
        mlb.append(ML(x, sd[0])); plb.append(PL(x, sd[0]))
    T('f. Every signal on its own', f'{s}: moneyline', mlb)
    T('f. Every signal on its own', f'{s}: puck line', plb)
for name in ('Sharp Action', 'Big Money', 'PRO Systems'):
    bb = []
    for x in rows:
        for nm, sd in (x['g'].get('sh_pl') or {}).items():
            if nm == name: bb.append(PL(x, sd))
    T('f. Every signal on its own', f'Action Network {name} lit on the puck line market: puck line', bb)
    bb = []
    for x in rows:
        for nm, sd in (x['g'].get('sh_pl') or {}).items():
            if nm == name: bb.append(ML(x, sd))
    T('f. Every signal on its own', f'Action Network {name} lit on the puck line market: moneyline', bb)

def cell(a):
    if not a['n'] and not a['p']: return '0'
    if not a['n']: return f"0-0-{a['p']}"
    return f"{a['w']}-{a['l']}" + (f"-{a['p']}" if a['p'] else '') + f" {100*a['wp']:.0f}% {a['u']:+.1f}u"
if __name__ == '__main__':
    for sec in RES:
        print('\n##', sec)
        for n, o in RES[sec]:
            s = o['season']
            if s['n']: print(f"  {'*' if o['qual'] else ' '} {n}: {cell(s)} be {100*s['be']:.1f}%  " + ' '.join(f"{m} {cell(o[m])}" for m in MONTHS) + f"  L14 {cell(o['L14'])}")
