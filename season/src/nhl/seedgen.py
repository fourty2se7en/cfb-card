"""Seeds the day's picks and pick-time inputs into the ledger (writes seedDD/ files and seedDD_writes.json for ArtifactData batches).
Usage: python3 seedgen.py YYYY-MM-DD [suffix] [--no-props]
picks collection: rule picks _ml (ML1), _pl (PL1), _tot1 (TOT1) with rule and version; a switched-off rule logs shadow:true. Props as before.
inputs collection: one doc per game, id YYYY-MM-DD_AWAY-HOME, with the pick-time inputs (Action Network splits and sharp codes,
second-source DraftKings lines, texas222 lines, goalies, injuries, scored signals) so they can be tested later."""
import json, os, re, sys
import render as R, model as M, rules as RL, signals as SG
D = sys.argv[1]; suffix = sys.argv[2] if len(sys.argv) > 2 else ''
base = os.path.abspath('seed' + D[-2:] + suffix); os.makedirs(base, exist_ok=True); W = []
G = {g[0]+'-'+g[1]: g for g in M.GAMES}
def put(doc_id, doc, coll='picks'):
    p = f'{base}/{coll}_{doc_id}.json'; json.dump(doc, open(p, 'w')); W.append({'op': 'set', 'collection': coll, 'doc_id': doc_id, 'file_path': p})
SUF = {'ML1': 'ml', 'PL1': 'pl', 'TOT1': 'tot1'}
for x in R.PICKS:
    k = x['key']; a, h, tm = G[k][0], G[k][1], G[k][2]; nm = {'A': a, 'H': h}
    common = dict(date=D, game=f'{a} @ {h}', away=a, home=h, time=tm, result='pending', final='', conflicting=False)
    for pk in x['rp']:
        sd = pk['side']
        if pk['market'] == 'Moneyline': text = f"{M.NAMES[nm[sd]]} moneyline"
        elif pk['market'] == 'Puck line': text = f"{M.NAMES[nm[sd]]} {'+1.5' if pk['line'] > 0 else '-1.5'}"
        else: text = f"{'Over' if sd == 'O' else 'Under'} {pk['line']:g}"
        doc = dict(common, market=pk['market'], pick=text, price=pk['price'], tier=pk['tier'], rule=pk['rule'], version=pk['version'])
        if pk['market'] == 'Moneyline' and x['ml'] and not x['ml'].get('nopick'): doc['conflicting'] = bool(x['ml']['conf']); doc['projected'] = round(x['ml']['prob'], 3)
        _k = {'Moneyline': 'ml', 'Puck line': 'pl', 'Total': 'tot'}[pk['market']]
        if x[_k] and not x[_k].get('nopick') and x[_k].get('tier'): doc['tier'] = doc['strength'] = x[_k]['tier']  # one 3-tier scale for every market (Nov 2)  # signal tier (Strong/Solid/Lean/Thin), shown as the colored pill
        if pk['status'] == 'off': doc['shadow'] = True
        if pk['market'] != 'Moneyline': doc['line'] = pk['line']
        put(f"{D}_{k}_{SUF[pk['rule']]}", doc)
    # pick-time inputs
    c, r = x['c'], x['r']; gm = G[k]
    put(f'{D}_{k}', dict(date=D, game=f'{a} @ {h}', away=a, home=h, time=tm, read_time=R.READ_TIME,
        action_network=SG.AN.get(k), draftkings=(getattr(SG, 'DK', {}) or {}).get(k),
        texas222=dict(ml=[c['mla'], c['mlh']], pl=c.get('pl'), total=c.get('line'), total_prices=list(c['tprice']) if c.get('tprice') else None),
        goalies=dict(away=[gm[4], gm[5]], home=[gm[6], gm[7]]), injuries_out={t: [list(p) for p in M.OUT.get(t, [])] for t in (a, h)},
        signals=[[s_, m_, sd_, p_] for s_, m_, sd_, p_, n_ in r['S'] + r.get('T', [])], side=r['side'], lead=r['ml_lead'],
        div=[c['div_a'], c['div_h'], r.get('div_pts', 0)], rule_picks=[[p['rule'], p['version'], p['side'], p['price'], p['status']] for p in x['rp']],
        rules={kk: [RL.RULES[kk]['status'], RL.RULES[kk]['version']] for kk in RL.ORDER}), coll='inputs')
SM = {'sog': 'shots', 'pts': 'points', 'pts2': 'points', 'goal': 'goals'}
if '--no-props' not in sys.argv:
    for k, tid, tm, x in R.PROPPICKS:
        a, h = G[k][0], G[k][1]; line = {'pts': 0.5, 'pts2': 1.5, 'goal': 0.5}.get(x['mkt'])
        if x['mkt'] == 'sog':
            n = float(re.search(r'[\d.]+', x['lab']).group()); line = n-0.5 if '+' in x['lab'] else n
        put(f"{D}_{k}_prop_{re.sub(r'[ .\x27]', '', x['pl'])}", dict(date=D, game=f'{a} @ {h}', away=a, home=h, time=tm, market='Prop', pick=f"{x['pl']} {x['lab']}", player=x['pl'], team=x['team'], stat=SM[x['mkt']], line=line, price=x['price'], book=x['book'], tier=x['call'], conflicting=False, projected=round(x['est'], 3), result='pending', final=''))
json.dump(W, open(f'seed{D[-2:]}{suffix}_writes.json', 'w')); print(len(W), 'writes:', sum(w['collection'] == 'picks' for w in W), 'picks,', sum(w['collection'] == 'inputs' for w in W), 'inputs')
