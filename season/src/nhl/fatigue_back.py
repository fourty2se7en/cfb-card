"""Back the tired team: would-be picks for the reverse fatigue test (Trina, Nov 11, 2026). TRACKING ONLY, never a card pick.
A team is tired when tonight is its 3rd (or later) game within 4 calendar days (same test as review/fatigue.py, n4 >= 3).
Games where both teams are tired are skipped. For each qualifying game today it logs two docs to hub sports/nhl/picks:
  <date>_<AWAY>-<HOME>_ml_FATIGUE_BACK_ML  tired team moneyline at the card's texas222 price
  <date>_<AWAY>-<HOME>_pl_FATIGUE_BACK_PL  tired team puck line (+1.5 or -1.5, as texas222 posts it for that team)
with shadow: true, tracking: true, conflict "Test rule, not active". These rule keys are NOT in hub meta rules, so they never
change a rule status or tier, and the page lists them only under "Inactive rules: picks they would make".
The original fade tracker (review/fatigue.py) keeps running in the daily re-check, now next to its reverse.
Use: hubx.py calls add(newW) at its end (after the card picks are final), or run `python3 fatigue_back.py` after hubx.py
to append the docs to hub_writes.json. Needs review/ng.txt through yesterday (Step 0 of the run)."""
import json, os, datetime, pathlib
HERE = pathlib.Path(__file__).parent; OUT = HERE/'hub'
RULE_LABEL = {'FATIGUE_BACK_ML': 'Back the tired team (3rd game in 4 nights) moneyline',
              'FATIGUE_BACK_PL': 'Back the tired team (3rd game in 4 nights) puck line'}
CONFLICT = 'Test rule, not active'

def _dates():
    """team -> sorted list of game dates from review/ng.txt (every regular season game through yesterday)."""
    out = {}
    for ln in (HERE/'review'/'ng.txt').read_text().splitlines():
        f = ln.split('|')
        if len(f) < 6: continue
        mm = int(f[1][:2]); y = 2026 if mm >= 9 else 2027   # 2026-27 season: Sep to Dec 2026, Jan to Apr 2027
        d = datetime.date(y, mm, int(f[1][3:5]))
        for t in (f[2], f[3]): out.setdefault(t, []).append(d)
    return {t: sorted(v) for t, v in out.items()}

def n4(team, day, DATES):
    """Games in the 4 days ending today (today counted): 3 or more means tired."""
    return sum(1 for d in DATES.get(team, []) if 0 < (day - d).days <= 3) + 1

def _rec(key):
    """Records for rule_record: 2026-27 every game (re-check tracker) and the Nov 11 three season backtest."""
    rr = {}
    try:
        tr = json.load(open(HERE/'review'/'recheck.json')).get('trackers', {})
        v = tr.get('Back a team playing 3 games in 4 nights | ' + ('Moneyline' if key.endswith('ML') else 'Puck line'))
        if v: s = v['season']; rr['every_game'] = f"{s['w']}-{s['l']} {s['u']:+.2f}u"
    except Exception: pass
    try:
        bt = json.load(open(HERE/'review'/'fatigue_back_bt.json')); mk = 'Moneyline' if key.endswith('ML') else 'Puck line'
        for nm, lab in (('2024-25', 'backtest_2024_25'), ('2025-26', 'backtest_2025_26')):
            s = bt[nm][mk]['all']; rr[lab] = f"{s['w']}-{s['l']} {s['u']:+.2f}u" + (' (estimated puck line prices)' if mk == 'Puck line' else '')
    except Exception: pass
    return dict(rule=key, **rr)

def _fade():
    try:
        tr = json.load(open(HERE/'review'/'recheck.json')).get('trackers', {}); out = []
        for mk in ('Moneyline', 'Puck line'):
            v = tr.get('Fade a team playing 3 games in 4 nights | ' + mk)
            if v: s = v['season']; out.append(f"{mk.lower()} {s['w']}-{s['l']} {s['u']:+.2f}u")
        return ', '.join(out) or 'record not available'
    except Exception: return 'record not available'

def build(D):
    """Returns [(doc_id, doc)] for today's qualifying games."""
    import render as R, model as M, rules as RL
    day = datetime.date.fromisoformat(D); DATES = _dates()
    last = max(max(v) for v in DATES.values())
    if (day - last).days > 1: print(f'fatigue_back WARNING: ng.txt ends {last}, not yesterday; 3 in 4 counts may be short')
    G = {g[0] + '-' + g[1]: g for g in M.GAMES}; docs = []
    for x in R.PICKS:
        k = x['key']; a, h = k.split('-'); c, r = x['c'], x['r']
        na, nh = n4(a, day, DATES), n4(h, day, DATES)
        if (na >= 3) == (nh >= 3): continue
        side = 'A' if na >= 3 else 'H'; t, o = (a, h) if side == 'A' else (h, a)
        dates = [d.isoformat() for d in DATES.get(t, []) if 0 < (day - d).days <= 3]
        lead = r['sc'][side] - r['sc']['H' if side == 'A' else 'A']; tr = RL.tier(lead)
        common = dict(date=D, game=f'{a} @ {h}', away=a, home=h, time=G[k][2], result='pending', final='', sport='nhl', side=t,
                      shadow=True, tracking=True, conflict=CONFLICT, conflicting=False, version='test', tier=tr, strength=tr,
                      tier_basis=f"card signal lead {lead:+d} toward {t} (the test rule itself has no signal points)",
                      line_source='texas222', experts=[],
                      reasons=[dict(label='3rd game in 4 nights', detail=f"{M.NAMES[t]} play their 3rd game in 4 nights (earlier games {', '.join(dates)}); {M.NAMES[o]} do not.",
                                    points=None, source='NHL schedule (review/ng.txt)', market='Game context')],
                      against=[dict(label='Fatigue', detail=f"{M.NAMES[t]} are on a compressed schedule. Fade side this season: {_fade()}.",
                                    points=None, source='Fatigue tracker', market='Game context')],
                      note='Test rule (reverse of the fade tracker, Trina Nov 11): logged and graded as a would-be pick, never a card pick. Not in hub meta rules.')
        mlp = c['mla'] if side == 'A' else c['mlh']
        docs.append((f"{D}_{k}_ml_FATIGUE_BACK_ML", dict(common, market='Moneyline', rule='FATIGUE_BACK_ML', rule_label=RULE_LABEL['FATIGUE_BACK_ML'],
                     pick=f"{M.NAMES[t]} moneyline", price=mlp, rule_record=_rec('FATIGUE_BACK_ML'))))
        pl = c.get('pl')
        if pl and pl.get('sp_a') is not None:
            sp = pl['sp_a'] if side == 'A' else -pl['sp_a']; pp = pl['price_a'] if side == 'A' else pl['price_h']
            docs.append((f"{D}_{k}_pl_FATIGUE_BACK_PL", dict(common, market='Puck line', rule='FATIGUE_BACK_PL', rule_label=RULE_LABEL['FATIGUE_BACK_PL'],
                         pick=f"{M.NAMES[t]} {sp:+.1f}", line=sp, price=pp, rule_record=_rec('FATIGUE_BACK_PL'))))
    return docs

def add(W, D=None):
    """Append the would-be docs to a hub writes list (W) as set ops on sports/nhl/picks. Returns the doc ids."""
    D = D or datetime.date.today().isoformat()   # pass the card date (sandbox clock is UTC)
    OUT.mkdir(exist_ok=True); ids = []
    for did, doc in build(D):
        p = OUT/(('sports/nhl/picks__' + did).replace('/', '_') + '.json'); json.dump(doc, open(p, 'w'))
        W[:] = [w for w in W if not (w['collection'] == 'sports/nhl/picks' and w['doc_id'] == did)]
        W.append(dict(op='set', collection='sports/nhl/picks', doc_id=did, file_path=str(p))); ids.append(did)
    print('fatigue_back:', ids or 'no qualifying game today')
    return ids

if __name__ == '__main__':
    import sys
    D = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
    wp = HERE/'hub_writes.json'; W = json.load(open(wp)) if wp.exists() else []
    add(W, D); json.dump(W, open(wp, 'w'), indent=0)
