"""A43 (Trina approved): team total contradiction flag. Flags a game when both team total picks go against the game total pick
and they cannot all win together; keeps all picks, sets tt_contradiction on those pick docs and adds a game doc flag."""
import json, os, glob, math
H = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hub') + '/'
P = {os.path.basename(f)[18:-5]: (f, json.load(open(f))) for f in glob.glob(H + 'sports_nhl_picks__*.json')}
games = {}
for k, (f, d) in P.items(): games.setdefault(k.split('_')[1], []).append((k, f, d))
flags = {}
for g, L in games.items():
    a, h = g.split('-'); tts = [x for x in L if x[2].get('market') == 'Team total']; hit = []
    for t in [x for x in L if x[2].get('market') == 'Total']:
        over = t[2]['pick'].startswith('Over'); opp = 'Under' if over else 'Over'
        ag = {x[2]['side']: x for x in tts if f' {opp} ' in x[2]['pick']}
        if set(ag) != {a, h}: continue
        ls = [ag[s][2]['line'] for s in (a, h)]
        if (sum(math.floor(l) for l in ls) <= t[2]['line']) if over else (sum(math.ceil(l) for l in ls) >= t[2]['line']): hit.append(t)
    if hit:
        ag = [x for x in tts if x[2]['side'] in (a, h)]; s = sum(x[2]['line'] for x in ag)
        rl = ' and '.join(f"{t[2].get('rule_label', t[2]['rule'])} {t[2]['pick']}" for t in hit)
        flags[g] = f"Team total contradiction: {ag[0][2]['pick']} and {ag[1][2]['pick']} (lines add to {s:g}) vs {rl}: they cannot all win together; all picks stay"
        for x in ag + hit: x[2]['tt_contradiction'] = True; json.dump(x[2], open(x[1], 'w'), indent=1)
for g, m in flags.items():
    f = H + f'sports_nhl_games__2026-11-15_{g}.json'; d = json.load(open(f)); d['flags'] = (d.get('flags') or []) + [m]; json.dump(d, open(f, 'w'), indent=1)
print('tt flags', sorted(flags))
