"""Season Cards data checks (Trina, Nov 11). Run after every Run All Cards, after the tier rebuild, before publishing.
Usage: python3 validate.py <dl_dir> <today YYYY-MM-DD>
<dl_dir> holds an ArtifactData out_dir download of meta, sports/<sport>/{picks,picks_bg,games,backtest}.
Prints every problem; exit code 1 when any FAIL is found. A FAIL must be fixed (or listed in the run reply) before publishing.
Checks
 1. Tier coverage: every graded backtest doc of a game rule gets a tier; untiered docs FAIL (the Nov 10 gap).
 2. Tier totals: the rule's tier records add up to its every game backtest record (wins, losses, units).
 3. Ungraded: a card or would-be pick dated before yesterday still pending FAILS (yesterday may wait for the run).
 4. Today's picks: tier, rule known to meta, reasons, experts and a game doc.
 5. Opposing picks: two card picks in one game on opposite teams or opposite sides of a total FAIL.
 6. Counts: meta.counts equals the documents in the hub (what the page compares against).
 7. Preview (Nov 11): preview docs carry as_of, game_id with a game doc, and no opposing picks in one game per as_of; a change entry carries a reason.
 9. Lineups (Nov 11): every prop pick today has its player on the game doc lineups; every prop pick today carries a matchup.
10. Full lineups (Nov 11): every game from today on lists a full starting lineup per team (NFL, FBS 22 starters; NBA, NCAAM, NCAAW 5; NHL 18 skaters and a goalie), each starter rated, each starter out with a backup named, and model.adjustments when any starter is out.
 8. Football QBs (Nov 11): every NFL and FBS game doc from today on carries qbs.away and qbs.home with name and depth (QB1, QB2, QB3).
"""
import json, glob, os, sys, re, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DL, TODAY = sys.argv[1], sys.argv[2]
SPORTS = ['nba', 'nhl', 'nfl', 'ncaam', 'ncaaw', 'fbs']
fails, warns = [], []
def load(path):
    out = []
    for f in glob.glob(os.path.join(DL, path, '*.json')):
        d = json.load(open(f)); d = d.get('data', d) if isinstance(d, dict) and set(d) <= {'data', 'id', 'version'} else d
        d['__id'] = os.path.basename(f)[:-5]; out.append(d)
    return out
def sc(l): return 'Strong' if l >= 4 else ('Solid' if l >= 2 else 'Lean')
def tier_bt(s, b):
    i = b.get('inputs') or {}; m = b.get('market')
    if s == 'nba':
        if m == 'Total':
            tc = i.get('total_scores') or {}; return sc((tc.get('U', 0) or 0) - (tc.get('O', 0) or 0))
        ss = i.get('side_scores') or {}; side = b['away'] if str(b.get('pick', '')).startswith(b['away']) else b['home']
        oth = b['home'] if side == b['away'] else b['away']; return sc((ss.get(side, 0) or 0) - (ss.get(oth, 0) or 0))
    if s == 'fbs' and i.get('lead') is not None: return sc(float(i['lead']))
    if s in ('ncaam', 'ncaaw'):
        g = i.get('edge') if i.get('edge') is not None else i.get('gap_vs_open')
        if g is not None: return sc(min(4, math.floor(abs(float(g)) / 2)))
        return sc(float(i['lead'])) if i.get('lead') is not None else None
    t = {'Thin': 'Lean'}.get(b.get('tier'), b.get('tier'))
    if t in ('Strong', 'Solid', 'Lean'): return t
    pk = str(b.get('pick', ''))
    if m == 'Total' and i.get('total_over') is not None:
        d = float(i.get('total_over') or 0) - float(i.get('total_under') or 0); return sc(d if pk.startswith('Over') else -d)
    if i.get('signal_lead') is not None and i.get('signal_team'):
        return sc(float(i['signal_lead']) if pk.startswith(str(i['signal_team'])) else -float(i['signal_lead']))
    return None
def units(d):
    if d.get('units') is not None: return float(d['units'])
    r = d.get('result'); pr = d.get('price')
    try: pr = float(pr)
    except Exception: pr = None
    if r == 'win': return 1 if pr is None else (pr / 100 if pr > 0 else 100 / -pr)
    return -1 if r == 'loss' else 0
def team(p): return re.sub(r'\s+(ML|moneyline|[+-]\d.*)$', '', str(p.get('pick', '')), flags=re.I).strip()
from datetime import date, timedelta
yday = (date.fromisoformat(TODAY) - timedelta(days=1)).isoformat()
for s in SPORTS:
    mp = os.path.join(DL, 'meta', s + '.json')
    if not os.path.exists(mp): warns.append(f'{s}: no meta downloaded'); continue
    m = json.load(open(mp)); m = m.get('data', m)
    picks, games, bt = load(f'sports/{s}/picks'), load(f'sports/{s}/games'), load(f'sports/{s}/backtest')
    pv = load(f'sports/{s}/preview')
    bg = load('sports/nfl/picks_bg') if s == 'nfl' else []
    keys = {}
    for r in m.get('rules', []):
        for k in (r.get('keys') or [r.get('key')]): keys[k] = r
    # 1 and 2
    for r in m.get('rules', []):
        if r.get('market') == 'Prop': continue
        ks = r.get('keys') or [r['key']]
        L = [b for b in bt if b.get('rule_key') in ks and b.get('result') in ('win', 'loss', 'push') and b.get('first_in_rule_order') is not False]
        if not L: continue
        un = [b for b in L if tier_bt(s, b) not in ('Strong', 'Solid', 'Lean')]
        if un: fails.append(f'{s} {r["key"]}: {len(un)} of {len(L)} backtest docs have no tier')
        T = r.get('tiers') or {}
        if not T: fails.append(f'{s} {r["key"]}: no tier records in meta'); continue
        tw = sum((v.get('season') or {}).get('w', 0) for v in T.values()); tl = sum((v.get('season') or {}).get('l', 0) for v in T.values())
        tu = round(sum((v.get('season') or {}).get('u', 0) for v in T.values()), 2)
        w = sum(b['result'] == 'win' for b in L); l = sum(b['result'] == 'loss' for b in L); u = round(sum(units(b) for b in L), 2)
        if (tw, tl) != (w, l) or abs(tu - u) > 0.05: fails.append(f'{s} {r["key"]}: tiers {tw}-{tl} {tu:+.2f}u do not add up to the backtest {w}-{l} {u:+.2f}u (rebuild tiers)')
    # 3
    old = [p['__id'] for p in picks + bg if p.get('result') == 'pending' and str(p.get('date', '')) < yday]
    if old: fails.append(f'{s}: {len(old)} picks before {yday} still pending, e.g. {old[:3]}')
    # 4
    gids = {g['__id'] for g in games}
    for p in picks:
        if p.get('date') != TODAY: continue
        pid = p['__id']
        if p.get('market') != 'Prop':
            if not p.get('tier'): fails.append(f'{s} {pid}: no tier')
            if p.get('rule') and p['rule'] not in keys and not any(p['rule'] in (r.get('keys') or []) for r in m.get('rules', [])): warns.append(f'{s} {pid}: rule {p["rule"]} not in meta')
        if 'reasons' not in p: fails.append(f'{s} {pid}: no reasons')
        if 'experts' not in p: warns.append(f'{s} {pid}: no experts field')
        gid = '_'.join(pid.split('_')[:2])
        if gid not in gids: fails.append(f'{s} {pid}: no game doc {gid}')
    # 5
    byg = collections.defaultdict(list)
    for p in picks:
        if p.get('date') == TODAY and not p.get('shadow') and p.get('market') != 'Prop': byg[(p.get('date'), p.get('game'))].append(p)
    for k, L in byg.items():
        sides = {team(p) for p in L if p.get('market') != 'Total'}; tots = {str(p.get('pick', '')).split()[0] for p in L if p.get('market') == 'Total'}
        if len(sides) > 1 or len(tots) > 1: fails.append(f'{s} {k[1]}: opposing card picks {[p["pick"] for p in L]}')
    # 7
    gids_all = {g['__id'] for g in games}
    lastpv = max([str(p.get('as_of', '')) for p in pv] or [''])
    pg = collections.defaultdict(list)
    for p in pv:
        if not p.get('as_of') or not p.get('game_id'): fails.append(f'{s} preview {p["__id"]}: missing as_of or game_id'); continue
        if p['game_id'] not in gids_all: fails.append(f'{s} preview {p["__id"]}: no game doc {p["game_id"]}')
        if p.get('change') and not p['change'].get('reason'): fails.append(f'{s} preview {p["__id"]}: change without a reason')
        if p.get('as_of') == lastpv and not p.get('shadow') and not p.get('tracking') and p.get('market') != 'Prop': pg[p['game_id']].append(p)
    for k, L in pg.items():
        sides = {team(p) for p in L if p.get('market') != 'Total'}; tots = {str(p.get('pick', '')).split()[0] for p in L if p.get('market') == 'Total'}
        if len(sides) > 1 or len(tots) > 1: fails.append(f'{s} preview {k}: opposing picks {[p["pick"] for p in L]}')
    # 8
    if s in ('nfl', 'fbs'):
        for g in games:
            if str(g.get('date') or g['__id'][:10]) >= TODAY:
                Q = g.get('qbs') or {}
                for side in ('away', 'home'):
                    q = Q.get(side) or {}
                    if not q.get('name') or str(q.get('depth', '')).upper() not in ('QB1', 'QB2', 'QB3'): fails.append(f'{s} {g["__id"]}: {side} starting QB or depth missing'); break
    # 9
    gmap = {g['__id']: g for g in games}
    for p in picks:
        if p.get('date') != TODAY or p.get('market') != 'Prop': continue
        g = gmap.get('_'.join(p['__id'].split('_')[:2])) or {}
        L = g.get('lineups') or {}
        names = {str(x.get('player', '')).lower() for side in ('away', 'home') for x in (L.get(side) or [])}
        if not names or str(p.get('player', '')).lower() not in names: fails.append(f'{s} {p["__id"]}: player not on the validated lineup')
        if not p.get('matchup'): fails.append(f'{s} {p["__id"]}: no matchup')
    # 10
    need = {'nfl': 22, 'fbs': 22, 'nba': 5, 'ncaam': 5, 'ncaaw': 5, 'nhl': 19}[s]
    for g in games:
        if str(g.get('date') or g['__id'][:10]) < TODAY: continue
        L = g.get('lineups') or {}
        for side in ('away', 'home'):
            P = L.get(side) or []
            st = [x for x in P if x.get('starter', True)]
            if len(st) < need: fails.append(f'{s} {g["__id"]}: {side} lineup has {len(st)} starters, needs {need}'); break
            if any(x.get('rating') is None for x in st): fails.append(f'{s} {g["__id"]}: {side} starters without a rating'); break
            outs = [x for x in st if re.search(r'\b(out|doubtful|ir|injured reserve)\b', str(x.get('status', '')).lower())]   # Nov 11: whole words ("Confirmed" contains ir)
            if any(not x.get('backup') for x in outs): fails.append(f'{s} {g["__id"]}: {side} starter out with no backup named'); break
            if outs and not (g.get('model') or {}).get('adjustments'): fails.append(f'{s} {g["__id"]}: starters out but no model.adjustments'); break
    # 6
    C = m.get('counts') or {}
    have = {'picks': len(picks), 'bt': len(bt), 'games': len(games), 'pv': len(pv)}
    if s == 'nfl': have['bg'] = len(bg)
    for k, v in have.items():
        if C.get(k) != v: warns.append(f'{s}: meta.counts.{k} {C.get(k)} vs hub {v} (write counts before publishing)')
    print(f'{s}: picks {len(picks)}, backtest {len(bt)}, games {len(games)}' + (f', bg {len(bg)}' if s == 'nfl' else ''))
for w in warns: print('WARN', w)
for f in fails: print('FAIL', f)
print('checks done:', len(fails), 'fail,', len(warns), 'warn')
sys.exit(1 if fails else 0)
