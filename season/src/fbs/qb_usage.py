"""QB usage for inj_merge.py (Nov 9 2026). Two steps:
  1) python3 qb_usage.py ids      -> prints window.IDS = [...] for qb_usage_pull.js (finished 2026 games with an FBS team, in week order)
  2) run qb_usage_pull.js in a site.api.espn.com tab, read window.QU in 950-character slices, save as qu_raw.txt
     python3 qb_usage.py build qu_raw.txt -> qb_usage.txt (team|qb1_by_attempts|qb1_share|last_game_passer), team = CFBD school
Covers games with an FBS team only, so an FCS team's line reflects its FBS games only (the FCS deep dive has its own pull)."""
import sys, json
from pathlib import Path
import pandas as pd
R = Path(__file__).parent / 'repo'
G = pd.read_csv(R / 'games.csv'); G = G[(G.season == 2026) & G.homePoints.notna() & ((G.homeClassification == 'fbs') | (G.awayClassification == 'fbs'))]
G = G.sort_values(['week', 'startDate'])
if sys.argv[1] == 'ids':
    print('window.IDS=' + json.dumps([str(int(i)) for i in G.id]) + ';')
else:
    TM = pd.read_csv(R / 'teams.csv').drop_duplicates('id').set_index('id').school.to_dict()
    out = []
    for l in Path(sys.argv[2]).read_text().splitlines():
        f = l.strip().split('|')
        if len(f) == 4 and f[0].isdigit() and int(f[0]) in TM: out.append('|'.join([TM[int(f[0])], f[1], f[2], f[3]]))
    Path(Path(__file__).parent / 'qb_usage.txt').write_text('\n'.join(out) + '\n'); print(len(out), 'teams')
