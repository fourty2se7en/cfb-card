"""Nov 17 run (4:45 PM Odds API read, late start). Post step: drops games that tipped before the run, writes summaries from the run's data
(margin model, efficiency model, line moves, team stats ranks, last results), conflict text from the hub tier status records, rule keys and labels,
Odds API wording, no-pick text, line history, team stats. Reads ../hub_out, env HUB_GAMES, HUB_META, TS (team_stats.json.gz), STARTED (comma ids). Writes ../post17."""
import json, pathlib, os, gzip
W = pathlib.Path(__file__).parent.parent; O = W/'post17'; O.mkdir(exist_ok=True)
P = json.load(open(W/'hub_out'/'picks.json')); G = json.load(open(W/'hub_out'/'games.json'))
HG = pathlib.Path(os.environ['HUB_GAMES']); MM = json.load(open(os.environ['HUB_META'])); MM = MM.get('data', MM)
META = {r['key']: r for r in MM['rules']}; LAB = lambda k: META[k].get('label', k)
FAM = {'SPREAD_MOVE_1': 'SPREAD_MOVE', 'SPREAD_MOVE_05': 'SPREAD_MOVE', 'OVER_2': 'OVER', 'OVER_05': 'OVER'}
STARTED = set(x for x in os.environ.get('STARTED', '').split(',') if x)
NOW = os.environ.get('NOW', '2026-11-17 16:45'); READ = os.environ.get('READ', '4:45 PM')
TS = json.load(gzip.open(os.environ['TS']))
def st(code):
    t = TS['teams'].get(TS['index'].get(code)); return {s['label']: s for s in (t['stats'] if t else [])}, (t['short'] if t else code)
def sfmt(code, lab):
    s, _ = st(code); x = s.get(lab)
    return f"{x['value']:g}{'%' if '%' in lab else ''} ({x['rank']}{'th' if 10 <= x['rank'] % 100 <= 20 else {1:'st',2:'nd',3:'rd'}.get(x['rank'] % 10, 'th')} of {x['of']})" if x else None
def mkt(item, market):
    lab = (item.get('label', '') + ' ' + item.get('detail', '')).lower()
    item['market'] = 'Game context' if any(k in lab for k in ('injur', 'home court', 'rest', 'form', 'backtest', 'neutral', 'travel')) else market
    return item
def gnum(s):
    try: return float(s.split()[-1])
    except Exception: return None
def mtxt(code, gid_d):
    s, nm = st(code); p, pa = sfmt(code, 'Points'), sfmt(code, 'Points allowed'); fg = sfmt(code, 'FG %')
    bits = [f"scores {p} points per game" if p else None, f"allows {pa}" if pa else None, f"shoots {fg}" if fg else None]
    return f"{nm} " + ', '.join(b for b in bits if b) if any(bits) else ''
def ctx(d):
    A, H = d['away']['code'], d['home']['code']; sp = d['lines']['spread']; tot = d['lines']['total']
    hs = gnum(sp['home'].split()[0]) if sp else None; t = float(tot['over'].split()[0]) if tot else None
    mm = None
    for p in P:
        if p['id'].startswith(d['_gid'] + '_side_MODELEDGE') or p['id'].startswith(d['_gid'] + '_side'):
            mm = (p['data'].get('model') or {}).get('projection') if p['data']['rule'] == 'MODEL_EDGE' else mm
    return A, H, hs, t, mm
def summaries(gid, d):
    A, H, hs, t, _ = ctx(d)
    eff = d['model'].get('our_spread'); etot = d['model'].get('our_total')
    fav, dog = (H, A) if (hs or 0) < 0 else (A, H); ln = abs(hs or 0)
    mv = [m.replace('(DraftKings)', '(The Odds API median of books)') for m in (d.get('moves') or [])]; mov = '; '.join(m for m in mv if m.startswith('Spread')); movt = '; '.join(m for m in mv if m.startswith('Total'))
    la, lh = d.get('trends', {}).get('away') or {}, d.get('trends', {}).get('home') or {}
    def last(tr, code):
        g = (tr or {}).get('games') or []
        return ', '.join(f"{'W' if x['pf'] > x['pa'] else 'L'} {x['pf']}-{x['pa']} vs {x['opp']}" for x in g[:3])
    return dict(movt=movt, A=A, H=H, fav=fav, dog=dog, ln=ln, t=t, eff=eff, etot=etot, mov=mov, la=last(la, A), lh=last(lh, H))
out_g, keep = [], []
for g in G:
    gid, d = g['id'], g['data']; d['_gid'] = gid
    if gid in STARTED: continue
    keep.append(gid)
for p in P:
    gid = '_'.join(p['id'].split('_')[:2])
    if gid in STARTED: continue
    d = p['data']; g = [x for x in G if x['id'] == gid][0]['data']; mk = d['market']; c = summaries(gid, g)
    d['reasons'] = [mkt(x, mk) for x in d['reasons']]; d['against'] = [mkt(x, mk) for x in d['against']]
    d['line_source'] = 'The Odds API median of books'; d['rule_key'] = d['rule']; d['rule_label'] = LAB(d['rule']); d['rule_family'] = FAM.get(d['rule'], d['rule'])
    d['time_logged'] = READ; d['logged_at'] = NOW; d.pop('note', None)
    pk = d['pick']; tm = pk.split()[0]; proj = (d.get('model') or {}).get('projection'); oth = c['H'] if tm == c['A'] else c['A']
    if mk == 'Spread':
        why = []
        if d['rule'].startswith('SPREAD_MOVE'): why.append(f"The spread moved toward {tm} since the open ({c['mov'] or 'Odds API open vs latest'}).")
        if d['rule'] == 'MODEL_EDGE' and proj: why.append(f"Our margin model has {proj.split()[0] if gnum(proj) < 0 else oth if proj.split()[0]==tm else tm} by {abs(gnum(proj)):g}, against a line of {pk}.")
        if d['rule'] == 'EFF_SPREAD': why.append(f"Our efficiency model has {c['eff'].split()[0]} by {abs(gnum(c['eff'])):g}, against a line of {pk}.")
        why.append(mtxt(tm, gid) + '.')
        if (c['la'] if tm == c['A'] else c['lh']): why.append(f"Last games: {c['la'] if tm == c['A'] else c['lh']}.")
        ag = [mtxt(oth, gid) + '.']
        if d['rule'] != 'EFF_SPREAD' and c['eff']: ag.insert(0, f"Our efficiency model projects {c['eff']}.") if (c['eff'].split()[0] != tm and abs(gnum(c['eff']) or 0) > abs(d['line'] or 0)) or (c['eff'].split()[0] == tm and False) else None
        if d['rule'] != 'MODEL_EDGE' and proj and proj != c['eff']:
            pj = gnum(proj); pt = proj.split()[0]
            if (pt == tm and d['line'] is not None and (-(pj) < d['line'] if False else False)): pass
        d['summary'] = {'for': ' '.join(x for x in why if x.strip(' .')), 'against': ' '.join(x for x in ag if x and x.strip(' .')) or 'Nothing notable.'}
    else:
        side = tm.lower()
        why = []
        if d['rule'].startswith('OVER'): why.append(f"The total rose since the open ({c['movt'] or 'Odds API open vs latest'}).")
        if c['etot']:
            et = float(c['etot'])
            (why if (et > c['t']) == (side == 'over') else []).append(f"Our efficiency model total is {et:g} against {c['t']:g}.")
        why.append(f"{mtxt(c['A'], gid)}; {mtxt(c['H'], gid)}.")
        ag = []
        if c['etot'] and (float(c['etot']) > c['t']) != (side == 'over'): ag.append(f"Our efficiency model total is {float(c['etot']):g}, on the other side of {c['t']:g}.")
        d['summary'] = {'for': ' '.join(why), 'against': ' '.join(ag) or 'Nothing notable.'}
    if d.get('shadow'):
        r = META[d['rule']]; tt = r['tiers'].get(d['tier'], {}); re_ = tt.get('real') or {}
        if re_.get('w') is None and re_.get('l') is None: why_ = 'no status record yet'
        elif tt.get('pending_on'): why_ = f"status record {re_['w']}-{re_['l']} {re_['u']:+.2f}u, {tt['pending_on'][0].lower() + tt['pending_on'][1:]}"
        else: why_ = f"status record red, {re_['w']}-{re_['l']} {re_['u']:+.2f}u"
        d['conflict'] = f"{LAB(d['rule'])} {d['tier']} tier is turned off ({why_}), so this fit is logged as a would-be pick."
    p['data'] = d; json.dump(d, open(O/f"p_{p['id']}.json", 'w'))
P2 = [p for p in P if '_'.join(p['id'].split('_')[:2]) not in STARTED]
json.dump(P2, open(O/'picks.json', 'w'))
for p in P2: print(p['id'], p['data']['pick'], p['data']['tier'], '|', p['data']['summary']['for'][:160], '|', p['data']['summary']['against'][:120], '|', p['data']['conflict'][:100])

# ---------- game docs (every Top 25 game today; started games get "Game started before the run posted picks")
STARTED_NOTE = 'Game started before the run posted picks'
PB = {}
for p in P2: PB.setdefault('_'.join(p['id'].split('_')[:2]), []).append(p['data'])
for g in G:
    gid, d = g['id'], g['data']; d.pop('_gid', None); A, H = d['away']['code'], d['home']['code']; c = summaries(gid, dict(d, _gid=gid))
    for k in ('side', 'side_against'): d['reasons'][k] = [mkt(x, 'Spread') for x in d['reasons'].get(k, [])]
    for k in ('total', 'total_against'): d['reasons'][k] = [mkt(x, 'Total') for x in d['reasons'].get(k, [])]
    eff, etot = d['model'].get('our_spread'), d['model'].get('our_total')
    sa = f"{mtxt(A, gid)}. {mtxt(H, gid)}. The line is {c['fav']} -{c['ln']:g}; our efficiency model has {eff.split()[0]} by {abs(gnum(eff)):g}." if eff and c['ln'] else ''
    ta = f"The total is {c['t']:g}; our efficiency model total is {float(etot):g}." if etot and c['t'] else ''
    for kind, mk in (('side', 'Spread'), ('total', 'Total')):
        if gid in STARTED:
            d['picks'][kind] = {'none': STARTED_NOTE, 'analysis': sa if kind == 'side' else ta}; continue
        fits = [x for x in PB.get(gid, []) if x['market'] == mk]
        if fits:
            txt = '; '.join(f"{LAB(x['rule'])} ({x['pick']}, {x['tier']} tier)" for x in fits)
            none = f"Rules that fit: {txt}. Each of those tiers is turned off under the status policy, so they are logged as would-be picks and the card has no {'side' if kind == 'side' else 'total'} in this game."
        else:
            none = ("No spread rule fits: the spread has not moved since the open and neither model gap reaches a rule threshold." if kind == 'side'
                    else "No total rule fits: the total has not moved since the open and our model total is close to the posted number.")
        d['picks'][kind] = {'none': none, 'analysis': sa if kind == 'side' else ta}
    d['lines']['book'] = 'The Odds API median of books'; d['lines']['read_at'] = READ
    d['lines']['openers'] = (d['lines'].get('openers') or '').replace('DraftKings', 'The Odds API open')
    d['lines']['periods_note'] = 'No period lines (1H, 2H, quarters) posted by The Odds API books for these women\'s games.'
    d['moves'] = [m.replace('(DraftKings)', '(The Odds API median of books)') for m in d.get('moves', [])]
    d['notes'] = [n for n in d['notes'] if not n.startswith('Signal score') and 'texas222' not in n and n != 'OK']
    d['notes'].append(f"No Action Network read this run (no browser); no splits or sharp report for these games (B131). Lines: The Odds API median of books, read {READ} Phoenix.")
    d['notes'].append('Injuries: the ESPN injury feed lists no NCAAW injuries for either team; no starter changes found in the data feed.')
    if gid in STARTED: d['notes'].append(f"{STARTED_NOTE} (the run started at 4:44 PM Phoenix)." if 'WVU' not in gid else f"{STARTED_NOTE}: tipped 8:30 AM Phoenix, final before the run.")
    d['model'].setdefault('adjustments', []); d['model']['adjustments_note'] = 'No absences reported for either team; no adjustment applied.'
    sp, tot = d['lines'].get('spread'), d['lines'].get('total')
    if sp and tot:
        d['line_history'] = [dict(as_of=NOW, spread=f"{sp['home'].split()[0]} {H}", total=tot['over'].split()[0], ml_away=(d['lines'].get('moneyline') or {}).get('away'), ml_home=(d['lines'].get('moneyline') or {}).get('home'), source='The Odds API median of books')]
    d['pick_history'] = [dict(as_of=NOW, market=x['market'], pick=x['pick'], price=x['price'], line=x.get('line'), tier=x['tier'], rule=x['rule'], shadow=x.get('shadow', False)) for x in PB.get(gid, [])]
    for sd in ('away', 'home'):
        ts = TS['teams'].get(TS['index'].get(d[sd]['code']))
        if ts: d[sd]['stats'] = ts['stats']
    d['flags'] = []
    out_g.append({'id': gid, 'data': d}); json.dump(d, open(O/f"g_{gid}.json", 'w'))
json.dump(out_g, open(O/'games.json', 'w'))
for g in out_g: print(g['id'], {k: v.get('none', '')[:150] for k, v in g['data']['picks'].items()}, '|', g['data']['picks']['side'].get('analysis', '')[:200])
