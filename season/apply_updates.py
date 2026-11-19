"""Apply the nightly grade updates to the Season Cards hub from a chat (Nov 19 2026). Read season/apply_updates.md first.

    python3 season/apply_updates.py prepare [--file season/ledger/updates/<day>.json] [--out DIR]
    python3 season/apply_updates.py pin DIR versions.json
    python3 season/apply_updates.py done DIR [batch_00.json ...] [--results results.json]

prepare  Takes every updates file in season/ledger/updates/ that has no <day>.applied marker (or just --file), merges them
         (later files win per doc), and writes DIR (default /tmp/apply_updates): batch_00.json, batch_01.json ... each a list
         of at most 50 hub batch entries {op: "update", collection, doc_id, data, if_version} and at most ~900 KB;
         unpinned.json for writes whose ledger version is unknown (the hub refuses an unpinned write to an existing doc);
         plan.json (source files, batches, done flags, the nightly summary). Prints the summary.
need     DIR: lists the unpinned docs by collection and date (need_versions.json) so the chat knows which hub reads to make.
pin      versions.json maps "collection/doc_id" -> current hub version (read with ArtifactData get/query). Sets if_version on
         those entries (in batches and unpinned.json) and moves now pinned unpinned entries into new batch files.
         Use it too when a batch fails on a stale version: the hub names the entry and its current version.
done     After the hub tool reports success for the named batches (default: every batch not yet done): builds the results,
         writes DIR/ledger_updates.json (the same data plus pending_hub removed) and runs
         `season/ledger.py apply-result DIR/ledger_updates.json DIR/results.json`, so the ledger docs get the new versions and
         lose pending_hub. --results: a JSON list {collection, doc_id, ok, version} from the tool result, when it gives
         versions; otherwise each new version is taken as if_version + 1. When every batch of the plan is done, writes
         <day>.applied markers next to the source updates files. Commit season/ledger afterwards (season/push_retry.sh).
"""
import argparse, glob, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UPD = ROOT / 'season' / 'ledger' / 'updates'
MAXN, MAXB = 50, 900_000


def key(w): return f"{w['collection']}/{w['doc_id']}"


def entry(w):
    e = dict(op=w.get('op', 'update'), collection=w['collection'], doc_id=w['doc_id'], data=w['data'])
    if w.get('if_version') is not None: e['if_version'] = int(w['if_version'])
    return e


def chunk(entries, start=0):
    out, cur, size = [], [], 0
    for e in entries:
        n = len(json.dumps(e, ensure_ascii=False).encode())
        if cur and (len(cur) >= MAXN or size + n > MAXB): out.append(cur); cur, size = [], 0
        cur.append(e); size += n
    if cur: out.append(cur)
    return out


def save_batches(d, plan, groups):
    for g in groups:
        name = f"batch_{len(plan['batches']):02d}.json"
        json.dump(g, open(d / name, 'w'), ensure_ascii=False)
        plan['batches'].append(dict(file=name, n=len(g), done=False))


def cmd_prepare(a):
    files = [Path(a.file)] if a.file else [Path(f) for f in sorted(glob.glob(str(UPD / '*.json'))) if not Path(f[:-5] + '.applied').exists()]
    if not files: print('no unapplied updates files'); return
    merged, summ = {}, {}
    for f in files:
        J = json.load(open(f)); summ[f.name] = J.get('summary')
        for w in J.get('writes', []):
            k = key(w)
            if k in merged: merged[k] = dict(merged[k], data=dict(merged[k]['data'], **w['data']))
            else: merged[k] = dict(w)
    d = Path(a.out); d.mkdir(parents=True, exist_ok=True)
    for f in glob.glob(str(d / '*.json')): os.remove(f)
    pinned = [entry(w) for w in merged.values() if w.get('if_version') is not None]
    unpinned = [entry(w) for w in merged.values() if w.get('if_version') is None]
    plan = dict(sources=[str(f.relative_to(ROOT)) for f in files], batches=[], summary=summ)
    save_batches(d, plan, chunk(pinned))
    json.dump(unpinned, open(d / 'unpinned.json', 'w'), ensure_ascii=False)
    json.dump(plan, open(d / 'plan.json', 'w'), indent=1, ensure_ascii=False)
    print(f"{len(merged)} writes from {len(files)} file(s): {len(plan['batches'])} batches ({len(pinned)} pinned), {len(unpinned)} unpinned -> {d}")
    for f, s in summ.items():
        for sp, v in ((s or {}).get('sports') or {}).items(): print(f'  {f} {sp}: {v}')
        for sp, L in ((s or {}).get('tier_switches') or {}).items():
            for x in L: print(f"  {f} {sp} switch: {x['rule']} {x['tier']} -> {x['to']} ({x.get('record')})")
    if unpinned: print('  unpinned docs (read their versions, then pin):', ', '.join(key(e) for e in unpinned[:20]), '...' if len(unpinned) > 20 else '')


def cmd_pin(a):
    d = Path(a.dir); V = json.load(open(a.versions)); plan = json.load(open(d / 'plan.json')); n = 0
    for b in plan['batches']:
        if b['done']: continue
        B = json.load(open(d / b['file']))
        for e in B:
            if key(e) in V: e['if_version'] = int(V[key(e)]); n += 1
        json.dump(B, open(d / b['file'], 'w'), ensure_ascii=False)
    U = json.load(open(d / 'unpinned.json')); now = []
    for e in U:
        if key(e) in V: e['if_version'] = int(V[key(e)]); now.append(e); n += 1
    json.dump([e for e in U if e not in now], open(d / 'unpinned.json', 'w'), ensure_ascii=False)
    save_batches(d, plan, chunk(now))
    json.dump(plan, open(d / 'plan.json', 'w'), indent=1, ensure_ascii=False)
    print(f'pinned {n} entries; {len(now)} moved from unpinned into new batches; batches now {len(plan["batches"])}')


def cmd_need(a):
    """Which hub reads give the missing versions: per collection, the dates (doc id prefixes) of the unpinned docs."""
    U = json.load(open(Path(a.dir) / 'unpinned.json')); by = {}
    for e in U: by.setdefault(e['collection'], {}).setdefault(e['doc_id'][:10], []).append(e['doc_id'])
    for c, D in sorted(by.items()):
        print(c, {k: len(v) for k, v in sorted(D.items())})
    json.dump({c: sorted(i for v in D.values() for i in v) for c, D in by.items()}, open(Path(a.dir) / 'need_versions.json', 'w'), indent=1)
    print('ids ->', Path(a.dir) / 'need_versions.json')


def cmd_done(a):
    d = Path(a.dir); plan = json.load(open(d / 'plan.json'))
    names = a.batches or [b['file'] for b in plan['batches'] if not b['done']]
    given = {}
    if a.results:
        R = json.load(open(a.results)); R = R.get('results', R) if isinstance(R, dict) else R
        given = {key(r): r for r in R}
    ups, res = [], []
    for b in plan['batches']:
        if b['file'] not in names or b['done']: continue
        for e in json.load(open(d / b['file'])):
            r = given.get(key(e))
            if a.results and r is None: continue   # not in the tool result: not applied
            ok = True if r is None else bool(r.get('ok', r.get('success', True))) and not r.get('error')
            v = (r or {}).get('version') or ((e.get('if_version') or 0) + 1 if e.get('if_version') else None)
            res.append(dict(collection=e['collection'], doc_id=e['doc_id'], ok=ok, version=v))
            ups.append(dict(collection=e['collection'], doc_id=e['doc_id'], op=e['op'], data=dict(e['data'], pending_hub={'__delete__': True})))
        b['done'] = True
    json.dump(ups, open(d / 'ledger_updates.json', 'w'), ensure_ascii=False); json.dump(res, open(d / 'results.json', 'w'))
    r = subprocess.run([sys.executable, str(ROOT / 'season' / 'ledger.py'), 'apply-result', str(d / 'ledger_updates.json'), str(d / 'results.json')],
                       capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr.strip())
    json.dump(plan, open(d / 'plan.json', 'w'), indent=1, ensure_ascii=False)
    left = [b['file'] for b in plan['batches'] if not b['done']]; un = json.load(open(d / 'unpinned.json'))
    if not left and not un:
        for s in plan['sources']:
            m = ROOT / (s[:-5] + '.applied'); m.write_text(json.dumps(dict(applied=True, writes=sum(b['n'] for b in plan['batches']))) + '\n')
        print('all batches done; .applied markers written for', ', '.join(plan['sources']))
    else: print('still to apply:', left, f'and {len(un)} unpinned' if un else '')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('prepare'); p.add_argument('--file'); p.add_argument('--out', default='/tmp/apply_updates'); p.set_defaults(fn=cmd_prepare)
    p = sp.add_parser('pin'); p.add_argument('dir'); p.add_argument('versions'); p.set_defaults(fn=cmd_pin)
    p = sp.add_parser('need'); p.add_argument('dir'); p.set_defaults(fn=cmd_need)
    p = sp.add_parser('done'); p.add_argument('dir'); p.add_argument('batches', nargs='*'); p.add_argument('--results'); p.set_defaults(fn=cmd_done)
    a = ap.parse_args(); a.fn(a)


if __name__ == '__main__':
    main()
