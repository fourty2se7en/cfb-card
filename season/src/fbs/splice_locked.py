"""Second run of the day: games that kick off before CUTOFF keep the morning slate entry (lines, signals, picks, props) exactly as logged.
python3 splice_locked.py <div> <cutoff HH:MM Phoenix>"""
import json, sys
from pathlib import Path
import pandas as pd
D = Path(__file__).parent; AM = Path('/home/claude/cfb/w')
div, cut = sys.argv[1], sys.argv[2]
CUT = pd.Timestamp(f'2026-11-07 {cut}', tz='America/Phoenix')
NOW = pd.Timestamp.now(tz='America/Phoenix')
S = json.load(open(D / f'slate_{div}.json')); A = json.load(open(AM / f'slate_{div}.json'))
am = {g['id']: g for g in A['games']}
locked = set()
for i, g in enumerate(S['games']):
    if g['date'] != '2026-11-07': continue
    if pd.Timestamp(g['dt']) <= CUT and g['id'] in am:
        m = dict(am[g['id']]); m['started'] = bool(pd.Timestamp(g['dt']) <= NOW) or True
        m['locked_note'] = 'kicked off before the 2nd run update; picks kept as logged at the morning run'
        S['games'][i] = m; locked.add(g['id'])
lk = {(g['away'], g['home']) for g in S['games'] if g['id'] in locked}
S['props'] = [p for p in (S.get('props') or []) if (p['away'], p['home']) not in lk] + \
             [dict(p, started=True) for p in (A.get('props') or []) if (p['away'], p['home']) in lk]
S['locked'] = sorted(locked)
json.dump(S, open(D / f'slate_{div}.json', 'w'), indent=1, default=str)
# pick-time inputs and snapshots: locked games keep the morning lines
for fn in (f'pickinputs_{div}.jsonl', f'snap_{div}.jsonl'):
    old = {}
    for line in (AM / 'hist' / fn).read_text().splitlines():
        if line.strip(): z = json.loads(line); old[z['id']] = line
    out = []
    for line in (D / 'hist' / fn).read_text().splitlines():
        if not line.strip(): continue
        z = json.loads(line)
        out.append(old.get(z['id'], line) if z['id'] in locked else line)
    (D / 'hist' / fn).write_text('\n'.join(out) + '\n')
print(div, 'locked', len(locked), 'cutoff', cut)
