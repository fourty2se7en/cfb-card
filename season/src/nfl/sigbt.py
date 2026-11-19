"""Walk-forward backtest of the new NFL signals against the closing spread and total.
nflverse schedules, regular season 2006-2025. Every feature for a game in week w of season S uses only
games before week w of season S (plus season S-1 where stated). Thresholds are judged on 2006-2017 (train)
and checked out of sample on 2018-2025 (test). Break-even at -110 is 52.4%.
Point rule (same as the CFB card): 2 pts if both halves beat 52.4% and the full 95% interval clears 50%;
1 pt if both halves beat 51%; else 0 (shown, not scored)."""
import math, json, numpy as np, pandas as pd, nflreadpy as nfl
import nflmodel as M

S = nfl.load_schedules(list(range(2005, 2026))).to_pandas()
S = S[S.game_type == 'REG'].copy()
S['gameday'] = pd.to_datetime(S.gameday)
S['margin'] = S.home_score - S.away_score
S['tot'] = S.home_score + S.away_score
CONF = lambda t: M.DIV.get(t, 'X X').split()[0]
FIX = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA', 'LAR': 'LA'}
for c in ('home_team', 'away_team'): S[c] = S[c].replace(FIX)

rows = []
for y in range(2006, 2026):
    Y = S[S.season == y]; P = S[S.season == y-1]
    lastpct = {}
    for t in M.DIV:
        g = P[(P.home_team == t) | (P.away_team == t)]
        w = ((g.home_team == t) & (g.margin > 0)).sum() + ((g.away_team == t) & (g.margin < 0)).sum()
        lastpct[t] = (w + 0.5*(g.margin == 0).sum())/len(g) if len(g) else 0.5
    # primary QB per team last game, for QB change
    for wk in sorted(Y.week.unique()):
        pr = Y[(Y.week < wk) & Y.result.notna()]
        te = Y[(Y.week == wk) & Y.result.notna() & Y.spread_line.notna()]
        if te.empty: continue
        # division and conference strength: out-of-division results, win % and point diff
        dv, cf = {}, {}
        log = {}
        for r in pr.itertuples():
            for t, o, m, vt in ((r.home_team, r.away_team, r.margin, 'H'), (r.away_team, r.home_team, -r.margin, 'R')):
                log.setdefault(t, []).append((r.week, vt, m, r.home_qb_id if vt == 'H' else r.away_qb_id))
                if M.DIV.get(t) != M.DIV.get(o):
                    d = dv.setdefault(M.DIV.get(t), [0, 0]); d[0] += (m > 0) + 0.5*(m == 0); d[1] += 1
                if CONF(t) != CONF(o):
                    d = cf.setdefault(CONF(t), [0, 0]); d[0] += (m > 0) + 0.5*(m == 0); d[1] += 1
        def adj(d, k=8): return (d[0] + 0.5*k)/(d[1] + k) if d else 0.5
        for r in te.itertuples():
            h, a = r.home_team, r.away_team
            d = dict(season=y, week=wk, h=h, a=a, spread=r.spread_line, total=r.total_line, margin=r.margin, tot=r.tot,
                     div_game=bool(r.div_game), neutral=r.location == 'Neutral', roof=r.roof, temp=r.temp, wind=r.wind,
                     rest_h=r.home_rest, rest_a=r.away_rest, wd=r.weekday, kick=r.gametime)
            d['cover'] = np.sign(r.margin - r.spread_line)
            d['ou'] = np.sign(r.tot - r.total_line) if pd.notna(r.total_line) else 0
            if M.DIV.get(h) != M.DIV.get(a):
                d['div_gap'] = adj(dv.get(M.DIV.get(h))) - adj(dv.get(M.DIV.get(a)))
            if CONF(h) != CONF(a):
                d['conf_gap'] = adj(cf.get(CONF(h))) - adj(cf.get(CONF(a)))
            lh, la = log.get(h, []), log.get(a, [])
            if not d['neutral']:
                hh = [x for x in lh if x[1] == 'H']; ar = [x for x in la if x[1] == 'R']
                if hh and ar:
                    rp = lambda l: (sum((x[2] > 0) + 0.5*(x[2] == 0) for x in l) + 2)/(len(l) + 4)
                    d['venue_gap'] = rp(hh) - rp(ar)
            def streak(l):
                s = 0
                for x in sorted(l, key=lambda z: -z[0]):
                    if s >= 0 and x[2] > 0: s += 1
                    elif s <= 0 and x[2] < 0: s -= 1
                    else: break
                return s
            if len(lh) >= 3 and len(la) >= 3:
                d['str_h'], d['str_a'] = streak(lh), streak(la)
                d['pd_gap'] = np.mean([x[2] for x in lh]) - np.mean([x[2] for x in la])
                d['l3_gap'] = np.mean([x[2] for x in sorted(lh)[-3:]]) - np.mean([x[2] for x in sorted(la)[-3:]])
                # recent scoring for totals: both teams' last 3 game totals vs this total
            d['last_gap'] = lastpct.get(h, .5) - lastpct.get(a, .5)
            # QB change: this game's starter is not the team's most frequent starter so far (2+ games)
            for side, l, q in (('h', lh, r.home_qb_id), ('a', la, r.away_qb_id)):
                qs = [x[3] for x in l if isinstance(x[3], str)]
                d['qbchg_'+side] = bool(len(qs) >= 2 and isinstance(q, str) and q != max(set(qs), key=qs.count))
            # travel: road team's home zone vs venue (home team's zone), early 1 PM ET kickoff
            d['tz_a'] = M.TZ.get(a, 0) - M.TZ.get(h, 0)   # positive = road team from further west
            rows.append(d)
    # recent scoring per team (done in a second pass below)
T = pd.DataFrame(rows)
# recent game totals per team, last 3, before each game
tl = {}
for r in S.sort_values(['season', 'week']).itertuples():
    pass
recent = []
for (y, wk), g in T.groupby(['season', 'week']):
    pr = S[(S.season == y) & (S.week < wk) & S.result.notna()]
    for i, r in g.iterrows():
        vals = []
        for t in (r.h, r.a):
            x = pr[(pr.home_team == t) | (pr.away_team == t)].sort_values('week').tail(3)
            vals.append(x.tot.mean() if len(x) == 3 else np.nan)
        T.loc[i, 'rec_tot'] = np.mean(vals) if not any(np.isnan(vals)) else np.nan
T.to_csv('sig_rows.csv', index=False)

def rate(side, f, col='cover'):
    m = side != 0; c = f[col][m]*side[m]; c = c[c != 0]
    n = len(c); k = int((c > 0).sum())
    if n == 0: return 0, float('nan'), float('nan'), float('nan')
    p = k/n; se = math.sqrt(p*(1-p)/n); return n, p, p-1.96*se, p+1.96*se

TESTS = []
def add(key, name, fn, col='cover'): TESTS.append((key, name, fn, col))
nz = lambda s: s.fillna(0)
for t in (0.10, 0.15, 0.20):
    add(f'div_{t}', f'Division strength gap {t:.2f}+ (stronger division side)', lambda f, t=t: np.where(nz(f.div_gap) >= t, 1, np.where(nz(f.div_gap) <= -t, -1, 0)))
for t in (0.05, 0.10):
    add(f'conf_{t}', f'AFC vs NFC strength gap {t:.2f}+', lambda f, t=t: np.where(nz(f.conf_gap) >= t, 1, np.where(nz(f.conf_gap) <= -t, -1, 0)))
add('div_dog', 'Division game: underdog', lambda f: np.where(f.div_game, np.where(f.spread > 0, -1, np.where(f.spread < 0, 1, 0)), 0))
add('div_home', 'Division game: home side', lambda f: np.where(f.div_game & ~f.neutral, 1, 0))
for t in (0.15, 0.25, 0.35):
    add(f'venue_{t}', f'Home/road split gap {t:.2f}+', lambda f, t=t: np.where(nz(f.venue_gap) >= t, 1, np.where(nz(f.venue_gap) <= -t, -1, 0)))
add('home', 'Home field (always home)', lambda f: np.where(~f.neutral, 1, 0))
add('bye', 'Off a bye vs normal rest', lambda f: np.where((f.rest_h >= 13) & (f.rest_a <= 8), 1, np.where((f.rest_a >= 13) & (f.rest_h <= 8), -1, 0)))
add('short', 'Opponent on a short week (5 days or less vs 6+)', lambda f: np.where((f.rest_a <= 5) & (f.rest_h >= 6), 1, np.where((f.rest_h <= 5) & (f.rest_a >= 6), -1, 0)))
add('rest2', 'Rest edge 3+ days', lambda f: np.where(f.rest_h - f.rest_a >= 3, 1, np.where(f.rest_a - f.rest_h >= 3, -1, 0)))
add('tnf_road', 'Thursday game: home side', lambda f: np.where((f.wd == 'Thursday') & ~f.neutral, 1, 0))
add('west_early', 'West coast road team, 1 PM ET kickoff: fade it', lambda f: np.where((f.tz_a >= 3) & (f.kick.astype(str).str[:2] == '13'), 1, 0))
add('tz2', 'Road team crossed 2+ time zones: fade it', lambda f: np.where(f.tz_a.abs() >= 2, 1, 0))
add('intl', 'International / neutral: favourite', lambda f: np.where(f.neutral, np.where(f.spread > 0, 1, -1), 0))
add('qb_opp', 'Opponent starting a different QB than usual', lambda f: np.where(f.qbchg_a & ~f.qbchg_h, 1, np.where(f.qbchg_h & ~f.qbchg_a, -1, 0)))
add('hot', 'Hot streak W3+', lambda f: np.where((f.str_h >= 3) & (f.str_a < 3), 1, np.where((f.str_a >= 3) & (f.str_h < 3), -1, 0)))
add('cold', 'Opponent cold streak L3+', lambda f: np.where((f.str_a <= -3) & (f.str_h > -3), 1, np.where((f.str_h <= -3) & (f.str_a > -3), -1, 0)))
for t in (5, 10):
    add(f'l3_{t}', f'Recent form: last-3 point diff gap {t}+', lambda f, t=t: np.where(nz(f.l3_gap) >= t, 1, np.where(nz(f.l3_gap) <= -t, -1, 0)))
    add(f'pd_{t}', f'Season point diff gap {t}+ per game', lambda f, t=t: np.where(nz(f.pd_gap) >= t, 1, np.where(nz(f.pd_gap) <= -t, -1, 0)))
for t in (0.25, 0.40):
    add(f'last_{t}', f'Track record: last season win% gap {t:.2f}+ (better team)', lambda f, t=t: np.where(f.last_gap >= t, 1, np.where(f.last_gap <= -t, -1, 0)))
    add(f'lastfade_{t}', f'Last season overrated: back the worse last-season team ({t:.2f}+)', lambda f, t=t: np.where(f.last_gap >= t, -1, np.where(f.last_gap <= -t, 1, 0)))
# totals (+1 = over)
out_ = lambda f: (f.roof == 'outdoors') | (f.roof == 'open')
for t in (10, 15, 20):
    add(f'wind_{t}', f'Wind {t}+ mph (outdoors): under', lambda f, t=t: np.where(out_(f) & (f.wind >= t), -1, 0), 'ou')
for t in (32, 25):
    add(f'cold_{t}', f'Temperature {t}F or lower: under', lambda f, t=t: np.where(out_(f) & (f.temp <= t), -1, 0), 'ou')
add('dome_over', 'Dome: over', lambda f: np.where(f.roof == 'dome', 1, 0), 'ou')
add('div_under', 'Division game: under', lambda f: np.where(f.div_game, -1, 0), 'ou')
for t in (5, 8):
    add(f'rec_fade_{t}', f'Recent scoring {t}+ off the total: fade it', lambda f, t=t: np.where(nz(f.rec_tot - f.total) >= t, -1, np.where(nz(f.rec_tot - f.total) <= -t, 1, 0)), 'ou')
    add(f'rec_follow_{t}', f'Recent scoring {t}+ off the total: follow it', lambda f, t=t: np.where(nz(f.rec_tot - f.total) >= t, 1, np.where(nz(f.rec_tot - f.total) <= -t, -1, 0)), 'ou')
add('tnf_under', 'Thursday game: under', lambda f: np.where(f.wd == 'Thursday', -1, 0), 'ou')
add('all_under', 'Every game: under', lambda f: np.full(len(f), -1), 'ou')

tr, ts = T[T.season <= 2017], T[T.season >= 2018]
out = []
for key, name, fn, col in TESTS:
    a = rate(fn(tr), tr, col); b = rate(fn(ts), ts, col); c = rate(fn(T), T, col)
    pts = 2 if (a[1] > .524 and b[1] > .524 and c[2] > .5) else 1 if (a[1] > .51 and b[1] > .51) else 0
    out.append(dict(key=key, signal=name, market='Total' if col == 'ou' else 'Side', n_train=a[0], train=a[1], n_test=b[0], test=b[1], n=c[0], all=c[1], lo=c[2], hi=c[3], pts=pts))
R = pd.DataFrame(out)
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 60)
print('test games', len(T))
print(R.round(3).to_string(index=False))
R.to_csv('sig_results.csv', index=False)
