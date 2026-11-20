"""Starting lineups for game docs from the repo ESPN box scores (Trina Nov 19 2026, B160). Runs every run, lean or full.

    python3 season/lineups_build.py <hub dir (ledger unpack)> <out dir> <YYYY-MM-DD> [sports]

NBA, NCAAM, NCAAW: starters = the five with the most starts in the team's last 3 games (ties by minutes); a starter listed
Out on the ESPN injury report is moved off the five with the next man up named as his backup; rotation players (10+ minutes
a game) follow with starter false. NHL: the 18 skaters dressed in the team's last game plus the projected goalie (most
starts in the last 5 games unless NHL_GOALIES names one). Every player gets a 0 to 100 rating (percentile of a per minute
composite across the sport) and plain strengths. Any player with a prop pick that day is added if missing.
Football (22 starters) is not built here: ESPN box scores carry no offensive line.
Writes <out dir>/<sport>/<game doc id>.json = {"lineups": {...}, "lineups_source": ...} for a hub update (merge)."""
import datetime as dt, glob, gzip, json, os, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ESPN = ROOT / 'data' / 'espn'
TO_ESPN = {'nba': {'GSW': 'GS', 'NYK': 'NY', 'SAS': 'SA', 'NOP': 'NO', 'UTA': 'UTAH', 'WAS': 'WSH'},
           'nhl': {'TBL': 'TB', 'LAK': 'LA', 'NJD': 'NJ', 'SJS': 'SJ', 'UTA': 'UTAH'}}
OUT_WORDS = ('out', 'injured reserve', 'suspension')


def num(x):
    try: return float(str(x).split('-')[0])
    except Exception: return 0.0


def toi(x):
    try: m, s = str(x).split(':'); return int(m) + int(s) / 60
    except Exception: return 0.0


def boxes(sport, day, back=30):
    d0 = dt.date.fromisoformat(day); res = []
    for i in range(1, back + 1):
        d = (d0 - dt.timedelta(days=i)).isoformat(); f = ESPN / sport / d / 'boxscores.json.gz'
        if f.exists():
            for b in json.load(gzip.open(f, 'rt')).values(): res.append((d, b))
    return sorted(res, key=lambda x: x[0], reverse=True)


def injuries(sport, day):
    f = ESPN / sport / day / 'injuries.json.gz'; m = {}
    if not f.exists(): return m
    for t in json.load(gzip.open(f, 'rt')).get('injuries', []):
        for y in t.get('injuries', []):
            m[(y.get('athlete') or {}).get('displayName', '').lower()] = (y.get('status') or '', (y.get('shortComment') or '')[:140])
    return m


def pct_fn(vals):
    v = sorted(vals)
    return lambda x: int(round(100 * sum(1 for y in v if y <= x) / len(v))) if v else 50


def basketball(sport, bx):
    """per team: list of games newest first, each {player: dict(start, min, pos, s...)}"""
    T = defaultdict(list); P = defaultdict(lambda: defaultdict(float))
    for d, b in bx:
        for t in b.get('players') or []:
            ab = (t.get('team') or {}).get('abbreviation'); st = (t.get('statistics') or [{}])[0]
            lab = st.get('labels') or st.get('names') or []; ix = {k: i for i, k in enumerate(lab)}; g = {}
            for a in st.get('athletes') or []:
                if a.get('didNotPlay') or not a.get('stats'): continue
                n = (a.get('athlete') or {}).get('displayName'); s = a['stats']; get = lambda k: num(s[ix[k]]) if k in ix and ix[k] < len(s) else 0.0
                mn = get('MIN')
                if mn <= 0: continue
                g[n] = dict(start=bool(a.get('starter')), min=mn, pos=((a.get('athlete') or {}).get('position') or {}).get('abbreviation', ''))
                p = P[(ab, n)]; p['min'] += mn; p['g'] += 1; p['pts'] += get('PTS'); p['reb'] += get('REB'); p['ast'] += get('AST')
                p['d'] += get('STL') + get('BLK'); p['to'] += get('TO'); p['t3'] += num(str(s[ix['3PT']]).split('-')[0]) if '3PT' in ix and ix['3PT'] < len(s) else 0
            if g: T[ab].append(g)
    comp = {k: (v['pts'] + 1.2 * v['reb'] + 1.5 * v['ast'] + 2 * v['d'] - v['to']) * 36 / v['min'] for k, v in P.items() if v['min'] >= 30}
    return T, P, comp


def hockey(bx):
    T = {}; P = defaultdict(lambda: defaultdict(float)); GO = defaultdict(list)
    for d, b in bx:
        for t in b.get('players') or []:
            ab = (t.get('team') or {}).get('abbreviation'); dressed = []
            for st in t.get('statistics') or []:
                lab = st.get('labels') or []; ix = {k: i for i, k in enumerate(lab)}
                for a in st.get('athletes') or []:
                    n = (a.get('athlete') or {}).get('displayName'); s = a.get('stats') or []
                    pos = ((a.get('athlete') or {}).get('position') or {}).get('abbreviation', '')
                    if st.get('name') == 'goalies' or pos == 'G':
                        if s and toi(s[ix['TOI']] if 'TOI' in ix else 0) > 20: GO[ab].append(n)
                        continue
                    get = lambda k: num(s[ix[k]]) if k in ix and ix[k] < len(s) else 0.0
                    m = toi(s[ix['TOI']]) if 'TOI' in ix and ix['TOI'] < len(s) else 0
                    dressed.append((n, pos))
                    p = P[(ab, n)]; p['toi'] += m; p['g'] += 1; p['pts'] += get('G') + get('A'); p['sog'] += get('SOG'); p['bs'] += get('BS'); p['ht'] += get('HT')
            if dressed: T.setdefault(ab, []).append(dressed)
    comp = {k: (v['pts'] * 1.0 + v['sog'] * 0.15 + v['bs'] * 0.05) * 60 / v['toi'] for k, v in P.items() if v['toi'] >= 30}
    return T, P, comp, GO


def tags_bb(v, th):
    w = []
    if v['pts'] * 36 / v['min'] >= th['pts']: w.append('scoring')
    if v['reb'] * 36 / v['min'] >= th['reb']: w.append('rebounding')
    if v['ast'] * 36 / v['min'] >= th['ast']: w.append('playmaking')
    if v['d'] * 36 / v['min'] >= th['d']: w.append('steals and blocks')
    return w


def main():
    hub, out, day = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    sports = sys.argv[4].split(',') if len(sys.argv) > 4 and sys.argv[4] else ['nba', 'nhl', 'ncaam', 'ncaaw']
    goalies = json.loads(os.environ.get('NHL_GOALIES', '{}'))   # {"CHI": "Spencer Knight", ...} projected starters for today
    rep = {}
    SK = {}
    f = ROOT / 'data' / 'nhl' / day / 'skater_logs.json.gz'
    if f.exists():
        for t, L in json.load(gzip.open(f, 'rt')).get('skaters', {}).items():
            for x in L:
                se = x.get('season') or {}
                if se.get('gp', 0) >= 3: SK[(t, x['name'].lower())] = se.get('pts', 0) + 0.15 * se.get('sog', 0)
    skp = pct_fn(SK.values())
    def nhl_rate(team, name, fallback):
        v = SK.get((team, name.lower()))
        return skp(v) if v is not None else 50
    NB = {}
    f = ESPN / 'nba' / day / 'player_logs.json.gz'
    if f.exists():
        for x in json.load(gzip.open(f, 'rt')).get('players', {}).values():
            G = [g for g in x['games'] if g['date'] >= '2026-10-01' and g.get('min')]
            m = sum(g['min'] for g in G)
            if m >= 60: NB[x['name']] = sum((g.get('pts') or 0) + 1.2 * (g.get('reb') or 0) + 1.5 * (g.get('ast') or 0) + 2 * ((g.get('stl') or 0) + (g.get('blk') or 0)) - (g.get('to') or 0) for g in G) * 36 / m
    nbp = pct_fn(NB.values())
    for sp in sports:
        games = []
        for f in glob.glob(f'{hub}/sports/{sp}/games/{day}_*.json'):
            g = json.load(open(f)); g = g.get('data', g); g['__id'] = Path(f).stem; games.append(g)
        props = defaultdict(set)
        for f in glob.glob(f'{hub}/sports/{sp}/picks/{day}_*_prop_*.json'):
            p = json.load(open(f)); p = p.get('data', p)
            if p.get('player'): props['_'.join(Path(f).stem.split('_')[:2])].add((p['player'], p.get('team')))
        bx = boxes(sp, day); inj = injuries(sp, day); fx = TO_ESPN.get(sp, {}); n_ok = 0
        (out / sp).mkdir(parents=True, exist_ok=True)
        if sp == 'nhl':
            T, P, comp, GO = hockey(bx); pc = pct_fn(comp.values())
        else:
            T, P, comp = basketball(sp, bx); pc = pct_fn(comp.values())
            per = lambda k: sorted(v[k] * 36 / v['min'] for v in P.values() if v['min'] >= 30)
            th = {k: (lambda L: L[int(len(L) * 0.75)] if L else 99)(per(k)) for k in ('pts', 'reb', 'ast', 'd')}
        for g in games:
            L = {}
            for side in ('away', 'home'):
                code = ((g.get(side) or {}).get('code') or ''); ab = fx.get(code, code)
                rows = []
                if sp == 'nhl':
                    games3 = (T.get(ab) or [])[:3]; dressed = games3[0] if games3 else []
                    extra = [x for gm in games3[1:] for x in gm if x[0] not in {y[0] for y in dressed}]
                    outs = [x for x in dressed if any(w in inj.get(x[0].lower(), ('', ''))[0].lower() for w in OUT_WORDS)]
                    ups = [x for x in extra if not any(w in inj.get(x[0].lower(), ('', ''))[0].lower() for w in OUT_WORDS)]
                    for o in outs:
                        b = next((u for u in ups if (u[1] == 'D') == (o[1] == 'D')), None)
                        if b: ups.remove(b); dressed = dressed + [b]
                    for n, pos in dressed:
                        v = P.get((ab, n)) or {}; st = inj.get(n.lower(), ('', '')); isout = (n, pos) in outs
                        r0 = dict(player=n, pos=pos, starter=not isout, status=st[0] or 'Active', rating=nhl_rate(code, n, comp.get((ab, n))),
                                         strengths=[x for x, ok in (('shooting volume', v.get('toi') and v.get('sog', 0) * 60 / v['toi'] >= 8), ('scoring', v.get('toi') and v.get('pts', 0) * 60 / v['toi'] >= 2.2), ('shot blocking', v.get('toi') and v.get('bs', 0) * 60 / v['toi'] >= 3.5)) if ok])
                        if isout: r0['backup'] = next((u[0] for u in dressed if u not in outs and u not in games3[0]), None) or 'Next man up'
                        rows.append(r0)
                    gname = goalies.get(code)
                    if not gname and GO.get(ab):
                        last5 = GO[ab][:5]; gname = max(set(last5), key=last5.count)
                    if gname:
                        gp = len([x for x in GO.get(ab, []) if x == gname])
                        rows.append(dict(player=gname, pos='G', starter=True, status=('Projected (Daily Faceoff)' if goalies.get(code) else 'Expected'), rating=min(99, 40 + 5 * gp), strengths=[]))
                else:
                    G3 = (T.get(ab) or [])[:3]
                    if not G3: L[side] = []; continue
                    starts = defaultdict(float)
                    for gm in G3:
                        for n, x in gm.items(): starts[n] += (1 if x['start'] else 0) + x['min'] / 1000
                    order = sorted(starts, key=lambda n: -starts[n])
                    mpg = {n: v['min'] / v['g'] for (t, n), v in P.items() if t == ab and v['g']}
                    pos = {n: x['pos'] for gm in G3 for n, x in gm.items()}
                    five, outs = [], []
                    for n in order:
                        st = inj.get(n.lower(), ('', ''))
                        if any(w in st[0].lower() for w in OUT_WORDS): outs.append(n); continue
                        if len(five) < 5: five.append(n)
                    bench = [n for n in sorted(mpg, key=lambda n: -mpg[n]) if n not in five and n not in outs and mpg[n] >= 10][:6]
                    def row(n, starter, backup=None):
                        v = P.get((ab, n)); st = inj.get(n.lower(), ('', ''))
                        r = dict(player=n, pos=pos.get(n, ''), starter=starter, status=st[0] or 'Active', rating=(nbp(NB[n]) if sp == 'nba' and n in NB else pc(comp.get((ab, n), 0))),
                                 strengths=tags_bb(v, th) if v and v['min'] >= 30 else [], mpg=round(mpg.get(n, 0), 1))
                        if backup: r['backup'] = backup
                        if st[1]: r['note'] = st[1]
                        return r
                    rows = [row(n, True) for n in five] + [row(n, False) for n in bench]
                    for n in outs[:3]:
                        if starts[n] >= 1: rows.append(row(n, False, backup=bench[0] if bench else None))
                names = {r['player'].lower() for r in rows}
                for pl, tm in props.get(g['__id'], ()):
                    if pl.lower() not in names and (not tm or tm == code):
                        rows.append(dict(player=pl, pos='', starter=False, status=inj.get(pl.lower(), ('Active', ''))[0] or 'Active', rating=None, strengths=[], note='Prop player, not in the recent box scores'))
                L[side] = rows
            if L.get('away') and L.get('home'):
                json.dump(dict(lineups=L, lineups_source=f'ESPN box scores last 3 games and injury report, {day} (season/lineups_build.py)'),
                          open(out / sp / f"{g['__id']}.json", 'w'), ensure_ascii=False, separators=(',', ':')); n_ok += 1
        rep[sp] = dict(games=len(games), lineups=n_ok)
    print(json.dumps(rep))


if __name__ == '__main__':
    main()
