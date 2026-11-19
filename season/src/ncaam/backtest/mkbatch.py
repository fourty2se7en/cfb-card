"""Usage: python3 mkbatch.py M|W FROM_DATE TO_DATE (YYYY-MM-DD). Reads out_<LG>.json in the current folder, writes one doc file per pick to d/ and
ArtifactData batch files of 50 set writes to batches/. Docs that already exist in the hub need if_version added to their entries."""
import json, sys, os
os.makedirs('d', exist_ok=True); os.makedirs('batches', exist_ok=True)
L, lo, hi = sys.argv[1], sys.argv[2], sys.argv[3]
d = [x for x in json.load(open(f'out_{L}.json')) if lo <= x['data']['date'] <= hi]
w = []
for i, x in enumerate(d):
    p = f'd/{L.lower()}{lo[-2:]}{i:03d}.json'; json.dump(x['data'], open(p, 'w')); w.append(dict(op='set', collection=f'sports/ncaa{L.lower()}/backtest', doc_id=x['id'], file_path=p))
for i in range(0, len(w), 50): open(f'batches/{L}{lo[-2:]}_{i//50:02d}.json', 'w').write(json.dumps(w[i:i+50], separators=(',', ':')))
print(L, len(d), (len(w)+49)//50)
