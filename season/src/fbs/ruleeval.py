"""CFB rule evaluation, NBA-card style: season to date, a column per month, last 3 weeks (early warning), per division.
A version qualifies at min_picks+ graded picks with positive units and a win % above break-even (season to date).
Moneylines at the cleaned closing median, spreads and totals at -110.
python3 ruleeval.py fbs|fcs  -> ruleeval_<div>.md / .json   (analysis only; changes nothing on the cards)
"""
import json, sys, copy, datetime as dt
from pathlib import Path
import rules as RU, cfbdata

D = Path(__file__).parent
DIV = sys.argv[1] if len(sys.argv) > 1 else 'fbs'
SIG = json.load(open(D / 'signals.json'))
RULES = SIG['rules_' + DIV]
QUAL = dict(min_picks=SIG['recheck_policy']['qualify']['min_picks'])
ROWS = cfbdata.load(DIV, SIG)
CUR = [r for r in ROWS if r['y'] == 2026]
MONTHS = [m for m in ('Aug', 'Sep', 'Oct', 'Nov', 'Dec') if any(r['month'] == m for r in CUR)]
WEEKS = sorted({r['wk'] for r in CUR}); LAST3 = set(WEEKS[-3:])
PER = [('Season', lambda r: r['y'] == 2026)] + [(m, lambda r, m=m: r['y'] == 2026 and r['month'] == m) for m in MONTHS] + \
      [(f'Last 3 wks ({min(LAST3)}-{max(LAST3)})', lambda r: r['y'] == 2026 and r['wk'] in LAST3)]
if DIV == 'fcs': PER.append(('2022-25 (ref)', lambda r: r['y'] < 2026))


def run(fn, rows=None, at_open=False):
    out = {}
    for name, sel in PER:
        res = []
        for r in (rows or ROWS):
            if not sel(r): continue
            x = r
            if at_open:   # pick-time check: grade at the CFBD opener (the card's morning line is only logged from Oct 29)
                if r.get('open_h') is None and r.get('tot_open') is None: continue
                x = dict(r, spread_h=r['open_h'] if r.get('open_h') is not None else r['spread_h'], total=r['tot_open'] or r['total'])
            p = fn(x)
            if not p: continue
            if p['market'] == 'Moneyline' and x.get('ml_' + p['k']) is None: continue
            if p['market'] == 'Spread' and x.get('spread_h') is None: continue
            if p['market'] == 'Total' and x.get('total') is None: continue
            w, pr = RU.grade(x, p); res.append((r['wk'], w, pr))
        out[name] = RU.record(res)
    return out


def qualifies(o):
    s = o['Season']
    return s['n'] >= QUAL['min_picks'] and s['units'] > 0 and s['pct'] is not None and s['pct'] > s['be']


def fmt1(v): return f"{v['w']}-{v['l']} {v['pct']}% {v['units']:+.1f}u" if v['n'] else '·'


def only(Rset, name):
    Q = copy.deepcopy(Rset)
    for k in Q['side']: Q['side'][k]['on'] = (k == name)
    for k in Q['total']: Q['total'][k]['on'] = (k == name)
    return Q


def side_of(Q): return lambda r: RU.decide(r, r['sideS'], r['totS'], Q)[0]
def tot_of(Q): return lambda r: RU.decide(r, r['sideS'], r['totS'], Q)[1]


def variant(name, **chg):
    Q = copy.deepcopy(RULES)
    tgt = Q['total'][name] if name in Q['total'] else Q['side'][name]
    tgt.update(chg); tgt['on'] = True
    return only(Q, name), (tot_of if name in Q['total'] else side_of)


# ---------------- rule versions: the current version and its other version ----------------
POL = SIG['recheck_policy']
APPLY = '--apply' in sys.argv
def rule_obj(Q, name): return Q['total'][name] if name in Q['total'] else Q['side'][name]
NAMES = list(RULES['order']) + list(RULES['total'].keys())
LAST_MONTH = MONTHS[-1] if MONTHS else None
OUT = dict(div=DIV, run=dt.datetime.now().isoformat(timespec='minutes'), periods=[p for p, _ in PER], last_month=LAST_MONTH,
           games=len(CUR), weeks=[WEEKS[0], WEEKS[-1]] if WEEKS else [], rules={}, grid={}, picktime={}, changes=[], warnings=[])
PI = {}   # the card's own morning lines, logged by model.py (hist/pickinputs_<div>.jsonl)
_pf = D / 'hist' / f'pickinputs_{DIV}.jsonl'
if _pf.exists():
    for line in _pf.read_text().splitlines():
        if line.strip():
            z = json.loads(line); PI[int(z['id'])] = z
def run_pick(fn):
    """Grade at the card's logged morning line when there is one, else the CFBD opener (proxy)."""
    out = {}
    for name, sel in PER:
        res = []
        for r in ROWS:
            if not sel(r): continue
            z = PI.get(r.get('id'))
            if z and z.get('spread_h') is not None:
                x = dict(r, spread_h=z['spread_h'], total=z.get('total') or r['total'], ml_a=z.get('ml_a') or r['ml_a'], ml_h=z.get('ml_h') or r['ml_h'])
            elif r.get('open_h') is not None or r.get('tot_open'):
                x = dict(r, spread_h=r['open_h'] if r.get('open_h') is not None else r['spread_h'], total=r['tot_open'] or r['total'])
            else: continue
            p = fn(x)
            if not p: continue
            if p['market'] == 'Moneyline' and x.get('ml_' + p['k']) is None: continue
            w, pr = RU.grade(x, p); res.append((r['wk'], w, pr))
        out[name] = RU.record(res)
    return out
NEW = copy.deepcopy(RULES)
for name in NAMES:
    R_ = rule_obj(RULES, name)
    if R_.get('retired'): continue
    mk = tot_of if name in RULES['total'] else side_of
    Qc = only(RULES, name); rule_obj(Qc, name)['on'] = True
    cur = run(mk(Qc))
    vers = [dict(version=R_.get('version', 'current'), current=True, rec=cur, qualifies=qualifies(cur))]
    alt = R_.get('alt'); altrec = None
    if alt:
        Qa = only(RULES, name); ra = rule_obj(Qa, name); ra.update(alt['params']); ra['on'] = True
        altrec = run(mk(Qa))
        vers.append(dict(version=alt['version'], current=False, rec=altrec, qualifies=qualifies(altrec)))
    OUT['rules'][name] = dict(label=R_['label'], text=R_['text'], on=R_['on'], versions=vers)
    for v, Q in ((vers[0], Qc),) + (((vers[1], Qa),) if alt else ()):
        if v['qualifies']: OUT['picktime'][f"{R_['label']} · {v['version']}"] = run_pick(mk(Q))
    # ---- switching (signals.json recheck_policy) ----
    S_ = cur['Season']; M_ = cur.get(LAST_MONTH) if LAST_MONTH else None
    T = rule_obj(NEW, name)
    # Season Cards rule status (Trina, Nov 9, 2026; replaces the Nov 6 month test): season to date decides.
    # Off once the rule has the league pick minimum (FBS 3, recheck_policy.off.min_picks) and season units are negative.
    # On when season units are green. The current month is a watch only: a red month on 5+ picks is reported, never switches.
    # Two red months in a row (first check Dec 14) is applied by the run, not here.
    MMIN = POL.get('month_min', 5)
    m_red = bool(M_ and M_['n'] >= MMIN and M_['units'] < 0)
    if S_['n'] >= POL['off']['min_picks'] and S_['units'] < 0 and T['on']:
        T['on'] = False; T['switched'] = f"Off {OUT['run'][:10]}: season {fmt1(S_)}"
        OUT['changes'].append(f"{R_['label']} switched OFF: season {fmt1(S_)}")
    elif S_['units'] > 0 and not T['on']:
        T['on'] = True; T['switched'] = f"Back on {OUT['run'][:10]}: season {fmt1(S_)}"
        OUT['changes'].append(f"{R_['label']} switched back ON: season {fmt1(S_)}")
    if m_red: OUT['warnings'].append(f"Watch: {R_['label']} is red in {LAST_MONTH} on {M_['n']} picks ({fmt1(M_)}); the month never switches a rule")
    if alt and S_['n'] >= POL['switch']['min_picks']:
        A_ = altrec['Season']; AM = altrec.get(LAST_MONTH) if LAST_MONTH else None
        if (A_['n'] >= POL['switch']['min_picks'] and (A_['pct'] or 0) >= (S_['pct'] or 0) and A_['units'] > S_['units']
                and A_['units'] > 0 and AM and AM['units'] > 0):
            T.update(alt['params']); old_v = T.get('version')
            T['version'], T['alt'] = alt['version'], dict(version=old_v, params=alt.get('cur_params', {}), cur_params=alt['params'])
            OUT['changes'].append(f"{R_['label']} moved to its other version '{alt['version']}': season {fmt1(A_)} vs {fmt1(S_)}")
    q = qualifies(cur)
    T['tier'] = 'Strong' if q else 'Solid'   # rule standing by season only (Season Cards, Nov 9: the month is a watch)
    if not q: OUT['warnings'].append(f"{R_['label']} does not qualify season to date: {fmt1(S_)}")
    l3 = cur[[p for p, _ in PER if p.startswith('Last 3')][0]]
    if l3['n'] and l3['units'] < 0: OUT['warnings'].append(f"{R_['label']} is negative over the last 3 weeks: {fmt1(l3)}")
    T['records'] = {p: cur[p] for p in cur}
    T['record_text'] = ' | '.join(f"{p}: {fmt1(cur[p])}" for p in cur if cur[p]['n'])
NEW['checked'] = OUT['run'][:10]

# ---------------- the full test grid ----------------
def pk(r): return RU.decide(r, r['sideS'], r['totS'], RULES)[2]['pick']
def fav(r): return RU.favourite(r)
def dog(r): f = fav(r); return None if not f else ('h' if f == 'a' else 'a')
def keys(r, k): return {s['key'] for s in r['sideS'][r['a'] if k == 'a' else r['h']]}
def tkeys(r, s): return {z['key'] for z in r['totS'][s]}
def inb(v, lo, hi): return v is not None and lo <= v <= hi
SP = lambda k: dict(market='Spread', k=k); ML = lambda k: dict(market='Moneyline', k=k); TT = lambda k: dict(market='Total', k=k)
GR = OUT['grid']
def add(sec, name, fn): GR.setdefault(sec, {})[name] = run(fn)
for lo, hi in ((-100000, -501), (-500, -301), (-300, -201), (-200, -100)):
    add('Favorite moneyline', f'every favorite {lo}..{hi}', lambda r, lo=lo, hi=hi: fav(r) and inb(r.get('ml_' + fav(r)), lo, hi) and ML(fav(r)))
    add('Favorite moneyline', f'signals favor the favorite {lo}..{hi}', lambda r, lo=lo, hi=hi: pk(r) and pk(r) == fav(r) and inb(r.get('ml_' + fav(r)), lo, hi) and ML(fav(r)))
for lo, hi in ((100, 150), (151, 200), (201, 300), (301, 500), (501, 100000)):
    tag = f'+{lo}..{"up" if hi > 9999 else hi}'
    add('Underdog moneyline', f'every underdog {tag}', lambda r, lo=lo, hi=hi: dog(r) and inb(r.get('ml_' + dog(r)), lo, hi) and ML(dog(r)))
    add('Underdog moneyline', f'signals favor the underdog {tag}', lambda r, lo=lo, hi=hi: pk(r) and pk(r) == dog(r) and inb(r.get('ml_' + dog(r)), lo, hi) and ML(dog(r)))
add('Spread', 'every favorite', lambda r: fav(r) and SP(fav(r)))
add('Spread', 'every underdog', lambda r: dog(r) and SP(dog(r)))
add('Spread', 'signal side, every game', lambda r: pk(r) and SP(pk(r)))
for L in (1, 2, 3, 4, 5, 6):
    add('Spread', f'signal side, lead {L}', lambda r, L=L: pk(r) and RU.decide(r, r['sideS'], r['totS'], RULES)[2]['lead'] == L and SP(pk(r)))
for key in ('rlm', 'last_season', 'short_week', 'sharp_action', 'big_money', 'pro_systems', 'money_vs_tickets', 'fade_public'):
    add('Underdog spread by signal', f'underdog with {key}', lambda r, key=key: dog(r) and key in keys(r, dog(r)) and SP(dog(r)))
add('Totals', 'always over', lambda r: TT('Over')); add('Totals', 'always under', lambda r: TT('Under'))
for key in ('sharp_action', 'pro_systems', 'top_experts', 'money_vs_tickets', 'fade_public', 'moved_down', 'fade_recent'):
    for side in ('Over', 'Under'):
        add('Totals by signal', f'{side.lower()} with {key}', lambda r, key=key, side=side: key in tkeys(r, side) and TT(side))
OV = ('sharp_action', 'pro_systems', 'top_experts', 'money_vs_tickets', 'fade_recent')
add('Over totals with signals', 'over with any signal, none on the under', lambda r: (tkeys(r, 'Over') & set(OV)) and not (tkeys(r, 'Under') & set(OV)) and TT('Over'))
add('Over totals with signals', 'over with 2+ signals', lambda r: len(tkeys(r, 'Over') & set(OV)) >= 2 and TT('Over'))
add('Over totals with signals', 'over with sharp action and money vs tickets', lambda r: {'sharp_action', 'money_vs_tickets'} <= tkeys(r, 'Over') and TT('Over'))
add('Over totals with signals', 'over, total 55+, with a signal', lambda r: r['total'] is not None and r['total'] >= 55 and (tkeys(r, 'Over') & set(OV)) and TT('Over'))
add('Over totals with signals', 'over, total under 50, with a signal', lambda r: r['total'] is not None and r['total'] < 50 and (tkeys(r, 'Over') & set(OV)) and TT('Over'))
if DIV == 'fcs':
    def nr(r, k):
        R_ = RULES['side']['fcs_dog_spread']; return len(RU.underdog_reasons(r, k, R_))
    for n_ in (0, 1, 2):
        add('FCS underdog reasons', f'underdog spread, {n_}{"+" if n_ == 2 else ""} reasons', lambda r, n_=n_: dog(r) and r['spread_h'] is not None and ((nr(r, dog(r)) >= 2) if n_ == 2 else nr(r, dog(r)) == n_) and SP(dog(r)))
    add('FCS underdog reasons', 'favorite spread with a reason', lambda r: fav(r) and r['spread_h'] is not None and nr(r, fav(r)) >= 1 and SP(fav(r)))
# ---------------- write ----------------
cols = [p for p, _ in PER]
def row(label, o, q=None):
    return f"| {label} | " + ' | '.join(fmt1(o[c]) for c in cols) + (f" | {'yes' if q else 'no'} |" if q is not None else ' |')
md = [f"# {DIV.upper()} rule evaluation, {OUT['run'][:10]}", '', f"{len(CUR)} {DIV.upper()} games graded in 2026 (weeks {WEEKS[0]}-{WEEKS[-1]}). Qualifies: {QUAL['min_picks']}+ picks, positive units, win % above break-even, season to date. CFBD consensus close; moneylines cleaned.", '',
      '## Rule versions', '', '| Rule · version | ' + ' | '.join(cols) + ' | Qualifies |', '|' + '---|' * (len(cols) + 2)]
for rule, d_ in OUT['rules'].items():
    for v in d_['versions']: md.append(row(f"{d_['label']} · {'current: ' if v['current'] else 'other: '}{v['version']}", v['rec'], v['qualifies']))
md += ['', '## Changes' + (' (applied)' if APPLY else ' (not applied)'), *([f'- {c}' for c in OUT['changes']] or ['- none']),
       '', '## Warnings', *([f'- {w}' for w in OUT['warnings']] or ['- none'])]
md += ['', '## Pick-time check (graded at the card\'s morning line when logged, else the CFBD opener)', '', '| Rule · version | ' + ' | '.join(cols) + ' |', '|' + '---|' * (len(cols) + 1)]
for k, o in OUT['picktime'].items(): md.append(row(k, o))
for sec, tests in GR.items():
    md += ['', f'## {sec}', '', '| Test | ' + ' | '.join(cols) + ' | Qualifies |', '|' + '---|' * (len(cols) + 2)]
    for k, o in tests.items(): md.append(row(k, o, qualifies(o)))
(D / f'ruleeval_{DIV}.md').write_text('\n'.join(md) + '\n')
json.dump(OUT, open(D / f'ruleeval_{DIV}.json', 'w'), indent=1, default=str)
if APPLY:
    S2 = json.load(open(D / 'signals.json')); S2['rules_' + DIV] = NEW
    if OUT['changes']: S2['changelog'].append(dict(date=OUT['run'][:10], div=DIV, change=' | '.join(OUT['changes']), why='Sunday re-check (ruleeval.py), recheck_policy'))
    json.dump(S2, open(D / 'signals.json', 'w'), indent=1, default=str)
print('\n'.join(l for l in md if l.startswith(('#', '- ', '| ')) and 'Test |' not in l)[:6000])
