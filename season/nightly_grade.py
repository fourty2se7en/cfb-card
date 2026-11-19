"""Nightly grade in GitHub (Season Cards, Nov 19 2026). season/loop.py runs this once a day right after the 02:00 Phoenix
ESPN finals pull; a chat can run it too.

    python3 season/nightly_grade.py [--day YYYY-MM-DD] [--hub /tmp/hub] [--dry-run]

Steps
  1. python3 season/ledger.py unpack <hub> --with-meta     (fresh copy of the repo ledger, {id, version, data} per doc)
  2. season/grade.py for every sport (sports/<s>/picks, NFL also picks_bg) with --backfill-close: grades every pending pick
     that has an ESPN final, adds the Odds API close (close_line, close_price, clv, close_result), and adds the close to
     graded picks that still have none.
  3. The graded fields go into the unpacked copy, then season/rebuild_tiers.py <hub> <hub>/_tiers (TODAY = --day) rebuilds
     every sport's meta rules from it.
  4. season/ledger/updates/<day>.json gets:
       writes   [{collection, doc_id, op: "update", if_version, data, kind}]  one per changed pick (kind grade or close)
                and per changed meta doc (kind meta, data {rules}). if_version is the ledger version (null when unknown:
                the hub write then fails, names the current version, and the chat retries with it).
       summary  per sport: picks graded tonight W-L-P and units (all, card only, and at the close for A64), close fields
                added, tier switches (rule, tier, to, record).
  5. The same changes go into the packed ledger with pending_hub: true and the version left as it was, until a chat applies
     the file to the hub (season/apply_updates.md) and runs ledger.py apply-result.
Safe to run twice: picks graded the first time are no longer pending in the ledger, so a rerun adds nothing; a rerun that does
find new finals merges its writes into the same day's file. --dry-run writes nothing to the ledger (the updates file goes to
<hub>/updates_<day>.json).
"""
import argparse, datetime as dt, json, os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'season'))
import ledger as LG  # noqa: E402

PHX = dt.timezone(dt.timedelta(hours=-7))
SPORTS = ['nba', 'nhl', 'nfl', 'ncaam', 'ncaaw', 'fbs']
CLOSE_KEYS = ('close_line', 'close_price', 'clv', 'clv_unit', 'close_result', 'close_source', 'close_at')


def sh(cmd, env=None):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=dict(os.environ, **(env or {})))
    out = (r.stdout or '') + (r.stderr or '')
    print('$', ' '.join(map(str, cmd)), '\n' + out.strip()[-1200:], flush=True)
    return r.returncode, out


def units(res, price):
    try: p = float(str(price).replace('+', ''))
    except (TypeError, ValueError): p = None
    if res == 'win': return 1.0 if p is None else (p / 100 if p > 0 else 100 / -p)
    return -1.0 if res == 'loss' else 0.0


def rec(rows):
    w = sum(r[0] == 'win' for r in rows); l = sum(r[0] == 'loss' for r in rows); p = sum(r[0] == 'push' for r in rows)
    return dict(w=w, l=l, p=p, u=round(sum(units(*r) for r in rows), 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--day', default=dt.datetime.now(PHX).strftime('%Y-%m-%d'))
    ap.add_argument('--hub', default='/tmp/hub')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    hub = Path(a.hub); day = a.day
    if hub.exists(): shutil.rmtree(hub)
    rc, _ = sh([sys.executable, 'season/ledger.py', 'unpack', str(hub), '--with-meta'])
    if rc: sys.exit('unpack failed')

    writes = {}   # (collection, doc_id) -> write
    def ver(coll, i):
        d = LG.read_coll(coll).get(i) if coll not in VCACHE else VCACHE[coll].get(i)
        return d.get('_v') if d else None
    VCACHE = {}

    # 2. grade every sport
    for s in SPORTS:
        for coll in [f'sports/{s}/picks'] + (['sports/nfl/picks_bg'] if s == 'nfl' else []):
            src = hub / coll
            if not src.is_dir(): continue
            out = hub / f'_grade_{coll.replace("/", "_")}.json'
            rc, _ = sh([sys.executable, 'season/grade.py', s, str(src), str(out), '--backfill-close'])
            if rc or not out.exists(): print('grade failed for', coll); continue
            VCACHE.setdefault(coll, LG.read_coll(coll))
            for u in json.load(open(out))['updates']:
                kind = 'close' if u.get('backfill') else 'grade'
                data = {k: v for k, v in u.items() if k in CLOSE_KEYS or (kind == 'grade' and k in ('result', 'final'))}
                if not data: continue
                f = src / f"{u['id']}.json"   # the unpacked copy gets the graded fields for the tier rebuild
                x = json.load(open(f)); x['data'].update(data); json.dump(x, open(f, 'w'))
                writes[(coll, u['id'])] = dict(collection=coll, doc_id=u['id'], op='update', if_version=ver(coll, u['id']), data=data, kind=kind)

    # 3. tier rebuild on the graded copy
    tiers = hub / '_tiers'
    rc, _ = sh([sys.executable, 'season/rebuild_tiers.py', str(hub), str(tiers)], env=dict(TODAY=day))
    switches = {}
    metas = LG.read_coll('meta')
    if rc == 0:
        for s in SPORTS:
            f = tiers / f'm_{s}.json'
            old = metas.get(s)
            if not f.exists() or not old: continue
            new_rules = json.load(open(f))['rules']
            if json.dumps(new_rules, sort_keys=True) == json.dumps(old.get('rules'), sort_keys=True): continue
            writes[('meta', s)] = dict(collection='meta', doc_id=s, op='update', if_version=old.get('_v'), data=dict(rules=new_rules), kind='meta')
            ob = {r.get('key') or r.get('label'): r for r in old.get('rules') or []}
            for r in new_rules:
                o = ob.get(r.get('key') or r.get('label')) or {}
                for t, v in (r.get('tiers') or {}).items():
                    was = bool(((o.get('tiers') or {}).get(t) or {}).get('on'))
                    if bool(v.get('on')) != was:
                        rr = v.get('real') or {}
                        switches.setdefault(s, []).append(dict(rule=r.get('label') or r.get('key'), key=r.get('key'), tier=t, to='on' if v.get('on') else 'off',
                                                               record=f"{rr.get('w', 0)}-{rr.get('l', 0)} {rr.get('u', 0):+.2f}u" if rr else None))
    else:
        print('rebuild_tiers failed: meta left as it is')

    # 4. merge with an earlier run of the same day
    upd_dir = ROOT / 'season' / 'ledger' / 'updates'
    target = (hub / f'updates_{day}.json') if a.dry_run else (upd_dir / f'{day}.json')
    prev = json.load(open(upd_dir / f'{day}.json')) if (upd_dir / f'{day}.json').exists() else {}
    merged = {(w['collection'], w['doc_id']): w for w in prev.get('writes', [])}
    for k, w in writes.items():
        if k in merged:
            merged[k] = dict(merged[k], data=dict(merged[k]['data'], **w['data']), kind=merged[k]['kind'] if merged[k]['kind'] == 'grade' else w['kind'])
        else: merged[k] = w
    sw = prev.get('summary', {}).get('tier_switches', {})
    for s, L in switches.items():
        have = {(x['key'], x['tier']) for x in sw.get(s, [])}
        sw[s] = [x for x in sw.get(s, []) if (x['key'], x['tier']) not in {(y['key'], y['tier']) for y in L}] + L

    # summary from the merged writes and the pick docs
    summ = dict(day=day, sports={}, tier_switches=sw)
    for s in SPORTS:
        g = []; card = []; atc = []; nclose = 0
        for (coll, i), w in merged.items():
            if not coll.startswith(f'sports/{s}/'): continue
            if 'close_line' in w['data'] or 'close_price' in w['data']: nclose += 1
            if w['kind'] != 'grade': continue
            d = (VCACHE.get(coll) or LG.read_coll(coll)).get(i, {})
            d = dict(d, **w['data'])
            g.append((d.get('result'), d.get('price')))
            if not d.get('shadow') and coll.endswith('/picks'): card.append((d.get('result'), d.get('price')))
            atc.append((d.get('close_result') or d.get('result'), d.get('close_price') if d.get('close_price') is not None else d.get('price')))
        if g or nclose or s in sw:
            summ['sports'][s] = dict(graded=rec(g), card=rec(card), at_close=rec(atc), close_added=nclose, tier_switches=len(sw.get(s, [])))
    doc = dict(day=day, generated_at=dt.datetime.now(PHX).strftime('%Y-%m-%d %H:%M Phoenix'), source='season/nightly_grade.py',
               note='Apply with season/apply_updates.py (see season/apply_updates.md). Ledger docs carry pending_hub: true until then.',
               summary=summ, writes=sorted(merged.values(), key=lambda w: (w['collection'], w['doc_id'])))
    target.parent.mkdir(parents=True, exist_ok=True)
    if not writes:
        print(f'nothing new to grade or update for {day}; updates file left as it is'); return
    json.dump(doc, open(target, 'w'), indent=1, ensure_ascii=False)
    print(f'{len(doc["writes"])} writes ({len(writes)} new this run) -> {target}')
    for s, v in summ['sports'].items(): print(' ', s, v)

    # 5. packed ledger: same fields, pending_hub true, version unchanged
    if a.dry_run or not writes: return
    by = {}
    for (coll, i), w in writes.items(): by.setdefault(coll, []).append(w)
    for coll, L in by.items():
        docs = LG.read_coll(coll)
        for w in L:
            d = docs.get(w['doc_id'])
            if d is None: continue
            d.update(w['data']); d['pending_hub'] = True
        LG.write_coll(coll, docs)
    m = LG.load_manifest(); m['pending_hub_file'] = f'season/ledger/updates/{day}.json'; LG.save_manifest(m)
    print('ledger updated (pending_hub)')


if __name__ == '__main__':
    main()
