"""Grade pending Season Cards picks from the ESPN finals saved by season/espn_pull.py (Season Cards, Nov 12 2026).

    python3 season/grade.py <sport> <pending.json | folder of pick docs> <out updates.json>

Input: the hub ledger's pending docs (ArtifactData query export: a list of {id, version, data} or a folder of doc files).
Output: {"updates": [{id, version, result, final, close fields}], "ungraded": [{id, why}], "no_close": [{id, why}]};
the run writes the updates with one ArtifactData batch (update result, final and the close fields, if_version = version).

Close step (B82, B135, A64; Nov 19): every graded pick also gets the saved Odds API close (odds/data/<sport>/<date>/close_*.csv.gz
via odds/read.py: median of books, the latest close read before the start; first half or period lines and team totals from
close_periods, props from close_props): close_line, close_price, clv, clv_unit, close_result, close_source, close_at.
result stays graded at the pick's own line; close_result is the same pick graded at the close line (A64 uses it).
clv: points for spread, total, team total and prop lines (+ = the pick got a better number than the close); for moneylines,
implied win chance at the close minus at the pick price, in percentage points (+ = the price shortened after the pick).
Options:  --no-close          skip the close step
          --backfill-close    also add the close fields to already graded picks that have no close_line yet
          --day YYYY-MM-DD    only picks dated that day Rules, same as every sport skill:
  Moneyline: higher final score (shootout and overtime included). Spread / Puck line: team margin + line > 0 win, = 0 push.
  Total: final total vs line, equal is push. Team total: the team's points. 1st half / 1st period markets: period scores
  (NBA, NFL, FBS, NCAAW quarters 1+2; NCAAM half 1; NHL period 1). Props: the player's box score stat, more than the line
  is an over win; a player with no box score line did not play and is a push (void). Postponed or not final: left pending.
"""
import difflib, glob, gzip, json, os, re, sys
from datetime import date as _date, datetime as _datetime, timedelta as _td
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'odds'))
ALIAS = {'GSW': 'GS', 'SAS': 'SA', 'NOP': 'NO', 'NYK': 'NY', 'UTA': 'UTAH', 'WAS': 'WSH', 'TBL': 'TB', 'SJS': 'SJ', 'LAK': 'LA',
         'NJD': 'NJ', 'LA': 'LAR', 'JAC': 'JAX', 'MON': 'MTL', 'CLB': 'CBJ', 'VGS': 'VGK', 'NAS': 'NSH', 'WIN': 'WPG', 'CAL': 'CGY'}
HALF1 = {'nba': [1, 2], 'nfl': [1, 2], 'fbs': [1, 2], 'ncaaw': [1, 2], 'ncaam': [1], 'nhl': [1]}
STAT = {  # pick stat -> (box score keys summed, groups to search or None for any)
    'points': (['points'], None), 'rebounds': (['rebounds'], None), 'assists': (['assists'], None),
    'threes': (['threePointFieldGoalsMade-threePointFieldGoalsAttempted'], None),
    'shots': (['shotsTotal'], None), 'goals': (['goals'], None), 'nhl_points': (['goals', 'assists'], None),
    'PASS': (['passingYards'], ['passing']), 'RUSH': (['rushingYards'], ['rushing']), 'REC': (['receivingYards'], ['receiving']),
    'passing yards': (['passingYards'], ['passing']), 'rushing yards': (['rushingYards'], ['rushing']),
    'receiving yards': (['receivingYards'], ['receiving']), 'passing touchdowns': (['passingTouchdowns'], ['passing']),
    'receptions': (['receptions'], ['receiving']), 'REC_N': (['receptions'], ['receiving'])}


def nrm(s): return re.sub(r'[^a-z0-9 ]', '', str(s).lower().replace('&', ' and ').replace('.', '')).strip()


def load(sport, day):
    d = ROOT / 'season' / 'data' / 'espn' / sport / day
    ev = {}
    for f in ('scoreboard_final.json.gz',):
        p = d / f
        if p.exists():
            for e in json.load(gzip.open(p))['events']:
                c = e['competitions'][0]
                ev[e['id']] = dict(id=e['id'], date=e.get('date') or c.get('date'), state=c['status']['type']['state'], completed=c['status']['type'].get('completed'),
                                   status=c['status']['type']['name'],
                                   t={x['homeAway']: dict(team=x['team'], score=int(x.get('score') or 0),
                                                          ls=[int(float(l.get('value', 0))) for l in x.get('linescores', [])]) for x in c['competitors']})
    box = json.load(gzip.open(d / 'boxscores.json.gz')) if (d / 'boxscores.json.gz').exists() else {}
    return ev, box


def tscore(code, team):
    """How well a card code or name fits an ESPN team (0 to 1)."""
    if not code: return 0
    ab = team.get('abbreviation', '')
    if ab in (code.upper(), ALIAS.get(code.upper())): return 1.0
    a = nrm(code)
    best = 0.0
    for c in (team.get('displayName'), team.get('location'), team.get('shortDisplayName'), team.get('name')):
        if c: best = max(best, difflib.SequenceMatcher(None, a, nrm(c)).ratio(), 0.97 if a == nrm(c) else 0)
    return best


def find_game(doc, ev):
    best = None
    for e in ev.values():
        s = tscore(doc.get('away'), e['t']['away']['team']) + tscore(doc.get('home'), e['t']['home']['team'])
        s2 = tscore(doc.get('away'), e['t']['home']['team']) + tscore(doc.get('home'), e['t']['away']['team'])   # neutral sites
        for v, flip in ((s, False), (s2, True)):
            if best is None or v > best[0]: best = (v, e, flip)
    return (best[1], best[2]) if best and best[0] >= 1.5 else (None, None)


def side_of(doc, e, flip, text):
    """'away' or 'home' (doc sense) for the team a side pick names."""
    for k in ('side', 'team'):
        v = doc.get(k)
        if v and v not in ('Over', 'Under', 'over', 'under'):
            if v == doc.get('away'): return 'away'
            if v == doc.get('home'): return 'home'
    t = nrm(text)
    sc = {}
    for s in ('away', 'home'):
        es = s if not flip else ('home' if s == 'away' else 'away')
        tm = e['t'][es]['team']; code = doc.get(s) or ''
        v = 2.0 if t.startswith(nrm(code) + ' ') else 0
        for c in (tm.get('displayName'), tm.get('location'), tm.get('name'), tm.get('shortDisplayName')):
            if c and nrm(c) and nrm(c) in t: v = max(v, 1 + len(nrm(c)) / 100)
        sc[s] = v
    if max(sc.values()) == 0 or sc['away'] == sc['home']: return None
    return max(sc, key=sc.get)


def num(text, signed=True):
    m = re.findall(r'([+-]\d+(?:\.\d+)?)' if signed else r'(\d+(?:\.\d+)?)', text.replace('½', '.5'))
    return float(m[-1]) if m else (0.0 if re.search(r'\bPK\b', text) else None)


def ou(text, doc):
    s = (doc.get('side') or '').lower()
    if s in ('over', 'under'): return s
    t = text.lower()
    if re.search(r'\bover\b|\bo\d', t) or 'anytime' in t or re.search(r'\d\+', t): return 'over'
    if re.search(r'\bunder\b|\bu\d', t): return 'under'
    return None


def cmp(val, line, way):
    if val == line: return 'push'
    return 'win' if (val > line) == (way == 'over') else 'loss'


def player_stat(box, name, team_code, keys, groups):
    found = None
    for tb in box.get('players', []):
        for g in tb.get('statistics', []):
            if groups and (g.get('name') or '').lower() not in groups: continue
            ks = g.get('keys') or []
            for a in g.get('athletes', []):
                nm = a.get('athlete', {}).get('displayName', '')
                if nrm(nm) == nrm(name) or nrm(nm).split()[-1:] == nrm(name).split()[-1:] and (len(nrm(name).split()) == 1 or nrm(nm)[0] == nrm(name)[0]):
                    if a.get('didNotPlay') or not a.get('stats'): return 'dnp', nm
                    tot = 0.0
                    for k in keys:
                        if k not in ks: continue
                        v = a['stats'][ks.index(k)]
                        v = v.split('-')[0] if '-' in str(v) and not str(v).startswith('-') else v
                        try: tot += float(v)
                        except ValueError: pass
                    found = (found[0] + tot if found and found[0] != 'dnp' else tot, nm)
    return found or ('dnp', name)


def grade(sport, doc, ev, box):
    e, flip = find_game(doc, ev)
    if not e: return None, 'game not in ESPN finals'
    if not e['completed'] or e['state'] != 'post': return None, f"not final ({e['status']})"
    A, H = (e['t']['home'], e['t']['away']) if flip else (e['t']['away'], e['t']['home'])
    fin = f"{doc.get('away')} {A['score']}, {doc.get('home')} {H['score']}"
    mk = (doc.get('market') or '').lower(); text = doc.get('pick') or ''
    per = None
    if re.match(r'^\s*(1h|1p|1st)', text.lower()) or mk.startswith('1st') or '1h' in mk.split():
        q = HALF1[sport]
        if not A['ls'] or len(A['ls']) < max(q): return None, 'no period scores'
        per = (sum(A['ls'][i - 1] for i in q), sum(H['ls'][i - 1] for i in q))
        fin += f" ({'1P' if sport == 'nhl' else '1H'} {per[0]}-{per[1]})"
    sa, sh = per if per else (A['score'], H['score'])
    if mk == 'prop' or (doc.get('player') and mk not in ('team total',)):
        st = doc.get('stat') or ''
        key = 'nhl_points' if sport == 'nhl' and st == 'points' else st
        if key == 'REC' and 'rec yds' not in text and 'receptions' in text: key = 'REC_N'
        if key not in STAT: return None, f'prop stat {st} not mapped'
        b = box.get(e['id'])
        if not b: return None, 'no box score'
        line = doc.get('line'); way = ou(text, doc)
        if line is None or not way: return None, 'prop line or side unclear'
        v, nm = player_stat(b, doc['player'], doc.get('team'), *STAT[key])
        if v == 'dnp': return ('push', f'{nm} did not play'), None
        return (cmp(v, float(line), way), f'{v:g} {st}'), None
    if 'team total' in mk:
        s = side_of(doc, e, flip, text); way = ou(text, doc); line = doc.get('line') or num(text, False)
        if not s or not way or line is None: return None, 'team total side unclear'
        return (cmp(sa if s == 'away' else sh, float(line), way), fin), None
    if 'total' in mk or re.match(r'^\s*(1h |1p )?(over|under)\b', text.lower()):
        way = ou(text, doc); line = num(text, False) if num(text, False) is not None else doc.get('line')
        if not way or line is None: return None, 'total line unclear'
        return (cmp(sa + sh, float(line), way), fin), None
    s = side_of(doc, e, flip, text)
    if not s: return None, 'side team unclear'
    m = (sa - sh) if s == 'away' else (sh - sa)
    if 'moneyline' in mk or text.strip().endswith(' ML') or 'moneyline' in text.lower():
        return ('win' if m > 0 else 'loss' if m < 0 else 'push', fin), None
    line = num(text)
    if line is None: return None, 'spread line unclear'
    v = m + line
    return ('win' if v > 0 else 'loss' if v < 0 else 'push', fin), None


def docs_in(path):
    p = Path(path)
    items = []
    if p.is_dir():
        for f in sorted(glob.glob(str(p / '**' / '*.json'), recursive=True)):
            x = json.load(open(f)); items += x if isinstance(x, list) else [dict(x, _file=f)]
    else:
        x = json.load(open(p)); items = x if isinstance(x, list) else x.get('docs') or x.get('results') or []
    out = []
    for x in items:
        d = x.get('data') or x.get('fields') or x
        i = x.get('id') or x.get('doc_id') or (Path(x['_file']).stem if '_file' in x else None)
        out.append((i, x.get('version'), d))
    return out


# ---------------- close step ----------------
ODDS_CACHE = {}
PROP_MK = {'points': 'player_points', 'nhl_points': 'player_points', 'rebounds': 'player_rebounds', 'assists': 'player_assists',
           'threes': 'player_threes', 'shots': 'player_shots_on_goal', 'goals': 'player_goals', 'saves': 'player_total_saves',
           'PASS': 'player_pass_yds', 'passing yards': 'player_pass_yds', 'RUSH': 'player_rush_yds', 'rushing yards': 'player_rush_yds',
           'REC': 'player_reception_yds', 'receiving yards': 'player_reception_yds', 'REC_N': 'player_receptions', 'receptions': 'player_receptions',
           'passing touchdowns': 'player_pass_tds', 'pra': 'player_points_rebounds_assists'}


def odds_for(sport, day):
    if (sport, day) not in ODDS_CACHE:
        try:
            import read as OR
            ODDS_CACHE[(sport, day)] = OR.build(sport, day) if (ROOT / 'odds' / 'data' / sport / day).is_dir() else {}
        except Exception as x:   # a bad file never stops grading
            print('odds read failed', sport, day, x); ODDS_CACHE[(sport, day)] = {}
    return ODDS_CACHE[(sport, day)]


def osim(name, team):
    a = nrm(name); best = 0.0
    for c in (team.get('displayName'), team.get('location'), team.get('shortDisplayName'), (team.get('location', '') + ' ' + team.get('name', ''))):
        if not c: continue
        b = nrm(c); r = difflib.SequenceMatcher(None, a, b).ratio()
        if a == b or a.startswith(b + ' '): r = max(r, 0.95)
        best = max(best, r)
    return best


def odds_event(sport, day, e):
    """The Odds API event for an ESPN event: (event, swapped) where swapped = Odds API home is ESPN away."""
    try: t = _datetime.fromisoformat(str(e.get('date')).replace('Z', '+00:00'))
    except Exception: t = None
    best = None
    d0 = _date.fromisoformat(day)
    for dd in (d0, d0 - _td(days=1), d0 + _td(days=1)):
        for g in odds_for(sport, dd.isoformat()).values():
            if not (g.get('close') or g.get('periods_close') or g.get('props_close')): continue
            if t is not None:
                try:
                    if abs((_datetime.fromisoformat(g['commence'].replace('Z', '+00:00')) - t).total_seconds()) > 3 * 3600: continue
                except Exception: pass
            A, H = e['t']['away']['team'], e['t']['home']['team']
            for sc, sw, mn in ((osim(g['away'], A) + osim(g['home'], H), False, min(osim(g['away'], A), osim(g['home'], H))),
                               (osim(g['away'], H) + osim(g['home'], A), True, min(osim(g['away'], H), osim(g['home'], A)))):
                if sc >= 1.2 and mn >= 0.6 and (best is None or sc > best[0]): best = (sc, g, sw)
        if best: break
    return (best[1], best[2]) if best else (None, None)


def implied(a):
    a = float(a); return 100 / (a + 100) if a > 0 else -a / (-a + 100)


def close_for(sport, doc, e, flip):
    """dict of close fields for a graded pick, or (None, why)."""
    g, sw = odds_event(sport, doc.get('date'), e)
    if not g: return None, 'no Odds API close for this game'
    def oside(s):   # doc side 'away'/'home' -> Odds API side
        es = s if not flip else ('home' if s == 'away' else 'away')
        return es if not sw else ('home' if es == 'away' else 'away')
    mk = (doc.get('market') or '').lower(); text = doc.get('pick') or ''
    per = re.match(r'^\s*(1h|1p|1st)', text.lower()) or mk.startswith('1st') or '1h' in mk.split()
    out = dict(close_source='The Odds API median of books, last close read before the start')
    try: pprice = float(str(doc.get('price')).replace('+', '')) if doc.get('price') not in (None, '') else None
    except ValueError: pprice = None
    if mk == 'prop' or (doc.get('player') and mk not in ('team total',)):
        st = doc.get('stat') or ''
        key = 'nhl_points' if sport == 'nhl' and st == 'points' else st
        if key == 'REC' and 'rec yds' not in text and 'receptions' in text: key = 'REC_N'
        om = PROP_MK.get(key) or PROP_MK.get(str(st).lower())
        P = g.get('props_close') or {}
        if not om or not P: return None, 'no closing props saved'
        sfx = lambda n: ' '.join(w for w in nrm(n).split() if w not in ('jr', 'sr', 'ii', 'iii', 'iv'))
        nm = sfx(doc.get('player') or ''); ent = None
        for exact in (True, False):   # exact name first, then last name plus first initial
            for pl, mks in P.items():
                q = sfx(pl)
                if om in mks and (q == nm if exact else (q.split()[-1:] == nm.split()[-1:] and q[:1] == nm[:1])): ent = mks[om]; break
            if ent: break
        if not ent or ent.get('line') is None: return None, f'player or market not in the closing props ({om})'
        way = ou(text, doc)
        out.update(close_line=ent['line'], close_price=ent.get(way), close_at=g.get('close_at'))
        ln = doc.get('line')
        if ln is not None and way: out.update(clv=round((float(ln) - ent['line']) if way == 'under' else (ent['line'] - float(ln)), 1), clv_unit='points')
        out['_kind'] = ('prop', way); return out, None
    L = (g.get('periods_close') or {}).get('p1' if sport == 'nhl' else 'h1') if per else g.get('close')
    if 'team total' in mk:
        TT = (g.get('periods_close') or {}).get('team_totals') or {}
        s = side_of(doc, e, flip, text); way = ou(text, doc)
        if not s or not way: return None, 'team total side unclear'
        x = TT.get(oside(s))
        if not x or x.get('line') is None: return None, 'no closing team total saved'
        out.update(close_line=x['line'], close_price=x.get(way + '_price'), close_at=g.get('close_at'))
        ln = doc.get('line') or num(text, False)
        if ln is not None: out.update(clv=round((float(ln) - x['line']) if way == 'under' else (x['line'] - float(ln)), 1), clv_unit='points')
        out['_kind'] = ('team', s, way); return out, None
    if not L: return None, ('no closing period lines saved' if per else 'no closing full game lines saved')
    out['close_at'] = g.get('close_at')
    if 'total' in mk or re.match(r'^\s*(1h |1p )?(over|under)\b', text.lower()):
        way = ou(text, doc)
        if L.get('total') is None or not way: return None, 'no closing total'
        out.update(close_line=L['total'], close_price=L.get(way + '_price'))
        ln = num(text, False) if num(text, False) is not None else doc.get('line')
        if ln is not None: out.update(clv=round((float(ln) - L['total']) if way == 'under' else (L['total'] - float(ln)), 1), clv_unit='points')
        out['_kind'] = ('total', way); return out, None
    s = side_of(doc, e, flip, text)
    if not s: return None, 'side team unclear'
    os_ = oside(s)
    if 'moneyline' in mk or text.strip().endswith(' ML') or 'moneyline' in text.lower():
        cp = L.get('ml_' + os_)
        if cp is None: return None, 'no closing moneyline'
        out.update(close_line=None, close_price=cp)
        if pprice is not None: out.update(clv=round((implied(cp) - implied(pprice)) * 100, 1), clv_unit='pct')
        out['_kind'] = ('ml', s); return out, None
    if L.get('spread_home') is None: return None, 'no closing spread'
    cl = L['spread_home'] if os_ == 'home' else -L['spread_home']
    out.update(close_line=cl, close_price=L.get('spread_home_price' if os_ == 'home' else 'spread_away_price'))
    ln = num(text)
    if ln is not None: out.update(clv=round(ln - cl, 1), clv_unit='points')
    out['_kind'] = ('spread', s); return out, None


def close_result(sport, doc, e, flip, box, c):
    """The pick graded at the close line (same final, same box score)."""
    k = c.get('_kind'); cl = c.get('close_line')
    if not k: return None
    if k[0] == 'ml': return grade(sport, doc, {e['id']: e}, box)[0][0] if grade(sport, doc, {e['id']: e}, box)[0] else None
    if cl is None: return None
    if k[0] == 'prop':
        r, _ = grade(sport, dict(doc, line=cl), {e['id']: e}, box)
        return r[0] if r else None
    A, H = (e['t']['home'], e['t']['away']) if flip else (e['t']['away'], e['t']['home'])
    text = (doc.get('pick') or '').lower(); mk = (doc.get('market') or '').lower()
    if re.match(r'^\s*(1h|1p|1st)', text) or mk.startswith('1st') or '1h' in mk.split():
        q = HALF1[sport]
        if not A['ls'] or len(A['ls']) < max(q): return None
        sa, sh = sum(A['ls'][i - 1] for i in q), sum(H['ls'][i - 1] for i in q)
    else: sa, sh = A['score'], H['score']
    if k[0] == 'team': return cmp(sa if k[1] == 'away' else sh, float(cl), k[2])
    if k[0] == 'total': return cmp(sa + sh, float(cl), k[1])
    m = (sa - sh) if k[1] == 'away' else (sh - sa); v = m + float(cl)
    return 'win' if v > 0 else 'loss' if v < 0 else 'push'


def add_close(sport, d, ev, box, up, noc, i):
    e, flip = find_game(d, ev)
    if not e: noc.append(dict(id=i, why='game not in ESPN finals')); return
    c, why = close_for(sport, d, e, flip)
    if not c: noc.append(dict(id=i, why=why)); return
    try: cr = close_result(sport, d, e, flip, box, c)
    except Exception as x: cr = None; print('close_result failed', i, x)
    c.pop('_kind', None)
    if cr: c['close_result'] = cr
    up.update({k: v for k, v in c.items() if v is not None or k == 'close_line'})


def main(sport, src, out, close=True, backfill=False, only_day=None):
    cache, ups, ung, noc = {}, [], [], []
    for i, ver, d in docs_in(src):
        if only_day and d.get('date') != only_day: continue
        res = d.get('result', 'pending')
        if res != 'pending' and not (backfill and close and res in ('win', 'loss', 'push') and d.get('close_line') is None and 'close_price' not in d): continue
        day = d.get('date')
        if day not in cache: cache[day] = load(sport, day)
        ev, box = cache[day]
        if not ev: ung.append(dict(id=i, why=f'no finals saved for {day}')); continue
        if res != 'pending':   # backfill: close fields only, result left as it is
            u = dict(id=i, version=ver, result=res, final=d.get('final'), backfill=True)
            if close: add_close(sport, d, ev, box, u, noc, i)
            if 'close_source' in u: ups.append(u)
            continue
        r, why = grade(sport, d, ev, box)
        if r:
            u = dict(id=i, version=ver, result=r[0], final=r[1])
            if close: add_close(sport, d, ev, box, u, noc, i)
            ups.append(u)
        else: ung.append(dict(id=i, why=why))
    Path(out).write_text(json.dumps(dict(updates=ups, ungraded=ung, no_close=noc), indent=1))
    G = [u for u in ups if not u.get('backfill')]
    w = sum(u['result'] == 'win' for u in G); l = sum(u['result'] == 'loss' for u in G); p = sum(u['result'] == 'push' for u in G)
    nc = sum('close_source' in u for u in ups)
    print(f'{sport}: graded {len(G)} ({w}-{l}-{p}), backfilled close {len(ups) - len(G)}, with close {nc}, no close {len(noc)}, ungraded {len(ung)} -> {out}')
    for u in ung[:15]: print('  ', u['id'], u['why'])


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    day = sys.argv[sys.argv.index('--day') + 1] if '--day' in sys.argv else None
    if day in a: a.remove(day)
    main(*a[:3], close='--no-close' not in sys.argv, backfill='--backfill-close' in sys.argv, only_day=day)
