"""Season Cards extras for the NCAAM run (Nov 7, 2026): pick details, game docs with team game logs, Nov 6 finals on game docs,
expert grading, standings and hub meta. Usage: python3 extras.py YYYY-MM-DD YESTERDAY_YYYYMMDD. Writes out/hubw/*.json (ArtifactData batch inputs)."""
import json, sys, runpy, pathlib, datetime, glob, re
D = pathlib.Path(__file__).parent; W = D.parent; OUT = W/'out'/'hubw'; OUT.mkdir(parents=True, exist_ok=True)
DATE, YD = sys.argv[1], sys.argv[2]
sys.argv = ['build.py', 'M', DATE]
B = runpy.run_path(str(D/'build.py'), run_name='build')
R = B['R']; STATE = B['STATE']; games = B['games']; EF = B['EF']
dt = datetime.date.fromisoformat(DATE)
safe = lambda s: re.sub(r'[^A-Za-z0-9]', '', s)   # letters and digits only, same as the backtest ids (B6, Nov 10)
# ---------- team info (ESPN today) and names
TI = {}
for l in (W/'data'/'raw'/f"teaminfo_m_{DATE.replace('-', '')}.txt").read_text().strip().splitlines():
    gid, a, h, ven = l.split('|'); TI[gid] = (a.split('^'), h.split('^'), ven)
NAMES = {}
for f in glob.glob(str(W/'hub'/'sports'/'ncaam'/'games'/'*.json')):
    d = json.load(open(f))
    for s in ('away', 'home'):
        t = d.get(s) or {}
        if t.get('name'): NAMES[t['code']] = t['name']
        for gl in ((d.get('trends') or {}).get(s) or {}).get('games', []) or []:
            if gl.get('opp_name'): NAMES[gl['opp']] = gl['opp_name']
for g in games:
    ti = TI.get(g['id'])
    if ti: NAMES[g['away']] = ti[0][0]; NAMES[g['home']] = ti[1][0]
AP = {r['team']: r['rank'] for r in json.loads((W/'data'/'ap_poll.json').read_text())['M']}
# ---------- season game logs (lined D1 games, closing DraftKings lines)
SG = [json.loads(x) for x in (D/'season'/'games_M.txt').read_text().strip().splitlines()]
LOG = {}
# closing period lines saved on earlier game docs (lines.periods) -> GAMELOG plines (Season Cards, Nov 7)
PL = {}
for f in glob.glob(str(W/'hub'/'sports'/'ncaam'/'games'/'*.json')):
    d = json.load(open(f)); per = ((d.get('lines') or {}).get('periods') or {})
    num = lambda x: (0.0 if x.split()[0] == 'PK' else float(x.split()[0])) if x else None
    for lab, pv in per.items():
        try:
            sa, sh = num(pv['spread']['away']), num(pv['spread']['home']); tt = num(pv['total']['over'])
        except Exception: continue
        PL.setdefault((d['date'], d['away']['code'], d['home']['code']), {})[lab] = (sa, sh, tt)
# closing first half lines from The Odds API (periods_close) for yesterday's games (B7, Nov 10): they replace the earlier texas222 read as the closing number
PCLOSE = {}
_oc = W/'data'/'raw'/f'odds_ncaam_{YD}_close.json'; _ti = W/'data'/'raw'/f'teaminfo_m_{YD}.txt'; _yf = W/'data'/'raw'/f'y_{YD}.txt'
if _oc.exists() and _ti.exists() and _yf.exists():
    _nm = B['_nm']; _ev = list(json.load(open(_oc)).values())
    _yc = {l.split('|')[1]: (l.split('|')[3], l.split('|')[2]) for l in _yf.read_text().strip().splitlines()}
    def _m(p, q): return p == q or p.startswith(q) or q.startswith(p)
    def _mm(a, h, xa, xh): return _m(a, xa) and _m(h, xh) or (a.split()[-1] == xa.split()[-1] and h.split()[-1] == xh.split()[-1] and (a.split()[0] == xa.split()[0] or h.split()[0] == xh.split()[0]))
    for _l in _ti.read_text().strip().splitlines():
        _gid, _a, _h = _l.split('|')[:3]; _a, _h = _nm(_a.split('^')[0]), _nm(_h.split('^')[0])
        if _gid not in _yc: continue
        for _x in _ev:
            xa, xh = _nm(_x['away']), _nm(_x['home']); fl = None
            if _mm(_a, _h, xa, xh): fl = False
            elif _mm(_a, _h, xh, xa): fl = True
            if fl is None: continue
            h1 = (_x.get('periods_close') or {}).get('h1') or {}
            if h1.get('spread_home') is not None and h1.get('total') is not None:
                sh = -h1['spread_home'] if fl else h1['spread_home']; ca, ch = _yc[_gid]
                yi = f"{YD[:4]}-{YD[4:6]}-{YD[6:]}"
                PL.setdefault((yi, ca, ch), {})['1H'] = (-sh, sh, h1['total'])
                PCLOSE[(yi, ca, ch)] = dict(spread_home=sh, total=h1['total'], books=h1.get('books'))
            break
for r in SG:
    d, h, a, nu, hs, as_, h1, a1, sp, tot = r[2], r[3], r[4], r[8], r[12], r[13], r[14], r[15], r[26], r[27]
    iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    for team, opp, pf, pa, f1, a1_, tsp, site in ((h, a, hs, as_, h1, a1, sp, 'neutral' if nu else 'home'), (a, h, as_, hs, a1, h1, -sp if sp is not None else None, 'neutral' if nu else 'away')):
        gl = dict(date=iso, opp=opp, opp_name=NAMES.get(opp), opp_rank=AP.get(opp), site=site, pf=pf, pa=pa)
        if f1 is not None and a1_ is not None:
            gl['periods'] = dict(labels=['1H', '2H'], **{'for': [int(f1), pf - int(f1)], 'against': [int(a1_), pa - int(a1_)]})
        if tsp is not None:
            gl['spread'] = f"{tsp:+g}" if tsp else 'PK'; v = pf - pa + tsp; gl['ats'] = 'W' if v > 0 else ('L' if v < 0 else 'P')
        pk = PL.get((iso, a, h))
        if pk: gl['plines'] = {lab: dict(spread=(v[1] if team == h else v[0]), total=v[2]) for lab, v in pk.items()}
        if tot is not None:
            gl['total'] = tot; v = pf + pa - tot; gl['ou'] = 'O' if v > 0 else ('U' if v < 0 else 'P')
        LOG.setdefault(team, []).append({k: v for k, v in gl.items() if v is not None})
for t in LOG: LOG[t].sort(key=lambda x: x['date'])
def rec(gs, k):
    vals = [g.get(k) for g in gs if g.get(k)]
    if k == 'r': w = sum(1 for g in gs if g['pf'] > g['pa']); return f"{w}-{len(gs) - w}"
    a, b, p = (('W', 'L', 'P') if k == 'ats' else ('O', 'U', 'P'))
    s = f"{vals.count(a)}-{vals.count(b)}"; return s + (f"-{vals.count(p)}" if vals.count(p) else '')
def hist(gs):
    if not gs: return None
    ha = lambda s: rec([g for g in gs if g['site'] == s], 'r')
    parts = [f"{ha('home')} home"] if any(g['site'] == 'home' for g in gs) else []
    if any(g['site'] == 'away' for g in gs): parts.append(f"{ha('away')} road")
    if any(g['site'] == 'neutral' for g in gs): parts.append(f"{ha('neutral')} neutral")
    return dict(record=rec(gs, 'r'), ats=rec(gs, 'ats'), ou=rec(gs, 'ou'), pf=round(sum(g['pf'] for g in gs)/len(gs), 1), pa=round(sum(g['pa'] for g in gs)/len(gs), 1), home_away=' · '.join(parts), games=len(gs))
monday = dt - datetime.timedelta(days=dt.weekday())
def trend(t, rest):
    gs = LOG.get(t, []); l5 = gs[-5:]
    if not gs: return dict(rest_days=rest, games=[], note='No Division I games with a posted line yet this season')
    st = 'W' if gs[-1]['pf'] > gs[-1]['pa'] else 'L'; n = 0
    for g in reversed(gs):
        if ('W' if g['pf'] > g['pa'] else 'L') == st: n += 1
        else: break
    return dict(last5=['W' if g['pf'] > g['pa'] else 'L' for g in l5], pf=round(sum(g['pf'] for g in gs)/len(gs), 1), pa=round(sum(g['pa'] for g in gs)/len(gs), 1),
                last5_scores=[g['pf'] for g in l5], last5_totals=[g['pf'] + g['pa'] for g in l5], last5_margins=[g['pf'] - g['pa'] for g in l5],
                rest_days=rest, back_to_back=(rest == 1), streak=f"{st}{n}",
                history={k: v for k, v in dict(season=hist(gs), month=hist([g for g in gs if g['date'][:7] == DATE[:7]]), week=hist([g for g in gs if g['date'] >= monday.isoformat()]),
                                                last10=hist(gs[-10:]), last5=hist(l5)).items() if v},
                games=list(reversed(gs[-10:])))
# ---------- records
RS = STATE['rules']
def rs(s): return f"{s['w']}-{s['l']}" + (f"-{s['p']}" if s.get('p') else '') + f" {s['u'] + 0.0:+.2f}u"
LED = [json.load(open(f)) for f in glob.glob(str(W/'hub'/'ledger'/'sports'/'ncaam'/'picks'/'*.json'))]
GRADED = {'2026-11-06_' + k: v for k, v in []}
def card(rule):
    rows = [(1 if x['result'] == 'win' else (-1 if x['result'] == 'loss' else 0), x['price']) for x in LED if not x.get('shadow') and x.get('rule') == rule and x.get('result') in ('win', 'loss', 'push')]
    s = R.summarize(rows); return rs(s)
# ---------- experts found today (named people only)
EXP = []
EXPERTS_TODAY = json.loads((W/'data'/'experts_today.json').read_text()) if (W/'data'/'experts_today.json').exists() else []
# Experts found for this slate (named people only; Action Network game articles, read in Chrome). Edit per run.
AN = 'https://www.actionnetwork.com/ncaab/'
CM = "NCAAB 814-780-15 +21.8u all time; all sports last 30 days 20-12-0 +8.14u (Action Network profile, Nov 10)"
SK = "NCAAB 2176-2027-92 +23.37u all time (Action Network profile, Nov 10)"
for game, name, pick, market, side, line, url, price, units, record in EXPERTS_TODAY:
    EXP.append(dict(game=game, name=name, platform='Action Network', pick=pick, market=market, side=side, line=line, price=price, units=units, record=record, card_record=None, url=url, pulled_at=f"{DATE} 3:05 PM Phoenix"))
# ---------- per game docs
import os as _os
now_lbl = _os.environ.get('READ_AT', '8:00 AM')
def fmtp(x): return '' if x is None else (f"{int(x):+d}" if abs(x) >= 100 else f"{int(x)}")
def sps(v, p): return ('PK' if v == 0 else f"{v:+g}") + (f" {int(p):+d}" if p else '')
H1 = {}
import os
for l in (W/'data'/'raw'/(os.environ.get('H1FILE') or f"t222_m1h_{DATE.replace('-', '')}.txt")).read_text().strip().splitlines():
    f = l.split('|'); H1[f[2]] = f

MODEL_RULES = {'EARLY_UNDER_OPEN': 'Efficiency model vs opener', 'EARLY_OVER_OPEN': 'Efficiency model vs opener', 'EFF_SPREAD': 'Efficiency model vs spread', 'EFF_OVER': 'Model vs current total', 'MODEL_EDGE': 'Efficiency model vs spread'}
def score(rule, pro, con):
    """Season Cards tier scale (Nov 7): lead = reason points minus against points. Model rules: trigger gap 1 point per 2 (max 4); line moved against = 2 against."""
    if rule in MODEL_RULES:
        for x in pro:
            if x['label'] == MODEL_RULES[rule] and x['points'] is None:
                m = re.search(r'\(([+-][\d.]+)', x['detail']) or re.search(r'([+-][\d.]+) for', x['detail'])
                gap = abs(float(m.group(1))) if m else 0; x['points'] = min(4, int(gap // 2))
        for x in con:
            if x['label'] == 'Total moved against the pick' and x['points'] is None: x['points'] = 2
    f = sum(x['points'] for x in pro if isinstance(x.get('points'), (int, float))); a = sum(x['points'] for x in con if isinstance(x.get('points'), (int, float)))
    lead = f - a; tier = 'Strong' if lead >= 4 else ('Solid' if lead >= 2 else 'Lean')
    return tier, f"signal lead {lead} (for {f}, against {a})"
INACTIVE = {k: dict(v, on=True) for k, v in STATE['rules'].items() if not v['on'] and v.get('since', '2026-11-02') <= DATE}
ALLR = {k: dict(v, on=True) for k, v in STATE['rules'].items() if v.get('since', '2026-11-02') <= DATE}
SHADOW = []; UPG = []
gdocs, pdocs = [], []
LEDG = {f"{d['data']['date']}_{safe(d['data']['away'])}-{safe(d['data']['home'])}_{d['id'].rsplit('_', 1)[1]}": d['data'] for d in json.loads((W/'out'/'M'/'ledger_today.json').read_text())}
# hub meta tier flags (Season Cards, Nov 9): upgraded tiers of inactive rules make card picks; downgraded tiers of active rules make would-be picks
META = json.load(open(W/'hub'/'meta'/'ncaam.json')); META = META.get('data', META)
TIERS = {r['key']: (r.get('tiers') or {}) for r in META['rules']}
sys.path.insert(0, str(D)); import gapguard as GG   # A57 (Trina, Nov 16): spread gap over 10 and Over gap under 10 are would-be picks
GGL = GG.limits(META)
def tier_flag(rule, tier, key): return bool((TIERS.get(rule, {}).get(tier) or {}).get(key)) and (key != 'upgraded' or bool((TIERS.get(rule, {}).get(tier) or {}).get('on')))
def tier_rec(rule, tier):
    t = TIERS.get(rule, {}).get(tier) or {}; s_ = t.get('season')
    return (f"{s_['w']}-{s_['l']}" + (f"-{s_['p']}" if s_.get('p') else '') + f" {s_['u'] + 0.0:+.2f}u") if s_ else None
for g in games:
    a, h = g['away'], g['home']; gid = f"{DATE}_{safe(a)}-{safe(h)}"; ti = TI.get(g['id'])
    def team(code, i, conf):
        t = dict(code=code, short=code, conference=conf, logo=None)
        if ti:
            x = ti[i]; t['name'] = x[0]; t['color'] = ('#' + x[1]) if x[1] else None
            tot, hm, rd = (x[2].split('/') + ['', '', ''])[:3]; t['record'] = tot or None
            t['venue_record'] = (f"{hm} home" if i == 1 else f"{rd} road") if (hm if i == 1 else rd) else None
        if AP.get(code): t['rank'] = AP[code]; t['rank_label'] = f"AP #{AP[code]}"
        return {k: v for k, v in t.items() if v is not None}
    S = g['S']; e = B['EB'].get(g['id']) or {}
    lines = dict(book='The Odds API median of books' if g['src'] == 'texas222' else 'DraftKings', read_at=now_lbl)
    if g['posted']:
        lines['spread'] = dict(away=sps(-g['sp'], g['sp_price_away']), home=sps(g['sp'], g['sp_price_home']))
        if g['mla'] is not None and g['mlh'] is not None: lines['moneyline'] = dict(away=fmtp(g['mla']), home=fmtp(g['mlh']))
        lines['total'] = dict(over=f"{g['tot']:g} {int(g['o_price']):+d}", under=f"{g['tot']:g} {int(g['u_price']):+d}")
        op = []
        if g['src'] == 'texas222' and g['o1'] is not None: op.append(f"Action Network {h} {g['o1']:+g}")
        if e.get('o') is not None: op.append(f"DraftKings {h} {e['o']:+g}" + (f" / total {e['to']:g}" if e.get('to') is not None else ''))
        xo, xto = B['odds_open'](g['id'])
        if xo is not None or xto is not None: op.append("The Odds API median open " + (f"{h} {xo:+g}" if xo is not None else '') + (f" / total {xto:g}" if xto is not None else ''))
        if op: lines['openers'] = ' · '.join(op)
    if g['src'] == 'texas222':
        # first half lines (texas222 1H menu); t222 names are matched through the build ALIAS
        per = {}
        for nm, f in H1.items():
            c = nm if nm in B['BYAB'] else B['ALIAS'].get(B['norm'](nm))   # Nov 12: Odds API 1H file carries ESPN codes
            if c in (a, h): per.setdefault('1H', {}).setdefault('_', {})[c] = f
        if '1H' in per and len(per['1H']['_']) == 2:
            fa, fh = per['1H']['_'][a], per['1H']['_'][h]
            m1 = lambda x: re.match(r'([+-][\d.]+|PK)([+-]\d+)', x); t1 = lambda x: re.match(r'[ou]([\d.]+)([+-]\d+)', x)
            sa, sh = m1(fa[3]), m1(fh[3]); ta, th = (t1(fa[4]), t1(fh[4])) if fa[4].startswith('o') else (t1(fh[4]), t1(fa[4]))
            lines['periods'] = {'1H': dict(spread=dict(away=f"{sa.group(1)} {sa.group(2)}", home=f"{sh.group(1)} {sh.group(2)}"),
                                           total=dict(over=f"{ta.group(1)} {ta.group(2)}", under=f"{th.group(1)} {th.group(2)}"))}
    moves = []
    if e.get('o') is not None and e.get('c') is not None and e['o'] != e['c']: moves.append(f"DraftKings spread opened {h} {e['o']:+g}, now {h} {e['c']:+g}")
    if e.get('to') is not None and e.get('tc') is not None and e['to'] != e['tc']: moves.append(f"DraftKings total opened {e['to']:g}, now {e['tc']:g}")
    if g['src'] == 'texas222' and g['o1'] is not None and g['o1'] != g['sp']: moves.append(f"Spread opened {h} {g['o1']:+g} (Action Network), Odds API now {h} {g['sp']:+g}")
    an = g['an'] or B['AN'].get(frozenset((a, h)))
    splits = []
    if an:
        aw = an['a'] == a
        sp_ = dict(market='Spread', opener=(f"{a} {an['open_a'] if aw else -an['open_a']:+g}" if an['open_a'] is not None else None))
        if an.get('ba') is not None:
            sp_['away_or_over'] = dict(tickets=an['ba'] if aw else an['bh'], money=an['ma'] if aw else an['mh'], tags=[])
            sp_['home_or_under'] = dict(tickets=an['bh'] if aw else an['ba'], money=an['mh'] if aw else an['ma'], tags=[])
        splits.append({k: v for k, v in sp_.items() if v is not None})
    model = {}
    if g.get('emar') is not None: model['our_spread'] = f"{h if g['emar'] >= 0 else a} -{abs(g['emar']):.1f}"
    elif g.get('proj') is not None: model['our_spread'] = f"{h if g['proj'] >= 0 else a} -{abs(g['proj']):.1f}"
    if g.get('etot') is not None: model['our_total'] = f"{g['etot']:.1f}"
    if g.get('emar') is not None and g['sp'] is not None: model['note'] = f"Efficiency model (last season blended with this season); margin vs spread {g['emar'] + g['sp']:+.1f}"
    gx = [x for x in EXP if x['game'] == f"{a}-{h}"]
    # reasons
    ot = g.get('t2o') if g.get('t2o') is not None else g.get('t1o')
    if ot is None: ot = e.get('to')
    def tot_reasons(side):
        pro, con = [], []
        if g.get('etot') is not None and ot is not None:
            (pro if (g['etot'] < ot) == (side == 'under') else con).append(dict(label='Efficiency model vs opener', detail=f"model total {g['etot']:.1f} vs DraftKings opening total {ot:g} ({g['etot'] - ot:+.1f})", points=None, source='Card model'))
        if ot is not None and g['tot'] is not None and ot != g['tot']:
            w = (g['tot'] < ot) == (side == 'under')
            (pro if w else con).append(dict(label='Total moved with the pick' if w else 'Total moved against the pick', detail=f"opened {ot:g}, {lines['book']} now {g['tot']:g}", points=None, source=f"DraftKings open, {lines['book']}"))
        # Trina Nov 24: when the total has not moved, model vs current is the same signal as model vs opener; count it once.
        if g.get('etot') is not None and g['tot'] is not None and not (ot is not None and ot == g['tot']):
            w = (g['etot'] < g['tot']) == (side == 'under')
            (pro if w else con).append(dict(label='Model vs current total', detail=f"model {g['etot']:.1f} vs {g['tot']:g} now ({g['etot'] - g['tot']:+.1f})", points=None, source='Card model'))
        con.append(dict(label='Injuries unknown', detail='College injury reporting is thin; no confirmed absences pulled (LOW)', points=None, source='ESPN'))
        for x in pro + con: x['market'] = 'Game context' if x['label'] == 'Injuries unknown' else 'Total'
        return pro, con
    def side_reasons(sd):
        pro = [dict(label=w[:1].upper() + w[1:], detail=w, points=(int(m.group(1)) if (m := re.search(r'\((\d)\)$', w)) else 1), source='Card signals') for w in (S['why_h'] if sd == 'home' else S['why_a'])]
        con = [dict(label=w[:1].upper() + w[1:], detail=w, points=(int(m.group(1)) if (m := re.search(r'\((\d)\)$', w)) else 1), source='Card signals') for w in (S['why_a'] if sd == 'home' else S['why_h'])]
        tm = h if sd == 'home' else a
        if g.get('emar') is not None and g['sp'] is not None:
            edge = (g['emar'] + g['sp']) if sd == 'home' else -(g['emar'] + g['sp'])
            (pro if edge > 0 else con).append(dict(label='Efficiency model vs spread', detail=f"model {model.get('our_spread')} vs {tm} {(g['sp'] if sd == 'home' else -g['sp']):+g} ({edge:+.1f} for {tm})", points=None, source='Card model'))
        if an and an.get('ba') is not None:
            aw = an['a'] == a; tk = (an['bh'] if aw else an['ba']) if sd == 'home' else (an['ba'] if aw else an['bh']); mn = (an['mh'] if aw else an['ma']) if sd == 'home' else (an['ma'] if aw else an['mh'])
            (pro if mn > tk else con).append(dict(label='Money ahead of tickets' if mn > tk else 'Public side', detail=f"{tm} {tk}% of tickets, {mn}% of money", points=None, source='Action Network'))
        for x in gx:
            (pro if x['side'] == tm else con).append(dict(label='Expert pick', detail=f"{x['name']} ({x['platform']}): {x['pick']}", points=None, source=x['platform']))
        con.append(dict(label='Injuries unknown', detail='College injury reporting is thin; no confirmed absences pulled (LOW)', points=None, source='ESPN'))
        for x in pro + con:
            lb = x['label'].lower()
            if 'line moved' in lb or 'projection beats the spread' in lb or 'efficiency model vs spread' in lb or 'money ahead' in lb or 'public side' in lb: x['market'] = 'Spread'
            elif lb == 'expert pick': x['market'] = 'Moneyline' if ' ML' in x['detail'] else 'Spread'
            else: x['market'] = 'Game context'
        return pro, con
    NM = lambda c: (NAMES.get(c) or c)
    def tfacts(c):
        gs = LOG.get(c, []); tr = []
        x = ti[0 if c == a else 1] if ti else None
        rec = (x[2].split('/')[0] if x else '') or (f"{sum(1 for z in gs if z['pf'] > z['pa'])}-{sum(1 for z in gs if z['pf'] < z['pa'])}" if gs else '')
        if gs:
            pf = sum(z['pf'] for z in gs)/len(gs); pa_ = sum(z['pa'] for z in gs)/len(gs)
            l5 = ''.join('W' if z['pf'] > z['pa'] else 'L' for z in gs[-5:])
            ats = [z.get('ats') for z in gs if z.get('ats')]
            tr.append(f"{NM(c)} is {rec}" + (f" (AP #{AP[c]})" if AP.get(c) else '') + f", scoring {pf:.1f} and allowing {pa_:.1f} a game against Division I teams with a line, {ats.count('W')}-{ats.count('L')} against the spread")
        elif rec: tr.append(f"{NM(c)} is {rec}" + (f" (AP #{AP[c]})" if AP.get(c) else '') + " with no lined Division I game yet")
        rd = B['rest_days'](c)
        return tr, rd
    def projs():
        if g.get('etot') is not None and g.get('emar') is not None:
            ph = (g['etot'] + g['emar'])/2; pa_ = (g['etot'] - g['emar'])/2; return pa_, ph
        return None, None
    def mv_txt():
        out = []
        if e.get('o') is not None and g['sp'] is not None and e['o'] != g['sp']: out.append(f"the spread opened {h} {e['o']:+g} and is now {h} {g['sp']:+g}")
        if ot is not None and g['tot'] is not None and ot != g['tot']: out.append(f"the total opened {ot:g} and is now {g['tot']:g}")
        return out
    def spl_txt(tm):
        if not (an and an.get('ba') is not None): return None
        aw = an['a'] == a; tk = (an['bh'] if aw else an['ba']) if tm == h else (an['ba'] if aw else an['bh']); mn = (an['mh'] if aw else an['ma']) if tm == h else (an['ma'] if aw else an['mh'])
        return tk, mn
    def SUMM(c, kind, lbl, ln):
        pa_, ph = projs(); F, A = [], []
        if kind == 'total':
            und = c['side'] == 'under'
            if pa_ is not None: F.append(f"Our model projects {NM(a)} {pa_:.0f}, {NM(h)} {ph:.0f}, a {g['etot']:.1f} point total against {g['tot']:g}" + (f" (opened {ot:g})" if ot is not None and ot != g['tot'] else '') + '.')
            ta = [z['pf'] + z['pa'] for z in LOG.get(a, [])]; th = [z['pf'] + z['pa'] for z in LOG.get(h, [])]
            if ta or th:
                F.append(' '.join(x for x in [f"{NM(a)} games have averaged {sum(ta)/len(ta):.1f} combined points ({len(ta)} lined games)." if ta else '', f"{NM(h)} games have averaged {sum(th)/len(th):.1f} ({len(th)})." if th else ''] if x))
            mv = mv_txt()
            if mv: (F if ((g['tot'] < ot) == und if ot is not None else False) else A).append(f"In the market, {mv[-1]}.")
            if pa_ is not None:
                gap = g['etot'] - g['tot']
                if (gap > 0) == und: A.append(f"Against the current number our model is {abs(gap):.1f} points on the other side, so the edge is against the opener rather than today's total.")
            ex = [z for z in LOG.get(a, []) + LOG.get(h, []) if z.get('ou')]
            o = sum(1 for z in ex if z['ou'] == 'O'); u_ = sum(1 for z in ex if z['ou'] == 'U')
            if ex: (A if (o > u_) == und else F).append(f"These two teams' games went {o}-{u_} to the over against closing totals so far.")
            A.append('No confirmed absences were found for either team; college injury reports are thin early in the season.')
        else:
            tm = h if c['side'] == 'home' else a; op = a if tm == h else h
            if pa_ is not None:
                fav = h if g['emar'] >= 0 else a
                F.append(f"Our model projects {NM(a)} {pa_:.0f}, {NM(h)} {ph:.0f}, {NM(fav)} by {abs(g['emar']):.1f}, against a market of {NM(tm)} {('PK' if ln == 0 else f'{ln:+g}')}" + (f" ({int(c['price']):+d} on the moneyline)" if c['market'] == 'Moneyline' else '') + '.')
            f1, r1 = tfacts(tm); f2, r2 = tfacts(op)
            F += [x + '.' for x in f1]; A += [x + '.' for x in f2]
            if r1 is not None and r2 is not None and r1 != r2: (F if r1 > r2 else A).append(f"{NM(tm)} has {r1} days of rest to {r2} for {NM(op)}.")
            if not g['neutral'] and tm == h: F.append(f"{NM(h)} is at home ({ti[2] if ti else 'home court'}).")
            elif not g['neutral'] and tm == a: A.append(f"{NM(h)} has home court.")
            mv = mv_txt()
            if mv and e.get('o') is not None and g['sp'] is not None and e['o'] != g['sp']:
                toward = (g['sp'] < e['o']) == (tm == h)
                (F if toward else A).append(f"In the market, {mv[0]}.")
            sp_ = spl_txt(tm)
            if sp_: (F if sp_[1] > sp_[0] else A).append(f"{NM(tm)} has {sp_[0]}% of spread tickets and {sp_[1]}% of the money at Action Network.")
            if pa_ is not None and g['sp'] is not None:
                edge = (g['emar'] + g['sp']) if tm == h else -(g['emar'] + g['sp'])
                if edge < 0: A.append(f"Our efficiency model is {abs(edge):.1f} points short of this number for {NM(tm)}.")
            if c['market'] == 'Moneyline':
                be = 100*R.breakeven(c['price']); A.append(f"At {int(c['price']):+d} the pick needs to win {be:.0f}% of the time.")
            A.append('No confirmed absences were found for either team; college injury reports are thin early in the season.')
        f_ = ' '.join(F[:4]); a_ = ' '.join(A[:4])
        return {'for': f_, 'against': a_}
    def ANALYSIS(kind):
        pa_, ph = projs(); out = []
        if kind == 'total':
            if pa_ is not None and g['tot'] is not None: out.append(f"Our model total is {g['etot']:.1f} against {g['tot']:g}" + (f", which opened {ot:g}" if ot is not None and ot != g['tot'] else '') + '.')
            ta = [z['pf'] + z['pa'] for z in LOG.get(a, [])]; th = [z['pf'] + z['pa'] for z in LOG.get(h, [])]
            if ta and th: out.append(f"{NM(a)} games average {sum(ta)/len(ta):.1f} combined points and {NM(h)} games {sum(th)/len(th):.1f}.")
        else:
            if pa_ is not None: out.append(f"Our model has {NM(a)} {pa_:.0f}, {NM(h)} {ph:.0f}" + (f" against a spread of {h} {g['sp']:+g}" if g['sp'] is not None else '') + '.')
            for c_ in (a, h):
                f1, _ = tfacts(c_); out += [x + '.' for x in f1]
            ra, rh = B['rest_days'](a), B['rest_days'](h)
            if ra is not None and rh is not None: out.append(f"Rest: {NM(a)} {ra} days, {NM(h)} {rh} days.")
        return ' '.join(out[:4]) or 'Not enough data yet for a game analysis.'
    picks = {}; reasons = dict(side=[], total=[], side_against=[], total_against=[])
    def label_of(c):
        if c['market'] == 'Total': return f"{'Under' if c['side'] == 'under' else 'Over'} {g['tot']:g}", g['tot']
        tm = h if c['side'] == 'home' else a; ln = g['sp'] if c['side'] == 'home' else -g['sp']
        return (f"{tm} ML" if c['market'] == 'Moneyline' else (f"{tm} PK" if ln == 0 else f"{tm} {ln:+g}")), ln
    def details(c, kind):
        pro, con = tot_reasons(c['side']) if kind == 'total' else side_reasons(c['side'])
        tier, basis = score(c['rule'], pro, con)
        s = RS[c['rule']]
        rr = dict(rule=c['rule'], every_game=rs(s['season']), card=card(c['rule']), last_3_weeks=rs(s['season']) + ' (season began Nov 2)')
        trc = tier_rec(c['rule'], tier)
        if trc: rr['tier'] = f"{tier} tier: {trc}"
        be = round(100 * R.breakeven(c['price']), 1)
        if kind == 'total':
            mdl = dict(projection=round(g['etot'], 1) if g.get('etot') is not None else None, needed_pct=be, edge=round((g['tot'] - g['etot']) if c['side'] == 'under' else (g['etot'] - g['tot']), 1) if g.get('etot') is not None else None)
            l5 = dict(last5_away=[x['pf'] + x['pa'] for x in LOG.get(a, [])[-5:]], last5_home=[x['pf'] + x['pa'] for x in LOG.get(h, [])[-5:]], line=g['tot'])
        else:
            em = g.get('emar')
            proj = None if em is None else (f"{h} by {em:.1f}" if em >= 0 else f"{a} by {-em:.1f}")
            edge = None if em is None or g['sp'] is None else round((em + g['sp']) if c['side'] == 'home' else -(em + g['sp']), 1)
            mdl = dict(projection=proj, needed_pct=be, edge=edge, edge_note='model margin vs the spread for the pick side')
            if c['market'] == 'Moneyline':
                l5 = dict(last5_away=[dict(r='W' if x['pf'] > x['pa'] else 'L', pf=x['pf'], pa=x['pa']) for x in LOG.get(a, [])[-5:]],
                          last5_home=[dict(r='W' if x['pf'] > x['pa'] else 'L', pf=x['pf'], pa=x['pa']) for x in LOG.get(h, [])[-5:]], line=f"{int(c['price']):+d}")
            else:
                l5 = dict(last5_away=[x['pf'] - x['pa'] for x in LOG.get(a, [])[-5:]], last5_home=[x['pf'] - x['pa'] for x in LOG.get(h, [])[-5:]], line=g['sp'] if c['side'] == 'home' else -g['sp'])
        exps = [{k: v for k, v in x.items() if k != 'game'} for x in gx if x['market'] == c['market'] or c['market'] in ('Spread', 'Moneyline') and x['market'] in ('Spread', 'Moneyline')]
        return tier, basis, pro, con, rr, {k: v for k, v in mdl.items() if v is not None}, l5, exps
    lsrc = B['LSRC'](g)
    base = lambda: dict(date=DATE, game=f"{a} @ {h}", away=a, home=h, time=g['time'], day=g['day'], conflicting=False, projected=None, result='pending', final='',
                        line_source=lsrc, conference=g['hconf'] if g['cg'] else f"{g['aconf']} vs {g['hconf']}")
    def shadow_doc(c, kind, note=None, conflict=None):
        tier, basis, pro, con, rr, mdl, l5, exps = details(c, kind); lbl, ln = label_of(c)
        rr = {k: v for k, v in rr.items() if k != 'card'}
        d = dict(base(), market=c['market'], pick=lbl, price=int(c['price']), line=ln, side=c['side'], tier=tier, tier_basis=basis, rule=c['rule'], rule_key=c['rule'], rule_variant=c.get('variant'), shadow=True,
                 reasons=pro, against=con, rule_record=rr, model=mdl, last5=l5, experts=exps)
        if note: d['note'] = note
        d['conflict'] = conflict or note or 'Rule is not active for this tier'
        if c.get('gap_guard'): d['gap_guard'] = GG.doc_flag(c['gap_guard'])
        d['rule_label'] = R.RULES[c['rule']]['name']
        d['summary'] = SUMM(c, kind, lbl, ln)
        mk = 'total' if c['market'] == 'Total' else ('ml' if c['market'] == 'Moneyline' else 'side')
        SHADOW.append(dict(id=f"{DATE}_{safe(a)}-{safe(h)}_{mk}_{c['rule']}", data=d))
    def card_doc(c, kind, upgraded=False):
        did = f"{DATE}_{safe(a)}-{safe(h)}_{kind}"; lbl, ln = label_of(c)
        tier, basis, pro, con, rr, mdl, l5, exps = details(c, kind)
        sm = SUMM(c, kind, lbl, ln)
        picks[kind] = dict(pick=lbl, price=f"{int(c['price']):+d}", tier=tier, rule_label=R.RULES[c['rule']]['name'] + (f" ({tier} tier upgraded)" if upgraded else ''), doc_id=did, summary=sm, line_source=lsrc)
        reasons[kind] = pro; reasons[kind + '_against'] = con
        led = LEDG.get(did)
        if not led or led.get('rule') != c['rule'] or led.get('market') != c['market']: led = dict(base(), market=c['market'], pick=lbl, price=int(c['price']), rule=c['rule'], rule_variant=c.get('variant'))
        d = dict(led, tier=tier, tier_basis=basis, rule_tier=led.get('tier') if led.get('tier') != tier else None, reasons=pro, against=con, rule_record=rr, model=mdl, last5=l5, experts=exps,
                 side=c['side'], line=ln, shadow=False, rule_key=c['rule'])
        d['summary'] = sm; d['rule_label'] = R.RULES[c['rule']]['name']
        if upgraded: d['tier_upgrade'] = True; d['note'] = f"Card pick from the upgraded {tier} tier of an inactive rule (Season Cards tiers, Nov 9)"
        pdocs.append(dict(id=did, data={k: v for k, v in d.items() if v is not None}))
    live = g['posted'] and g.get('state', 'p') == 'p'; picks_extra = []
    fits = R.candidates(g, S, ALLR) if live else []
    GG.apply_gap_guard(fits, GG.ctx_build(g), GGL)   # A57: marks guarded fits; they can only be would-be picks
    RN = lambda r: R.RULES[r]['name']
    def eligible(c, kind):
        t = details(c, kind)[0]; tr = TIERS.get(c['rule'], {}).get(t)
        if c.get('gap_guard'): return False, t   # A57 gap guard: never a card pick
        ron = bool(STATE['rules'][c['rule']]['on'])
        if tr is None: return ron, t
        return bool(tr.get('on')), t
    def tunits(c, kind):
        t = details(c, kind)[0]; tr = TIERS.get(c['rule'], {}).get(t) or {}
        r_ = tr.get('real') or tr.get('season') or {}; return r_.get('u', 0)
    TR = {'Strong': 3, 'Solid': 2, 'Lean': 1}
    # Nov 13 (Trina, A39/B91): rules run independently. Every fit whose rule tier is on is a card pick; two rules can both be
    # card picks in one game. Opposing picks (other team, or other side of the total): higher tier stays; same tier, more season units.
    chosen = {}; extra_cards = []
    mk_of = lambda c: 'total' if c['market'] == 'Total' else ('ml' if c['market'] == 'Moneyline' else 'side')
    for kind in ('side', 'total'):
        kf = [x for x in fits if (x['market'] == 'Total') == (kind == 'total')]
        el = [x for x in kf if eligible(x, kind)[0]]
        if not el: continue
        bp = g['side'] if kind == 'side' else g['total']
        el.sort(key=lambda x: (-TR[details(x, kind)[0]], -tunits(x, kind), 0 if (bp and x['rule'] == bp['rule'] and x['side'] == bp['side'] and x['market'] == bp['market']) else 1))
        win = el[0]; chosen[kind] = win
        card_doc(win, kind, upgraded=not STATE['rules'][win['rule']]['on'])
        if not STATE['rules'][win['rule']]['on']: UPG.append((g, win, kind))
        for x in el[1:]:
            if x['side'] == win['side']: extra_cards.append((x, kind))
    for x, kind in extra_cards:   # same direction as the top pick: its own card pick, doc id per rule
        lbl, ln = label_of(x); tier, basis, pro, con, rr, mdl, l5, exps = details(x, kind)
        did = f"{DATE}_{safe(a)}-{safe(h)}_{mk_of(x)}_{x['rule']}"
        d = dict(base(), market=x['market'], pick=lbl, price=int(x['price']), line=ln, side=x['side'], tier=tier, tier_basis=basis, rule=x['rule'], rule_key=x['rule'], rule_variant=x.get('variant'),
                 shadow=False, reasons=pro, against=con, rule_record=rr, model=mdl, last5=l5, experts=exps, rule_label=R.RULES[x['rule']]['name'], summary=SUMM(x, kind, lbl, ln),
                 note=f"Separate rule (Nov 13): also a card pick in this game beside {picks[kind]['pick']} ({R.RULES[chosen[kind]['rule']]['name']})")
        pdocs.append(dict(id=did, data={k: v for k, v in d.items() if v is not None}))
        picks_extra.append(dict(market=x['market'], pick=lbl, price=f"{int(x['price']):+d}", tier=tier, rule_label=R.RULES[x['rule']]['name'], doc_id=did))
    for c in fits:
        kd = 'total' if c['market'] == 'Total' else 'side'
        if chosen.get(kd) is c or any(c is x for x, _ in extra_cards): continue
        el, t = eligible(c, kd); w = chosen.get(kd)
        if c.get('gap_guard'): cf = c['gap_guard']['conflict']   # A57
        elif not el:
            if STATE['rules'][c['rule']]['on']: cf = f"The {t} tier of this rule is turned off because its status record is in the red"
            else: cf = f"This rule's {t} tier is off (no green status record for 2 pick days yet)"
        elif w is not None and w['side'] != c['side']:
            wt = picks[kd].get('tier'); cf = dict(text=(f"Card picked the other side of this total" if kd == 'total' else "Card is already backing the other team in this game") +
                                                f" ({picks[kd]['pick']}, {RN(w['rule'])}, {wt}); the higher tier, or the tier with more season units, stays the card pick",
                                                with_=picks[kd]['doc_id'], kept=picks[kd]['pick'])
            cf = f"{cf['text']} ('kept': '{cf['kept']}')"
        else:
            cf = "Not the card pick for this market"
        shadow_doc(c, kd, conflict=cf)
    for kind in ('side', 'total'):
        if kind in chosen: continue
        if not g['posted']: picks[kind] = dict(none='No book has posted a line for this game', analysis=ANALYSIS(kind)); continue
        if g.get('state', 'p') != 'p': picks[kind] = dict(none='This game had already tipped when the card ran, so no pick was made', analysis=ANALYSIS(kind)); continue
        kf = [x for x in fits if (x['market'] == 'Total') == (kind == 'total')]
        if kf and any(x.get('gap_guard') for x in kf): why = 'The rules that fit this market are held back by the gap guard or not active at their tier, so they are tracked as would be picks'
        elif kf: why = 'The only rules that fit this market are not active at their tier, so they are tracked as would be picks'
        elif kind == 'total': why = 'The total has not moved enough and our model total is close to the posted number, so no total rule fits'
        else: why = 'Neither team has the line movement, rest edge or model edge any side rule needs'
        picks[kind] = dict(none=why, analysis=ANALYSIS(kind))
    gd = dict(sport='ncaam', date=DATE, time=g['time'], kickoff_label=dt.strftime('%a ') + g['time'], status='scheduled',
              away=team(a, 0, g['aconf']), home=team(h, 1, g['hconf']), venue=ti[2] if ti else None, neutral=g['neutral'], conference_game=g['cg'],
              lines=lines, model=model, splits=splits, moves=moves, picks=picks, picks_extra=picks_extra or None, reasons=reasons,
              trends=dict(away=trend(a, B['rest_days'](a)), home=trend(h, B['rest_days'](h))), props=[], experts=[{k: v for k, v in x.items() if k != 'game'} for x in gx],
              injuries=[], notes=[f"Signal score {a} {S['sa']}, {h} {S['sh']} (lead {S['lead']:+d})", f"Line source: {lines['book']}" + ('' if g['src'] == 'texas222' else ' (The Odds API books have not posted this game)')])
    gdocs.append(dict(id=gid, data={k: v for k, v in gd.items() if v is not None}))
json.dump(pdocs, open(OUT/'picks.json', 'w'), indent=1); json.dump(SHADOW, open(OUT/'shadow.json', 'w'), indent=1); json.dump(gdocs, open(OUT/'games_today.json', 'w'))
# ---------- yesterday's finals onto game docs, expert grading
Y = {}
for l in (W/'data'/'raw'/f'y_{YD}.txt').read_text().strip().splitlines():
    f = l.split('|')
    if f[0] == 'M': Y[(f[3], f[2])] = dict(as_=int(f[11]), hs=int(f[10]), a1=int(f[13]) if f[13] else None, h1=int(f[12]) if f[12] else None)
yiso = f"{YD[:4]}-{YD[4:6]}-{YD[6:]}"; ups, egr = [], []
for fp in sorted(glob.glob(str(W/'hub'/'sports'/'ncaam'/'games'/f'{yiso}_*.json'))):
    d = json.load(open(fp)); a, h = d['away']['code'], d['home']['code']; y = Y.get((a, h))
    if not y and Y.get((h, a)):   # ESPN lists home and away the other way round (neutral site games, Nov 9)
        r_ = Y[(h, a)]; y = dict(as_=r_['hs'], hs=r_['as_'], a1=r_['h1'], h1=r_['a1'])
    if not y: print('no final for', fp); continue
    _pc = PCLOSE.get((yiso, a, h)) or (lambda z: dict(spread_home=-z['spread_home'], total=z['total'], books=z.get('books')) if z else None)(PCLOSE.get((yiso, h, a)))
    _upd = dict(status='final', final=f"{a} {y['as_']}, {h} {y['hs']}")
    if _pc:
        _f = lambda v: 'PK' if v == 0 else f"{v:+g}"
        _upd['periods_close'] = {'1H': dict(spread=dict(away=_f(-_pc['spread_home']), home=_f(_pc['spread_home'])), total=dict(over=f"{_pc['total']:g}", under=f"{_pc['total']:g}"),
                                            source=f"The Odds API closing median ({_pc.get('books')} books)")}
    ups.append(dict(id=pathlib.Path(fp).stem, data=_upd))
    for x in d.get('experts', []):
        m = x['market']; side = x.get('side'); ln = x.get('line'); pr = x.get('price')
        first = m.startswith('1H'); A, Hh = (y['a1'], y['h1']) if first else (y['as_'], y['hs'])
        if A is None: continue
        if 'Total' in m: t = A + Hh; r = (t > ln) - (t < ln) if side == 'Over' else (t < ln) - (t > ln)
        elif 'Spread' in m: mm = (Hh - A) if side == h else (A - Hh); r = (mm + ln > 0) - (mm + ln < 0)
        else: r = 1 if ((Hh > A) if side == h else (A > Hh)) else -1
        p = int(pr) if pr not in (None, '') else -110
        u = (p/100 if p > 0 else 100/-p) if r > 0 else (-1 if r < 0 else 0)
        did = f"{yiso}_{a}-{h}_{safe(x['name'])}_{safe(m)}_{safe(x['pick'])}"[:200]
        egr.append(dict(id=did, data=dict(date=yiso, game=f"{a} @ {h}", name=x['name'], platform=x['platform'], pick=x['pick'], market=m, side=side, line=ln, price=pr,
                                          record=x.get('record'), final=f"{a} {y['as_']}, {h} {y['hs']}" + (f" (1H {a} {A}, {h} {Hh})" if first else ''),
                                          result={1: 'win', -1: 'loss', 0: 'push'}[r], units=round(u, 2), url=x.get('url'))))
json.dump(ups, open(OUT/'games_yday.json', 'w')); json.dump(egr, open(OUT/'experts.json', 'w'), indent=1)
print(len(pdocs), 'pick docs;', len(gdocs), 'game docs;', len(ups), 'final updates;', len(egr), 'expert grades')
