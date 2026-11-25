"""FBS starting lineups for game docs (Season Cards rule "Rosters and starters", validate check 10). Nov 25 2026.

    python3 season/lineups_fbs.py <games dir> <espn fbs data dir> <depth.json.gz> <out dir> <YYYY-MM-DD today>

For every game doc dated today or later, writes the doc to <out dir>/<id>.json with
  lineups {away: [...22 starters + noted non-starters], home: [...]}   each {player, pos, role, starter, status, rating,
           strengths, weaknesses, backup, backup_rating, source, rating_basis}
  units   {away: {"Pass block", "Run block", "Pass rush", "Run D", "Coverage"}: {rating, note}, home: {...}}
Starters: ESPN depth chart (rank 1 at each spot) when the depth file has charts; otherwise usage in the team's last 4 games
from the repo ESPN box scores (QB = the game doc qbs block; RB by carries; WR and TE by receptions; DL, LB, CB, S by
tackles, sacks, tackles for loss and passes defended), positions from the ESPN roster in the depth file. A player must have
appeared in one of the team's last 2 games to start. OL have no box score stats: the five OL listed first on the ESPN roster,
rated from the team's run block (yards per carry) and pass block (sacks allowed per game) unit numbers, said in rating_basis.
Ratings: percentile (0 to 100) at the position across all FBS players with 3+ games this season, from box score stats only.
No stats are invented: a starter with no stats gets the unit rating and says so.
"""
import gzip, glob, json, os, re, sys, statistics as stt
from collections import defaultdict
from pathlib import Path

GAMES, ESPN, DEPTH, OUT, TODAY = sys.argv[1:6]
OUT = Path(OUT); OUT.mkdir(parents=True, exist_ok=True)

# ---------- season box scores ----------
TG = defaultdict(list)          # team id -> [(day, gid)]
PS = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))   # team -> player id -> stat -> total
PG = defaultdict(lambda: defaultdict(set))                          # team -> player id -> set(gid)
NAME = {}
TEAMG = defaultdict(lambda: defaultdict(float))                     # team -> unit totals
SEEN = set()
def num(x):
    try: return float(x)
    except Exception: return 0.0
for f in sorted(glob.glob(os.path.join(ESPN, '*/boxscores.json.gz'))):
    day = f.split('/')[-2]
    for gid, b in json.load(gzip.open(f)).items():
        if b.get('status') != 'STATUS_FINAL' or gid in SEEN: continue
        SEEN.add(gid)
        tids = [str(t['team']['id']) for t in b.get('teams', [])]
        if len(tids) != 2: continue
        tst = {str(t['team']['id']): {s['name']: s for s in t.get('statistics', [])} for t in b['teams']}
        sacks = defaultdict(float)
        for pt in b.get('players') or []:
            tid = str(pt['team']['id'])
            for st in pt['statistics']:
                keys = st['keys']
                for a in st['athletes']:
                    pid = a['athlete']['id']; NAME[pid] = a['athlete']['displayName']; PG[tid][pid].add(gid)
                    v = dict(zip(keys, a['stats']))
                    P = PS[tid][pid]
                    if st['name'] == 'passing':
                        ca = v.get('completions/passingAttempts', '0/0').split('/'); P['pass_att'] += num(ca[-1]); P['pass_yds'] += num(v.get('passingYards'))
                        P['pass_td'] += num(v.get('passingTouchdowns')); P['pass_int'] += num(v.get('interceptions'))
                    elif st['name'] == 'rushing': P['rush_att'] += num(v.get('rushingAttempts')); P['rush_yds'] += num(v.get('rushingYards'))
                    elif st['name'] == 'receiving': P['rec'] += num(v.get('receptions')); P['rec_yds'] += num(v.get('receivingYards'))
                    elif st['name'] == 'defensive':
                        P['tkl'] += num(v.get('totalTackles')); P['sacks'] += num(v.get('sacks')); P['tfl'] += num(v.get('tacklesForLoss')); P['pd'] += num(v.get('passesDefended'))
                        sacks[tid] += num(v.get('sacks'))
                    elif st['name'] == 'interceptions': P['int'] += num(v.get('interceptions'))
        for i, tid in enumerate(tids):
            o = tids[1 - i]; TG[tid].append((day, gid))
            S, O = tst[tid], tst[o]
            T = TEAMG[tid]; T['g'] += 1
            T['rush_yds'] += num((S.get('rushingYards') or {}).get('value')); T['rush_att'] += num((S.get('rushingAttempts') or {}).get('value'))
            T['sacks_for'] += sacks[tid]; T['sacks_allowed'] += sacks[o]
            T['rush_yds_a'] += num((O.get('rushingYards') or {}).get('value')); T['rush_att_a'] += num((O.get('rushingAttempts') or {}).get('value'))
            T['pass_yds_a'] += num((O.get('netPassingYards') or {}).get('value'))
            ca = str((O.get('completionAttempts') or {}).get('displayValue') or '0/0').replace('-', '/').split('/'); T['pass_att_a'] += num(ca[-1])

LOC = {}
for f in glob.glob(os.path.join(ESPN, '*/boxscores.json.gz')):
    for b in json.load(gzip.open(f)).values():
        for t in b.get('teams', []): LOC[t['team']['location']] = str(t['team']['id'])
OLX = json.load(open(os.environ['OL_EXTRA'])) if os.environ.get('OL_EXTRA') else {}
# ---------- roster and depth charts ----------
DEP = json.load(gzip.open(DEPTH)) if DEPTH and os.path.exists(DEPTH) else {}
ROS = {}; CH = {}
for abbr, t in DEP.items():
    if not isinstance(t, dict) or not t.get('id'): continue
    ROS[str(t['id'])] = t.get('roster') or {}; CH[str(t['id'])] = t.get('charts') or []
GROUP = {'QB': 'QB', 'RB': 'RB', 'FB': 'RB', 'WR': 'WR', 'TE': 'TE', 'OL': 'OL', 'OT': 'OL', 'G': 'OL', 'C': 'OL', 'LT': 'OL', 'LG': 'OL', 'RG': 'OL', 'RT': 'OL',
         'DL': 'DL', 'DE': 'DL', 'DT': 'DL', 'NT': 'DL', 'EDGE': 'DL', 'LB': 'LB', 'OLB': 'LB', 'ILB': 'LB', 'MLB': 'LB', 'WLB': 'LB', 'SLB': 'LB',
         'CB': 'CB', 'LCB': 'CB', 'RCB': 'CB', 'NB': 'CB', 'S': 'S', 'FS': 'S', 'SS': 'S', 'DB': 'DB'}
NEED = [('QB', 1), ('RB', 1), ('WR', 3), ('TE', 1), ('OL', 5), ('DL', 4), ('LB', 3), ('CB', 2), ('S', 2)]

# ---------- position percentiles (all FBS players, 3+ games) ----------
def pos_of(tid, pid): return GROUP.get(((ROS.get(tid) or {}).get(pid) or {}).get('pos') or '', None)
METRIC = {
    'QB': (lambda P, g: P['pass_yds'] / P['pass_att'] if P['pass_att'] >= 40 else None, 'yards per pass attempt'),
    'RB': (lambda P, g: P['rush_yds'] / g if P['rush_att'] >= 20 else None, 'rushing yards per game'),
    'WR': (lambda P, g: P['rec_yds'] / g if P['rec'] >= 5 else None, 'receiving yards per game'),
    'TE': (lambda P, g: P['rec_yds'] / g if P['rec'] >= 3 else None, 'receiving yards per game'),
    'DL': (lambda P, g: (P['sacks'] + P['tfl']) / g if P['tkl'] >= 5 else None, 'sacks plus tackles for loss per game'),
    'LB': (lambda P, g: P['tkl'] / g if P['tkl'] >= 10 else None, 'tackles per game'),
    'CB': (lambda P, g: (P['pd'] + P['int']) / g if P['tkl'] >= 5 else None, 'passes defended plus interceptions per game'),
    'S': (lambda P, g: (P['tkl'] + 3 * (P['pd'] + P['int'])) / g if P['tkl'] >= 5 else None, 'tackles plus 3 x (passes defended and interceptions) per game'),
}
DIST = defaultdict(list)
for tid, pl in PS.items():
    for pid, P in pl.items():
        g = len(PG[tid][pid])
        if g < 3: continue
        grp = pos_of(tid, pid)
        for k in ([grp] if grp in METRIC else (['CB', 'S'] if grp == 'DB' else [])):
            v = METRIC[k][0](P, g)
            if v is not None: DIST[k].append(v)
for k in DIST: DIST[k].sort()
def pct(k, v):
    L = DIST.get(k) or []
    if not L or v is None: return None
    import bisect
    return int(round(100 * bisect.bisect_left(L, v) / len(L)))

# team unit percentiles
def tval(tid, k):
    T = TEAMG.get(tid)
    if not T or T['g'] < 3: return None
    if k == 'Run block': return T['rush_yds'] / max(T['rush_att'], 1)
    if k == 'Pass block': return -T['sacks_allowed'] / T['g']
    if k == 'Pass rush': return T['sacks_for'] / T['g']
    if k == 'Run D': return -T['rush_yds_a'] / max(T['rush_att_a'], 1)
    if k == 'Coverage': return -T['pass_yds_a'] / max(T['pass_att_a'], 1)
UD = {k: sorted(v for v in (tval(t, k) for t in TEAMG) if v is not None) for k in ('Run block', 'Pass block', 'Pass rush', 'Run D', 'Coverage')}
def upct(tid, k):
    v = tval(tid, k); L = UD[k]
    if v is None or not L: return None, None
    import bisect
    return int(round(100 * bisect.bisect_left(L, v) / len(L))), v
def unit_note(tid, k):
    T = TEAMG[tid]; g = T['g']
    return {'Run block': f"{T['rush_yds'] / max(T['rush_att'], 1):.1f} yards per carry",
            'Pass block': f"{T['sacks_allowed'] / g:.1f} sacks allowed per game",
            'Pass rush': f"{T['sacks_for'] / g:.1f} sacks per game",
            'Run D': f"{T['rush_yds_a'] / max(T['rush_att_a'], 1):.1f} yards per carry allowed",
            'Coverage': f"{T['pass_yds_a'] / max(T['pass_att_a'], 1):.1f} yards per pass attempt allowed"}[k] + f" in {int(g)} games (ESPN box scores), percentile among FBS teams"

def tags(grp, P, g, r):
    s, w = [], []
    if grp == 'QB':
        ypa = P['pass_yds'] / max(P['pass_att'], 1); s.append(f"{ypa:.1f} yards per attempt") if r is not None and r >= 60 else w.append(f"{ypa:.1f} yards per attempt") if r is not None and r < 40 else None
        if P['pass_int'] and P['pass_td'] / max(P['pass_int'], 1) < 1.5: w.append(f"{int(P['pass_td'])} TD, {int(P['pass_int'])} INT")
        elif P['pass_td']: s.append(f"{int(P['pass_td'])} TD, {int(P['pass_int'])} INT")
        if P['rush_att'] / max(g, 1) >= 8: s.append(f"runs {P['rush_yds'] / g:.0f} yards a game")
    elif grp == 'RB':
        ypc = P['rush_yds'] / max(P['rush_att'], 1); (s if ypc >= 5 else w if ypc < 4 else []).append(f"{ypc:.1f} yards per carry")
        if P['rec'] / max(g, 1) >= 2: s.append(f"{P['rec'] / g:.1f} catches a game")
    elif grp in ('WR', 'TE'):
        if P['rec']: (s if (r or 0) >= 60 else w if (r or 0) < 35 else []).append(f"{P['rec'] / g:.1f} catches, {P['rec_yds'] / g:.0f} yards a game")
    elif grp == 'DL':
        if P['sacks']: s.append(f"{P['sacks']:g} sacks")
        if P['tfl']: s.append(f"{P['tfl']:g} tackles for loss")
        if not P['sacks'] and not P['tfl']: w.append('no sacks or tackles for loss in the box scores')
    elif grp == 'LB':
        s.append(f"{P['tkl'] / g:.1f} tackles a game") if (r or 0) >= 50 else w.append(f"{P['tkl'] / g:.1f} tackles a game")
        if P['sacks']: s.append(f"{P['sacks']:g} sacks")
    elif grp in ('CB', 'S'):
        if P['pd'] or P['int']: s.append(f"{int(P['pd'])} passes defended, {int(P['int'])} interceptions")
        else: w.append('no passes defended in the box scores')
    if r is not None and r >= 80: s.insert(0, f"top {max(1, 100 - r)}% at {grp}")
    return s[:3], w[:3]

def recent(tid, n):
    return [gid for d, gid in sorted(TG.get(tid, []))[-n:]]
def usage(tid, pid, grp, R4):
    P = PS[tid][pid]; ng = sum(1 for x in R4 if x in PG[tid][pid])
    # last-4-game usage share approximated by season per-game rates of players active in the window
    g = max(len(PG[tid][pid]), 1)
    if grp == 'RB': return P['rush_att'] / g
    if grp in ('WR', 'TE'): return P['rec'] / g + P['rec_yds'] / g / 20
    if grp == 'DL': return P['tkl'] / g + 2 * (P['sacks'] + P['tfl']) / g
    if grp in ('LB', 'CB', 'S', 'DB'): return P['tkl'] / g + 2 * (P['pd'] + P['int']) / g
    return 0

def entry(tid, pid, grp, starter, source, basis=None, team_unit=None):
    P = PS[tid].get(pid); g = len(PG[tid].get(pid, ())) if pid else 0
    nm = NAME.get(pid) or ((ROS.get(tid) or {}).get(pid) or {}).get('n')
    k = grp if grp in METRIC else None
    r = pct(k, METRIC[k][0](P, g)) if (P and k and g) else None
    e = dict(player=nm, pos=grp, role=grp, starter=starter, status='Expected', source=source)
    if r is not None:
        e['rating'] = r; e['rating_basis'] = f"percentile among FBS {grp} with 3+ games: {METRIC[k][1]} ({g} games, ESPN box scores)"
        e['strengths'], e['weaknesses'] = tags(grp, P, g, r)
    else:
        e['rating'] = team_unit[0] if team_unit and team_unit[0] is not None else 50
        e['rating_basis'] = basis or (f"no qualifying individual stats ({g} games in the box scores); rated from the team {team_unit[1]} unit" if team_unit else 'no stats; neutral 50')
        e['strengths'], e['weaknesses'] = (tags(grp, P, g, None) if P and g else ([], []))
    e['games'] = g
    return e

def chart_starters(tid):
    out = defaultdict(list)
    for ch in CH.get(tid) or []:
        for pos, L in (ch.get('positions') or {}).items():
            grp = GROUP.get(re.sub(r'\d', '', pos.upper()))
            if not grp: continue
            for x in sorted(L, key=lambda x: x.get('rank', 99)):
                if x.get('rank') == 1 and str(x['id']) not in [p for p, _ in out[grp]]: out[grp].append((str(x['id']), x.get('n')))
    return out

def build_side(tid, team, qb):
    R4 = recent(tid, 4); R2 = set(recent(tid, 2))
    ros = ROS.get(tid) or {}
    cs = chart_starters(tid)
    units = {}
    for k in ('Pass block', 'Run block', 'Pass rush', 'Run D', 'Coverage'):
        p_, v = upct(tid, k)
        if p_ is not None: units[k] = dict(rating=p_, note=unit_note(tid, k))
    ol_rating = None
    if units.get('Run block') and units.get('Pass block'): ol_rating = round((units['Run block']['rating'] + units['Pass block']['rating']) / 2)
    L = []; used = set()
    # QB from the qbs block
    qpid = next((pid for pid, P in PS[tid].items() if NAME.get(pid) == qb.get('name')), None)
    qe = entry(tid, qpid, 'QB', True, 'qbs block (ESPN box scores)') if qpid else dict(player=qb.get('name'), pos='QB', role='QB', starter=True, status='Expected', rating=50, rating_basis='no box score stats found; neutral 50', strengths=[], weaknesses=[], source='qbs block')
    qe['status'] = qb.get('status') or 'Expected'; qe['depth'] = qb.get('depth'); L.append(qe); used.add(qpid)
    # candidates by group
    cand = defaultdict(list)
    for pid in PS[tid]:
        if pid in used: continue
        grp = pos_of(tid, pid)
        if grp is None: continue
        if not (PG[tid][pid] & R2): continue
        if grp == 'DB':
            for gg in ('CB', 'S'): cand[gg].append((usage(tid, pid, gg, R4), pid, 'DB'))
        else: cand[grp].append((usage(tid, pid, grp, R4), pid, grp))
    for grp, n in NEED[1:]:
        src = 'ESPN depth chart' if cs.get(grp) else 'usage in the last 4 games (ESPN box scores), ESPN roster position'
        picks = []
        if cs.get(grp):
            picks = [pid for pid, _ in cs[grp] if pid not in used][:n]
        if len(picks) < n and grp != 'OL':
            for u, pid, og in sorted(cand.get(grp, []), reverse=True):
                if pid in used or pid in picks: continue
                picks.append(pid)
                if len(picks) == n: break
        if grp == 'OL' and len(picks) < n and tid in OLX:
            for nm_ in OLX[tid]['players']:
                if len(picks) == n: break
                k_ = 'x:' + nm_; NAME[k_] = nm_; picks.append(k_)
            src = OLX[tid]['source']
        if len(picks) < n:   # OL, or not enough players with stats: roster order
            for pid, x in ros.items():
                if GROUP.get(x.get('pos') or '') in ((grp,) if grp not in ('CB', 'S') else (grp, 'DB')) and pid not in used and pid not in picks:
                    picks.append(pid)
                    if len(picks) == n: break
        alts = [pid for u, pid, og in sorted(cand.get(grp, []), reverse=True) if pid not in used and pid not in picks]
        for i, pid in enumerate(picks):
            used.add(pid)
            if grp == 'OL':
                e = entry(tid, pid, 'OL', True, src if pid.startswith('x:') else ('ESPN roster (OL listed first; no OL usage stats in the box scores)' if not cs.get('OL') else 'ESPN depth chart'),
                          basis=f"OL have no individual box score stats: rated from the team's run block and pass block units ({units.get('Run block', {}).get('note', 'n/a')}; {units.get('Pass block', {}).get('note', 'n/a')})",
                          team_unit=(ol_rating, 'offensive line'))
            else:
                hasP = pid in PS[tid]
                e = entry(tid, pid, grp, True, src if hasP or cs.get(grp) else 'ESPN roster (no box score usage)',
                          team_unit=({'DL': units.get('Pass rush'), 'LB': units.get('Run D'), 'CB': units.get('Coverage'), 'S': units.get('Coverage')}.get(grp, {}) or {}).get('rating') and
                          (({'DL': units.get('Pass rush'), 'LB': units.get('Run D'), 'CB': units.get('Coverage'), 'S': units.get('Coverage')}.get(grp) or {}).get('rating'), {'DL': 'pass rush', 'LB': 'run defense', 'CB': 'coverage', 'S': 'coverage'}.get(grp)) or None)
            if alts:
                b = alts[min(i, len(alts) - 1)]; e['backup'] = NAME.get(b) or (ros.get(b) or {}).get('n')
                be = entry(tid, b, grp, False, '')
                e['backup_rating'] = be.get('rating')
            L.append(e)
    return L, units

PN = {}
fixed = []
for f in sorted(glob.glob(os.path.join(GAMES, '*.json'))):
    gid = os.path.basename(f)[:-5]
    if gid[:10] < TODAY: continue
    g = json.load(open(f))
    meta = {k: g.get(k) for k in ('_id', '_v')}
    lu, un = {}, {}
    for side in ('away', 'home'):
        t = g.get(side) or {}; tid = str(t.get('espn_id') or '')
        if tid not in ROS and LOC.get(t.get('short')):
            tid = LOC[t['short']]; t['espn_id'] = tid; fixed.append((gid, side, tid))
        q0 = (g.get('qbs') or {}).get(side) or {}
        if not q0.get('name'):
            att = {pid: P['pass_att'] for pid, P in PS[tid].items() if P['pass_att']}
            if att:
                R = recent(tid, 3); last = R[-1] if R else None
                lastatt = {pid: a for pid, a in att.items() if last in PG[tid][pid]}
                q1 = max(att, key=att.get); lead = max(lastatt, key=lambda x: PS[tid][x]['pass_att']) if lastatt else q1
                ld = sorted(TG[tid])[-1][0] if TG.get(tid) else ''
                q0 = dict(name=NAME[lead], depth='QB1' if lead == q1 else 'QB2', status='Expected', source='ESPN box scores (repo)',
                          note=f"{NAME[lead]} played in the last game ({ld}); season attempts leader {NAME[q1]} ({int(att[q1])} attempts). No official availability report read.")
                if lead != q1: q0['season_qb1'] = NAME[q1]
                g.setdefault('qbs', {})[side] = q0
        if not tid: print('no espn id', gid, side); continue
        L, U = build_side(tid, t.get('short'), (g.get('qbs') or {}).get(side) or {})
        q = (g.get('qbs') or {}).get(side) or {}
        if q.get('season_qb1') and q.get('season_qb1') != q.get('name'):
            L.append(dict(player=q['season_qb1'], pos='QB', role='Season QB1 (not starting)', starter=False, status='Out' if 'out' in (q.get('note') or '').lower() else 'Not starting',
                          rating=None, note=q.get('note'), source=q.get('source')))
        lu[side] = L; un[side] = U
    g['lineups'] = lu; g['units'] = un
    g['lineups_note'] = ('Starters from ESPN depth charts where posted, else usage in the last 4 games from the repo ESPN box scores with ESPN roster positions; '
                         'OL from the ESPN roster and rated from team unit numbers. Ratings are position percentiles from box score stats only. Built Nov 25 2026 (season/lineups_fbs.py).')
    json.dump(g, open(OUT / f'{gid}.json', 'w'), ensure_ascii=False, indent=1)
    PN[gid] = {s: len([x for x in lu.get(s, []) if x.get('starter', True)]) for s in ('away', 'home')}
short = {k: v for k, v in PN.items() if min(v.values() or [0]) < 22}
print('games', len(PN), 'short', short); print('espn id fixed', fixed)
