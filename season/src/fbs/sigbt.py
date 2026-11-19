"""Walk-forward backtest of candidate college signals against the closing spread.

Every feature for a game in season S, week w uses only games played before week w
of season S (plus season S-1 where stated). Test games: FBS vs FBS, regular season,
with a consensus closing spread. Outcome: does the side the signal names cover?
Thresholds are picked on 2017-2022 and checked out of sample on 2023-2025.
"""
import gzip, json, sys, math
import numpy as np, pandas as pd
from sklearn.linear_model import Ridge

D = sys.argv[1] if len(sys.argv) > 1 else 'bt'
YEARS = range(2016, 2026)

def load(kind, y):
    try:
        return json.load(gzip.open(f'{D}/{kind}_{y}.json.gz'))
    except FileNotFoundError:
        return []

G = []
for y in YEARS:
    for g in load('games', y):
        if g.get('seasonType') != 'regular' or not g.get('completed'):
            continue
        if g.get('homePoints') is None or g.get('awayPoints') is None:
            continue
        G.append(dict(id=g['id'], season=y, week=g['week'], date=g['startDate'][:10],
                      home=g['homeTeam'], away=g['awayTeam'],
                      hc=g.get('homeClassification'), ac=g.get('awayClassification'),
                      hconf=g.get('homeConference'), aconf=g.get('awayConference'),
                      neutral=bool(g.get('neutralSite')), confgame=bool(g.get('conferenceGame')),
                      venue=g.get('venueId'),
                      margin=g['homePoints'] - g['awayPoints']))
G = pd.DataFrame(G)
G['date'] = pd.to_datetime(G.date)

# consensus closing spread (home perspective, negative = home favoured)
SP = {}
for y in YEARS:
    for l in load('lines', y):
        s = [x['spread'] for x in (l.get('lines') or []) if x.get('spread') is not None]
        if s:
            SP[l['id']] = float(np.median(s))
G['spread'] = G.id.map(SP)

# talent by season
TAL = {}
for y in YEARS:
    for t in load('talent', y):
        TAL[(y, t.get('team') or t.get('school'))] = float(t['talent'])

# venue time zones -> team home zone (most common non-neutral home venue)
V = pd.read_csv('venues.csv')
OFF = {'America/New_York': -5, 'America/Detroit': -5, 'America/Indiana/Indianapolis': -5,
       'America/Kentucky/Louisville': -5, 'America/Chicago': -6, 'America/Denver': -7,
       'America/Boise': -7, 'America/Phoenix': -7, 'America/Los_Angeles': -8,
       'Pacific/Honolulu': -10, 'America/Anchorage': -9}
vtz = {int(r.id): OFF.get(r.timezone) for r in V.itertuples() if isinstance(r.timezone, str)}
hv = G[~G.neutral].groupby('home').venue.agg(lambda s: s.mode().iloc[0] if len(s.mode()) else None)
team_tz = {t: vtz.get(int(v)) if v == v and v is not None else None for t, v in hv.items()}

fbs_by_season = {}
for y in YEARS:
    s = G[G.season == y]
    fbs_by_season[y] = set(s.home[s.hc == 'fbs']) | set(s.away[s.ac == 'fbs'])

def conf_of(row, side):
    c = row['hconf' if side == 'home' else 'aconf']
    cl = row['hc' if side == 'home' else 'ac']
    if cl == 'fcs':
        return 'FCS'
    if cl != 'fbs':
        return None
    return c

def conf_ratings(prior, alpha=6.0):
    """Ridge on conference labels from non-conference FBS/FCS games only."""
    rows = []
    for r in prior.itertuples():
        a, b = conf_of(r._asdict(), 'home'), conf_of(r._asdict(), 'away')
        if a is None or b is None or a == b:
            continue
        rows.append((a, b, 0.0 if r.neutral else 1.0, max(-40, min(40, r.margin))))
    if len(rows) < 20:
        return {}
    confs = sorted({x[0] for x in rows} | {x[1] for x in rows})
    ix = {c: i for i, c in enumerate(confs)}
    X = np.zeros((len(rows), len(confs) + 1)); y = np.zeros(len(rows))
    for k, (a, b, h, m) in enumerate(rows):
        X[k, ix[a]] = 1; X[k, ix[b]] = -1; X[k, -1] = h; y[k] = m
    m = Ridge(alpha=alpha, fit_intercept=False).fit(X, y)
    r = pd.Series(m.coef_[:-1], index=confs)
    fb = [c for c in confs if c != 'FCS']
    return (r - r[fb].mean()).to_dict()

def team_log(prior):
    """per team list of (date, venue_type, margin, won)"""
    out = {}
    for r in prior.itertuples():
        for side, opp, sign in (('home', 'away', 1), ('away', 'home', -1)):
            t = getattr(r, side)
            vt = 'N' if r.neutral else ('H' if side == 'home' else 'R')
            m = sign * r.margin
            out.setdefault(t, []).append((r.date, vt, m, m > 0))
    return out

def rp(wins, n, k):
    return (wins + 0.5 * k) / (n + k)

rows = []
for y in range(2017, 2026):
    S = G[G.season == y]; P = G[G.season == y - 1]
    last = {}
    for t, lst in team_log(P).items():
        last[t] = sum(x[3] for x in lst) / len(lst)
    for w in sorted(S.week.unique()):
        prior = S[S.week < w]
        test = S[(S.week == w) & (S.hc == 'fbs') & (S.ac == 'fbs') & S.spread.notna()]
        if test.empty:
            continue
        cr = conf_ratings(prior) if w >= 3 else {}
        tl = team_log(prior)
        for r in test.itertuples():
            d = dict(season=y, week=w, home=r.home, away=r.away, neutral=r.neutral,
                     confgame=r.confgame, spread=r.spread, margin=r.margin)
            d['cover'] = np.sign(r.margin + r.spread)  # +1 home covers, -1 away, 0 push
            d['su'] = np.sign(r.margin)
            # conference strength (non-conference games only)
            if not r.confgame and r.hconf != r.aconf and cr:
                ch, ca = cr.get(r.hconf), cr.get(r.aconf)
                d['conf_gap'] = None if ch is None or ca is None else ch - ca
            lh, la = tl.get(r.home, []), tl.get(r.away, [])
            # venue split: home team's home win%, away team's road win% (regressed 4 games)
            if not r.neutral:
                hh = [x for x in lh if x[1] == 'H']; ar = [x for x in la if x[1] == 'R']
                if len(hh) >= 1 and len(ar) >= 1:
                    d['venue_gap'] = rp(sum(x[3] for x in hh), len(hh), 4) - rp(sum(x[3] for x in ar), len(ar), 4)
            # rest
            if lh and la:
                rh = (r.date - max(x[0] for x in lh)).days; ra = (r.date - max(x[0] for x in la)).days
                d['rest_h'], d['rest_a'] = rh, ra
            # travel (time zones crossed by the road team; neutral: both)
            vz = vtz.get(int(r.venue)) if r.venue == r.venue and r.venue is not None else None
            th, ta = team_tz.get(r.home), team_tz.get(r.away)
            if vz is not None and th is not None and ta is not None:
                d['tz_h'], d['tz_a'] = abs(vz - th), abs(vz - ta)
            # streaks and form
            def streak(l):
                s = 0
                for x in sorted(l, key=lambda z: z[0], reverse=True):
                    if s >= 0 and x[3]: s += 1
                    elif s <= 0 and not x[3]: s -= 1
                    else: break
                return s
            if lh and la:
                d['str_h'], d['str_a'] = streak(lh), streak(la)
                d['pd_gap'] = np.mean([x[2] for x in lh]) - np.mean([x[2] for x in la])
                d['n_h'], d['n_a'] = len(lh), len(la)
            if r.home in last and r.away in last:
                d['last_gap'] = last[r.home] - last[r.away]
            th_, ta_ = TAL.get((y, r.home)), TAL.get((y, r.away))
            if th_ and ta_:
                d['tal_gap'] = th_ - ta_
            rows.append(d)

T = pd.DataFrame(rows)
T.to_csv('sig_rows.csv', index=False)
print('test games', len(T), 'seasons', T.season.min(), T.season.max())

def rate(side, frame):
    """side: +1 home, -1 away per row (0 = no signal). Returns n, cover %, CI."""
    m = side != 0
    c = frame.cover[m] * side[m]
    c = c[c != 0]
    n = len(c); k = int((c > 0).sum())
    if n == 0:
        return n, float('nan'), float('nan'), float('nan')
    p = k / n; se = math.sqrt(p * (1 - p) / n)
    return n, p, p - 1.96 * se, p + 1.96 * se

def su(side, frame):
    m = side != 0
    c = frame.su[m] * side[m]; c = c[c != 0]
    return (c > 0).mean() if len(c) else float('nan')

TESTS = []
def add(name, fn, threshold_desc):
    TESTS.append((name, fn, threshold_desc))

for t in (3, 6, 10):
    add(f'Conference strength gap {t}+ pts', lambda f, t=t: np.where(f.conf_gap.fillna(0) >= t, 1, np.where(f.conf_gap.fillna(0) <= -t, -1, 0)), t)
for t in (0.15, 0.25, 0.35):
    add(f'Home/road split gap {t:.2f}+', lambda f, t=t: np.where(f.venue_gap.fillna(0) >= t, 1, np.where(f.venue_gap.fillna(0) <= -t, -1, 0)), t)
add('Home field (always home, non-neutral)', lambda f: np.where(~f.neutral, 1, 0), None)
add('Conference game: home side', lambda f: np.where(f.confgame & ~f.neutral, 1, 0), None)
add('Off a bye vs team on normal rest', lambda f: np.where((f.rest_h >= 13) & (f.rest_a <= 9), 1, np.where((f.rest_a >= 13) & (f.rest_h <= 9), -1, 0)), None)
add('Opponent on short week (6 days or less)', lambda f: np.where((f.rest_a <= 6) & (f.rest_h >= 7), 1, np.where((f.rest_h <= 6) & (f.rest_a >= 7), -1, 0)), None)
for t in (1, 2):
    add(f'Opponent crossed {t}+ time zones', lambda f, t=t: np.where((f.tz_a >= t) & (f.tz_h < t), 1, np.where((f.tz_h >= t) & (f.tz_a < t), -1, 0)), t)
add('Hot streak W3+', lambda f: np.where((f.str_h >= 3) & (f.str_a < 3), 1, np.where((f.str_a >= 3) & (f.str_h < 3), -1, 0)), None)
add('Opponent cold streak L3+', lambda f: np.where((f.str_a <= -3) & (f.str_h > -3), 1, np.where((f.str_h <= -3) & (f.str_a > -3), -1, 0)), None)
for t in (7, 14):
    add(f'Point differential gap {t}+ per game', lambda f, t=t: np.where((f.pd_gap >= t) & (f.n_h >= 3), 1, np.where((f.pd_gap <= -t) & (f.n_a >= 3), -1, 0)), t)
for t in (0.25, 0.40):
    add(f'Track record: last season win% gap {t:.2f}+', lambda f, t=t: np.where(f.last_gap.fillna(0) >= t, 1, np.where(f.last_gap.fillna(0) <= -t, -1, 0)), t)
for t in (100, 200):
    add(f'Talent gap {t}+', lambda f, t=t: np.where(f.tal_gap.fillna(0) >= t, 1, np.where(f.tal_gap.fillna(0) <= -t, -1, 0)), t)
# underdog versions where a signal backs the dog (the case the market may underprice)
add('Conference strength 6+ backing the underdog', lambda f: np.where((f.conf_gap.fillna(0) >= 6) & (f.spread > 0), 1, np.where((f.conf_gap.fillna(0) <= -6) & (f.spread < 0), -1, 0)), None)

train = T[T.season <= 2022]; test = T[T.season >= 2023]
out = []
for name, fn, th in TESTS:
    a = rate(fn(train), train); b = rate(fn(test), test); c = rate(fn(T), T)
    out.append(dict(signal=name, n_train=a[0], ats_train=a[1], n_test=b[0], ats_test=b[1],
                    n_all=c[0], ats_all=c[1], lo=c[2], hi=c[3], su_all=su(fn(T), T)))
R = pd.DataFrame(out)
pd.set_option('display.width', 220); pd.set_option('display.max_colwidth', 50)
print(R.round(3).to_string(index=False))
R.to_csv('sig_results.csv', index=False)
