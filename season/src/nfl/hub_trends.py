"""Season Cards TREND blocks for NFL game docs (season-cards skill, Game docs: trends.away / trends.home with the team's last 10 games).
Usage: python3 hub_trends.py <hub_out dir> [hub games dir with saved game docs for plines]
Reads nflverse schedules (finals, closing spread and total) and play-by-play (score by quarter), adds 'trends' to every
hub_out/games/*.json and returns nothing else. Period lines (plines) come from saved game docs' lines.periods when present."""
import sys, json, glob, os, pathlib, datetime as dt
from zoneinfo import ZoneInfo
import pandas as pd, nflreadpy as nfl
OUT = pathlib.Path(sys.argv[1]); SAVED = sys.argv[2] if len(sys.argv) > 2 else None
PHX = ZoneInfo('America/Phoenix'); TODAY = dt.datetime.now(PHX).date()
NAMES = {'ARI': 'Arizona Cardinals', 'ATL': 'Atlanta Falcons', 'BAL': 'Baltimore Ravens', 'BUF': 'Buffalo Bills', 'CAR': 'Carolina Panthers', 'CHI': 'Chicago Bears',
 'CIN': 'Cincinnati Bengals', 'CLE': 'Cleveland Browns', 'DAL': 'Dallas Cowboys', 'DEN': 'Denver Broncos', 'DET': 'Detroit Lions', 'GB': 'Green Bay Packers',
 'HOU': 'Houston Texans', 'IND': 'Indianapolis Colts', 'JAX': 'Jacksonville Jaguars', 'KC': 'Kansas City Chiefs', 'LA': 'Los Angeles Rams', 'LAC': 'Los Angeles Chargers',
 'LV': 'Las Vegas Raiders', 'MIA': 'Miami Dolphins', 'MIN': 'Minnesota Vikings', 'NE': 'New England Patriots', 'NO': 'New Orleans Saints', 'NYG': 'New York Giants',
 'NYJ': 'New York Jets', 'PHI': 'Philadelphia Eagles', 'PIT': 'Pittsburgh Steelers', 'SEA': 'Seattle Seahawks', 'SF': 'San Francisco 49ers', 'TB': 'Tampa Bay Buccaneers',
 'TEN': 'Tennessee Titans', 'WAS': 'Washington Commanders'}
TZ = {'ARI': -7, 'LA': -8, 'LAC': -8, 'LV': -8, 'SF': -8, 'SEA': -8, 'DEN': -7, 'DAL': -6, 'HOU': -6, 'KC': -6, 'CHI': -6, 'GB': -6, 'MIN': -6, 'NO': -6, 'TEN': -6}
SCH = nfl.load_schedules([2026]).to_pandas(); SCH = SCH[SCH.game_type == 'REG']
DONE = SCH[SCH.result.notna()].sort_values(['gameday', 'gametime'])
PBP = nfl.load_pbp([2026]).to_pandas()[['game_id', 'qtr', 'total_home_score', 'total_away_score']]
QS = {}
for gid, x in PBP.groupby('game_id'):
    hs, as_ = [], []; ph = pa = 0
    for q in sorted(x.qtr.dropna().unique()):
        e = x[x.qtr == q].iloc[-1]; hs.append(int(e.total_home_score) - ph); as_.append(int(e.total_away_score) - pa); ph, pa = int(e.total_home_score), int(e.total_away_score)
    QS[gid] = (hs, as_)
PL = {}
if SAVED:
    for f in glob.glob(os.path.join(SAVED, '*.json')):
        D = json.load(open(f)); d = D.get('data', D); per = (d.get('lines') or {}).get('periods') or {}
        if per: PL[(d.get('date'), d.get('away', {}).get('code') if isinstance(d.get('away'), dict) else d.get('away'), d.get('home', {}).get('code') if isinstance(d.get('home'), dict) else d.get('home'))] = per
def num(s):
    try: return float(str(s).split()[0].replace('PK', '0'))
    except Exception: return None
def gamelog(t):
    out = []
    for r in DONE.itertuples():
        if t not in (r.home_team, r.away_team): continue
        home = t == r.home_team; neutral = r.location == 'Neutral'
        pf, pa = (int(r.home_score), int(r.away_score)) if home else (int(r.away_score), int(r.home_score))
        sp_t = (-r.spread_line if home else r.spread_line) if pd.notna(r.spread_line) else None   # team's line, negative = favored
        g = dict(date=r.gameday, opp=r.away_team if home else r.home_team, opp_name=NAMES[r.away_team if home else r.home_team], opp_rank=None,
                 site='neutral' if neutral else ('home' if home else 'away'), pf=pf, pa=pa, ot=bool(r.overtime) if pd.notna(r.overtime) else False)
        if r.game_id in QS:
            hs, as_ = QS[r.game_id]; f_, a_ = (hs, as_) if home else (as_, hs)
            labels = ['Q1', 'Q2', 'Q3', 'Q4'] + (['OT'] if len(f_) > 4 else [])
            g['periods'] = dict(labels=labels, **{'for': f_[:len(labels)], 'against': a_[:len(labels)]})
        if sp_t is not None:
            g['spread'] = f"{sp_t:+g}"; m = pf - pa + sp_t; g['ats'] = 'W' if m > 0 else ('L' if m < 0 else 'P')
        if pd.notna(r.total_line):
            g['total'] = float(r.total_line); tt = pf + pa - r.total_line; g['ou'] = 'O' if tt > 0 else ('U' if tt < 0 else 'P')
        per = PL.get((r.gameday, r.away_team, r.home_team))
        if per:
            pl = {}
            for k, v in per.items():
                sp = (v.get('spread') or {}).get('home' if home else 'away'); to = (v.get('total') or {}).get('over')
                e = {}
                if sp: e['spread'] = num(sp)
                if to: e['total'] = num(to)
                if e: pl[k] = e
            if pl: g['plines'] = pl
        out.append(g)
    return out
def hist(gs):
    if not gs: return dict(games=0, record='0-0')
    w = sum(g['pf'] > g['pa'] for g in gs); l = sum(g['pf'] < g['pa'] for g in gs); t = len(gs) - w - l
    a = [g for g in gs if 'ats' in g]; o = [g for g in gs if 'ou' in g]
    def rec(xs, k, W, L): return f"{sum(x[k] == W for x in xs)}-{sum(x[k] == L for x in xs)}" + (f"-{sum(x[k] == 'P' for x in xs)}" if any(x[k] == 'P' for x in xs) else '')
    hm = [g for g in gs if g['site'] == 'home']; rd = [g for g in gs if g['site'] != 'home']
    def wl(xs): return f"{sum(x['pf'] > x['pa'] for x in xs)}-{sum(x['pf'] < x['pa'] for x in xs)}"
    ha = ' · '.join(([f"{wl(hm)} home"] if hm else []) + ([f"{wl(rd)} road"] if rd else []))
    return dict(games=len(gs), record=f"{w}-{l}" + (f"-{t}" if t else ''), ats=rec(a, 'ats', 'W', 'L'), ou=rec(o, 'ou', 'O', 'U'),
                pf=round(sum(g['pf'] for g in gs)/len(gs), 1), pa=round(sum(g['pa'] for g in gs)/len(gs), 1), home_away=ha)
def trend(t, gday, opp_home=None):
    gs = gamelog(t); l5 = gs[-5:]
    mon = [g for g in gs if g['date'][:7] == str(TODAY)[:7]]
    wk0 = TODAY - dt.timedelta(days=TODAY.weekday()); wk = [g for g in gs if g['date'] >= str(wk0)]
    s = ''
    if gs:
        last = 'W' if gs[-1]['pf'] > gs[-1]['pa'] else ('L' if gs[-1]['pf'] < gs[-1]['pa'] else 'T'); n = 0
        for g in reversed(gs):
            r_ = 'W' if g['pf'] > g['pa'] else ('L' if g['pf'] < g['pa'] else 'T')
            if r_ != last: break
            n += 1
        s = f"{last}{n}"
    rest = (dt.date.fromisoformat(gday) - dt.date.fromisoformat(gs[-1]['date'])).days if gs else None
    tz = abs(TZ.get(t, -5) - TZ.get(opp_home, -5)) if opp_home else 0
    l3 = gs[-3:]
    return dict(last5=['W' if g['pf'] > g['pa'] else ('L' if g['pf'] < g['pa'] else 'T') for g in l5],
                pf=hist(gs).get('pf'), pa=hist(gs).get('pa'), last5_scores=[g['pf'] for g in l5], last5_totals=[g['pf'] + g['pa'] for g in l5],
                last5_margins=[g['pf'] - g['pa'] for g in l5], rest_days=rest, travel=f"{tz} time zone" + ('' if tz == 1 else 's'), streak=s,
                last3_diff=f"{sum(g['pf'] - g['pa'] for g in l3)/len(l3):.1f}" if l3 else None,
                history=dict(season=hist(gs), month=hist(mon), week=hist(wk), last10=hist(gs[-10:]), last5=hist(l5)),
                games=list(reversed(gs[-10:])))
n = 0
for f in glob.glob(str(OUT/'games'/'*.json')):
    d = json.load(open(f)); a = d['away']['code'] if isinstance(d['away'], dict) else d['away']; h = d['home']['code'] if isinstance(d['home'], dict) else d['home']
    d['trends'] = dict(away=trend(a, d['date'], None if d.get('neutral') else h), home=trend(h, d['date'], None))
    json.dump(d, open(f, 'w'), indent=1, default=str); n += 1
print('trends added to', n, 'game docs')
