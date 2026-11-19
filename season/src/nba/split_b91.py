"""B91 (Nov 14): split two-version NBA rules into separate rules. Old docs keep their ids and rule; the loose rule's meta keys include the
legacy key. Docs that also met the stricter trigger get a twin doc (<old id>_<STRICT KEY>) with rule = the strict key."""
import json, glob, re, os, sys, copy
DL = sys.argv[1]; OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True)
STRICT = {'FAV_ML': 'FAV_ML_3', 'DOG_ML': 'DOG_ML_MOVE', 'SPREAD_MOVE': 'SPREAD_MOVE_1', 'UNDER_DROP': 'UNDER_DROP_75'}
LOOSE = {'FAV_ML': 'FAV_ML_2', 'DOG_ML': 'DOG_ML_1', 'SPREAD_MOVE': 'SPREAD_MOVE_05', 'UNDER_DROP': 'UNDER_DROP_ANY'}
def num(s): return [float(x) for x in re.findall(r'[-+]?\d+(?:\.\d+)?', s)]
def trig_pick(d):
    r = d.get('rule'); R = d.get('reasons') or []; A = d.get('against') or []
    txt = lambda lab: ' '.join(str(x.get('detail', '')) for x in R if str(x.get('label', '')).startswith(lab))
    if r == 'SPREAD_MOVE':
        t = txt('Reverse line movement') or txt('Line move')
        m = re.search(r'opened \w+ ([-+]?\d+(?:\.\d+)?), now ([-+]?\d+(?:\.\d+)?)', t)
        if m: return abs(float(m.group(1)) - float(m.group(2))) >= 1, f"spread moved {abs(float(m.group(1)) - float(m.group(2))):g}"
        return None, 'move size not in the doc'
    if r == 'UNDER_DROP':
        if d.get('rule_variant') == 'strict': return True, 'logged under the 75%+ over tickets version'
        t = txt('Fade the public') + ' ' + txt('Total moved down')
        m = re.search(r'(\d+)% (?:of )?(?:over )?tickets', t) or re.search(r'(\d+)% over tickets', t)
        if m: return int(m.group(1)) >= 75, f"{m.group(1)}% of tickets on the over"
        return None, 'ticket share not in the doc'
    if r == 'DOG_ML':
        t = txt('Reverse line movement')
        return bool(t), ('line moved toward the underdog against the tickets' if t else 'no line move toward the underdog')
    if r == 'FAV_ML':
        ok = lambda x: x.get('market') in (None, 'Moneyline', 'Game context') and isinstance(x.get('points'), (int, float))
        lead = sum(x['points'] for x in R if ok(x)) - sum(x['points'] for x in A if ok(x))
        return lead >= 3, f'moneyline signal lead {lead:g}'
    return None, ''
def trig_bt(b):
    i = b.get('inputs') or {}; r = b.get('rule_key')
    if r == 'SPREAD_MOVE':
        dk = i.get('dk_spread_away') or [None, None]; ao, c = i.get('an_open_spread_away'), i.get('close_spread_away')
        if None in (dk[0], dk[1], ao, c): return None
        return min(abs(dk[1] - dk[0]), abs(c - ao)) >= 1
    if r == 'UNDER_DROP': return (i.get('over_tickets') or 0) >= 75
    if r == 'FAV_ML': return (i.get('ml_lead') or 0) >= 3
    if r == 'DOG_ML':
        dk = i.get('dk_spread_away') or [None, None]; ao, c = i.get('an_open_spread_away'), i.get('close_spread_away')
        if None in (dk[0], dk[1], ao, c): return None
        dog_away = str(b.get('pick', '')).startswith(b.get('away', '~'))
        mv = (dk[1] - dk[0]) if True else 0; mv2 = c - ao
        tk = i.get('spread_tickets_away') or 50
        if dog_away: return mv < 0 and mv2 < 0 and tk < 50
        return mv > 0 and mv2 > 0 and tk > 50
    return None
SEEN = set(); W = []; rep = {k: [0, 0, 0] for k in STRICT}
for f in sorted(glob.glob(f'{DL}/sports/nba/picks/*.json')):
    i = os.path.basename(f)[:-5]; d = json.load(open(f)); d = d.get('data', d)
    r = d.get('rule')
    if r not in STRICT or d.get('market') == 'Prop': continue
    ok, why = trig_pick(d)
    if ok is None:
        g = re.match(r'(\d{4}-\d\d-\d\d_[A-Z]+-[A-Z]+)', i).group(1); bf = f'{DL}/sports/nba/backtest/{g}_{r}.json'
        if os.path.exists(bf):
            b = json.load(open(bf)); b = b.get('data', b); ok = trig_bt(b); why = 'from the saved game inputs (closing replay)'
    rep[r][0 if ok else (1 if ok is False else 2)] += 1
    if ok:
        t = copy.deepcopy(d); t['rule'] = STRICT[r]; t['rule_key'] = STRICT[r]; t['split_from'] = i; t['trigger'] = why
        t.pop('rule_variant', None); nid = f"{i}_{STRICT[r]}" if not i.endswith('_' + r) else i[:-len(r)] + STRICT[r]
        if nid in SEEN: nid = f"{i}_c_{STRICT[r]}"
        SEEN.add(nid); fn = f'{OUT}/p_{nid}.json'; json.dump(t, open(fn, 'w')); W.append(dict(op='set', collection='sports/nba/picks', doc_id=nid, file_path=fn))
print('picks strict yes/no/unknown', rep)
rb = {k: [0, 0, 0] for k in STRICT}
for f in (sorted(glob.glob(f'{DL}/sports/nba/backtest/*.json')) if os.environ.get('BT') else []):
    i = os.path.basename(f)[:-5]; b = json.load(open(f)); b = b.get('data', b); r = b.get('rule_key')
    if r not in STRICT: continue
    ok = trig_bt(b); rb[r][0 if ok else (1 if ok is False else 2)] += 1
    if ok:
        t = copy.deepcopy(b); t['rule_key'] = STRICT[r]; t['rule'] = STRICT[r]; t['split_from'] = i; t.pop('rule_variant', None)
        nid = i[:-len(r)] + STRICT[r]; fn = f'{OUT}/b_{nid}.json'; json.dump(t, open(fn, 'w'))
        W.append(dict(op='set', collection='sports/nba/backtest', doc_id=nid, file_path=fn))
print('backtest strict yes/no/unknown', rb, 'writes', len(W))
json.dump(W, open(f'{OUT}/writes.json', 'w'))
