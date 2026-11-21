"""CFB card model: reads the cfb-card repo data plus the day's browser pulls,
builds features, scores signals, picks a side and a total per game, grades props.
Run: python3 model.py fbs|fcs  -> writes slate_<div>.json
Inputs (same folder):
  repo/ games.csv games_prior.csv lines.csv power_ratings.csv weather.csv venues.csv talent_2026.csv model_state.json meta.json
  live_numbers.json  our spread/total per game, parsed from the repo's docs/index.html (parse_live.py)
  t222_fbs.txt t222_fcs.txt t222_props.txt  texas222 boards
  an_raw.txt an_sharp.txt  Action Network public betting and sharp report
  injuries.json players_raw.txt signals.json
"""
import json, copy, math, re, sys, ast, unicodedata
from pathlib import Path
import numpy as np, pandas as pd
import rules as RU
from sklearn.linear_model import Ridge

D = Path(__file__).parent
R = D / 'repo'
DIV = sys.argv[1] if len(sys.argv) > 1 else 'fbs'
SIG = json.load(open(D / 'signals.json'))
RULES = SIG['rules_' + (sys.argv[1] if len(sys.argv) > 1 else 'fbs')]
SNAP = []          # Action Network numbers per game, saved for the end-of-week re-check
MS = json.load(open(R / 'model_state.json'))
META = json.load(open(R / 'meta.json'))
PHX = 'America/Phoenix'
P4 = {'ACC', 'Big 12', 'Big Ten', 'SEC'}
REPORT = []          # problems found, shown on the card (Needs attention)

def norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z]', '', s.lower())

# ---------------- games ----------------
G = pd.read_csv(R / 'games.csv')
G = G[G.season == 2026].copy()
G['dt'] = pd.to_datetime(G.startDate, utc=True).dt.tz_convert(PHX)
G['done'] = G.completed.astype(str).str.lower().eq('true')
fbs_side = (G.homeClassification == 'fbs') | (G.awayClassification == 'fbs')
WEEK = int(G[fbs_side & ~G.done & (G.seasonType == 'regular')].week.min())
WEEK = int(__import__("os").environ.get("WEEK", WEEK))  # Nov 15: preview the next week while a postponed week 11 game is still open
NOW = pd.Timestamp.now(tz=PHX)
if DIV == 'fbs':
    SL = G[(G.week == WEEK) & fbs_side & (G.seasonType == 'regular')]
else:
    SL = G[(G.week == WEEK) & (G.homeClassification == 'fcs') & (G.awayClassification == 'fcs') & (G.seasonType == 'regular')]
SL = SL[~SL.done].sort_values(['dt', 'awayTeam'])
_old = SL[SL.dt.dt.date < NOW.date()]
if len(_old):
    REPORT.append(f"{len(_old)} game(s) from earlier days are not final in the repo yet ({', '.join(_old.awayTeam + ' @ ' + _old.homeTeam)}); left off the slate, picks graded from ESPN.")
SL = SL[SL.dt.dt.date >= NOW.date()]
PLAYED = G[G.done & G.homePoints.notna()].copy()
PLAYED['margin'] = PLAYED.homePoints - PLAYED.awayPoints
PRIOR = pd.read_csv(R / 'games_prior.csv')
PRIOR = PRIOR[(PRIOR.season == 2025) & PRIOR.homePoints.notna()]
CLS = {}
for r in G.itertuples():
    CLS[r.homeTeam] = r.homeClassification; CLS[r.awayTeam] = r.awayClassification
CONF = {}
for r in G.itertuples():
    CONF[r.homeTeam] = r.homeConference; CONF[r.awayTeam] = r.awayConference

# ---------------- ratings & our numbers ----------------
PR = pd.read_csv(R / 'power_ratings.csv').set_index('team')
LIVE = json.load(open(D / 'live_numbers.json'))
def parse_side(s):
    m = re.match(r'(.+?) ([+-]\d+(?:\.\d+)?)$', (s or '').strip())
    return (m.group(1), float(m.group(2))) if m else (None, None)
def our_home_margin(a, h):
    L = LIVE.get(f'{a}@{h}')
    if L and L.get('our_spread'):
        t, v = parse_side(L['our_spread'])
        if t == h: return -v, 'card'
        if t == a: return v, 'card'
    if a in PR.index and h in PR.index:
        neu = False
        return PR.rating[h] - PR.rating[a] + META['hfa'], 'ratings'
    return None, None
def our_total(a, h):
    L = LIVE.get(f'{a}@{h}')
    try: return float(L['our_total'])
    except Exception: return None

# ---------------- texas222 ----------------
ALIAS = {'miamiflorida': 'Miami', 'centralflorida': 'UCF', 'sacramentost': 'Sacramento State', 'mississippi': 'Ole Miss',
         'floridainternational': 'Florida International', 'connecticut': 'UConn', 'sanjosestate': 'San José State',
         'appalachianstate': 'App State', 'socarolinast': 'South Carolina State', 'ulmonroe': 'UL Monroe',
         'miamiohio': 'Miami (OH)', 'hawaii': "Hawai'i", 'massachusetts': 'Massachusetts',
         'ullafayette': 'Louisiana', 'middletennesseestate': 'Middle Tennessee', 'samhoustonst': 'Sam Houston',
         'texasaandm': 'Texas A&M'}   # Nov 10: texas222 writes TEXAS A AND M
NAMES = {norm(t): t for t in set(G.homeTeam) | set(G.awayTeam)}
def resolve(code):
    k = norm(code)
    if k in ALIAS and ALIAS[k] in set(G.homeTeam) | set(G.awayTeam): return ALIAS[k]
    if k in ALIAS and norm(ALIAS[k]) in NAMES: return NAMES[norm(ALIAS[k])]
    return NAMES.get(k)

def frac(s):
    return s.replace('½', '.5')
def parse_t222(path):
    out = {}
    txt = (D / path).read_text().strip()
    if not txt: return out
    rows = [r.split(',') for r in txt.split(';')]
    for i in range(0, len(rows) - 1, 2):
        a, h = rows[i], rows[i + 1]
        ta, th = resolve(a[3]), resolve(h[3])
        if not ta or not th:
            REPORT.append(f'texas222 name not matched: {a[3]} / {h[3]} (left out, not guessed)'); continue
        def sp(x):
            m = re.match(r'(PK|[+-][\d.½]+)\s*([+-]\d+)', x.replace(' ', ''))
            if not m: return None, None
            v = 0.0 if m.group(1) == 'PK' else float(frac(m.group(1)))
            return v, int(m.group(2))
        def tot(x):
            m = re.match(r'(Ov|Un)([\d.½]+)([+-]\d+)', x)
            return (float(frac(m.group(2))), int(m.group(3))) if m else (None, None)
        sa, pa = sp(a[4]); sh, ph = sp(h[4]); tl, po = tot(a[5]); _, pu = tot(h[5])
        ml = lambda x: int(x) if re.match(r'^[+-]\d+$', x or '') else None
        out[(ta, th)] = dict(rot=int(a[2]), spread_a=sa, price_a=pa, spread_h=sh, price_h=ph, total=tl, over=po, under=pu,
                             ml_a=ml(a[6] if len(a) > 6 else ''), ml_h=ml(h[6] if len(h) > 6 else ''), src='The Odds API median of books',
                             lock=f'{a[0]} {a[1]}')
    return out
T222 = parse_t222('t222_fbs.txt' if DIV == 'fbs' else 't222_fcs.txt')

# Nov 11 (B41): The Odds API median moneyline as the last backup (latest pull in odds_y.json / odds_t.json)
ODDS_BK = {}
try:
    _TM = pd.read_csv(R / 'teams.csv')
    _mas = {f"{r.school} {r.mascot}": r.school for r in _TM.itertuples() if isinstance(r.mascot, str)}
    for _fn in ('odds_y.json', 'odds_t.json'):
        if not (D / _fn).exists(): continue
        for _k, _v in json.load(open(D / _fn)).items():
            _a, _h = _mas.get(_v['away']), _mas.get(_v['home']); _ln = _v.get('close') or _v.get('open') or {}
            if _a and _h and _ln.get('ml_away') is not None: ODDS_BK[(_a, _h)] = (_ln['ml_away'], _ln['ml_home'])
except Exception as _e: print('odds backup skipped', _e)
# CFBD consensus as the fallback book
LN = pd.read_csv(R / 'lines.csv')
CONS = {}
for r in LN[(LN.season == 2026) & (LN.week == WEEK)].itertuples():
    CONS[(r.awayTeam, r.homeTeam)] = RU.consensus(r.lines, MS['thresholds']['ml_sane'])   # clean moneyline, same as the re-check

# ---------------- Action Network ----------------
def parse_an():
    pub, sh = {}, {}
    for line in (D / 'an_raw.txt').read_text().splitlines():
        mk, body = line.split(' ', 1)
        for r in body.split(';'):
            p = r.split(',')
            if len(p) < 4 or not p[2]: continue
            pub.setdefault(int(p[0]), {})[mk] = dict(open=p[1], bets=int(p[2].rstrip('%')), money=int(p[3].rstrip('%')))
    for line in (D / 'an_sharp.txt').read_text().splitlines():
        mk, body = line.split(' ', 1)
        for r in body.split(';'):
            rot, lit = r.split(':')
            sh.setdefault(int(rot), {})[mk] = lit.split('+')
    return pub, sh
AN_PUB, AN_SH = parse_an()   # keyed by rotation number; FCS games get Action Network numbers when AN lists them

# ---------------- injuries, weather, venues ----------------
INJ = json.load(open(D / 'injuries.json'))
WX = pd.read_csv(R / 'weather.csv').set_index('game_id') if (R / 'weather.csv').exists() else pd.DataFrame()
V = pd.read_csv(R / 'venues.csv')
TZ = {'America/New_York': -5, 'America/Detroit': -5, 'America/Indiana/Indianapolis': -5, 'America/Kentucky/Louisville': -5,
      'America/Chicago': -6, 'America/Denver': -7, 'America/Boise': -7, 'America/Phoenix': -7, 'America/Los_Angeles': -8,
      'Pacific/Honolulu': -10, 'America/Anchorage': -9}
VTZ = {int(r.id): TZ.get(r.timezone) for r in V.itertuples() if isinstance(r.timezone, str)}
VNAME = {int(r.id): f'{r.name}, {r.city} {r.state if isinstance(r.state, str) else ""}'.strip() for r in V.itertuples()}
homev = pd.concat([PLAYED[~PLAYED.neutralSite.astype(bool)][['homeTeam', 'venueId']], PRIOR[~PRIOR.neutralSite.astype(bool)][['homeTeam', 'venueId']]])
TEAMTZ = {t: VTZ.get(int(s.mode().iloc[0])) for t, s in homev.dropna().groupby('homeTeam').venueId}
TAL = pd.read_csv(R / 'talent_2026.csv').set_index('team').talent.to_dict()

# ---------------- features ----------------
def log_of(team):
    rows = []
    for r in PLAYED.itertuples():
        if r.homeTeam == team: side, m, pf, pa = ('N' if r.neutralSite else 'H'), r.margin, r.homePoints, r.awayPoints
        elif r.awayTeam == team: side, m, pf, pa = ('N' if r.neutralSite else 'R'), -r.margin, r.awayPoints, r.homePoints
        else: continue
        opp = r.awayTeam if r.homeTeam == team else r.homeTeam
        rows.append(dict(dt=r.dt, v=side, m=m, pf=pf, pa=pa, opp=opp, conf=bool(r.conferenceGame)))
    return sorted(rows, key=lambda x: x['dt'])
LOGS = {}
def lg(t):
    if t not in LOGS: LOGS[t] = log_of(t)
    return LOGS[t]
def rec(rows):
    w = sum(1 for x in rows if x['m'] > 0); return w, len(rows) - w
def rp(w, n, k): return (w + 0.5 * k) / (n + k)
def streak(rows):
    s = 0
    for x in reversed(rows):
        if s >= 0 and x['m'] > 0: s += 1
        elif s <= 0 and x['m'] < 0: s -= 1
        else: break
    return s
LAST = {}
for t in set(PRIOR.homeTeam) | set(PRIOR.awayTeam):
    h = PRIOR[PRIOR.homeTeam == t]; a = PRIOR[PRIOR.awayTeam == t]
    w = (h.homePoints > h.awayPoints).sum() + (a.awayPoints > a.homePoints).sum(); n = len(h) + len(a)
    if n: LAST[t] = (w / n, int(w), int(n - w))

def conf_label(team):
    c = CLS.get(team)
    if c == 'fcs': return 'FCS'
    if c != 'fbs': return None
    return CONF.get(team)
def conference_table():
    rows = []
    for r in PLAYED.itertuples():
        a, b = conf_label(r.homeTeam), conf_label(r.awayTeam)
        if a is None or b is None or a == b: continue
        rows.append((a, b, 0.0 if r.neutralSite else 1.0, float(np.clip(r.margin, -40, 40)), r.homeTeam, r.awayTeam, r.margin))
    confs = sorted({x[0] for x in rows} | {x[1] for x in rows}); ix = {c: i for i, c in enumerate(confs)}
    X = np.zeros((len(rows), len(confs) + 1)); y = np.zeros(len(rows))
    for k, (a, b, h, m, *_rest) in enumerate(rows):
        X[k, ix[a]] = 1; X[k, ix[b]] = -1; X[k, -1] = h; y[k] = m
    m = Ridge(alpha=6.0, fit_intercept=False).fit(X, y)
    rt = pd.Series(m.coef_[:-1], index=confs); fb = [c for c in confs if c != 'FCS']; rt = rt - rt[fb].mean()
    tab = {}
    for c in confs:
        d = dict(rating=round(float(rt[c]), 1), w=0, l=0, pf=0, pa=0, n=0, vs={})
        for (a, b, h, mc, ht, at, mg) in rows:
            if c not in (a, b): continue
            mine = mg if a == c else -mg; opp = b if a == c else a
            grp = 'FCS' if opp == 'FCS' else ('Power 4' if opp in P4 or opp == 'FBS Independents' and False else ('Group of 5' if opp not in P4 and opp != 'FBS Independents' else 'Independents'))
            d['n'] += 1; d['w'] += mine > 0; d['l'] += mine < 0
            v = d['vs'].setdefault(grp, [0, 0]); v[0] += mine > 0; v[1] += mine < 0
            d['pf'] += mine
        tab[c] = d
    return tab, len(rows)
CONFTAB, NCONF = conference_table()

def implied(o):
    return 100 / (o + 100) if o > 0 else -o / (-o + 100)
def novig(a, b):
    if a is None or b is None: return None, None
    x, y = implied(a), implied(b); return x / (x + y), y / (x + y)
def Phi(z): return 0.5 * (1 + math.erf(z / math.sqrt(2)))
SD_SPREAD = math.sqrt(MS['simulation']['line_sd'] ** 2 + MS['simulation']['margin_sd'] ** 2)
SD_TOTAL = math.sqrt(MS['simulation']['total_line_sd'] ** 2 + MS['simulation']['total_sd'] ** 2)

def fmt_line(v):
    if v is None: return '·'
    if v == 0: return 'PK'
    return f'{v:+g}'
def fmt_price(p): return '·' if p is None else (f'+{p}' if p > 0 else str(p))

# ---------------- freshness: no picks on lines read before today ----------------
PULL = pd.Timestamp((D / 'pull_time.txt').read_text().strip()) if (D / 'pull_time.txt').exists() else None
if PULL is not None and PULL.tzinfo is None: PULL = PULL.tz_localize(PHX)
LINES_FRESH = PULL is not None and PULL.tz_convert(PHX).strftime('%Y-%m-%d') == NOW.strftime('%Y-%m-%d')
if not LINES_FRESH and (SL.dt.dt.date == NOW.date()).any():
    REPORT.append(f"Lines and splits were last read {PULL.tz_convert(PHX).strftime('%b %-d %-I:%M %p') if PULL is not None else 'never'}, not today, so no picks are made. Run CFB Card to read today's lines.")

# ---------------- per game ----------------
S, T = SIG['side'], SIG['total']
games = []
for r in SL.itertuples():
    a, h = r.awayTeam, r.homeTeam
    g = dict(id=int(r.id), away=a, home=h, dt=r.dt.isoformat(), date=r.dt.strftime('%Y-%m-%d'), day=r.dt.strftime('%a'),
             time=r.dt.strftime('%-I:%M %p'), neutral=bool(r.neutralSite), confgame=bool(r.conferenceGame),
             conf_a=r.awayConference, conf_h=r.homeConference, cls_a=r.awayClassification, cls_h=r.homeClassification,
             venue=VNAME.get(int(r.venueId), '') if r.venueId == r.venueId else '', started=bool(r.dt <= NOW) or bool(r.done))
    cross = {r.homeClassification, r.awayClassification} == {'fbs', 'fcs'}
    g['reference_only'] = cross
    # lines
    L = T222.get((a, h)); C = CONS.get((a, h), {})
    if L and L['spread_h'] is not None:
        g['book'] = 'The Odds API median of books'; g.update(spread_h=L['spread_h'], price_a=L['price_a'], price_h=L['price_h'], total=L['total'],
            over=L['over'], under=L['under'], ml_a=L['ml_a'], ml_h=L['ml_h'], rot=L['rot'], lock=L['lock'])
    elif C.get('spread_h') is not None:
        g['book'] = f"consensus of {C['books']} books (Odds API line not posted)"; g.update(spread_h=C['spread_h'], price_a=-110, price_h=-110,
            total=C['total'], over=-110, under=-110, ml_a=C['ml_a'], ml_h=C['ml_h'], rot=None, lock='')
    else:
        g['book'] = None
    g['open_h'] = C.get('open_h'); g['tot_open_cfbd'] = C.get('tot_open')
    g['ml_book'] = 'The Odds API median of books' if g.get('book') == 'The Odds API median of books' and g.get('ml_a') is not None else None
    if g.get('book') and g.get('ml_book') is None and C.get('dk_ml_a') is not None:
        g['ml_a'], g['ml_h'], g['ml_book'] = C['dk_ml_a'], C['dk_ml_h'], 'DraftKings'   # Nov 11 (Trina, B41): backup line for every game, DraftKings first
    elif g.get('book') and g.get('ml_book') is None and ODDS_BK.get((a, h)):
        g['ml_a'], g['ml_h'], g['ml_book'] = ODDS_BK[(a, h)][0], ODDS_BK[(a, h)][1], 'The Odds API'   # then The Odds API median
    g['line_source'] = 'The Odds API median of books' if g.get('book') == 'The Odds API median of books' else ('consensus' if g.get('book') else None)
    hm, src = our_home_margin(a, h); g['our_margin'] = hm; g['our_src'] = src; g['our_total'] = our_total(a, h)
    for t, k in ((a, 'a'), (h, 'h')):
        g['rating_' + k] = round(float(PR.rating[t]), 1) if t in PR.index else None
        g['rank_' + k] = int(PR['rank'][t]) if t in PR.index and PR['rank'][t] == PR['rank'][t] else None
        rows = lg(t); w, l = rec(rows)
        g['rec_' + k] = f'{w}-{l}'
        g['wp_' + k] = (w / (w + l)) if (w + l) else None; g['n_' + k] = w + l
        cw = sum(1 for x in rows if x['conf'] and x['m'] > 0); cl = sum(1 for x in rows if x['conf'] and x['m'] < 0)
        g['crec_' + k] = f'{cw}-{cl}'
        hv = [x for x in rows if x['v'] == ('H' if k == 'h' else 'R')]
        hw, hl = rec(hv); g['venue_rec_' + k] = f'{hw}-{hl}'; g['venue_rp_' + k] = rp(hw, len(hv), 4)
        nv = [x for x in rows if x['v'] == 'N']; g['neutral_rec_' + k] = '%d-%d' % rec(nv)
        g['streak_' + k] = streak(rows)
        g['pd_' + k] = round(float(np.mean([x['m'] for x in rows])), 1) if rows else None
        g['ppg_' + k] = round(float(np.mean([x['pf'] for x in rows])), 1) if rows else None
        g['papg_' + k] = round(float(np.mean([x['pa'] for x in rows])), 1) if rows else None
        g['last3_tot_' + k] = round(float(np.mean([x['pf'] + x['pa'] for x in rows[-3:]])), 1) if len(rows) >= 3 else None
        g['last5_' + k] = ' '.join(('W' if x['m'] > 0 else 'L') for x in rows[-5:])
        g['rest_' + k] = RU.cal_days(r.dt, rows[-1]['dt']) if rows else None
        vz = VTZ.get(int(r.venueId)) if r.venueId == r.venueId else None
        tz = TEAMTZ.get(t); g['tz_' + k] = abs(vz - tz) if vz is not None and tz is not None else None
        g['last_' + k] = LAST.get(t)
        g['talent_' + k] = TAL.get(t)
        g['inj_' + k] = INJ.get(t, [])
        cl_ = conf_label(t); g['confrt_' + k] = CONFTAB.get(cl_, {}).get('rating')
    # weather
    if len(WX) and r.id in WX.index:
        w = WX.loc[r.id]; g['wx'] = dict(temp=float(w.temp_f), precip=int(w.precip_pct), wind=float(w.wind_mph))
    else: g['wx'] = None
    # ---------- signals ----------
    # Scored signals (rest, last season, Action Network, line moves, recent scoring) come from rules.py,
    # the same code the end-of-week re-check runs on every game played. Below them, model.py adds
    # display-only signals that score 0.
    rot = g.get('rot'); pub = AN_PUB.get(rot, {}) if rot else {}; shp = AN_SH.get(rot, {}) if rot else {}
    g['an'] = dict(pub=pub, sharp=shp)
    xin = dict(a=a, h=h, rest_a=g['rest_a'], rest_h=g['rest_h'], last_a=g['last_a'], last_h=g['last_h'],
               l3_a=g['last3_tot_a'], l3_h=g['last3_tot_h'], spread_h=g.get('spread_h'), open_h=g.get('open_h'),
               total=g.get('total'), tot_open=g.get('tot_open_cfbd'), ml_a=g.get('ml_a'), ml_h=g.get('ml_h'),
               wp_a=g['wp_a'], wp_h=g['wp_h'], n_a=g['n_a'], n_h=g['n_h'],
               an=dict(pub=pub, sharp=shp))
    sideS, mlS, totS = RU.build_signals(xin, SIG)
    for k_ in ('move_a', 'open_a', 'recent_tot', 'tot_open_an'):
        if k_ in xin: g[k_ if k_ != 'tot_open_an' else 'tot_open'] = xin[k_]
    if pub or shp:
        SNAP.append(dict(id=g['id'], taken=NOW.isoformat(timespec='minutes'), an=dict(pub=pub, sharp=shp)))
    def add(lst, key, team, pts_over=None, detail=''):
        spec = S.get(key) or T.get(key)
        p = spec['pts'] if pts_over is None else pts_over
        lst[team].append(dict(key=key, label=spec['label'], pts=p, status=spec['status'], detail=detail))
    other = {a: h, h: a}
    for t, k, o, ko in ((a, 'a', h, 'h'), (h, 'h', a, 'a')):
        ro, rt_ = g['rest_' + ko], g['rest_' + k]
        if rt_ is not None and ro is not None and rt_ >= 13 and ro <= 9:
            add(sideS, 'bye', t, detail=f'{t} off a bye ({rt_} days), {o} {ro}')
        if g['tz_' + ko] is not None and g['tz_' + ko] >= 2 and (g['tz_' + k] or 0) < 2:
            add(sideS, 'travel', t, detail=f'{o} crossed {g["tz_" + ko]} time zones')
        if g['streak_' + k] >= 3 and g['streak_' + ko] < 3: add(sideS, 'hot_streak', t, detail=f'{t} won {g["streak_" + k]} straight')
        if g['streak_' + ko] <= -3 and g['streak_' + k] > -3: add(sideS, 'cold_opp', t, detail=f'{o} lost {-g["streak_" + ko]} straight')
        if g['pd_' + k] is not None and g['pd_' + ko] is not None and g['pd_' + k] - g['pd_' + ko] >= 7:
            add(sideS, 'form_pd', t, detail=f'point differential {g["pd_" + k]:+.1f} vs {g["pd_" + ko]:+.1f} per game')
        if g['talent_' + k] and g['talent_' + ko] and g['talent_' + k] - g['talent_' + ko] >= 100:
            add(sideS, 'talent', t, detail=f'talent {g["talent_" + k]:.0f} vs {g["talent_" + ko]:.0f}')
        for p in g['inj_' + ko]:
            if p.get('qb1') and p['status'] == 'OUT' and p.get('confirmed', True): add(sideS, 'qb_out', t, detail=f"{o} QB {p['player']} out ({p.get('source', 'report')})")
    if not g['confgame'] and g['confrt_a'] is not None and g['confrt_h'] is not None and conf_label(a) != conf_label(h):
        d = g['confrt_h'] - g['confrt_a']
        if abs(d) >= S['conf_strength']['gap']:
            t = h if d > 0 else a
            add(sideS, 'conf_strength', t, detail=f'{conf_label(t)} rates {abs(d):.1f} pts stronger in non-conference games')
    if not g['neutral']:
        add(sideS, 'home_field', h, detail='home team')
        d = g['venue_rp_h'] - g['venue_rp_a']
        if abs(d) >= S['venue_split']['gap']:
            t = h if d > 0 else a
            add(sideS, 'venue_split', t, detail=f'{h} {g["venue_rec_h"]} at home vs {a} {g["venue_rec_a"]} on the road')
    if g.get('spread_h') is not None and hm is not None:
        cover_h = hm + g['spread_h']
        g['model_cover_h'] = Phi(cover_h / SD_SPREAD)
        t = h if cover_h > 0 else a
        add(sideS, 'projection', t, detail=f'our number {h} {-hm:+.1f} vs line {fmt_line(g["spread_h"])}')
        g['proj_side'] = t
    else:
        g['proj_side'] = None; g['model_cover_h'] = None
    if g.get('total') is not None:
        if g['our_total'] is not None:
            side = 'Over' if g['our_total'] > g['total'] else 'Under'
            totS[side].append(dict(key='projection', label=T['projection']['label'], pts=T['projection']['pts'], status=T['projection']['status'], detail=f'our total {g["our_total"]:.1f} vs {g["total"]:g}'))
            g['model_over'] = 1 - Phi((g['total'] - g['our_total']) / SD_TOTAL)
        wx = g['wx']
        if wx and (wx['wind'] >= 15 or wx['precip'] >= 60):
            totS['Under'].append(dict(key='weather', label=T['weather']['label'], pts=T['weather']['pts'], status=T['weather']['status'], detail=f"wind {wx['wind']:.0f} mph, rain {wx['precip']}%"))
        if g['confgame']:
            totS['Under'].append(dict(key='conf_game_under', label=T['conf_game_under']['label'], pts=T['conf_game_under']['pts'], status=T['conf_game_under']['status'], detail='conference game'))
    g['sig_side'] = sideS; g['sig_ml'] = mlS; g['sig_tot'] = totS
    # ---------- picks: rules from signals.json rules_<div>, applied by rules.decide ----------
    picks = []
    g['nopick'] = None
    if g['book'] and not g['reference_only']:
        sp_, tp_, inf = RU.decide(xin, sideS, totS, RULES)
        g['rule_info'] = inf
        # Nov 11 2026 (Trina, B40): log every rule fit. Each rule is tried on its own (on or off); fits other than the
        # card order winner are kept in g['fits'] and logged as would-be picks with the reason.
        _extra = []
        for _nm in RULES['order']:
            _R1 = copy.deepcopy(RULES)
            for _k2 in _R1['side']: _R1['side'][_k2]['on'] = (_k2 == _nm)
            for _k3 in _R1['total']: _R1['total'][_k3]['on'] = False
            _s1, _, _ = RU.decide(xin, sideS, totS, _R1)
            if _s1 and not (sp_ and _s1['rule'] == sp_['rule']): _extra.append(dict(_s1, extra=True))
        for _tn in RULES['total']:   # Nov 14 (B91): each total rule tried on its own
            _R1 = copy.deepcopy(RULES)
            for _k3 in _R1['total']: _R1['total'][_k3]['on'] = (_k3 == _tn)
            for _k2 in _R1['side']: _R1['side'][_k2]['on'] = False
            _, _t1, _ = RU.decide(xin, sideS, totS, _R1)
            if _t1 and not (tp_ and _t1['rule'] == tp_['rule']): _extra.append(dict(_t1, extra=True))
        _all = [sp_, tp_] + _extra
        for p_ in _all:
            if not p_: continue
            R_ = RULES['total'][p_['rule']] if p_['rule'] in RULES['total'] else RULES['side'][p_['rule']]
            rec_ = R_.get('record_text', '')
            if p_['market'] == 'Total':
                side = p_['k']; os_ = 'Under' if side == 'Over' else 'Over'
                price = g['over'] if side == 'Over' else g['under']
                mp = g.get('model_over'); mp = (mp if side == 'Over' else 1 - mp) if mp is not None else None
                nv = novig(g['over'], g['under']); mkp = (nv[0] if side == 'Over' else nv[1]) if nv[0] is not None else None
                lead = abs(RU.score(totS['Over']) - RU.score(totS['Under']))
                picks.append(dict(kind='total', rule=p_['rule'], rule_label=R_['label'], rule_text=R_['text'], rule_record=rec_,
                                  market='Total', team=side, text=f'{side} {g["total"]:g}', price=price, line=g['total'], tier=p_['tier'], lead=lead,
                                  conflicting=any(x['key'] == 'sharp_action' for x in totS[os_]), model_p=mp, market_p=mkp,
                                  tested=sum(x['pts'] for x in totS[side] if x['pts'] > 0 and x['status'] == 'validated'),
                                  score=sum(x['pts'] for x in totS[side] if x['pts'] > 0), why=totS[side], against=totS[os_]))
            else:
                k = p_['k']; team = a if k == 'a' else h; o = other[team]
                src = sideS
                if p_['market'] == 'Spread':
                    line = -g['spread_h'] if k == 'a' else g['spread_h']; price = g['price_a'] if k == 'a' else g['price_h']
                    text = f'{team} {fmt_line(line)}'
                    prob = g['model_cover_h'] if team == h else (1 - g['model_cover_h'] if g['model_cover_h'] is not None else None)
                    nv = novig(g['price_a'], g['price_h'])
                else:
                    line = None; price = g['ml_a'] if k == 'a' else g['ml_h']; text = f'{team} ML'
                    prob = Phi(((hm if team == h else -hm)) / SD_SPREAD) if hm is not None else None
                    nv = novig(g['ml_a'], g['ml_h'])
                mkp = (nv[0] if k == 'a' else nv[1]) if nv[0] is not None else None
                picks.append(dict(kind='side', rule=p_['rule'], reasons=p_.get('reasons', []), book=(g.get('ml_book') if p_['market'] == 'Moneyline' else g['book']), rule_label=R_['label'], rule_text=R_['text'], rule_record=rec_,
                                  market=p_['market'], team=team, text=text, price=price, line=line, tier=p_['tier'], lead=inf['lead'],
                                  conflicting=any(x['key'] in ('sharp_action', 'rlm') for x in src[o]), model_p=prob, market_p=mkp,
                                  tested=sum(x['pts'] for x in src[team] if x['pts'] > 0 and x['status'] == 'validated'),
                                  score=sum(x['pts'] for x in src[team] if x['pts'] > 0),
                                  why=[x for x in src[team] if x['pts'] > 0] + [x for x in src[team] if x['pts'] == 0], against=src[o]))
        _flags = [bool(p_.get('extra')) for p_ in _all if p_]
        g['fits'] = [pk for pk, f in zip(picks, _flags) if f]; picks = [pk for pk, f in zip(picks, _flags) if not f]
        for pk, p_ in zip(g['fits'], [p_ for p_ in _all if p_ and p_.get('extra')]): pk['tier'] = p_['tier']
        # why no side pick, in one line
        if not sp_ and any(R_.get('kind') == 'dog_reasons' for R_ in RULES['side'].values()):
            fv = inf['fav']; dg_ = None if not fv else ('h' if fv == 'a' else 'a')
            rs_ = inf.get('reasons', [])
            g['nopick'] = ('No favorite or underdog could be set.' if not dg_ else
                           f"Underdog {a if dg_ == 'a' else h} has " + (('one reason (' + rs_[0] + ') but the line is over +' + str(RULES['side']['fcs_dog_spread']['max_line_one_reason'])) if rs_ else 'no reason (short week, last season, better record)') + '. FCS backs underdogs only.')
        elif not sp_:
            if not inf['pick']: g['nopick'] = 'Signals tied on the side, so no rule applies.'
            else:
                t_ = a if inf['pick'] == 'a' else h
                fv = inf['fav']; isdog = fv and inf['pick'] != fv
                pr_ = g.get('ml_' + inf['pick'])
                g['nopick'] = (f"Signals favor {t_} (lead {inf['lead']}) but no rule fits: " +
                               (f"underdog at {fmt_price(pr_)} without a line move toward it" if isdog else f"favorite at {fmt_price(pr_)}, outside -200 to -100, lead under {RULES['side']['strong_spread']['min_lead']}") + '.')
    elif g['book'] and g['reference_only'] and DIV == 'fbs':
        # FBS favorite vs FCS, week 11+ (Trina, Nov 9 2026); every other FBS rule stays off these games
        R_ = RULES['side'].get('fbs_fav_vs_fcs'); fk = 'h' if g['cls_h'] == 'fbs' else 'a'
        p_ = RU.fbs_fav_vs_fcs(xin, WEEK, R_, fk)
        if p_:
            k = p_['k']; team = a if k == 'a' else h; o = other[team]
            line = -g['spread_h'] if k == 'a' else g['spread_h']; price = g['price_a'] if k == 'a' else g['price_h']
            nv = novig(g['price_a'], g['price_h']); mkp = (nv[0] if k == 'a' else nv[1]) if nv[0] is not None else None
            lead = abs(RU.score(sideS[a]) - RU.score(sideS[h]))
            picks.append(dict(kind='side', rule=p_['rule'], reasons=[], book=g['book'], rule_label=R_['label'], rule_text=R_['text'], rule_record=R_.get('record_text', ''),
                              market='Spread', team=team, text=f'{team} {fmt_line(line)}', price=price, line=line, tier=p_['tier'], lead=lead,
                              conflicting=any(x['key'] in ('sharp_action', 'rlm') for x in sideS[o]), model_p=None, market_p=mkp,
                              tested=0, score=sum(x['pts'] for x in sideS[team] if x['pts'] > 0),
                              why=[dict(key='fbs_fav_vs_fcs', label='FBS favorite vs FCS, week 11+', pts=0, status='validated',
                                        detail=R_.get('record_text', ''))] + [x for x in sideS[team] if x['pts'] > 0], against=sideS[o]))
        elif R_ and R_.get('on'):
            g['nopick'] = (f"FBS vs FCS: the FBS team is not the favorite." if WEEK >= R_.get('min_week', 11) else f"FBS vs FCS: the FBS favorite rule starts in week {R_.get('min_week', 11)}.")
    g['today'] = g['date'] == NOW.strftime('%Y-%m-%d') and LINES_FRESH
    # picks are made on game day only, so every pending pick in the ledger is today's
    g['preview_picks'] = picks if not g['today'] else []   # Nov 11: preview mode for later games
    g['picks'] = picks if g['today'] else []
    g['day_pending'] = (not g['today']) and bool(picks)
    games.append(g)

# ---------------- props (texas222) ----------------
PL = {}
for line in (D / 'players_raw.txt').read_text().splitlines():
    team, name, cat, vals = line.split('|')
    PL[(norm(name), cat)] = dict(team=team, name=name, games=[(float(v.split('/')[0]), float(v.split('/')[1])) for v in vals.split(',')])
PROPS = []
CODE = {'FAT': 'Florida Atlantic', 'NT': 'North Texas', 'TRO': 'Troy', 'JM': 'James Madison'}
txt = (D / 't222_props.txt').read_text().strip()
raw = [r.split('|') for r in txt.split(';')] if txt else []
pairs = {}
for gm, nm, stat, pr in raw:
    m = re.match(r'(Ov|Un)([\d.½]+)([+-]\d+)', pr)
    if not m: continue
    k = (gm, nm, stat, float(frac(m.group(2))))
    pairs.setdefault(k, {})[m.group(1)] = int(m.group(3))
CATS = {'PASSING YARDS': ('pass', 0), 'RUSHING YARDS': ('rush', 0), 'RECEIVING YARDS': ('rec', 0), 'PASSING TOUCHDOWNS': ('pass', 1)}
for (gm, nm, stat, line), pr in pairs.items():
    if 'Ov' not in pr or 'Un' not in pr or stat not in CATS: continue
    cat, ix = CATS[stat]; P = PL.get((norm(nm), cat))
    a_, h_ = [CODE.get(x, x) for x in gm.split('/')]
    gg = next((x for x in games if x['away'] == a_ and x['home'] == h_), None)
    if not gg: continue
    if not P or len(P['games']) < 4:
        REPORT.append(f'prop skipped, no game log: {nm} {stat.lower()}'); continue
    team = next((t for t in (a_, h_) if norm(t) == norm(P['team']) or P['team'] in t), None)
    vals = np.array([x[ix] for x in P['games']]); n = len(vals)
    is_h = team == h_
    exp_pts = gg['total'] / 2 + (-gg['spread_h'] / 2 if is_h else gg['spread_h'] / 2)
    ppg = gg['ppg_h'] if is_h else gg['ppg_a']
    ratio = (exp_pts / ppg) if ppg else 1.0
    # game script: favorites lean on the run, underdogs throw more
    team_spread = gg['spread_h'] if is_h else -gg['spread_h']
    fav = -team_spread  # points the team is favored by (negative = underdog)
    tilt = 1 + 0.006 * fav if cat == 'rush' else (1 - 0.004 * fav if cat == 'pass' or cat == 'rec' else 1)
    mean = float(vals.mean()) * (ratio ** (0.5 if ix == 0 else 1.0)) * (tilt if ix == 0 else 1)
    sd = max(float(vals.std(ddof=1)) if n > 1 else mean * 0.5, (0.6 if ix == 1 else 8.0))
    rate_p = 1 - Phi((line - mean) / sd)
    rec_p = float((vals > line).mean())
    model_over = 0.5 * rate_p + 0.5 * rec_p
    nvo, nvu = novig(pr['Ov'], pr['Un'])
    for side, mp, price, mk in (('Over', model_over, pr['Ov'], nvo), ('Under', 1 - model_over, pr['Un'], nvu)):
        rp_, rcp = (rate_p, rec_p) if side == 'Over' else (1 - rate_p, 1 - rec_p)
        est = 0.6 * mp + 0.4 * mk
        be = implied(price); edge = 100 * (est - be)
        agree = abs(rp_ - rcp) <= 0.08
        t = None
        if edge >= 3 and agree and n >= 5: t = 'PLAY'
        elif edge >= 1.5: t = 'LEAN'
        PROPS.append(dict(game=f'{a_} @ {h_}', away=a_, home=h_, date=gg['date'], time=gg['time'], team=team, player=P['name'], stat=stat.lower(),
                          side=side, line=line, price=price, book='The Odds API median of books', n=n, avg=round(float(vals.mean()), 1), proj=round(mean, 1),
                          hit=f'{int((vals > line).sum()) if side == "Over" else int((vals < line).sum())}/{n}', rate=rp_, rec=rcp,
                          est=est, be=be, edge=edge, tier=t if gg['today'] else None, started=gg['started']))
# props held back by hand when the season log does not describe the player's current role (injuries.json _prop_hold)
try: INJ_HOLD = json.load(open(D / 'injuries.json')).get('_prop_hold', {})
except Exception: INJ_HOLD = {}
# Nov 9 2026 (Trina: injuries captured and used by the model): automatic holds from injuries.json (inj_merge.py).
# A player listed OUT, DOUBTFUL or OUT1H gets no prop; a team whose QB role changed (QB1 out or unconfirmed, or a new passer last game)
# gets no passing or receiving props until the new role has 5+ games of log. Card picks whose own starting QB is not confirmed go to Needs attention.
_INJP = {(t, x['player']): x for t, v in INJ.items() if not t.startswith('_') for x in v}
_QBCH = {t for t, v in INJ.items() if not t.startswith('_') for x in v if x.get('pos') == 'QB' and x.get('role_change')}
def _same(a, b): return norm(a).replace('.', '') == norm(b).replace('.', '') or (a.split()[-1:] == b.split()[-1:] and a[:1] == b[:1])
for p in PROPS:
    x = next((v for (t, n), v in _INJP.items() if t == p['team'] and _same(n, p['player'])), None)
    if x and x['status'] in ('OUT', 'DOUBTFUL', 'OUT1H'):
        INJ_HOLD = dict(INJ_HOLD or {}); INJ_HOLD.setdefault(p['player'], f"listed {x['status'].lower()} ({x['source']}, {x['date']})")
    elif p['team'] in _QBCH and any(k in p['stat'] for k in ('pass', 'rec')):
        INJ_HOLD = dict(INJ_HOLD or {}); INJ_HOLD.setdefault(p['player'], f"{p['team']} QB role changed (injuries.json); passing and receiving logs do not describe this game")
for g in games:
    for pk in g.get('picks', []):
        if pk['kind'] != 'side': continue
        own = INJ.get(pk.get('team'), []) if isinstance(INJ.get(pk.get('team')), list) else []
        q = next((x for x in own if x.get('pos') == 'QB' and x.get('qb1') and (not x.get('confirmed') or x['status'] not in ('AVAILABLE', 'OUT'))), None)
        if q: REPORT.append(f"Injury watch: {pk.get('text', pk.get('team'))} ({g['away']} @ {g['home']}): own QB1 {q['player']} {q['status'].lower()}{'' if q.get('confirmed') else ', unconfirmed'}. Check the gameday availability report before kickoff.")
# props must not fight the game picks
# Nov 11: only a card total pick holds props back; a total whose tier is turned off (hub meta tiers) is a would-be pick
try: _HM = json.load(open(D / 'hub' / 'meta' / 'fbs.json')); _HM = _HM.get('data', _HM); _HMR = {r['key']: r for r in _HM['rules']}
except Exception: _HMR = {}
def _TOT_ON(tp):
    L_ = sum(x['pts'] for x in tp['why'] if isinstance(x.get('pts'), (int, float))) - sum(x['pts'] for x in tp['against'] if isinstance(x.get('pts'), (int, float)))
    t_ = 'Strong' if L_ >= 4 else ('Solid' if L_ >= 2 else 'Lean')
    T_ = ((_HMR.get(tp['rule']) or {}).get('tiers') or {}).get(t_)
    return True if T_ is None else bool(T_.get('on'))
for p in PROPS:
    gg = next(x for x in games if x['away'] == p['away'] and x['home'] == p['home'])
    tp = next((x for x in gg['picks'] if x['kind'] == 'total'), None)
    p['blocked'] = None
    hold = (INJ_HOLD or {}).get(p['player'])
    if p['tier'] and hold:
        p['blocked'] = hold
    elif p['tier'] and tp and _TOT_ON(tp):
        if tp['team'] == 'Under' and p['side'] == 'Over' and tp['tier'] != 'Thin':
            p['blocked'] = f'card total pick is Under ({tp["tier"]})'
        if tp['team'] == 'Over' and p['side'] == 'Under' and tp['tier'] != 'Thin':
            p['blocked'] = f'card total pick is Over ({tp["tier"]})'
# keep the better side of each prop
best = {}
for p in PROPS:
    k = (p['game'], p['player'], p['stat'], p['line'])
    if k not in best or p['edge'] > best[k]['edge']: best[k] = p
PROPS = sorted(best.values(), key=lambda p: -p['edge'])

def clean(o):
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return float(o)
    if isinstance(o, (np.bool_,)): return bool(o)
    return o
conf_out = {k: v for k, v in CONFTAB.items()}
json.dump(clean(dict(div=DIV, week=WEEK, built=NOW.isoformat(), games=games, props=PROPS if DIV == 'fbs' else [],
                     conf=conf_out, nconf=NCONF, meta=META, report=REPORT)), open(D / f'slate_{DIV}.json', 'w'), indent=1, default=str)
(D / 'hist').mkdir(exist_ok=True)
PIF = D / 'hist' / f'pickinputs_{DIV}.jsonl'   # pick-time inputs per game: lines (book and second source), splits, sharp codes, injuries, weather
pik = {}
if PIF.exists():
    for line in PIF.read_text().splitlines():
        if line.strip(): z = json.loads(line); pik[z['id']] = z
if LINES_FRESH:
    for g in games:
        if g['started'] or not g['book'] or g['reference_only']: continue
        C2 = CONS.get((g['away'], g['home']), {})
        pik[g['id']] = clean(dict(id=g['id'], week=WEEK, date=g['date'], taken=PULL.isoformat(), book=g['book'], spread_h=g.get('spread_h'),
            price_a=g.get('price_a'), price_h=g.get('price_h'), total=g.get('total'), over=g.get('over'), under=g.get('under'),
            ml_a=g.get('ml_a'), ml_h=g.get('ml_h'), ml_book=g.get('ml_book'),
            second=dict(source='CFBD consensus', spread_h=C2.get('spread_h'), total=C2.get('total'), ml_a=C2.get('ml_a'), ml_h=C2.get('ml_h'),
                        open_h=C2.get('open_h'), tot_open=C2.get('tot_open'), dk_ml_a=C2.get('dk_ml_a'), dk_ml_h=C2.get('dk_ml_h')),
            an_open_a=g.get('open_a'), an=g['an'], inj_a=g['inj_a'], inj_h=g['inj_h'], wx=g['wx'],
            picks=[dict(rule=p['rule'], text=p['text'], price=p['price']) for p in g['picks']]))
    PIF.write_text(''.join(json.dumps(z, default=str) + '\n' for z in pik.values()))
SNAPF = D / 'hist' / f'snap_{DIV}.jsonl'
keep = {}
if SNAPF.exists():
    for line in SNAPF.read_text().splitlines():
        if line.strip(): z = json.loads(line); keep[z['id']] = z
for z in SNAP:   # the latest pre-kickoff numbers replace earlier ones for the same game
    if not next(g for g in games if g['id'] == z['id'])['started']: keep[z['id']] = clean(z)
SNAPF.write_text(''.join(json.dumps(z) + '\n' for z in keep.values()))
print(DIV, 'week', WEEK, 'games', len(games), 'with book', sum(1 for g in games if g['book']), 'picks', sum(len(g['picks']) for g in games), 'props', len(PROPS))
for x in REPORT: print('REPORT:', x)
