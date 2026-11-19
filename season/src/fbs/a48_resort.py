import json, glob, os, re, collections
D = '/home/claude/a48f/dl/sports/fbs/picks'; B = '/home/claude/a48f/dlq/sports/fbs/backtest'
STRICT = {'fav_ml': 'fav_ml_2', 'strong_spread': 'strong_spread_6', 'dog_ml': 'dog_ml_rlm', 'dog_spread': 'dog_spread_rlm'}
LAB = {'fav_ml_2': 'FG Favorite ML Lead 2+', 'strong_spread_6': 'FG Strong Spread Lead 6+', 'dog_ml_rlm': 'FG Underdog ML Line Move', 'dog_spread_rlm': 'FG Underdog Spread Line Move'}
W = {'Sharp action': 2, 'Reverse line movement': 2, 'Big money': 1, 'PRO systems': 1, 'Money vs tickets': 1, 'Fade the public': 1,
     'Rest: opponent had less time off': 1, 'Rest: opponent on a short week': 1, 'Track record: last season overrated': 1, 'Top experts (moneyline)': 1, 'PRO systems (moneyline)': 1}
KEYLAB = {'sharp_action': 'Sharp action', 'rlm': 'Reverse line movement', 'big_money': 'Big money', 'pro_systems': 'PRO systems', 'money_vs_tickets': 'Money vs tickets',
          'fade_public': 'Fade the public', 'short_week': 'Rest: opponent had less time off', 'last_season': 'Track record: last season overrated', 'ml_experts': 'Top experts (moneyline)', 'ml_pro': 'PRO systems (moneyline)'}
def bt(j, base):
    g = j['_id'].split('_side')[0].split('_bf_')[0]
    p = f'{B}/{g}_{base}.json'
    return json.load(open(p)) if os.path.exists(p) else None
def bsig(lst):
    out = []
    for s in lst or []:
        k, p = s.rsplit(' ', 1); p = int(p.strip('()'))
        if p: out.append(k)
    return out
def norm(l): return 'Rest: opponent had less time off' if l and l.startswith('Rest: opponent') else l
def classify(j):
    r = j['rule']; tb = j.get('tier_basis') or ''
    labs = [norm(x.get('label')) for x in j.get('reasons') or []] or [norm(x) for x in j.get('signals') or []]
    if r in ('dog_ml', 'dog_spread'):
        if labs: return ('Reverse line movement' in labs), 'doc reasons' if j.get('reasons') else 'doc signals'
        b = bt(j, r)
        if b and j.get('backfill'): return ('rlm' in bsig(b['inputs'].get('signals_on_pick'))), 'backtest (backfill source)'
        return None, 'no signals'
    need = 2 if r == 'fav_ml' else 6
    m = re.search(r'signal lead (-?\d+)', tb)
    if m: return int(m.group(1)) >= need, 'tier_basis lead ' + m.group(1)
    if j.get('reasons') and j.get('against') is not None:
        ld = sum(x.get('points', 0) for x in j['reasons']) - sum(x.get('points', 0) for x in j['against'])
        return ld >= need, f'doc reasons lead {ld}'
    b = bt(j, r)
    if b:
        I = b['inputs']
        if j.get('backfill'): return I['lead'] >= need, f"backtest (backfill source) lead {I['lead']}"
        fp = sum(W.get(l, 0) for l in labs)
        bl = sorted(KEYLAB.get(k, k) for k in bsig(I.get('signals_on_pick')))
        if sorted(l for l in labs if W.get(l, 0)) == bl:
            return I['lead'] >= need, f"doc signals match backtest, lead {I['lead']}"
        if labs and fp < need and r == 'fav_ml': return False, f'doc signals for {fp}'
        return None, f'signals differ {sorted(labs)} vs {bl}'
    if labs and r == 'fav_ml' and sum(W.get(l, 0) for l in labs) < need: return False, 'doc signals for under 2'
    return None, 'no lead'
out = {}; cnt = collections.Counter(); unk = []
for f in sorted(glob.glob(D + '/*.json')):
    j = json.load(open(f)); j['_id'] = f.split('/')[-1][:-5]
    if j.get('rule') not in STRICT or j['date'] >= '2026-11-14' or j.get('market') == 'Prop': continue
    s, why = classify(j)
    cnt[(j['rule'], s, re.sub(r'[-\d]+$', '', why)[:40])] += 1
    if s: out[j['_id']] = dict(to=STRICT[j['rule']], frm=j['rule'], why=why)
    if s is None: unk.append((j['_id'], why))
for k, v in sorted(cnt.items(), key=str): print(k, v)
print('rekey', len(out)); [print(' ', i, v['frm'], '->', v['to'], '|', v['why']) for i, v in out.items()]
print('unknown', len(unk)); [print(' ', u) for u in unk]
json.dump(out, open('/home/claude/a48f/rekey_fbs.json', 'w'), indent=0)
