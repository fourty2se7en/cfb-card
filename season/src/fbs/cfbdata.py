"""Game rows for the CFB rule re-check, one per graded game, with every feature rules.py needs.
load('fbs') -> 2026 FBS vs FBS games (Action Network numbers from hist/ where saved).
load('fcs') -> 2026 FCS vs FCS games, plus past seasons 2022-2025 marked y < 2026 (reference only).
Lines are the CFBD consensus close (rules.consensus); openers are kept for the pick-time check.
"""
import gzip, json
from pathlib import Path
import pandas as pd, numpy as np
import rules as RU

D = Path(__file__).parent; R = D / 'repo'; H = D / 'hist'; BT = D.parent / 'bt'
PHX = 'America/Phoenix'


def ok(v): return v is not None and v == v


def _an():
    AN = {}
    f = H / 'an_fbs_w1_8.txt'
    if f.exists():
        for row in f.read_text().strip().split(';'):
            gid, ss, st, sm, sp, tt, ml = row.split('|')
            def pub(s):
                o, b, m = s.split(',')
                return dict(open=o, bets=int(b), money=int(m)) if b != '' and m != '' else (dict(open=o, bets=None, money=None) if o else None)
            cod = lambda s: [c for c in s.split('+') if c]
            AN[int(gid)] = dict(pub={k: v for k, v in (('SPREAD', pub(sp)), ('TOTAL', pub(tt)), ('ML', pub(ml))) if v},
                                sharp=dict(SPREAD=cod(ss), TOTAL=cod(st), ML=cod(sm)))
    for div in ('fbs', 'fcs'):
        f = H / f'snap_{div}.jsonl'
        if f.exists():
            for line in f.read_text().splitlines():
                if line.strip():
                    z = json.loads(line); AN[int(z['id'])] = z['an']
    return AN


def _features(r, logs, last, t, a, h):
    for k, tm in (('a', a), ('h', h)):
        p = RU.before(logs, tm, t)
        r['rest_' + k] = RU.cal_days(t, p[-1][0]) if p else None
        r['l3_' + k] = float(np.mean([q[1] + q[2] for q in p[-3:]])) if len(p) >= 3 else None
        r['n_' + k] = len(p)
        r['wp_' + k] = (sum(1 for q in p if q[1] > q[2]) / len(p)) if p else None
        r['last_' + k] = last.get(tm)


def load(div, SIG):
    LN = pd.read_csv(R / 'lines.csv'); LN = LN[(LN.season == 2026) & (LN.seasonType == 'regular') & LN.homeScore.notna() & LN.awayScore.notna()]
    LN = LN[(LN.homeClassification == div) & (LN.awayClassification == div)]
    G = pd.read_csv(R / 'games.csv'); G = G[(G.season == 2026) & G.homePoints.notna()]
    G['dt'] = pd.to_datetime(G.startDate, utc=True)
    logs = RU.team_logs(zip(G.dt, G.homeTeam, G.awayTeam, G.homePoints, G.awayPoints))
    P = pd.read_csv(R / 'games_prior.csv'); P = P[(P.season == 2025) & P.homePoints.notna()]
    last = RU.last_season(zip(P.homeTeam, P.awayTeam, P.homePoints, P.awayPoints))
    meta = {int(g.id): g for g in G.itertuples()}
    AN = _an()
    rows = []
    for x in LN.itertuples():
        c = RU.consensus(x.lines)
        if c['spread_h'] is None and c['total'] is None: continue
        t = pd.Timestamp(x.startDate); m = meta.get(int(x.id))
        r = dict(id=int(x.id), y=2026, wk=int(x.week), month=t.tz_convert(PHX).strftime('%b'), a=x.awayTeam, h=x.homeTeam,
                 pts_a=float(x.awayScore), pts_h=float(x.homeScore), conf=bool(m.conferenceGame) if m is not None else False,
                 neutral=bool(m.neutralSite) if m is not None else False, an=AN.get(int(x.id)),
                 **{k: c[k] for k in ('spread_h', 'open_h', 'total', 'tot_open', 'ml_a', 'ml_h')})
        _features(r, logs, last, t, x.awayTeam, x.homeTeam)
        rows.append(r)
    if div == 'fcs':
        rows += _fcs_past()
    for r in rows:
        r['sideS'], r['mlS'], r['totS'] = RU.build_signals(r, SIG)
    return rows


def _fcs_past():
    """FCS vs FCS 2022-2025 rows (reference). Cached in hist/ so the re-check does not need the bt/ cache."""
    cache = H / 'fcs_rows_2022_2025.json'
    if cache.exists():
        out = []
        for r in json.load(open(cache)):
            r = dict(r, last_a=tuple(r['last_a']) if r['last_a'] else None, last_h=tuple(r['last_h']) if r['last_h'] else None, month='', an=None)
            out.append(r)
        return out
    return []
