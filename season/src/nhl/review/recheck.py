"""Daily re-check (start of every NHL card run). Approved by Trina Oct 30, 2026.
1. The card run appends every game from the day after the last date in ng.txt through yesterday to
   ng.txt, sb.txt, ah.txt, sh2.txt and dk.txt (browser steps: ../src/browser_pulls.js, "Daily re-check pulls"),
   then runs:  python3 build_data.py && python3 recheck.py
2. This script reruns every test (tests.py, a to f) on all games played: season to date, each month, last 14 days;
   measures each rule's base and strict versions (rules.apply_rules on closing lines); runs the pick-time check (g)
   at DraftKings opening prices and at the card's own texas222 prices (ledger docs in ledger/picks/*.json);
   applies the switch logic (rules.decide) and writes ../rules_state.json, recheck.json (for the card's Results tab)
   and recheck_report.md (changes and warnings for the daily reply)."""
import json, sys, pathlib, glob, datetime
R = pathlib.Path(__file__).parent; sys.path.insert(0, str(R.parent)); sys.path.insert(0, str(R))
import tests as T
import rules
from signals import RULESET
from build_data import ok

rows, MONTHS, AS_OF, L14 = T.rows, T.MONTHS, T.AS_OF, T.L14
APPROVED = RULESET['approved']
CUR_MONTH = rules.month_of(AS_OF)

def grade(x, pk, price=None, line=None):
    g = x['g']; ag, hg = g['ag'], g['hg']; p = price if price is not None else pk['price']; ln = line if line is not None else pk['line']
    if pk['market'] == 'Moneyline':
        r = 'W' if ((ag > hg) if pk['side'] == 'A' else (hg > ag)) else 'L'
    elif pk['market'] == 'Puck line':
        m = (ag-hg) if pk['side'] == 'A' else (hg-ag); r = 'W' if m + ln > 0 else 'L'
    else:
        t = ag + hg; r = 'P' if t == ln else ('W' if (t > ln) == (pk['side'] == 'O') else 'L')
    return (g['date'], r, p if ok(p) else -110)

def block(bets):
    o = dict(season=rules.agg(bets))
    for m in MONTHS: o[m] = rules.agg([b for b in bets if rules.month_of(b[0]) == m])
    o['L14'] = rules.agg([b for b in bets if b[0] >= L14])
    o['since'] = rules.agg([b for b in bets if b[0] >= APPROVED])
    return o

# ---- rule records, both versions
REC, PICKROWS = {}, {}
for rid in rules.ORDER:
    REC[rid] = {}
    for v in ('base', 'strict'):
        bets, pr = [], []
        for x in rows:
            for pk in rules.apply_rules(x['c'], x['r'], version=v):
                if pk['rule'] == rid:
                    bets.append(grade(x, pk)); pr.append((x, pk))
        REC[rid][v] = block(bets); PICKROWS[(rid, v)] = pr

# ---- test g: pick-time prices for each rule's active version
def dk_open_bet(x, pk):
    o = (x['g'].get('dk') or {}).get('open')
    if not o: return None
    if pk['market'] == 'Moneyline':
        p = o['ml'][0 if pk['side'] == 'A' else 1]
        return grade(x, pk, price=p) if ok(p) and rules.within_limits(p) else None
    if pk['market'] == 'Puck line':
        if o['pl_sp_a'] is None: return None
        sp = o['pl_sp_a'] if pk['side'] == 'A' else -o['pl_sp_a']; p = o['pl'][0 if pk['side'] == 'A' else 1]
        return grade(x, pk, price=p, line=sp) if ok(p) else None
    if o['tot'] is None: return None
    return grade(x, pk, price=o['ou'][0], line=o['tot'])
LED = {}
for f in glob.glob(str(R/'ledger'/'picks'/'*.json')):
    try: d = json.load(open(f))
    except Exception: continue
    if d.get('result') not in ('win', 'loss', 'push') or d.get('market') == 'Prop': continue
    LED.setdefault((d['date'], d['away'], d['home'], d['market']), []).append(d)
import teams
def card_bet(x, pk):
    g = x['g']; L = LED.get((g['date'], g['a'], g['h'], pk['market']), [])
    for d in L:
        if pk['market'] == 'Total':
            if d['pick'].lower().startswith('over') and d.get('line') == pk['line']: return grade(x, pk, price=d['price'])
            continue
        side = 'A' if teams.TEAMS[g['a']][1] in d['pick'] else 'H'
        if side == pk['side']: return grade(x, pk, price=d['price'])
    return None
G_CHECK = {}
for rid in rules.ORDER:
    v = rules.RULES[rid]['version']; pr = PICKROWS[(rid, v)]
    op = [b for b in (dk_open_bet(x, pk) for x, pk in pr) if b]
    cb, cs = [], []
    for x, pk in pr:
        b = card_bet(x, pk)
        if b: cb.append(b); cs.append(grade(x, pk))
    G_CHECK[rid] = dict(close=rules.agg([grade(x, pk) for x, pk in pr]), dk_open=rules.agg(op), card=rules.agg(cb), card_close=rules.agg(cs))

# ---- fatigue trackers (tracking only, Nov 3)
import fatigue
TRACK = fatigue.run(rows, block)

# ---- data checks
CK = dict(games=len(T.GAMES), scored=len(rows), dk_join=sum(1 for g in T.GAMES if g.get('dk')),
          dk_final_match=sum(1 for g in T.GAMES if g.get('dk') and (g['dk']['ag'], g['dk']['hg']) == (g['ag'], g['hg'])),
          open_agree=sum(1 for g in T.GAMES if __import__('score').open_check(g) is not None))
ledger_rows = ledger_match = 0
GI = {(g['date'], g['a'], g['h']): g for g in T.GAMES}
import re
for k, L in LED.items():
    g = GI.get(k[:3])
    for d in L:
        if not g or not d.get('final'): continue
        n = re.findall(r'(\d+)', d['final'])
        if len(n) >= 2:
            ledger_rows += 1; ledger_match += (int(n[0]), int(n[1])) == (g['ag'], g['hg'])
CK.update(ledger_rows=ledger_rows, ledger_finals_match=ledger_match)

# ---- switch logic
prev = rules.STATE_DATA if isinstance(rules.STATE_DATA, dict) else {}
CHANGES, WARN, STATE = [], [], {}
for rid in rules.ORDER:
    v = rules.RULES[rid]['version']; ov = 'strict' if v == 'base' else 'base'
    a, o = REC[rid][v], REC[rid][ov]
    st, nv, ch, wn = rules.decide(rid, a['season'], a['since'], a.get(CUR_MONTH, rules.agg([])), o['since'], o.get(CUR_MONTH, rules.agg([])))
    CHANGES += ch; WARN += wn
    rec = REC[rid][nv]['season']
    STATE[rid] = dict(status=st, version=nv, label=rules.RULES[rid]['versions'][nv]['label'], market=rules.RULES[rid]['market'],
                      record=[rec['w'], rec['l'], rec['p'], rec['u']])
for sec, lst in T.RES.items():
    pass
hist = (prev.get('history') or [])[-60:]
if CHANGES: hist.append(dict(date=AS_OF, changes=CHANGES))
run_date = datetime.date.today().isoformat()
json.dump(dict(as_of=AS_OF, run=run_date, approved=APPROVED, rules=STATE, changes=CHANGES, warnings=WARN, history=hist),
          open(R.parent/'rules_state.json', 'w'), indent=1)
json.dump(dict(as_of=AS_OF, months=MONTHS, l14_from=L14, approved=APPROVED, checks=CK, records=REC, g=G_CHECK, state=STATE,
               changes=CHANGES, warnings=WARN, trackers=TRACK, tests={k: [[n, o] for n, o in v] for k, v in T.RES.items()}),
          open(R/'recheck.json', 'w'))

def c(a): return T.cell(a)
lines = [f"# NHL daily re-check through {AS_OF}", '',
         f"Games {CK['games']} (scored {CK['scored']}); DraftKings joined {CK['dk_join']}, finals match {CK['dk_final_match']}; "
         f"opening lines agreed {CK['open_agree']}; card ledger finals match {CK['ledger_finals_match']}/{CK['ledger_rows']}.", '',
         '| Rule | Status | Version | Season | ' + ' | '.join(MONTHS) + ' | Last 14 | Since approval | Other version since approval |',
         '|' + ' --- |'*(7+len(MONTHS))]
for rid in rules.ORDER:
    s = STATE[rid]; a = REC[rid][s['version']]; o = REC[rid]['strict' if s['version'] == 'base' else 'base']
    lines.append(f"| {rid} | {s['status']} | {s['version']} | {c(a['season'])} | " + ' | '.join(c(a[m]) for m in MONTHS) + f" | {c(a['L14'])} | {c(a['since'])} | {c(o['since'])} |")
lines += ['', '**Changes:** ' + ('; '.join(CHANGES) if CHANGES else 'none'), '', '**Warnings:** ' + ('; '.join(WARN) if WARN else 'none'), '',
          '**Fatigue trackers (tracking only):** ' + '; '.join(f"{k} {c(v['season'])}" for k, v in TRACK.items()), '', '**Pick-time check (g):** ' + '; '.join(f"{rid} close {c(G_CHECK[rid]['close'])}, DraftKings open {c(G_CHECK[rid]['dk_open'])}, card texas222 {c(G_CHECK[rid]['card'])} (same picks at close {c(G_CHECK[rid]['card_close'])})" for rid in rules.ORDER)]
(R/'recheck_report.md').write_text('\n'.join(lines) + '\n')
print('\n'.join(lines))
