"""Nov 15 post step (run after b91_post.py, before writeups): python3 post15.py DATE <final dir> <cfb-card clone> <meta json>
1. Game docs: away.stats / home.stats from the repo team_stats.json.gz (rank 1 = best; defense rank 1 = allows the least).
2. Lineup source text names the repo ESPN data (NBA.com retired as the player source Nov 15).
3. Backup starters (B93): for each starter ruled Out (8+ starts this season), who replaces him in the starting five,
   the games the team has played without him this season, its record and the replacement's line in them; game doc
   backup_starters [...] and a notes line.
4. Opposing would-be picks (B106): two would-be docs on opposite sides of one market group in a game (side markets: spread,
   moneyline; totals): higher tier stays, same tier more season units in its tier; the other gets conflict and a dropped flag removed
   from the ledger write (deleted from the folder)."""
import sys, json, gzip, glob, os, re, collections
DATE, FD, REPO, MF = sys.argv[1:5]
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
from teams import FULL
MAP = {'NY':'NYK','SA':'SAS','UTAH':'UTA','NO':'NOP','GS':'GSW','WSH':'WAS'}
TS = json.load(gzip.open(f'{REPO}/season/data/espn/nba/{DATE}/team_stats.json.gz'))['teams']
BYC = {MAP.get(v.get('nba_code') or v['abbr'], v.get('nba_code') or v['abbr']): v for v in TS.values()}
PL = json.load(gzip.open(f'{REPO}/season/data/espn/nba/{DATE}/player_logs.json.gz'))['players']
M = json.load(open(MF)); M = M.get('data', M); RULES = {r['key']: r for r in M['rules']}
def ld(p): d = json.load(open(p)); return d, d.get('data', d)
def sv(p, doc): json.dump(doc, open(p, 'w'), indent=1)
nz = lambda s: re.sub(r"[.'’]", '', s).lower()
# team games and starters this season
TG = collections.defaultdict(dict)   # team -> eid -> {date, starters:set, lines:{name:game}}
for p in PL.values():
    for g in p['games']:
        if g['date'] < '2026-10-01': continue
        t = MAP.get(g['team'], g['team']); e = TG[t].setdefault(g['eid'], dict(date=g['date'], starters=set(), lines={}))
        e['lines'][p['name']] = g
        if g.get('starter'): e['starters'].add(p['name'])
FIN = {}
for l in open(f'{D}/season/espn_odds.txt'):
    f = l.strip().split('|')
    if len(f) > 6: FIN[f[5]] = (MAP.get(f[1], f[1]), MAP.get(f[2], f[2]), int(f[3]), int(f[4]))
def backups(team, inj):
    out = []
    games = TG.get(team, {})
    for it in inj:
        if it.get('team') != team or it.get('status') not in ('Out', 'Suspension'): continue
        name = it['player']; starts = sum(1 for e in games.values() if any(nz(n) == nz(name) for n in e['starters']))
        if starts < 5: continue
        without = [(eid, e) for eid, e in games.items() if not any(nz(n) == nz(name) for n in e['lines'])]
        cnt = collections.Counter(); 
        usual = collections.Counter(n for e in games.values() for n in e['starters'])
        for eid, e in without:
            for n in e['starters']: cnt[n] += 1
        repl = [n for n, c in cnt.most_common() if usual[n] - c < 3 and not any(nz(n) == nz(x['player']) for x in inj if x.get('team') == team)]
        rp = repl[0] if repl else None
        w = l = 0; rl = []
        for eid, e in without:
            fz = FIN.get(eid)
            if fz:
                a, h, sa, sh = fz; my, op = (sa, sh) if a == team else (sh, sa); w += my > op; l += my < op
            if rp and rp in e['lines']: g = e['lines'][rp]; rl.append((g.get('pts') or 0, g.get('reb') or 0, g.get('ast') or 0, g.get('min') or 0))
        line = (f"{sum(x[0] for x in rl)/len(rl):.1f} points, {sum(x[1] for x in rl)/len(rl):.1f} rebounds, {sum(x[2] for x in rl)/len(rl):.1f} assists in {sum(x[3] for x in rl)/len(rl):.0f} minutes") if rl else None
        txt = (f"{name} ({it.get('note') or it.get('injury') or 'injury'}) is out; he has started {starts} games this season. "
               + (f"{FULL[team].split()[-1]} are {w}-{l} in the {len(without)} game{'s' if len(without)!=1 else ''} he missed" if without else "He has not missed a game yet")
               + (f"; {rp} has started in his place" + (f" ({line} in those games)" if line else '') if rp and without else '') + '.')
        out.append(dict(team=team, player=name, starts=starts, games_without=len(without), record_without=f"{w}-{l}", replacement=rp, replacement_line=line, text=txt, source='ESPN injury report and box scores (GitHub pull)'))
    return out
TIER = {'Strong': 3, 'Solid': 2, 'Lean': 1}
picks = {}
for p in glob.glob(f'{FD}/sports_nba_picks__{DATE}_*.json'):
    doc, d = ld(p); picks[p] = (doc, d)
for p in glob.glob(f'{FD}/sports_nba_games__{DATE}_*.json'):
    doc, g = ld(p)
    for side in ('away', 'home'):
        c = g[side]['code']; t = BYC.get(c)
        if t: g[side]['stats'] = t['stats']
    for side in ('away', 'home'):
        for x in g.get('lineups', {}).get(side, []): x['source'] = 'ESPN box scores (last 5 team games, GitHub pull), ESPN injury report; starters estimated by minutes'
    inj = g.get('injuries', [])
    bs = backups(g['away']['code'], inj) + backups(g['home']['code'], inj)
    g['backup_starters'] = bs
    notes = [n for n in g.get('notes', []) if not str(n).startswith('Backup starter: ')]
    g['notes'] = notes + ['Backup starter: ' + b['text'] for b in bs]
    sv(p, doc)
# opposing would-be picks
def grp(d):
    m = d.get('market'); return 'total' if m == 'Total' else ('side' if m in ('Spread', 'Moneyline') else None)
def dirn(d):
    if grp(d) == 'total': return 'O' if str(d['pick']).startswith('Over') else 'U'
    return d['pick'].split(' moneyline')[0].rsplit(' ', 1)[0] if 'moneyline' not in d['pick'] else d['pick'].split(' moneyline')[0]
def tu(d):
    r = RULES.get(d.get('rule')) or {}; t = (r.get('tiers') or {}).get(d.get('tier')) or {}
    s = t.get('real') or t.get('season') or {}; return s.get('u', 0) or 0
games = collections.defaultdict(list)
for p, (doc, d) in picks.items():
    if d.get('shadow') and grp(d) and d.get('market') != 'Game prop': games[(d['game'], grp(d))].append(p)
dropped = []
for k, L in games.items():
    for i in range(len(L)):
        for j in range(i + 1, len(L)):
            a, b = picks[L[i]][1], picks[L[j]][1]
            if L[i] in dropped or L[j] in dropped: continue
            da, db = dirn(a), dirn(b)
            if da == db: continue
            ka = (TIER.get(a['tier'], 0), tu(a)); kb = (TIER.get(b['tier'], 0), tu(b))
            keep, lose = (L[i], L[j]) if ka >= kb else (L[j], L[i])
            kd, lg = picks[keep][1], picks[lose][1]
            print('OPPOSING would-be', os.path.basename(lose), 'loses to', os.path.basename(keep))
            dropped.append(lose)
for p in dropped:
    doc, d = picks[p]
    keepdoc = None
    d['conflict'] = dict(with_rule=None, kept='other side', text='Another would-be pick in this game takes the other side at a higher tier or with more season units, so this one is not logged')
    os.remove(p)
print('game docs', len(glob.glob(f'{FD}/sports_nba_games__{DATE}_*.json')), 'dropped', len(dropped))
