"""Append one day's finals (data/raw/y_<YD>.txt) to bt7/src/season, with DraftKings opens from data/raw/espn_board_<YD>.txt.
Usage: [ROOT=dir] python3 append.py YD [season_dir]. Replaces any rows already in the season files for that date (safe to rerun)."""
import json, sys, pathlib
import os
ROOT = pathlib.Path(os.environ.get('ROOT') or pathlib.Path(__file__).resolve().parent.parent.parent)
YD = sys.argv[1]; S = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT/'src'/'season'; RAW = ROOT/'data'/'raw'
nf = lambda x: float(x) if x not in ('', None) else None
YB = {}
p = RAW/f'espn_board_{YD}.txt'
if p.exists():
    for l in p.read_text().strip().splitlines(): f = l.split('|'); YB[f[1]] = f
add = {'M': [[], []], 'W': [[], []]}
for l in (RAW/f'y_{YD}.txt').read_text().strip().splitlines():
    f = l.split('|'); lg, gid, h, a, hc, ac, cg, nu, hr, ar, hs, as_, h1, a1, vs, bx = f[:16]; od = f[16] if len(f) > 16 else ''
    if not hc or not ac: continue
    o = [nf(x) for x in od.split(',')] if od else [None]*6
    op, cl, to, tc = o[0], o[1], o[2], o[3]; yb = YB.get(gid)
    if yb:
        op = nf(yb[14]) if yb[14] else op; to = nf(yb[16]) if yb[16] else to
        cl = cl if cl is not None else nf(yb[15]); tc = tc if tc is not None else nf(yb[17])
    ml = lambda x: x if x is not None and 100 <= abs(x) <= 5000 else None
    mlh, mla = (ml(o[4]), ml(o[5])) if len(o) > 5 else (None, None)
    rk = lambda x: int(x) if x else None
    if cl is not None and tc is not None:
        add[lg][0].append([lg, '2026-27', YD, h, a, hc, ac, int(cg), int(nu), '', rk(hr), rk(ar), int(hs), int(as_), nf(h1), nf(a1), None, vs, op, cl, to, tc, None, None, None, None, cl, tc, mlh, mla, 1])
    b = [int(x) if x else None for x in bx.split(',')] if bx else [None]*8
    add[lg][1].append(['2026-27', YD, h, a, int(nu), int(cg), int(hs), int(as_), *b, op, cl, to, tc, None, None, None, None, cl, tc])
for lg in 'MW':
    for fn, rows in (('games', add[lg][0]), ('box', add[lg][1])):
        p = S/f'{fn}_{lg}.txt'
        if not p.exists(): continue   # one league per artifact (Nov 8)
        old = [x for x in p.read_text().strip().splitlines() if f'"{YD}"' not in x]
        p.write_text('\n'.join(old + [json.dumps(r) for r in rows]) + '\n'); print(fn, lg, '+', len(rows))
