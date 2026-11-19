"""NFL card: the ONE home of signal scoring, pick rules and grading.
model.py (daily card) and recheck.py (end-of-week re-check) both import this file, so the card can never publish
a method the re-check did not measure (project 4.3n).

A game is a flat dict `r` (the columns of hist/games.csv). Signal points and rule settings live in signals.json."""
import json, math, pathlib
import numpy as np, pandas as pd
import nflmodel as M

D = pathlib.Path(__file__).parent
def load_sig(): return json.load(open(D/'signals.json'))

def isna(v): return v is None or (isinstance(v, float) and math.isnan(v))
def dec(m): return 1 + m/100 if m > 0 else 1 + 100/(-m)
def payout(price, res): return 0.0 if res == 0 else ((dec(price) - 1) if res > 0 else -1.0)
def be(prices): return float(np.mean([1/dec(p) for p in prices])) if len(prices) else float('nan')

# ---------------- openers: two sources must agree ----------------
def opener(r, kind):
    """Opener = Action Network open and DraftKings (via ESPN) open, counted only when they agree exactly (Trina, Oct 30).
    Rows carry an_open_* and dk_open_* (history: hist/openers2.csv; live: an_raw.txt open column and dk_today.txt).
    Older rows without those fields fall back to the earlier sources."""
    if 'an_open_sp_h' in r or 'dk_open_sp_h' in r:
        a_, d_ = (r.get('an_open_sp_h'), r.get('dk_open_sp_h')) if kind == 'sp' else (r.get('an_open_tot'), r.get('dk_open_tot'))
        if isna(a_) or isna(d_): return None, 'missing'
        return (float(a_), 'AN+DK') if float(a_) == float(d_) else (None, 'disagree')
    direct = r.get('open_sp_h' if kind == 'sp' else 'open_tot')
    if not isna(direct): return float(direct), r.get('open_src', 'openers.json')
    n = r.get('note_open_sp_h' if kind == 'sp' else 'note_open_tot'); s = r.get('sbr_open_sp_h' if kind == 'sp' else 'sbr_open_tot')
    cnt = r.get('sbr_open_sp_n' if kind == 'sp' else 'sbr_open_tot_n'); close = r['spread_h'] if kind == 'sp' else r['total']
    if isna(n) or isna(s) or isna(cnt) or cnt < 3: return None, 'none'
    if n == s: return float(n), 'confirmed'
    if np.sign(close - n) == np.sign(close - s) and np.sign(close - n) != 0:
        return float(n if abs(close - n) < abs(close - s) else s), 'direction'
    return None, 'disagree'

# ---------------- results log for streaks, form, last season ----------------
def build_log(sched):
    """sched: nflverse schedules (any seasons). Returns {team: [(season, week, margin), ...]} for finished REG games."""
    s = sched[(sched.game_type == 'REG') & sched.result.notna()].sort_values(['season', 'week'])
    L = {}
    for g in s.itertuples():
        for t, m in ((g.home_team, g.result), (g.away_team, -g.result)): L.setdefault(t, []).append((int(g.season), int(g.week), float(m)))
    return L
def _before(log, t, season, w): return [m for s_, w_, m in log.get(t, []) if s_ == season and w_ < w]
def _last(log, t, season): return [m for s_, w_, m in log.get(t, []) if s_ == season - 1]
def _streak(ms):
    s = 0
    for m in reversed(ms):
        if m > 0 and s >= 0: s += 1
        elif m < 0 and s <= 0: s -= 1
        else: break
    return s
def fl(v): return 'PK' if v == 0 else f'{v:+g}'

# ---------------- signals ----------------
def score_game(r, log, SIG=None, season=2026):
    """Returns side {team: [(key, pts, detail)]}, ml {team: [...]}, tot {'Over'/'Under': [...]}.
    ml holds only the moneyline-market Action Network signals; the moneyline score adds the non-Action Network side signals."""
    SIG = SIG or load_sig(); S, TT = SIG['side'], SIG['total']
    a, h, w = r['away'], r['home'], int(r['week'])
    side = {a: [], h: []}; ml = {a: [], h: []}; tot = {'Over': [], 'Under': []}
    def add(lst, key, t, detail, pts=None, spec=None):
        spec = spec if spec is not None else S
        p = (spec.get(key) or {}).get('pts', 0) if pts is None else pts
        lst[t].append((key, p, detail))
    other = {a: h, h: a}
    sp = r['spread_h']; fav = h if sp < 0 else (a if sp > 0 else None); dog = other[fav] if fav else None
    if r['div_game'] and fav: add(side, 'div_dog', dog, f'{dog} is the underdog in a division game')
    if r['neutral'] and fav: add(side, 'intl_fav', fav, f'{fav} favored at a neutral site')
    if not r['neutral']: add(side, 'home_field', h, f'{h} at home', 0)
    ra, rh = r['away_rest'], r['home_rest']
    for t, rt, ro in ((a, ra, rh), (h, rh, ra)):
        o = other[t]
        if rt >= 13 and ro <= 8: add(side, 'bye', t, f'{t} off a bye ({rt:g} days rest), {o} on {ro:g}', 0)
        if rt - ro >= 3 and not (rt >= 13 and ro <= 8): add(side, 'rest_edge', t, f'{t} {rt:g} days rest vs {o} {ro:g}', 0)
        if ro <= 5 and rt >= 6: add(side, 'short_week', t, f'{o} on a short week ({ro:g} days)', 0)
        bt, bo = _before(log, t, season, w), _before(log, o, season, w)
        if _streak(bt) >= 3 and _streak(bo) < 3: add(side, 'hot_streak', t, f'{t} won {_streak(bt)} straight', 0)
        if _streak(bo) <= -3 and _streak(bt) > -3: add(side, 'cold_opp', t, f'{o} lost {-_streak(bo)} straight', 0)
        if len(bt) >= 3 and len(bo) >= 3 and np.mean(bt[-3:]) - np.mean(bo[-3:]) >= 5:
            add(side, 'form', t, f'last 3 point diff {np.mean(bt[-3:]):+.1f} vs {np.mean(bo[-3:]):+.1f} per game', 0)
        lt, lo = _last(log, t, season), _last(log, o, season)
        wt, wo = sum(m > 0 for m in lt), sum(m > 0 for m in lo)
        if lt and lo and (wt - wo)/17 >= .25: add(side, 'track_record', t, f'{t} won {wt} last season vs {o} {wo}', 0)
        if r.get(f'qbchg_{"a" if o == a else "h"}') == 1: add(side, 'qb_change', t, f'{o} starting a different QB than usual', 0)
    if abs(M.TZ.get(a, 0) - M.TZ.get(h, 0)) >= 2 and not r['neutral']: add(side, 'travel', h, f'{a} crossed {abs(M.TZ.get(a, 0) - M.TZ.get(h, 0))} time zones', 0)
    if r['weekday'] == 'Thursday' and not r['neutral']: add(side, 'tnf_home', h, 'Thursday game, home side', 0)
    if isinstance(r.get('proj_side'), str) and r['proj_side'] in (a, h): add(side, 'projection', r['proj_side'], r.get('proj_detail', 'card projection side'), 0)
    if not isna(r.get('rk_a')) and not isna(r.get('rk_h')):
        gap = r['rk_a'] - r['rk_h']
        if abs(gap) >= S['pr_fade']['gap']:
            hi = h if gap > 0 else a; lo = other[hi]
            add(side, 'pr_fade', lo, f'NFL.com ranks {hi} #{int(min(r["rk_a"], r["rk_h"]))} and {lo} #{int(max(r["rk_a"], r["rk_h"]))}; fade the ranking')
    ea, eh = int(r.get('exp_a') or 0), int(r.get('exp_h') or 0); n = ea + eh
    if n >= 3:
        t = a if ea >= eh else h; sh = max(ea, eh)/n
        if sh >= S['expert_follow']['min_share']:
            conf = [k for k, p, _ in side[t] if k in S['expert_follow']['confirms'] and p > 0]
            det = f'{max(ea, eh)} of {n} experts ({sh*100:.0f}%) on {t}'
            if conf: add(side, 'expert_follow', t, det + ', agreeing with ' + ', '.join(S[k]['label'] for k in conf))
            add(side, 'expert_any', t, det + ('' if conf else '; nothing tested agrees'), 0)
    def code(mk, nm):
        v = r.get(f'{mk}_{nm}')
        return [] if isna(v) else {0: [], 1: [a], 2: [h], 3: [a, h]}[int(v)]
    for nm, key in (('SA', 'sharp_action'), ('BM', 'big_money'), ('PRO', 'pro_systems')):
        for t in code('sp', nm): add(side, key, t, f'Action Network spread sharp report')
        for t in code('ml', nm): add(ml, key, t, f'Action Network moneyline sharp report')
    for t in code('sp', 'MP'): add(side, 'an_model', t, 'Action Network model projection', 0)
    for t in code('sp', 'EXP'): add(side, 'an_experts', t, 'Action Network top experts', 0)
    for lst, bk, mk, nm in ((side, 'sp_bets_a', 'sp_money_a', 'spread'), (ml, 'ml_bets_a', 'ml_money_a', 'moneyline')):
        b_, m_ = r.get(bk), r.get(mk)
        if isna(b_) or isna(m_): continue
        for t, bb, mm in ((a, b_, m_), (h, 100-b_, 100-m_)):
            if mm - bb >= S['money_vs_tickets']['gap']: add(lst, 'money_vs_tickets', t, f'{mm:g}% of money on {bb:g}% of tickets ({nm})')
            if bb <= S['fade_public']['max_tickets']: add(lst, 'fade_public', t, f'only {bb:g}% of tickets ({nm})')
    op, src = opener(r, 'sp'); r['open_sp'], r['open_sp_src'] = op, src
    if op is not None and not isna(r.get('sp_bets_a')):
        mv = sp - op
        if abs(mv) >= S['rlm']['min_move']:
            t = a if mv > 0 else h; tb = r['sp_bets_a'] if t == a else 100 - r['sp_bets_a']
            det = f'spread moved {abs(mv):g} toward {t} (open {h} {fl(op)}, now {fl(sp)})'
            if tb < 50: add(side, 'rlm', t, det + f' with {tb:g}% of tickets')
            add(side, 'line_move', t, det, 0)
    # totals
    def tadd(sd, key, detail, pts=None): tot[sd].append((key, (TT.get(key) or {}).get('pts', 0) if pts is None else pts, detail))
    for nm, key in (('SA', 'sharp_action'), ('BM', 'big_money'), ('PRO', 'pro_systems'), ('MP', 'an_model'), ('EXP', 'an_experts')):
        v = r.get(f'tot_{nm}')
        if not isna(v):
            for sd in {0: [], 1: ['Over'], 2: ['Under'], 3: ['Over', 'Under']}[int(v)]: tadd(sd, key, 'Action Network total sharp report')
    ob, om = r.get('tot_bets_o'), r.get('tot_money_o')
    if not isna(ob) and not isna(om):
        for sd, bb, mm in (('Over', ob, om), ('Under', 100-ob, 100-om)):
            if mm - bb >= TT['money_vs_tickets']['gap']: tadd(sd, 'money_vs_tickets', f'{mm:g}% of money on {bb:g}% of tickets')
            if bb >= TT['fade_public']['min_tickets']: tadd('Under' if sd == 'Over' else 'Over', 'fade_public', f'{bb:g}% of tickets on the {sd.lower()}')
    ot, tsrc = opener(r, 'tot'); r['open_tot_v'], r['open_tot_src'] = ot, tsrc
    if ot is not None:
        mv = r['total'] - ot
        if mv <= -TT['moved_down']['min_move']:
            p_ = TT['moved_down']['pts_public_under'] if (not isna(ob) and 100-ob >= 50) else TT['moved_down']['pts']
            tadd('Under', 'moved_down', f'total {ot:g} to {r["total"]:g}', p_)
        if mv >= TT['moved_down']['min_move']: tadd('Over', 'moved_up', f'total {ot:g} to {r["total"]:g}', 0)
    outdoor = r.get('roof') in ('outdoors', 'open')
    if outdoor and not isna(r.get('wind')) and r['wind'] >= TT['wind']['gap']: tadd('Under', 'wind', f'wind {r["wind"]:.0f} mph')
    if r.get('roof') in ('dome', 'closed'): tadd('Over', 'dome_over', 'roof closed')
    if r['div_game']: tadd('Under', 'div_under', 'division game', 0)
    if r['weekday'] == 'Thursday': tadd('Under', 'tnf_under', 'Thursday game', 0)
    eo, eu = int(r.get('exp_over') or 0), int(r.get('exp_under') or 0)
    if eo + eu >= 3 and max(eo, eu)/(eo+eu) >= .6: tadd('Over' if eo > eu else 'Under', 'expert_any', f'{max(eo, eu)} of {eo+eu} experts', 0)
    if not isna(r.get('card_our_total')) and not isna(r.get('card_market_total')):
        tadd('Over' if r['card_our_total'] > r['card_market_total'] else 'Under', 'projection', f'our total {r["card_our_total"]:.1f} vs {r["card_market_total"]:g}', 0)
    return side, ml, tot

ANK = ('sharp_action', 'big_money', 'pro_systems', 'money_vs_tickets', 'fade_public', 'rlm')
def summarize(r, side, ml, tot):
    """The decision inputs for one game: signal side, leads, totals score, favorite and prices."""
    a, h = r['away'], r['home']
    sc = lambda l: sum(p for _, p, _ in l)
    sa, sh = sc(side[a]), sc(side[h])
    team = (a if sa > sh else h) if sa != sh else (r['proj_side'] if isinstance(r.get('proj_side'), str) and r['proj_side'] in (a, h) else None)
    lead = abs(sa - sh)
    mlL = {t: [z for z in side[t] if z[0] not in ANK] + ml[t] for t in (a, h)}
    mll = (sc(mlL[team]) - sc(mlL[a if team == h else h])) if team else 0
    fav = h if r['spread_h'] < 0 else (a if r['spread_h'] > 0 else None)
    return dict(week=int(r['week']), game=r['game'], away=a, home=h, fav=fav, spread_h=r['spread_h'], total=r['total'],
                ml_a=r['ml_a'], ml_h=r['ml_h'], sp_price_a=r['sp_price_a'], sp_price_h=r['sp_price_h'],
                over_price=r['over_price'], under_price=r['under_price'], band_ml_a=r.get('band_ml_a'), band_ml_h=r.get('band_ml_h'),
                margin_h=r.get('margin_h'), total_pts=r.get('total_pts'),
                team=team, lead=lead, ml_lead=mll, score_a=sa, score_h=sh,
                side_keys={t: [k for k, _, _ in side[t]] for t in (a, h)}, side_pts={t: {k: p for k, p, _ in side[t]} for t in (a, h)},
                tot_keys={s_: [k for k, _, _ in tot[s_]] for s_ in tot}, so=sc(tot['Over']), su=sc(tot['Under']),
                open_sp=r.get('open_sp'), open_sp_src=r.get('open_sp_src'), open_tot=r.get('open_tot_v'), open_tot_src=r.get('open_tot_src'))

# ---------------- rules ----------------
def active(rule):
    """A rule's live settings: its fixed fields plus the parameters of its current version (lowered or strict)."""
    x = {k: v for k, v in rule.items() if k != 'versions'}
    x.update(rule.get('versions', {}).get(rule.get('version', ''), {}))
    return x
def ml_price(g, t): return g['ml_h'] if t == g['home'] else g['ml_a']
def band_price(g, t):
    """Price used to test a rule's moneyline band: the pick-time (morning) price when the row carries one, else the line in use."""
    b = g.get('band_ml_h') if t == g['home'] else g.get('band_ml_a')
    return ml_price(g, t) if isna(b) else b
def side_rule(g, rule):
    """Does this side rule fire for game g? Returns (team, market) or None."""
    rule = active(rule); t = g['team']
    if not t or not rule.get('on', True): return None
    # Nov 15 (A48, NFL split): a looser rule covers only the band its stricter rule misses (max_lead)
    if rule.get('max_lead') is not None and g['lead'] > rule['max_lead']: return None
    if rule['id'].startswith('fav_ml'):
        if g['fav'] and t == g['fav'] and g['lead'] >= rule['min_lead']:
            pr = band_price(g, t)
            if not isna(pr) and rule['price'][0] <= pr <= rule['price'][1]: return t, 'Moneyline'
        return None
    if rule['id'].startswith('spread'):
        if g['lead'] >= rule['min_lead'] and (not rule.get('dog_only') or (g['fav'] and t != g['fav'])): return t, 'Spread'
        return None
    if rule['id'].startswith('dog_ml'):
        if g['fav'] and t != g['fav'] and g['lead'] >= rule['min_lead']:
            pr = band_price(g, t)
            if isna(pr) or not (rule['price'][0] <= pr <= rule['price'][1]): return None
            if rule.get('reasons') and not any(k in rule['reasons'] and g['side_pts'][t].get(k, 0) > 0 for k in g['side_keys'][t]): return None
            return t, 'Moneyline'
        return None
    if rule['id'].startswith('dog_spread'):
        # underdog spread (Nov 7 backtest): the signal side is the underdog, lead min_lead+, and a tested reason on its side
        if g['fav'] and t != g['fav'] and g['lead'] >= rule['min_lead']:
            if rule.get('reasons') and not any(k in rule['reasons'] and g['side_pts'][t].get(k, 0) > 0 for k in g['side_keys'][t]): return None
            return t, 'Spread'
        return None
    return None
def total_rule(g, rule):
    rule = active(rule)
    if not rule.get('on', True): return None
    if rule.get('id', '').startswith('over'):
        # overs (Nov 7 backtest): the over's signal score beats the under's by min_diff+ (Nov 15 split: and at most max_diff)
        d_ = g['so'] - g['su']
        if rule.get('max_diff') is not None and d_ > rule['max_diff']: return None
        return 'Over' if d_ >= rule['min_diff'] else None
    keys = rule['keys']
    on = [s_ for s_ in ('Over', 'Under') if any(k in g['tot_keys'][s_] for k in keys)]
    if len(on) != 1: return None
    sd = on[0]; os_ = 'Under' if sd == 'Over' else 'Over'
    if rule.get('no_against'):
        scored = {'sharp_action', 'fade_public', 'moved_down', 'wind', 'dome_over', 'money_vs_tickets'}
        if any(k in scored for k in g['tot_keys'][os_]): return None
    # Nov 15 (A48, NFL split): the looser one-sided total rule covers only games the strict rule misses
    if rule.get('exclude') and total_rule(g, dict(rule['exclude'], id='total_one_sided', on=True)): return None
    return sd
def pick_side(g, RULES):
    for rule in RULES['side']:
        z = side_rule(g, rule)
        if z: return rule, z[0], z[1]
    return None
def pick_total(g, RULES):
    for rule in RULES['total']:
        z = total_rule(g, rule)
        if z: return rule, z
    return None
def no_pick_reason(g, RULES):
    if not g['team']: return 'signals tied and no projection'
    fr = active(next(r_ for r_ in RULES['side'] if r_['id'].startswith('fav_ml'))); sr = active(min((r_ for r_ in RULES['side'] if r_['id'].startswith('spread')), key=lambda r_: active(r_)['min_lead']))
    _sp = next(r_ for r_ in RULES['side'] if r_['id'].startswith('spread')); _fm = next(r_ for r_ in RULES['side'] if r_['id'].startswith('fav_ml'))
    if not _sp.get('on', True) and g['lead'] >= sr['min_lead']: bits = [f"signal lead {g['lead']} on {g['team']} fits the spread rule, but the spread rule is off (Nov policy)"]
    else: bits = [f"signal lead {g['lead']} on {g['team']} (spread needs {sr['min_lead']}+)"]
    if not _fm.get('on', True) and g['fav'] and g['team'] == g['fav']: bits.append('favorite moneyline rule is off (Nov policy)')
    if g['fav'] and g['team'] == g['fav']:
        pr = ml_price(g, g['team'])
        if not isna(pr) and not (fr['price'][0] <= pr <= fr['price'][1]): bits.append(f"favorite moneyline {pr:+g} outside {fr['price'][0]} to {fr['price'][1]}")
    elif g['fav']:
        dr = [r_ for r_ in RULES['side'] if r_['id'].startswith('dog')]
        if not any(r_.get('on', True) for r_ in dr): bits.append('underdog rules are off')
        else: bits.append('underdog rule needs a tested reason (' + ', '.join(active(dr[0]).get('reasons', [])) + f") and a moneyline {active(dr[0])['price'][0]:+g} to {active(dr[0])['price'][1]:+g}")
    return '; '.join(bits)

# ---------------- grading ----------------
def side_res(g, t, market):
    m = g['margin_h'] if t == g['home'] else -g['margin_h']
    if market in ('ml', 'Moneyline'): return int(np.sign(m)), ml_price(g, t)
    line = -g['spread_h'] if t == g['away'] else g['spread_h']
    return int(np.sign(m + line)), (g['sp_price_h'] if t == g['home'] else g['sp_price_a'])
def tot_res(g, sd):
    return int(np.sign(g['total_pts'] - g['total']) * (1 if sd == 'Over' else -1)), (g['over_price'] if sd == 'Over' else g['under_price'])
def week_months(sched, season=2026):
    """{week: 'Sep'|'Oct'|...} by the month most of that week's games are played in."""
    s = sched[(sched.season == season) & (sched.game_type == 'REG')]
    return {int(w): pd.to_datetime(x.gameday).dt.strftime('%b').mode().iloc[0] for w, x in s.groupby('week')}
def grade(picks, MW, last3):
    """picks: [(week, result, price)]. Season to date, one column per month, and the last 3 weeks.
    Qualifies at 5+ picks with positive units and a win % above break-even."""
    def agg(p):
        p = [(r_, pr) for r_, pr in p if not isna(pr)]
        W = sum(r_ > 0 for r_, _ in p); L = sum(r_ < 0 for r_, _ in p); P = sum(r_ == 0 for r_, _ in p)
        u = sum(payout(pr, r_) for r_, pr in p); b = be([pr for r_, pr in p if r_ != 0])
        pct = W/(W+L) if W+L else float('nan')
        return dict(W=W, L=L, P=P, n=W+L+P, pct=pct, units=u, be=b, q=bool(W+L+P >= 5 and u > 0 and W+L and pct > b))
    out = dict(season=agg([(r_, pr) for w, r_, pr in picks]), months={}, last3=agg([(r_, pr) for w, r_, pr in picks if w in last3]))
    for m in dict.fromkeys(MW.values()):
        out['months'][m] = agg([(r_, pr) for w, r_, pr in picks if MW.get(w) == m])
    out['qualifies'] = out['season']['q']
    out['warn'] = bool(out['season']['q'] and out['last3']['n'] and out['last3']['units'] < 0)
    return out
def rec_text(gr):
    a = gr['season'] if 'season' in gr else gr
    if not a['n']: return '0 picks'
    return f"{a['W']}-{a['L']}" + (f"-{a['P']}" if a['P'] else '') + f", {a['units']:+.1f}u"
def cell(d): return rec_text(d) if d['n'] else '-'

def score_all(T, log, SIG):
    """T: DataFrame of games (games.csv columns). Returns list of summarize() dicts with results attached."""
    out = []
    for _, row in T.iterrows():
        r = {k: (None if (isinstance(v, float) and math.isnan(v)) else v) for k, v in row.to_dict().items()}
        r['margin_h'] = r['home_score'] - r['away_score']; r['total_pts'] = r['home_score'] + r['away_score']
        side, ml, tot = score_game(r, log, SIG)
        out.append(summarize(r, side, ml, tot))
    return out

def rule_records(G, RULES, MW, last3):
    """Season record of each rule, applied in order (one side pick per game), on finished games G."""
    by = {r_['id']: [] for r_ in RULES['side'] + RULES['total']}
    for g in G:
        z = pick_side(g, RULES)
        if z: by[z[0]['id']].append((g['week'], *side_res(g, z[1], z[2])))
        t = pick_total(g, RULES)
        if t: by[t[0]['id']].append((g['week'], *tot_res(g, t[1])))
    return {k: grade(v, MW, last3) for k, v in by.items()}, by
def card_order_record(G, RULES, rid, MW, last3, version=None):
    """One rule's record graded in card order (Trina, Nov 6): every other rule at its current on/off state and version,
    this rule switched on (optionally at another version). Side order: fav_ml, spread, dog_ml, dog_spread; total order:
    total_one_sided, over. So an off rule is still graded on exactly the games it would get if it were turned on now."""
    import copy
    R = copy.deepcopy(RULES)
    for r_ in R['side'] + R['total']:
        if r_['id'] == rid:
            r_['on'] = True
            if version: r_['version'] = version
    return rule_records(G, R, MW, last3)[0][rid]

# ---------------- the full test suite (review and weekly re-check) ----------------
def run_tests(G, MW, last3, TESTED=('rlm', 'div_dog', 'pr_fade', 'expert_follow'), out=print):
    """Every test from the reviews, graded season to date, by month and over the last 3 weeks.
    Returns (groups, text): groups = [{'title', 'rows': [{'label', 'season', 'months', 'last3', 'qualifies', 'warn'}]}]."""
    groups = []
    months = list(dict.fromkeys(MW.values()))
    def line(lbl, picks):
        gr = grade(picks, MW, last3); s_ = gr['season']
        pc = f"{s_['pct']*100:4.1f}%" if s_['W'] + s_['L'] else '  -  '
        txt = (f"{lbl:62s} {cell(s_):>16s} {pc} be {s_['be']*100 if s_['W']+s_['L'] else 0:4.1f}% | "
               + ' | '.join(f"{m} {cell(gr['months'][m]):>14s}" for m in months) + f" | last 3 wk {cell(gr['last3']):>14s}"
               + (' QUALIFIES' if gr['qualifies'] else '') + ('  WARN last 3 wk negative' if gr['warn'] else ''))
        out(txt); groups[-1]['rows'].append(dict(label=lbl.strip(), season=s_, months=gr['months'], last3=gr['last3'], qualifies=gr['qualifies'], warn=gr['warn']))
        return gr
    def head(t): out('\n## ' + t); groups.append(dict(title=t, rows=[]))
    dog = lambda g: (g['away'] if g['fav'] == g['home'] else g['home']) if g['fav'] else None
    # a
    head('a. Favorite moneyline by price band')
    for lb, lo, hi in (('shorter than -500', -1e9, -500.01), ('-500 to -301', -500, -301), ('-300 to -201', -300, -201), ('-200 to -100', -200, -100)):
        for ver in ('every favorite', 'signals agree'):
            pk = [(g['week'], *side_res(g, g['fav'], 'ml')) for g in G if g['fav'] and lo <= ml_price(g, g['fav']) <= hi
                  and (ver == 'every favorite' or (g['team'] == g['fav'] and g['lead'] >= 1))]
            line(f'Fav ML {lb}, {ver}', pk)
    for ld in (1, 2, 3):
        line(f'Fav ML -200 to -100, signal lead {ld}{"+" if ld == 3 else ""}',
             [(g['week'], *side_res(g, g['fav'], 'ml')) for g in G if g['fav'] and g['team'] == g['fav'] and -200 <= ml_price(g, g['fav']) <= -100
              and ((g['lead'] == ld) if ld < 3 else g['lead'] >= 3)])
    # b
    head('b. Underdog moneyline from +100')
    reason = lambda g, d: any(k in TESTED and g['side_pts'][d].get(k, 0) > 0 for k in g['side_keys'][d])
    for lb, lo, hi in (('+100 to +150', 100, 150), ('+151 to +200', 151, 200), ('+201 to +300', 201, 300), ('+301 to +500', 301, 500), ('+501 and up', 501, 1e9),
                       ('+100 to +200', 100, 200), ('+100 to +300', 100, 300), ('+100 and up', 100, 1e9)):
        for ver in ('every underdog', 'signals on the dog', 'signals on the dog + reason'):
            pk = []
            for g in G:
                d = dog(g)
                if not d or not (lo <= ml_price(g, d) <= hi): continue
                if ver != 'every underdog' and not (g['team'] == d and g['lead'] >= 1): continue
                if ver.endswith('reason') and not reason(g, d): continue
                pk.append((g['week'], *side_res(g, d, 'ml')))
            line(f'Dog ML {lb}, {ver}', pk)
    # c
    head('c. Underdog spread, signals on the dog')
    base = [g for g in G if dog(g) and g['team'] == dog(g) and g['lead'] >= 1]
    line('Dog spread, signals on the dog', [(g['week'], *side_res(g, g['team'], 'sp')) for g in base])
    keys = sorted({k for g in G for t in (g['away'], g['home']) for k in g['side_keys'][t]})
    for k in keys:
        pk = [(g['week'], *side_res(g, g['team'], 'sp')) for g in base if k in g['side_keys'][g['team']]]
        if pk: line(f'  ... with {k}', pk)
    line('Dog spread, signals on the dog + a tested reason', [(g['week'], *side_res(g, g['team'], 'sp')) for g in base if reason(g, g['team'])])
    # d
    head('d. Spread on the signal side')
    for ld in range(1, 7):
        line(f'Signal side spread, lead {ld}{"+" if ld == 6 else ""}', [(g['week'], *side_res(g, g['team'], 'sp')) for g in G if g['team'] and ((g['lead'] == ld) if ld < 6 else g['lead'] >= 6)])
    for ld in (1, 2, 3, 4):
        line(f'Signal side spread, lead {ld}+', [(g['week'], *side_res(g, g['team'], 'sp')) for g in G if g['team'] and g['lead'] >= ld])
        for nm, f in (('favorite', lambda g: g['team'] == g['fav']), ('underdog', lambda g: g['fav'] and g['team'] != g['fav'])):
            line(f'Signal side spread, lead {ld}+, {nm}', [(g['week'], *side_res(g, g['team'], 'sp')) for g in G if g['team'] and g['lead'] >= ld and f(g)])
        for nm, lo, hi in (('line 0 to 3', 0, 3), ('line 3.5 to 6.5', 3.5, 6.5), ('line 7 to 9.5', 7, 9.5), ('line 10+', 10, 99)):
            line(f'Signal side spread, lead {ld}+, {nm}', [(g['week'], *side_res(g, g['team'], 'sp')) for g in G if g['team'] and g['lead'] >= ld and lo <= abs(g['spread_h']) <= hi])
    # e
    head('e. Totals')
    line('Always over', [(g['week'], *tot_res(g, 'Over')) for g in G]); line('Always under', [(g['week'], *tot_res(g, 'Under')) for g in G])
    for ld in (1, 2, 3):
        line(f'Total score, lead {ld}+', [(g['week'], *tot_res(g, 'Over' if g['so'] > g['su'] else 'Under')) for g in G if abs(g['so'] - g['su']) >= ld])
    tkeys = sorted({k for g in G for s_ in ('Over', 'Under') for k in g['tot_keys'][s_]})
    for k in tkeys:
        for sd in ('Over', 'Under', 'either'):
            pk = []
            for g in G:
                ss = [s_ for s_ in ('Over', 'Under') if k in g['tot_keys'][s_]]
                if len(ss) == 1 and (sd == 'either' or ss[0] == sd): pk.append((g['week'], *tot_res(g, ss[0])))
            if pk: line(f'Total: {k} alone ({sd})', pk)
    for keys_, nm in ((('money_vs_tickets', 'pro_systems'), 'Money vs tickets or PRO'), (('money_vs_tickets',), 'Money vs tickets'), (('pro_systems',), 'PRO'),
                      (('pro_systems', 'big_money'), 'PRO or big money')):
        for na in (False, True):
            line(f'{nm} on one side only{", nothing against" if na else ""}', [(g['week'], *tot_res(g, sd)) for g in G if (sd := total_rule(g, dict(keys=keys_, no_against=na)))])
    # e2: over totals with signals
    head('e2. Over totals with signals')
    for ld in (1, 2, 3):
        line(f'Over when the total score leans over by {ld}+', [(g['week'], *tot_res(g, 'Over')) for g in G if g['so'] - g['su'] >= ld])
    for keys_, nm in ((('money_vs_tickets', 'pro_systems'), 'money vs tickets or PRO'), (('pro_systems', 'big_money'), 'PRO or big money'),
                      (('sharp_action',), 'sharp action'), (('dome_over',), 'dome'), (('moved_up',), 'total moved up')):
        line(f'Over with {nm} on the over only', [(g['week'], *tot_res(g, sd)) for g in G if (sd := total_rule(g, dict(keys=keys_, no_against=False))) == 'Over'])
    # f
    head('f. Every side signal on its own')
    for k in keys:
        for mk in ('sp', 'ml'):
            pk = []
            for g in G:
                ts = [t for t in (g['away'], g['home']) if k in g['side_keys'][t]]
                if len(ts) != 1: continue
                res, p_ = side_res(g, ts[0], mk)
                if mk == 'ml' and not (-300 <= p_ <= 300): continue
                pk.append((g['week'], res, p_))
            if pk: line(f'{k} ({"spread" if mk == "sp" else "ML -300 to +300"})', pk)
    return groups
