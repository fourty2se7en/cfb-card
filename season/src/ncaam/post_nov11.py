"""Nov 11 post step: lineups, player and unit ratings, absence adjustments and ESPN predictor onto today's game docs (B35, B37)."""
import json, pathlib, re, sys
W = pathlib.Path(__file__).resolve().parent.parent; OUT = W/'out'/'hubw'; DATE = sys.argv[1]; DS = DATE.replace('-', '')
raw = (W/'data'/'raw'/f'lineups_m_{DS}.txt').read_text().strip().split('\n@@LU\n')
PR = {l.split('|')[0]: l.split('|')[1:] for l in raw[0].strip().splitlines()}
LU = {}
for l in raw[1].strip().splitlines():
    ab, ng, ps = l.split('|', 2)
    pl = []
    for x in ps.split(';'):
        f = x.split(',')
        if len(f) < 7: continue
        pl.append(dict(player=f[0], pos=f[1], starter=f[2] != 'b', mpg=float(f[3]), ppg=float(f[4]), rpg=float(f[5]), apg=float(f[6])))
    LU[ab] = (int(ng), pl)
imp = lambda p: p['ppg'] + 0.7*p['rpg'] + 1.0*p['apg']
allv = sorted(imp(p) for _, pl in LU.values() for p in pl)
pct = lambda v: round(100*sum(1 for x in allv if x <= v)/len(allv))
def tags(p):
    s, w = [], []
    if p['ppg'] >= 15: s.append('primary scorer')
    elif p['ppg'] >= 10: s.append('steady scorer')
    if p['rpg'] >= 7: s.append('rebounder')
    if p['apg'] >= 4: s.append('playmaker')
    if p['ppg'] < 5 and p['mpg'] >= 20: w.append('limited scoring')
    if p['rpg'] < 2 and p['pos'] in ('F', 'C', 'PF'): w.append('light on the glass for a big')
    if p['mpg'] < 15: w.append('short minutes')
    return s, w
def unit_vals(pl):
    st = [p for p in pl if p['starter']]; bn = [p for p in pl if not p['starter']]
    return {'Scoring': sum(p['ppg'] for p in st), 'Rebounding': sum(p['rpg'] for p in st), 'Playmaking': sum(p['apg'] for p in st), 'Bench': sum(imp(p) for p in bn)}
UV = {ab: unit_vals(pl) for ab, (_, pl) in LU.items()}
def upct(k, v):
    xs = sorted(u[k] for u in UV.values()); return round(100*sum(1 for x in xs if x <= v)/len(xs))
TID = {}
for l in (W/'data'/'raw'/f't_{DS}.txt').read_text().strip().splitlines():
    f = l.split('|'); TID[(f[3], f[4])] = f[1]
G = json.load(open(OUT/'games_today.json')); n = 0
for d in G:
    g = d['data']; a, h = g['away']['code'], g['home']['code']; gid = TID.get((a, h))
    lu, un = {}, {}
    for side, code in (('away', a), ('home', h)):
        if code not in LU: continue
        ng, pl = LU[code]; rows = []
        for p in pl:
            s, w = tags(p)
            rows.append(dict(player=p['player'], pos=p['pos'], role='Starter' if p['starter'] else 'Top reserve', starter=p['starter'], status='Available (no ESPN injury report)',
                             rating=pct(imp(p)), strengths=s, weaknesses=w, line=f"{p['mpg']:.0f} min, {p['ppg']:.1f} pts, {p['rpg']:.1f} reb, {p['apg']:.1f} ast", source=f"ESPN box scores, last {ng} games (starters from the most recent game)"))
        lu[side] = rows
        u = UV[code]; un[side] = {k: dict(rating=upct(k, v), note=f"starters {v:.1f} per game" if k != 'Bench' else f"top reserve impact {v:.1f}") for k, v in u.items()}
    if lu: g['lineups'] = lu; g['units'] = un; n += 1
    g.setdefault('model', {})['adjustments'] = []
    g['model']['adjustments_note'] = 'No starter listed out on the ESPN injury report for either team; no absence adjustment applied'
    if gid in PR:
        hp = float(PR[gid][0]); g['model']['espn_bpi_win_pct_home'] = hp
        g.setdefault('notes', []).append(f"ESPN BPI gives {g['home'].get('name', h)} a {hp:.0f}% chance to win")
    g['injuries'] = []
json.dump(G, open(OUT/'games_today.json', 'w'))
print('lineups on', n, 'of', len(G), 'games')
