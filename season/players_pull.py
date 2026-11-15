"""Player and team stat pulls for the Season Cards prop models and the game card "Season stats" block (Trina, Nov 14 2026, B115).
No login and no Chrome: ESPN public JSON, the NHL API and the repo's own Odds API files. Runs in GitHub Actions (season/loop.py once a day
after 09:15 Phoenix, players.yml as backup and on demand); stats.nba.com times out from GitHub runners, so NBA uses ESPN.

    python3 season/players_pull.py <mode> [sports] [YYYY-MM-DD Phoenix]
    modes: all       backfill + teams + nba + nba_raw + nhl + fbs (the daily pull)
           backfill  ESPN finals (scoreboard_final + boxscores) for every past season date missing them (one time, then daily
                     espn_pull finals keeps them current)
           teams     team season stats with ranks (game card Season stats block) and defense vs stat or position (prop matchups)
           nba       NBA player logs: this season from the repo box scores, last season from ESPN athlete game logs (cached)
           nba_raw   NBA season_raw.txt, players_raw.txt, splits_raw.txt from the logs plus today's prop lines in odds/data
                     (rerun after props_open or props_now; odds.yml props_now and the loop do this)
           nhl       NHL skater and goalie game logs for the slate's teams (NHL API) -> plogs.txt and skater_logs.json.gz
           fbs       FBS player box score logs for the slate's teams -> players_raw.txt (Team|Player|pass/rush/rec|yds/td,...)

Files (gzip JSON unless .txt):
  season/data/espn/<sport>/<date>/team_stats.json.gz   every sport (NHL also writes season/data/nhl/<date>/team_stats.json.gz)
  season/data/espn/nba/<date>/player_logs.json.gz, season_raw.txt, players_raw.txt, splits_raw.txt, usage_raw.txt,
                                matchup_raw.txt, ratings.txt
  season/data/espn/nba/_lastseason/<athlete id>.json.gz   2025-26 regular season game logs (written once per player)
  season/data/espn/fbs/<slate date>/players_raw.txt, player_logs.json.gz
  season/data/nhl/<date>/plogs.txt, skater_logs.json.gz
A missing feed is skipped, never fatal."""
import datetime as dt, glob, gzip, json, math, re, statistics as stt, sys, time, unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'odds'))
import espn_pull as EP   # noqa: E402  (j, save, trim_summary, SP)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'season' / 'data'
PHX = dt.timezone(dt.timedelta(hours=-7))
START = {'nba': '2026-10-20', 'nhl': '2026-10-06', 'nfl': '2026-09-09', 'fbs': '2026-08-27', 'ncaam': '2026-11-02', 'ncaaw': '2026-11-02'}
NBA_CODE = {'NY': 'NYK', 'GS': 'GSW', 'SA': 'SAS', 'NO': 'NOP', 'UTAH': 'UTA', 'WSH': 'WAS'}
NHL = 'https://api-web.nhle.com'
j = EP.j


def phx_now(): return dt.datetime.now(PHX)
def stamp(): return phx_now().strftime('%b %d about %-I:%M %p Phoenix')
def r1(x): return f'{round(x * 10) / 10:.1f}'


def nz(s):
    s = unicodedata.normalize('NFD', s or ''); s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r"[.'’]", '', s); s = re.sub(r'\b(Jr|Sr|II|III|IV)\b', '', s)
    return re.sub(r'\s+', ' ', s).strip().lower()


def gz_read(p):
    try:
        with gzip.open(p, 'rt') as z: return json.load(z)
    except (OSError, ValueError): return None


def gz_write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, 'wt') as z: json.dump(obj, z, separators=(',', ':'))


def num(v):
    try: return float(str(v).replace(',', ''))
    except (TypeError, ValueError): return None


def ma(v):   # "39-91" or "16/37" -> (39, 91)
    m = re.match(r'(\d+)[-/](\d+)', str(v or ''))
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


# ---------------------------------------------------------------- season box scores (repo files, ESPN finals format)
def dates(sport, day):
    d0, d1 = dt.date.fromisoformat(START[sport]), dt.date.fromisoformat(day)
    return [(d0 + dt.timedelta(n)).isoformat() for n in range((d1 - d0).days)]


def backfill(sport, day):
    """Finals for every season date before `day` with no boxscores file yet (same files espn_pull finals writes)."""
    path, grp = EP.SP[sport]; n = 0
    for d in dates(sport, day):
        if (DATA / 'espn' / sport / d / 'boxscores.json.gz').exists(): continue
        sb = j(f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={d.replace('-', '')}&limit=500" + (f'&groups={grp}' if grp else ''))
        evs = [e for e in (sb or {}).get('events', []) if ((e.get('status') or {}).get('type') or {}).get('state') == 'post']
        if not evs: continue
        box = {}
        for e in evs:
            s = j(f'https://site.api.espn.com/apis/site/v2/sports/{path}/summary?event={e["id"]}')
            if s: box[e['id']] = EP.trim_summary(s)
        EP.save(sport, d, 'scoreboard_final', sb); EP.save(sport, d, 'boxscores', box); n += len(box)
    print(f'backfill {sport}: {n} games added')
    return n


def season_games(sport, day):
    """[(date, event id, box)] for regular and postseason games before `day`, oldest first."""
    out = []
    for d in dates(sport, day):
        box = gz_read(DATA / 'espn' / sport / d / 'boxscores.json.gz')
        if not box: continue
        sb = gz_read(DATA / 'espn' / sport / d / 'scoreboard_final.json.gz') or {}
        typ = {e['id']: (e.get('season') or {}).get('type') for e in sb.get('events', [])}
        for eid, b in box.items():
            if typ.get(eid, 2) in (2, 3) and (b.get('status') or 'STATUS_FINAL').startswith('STATUS_FINAL'): out.append((d, eid, b))
    return out


def slate(sport, day):
    """Today's games from the repo scoreboard (or ESPN): [(away team dict, home team dict, event id, start)]."""
    sb = gz_read(DATA / 'espn' / sport / day / 'scoreboard.json.gz')
    if not sb:
        path, grp = EP.SP[sport]
        sb = j(f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={day.replace('-', '')}&limit=500" + (f'&groups={grp}' if grp else '')) or {}
    out = []
    for e in sb.get('events', []):
        c = e['competitions'][0]; t = {x['homeAway']: x['team'] for x in c['competitors']}
        out.append((t.get('away'), t.get('home'), e['id'], e.get('date')))
    return out


def ranked_ids(sport, day):
    for f in sorted(glob.glob(str(DATA / 'espn' / sport / '*' / 'standings.json.gz')), reverse=True):
        ids = set()
        def walk(o):
            if isinstance(o, dict):
                t = o.get('team')
                if isinstance(t, dict) and 'id' in t and 'stats' in o: ids.add(str(t['id']))
                for v in o.values(): walk(v)
            elif isinstance(o, list):
                for v in o: walk(v)
        walk(gz_read(f) or {})
        if ids: return ids
    return None


# ---------------------------------------------------------------- team season stats and ranks
def team_rows(sport, b):
    """Per game: {team id: dict(meta, for stats)} from one trimmed box score."""
    comp = {c.get('abbr'): c for c in b.get('competitors', [])}
    T = {}
    for t in b.get('teams') or []:
        tm = t.get('team') or {}; s = {x.get('name'): x.get('displayValue') for x in t.get('statistics', [])}
        c = comp.get(tm.get('abbreviation'), {})
        r = dict(pts=num(c.get('score')) or 0)
        if sport in ('fbs', 'nfl'):
            r.update(pass_yds=num(s.get('netPassingYards')) or 0, rush_yds=num(s.get('rushingYards')) or 0, rush_att=num(s.get('rushingAttempts')) or 0,
                     yds=num(s.get('totalYards')) or 0, comp=ma(s.get('completionAttempts'))[0])
        else:
            fg, t3, ft = ma(s.get('fieldGoalsMade-fieldGoalsAttempted')), ma(s.get('threePointFieldGoalsMade-threePointFieldGoalsAttempted')), ma(s.get('freeThrowsMade-freeThrowsAttempted'))
            orb = num(s.get('offensiveRebounds')) or 0; to = num(s.get('totalTurnovers')) or num(s.get('turnovers')) or 0
            r.update(fgm=fg[0], fga=fg[1], t3m=t3[0], t3a=t3[1], fta=ft[1], reb=num(s.get('totalRebounds')) or 0, ast=num(s.get('assists')) or 0,
                     orb=orb, to=to, poss=fg[1] - orb + to + 0.44 * ft[1])
        T[str(tm.get('id'))] = dict(meta=dict(id=str(tm.get('id')), abbr=tm.get('abbreviation'), location=tm.get('location'), name=tm.get('name'),
                                              display=tm.get('displayName'), short=tm.get('shortDisplayName')), r=r)
    return T


def rank(vals, ids, key, best_high):
    v = {i: vals[i][key] for i in ids if vals[i].get(key) is not None}
    srt = sorted(v.values(), reverse=best_high)
    return {i: srt.index(x) + 1 for i, x in v.items()}, len(v)


def teams(sport, day, games=None):
    games = games if games is not None else season_games(sport, day)
    acc = defaultdict(lambda: dict(gp=0, f=defaultdict(float), a=defaultdict(float), pos=defaultdict(lambda: defaultdict(float))))
    meta = {}
    for d, eid, b in games:
        T = team_rows(sport, b)
        if len(T) != 2: continue
        (i1, x1), (i2, x2) = T.items()
        for me, opp in ((i1, i2), (i2, i1)):
            A = acc[me]; A['gp'] += 1; meta[me] = T[me]['meta']
            for k, v in T[me]['r'].items(): A['f'][k] += v
            for k, v in T[opp]['r'].items(): A['a'][k] += v
        if sport == 'nba':   # points, rebounds, assists, threes allowed by position (G, F, C) to each defense
            for p in b.get('players') or []:
                tid = str((p.get('team') or {}).get('id')); opp = i2 if tid == i1 else i1
                for cat in p.get('statistics', [])[:1]:
                    K = cat.get('keys') or []
                    for a in cat.get('athletes', []):
                        st = a.get('stats') or []
                        if not st or a.get('didNotPlay'): continue
                        pos = (((a.get('athlete') or {}).get('position') or {}).get('abbreviation') or '?')[-1:].upper()
                        pos = {'G': 'G', 'F': 'F', 'C': 'C'}.get(pos, 'F')
                        v = dict(zip(K, st))
                        P = acc[opp]['pos'][pos]
                        P['pts'] += num(v.get('points')) or 0; P['reb'] += num(v.get('rebounds')) or 0; P['ast'] += num(v.get('assists')) or 0
                        P['t3m'] += ma(v.get('threePointFieldGoalsMade-threePointFieldGoalsAttempted'))[0]
    R = ranked_ids(sport, day)
    ids = [i for i in acc if (R is None or i in R) and acc[i]['gp']]
    V = {}
    for i, A in acc.items():
        g = A['gp'] or 1; f, a = A['f'], A['a']; v = dict(gp=A['gp'], pf=f['pts'] / g, pa=a['pts'] / g)
        if sport in ('fbs', 'nfl'):
            v.update(pass_f=f['pass_yds'] / g, rush_f=f['rush_yds'] / g, pass_a=a['pass_yds'] / g, rush_a=a['rush_yds'] / g,
                     ypc_a=(a['rush_yds'] / a['rush_att']) if a['rush_att'] else None, comp_a=a['comp'] / g, yds=f['yds'] / g, yds_a=a['yds'] / g)
        else:
            v.update(reb=f['reb'] / g, ast=f['ast'] / g, t3m=f['t3m'] / g, fgp=100 * f['fgm'] / f['fga'] if f['fga'] else None,
                     t3p=100 * f['t3m'] / f['t3a'] if f['t3a'] else None, reb_a=a['reb'] / g, ast_a=a['ast'] / g, t3m_a=a['t3m'] / g,
                     fgp_a=100 * a['fgm'] / a['fga'] if a['fga'] else None, pace=(f['poss'] + a['poss']) / 2 / g,
                     ortg=100 * f['pts'] / f['poss'] if f['poss'] else None, drtg=100 * a['pts'] / a['poss'] if a['poss'] else None,
                     opp_reb100=100 * a['reb'] / a['poss'] if a['poss'] else None, opp_ast100=100 * a['ast'] / a['poss'] if a['poss'] else None,
                     opp_t3m100=100 * a['t3m'] / a['poss'] if a['poss'] else None, opp_t3a100=100 * a['t3a'] / a['poss'] if a['poss'] else None)
            if sport == 'nba':
                for pos, P in A['pos'].items():
                    for k, x in P.items(): v[f'{pos}_{k}_a'] = x / g
        V[i] = v
    SPEC = {   # (key, label, per game?, side, best high?, fmt)
        'football': [('pf', 'Points', 1, 'offense', 1), ('pass_f', 'Passing yards', 1, 'offense', 1), ('rush_f', 'Rushing yards', 1, 'offense', 1),
                     ('pa', 'Points allowed', 1, 'defense', 0), ('pass_a', 'Passing yards allowed', 1, 'defense', 0), ('rush_a', 'Rushing yards allowed', 1, 'defense', 0)],
        'nba': [('pf', 'Points', 1, 'offense', 1), ('reb', 'Rebounds', 1, 'offense', 1), ('ast', 'Assists', 1, 'offense', 1), ('t3m', '3 pointers made', 1, 'offense', 1),
                ('pa', 'Points allowed', 1, 'defense', 0)],
        'college': [('pf', 'Points', 1, 'offense', 1), ('fgp', 'FG %', 0, 'offense', 1), ('t3p', '3 point %', 0, 'offense', 1), ('reb', 'Rebounds', 1, 'offense', 1),
                    ('pa', 'Points allowed', 1, 'defense', 0)]}['football' if sport in ('fbs', 'nfl') else 'nba' if sport == 'nba' else 'college']
    MATCH = ({'passing yards': ('pass_a', 0), 'receiving yards': ('pass_a', 0), 'rushing yards': ('rush_a', 0), 'yards per carry': ('ypc_a', 0),
              'receptions': ('comp_a', 0), 'points': ('pa', 0), 'total yards': ('yds_a', 0)} if sport in ('fbs', 'nfl') else
             {'points': ('pa', 0), 'rebounds': ('reb_a', 0), 'assists': ('ast_a', 0), '3 pointers made': ('t3m_a', 0), 'FG % allowed': ('fgp_a', 0)})
    if sport == 'nba':
        for pos, nm in (('G', 'guards'), ('F', 'forwards'), ('C', 'centers')):
            for k, lab in (('pts', 'points'), ('reb', 'rebounds'), ('ast', 'assists'), ('t3m', '3 pointers made')): MATCH[f'{lab} to {nm}'] = (f'{pos}_{k}_a', 0)
    RK = {}
    for key, *_ in SPEC: RK[key] = rank(V, ids, key, _[3] == 1)
    for lab, (key, _) in MATCH.items():
        if key not in RK: RK[key] = rank(V, ids, key, False)
    out = {}
    for i, v in V.items():
        m = meta[i]; ranked = i in ids
        stats = []
        for key, label, per, side, hi in SPEC:
            x = v.get(key)
            if x is None: continue
            e = dict(label=label, value=round(x, 1), side=side)
            if per: e['per'] = 'game'
            if ranked and i in RK[key][0]: e['rank'], e['of'] = RK[key][0][i], RK[key][1]
            stats.append(e)
        mt = {}
        for lab, (key, _) in MATCH.items():
            x = v.get(key)
            if x is None: continue
            e = dict(stat_label=lab, allowed_per_game=round(x, 2 if key == 'ypc_a' else 1))
            if ranked and i in RK[key][0]: e['rank'], e['of'] = RK[key][0][i], RK[key][1]
            mt[lab] = e
        out[i] = dict(**m, nba_code=NBA_CODE.get(m['abbr'], m['abbr']) if sport == 'nba' else None, gp=v['gp'], ranked=ranked, stats=stats, matchup=mt,
                      raw={k: (round(x, 3) if isinstance(x, float) else x) for k, x in v.items()})
    idx = {}
    for i, t in out.items():
        for k in (t['abbr'], t['location'], t['display'], t['short'], t.get('nba_code')):
            if k: idx.setdefault(k, i)
    res = dict(built=stamp(), source=f'ESPN box scores in the repo, {START[sport]} to {day} (games before today)', games=len(games),
               ranked_of=len(ids), rank_rule='1 = best: offense the most, defense the least allowed', teams=out, index=idx)
    gz_write(DATA / 'espn' / sport / day / 'team_stats.json.gz', res)
    print(f'teams {sport}: {len(out)} teams, {len(ids)} ranked, {len(games)} games')
    return res, V


# ---------------------------------------------------------------- NBA player logs, season_raw and friends
def nba_box_logs(games):
    """This season per player from the repo box scores: {athlete id: dict(name, pos, games=[...])}."""
    P = {}; team_dates = defaultdict(set)
    for d, eid, b in games:
        comp = {c.get('abbr'): c for c in b.get('competitors', [])}
        for p in b.get('players') or []:
            tm = p.get('team') or {}; ab = tm.get('abbreviation'); team_dates[NBA_CODE.get(ab, ab)].add(d)
            home = (comp.get(ab) or {}).get('home_away') == 'home'
            opp = next((NBA_CODE.get(k, k) for k in comp if k != ab), '')
            for cat in p.get('statistics', [])[:1]:
                K = cat.get('keys') or []
                for a in cat.get('athletes', []):
                    st = a.get('stats') or []; ath = a.get('athlete') or {}
                    if not st or a.get('didNotPlay'): continue
                    v = dict(zip(K, st)); mn = num(v.get('minutes')) or 0
                    if mn <= 0: continue
                    e = P.setdefault(str(ath.get('id')), dict(id=str(ath.get('id')), name=ath.get('displayName'), pos=(ath.get('position') or {}).get('abbreviation'), games=[]))
                    e['games'].append(dict(date=d, eid=eid, team=NBA_CODE.get(ab, ab), opp=opp, home=home, starter=bool(a.get('starter')), min=mn,
                                           pts=num(v.get('points')) or 0, reb=num(v.get('rebounds')) or 0, ast=num(v.get('assists')) or 0,
                                           t3m=ma(v.get('threePointFieldGoalsMade-threePointFieldGoalsAttempted'))[0],
                                           stl=num(v.get('steals')) or 0, blk=num(v.get('blocks')) or 0, to=num(v.get('turnovers')) or 0))
    for e in P.values(): e['games'].sort(key=lambda g: g['date'])
    return P, team_dates


def nba_last_season(aid):
    """2025-26 regular season game log for one athlete (ESPN), cached once in season/data/espn/nba/_lastseason/."""
    f = DATA / 'espn' / 'nba' / '_lastseason' / f'{aid}.json.gz'
    c = gz_read(f)
    if c is not None: return c
    gl = j(f'https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{aid}/gamelog?season=2026')
    if gl is None: return None
    names = gl.get('names') or []; EV = gl.get('events') or {}; out = []
    for stp in gl.get('seasonTypes') or []:
        if 'Regular Season' not in (stp.get('displayName') or ''): continue
        for cat in stp.get('categories') or []:
            if cat.get('type') != 'event': continue
            for ev in cat.get('events') or []:
                v = dict(zip(names, ev.get('stats') or [])); m = EV.get(str(ev.get('eventId'))) or {}
                tm = (m.get('team') or {}).get('abbreviation') or ''; op = (m.get('opponent') or {}).get('abbreviation') or ''
                out.append(dict(date=(m.get('gameDate') or '')[:10], team=NBA_CODE.get(tm, tm), opp=NBA_CODE.get(op, op), home=(m.get('atVs') or '') != '@',
                                min=num(v.get('minutes')) or 0, pts=num(v.get('points')) or 0, reb=num(v.get('totalRebounds')) or 0,
                                ast=num(v.get('assists')) or 0, t3m=ma(v.get('threePointFieldGoalsMade-threePointFieldGoalsAttempted'))[0]))
    out.sort(key=lambda g: g['date'])
    gz_write(f, out)
    return out


def nba(day, games=None):
    games = games if games is not None else season_games('nba', day)
    P, team_dates = nba_box_logs(games)
    sl = slate('nba', day); teams_today = {NBA_CODE.get(t.get('abbreviation'), t.get('abbreviation')) for g in sl for t in g[:2] if t}
    keep = {i: e for i, e in P.items() if e['games'] and e['games'][-1]['team'] in teams_today}
    fetched = 0
    for i, e in keep.items():
        had = (DATA / 'espn' / 'nba' / '_lastseason' / f'{i}.json.gz').exists()
        mpg = sum(g['min'] for g in e['games']) / len(e['games'])
        e['last_season'] = nba_last_season(i) if (had or mpg >= 8) else None
        fetched += (not had and e['last_season'] is not None)
    res = dict(built=stamp(), source='ESPN box scores (2026-27, repo) and ESPN athlete game logs (2025-26 regular season)',
               slate=sorted(teams_today), players=keep)
    gz_write(DATA / 'espn' / 'nba' / day / 'player_logs.json.gz', res)
    print(f'nba players: {len(keep)} players on {len(teams_today)} slate teams, {fetched} last-season logs fetched')
    return res


ODDS_NBA = {'player_points': 'p', 'player_rebounds': 'r', 'player_assists': 'a', 'player_threes': 't'}
SK = {'p': 'pts', 'r': 'reb', 'a': 'ast', 't': 't3m'}


def nba_lines(day):
    """{player name: {stat: line}} for games on `day` (Phoenix) from the latest props in odds/data (props_now, props_open or close_props)."""
    import read as OR
    rows = [r for r in OR.load('nba', day) if r['kind'] in ('props_now', 'props_open', 'close_props')]
    rows = [r for r in rows if dt.datetime.fromisoformat(r['commence'].replace('Z', '+00:00')).astimezone(PHX).strftime('%Y-%m-%d') == day]
    L = {}; src = set()
    for eid, rs in OR.group(rows, lambda r: r['event_id']).items():
        last = max(r['snap'] for r in rs); cur = [r for r in rs if r['snap'] == last]; src.add(cur[0]['kind'])
        for pl, mk in OR.props(cur).items():
            for m, e in mk.items():
                if m in ODDS_NBA and e.get('line') is not None: L.setdefault(pl, {})[ODDS_NBA[m]] = e['line']
    return L, sorted(src)


def nba_raw(day):
    logs = gz_read(DATA / 'espn' / 'nba' / day / 'player_logs.json.gz')
    if not logs: print('nba_raw: no player_logs for', day); return
    L, src = nba_lines(day)
    byname = {nz(e['name']): e for e in logs['players'].values()}
    ALIAS = {'herb jones': 'herbert jones', 'ron holland': 'ronald holland', 'nic claxton': 'nicolas claxton', 'cam johnson': 'cameron johnson',
             'kj martin': 'kenyon martin', 'gg jackson': 'gregory jackson', 'bub carrington': 'carlton carrington', 'moe wagner': 'moritz wagner'}
    for k, v in ALIAS.items():
        if v in byname and k not in byname: byname[k] = byname[v]
    last = defaultdict(list)
    for k, e in byname.items(): last[(k.split(' ')[0][:1], k.split(' ')[-1])].append(e)
    for name in L:   # fallback: same first initial and last name, only when unique
        k = nz(name)
        if k not in byname and len({id(e) for e in last.get((k[:1], k.split(' ')[-1]), [])}) == 1: byname[k] = last[(k[:1], k.split(' ')[-1])][0]
    out = DATA / 'espn' / 'nba' / day; when = stamp()
    sr = [f'ESPN box scores 2026-27 and ESPN athlete game logs 2025-26 (GitHub players pull), built {when}; lines {",".join(src) or "none"} (Odds API median). '
          'name|team now|team last season|2025-26 GP|2025-26 MPG|2026-27 minutes by game|stat+line:2025-26 avg/sd/games over line/2026-27 values by game (p points, r rebounds, a assists, t 3PM)']
    pr = [f'Built {when} from season_raw: 2026-27 regular season games, ESPN box scores. name|gp|min|P pts|R reb|A ast|T 3pm|team|last date|prev team|games this season']
    sp = [f'ESPN 2025-26 home/road splits per prop stat (avg x games), built {when}. B2B rows: players with 20+ games in the repo logs, both seasons: group (S = 28+ MPG, O = 15 to 28), b2b games, b2b MPG, b2b PRA per minute, other games, other MPG, other PRA per minute']
    miss = []
    for name in sorted(L):
        e = byname.get(nz(name))
        if not e: miss.append(name); continue
        b = e['games']; a = e.get('last_season') or []
        tn = b[-1]['team'] if b else '-'; tl = a[-1]['team'] if a else '-'
        mpg = sum(g['min'] for g in a) / len(a) if a else 0
        toks, stoks = [], []
        for s in sorted(L[name]):
            ln = L[name][s]; k = SK[s]; v = [g[k] for g in a]; av = sum(v) / len(v) if v else 0
            sd = stt.stdev(v) if len(v) > 1 else 0; ov = sum(1 for x in v if x > ln)
            toks.append(f"{s}{ln:g}:{r1(av)}/{r1(sd)}/{ov}/" + '-'.join(str(int(g[k])) for g in b))
            h = [g[k] for g in a if g['home']]; w = [g[k] for g in a if not g['home']]
            avg = lambda x: sum(x) / len(x) if x else 0
            stoks.append(f'{s}{ln:g}:h{r1(avg(h))}x{len(h)}a{r1(avg(w))}x{len(w)}')
        sr.append('|'.join([e['name'], tn, tl, str(len(a)), r1(mpg), '-'.join(str(round(g['min'])) for g in b), ' '.join(toks)]))
        sp.append(e['name'] + '|' + ' '.join(stoks))
        b20 = b[-20:]
        pr.append('|'.join([e['name'], str(len(b20)), str(round(sum(g['min'] for g in b20) / len(b20))) if b20 else '0',
                            'P' + ','.join(str(int(g['pts'])) for g in b20), 'R' + ','.join(str(int(g['reb'])) for g in b20),
                            'A' + ','.join(str(int(g['ast'])) for g in b20), 'T' + ','.join(str(int(g['t3m'])) for g in b20), tn, '-', tl, str(len(b))]))
    # B2B rows from every cached player log (this season box scores know team dates; last season uses the player's own dates)
    acc = {'S': [0] * 6, 'O': [0] * 6}
    for e in logs['players'].values():
        for gs, own in ((e.get('last_season') or [], True), (e['games'], False)):
            if len(gs) < 20: continue
            mp = sum(g['min'] for g in gs) / len(gs); grp = 'S' if mp >= 28 else ('O' if mp >= 15 else None)
            if not grp: continue
            ds = {g['date'] for g in gs}
            for g in gs:
                prev = (dt.date.fromisoformat(g['date']) - dt.timedelta(1)).isoformat()
                o = 0 if prev in ds else 3; A = acc[grp]; A[o] += 1; A[o + 1] += g['min']; A[o + 2] += g['pts'] + g['reb'] + g['ast']
    for k in ('S', 'O'):
        t = acc[k]
        if t[0] and t[3]: sp.append(f'B2B|{k}|{t[0]},{t[1] / t[0]:.2f},{t[2] / t[1]:.4f},{t[3]},{t[4] / t[3]:.2f},{t[5] / t[4]:.4f}')
    (out / 'season_raw.txt').write_text('\n'.join(sr) + '\n')
    (out / 'players_raw.txt').write_text('\n'.join(pr) + '\n')
    (out / 'splits_raw.txt').write_text('\n'.join(sp) + '\n')
    print(f'nba_raw {day}: {len(sr) - 1} prop players in season_raw ({sum(len(x) for x in L.values())} lines), not matched: {", ".join(miss) or "none"}')


def nba_extras(day, V, games):
    """usage_raw (share of team production by players listed Out), matchup_raw (opponent per 100), ratings.txt (ORtg, DRtg, pace)."""
    out = DATA / 'espn' / 'nba' / day; when = stamp()
    ts = gz_read(out / 'team_stats.json.gz') or {'teams': {}}
    rows = []
    for i, t in ts['teams'].items():
        r = t['raw']
        if r.get('opp_reb100') is None: continue
        rows.append((t['nba_code'], t['name'], r))
    rows.sort()
    yday = (dt.date.fromisoformat(day) - dt.timedelta(1))
    (out / 'ratings.txt').write_text(f'{yday.month}/{yday.day}/{yday.year}|' + ';'.join(f"{c},{r['gp']},{r['ortg']:.1f},{r['drtg']:.1f},{r['pace']:.2f}" for c, n, r in rows) + '\n')
    (out / 'matchup_raw.txt').write_text(f'ESPN box scores, opponent per 100 possessions (estimated possessions), built {when}. season|team|gp|opp reb|opp ast|opp 3pm|opp 3pa\n'
                                         'OPP 2026-27 ' + ';'.join(f"{n},{r['gp']},{r['opp_reb100']:.1f},{r['opp_ast100']:.1f},{r['opp_t3m100']:.1f},{r['opp_t3a100']:.1f}" for c, n, r in rows) + '\n')
    inj = gz_read(DATA / 'espn' / 'nba' / day / 'injuries.json.gz') or {}
    logs = gz_read(out / 'player_logs.json.gz') or {'players': {}, 'slate': []}
    P, _ = nba_box_logs(games)
    outn = defaultdict(list)
    for t in inj.get('injuries', []):
        for x in t.get('injuries', []):
            if (x.get('status') or '').lower() == 'out': outn[nz((x.get('athlete') or {}).get('displayName'))].append(1)
    U = [f'ESPN box scores 2026-27 totals, built {when}: share of each team\'s season points, rebounds, assists, 3PM produced by players listed Out (ESPN injuries). team|pts,reb,ast,3pm|players (games played)']
    for tm in logs['slate']:
        tot = defaultdict(float); og = defaultdict(float); names = []
        for e in P.values():
            gs = [g for g in e['games'] if g['team'] == tm]
            for g in gs:
                for k in ('pts', 'reb', 'ast', 't3m'): tot[k] += g[k]
            if gs and nz(e['name']) in outn:
                names.append(f"{e['name']}({len(gs)}g)")
                for g in gs:
                    for k in ('pts', 'reb', 'ast', 't3m'): og[k] += g[k]
        U.append(f"{tm}|" + ','.join(f"{(og[k] / tot[k] if tot[k] else 0):.3f}" for k in ('pts', 'reb', 'ast', 't3m')) + '|' + ','.join(names))
    (out / 'usage_raw.txt').write_text('\n'.join(U) + '\n')
    print(f'nba extras: ratings {len(rows)} teams, usage {len(U) - 1} slate teams')


# ---------------------------------------------------------------- FBS players_raw
CATK = {'passing': ('pass', 'passingYards', 'passingTouchdowns', 'completions/passingAttempts'), 'rushing': ('rush', 'rushingYards', 'rushingTouchdowns', 'rushingAttempts'),
        'receiving': ('rec', 'receivingYards', 'receivingTouchdowns', 'receptions')}


def fbs(day, games=None):
    sl, sday = slate('fbs', day), day
    for k in range(1, 8):
        if sl: break
        sday = (dt.date.fromisoformat(day) + dt.timedelta(k)).isoformat(); sl = slate('fbs', sday)
    games = games if games is not None else season_games('fbs', sday)
    ids = {str(t.get('id')) for g in sl for t in g[:2] if t}
    P = {}
    for d, eid, b in games:
        for p in b.get('players') or []:
            tm = p.get('team') or {}
            if str(tm.get('id')) not in ids: continue
            for cat in p.get('statistics', []):
                if cat.get('name') not in CATK: continue
                c, yk, tk, vk = CATK[cat['name']]; K = cat.get('keys') or []
                for a in cat.get('athletes', []):
                    v = dict(zip(K, a.get('stats') or [])); ath = a.get('athlete') or {}
                    vol = ma(v.get(vk))[1] if c == 'pass' else (num(v.get(vk)) or 0)
                    e = P.setdefault((tm.get('location'), ath.get('displayName'), c), dict(team=tm.get('location'), team_id=str(tm.get('id')), id=str(ath.get('id')),
                                                                                       name=ath.get('displayName'), cat=c, games=[]))
                    e['games'].append(dict(date=d, eid=eid, yds=num(v.get(yk)) or 0, td=num(v.get(tk)) or 0, vol=vol,
                                           comp=ma(v.get(vk))[0] if c == 'pass' else None))
    keep = [e for e in P.values() if (e['cat'] != 'pass' or max(g['vol'] for g in e['games']) >= 5) and sum(g['yds'] for g in e['games']) >= 20]
    keep.sort(key=lambda e: (e['team'], e['cat'], -sum(g['yds'] for g in e['games'])))
    out = DATA / 'espn' / 'fbs' / sday
    (out).mkdir(parents=True, exist_ok=True)
    (out / 'players_raw.txt').write_text('\n'.join(f"{e['team']}|{e['name']}|{e['cat']}|" + ','.join(f"{int(g['yds'])}/{int(g['td'])}" for g in e['games']) for e in keep) + '\n')
    gz_write(out / 'player_logs.json.gz', dict(built=stamp(), slate_date=sday, source='ESPN box scores in the repo (FBS games, regular season and bowls)',
                                               note='vol = pass attempts, rush attempts or receptions', players=keep))
    print(f'fbs players {sday}: {len(keep)} player rows for {len(ids)} slate teams ({len(sl)} games)')


# ---------------------------------------------------------------- NHL skater and goalie logs, team stats
def nhl(day):
    out = DATA / 'nhl' / day; out.mkdir(parents=True, exist_ok=True)
    gj = out / 'games.json'
    games = json.loads(gj.read_text()) if gj.exists() else []
    if not games:
        sch = j(f'{NHL}/v1/schedule/{day}') or {}
        wk = next((d for d in sch.get('gameWeek', []) if d['date'] == day), {'games': []})
        games = [dict(away=g['awayTeam']['abbrev'], home=g['homeTeam']['abbrev']) for g in wk['games'] if g.get('gameType') == 2]
    teams_ = sorted({t for g in games for t in (g['away'], g['home'])})
    PL, GO, plog = {}, {}, []
    for t in teams_:
        cs = j(f'{NHL}/v1/club-stats/{t}/now') or {'skaters': [], 'goalies': []}
        rows = []
        for p in cs.get('skaters', []):
            if p.get('gamesPlayed', 0) < 1: continue
            lg = [g for g in (j(f'{NHL}/v1/player/{p["playerId"]}/game-log/now') or {}).get('gameLog', []) if g.get('gameTypeId', 2) == 2]
            lg.sort(key=lambda g: g['gameDate'])
            log = [dict(date=g['gameDate'], opp=g.get('opponentAbbrev'), home=g.get('homeRoadFlag') == 'H', sog=g.get('shots', 0), g=g.get('goals', 0), a=g.get('assists', 0),
                        pts=g.get('points', 0), ppp=g.get('powerPlayPoints', 0), toi=g.get('toi')) for g in lg]
            def summ(L):
                n = len(L) or 1
                return dict(gp=len(L), sog=round(sum(x['sog'] for x in L) / n, 2), pts=round(sum(x['pts'] for x in L) / n, 2), g=round(sum(x['g'] for x in L) / n, 2),
                            sog_tot=sum(x['sog'] for x in L), pts_tot=sum(x['pts'] for x in L), g_tot=sum(x['g'] for x in L),
                            s2=sum(1 for x in L if x['sog'] >= 2), s3=sum(1 for x in L if x['sog'] >= 3), p1=sum(1 for x in L if x['pts'] >= 1), g1=sum(1 for x in L if x['g'] >= 1))
            rows.append(dict(id=p['playerId'], name=f"{p['firstName']['default']} {p['lastName']['default']}", last=p['lastName']['default'],
                             first=p['firstName']['default'], pos=p.get('positionCode'), season=summ(log), last5=summ(log[-5:]), log=log))
        names = [r['last'] for r in rows]
        for r in rows:
            key = r['last'] if names.count(r['last']) == 1 else f"{r['first'][0]}.{r['last']}"
            plog.append(f"{t}:{key}:" + ','.join(f"{x['date']}/{x['sog']}/{x['g']}/{x['a']}" for x in r['log']))
        PL[t] = rows
        gl = []
        for g in cs.get('goalies', []):
            if g.get('gamesPlayed', 0) < 1: continue
            lg = sorted([x for x in (j(f'{NHL}/v1/player/{g["playerId"]}/game-log/now') or {}).get('gameLog', []) if x.get('gameTypeId', 2) == 2], key=lambda x: x['gameDate'])
            log = [dict(date=x['gameDate'], opp=x.get('opponentAbbrev'), home=x.get('homeRoadFlag') == 'H', started=bool(x.get('gamesStarted')), sa=x.get('shotsAgainst', 0),
                        ga=x.get('goalsAgainst', 0), saves=(x.get('shotsAgainst', 0) or 0) - (x.get('goalsAgainst', 0) or 0), decision=x.get('decision')) for x in lg]
            st_ = [x for x in log if x['started']]
            gl.append(dict(id=g['playerId'], name=f"{g['firstName']['default']} {g['lastName']['default']}", starts=len(st_),
                           saves_avg=round(sum(x['saves'] for x in st_) / len(st_), 1) if st_ else None,
                           saves_last5=round(sum(x['saves'] for x in st_[-5:]) / len(st_[-5:]), 1) if st_ else None, log=log))
        GO[t] = gl
    (out / 'plogs.txt').write_text('\n'.join(plog) + '\n')
    gz_write(out / 'skater_logs.json.gz', dict(built=stamp(), source='NHL API club-stats and player game-log (regular season)',
                                               fields='season and last5: per game averages (sog, pts, g), totals, games with 2+/3+ SOG, 1+ point, 1+ goal',
                                               teams=teams_, skaters=PL, goalies=GO))
    print(f'nhl players {day}: {sum(len(v) for v in PL.values())} skaters, {sum(len(v) for v in GO.values())} goalies, {len(teams_)} teams')
    nhl_teams(day)


def nhl_teams(day):
    tl = {t['id']: t for t in (j('https://api.nhle.com/stats/rest/en/team') or {}).get('data', [])}
    sm = (j('https://api.nhle.com/stats/rest/en/team/summary?cayenneExp=seasonId=20262027%20and%20gameTypeId=2') or {}).get('data', [])
    V = {}
    for r in sm:
        code = (tl.get(r['teamId']) or {}).get('triCode') or r['teamFullName']
        gp = r['gamesPlayed'] or 1; sa = r['shotsAgainstPerGame'] * gp
        V[code] = dict(name=r['teamFullName'], gp=r['gamesPlayed'], gf=r['goalsForPerGame'], sf=r['shotsForPerGame'], pp=100 * (r['powerPlayPct'] or 0),
                       ga=r['goalsAgainstPerGame'], sa=r['shotsAgainstPerGame'], pk=100 * (r['penaltyKillPct'] or 0),
                       sv=(1 - r['goalsAgainst'] / sa) if sa else None)
    ids = list(V)
    SPEC = [('gf', 'Goals', 1, 'offense', 1, 2), ('sf', 'Shots', 1, 'offense', 1, 1), ('pp', 'Power play %', 0, 'offense', 1, 1),
            ('ga', 'Goals allowed', 1, 'defense', 0, 2), ('sv', 'Save %', 0, 'defense', 1, 3)]
    MATCH = {'shots on goal': ('sa', 0), 'goals': ('ga', 0), 'penalty kill %': ('pk', 1)}
    RK = {k: rank(V, ids, k, hi == 1) for k, _, _, _, hi, _ in SPEC}
    for _, (k, hi) in MATCH.items(): RK.setdefault(k, rank(V, ids, k, hi == 1))
    out = {}
    for c, v in V.items():
        stats = []
        for k, lab, per, side, hi, dp in SPEC:
            if v.get(k) is None: continue
            e = dict(label=lab, value=round(v[k], dp) if k != 'sv' else f"{v[k]:.3f}".lstrip('0'), side=side, rank=RK[k][0][c], of=RK[k][1])
            if per: e['per'] = 'game'
            stats.append(e)
        mt = {lab: dict(stat_label=lab, allowed_per_game=round(v[k], 1 if k != 'ga' else 2), rank=RK[k][0][c], of=RK[k][1]) for lab, (k, _) in MATCH.items()}
        mt['penalty kill %'].pop('allowed_per_game'); mt['penalty kill %']['value'] = round(v['pk'], 1)
        out[c] = dict(abbr=c, name=v['name'], gp=v['gp'], stats=stats, matchup=mt, raw={k: (round(x, 4) if isinstance(x, float) else x) for k, x in v.items()})
    res = dict(built=stamp(), source='NHL API stats team summary, 2026-27 regular season', ranked_of=len(ids), rank_rule='1 = best', teams=out)
    gz_write(DATA / 'nhl' / day / 'team_stats.json.gz', res); gz_write(DATA / 'espn' / 'nhl' / day / 'team_stats.json.gz', res)
    print(f'teams nhl: {len(out)} teams ranked')


# ---------------------------------------------------------------- main
def run(mode, sports, day):
    ALL = ['nba', 'nhl', 'ncaam', 'ncaaw', 'nfl', 'fbs']
    sports = [s for s in (sports or ALL) if s in ALL]
    t0 = time.time()
    def step(name, f, *a):
        try: return f(*a)
        except Exception as e:
            import traceback; traceback.print_exc(); print(name, 'error', type(e).__name__, str(e)[:200])
    if mode in ('all', 'backfill'):
        for s in sports:
            if s != 'nhl': step('backfill ' + s, backfill, s, day)
    G = {}
    if mode in ('all', 'teams', 'nba', 'fbs', 'build'):
        for s in sports:
            if s != 'nhl': G[s] = season_games(s, day)
    if mode in ('all', 'teams', 'build'):
        for s in sports:
            if s == 'nhl': step('teams nhl', nhl_teams, day)
            else: step('teams ' + s, teams, s, day, G[s])
    if 'nba' in sports and mode in ('all', 'nba', 'build'):
        step('nba', nba, day, G['nba'])
        step('nba extras', nba_extras, day, None, G['nba'])
    if 'nba' in sports and mode in ('all', 'nba', 'nba_raw', 'build'): step('nba_raw', nba_raw, day)
    if 'nhl' in sports and mode in ('all', 'nhl'): step('nhl', nhl, day)
    if 'fbs' in sports and mode in ('all', 'fbs', 'build'): step('fbs', fbs, day, None)
    print(f'players {mode} {day}: done in {time.time() - t0:.0f}s')


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    sports = [s for s in sys.argv[2].split(',') if s] if len(sys.argv) > 2 and sys.argv[2] else None
    day = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else phx_now().strftime('%Y-%m-%d')
    run(mode, sports, day)
