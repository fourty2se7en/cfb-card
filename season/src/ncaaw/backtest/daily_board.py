import json, sys, pathlib
B = pathlib.Path('/home/claude/ncaa'); D = B/'data'; S = B/'src'/'season'
YD, TD = sys.argv[1], sys.argv[2]   # 20261103 20261104
nf = lambda x: float(x) if x not in ('', None) else None
# yesterday's pre-game board (DraftKings open and current)
YB = {}
for l in (D/'raw'/f'espn_board_{YD}.txt').read_text().strip().splitlines():
    f = l.split('|'); YB[f[1]] = f
add = {'M': [[], []], 'W': [[], []]}
seen = {lg: {json.loads(l)[2 if lg else 1] for l in []} for lg in 'MW'}
have = {lg: set(l for l in (S/f'games_{lg}.txt').read_text().splitlines()) for lg in 'MW'}
for l in (D/'raw'/f'y_{YD}.txt').read_text().strip().splitlines():
    f = l.split('|'); lg, gid, h, a, hc, ac, cg, nu, hr, ar, hs, as_, h1, a1, vs, bx = f[:16]; od = f[16] if len(f) > 16 else ''
    if not hc or not ac: continue
    o = [nf(x) for x in od.split(',')] if od else [None]*6
    yb = YB.get(gid)
    op, cl, to, tc = o[0], o[1], o[2], o[3]
    if yb:
        op = nf(yb[14]) if yb[14] else op; to = nf(yb[16]) if yb[16] else to
        cl = cl if cl is not None else nf(yb[15]); tc = tc if tc is not None else nf(yb[17])
    ml = lambda x: x if x is not None and 100 <= abs(x) <= 5000 else None
    mlh, mla = (ml(o[4]), ml(o[5])) if len(o) > 5 else (None, None)
    rk = lambda x: int(x) if x else None
    if cl is not None and tc is not None:
        add[lg][0].append([lg, '2026-27', YD, h, a, hc, ac, int(cg), int(nu), '', rk(hr), rk(ar), int(hs), int(as_), nf(h1), nf(a1), None, vs,
                           op, cl, to, tc, None, None, None, None, cl, tc, mlh, mla, 1])
    b = [int(x) if x else None for x in bx.split(',')] if bx else [None]*8
    add[lg][1].append(['2026-27', YD, h, a, int(nu), int(cg), int(hs), int(as_), *b, op, cl, to, tc, None, None, None, None, cl, tc])
for lg in 'MW':
    for fn, rows in (('games', add[lg][0]), ('box', add[lg][1])):
        p = S/f'{fn}_{lg}.txt'; old = p.read_text().strip().splitlines()
        if any(f'"{YD}"' in x for x in old): print('already has', fn, lg); continue
        p.write_text('\n'.join(old + [json.dumps(r) for r in rows]) + '\n'); print(fn, lg, '+', len(rows))
# today's board, slate, ids
ids = dict(x.split(':') for x in (D/'ids.txt').read_text().strip().split(',') if x)
board, today = [], {'M': ['id|time|away|home|awayName|homeName|aConf|hConf|confGame|neutral|aRank|hRank|state'], 'W': ['id|time|away|home|awayName|homeName|aConf|hConf|confGame|neutral|aRank|hRank|state']}
for l in (D/'raw'/f't_{TD}.txt').read_text().strip().splitlines():
    l = l.replace('~', '|'*12); f = l.split('|'); tids = f[26].split(','); f = f[:26]
    if not f[5] or not f[6]: continue
    if f[21] == 'Draft': f[21] = 'DraftKings'
    board.append('|'.join(f))
    t = f[2].replace('PM', 'p').replace('AM', 'a')
    today[f[0]].append('|'.join([f[1], t, f[3], f[4], f[3], f[4], f[5], f[6], f[7], f[8], f[9], f[10], f[11]]))
    ids[f[0]+f[3]] = tids[0]; ids[f[0]+f[4]] = tids[1]
(D/'espn_board.txt').write_text('\n'.join(board) + '\n')
for lg in 'MW': (D/f'espn_today_{lg.lower()}.txt').write_text('\n'.join(today[lg]) + '\n'); print(lg, 'today', len(today[lg]) - 1)
(D/'ids.txt').write_text(','.join(f'{k}:{v}' for k, v in ids.items()))
