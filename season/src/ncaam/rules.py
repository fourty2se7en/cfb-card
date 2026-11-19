"""NCAA card rules (men and women). Same rule families as the NBA card, plus the college tests.
Shared by build.py (today's picks) and recheck.py (every game played this season, and the backtest in bt_run.js uses the same logic in JS).

Game record (one per game, all spreads are the HOME spread):
  lg, season, date (YYYYMMDD), home, away, hconf, aconf, conf_game, neutral, hrank, arank, hs, as_,
  o1, c1 (book 1 open/close spread), t1o, t1c (book 1 totals), o2, c2, t2o, t2c (book 2), sp, tot (consensus close), mlh, mla
Live: book 1 = Action Network open vs texas222 now; book 2 = ESPN core odds (DraftKings) open vs now. A move counts only when both
books show it; when only one book has an opening number, that one is used (the 2024-25 and 2025-26 backtest seasons have one book).
Signal score (backtest-able signals only; tickets, money, Sharp Action, Big Money and PRO Systems have no history for college):
  line move toward the side at both books 2, model projection beats the spread by 1.5+ 1, rest edge 2+ days 1, home court 1,
  form (last 5) 0.4+ better 1, average margin 3+ better 1, bounce back after a 10+ point loss 1. Lead = side score minus other side.
Price limits are locked: favorite moneyline no longer than -200, underdog +100 to +200."""
RULES = {
    # Nov 13 (Trina, A39/B91): every two version rule is now separate rules with their own tiers and status records
    'FAV_ML_2': dict(name='FG Favorite ML Lead 2', market='Moneyline', variants=['lowered'], old='FAV_ML', old_variant='lowered'),
    'FAV_ML_3': dict(name='FG Favorite ML Lead 3+', market='Moneyline', variants=['lowered'], old='FAV_ML', old_variant='strict'),
    'DOG_ML_1': dict(name='FG Underdog ML No Line Move', market='Moneyline', variants=['lowered'], old='DOG_ML', old_variant='lowered'),
    'DOG_ML_MOVE': dict(name='FG Underdog ML Lead 1+ with Line Move', market='Moneyline', variants=['lowered'], old='DOG_ML', old_variant='strict'),
    'SPREAD_MOVE_05': dict(name='FG Spread Move 0.5 to 1', market='Spread', variants=['lowered'], old='SPREAD_MOVE', old_variant='lowered'),
    'SPREAD_MOVE_1': dict(name='FG Spread Move 1+', market='Spread', variants=['lowered'], old='SPREAD_MOVE', old_variant='strict'),
    'UNDER_DROP_ANY': dict(name='FG Total Drop Under 2 Under', market='Total', variants=['lowered'], old='UNDER_DROP', old_variant='lowered'),
    'UNDER_DROP_2': dict(name='FG Total Drop 2+ Outside 4.5 to 6.5 Under', market='Total', variants=['lowered'], old='UNDER_DROP', old_variant='strict'),
    'UNDER_DROP_BAND': dict(name='FG Total Drop 4.5 to 6.5 Under', market='Total', variants=['lowered'], old='UNDER_DROP', old_variant='band'),
    'OVER_ANY': dict(name='FG Total Rise Under 2 Over', market='Total', variants=['lowered'], old='OVER', old_variant='lowered'),
    'OVER_2': dict(name='FG Total Rise 2+ Over', market='Total', variants=['lowered'], old='OVER', old_variant='strict'),
    # College rules approved by Trina on Nov 2, 2026 (single variant)
    'ROAD1DAY_FADE': dict(name='FG Road Team 1 Day Rest Fade', market='Spread', variants=['lowered'], lg='M'),
    'MODEL_EDGE': dict(name='FG Model Edge 3+ Spread', market='Spread', variants=['lowered'], lg='W'),
    'NEUTRAL_UNDER': dict(name='FG Neutral Site Under', market='Total', variants=['lowered'], lg='W'),
    # Approved by Trina Nov 3, 2026: efficiency model total 4+ below the opening total, Nov and Dec only (backtest graded at the open)
    'EARLY_UNDER_OPEN': dict(name='FG Early Season Under vs Opener', market='Total', variants=['lowered']),
    # Efficiency model rules (Nov 3, 2026 backtest v2). Tracked on both cards; live per rules_state.
    'EARLY_OVER_OPEN': dict(name='FG Early Season Over vs Opener', market='Total', variants=['lowered']),
    'EFF_SPREAD': dict(name='FG Efficiency Spread 3+', market='Spread', variants=['lowered']),
    'EFF_OVER': dict(name='FG Efficiency Over 3+', market='Total', variants=['lowered']),
}
HCA = 3.0
FAV_MIN, FAV_MAX, DOG_MIN, DOG_MAX = -200, -100, 100, 200

def win_units(price): return price / 100 if price > 0 else 100 / -price
def breakeven(price): return 100 / (price + 100) if price > 0 else -price / (-price + 100)

def moves(g):
    def mv(o, c): return None if o is None or c is None else c - o
    m1, m2 = mv(g.get('o1'), g.get('c1')), mv(g.get('o2'), g.get('c2'))
    def both(thr, sign):
        if m1 is not None and m2 is not None: return sign*m1 >= thr and sign*m2 >= thr
        if m1 is not None: return sign*m1 >= thr
        return m2 is not None and sign*m2 >= thr
    t = [x for x in (mv(g.get('t1o'), g.get('t1c')), mv(g.get('t2o'), g.get('t2c'))) if x is not None]
    d = dict(home=both(0.5, -1), away=both(0.5, 1), home1=both(1, -1), away1=both(1, 1),
                drop=bool(t) and all(x < 0 for x in t), drop2=bool(t) and all(x <= -2 for x in t),
                dropband=bool(t) and all(x < 0 for x in t) and 4.5 <= min(-x for x in t) <= 6.5,   # Trina Nov 9 (A12): band version
                up=bool(t) and all(x > 0 for x in t), up2=bool(t) and all(x >= 2 for x in t), m1=m1, m2=m2, t=t)
    # A48 (Trina, Nov 14): split rules are disjoint. The looser rule fires only on the band the stricter rule misses.
    d['home05'] = d['home'] and not d['home1']; d['away05'] = d['away'] and not d['away1']
    d['drop_lt2'] = d['drop'] and not d['drop2']; d['drop2_out'] = d['drop2'] and not d['dropband']
    d['up_lt2'] = d['up'] and not d['up2']
    return d

def signals(g, ctx):
    """ctx: proj (home margin), rest_h, rest_a, form_h, form_a, avgm_h, avgm_a, lastm_h, lastm_a (None when unknown)."""
    M = moves(g); sh = sa = 0; why_h, why_a = [], []
    if M['home']: sh += 2; why_h.append('line moved toward it at both books (2)')
    if M['away']: sa += 2; why_a.append('line moved toward it at both books (2)')
    p, sp = ctx.get('proj'), g['sp']
    if p is not None and sp is not None:
        if p + sp >= 1.5: sh += 1; why_h.append(f'projection beats the spread by {p+sp:.1f}')
        if p + sp <= -1.5: sa += 1; why_a.append(f'projection beats the spread by {-(p+sp):.1f}')
    rh, ra = ctx.get('rest_h'), ctx.get('rest_a')
    if rh is not None and ra is not None:
        if rh - ra >= 2: sh += 1; why_h.append(f'rest edge {rh} vs {ra} days')
        if ra - rh >= 2: sa += 1; why_a.append(f'rest edge {ra} vs {rh} days')
    if not g['neutral']: sh += 1; why_h.append('home court')
    fh, fa = ctx.get('form_h'), ctx.get('form_a')
    if fh is not None and fa is not None:
        if fh - fa >= 0.4: sh += 1; why_h.append('better form (last 5)')
        if fa - fh >= 0.4: sa += 1; why_a.append('better form (last 5)')
    ah, aa = ctx.get('avgm_h'), ctx.get('avgm_a')
    if ah is not None and aa is not None:
        if ah - aa >= 3: sh += 1; why_h.append('better average margin')
        if aa - ah >= 3: sa += 1; why_a.append('better average margin')
    if (ctx.get('lastm_h') or 0) <= -10 and ctx.get('lastm_h') is not None: sh += 1; why_h.append('bounce back after a 10+ point loss')
    if (ctx.get('lastm_a') or 0) <= -10 and ctx.get('lastm_a') is not None: sa += 1; why_a.append('bounce back after a 10+ point loss')
    return dict(sh=sh, sa=sa, lead=sh - sa, why_h=why_h, why_a=why_a, M=M, proj=p, rest_h=rh, rest_a=ra)

def candidates(g, S, state):
    """All rule fits for one game. state: {rule: {'on': bool, 'variant': 'lowered'|'strict'}}. Returns list of dicts."""
    out = []; M = S['M']; lead = S['lead']
    on = lambda r: state.get(r, {}).get('on')
    var = lambda r: state.get(r, {}).get('variant', 'lowered')
    mlh, mla = g.get('mlh'), g.get('mla')
    if mlh is not None and mla is not None:
        fav = 'home' if mlh < mla else 'away'; fp = mlh if fav == 'home' else mla; dp = mla if fav == 'home' else mlh
        flead = lead if fav == 'home' else -lead
        for rk, need, cap in (('FAV_ML_2', 2, 3), ('FAV_ML_3', 3, 99)):   # A48: Lead 2 is exactly 2, Lead 3+ is 3 or more
            if on(rk) and FAV_MIN <= fp <= FAV_MAX and need <= flead < cap:
                out.append(dict(rule=rk, variant='lowered', market='Moneyline', side=fav, price=fp, lead=flead))
        dog = 'away' if fav == 'home' else 'home'; dmoved = M['away'] if dog == 'away' else M['home']
        for rk, mv in (('DOG_ML_1', False), ('DOG_ML_MOVE', True)):
            if on(rk) and DOG_MIN <= dp <= DOG_MAX and -flead >= 1 and (dmoved if mv else not dmoved):   # A48: DOG_ML_1 only with no line move
                out.append(dict(rule=rk, variant='lowered', market='Moneyline', side=dog, price=dp, lead=-flead))
    for rk, sfx in (('SPREAD_MOVE_05', '05'), ('SPREAD_MOVE_1', '1')):   # A48: 0.5 to 1 vs 1+
        if on(rk) and g.get('sp') is not None:
            for side in ('home', 'away'):
                if M[side + sfx] and (g.get('tix_' + side) is None or g['tix_' + side] < 50):   # live: under 50% of spread tickets on that side
                    out.append(dict(rule=rk, variant='lowered', market='Spread', side=side, price=g.get('sp_price_' + side, -110)))
    for rk, mk in (('UNDER_DROP_ANY', 'drop_lt2'), ('UNDER_DROP_2', 'drop2_out'), ('UNDER_DROP_BAND', 'dropband')):   # A48: disjoint
        if on(rk) and M[mk]:
            out.append(dict(rule=rk, variant='lowered', market='Total', side='under', price=g.get('u_price', -110)))
    # ROAD1DAY_FADE: road team on 1 day rest (back to back), home team on 2+ days: home team ATS
    if on('ROAD1DAY_FADE') and g.get('sp') is not None and S.get('rest_a') is not None and S.get('rest_h') is not None and S['rest_a'] <= 1 and S['rest_h'] >= 2:
        out.append(dict(rule='ROAD1DAY_FADE', variant='lowered', market='Spread', side='home', price=g.get('sp_price_home', -110)))
    # MODEL_EDGE: projection beats the spread by 3+ points
    if on('MODEL_EDGE') and g.get('sp') is not None and S.get('proj') is not None and abs(S['proj'] + g['sp']) >= 3:
        side = 'home' if S['proj'] + g['sp'] > 0 else 'away'
        out.append(dict(rule='MODEL_EDGE', variant='lowered', market='Spread', side=side, price=g.get('sp_price_' + side, -110)))
    # EARLY_UNDER_OPEN: Nov/Dec, efficiency model total 4+ points below the opening total -> under
    ot = g.get('t2o') if g.get('t2o') is not None else g.get('t1o')
    if on('EARLY_UNDER_OPEN') and g.get('month') in (11, 12) and g.get('etot') is not None and ot is not None and g.get('tot') is not None and g['etot'] <= ot - 4:
        out.append(dict(rule='EARLY_UNDER_OPEN', variant='lowered', market='Total', side='under', price=g.get('u_price', -110), open_tot=ot, etot=g['etot']))
    if on('EARLY_OVER_OPEN') and g.get('month') in (11, 12) and g.get('etot') is not None and ot is not None and g.get('tot') is not None and g['etot'] >= ot + 4:
        out.append(dict(rule='EARLY_OVER_OPEN', variant='lowered', market='Total', side='over', price=g.get('o_price', -110), open_tot=ot, etot=g['etot']))
    # EFF_SPREAD: efficiency model margin beats the spread by 3+ points
    if on('EFF_SPREAD') and g.get('emar') is not None and g.get('sp') is not None and abs(g['emar'] + g['sp']) >= 3:
        side = 'home' if g['emar'] + g['sp'] > 0 else 'away'
        out.append(dict(rule='EFF_SPREAD', variant='lowered', market='Spread', side=side, price=g.get('sp_price_' + side, -110)))
    # EFF_OVER: efficiency model total 3+ above the posted total
    if on('EFF_OVER') and g.get('etot') is not None and g.get('tot') is not None and g['etot'] >= g['tot'] + 3:
        out.append(dict(rule='EFF_OVER', variant='lowered', market='Total', side='over', price=g.get('o_price', -110)))
    # NEUTRAL_UNDER: under at a neutral site
    if on('NEUTRAL_UNDER') and g.get('neutral') and g.get('tot') is not None:
        out.append(dict(rule='NEUTRAL_UNDER', variant='lowered', market='Total', side='under', price=g.get('u_price', -110)))
    for rk, mk in (('OVER_ANY', 'up_lt2'), ('OVER_2', 'up2')):   # A48: disjoint
        if on(rk) and M[mk]:
            out.append(dict(rule=rk, variant='lowered', market='Total', side='over', price=g.get('o_price', -110)))
    return out

def grade(c, g):
    """+1 win, -1 loss, 0 push for a candidate c on finished game g (hs, as_)."""
    m = g['hs'] - g['as_']
    if c['market'] == 'Moneyline': return 1 if (m > 0) == (c['side'] == 'home') else -1
    if c['market'] == 'Spread':
        sp = g['sp'] if c['side'] == 'home' else -g['sp']; mm = m if c['side'] == 'home' else -m
        v = mm + sp; return (v > 0) - (v < 0)
    tot = g['hs'] + g['as_']; v = (g['tot'] - tot) if c['side'] == 'under' else (tot - g['tot'])
    return (v > 0) - (v < 0)

def summarize(rows):
    """rows: list of (result, price). Returns w, l, p, n, pct, u, be."""
    w = sum(1 for r, _ in rows if r > 0); l = sum(1 for r, _ in rows if r < 0); p = len(rows) - w - l
    u = sum(win_units(pr) if r > 0 else (-1 if r < 0 else 0) for r, pr in rows)
    bes = [breakeven(pr) for r, pr in rows if r != 0]
    return dict(w=w, l=l, p=p, n=len(rows), pct=(w / (w + l)) if w + l else None, u=round(u, 2), be=(sum(bes) / len(bes)) if bes else None)
