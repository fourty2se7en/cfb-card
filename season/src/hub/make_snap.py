"""Build snap/<sport>.json for Season Cards from a hub download folder (ArtifactData out_dir layout).
usage: python3 make_snap.py <download_dir> <out_dir> "<as of label>" """
import json, glob, os, sys
src, out, at = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
def coll(path):
    res = []
    for f in sorted(glob.glob(os.path.join(src, path, '*.json'))):
        d = json.load(open(f)); d = d.get('data', d) if isinstance(d, dict) and set(d.keys()) <= {'data', 'id', 'version'} else d
        d['__id'] = os.path.basename(f)[:-5]; res.append(d)
    return res
def one(path, did):
    f = os.path.join(src, path, did + '.json')
    if not os.path.exists(f): return None
    d = json.load(open(f)); return d.get('data', d) if isinstance(d, dict) and set(d.keys()) <= {'data', 'id', 'version'} else d
for sp in ['nba', 'nhl', 'nfl', 'ncaam', 'ncaaw', 'fbs', 'fcs']:
    J = dict(at=at, picks=coll(f'sports/{sp}/picks'), bg=coll(f'sports/{sp}/picks_bg') if sp == 'nfl' else [],
             games=coll(f'sports/{sp}/games'), bt=coll(f'sports/{sp}/backtest'), pv=coll(f'sports/{sp}/preview'), meta=one('meta', sp), std=one('standings', sp))
    p = os.path.join(out, sp + '.json'); json.dump(J, open(p, 'w'), separators=(',', ':'))
    print(sp, len(J['picks']), len(J['games']), len(J['bt']), round(os.path.getsize(p) / 1e6, 2), 'MB')
