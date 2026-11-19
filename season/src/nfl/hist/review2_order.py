import sys, contextlib, io, pathlib
sys.argv = ['x']; sys.path.insert(0, 'hist'); sys.path.insert(0, '.')
import review2 as R
GA = R.scored(R.with_openers(R.T0, 'an_dk'))
TM, _ = R.morning(R.with_openers(R.T0, 'an_dk')); GM = R.scored(TM)
band = lambda g: (g['m_ml_h'] if g['fav'] == g['home'] else g['m_ml_a']); bandd = lambda g, d: (g['m_ml_h'] if d == g['home'] else g['m_ml_a'])
def ordered(G, rules):
    by = {n: [] for n, _ in rules}
    for g in G:
        for n, f in rules:
            z = f(g)
            if z: by[n].append(R.P(g, z)); break
    return by
# same games: dog + reason, price +100..+200: spread vs moneyline
sp, ml = [], []
for g in GA:
    d = R.dog(g)
    if d and g['team'] == d and R.reason(g, d) and 100 <= R.RU.ml_price(g, d) <= 200:
        sp.append(R.P(g, R.RU.side_res(g, d, 'sp'))); ml.append(R.P(g, R.RU.side_res(g, d, 'ml')))
R.head('Same games (dog with a reason, +100 to +200): spread vs moneyline')
R.line('  as spread', sp); R.line('  as moneyline', ml)
for nm, G, fav, dml in (('closing lines', GA, R.v_fav(1), R.v_dogml(1, True)), ('morning lines', GM, R.v_fav(1, band), R.v_dogml(1, True, bandd))):
    for ver, rs in (('LOWERED', [('fav_ml lead 1+', fav), ('spread lead 2+', R.v_spread(2)), ('dog spread + reason', R.v_dogsp(1, True)), ('dog ML + reason', dml)]),
                    ('STRICT', [('fav_ml lead 2+', R.v_fav(2, band) if G is GM else R.v_fav(2)), ('spread lead 3+', R.v_spread(3)), ('dog spread + reason, lead 2+', R.v_dogsp(2, True)),
                                ('dog ML + reason, lead 2+', R.v_dogml(2, True, bandd) if G is GM else R.v_dogml(2, True))])):
        R.head(f'{ver} side rules in order, {nm}')
        by = ordered(G, rs)
        for n, _ in rs: R.line(f'  {n}', by[n])
        R.line('  all side rules', [z for v in by.values() for z in v])
    for ver, rs in (('LOWERED', [('one-sided MvT or PRO', R.v_total(['money_vs_tickets', 'pro_systems'])), ('over lean 3+', R.v_over(3))]),
                    ('STRICT', [('one-sided PRO or BM, nothing against', R.v_total(['pro_systems', 'big_money'], True)), ('over lean 3+', R.v_over(3))])):
        R.head(f'{ver} total rules in order, {nm}')
        by = ordered(G, rs)
        for n, _ in rs: R.line(f'  {n}', by[n])
        R.line('  all total rules', [z for v in by.values() for z in v])
for nm, G, fav, dml in (('closing lines', GA, R.v_fav(1), R.v_dogml(1, True)), ('morning lines', GM, R.v_fav(1, band), R.v_dogml(1, True, bandd))):
    rs = [('fav_ml lead 1+', fav), ('dog ML + reason', dml), ('spread lead 2+', R.v_spread(2)), ('dog spread + reason', R.v_dogsp(1, True))]
    R.head(f'OPTION B (underdog moneyline before spreads), LOWERED, {nm}')
    by = ordered(G, rs)
    for n, _ in rs: R.line(f'  {n}', by[n])
    R.line('  all side rules', [z for v in by.values() for z in v])
