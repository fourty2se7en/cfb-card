"""Season Cards hub docs for the CFB card (FBS/FCS): enriched pick docs, game docs, experts, meta, standings.
python3 hubdocs.py  -> /home/claude/cfb/x/out/<collection path>/<doc_id>.json plus batches.json
Uses only what this run pulled (slate_<div>.json, repo/, players_raw.txt, experts.json, hub ledger dump, ruleeval_<div>.json)."""
import json, math, re, glob, os
from pathlib import Path
import numpy as np, pandas as pd
import rules as RU

D = Path(__file__).parent; R = D / 'repo'
X = Path('/home/claude/cfb/x8'); OUT = X / 'out'; HUB = Path('/home/claude/cfb/hubfull')
TODAY = '2026-11-07'; READ_AT = '9:36 AM'; MONTH = 'Nov'
PHX = 'America/Phoenix'
EXP = json.load(open(Path('/home/claude/cfb/x7') / 'experts.json'))
TM = pd.read_csv(R / 'teams.csv'); TM['_k'] = TM.classification.map({'fbs': 0, 'fcs': 1}).fillna(2)
TM = TM.sort_values('_k').drop_duplicates('school').set_index('school')
PR = pd.read_csv(R / 'power_ratings.csv').set_index('team')
G = pd.read_csv(R / 'games.csv'); G = G[(G.season == 2026)].copy()
G['dt'] = pd.to_datetime(G.startDate, utc=True).dt.tz_convert(PHX)
LATE = json.load(open(D / 'finals_late.json')) if (D / 'finals_late.json').exists() else {}
for gid, v in LATE.items():
    m = G.id == int(gid)
    G.loc[m, ['awayPoints', 'homePoints', 'completed']] = [v['a'], v['h'], True]
    G.loc[m, 'awayLineScores'] = str(v['qa']); G.loc[m, 'homeLineScores'] = str(v['qh'])
DONE = G[G.homePoints.notna()].copy()
import ast
def _ls(x):
    try: v = ast.literal_eval(x) if isinstance(x, str) else []
    except Exception: v = []
    return [int(float(i)) for i in v] if isinstance(v, list) else []
NAMES = {}
LN = pd.read_csv(R / 'lines.csv'); LN = LN[LN.season == 2026]
CLOSE = {int(r.id): RU.consensus(r.lines) for r in LN.itertuples()}
WRITES = {}   # (collection, doc_id) -> data


import unicodedata
def slug(s): return re.sub(r'[^A-Za-z0-9]', '', unicodedata.normalize('NFKD', s))
def fp(p): return None if p is None else (f'+{p}' if p > 0 else str(p))
def fl(v): return None if v is None else ('PK' if v == 0 else f'{v:+g}')
def clean(o):
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items() if v is not None}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, np.integer): return int(o)
    if isinstance(o, np.floating): return float(o)
    if isinstance(o, np.bool_): return bool(o)
    return o
def put(col, doc_id, data): WRITES[(col, doc_id)] = clean(data)


# ---------------- team game logs with ATS / OU ----------------
def tlog(team):
    rows = []
    for r in DONE.itertuples():
        if team not in (r.homeTeam, r.awayTeam): continue
        home = r.homeTeam == team
        pf, pa = (r.homePoints, r.awayPoints) if home else (r.awayPoints, r.homePoints)
        c = CLOSE.get(int(r.id), {})
        sp = c.get('spread_h'); line = (sp if home else (-sp if sp is not None else None))
        ats = None if line is None else (1 if pf - pa + line > 0 else (-1 if pf - pa + line < 0 else 0))
        tot = c.get('total'); ou = None if tot is None else (1 if pf + pa > tot else (-1 if pf + pa < tot else 0))
        v = 'neutral' if r.neutralSite else ('home' if home else 'road')
        lf, la = (_ls(r.homeLineScores), _ls(r.awayLineScores)) if home else (_ls(r.awayLineScores), _ls(r.homeLineScores))
        opp = r.awayTeam if home else r.homeTeam
        labs = ['Q1', 'Q2', 'Q3', 'Q4'] + [f'OT{i}' if i > 1 else 'OT' for i in range(1, max(0, len(lf) - 4) + 1)]
        gl = dict(date=r.dt.strftime('%Y-%m-%d'), opp=slug(opp), opp_name=opp, site=('neutral' if r.neutralSite else ('home' if home else 'away')),
                  pf=int(pf), pa=int(pa), ot=len(lf) > 4, spread=(fl(line) if line is not None else None), total=(f"{tot:g}" if tot is not None else None),
                  ats=({1: 'W', -1: 'L', 0: 'P'}[ats] if ats is not None else None), ou=({1: 'O', -1: 'U', 0: 'P'}[ou] if ou is not None else None))
        if lf and la and len(lf) == len(la): gl['periods'] = dict(labels=labs[:len(lf)], **{'for': lf, 'against': la})
        rows.append(dict(dt=r.dt, pf=float(pf), pa=float(pa), ats=ats, ou=ou, v=v, gl=gl))
    return sorted(rows, key=lambda x: x['dt'])
LOGS = {}
def lg(t):
    if t not in LOGS: LOGS[t] = tlog(t)
    return LOGS[t]
def wl(rows, k='m'):
    w = sum(1 for x in rows if x['pf'] > x['pa']); return f"{w}-{len(rows) - w}"
def rec3(rows, key):
    v = [x[key] for x in rows if x[key] is not None]
    if not v: return None
    w, l, p = v.count(1), v.count(-1), v.count(0)
    return f"{w}-{l}" + (f"-{p}" if p else '')
def period(rows):
    if not rows: return None
    ha = []
    for lab in ('home', 'road', 'neutral'):
        s = [x for x in rows if x['v'] == lab]
        if s: ha.append(f"{wl(s)} {lab}")
    return dict(record=wl(rows), ats=rec3(rows, 'ats'), ou=rec3(rows, 'ou'), pf=round(float(np.mean([x['pf'] for x in rows])), 1),
                pa=round(float(np.mean([x['pa'] for x in rows])), 1), home_away=' · '.join(ha), games=len(rows))
WEEK_START = pd.Timestamp('2026-11-02', tz=PHX)
def trend(g, k):
    t = g['away'] if k == 'a' else g['home']; rows = lg(t)
    l5 = rows[-5:]
    st = g.get('streak_' + k) or 0
    hist = dict(season=period(rows), month=period([x for x in rows if x['dt'].strftime('%b') == MONTH]),
                week=period([x for x in rows if x['dt'] >= WEEK_START]), last10=period(rows[-10:]), last5=period(l5))
    return dict(last5=['W' if x['pf'] > x['pa'] else 'L' for x in l5], pf=g.get('ppg_' + k), pa=g.get('papg_' + k),
                last5_scores=[int(x['pf']) for x in l5], last5_allowed=[int(x['pa']) for x in l5],
                last5_totals=[int(x['pf'] + x['pa']) for x in l5], last5_margins=[int(x['pf'] - x['pa']) for x in l5],
                rest_days=g.get('rest_' + k), travel=(f"{g['tz_' + k]} time zone{'s' if g['tz_' + k] != 1 else ''}" if g.get('tz_' + k) is not None else None),
                back_to_back=False, streak=(f"W{st}" if st > 0 else (f"L{-st}" if st < 0 else None)),
                history={k2: v for k2, v in hist.items() if v}, games=[x['gl'] for x in reversed(rows[-10:])])


def team(g, k):
    t = g['away'] if k == 'a' else g['home']
    m = TM.mascot[t] if t in TM.index and isinstance(TM.mascot[t], str) else None
    col = TM.color[t] if t in TM.index and isinstance(TM.color[t], str) and TM.color[t].startswith('#') else None
    vr = g.get('venue_rec_' + k)
    ls = g.get('last_' + k)
    rk = g.get('rank_' + k)
    return dict(code=slug(t), name=f"{t} {m}" if m else t, short=t, mascot=m, record=g.get('rec_' + k), conf_record=g.get('crec_' + k),
                venue_record=(f"{vr} {'home' if k == 'h' else 'road'}" if vr else None), neutral_record=g.get('neutral_rec_' + k),
                conference=g.get('conf_' + k), rank=rk, rank_label=(f"Model #{rk}" if rk else None),
                rating=(f"{g['rating_' + k]:.1f}" if g.get('rating_' + k) is not None else None), talent=g.get('talent_' + k),
                last_season=(f"{ls[1]}-{ls[2]}" if ls else None), color=col, logo=None)

AN_SRC = {'sharp_action', 'big_money', 'pro_systems', 'money_vs_tickets', 'fade_public', 'spread_experts', 'spread_model', 'ml_pro', 'ml_experts', 'ml_model', 'top_experts', 'model_proj', 'moved_down'}
def src(key):
    if key in AN_SRC: return 'Action Network'
    if key == 'rlm': return 'Action Network and CollegeFootballData openers'
    if key in ('short_week', 'last_season', 'fade_recent', 'hot_streak', 'cold_opp', 'form_pd', 'venue_split', 'bye'): return 'CollegeFootballData results'
    if key in ('projection',): return 'cfb-card model'
    if key in ('weather',): return 'cfb-card weather'
    if key in ('qb_out',): return 'Covers and ESPN'
    return 'cfb-card'
def rz(lst, scored=True):
    return [dict(label=x['label'], detail=x.get('detail', ''), points=x['pts'], source=src(x['key'])) for x in lst if (x['pts'] > 0) == scored]


# ---------------- rule records ----------------
def ledger(div):
    out = []
    for f in glob.glob(str(HUB / 'sports' / div / 'picks' / '*.json')):
        d = json.load(open(f)); out.append(d.get('data', d))
    return out
def units(r, p):
    return RU.payout(True if r == 'win' else (False if r == 'loss' else None), p or -110)
def fmtr(w, l, p, u): return f"{w}-{l}" + (f"-{p}" if p else '') + f" {u:+.2f}u"
def card_rec(rows):
    w = sum(r['result'] == 'win' for r in rows); l = sum(r['result'] == 'loss' for r in rows); p = sum(r['result'] == 'push' for r in rows)
    u = sum(units(r['result'], r.get('price')) for r in rows if r['result'] in ('win', 'loss', 'push'))
    return w, l, p, round(u, 2)
RE = {d: json.load(open(D / f'ruleeval_{d}.json')) for d in ('fbs', 'fcs')}
SIG = json.load(open(D / 'signals.json'))
def rerec(div, name, per):
    v = RE[div]['rules'].get(name, {}).get('versions', [{}])[0].get('rec', {}).get(per)
    return v
def l3key(div): return [p for p in RE[div]['periods'] if p.startswith('Last 3')][0]
def rule_record(div, name):
    s = rerec(div, name, 'Season'); l3 = rerec(div, name, l3key(div))
    cr = card_rec([r for r in ledger(div) if r.get('rule') == name and r['market'] != 'Prop'])
    return dict(rule=name, every_game=(f"{s['w']}-{s['l']} {s['units']:+.1f}u" if s else None), card=fmtr(*cr),
                last_3_weeks=(f"{l3['w']}-{l3['l']} {l3['units']:+.1f}u" if l3 and l3['n'] else None))
def prop_cat(div, stat, side):
    rows = [r for r in ledger(div) if r['market'] == 'Prop' and r.get('stat') == stat and r.get('side') == side and r['result'] in ('win', 'loss', 'push')]
    mrows = [r for r in rows if r['date'] >= '2026-11-01']
    return card_rec(rows), card_rec(mrows)


# ---------------- experts ----------------
def experts_for(gkey):
    E = EXP['games'].get(gkey)
    if not E: return []
    out = []
    for e in E['picks']:
        url = E['cbs_url'] if e['platform'] == 'CBS Sports' else E['an_url']
        out.append(dict(name=e['name'], platform=e['platform'], pick=e['pick'], market=e['market'], side=e['side'], line=e['line'] or None,
                        price=e['price'] or None, units=e['units'] or None, record=e['record'], card_record=None, url=url, pulled_at=EXP['pulled_at']))
    # rank: platform record units first (no card records yet), then win rate
    def key(x):
        m = re.search(r'\(([+-][\d.]+)u\)', x['record']); u = float(m.group(1)) if m else -999
        w = re.match(r'(\d+)-(\d+)', x['record']); wr = int(w.group(1)) / max(1, int(w.group(1)) + int(w.group(2))) if w else 0
        return (-u, -wr)
    return sorted(out, key=key)
def exp_match(exps, pick_market, team_or_side=None, player=None):
    if pick_market == 'Prop': return [e for e in exps if e['market'] == 'Prop' and player and player.split()[-1].lower() in e['pick'].lower()]
    if pick_market == 'Total': return [e for e in exps if e['market'].startswith('Total')]
    return [e for e in exps if e['market'].startswith(('Spread', 'Moneyline'))]


# ---------------- build per division ----------------
PL = {}
for line in (D / 'players_raw.txt').read_text().splitlines():
    try: t, n, c, v = line.split('|')
    except ValueError: continue
    PL[(re.sub(r'[^a-z]', '', n.lower()), c)] = [(float(x.split('/')[0]), float(x.split('/')[1])) for x in v.split(',')]
CATS = {'passing yards': ('pass', 0), 'rushing yards': ('rush', 0), 'receiving yards': ('rec', 0), 'passing touchdowns': ('pass', 1)}
def plast(p):
    v = PL.get((re.sub(r'[^a-z]', '', p['player'].lower()), CATS[p['stat']][0]))
    return [x[CATS[p['stat']][1]] for x in v] if v else []

PER = {}
def _pv(x):
    m = re.match(r'(PK|[+-][\d½.]*)\s*([+-]\d+)$', x)
    return f"{'PK' if m.group(1) == 'PK' else m.group(1).replace('½', '.5').replace('+.5', '+0.5').replace('-.5', '-0.5')} {m.group(2)}" if m else None
def _tv(x):
    m = re.match(r'(Ov|Un)([\d½.]+)([+-]\d+)$', x)
    return f"{m.group(2).replace('½', '.5') if m.group(2) != '½' else '0.5'} {m.group(3)}".replace(' ', ' ') if m else None
for fn in ('t222_1h.txt', 't222_q1.txt'):
    if not (D / fn).exists(): continue
    for r in (D / fn).read_text().strip().split(';'):
        p = r.split(',')
        if len(p) < 3: continue
        d_ = {}
        for f in p[2:]:
            if f.startswith(('Ov', 'Un')): d_['to'] = _tv(f)
            elif re.match(r'^[+-]\d+$', f): d_['ml'] = f
            else: d_['sp'] = _pv(f)
        PER[int(p[0])] = d_
stats = {}
for div in ('fbs', 'fcs'):
    S = json.load(open(D / f'slate_{div}.json'))
    gcol = f'sports/{div}/games'; pcol = f'sports/{div}/picks'
    n_games = n_picks = n_exp = 0; prop_play = []
    for g in S['games']:
        gk = f"{slug(g['away'])}-{slug(g['home'])}"; did = f"{g['date']}_{gk}"
        exps = experts_for(gk) if g['date'] == TODAY else []
        sp = g.get('spread_h')
        lines = dict(book=g.get('book') or 'no line yet', read_at=READ_AT if g.get('book') == 'texas222' else None)
        if sp is not None:
            lines['spread'] = dict(away=f"{fl(-sp)} {fp(g.get('price_a'))}", home=f"{fl(sp)} {fp(g.get('price_h'))}")
        if g.get('ml_a') is not None: lines['moneyline'] = dict(away=fp(g['ml_a']), home=fp(g['ml_h']))
        if g.get('total') is not None: lines['total'] = dict(over=f"{g['total']:g} {fp(g.get('over'))}", under=f"{g['total']:g} {fp(g.get('under'))}")
        op = []
        if g.get('open_a') is not None: op.append(f"Action Network {g['away']} {fl(g['open_a'])}")
        if g.get('open_h') is not None: op.append(f"CollegeFootballData {g['away']} {fl(-g['open_h'])}")
        if g.get('tot_open') is not None: op.append(f"total {g['tot_open']:g}")
        if op: lines['openers'] = ' / '.join(op)
        per = {}
        for lab, base in (('1H', 1000), ('Q1', 3000)):
            ra, rh = PER.get(base + int(g.get('rot') or 0)), PER.get(base + int(g.get('rot') or 0) + 1)
            if not ra or not rh or not g.get('rot'): continue
            e = {}
            if ra.get('sp') and rh.get('sp'): e['spread'] = dict(away=ra['sp'], home=rh['sp'])
            if ra.get('to') and rh.get('to'): e['total'] = dict(over=ra['to'], under=rh['to'])
            if ra.get('ml') and rh.get('ml'): e['moneyline'] = dict(away=ra['ml'], home=rh['ml'])
            if e: per[lab] = e
        if per: lines['periods'] = per
        hm = g.get('our_margin')
        model = dict(our_spread=(f"{g['home'] if hm >= 0 else g['away']} {-abs(hm):+.1f}" if hm is not None else None),
                     our_total=(f"{g['our_total']:.1f}" if g.get('our_total') is not None else None),
                     cover_pct_home=(round(100 * g['model_cover_h']) if g.get('model_cover_h') is not None else None),
                     over_pct=(round(100 * g['model_over']) if g.get('model_over') is not None else None),
                     note='cfb-card model, shown for reference and scored 0', source='cfb-card model')
        splits = []
        for mk, lab in (('SPREAD', 'Spread'), ('ML', 'Moneyline'), ('TOTAL', 'Total')):
            P = (g.get('an') or {}).get('pub', {}).get(mk); sh = (g.get('an') or {}).get('sharp', {}).get(mk, [])
            if not P and not sh: continue
            ta = [c[:-1] for c in sh if c.endswith('a')]; th = [c[:-1] for c in sh if c.endswith('h')]
            d_ = dict(market=lab, opener=(P or {}).get('open'), away_or_over=dict(tags=ta), home_or_under=dict(tags=th))
            if P and P.get('bets') is not None:
                d_['away_or_over'].update(tickets=P['bets'], money=P['money']); d_['home_or_under'].update(tickets=100 - P['bets'], money=100 - P['money'])
            splits.append(d_)
        moves = []
        if g.get('open_a') is not None and sp is not None and g['open_a'] != -sp: moves.append(f"Spread opened {g['away']} {fl(g['open_a'])}, now {fl(-sp)}")
        if g.get('tot_open') is not None and g.get('total') is not None and g['tot_open'] != g['total']: moves.append(f"Total opened {g['tot_open']:g}, now {g['total']:g}")
        pk = {}; reasons = {}
        sidep = next((p for p in g['picks'] if p['kind'] == 'side'), None); totp = next((p for p in g['picks'] if p['kind'] == 'total'), None)
        later = g['date'] != TODAY
        def none_txt(kind):
            if g.get('reference_only'): return 'FBS vs FCS game: reference only, no pick.'
            if later: return (f"Line {g['home']} {fl(sp)} · total {g['total']:g}. " if sp is not None and g.get('total') is not None else 'No line posted yet. ') + 'Picks are made on game day.'
            if not g.get('book'): return 'No line posted yet.'
            if kind == 'side': return g.get('nopick') or 'No rule fits.'
            return 'No total rule fits: the two-signal total needs two of money vs tickets, PRO systems and sharp action on one side and none on the other.'
        for kind, p in (('side', sidep), ('total', totp)):
            if p:
                pdid = f"{did}_{'side' if kind == 'side' else 'total'}"
                pk[kind] = dict(pick=p['text'], price=fp(p['price']), tier=p['tier'], rule_label=p['rule_label'], rule=p['rule'], doc_id=pdid, book=p.get('book') or 'texas222')
                reasons[kind] = rz(p['why']); reasons[kind + '_against'] = rz(p['against'])
            else:
                pk[kind] = {'none': none_txt(kind)}
        if not sidep and g.get('sig_side'):
            reasons['side_away'] = rz(g['sig_side'][g['away']]); reasons['side_home'] = rz(g['sig_side'][g['home']])
        if not totp and g.get('sig_tot'):
            reasons['total_over'] = rz(g['sig_tot']['Over']); reasons['total_under'] = rz(g['sig_tot']['Under'])
        # props
        props = []
        for p in (S.get('props') or []):
            if p['away'] != g['away'] or p['home'] != g['home']: continue
            l5 = plast(p)[-5:]
            hold = p.get('blocked')
            grade = 'held' if (p['tier'] and hold) else (p['tier'] or 'pass')
            pd_ = f"{did}_prop_{slug(p['player'])}_{slug(p['stat'])}"
            hit5 = sum(1 for v in l5 if (v > p['line'] if p['side'] == 'Over' else v < p['line']))
            props.append(dict(player=p['player'], team=p['team'], stat=p['stat'], line=p['line'], side=p['side'], price=fp(p['price']), proj=p['proj'],
                              hit_pct=round(100 * p['est'], 1), needed_pct=round(100 * p['be'], 1), edge=f"{p['edge']:+.1f}", grade=grade,
                              held_reason=(hold if grade == 'held' else None), last5=l5, last5_label=p['stat'],
                              hit5=f"{hit5} of {len(l5)} {p['side'].lower()}", avg5=(round(float(np.mean(l5)), 1) if l5 else None),
                              season_avg=p['avg'], record_vs_line=p['hit'], doc_id=(pd_ if grade in ('PLAY', 'LEAN') else None),
                              tracking=(True if grade == 'LEAN' else None)))
        inj = [dict(team=t, player=x['player'], pos=x['pos'], status=x['status'], note=x['note']) for k, t in (('a', g['away']), ('h', g['home'])) for x in (g.get('inj_' + k) or [])]
        wx = g.get('wx')
        notes = []
        if g.get('reference_only'): notes.append('FBS vs FCS: reference only.')
        if g.get('book') and g['book'] != 'texas222' and g['book']: notes.append(f"Line source: {g['book']}.")
        doc = dict(sport=div, date=g['date'], time=g['time'], kickoff_label=f"{g['day']} {g['time']}", week=S['week'], status='scheduled',
                   espn_id=g['id'], away=team(g, 'a'), home=team(g, 'h'), venue=g.get('venue') or None, neutral=g['neutral'], conference_game=g['confgame'],
                   weather=(f"{wx['temp']:.0f}°F, wind {wx['wind']:.0f} mph, rain {wx['precip']}%" if wx else None),
                   lines=lines, model=model, splits=splits or None, splits_tag_key='SA sharp action, BM big money, PRO PRO systems, MP model projection, EXP top experts (MP and EXP shown, not scored)',
                   moves=moves or None, picks=pk, reasons=reasons, trends=dict(away=trend(g, 'a'), home=trend(g, 'h')),
                   props=props or None, props_note=(None if props or div != 'fbs' or later else 'No texas222 props posted for this game.'),
                   experts=exps or None, injuries=inj or None, notes=notes or None)
        put(gcol, did, doc); n_games += 1
        n_exp += len(exps)
        # ---------- pick docs ----------
        if g['date'] != TODAY: continue
        if g.get('started'): continue   # 2nd run: started games keep their picks as logged
        for kind, p in (('side', sidep), ('total', totp)):
            if not p: continue
            fn = D / f'seed_{div}' / f"{did}_{kind}.json"
            d0 = json.load(open(fn))
            a, h = g['away'], g['home']
            if p['market'] == 'Total':
                l5 = dict(last5_away=trend(g, 'a')['last5_totals'], last5_home=trend(g, 'h')['last5_totals'], line=p['line'], label='game totals')
            elif p['market'] == 'Spread':
                l5 = dict(last5_away=trend(g, 'a')['last5_margins'], last5_home=trend(g, 'h')['last5_margins'], line=p['line'], label='margins')
            else:
                ta, th = trend(g, 'a'), trend(g, 'h')
                l5 = dict(last5_away=ta['last5'], last5_home=th['last5'], last5_away_pf=ta['last5_scores'], last5_away_pa=ta['last5_allowed'],
                          last5_home_pf=th['last5_scores'], last5_home_pa=th['last5_allowed'], line=p['price'], label='results')
            mp = p.get('model_p'); be = RU.implied(p['price']) if p.get('price') is not None else None
            d0.update(reasons=rz(p['why']), against=rz(p['against']), rule_record=rule_record(div, p['rule']),
                      model=dict(projection=(model['our_total'] if p['market'] == 'Total' else model['our_spread']),
                                 hit_pct=(round(100 * mp, 1) if mp is not None else None), needed_pct=(round(100 * be, 1) if be else None),
                                 edge=(round(100 * (mp - be), 1) if mp is not None and be else None), note='cfb-card model, scored 0'),
                      last5=l5, experts=exp_match(exps, p['market']), espn_id=g['id'])
            put(pcol, f"{did}_{kind}", d0); n_picks += 1
        for p in (S.get('props') or []):
            if p['away'] != g['away'] or p['home'] != g['home'] or not p['tier'] or p.get('blocked') or p['started']: continue
            k = f"{did}_prop_{slug(p['player'])}_{slug(p['stat'])}"
            d0 = json.load(open(D / f'seed_{div}' / f'{k}.json'))
            (w, l, pu, u), (mw, ml_, mpu, mu) = prop_cat(div, p['stat'], p['side'])
            l5 = plast(p)[-5:]
            d0.update(reasons=[dict(label='Model edge', detail=f"projection {p['proj']:g} vs line {p['line']:g}; {p['hit']} games {p['side'].lower()} the line; est {100*p['est']:.1f}% vs {100*p['be']:.1f}% needed", points=0, source='cfb-card prop model, ESPN box scores')],
                      against=[], rule_record=dict(rule=f"{p['stat'].capitalize()} · {p['side']}", every_game=None, card=fmtr(w, l, pu, u), month=fmtr(mw, ml_, mpu, mu) if (mw + ml_ + mpu) else None, last_3_weeks=None),
                      model=dict(projection=p['proj'], hit_pct=round(100 * p['est'], 1), needed_pct=round(100 * p['be'], 1), edge=round(p['edge'], 1)),
                      last5=dict(values=l5, line=p['line'], label=p['stat']), experts=exp_match(exps, 'Prop', player=p['player']), espn_id=g['id'])
            if p['tier'] == 'LEAN':
                d0['tracking'] = True; d0['tier'] = 'LEAN'
            else:
                prop_play.append(d0)
            put(pcol, k, d0); n_picks += 1
        for e in exps:
            eid = f"{TODAY}_{gk}_{slug(e['name'])}_{slug(e['market'])}"
            put(f'sports/{div}/experts', eid, dict(e, date=TODAY, game=f"{g['away']} @ {g['home']}", away=g['away'], home=g['home'], espn_id=g['id'], result='pending'))
    stats[div] = dict(game_docs=n_games, picks=n_picks, experts=n_exp, plays=len(prop_play))

json.dump({f"{c}|{d}": v for (c, d), v in WRITES.items()}, open(X / 'writes.json', 'w'), indent=0, default=str)
print(stats)
