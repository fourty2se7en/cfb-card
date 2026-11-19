"""Builds Season Cards hub docs for the NHL run (updated Nov 7, 2026: every rule pick, period lines, team game logs with periods): pick docs with detail fields, inputs, game docs, Nov 5 finals,
standings, meta and expert docs. Writes JSON files under hub/ and a batch list hub_writes.json (for ArtifactData batch)."""
import json, os, re, sys, glob, datetime, collections, math
sys.argv = [sys.argv[0]]
import render as R, model as M, rules as RL, signals as SG, standings as STD, divisions as DV
D = '2026-11-15'; NOW = '7:30 AM'; DOW = 'Sun'; YD = '2026-11-14'; READ_AT = open('/home/claude/season/nhl15w/read_at.txt').read().strip()
WK = '/home/claude/season/nhl15w'  # this run's scratch inputs (pull files, ledger download, plogs, game doc versions)
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'hub'); os.makedirs(OUT, exist_ok=True)
SP = os.path.dirname(HERE)
W = []
def put(coll, doc_id, doc, op='set', ver=None):
    p = os.path.join(OUT, (coll + '__' + doc_id).replace('/', '_') + '.json'); json.dump(doc, open(p, 'w'))
    w = {'op': op, 'collection': coll, 'doc_id': doc_id, 'file_path': p}
    if ver: w['if_version'] = ver
    W.append(w)
def fmt(o): return f'+{o}' if o > 0 else f'{o}'
def be(o): return -o/(-o+100) if o < 0 else 100/(o+100)
def units(r, p): return (p/100 if p > 0 else 100/(-p)) if r == 'win' else (-1 if r == 'loss' else 0)

# ---------- team game logs (review/games.json: every regular-season game through Nov 5 with SBR closing lines)
GJ = json.load(open(os.path.join(HERE, 'review', 'games.json')))
TG = collections.defaultdict(list)
for g in GJ:
    sb = g['sb']; plc = sb.get('plc'); tc = sb.get('tc')
    for side in ('a', 'h'):
        t = g[side]; home = side == 'h'
        gf, ga = (g['hg'], g['ag']) if home else (g['ag'], g['hg'])
        res = 'W' if gf > ga else ('L' if g['lp'] == 'REG' else 'OTL')
        ats = None
        if plc:
            sp = plc['sp'] if not home else -plc['sp']
            ats = 'W' if (gf - ga) + sp > 0 else 'L'
        ou = None
        if tc:
            tot = gf + ga; ou = 'P' if tot == tc['line'] else ('O' if tot > tc['line'] else 'U')
        TG[t].append(dict(date=g['date'], home=home, opp=g['h'] if not home else g['a'], gf=gf, ga=ga, res=res, ats=ats, ou=ou, id=g.get('id'), lp=g['lp'],
                           spread=(('+' if (plc['sp'] if not home else -plc['sp']) > 0 else '') + str(plc['sp'] if not home else -plc['sp'])) if plc else None, total=tc['line'] if tc else None))
for t in TG: TG[t].sort(key=lambda x: x['date'])
LS = {}
for ln in open(os.path.join(WK, 'pull', 'linescores.txt')).read().split('\n'):
    if '|' in ln:
        i_, per = ln.split('|'); LS[int(i_)] = [(p.rstrip('0123456789-').strip() or None, *map(int, p.lstrip('OTS').split('-'))) for p in per.split(',')]
TEAMNAME = {}
import teams as TMS
for k_, v_ in TMS.TEAMS.items(): TEAMNAME[k_] = f"{v_[0]} {v_[1]}"
PLINES = json.load(open(os.path.join(WK, 'pull', 'plines_today.json')))
PLH = {}
for ln in open(os.path.join(HERE, 'review', 'plines.txt')).read().split('\n'):
    f_ = ln.split('|')
    if len(f_) == 6 and not ln.startswith('#'):
        d_, t_, per_, sp_, ou_, ml_ = f_
        PLH.setdefault((d_, t_), {})[per_] = dict(spread=float(sp_.split()[0]), total=float(ou_[1:].split()[0]))
def gamelog(t):
    out = []
    for x in reversed(TG[t][-10:]):
        e = dict(date=x['date'], opp=x['opp'], opp_name=TEAMNAME.get(x['opp']), opp_rank=None, site='home' if x['home'] else 'away',
                 pf=x['gf'], pa=x['ga'], ot=x['lp'] != 'REG', spread=x['spread'], total=x['total'], ats=x['ats'], ou=x['ou'])
        ls = LS.get(x['id'])
        if ls:
            labs = []; f_ = []; a_ = []
            for k, (typ, aw, hm) in enumerate(ls):
                labs.append(typ if typ else f'P{k+1}'); f_.append(hm if x['home'] else aw); a_.append(aw if x['home'] else hm)
            e['periods'] = dict(labels=labs, **{'for': f_, 'against': a_})
        if (x['date'], t) in PLH:
            e['plines'] = PLH[(x['date'], t)]; e['plines_note'] = 'texas222 period lines read the morning of the game (pick time), not the closing number'
        out.append(e)
    return out
def hist(gs):
    if not gs: return None
    w = sum(x['res'] == 'W' for x in gs); l = sum(x['res'] == 'L' for x in gs); o = sum(x['res'] == 'OTL' for x in gs)
    aw = sum(x['ats'] == 'W' for x in gs); al = sum(x['ats'] == 'L' for x in gs)
    ov = sum(x['ou'] == 'O' for x in gs); un = sum(x['ou'] == 'U' for x in gs); pu = sum(x['ou'] == 'P' for x in gs)
    def rec(xs): return f"{sum(x['res']=='W' for x in xs)}-{sum(x['res']=='L' for x in xs)}-{sum(x['res']=='OTL' for x in xs)}"
    H = [x for x in gs if x['home']]; A = [x for x in gs if not x['home']]
    return dict(record=f'{w}-{l}-{o}', ats=f'{aw}-{al}', ou=f'{ov}-{un}' + (f'-{pu}' if pu else ''),
                pf=round(sum(x['gf'] for x in gs)/len(gs), 2), pa=round(sum(x['ga'] for x in gs)/len(gs), 2),
                home_away=f"{rec(H)} home · {rec(A)} road", games=len(gs))
def trend(t, T):
    gs = TG[t]; l5 = gs[-5:]
    month = [x for x in gs if x['date'] >= '2026-11-01']; week = [x for x in gs if '2026-11-09' <= x['date'] <= '2026-11-15']
    st = next((r for r in STD.load()[0] if r['t'] == t), None)
    return dict(last5=['W' if x['res'] == 'W' else 'L' for x in l5], pf=T['gf'], pa=T['ga'],
                last5_scores=[x['gf'] for x in l5], last5_against=[x['ga'] for x in l5], last5_totals=[x['gf']+x['ga'] for x in l5],
                last5_margins=[x['gf']-x['ga'] for x in l5], rest_days=T['rest'], back_to_back=T['rest'] == 0,
                streak=st['strk'] if st else None, last10=T['l10'], last_game=T['last'],
                history=dict(season=hist(gs), month=hist(month), week=hist(week), last10=hist(gs[-10:]), last5=hist(l5)),
                games=gamelog(t), history_note='ats = puck line at the SBR closing number (+1.5/-1.5); ou = vs the SBR closing total. Month = November; week = Mon Nov 9 to Sun Nov 15.')

# ---------- rule records (re-check) and card live records
RC = json.load(open(os.path.join(HERE, 'review', 'recheck.json')))
ST = json.load(open(os.path.join(HERE, 'rules_state.json')))
def cell(a): return f"{a['w']}-{a['l']}" + (f"-{a['p']}" if a.get('p') else '') + f" {a['u']:+.2f}u"
LED = [json.load(open(f)) for f in glob.glob(os.path.join(WK, 'ledger', 'sports', 'nhl', 'picks', '*.json'))]
def card_rec(rule=None, cat=None, since='2026-10-30', min_date=None):
    w = l = p = 0; u = 0.0
    for d in LED:
        if d.get('result') not in ('win', 'loss', 'push'): continue
        if rule and (d.get('rule') != rule or d.get('shadow') or d.get('watch')): continue
        if cat and not (d.get('market') == 'Prop' and d.get('stat') == cat): continue
        if d['date'] < (min_date or since): continue
        w += d['result'] == 'win'; l += d['result'] == 'loss'; p += d['result'] == 'push'; u += units(d['result'], d['price'])
    return dict(w=w, l=l, p=p, u=round(u, 2), n=w+l+p)
# last 3 weeks of the re-check (every game) for each rule's active version
sys.path.insert(0, os.path.join(HERE, 'review'))
import tests as TT
def rule_bets(rid, v):
    out = []
    for x in TT.rows:
        for pk in RL.apply_rules(x['c'], x['r'], version=v):
            if pk['rule'] == rid:
                g = x['g']; ag, hg = g['ag'], g['hg']
                if pk['market'] == 'Moneyline': r = 'W' if ((ag > hg) if pk['side'] == 'A' else (hg > ag)) else 'L'
                elif pk['market'] == 'Puck line':
                    m = (ag-hg) if pk['side'] == 'A' else (hg-ag); r = 'W' if m + pk['line'] > 0 else 'L'
                else:
                    t = ag+hg; r = 'P' if t == pk['line'] else ('W' if (t > pk['line']) == (pk['side'] == 'O') else 'L')
                pr = pk['price'] if (pk['price'] and 100 <= abs(pk['price']) <= 5000) else -110
                out.append((g['date'], r, pr))
    return out
L3W = '2026-10-19'
RREC = {}
for rid in RL.ORDER:
    v = ST['rules'][rid]['version']; recs = RC['records'][rid][v]
    b3 = RL.agg([b for b in rule_bets(rid, v) if b[0] >= L3W])
    RREC[rid] = dict(season=recs['season'], month=recs.get('Nov 2026'), l3w=b3, card=card_rec(rule=rid))
def rule_record(rid):
    x = RREC[rid]
    return dict(rule=rid, every_game=cell(x['season']), card=cell(x['card']) + ' (live card picks since Oct 30)', last_3_weeks=cell(x['l3w']),
                month=cell(x['month']) if x['month'] else None, status=ST['rules'][rid]['status'])
PCAT = {}
for cat in ('shots', 'points', 'goals'):
    s = card_rec(cat=cat, min_date='2026-01-01'); m = card_rec(cat=cat, min_date='2026-11-01'); l3 = card_rec(cat=cat, min_date=L3W)
    PCAT[cat] = dict(season=s, month=m, l3w=l3)
def prop_rule_record(cat):
    x = PCAT[cat]; lab = {'shots': 'Shots on goal', 'points': 'Points', 'goals': 'Goals'}[cat] + ' · Over'
    return dict(rule=lab, every_game=cell(x['season']) + ' (every logged prop of this stat and side)', card=cell(x['season']), last_3_weeks=cell(x['l3w']),
                month=cell(x['month']) if x['month']['n'] else None,
                status='off' if (x['season']['n'] >= 20 and x['season']['u'] < 0) else 'on')  # season only policy (Nov 9); the month is a watch only

# ---------- player last 5
PL5 = {}
for ln in open(os.path.join(WK, 'plogs.txt')).read().split('\n'):
    if not ln.strip(): continue
    t, n, rest = ln.split(':', 2)
    PL5[(t, n)] = [tuple(int(v) if i else v for i, v in enumerate(x.split('/'))) for x in rest.split(',')]

# ---------- experts (named people only)
EXP = {}  # Nov 15 morning run: no named expert NHL picks posted yet (was: Nov 14 early run (~1:40 AM): Action Network NHL picks page showed only Nov 13 picks (graded); no named picks posted for Nov 14 yet
for k, L in EXP.items():
    for e in L:
        e['pulled_at'] = f'{D} ~1:24 PM Phoenix'; e['card_record'] = None
        if e.get('record') is None: e.pop('record')
def exp_ranked(k):
    def key(e):
        m = re.search(r'\(([+-][\d.]+)u\)', e.get('record') or '')
        return (-(float(m.group(1)) if m else -999),)
    return sorted(EXP.get(k, []), key=key)
for k, L in EXP.items():
    a, h = k.split('-')
    for e in L:
        did = re.sub(r'[^A-Za-z0-9_\-]', '', f"{D}_{k}_{e['name'].replace(' ', '')}_{e['market'].replace(' ', '')}_{re.sub(r'[^A-Za-z]', '', e['pick'])[:24]}")
        put('sports/nhl/experts', did, dict(e, date=D, game=f'{a} @ {h}', away=a, home=h, sport='nhl', result='pending'))

# ---------- per game
def _f(v): return f'+{v:g}' if v > 0 else f'{v:g}'
def pperiods(a, h):
    out = {}
    for per in ('P1', 'P2', 'P3'):
        if per not in PLINES.get(a, {}) or per not in PLINES.get(h, {}): continue
        A_, H_ = PLINES[a][per], PLINES[h][per]
        ov = A_ if A_['ou'] == 'O' else H_; un = H_ if A_['ou'] == 'O' else A_
        out[per] = dict(spread=dict(away=f"{_f(A_['sp'])} {fmt(A_['sp_price'])}", home=f"{_f(H_['sp'])} {fmt(H_['sp_price'])}"),
                        total=dict(over=f"{ov['tot']:g} {fmt(ov['tot_price'])}", under=f"{un['tot']:g} {fmt(un['tot_price'])}"),
                        moneyline=dict(away=fmt(A_['ml']), home=fmt(H_['ml'])))
    return out
G = {g[0]+'-'+g[1]: g for g in M.GAMES}
games = {f"{g['a']}-{g['h']}": g for g in R.games}
SIGN = lambda s: s
def reasons(rows, side):
    f = [dict(label=s, detail=n, points=p, source=m) for s, m, sd, p, n in rows if sd == side and p]
    ag = [dict(label=s, detail=n, points=p, source=m) for s, m, sd, p, n in rows if sd != side and p]
    info_f = [dict(label=s, detail=n, points=0, source=m, info=True) for s, m, sd, p, n in rows if sd == side and not p]
    return f, ag, info_f
INJ = json.load(open(os.path.join(WK, 'inj15.json')))  # ESPN injuries feed saved by the cfb-card season loop, Nov 13 ~2 PM Phoenix (Nov 14 6:12 AM feed checked: no changes)
STROWS = {r['t']: r for r in STD.load()[0]}
def team(t, T, side, gx):
    st = STROWS[t]; n, sstat, data, svr, sa = gx
    return dict(code=t, name=M.NAMES[t], short=M.NAMES[t].split(' ', 1)[1] if t not in ('SJS',) else 'Sharks', record=T['rec'],
                venue_record=('home ' + T['home']) if side == 'H' else ('road ' + T['road']), conference=STD.CONF[st['conf']], division=STD.DIV[st['div']],
                points=st['pts'], rank_label='League standings', rank=st['lg'], color=R.COLORS[t][0], color_dark=R.COLORS[t][1], logo=None,
                goalie=dict(name=n, status=sstat, season_starts=data['gs'] if data else 0, season_record=data['rec'] if data else None,
                            gaa=data['gaa'] if data else None, sv_pct=data['sv'] if data else None, card_sv_pct=round(svr, 3)))
PICKDOCS = []
for x in R.PICKS:
    k = x['key']; g = games[k]; a, h = g['a'], g['h']; c, r = x['c'], x['r']; nm = {'A': a, 'H': h}
    graded, _ = R.analyse(g)
    la, lh = g['la'], g['lh']
    lam = g['lamT']; un, pu = g['p_tot_under'](c['line']); over = 1 - un - pu
    an = SG.AN[k]; dk = SG.DK[k]
    l5a, l5h = TG[a][-5:], TG[h][-5:]
    # ---- picks for this game (every rule pick; shadow when the rule is off)
    side_pick, tot_pick, pl_pick = None, None, None
    SUFX = {'ML1': 'ml', 'PL1': 'pl', 'TOT1': 'tot1', 'TOT2': 'tot2', 'P1O': 'p1o'}
    def est_of(m): return next((y['est'] for y in graded if y['m'] == m), None)
    for pk in x['rp']:
        sd = pk['side']; t = nm.get(sd); rid = pk['rule']
        common = dict(date=D, game=f'{a} @ {h}', away=a, home=h, time=G[k][2], result='pending', final='', conflicting=False, sport='nhl',
                      rule=rid, version=pk['version'], price=pk['price'], experts=[])
        if pk['status'] != 'on': common['shadow'] = True
        if rid == 'ML1':
            f, ag, info = reasons(r['S'], sd); est = c['estH'] if sd == 'H' else 1 - c['estH']
            doc = dict(common, market='Moneyline', pick=f"{M.NAMES[t]} moneyline", tier=r['ml_tier'], strength=r['ml_tier'], projected=round(est, 3), side=t,
                       conflicting=bool(x['ml'].get('conf')) if x['ml'] else False, reasons=f, against=ag, rule_record=rule_record('ML1'),
                       model=dict(projection=f"{100*est:.1f}% win chance (40% model and Sportradar, 60% texas222 no-vig)", hit_pct=round(100*est, 1), needed_pct=round(100*be(pk['price']), 1), edge=round(100*(est - be(pk['price'])), 1)),
                       last5=dict(line=None, last5_away=[dict(r=('W' if z['res'] == 'W' else 'L'), gf=z['gf'], ga=z['ga'], date=z['date']) for z in l5a],
                                  last5_home=[dict(r=('W' if z['res'] == 'W' else 'L'), gf=z['gf'], ga=z['ga'], date=z['date']) for z in l5h], label='results, goals for and against'),
                       experts=[e for e in exp_ranked(k) if e['market'] == 'Moneyline'])
            side_pick = (f"{D}_{k}_ml", doc)
        elif rid == 'PL1':
            ln = '+1.5' if pk['line'] > 0 else '-1.5'
            mf = [(p_, s_, n_) for s_, m_, sd_, p_, n_ in r['S'] if p_ and sd_ == sd]; ma = [(p_, s_, n_) for s_, m_, sd_, p_, n_ in r['S'] if p_ and sd_ != sd]
            prob = est_of(f'Puck line {t} {ln}')
            f_, ag_, pf, pa = R.pl_score(k, c, sd, ln, pk['price'], prob, nm, ma, mf)
            tr = RL.tier(pf - pa)
            doc = dict(common, market='Puck line', pick=f"{M.NAMES[t]} {ln}", line=pk['line'], tier=tr, strength=tr, side=t, projected=round(prob, 3) if prob else None,
                       reasons=[dict(label=s_, detail=n_, points=p_, source='Puck line evidence') for p_, s_, n_ in f_],
                       against=[dict(label=s_, detail=n_, points=p_, source='Puck line evidence') for p_, s_, n_ in ag_], rule_record=rule_record('PL1'),
                       model=dict(projection=f"{100*prob:.1f}% cover chance" if prob else None, hit_pct=round(100*prob, 1) if prob else None, needed_pct=round(100*be(pk['price']), 1), edge=round(100*(prob - be(pk['price'])), 1) if prob else None),
                       last5=dict(line=pk['line'], last5_away=[z['gf']-z['ga'] for z in l5a], last5_home=[z['gf']-z['ga'] for z in l5h], label='goal margins'))
            pl_pick = (f"{D}_{k}_pl", doc)
        elif rid in ('TOT2', 'P1O'):
            ws = 'Over' if sd == 'O' else 'Under'; lean = 'U' if sd == 'O' else 'O'
            tf_, ta_, _ = reasons(r.get('T', []), lean)   # TOT2 fades the totals signals: their side is the reason
            lead = r['tc'][lean] - r['tc'][sd]
            if rid == 'TOT2':
                prob = est_of(f"{ws} {pk['line']:g}") if est_of(f"{ws} {pk['line']:g}") else (over if sd == 'O' else un)
                doc = dict(common, market='Total', pick=f"{ws} {pk['line']:g}", line=pk['line'], tier=pk['tier'], strength=pk['tier'], tier_basis=f"signal lead {lead} (the totals lead this rule fades)", side=ws, projected=round(prob, 3) if prob else None,
                           reasons=[dict(label='Contrarian totals', detail=f"The totals signals lean {'Under' if lean == 'U' else 'Over'} by {lead} points; TOT2 takes the other side (totals signals followed lost all season)", points=lead, source='TOT2')],
                           against=[dict(label='Model', detail=f"Model total {lam:.2f} goals", points=None, source='Card model')] if (lam > pk['line']) != (sd == 'O') else [],
                           signals_faded=tf_, rule_record=rule_record('TOT2') if 'TOT2' in RREC else None,
                           model=dict(projection=f"{lam:.2f} goals", hit_pct=round(100*prob, 1) if prob else None, needed_pct=round(100*be(pk['price']), 1), edge=round(100*(prob - be(pk['price'])), 1) if prob else None),
                           last5=dict(line=pk['line'], last5_away=[z['gf']+z['ga'] for z in l5a], last5_home=[z['gf']+z['ga'] for z in l5h], label='game totals'))
                tot_pick = (f"{D}_{k}_tot2", doc)
            else:
                doc = dict(common, market='1st period total', category='Game prop', sub_market='1st period total', pick=f"1P {ws} {pk['line']:g}", line=pk['line'], tier=pk['tier'], strength=pk['tier'], tier_basis=f"signal lead {lead} (the totals lead TOT2 fades)", side=ws,
                           reasons=[dict(label='1st period over with TOT2 Over', detail=f"TOT2 takes the Over in this game; the 1st period Over {pk['line']:g} went 123-74 +16.2u at the SBR close this season", points=None, source='P1O')],
                           against=[], rule_record=rule_record('P1O') if 'P1O' in RREC else None,
                           model=dict(projection=None, needed_pct=round(100*be(pk['price']), 1)),
                           last5=dict(line=pk['line'], last5_away=[z.get('p1', None) for z in l5a], last5_home=[z.get('p1', None) for z in l5h], label='1st period goals'))
        else:
            tf_, ta_, _ = reasons(r.get('T', []), 'O'); prob = est_of(f"Over {c['line']:g}")
            tr = RL.tier(r['tc']['O'] + 2 - r['tc']['U'])
            doc = dict(common, market='Total', pick=f"Over {pk['line']:g}", line=pk['line'], tier=tr, strength=tr, side='Over', projected=round(prob, 3) if prob else None,
                       reasons=[dict(label='Division matchup', detail=f"{c['div_a']} vs {c['div_h']}", points=2, source='TOT1')] + tf_, against=ta_, rule_record=rule_record('TOT1'),
                       model=dict(projection=f"{lam:.2f} goals", hit_pct=round(100*prob, 1) if prob else None, needed_pct=round(100*be(pk['price']), 1), edge=round(100*(prob - be(pk['price'])), 1) if prob else None),
                       last5=dict(line=pk['line'], last5_away=[z['gf']+z['ga'] for z in l5a], last5_home=[z['gf']+z['ga'] for z in l5h], label='game totals'))
            tot_pick = (f"{D}_{k}_tot1", doc)
        if common.get('shadow'):
            doc['note'] = (f"Would-be pick: the {doc.get('tier')} tier of {rid} is turned off (its real picks are red, season to date; Nov 11 policy); logged and graded, not shown as a pick." if pk.get('rule_status') == 'on'
                           else f"Would-be pick: {rid} is switched off (season to date is red); logged and graded, not shown as a pick.")
        PICKDOCS.append((f"{D}_{k}_{SUFX[rid]}", doc))
    # ---- props
    pr = R.props(g); plist = []
    for (tm, pl, mkt, line, price, book, src) in R.PRICED:
        if tm not in (a, h): continue
        p = next((y for y in pr if y['team'] == tm and y['s']['n'] == pl), None)
        if not p: continue
        q = R.prop_grade(p, mkt, line, price)
        stat = {'sog': 'shots', 'pts': 'points', 'pts2': 'points', 'goal': 'goals'}[mkt]
        lab = {'sog': f'o{line:g} SOG', 'pts': 'o0.5 points', 'pts2': '2+ points', 'goal': 'anytime goal'}[mkt]
        logs = PL5.get((tm, pl))
        idx = {'shots': 1, 'goals': 2}.get(stat)
        l5 = None
        slog = None
        if logs:
            slog = [z[1] for z in logs] if stat == 'shots' else ([z[2] for z in logs] if stat == 'goals' else [z[2]+z[3] for z in logs])
            l5 = slog[-5:]
        pass
        hit5 = (f"{sum(v > line for v in l5)} of 5 over") if l5 else None
        grade = q['call'] if q['call'] in ('LEAN',) else ('PLAY' if q['call'] == 'PLAY' else 'pass')
        proj = p['ls'] if stat == 'shots' else (p['lp'] if stat == 'points' else None)
        ent = dict(player=pl, team=tm, stat=stat, market_label=lab, line=line, side='Over', price=price, book=book, proj=round(proj, 2) if proj else None,
                   hit_pct=round(100*q['est'], 1), needed_pct=round(100*be(price), 1), edge=round(q['edge'], 1), grade=grade, conf=q['conf'], basis=q['basis'],
                   last5=l5, last5_label={'shots': 'shots on goal', 'points': 'points', 'goals': 'goals'}[stat], hit5=hit5,
                   avg5=round(sum(l5)/5, 2) if l5 else None,
                   season_log=slog, season_hit=(f"{sum(v > line for v in slog)} of {len(slog)} over" if slog else None), season_avg=round((p['s']['sh'] if stat == 'shots' else (p['s']['p'] if stat == 'points' else p['s']['g']))/p['n'], 2))
        if grade in ('LEAN', 'PLAY'):
            suf = '_' + mkt if sum(1 for y in R.PROPPICKS if y[0] == k and y[3]['pl'] == pl) > 1 else ''
            did = f"{D}_{k}_prop_{re.sub(r'[^A-Za-z0-9]', '', __import__('unicodedata').normalize('NFKD', pl).encode('ascii', 'ignore').decode())}{suf}"
            ent['doc_id'] = did
            pdoc = dict(date=D, game=f'{a} @ {h}', away=a, home=h, time=G[k][2], market='Prop', pick=f"{pl} {lab}", player=pl, team=tm, stat=stat, side='Over',
                        line=line, price=price, book=book, tier=grade, conflicting=False, projected=round(q['est'], 3), result='pending', final='', tracking=(grade == 'LEAN' or prop_rule_record(stat)['status'] == 'off'), sport='nhl',
                        reasons=[dict(label='Card prop model', detail=q['basis'], points=None, source='NHL API game logs')],
                        against=([dict(label='Low confidence', detail='Record and rate disagree by 8+ points or fewer than 9 games, so the card cannot call it a Play.', source='Card prop model')] if q['conf'] == 'LOW' else []),
                        rule_record=prop_rule_record(stat),
                        model=dict(projection=ent['proj'], hit_pct=ent['hit_pct'], needed_pct=ent['needed_pct'], edge=ent['edge']),
                        last5=dict(values=l5, line=line, label=ent['last5_label']) if l5 else dict(values=[], line=line, note='game log not pulled'),
                        season_log=slog, season_hit=ent['season_hit'],
                        experts=[e for e in EXP.get(k, []) if e['market'] == 'Prop' and pl.split('.')[-1] in e['pick']],
                        note=('Prop Lean: logged as tracking only (props are a Play or nothing on the page).' if grade == 'LEAN' else ('Prop Play: card prop pick.' if prop_rule_record(stat)['status'] == 'on' else 'Prop Play on a switched off prop rule: logged as tracking only.')))
            PICKDOCS.append((did, pdoc))
        plist.append(ent)
    # ---- game doc
    gA, gH = R.gl(g, 'A'), R.gl(g, 'H')
    fA, agA, _ = reasons(r['S'], r['side'])
    tside = r.get('tside', 'U')
    tf, tag_, _ = reasons(r.get('T', []), tside)
    ml_none = ((x['ml'].get('why') or '') + ' Would-be pick ' + side_pick[1]['pick'] + ' ' + fmt(side_pick[1]['price']) + ' is tracked, not shown.') if side_pick else x['ml'].get('why')
    def _card(p, lab): return dict(pick=p[1]['pick'], price=p[1]['price'], tier=p[1]['tier'], rule_label=lab, doc_id=p[0])
    doc = dict(sport='nhl', date=D, time=G[k][2], kickoff_label=DOW + ' ' + G[k][2], status='scheduled', away=team(a, g['A'], 'A', gA), home=team(h, g['H'], 'H', gH),
               venue=g['venue'], neutral=False, conference_game=STROWS[a]['conf'] == STROWS[h]['conf'], division_game=STROWS[a]['div'] == STROWS[h]['div'],
               lines=dict(book='texas222', read_at=READ_AT, spread_label='Puck line', periods=pperiods(a, h),
                          spread=dict(away=f"{fmt(la['pl'][0]) if la['pl'][0] < 0 else '+'+str(la['pl'][0])} {fmt(la['pl'][1])}", home=f"{'+' if lh['pl'][0] > 0 else ''}{lh['pl'][0]} {fmt(lh['pl'][1])}"),
                          moneyline=dict(away=fmt(la['ml']), home=fmt(lh['ml'])),
                          total=dict(over=f"{c['line']:g} {fmt(c['tprice'][0])}", under=f"{c['line']:g} {fmt(c['tprice'][1])}"),
                          openers=f"Action Network open: {a} {fmt(an['ml_open'][0])} / {h} {fmt(an['ml_open'][1])}, total {an['tot_open']:g}",
                          draftkings=dict(moneyline=dict(away=fmt(dk['ml'][0]), home=fmt(dk['ml'][1])), puck_line=f"{a} {'+' if dk['pl'][0] > 0 else ''}{dk['pl'][0]} {fmt(dk['pl'][1])} / {h} {fmt(dk['pl'][2])}", total=f"{dk['total'][0]:g} o{fmt(dk['total'][1])} u{fmt(dk['total'][2])}"),
                          other_markets=[dict(market=y['m'], price=y['ps'], est=round(100*y['est'], 1), break_even=round(100*be(y['price']), 1), edge=round(y['edge'], 1), grade=R.PRICEL[y['call']], conf=y['conf'], basis=re.sub('<[^>]+>', '', y['why'])) for y in graded]),
               model=dict(proj_goals={a: round(g['lamA'], 2), h: round(g['lamH'], 2)}, our_total=f"{lam:.2f}", win_pct_home=round(100*g['pH'], 1), win_pct_away=round(100*g['pA'], 1),
                          blended_win_pct_home=round(100*c['estH'], 1), sportradar_win_pct={h: g['sr']} if g['sr'] else None,
                          pl_cover_pct_home_minus1_5=round(100*g['pH2'], 1), over_pct=round(100*over, 1),
                          expected_shots={a: round(g['shotsA'], 1), h: round(g['shotsH'], 1)},
                          venue_factors=dict(home=round(g['vH'], 3), away=round(g['vA'], 3)),
                          note=f"Goalies faced: {a} shoots on {gH[0]} {gH[3]:.3f} · {h} shoots on {gA[0]} {gA[3]:.3f}" + (f" · {a} on a back-to-back (x0.97)" if g['A']['rest'] == 0 else '') + (f" · {h} on a back-to-back (x0.97)" if g['H']['rest'] == 0 else '')),
               splits=[dict(market='Moneyline', opener=f"{fmt(an['ml_open'][0])}/{fmt(an['ml_open'][1])}", away_or_over=dict(tickets=an['bets'], money=an['money'], tags=[n_ for n_, s_ in an['sig_ml'].items() if s_ == 'A']),
                            home_or_under=dict(tickets=100-an['bets'], money=100-an['money'], tags=[n_ for n_, s_ in an['sig_ml'].items() if s_ == 'H'])),
                       dict(market='Total', opener=f"{an['tot_open']:g}", away_or_over=dict(tickets=an['o_bets'], money=an['o_money'], tags=[n_ for n_, s_ in an['sig_tot'].items() if s_ == 'O']),
                            home_or_under=dict(tickets=(100-an['o_bets']) if an['o_bets'] is not None else None, money=(100-an['o_money']) if an['o_money'] is not None else None, tags=[n_ for n_, s_ in an['sig_tot'].items() if s_ == 'U']))],
               moves=[f"Moneyline: Action Network opened {a} {fmt(an['ml_open'][0])}, now {fmt(la['ml'])} (The Odds API median).", f"Total: opened {an['tot_open']:g}, now {c['line']:g}."],
               picks=dict(side=(_card(side_pick, 'ML1 Signal moneyline') if side_pick and not side_pick[1].get('shadow') else {'none': ml_none, 'shadow_doc_id': side_pick[0] if side_pick else None}),
                          puck_line=(_card(pl_pick, 'PL1 Sharp puck line') if pl_pick and not pl_pick[1].get('shadow') else {'none': (x['pl'].get('why') if x['pl'] else 'No pick'), 'shadow_doc_id': pl_pick[0] if pl_pick else None}),
                          total={'none': x['tot'].get('why') if x['tot'] else 'No pick'} if not (tot_pick and not tot_pick[1].get('shadow')) else dict(pick=tot_pick[1]['pick'], price=tot_pick[1]['price'], tier=tot_pick[1]['tier'], rule_label='TOT1 Division over', doc_id=tot_pick[0])),
               reasons=dict(side=fA, side_against=agA, total=tf, total_against=tag_, side_team=nm[r['side']], total_lean=('Over' if tside == 'O' else 'Under'),
                            total_note='Totals signals are information only; they lost on their own in the review.'),
               signals=[dict(label=s, market=m, to=(nm.get(sd) or ('Over' if sd == 'O' else 'Under')), weight=('+'+str(p)) if p else 'info', detail=n) for s, m, sd, p, n in r['S'] + r.get('T', [])],
               trends=dict(away=trend(a, g['A']), home=trend(h, g['H'])),
               props=plist, experts=exp_ranked(k), injuries=INJ.get(k, []),
               notes=[f"Audit ({s_}): {w_}" for c_, s_, w_ in R.NOTES.get(k, [])] + [f"Goalies: {gA[0]} ({gA[1]}) vs {gH[0]} ({gH[1]})", 'texas222 posts no NHL player props; prop prices are from the book named on each prop'],
               source_read=f"Goalies: {gA[0]} ({gA[1]}) vs {gH[0]} ({gH[1]}) · NHL API and ESPN files from the cfb-card repo (6:30 AM pull); {READ_AT}; Action Network and goalies about 6:55 to 7:00 AM Phoenix")
    put('sports/nhl/games', f'{D}_{k}', doc)
    # inputs doc (pick-time inputs) to the hub
    put('sports/nhl/inputs', f'{D}_{k}', dict(date=D, game=f'{a} @ {h}', away=a, home=h, time=G[k][2], read_time=R.READ_TIME, action_network=an, draftkings=dk,
        texas222=dict(ml=[c['mla'], c['mlh']], pl=c.get('pl'), total=c.get('line'), total_prices=list(c['tprice'])),
        goalies=dict(away=[G[k][4], G[k][5]], home=[G[k][6], G[k][7]]), injuries_out={t: [list(p_) for p_ in M.OUT.get(t, [])] for t in (a, h)},
        signals=[[s_, m_, sd_, p_] for s_, m_, sd_, p_, n_ in r['S'] + r.get('T', [])], side=r['side'], lead=r['ml_lead'],
        div=[c['div_a'], c['div_h'], r.get('div_pts', 0)], rule_picks=[[p['rule'], p['version'], p['side'], p['price'], p['status']] for p in x['rp']],
        rules={kk: [RL.RULES[kk]['status'], RL.RULES[kk]['version']] for kk in RL.ORDER}))
for did, doc in PICKDOCS:
    put('sports/nhl/picks', did, doc)

# ---------- yesterday's game docs to final (11 games)
FIN = {}
for ln in open(os.path.join(HERE, 'review', 'ng.txt')).read().split('\n'):
    f = ln.split('|')
    if len(f) > 6 and f[1] == YD[5:]: FIN[f'{f[2]}-{f[3]}'] = (f[2], int(f[4]), f[3], int(f[5]), f[6])
VERS = json.load(open(os.path.join(WK, 'gver.json')))
for k, (a, ag, h, hg, lp) in FIN.items():
    if f'{YD}_{k}' not in VERS: continue   # CAR-SEA had no game doc (written separately as final)
    put('sports/nhl/games', f'{YD}_{k}', dict(status='final', final=f"{a} {ag}, {h} {hg}" + ('' if lp == 'REG' else f' ({lp})'), final_score={a: ag, h: hg}, final_period=lp), op='update', ver=VERS[f'{YD}_{k}'])

json.dump(W, open(os.path.join(HERE, 'hub_writes.json'), 'w'), indent=0)
print(len(W), 'writes'); print(collections.Counter(w['collection'] for w in W))
print([d for d, _ in PICKDOCS])
json.dump(dict(RREC={k: dict(season=v['season'], month=v['month'], l3w=v['l3w'], card=v['card']) for k, v in RREC.items()}, PCAT=PCAT), open(os.path.join(HERE, 'recs.json'), 'w'), indent=1)
