"""Nov 14 (B91, A39): run after post2.py and newdocs.py on the final docs folder.
1. Renames legacy rule keys on today's pick docs to the split rules: FAV_ML -> FAV_ML_2, DOG_ML -> DOG_ML_1, SPREAD_MOVE -> SPREAD_MOVE_05,
   UNDER_DROP -> UNDER_DROP_ANY (doc ids ending in the legacy key get the new key; card pick ids _side/_total stay).
2. Adds the stricter rule's own pick doc when its trigger is met (FAV_ML_3 lead 3+ in the moneyline market, DOG_ML_MOVE line moved toward the
   underdog against the tickets, SPREAD_MOVE_1 move 1+ at both sources, UNDER_DROP_75 75%+ over tickets), tiered and gated by its own status record.
3. Contradiction flag: a FG spread or total pick that points the other way from a 1H spread or total pick in the same game keeps both picks;
   both docs get contradiction: true and the game doc gets flags ["FG vs 1H contradiction: ..."] and contradiction: true.
A48 (Nov 14, Trina): split rules are non overlapping; when the stricter trigger is met the looser doc is dropped.
Usage: python3 b91_post.py DATE <final dir> <meta json (split rules)>"""
import json, glob, os, sys, copy, re
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
import pickrules as P
DATE, FD, MF = sys.argv[1:4]
M = json.load(open(MF)); M = M.get('data', M); R = {r['key']: r for r in M['rules']}
LOOSE = {'FAV_ML': 'FAV_ML_2', 'DOG_ML': 'DOG_ML_1', 'SPREAD_MOVE': 'SPREAD_MOVE_05', 'UNDER_DROP': 'UNDER_DROP_ANY'}
STRICT = {'FAV_ML': 'FAV_ML_3', 'DOG_ML': 'DOG_ML_MOVE', 'SPREAD_MOVE': 'SPREAD_MOVE_1', 'UNDER_DROP': 'UNDER_DROP_75'}
TI = json.load(open(os.path.join(D, 'today_inp.json')))
def rec(x): return f"{x['w']}-{x['l']}" + (f"-{x['p']}" if x.get('p') else '') + f" {x['u']:+.2f}u" if x else None
def strict_met(old, d):
    k = f"{d['away']}-{d['home']}"; inp = TI.get(k)
    if not inp: return False, ''
    S = P.score_game(inp)
    from teams import FULL
    sd = 'A' if (d.get('side') == d['away'] or str(d.get('pick', '')).startswith(FULL[d['away']])) else 'H'
    if old == 'FAV_ML':
        lead = P.market_lead(S, 'Moneyline', sd)[0]; return lead >= 3, f'moneyline signal lead {lead}'
    if old == 'DOG_ML': return S.get('lm_side') == sd, 'line moved toward the underdog against the tickets'
    if old == 'SPREAD_MOVE':
        lm, mv, how = P.spread_move(inp, 1.0); return lm == sd, f'spread moved {mv} at both sources'
    if old == 'UNDER_DROP': return inp.get('o_bets', 0) >= 75, f"{inp.get('o_bets')}% of tickets on the over"
    return False, ''
renamed, added = [], []; dropped = {}
for f in sorted(glob.glob(f'{FD}/sports_nba_picks__{DATE}_*.json')):
    d = json.load(open(f)); old = d.get('rule')
    INV = {v: k for k, v in LOOSE.items()}
    if old in INV: old = INV[old]   # already renamed (rerun): still check the stricter rule
    if old not in LOOSE: continue
    did = os.path.basename(f)[len('sports_nba_picks__'):-5]
    new = LOOSE[old]; d['rule'] = new; d['rule_key'] = new; d['rule_label'] = R[new]['label']; d.pop('rule_variant', None)
    if isinstance(d.get('rule_record'), dict): d['rule_record']['rule'] = R[new]['label']
    nid = did[:-len(old)] + new if did.endswith('_' + old) else did
    os.remove(f); json.dump(d, open(f'{FD}/sports_nba_picks__{nid}.json', 'w'), indent=1); renamed.append((did, nid))
    ok, why = strict_met(old, d)
    if ok:
        s = STRICT[old]; t = copy.deepcopy(d); t['rule'] = s; t['rule_key'] = s; t['rule_label'] = R[s]['label']; t['trigger'] = why
        tr = (R[s].get('tiers') or {}).get(d['tier']) or {}
        t['tier_record'] = dict(tier=d['tier'], on=bool(tr.get('on')), real=rec(tr.get('real')), pending_on=tr.get('pending_on'))
        if isinstance(t.get('rule_record'), dict): t['rule_record'] = dict(rule=R[s]['label'], status='on' if tr.get('on') else 'off')
        if not tr.get('on'):
            t['shadow'] = True
            t['conflict'] = (f"Its {d['tier']} tier is turned off (status record {rec(tr['real'])}), so it is logged as a would-be pick." if tr.get('real')
                             else f"Its {d['tier']} tier has no status record yet, so it is turned off and logged as a would-be pick.")
            t['note'] = 'Would-be pick: rule tier turned off; logged and graded, never a card pick.'
        else: t['shadow'] = False; t.pop('conflict', None)
        kind = 'total' if d['market'] == 'Total' else 'side'
        sid = f"{DATE}_{d['away']}-{d['home']}_{kind}_{s}"
        json.dump(t, open(f'{FD}/sports_nba_picks__{sid}.json', 'w'), indent=1); added.append((sid, t['pick'], t['tier'], 'card' if not t['shadow'] else 'would-be', why))
        # Nov 14 (A48, Trina): split rules are non overlapping. The game met the stricter trigger, so it does not fit the looser rule:
        # drop the looser doc; the game doc slot follows the stricter doc (card when its tier is on, else No pick with the would-be listed).
        os.remove(f'{FD}/sports_nba_picks__{nid}.json'); dropped[nid] = (sid, t)
# A48 follow-up (Nov 14, Trina): MODEL_ONLY_TOTAL ("FG Model Only Total, No Line Move") and NBA_TOT_MOVE are disjoint. newrules.today_fits
# no longer fits MODEL_ONLY_TOTAL when the total moved toward the model side; as a safety net, drop a MODEL_ONLY_TOTAL doc whose game and side
# also have an NBA_TOT_MOVE doc (the game doc slot follows the NBA_TOT_MOVE doc, as for the other split pairs).
for f in sorted(glob.glob(f'{FD}/sports_nba_picks__{DATE}_*_MODEL_ONLY_TOTAL.json')):
    d = json.load(open(f)); mid = os.path.basename(f)[len('sports_nba_picks__'):-5]
    tf = f.replace('_MODEL_ONLY_TOTAL.json', '_NBA_TOT_MOVE.json')
    if os.path.exists(tf):
        t = json.load(open(tf))
        if str(t.get('pick', '')).split()[0] == str(d.get('pick', '')).split()[0]:
            os.remove(f); dropped[mid] = (mid[:-len('MODEL_ONLY_TOTAL')] + 'NBA_TOT_MOVE', t)
    else:
        d['rule_label'] = R['MODEL_ONLY_TOTAL']['label']; json.dump(d, open(f, 'w'), indent=1)
# game docs: point picks.side/total doc ids at the renamed docs and relabel
RN = dict(renamed)
for f in sorted(glob.glob(f'{FD}/sports_nba_games__{DATE}_*.json')):
    g = json.load(open(f)); ch = False
    for m in ('side', 'total'):
        p = g.get('picks', {}).get(m) or {}
        if p.get('doc_id') in RN: p['doc_id'] = RN[p['doc_id']]; ch = True
        if p.get('doc_id') in dropped:
            sid, t = dropped[p['doc_id']]; ch = True
            if not t.get('shadow'):
                p.update(doc_id=sid, rule=t['rule'], rule_label=t['rule_label'], tier=t['tier'])
            else:
                s_ = p.get('summary') or {}
                g['picks'][m] = p = dict(none=f"No card pick. Only {t['rule_label']} fits ({t.get('trigger') or 'the stricter trigger is met'}), and its {t['tier']} tier is off, so {t['pick']} is a would-be pick.",
                                         analysis=p.get('analysis') or ' '.join(filter(None, [s_.get('for'), s_.get('against')])), shadow_doc_ids=[sid])
        for old, new in LOOSE.items():
            if p.get('rule') == old: p['rule'] = new; p['rule_label'] = R[new]['label']; ch = True
        if p.get('rule_label') in ('Favorite moneyline', 'Underdog moneyline', 'Spread line move', 'Under on a dropping total'):
            p['rule_label'] = R[LOOSE[{'Favorite moneyline': 'FAV_ML', 'Underdog moneyline': 'DOG_ML', 'Spread line move': 'SPREAD_MOVE', 'Under on a dropping total': 'UNDER_DROP'}[p['rule_label']]]]['label']; ch = True
    if ch: json.dump(g, open(f, 'w'), indent=1)
# contradiction flag
by = {}
for f in sorted(glob.glob(f'{FD}/sports_nba_picks__{DATE}_*.json')):
    d = json.load(open(f))
    if d.get('market') == 'Prop': continue
    by.setdefault(f"{d['away']}-{d['home']}", []).append((f, d))
flags = {}
def direction(d):
    sub = d.get('sub_market') or ''
    if d['market'] == 'Spread' or sub == '1st half spread': return ('side', d.get('side'))
    if d['market'] == 'Total' or sub == '1st half total': return ('total', 'U' if str(d['pick']).startswith('Under') or '1st half under' in str(d['pick']).lower() else 'O')
    return None
for k, L in by.items():
    fg = [(f, d) for f, d in L if d['market'] in ('Spread', 'Total')]
    h1 = [(f, d) for f, d in L if (d.get('sub_market') or '').startswith('1st half')]
    for f1, a in fg:
        for f2, b in h1:
            da, db = direction(a), direction(b)
            if da and db and da[0] == db[0] and da[1] != db[1]:
                txt = f"{a['pick']} ({a.get('rule_label') or a['rule']}{', would-be' if a.get('shadow') else ''}) vs {b['pick']} ({b.get('rule_label') or b['rule']}{', would-be' if b.get('shadow') else ''})"
                flags.setdefault(k, []).append(f'FG vs 1H contradiction: {txt}')
                for ff, dd in ((f1, a), (f2, b)): dd['contradiction'] = True; json.dump(dd, open(ff, 'w'), indent=1)
for k, fl in flags.items():
    gf = f'{FD}/sports_nba_games__{DATE}_{k}.json'
    if os.path.exists(gf):
        g = json.load(open(gf)); g['flags'] = sorted(set((g.get('flags') or []) + fl)); g['contradiction'] = True; json.dump(g, open(gf, 'w'), indent=1)
print('renamed', renamed); print('strict picks', added); print('looser docs dropped (A48)', list(dropped)); print('contradictions', flags)
