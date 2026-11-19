"""Nov 12 (B56, B74, A33): NCAAM_SP_CAL, MODEL_ONLY_SPREAD, MODEL_ONLY_TOTAL and NCAAM_1H_UNDER for the NCAAM run.
Usage: python3 newrules_nov12.py DATE  (after extras.py; reads out/hubw/picks.json, shadow.json, games_today.json and hub/sports/ncaam/games, hub/meta)
Model rules follow Season Cards tools/model_tests/harness.py: spread p = Phi((model home margin + home spread)/11), total p = Phi((model total - line)/15),
bet when the edge at the price is 1%+; NCAAM_SP_CAL calibrates p walk-forward on this season's final game docs (logistic, 50 game minimum).
Tiers (B74): model gap 1 point per 2 points (cap 4) on the one scale; NCAAM_1H_UNDER takes the OVER fit's signal lead on its own market (1st half total).
Opposing picks: higher tier stays; same tier, more season units. One card pick per market per game; other fits are would-be picks."""
import json, glob, math, re, sys, pathlib
import numpy as np
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression
W = pathlib.Path(__file__).resolve().parent.parent; OUT = W/'out'/'hubw'; DATE = sys.argv[1]
imp = lambda p: 100/(p+100) if p > 0 else -p/(-p+100)
lg = lambda p: math.log(min(max(p, 1e-4), 1-1e-4)/(1-min(max(p, 1e-4), 1-1e-4)))
num = lambda s: (lambda m: float(m.group()) if m else None)(re.search(r'[-+]?\d+(\.\d+)?', str(s or '')))
safe = lambda s: re.sub(r'[^A-Za-z0-9]', '', s)
META = json.load(open(W/'hub'/'meta'/'ncaam.json')); META = META.get('data', META); RS = {r['key']: r for r in META['rules']}
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent)); import gapguard as GG   # A57 (Trina, Nov 16)
GGL = GG.limits(META)
def sc(l): return 'Strong' if l >= 4 else ('Solid' if l >= 2 else 'Lean')
TO = {'Strong': 3, 'Solid': 2, 'Lean': 1}
def tier_units(key, t):
    v = ((RS.get(key) or {}).get('tiers') or {}).get(t) or (RS.get(key) or {}).get('tiers', {}).get('All') or {}
    return ((v.get('real') or v.get('season') or {}).get('u') or 0)
def rule_on(key, t):
    r = RS.get(key) or {}; T = r.get('tiers') or {}
    if t in T: return bool(T[t].get('on'))
    if 'All' in T: return bool(T['All'].get('on'))
    return bool(r.get('on'))
def hm_of(d):
    m = d.get('model') or {}; os_ = m.get('our_spread'); A, H = d['away'], d['home']
    if not os_: return None
    t = str(os_).rsplit(' ', 1); v = num(t[-1]); tm = t[0].strip()
    ac, hc = (A.get('code') if isinstance(A, dict) else A), (H.get('code') if isinstance(H, dict) else H)
    return -v if tm == hc else (v if tm == ac else None)
# ---- history (final game docs with a model), same as model_tests/b_ncaam.py
hist = []
for f in glob.glob(str(W/'hub'/'sports'/'ncaam'/'games'/'*.json')):
    d = json.load(open(f)); d = d.get('data', d)
    if d.get('status') != 'final' or not d.get('model') or d.get('date', '') >= DATE: continue
    m = re.findall(r'([A-Za-z&\-.\' ]+?)\s(\d+)(?:,|$)', str(d.get('final', '')))
    pts = {}
    for t, v in m:
        t = t.strip(' ,')
        if t == d['away'].get('code'): pts['a'] = int(v)
        if t == d['home'].get('code'): pts['h'] = int(v)
    if len(pts) < 2: continue
    L = d.get('lines') or {}; sp = num((L.get('spread') or {}).get('home')); hm = hm_of(d)
    if hm is None or sp is None: continue
    o = (pts['h'] - pts['a']) + sp
    if o == 0: continue
    hist.append((d['date'], norm.cdf((hm + sp)/11.0), int(o > 0)))
hist.sort()
H = [x for x in hist if x[0] < DATE]
cal = None
if len(H) >= 50 and len({x[2] for x in H}) == 2:
    cal = LogisticRegression(C=1e6).fit(np.array([[lg(x[1])] for x in H]), np.array([x[2] for x in H]))
print('SP_CAL history', len(H), 'calibrated' if cal else 'not enough history')
G = json.load(open(OUT/'games_today.json')); P = json.load(open(OUT/'picks.json')); S = json.load(open(OUT/'shadow.json'))
new = []
def pr(s): v = num(s); return int(v) if v is not None and abs(v) >= 100 else -110
STARTED = {l.split('|')[2] + '-' + l.split('|')[3] for l in (W/'data'/'espn_today_m.txt').read_text().strip().splitlines()[1:] if l.split('|')[12] != 'p'}
for g in G:
    d = g['data']; a, h = d['away']['code'], d['home']['code']; L = d.get('lines') or {}
    if f'{a}-{h}' in STARTED: continue   # never pick a started game
    gid = f"{DATE}_{safe(a)}-{safe(h)}"
    base = dict(date=DATE, game=f"{a} @ {h}", away=a, home=h, time=d.get('time'), day=d.get('day'), conflicting=False, result='pending', final='',
                line_source='The Odds API median of books', conference=d.get('conference'), experts=[], rule_variant='base')
    hm = hm_of(d); sp = num(((L.get('spread') or {}).get('home') or '').split(' ')[0] if (L.get('spread') or {}).get('home') else None)
    sh_s = (L.get('spread') or {}).get('home'); sa_s = (L.get('spread') or {}).get('away')
    if hm is not None and sh_s:
        sp = num(sh_s.split()[0]) if not sh_s.startswith('PK') else 0.0
        ph, pa = pr(sh_s.split()[-1]) if len(sh_s.split()) > 1 else -110, pr(sa_s.split()[-1]) if sa_s and len(sa_s.split()) > 1 else -110
        praw = norm.cdf((hm + sp)/11.0); gap = abs(hm + sp)
        for key, p in (('MODEL_ONLY_SPREAD', praw), ('NCAAM_SP_CAL', cal.predict_proba([[lg(praw)]])[0, 1] if cal is not None else None)):
            if p is None: continue
            eh, ea = p - imp(ph), (1 - p) - imp(pa)
            if max(eh, ea) < 0.01: continue
            home = eh >= ea; team = h if home else a; ln = sp if home else -sp; price = ph if home else pa
            pts = min(4, int(gap // 2)); t = sc(pts); e = round(100*(eh if home else ea), 1)
            why = f"Our model projects {h} by {hm:+.1f}" if hm >= 0 else f"Our model projects {a} by {-hm:+.1f}".replace('+', '')
            new.append(dict(id=f"{gid}_side_{key}", data=dict(base, market='Spread', pick=f"{team} {'PK' if ln == 0 else f'{ln:+g}'}", price=price, line=ln, side='home' if home else 'away',
                rule=key, rule_label=RS[key]['label'], tier=t, tier_basis=f"model gap {gap:.1f} points = {pts} (1 point per 2, cap 4)",
                reasons=[dict(label='Model vs spread', detail=f"model {h} {-hm:+.1f} vs {h} {sp:+g} (gap {gap:.1f})", points=pts, source='Card model', market='Spread')],
                against=[], model=dict(projection=round(hm, 1), hit_pct=round(100*(p if home else 1-p), 1), needed_pct=round(100*imp(price), 1), edge=e),
                rule_record=dict(rule=key, every_game=RS[key].get('every_game')),
                summary={'for': f"{why.replace('by +','by ')} against a {h} {sp:+g} line; the {'calibrated ' if key == 'NCAAM_SP_CAL' else ''}model gives {team} {100*(p if home else 1-p):.1f}% to cover, {e:.1f} points above the {100*imp(price):.1f}% the price needs.",
                         'against': f"The market has {h} at {sp:+g}; the model gap is {gap:.1f} points and early season ratings still lean on last season."})))
    tm = num((d.get('model') or {}).get('our_total')); to = (L.get('total') or {}).get('over'); tu = (L.get('total') or {}).get('under')
    if tm is not None and to:
        Lt = num(to.split()[0]); po, pu = pr(to.split()[-1]), pr(tu.split()[-1]) if tu else -110
        p = norm.cdf((tm - Lt)/15.0); eo, eu = p - imp(po), (1-p) - imp(pu)
        if max(eo, eu) >= 0.01:
            ov = eo >= eu; gap = abs(tm - Lt); pts = min(4, int(gap // 2)); price = po if ov else pu; e = round(100*(eo if ov else eu), 1)
            new.append(dict(id=f"{gid}_total_MODEL_ONLY_TOTAL", data=dict(base, market='Total', pick=f"{'Over' if ov else 'Under'} {Lt:g}", price=price, line=Lt, side='over' if ov else 'under',
                rule='MODEL_ONLY_TOTAL', rule_label=RS['MODEL_ONLY_TOTAL']['label'], tier=sc(pts), tier_basis=f"model gap {gap:.1f} points = {pts} (1 point per 2, cap 4)",
                reasons=[dict(label='Model vs current total', detail=f"model {tm:g} vs {Lt:g} ({tm-Lt:+.1f})", points=pts, source='Card model', market='Total')], against=[],
                model=dict(projection=tm, hit_pct=round(100*(p if ov else 1-p), 1), needed_pct=round(100*imp(price), 1), edge=e), rule_record=dict(rule='MODEL_ONLY_TOTAL', every_game=RS['MODEL_ONLY_TOTAL'].get('every_game')),
                summary={'for': f"Our model projects {tm:g} total points against a {Lt:g} total, {gap:.1f} points to the {'Over' if ov else 'Under'}.", 'against': f"The market total is {Lt:g}; early season efficiency ratings still lean on last season."})))
    # ---- NCAAM_1H_UNDER: 1st half Under when the OVER rule fits this game (card or would-be)
    ovr = [x for x in P + S if str(x['data'].get('rule')).startswith('OVER_') and x['data']['away'] == a and x['data']['home'] == h]
    h1 = ((L.get('periods') or {}).get('1H') or {}).get('total') or {}
    if ovr and h1.get('under'):
        o = ovr[0]['data']; L1 = num(h1['under'].split()[0]); p1 = pr(h1['under'].split()[-1])
        card_tot = [x['data'] for x in P if x['data']['away'] == a and x['data']['home'] == h and x['data']['market'] == 'Total']
        flag = bool(card_tot and str(card_tot[0]['pick']).startswith('Over'))
        lead = num(re.search(r'signal lead (-?\d+)', o.get('tier_basis', '')).group(1)) if re.search(r'signal lead (-?\d+)', o.get('tier_basis', '')) else 0
        new.append(dict(id=f"{gid}_h1_NCAAM_1H_UNDER", data=dict(base, market='Game prop', sub_market='1st half total', category='Game prop', pick=f"1H Under {L1:g}", price=p1, line=L1, side='under',
            rule='NCAAM_1H_UNDER', rule_label=RS['NCAAM_1H_UNDER']['label'], tier=sc(lead), tier_basis=f"signal lead {int(lead)} from the full game OVER fit (B74: own market, same scale)",
            direction_flag=flag, direction_note=("The card's full game total is Over; this 1st half Under points the other way (Trina A33)." if flag else None),
            reasons=[dict(label='Full game OVER rule fits', detail=o.get('pick'), points=None, source='Card rules', market='Total')], against=[],
            rule_record=dict(rule='NCAAM_1H_UNDER', every_game=RS['NCAAM_1H_UNDER'].get('every_game')),
            summary={'for': f"The full game total has risen at both books, which fits the Over rule ({o.get('pick')}); in those games the 1st half Under went 59-43 this season (SBR 1st half close). 1st half total {L1:g}.",
                     'against': "The same line move points to the Over for the full game, so the half and game totals point opposite ways."})))
# ---- card or would-be: rule tier on, one card per market, opposing picks rule (higher tier, then season units)
def mk(d): return 'side' if d['market'] in ('Spread', 'Moneyline') else ('total' if d['market'] == 'Total' else d['market'])
def team(d): return re.sub(r'\s+(ML|[+-][\d.]+|PK)$', '', d['pick'])
added_card, added_shadow = [], []
GCTX = {f"{g['data']['away']['code']}-{g['data']['home']['code']}": GG.ctx_doc(g['data']) for g in G}
def guard(d):   # A57: one gap guard for every rule (spread gap over spread_max, Over gap under over_min)
    c = GCTX.get(f"{d['away']}-{d['home']}")
    if c is None or d.get('market') not in ('Spread', 'Total'): return None
    gg = GG.apply_gap_guard([dict(market=d['market'], side=d.get('side'), line=d.get('line'))], c, GGL)
    return gg[0]['gap_guard'] if gg else None
for x in new:
    d = x['data']; key = d['rule']
    g0 = guard(d)
    if g0:
        d['shadow'] = True; d['conflict'] = g0['conflict']; d['gap_guard'] = GG.doc_flag(g0); added_shadow.append(x); continue
    on = rule_on(key, d['tier'])
    if not on:
        d['shadow'] = True; d['conflict'] = f"This rule is off and its {d['tier']} tier is not on (its status record is not in the green)"; added_shadow.append(x); continue
    rivals = [y for y in P + added_card if y['data']['away'] == d['away'] and y['data']['home'] == d['home'] and not y['data'].get('shadow') and mk(y['data']) == mk(d)]
    if not rivals: d['shadow'] = False; added_card.append(x); continue
    r = rivals[0]['data']
    same = (team(r) == team(d)) if mk(d) == 'side' else (r['pick'].split()[0] == d['pick'].split()[0])
    if same:   # Nov 13 (B91): rules run independently; same direction is its own card pick
        d['shadow'] = False; d['note'] = f"Separate rule: also a card pick beside {r['pick']} ({r.get('rule_label') or r['rule']})"; added_card.append(x); continue
    mine, theirs = (TO[d['tier']], tier_units(key, d['tier'])), (TO.get(r['tier'], 1), tier_units(r['rule'], r['tier']))
    if mine > theirs:
        r['shadow'] = True; r['conflict'] = {'with': x['id'], 'kept': d['pick'], 'why': 'Opposing picks in one game: higher tier stays (same tier: more season units)'}
        S.append(rivals[0]); P[:] = [y for y in P if y is not rivals[0]]; added_card = [y for y in added_card if y is not rivals[0]]
        d['shadow'] = False; added_card.append(x)
    else:
        d['shadow'] = True; d['conflict'] = {'with': rivals[0]['id'], 'kept': r['pick'], 'why': 'Opposing picks in one game: higher tier stays (same tier: more season units)'}; added_shadow.append(x)
P += added_card; S += added_shadow
# A57 final sweep: no card pick leaves this step with a guarded gap (extras.py guards its fits already; this catches any other source)
GIx = {f"{g['data']['away']['code']}-{g['data']['home']['code']}": g for g in G}; GG_MOVED = []
for x in list(P):
    d = x['data']
    if d.get('shadow'): continue
    g0 = guard(d)
    if not g0: continue
    d['shadow'] = True; d['conflict'] = g0['conflict']; d['gap_guard'] = GG.doc_flag(g0); P.remove(x); S.append(x); GG_MOVED.append(x['id'])
    gd = (GIx.get(f"{d['away']}-{d['home']}") or {}).get('data') or {}; pk = gd.get('picks') or {}; m = mk(d)
    if (pk.get(m) or {}).get('doc_id') == x['id']: pk[m] = dict(none=f"Held back as a would-be pick. {g0['conflict']}", analysis=pk[m].get('analysis'))
    if gd.get('picks_extra'): gd['picks_extra'] = [e for e in gd['picks_extra'] if e.get('doc_id') != x['id']] or None
print('gap guard: new rule fits held back', sum(1 for x in added_shadow if x['data'].get('gap_guard')), '| card picks moved by the final sweep', len(GG_MOVED), GG_MOVED)
json.dump(P, open(OUT/'picks.json', 'w'), indent=1); json.dump(S, open(OUT/'shadow.json', 'w'), indent=1)
# game docs: card picks of the new rules fill the market; game props group
GI = {f"{g['data']['away']['code']}-{g['data']['home']['code']}": g for g in G}
for x in P:
    d = x['data']; g = GI.get(f"{d['away']}-{d['home']}")
    if not g: continue
    pk = g['data'].setdefault('picks', {}); m = mk(d)
    ent = dict(pick=d['pick'], price=str(d['price']), tier=d['tier'], rule_label=d.get('rule_label'), doc_id=x['id'], summary=d.get('summary'), line_source=d['line_source'])
    if d['rule'] in ('NCAAM_SP_CAL', 'MODEL_ONLY_TOTAL', 'MODEL_ONLY_SPREAD'):
        if not pk.get(m) or pk[m].get('none') or pk[m].get('doc_id') == x['id']: pk[m] = ent
        else:
            pe = g['data'].get('picks_extra') or []; pe = [e for e in pe if e.get('doc_id') != x['id']]
            pe.append(dict(market=d['market'], pick=d['pick'], price=str(d['price']), tier=d['tier'], rule_label=d.get('rule_label'), doc_id=x['id'])); g['data']['picks_extra'] = pe
    if d['market'] == 'Game prop':
        gp = g['data'].setdefault('game_props', []); gp[:] = [e for e in gp if e.get('doc_id') != x['id']]; gp.append(dict(ent, sub_market=d['sub_market'], direction_flag=d.get('direction_flag'), direction_note=d.get('direction_note')))
for x in S:   # dropped by the opposing picks rule: game doc market shows the kept pick (already) or No pick
    pass
# ---- Contradiction flag (Trina Nov 13): a FG spread or total pick pointing the other way from a 1H spread or total pick in the same game keeps both picks and flags the game
NC = 0
for g in G:
    gd = g['data']; a, h = gd['away']['code'], gd['home']['code']
    docs = [x for x in P + S if x['data']['away'] == a and x['data']['home'] == h]
    fg_t = [x for x in docs if x['data']['market'] == 'Total']; h1_t = [x for x in docs if x['data'].get('sub_market') == '1st half total']
    fg_s = [x for x in docs if x['data']['market'] == 'Spread']; h1_s = [x for x in docs if x['data'].get('sub_market') == '1st half spread']
    fl = []
    for F, Hh, kind in ((fg_t, h1_t, 'total'), (fg_s, h1_s, 'spread')):
        for f in F:
            for y in Hh:
                if kind == 'total': opp = f['data']['pick'].split()[0] != y['data']['pick'].split()[1]
                else: opp = f['data']['side'] != y['data']['side']
                if not opp: continue
                f['data']['contradiction'] = True; y['data']['contradiction'] = True
                fl.append(f"FG vs 1H contradiction: {f['data']['pick']} ({f['data'].get('rule_label') or f['data']['rule']}{', would-be' if f['data'].get('shadow') else ''}) vs {y['data']['pick']} ({y['data'].get('rule_label') or y['data']['rule']}{', would-be' if y['data'].get('shadow') else ''})")
    if fl: gd['flags'] = sorted(set(fl)); NC += 1
json.dump(P, open(OUT/'picks.json', 'w'), indent=1); json.dump(S, open(OUT/'shadow.json', 'w'), indent=1)
print('contradiction games', NC)
json.dump(G, open(OUT/'games_today.json', 'w'))
print('new rule fits', len(new), 'card', len(added_card), 'would-be', len(added_shadow))
for x in added_card + added_shadow: print(' ', x['id'], x['data']['pick'], x['data']['price'], x['data']['tier'], 'would-be' if x['data']['shadow'] else 'CARD', str(x['data'].get('conflict') or '')[:70])
