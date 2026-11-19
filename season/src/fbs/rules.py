"""Single home for the scored signals, the pick rules and the grading used by BOTH
model.py (today's card) and recheck.py (the end-of-week re-check). Nothing here may
be copied into another file: a backtest that measures different code from the card
is worse than no backtest (project rule 4.3n).

Every number comes from signals.json (points, thresholds) and its rules_<div> block.
"""
import math, ast
import numpy as np


# ---------------- prices ----------------
def implied(o):
    return 100 / (o + 100) if o > 0 else -o / (-o + 100)


def novig(a, b):
    if a is None or b is None: return None, None
    x, y = implied(a), implied(b)
    return x / (x + y), y / (x + y)


def dec(m): return 1 + m / 100 if m > 0 else 1 + 100 / -m


def amer(d): return int(round((d - 1) * 100)) if d >= 2 else int(round(-100 / (d - 1)))


def payout(win, price):
    """Units won on a 1-unit bet. win None = push."""
    if win is None: return 0.0
    if not win: return -1.0
    return price / 100 if price > 0 else 100 / -price


def breakeven(price): return implied(price)


def consensus(lines, ml_cap=5000):
    """CFBD per-book lines -> median spread/total/openers and a CLEAN moneyline.
    Broken quotes are dropped (|ML| under 100 or over the cap, both sides favourites
    beyond -130) and the median is taken in decimal odds, because a plain median of
    +105 and -110 gives -2.5 (found Oct 29, 2026)."""
    if isinstance(lines, str):
        try: lines = ast.literal_eval(lines)
        except Exception: lines = []
    sp = [x['spread'] for x in lines if x.get('spread') is not None]
    tt = [x['overUnder'] for x in lines if x.get('overUnder')]
    so = [x['spreadOpen'] for x in lines if x.get('spreadOpen') is not None]
    to = [x['overUnderOpen'] for x in lines if x.get('overUnderOpen')]
    ok = []
    for x in lines:
        a, h = x.get('awayMoneyline'), x.get('homeMoneyline')
        if a is None or h is None: continue
        if not (100 <= abs(a) <= ml_cap and 100 <= abs(h) <= ml_cap): continue
        if a < 0 and h < 0 and (a < -130 or h < -130): continue
        ok.append((a, h))
    med = lambda v: float(np.median(v)) if v else None
    dk = next(((a, h) for (a, h), x in zip([(x.get('awayMoneyline'), x.get('homeMoneyline')) for x in lines], lines)
               if x.get('provider') == 'DraftKings' and (a, h) in ok), (None, None))
    return dict(dk_ml_a=dk[0], dk_ml_h=dk[1], spread_h=med(sp), total=med(tt), open_h=med(so), tot_open=med(to),
                ml_a=amer(float(np.median([dec(a) for a, _ in ok]))) if ok else None,
                ml_h=amer(float(np.median([dec(h) for _, h in ok]))) if ok else None, books=len(lines))


# ---------------- team form helpers ----------------
def team_logs(rows):
    """rows: iterable of (dt, home, away, home_pts, away_pts), completed games only."""
    L = {}
    for dt, h, a, hp, ap in rows:
        L.setdefault(h, []).append((dt, hp, ap)); L.setdefault(a, []).append((dt, ap, hp))
    for k in L: L[k].sort(key=lambda r: r[0])
    return L


def before(logs, team, dt):
    return [r for r in logs.get(team, []) if r[0] < dt]


def rest_days(logs, team, dt):
    p = before(logs, team, dt)
    return (dt - p[-1][0]).days if p else None


def last3_total(logs, team, dt):
    p = before(logs, team, dt)
    return float(np.mean([r[1] + r[2] for r in p[-3:]])) if len(p) >= 3 else None


def last_season(prior_rows):
    """prior_rows: (home, away, hp, ap) -> {team: (win%, w, l)}"""
    W = {}
    for h, a, hp, ap in prior_rows:
        for t, won in ((h, hp > ap), (a, ap > hp)):
            w = W.setdefault(t, [0, 0]); w[0 if won else 1] += 1
    return {t: (w / (w + l), w, l) for t, (w, l) in W.items() if w + l}


def fmt_line(v):
    if v is None: return '·'
    if v == 0: return 'PK'
    return f'{v:+g}'


# ---------------- scored signals ----------------
def build_signals(x, SIG):
    """x: a, h, rest_a, rest_h, last_a, last_h (win%, w, l), l3_a, l3_h, spread_h, open_h (CFBD opener),
    total, tot_open (CFBD opener), an = dict(pub={SPREAD|TOTAL|ML: dict(open, bets, money)},
    sharp={SPREAD|TOTAL|ML: [codes]}). Returns side, ml, tot signal lists."""
    S, T = SIG['side'], SIG['total']
    a, h = x['a'], x['h']
    sideS = {a: [], h: []}; mlS = {a: [], h: []}; totS = {'Over': [], 'Under': []}

    def mk(spec, key, detail, pts=None):
        return dict(key=key, label=spec['label'], pts=spec['pts'] if pts is None else pts, status=spec['status'], detail=detail)

    def add(lst, key, team, detail=''):
        lst[team].append(mk(S[key], key, detail))

    for t, k, o, ko in ((a, 'a', h, 'h'), (h, 'h', a, 'a')):
        ro, rt = x.get('rest_' + ko), x.get('rest_' + k)
        if ro is not None and rt is not None and ro <= 6 and rt >= 7:
            add(sideS, 'short_week', t, f'{o} {ro} days since its last game date, {t} {rt}'); add(mlS, 'short_week', t, f'{o} {ro} days since its last game date, {t} {rt}')
        la, lo = x.get('last_' + k), x.get('last_' + ko)
        if la and lo and lo[0] - la[0] >= S['last_season']['gap']:
            d = f'{t} {la[1]}-{la[2]} last season vs {o} {lo[1]}-{lo[2]}; market leans on last year'
            add(sideS, 'last_season', t, d); add(mlS, 'last_season', t, d)

    an = x.get('an') or {}; pub = an.get('pub') or {}; shp = an.get('sharp') or {}
    for code in shp.get('SPREAD', []):
        t = a if code.endswith('a') else h
        key = {'SA': 'sharp_action', 'BM': 'big_money', 'PRO': 'pro_systems', 'EXP': 'spread_experts', 'MP': 'spread_model'}.get(code[:-1])
        if key: add(sideS, key, t, 'Action Network spread report')
    for code in shp.get('ML', []):
        t = a if code.endswith('a') else h
        key = {'SA': 'sharp_action', 'BM': 'big_money', 'PRO': 'ml_pro', 'EXP': 'ml_experts', 'MP': 'ml_model'}.get(code[:-1])
        if key: add(mlS, key, t, 'Action Network moneyline report')
    for mkt, lst in (('SPREAD', sideS), ('ML', mlS)):
        P = pub.get(mkt)
        if P and P.get('bets') is not None:
            ba, ma = P['bets'], P['money']
            for t, b_, m_ in ((a, ba, ma), (h, 100 - ba, 100 - ma)):
                if m_ - b_ >= S['money_vs_tickets']['gap']: add(lst, 'money_vs_tickets', t, f'{m_}% of money on {b_}% of tickets')
                if b_ <= S['fade_public']['max_tickets']: add(lst, 'fade_public', t, f'only {b_}% of tickets')
    # reverse line movement: Action Network opener and CFBD opener must agree on direction
    P = pub.get('SPREAD'); x['move_a'] = None
    if P and x.get('spread_h') is not None:
        try:
            open_a = float(str(P['open']).replace('PK', '0')); now_a = -x['spread_h']
            mv = now_a - open_a; x['move_a'] = mv; x['open_a'] = open_a
            mv2 = (now_a + x['open_h']) if x.get('open_h') is not None else None
            if abs(mv) >= S['rlm']['min_move'] and mv2 is not None and mv2 * mv > 0 and abs(mv2) >= 0.5 and P.get('bets') is not None:
                t = h if mv > 0 else a; tb = (100 - P['bets']) if t == h else P['bets']
                if tb < 50: add(sideS, 'rlm', t, f'spread moved {abs(mv):g} toward {t} with {tb}% of tickets (open {a} {fmt_line(open_a)}, now {fmt_line(now_a)})')
        except (ValueError, TypeError): pass

    if x.get('total') is not None:
        for code in shp.get('TOTAL', []):
            side = 'Over' if code.endswith('a') else 'Under'
            key = {'SA': 'sharp_action', 'BM': 'big_money', 'PRO': 'pro_systems', 'EXP': 'top_experts', 'MP': 'model_proj'}.get(code[:-1])
            if key: totS[side].append(mk(T[key], key, 'Action Network total report'))
        PT = pub.get('TOTAL')
        if PT and PT.get('bets') is not None:
            ob, om = PT['bets'], PT['money']
            for side, b_, m_ in (('Over', ob, om), ('Under', 100 - ob, 100 - om)):
                if m_ - b_ >= T['money_vs_tickets']['gap']: totS[side].append(mk(T['money_vs_tickets'], 'money_vs_tickets', f'{m_}% of money on {b_}% of tickets'))
                if b_ >= T['fade_public']['min_tickets']:
                    o_ = 'Under' if side == 'Over' else 'Over'
                    totS[o_].append(mk(T['fade_public'], 'fade_public', f'{b_}% of tickets on the {side.lower()}'))
            try:
                o_tot = float(str(PT['open']).lstrip('ou')); mv = x['total'] - o_tot; x['tot_open_an'] = o_tot
                mv2 = (x['total'] - x['tot_open']) if x.get('tot_open') else None
                if mv <= -T['moved_down']['min_move'] and mv2 is not None and mv2 <= -0.5:
                    p_ = T['moved_down']['pts_public_under'] if (100 - ob) >= 50 else T['moved_down']['pts']
                    if T['moved_down']['pts'] == 0: p_ = 0
                    totS['Under'].append(mk(T['moved_down'], 'moved_down', f'total {o_tot:g} to {x["total"]:g}', pts=p_))
            except (ValueError, TypeError): pass
        if x.get('l3_a') is not None and x.get('l3_h') is not None:
            rec3 = (x['l3_a'] + x['l3_h']) / 2; d = rec3 - x['total']; x['recent_tot'] = rec3
            if abs(d) >= T['fade_recent']['gap']:
                side = 'Under' if d > 0 else 'Over'
                totS[side].append(mk(T['fade_recent'], 'fade_recent', f'last 3 games average {rec3:.1f} total, line {x["total"]:g}: fade the run'))
    return sideS, mlS, totS


def score(lst): return sum(s['pts'] for s in lst)


# ---------------- pick rules ----------------
def favourite(x):
    """'a' or 'h' by no-vig moneyline, else by spread sign."""
    pa, ph = novig(x.get('ml_a'), x.get('ml_h'))
    if pa is not None and pa != 0.5: return 'a' if pa > 0.5 else 'h'
    if x.get('spread_h') is not None and x['spread_h'] != 0: return 'a' if x['spread_h'] > 0 else 'h'
    return None


def underdog_reasons(x, k, R):
    """Reasons the underdog k ('a'|'h') has, by the FCS rule's own definitions (signals.json rules_fcs)."""
    o = 'h' if k == 'a' else 'a'; out = []
    ro, rk = x.get('rest_' + o), x.get('rest_' + k)
    if 'short_week' in R['reasons'] and ro is not None and rk is not None and ro <= 6 and rk >= 7: out.append('opponent had less time off')
    lk, lo = x.get('last_' + k), x.get('last_' + o)
    if 'last_season' in R['reasons'] and lk and lo and lo[0] - lk[0] >= R.get('last_gap', 0.4): out.append('market overrates last season')
    wk, wo, nk = x.get('wp_' + k), x.get('wp_' + o), x.get('n_' + k) or 0
    if 'better_record' in R['reasons'] and wk is not None and wo is not None and nk >= R.get('min_games', 3) and wk > wo: out.append('better record this season')
    return out


def fbs_fav_vs_fcs(x, week, R, fbs_k):
    """FBS favourite vs FCS, week 11+ (Trina, Nov 9 2026). Spread pick on the FBS team when it is the favourite.
    2017-2025 week 11+: 31-18 +10.2u at the CFBD consensus close (hist/fbs_vs_fcs_2017_2025.json). Below the backtest bar (49 games); on by Trina's call."""
    if not R or not R.get('on') or week is None or week < R.get('min_week', 11) or x.get('spread_h') is None: return None
    fav = 'h' if x['spread_h'] < 0 else ('a' if x['spread_h'] > 0 else None)
    if fav is None or fav != fbs_k or abs(x['spread_h']) > R.get('max_line', 99): return None
    return dict(rule='fbs_fav_vs_fcs', market='Spread', k=fav, tier=R.get('tier'))


def decide(x, sideS, totS, RULES):
    """Apply the rules (signals.json rules_<div>) in order. Returns (side_pick or None, total_pick or None, info).
    A pick is dict(rule, market, k ('a'|'h'|'Over'|'Under'), tier)."""
    a, h = x['a'], x['h']
    sa, sh = score(sideS[a]), score(sideS[h])
    info = dict(score_a=sa, score_h=sh, lead=abs(sa - sh), fav=favourite(x))
    pk = 'a' if sa > sh else ('h' if sh > sa else None)
    info['pick'] = pk
    side = None
    fav = info['fav']
    # FCS-style rules: back the underdog on its own reasons, whatever the signal score says
    if fav and x.get('spread_h') is not None:
        dg = 'h' if fav == 'a' else 'a'
        for name in RULES['order']:
            R = RULES['side'][name]
            if not R['on'] or R.get('kind') != 'dog_reasons': continue
            rs = underdog_reasons(x, dg, R); info['reasons'] = rs
            ok = len(rs) >= R['min_reasons_any_line'] or (len(rs) >= 1 and abs(x['spread_h']) <= R['max_line_one_reason'])
            if not ok: continue
            if R['market'] == 'Moneyline':
                p = x.get('ml_' + dg)
                if p is None or not (R['min'] <= p <= R['max']): continue
            side = dict(rule=name, market=R['market'], k=dg, tier=R['tier'], reasons=rs); break
        if side: pk = None
    if pk and fav and not side:
        team = a if pk == 'a' else h
        keys = {s['key'] for s in sideS[team] if s['pts'] > 0 or s['key'] in ('rlm', 'last_season')}
        price = x.get('ml_' + pk)
        is_dog = pk != fav
        for name in RULES['order']:
            R = RULES['side'][name]
            if not R['on'] or R.get('kind') == 'dog_reasons': continue
            b = R.get('base', name)   # Nov 14 (B91): split rules share their base rule's logic
            # Nov 14 (A48): looser rules carry lead_below / not_reasons so a game fits at most one rule of each split pair
            if b == 'dog_ml' and is_dog and price is not None and R['min'] <= price <= R['max'] and keys & set(R['reasons']) and not keys & set(R.get('not_reasons', [])):
                side = dict(rule=name, market='Moneyline', k=pk, tier=R['tier']); break
            if b == 'fav_ml' and not is_dog and price is not None and R['min'] <= price <= R['max'] and info['lead'] >= R.get('min_lead', 1) and info['lead'] < R.get('lead_below', 1e9):
                side = dict(rule=name, market='Moneyline', k=pk, tier=R['tier']); break
            if (b == 'dog_spread' and is_dog and keys & set(R['reasons']) and not keys & set(R.get('not_reasons', [])) and x.get('spread_h') is not None
                    and abs(x['spread_h']) <= R.get('max_line', 99)
                    and not (R.get('no_sharp_against') and any(z['key'] == 'sharp_action' for z in sideS[h if team == a else a]))):
                side = dict(rule=name, market='Spread', k=pk, tier=R['tier']); break
            if b == 'strong_spread' and R['min_lead'] <= info['lead'] < R.get('lead_below', 1e9) and x.get('spread_h') is not None:
                side = dict(rule=name, market='Spread', k=pk, tier=R['tier']); break
    tot = None
    def _tot_side(TR):
        cnt = {s: len({z['key'] for z in totS[s] if z['key'] in TR['keys']}) for s in ('Over', 'Under')}
        has = [s for s in ('Over', 'Under') if cnt[s] > 0]
        if len(has) == 1 and cnt[has[0]] >= TR.get('min_keys', 1) and has[0] in TR.get('sides', ('Over', 'Under')): return has[0]
        return None
    for tname, TR in RULES['total'].items():   # Nov 14 (B91): every total rule, first that fits wins (fits are tried one by one in model.py)
        if not TR['on'] or x.get('total') is None: continue
        sd = _tot_side(TR)
        # Nov 14 (A48, Trina): split rules are non overlapping; a rule with not_if never fits a game its stricter rule fits (on or off)
        if sd and TR.get('not_if') and TR['not_if'] in RULES['total'] and _tot_side(RULES['total'][TR['not_if']]) == sd: sd = None
        if sd:
            tot = dict(rule=tname, market='Total', k=sd, tier=TR['tier']); break
    return side, tot, info


def grade(x, pick):
    """Returns (win True/False/None push, price) for a pick on a finished game (x has pts_a, pts_h)."""
    pa, ph = x['pts_a'], x['pts_h']
    if pick['market'] == 'Moneyline':
        price = x['ml_' + pick['k']]
        return ((pa > ph) if pick['k'] == 'a' else (ph > pa)), price
    if pick['market'] == 'Spread':
        line = -x['spread_h'] if pick['k'] == 'a' else x['spread_h']
        m = (pa - ph) if pick['k'] == 'a' else (ph - pa)
        v = m + line
        return (None if v == 0 else v > 0), x.get('price_' + pick['k']) or -110
    t = pa + ph
    if t == x['total']: return None, -110
    return ((t > x['total']) if pick['k'] == 'Over' else (t < x['total'])), (x.get('over') if pick['k'] == 'Over' else x.get('under')) or -110


def record(rows):
    """rows: list of (week, win, price) -> dict w, l, p, units, pct, be (break-even at average price)."""
    w = sum(1 for r in rows if r[1] is True); l = sum(1 for r in rows if r[1] is False); p = sum(1 for r in rows if r[1] is None)
    u = sum(payout(r[1], r[2]) for r in rows)
    bes = [breakeven(r[2]) for r in rows if r[1] is not None]
    return dict(w=w, l=l, p=p, n=w + l, units=round(u, 2), pct=round(100 * w / (w + l), 1) if w + l else None,
                be=round(100 * float(np.mean(bes)), 1) if bes else None)
