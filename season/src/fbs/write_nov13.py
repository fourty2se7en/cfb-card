"""Nov 11, 2026 run: turn hubdocs11 output (x/writes.json) plus slate_fbs.json into hub batches.
- Card picks: signal lead tier (Strong 4+, Solid 2 to 3, Lean 0 to 1 or behind); a pick is a card pick only when hub meta
  rules[].tiers[tier].on is true (real picks policy, Nov 11). Otherwise it is a would-be pick (shadow true, conflict says why).
- Every other rule fit (g['fits'], B40) is a would-be pick, doc id <game id>_<side|ml|total>_<rule key>.
- Props: a Play in an off prop rule is tracking only; matchup {opp, vs, effect, adj, source} from CFBD season stats (shown only).
- Game docs (every game): qbs, lineups (QBs; skill players with logs for today's games), units (team unit ratings from CFBD
  season stats), model.adjustments, summary/none/analysis per market, market on every reason, line_history, pick_history, changes.
- Preview docs (later games): sports/fbs/preview/<as_of>_<game id>_<market>.
- Nov 10 game docs set final."""
import json, glob, os, re, unicodedata, math
from pathlib import Path
import pandas as pd, numpy as np
D = Path(__file__).parent; X = D / 'x'; GD = D / 'gd13' / 'sports' / 'fbs' / 'games'
AS_OF = '2026-11-13'; READ_AT = '3:07 PM Phoenix'
W = {tuple(k.split('|', 1)): v for k, v in json.load(open(X / 'writes.json')).items()}
S = json.load(open(D / 'slate_fbs.json')); GAMES = {}
def slug(s): return re.sub(r'[^A-Za-z0-9]', '', unicodedata.normalize('NFKD', s))
for g in S['games']: GAMES[f"{g['date']}_{slug(g['away'])}-{slug(g['home'])}"] = g
M = json.load(open(D / 'hub' / 'meta' / 'fbs.json')); M = M.get('data', M); MR = {r['key']: r for r in M['rules']}
SIG = json.load(open(D / 'signals.json'))
INJ = json.load(open(D / 'injuries.json'))
QU = {}
TMID = pd.read_csv(D / 'repo' / 'teams.csv').drop_duplicates('id').set_index('id').school.to_dict()
for l in (D / 'qu_raw6.txt').read_text().splitlines():
    f = l.split('|')
    if len(f) >= 4 and int(f[0]) in TMID:
        QU[TMID[int(f[0])]] = dict(qb1=f[1], share=float(f[2]), last=f[3], qb2=(f[4].split(':')[0] if len(f) > 4 and f[4] else None),
                                   qb2_share=(float(f[4].split(':')[1]) if len(f) > 4 and ':' in f[4] else None), qb3=(f[5] if len(f) > 5 and f[5] and f[5] != ' Team' else None))
GP = {tuple(l.split('|')[:2]): float(l.split('|')[2]) for l in (D / 'qb_gp.txt').read_text().splitlines() if l.count('|') == 2}
# ---------- team unit ratings from CFBD season stats (percentile among FBS teams, 0 to 100) ----------
SS = pd.read_csv(D / 'repo' / 'season_stats.csv').pivot_table(index='team', columns='stat', values='value', aggfunc='first')
FBS = set(pd.read_csv(D / 'repo' / 'teams.csv').query("classification == 'fbs'").school)
SS = SS[SS.index.isin(FBS)].astype(float)
U = pd.DataFrame(index=SS.index)
U['Pass offense'] = SS.netPassingYards / SS.passAttempts.clip(lower=1)
U['Run offense'] = SS.rushingYards / SS.rushingAttempts.clip(lower=1)
U['Pass block'] = -(SS.sacksOpponent / (SS.passAttempts + SS.sacksOpponent).clip(lower=1))
U['Pass rush'] = SS.sacks / (SS.passAttemptsOpponent + SS.sacks).clip(lower=1)
U['Pass D'] = -(SS.netPassingYardsOpponent / SS.passAttemptsOpponent.clip(lower=1))
U['Run D'] = -(SS.rushingYardsOpponent / SS.rushingAttemptsOpponent.clip(lower=1))
UP = (U.rank(pct=True) * 100).round().astype('Int64')
RAWU = dict(pass_ypa=SS.netPassingYards / SS.passAttempts.clip(lower=1), rush_ypc=SS.rushingYards / SS.rushingAttempts.clip(lower=1),
            opp_pass_ypg=SS.netPassingYardsOpponent / SS.games.clip(lower=1), opp_rush_ypg=SS.rushingYardsOpponent / SS.games.clip(lower=1),
            sack_rate=SS.sacks / (SS.passAttemptsOpponent + SS.sacks).clip(lower=1), sacked_rate=SS.sacksOpponent / (SS.passAttempts + SS.sacksOpponent).clip(lower=1),
            opp_pass_ypa=SS.netPassingYardsOpponent / SS.passAttemptsOpponent.clip(lower=1), opp_rush_ypc=SS.rushingYardsOpponent / SS.rushingAttemptsOpponent.clip(lower=1))
RANK = {k: v.rank(ascending=(k in ('opp_pass_ypg', 'opp_rush_ypg', 'sacked_rate', 'opp_pass_ypa', 'opp_rush_ypc')), method='min') for k, v in RAWU.items()}
NF = len(SS)
def units(t):
    if t not in UP.index: return None
    note = {'Pass offense': f"{RAWU['pass_ypa'][t]:.1f} net yards per pass",
            'Run offense': f"{RAWU['rush_ypc'][t]:.1f} yards per carry",
            'Pass block': f"sacked on {100 * RAWU['sacked_rate'][t]:.1f}% of dropbacks",
            'Pass rush': f"sacks on {100 * RAWU['sack_rate'][t]:.1f}% of dropbacks",
            'Pass D': f"allows {RAWU['opp_pass_ypa'][t]:.1f} net yards per pass ({RAWU['opp_pass_ypg'][t]:.0f} per game)",
            'Run D': f"allows {RAWU['opp_rush_ypc'][t]:.1f} yards per carry ({RAWU['opp_rush_ypg'][t]:.0f} per game)"}
    return {k: dict(rating=int(UP.loc[t, k]), note=note[k] + ' (team unit, CFBD season stats; percentile among FBS)') for k in UP.columns if pd.notna(UP.loc[t, k])}
def rk(k, t): return int(RANK[k][t]) if t in RANK[k].index else None
# ---------- helpers ----------
def tier_of(reasons, against):
    f = sum(x['points'] for x in reasons if isinstance(x.get('points'), (int, float)))
    a = sum(x['points'] for x in against if isinstance(x.get('points'), (int, float)))
    L = f - a; return ('Strong' if L >= 4 else ('Solid' if L >= 2 else 'Lean')), f"signal lead {L:g} (for {f:g}, against {a:g})"
def tier_state(rule, t):
    T = ((MR.get(rule) or {}).get('tiers') or {}).get(t)
    if T is None: return True, None, None
    r = T.get('real') or T.get('season') or {}
    rec = f"{r.get('w', 0)}-{r.get('l', 0)}" + (f"-{r['p']}" if r.get('p') else '') + f" {r.get('u', 0):+.2f}u"
    return bool(T.get('on')), rec, T.get('pending_on')
AN = {'Sharp action', 'Big money', 'PRO systems', 'Money vs tickets', 'Fade the public', 'Reverse line movement', 'Line moved toward', 'Total moved down', 'Top experts', 'Model projection'}
CTX_KEYS = ('rest', 'less time off', 'last season', 'home', 'road', 'streak', 'form', 'projection', 'travel', 'venue', 'weather', 'conference game', 'qb', 'injur', 'bye', 'record')
def tag_market(items, mk):
    out = []
    for x in items or []:
        x = dict(x); lab = (x.get('label') or '').lower(); src = (x.get('source') or '')
        if 'Action Network' in src and not any(k in lab for k in ('model', 'projection')): x['market'] = mk
        elif mk == 'Total' and any(k in lab for k in ('weather', 'conference game')): x['market'] = 'Total'
        else: x['market'] = 'Game context'
        out.append(x)
    return out
def fl(v): return 'PK' if v == 0 else f"{v:+g}"
def fp(p): return None if p is None else (f"+{int(p)}" if p > 0 else str(int(p)))
def team_line(g, t): return (-g['spread_h'] if t == g['away'] else g['spread_h']) if g.get('spread_h') is not None else None
def proj_side(g):
    hm = g.get('our_margin')
    if hm is None: return None
    return (g['home'], hm) if hm >= 0 else (g['away'], -hm)
def form(g, k): return g.get('last5_' + k, '').split()
def l5(g, k):
    f = form(g, k); return f"{f.count('W')}-{f.count('L')} in its last {len(f)}" if f else None
def qbline(g, t):
    q = QBS.get((g['date'], t))
    if not q: return None
    s = f"{q['name']} ({q['depth']}, {q['status'].lower()})"
    return s
def wxtxt(g):
    wx = g.get('wx')
    if not wx: return None
    return f"forecast {wx['temp']:.0f}°F with {wx['wind']:.0f} mph wind and {wx['precip']}% chance of rain"
def mvt(g):
    if g.get('open_a') is None or g.get('spread_h') is None: return None
    now = -g['spread_h']
    if g['open_a'] == now: return None
    return f"the spread opened {g['away']} {fl(g['open_a'])} and sits at {fl(now)} now"
# ---------- QBs for every game ----------
QBS = {}
def qb_entry(t, date, today):
    u = QU.get(t); items = [x for x in (INJ.get(t) or []) if isinstance(x, dict) and x.get('pos') == 'QB']
    rep = next((x for x in items if x.get('status') == 'AVAILABLE'), None)
    if rep:
        name = rep['player']; conf = rep.get('confirmed')
        depth = 'QB1' if (u and u['qb1'] == name) else ('QB2' if (u and u.get('qb2') == name) else ('QB3' if u and u.get('qb3') == name else 'QB1'))
        st = 'Confirmed' if conf else 'Expected'
        note = rep.get('note', '')
        src = 'Odds API player props posted; ESPN box score attempts' + (' (A18 rule)' if 'A18' in note else '')
    elif u:
        name = u['qb1']; depth = 'QB1'; st = 'Expected'
        note = f"season QB1 by attempts ({round(100 * u['share'])}%)"
        if u['last'] and u['last'] != u['qb1']:
            nm2 = u['last']; d2 = 'QB2' if u.get('qb2') == nm2 else ('QB3' if u.get('qb3') == nm2 else 'QB2')
            note += f"; {nm2} ({d2}) led the last game, so the starter is not settled"
            st = 'Questionable'
        src = 'ESPN box score attempts (no conference availability report read yet; midweek reports post later in the week)'
    else:
        return None
    return dict(name=name, depth=depth, status=st, note=note, source=src)
for g in S['games']:
    for t in (g['away'], g['home']):
        e = qb_entry(t, g['date'], g['today'])
        if e: QBS[(g['date'], t)] = e
# ---------- analysis text (facts only) ----------
def side_case(g, t):
    k = 'a' if t == g['away'] else 'h'; o = g['home'] if k == 'a' else g['away']; ko = 'h' if k == 'a' else 'a'
    ps = proj_side(g); line = team_line(g, t)
    bits = []
    if ps:
        pm = ps[1] if ps[0] == t else -ps[1]
        if line is not None: bits.append(f"Our model has {t} {'winning' if pm > 0 else 'losing'} by {abs(pm):.1f} against a line of {t} {fl(line)}.")
        else: bits.append(f"Our model has {t} {'winning' if pm > 0 else 'losing'} by {abs(pm):.1f}.")
    if g.get('ppg_' + k) is not None:
        bits.append(f"{t} scores {g['ppg_' + k]:.1f} and allows {g['papg_' + k]:.1f} per game ({g.get('rec_' + k)}, {g.get('crec_' + k)} in conference), {l5(g, k)}.")
    if t in UP.index and o in UP.index:
        bits.append(f"{t}'s run game ({RAWU['rush_ypc'][t]:.1f} yards per carry) meets a {o} run defense ranked {rk('opp_rush_ypc', o)} of {NF}, and its passing ({RAWU['pass_ypa'][t]:.1f} per attempt) meets a pass defense ranked {rk('opp_pass_ypa', o)}.")
    q = qbline(g, t)
    if q: bits.append(f"Quarterback: {q}.")
    if g.get('rest_' + k) is not None and g.get('rest_' + ko) is not None and g['rest_' + k] != g['rest_' + ko]:
        bits.append(f"Rest: {g['rest_' + k]} days for {t}, {g['rest_' + ko]} for {o}.")
    return bits
def total_case(g, side):
    a, h = g['away'], g['home']; bits = []
    if g.get('our_total') is not None and g.get('total') is not None:
        bits.append(f"Our model projects {g['our_total']:.1f} points against a total of {g['total']:g}.")
    if g.get('ppg_a') is not None:
        bits.append(f"{a} games average {g['ppg_a'] + g['papg_a']:.1f} points ({g['ppg_a']:.1f} for, {g['papg_a']:.1f} against) and {h} games {g['ppg_h'] + g['papg_h']:.1f} ({g['ppg_h']:.1f} for, {g['papg_h']:.1f} against).")
    if g.get('last3_tot_a') is not None: bits.append(f"Last three games: {a} totals averaged {g['last3_tot_a']:.1f}, {h} {g['last3_tot_h']:.1f}.")
    w = wxtxt(g)
    if w: bits.append(f"Weather: {w}.")
    return bits
def pick_summary(g, p):
    if p['market'] == 'Total':
        side = p['team']; other = 'Under' if side == 'Over' else 'Over'
        allb = total_case(g, side)
        ot = g.get('our_total')
        fb = [b for b in allb if not (ot is not None and 'Our model' in b and ((ot > g['total']) != (side == 'Over')))]
        ab = [b for b in allb if b not in fb]
        if not ab: ab = [f"The case for the {other}: " + (f"our model sits {abs(ot - g['total']):.1f} points {'above' if ot > g['total'] else 'below'} the number. " if ot is not None else '') + "Both offenses have topped this total in recent weeks." if ot is not None and ((ot > g['total']) == (other == 'Over')) else f"The case for the {other}: the market total of {g['total']:g} already prices the matchup, and one long scoring drive changes it."]
        return dict(**{'for': ' '.join(fb[:4]), 'against': ' '.join(ab[:4])})
    t = p['team']; o = g['home'] if t == g['away'] else g['away']
    fb = side_case(g, t); ab = side_case(g, o)
    if p['market'] == 'Moneyline' and p.get('price') is not None and p['price'] > 0:
        fb.append(f"At {fp(p['price'])}, {t} needs to win {100 * 100 / (p['price'] + 100):.0f}% of the time to break even.")
    m = mvt(g)
    if m: fb.append(f"Line move: {m}.")
    return {'for': ' '.join(fb[:5]), 'against': ' '.join(ab[:4])}
def none_side(g):
    if not g['today']: return 'Picks are made on game day. ' + ('At today\'s line no side rule fits.' if not any(p['kind'] == 'side' for p in g.get('preview_picks', [])) else 'At today\'s line a side rule fits (see the preview pick); the pick posts on game day if it still fits.')
    n = g.get('nopick') or 'No side rule fits.'
    n = re.sub(r'\(lead (\d+)\)', '', n)
    n = n.replace('favorite at -620, outside -200 to -100, lead under 5', 'the favorite is priced at -620, longer than the -200 limit, and the signal edge is not big enough for the strong spread rule')
    n = n.replace('underdog at +555 without a line move toward it', 'the underdog is +555, outside the +100 to +200 underdog range, and the line has not moved toward it')
    return re.sub(r'\s+', ' ', n).strip()
def none_total(g):
    if not g['today']: return 'Picks are made on game day. ' + ('At today\'s line no total rule fits.' if not any(p['kind'] == 'total' for p in g.get('preview_picks', [])) else 'At today\'s line a total rule fits (see the preview pick).')
    tS = g.get('sig_tot') or {}
    keys = {'money_vs_tickets', 'pro_systems', 'sharp_action'}
    co = len({x['key'] for x in tS.get('Over', []) if x['key'] in keys}); cu = len({x['key'] for x in tS.get('Under', []) if x['key'] in keys})
    if co and cu: return f"The total signals are split ({co} for the Over, {cu} for the Under), and the total rule needs them clearly on one side."
    if co + cu == 1: return f"Only one of the three total signals (money vs tickets, PRO systems, sharp action) points to the {'Over' if co else 'Under'}, and the total rule needs two."
    return 'None of the total signals (money vs tickets, PRO systems, sharp action) point to either side.'
def analysis_side(g):
    a, h = g['away'], g['home']; ps = proj_side(g); bits = []
    if ps and g.get('spread_h') is not None:
        fav = h if g['spread_h'] < 0 else (a if g['spread_h'] > 0 else None)
        bits.append(f"Our model makes {ps[0]} a {ps[1]:.1f} point favorite; the market has " + (f"{fav} {fl(-abs(g['spread_h']))}." if fav else "a pick'em."))
    for t, k in ((a, 'a'), (h, 'h')):
        if g.get('ppg_' + k) is not None: bits.append(f"{t} is {g.get('rec_' + k)} ({g['ppg_' + k]:.1f} scored, {g['papg_' + k]:.1f} allowed), {l5(g, k)}.")
    qa, qh = qbline(g, a), qbline(g, h)
    if qa and qh: bits.append(f"Quarterbacks: {a} {qa}; {h} {qh}.")
    m = mvt(g)
    if m: bits.append(f"Line move: {m}.")
    return ' '.join(bits[:5])
def analysis_total(g): return ' '.join(total_case(g, None)[:4])
# ---------- writes ----------
writes = []; rep = dict(card=[], shadow=[], props_play=[], props_track=[], preview=0, games=0)
existing = {os.path.basename(f)[:-5]: f for f in glob.glob(str(GD / '*.json'))}
VER = {k: (3 if k.split('_',1)[1] in {'ArizonaState-UCF','Baylor-BYU','Cincinnati-IowaState','Florida-Kentucky','Kansas-WestVirginia','KansasState-TCU','Louisville-NorthCarolina','Missouri-Georgia','OleMiss-Oklahoma','Stanford-VirginiaTech','Tennessee-TexasAM','Texas-LSU','TexasTech-OklahomaState','Utah-Arizona'} else 4) for k in existing}
def base_doc(did):
    if did not in existing: return None, None
    b = json.load(open(existing[did])); v = VER.get(did, 4); b = b.get('data', b) if isinstance(b.get('data'), dict) else b
    return {k: x for k, x in b.items() if k not in ('version', 'id')}, v
def rule_rec(rule, t):
    on, rec, pend = tier_state(rule, t)
    R = MR.get(rule) or {}; s = R.get('season') or {}
    d = dict(rule=rule, every_game=(f"{s.get('w', 0)}-{s.get('l', 0)} {s.get('u', 0):+.2f}u" if s else None), tier=f"{t}: real picks {rec}" if rec else None,
             status=('on' if on else 'off'), pending_on=pend)
    return {k: v for k, v in d.items() if v is not None}
def mk_pick_doc(g, did, p, kind, shadow, conflict, base=None):
    reasons = [dict(label=x['label'], detail=x.get('detail', ''), points=x['pts'], source=('Action Network' if x['key'] in ('sharp_action', 'big_money', 'pro_systems', 'money_vs_tickets', 'fade_public') else ('Action Network and CollegeFootballData openers' if x['key'] == 'rlm' else 'CollegeFootballData results')))
               for x in p['why'] if x['pts'] > 0]
    against = [dict(label=x['label'], detail=x.get('detail', ''), points=x['pts'], source=('Action Network' if x['key'] in ('sharp_action', 'big_money', 'pro_systems', 'money_vs_tickets', 'fade_public') else ('Action Network and CollegeFootballData openers' if x['key'] == 'rlm' else 'CollegeFootballData results')))
               for x in p['against'] if x['pts'] > 0]
    mk = p['market']; tmk = 'Total' if mk == 'Total' else ('Moneyline' if mk == 'Moneyline' else 'Spread')
    t, tb = tier_of(reasons, against)
    d = dict(base or {})
    d.update(date=g['date'], week=S['week'], game=f"{g['away']} @ {g['home']}", away=g['away'], home=g['home'], time=g['time'], market=mk,
             pick=p['text'], price=p['price'], line=p.get('line'), tier=t, tier_basis=tb, rule_tier=p.get('tier'), rule=p['rule'], rule_label=p['rule_label'],
             book=(p.get('book') or g.get('book')), line_source='The Odds API median of books',
             conflicting=p.get('conflicting', False), result='pending', espn_id=g['id'], shadow=bool(shadow),
             reasons=tag_market(reasons, tmk), against=tag_market(against, tmk), rule_record=rule_rec(p['rule'], t),
             summary=pick_summary(g, p), logged_at=f"{AS_OF}T15:40:00-07:00")
    if conflict: d['conflict'] = conflict
    elif 'conflict' in d: d.pop('conflict')
    return {k: v for k, v in d.items() if v is not None}, t
# meta prop rule on/off
def prop_on(stat, side):
    R = MR.get(f"PROP_{re.sub('[^a-z]', '', stat)}_{side}") or {}
    return R.get('on', True), R
V2 = {'ArizonaState-UCF','Baylor-BYU','Cincinnati-IowaState','Florida-Kentucky','Kansas-WestVirginia','KansasState-TCU','Louisville-NorthCarolina','Missouri-Georgia','OleMiss-Oklahoma','Stanford-VirginiaTech','Tennessee-TexasAM','Texas-LSU','TexasTech-OklahomaState','Utah-Arizona'}
PICKS = {}   # game did -> list of (market kind, pick doc id, doc)
for did, g in GAMES.items():
    if not g['today']: continue
    # card candidates from hubdocs (seed) docs
    for kind in ('side', 'total'):
        cd = W.get(('sports/fbs/picks', f"{did}_{kind}"))
        p = next((x for x in g['picks'] if x['kind'] == kind), None)
        if not p: continue
        doc, t = mk_pick_doc(g, did, p, kind, False, None, base=cd)
        on, rec, pend = tier_state(p['rule'], t)
        if on:
            PICKS.setdefault(did, []).append((kind, f"{did}_{kind}", doc)); rep['card'].append((f"{did}_{kind}", doc['pick'], doc['price'], t, p['rule']))
        else:
            mk = 'ml' if p['market'] == 'Moneyline' else kind
            doc['shadow'] = True
            doc['conflict'] = f"{p['rule_label']} {t} tier is turned off: its real picks are {rec}" + (f"; {pend.lower()}" if pend else '') + '. Logged as a would-be pick.'
            sid = f"{did}_{mk}_{p['rule']}"
            PICKS.setdefault(did, []).append((kind, sid, doc)); rep['shadow'].append((sid, doc['pick'], doc['price'], t, doc['conflict']))
    card_side = next((d for k, i, d in PICKS.get(did, []) if k == 'side' and not d['shadow']), None)
    for p in g.get('fits', []):
        kind = p['kind']; mk = 'total' if kind == 'total' else ('ml' if p['market'] == 'Moneyline' else 'side')
        doc, t = mk_pick_doc(g, did, p, kind, True, None)
        on, rec, pend = tier_state(p['rule'], t)
        winner = next((d for k, i, d in PICKS.get(did, []) if k == kind), None)
        if winner: why = f"Card order: {winner['rule_label']} took this market ({winner['pick']}); one side pick per game." if kind == 'side' else f"Card order: {winner['rule_label']} took the total."
        else: why = f"{p['rule_label']} fits, but the card's rule order picked no {kind} here."
        if not on: why += f" Its {t} tier is also turned off (real picks {rec})."
        doc['conflict'] = why
        sid = f"{did}_{mk}_{p['rule']}"
        PICKS.setdefault(did, []).append((kind + '_fit', sid, doc)); rep['shadow'].append((sid, doc['pick'], doc['price'], t, why))
for (did, kind, pid, doc) in [(d, k, i, x) for d, L in PICKS.items() for (k, i, x) in L]:
    writes.append(dict(op='set', collection='sports/fbs/picks', doc_id=pid, data=doc))
# props
PROPS_BY = {}
for (col, pid), v in W.items():
    if col != 'sports/fbs/picks' or '_prop_' not in pid: continue
    v = dict(v); did = pid.split('_prop_')[0]; g = GAMES[did]
    on, R = prop_on(v['stat'], v['side'])
    if v.get('tier') == 'PLAY' and not on:
        v['tracking'] = True; v['tracking_reason'] = f"{R.get('label')} props are off (real picks {R['season']['w']}-{R['season']['l']} {R['season']['u']:+.2f}u); logged as tracking only"
    t = v.get('team'); o = g['home'] if t == g['away'] else g['away']
    st = v['stat']
    if o in RANK['opp_pass_ypa'].index:
        if 'pass' in st or 'receiv' in st:
            r1 = rk('opp_pass_ypa', o); r2 = rk('sack_rate', o)
            vs = f"{o} pass D {r1} of {NF} by yards per attempt ({RAWU['opp_pass_ypg'][o]:.0f} per game) · pass rush {r2}"
            good = r1 > NF * 2 / 3; bad = r1 < NF / 3
        else:
            r1 = rk('opp_rush_ypc', o); vs = f"{o} run D {r1} of {NF} by yards per carry ({RAWU['opp_rush_ypg'][o]:.0f} per game)"
            good = r1 > NF * 2 / 3; bad = r1 < NF / 3
        eff = ('supports Over' if v['side'] == 'Over' else 'works against') if good else (('supports Under' if v['side'] == 'Under' else 'works against') if bad else 'neutral')
        v['matchup'] = dict(opp=o, vs=vs, effect=eff, adj=None, source='CFBD season stats (repo season_stats.csv); shown only, not in the projection until backtested (B36)')
    v['lineup_check'] = f"{v['player']} is on the {t} roster (ESPN) with a 2026 game log"
    v['logged_at'] = f"{AS_OF}T15:40:00-07:00"; v['line_source'] = 'The Odds API median of books'; v['book'] = 'The Odds API median of books'
    PROPS_BY.setdefault(did, []).append(v)
    writes.append(dict(op='set', collection='sports/fbs/picks', doc_id=pid, data=v))
    rep['props_play' if v.get('tier') == 'PLAY' and not v.get('tracking') else 'props_track'].append((pid, v['pick'], v['price'], v.get('tier'), v.get('matchup', {}).get('effect')))
# experts docs
for (col, eid), v in W.items():
    if col == 'sports/fbs/experts': writes.append(dict(op='set', collection=col, doc_id=eid, data=v))
# ---------- game docs ----------
PV = []
for did, g in GAMES.items():
    nd = dict(W[('sports/fbs/games', did)])
    base, ver = base_doc(did)
    # reasons with market
    rs = nd.get('reasons') or {}
    for k in list(rs):
        mk = 'Total' if k.startswith('total') else ('Moneyline' if (nd['picks'].get('side') or {}).get('rule') in ('dog_ml', 'fav_ml') else 'Spread')
        rs[k] = tag_market(rs[k], mk)
    nd['reasons'] = rs
    # picks per market
    picks = {}
    L = PICKS.get(did, [])
    for kind in ('side', 'total'):
        card = next((x for k, i, x in L if k == kind and not x['shadow']), None)
        if g['today'] and card:
            pid = next(i for k, i, x in L if x is card)
            picks[kind] = dict(pick=card['pick'], price=fp(card['price']), tier=card['tier'], tier_basis=card['tier_basis'], rule_tier=card.get('rule_tier'), rule_label=card['rule_label'],
                               rule=card['rule'], doc_id=pid, book=card.get('book'), line_source=card.get('line_source'), summary=card['summary'])
        elif g['today']:
            sh = [x for k, i, x in L if k.startswith(kind)]
            nt = none_side(g) if kind == 'side' else none_total(g)
            if sh: nt = ('Would-be pick only: ' + '; '.join(f"{x['pick']} ({x['rule_label']}, {x['tier']}): {x['conflict']}" for x in sh if not (kind == 'side' and card)))[:600] if not card else nt
            picks[kind] = {'none': nt, 'analysis': analysis_side(g) if kind == 'side' else analysis_total(g)}
        else:
            pp = next((p for p in g.get('preview_picks', []) if p['kind'] == kind), None)
            if pp:
                doc, t = mk_pick_doc(g, did, pp, kind, False, None)
                on, rec, pend = tier_state(pp['rule'], t)
                picks[kind] = dict(pick=pp['text'], price=fp(pp['price']), tier=t, tier_basis=doc['tier_basis'], rule_label=pp['rule_label'], rule=pp['rule'],
                                   preview=True, as_of=AS_OF, shadow=(not on), summary=doc['summary'],
                                   note=('Preview at today\'s line; picks are made on game day.' + ('' if on else f" Its {t} tier is turned off (real picks {rec}), so it would be a would-be pick.")))
                pvid = f"{AS_OF}_{did}_{'total' if kind == 'total' else ('ml' if pp['market'] == 'Moneyline' else 'side')}"
                pv = {k: v for k, v in doc.items() if k not in ('result', 'logged_at')}
                pv.update(as_of=AS_OF, game_id=did, game_date=g['date'], time=g['time'], shadow=(not on), experts=[e for e in (nd.get('experts') or []) if (e['market'].startswith('Total') if kind == 'total' else e['market'].startswith(('Spread', 'Moneyline')))][:5])
                PV.append((pvid, pv)); rep['preview'] += 1
            else:
                picks[kind] = {'none': none_side(g) if kind == 'side' else none_total(g), 'analysis': analysis_side(g) if kind == 'side' else analysis_total(g)}
            for fp_ in [p for p in g.get('fits', []) if p['kind'] == kind]:
                doc, t = mk_pick_doc(g, did, fp_, kind, True, None); on, rec, pend = tier_state(fp_['rule'], t)
                pvid = f"{AS_OF}_{did}_{'total' if kind == 'total' else ('ml' if fp_['market'] == 'Moneyline' else 'side')}_{fp_['rule']}"
                pv = {k: v for k, v in doc.items() if k not in ('result', 'logged_at')}
                pv.update(as_of=AS_OF, game_id=did, game_date=g['date'], time=g['time'], shadow=True, conflict='Card order would give this market to another rule (one side pick per game).' + ('' if on else f" Its {t} tier is turned off (real picks {rec})."))
                PV.append((pvid, pv)); rep['preview'] += 1
    nd['picks'] = picks
    # qbs, lineups, units, adjustments
    qa, qh = QBS.get((g['date'], g['away'])), QBS.get((g['date'], g['home']))
    if qa or qh: nd['qbs'] = {k: v for k, v in (('away', qa), ('home', qh)) if v}
    lu = {}
    for side_, t in (('away', g['away']), ('home', g['home'])):
        q = QBS.get((g['date'], t)); rows = []
        if q:
            u = QU.get(t) or {}
            rows.append(dict(player=q['name'], pos='QB', role=q['depth'], starter=True, status=q['status'],
                             strengths=[f"{round(100 * GP[(t, q['name'])])}% of attempts in games played"] if (t, q['name']) in GP else [], weaknesses=[],
                             backup=(u.get('qb2') if u.get('qb2') != q['name'] else u.get('qb1')), source=q['source']))
        if g['today']:
            seen = set()
            for p in sorted(PROPS_BY.get(did, []), key=lambda x: -(x.get('line') or 0)):
                if p['team'] != t or p['player'] in seen or (q and p['player'] == q['name']): continue
                seen.add(p['player']); pos = 'RB' if 'rush' in p['stat'] else 'WR/TE'
                sl = p.get('season_log') or []
                rows.append(dict(player=p['player'], pos=pos, role='skill starter (Odds API props posted)', starter=True, status='Available',
                                 strengths=([f"{np.mean(sl):.0f} {p['stat']} per game"] if sl else []), weaknesses=[], source='ESPN roster and game log; Odds API props'))
        if rows: lu[side_] = rows
    if lu: nd['lineups'] = lu; nd['lineups_note'] = 'Partial: QBs for every game; skill players only where The Odds API posted props. ESPN has no college depth charts and CFBD usage is not in the repo, so full 22-man lineups and player ratings are not built yet.'
    un = {s_: units(t) for s_, t in (('away', g['away']), ('home', g['home'])) if units(t)}
    if un: nd['units'] = un
    adj = []
    for t in (g['away'], g['home']):
        q = QBS.get((g['date'], t))
        if q and q['status'] == 'Questionable': adj.append(dict(team=t, out=[], effect='0 pts (not in our number)', reason=f"QB not settled: {q['note']}. Our model does not adjust for it; the market may."))
    nd['model'] = dict(nd.get('model') or {}, adjustments=adj)
    # line and pick history
    lh = [x for x in ((base or {}).get('line_history') or []) if x.get('as_of') != AS_OF]
    if g.get('spread_h') is not None:
        lh.append(dict(as_of=AS_OF, spread=f"{g['home']} {fl(g['spread_h'])}", total=g.get('total'), ml_away=g.get('ml_a'), ml_home=g.get('ml_h'),
                       source=(g.get('book') or '') + (f"; moneyline {g['ml_book']}" if g.get('ml_book') and g.get('ml_book') != g.get('book') else '')))
    nd['line_history'] = lh
    ph = [x for x in ((base or {}).get('pick_history') or []) if x.get('as_of') != AS_OF]
    prev = {x['market']: x for x in ((base or {}).get('pick_history') or []) if x.get('as_of') != AS_OF}
    for kind in ('side', 'total'):
        pk = picks.get(kind) or {}
        if 'pick' in pk:
            ph.append(dict(as_of=AS_OF, market=kind, pick=pk['pick'], price=pk['price'], line=None, tier=pk['tier'], rule=pk['rule'], shadow=bool(pk.get('shadow'))))
    nd['pick_history'] = ph
    ch = list((base or {}).get('changes') or [])
    for kind in ('side', 'total'):
        old = prev.get(kind); new = picks.get(kind) or {}
        if old and 'pick' in new and old.get('pick') != new['pick']:
            ch.append(dict(as_of=AS_OF, market=kind, **{'from': old['pick'], 'to': new['pick']}, line_from=None, line_to=None, reason='line move only, no news found', source='The Odds API median of books'))
    if ch: nd['changes'] = ch
    nd['updated'] = f"Nov 13 run, The Odds API median of books read {READ_AT}"; nd.setdefault('lines', {})['line_source'] = 'The Odds API median of books'
    if base:
        b2 = {k: x for k, x in base.items() if not (k in ('notes', 'props_note', 'experts', 'injuries', 'splits', 'moves', 'props', 'deep_dive', 'reasons', 'qbs', 'lineups', 'units') and k not in nd)}; b2.update(nd)
        writes.append(dict(op='set', collection='sports/fbs/games', doc_id=did, data=b2, if_version=ver))
    else:
        writes.append(dict(op='set', collection='sports/fbs/games', doc_id=did, data=nd))
    rep['games'] += 1
for pvid, pv in PV: writes.append(dict(op='set', collection='sports/fbs/preview', doc_id=pvid, data=pv))
# Nov 10 finals
FIN = {'2026-11-12_Memphis-SouthFlorida': 'Memphis 52, South Florida 41', '2026-11-12_Louisiana-ULMonroe': 'Louisiana 42, UL Monroe 21'}
for did, f in FIN.items():
    b, v = base_doc(did)
    if b is not None: writes.append(dict(op='update', collection='sports/fbs/games', doc_id=did, data=dict(status='final', final=f), if_version=v))
# ---------- batches ----------
DD = X / 'docs13'; DD.mkdir(exist_ok=True)
for f in DD.glob('*.json'): f.unlink()
ents = []
for w in writes:
    e = {k: w[k] for k in ('op', 'collection', 'doc_id')}
    if 'if_version' in w: e['if_version'] = w['if_version']
    fp_ = DD / f"{w['collection'].replace('/', '_')}__{w['doc_id']}.json"; json.dump(w['data'], open(fp_, 'w'), default=str, ensure_ascii=False); e['file_path'] = str(fp_)
    ents.append(e)
B = []; cur = []; size = 0
for e in ents:
    sz = os.path.getsize(e['file_path'])
    if cur and (len(cur) >= 50 or size + sz > 800000): B.append(cur); cur = []; size = 0
    cur.append(e); size += sz
if cur: B.append(cur)
for f in X.glob('nb*.json'): f.unlink()
for i, b in enumerate(B): json.dump(b, open(X / f'nb{i}.json', 'w'))
print('writes', len(writes), 'batches', [len(b) for b in B])
for k, v in rep.items(): print(k, v if not isinstance(v, list) else len(v)); [print('   ', x) for x in (v if isinstance(v, list) else [])]
json.dump(rep, open(X / 'report13.json', 'w'), default=str, indent=1)
