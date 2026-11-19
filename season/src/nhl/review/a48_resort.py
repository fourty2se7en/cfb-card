import json, glob, os, re, sys, collections
sys.path.insert(0, '/home/claude/season/nhl14a48')
from teams import TEAMS
D = '/home/claude/a48f/dl/sports/nhl'
LOOSE = {'ML1': 'ML1_2', 'ML1_2': 'ML1_2', 'PL1': 'PL1_SA', 'PL1_SA': 'PL1_SA', 'TOT1': 'TOT1_DIV', 'TOT1_DIV': 'TOT1_DIV', 'TOT2': 'TOT2_2', 'TOT2_2': 'TOT2_2'}
STRICT = {'ML1_2': 'ML1_3', 'PL1_SA': 'PL1_SAM', 'TOT1_DIV': 'TOT1_BOTH', 'TOT2_2': 'TOT2_3'}
LAB = {'ML1_3': 'FG Signal Moneyline 3+', 'PL1_SAM': 'FG Sharp Puck Line + Money or Line Move', 'TOT1_BOTH': 'FG Division Over, Both', 'TOT2_3': 'FG Contrarian Total 3+'}
CONF = ('reverse line move', 'reverse line movement', 'bigger bets than ticket share', 'money % above ticket %')
CL = json.load(open('/home/claude/a48f/nhl_close_scores.json'))
META = json.load(open(D.replace('sports/nhl','meta/nhl.json'))); META = META.get('data', META); RET = META.get('retier', {})
picks = {f.split('/')[-1][:-5]: json.load(open(f)) for f in glob.glob(D + '/picks/*.json')}
def ld(p):
    return json.load(open(p)) if os.path.exists(p) else None
def side_of(j):
    p = j.get('pick', '')
    for code in (j['away'], j['home']):
        t = TEAMS.get(code)
        if t and (t[1] in p or t[0] in p): return 'A' if code == j['away'] else 'H'
    return None
def ml_sigs(j):
    """moneyline signals (label, side, pts) for the game, with source."""
    g = f"{j['date']}_{j['away']}-{j['home']}"
    inp = ld(f'{D}/inputs/{g}.json')
    if inp and inp.get('signals'):
        return [(s[0].lower(), s[2], s[3]) for s in inp['signals'] if s[1] == 'Moneyline'], 'inputs doc'
    for i, d in picks.items():
        if i.startswith(g) and d.get('market') == 'Moneyline' and (d.get('reasons') or d.get('against')) and d.get('rule') in ('ML1', 'ML1_2', 'ML1_3'):
            sd = side_of(d); od = 'H' if sd == 'A' else 'A'
            if sd: return [(x['label'].lower(), sd, x.get('points', 0)) for x in d.get('reasons') or []] + [(x['label'].lower(), od, x.get('points', 0)) for x in d.get('against') or []], 'ML pick doc'
    b = ld(f'{D}/backtest/{g}_ML1.json')
    if b:
        I = b['inputs']; sd = I.get('signal_side'); od = 'H' if sd == 'A' else 'A'
        f = lambda s: (s.rsplit(' ', 1)[0].lower(), int(s.rsplit(' ', 1)[1]))
        return [(f(s)[0], sd, f(s)[1]) for s in I.get('signals_for', [])] + [(f(s)[0], od, f(s)[1]) for s in I.get('signals_against', [])], 'backtest close'
    x = CL.get(g)
    if x: return [(a.lower(), sd, p) for a, m, sd, p in x['S'] if m == 'Moneyline'], 'close score'
    return None, None
def classify(i, j):
    r = LOOSE[j['rule']]; g = f"{j['date']}_{j['away']}-{j['home']}"
    tb = j.get('tier_basis') or ''
    if r == 'ML1_2':
        m = re.search(r'signal lead (-?\d+)', tb)
        if m: return int(m.group(1)) >= 3, 'tier_basis lead ' + m.group(1)
        if j.get('reasons') or j.get('against'):
            ld_ = sum(x.get('points', 0) for x in j.get('reasons') or []) - sum(x.get('points', 0) for x in j.get('against') or [])
            return ld_ >= 3, f'reasons lead {ld_}'
        inp = ld(f'{D}/inputs/{g}.json'); sd = side_of(j)
        if inp and inp.get('side') == sd and inp.get('lead') is not None: return inp['lead'] >= 3, f"inputs doc lead {inp['lead']}"
        if j['date'] >= '2026-11-02' and j.get('tier') == 'Strong': return True, 'doc tier Strong (lead 4+)'
        if not j.get('backfill'): return None, 'no run-time lead'
        b = ld(f'{D}/backtest/{g}_ML1.json')
        if b and b['inputs'].get('signal_side') == sd and b['inputs'].get('lead') is not None: return b['inputs']['lead'] >= 3, f"backtest close lead {b['inputs']['lead']}"
        x = CL.get(g)
        if x and x['side'] == sd: return x['lead'] >= 3, f"close score lead {x['lead']}"
        return None, 'no lead'
    if r == 'TOT2_2':
        m = re.search(r'(?:fades: |signal lead )(-?\d+)', tb)
        if m: return int(m.group(1)) >= 3, 'totals lead ' + m.group(1)
        return None, 'no lead'
    if r == 'TOT1_DIV':
        inp = ld(f'{D}/inputs/{g}.json')
        if inp and inp.get('div'):
            a, h, p = inp['div']; return ({a, h} == {'Atlantic', 'Pacific'} and p == 2), f'inputs div {a}/{h} {p}'
        b = ld(f'{D}/backtest/{g}_TOT1.json')
        if b and 'div_pts' in b['inputs']:
            I = b['inputs']; return bool(I.get('atlantic_vs_pacific')) and I['div_pts'] == 2, f"backtest div {I.get('div_away')}/{I.get('div_home')} {I['div_pts']}"
        x = CL.get(g)
        if x and x['div'][2] is not None:
            a, h, p = x['div']; return ({a, h} == {'Atlantic', 'Pacific'} and p == 2), f'close score div {a}/{h} {p}'
        return None, 'no division inputs'
    if r == 'PL1_SA':
        sd = side_of(j)
        labs = [(x.get('label') or '').lower() for x in j.get('reasons') or []]
        if any(l in CONF for l in labs): return True, 'doc reasons'
        full = [l for l in labs if l not in ('sharp action on its moneyline', 'cover chance about even with price', 'cover chance below price')]
        if full: return False, 'doc reasons (full evidence, no money or move)'
        S, src = ml_sigs(j)
        if src in ('backtest close', 'close score') and not j.get('backfill'): return None, 'only close-time signals'
        if S is None or sd is None: return None, 'no signals'
        hit = any(l in CONF and s == sd and p for l, s, p in S)
        return hit, src
out = {}; cnt = collections.Counter(); unk = []
for i, j in sorted(picks.items()):
    if j.get('rule') not in LOOSE or j['date'] >= '2026-11-14' or j.get('market') == 'Prop': continue
    if j['rule'] in ('ML1_2', 'PL1_SA', 'TOT1_DIV', 'TOT2_2'): continue  # already disjoint-era docs (none before Nov 14)
    s, why = classify(i, j)
    cnt[(LOOSE[j['rule']], s, why.split(' ')[0] + ' ' + why.split(' ')[1] if s is not None else why)] += 1
    if s: out[i] = dict(to=STRICT[LOOSE[j['rule']]], frm=j['rule'], why=why)
    if s is None: unk.append(i)
for k, v in sorted(cnt.items(), key=str): print(k, v)
print('rekey', len(out), 'unknown', len(unk), unk)
json.dump(out, open('/home/claude/a48f/rekey_nhl.json', 'w'), indent=0)
