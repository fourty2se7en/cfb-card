"""Nov 12 (B56, B64, B74): NBA_TOT_CAL, NBA_TOT_MOVE, MODEL_ONLY_* (Season Cards tools/model_tests harness) and NBA_1H_FAV,
each with real tiers (the pick side's signal lead in its own market, one scale). Season replay at the close (walk-forward)
per tier, and today's fits at the opening line (A32).   python3 newrules.py <today> <out json>"""
import json, sys, collections, math
import season_build as SB, pickrules as P, harness as H
from scipy.stats import norm
def sc(l): return 'Strong' if l >= 4 else ('Solid' if l >= 2 else 'Lean')
DEF = {  # key: (market, variant, calibrate, need_move)
 'NBA_TOT_CAL': ('Total', 'blend', True, False),
 'NBA_TOT_MOVE': ('Total', 'raw', False, True),
 'MODEL_ONLY_SPREAD': ('Spread', 'raw', False, False),
 'MODEL_ONLY_TOTAL': ('Total', 'raw', False, False),
 'MODEL_ONLY_MONEYLINE': ('Moneyline', 'raw', False, False)}
def row(g):
    i = g['inp']
    return dict(sport='nba', date=g['d'], as_=g['as_'], hs=g['hs'], hm=i['margin'], sd_m=12.5, sd_t=18.0,
                sp_close_h=-i['sp_a'], sp_open_h=(-i['open_sp_a'] if i.get('open_sp_a') is not None else None), sp_ph=i['sp_ph'], sp_pa=i['sp_pa'],
                tot_close=i['tot'], tot_m=i['ptotal'], tot_open=i.get('open_tot'), po=i['tot_po'], pu=i['tot_pu'],
                ml_h=i['ml_h'], ml_a=i['ml_a'], ml_open_h=i.get('open_ml_h'), ml_open_a=i.get('open_ml_a'))
def tier_of(S, mk, side_is_A):
    if mk == 'Total': d = S['tc']['O'] - S['tc']['U']; return sc(d if side_is_A else -d), d if side_is_A else -d
    # B78 (Nov 13): market specific signal lead (harness side A = home for spread and ML, over for totals)
    d = P.market_lead(S, 'Spread' if mk in ('Spread', '1st half spread') else 'Moneyline', 'H' if side_is_A else 'A')[0]; return sc(d), d
def replay(rows, Ss, key, upto=None):
    mk, var, cal, mv = DEF[key]; out = []; hist = []
    for r, S in sorted(zip(rows, Ss), key=lambda z: z[0]['date']):
        for m, p, pA, pB, oA, move in H.markets(r, var, 0.5):
            if m != mk: continue
            praw = p
            if cal:
                Hh = [x for x in hist if x[2] < r['date']]
                if len(Hh) < 50: p = None
                else:
                    import numpy as np; from sklearn.linear_model import LogisticRegression
                    X = np.array([[H.lg(x[0])] for x in Hh]); y = np.array([x[1] for x in Hh])
                    p = LogisticRegression(C=1e6).fit(X, y).predict_proba([[H.lg(praw)]])[0, 1]
            if oA is not None: hist.append((praw, int(oA), r['date']))
            if p is None: continue
            s = H.bet(p, pA, pB)
            if s is None: continue
            if mv and (move is None or move == 0 or (move > 0) != (s == 'A')): continue
            # A48 follow-up (Nov 14, Trina): MODEL_ONLY_TOTAL is "FG Model Only Total, No Line Move": never a game NBA_TOT_MOVE fits
            if key == 'MODEL_ONLY_TOTAL' and move is not None and move != 0 and (move > 0) == (s == 'A'): continue
            price = pA if s == 'A' else pB; win = None if oA is None else (oA if s == 'A' else not oA)
            t, lead = tier_of(S, mk, s == 'A')
            out.append(dict(date=r['date'], game=r['g'], side=s, price=price, win=win, tier=t, lead=lead, p=round(p, 3), praw=round(praw, 3)))
    return out, hist
def rec(L):
    w = sum(1 for x in L if x['win'] is True); l = sum(1 for x in L if x['win'] is False); p = sum(1 for x in L if x['win'] is None)
    u = round(sum(H.pay(x['price']) if x['win'] else (-1 if x['win'] is False else 0) for x in L), 2)
    return dict(w=w, l=l, p=p, u=u)
if __name__ == '__main__':
    today, outp = sys.argv[1], sys.argv[2]
    G = SB.build(); rows = []; Ss = []
    for g in G:
        r = row(g); r['g'] = f"{g['a']}-{g['h']}"; rows.append(r); Ss.append(P.score_game(g['inp']))
    RES = {}
    for k in DEF:
        L, _ = replay(rows, Ss, k)
        by = collections.defaultdict(list)
        for x in L: by[x['tier']].append(x)
        RES[k] = dict(season=rec(L), n=len(L), tiers={t: dict(season=rec(v), n=len(v), month=rec([x for x in v if x['date'] >= today[:7]])) for t, v in by.items()})
        print(k, rec(L), {t: (lambda q: f"{q['w']}-{q['l']} {q['u']:+.2f}u")(rec(v)) for t, v in sorted(by.items())})
    json.dump(dict(replay=RES), open(outp, 'w'), indent=1)

def today_fits(today, rows, Ss, TI):
    """Today's fits at the Odds API opening line (A32). Calibration history = every season game before today."""
    import numpy as np; from sklearn.linear_model import LogisticRegression
    hist = collections.defaultdict(list)
    for r in rows:
        for m, p, pA, pB, oA, mv in H.markets(r, 'blend', 0.5):
            if oA is not None: hist[('blend', m)].append((p, int(oA)))
    out = []
    for key, i in TI.items():
        S = P.score_game(i)
        r = dict(sport='nba', date=today, as_=0, hs=0, hm=i['margin'], sd_m=12.5, sd_t=18.0, sp_close_h=-i['sp_a'], sp_open_h=-i['sp_a'],
                 sp_ph=i['sp_ph'], sp_pa=i['sp_pa'], tot_close=i['tot'], tot_m=i['ptotal'], tot_open=i['tot'], po=i['tot_po'], pu=i['tot_pu'],
                 ml_h=i['ml_h'], ml_a=i['ml_a'], ml_open_h=i['ml_h'], ml_open_a=i['ml_a'])
        mvs = {'Total': (i.get('tot_now_v', i['tot']) - i['tot']), 'Spread': (-i['sp_a']) - (-i.get('sp_now_a', i['sp_a'])),
               'Moneyline': ((H.nv(i['ml_now'][1], i['ml_now'][0]) - H.nv(i['ml_h'], i['ml_a'])) if i.get('ml_now') else None)}
        for k, (mk, var, cal, need) in DEF.items():
            for m, p, pA, pB, oA, _ in H.markets(r, var, 0.5):
                if m != mk: continue
                praw = p
                if cal:
                    Hh = hist[('blend', m)]
                    X = np.array([[H.lg(x[0])] for x in Hh]); y = np.array([x[1] for x in Hh])
                    p = LogisticRegression(C=1e6).fit(X, y).predict_proba([[H.lg(praw)]])[0, 1]
                s = H.bet(p, pA, pB)
                if s is None: continue
                mv = mvs[mk]
                if need and (mv is None or mv == 0 or (mv > 0) != (s == 'A')): continue
                # A48 follow-up (Nov 14): MODEL_ONLY_TOTAL = model side with NO line move toward it (disjoint from NBA_TOT_MOVE)
                if k == 'MODEL_ONLY_TOTAL' and mv is not None and mv != 0 and (mv > 0) == (s == 'A'): continue
                t, lead = tier_of(S, mk, s == 'A')
                price = pA if s == 'A' else pB
                imp = H.imp(price)
                out.append(dict(game=key, a=i['a'], h=i['h'], rule=k, market=mk, side=s, price=price, tier=t, lead=lead,
                                p=round(p, 3), praw=round(praw, 3), edge=round(100*((p if s == 'A' else 1-p) - imp), 1),
                                line=(i['tot'] if mk == 'Total' else (-i['sp_a'] if mk == 'Spread' else None)), move=mv,
                                model_total=round(i['ptotal'], 1), model_home_margin=round(i['margin'], 1)))
        # NBA_1H_FAV: when FAV_ML fits, same team on the 1st half spread
        for c in P.candidates(i, S, None):
            if c['rule'] == 'FAV_ML':
                sd = c['side']; h1 = i['h1']['sp_a'] if sd == 'A' else i['h1']['sp_h']
                if h1: t, lead = tier_of(S, '1st half spread', sd == 'H')
                if h1: out.append(dict(game=key, a=i['a'], h=i['h'], rule='NBA_1H_FAV', market='1st half spread', side=sd, line=h1[0], price=h1[1], tier=t, lead=lead))
    return out
