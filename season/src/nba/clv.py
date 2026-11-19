"""Closing line check for logged prop picks.
Usage: python3 clv.py <props_open.txt> <props_close.txt> <ledger_today.json> <out_dir>
Both props files use the props_raw.txt format (game|player|stat|line|over|under). For each logged prop (PLAY or LEAN), finds the
closing texas222 line for the same player and stat and writes close_line, close_price and clv: the change in our side's no-vig
chance, in points, plus about 8 points of chance per full stat point the line moved our way. Writes one update JSON per doc and
writes.json (ArtifactData batch entries; add each doc's if_version before sending)."""
import json, sys, pathlib
def be(o): return -o/(-o+100) if o < 0 else 100/(o+100)
def nv(o, u): a, b = be(o), be(u); return a/(a+b)
def load(p):
    R = {}
    for ln in pathlib.Path(p).read_text().strip().splitlines()[1:]:
        g, pl, st, line, o, u = ln.split('|'); R.setdefault((pl, st), []).append((float(line), int(o), int(u)))
    return R
def main(op, cl, led, out):
    O, C = load(op), load(cl); out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=True); W = []
    for d in json.loads(pathlib.Path(led).read_text()):
        x = d['data']
        if x.get('market') != 'Prop': continue
        k = (x['player'], x['stat'])
        o = next((r for r in O.get(k, []) if r[0] == x['line']), None)
        if not o or k not in C: continue
        c = min(C[k], key=lambda r: abs(r[0] - x['line']))
        ov = x['side'] == 'over'
        p0 = nv(o[1], o[2]) if ov else 1 - nv(o[1], o[2])
        p1 = nv(c[1], c[2]) if ov else 1 - nv(c[1], c[2])
        mv = (c[0] - x['line']) * (1 if ov else -1)
        clv = round(100*(p1 - p0) + 8*mv, 1)
        upd = dict(close_line=c[0], close_price=(c[1] if ov else c[2]), clv=clv)
        f = out/f"{d['id']}.json"; f.write_text(json.dumps(upd))
        W.append(dict(op='update', collection='picks', doc_id=d['id'], file_path=str(f.resolve())))
    (out/'writes.json').write_text(json.dumps(W, indent=1)); print(len(W), 'closing lines matched')
if __name__ == '__main__': main(*sys.argv[1:5])
