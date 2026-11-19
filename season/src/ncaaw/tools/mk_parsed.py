"""Build ../pull/parsed.json for extra_hub.py from the cfb-card repo ESPN files (Nov 17). Usage: python3 mk_parsed.py <repo> <date> <ap_poll.json> <out>
T: code~name~short~color~t:rec,v:conf,h:home,r:road (today's slate); V: id~venue~city~state; A: ['rank:team;...']; LOG: YYYYMMDD|id|home|away|hs|as||hq|aq|ar|hr (every final this season)."""
import gzip, json, sys, pathlib
repo, day, apf, out = sys.argv[1:5]; base = pathlib.Path(repo)/'season'/'data'/'espn'/'ncaaw'
T, V, LOG = {}, [], []
ev = json.load(gzip.open(base/day/'scoreboard.json.gz'))['events']
for e in ev:
    c = e['competitions'][0]; vn = c.get('venue') or {}; ad = vn.get('address') or {}
    V.append(f"{e['id']}~{vn.get('fullName','')}~{ad.get('city','')}~{ad.get('state','')}")
    for x in c['competitors']:
        t = x['team']; R = {r.get('type'): r.get('summary') for r in x.get('records') or []}
        recs = ','.join(f"{k}:{R[s]}" for k, s in (('t', 'total'), ('v', 'vsconf'), ('h', 'home'), ('r', 'road')) if R.get(s))
        T[t['abbreviation']] = f"{t['abbreviation']}~{t.get('displayName','')}~{t.get('shortDisplayName','')}~{t.get('color','')}~{recs}"
for d in sorted(p.name for p in base.iterdir() if p.is_dir() and p.name < day):
    f = base/d/'scoreboard_final.json.gz'
    if not f.exists(): f = base/d/'scoreboard.json.gz'
    if not f.exists(): continue
    for e in json.load(gzip.open(f))['events']:
        c = e['competitions'][0]
        if c['status']['type']['state'] != 'post': continue
        C = {x['homeAway']: x for x in c['competitors']}; H, A = C['home'], C['away']
        ls = lambda x: ','.join(str(int(q['value'])) for q in x.get('linescores') or [])
        rk = lambda x: '' if (x.get('curatedRank') or {}).get('current', 99) in (99, None) else str(x['curatedRank']['current'])
        LOG.append('|'.join([d.replace('-', ''), e['id'], H['team']['abbreviation'], A['team']['abbreviation'], H.get('score', ''), A.get('score', ''), '', ls(H), ls(A), rk(A), rk(H)]))
        for x in (H, A):
            t = x['team']; T.setdefault(t['abbreviation'], f"{t['abbreviation']}~{t.get('displayName','')}~{t.get('shortDisplayName','')}~{t.get('color','')}~")
ap = json.load(open(apf))['W']
json.dump(dict(T=list(T.values()), V=V, A=[';'.join(f"{x['rank']}:{x['team']}" for x in ap)], LOG=LOG), open(out, 'w'))
print(len(T), len(V), len(LOG))
