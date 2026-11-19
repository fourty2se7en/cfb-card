"""Parse Action Network open and DraftKings (ESPN) open/close into hist/openers2.csv. Home-spread convention (home favoured = negative)."""
import pathlib, sys, pandas as pd, numpy as np
D = pathlib.Path(__file__).parent; sys.path.insert(0, str(D.parent)); import nflmodel as M
def canon(x): return M.canon_team({'JAC': 'JAX', 'LAR': 'LA', 'WSH': 'WAS'}.get(x, x)) or x
def num(s):
    try: return float(s)
    except Exception: return None
rows = {}
for it in ''.join(open(D/'an_open_parts.txt').read().split('\n')).split(';'):
    p = it.split(' ')
    w, (a, h) = int(p[0]), [canon(z) for z in p[1].split('@')]
    sa = num(p[2]); ml = p[4].split('/') if p[4] != '-' else [None, None]
    rows[(w, f'{a}@{h}')] = dict(an_open_sp_h=(-sa if sa is not None else None), an_open_tot=num(p[3]), an_open_ml_a=num(ml[0]), an_open_ml_h=num(ml[1]) if len(ml) > 1 else None)
for it in ''.join(open(D/'dk_parts.txt').read().split('\n')).split(';'):
    p = it.split(' ')
    while len(p) < 14: p.append('')
    w, (a, h) = int(p[0]), [canon(z) for z in p[1].split('@')]
    r = rows.setdefault((w, f'{a}@{h}'), {})
    r.update(dk_open_sp_h=num(p[2]), dk_close_sp_h=num(p[3]), dk_open_tot=num(p[4]), dk_close_tot=num(p[5]), dk_open_ml_a=num(p[6]), dk_open_ml_h=num(p[7]),
             dk_close_ml_a=num(p[8]), dk_close_ml_h=num(p[9]), dk_close_sp_price_a=num(p[10]), dk_close_sp_price_h=num(p[11]), dk_close_over=num(p[12]), dk_close_under=num(p[13]))
O = pd.DataFrame([dict(week=k[0], game=k[1], **v) for k, v in rows.items()])
O.to_csv(D/'openers2.csv', index=False); print(len(O), 'rows')
