"""Shared signal scoring and pick rules for the NBA card. The card (render.py) and the daily re-check (recheck.py)
both import this file, so the card's signals and the tests always use the same logic.

Input is one normalized dict per game (see INPUT below). Output:
  score_game(inp)  -> side and total signal rows, scores, signal side and leads
  apply_rules(inp, S, state) -> the side pick and total pick under the active rule set, or None (No pick)

INPUT keys
  a, h                       team codes
  ml_a, ml_h                 moneyline prices (texas222 on the card, closing median in the re-check)
  sp_a, sp_pa, sp_ph         away spread value and both spread prices
  tot, tot_po, tot_pu        total line and over / under prices
  open_sp_a, open_tot, open_ml_a, open_ml_h     source 1 opening line (Action Network open)
  src2                       second source dict(sp_open_a, sp_now_a, tot_open, tot_now) (DraftKings via ESPN) or None
  ml_bets_a, ml_money_a, sp_bets_a, sp_money_a, o_bets, o_money   Action Network ticket and money %
  sig_ml, sig_sp, sig_tot    Action Network PRO codes {name: 'A'|'H'|'O'|'U'}
  margin, ptotal, pace, sdm, sr      model home margin, projected total, possessions, margin sd, Sportradar home win % or None
  stA, stH                   dict(gp, pct, strk 'W3', l10w, l10n, diff, ppg, oppg)
  restA, restH, inj {team: (pts, note)}, dsA, dsH, same_div, divA, divH
  lastA, lastH               last season win %;  cupA, cupH  title odds (American)
  lg_pace                    league pace
"""
import math, re

WEIGHTS = {'Sharp Action': 2, 'PRO Systems': 1, 'Big Money': 1}
DIVNAME = dict(SE='Southeast', AT='Atlantic', CE='Central', NW='Northwest', PA='Pacific', SW='Southwest')

def dec(a): return 1 + a/100 if a > 0 else 1 + 100/(-a)
def novig(a, b):
    x, y = 1/dec(a), 1/dec(b); return x/(x+y), y/(x+y)
def Phi(z): return 0.5*(1+math.erf(z/math.sqrt(2)))
def fmt(o): return f'+{o:g}' if o > 0 else f'{o:g}'
def sp(v): return 'pick' if v == 0 else (f'+{v:g}' if v > 0 else f'{v:g}')
def imp(o): return 100/(o+100) if o > 0 else -o/(-o+100)

# ------------------------------------------------------------------ line moves (two sources must agree)
def spread_move(inp, thr):
    """Side the spread moved toward by thr+ points at both sources ('A'/'H'), the move size, and a note. None if no agreed move."""
    m1 = inp.get('sp_now_a', inp['sp_a']) - inp['open_sp_a']   # >0: away getting more points, so the line moved toward home (Nov 12, A32: moves read to the latest line; picks price at the opener)
    s2 = inp.get('src2')
    if s2 and s2.get('sp_open_a') is not None and s2.get('sp_now_a') is not None:
        m2 = s2['sp_now_a'] - s2['sp_open_a']
        if abs(m1) >= thr and abs(m2) >= thr and (m1 > 0) == (m2 > 0):
            return ('H' if m1 > 0 else 'A'), m1, 'both sources'
        return None, m1, ('sources disagree' if (abs(m1) >= thr or abs(m2) >= thr) else '')
    return None, m1, ('second source missing' if abs(m1) >= thr else '')

def total_drop(inp):
    d1 = inp.get('tot_now_v', inp['tot']) - inp['open_tot']
    s2 = inp.get('src2')
    if s2 and s2.get('tot_open') is not None and s2.get('tot_now') is not None:
        d2 = s2['tot_now'] - s2['tot_open']
        return (d1 < 0 and d2 < 0), d1, d2
    return False, d1, None   # a drop only counts when both sources show it

# ------------------------------------------------------------------ signal scoring (same weights as the card has used all season)
def score_game(inp, rlm_thr=0.5):
    a, h = inp['a'], inp['h']; nm = {'A': a, 'H': h}
    S = dict(srows=[], sc={'A': 0, 'H': 0}, trows=[], tc={'O': 0, 'U': 0})
    def add(rows, sc, sig, mkt, side, pts, note):
        rows.append((sig, mkt, side, pts, note)); sc[side] += pts
    sr, sc = S['srows'], S['sc']
    seen = set()
    for src, mk in ((inp['sig_sp'], 'Spread'), (inp['sig_ml'], 'Moneyline')):
        for s, sd in src.items():
            if (s, sd) in seen: continue
            seen.add((s, sd)); add(sr, sc, f'Action Network {s}', mk, sd, WEIGHTS[s], f'PRO signal is lit on this side ({mk.lower()}).')
    ba, ma = inp['ml_bets_a'], inp['ml_money_a']
    if ma - ba >= 10: add(sr, sc, 'Money % above ticket %', 'Moneyline', 'A', 1, f'{a}: {ba}% of bets but {ma}% of money.')
    elif ba - ma >= 10: add(sr, sc, 'Money % above ticket %', 'Moneyline', 'H', 1, f'{h}: {100-ba}% of bets but {100-ma}% of money.')
    if ba <= 35: add(sr, sc, 'Fade the public', 'Moneyline', 'A', 1, f'{100-ba}% of moneyline tickets are on {h}.')
    elif ba >= 65: add(sr, sc, 'Fade the public', 'Moneyline', 'H', 1, f'{ba}% of moneyline tickets are on {a}.')
    lm, mv, how = spread_move(inp, rlm_thr)
    S['lm_side'] = None
    if lm:
        tb = inp['sp_bets_a'] if lm == 'A' else 100 - inp['sp_bets_a']
        txt = f"spread opened {a} {sp(inp['open_sp_a'])}, now {sp(inp.get('sp_now_a', inp['sp_a']))} ({how})"
        if tb < 50:
            add(sr, sc, 'Reverse line movement', 'Spread', lm, 2, f'Line moved toward {nm[lm]} with only {tb}% of spread tickets: {txt}.'); S['lm_side'] = lm
        else: sr.append(('Line move with the public', 'Spread', lm, 0, f'{txt}. Moved with the ticket majority, so it is not a sharp tell.'))
    elif how in ('sources disagree', 'second source missing'):
        sr.append(('Line move', 'Spread', 'A', 0, f"Opened {a} {sp(inp['open_sp_a'])}, now {sp(inp.get('sp_now_a', inp['sp_a']))}, but the second source {'does not show the same move' if how == 'sources disagree' else 'was not read'}, so no call."))
    pm = Phi(inp['margin']/inp['sdm'])
    if inp.get('sr'): pm = (pm + inp['sr']/100)/2
    estH = 0.4*pm + 0.6*novig(inp['ml_a'], inp['ml_h'])[1]
    S['estH'] = estH
    ms = 'H' if estH > 0.5 else 'A'
    add(sr, sc, 'Card projection', 'Moneyline', ms, 1, f"Blended win chance {100*max(estH,1-estH):.1f}%; model margin {h} {inp['margin']:+.1f}.")
    A, H = inp['stA'], inp['stH']
    if inp['restA'] == 0 and inp['restH'] > 0: add(sr, sc, 'Rest edge', 'Moneyline', 'H', 1, f'{a} on the second night of a back-to-back.')
    if inp['restH'] == 0 and inp['restA'] > 0: add(sr, sc, 'Rest edge', 'Moneyline', 'A', 1, f'{h} on the second night of a back-to-back.')
    for t, sd in ((a, 'A'), (h, 'H')):
        if t in inp['inj']: add(sr, sc, 'Injury edge', 'Moneyline', 'H' if sd == 'A' else 'A', 1, f"{t} missing starters: {inp['inj'][t][1]}.")
    if inp.get('dsA') is not None and not inp['same_div'] and abs(inp['dsA'] - inp['dsH']) >= 2.0:
        add(sr, sc, 'Division strength', 'Moneyline', 'A' if inp['dsA'] > inp['dsH'] else 'H', 1,
            f"{DIVNAME[inp['divA']]} {inp['dsA']:+.1f} vs {DIVNAME[inp['divH']]} {inp['dsH']:+.1f} per game against other divisions.")
    add(sr, sc, 'Home court', 'Moneyline', 'H', 1, f'{h} at home.')
    for sd, st, t in (('A', A, a), ('H', H, h)):
        m = re.match(r'([WL])(\d+)', st.get('strk') or '')
        if m and m.group(1) == 'W' and int(m.group(2)) >= 3: add(sr, sc, 'Hot streak', 'Moneyline', sd, 1, f'{t} has won {m.group(2)} straight.')
        if m and m.group(1) == 'L' and int(m.group(2)) >= 3: add(sr, sc, 'Cold streak', 'Moneyline', 'H' if sd == 'A' else 'A', 1, f'{t} has lost {m.group(2)} straight.')
    if A['gp'] >= 5 and H['gp'] >= 5:
        fa, fh = A['l10w']/max(A['l10n'], 1), H['l10w']/max(H['l10n'], 1)
        if abs(fa - fh) >= 0.20: add(sr, sc, 'Recent form', 'Moneyline', 'A' if fa > fh else 'H', 1, f"Last 10: {a} {A['l10w']}-{A['l10n']-A['l10w']}, {h} {H['l10w']}-{H['l10n']-H['l10w']}.")
        if abs(A['diff'] - H['diff']) >= 5: add(sr, sc, 'Point differential', 'Moneyline', 'A' if A['diff'] > H['diff'] else 'H', 1, f"Per game: {a} {A['diff']:+.1f}, {h} {H['diff']:+.1f}.")
    else:
        sr.append(('Recent form / point differential', 'Moneyline', 'A', 0, f"Early season ({A['gp']} and {H['gp']} games played); scored from 5 games on."))
    la, lh = inp['lastA'], inp['lastH']
    if abs(la - lh) >= 0.10: add(sr, sc, 'Track record', 'Moneyline', 'A' if la > lh else 'H', 1, f'Last season win %: {a} {la:.3f}, {h} {lh:.3f}.')
    for sd, t, st, l in (('A', a, A, la), ('H', h, H, lh)):
        if st['gp'] >= 5:
            if l - st['pct'] >= 0.15 and l >= 0.600: add(sr, sc, 'Bounce-back candidate', 'Moneyline', sd, 1, f"{t} is {st['pct']:.3f} after {l:.3f} last season.")
            if st['pct'] - l >= 0.20 and l <= 0.450: add(sr, sc, 'Regression watch', 'Moneyline', 'H' if sd == 'A' else 'A', 1, f"{t} is {st['pct']:.3f} after {l:.3f} last season.")
    if inp.get('cupA') and inp.get('cupH'):
        ca, ch = imp(inp['cupA']), imp(inp['cupH'])
        if max(ca, ch)/min(ca, ch) >= 2: add(sr, sc, 'Roster strength', 'Moneyline', 'A' if ca > ch else 'H', 1, f"Title odds: {a} {fmt(inp['cupA'])}, {h} {fmt(inp['cupH'])}.")
    side = 'A' if sc['A'] > sc['H'] else ('H' if sc['H'] > sc['A'] else ms)
    other = 'H' if side == 'A' else 'A'
    S['side'], S['other'], S['ml_lead'] = side, other, sc[side] - sc[other]
    # spread-only rows for the signal side
    spl = inp['sp_a'] if side == 'A' else -inp['sp_a']
    my_p, ot_p = (inp['sp_pa'], inp['sp_ph']) if side == 'A' else (inp['sp_ph'], inp['sp_pa'])
    pmod = Phi(((-inp['margin'] if side == 'A' else inp['margin']) + spl)/inp['sdm'])
    p_sp = 0.4*pmod + 0.6*novig(my_p, ot_p)[0]
    me = sc[side]; ot = sc[other]; prows = []
    pb = inp['sp_bets_a'] if side == 'A' else 100 - inp['sp_bets_a']; pmn = inp['sp_money_a'] if side == 'A' else 100 - inp['sp_money_a']
    if pmn - pb >= 10: me += 1; prows.append(('Money % above ticket %', 'Spread', side, 1, f'{pb}% of spread bets, {pmn}% of the money.'))
    elif pb - pmn >= 10: ot += 1; prows.append(('Money % above ticket %', 'Spread', other, 1, f'{100-pb}% of spread bets, {100-pmn}% of the money on the other side.'))
    if pb <= 35: me += 1; prows.append(('Fade the public', 'Spread', side, 1, f'Only {pb}% of spread tickets on {nm[side]}.'))
    elif pb >= 65: ot += 1; prows.append(('Fade the public', 'Spread', other, 1, f'{pb}% of spread tickets on {nm[side]}.'))
    if spl > 0 and p_sp >= 0.55: me += 1; prows.append(('Points cushion', 'Spread', side, 1, f'Cashes on a win or a loss by less than {spl:g}: projected {100*p_sp:.1f}%.'))
    if spl < 0 and p_sp < 0.45: ot += 2; prows.append(('Needs to win by the number', 'Spread', other, 2, f'{nm[side]} covers {sp(spl)} only about {100*p_sp:.1f}% of the time.'))
    S['prows'], S['sp_lead'], S['side_spread'], S['p_sp'] = prows, me - ot, spl, p_sp
    # totals
    tr, tc = S['trows'], S['tc']
    for k, v in inp['sig_tot'].items(): add(tr, tc, f'Action Network {k}', 'Total', v, WEIGHTS[k], 'PRO signal is lit on this side.')
    ob, om = inp['o_bets'], inp['o_money']
    if ob >= 75: add(tr, tc, 'Fade the public', 'Total', 'U', 1, f'{ob}% of tickets on the over.')
    elif ob <= 25: add(tr, tc, 'Fade the public', 'Total', 'O', 1, f'{100-ob}% of tickets on the under.')
    if om - ob >= 10: add(tr, tc, 'Money % above ticket %', 'Total', 'O', 1, f'Over {ob}% of bets, {om}% of money.')
    elif ob - om >= 10: add(tr, tc, 'Money % above ticket %', 'Total', 'U', 1, f'Under {100-ob}% of bets, {100-om}% of money.')
    dropped, d1, d2 = total_drop(inp)
    S['dropped'] = dropped
    src = f"opened {inp['open_tot']:g}, now {inp.get('tot_now_v', inp['tot']):g}" + (f"; second source {d2:+g}" if d2 is not None else '; one source only')
    if dropped: add(tr, tc, 'Total moved down', 'Total', 'U', 2 if ob >= 50 else 1, f'Total dropped ({src}) against {ob}% over tickets.')
    elif d1 < 0: tr.append(('Total moved down (one source)', 'Total', 'U', 0, f'Total dropped ({src}), but the second source does not confirm it, so no call.'))
    elif d1 > 0: tr.append(('Total moved up', 'Total', 'O', 0, f'Total rose ({src}). Moved with the over tickets, so it is not a sharp tell.'))
    d = inp['ptotal'] - inp['tot']
    if abs(d) >= 3: add(tr, tc, 'Card projection', 'Total', 'O' if d > 0 else 'U', 1, f"Projected {inp['ptotal']:.1f} vs {inp['tot']:g}.")
    else: tr.append(('Card projection', 'Total', 'O' if d > 0 else 'U', 0, f"Projected {inp['ptotal']:.1f}, within 3 points of {inp['tot']:g}."))
    if A['gp'] >= 5 and H['gp'] >= 5:
        rs = (A['ppg'] + A['oppg'] + H['ppg'] + H['oppg'])/2
        if rs >= inp['tot'] + 6: add(tr, tc, 'Recent scoring', 'Total', 'O', 1, f'Season games average {rs:.1f} total points.')
        elif rs <= inp['tot'] - 6: add(tr, tc, 'Recent scoring', 'Total', 'U', 1, f'Season games average {rs:.1f} total points.')
    if inp['pace'] >= 101.5: add(tr, tc, 'Pace', 'Total', 'O', 1, f"Projected {inp['pace']:.1f} possessions.")
    elif inp['pace'] <= 98.5: add(tr, tc, 'Pace', 'Total', 'U', 1, f"Projected {inp['pace']:.1f} possessions.")
    ts = 'O' if tc['O'] > tc['U'] else ('U' if tc['U'] > tc['O'] else ('O' if d > 0 else 'U'))
    S['tside'], S['t_lead'] = ts, tc[ts] - tc['U' if ts == 'O' else 'O']
    return S


# B78 (Nov 13): one tier basis for every side rule: the pick side's signal lead in its own market.
# Betting signals (Action Network PRO, money vs tickets, fade the public, reverse line movement) count only in the market they were read from;
# team facts (projection, rest, injuries, home court, form, streaks, division, track record, roster) are game context and count in every side market.
BETTING = ('Action Network', 'Money % above', 'Fade the public', 'Reverse line movement', 'Line move')
def market_lead(S, mk, side):
    other = 'H' if side == 'A' else 'A'; f = a = 0
    rows = list(S['srows']) + (list(S.get('prows', [])) if mk == 'Spread' else [])
    for (sig, m, sd, pts, note) in rows:
        if not pts: continue
        if sig.startswith(BETTING) and m != mk: continue
        if sd == side: f += pts
        elif sd == other: a += pts
    return f - a, f, a

# ------------------------------------------------------------------ rules: the rule set lives in signals.py (one rule set per card)
from signals import RULES, FAV_MIN, FAV_MAX, DOG_MIN, DOG_MAX
DEFAULT_STATE = {k: dict(on=(k != 'OVER'), variant='lowered') for k in RULES}

def rule_desc(rid, state):
    v = (state or DEFAULT_STATE).get(rid, DEFAULT_STATE[rid])['variant']
    return RULES[rid]['variants'][v]['desc']

def _st(state, rid):
    return (state or DEFAULT_STATE).get(rid, DEFAULT_STATE[rid])

def candidates(inp, S, state=None):
    """Every rule that fires for this game (side rules and total rules), before choosing one per market."""
    out = []
    a, h = inp['a'], inp['h']
    fav = None
    if inp['ml_a'] != inp['ml_h']: fav = 'A' if dec(inp['ml_a']) < dec(inp['ml_h']) else 'H'
    if fav:
        dog = 'H' if fav == 'A' else 'A'
        fp = inp['ml_a'] if fav == 'A' else inp['ml_h']; dp = inp['ml_a'] if dog == 'A' else inp['ml_h']
        st = _st(state, 'FAV_ML'); P = RULES['FAV_ML']['variants'][st['variant']]
        if FAV_MIN <= fp <= FAV_MAX and S['side'] == fav and S['ml_lead'] >= P['lead']:
            out.append(dict(rule='FAV_ML', market='Moneyline', side=fav, price=fp))
        st = _st(state, 'DOG_ML'); P = RULES['DOG_ML']['variants'][st['variant']]
        if DOG_MIN <= dp <= DOG_MAX and S['side'] == dog and S['ml_lead'] >= P['lead']:
            if not P['need_move'] or S.get('lm_side') == dog:
                out.append(dict(rule='DOG_ML', market='Moneyline', side=dog, price=dp))
    st = _st(state, 'SPREAD_MOVE'); P = RULES['SPREAD_MOVE']['variants'][st['variant']]
    lm, mv, how = spread_move(inp, P['thr'])
    if lm:
        tb = inp['sp_bets_a'] if lm == 'A' else 100 - inp['sp_bets_a']
        if tb < 50:
            spl = inp['sp_a'] if lm == 'A' else -inp['sp_a']
            out.append(dict(rule='SPREAD_MOVE', market='Spread', side=lm, line=spl, price=inp['sp_pa'] if lm == 'A' else inp['sp_ph'], how=how))
    st = _st(state, 'UNDER_DROP'); P = RULES['UNDER_DROP']['variants'][st['variant']]
    if S['dropped'] and inp['o_bets'] >= P['min_over']:
        out.append(dict(rule='UNDER_DROP', market='Total', side='U', line=inp['tot'], price=inp['tot_pu']))
    return out

def apply_rules(inp, S, state=None, records=None):
    """One side pick (moneyline or spread) and one total pick, each from an active rule, else None (No pick).
    When two side rules fire, the one with more season-to-date units wins (spread first on a tie)."""
    C = [c for c in candidates(inp, S, state) if _st(state, c['rule'])['on']]
    rec = lambda r: ((records or {}).get(r) or {}).get('u', 0)
    sides = sorted([c for c in C if c['market'] != 'Total'], key=lambda c: (-rec(c['rule']), c['market'] != 'Spread'))
    tots = [c for c in C if c['market'] == 'Total']
    return (sides[0] if sides else None), (tots[0] if tots else None), C

# ------------------------------------------------------------------ grading helpers (shared with the re-check)
def grade_side(c, as_, hs):
    m = (as_ - hs) if c['side'] == 'A' else (hs - as_)
    if c['market'] == 'Moneyline': return 'win' if m > 0 else 'loss'
    v = m + c['line']; return 'push' if v == 0 else ('win' if v > 0 else 'loss')
def grade_total(c, as_, hs):
    t = as_ + hs
    if t == c['line']: return 'push'
    return 'win' if (t > c['line']) == (c['side'] == 'O') else 'loss'
def units(result, price):
    return (dec(price) - 1) if result == 'win' else (-1 if result == 'loss' else 0)
def summarize(rows):
    """rows: list of (result, price). W-L-P, win %, units, break-even."""
    w = sum(1 for r, _ in rows if r == 'win'); l = sum(1 for r, _ in rows if r == 'loss'); p = sum(1 for r, _ in rows if r == 'push')
    u = sum(units(r, pr) for r, pr in rows)
    be = [1/dec(pr) for r, pr in rows if r != 'push']
    return dict(w=w, l=l, p=p, n=w+l, pct=(w/(w+l) if w+l else 0), u=round(u, 2), be=(sum(be)/len(be) if be else 0))
def rec_txt(s):
    if not s or not (s['n'] or s['p']): return '0-0'
    return f"{s['w']}-{s['l']}" + (f"-{s['p']}" if s['p'] else '') + f", {s['u']:+.2f}u"
