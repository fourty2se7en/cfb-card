#!/usr/bin/env python3
"""Repo ledger: a full copy of the Season Cards hub database, kept in the repo.

Layout: season/ledger/<collection path with / replaced by __>.jsonl.gz
        one JSON object per line {"_id": doc id, "_v": hub version or null, ...doc fields}, sorted by _id
        season/ledger/manifest.json  {collections: {collection: count}, packed_at, updated_at, source}

Commands (standard library only):
  pack <seed_dir> [--versions versions.json]
        Read an ArtifactData out_dir tree (<seed_dir>/<collection path>/<doc_id>.json) and rewrite the whole ledger.
        Versions are not in the saved files; --versions maps collection -> rules (see VERSION RULES below).
  unpack <out_dir> [--collections a,b] [--with-meta]
        Rebuild the ArtifactData out_dir tree (<out_dir>/<collection>/<doc_id>.json, plain fields), so
        season/grade.py and season/rebuild_tiers.py read it unchanged. --with-meta writes
        {"id","version","data"} wrappers instead (grade.py then also sees the version).
  add <collection> <file ...> [--version N]
        Upsert docs. Each file is one doc: <doc_id>.json with the plain fields (id from the filename), or a wrapper
        {"id"/"doc_id", "version", "data": {...}}; or a JSON list of wrappers / ledger rows ({"_id", "_v", fields}).
        _v: the version given (hub write result), else old _v + 1, else null if the old _v was unknown.
  apply-result <updates.json> <results.json>
        After a chat applies an updates file to the hub: for each doc that succeeded, upsert its new fields and
        set _v to the version the result reports (else _v + 1).
        updates.json: list of {collection, doc_id, op: set|update|delete, data}
        results.json: list of {collection, doc_id, ok: true/false, version}  (or {"results": [...]})
  count
        Print collection counts from the ledger files next to the manifest counts.

VERSION RULES (pack --versions): {collection: {"unknown": true} | {"default": n, "prefix": {p: n},
  "prefix_nonprop": {p: n}, "suffix": {s: n}, "overrides": {id: n}, "unknown_ids_file": path}}
  Precedence: overrides > suffix > prefix (longest) > default. Missing collection or unknown -> _v null.
  A null or stale _v is safe: a pinned hub write fails, names the current version, and the run retries with it.
"""
import argparse, datetime, gzip, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, 'ledger')
MANIFEST = os.path.join(LEDGER, 'manifest.json')


def now_phx():
    # Phoenix is UTC-7 all year (no DST)
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=7)).strftime('%Y-%m-%d %H:%M Phoenix')


def fname(coll):
    return os.path.join(LEDGER, coll.replace('/', '__') + '.jsonl.gz')


def coll_of(fn):
    return os.path.basename(fn)[:-len('.jsonl.gz')].replace('__', '/')


def read_coll(coll):
    fn = fname(coll)
    docs = {}
    if os.path.exists(fn):
        with gzip.open(fn, 'rt', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    docs[d['_id']] = d
    return docs


def write_coll(coll, docs):
    os.makedirs(LEDGER, exist_ok=True)
    fn = fname(coll)
    tmp = fn + '.tmp'
    # mtime=0 keeps the gzip bytes stable when content is unchanged (smaller git diffs)
    with open(tmp, 'wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as gz:
            for i in sorted(docs):
                gz.write((json.dumps(docs[i], ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8'))
    os.replace(tmp, fn)


def load_manifest():
    if os.path.exists(MANIFEST):
        return json.load(open(MANIFEST))
    return {'collections': {}, 'source': 'hub'}


def save_manifest(m):
    m['updated_at'] = now_phx()
    m['collections'] = dict(sorted(m['collections'].items()))
    json.dump(m, open(MANIFEST, 'w'), indent=1)
    open(MANIFEST, 'a').write('\n')


def all_colls():
    if not os.path.isdir(LEDGER):
        return []
    return sorted(coll_of(f) for f in os.listdir(LEDGER) if f.endswith('.jsonl.gz'))


def version_for(rule, doc_id, unknown_ids):
    if not rule or rule.get('unknown') or doc_id in unknown_ids:
        return None
    if doc_id in rule.get('overrides', {}):
        return rule['overrides'][doc_id]
    for s, n in rule.get('suffix', {}).items():
        if doc_id.endswith(s):
            return n
    if '_prop_' not in doc_id:
        best = None
        for p, n in rule.get('prefix_nonprop', {}).items():
            if doc_id.startswith(p) and (best is None or len(p) > len(best[0])):
                best = (p, n)
        if best:
            return best[1]
    best = None
    for p, n in rule.get('prefix', {}).items():
        if doc_id.startswith(p) and (best is None or len(p) > len(best[0])):
            best = (p, n)
    if best:
        return best[1]
    return rule.get('default')


def split_doc(x):
    """Return (id, version, fields) from a plain doc or a wrapper."""
    if isinstance(x, dict) and ('data' in x and isinstance(x['data'], dict)) and ('id' in x or 'doc_id' in x):
        return x.get('id') or x.get('doc_id'), x.get('version', x.get('_v')), x['data']
    # plain doc: fields kept as they are (docs may have their own id/doc_id/version fields); ledger keys _id/_v only
    return x.get('_id'), x.get('_v'), {k: val for k, val in x.items() if k not in ('_id', '_v')}


def cmd_pack(a):
    seed = os.path.abspath(a.seed_dir)
    rules = json.load(open(a.versions)) if a.versions else {}
    m = {'collections': {}, 'packed_at': now_phx(), 'source': 'hub'}
    unk_total = 0
    # keep collections that are no longer in the seed out of the ledger: pack is a full rewrite
    for f in os.listdir(LEDGER) if os.path.isdir(LEDGER) else []:
        if f.endswith('.jsonl.gz'):
            os.remove(os.path.join(LEDGER, f))
    for root, dirs, files in os.walk(seed):
        js = [f for f in files if f.endswith('.json')]
        if not js:
            continue
        coll = os.path.relpath(root, seed).replace(os.sep, '/')
        rule = rules.get(coll, {})
        unknown_ids = set()
        if rule.get('unknown_ids_file'):
            p = rule['unknown_ids_file']
            p = p if os.path.isabs(p) else os.path.join(os.path.dirname(os.path.abspath(a.versions)), p)
            unknown_ids = set(l.strip() for l in open(p) if l.strip())
        docs = {}
        for f in js:
            i = f[:-5]
            x = json.load(open(os.path.join(root, f)))
            fields = x if isinstance(x, dict) else {'_value': x}   # ArtifactData out_dir files are the plain doc fields
            v = version_for(rule, i, unknown_ids)
            if v is None:
                unk_total += 1
            docs[i] = dict(fields, _id=i, _v=v)
        write_coll(coll, docs)
        m['collections'][coll] = len(docs)
    m['unknown_versions'] = unk_total
    save_manifest(m)
    print(f"packed {sum(m['collections'].values())} docs in {len(m['collections'])} collections; {unk_total} with _v null")


def cmd_unpack(a):
    out = os.path.abspath(a.out_dir)
    colls = a.collections.split(',') if a.collections else all_colls()
    n = 0
    for c in colls:
        d = os.path.join(out, *c.split('/'))
        os.makedirs(d, exist_ok=True)
        for i, doc in read_coll(c).items():
            fields = {k: v for k, v in doc.items() if k not in ('_id', '_v')}
            obj = {'id': i, 'version': doc.get('_v'), 'data': fields} if a.with_meta else fields
            with open(os.path.join(d, i + '.json'), 'w', encoding='utf-8') as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
            n += 1
    print(f'unpacked {n} docs from {len(colls)} collections into {out}')


def upsert(coll, items, force_v=None, merge=False):
    docs = read_coll(coll)
    n = 0
    for i, v, fields in items:
        if not i:
            raise SystemExit(f'doc without id in {coll}')
        old = docs.get(i)
        if force_v is not None:
            nv = force_v
        elif v is not None:
            nv = v
        elif old is None:
            nv = 1
        else:
            nv = old['_v'] + 1 if isinstance(old.get('_v'), int) else None
        base = {k: val for k, val in old.items() if k not in ('_id', '_v')} if (merge and old) else {}
        base.update(fields)
        base = {k: val for k, val in base.items() if not (isinstance(val, dict) and val.get('__delete__'))}
        docs[i] = dict(base, _id=i, _v=nv)
        n += 1
    write_coll(coll, docs)
    m = load_manifest()
    m['collections'][coll] = len(docs)
    save_manifest(m)
    return n


def cmd_add(a):
    items = []
    for p in a.files:
        x = json.load(open(p))
        if isinstance(x, list):
            items += [split_doc(e) for e in x]
        else:
            i, v, f = split_doc(x)
            items.append((i or os.path.basename(p)[:-5], v, f))
    n = upsert(a.collection, items, force_v=a.version, merge=a.merge)
    print(f'added/updated {n} docs in {a.collection}')


def cmd_apply_result(a):
    ups = json.load(open(a.updates))
    res = json.load(open(a.results))
    res = res.get('results', res) if isinstance(res, dict) else res
    ok = {}
    for r in res:
        if r.get('ok', r.get('success', True)) and not r.get('error'):
            ok[(r['collection'], r['doc_id'])] = r.get('version')
    by_coll, dels, skipped = {}, {}, 0
    for u in ups:
        key = (u['collection'], u['doc_id'])
        if key not in ok:
            skipped += 1
            continue
        if u.get('op') == 'delete':
            dels.setdefault(u['collection'], []).append(u['doc_id'])
            continue
        by_coll.setdefault(u['collection'], []).append((u['doc_id'], ok[key], u.get('data', {}), u.get('op', 'update')))
    n = 0
    for c, rows in by_coll.items():
        for op in ('set', 'update'):
            sel = [(i, v, d) for i, v, d, o in rows if o == op]
            if sel:
                n += upsert(c, sel, merge=(op == 'update'))
    for c, ids in dels.items():
        docs = read_coll(c)
        for i in ids:
            docs.pop(i, None); n += 1
        write_coll(c, docs)
        m = load_manifest(); m['collections'][c] = len(docs); save_manifest(m)
    print(f'applied {n} succeeded writes; {skipped} not applied (failed or missing from results)')


def cmd_setv(a):
    """Record hub versions read with an ArtifactData query: versions.json is {"<collection>/<doc_id>": version}.
    Only _v changes; docs missing from the ledger are reported, not created."""
    vers = json.load(open(a.versions))
    by = {}
    for k, v in vers.items():
        c, i = k.rsplit('/', 1)
        by.setdefault(c, {})[i] = int(v)
    n = miss = 0
    for c, m in by.items():
        docs = read_coll(c)
        for i, v in m.items():
            if i not in docs: miss += 1; continue
            if docs[i].get('_v') != v: docs[i]['_v'] = v; n += 1
        write_coll(c, docs)
    print(f'set _v on {n} docs; {miss} not in the ledger')


def cmd_count(a):
    m = load_manifest()
    mc = m.get('collections', {})
    colls = sorted(set(all_colls()) | set(mc))
    tot = 0
    print(f"{'collection':32} {'ledger':>7} {'manifest':>8}")
    for c in colls:
        n = len(read_coll(c))
        tot += n
        flag = '' if n == mc.get(c) else '  <- differs'
        print(f'{c:32} {n:7} {mc.get(c, "-"):>8}{flag}')
    print(f"{'total':32} {tot:7} {sum(mc.values()):8}   packed_at {m.get('packed_at')}, updated_at {m.get('updated_at')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('pack'); p.add_argument('seed_dir'); p.add_argument('--versions'); p.set_defaults(fn=cmd_pack)
    p = sp.add_parser('unpack'); p.add_argument('out_dir'); p.add_argument('--collections'); p.add_argument('--with-meta', action='store_true'); p.set_defaults(fn=cmd_unpack)
    p = sp.add_parser('add'); p.add_argument('collection'); p.add_argument('files', nargs='+'); p.add_argument('--version', type=int)
    p.add_argument('--merge', action='store_true', help='merge fields into the existing doc (hub "update") instead of replacing it (hub "set")')
    p.set_defaults(fn=cmd_add)
    p = sp.add_parser('apply-result'); p.add_argument('updates'); p.add_argument('results'); p.set_defaults(fn=cmd_apply_result)
    p = sp.add_parser('count'); p.set_defaults(fn=cmd_count)
    p = sp.add_parser('setv', help='record hub versions {"<collection>/<doc_id>": version} (only _v changes)')
    p.add_argument('versions'); p.set_defaults(fn=cmd_setv)
    a = ap.parse_args()
    a.fn(a)


if __name__ == '__main__':
    main()
