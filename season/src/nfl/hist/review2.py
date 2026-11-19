"""NFL pick-rule review #2 (Oct 29 evening), NBA-card style. Analysis only: changes nothing on the card.
Evaluation: season to date plus one column per month, plus the last 3 weeks as an early warning.
A method qualifies at 5+ picks with positive units and a win % above its break-even.
Moneylines at the cleaned Sportsbook Review closing median (8 books, quotes under 100 or over 5000 dropped, decimal median);
spreads and totals at the book's closing price (nflverse), -110 where unknown.
Line moves: opener = Action Network open and DraftKings (ESPN) open when they agree exactly (Trina's spec). Variant B reruns
the side tests with the week-of opener (weekly notes + Sportsbook Review agreeing) for comparison.
Pick-time check: the qualifying rules rerun on the old card's game-day morning lines (ledger_history.csv)."""
import sys, math, copy, json, pathlib
import numpy as np, pandas as pd, nflreadpy as nfl
D = pathlib.Path(__file__).parent; C = D.parent; sys.path.insert(0, str(C))
import rules as RU
SIG = RU.load_sig()
SCH = nfl.load_schedules([2025, 2026]).to_pandas(); LOG = RU.build_log(SCH)
T0 = pd.read_csv(D/'games.csv').merge(pd.read_csv(D/'openers2.csv'), on=['week', 'game'], how='left')
s26 = SCH[(SCH.season == 2026) & (SCH.game_type == 'REG')].copy(); s26['game'] = s26.away_team + '@' + s26.home_team
MONTH = {(int(r.week), r.game): pd.Timestamp(r.gameday).strftime('%b') for r in s26.itertuples()}
WEEKS = sorted(T0.week.unique()); LAST3 = set(WEEKS[-3:])

def with_openers(T, mode):
    T = T.copy()
    if mode == 'an_dk':
        agree = lambda a, b: a if (not pd.isna(a) and not pd.isna(b) and a == b) else np.nan
        T['open_sp_h'] = [agree(a, b) for a, b in zip(T.an_open_sp_h, T.dk_open_sp_h)]
        T['open_tot'] = [agree(a, b) for a, b in zip(T.an_open_tot, T.dk_open_tot)]
        T['open_src'] = 'AN+DK'
        for c in ('note_open_sp_h', 'note_open_tot', 'sbr_open_sp_h', 'sbr_open_tot'): T[c] = np.nan   # only the named pair counts
    return T

def morning(T):
    """Replace closing spread and total with the old card's game-day morning line (first record that day before kickoff,
    else the last record before kickoff). Spreads and totals then grade at -110; moneyline band uses the morning no-vig price."""
    L = pd.read_csv(C.parent/'nfl-card'/'scripts'/'ledger_history.csv'); L['taken'] = pd.to_datetime(L.taken, utc=True)
    s = s26.copy(); s['kick'] = pd.to_datetime(s.gameday + ' ' + s.gametime).dt.tz_localize('America/New_York').dt.tz_convert('UTC')
    K = {(int(r.week), r.game): (r.kick, pd.Timestamp(r.gameday).date()) for r in s.itertuples()}
    T = T.copy(); used = 0
    for i, r in T.iterrows():
        k = K.get((int(r.week), r.game))
        if not k: continue
        x = L[(L.week == r.week) & (L.game == r.game) & (L.taken < k[0])]
        if not len(x): continue
        day = x[x.taken.dt.tz_convert('America/Phoenix').dt.date == k[1]]
        pick = (day.sort_values('taken').groupby('market').head(1) if len(day) else x.sort_values('taken').groupby('market').tail(1)).set_index('market')
        if 'Spread' in pick.index: T.at[i, 'spread_h'] = -float(pick.loc['Spread', 'market_num'])
        if 'Total' in pick.index: T.at[i, 'total'] = float(pick.loc['Total', 'market_num'])
        if 'Moneyline' in pick.index:
            p = float(pick.loc['Moneyline', 'market_num'])/100; team = RU.M.canon_team(str(pick.loc['Moneyline', 'pick']).split(' ')[0])
            ph = p if team == r.home else 1 - p
            am = lambda q: -100*q/(1-q) if q >= .5 else 100*(1-q)/q
            T.at[i, 'm_ml_h'], T.at[i, 'm_ml_a'] = am(ph), am(1-ph)
        T.at[i, 'sp_price_a'] = T.at[i, 'sp_price_h'] = T.at[i, 'over_price'] = T.at[i, 'under_price'] = -110
        used += 1
    return T, used

# ---------------- evaluation ----------------
COLS = ['Sep', 'Oct']
def ev(picks):
    """picks: [(week, game, result, price)] -> dict of season / per month / last 3 weeks."""
    def agg(p):
        p = [(r_, pr) for r_, pr in p if not pd.isna(pr)]
        W = sum(r_ > 0 for r_, _ in p); L = sum(r_ < 0 for r_, _ in p); P = sum(r_ == 0 for r_, _ in p)
        u = sum(RU.payout(pr, r_) for r_, pr in p); b = RU.be([pr for r_, pr in p if r_ != 0])
        pct = W/(W+L) if W+L else float('nan')
        return dict(W=W, L=L, P=P, n=W+L+P, pct=pct, units=u, be=b, q=bool(W+L+P >= 5 and u > 0 and W+L and pct > b))
    out = dict(season=agg([(r_, pr) for w, g, r_, pr in picks]))
    for m in COLS: out[m] = agg([(r_, pr) for w, g, r_, pr in picks if MONTH.get((w, g)) == m])
    out['last3'] = agg([(r_, pr) for w, g, r_, pr in picks if w in LAST3])
    return out
def cell(d):
    if not d['n']: return '      -      '
    return f"{d['W']}-{d['L']}{('-'+str(d['P'])) if d['P'] else ''} {d['units']:+.1f}u"
ROWS = []
def line(lbl, picks, show=True):
    e = ev(picks); s = e['season']
    txt = (f"{lbl:60s} {cell(s):>16s} {s['pct']*100 if s['W']+s['L'] else 0:5.1f}% be {s['be']*100 if s['W']+s['L'] else 0:4.1f}% "
           f"| Sep {cell(e['Sep']):>14s} | Oct {cell(e['Oct']):>14s} | last 3 wk {cell(e['last3']):>14s} {'QUALIFIES' if s['q'] else ''}"
           f"{'  WARN last 3 wk negative' if s['q'] and e['last3']['n'] and e['last3']['units'] < 0 else ''}")
    if show: print(txt)
    ROWS.append(dict(label=lbl, **{f'{k}_{kk}': v for k in ('season', 'Sep', 'Oct', 'last3') for kk, v in e[k].items()}))
    return e
def head(t): print('\n## ' + t); ROWS.append(dict(label='## ' + t))

def scored(T):
    out = []
    for _, row in T.iterrows():
        r = {k: (None if (isinstance(v, float) and math.isnan(v)) else v) for k, v in row.to_dict().items()}
        r['margin_h'] = r['home_score'] - r['away_score']; r['total_pts'] = r['home_score'] + r['away_score']
        side, ml, tot = RU.score_game(r, LOG, SIG)
        g = RU.summarize(r, side, ml, tot); g['game'] = r['game']; g['m_ml_a'] = r.get('m_ml_a'); g['m_ml_h'] = r.get('m_ml_h')
        out.append(g)
    return out
P = lambda g, res_price: (g['week'], g['game'], *res_price)

def dog(g): return (g['away'] if g['fav'] == g['home'] else g['home']) if g['fav'] else None
TESTED = ('rlm', 'div_dog', 'pr_fade', 'expert_follow')
def reason(g, d): return any(k in TESTED and g['side_pts'][d].get(k, 0) > 0 for k in g['side_keys'][d])

# ---------------- rule versions (price limits locked) ----------------
def v_fav(lead, band_price=None):
    def f(g):
        if not (g['fav'] and g['team'] == g['fav'] and g['lead'] >= lead): return None
        pr = band_price(g) if band_price else RU.ml_price(g, g['fav'])
        if pr is None or pd.isna(pr) or not (-200 <= pr <= -100): return None
        return RU.side_res(g, g['fav'], 'ml')
    return f
def v_spread(lead, which=None):
    def f(g):
        if not (g['team'] and g['lead'] >= lead): return None
        if which == 'dog' and not (g['fav'] and g['team'] != g['fav']): return None
        if which == 'fav' and g['team'] != g['fav']: return None
        return RU.side_res(g, g['team'], 'sp')
    return f
def v_dogml(lead=1, need_reason=True, band_price=None):
    def f(g):
        d = dog(g)
        if not d or g['team'] != d or g['lead'] < lead: return None
        pr = band_price(g, d) if band_price else RU.ml_price(g, d)
        if pr is None or pd.isna(pr) or not (100 <= pr <= 200): return None
        if need_reason and not reason(g, d): return None
        return RU.side_res(g, d, 'ml')
    return f
def v_dogsp(lead=1, need_reason=True):
    def f(g):
        d = dog(g)
        if not d or g['team'] != d or g['lead'] < lead: return None
        if need_reason and not reason(g, d): return None
        return RU.side_res(g, d, 'sp')
    return f
def v_total(keys, no_against=False, side=None):
    def f(g):
        sd = RU.total_rule(g, dict(keys=keys, no_against=no_against))
        if not sd or (side and sd != side): return None
        return RU.tot_res(g, sd)
    return f
def v_over(lead):
    def f(g):
        if g['so'] - g['su'] < lead: return None
        return RU.tot_res(g, 'Over')
    return f
def run(G, f): return [P(g, z) for g in G if (z := f(g))]

VERSIONS = [
    ('Favourite moneyline -200 to -100', [('signals agree, lead 1+', v_fav(1)), ('signals agree, lead 2+', v_fav(2)), ('signals agree, lead 3+', v_fav(3))]),
    ('Spread on the signal side', [('lead 2+', v_spread(2)), ('lead 3+', v_spread(3)), ('lead 4+', v_spread(4))]),
    ('Underdog spread', [('signals on the dog + tested reason', v_dogsp(1, True)), ('signals on the dog, lead 2+', v_dogsp(2, False)), ('signals on the dog + reason, lead 2+', v_dogsp(2, True))]),
    ('Underdog moneyline +100 to +200', [('signals on the dog + reason', v_dogml(1, True)), ('signals on the dog + reason, lead 2+', v_dogml(2, True)), ('signals on the dog, lead 3+', v_dogml(3, False))]),
    ('Total, one-sided', [('money vs tickets or PRO on one side', v_total(['money_vs_tickets', 'pro_systems'])), ('... with nothing scored against', v_total(['money_vs_tickets', 'pro_systems'], True)),
                          ('PRO or big money on one side', v_total(['pro_systems', 'big_money'])), ('PRO or big money, nothing against', v_total(['pro_systems', 'big_money'], True))]),
    ('Over totals with signals', [('total score leans over by 1+', v_over(1)), ('leans over by 2+', v_over(2)), ('leans over by 3+', v_over(3)),
                                  ('money vs tickets or PRO on the over only', v_total(['money_vs_tickets', 'pro_systems'], side='Over')),
                                  ('PRO or big money on the over only', v_total(['pro_systems', 'big_money'], side='Over'))]),
]

if __name__ == '__main__':
    TA = with_openers(T0, 'an_dk'); GA = scored(TA)
    TB = with_openers(T0, 'weekof'); GB = scored(TB)
    nmv = sum(1 for _, r in TA.iterrows() if not pd.isna(r.open_sp_h))
    print(f'{len(GA)} games, weeks {WEEKS[0]}-{WEEKS[-1]}. Months: Sep = weeks 1-4, Oct = weeks 5-7. Last 3 weeks = {sorted(LAST3)}.')
    print(f'Openers: Action Network and DraftKings agree on {nmv} spreads and {TA.open_tot.notna().sum()} totals.')
    print('RLM fires (AN+DK):', sum('rlm' in g['side_keys'][t] for g in GA for t in (g['away'], g['home'])), ' (week-of):', sum('rlm' in g['side_keys'][t] for g in GB for t in (g['away'], g['home'])))
    head('Rule versions, AN+DK openers (the card as specified)')
    for grp, vs in VERSIONS:
        print(f'  {grp}')
        for lbl, f in vs: line(f'    {lbl}', run(GA, f))
    head('Same rule versions with the week-of opener instead (comparison only)')
    for grp, vs in VERSIONS[:4]:
        print(f'  {grp}')
        for lbl, f in vs: line(f'    {lbl}', run(GB, f))
    # reverse line movement alone, both opener sources
    head('Reverse line movement alone (spread)')
    for nm, G in (('AN+DK opener', GA), ('week-of opener', GB)):
        pk = []
        for g in G:
            ts = [t for t in (g['away'], g['home']) if 'rlm' in g['side_keys'][t]]
            if len(ts) == 1: pk.append(P(g, RU.side_res(g, ts[0], 'sp')))
        line(f'  RLM, {nm}', pk)
    # pick-time check on morning lines
    TM, used = morning(TA); GM = scored(TM)
    head(f'Pick-time check: game-day morning lines from the old card ({used} of {len(TM)} games), graded at -110 (moneyline at the closing price)')
    band = lambda g: (g['m_ml_h'] if g['fav'] == g['home'] else g['m_ml_a'])
    bandd = lambda g, d: (g['m_ml_h'] if d == g['home'] else g['m_ml_a'])
    for lbl, f in (('Fav ML lead 1+ (morning price band)', v_fav(1, band)), ('Fav ML lead 2+ (morning price band)', v_fav(2, band)),
                   ('Spread lead 2+', v_spread(2)), ('Spread lead 3+', v_spread(3)), ('Dog spread + reason', v_dogsp(1, True)),
                   ('Dog ML + reason (morning price band)', v_dogml(1, True, bandd)),
                   ('Total MvT or PRO one side', v_total(['money_vs_tickets', 'pro_systems'])), ('Total PRO or BM one side', v_total(['pro_systems', 'big_money']))):
        line(f'  {lbl}', run(GM, f))
    # every review test, new evaluation
    head('Full re-check test suite (season, month, last 3 weeks)')
    WM = {}
    for (w, g), m in MONTH.items(): WM.setdefault(w, m)
    def grade_new(picks, split):
        e = ev([(w, None, r_, pr) for w, r_, pr in picks])
        e2 = {'all': e['season'], 'h1': e['Sep'], 'h2': e['Oct'], 'counts': e['season']['q']}
        return e2
    # month by week (weeks 1-4 are September, 5+ October)
    global MONTH_BY_WEEK
    _ev = ev
    def ev_w(picks):
        return _ev([(w, g, r_, pr) for w, g, r_, pr in picks])
    MONTH.update({(w, None): ('Sep' if w <= 4 else 'Oct') for w in WEEKS})
    RU.grade = grade_new
    suite = []
    RU.run_tests(GA, 4, out=lambda s_: suite.append(s_))
    (D/'review2_suite.txt').write_text('\n'.join(suite).replace('W1-4', 'Sep').replace('W5+', 'Oct').replace('COUNTS', 'QUALIFIES'))
    print('full suite written to review2_suite.txt;', sum('QUALIFIES' in x for x in suite) if False else sum('COUNTS' in x for x in suite), 'test lines qualify of', sum(1 for x in suite if not x.startswith('\n') and not x.startswith('##') and x.strip()))
    pd.DataFrame(ROWS).to_csv(D/'review2_versions.csv', index=False)
    print('\nwrote review2_versions.csv')
