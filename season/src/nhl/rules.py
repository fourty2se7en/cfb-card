"""NHL card: signal scoring and pick rules. ONE shared file, used by the daily card (render.py) and the daily re-check (review/recheck.py).
The rule set itself (thresholds, versions, locked price limits) lives in signals.RULESET; this file applies it.
Approved by Trina Oct 30, 2026 after the v2 pick-method review (every game Sep 29 to Oct 28):
  Moneyline (ML1): signal side with a lead of 2+ and the price within the limits. Stricter version: lead 3+.
  Puck line (PL1): puck line of the team with Action Network Sharp Action on its moneyline. Stricter: plus money % above
    ticket % or a reverse line move on that team.
  Total (TOT1): Over in Atlantic vs Pacific games or when the division signal is 2 points. Stricter: both at once.
  Otherwise No pick.
Switching (decide): a rule goes off at 20+ season picks with negative season units and back on when season units are
positive (tracked as shadow picks while off). It moves to its other version only when that version has 30+ picks since
approval, wins at least as often, makes more units, and is positive since approval and in the current month.
Rule state (status, version, records) is written to rules_state.json by the daily re-check."""
import json, pathlib, sys
D = pathlib.Path(__file__).parent
sys.path.insert(0, str(D))
from signals import RULESET

PRICE = RULESET['price']
def within_limits(price):
    return (price < 0 and price >= PRICE['fav_max']) or (PRICE['dog_min'] <= price <= PRICE['dog_max'])

WEIGHTS = {'Sharp Action': 2, 'PRO Systems': 1, 'Big Money': 1}
ZERO = {'Division strength', 'Fade the public', 'Recent form', 'Goal differential', 'Hot streak'}  # info only (lost on their own)

def tier(m): return 'Strong' if m >= 4 else ('Solid' if m >= 2 else 'Lean')  # Nov 2 (Trina): three tiers on the pick side's lead, rule trigger signals included
def ip(a): return 100/(a+100) if a > 0 else -a/(-a+100)
def novig_home(a, h): x, y = ip(a), ip(h); return y/(x+y)

ORDER = ['ML1', 'PL1', 'TOT1', 'TOT2', 'P1O']
MONTH_MIN = 5   # Nov 9 policy: the month is a watch only once it has 5+ picks (season decides)
RULES = {}
for k in ORDER:
    v = RULESET[k]
    RULES[k] = dict(market=v['market'], short=v['short'], versions=v['versions'], status='on', version='base', record=None)
STATE = D/'rules_state.json'
STATE_DATA = {}
if STATE.exists():
    try:
        STATE_DATA = json.loads(STATE.read_text())
        for k, v in STATE_DATA.get('rules', {}).items():
            if k in RULES:
                RULES[k].update({kk: vv for kk, vv in v.items() if kk in ('status', 'version', 'record')})
    except Exception:
        STATE_DATA = {}
for k in RULES:
    if RULES[k]['version'] not in RULES[k]['versions']: RULES[k]['version'] = 'base'
    RULES[k]['label'] = RULES[k]['versions'][RULES[k]['version']]['label']

def month_of(date):
    import calendar
    return f"{calendar.month_abbr[int(date[5:7])]} {date[:4]}"

def score(c):
    """c: game context (see render.ctx_from_card and review/score.ctx_from_rebuild).
    Returns side, puck line and total scoring with rows (signal, market, side code, points, note)."""
    a, h = c['a'], c['h']; nm = {'A': a, 'H': h}
    S = []; sc = {'A': 0, 'H': 0}
    def add(sig, mkt, side, pts, note):
        if sig in ZERO: pts = 0; note = note + ' Info only: this signal lost on its own in the Oct 29 review.'
        S.append((sig, mkt, side, pts, note)); sc[side] += pts
    for name, side in (c.get('sig_ml') or {}).items():
        add(f'Action Network {name}', 'Moneyline', side, WEIGHTS[name], 'PRO signal is lit on this side.')
    ba, ma = c.get('bets'), c.get('money')
    if ba is not None and ma is not None:
        if ma - ba >= 10: add('Money % above ticket %', 'Moneyline', 'A', 1, f'{a}: {ba}% of bets but {ma}% of money.')
        elif ba - ma >= 10: add('Money % above ticket %', 'Moneyline', 'H', 1, f'{h}: {100-ba}% of bets but {100-ma}% of money.')
        if ba <= 35: add('Fade the public', 'Moneyline', 'A', 1, f'{100-ba}% of tickets are on {h}.')
        elif ba >= 65: add('Fade the public', 'Moneyline', 'H', 1, f'{ba}% of tickets are on {a}.')
    rlm = None
    pHn = novig_home(c['mla'], c['mlh'])
    if c.get('ml_open') and ba is not None:
        pHo = novig_home(*c['ml_open']); mv = pHn - pHo
        if abs(mv) >= 0.02:
            tw = 'H' if mv > 0 else 'A'; tb = (100-ba) if tw == 'H' else ba
            if tb < 50: add('Reverse line movement', 'Moneyline', tw, 2, f'Line moved toward {nm[tw]} with only {tb}% of tickets.'); rlm = tw
            else: S.append(('Line move with the public', 'Moneyline', tw, 0, 'Moved with the ticket majority, so it is not a sharp tell.'))
    estH = c['estH']; ms = 'H' if estH > 0.5 else 'A'
    add('Card projection', 'Moneyline', ms, 1, f'Blended win chance {100*max(estH, 1-estH):.1f}%.')
    if c['sv_a'] - c['sv_h'] >= 0.004: add('Goalie edge', 'Moneyline', 'A', 1, f"Card save % {c['sv_a']:.3f} vs {c['sv_h']:.3f}.")
    elif c['sv_h'] - c['sv_a'] >= 0.004: add('Goalie edge', 'Moneyline', 'H', 1, f"Card save % {c['sv_h']:.3f} vs {c['sv_a']:.3f}.")
    for loss, side_for, who in ((c.get('loss_a', 0), 'H', a), (c.get('loss_h', 0), 'A', h)):
        if loss >= 0.08: add('Key absence', 'Moneyline', side_for, 2 if loss >= 0.15 else 1, f'{who} loses {loss:.2f} goals per game to injuries.')
    if c['rest_a'] == 0 and c['rest_h'] > 0: add('Rest edge', 'Moneyline', 'H', 1, f'{a} on the second night of a back-to-back.')
    if c['rest_h'] == 0 and c['rest_a'] > 0: add('Rest edge', 'Moneyline', 'A', 1, f'{h} on the second night of a back-to-back.')
    def vp(r):
        w, l, o = r; n = w+l+o
        return ((2*w+o)/(2*n) if n else 0.5)*n/(n+10) + 0.5*10/(n+10)
    hp, rp = vp(c['home_rec_h']), vp(c['road_rec_a']); vgap = hp - rp
    if abs(vgap) >= 0.15 and not c.get('neutral'): add('Home/road split', 'Moneyline', 'H' if vgap > 0 else 'A', 2 if abs(vgap) >= 0.30 else 1, f'{h} home {hp:.3f} adjusted vs {a} road {rp:.3f} adjusted.')
    if not c.get('neutral'): add('Home ice', 'Moneyline', 'H', 1, f'{h} at home.')   # Nov 12: none at a neutral site
    for sd, (code, k), who in (('A', c['strk_a'], a), ('H', c['strk_h'], h)):
        if code == 'W' and k >= 3: add('Hot streak', 'Moneyline', sd, 1, f'{who} has won {k} straight.')
        if code in ('L', 'OT') and k >= 3: add('Cold streak', 'Moneyline', 'H' if sd == 'A' else 'A', 1, f'{who} has lost {k} straight.')
    def l10p(r):
        w, l, o = r; return (2*w+o)/max(2*(w+l+o), 1)
    if c.get('l10_a') and c.get('l10_h'):
        fa, fh = l10p(c['l10_a']), l10p(c['l10_h'])
        if abs(fa-fh) >= 0.20: add('Recent form', 'Moneyline', 'A' if fa > fh else 'H', 1, f'Last 10 points %: {a} {fa:.3f}, {h} {fh:.3f}.')
    if c.get('gd_a') is not None and c.get('gd_h') is not None:
        if abs(c['gd_a']-c['gd_h']) >= 0.6: add('Goal differential', 'Moneyline', 'A' if c['gd_a'] > c['gd_h'] else 'H', 1, f"Per game: {a} {c['gd_a']:+.2f}, {h} {c['gd_h']:+.2f}.")
    la_, lh_ = c['last_a'], c['last_h']
    if abs(la_-lh_) >= 0.08: add('Track record', 'Moneyline', 'A' if la_ > lh_ else 'H', 1, f'Last season points %: {a} {la_:.3f}, {h} {lh_:.3f}.')
    for sd, now_p, last_p, who in (('A', c['ppct_a'], la_, a), ('H', c['ppct_h'], lh_, h)):
        if now_p is None: continue
        if last_p - now_p >= 0.12 and last_p >= 0.58: add('Bounce-back candidate', 'Moneyline', sd, 1, f'{who} {now_p:.3f} after {last_p:.3f} last season.')
        if now_p - last_p >= 0.15 and last_p <= 0.53: add('Regression watch', 'Moneyline', 'H' if sd == 'A' else 'A', 1, f'{who} {now_p:.3f} after {last_p:.3f} last season.')
    ca, ch = ip(c['cup_a']), ip(c['cup_h'])
    if max(ca, ch)/min(ca, ch) >= 2: add('Roster strength', 'Moneyline', 'A' if ca > ch else 'H', 1, 'Stanley Cup odds 2x or better.')
    div_side, div_pts = None, 0
    if c['div_a'] != c['div_h']:
        gap = c['div_str'][c['div_a']] - c['div_str'][c['div_h']]
        div_pts = 2 if abs(gap) >= 0.10 else (1 if abs(gap) >= 0.05 else 0)
        if div_pts:
            div_side = 'A' if gap > 0 else 'H'
            add('Division strength', 'Moneyline', div_side, div_pts, f"{c['div_a']} {c['div_str'][c['div_a']]:.3f} vs {c['div_h']} {c['div_str'][c['div_h']]:.3f} adjusted out-of-division points %.")
    side = 'A' if sc['A'] > sc['H'] else ('H' if sc['H'] > sc['A'] else ms)
    other = 'H' if side == 'A' else 'A'
    lead = sc[side] - sc[other]
    conf_ml = any(s in ('Action Network Sharp Action', 'Reverse line movement') and sd == other and p for s, m, sd, p, n in S)
    out = dict(S=S, sc=sc, side=side, ml_lead=lead, ml_tier=tier(lead), conf_ml=conf_ml, estH=estH, rlm=rlm, div_side=div_side, div_pts=div_pts)
    # ---- totals signals (scored for information; totals rule is No pick)
    T = []
    if c.get('line') is not None:
        for name, v in (c.get('sig_tot') or {}).items(): T.append((f'Action Network {name}', 'Total', v, WEIGHTS[name], 'PRO signal is lit on this side.'))
        ob, om = c.get('o_bets'), c.get('o_money')
        if ob is not None:
            if ob >= 75: T.append(('Fade the public', 'Total', 'U', 1, f'{ob}% of tickets on the over.'))
            elif ob <= 25: T.append(('Fade the public', 'Total', 'O', 1, f'{100-ob}% of tickets on the under.'))
            if om is not None:
                if om - ob >= 10: T.append(('Money % above ticket %', 'Total', 'O', 1, f'Over {ob}% of bets, {om}% of money.'))
                elif ob - om >= 10: T.append(('Money % above ticket %', 'Total', 'U', 1, f'Under {100-ob}% of bets, {100-om}% of money.'))
        if c.get('tot_open') is not None and ob is not None and c['line'] < c['tot_open']:
            T.append(('Total moved down', 'Total', 'U', 2 if ob >= 50 else 1, f"Opened {c['tot_open']:g}, now {c['line']:g}."))
        d = c['lamT'] - c['line']
        if abs(d) >= 0.25: T.append(('Card projection', 'Total', 'O' if d > 0 else 'U', 1, f"Projected {c['lamT']:.2f} vs {c['line']:g}."))
        if c.get('last5') is not None:
            if c['last5'] >= c['line'] + 0.5: T.append(('Recent scoring', 'Total', 'O', 1, f"Last 5 games averaged {c['last5']:.1f} goals."))
            elif c['last5'] <= c['line'] - 0.5: T.append(('Recent scoring', 'Total', 'U', 1, f"Last 5 games averaged {c['last5']:.1f} goals."))
        gsv = (c['sv_a'] + c['sv_h'])/2
        if gsv >= 0.891: T.append(('Goaltending', 'Total', 'U', 1, f'Card save % average {gsv:.3f}.'))
        elif gsv <= 0.884: T.append(('Goaltending', 'Total', 'O', 1, f'Card save % average {gsv:.3f}.'))
        tc = {'O': sum(p for s, m, sd, p, n in T if sd == 'O'), 'U': sum(p for s, m, sd, p, n in T if sd == 'U')}
        tside = 'O' if tc['O'] > tc['U'] else ('U' if tc['U'] > tc['O'] else ('O' if d > 0 else 'U'))
        out.update(T=T, tc=tc, tside=tside, t_lead=tc[tside] - tc['U' if tside == 'O' else 'O'])
    return out

# Tier flags (Trina, Nov 9): hub meta rules[].tiers. A tier of an OFF rule that is upgraded and on makes card picks; a tier of an ON rule that is
# downgraded (on false) makes would-be (shadow) picks only. A rule that turns fully on keeps its downgraded tiers off. Copied from hub meta each run.
import json as _json, pathlib as _pl
try: TIER_FLAGS = _json.loads((_pl.Path(__file__).parent / 'tier_flags.json').read_text())
except Exception: TIER_FLAGS = {}
def tier_status(rule, status, tier):
    # Nov 11 (Trina): real picks decide; the tier's hub meta `on` flag is today's status (rebuilt by the main chat).
    f = TIER_FLAGS.get(rule, {}).get(tier) or {}
    if 'on' in f and f['on'] is not None: return 'on' if f['on'] else 'off'
    return status

def apply_rules(c, r, version=None):
    """Picks for one game. version: None = each rule's active version; 'base' or 'strict' = that version for every rule.
    Returns list of dicts {rule, version, market, side ('A'|'H'|'O'|'U'), price, line, status, tier}.
    status 'on' = card pick, 'off' = shadow (logged and graded, not shown)."""
    picks = []
    def ver(k): return version or RULES[k]['version']
    # ML1
    v = ver('ML1'); P = RULES['ML1']['versions'][v]
    side = r['side']; price = c['mla'] if side == 'A' else c['mlh']
    if r['ml_lead'] >= P['lead'] and within_limits(price):
        picks.append(dict(rule='ML1', version=v, market='Moneyline', side=side, price=price, line=None, status=RULES['ML1']['status'], tier=r['ml_tier']))
    # PL1
    v = ver('PL1'); P = RULES['PL1']['versions'][v]; pl = c.get('pl')
    if pl:
        lit = [sd for name, sd in (c.get('sig_ml') or {}).items() if name == 'Sharp Action']
        if len(lit) == 1:
            sd = lit[0]
            conf = any(s in ('Reverse line movement', 'Money % above ticket %') and x == sd for s, m, x, p, n in r['S'])
            if conf or not P['confirm']:
                sp = pl['sp_a'] if sd == 'A' else -pl['sp_a']
                picks.append(dict(rule='PL1', version=v, market='Puck line', side=sd, price=pl['price_a'] if sd == 'A' else pl['price_h'], line=sp,
                                  status=RULES['PL1']['status'], tier='Sharp'))
    # TOT1
    v = ver('TOT1'); P = RULES['TOT1']['versions'][v]
    if c.get('line') is not None and c.get('tprice'):
        ap = {c['div_a'], c['div_h']} == {'Atlantic', 'Pacific'}; d2 = r.get('div_pts') == 2
        if (ap and d2) if P['both'] else (ap or d2):
            picks.append(dict(rule='TOT1', version=v, market='Total', side='O', price=c['tprice'][0], line=c['line'], status=RULES['TOT1']['status'], tier='Division'))
    # TOT2 (Nov 12, Trina): every game gets an over or under look. The totals signals lost on their own all season, so when they lean
    # one way by the version's lead, the rule takes the other side (season replay at the close: lead 2+ 122-92-3 +21.6u, both halves green).
    if 'TOT2' in RULES and c.get('line') is not None and c.get('tprice') and r.get('tside') and r.get('t_lead') is not None:
        v = ver('TOT2'); P = RULES['TOT2']['versions'][v]
        if r['t_lead'] >= P['lead']:
            sd = 'U' if r['tside'] == 'O' else 'O'
            picks.append(dict(rule='TOT2', version=v, market='Total', side=sd, price=c['tprice'][0 if sd == 'O' else 1], line=c['line'],
                              status=tier_status('TOT2', RULES['TOT2']['status'], tier(r['t_lead'])), tier=tier(r['t_lead'])))   # Nov 13 (Trina, A34/B74): tier by the totals lead it fades
            # P1O (Nov 12, Trina, game props): first period Over 1.5 when TOT2 takes the Over (SBR 1P close 123-74 +16.2u)
            p1 = c.get('p1')
            if sd == 'O' and 'P1O' in RULES and p1 and p1[0] == 1.5 and (r['t_lead'] >= 3 or ver('P1O') == 'base'):
                picks.append(dict(rule='P1O', version=ver('P1O'), market='1st period total', side='O', price=p1[1], line=1.5,
                                  status=tier_status('P1O', RULES['P1O']['status'], tier(r['t_lead'])), tier=tier(r['t_lead'])))
    return picks

def nopick_reason(rule, c, r, nm):
    """Plain reason a rule did not fire for this game (for the card's No pick boxes)."""
    v = RULES[rule]['version']; P = RULES[rule]['versions'][v]
    if rule == 'ML1':
        side = r['side']; price = c['mla'] if side == 'A' else c['mlh']
        if r['ml_lead'] < P['lead']: return f"The signal side ({nm[side]}) leads by {r['ml_lead']}; the rule needs {P['lead']}+."
        return f"{nm[side]} at {price:+d} is outside the price limits (favorite no longer than {PRICE['fav_max']}, underdog +{PRICE['dog_min']} to +{PRICE['dog_max']})."
    if rule == 'PL1':
        lit = [sd for name, sd in (c.get('sig_ml') or {}).items() if name == 'Sharp Action']
        if not lit: return 'No Action Network Sharp Action on either moneyline.'
        if len(lit) > 1: return 'Sharp Action is lit on both moneylines.'
        return 'Sharp Action team has no money % edge or reverse line move (stricter version).'
    if rule == 'P1O':
        return 'Only when the totals rule (TOT2) takes the Over and the first period total is 1.5.'
    if rule == 'TOT2':
        if c.get('line') is None: return 'No total posted.'
        return f"Totals signals lean {'over' if r.get('tside') == 'O' else 'under'} by {r.get('t_lead', 0)} points; the rule takes the other side at a lead of {P['lead']}+."
    if rule == 'TOT1':
        if c.get('line') is None: return 'No total posted.'
        if P['both']: return 'Needs an Atlantic vs Pacific game with a division signal of 2 points (stricter version).'
        return f"Not an Atlantic vs Pacific game and the division signal is {r.get('div_pts', 0)} points (needs 2)."
    return ''

def agg(bets):
    """bets: list of (date, result W/L/P, price) -> dict w, l, p, n, wp, u, be."""
    def dec(a): return 1 + a/100 if a > 0 else 1 + 100/(-a)
    w = sum(x[1] == 'W' for x in bets); l = sum(x[1] == 'L' for x in bets); p = sum(x[1] == 'P' for x in bets)
    u = sum((dec(x[2])-1) if x[1] == 'W' else (-1 if x[1] == 'L' else 0) for x in bets)
    gr = [x for x in bets if x[1] != 'P']
    return dict(w=w, l=l, p=p, n=w+l, wp=(w/(w+l)) if w+l else None, u=round(u, 2), be=(len(gr)/sum(dec(x[2]) for x in gr)) if gr else None)

def decide(rule_id, season, since, month_now, other_since, other_month):
    """Switch logic for one rule. season = active version, every game this season; since = active version since approval;
    month_now = active version in the current month; other_* = the other version.
    Returns (status, version, changes[list of text], warnings[list of text])."""
    R_ = RULES[rule_id]; st, v = R_['status'], R_['version']; ch, wn = [], []
    mn = RULESET['switch']['off_min_picks']; vn = RULESET['switch']['version_min_picks']
    # Rule status policy (Trina, Nov 9, 2026; replaces the Nov 6 month test): season to date decides.
    # Off once the rule has the league pick minimum (NHL 20, one quarter of an 82 game season) and season units are negative.
    # On when season units are green. The current month is a watch only (a red month on 5+ picks is reported, never switches).
    # Two red months in a row (5+ picks each) switch off only after the first full week of the next month (first check Dec 14).
    mm = MONTH_MIN
    month_bad = month_now['n'] >= mm and month_now['u'] < 0
    if st == 'on' and season['n'] >= mn and season['u'] < 0:
        st = 'off'; ch.append(f"{rule_id} switched OFF: season {season['w']}-{season['l']}, {season['u']:+.2f}u over {season['n']} picks. Picks are still tracked.")
    elif st == 'off' and season['u'] > 0:
        st = 'on'; ch.append(f"{rule_id} switched ON (season only policy, Nov 9): season {season['w']}-{season['l']}, {season['u']:+.2f}u is green"
                             + (f"; this month {month_now['w']}-{month_now['l']}, {month_now['u']:+.2f}u is a watch only." if month_bad else "."))
    o = other_since
    if (o['n'] >= vn and o['wp'] is not None and (since['wp'] is None or o['wp'] >= since['wp']) and o['u'] > since['u']
            and o['u'] > 0 and other_month['u'] > 0):
        nv = 'strict' if v == 'base' else 'base'
        ch.append(f"{rule_id} moved to its {nv} version: since approval {o['w']}-{o['l']}, {o['u']:+.1f}u vs {since['w']}-{since['l']}, {since['u']:+.1f}u.")
        v = nv
    if st == 'on':
        if season['n'] >= 10 and season['u'] < 0: wn.append(f"{rule_id} is negative for the season ({season['u']:+.1f}u); it switches off at {mn} picks.")
        if month_now['n'] >= 5 and month_now['u'] < 0: wn.append(f"Watch: {rule_id} is down {month_now['u']:+.1f}u this month on {month_now['n']} picks (watch only; the season decides).")
        if season['wp'] is not None and season['be'] is not None and season['n'] >= 10 and season['wp'] <= season['be']:
            wn.append(f"{rule_id} wins {100*season['wp']:.0f}%, at or below break-even {100*season['be']:.0f}%.")
    return st, v, ch, wn
