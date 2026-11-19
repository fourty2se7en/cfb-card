"""Season backtest (Nov 7, 2026): every rule, on or off, applied to every lined game this season, graded at the closing line.
Usage: [RATINGS=path] python3 backtest.py M|W <hub meta json> <build.py with AN_ALIAS>...  -> out_<LG>.json (one doc per rule pick) and prints records."""
import json, sys, pathlib, datetime, ast, re
import os
# Layout (same as the daily runs): ROOT/src (rules.py, eff.py, season/), ROOT/data (ratings, eff priors, raw/), this file in ROOT/src/backtest/.
ROOT = pathlib.Path(os.environ.get('ROOT') or pathlib.Path(__file__).resolve().parent.parent.parent)
sys.path.insert(0, str(ROOT/'src'))
import rules as R, eff as EF
B = ROOT; OUT = pathlib.Path.cwd(); LG = sys.argv[1]
META = json.load(open(sys.argv[2])); META = META.get('data', META)
RS = {r['key']: r for r in META['rules']}
VAR = {k: (v.get('version') or 'lowered') for k, v in RS.items()}
ON = {k: bool(v.get('on')) for k, v in RS.items()}
I = dict(lg=0, se=1, d=2, h=3, a=4, hc=5, ac=6, cg=7, nu=8, hr=10, ar=11, hs=12, as_=13, vs=17, dko=18, dkc=19, dkto=20, dktc=21, s2o=22, s2c=23, s2to=24, s2tc=25, sp=26, tot=27, mlh=28, mla=29)
RAT_LAST = {}
RATF = os.environ.get('RATINGS') or str(B/'data'/f'ratings_{LG.lower()}_2025-26.txt')   # optional override; data/ratings_w_2025-26.txt is the full 363-team rebuild since Nov 7
for tok in pathlib.Path(RATF).read_text().strip().split(';'):
    f = tok.split(','); RAT_LAST[f[0]] = float(f[1]) if f[1] not in ('undefined', '') else 0.0
# ---- Action Network ticket splits (men only; saved per date)
AN_ALIAS = {}
for src in sys.argv[3:]:
    tree = ast.parse(open(src).read())
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(getattr(t, 'id', '') == 'AN_ALIAS' for t in n.targets): AN_ALIAS.update(ast.literal_eval(n.value))
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and getattr(n.value.func, 'attr', '') == 'update' and getattr(n.value.func.value, 'id', '') == 'AN_ALIAS':
            AN_ALIAS.update(ast.literal_eval(n.value.args[0]))
ANF = {'20261102': 'an_m_20261102.txt', '20261103': 'an_m_20261103.txt', '20261104': 'an_m_20261104.txt', '20261105': 'an_m_20261105.txt', '20261106': 'an_m_20261106.txt', '20261107': 'an_m_20261107_0930.txt', '20261108': 'an_m_20261108.txt'}
TIX = {}
if LG == 'M':
    for d, fn in ANF.items():
        p = B/'data'/'raw'/fn
        if not p.exists(): continue
        for l in p.read_text().splitlines():
            f = l.split('|')
            if len(f) < 7 or not f[3].endswith('%'): continue
            a, h = AN_ALIAS.get(f[0]), AN_ALIAS.get(f[1])
            if a and h: TIX[(d, a, h)] = (int(f[3][:-1]), int(f[4][:-1]), int(f[5][:-1]) if f[5] else None, int(f[6][:-1]) if f[6] else None)
def load():
    out = []
    for ln in (B/'src'/'season'/f'games_{LG}.txt').read_text().strip().splitlines():
        r = json.loads(ln); g = {k: r[i] for k, i in I.items()}
        g.update(neutral=bool(g['nu']), o1=g['dko'], c1=g['dkc'], t1o=g['dkto'], t1c=g['dktc'], o2=g['s2o'], c2=g['s2c'], t2o=g['s2to'], t2c=g['s2tc'], h1=r[14], a1=r[15])
        if g['sp'] is not None and g['tot'] is not None: out.append(g)
    return sorted(out, key=lambda g: g['d'])
def srs(games):
    r = {}; gs = []
    for g in games:
        m = g['hs'] - g['as_'] - (0 if g['neutral'] else R.HCA); gs += [(g['h'], g['a'], m), (g['a'], g['h'], -m)]
    for _ in range(12):
        s, n = {}, {}
        for t, o, m in gs: s[t] = s.get(t, 0) + m + r.get(o, 0); n[t] = n.get(t, 0) + 1
        r = {t: s[t]/n[t] for t in s}; mu = sum(r.values())/max(1, len(r)); r = {t: v - mu for t, v in r.items()}
    return r
safe = lambda s: re.sub(r'[^A-Za-z0-9]', '', s)
# B6 (Nov 10): use the card's away/home order when the card's game doc lists a neutral site game the other way round from ESPN's season row,
# so backtest ids match the ledger and game docs (GAMES_DIR = a download of hub sports/ncaam/games).
CARD_ORDER = set()
if os.environ.get('GAMES_DIR'):
    for f in pathlib.Path(os.environ['GAMES_DIR']).glob('*.json'):
        st = f.stem; d_, ah = st.split('_', 1); CARD_ORDER.add((d_, ah))
def order(iso, h, a):
    if (iso, f"{safe(a)}-{safe(h)}") not in CARD_ORDER and (iso, f"{safe(h)}-{safe(a)}") in CARD_ORDER: return True
    return False
docs = []
def add(d, h, a, hs, as_, rk, market, side, line, price, res, inputs):
    iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    if market == 'Total': pick = f"{side.title()} {line:g}"
    elif market == 'Spread':
        t = h if side == 'home' else a; ln = line if side == 'home' else -line; pick = f"{t} {'+' if ln > 0 else ''}{ln:g}" if ln else f"{t} PK"
    else: t = h if side == 'home' else a; pick = f"{t} ML"
    u = round(R.win_units(price), 3) if res > 0 else (-1 if res < 0 else 0)
    sw = order(iso, h, a)
    docs.append(dict(id=(f"{iso}_{safe(h)}-{safe(a)}_{rk}" if sw else f"{iso}_{safe(a)}-{safe(h)}_{rk}"), data=dict(date=iso, game=f"{a} @ {h}", away=a, home=h, market=market, rule_key=rk, rule=RS[rk]['label'] if rk in RS else rk,
        rule_variant=VAR.get(rk, 'lowered'), rule_on_now=ON.get(rk, False), pick=pick, line=(line if market != 'Moneyline' else None), price=price, tier='Backtest',
        final=f"{a} {as_}, {h} {hs}", result='win' if res > 0 else ('loss' if res < 0 else 'push'), units=u, inputs=inputs, source=os.environ.get('BT_SOURCE', 'backtest Nov 7'))))
# ---- families and the rating/rest rules (games_ rows)
G = load(); logs, done, rating, last_day = {}, [], {}, ''
FAM = [k for k in RS if k not in ('EARLY_UNDER_OPEN', 'EARLY_OVER_OPEN', 'EFF_SPREAD', 'EFF_OVER') and k in R.RULES]   # Nov 12: meta also holds A29/A31/A33 rules that rules.py does not define
for g in G:
    if g['d'] != last_day: rating = srs(done); last_day = g['d']
    def ctx_t(t):
        L = logs.get(t, []); n = len(L); w = n/(n+8); rt = w*rating.get(t, 0) + (1-w)*RAT_LAST.get(t, 0)
        dd = (datetime.date(int(g['d'][:4]), int(g['d'][4:6]), int(g['d'][6:])) - L[-1][0]).days if L else None
        return rt, dd, (sum(1 for x in L[-5:] if x[1] > 0)/len(L[-5:]) if L else None), (sum(x[1] for x in L)/n if n else None), (L[-1][1] if L else None)
    rh, dh, fh, ah, lh = ctx_t(g['h']); ra, da, fa, aa, la = ctx_t(g['a'])
    tx = TIX.get((g['d'], g['a'], g['h']))
    if tx: g['tix_away'], g['tix_home'] = tx[0], tx[1]
    proj = rh - ra + (0 if g['neutral'] else R.HCA)
    S = R.signals(g, dict(proj=proj, rest_h=dh, rest_a=da, form_h=fh, form_a=fa, avgm_h=ah, avgm_a=aa, lastm_h=lh, lastm_a=la))
    for rk in FAM:
        if R.RULES[rk].get('lg', LG) != LG: continue
        for c in R.candidates(g, S, {rk: dict(on=True, variant=VAR[rk])}):
            res = R.grade(c, g); M = S['M']
            inp = dict(variant=VAR[rk], spread_open_home=g['o1'], spread_close_home=g['c1'], total_open=g['t1o'], total_close=g['t1c'], ml_home=g['mlh'], ml_away=g['mla'],
                       move_spread=M['m1'], move_total=(M['t'][0] if M['t'] else None), score_home=S['sh'], score_away=S['sa'], lead=S['lead'],
                       proj_home_margin=round(proj, 2), rest_home=dh, rest_away=da, neutral=g['neutral'],
                       tickets_away=(tx[0] if tx else None), tickets_home=(tx[1] if tx else None), money_away=(tx[2] if tx else None), money_home=(tx[3] if tx else None),
                       why=(S['why_h'] if c['side'] == 'home' else S['why_a']) if c['market'] != 'Total' else None)
            inp = {k: v for k, v in inp.items() if v is not None}
            line = g['sp'] if c['market'] == 'Spread' else (g['tot'] if c['market'] == 'Total' else None)
            add(g['d'], g['h'], g['a'], g['hs'], g['as_'], rk, c['market'], c['side'], line, c['price'], res, inp)
    m = g['hs'] - g['as_']; dte = datetime.date(int(g['d'][:4]), int(g['d'][4:6]), int(g['d'][6:]))
    logs.setdefault(g['h'], []).append((dte, m)); logs.setdefault(g['a'], []).append((dte, -m)); done.append(g)
# ---- efficiency rules (box rows), graded at the closing consensus
pri, plg = EF.load_prior(LG); Bx = sorted([json.loads(x) for x in (B/'src'/'season'/f'box_{LG}.txt').read_text().strip().splitlines() if x.strip()], key=lambda r: r[1])
done2, day, cur = [], '', ({}, None, {}); sg = lambda x: (x > 0) - (x < 0); played = len(Bx); lined = 0; nopri = 0
for r in Bx:
    if r[1] != day: cur = EF.solve(done2); day = r[1]
    ct, cs = r[25], r[24]
    if cs is not None and ct is not None: lined += 1
    if r[2] in pri and r[3] in pri and cs is not None and ct is not None:
        em, et, ph, pa = EF.project(r[2], r[3], r[4] == 1, pri, plg, *cur); tot = r[6] + r[7]; m = r[6] - r[7]
        ot = r[18] if r[18] is not None else r[22]; early = int(r[1][4:6]) in (11, 12)
        base = dict(model_total=round(et, 1), model_home_margin=round(em, 1), total_open=ot, total_close=ct, spread_open_home=r[16], spread_close_home=cs, neutral=r[4] == 1)
        base = {k: v for k, v in base.items() if v is not None}
        if early and ot is not None and et <= ot - 4: add(r[1], r[2], r[3], r[6], r[7], 'EARLY_UNDER_OPEN', 'Total', 'under', ct, -110, sg(ct - tot), dict(base, gap_vs_open=round(et - ot, 1)))
        if early and ot is not None and et >= ot + 4: add(r[1], r[2], r[3], r[6], r[7], 'EARLY_OVER_OPEN', 'Total', 'over', ct, -110, sg(tot - ct), dict(base, gap_vs_open=round(et - ot, 1)))
        if abs(em + cs) >= 3:
            side = 'home' if em + cs > 0 else 'away'
            add(r[1], r[2], r[3], r[6], r[7], 'EFF_SPREAD', 'Spread', side, cs, -110, sg(m + cs) if side == 'home' else sg(-m - cs), dict(base, edge=round(em + cs, 1)))
        if et >= ct + 3: add(r[1], r[2], r[3], r[6], r[7], 'EFF_OVER', 'Total', 'over', ct, -110, sg(tot - ct), dict(base, edge=round(et - ct, 1)))
    elif cs is not None and ct is not None: nopri += 1
    if r[8] and r[12]: done2.append(dict(h=r[2], a=r[3], nu=r[4] == 1, hs=r[6], as_=r[7], poss=(EF.poss(*r[8:12]) + EF.poss(*r[12:16]))/2))
ids = [d['id'] for d in docs]; assert len(ids) == len(set(ids)), 'duplicate ids'
json.dump(docs, open(OUT/f'out_{LG}.json', 'w'))
dates = sorted({r[1] for r in Bx})
print(f"{LG}: played {played}, lined {lined}, no line {played - lined}, lined but no prior rating (eff rules skipped) {nopri}; games_ rows {len(G)}; tix matched {sum(1 for g in G if g.get('tix_away') is not None)}; dates {dates}")
for rk in [k for k in RS if k in R.RULES or k.startswith(('EARLY','EFF'))]:
    x = [d['data'] for d in docs if d['data']['rule_key'] == rk]
    s = R.summarize([(1 if z['result'] == 'win' else (-1 if z['result'] == 'loss' else 0), z['price']) for z in x])
    print(f"  {rk:17s} on={ON[rk]!s:5s} {VAR[rk]:8s} {s['w']}-{s['l']}-{s['p']}  {s['u']:+.2f}u")
