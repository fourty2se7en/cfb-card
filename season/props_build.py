"""Props builder (model v3), from the Nov 19 2026 scheduled props task (project doc claude/props_build_nov19.py.txt).
NBA, NHL, FBS and NFL player props from repo logs and The Odds API props reads.
NCAAM and NCAAW (Nov 19): points and rebounds props from repo box scores (ncaa()).
Usage: python3 season/props_build.py <repo> <date> <out.json> [hold_qb_json]
Meta: reads hub meta from $META_DIR (default /tmp/hub/meta, made by `python3 season/ledger.py unpack /tmp/hub`).
"""
import gzip, json, csv, math, re, sys, glob, os, statistics as st, collections, datetime as dt, unicodedata
sys.path.insert(0, sys.argv[1])
from season.prop_writeup import build as writeup

REPO, DATE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
META = os.environ.get('META_DIR', '/tmp/hub/meta').rstrip('/') + '/'
HUB = os.environ.get('HUB_DIR', '/tmp/hub')   # ledger unpack, for NCAA game docs
NOW = dt.datetime.now(dt.timezone(dt.timedelta(hours=-7)))
LOGGED = NOW.strftime('%Y-%m-%d %I:%M %p Phoenix').replace(' 0', ' ')
VERSION = 'v3 (hit chance blended 50/50 with the no vig market; median price in win chance space)'
HOLD_QB = {}   # FBS/NFL team -> reason, filled from game docs (A18)

def imp(p):
    p = float(p); return 100/(p+100) if p > 0 else -p/(-p+100)
def amer(q):
    return round(-100*q/(1-q)) if q >= 0.5 else round(100*(1-q)/q)
def phi(x): return 0.5*(1+math.erf(x/math.sqrt(2)))
def pois_ge(mu, k):
    return 1-sum(math.exp(-mu)*mu**i/math.factorial(i) for i in range(k))

def read_props(sport):
    # Nov 19 (Trina): every read of the day counts (props_open, props_now, close_props), latest read wins per game, so a game whose
    # props post after the morning read (Thursday FBS, late NBA lines) still gets props.
    fs = sorted(glob.glob(f'{REPO}/odds/data/{sport}/{DATE}/props_open_*.csv.gz') + glob.glob(f'{REPO}/odds/data/{sport}/{DATE}/props_now_*.csv.gz')
                + glob.glob(f'{REPO}/odds/data/{sport}/{DATE}/close_props_*.csv.gz'), key=lambda f: f.rsplit('_', 1)[-1])
    if not fs: return {}, ''
    latest = {}
    for f in fs:
        for r in csv.DictReader(gzip.open(f, 'rt')): latest.setdefault(r['event_id'], {}).setdefault(f, []).append(r)
    rows = [r for ev in latest.values() for r in ev[max(ev, key=lambda f: f.rsplit('_', 1)[-1])]]
    # Nov 20: keep only games on DATE (Phoenix); reads cover the next 30 hours, so Saturday FBS games showed up on Friday
    rows = [r for r in rows if dt.datetime.fromisoformat(r['commence'].replace('Z', '+00:00')).astimezone(dt.timezone(dt.timedelta(hours=-7))).strftime('%Y-%m-%d') == DATE]
    g = collections.defaultdict(lambda: collections.defaultdict(dict))
    for r in rows:
        key = (r['away'], r['home'], r['commence'], r['player'], r['market'])
        g[key][(r['book'], r['point'])][r['outcome']] = r['price']
    out = {}
    for key, bk in g.items():
        cnt = collections.Counter(pt for (b, pt), d in bk.items() if 'Over' in d and 'Under' in d)
        if not cnt: continue
        pt = max(cnt, key=lambda p: (cnt[p], -abs(float(p) if p else 0)))
        ov = [imp(d['Over']) for (b, p), d in bk.items() if p == pt and 'Over' in d and 'Under' in d]
        un = [imp(d['Under']) for (b, p), d in bk.items() if p == pt and 'Over' in d and 'Under' in d]
        qo, qu = st.median(ov), st.median(un)
        out[key] = dict(line=float(pt), books=len(ov), over=amer(qo), under=amer(qu), q_over=qo, q_under=qu,
                        novig_over=qo/(qo+qu), read=f.split('_')[-1][:4])
    return out, f

def tier_of(edge):
    return 'Strong' if edge >= 5 else 'Solid' if edge >= 3 else 'Lean' if edge >= 1.5 else None

def meta_rules(sport):
    d = json.load(open(META+sport+'.json')); d = d.get('data', d)
    return {r.get('label'): r for r in d['rules']}

def rec_str(r):
    if not r: return '0-0 +0.00u'
    return f"{r['w']}-{r['l']}" + (f"-{r['p']}" if r.get('p') else '') + f" {r['u']:+.2f}u"

def ptime(commence):
    t = dt.datetime.fromisoformat(commence.replace('Z', '+00:00')).astimezone(dt.timezone(dt.timedelta(hours=-7)))
    return t.strftime('%I:%M %p').lstrip('0')

def started(commence):
    return dt.datetime.fromisoformat(commence.replace('Z', '+00:00')) <= dt.datetime.now(dt.timezone.utc)

def tlook(teams, idx, name):
    if name in idx: return teams[idx[name]]
    last = name.split()[-1]
    if last in idx: return teams[idx[last]]
    for t in teams.values():
        if t.get('display', '').split()[-1] == last or t.get('name') == last: return t
    raise KeyError(name)
def key_name(s): return re.sub(r'[^A-Za-z0-9]', '', unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode())
def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z]', '', re.sub(r'\b(jr|sr|ii|iii|iv)\b\.?', '', s.lower()))

def finish(doc, rules, label, tier, edge):
    r = rules.get(label) or {}
    t = (r.get('tiers') or {}).get(tier) or {}
    on = bool(t.get('on'))
    doc.update(rule=label, rule_label=label, rule_key=r.get('key'), prop_rule=r.get('key'), tier=tier,
               tier_basis=f'prop tier by edge {edge:.1f} points over the price (Strong 5+, Solid 3 to 5, Lean 1.5 to 3)',
               shadow=not on, grade='PLAY' if on else 'LEAN',
               rule_record={'rule': label, 'tier': tier, 'record': rec_str(t.get('real')),
                            'month': rec_str(t.get('real_month')) if t.get('real_month') else None,
                            'status': 'on' if on else 'off'},
               tier_record={'tier': tier, 'on': on, 'real': rec_str(t.get('real')),
                            'month': rec_str(t.get('real_month')) if t.get('real_month') else None})
    if not on:
        doc['conflict'] = f'{label} {tier} tier is off'
        doc['note'] = 'Would-be prop pick: its tier is off.' + (' ' + t['pending_on'] if t.get('pending_on') else '')
    if not r: doc['note'] = (doc.get('note', '') + ' No prop rule in meta for this stat and side.').strip()
    return doc

def decide(model_p, q):
    res = []
    for side, mp, nv, need, price in (('Over', model_p, q['novig_over'], q['q_over'], q['over']),
                                      ('Under', 1-model_p, 1-q['novig_over'], q['q_under'], q['under'])):
        blend = 0.5*mp + 0.5*nv
        res.append(dict(side=side, hit=blend, model_raw=mp, need=need, price=price, edge=100*(blend-need)))
    b = max(res, key=lambda x: x['edge'])
    return b if tier_of(b['edge']) else None

def base_doc(sport, gid, away, home, team, opp, team_name, player, stat_label, stat_key, q, best, proj, log, commence, line, fpath):
    tier = tier_of(best['edge'])
    vals = [v for v in log if v is not None]
    side = best['side']
    over_n = sum(1 for v in vals if (v > line if side == 'Over' else v < line))
    d = dict(sport=sport, date=DATE, game=f'{away} @ {home}', game_id=gid, away=away, home=home, team=team, team_name=team_name,
             opp=opp, player=player, stat=stat_key, side=side if sport != 'nba' else side.lower(), market='Prop',
             line=line, price=best['price'], books=q['books'], book='The Odds API median of books',
             line_source='The Odds API median of books',
             read_at=f"{DATE} (The Odds API props read {q['read'][:2]}:{q['read'][2:]} UTC)",
             logged_at=LOGGED, time=ptime(commence), result='pending', final='',
             pick=f"{player} {side.lower()} {line:g} {stat_label}",
             proj=round(proj, 2), hit_pct=round(100*best['hit'], 1), needed_pct=round(100*best['need'], 1),
             edge=round(best['edge'], 2), projected=round(best['hit'], 4),
             model={'projection': round(proj, 2), 'hit_pct': round(100*best['hit'], 1), 'needed_pct': round(100*best['need'], 1),
                    'edge': round(best['edge'], 1), 'model_only_pct': round(100*best['model_raw'], 1), 'version': VERSION},
             last5={'label': stat_label, 'line': line, 'values': vals[-5:], 'order': 'this season, oldest to newest'},
             hit5=f"{sum(1 for v in vals[-5:] if (v > line if side=='Over' else v < line))} of {len(vals[-5:])} {side.lower()}",
             avg5=round(st.mean(vals[-5:]), 1) if vals else None,
             season_log=vals, season_avg=round(st.mean(vals), 1) if vals else None,
             season={'gp': len(vals), 'avg': round(st.mean(vals), 1) if vals else None, 'total': round(sum(vals), 1),
                     'over_line': f'{over_n} of {len(vals)}'},
             experts=[], against=[], reasons=[], props_source_file=fpath.split('/odds/')[-1])
    if len(vals) < 4: d['short_log'] = True
    return d, tier

def mdoc(opp, m, mf, side, src):
    if not m: return None
    eff = ('supports Over' if mf > 1.01 else 'works against' if mf < 0.99 else 'neutral') if side == 'Over' else \
          ('supports Under' if mf < 0.99 else 'works against' if mf > 1.01 else 'neutral')
    return {'opp': opp, 'stat_label': m['stat_label'], 'allowed_per_game': m['allowed_per_game'], 'rank': m['rank'], 'of': m['of'],
            'vs': f"{m['stat_label']} allowed {m['allowed_per_game']} per game, {m['rank']} of {m['of']}",
            'adj': f'x{mf:.2f}', 'effect': eff, 'source': src}

out = {'nba': [], 'nhl': [], 'fbs': [], 'nfl': [], 'ncaam': [], 'ncaaw': [], 'skipped': collections.defaultdict(list), 'held': collections.defaultdict(list)}

def nba():
    D = f'{REPO}/season/data/espn/nba/{DATE}/'
    props, fpath = read_props('nba')
    ts = json.load(gzip.open(D+'team_stats.json.gz')); teams, idx = ts['teams'], ts['index']
    logs = json.load(gzip.open(D+'player_logs.json.gz'))['players']
    bypl = {norm(p['name']): p for p in logs.values()}
    inj = json.load(gzip.open(D+'injuries.json.gz'))
    status = {}
    for t in inj['injuries']:
        for i in t['injuries']:
            status[norm(i['athlete']['displayName'])] = (i['status'], i.get('shortComment', ''))
    usage = {}
    for ln in open(D+'usage_raw.txt').read().splitlines()[1:]:
        p = ln.split('|')
        if len(p) >= 2 and p[1]:
            usage[p[0]] = dict(zip(['points', 'rebounds', 'assists', 'threes'], map(float, p[1].split(','))))
            usage[p[0]]['who'] = p[2] if len(p) > 2 else ''
    last = {}
    for ln in open(D+'season_raw.txt').read().splitlines()[1:]:
        p = ln.split('|')
        if len(p) < 7: continue
        rec = {'gp': float(p[3] or 0), 'mpg': float(p[4] or 0)}
        for it in p[6].split():
            m = re.match(r'([part])([\d.]+):([\d.]+)/([\d.]+)/', it)
            if m: rec[m.group(1)] = (float(m.group(3)), float(m.group(4)))
        last[norm(p[0])] = rec
    rules = meta_rules('nba')
    MK = {'player_points': ('points', 'pts', 'p', 'Points'), 'player_rebounds': ('rebounds', 'reb', 'r', 'Rebounds'),
          'player_assists': ('assists', 'ast', 'a', 'Assists'), 'player_threes': ('threes', 't3m', 't', 'Threes')}
    MLAB = {'points': 'points', 'rebounds': 'rebounds', 'assists': 'assists', 'threes': '3 pointers made'}
    POS = {'G': 'guards', 'F': 'forwards', 'C': 'centers'}
    lg = {}
    for s_ in MLAB.values():
        for pos in POS.values():
            k = f'{s_} to {pos}'
            v = [t['matchup'][k]['allowed_per_game'] for t in teams.values() if k in t.get('matchup', {})]
            if v: lg[k] = st.mean(v)
    CODE = {'NY': 'NYK', 'SA': 'SAS', 'UTAH': 'UTA', 'GS': 'GSW', 'NO': 'NOP', 'WSH': 'WAS'}
    for (away, home, com, player, mkt), q in props.items():
        if mkt not in MK: continue
        if started(com): out['skipped']['nba'].append(f'{player}: game started'); continue
        stat, fld, letter, lab = MK[mkt]
        tA, tH = tlook(teams, idx, away), tlook(teams, idx, home)
        cA, cH = CODE.get(tA['abbr'], tA['abbr']), CODE.get(tH['abbr'], tH['abbr'])
        gid = f'{DATE}_{cA}-{cH}'
        p = bypl.get(norm(player))
        if not p: out['skipped']['nba'].append(f'{player} {stat}: no repo game log'); continue
        g = [x for x in p['games'] if x.get('min')]
        team = CODE.get(g[-1]['team'], g[-1]['team']) if g else None
        if team not in (cA, cH): out['skipped']['nba'].append(f'{player}: team {team} not in {cA}-{cH}'); continue
        sts = status.get(norm(player))
        if sts and sts[0].lower() in ('out', 'injured reserve', 'suspension'):
            out['skipped']['nba'].append(f'{player} {stat}: listed {sts[0]}'); continue
        opp = cH if team == cA else cA; oppT = tH if team == cA else tA
        vals = [x[fld] for x in g]; mins = [x['min'] for x in g]; n = len(g)
        L = last.get(norm(player), {})
        rate_now = sum(vals)/sum(mins) if n else None
        rate_last = (L[letter][0]/L['mpg']) if letter in L and L.get('mpg') else None
        if rate_now is None and rate_last is None: continue
        w = min(0.8, n/(n+4)) if rate_last is not None else 1.0
        rate = w*(rate_now or 0) + (1-w)*(rate_last or 0) if rate_now is not None else rate_last
        mproj = st.mean(mins[-5:]) if n >= 3 else (L.get('mpg') or st.mean(mins))
        base = rate*mproj
        mk = f"{MLAB[stat]} to {POS.get(p['pos'], 'forwards')}"
        mu = oppT.get('matchup', {}).get(mk); mf = 1.0
        if mu and lg.get(mk): mf = max(0.9, min(1.1, 1 + 0.5*(mu['allowed_per_game']/lg[mk]-1)))
        uf = 1.0; tm_u = usage.get(team)
        if tm_u and tm_u.get(stat): uf = min(1.12, 1 + 0.375*tm_u[stat])
        proj = base*mf*uf
        sd_last = L[letter][1]*proj/L[letter][0] if letter in L and L[letter][0] > 0 else None
        sd_now = st.pstdev(vals) if n >= 5 else None
        sds = [s for s in (sd_last, sd_now) if s]
        sd = st.mean(sds) if sds else 0.35*proj
        sd = max(sd, 0.3*proj if stat == 'points' else 1.1*math.sqrt(max(proj, 0.3)))
        best = decide(1 - phi((q['line'] - proj)/sd), q)
        if not best: continue
        doc, tier = base_doc('nba', gid, cA, cH, team, opp, tA['display'] if team == cA else tH['display'], player, stat, stat, q, best, proj, vals, com, q['line'], fpath)
        doc['doc_id'] = f"{gid}_prop_{key_name(player)}_{stat}"
        m = mdoc(opp, mu, mf, best['side'], 'ESPN box scores in the repo (team_stats), opponent allowed per game by position')
        if m: doc['matchup'] = m
        src = 'Card prop model (repo ESPN logs, The Odds API)'
        doc['reasons'] = [r for r in [
            {'label': "Tonight's projection", 'detail': f"{proj:.1f} {stat} in about {mproj:.0f} minutes vs the {q['line']:g} line.", 'market': 'Prop', 'points': None, 'source': src},
            {'label': 'Season to date', 'detail': f"{n} games this season: " + ', '.join(f'{v:g}' for v in vals) + f" {stat}. Rate weighted {round(100*w)}% to this season.", 'market': 'Prop', 'points': None, 'source': src} if n else None,
            {'label': 'Last season', 'detail': f"{L[letter][0]} {stat} per game in {L['mpg']:.0f} minutes over {L['gp']:.0f} games.", 'market': 'Prop', 'points': None, 'source': src} if letter in L else None,
            {'label': 'Matchup', 'detail': f"{opp} allow {mu['allowed_per_game']} {mu['stat_label']} per game ({mu['rank']} of {mu['of']}); projection x{mf:.2f}.", 'market': 'Prop', 'points': None, 'source': src} if mu else None,
            {'label': 'Teammates out', 'detail': f"{tm_u['who']} out: {round(100*tm_u[stat])}% of {team}'s {stat} this season is missing; projection x{uf:.2f}.", 'market': 'Prop', 'points': None, 'source': src} if tm_u and tm_u.get(stat) and uf > 1.005 else None,
        ] if r]
        if sts: doc['injury_flag'] = f'{player} listed {sts[0]} (ESPN): {sts[1]}'
        out['nba'].append(finish(doc, rules, f'{lab} · {best["side"]}', tier, best['edge']))

def nhl():
    D = f'{REPO}/season/data/nhl/{DATE}/'
    props, fpath = read_props('nhl')
    sk = json.load(gzip.open(D+'skater_logs.json.gz'))
    ts = json.load(gzip.open(D+'team_stats.json.gz'))['teams']
    tbyname = {v['name']: v for v in ts.values()}
    tbyname.update({v['name'].replace('St. ', 'St '): v for v in ts.values()})
    tbyname.update({v['name'].replace('é', 'e'): v for v in ts.values()})
    players = {}
    for team, lst in sk['skaters'].items():
        for p in lst: players[(team, norm(p['name']))] = p
    rules = meta_rules('nhl')
    lg_sa = st.mean(v['raw']['sa'] for v in ts.values()); lg_ga = st.mean(v['raw']['ga'] for v in ts.values())
    MK = {'player_shots_on_goal': ('shots', 'sog', 'Shots on goal', 'shots on goal'), 'player_points': ('points', 'pts', 'Points', 'points'),
          'player_goals': ('goals', 'g', 'Goals', 'goals')}
    for (away, home, com, player, mkt), q in props.items():
        if mkt not in MK: continue
        if started(com): out['skipped']['nhl'].append(f'{player}: game started'); continue
        stat, fld, lab, slab = MK[mkt]
        tA, tH = tbyname.get(away), tbyname.get(home)
        if not tA or not tH: out['skipped']['nhl'].append(f'{away}@{home}: team name not matched'); continue
        cA, cH = tA['abbr'], tH['abbr']; gid = f'{DATE}_{cA}-{cH}'
        p = players.get((cA, norm(player))) or players.get((cH, norm(player)))
        if not p: out['skipped']['nhl'].append(f'{player} {stat}: no repo game log'); continue
        team = cA if (cA, norm(player)) in players else cH
        opp, oT = (cH, tH) if team == cA else (cA, tA)
        vals = [x[fld] for x in p['log']]
        if not vals: continue
        s_avg = p['season'][fld]; l5 = p['last5'][fld] if p['last5']['gp'] else s_avg
        mu0 = 0.65*s_avg + 0.35*l5
        if stat == 'shots':
            mf = max(0.9, min(1.1, 1 + 0.5*(oT['raw']['sa']/lg_sa-1))); m = oT['matchup'].get('shots on goal')
        else:
            mf = max(0.88, min(1.12, 1 + 0.5*(oT['raw']['ga']/lg_ga-1))); m = oT['matchup'].get('goals')
        mu = mu0*mf
        k = int(math.floor(q['line'])) + 1
        pover = 1 - phi((q['line'] - mu)/math.sqrt(1.3*max(mu, 0.2))) if stat == 'shots' else pois_ge(mu, k)
        best = decide(pover, q)
        if not best or best['side'] != 'Over': continue
        doc, tier = base_doc('nhl', gid, cA, cH, team, opp, tA['name'] if team == cA else tH['name'], player, slab, stat, q, best, mu, vals, com, q['line'], fpath)
        doc['doc_id'] = f"{gid}_prop_{key_name(player)}_{stat}"
        doc['pick'] = f"{player} over {q['line']:g} {slab}"; doc['side'] = 'Over'
        md = mdoc(opp, m, mf, 'Over', 'NHL API team stats (repo team_stats)')
        if md: doc['matchup'] = md
        doc['reasons'] = [{'label': 'Projection', 'detail': f"{mu:.2f} {slab} (season {s_avg}, last 5 {l5}) vs the {q['line']:g} line.", 'market': 'Prop', 'points': None, 'source': 'Card prop model (repo NHL API logs, The Odds API)'}]
        doc['goalie_note'] = 'Opposing goalie not confirmed by the builder; matchup uses team goals and shots allowed.'
        out['nhl'].append(finish(doc, rules, f'{lab} · Over', tier, best['edge']))

def football_doc(sport, gid, nA, nH, team, opp, tname, player, slab, lab, q, best, proj, vals, com, fpath, m, mf, extra, rules):
    doc, tier = base_doc(sport, gid, nA, nH, team, opp, tname, player, slab, slab, q, best, proj, vals, com, q['line'], fpath)
    doc['doc_id'] = f"{gid}_prop_{key_name(player)}_{slab.replace(' ', '')}"
    doc['side'] = best['side']
    md = mdoc(opp, m, mf, best['side'], 'ESPN box scores in the repo (team_stats)')
    if md: doc['matchup'] = md
    doc['reasons'] = [{'label': 'Projection', 'detail': f"{proj:.1f} {slab} ({extra}) vs the {q['line']:g} line; {q['books']} books.", 'market': 'Prop', 'points': None, 'source': 'Card prop model (repo ESPN logs, The Odds API)'}]
    return finish(doc, rules, f'{lab} · {best["side"]}', tier, best['edge'])

FMK = {'player_reception_yds': ('rec', 'receiving yards', 'Receiving yards'), 'player_rush_yds': ('rush', 'rushing yards', 'Rushing yards'),
       'player_pass_yds': ('pass', 'passing yards', 'Passing yards')}

def fbs():
    D = f'{REPO}/season/data/espn/fbs/{DATE}/'
    props, fpath = read_props('fbs')
    ts = json.load(gzip.open(D+'team_stats.json.gz')); teams, idx = ts['teams'], ts['index']
    logs = {}
    for ln in open(D+'players_raw.txt').read().splitlines():
        p = ln.split('|')
        if len(p) < 4: continue
        logs[(p[0], norm(p[1]), p[2])] = [int(x.split('/')[0]) for x in p[3].split(',') if x]
    rules = meta_rules('fbs')
    for (away, home, com, player, mkt), q in props.items():
        if mkt not in FMK: continue
        if started(com): out['skipped']['fbs'].append(f'{player}: game started'); continue
        kind, slab, lab = FMK[mkt]
        try: tA, tH = tlook(teams, idx, away), tlook(teams, idx, home)
        except KeyError as e: out['skipped']['fbs'].append(f'{player} {slab}: team not in repo team stats ({e})'); continue
        nA, nH = tA['location'], tH['location']
        gid = f"{DATE}_{key_name(nA.replace('(OH)', 'OH'))}-{key_name(nH)}"
        team = nA if (nA, norm(player), kind) in logs else nH if (nH, norm(player), kind) in logs else None
        if not team: out['skipped']['fbs'].append(f'{player} {slab}: no repo game log'); continue
        if kind in ('pass', 'rec') and team in HOLD_QB:
            out['held']['fbs'].append(f'{player} {slab} {q["line"]:g}: {HOLD_QB[team]}'); continue
        vals = logs[(team, norm(player), kind)]
        opp, oT = (nH, tH) if team == nA else (nA, tA)
        mean = st.mean(vals); l3 = st.mean(vals[-3:])
        m = oT['matchup'].get(slab)
        lgv = [t['matchup'][slab]['allowed_per_game'] for t in teams.values() if t.get('ranked') and slab in t.get('matchup', {})]
        mf = max(0.88, min(1.12, 1 + 0.5*(m['allowed_per_game']/st.mean(lgv)-1))) if m and lgv else 1.0
        proj = (0.6*mean + 0.4*l3)*mf
        sd = max(st.pstdev(vals)*1.2 if len(vals) >= 3 else 0, 0.55*proj, 8)
        best = decide(1 - phi((q['line'] - proj)/sd), q)
        if not best: continue
        d = football_doc('fbs', gid, nA, nH, team, opp, tA['display'] if team == nA else tH['display'], player, slab, lab, q, best, proj, vals, com, fpath, m, mf, f'season {mean:.1f}, last 3 {l3:.1f}', rules)
        out['fbs'].append(d)

def nfl():
    props, fpath = read_props('nfl')
    D = f'{REPO}/season/data/espn/nfl/{DATE}/'
    ts = json.load(gzip.open(D+'team_stats.json.gz')); teams, idx = ts['teams'], ts['index']
    seen = set(); logs = collections.defaultdict(list)   # (abbr, norm name, kind) -> [(date, val)]
    names = {}
    for f in sorted(glob.glob(f'{REPO}/season/data/espn/nfl/*/boxscores.json.gz')):
        day = f.split('/')[-2]
        for gidx, g in json.load(gzip.open(f)).items():
            if gidx in seen or g.get('status') != 'STATUS_FINAL': continue
            seen.add(gidx)
            for tp in g.get('players') or []:
                ab = tp['team']['abbreviation']
                for sgrp in tp['statistics']:
                    kind = {'passing': 'pass', 'rushing': 'rush', 'receiving': 'rec'}.get(sgrp['name'])
                    if not kind: continue
                    yi = sgrp['keys'].index({'pass': 'passingYards', 'rush': 'rushingYards', 'rec': 'receivingYards'}[kind])
                    for a in sgrp['athletes']:
                        try: v = int(float(a['stats'][yi]))
                        except Exception: continue
                        nm = a['athlete']['displayName']; names[norm(nm)] = nm
                        logs[(ab, norm(nm), kind)].append((day, v))
    rules = meta_rules('nfl')
    inj = json.load(gzip.open(D+'injuries.json.gz')); status = {}
    for t in inj['injuries']:
        for i in t['injuries']: status[norm(i['athlete']['displayName'])] = (i['status'], i.get('shortComment', ''))
    for (away, home, com, player, mkt), q in props.items():
        if mkt not in FMK: continue
        if started(com): out['skipped']['nfl'].append(f'{player}: game started'); continue
        kind, slab, lab = FMK[mkt]
        tA, tH = tlook(teams, idx, away), tlook(teams, idx, home)
        cA, cH = tA['abbr'], tH['abbr']; gid = f'{DATE}_{cA}-{cH}'
        team = cA if (cA, norm(player), kind) in logs else cH if (cH, norm(player), kind) in logs else None
        if not team: out['skipped']['nfl'].append(f'{player} {slab}: no repo box score log'); continue
        if kind in ('pass', 'rec') and team in HOLD_QB:
            out['held']['nfl'].append(f'{player} {slab} {q["line"]:g}: {HOLD_QB[team]}'); continue
        sts = status.get(norm(player))
        if sts and sts[0].lower() in ('out', 'injured reserve', 'doubtful', 'suspension'):
            out['skipped']['nfl'].append(f'{player} {slab}: listed {sts[0]}'); continue
        vals = [v for d_, v in sorted(logs[(team, norm(player), kind)])]
        opp, oT = (cH, tH) if team == cA else (cA, tA)
        mean = st.mean(vals); l3 = st.mean(vals[-3:])
        m = oT.get('matchup', {}).get(slab)
        lgv = [t['matchup'][slab]['allowed_per_game'] for t in teams.values() if slab in t.get('matchup', {})]
        mf = max(0.9, min(1.1, 1 + 0.5*(m['allowed_per_game']/st.mean(lgv)-1))) if m and lgv else 1.0
        proj = (0.6*mean + 0.4*l3)*mf
        sd = max(st.pstdev(vals)*1.1 if len(vals) >= 3 else 0, 0.45*proj, 8)
        best = decide(1 - phi((q['line'] - proj)/sd), q)
        if not best: continue
        if best['edge'] > 15: out['skipped']['nfl'].append(f'{player} {slab}: edge {best["edge"]:.0f} over 15 capped, no pick'); continue
        d = football_doc('nfl', gid, cA, cH, team, opp, tA['display'] if team == cA else tH['display'], player, slab, lab, q, best, proj, vals, com, fpath, m, mf, f'season {mean:.1f}, last 3 {l3:.1f}', rules)
        if sts and sts[0].lower() == 'questionable': d['injury_flag'] = f'{player} listed Questionable (ESPN): {sts[1]}'
        out['nfl'].append(d)

def ncaa(sport):
    """Nov 19 (Trina: props for every game in every sport). NCAAM and NCAAW points and rebounds props from the repo ESPN box
    scores (last 30 days, finals saved by espn_pull.py) and The Odds API props reads. Team and game come from the player's
    box score team and today's game docs (HUB games); matchup = opponent points or rebounds allowed per game with rank."""
    props, fpath = read_props(sport)
    if not props: out['skipped'][sport].append('no props posted by the books today'); return
    d0 = dt.date.fromisoformat(DATE); L = collections.defaultdict(list); allowed = collections.defaultdict(lambda: collections.defaultdict(list))
    for i in range(1, 31):
        f = f'{REPO}/season/data/espn/{sport}/{(d0 - dt.timedelta(days=i)).isoformat()}/boxscores.json.gz'
        if not os.path.exists(f): continue
        for b in json.load(gzip.open(f, 'rt')).values():
            tm = [(t.get('team') or {}).get('abbreviation') for t in b.get('players') or []]
            for t in b.get('players') or []:
                ab = (t.get('team') or {}).get('abbreviation'); opp = next((x for x in tm if x != ab), None)
                stt_ = (t.get('statistics') or [{}])[0]; lab = stt_.get('labels') or stt_.get('names') or []; ix = {k: j for j, k in enumerate(lab)}
                tp = tr = 0
                for a in stt_.get('athletes') or []:
                    sv = a.get('stats') or []
                    if a.get('didNotPlay') or not sv: continue
                    g = lambda k: float(str(sv[ix[k]]).split('-')[0]) if k in ix and ix[k] < len(sv) and str(sv[ix[k]]).split('-')[0].replace('.', '').isdigit() else 0.0
                    mn = g('MIN')
                    if mn <= 0: continue
                    L[norm((a.get('athlete') or {}).get('displayName', ''))].append(dict(team=ab, min=mn, pts=g('PTS'), reb=g('REB'), date=(d0 - dt.timedelta(days=i)).isoformat()))
                    tp += g('PTS'); tr += g('REB')
                if opp: allowed[opp]['pts'].append(tp); allowed[opp]['reb'].append(tr)
    for v in L.values(): v.sort(key=lambda x: x['date'])
    AL = {t: {k: st.mean(v) for k, v in d.items() if v} for t, d in allowed.items() if len(d.get('pts', [])) >= 3}
    games = {}
    for f in glob.glob(f'{HUB}/sports/{sport}/games/{DATE}_*.json'):
        g = json.load(open(f)); g = g.get('data', g)
        games[os.path.basename(f)[:-5]] = ((g.get('away') or {}).get('code'), (g.get('home') or {}).get('code'))
    try: rules = meta_rules(sport)
    except Exception: rules = {}
    MK = {'player_points': ('points', 'pts', 'Points'), 'player_rebounds': ('rebounds', 'reb', 'Rebounds')}
    for (away, home, com, player, mkt), q in props.items():
        if mkt not in MK: continue
        if started(com): out['skipped'][sport].append(f'{player}: game started'); continue
        stat, fld, lab = MK[mkt]
        g = L.get(norm(player))
        if not g: out['skipped'][sport].append(f'{player} {stat}: no repo box score'); continue
        team = g[-1]['team']; gid = next((k for k, v in games.items() if team in v), None)
        if not gid: out['skipped'][sport].append(f'{player}: team {team} has no game doc today'); continue
        cA, cH = games[gid]; opp = cH if team == cA else cA
        vals = [x[fld] for x in g]; mins = [x['min'] for x in g]
        rate = sum(vals) / sum(mins); mproj = st.mean(mins[-5:])
        lgv = [d[fld] for d in AL.values() if fld in d]
        mf = max(0.9, min(1.1, 1 + 0.5 * (AL.get(opp, {}).get(fld, st.mean(lgv)) / st.mean(lgv) - 1))) if lgv else 1.0
        proj = rate * mproj * mf
        sd = max(st.pstdev(vals) if len(vals) >= 4 else 0, 0.3 * proj if stat == 'points' else 1.1 * math.sqrt(max(proj, 0.3)), 2.0)
        best = decide(1 - phi((q['line'] - proj) / sd), q)
        if not best: continue
        if best['edge'] > 15: out['skipped'][sport].append(f'{player} {stat}: edge {best["edge"]:.0f} over 15 capped, no pick'); continue
        doc, tier = base_doc(sport, gid, cA, cH, team, opp, team, player, stat, stat, q, best, proj, vals, com, q['line'], fpath)
        doc['side'] = best['side']; doc['doc_id'] = f"{gid}_prop_{key_name(player)}_{stat}"
        if opp in AL and fld in AL[opp]:
            rk = sorted(AL, key=lambda t: AL[t].get(fld, 0)).index(opp) + 1
            doc['matchup'] = mdoc(opp, {'stat_label': stat, 'allowed_per_game': round(AL[opp][fld], 1), 'rank': rk, 'of': len(AL)}, mf, best['side'],
                                  'ESPN box scores in the repo (last 30 days), opponent allowed per game')
        src = 'Card prop model (repo ESPN box scores, The Odds API)'
        doc['reasons'] = [{'label': 'Projection', 'detail': f"{proj:.1f} {stat} in about {mproj:.0f} minutes vs the {q['line']:g} line (games: " + ', '.join(f'{v:g}' for v in vals[-6:]) + ').',
                           'market': 'Prop', 'points': None, 'source': src}]
        out[sport].append(finish(doc, rules, f'{lab} · {best["side"]}', tier, best['edge']))


if __name__ == '__main__':
    HOLD_QB.update(json.loads(sys.argv[4]) if len(sys.argv) > 4 else {})
    for fn in (nba, nhl, fbs, nfl, lambda: ncaa('ncaam'), lambda: ncaa('ncaaw')):
        try: fn()
        except Exception as e:
            import traceback; traceback.print_exc(); out['skipped'][getattr(fn, '__name__', 'ncaa')].append(f'builder error: {e}')
    for s in ('nba', 'nhl', 'fbs', 'nfl', 'ncaam', 'ncaaw'):
        for d in out[s]:
            try:
                w = writeup(d, None, d.get('matchup'))
                d['summary'] = {'for': w['for'], 'against': w['against'], 'by': 'season/prop_writeup.py'}
                if w.get('matchup'): d['matchup'] = {**d.get('matchup', {}), **w['matchup']}
            except Exception as e:
                d['summary'] = {'for': '', 'against': 'Nothing notable.', 'err': str(e)}
    json.dump(out, open(OUT, 'w'), indent=1, default=str)
    for s in ('nba', 'nhl', 'fbs', 'nfl', 'ncaam', 'ncaaw'):
        c = collections.Counter((d['tier'], d['shadow']) for d in out[s])
        print(s, len(out[s]), 'card', sum(1 for d in out[s] if not d['shadow']), dict(c))
    for s, v in out['skipped'].items(): print('skipped', s, len(v), v[:10])
    for s, v in out['held'].items(): print('held', s, len(v), v)
