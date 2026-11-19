"""CFB injuries (Trina, Nov 9 2026: injuries must be captured and used by the model). Replaces the stale Covers report.
Usage: python3 inj_merge.py inj_raw.txt [qb_usage.txt]   -> injuries.json (keeps _prop_hold entries added by hand)

inj_raw.txt, one line per report item read in Chrome this run (any FBS position):
    team|player|pos|status|source|date
  status: OUT, DOUBTFUL, QUESTIONABLE, PROBABLE, GTD (game-time decision), OUT1H (out for the first half), AVAILABLE
  source, in order of trust:
    official  = the conference availability report (Big Ten bigten.org, SEC secsports.com, ACC theacc.com, Big 12 big12sports.com,
                Mountain West themw.com, MAC getsomemaction.com; conference games; midweek reports, then the gameday report about
                90 to 120 minutes before kickoff; the latest report wins)
    team      = the school's own release or coach's statement
    news      = RotoBaller college football player news or a beat writer, with the date
    props     = texas222 posts (or stops posting) the player's props today
qb_usage.txt (ESPN box scores, from the existing pull): team|qb1_by_attempts|qb1_share|last_game_passer
A status is confirmed when it comes from an official report, or when two different sources agree. Anything else is shown as
unconfirmed (status kept, confirmed false). QB entries carry qb1 (season leader in attempts with a 60%+ share) and role_change
(QB1 out or unconfirmed, or a different passer led the last game), which model.py uses to hold that team's passing and receiving props.
Scoring: the opposing-QB1-out side signal stays at 0 points (signals.json qb_out: tested on 2,329 games, no edge at the close,
the market prices a known absence)."""
import json, sys
from pathlib import Path
from collections import defaultdict

D = Path(__file__).parent
RANK = {'official': 3, 'team': 2, 'news': 1, 'props': 1}
raw = [l.strip().split('|') for l in Path(sys.argv[1]).read_text().splitlines() if l.strip() and not l.startswith('#')]
use = {}
if len(sys.argv) > 2 and Path(sys.argv[2]).exists():
    for l in Path(sys.argv[2]).read_text().splitlines():
        f = l.strip().split('|')
        if len(f) >= 4: use[f[0]] = dict(qb1=f[1], share=float(f[2] or 0), last=f[3])
old = json.load(open(D / 'injuries.json')) if (D / 'injuries.json').exists() else {}
GP = {}   # Nov 11: qb_gp.txt team|player|share of team attempts in the games he played
if (D / 'qb_gp.txt').exists():
    for l in (D / 'qb_gp.txt').read_text().splitlines():
        f = l.strip().split('|')
        if len(f) == 3: GP[(f[0], f[1])] = float(f[2])
by = defaultdict(list)
for f in raw:
    if len(f) < 6: continue
    by[(f[0], f[1])].append(dict(pos=f[2], status=f[3].upper(), source=f[4].lower(), date=f[5]))
out = {'_read': None, '_prop_hold': old.get('_prop_hold', {})}
latest = ''
for (team, player), items in by.items():
    items.sort(key=lambda x: (x['date'], RANK.get(x['source'], 0)))
    off = [x for x in items if x['source'] == 'official']
    top = off[-1] if off else items[-1]
    agree = len({x['source'] for x in items if x['status'] == top['status']}) >= 2
    conf = bool(off) or agree
    u = use.get(team, {})
    qb1 = top['pos'] == 'QB' and u.get('qb1') == player and u.get('share', 0) >= 0.6
    # Nov 11 2026 (Trina, A18): with no official report (e.g. the MAC), a QB counts as confirmed when he is the season QB1
    # (depth chart proxy: most attempts; ESPN has no college depth charts), has 90%+ of his team's attempts in the games he played,
    # and the book posted his props today. Otherwise Expected, and that team's passing and receiving props are held.
    gp = GP.get((team, player))
    a18 = (not conf and top['pos'] == 'QB' and top['status'] == 'AVAILABLE' and u.get('qb1') == player and gp is not None and gp >= 0.9
           and any(x['source'] == 'props' for x in items))
    if a18: conf = True
    e = dict(player=player, pos=top['pos'], status=top['status'], confirmed=conf, source=top['source'], date=top['date'], qb1=qb1 or a18,
             note=('; '.join(f"{x['source']} {x['status']} ({x['date']})" for x in items)))
    if top['pos'] == 'QB':
        e['role_change'] = False if a18 else (bool(qb1 and (top['status'] != 'AVAILABLE' or not conf)) or bool(u.get('last') and u.get('qb1') and u['last'] != u['qb1'])
                                              or (not conf and top['source'] == 'props'))   # A18: an Expected QB holds the team's passing and receiving props
        if a18: e['note'] += f"; A18: season QB1 with {round(100 * gp)}% of attempts in the games he played and props posted, so confirmed"
        e['qb_status'] = 'Confirmed' if conf and top['status'] == 'AVAILABLE' else ('Questionable' if top['status'] in ('QUESTIONABLE', 'GTD', 'DOUBTFUL') else 'Expected')
        if u: e['note'] += f"; ESPN: QB1 by attempts {u.get('qb1')} ({round(100 * u.get('share', 0))}%), last game passer {u.get('last')}"
    out.setdefault(team, []).append(e); latest = max(latest, top['date'])
# a QB change with no report item still holds that team's props
for team, u in use.items():
    if u.get('last') and u.get('qb1') and u['last'] != u['qb1'] and not any(x['pos'] == 'QB' for x in out.get(team, [])):
        out.setdefault(team, []).append(dict(player=u['qb1'], pos='QB', status='UNREPORTED', confirmed=False, source='espn', date=latest, qb1=True,
                                             role_change=True, note=f"ESPN: {u['last']} led the last game, not QB1 {u['qb1']}; no report found"))
out['_read'] = f"inj_merge.py: {len(raw)} report items, latest {latest}. Confirmed = official conference report or two sources agree."
json.dump(out, open(D / 'injuries.json', 'w'), indent=1)
n = sum(len(v) for k, v in out.items() if not k.startswith('_'))
print(n, 'players;', sum(1 for k, v in out.items() if not k.startswith('_') for x in v if x['confirmed']), 'confirmed')
