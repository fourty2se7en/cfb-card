"""Season Cards hub docs for the NFL run: enrich seed pick docs (season-cards pick details, one tier scale),
shadow picks for inactive rules, game docs, standings. Writes JSON files under hub_out/ for ArtifactData batches.
Usage: python3 hub_build.py <hubfull dir> [only_times comma list]"""
import json, sys, glob, os, re, math, pathlib, datetime as dt
from zoneinfo import ZoneInfo
import pandas as pd, nflreadpy as nfl
import props_rules as PR

D = pathlib.Path(__file__).parent
HUB = pathlib.Path(sys.argv[1])
OUT = D/'hub_out'; OUT.mkdir(exist_ok=True)
for sub in ('picks', 'picks_bg', 'games', 'standings'): (OUT/sub).mkdir(exist_ok=True)
PHX = ZoneInfo('America/Phoenix'); NOW = dt.datetime.now(PHX)
PULLED = NOW.strftime('%Y-%m-%d ~%-I:%M %p Phoenix')
S = json.load(open(D/'slate.json')); SIG = json.load(open(D/'signals.json'))
PRJ = json.load(open(D/'hist/props_recheck.json'))
PER = json.load(open(D/'t222_periods.json'))['games']
EXM = json.load(open(D/'experts_an_meta.json'))
TODAY = os.environ.get('PICK_DATE') or NOW.strftime('%Y-%m-%d')
NAMES = {'ARI': 'Arizona Cardinals', 'ATL': 'Atlanta Falcons', 'BAL': 'Baltimore Ravens', 'BUF': 'Buffalo Bills', 'CAR': 'Carolina Panthers', 'CHI': 'Chicago Bears',
 'CIN': 'Cincinnati Bengals', 'CLE': 'Cleveland Browns', 'DAL': 'Dallas Cowboys', 'DEN': 'Denver Broncos', 'DET': 'Detroit Lions', 'GB': 'Green Bay Packers',
 'HOU': 'Houston Texans', 'IND': 'Indianapolis Colts', 'JAX': 'Jacksonville Jaguars', 'KC': 'Kansas City Chiefs', 'LA': 'Los Angeles Rams', 'LAC': 'Los Angeles Chargers',
 'LV': 'Las Vegas Raiders', 'MIA': 'Miami Dolphins', 'MIN': 'Minnesota Vikings', 'NE': 'New England Patriots', 'NO': 'New Orleans Saints', 'NYG': 'New York Giants',
 'NYJ': 'New York Jets', 'PHI': 'Philadelphia Eagles', 'PIT': 'Pittsburgh Steelers', 'SEA': 'Seattle Seahawks', 'SF': 'San Francisco 49ers', 'TB': 'Tampa Bay Buccaneers',
 'TEN': 'Tennessee Titans', 'WAS': 'Washington Commanders'}

def dec(m): return 1 + m/100 if m > 0 else 1 + 100/(-m)
def units(price, res): return 0.0 if res == 'push' else ((dec(price) - 1) if res == 'win' else -1.0)
def be_pct(price): return round(100/dec(price), 1) if price else None
def fmt_price(p): return None if p is None else (f'{p:+d}' if isinstance(p, int) else f'{int(p):+d}')

# ---------- hub ledger card records by rule ----------
LED = [json.load(open(f)) for f in glob.glob(str(HUB/'sports/nfl/picks/*.json'))]
LED = [d.get('data', d) for d in LED]
def card_rec(rule):
    g = [d for d in LED if d.get('rule') == rule and d.get('result') in ('win', 'loss', 'push') and not d.get('shadow')]
    if not g: return '0-0 (no graded card picks yet)'
    w = sum(d['result'] == 'win' for d in g); l = sum(d['result'] == 'loss' for d in g); p = sum(d['result'] == 'push' for d in g)
    u = sum(units(d['price'], d['result']) for d in g if d.get('price'))
    return f"{w}-{l}" + (f"-{p}" if p else '') + f" {u:+.2f}u (hub ledger)"

# ---------- schedules: team logs ----------
SCH = nfl.load_schedules([2026]).to_pandas(); SCH = SCH[SCH.game_type == 'REG']
DONE = SCH[SCH.result.notna()].sort_values('gameday')
def team_games(t):
    out = []
    for r in DONE.itertuples():
        if t not in (r.home_team, r.away_team): continue
        home = t == r.home_team
        pf, pa = (r.home_score, r.away_score) if home else (r.away_score, r.home_score)
        out.append(dict(date=r.gameday, pf=int(pf), pa=int(pa), m=int(pf - pa), tot=int(pf + pa), r='W' if pf > pa else ('L' if pf < pa else 'T')))
    return out
TG = {t: team_games(t) for t in NAMES}

# ---------- player stats ----------
PS = nfl.load_player_stats([2026]).to_pandas(); PS = PS[PS.season_type == 'REG'] if 'season_type' in PS else PS
PS['pn'] = PS.player_display_name.map(PR.pnorm)
COL = {'PASS': 'passing_yards', 'RUSH': 'rushing_yards', 'REC': 'receiving_yards'}
def season_log(player, stat):
    nm = PR.pnorm(PR.PALIAS.get(player, player)) if hasattr(PR, 'PALIAS') else PR.pnorm(player)
    m = PS[PS.pn == nm].sort_values('week')
    if not len(m): m = PS[PS.pn == PR.pnorm(player)].sort_values('week')
    return [int(v) for v in m[COL[stat]].fillna(0).tolist()]

# ---------- experts ----------
def exp_url(name, pick):
    nm = name.replace(' (Action Network)', '')
    for e in EXM:
        if e['name'] == nm and e['pick'] == pick: return e['url'], e['record']
    for e in EXM:
        if e['name'] == nm: return e['url'], e['record']
    return None, None
def experts_for(g, market=None):
    out = []
    for e in g.get('experts') or []:
        mk = {'spread': 'Spread', 'total': 'Total', 'moneyline': 'Moneyline'}.get(e['market'], e['market'])
        if market and mk != market: continue
        url, rec = exp_url(e['name'], e['pick'])
        plat = e.get('src') or 'Action Network'
        m = re.search(r'([+-]\d{3})$', e['pick']); price = int(m.group(1)) if m else None
        lm = re.search(r'([+-]?\d+(?:\.\d+)?)(?=[+-]\d{3}$)', e['pick'].split(' ', 1)[-1]) if ' ' in e['pick'] else None
        d = dict(name=e['name'].replace(' (Action Network)', ''), platform=plat, pick=e['pick'], market=mk, side=e.get('side'),
                 line=lm.group(1) if lm else None, price=price, units=None,
                 record=rec or (f"{e.get('rec30')} last 30 days" if e.get('rec30') else None),
                 card_record=e.get('rec'), pulled_at=PULLED)
        if url: d['url'] = url
        out.append({k: v for k, v in d.items() if v is not None})
    return out

# ---------- reasons and tier ----------
SRC = {'sharp_action': 'Action Network', 'big_money': 'Action Network', 'pro_systems': 'Action Network', 'money_vs_tickets': 'Action Network',
       'fade_public': 'Action Network', 'rlm': 'Action Network + DraftKings', 'moved_down': 'Action Network + DraftKings', 'pr_fade': 'NFL.com power rankings',
       'expert_follow': 'Action Network experts', 'expert_any': 'Action Network experts', 'div_dog': 'nflverse schedule', 'wind': 'Open-Meteo',
       'dome_over': 'nflverse schedule', 'projection': 'Card model', 'an_model': 'Action Network', 'intl_fav': 'nflverse schedule'}
def items(lst):
    out = []
    for z in lst or []:
        p = z.get('pts')
        out.append(dict(label=z['label'], detail=z.get('detail', ''), points=(p if p else None), source=SRC.get(z.get('key'), 'Card signals')))
    return out
def tier_of(reasons, against):
    f = sum(r['points'] for r in reasons if r['points']); a = sum(r['points'] for r in against if r['points'])
    lead = f - a
    return ('Strong' if lead >= 4 else 'Solid' if lead >= 2 else 'Lean'), f"signal lead {lead} (for {f}, against {a})"

def last3(halves):
    m = re.search(r'last 3 wk ([^·]+)', halves or ''); return m.group(1).strip() if m else None
def month(halves, mon='Nov'):
    m = re.search(mon + r' ([^·]+)', halves or ''); return m.group(1).strip() if m else None

def last5_for(market, a, h, line):
    A, H = TG[a][-5:], TG[h][-5:]
    if market == 'Total': return dict(label='game totals', last5_away=[x['tot'] for x in A], last5_home=[x['tot'] for x in H], line=line)
    if market == 'Spread': return dict(label='margins', last5_away=[x['m'] for x in A], last5_home=[x['m'] for x in H], line=line)
    return dict(label='results, points for and against', last5_away=[dict(date=x['date'], r=x['r'], pf=x['pf'], pa=x['pa']) for x in A],
                last5_home=[dict(date=x['date'], r=x['r'], pf=x['pf'], pa=x['pa']) for x in H], line=None)

GAMES = {f"{g['away']}-{g['home']}": g for g in S['games']}
def gkey(doc): return f"{doc['away']}-{doc['home']}"

def enrich_game_pick(doc):
    g = GAMES[gkey(doc)]
    kind = 'total' if doc['market'] == 'Total' else 'side'
    pk = next(p for p in g['picks'] if p['kind'] == kind)
    if kind == 'side':
        t = pk['team']; o = g['home'] if t == g['away'] else g['away']
        ml = doc['market'] == 'Moneyline'
        rs = items(g['sig_side'].get(t, []) + (g['sig_ml'].get(t, []) if ml else []))
        ag = items(g['sig_side'].get(o, []) + (g['sig_ml'].get(o, []) if ml else []))
    else:
        rs, ag = items(pk.get('why')), items(pk.get('against'))
    tier, basis = tier_of(rs, ag)
    doc['rule_tier'] = doc.get('tier'); doc['tier'] = tier; doc['tier_basis'] = basis
    doc['reasons'] = rs; doc['against'] = ag
    doc['rule_record'] = {k: v for k, v in dict(rule=pk.get('rule_label'), every_game=pk.get('rule_rec'), month=month(pk.get('rule_halves')),
                          last_3_weeks=last3(pk.get('rule_halves')), card=card_rec(doc['rule'])).items() if v}
    mp = pk.get('model_p'); need = be_pct(doc['price']) if doc.get('price') else None
    if kind == 'total': proj = f"our total {g['our_total']}"
    else:
        om = g['our_margin']; proj = f"our number {g['home']} {(-om if om else 0):+.1f}"
    doc['model'] = {k: v for k, v in dict(projection=proj, hit_pct=round(mp*100, 1) if mp else None, needed_pct=need,
                                          edge=round(mp*100 - need, 1) if mp and need else None).items() if v is not None}
    doc['last5'] = last5_for(doc['market'], doc['away'], doc['home'], doc.get('line'))
    doc['experts'] = experts_for(g, doc['market'] if doc['market'] != 'Moneyline' else None) if doc['market'] != 'Moneyline' else \
        [e for e in experts_for(g) if e['market'] in ('Moneyline', 'Spread')]
    doc['sport'] = 'nfl'; doc['side'] = pk.get('team')
    return doc

PRK = PRJ.get('records', {})
def prop_rule_record(cat, et):
    r = (PRK.get(cat) or {}).get(et) or {}
    def t(x):
        if not x or not x.get('n'): return None
        return f"{x['W']}-{x['L']}" + (f"-{x['P']}" if x.get('P') else '') + f" {x['units']:+.1f}u"
    return {k: v for k, v in dict(every_game=t(r.get('season')), month=t((r.get('months') or {}).get('Nov')), last_3_weeks=t(r.get('last3'))).items() if v}

PROPS = {(p['away'], p['home'], p['pkey'], p['stat']): p for p in S['props']}
def enrich_prop(doc):
    key = (doc['away'], doc['home'], re.sub(r'[^A-Za-z]', '', doc['player'].title().replace(' ', '')), doc['stat'])
    p = next((x for k, x in PROPS.items() if k[0] == doc['away'] and k[1] == doc['home'] and x['player'] == doc['player'] and x['stat'] == doc['stat']), None)
    log = season_log(doc['player'], doc['stat'])
    doc['season_log'] = log; doc['last5'] = dict(label=f"{doc['stat'].lower()} yards", values=log[-5:], line=doc.get('line'))
    if p:
        doc['model'] = dict(projection=f"{p['proj']} {doc['stat'].lower()} yds", hit_pct=round(p['est']*100, 1), needed_pct=round(p['be']*100, 1), edge=round(p['edge'], 1))
        doc['reasons'] = [dict(label='Projection', detail=f"projects {p['proj']} vs line {doc['line']} ({doc['side']})", points=None, source='Card prop model'),
                          dict(label='Hit record', detail=f"{p['hit']} games on the {doc['side'].lower()} at this line", points=None, source='nflverse player stats')]
        if p.get('other'): doc['reasons'].append(dict(label='Other book', detail=p['other'], points=None, source=doc.get('book')))
    else: doc['reasons'] = []
    doc['against'] = []
    cat = f"{doc['stat']} {doc['side']}"; et = doc.get('edge_tier') or 'LEAN'
    rr = prop_rule_record(cat, et); rr['rule'] = f"{cat.split()[0].title() if False else cat} · " + ('PLAY' if et == 'PLAY' else 'edge 1.5+')
    rr['card'] = card_rec(doc['rule'])
    doc['rule_record'] = rr
    doc['experts'] = []
    doc['sport'] = 'nfl'
    return doc

# ---------- shadow picks ----------
def shadow_docs():
    out = []
    for k, g in GAMES.items():
        if g['started'] or g['date'] != TODAY: continue
        for sh in g.get('shadow') or []:
            a, h = g['away'], g['home']
            if sh['grp'] == 'total':
                sd = sh['pick']; line = g['total']; price = g['over'] if sd == 'Over' else g['under']
                tl = [z for z in g['sig_tot'].get(sd, [])]; ta = [z for z in g['sig_tot'].get('Under' if sd == 'Over' else 'Over', [])]
                market = 'Total'; pick = f"{sd} {line:g}"; mp = g['p_over'] if sd == 'Over' else 1 - g['p_over']; side = sd
            else:
                t, market = sh['pick']; side = t
                line = -g['spread_h'] if t == a else g['spread_h']; price = g['price_a'] if t == a else g['price_h']
                pick = f"{t} {line:+g}"; tl = g['sig_side'].get(t, []); ta = g['sig_side'].get(h if t == a else a, [])
                mp = g['p_home_cover'] if t == h else 1 - g['p_home_cover']
            rs, ag = items(tl), items(ta)
            tier, basis = tier_of(rs, ag)
            rr = (SIG['rules'].get('records') or {}) if isinstance(SIG['rules'], dict) else {}
            doc = dict(sport='nfl', shadow=True, rule=sh['rule'], rule_label=sh['label'], date=g['date'], week=S['week'], game=f"{a} @ {h}", away=a, home=h,
                       time=g['time'], market=market, pick=pick, side=side, price=price, line=line, tier=tier, tier_basis=basis, reasons=rs, against=ag,
                       model=dict(hit_pct=round(mp*100, 1), needed_pct=be_pct(price), edge=round(mp*100 - be_pct(price), 1)),
                       last5=last5_for(market, a, h, line), experts=experts_for(g, market), result='pending', final='', game_id=g['id'],
                       issued=NOW.isoformat(), note=f"Shadow pick: {sh['rule']} is off under the Nov 6 policy; logged and graded, never a card pick.")
            out.append((f"{g['date']}_{a}-{h}_{'total' if market == 'Total' else 'side'}_shadow", doc))
    return out

# ---------- game docs ----------
def per_lines(a, h):
    k = f"{a}@{h}"
    alias = {'LA@WAS': 'LA@WAS'}
    v = PER.get(k)
    return json.loads(json.dumps(v, ensure_ascii=False).replace('\u00bd', '.5').replace(' .5', ' 0.5').replace('+.5', '+0.5').replace('-.5', '-0.5')) if v else None
def team_obj(g, s):
    t = g[s]; st = S['stand'].get(t, {})
    return {k: v for k, v in dict(code=t, name=NAMES.get(t, t), short=t, record=f"{st.get('w')}-{st.get('l')}" + (f"-{st['t']}" if st.get('t') else ''),
            conf_record=st.get('confrec'), venue_record=(st.get('road') + ' road') if s == 'away' else (st.get('home') + ' home') if st else None,
            conference=(st.get('div') or ' ').split()[0], division=st.get('div'), rank=st.get('rank'), rank_label=f"Power #{st.get('rank')}" if st.get('rank') else None,
            color=None, logo=None).items() if v is not None}
def pick_cell(g, kind, docs):
    pk = next((p for p in g['picks'] if p['kind'] == kind), None)
    if not pk or pk.get('text') in (None, 'No pick'):
        return {'none': (pk or {}).get('reason') or 'no rule fits'}
    did = f"{g['date']}_{g['away']}-{g['home']}_{kind}"
    d = docs.get(did)
    return {k: v for k, v in dict(pick=pk['text'], price=pk['price'], tier=(d or {}).get('tier'), rule_label=pk.get('rule_label'), doc_id=did if d else None).items() if v is not None}
def prop_rows(g, seeded):
    out = []
    for p in S['props']:
        if p['away'] != g['away'] or p['home'] != g['home']: continue
        log = season_log(p['player'], p['stat'])
        grade = 'held' if p.get('blocked') else (p['tier'] if p.get('shown') and p['tier'] == 'PLAY' else ('PLAY' if p.get('shown') else 'LEAN'))
        did = f"{g['date']}_{g['away']}-{g['home']}_prop_{p['pkey']}_{p['stat']}"
        r = dict(player=p['player'], team=p['team'], stat=p['stat'], line=p['line'], side=p['side'], price=p['price'], proj=p['proj'],
                 hit_pct=round(p['est']*100, 1), needed_pct=round(p['be']*100, 1), edge=round(p['edge'], 1), grade=grade,
                 last5=log[-5:], last5_label=f"{p['stat'].lower()} yards", hit5=p.get('hit'), avg5=p.get('avg'), season_log=log,
                 season_avg=round(sum(log)/len(log), 1) if log else None, book=p.get('book'))
        if p.get('blocked'): r['held_reason'] = p['blocked']
        if did in seeded: r['doc_id'] = did
        out.append({k: v for k, v in r.items() if v is not None})
    return out
def splits(g):
    an = g.get('an') or {}; pub = an.get('pub') or {}; sh = an.get('sharp') or {}
    out = []
    for mk, lbl in (('SPREAD', 'Spread'), ('ML', 'Moneyline'), ('TOTAL', 'Total')):
        p = pub.get(mk)
        if not p: continue
        codes = sh.get(mk) or []
        nm = {'SA': 'Sharp', 'BM': 'Big money', 'PRO': 'PRO', 'MP': 'Model', 'EXP': 'Experts'}
        ta = [nm[c[:-1]] for c in codes if c.endswith('a') and c[:-1] in nm]; th = [nm[c[:-1]] for c in codes if c.endswith('h') and c[:-1] in nm]
        out.append(dict(market=lbl, opener=p.get('open_a'), away_or_over=dict(tickets=p['bets'], money=p['money'], tags=ta),
                        home_or_under=dict(tickets=100 - p['bets'], money=100 - p['money'], tags=th)))
    return out
def build_game(g, old, docs, seeded):
    a, h = g['away'], g['home']
    d = dict(old or {})
    d.update(sport='nfl', date=g['date'], time=g['time'], kickoff_label=f"{g['day']} {g['time']}", week=S['week'], away=team_obj(g, 'away'), home=team_obj(g, 'home'),
             venue=g.get('stadium'), neutral=bool(g.get('neutral')), conference_game=S['stand'].get(a, {}).get('div', 'x').split()[0] == S['stand'].get(h, {}).get('div', 'y').split()[0])
    FIN = {r.game_id: f"{r.away_team} {int(r.away_score)}, {r.home_team} {int(r.home_score)}" for r in DONE.itertuples()}
    if g['id'] in FIN: d['final'] = FIN[g['id']].replace('JAX ', 'JAX ')
    d['status'] = 'final' if g['id'] in FIN else 'scheduled'
    _unused = 'final' if g.get('result') is not None and not (isinstance(g.get('result'), float) and math.isnan(g['result'])) else 'scheduled'
    if g.get('wx') and g.get('roof') == 'outdoors': d['weather'] = f"{g['wx']['t']:.0f}°F, wind {g['wx']['w']:.0f} mph, rain {g['wx']['p']:.0f}%"
    sp = g['spread_h']
    lines = dict(book=('The Odds API median of books' if g.get('book') in ('texas222', 'The Odds API median of books') else 'nflverse consensus (no Odds API line)'), read_at=NOW.strftime('%-I:%M %p'), spread=dict(away=f"{-sp:+g} {g['price_a']:+d}".replace('+0 ', 'PK '), home=f"{sp:+g} {g['price_h']:+d}".replace('+0 ', 'PK ')),
                 moneyline=dict(away=fmt_price(g['ml_a']), home=fmt_price(g['ml_h'])), total=dict(over=f"{g['total']:g} {g['over']:+d}", under=f"{g['total']:g} {g['under']:+d}"))
    op = g.get('openers') or {}
    if op: lines['openers'] = f"Action Network {h} {op.get('an_sp_h') if op.get('an_sp_h') is not None else '?'} / total {op.get('an_tot')}; DraftKings {h} {op.get('dk_sp_h')} / total {op.get('dk_tot')}"
    pl = per_lines(a, h)
    if pl: lines['periods'] = pl
    if g.get('dk'): lines['draftkings_now'] = f"{h} {g['dk'].get('sp_h')}, total {g['dk'].get('tot')}, moneyline {g['dk'].get('ml_a')} / {g['dk'].get('ml_h')}"
    d['lines'] = lines
    om = g['our_margin']
    d['model'] = dict(our_spread=f"{h} {(-om):+.1f}" if om is not None else None, our_total=f"{g['our_total']}", win_pct_home=round(g['p_home_win']*100),
                      cover_pct_home=round(g['p_home_cover']*100), over_pct=round(g['p_over']*100), margin_exact={'3': round(g['key3']*100, 1), '7': round(g['key7']*100, 1)},
                      adjustments=f"home field {g['hfa']:+.1f}, rest {g['rest_adj']:+.2f}, QB {g['qb_adj']:+.1f}, roster moves {g.get('roster_adj', 0):+.2f} (total {g.get('roster_tot_adj', 0):+.2f}), weather {g['wx_adj']:+.1f}",
                      elo_check=f"{h} {(-g['elo_margin']):+.1f}" if g.get('elo_margin') is not None else None, sims=20000)
    d['splits'] = splits(g)
    mv = []
    if g.get('move_h'): mv.append(f"Spread opener to now: {h} {g.get('open_spread_h'):+g} to {sp:+g}")
    if g.get('open_total') is not None and g['open_total'] != g['total']: mv.append(f"Total opener to now: {g['open_total']:g} to {g['total']:g}")
    d['moves'] = mv
    d['picks'] = dict(side=pick_cell(g, 'side', docs), total=pick_cell(g, 'total', docs)) if g['date'] == TODAY or g['started'] else \
        dict(side={'none': f"Picks post on game day ({g['day']} {g['date'][5:]})."}, total={'none': f"Picks post on game day ({g['day']} {g['date'][5:]})."})
    if g['started']:
        # a started game keeps what was issued: the hub ledger has no pick for it, so the old doc's picks stand
        d['picks'] = (old or {}).get('picks') or {'side': {'none': 'Started before this run; no pick issued.'}, 'total': {'none': 'Started before this run; no pick issued.'}}
        if 'Picks post on game day' in json.dumps(d['picks']):
            d['picks'] = {'side': {'none': 'Started before this run; no pick issued.'}, 'total': {'none': 'Started before this run; no pick issued.'}}
        if d['status'] == 'final' and g.get('result') is not None:
            pass
    ps_ = next((p for p in g['picks'] if p['kind'] == 'side'), {}); pt_ = next((p for p in g['picks'] if p['kind'] == 'total'), {})
    t_side = ps_.get('team') or (g.get('rules_in') or {}).get('team')
    _ml = ps_.get('market') == 'Moneyline'
    _o = (h if t_side == a else a) if t_side else None
    d['reasons'] = dict(side=items(g['sig_side'].get(t_side, []) + (g['sig_ml'].get(t_side, []) if _ml else [])) if t_side else [], side_against=items(g['sig_side'].get(_o, []) + (g['sig_ml'].get(_o, []) if _ml else [])) if t_side else [],
                        total=items(pt_.get('why')) if pt_.get('why') else items(g['sig_tot'].get('Over', [])),
                        total_against=items(pt_.get('against')) if pt_.get('against') else items(g['sig_tot'].get('Under', [])))
    d['experts'] = experts_for(g)
    inj = []
    for s_, kk in ((a, 'a'), (h, 'h')):
        for z in g.get('inj_' + kk) or []: inj.append(dict(team=s_, player=z['name'], pos=z['pos'], status=z['status'], note=z.get('inj')))
    d['injuries'] = inj
    d['props'] = prop_rows(g, seeded)
    notes = []
    if g.get('div_game'): notes.append('Division game')
    if g.get('key3') is not None: notes.append(f"Simulated margin lands on 3 in {g['key3']*100:.1f}% and on 7 in {g['key7']*100:.1f}% of 20,000 runs")
    if g.get('started') and d['status'] != 'final': notes.append('In progress at the run (picks frozen as issued).')
    d['notes'] = notes
    d.pop('props_note', None)
    return {k: v for k, v in d.items() if v is not None}

def standings():
    groups = []
    divs = sorted(set(v['div'] for v in S['stand'].values()))
    for dv in divs:
        rows = sorted([v for v in S['stand'].values() if v['div'] == dv], key=lambda v: (-v['pct'], -(v['pf'] - v['pa'])))
        groups.append(dict(name=dv, kind='division', columns=['W', 'L', 'T', 'PF', 'PA', 'Diff', 'Home', 'Road', 'Div', 'Conf', 'Streak', 'Last 5', 'Rating', 'Rank', 'Elo'],
                           rows=[dict(team=NAMES.get(v['team'], v['team']), code=v['team'], values={'W': v['w'], 'L': v['l'], 'T': v['t'], 'PF': v['pf'], 'PA': v['pa'],
                                 'Diff': v['pf'] - v['pa'], 'Home': v['home'], 'Road': v['road'], 'Div': v['divrec'], 'Conf': v['confrec'],
                                 'Streak': (f"W{v['strk']}" if v['strk'] > 0 else f"L{-v['strk']}" if v['strk'] < 0 else '-'), 'Last 5': v['last5'],
                                 'Rating': v['rating'], 'Rank': v['rank'], 'Elo': v['elo']}, mark=None) for v in rows]))
    return dict(sport='nfl', updated=TODAY, title_label=None, groups=groups)

if __name__ == '__main__':
    only = set(sys.argv[2].split(',')) if len(sys.argv) > 2 and sys.argv[2] else None
    docs = {}
    for f in sorted(glob.glob(str(D/'seed/*.json'))):
        d = json.load(open(f)); did = os.path.basename(f)[:-5]
        if only and d['time'] not in only: continue
        docs[did] = enrich_prop(d) if d['market'] == 'Prop' else enrich_game_pick(d)
        json.dump(docs[did], open(OUT/'picks'/f'{did}.json', 'w'), default=str)
    bg = {}
    for f in sorted(glob.glob(str(D/'seed_bg/*.json'))):
        d = json.load(open(f)); did = os.path.basename(f)[:-5]
        if only and d['time'] not in only: continue
        bg[did] = enrich_prop(d); json.dump(bg[did], open(OUT/'picks_bg'/f'{did}.json', 'w'), default=str)
    sh = [(i, d) for i, d in shadow_docs() if not only or d['time'] in only]
    for i, d in sh: json.dump(d, open(OUT/'picks'/f'{i}.json', 'w'), default=str)
    seeded = set(docs) | set(bg)
    allseed = set(os.path.basename(f)[:-5] for f in glob.glob(str(D/'seed/*.json'))) | set(os.path.basename(f)[:-5] for f in glob.glob(str(D/'seed_bg/*.json')))
    alldocs = {os.path.basename(f)[:-5]: json.load(open(f)) for f in glob.glob(str(OUT/'picks/*.json'))}
    for g in S['games']:
        gid = f"{g['date']}_{g['away']}-{g['home']}"
        if only and g['time'] not in only: continue
        of = HUB/'sports/nfl/games'/f'{gid}.json'
        old = json.load(open(of)) if of.exists() else None
        old = (old or {}).get('data', old)
        gd = build_game(g, old, alldocs, allseed)
        json.dump(gd, open(OUT/'games'/f'{gid}.json', 'w'), default=str)
    json.dump(standings(), open(OUT/'standings'/'nfl.json', 'w'), default=str)
    print('picks', len(docs), 'bg', len(bg), 'shadow', len(sh), 'games', len(list((OUT/'games').glob('*.json'))))
