"""Grade pending Season Cards picks from the ESPN finals saved by season/espn_pull.py (Season Cards, Nov 12 2026).

    python3 season/grade.py <sport> <pending.json | folder of pick docs> <out updates.json>

Input: the hub ledger's pending docs (ArtifactData query export: a list of {id, version, data} or a folder of doc files).
Output: {"updates": [{id, version, result, final}], "ungraded": [{id, why}]}; the run writes the updates with one
ArtifactData batch (update result and final, if_version = version). Rules, same as every sport skill:
  Moneyline: higher final score (shootout and overtime included). Spread / Puck line: team margin + line > 0 win, = 0 push.
  Total: final total vs line, equal is push. Team total: the team's points. 1st half / 1st period markets: period scores
  (NBA, NFL, FBS, NCAAW quarters 1+2; NCAAM half 1; NHL period 1). Props: the player's box score stat, more than the line
  is an over win; a player with no box score line did not play and is a push (void). Postponed or not final: left pending.
"""
import difflib, glob, gzip, json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
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
                ev[e['id']] = dict(id=e['id'], state=c['status']['type']['state'], completed=c['status']['type'].get('completed'),
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


def main(sport, src, out):
    cache, ups, ung = {}, [], []
    for i, ver, d in docs_in(src):
        if d.get('result', 'pending') != 'pending': continue
        day = d.get('date')
        if day not in cache: cache[day] = load(sport, day)
        ev, box = cache[day]
        if not ev: ung.append(dict(id=i, why=f'no finals saved for {day}')); continue
        r, why = grade(sport, d, ev, box)
        if r: ups.append(dict(id=i, version=ver, result=r[0], final=r[1]))
        else: ung.append(dict(id=i, why=why))
    Path(out).write_text(json.dumps(dict(updates=ups, ungraded=ung), indent=1))
    w = sum(u['result'] == 'win' for u in ups); l = sum(u['result'] == 'loss' for u in ups); p = sum(u['result'] == 'push' for u in ups)
    print(f'{sport}: graded {len(ups)} ({w}-{l}-{p}), ungraded {len(ung)} -> {out}')
    for u in ung[:15]: print('  ', u['id'], u['why'])


if __name__ == '__main__':
    main(*sys.argv[1:4])
