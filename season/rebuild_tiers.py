"""Rebuild hub meta rules[].tiers for every sport from the hub backtest collection (every game the rule fits).
Usage: python3 rebuild_tiers.py <dl_dir> <out_dir>   (set TODAY=YYYY-MM-DD in the environment)
<dl_dir>/meta/<sport>.json and <dl_dir>/sports/<sport>/backtest/*.json come from ArtifactData list with out_dir.
Writes <out_dir>/m_<sport>.json = {"rules": [...]} with tiers recomputed, and prints every tier status change.
Needs <dl_dir>/sports/<sport>/picks/*.json (and picks_bg for nfl) as well as the backtest.

Turn on rule (Trina, Nov 16, A58; replaces "off to on needs 2 positive pick days"): every tier of every rule, game or
prop, in every sport is ON when its status record has at least the sport minimum of graded status picks (MIN below:
NBA, NHL, NCAAM 20; NFL, FBS, NCAAW 10; pushes count) AND its units are green (above 0). Otherwise it is OFF and logs
would-be picks, with pending_on saying what is missing. On to off is immediate when units are not green (or if a
regrade drops the count below the minimum). No CLV condition. A red month stays a watch flag, not a switch.
The closing line replay (backtest) is kept as tiers[t].season for reference only and never turns a tier on.

Status record (Trina, Nov 11 evening): a tier is judged only on the picks it showed on the card: its card picks while
it was on, plus its would-be picks while it was off (listed under Non Active Picks). Fits that never showed (another
rule took the game, or the Nov 11 backfill) are tracked as `fits` but never decide on or off; held props are left out.
Old card picks count at their meta.retier tier (the Nov 7 one tier scale), the same tier the page shows. Units come
from the price (the units field only when there is no price).
Writes per tier: real (status record, season), real_month (status record, this month), fits (every fit),
season/month (replay), on, pending_on, switched {date, to, record}."""
import json, glob, math, os, sys, re, collections
DL, OUT = sys.argv[1], sys.argv[2]
MIN = {'nba': 20, 'nhl': 20, 'nfl': 10, 'fbs': 10, 'ncaam': 20, 'ncaaw': 10}   # A58 (Nov 16): minimum graded status picks to turn on
def sc(l): return 'Strong' if l >= 4 else ('Solid' if l >= 2 else 'Lean')
TODAY = os.environ.get('TODAY', '')
def units(d):
    r = d.get('result'); pr = d.get('price')
    try: pr = float(str(pr).replace('+', ''))
    except Exception: pr = None
    if pr is None and d.get('units') is not None: return float(d['units'])
    if r == 'win': return 1 if pr is None else (pr / 100 if pr > 0 else 100 / -pr)
    return -1 if r == 'loss' else 0
CONFLICT = re.compile(r"card picked another rule|card is already backing|card order|'kept': '|card picked [A-Z]", re.I)
def counts(p):
    """True when the pick showed on the card: a card pick, or a would-be pick logged because its rule or tier was off."""
    if not p.get('shadow'): return True
    if p.get('backfill'): return False
    c = p.get('conflict')
    if c and CONFLICT.search(str(c)) and not re.search(r'turned off|is off|not on|switched off', str(c), re.I): return False
    return True
def ptier(p, RT):
    t = RT.get(p.get('__id')) or p.get('tier') or 'Lean'
    t = str(t).capitalize(); return {'Thin': 'Lean'}.get(t, t)
def tier_bt(s, b):
    i = b.get('inputs') or {}; m = b.get('market')
    if str(b.get('tier')) == 'All': return 'All'   # Nov 11 (A29, A31): single-tier rules
    if s == 'nba':
        if m == 'Total':
            tc = i.get('total_scores') or {}; return sc((tc.get('U', 0) or 0) - (tc.get('O', 0) or 0))
        ss = i.get('side_scores') or {}; side = b['away'] if str(b.get('pick', '')).startswith(b['away']) else b['home']
        oth = b['home'] if side == b['away'] else b['away']; return sc((ss.get(side, 0) or 0) - (ss.get(oth, 0) or 0))
    if s == 'fbs' and i.get('lead') is not None: return sc(float(i['lead']))
    if s in ('ncaam', 'ncaaw'):
        g = i.get('edge') if i.get('edge') is not None else i.get('gap_vs_open')
        if g is not None: return sc(min(4, math.floor(abs(float(g)) / 2)))
        return sc(float(i['lead'])) if i.get('lead') is not None else None   # Nov 11: signal lead rules
    t = {'Thin': 'Lean'}.get(b.get('tier'), b.get('tier'))
    if t in ('Strong', 'Solid', 'Lean'): return t
    # Nov 11: NFL off rule docs carry no tier; use the signal lead toward the pick
    pk = str(b.get('pick', ''))
    if b.get('market') == 'Total' and i.get('total_over') is not None:
        d = float(i.get('total_over') or 0) - float(i.get('total_under') or 0)
        return sc(d if pk.startswith('Over') else -d)
    if i.get('signal_lead') is not None and i.get('signal_team'):
        return sc(float(i['signal_lead']) if pk.startswith(str(i['signal_team'])) else -float(i['signal_lead']))
    return None
def prop_cat(stat, rule):
    """Same as the page's propCat: the prop rule's stat name."""
    x = re.sub(r'[_\-]+', ' ', str(stat or '').lower()).strip()
    if not x:
        m = re.match(r'^(PASS|REC|RUSH)\b', str(rule or ''), re.I)
        if m: x = m.group(1).lower()
    if re.match(r'^(pra|p\s*\+\s*r\s*\+\s*a|pts\s*\+\s*reb\s*\+\s*ast|points\s*\+\s*rebounds\s*\+\s*assists)$', x): return 'Points + rebounds + assists'
    if re.search(r'pass.*(td|touchdown)', x): return 'Passing touchdowns'
    if re.match(r'^pass(ing)?( yds| yards)?$|^passing yards$', x): return 'Passing yards'
    if re.match(r'^receptions?$', x): return 'Receptions'
    if re.match(r'^rec(eiving)?( yds| yards)?$', x): return 'Receiving yards'
    if re.match(r'^rush(ing)?( yds| yards)?$', x): return 'Rushing yards'
    if re.search(r'three|3 ?pointers|^3pm$|^3s$', x): return 'Threes'
    if re.match(r'^reb', x): return 'Rebounds'
    if re.match(r'^ast', x) or 'assist' in x: return 'Assists'
    if re.match(r'^sog$', x) or 'shot' in x: return 'Shots on goal'
    if 'goal' in x: return 'Goals'
    if re.match(r'^(points?|pts)$', x): return 'Points'
    return x[:1].upper() + x[1:] if x else 'Prop'
def prop_side(p):
    """Same as the page's propSide."""
    sd = str(p.get('side') or '')
    if re.match(r'^u', sd, re.I): return 'Under'
    if re.match(r'^o', sd, re.I): return 'Over'
    t = str(p.get('pick') or '')
    if re.search(r'\bunder\b|\bu\d', t, re.I): return 'Under'
    if re.search(r'\bover\b|\bo\d|anytime|\d\+', t, re.I): return 'Over'
    r = str(p.get('rule') or '')
    if re.search(r'\bunder\b', r, re.I): return 'Under'
    if re.search(r'\bover\b', r, re.I): return 'Over'
    return ''
def prop_tier(p):
    """Nov 13/14: prop tier by edge over the price; old docs fall back to their edge, then PLAY=Solid, LEAN=Lean."""
    t = str(p.get('tier') or '')
    if t in ('Strong', 'Solid', 'Lean'): return t
    e = p.get('edge')
    try: e = float(str(e).replace('%', '').replace('+', ''))
    except Exception: e = None
    if e is not None:
        return 'Strong' if e >= 5 else 'Solid' if e >= 3 else 'Lean'
    g = str(p.get('grade') or p.get('tier') or '').upper()
    return 'Solid' if g == 'PLAY' else 'Lean'


def prop_rule_name(p):
    c, sd = prop_cat(p.get('stat'), p.get('rule')), prop_side(p)
    return c + (' · ' + sd if sd else '')
def turn_on(ps, s):
    """A58 (Trina, Nov 16): on when the status record has at least MIN[s] graded picks and units above 0."""
    n = len(ps); m = MIN[s]; u = round(sum(units(x) for x in ps), 2)
    if n >= m and u > 0: return True, ''
    if n < m:
        return False, (f'Green, {n} of {m} picks' if u > 0 else f'{n} of {m} status picks needed to turn on') + (f'; red, needs +{max(0.01, -u):.2f}u' if u <= 0 and n else '')
    return False, f'Red, needs +{max(0.01, -u):.2f}u'
BASIS = 'status record: card picks plus would-be picks while off; on with at least {m} graded status picks and units above 0 (Trina Nov 16, A58)'
def rec(a, label=None):
    o = dict(w=sum(x['result'] == 'win' for x in a), l=sum(x['result'] == 'loss' for x in a), p=sum(x['result'] == 'push' for x in a), u=round(sum(units(x) for x in a), 2))
    if label: o['label'] = label
    return o
os.makedirs(OUT, exist_ok=True)
for s in MIN:
    mp = f'{DL}/meta/{s}.json'
    if not os.path.exists(mp): continue
    d = json.load(open(mp)); m = d.get('data', d)
    bt = [json.load(open(f)) for f in glob.glob(f'{DL}/sports/{s}/backtest/*.json')]
    bt = [b.get('data', b) for b in bt]
    picks = [json.load(open(f)) for f in glob.glob(f'{DL}/sports/{s}/picks/*.json') + (glob.glob(f'{DL}/sports/nfl/picks_bg/*.json') if s == 'nfl' else [])]
    picks = [dict(x.get('data', x), __id=os.path.basename(f)[:-5]) for x, f in zip(picks, glob.glob(f'{DL}/sports/{s}/picks/*.json') + (glob.glob(f'{DL}/sports/nfl/picks_bg/*.json') if s == 'nfl' else []))]
    RT = m.get('retier') or {}
    month = (TODAY or max([str(b.get('date', '')) for b in bt] or ['2026-11']))[:7]
    for r in m['rules']:
        if r.get('market') == 'Prop':
            # Nov 14 (Trina): prop rules are tracked by tier like game rules; each tier has its own status record and turns on or off on its own
            mm = re.match(r'^(.*?) · (Over|Under)', str(r.get('label', '')))
            if mm:
                lbl = str(r.get('label', '')).split(',')[0].strip()
                F = [p for p in picks if p.get('market') == 'Prop' and p.get('result') in ('win', 'loss', 'push') and prop_rule_name(p) == lbl and not p.get('held')]
                old = r.get('tiers') or {}
                rule_was_on = r.get('on') is not False and r.get('real') is not None
                byt = collections.defaultdict(list)
                for p in F: byt[prop_tier(p)].append(p)
                new = {}
                for t in ('Strong', 'Solid', 'Lean'):
                    L = byt.get(t, []); o = old.get(t) or {}
                    v = dict(season=None, month=None, n=len(L), fits=rec(L) if L else None)
                    if not L:
                        v.update(real=None, real_month=None, on=False, pending_on=f'0 of {MIN[s]} status picks needed to turn on')
                    else:
                        real = rec(L); mo = [p for p in L if str(p.get('date'))[:7] == month]
                        v.update(real=real, real_month=rec(mo, 'Nov') if mo else None)
                        was = (bool(o.get('on')) and o.get('real') is not None) if o else rule_was_on
                        on, why = turn_on(L, s)   # A58: minimum status picks and green units
                        if not on: v['pending_on'] = why
                        if was != on:
                            print(s, lbl, t, 'status record turns it', 'on' if on else 'off', f"{real['w']}-{real['l']} {real['u']:+.2f}u")
                            v['switched'] = dict(date=TODAY, to='on' if on else 'off', record=f"{real['w']}-{real['l']} {real['u']:+.2f}u")
                        elif o.get('switched'): v['switched'] = o['switched']
                        v['on'] = on
                    v['basis'] = f'prop tier by edge (Strong 5+, Solid 3 to 5, Lean 1.5 to 3); status record per tier (Trina Nov 14); on with at least {MIN[s]} graded status picks and units above 0 (Trina Nov 16, A58)'
                    new[t] = v
                r['tiers'] = new
                r['fits'] = rec(F) if F else None
                r['real'] = rec(F) if F else None   # whole rule, reference only
                r['on'] = any(v.get('on') for v in new.values())   # rule shows on when any tier is on
                r.pop('pending_on', None)
            continue
        keys = r.get('keys') or [r['key']]; old = r.get('tiers') or {}
        new = {t: {k: v for k, v in dict(o).items() if k not in ('real', 'real_month', 'fits', 'pending_on')} for t, o in old.items() if isinstance(o, dict)}   # Nov 13: keep every stored tier
        E = {}
        for b in bt:
            if b.get('rule_key') in keys and b.get('result') in ('win', 'loss', 'push') and b.get('first_in_rule_order') is not False:   # Nov 11: NFL card order
                t = tier_bt(s, b)
                if t in ('Strong', 'Solid', 'Lean', 'All'): E.setdefault(t, []).append(b)
        on_rule = r.get('on') is not False
        if not bt:   # no backtest download: keep the stored replay numbers and statuses
            new = {t: {k: v for k, v in dict(o).items() if k not in ('real', 'real_month', 'fits', 'pending_on')} for t, o in old.items()}
        for t, e in E.items():
            se = rec(e); n = se['w'] + se['l'] + se['p']; mo = [x for x in e if str(x['date'])[:7] == month]
            new[t] = dict(new.get(t, {}), season=se, month=rec(mo, 'Nov') if mo else None, n=n)   # Nov 13: replay is reference only, never switches
        # Nov 11 evening (Trina): the status record decides (card picks, plus would-be picks while the tier was off)
        rp = collections.defaultdict(list); rf = collections.defaultdict(list)
        for p in picks:
            if p.get('market') != 'Prop' and p.get('rule') in keys and p.get('result') in ('win', 'loss', 'push'):
                t = ptier(p, RT); rf[t].append(p)
                if counts(p): rp[t].append(p)
        for t in set(rp) | set(rf):
            if t not in new: new[t] = dict(season=dict(w=0, l=0, p=0, u=0), month=None, n=0, on=False, upgraded=False, downgraded=False)
        for t, v in new.items():
            real = rec(rp[t]) if rp.get(t) else None
            mo = [p for p in rp.get(t, []) if str(p.get('date'))[:7] == month]
            v['real'] = real; v['real_month'] = rec(mo, 'Nov') if mo else None; v['fits'] = rec(rf[t]) if rf.get(t) else None
            v['basis'] = BASIS.format(m=MIN[s])
            o = old.get(t) or {}
            if real is None:   # Nov 13 (A36, A37): no status record, no switch on from the replay
                v['on'] = False; v['upgraded'] = False; v['downgraded'] = on_rule
                v['pending_on'] = f'0 of {MIN[s]} status picks needed to turn on'
                if o.get('on'): print(s, r['key'], t, 'turned off: no status record yet (was on by replay)')
                continue
            was = bool(o.get('on', False)) and o.get('real') is not None   # a tier turned on by the replay alone has not earned it
            v.pop('pending_on', None)
            on, why = turn_on(rp[t], s)   # A58: minimum status picks and green units
            if not on: v['pending_on'] = why
            if was != on:
                print(s, r['key'], t, 'status record turns it', 'on' if on else 'off', f"{real['w']}-{real['l']} {real['u']:+.2f}u")
                v['switched'] = dict(date=TODAY, to='on' if on else 'off', record=f"{real['w']}-{real['l']} {real['u']:+.2f}u")
            elif (old.get(t) or {}).get('switched'): v['switched'] = old[t]['switched']
            v['on'] = on; v['upgraded'] = (not on_rule) and on; v['downgraded'] = on_rule and not on
        # Nov 12 and 13 (Trina): no rule is single tier. Drop the old 'All' tier; every game rule carries Strong, Solid and Lean.
        if 'All' in new and not rp.get('All'): new.pop('All')
        for t in ('Strong', 'Solid', 'Lean'):
            if t not in new: new[t] = dict(season=None, month=None, n=0, on=False, upgraded=False, downgraded=on_rule, real=None, real_month=None, fits=None,
                                         basis=BASIS.format(m=MIN[s]), pending_on=f'0 of {MIN[s]} status picks needed to turn on')
        r.pop('single_tier', None)
        r['tiers'] = new
    json.dump(dict(rules=m['rules']), open(f'{OUT}/m_{s}.json', 'w'))
print('done')
