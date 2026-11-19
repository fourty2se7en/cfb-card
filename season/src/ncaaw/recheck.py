"""Daily re-check for the NCAA cards. Usage: python3 recheck.py M|W [today YYYY-MM-DD]
Reads season/games_<lg>.txt (one line per game played this season, same row format as the backtest: bt_build.js),
reruns every rule family (both variants) on every game played, season to date, by month and over the last 14 days,
applies the automatic switches and writes rules_state_<lg>.json and recheck_report_<lg>.md. The backtest stays a separate baseline.
Switches (automatic):
  - Season Cards policy (Trina, Nov 6 2026): a rule is active only while season units AND this month are green; off at 20+ season picks
    when season units are negative or the month is negative on 5+ picks; on when both are green, including rules that failed the backtest;
  - a rule moves to its other variant only after 30+ picks, when the other variant has more units season to date AND this month (5+ picks);
  - no switches while freeze_until (or a rule's hold_on_until) is in force; records still update.
  - Nov 9 2026 (Trina, later the same day): the NCAAW backtest gate is retired. NCAAW follows the standard Season Cards policy:
    season to date decides (off at policy.off_min picks with negative season units, on when season units are green), the month is a
    watch, and two completed red months in a row switch a rule off after the first full week of the next month. Pick minimum 7.
Any other rule change is shown to Trina with the numbers and waits for her OK."""
import json, sys, pathlib, datetime
import rules as R
import top25 as T25   # Nov 9 2026: NCAAW rule records count AP Top 25 games only
D = pathlib.Path(__file__).parent
LG = sys.argv[1] if len(sys.argv) > 1 else 'M'
TODAY = sys.argv[2] if len(sys.argv) > 2 else datetime.date.today().isoformat()
STATE_F = D/f'rules_state_{LG}.json'
OFF_N, VAR_N, MONTH_N = 7, 30, 5   # Nov 9: 1/4 of a 30 game team season
I = dict(lg=0, se=1, d=2, h=3, a=4, hc=5, ac=6, cg=7, nu=8, hr=10, ar=11, hs=12, as_=13, vs=17, dko=18, dkc=19, dkto=20, dktc=21, s2o=22, s2c=23, s2to=24, s2tc=25, sp=26, tot=27, mlh=28, mla=29)
RAT_LAST = {}
p = D.parent/'data'/f'ratings_{LG.lower()}_2025-26.txt'
if p.exists():
    for tok in p.read_text().strip().split(';'):
        f = tok.split(','); RAT_LAST[f[0]] = float(f[1]) if f[1] not in ('undefined', '') else 0.0

def load():
    p = D/'season'/f'games_{LG}.txt'
    if not p.exists(): return []
    out = []
    for ln in p.read_text().strip().splitlines():
        r = json.loads(ln)
        g = {k: r[i] for k, i in I.items()}
        g.update(neutral=bool(g['nu']), o1=g['dko'], c1=g['dkc'], t1o=g['dkto'], t1c=g['dktc'], o2=g['s2o'], c2=g['s2c'], t2o=g['s2to'], t2c=g['s2tc'])
        if g['sp'] is not None and g['tot'] is not None: out.append(g)
    return sorted(out, key=lambda g: g['d'])

def srs(games):
    r = {}; gs = []
    for g in games:
        m = g['hs'] - g['as_'] - (0 if g['neutral'] else R.HCA); gs += [(g['h'], g['a'], m), (g['a'], g['h'], -m)]
    for _ in range(12):
        s, n = {}, {}
        for t, o, m in gs: s[t] = s.get(t, 0) + m + r.get(o, 0); n[t] = n.get(t, 0) + 1
        r = {t: s[t]/n[t] for t in s}; mu = sum(r.values())/max(1, len(r)); r = {t: v - mu for t, v in r.items()}
    return r

def two_red_months(months, today):
    """Two completed calendar months in a row in the red (5+ picks each), checked only after the first full week (Mon to Sun) of the next month."""
    t = datetime.date.fromisoformat(today); first = t.replace(day=1)
    mon = first + datetime.timedelta(days=(7 - first.weekday()) % 7)
    if t <= mon + datetime.timedelta(days=6): return ''
    def prev(d): return (d.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
    m1 = prev(first); m2 = prev(m1); a, b = months.get(m2.strftime('%Y%m')), months.get(m1.strftime('%Y%m'))
    if a and b and a['n'] >= MONTH_N and b['n'] >= MONTH_N and a['u'] < 0 and b['u'] < 0: return f"{m2.strftime('%b')} and {m1.strftime('%b')}"
    return ''

def run():
    G = load(); state = json.loads(STATE_F.read_text())
    rows = {(rid, v): [] for rid in R.RULES if R.RULES[rid].get('lg', LG) == LG for v in R.RULES[rid]['variants']}
    logs, done, rating, last_day = {}, [], {}, ''
    for g in G:
        if g['d'] != last_day: rating = srs(done); last_day = g['d']
        def ctx_t(t):
            L = logs.get(t, []); n = len(L); w = n/(n+8); rt = w*rating.get(t, 0) + (1-w)*RAT_LAST.get(t, 0)
            dd = (datetime.date(int(g['d'][:4]), int(g['d'][4:6]), int(g['d'][6:])) - L[-1][0]).days if L else None
            return rt, dd, (sum(1 for x in L[-5:] if x[1] > 0)/len(L[-5:]) if L else None), (sum(x[1] for x in L)/n if n else None), (L[-1][1] if L else None)
        rh, dh, fh, ah, lh = ctx_t(g['h']); ra, da, fa, aa, la = ctx_t(g['a'])
        S = R.signals(g, dict(proj=rh - ra + (0 if g['neutral'] else R.HCA), rest_h=dh, rest_a=da, form_h=fh, form_a=fa, avgm_h=ah, avgm_a=aa, lastm_h=lh, lastm_a=la))
        for rid in (R.RULES if T25.row_in_scope(g['hr'], g['ar'], LG) else []):
            if R.RULES[rid].get('lg', LG) != LG: continue
            for v in R.RULES[rid]['variants']:
                for c in R.candidates(g, S, {rid: dict(on=True, variant=v)}):
                    rows[(rid, v)].append((g['d'], R.grade(c, g), c['price']))
        m = g['hs'] - g['as_']; d = datetime.date(int(g['d'][:4]), int(g['d'][4:6]), int(g['d'][6:]))
        logs.setdefault(g['h'], []).append((d, m)); logs.setdefault(g['a'], []).append((d, -m)); done.append(g)
    # Efficiency rules from season/box_<LG>.txt (bt_build2.js rows: box scores plus open and close lines).
    # EARLY_* and EFF_* graded at the closing total (Trina, Nov 7 2026).
    import eff as EF
    bp = D/'season'/f'box_{LG}.txt'
    if bp.exists():
        _gp = D/'season'/f'games_{LG}.txt'; SCOPE = T25.scope_keys([json.loads(x) for x in _gp.read_text().strip().splitlines() if x.strip()], LG) if _gp.exists() else set()
        pri, plg = EF.load_prior(LG); B = sorted([json.loads(x) for x in bp.read_text().strip().splitlines() if x.strip()], key=lambda r: r[1]); done, day, cur = [], '', ({}, None, {})
        sg = lambda x: (x > 0) - (x < 0)
        for r in B:
            if r[1] != day: cur = EF.solve(done); day = r[1]
            if r[2] in pri and r[3] in pri and (LG not in T25.ON or (r[1], r[2], r[3]) in SCOPE):
                em, et, _, _ = EF.project(r[2], r[3], r[4] == 1, pri, plg, *cur); tot = r[6] + r[7]; m = r[6] - r[7]
                ot = r[18] if r[18] is not None else r[22]; early = int(r[1][4:6]) in (11, 12)
                add = lambda k, res: rows[(k, 'fixed')].append((r[1], res, -110)) if (k, 'fixed') in rows else None
                # Trina, Nov 7 2026: EARLY_* fire vs the opening total but grade at the closing total (DraftKings close), like the backtest.
                ct = r[25] if r[25] is not None else ot
                if early and ot is not None and et <= ot - 4: add('EARLY_UNDER_OPEN', sg(ct - tot))
                if early and ot is not None and et >= ot + 4: add('EARLY_OVER_OPEN', sg(tot - ct))
                if r[24] is not None and abs(em + r[24]) >= 3: add('EFF_SPREAD', sg(m + r[24]) if em + r[24] > 0 else sg(-m - r[24]))
                if r[25] is not None and et >= r[25] + 3: add('EFF_OVER', sg(tot - r[25]))
            if r[8] and r[12]: done.append(dict(h=r[2], a=r[3], nu=r[4] == 1, hs=r[6], as_=r[7], poss=(EF.poss(*r[8:12]) + EF.poss(*r[12:16]))/2))
    cut = (datetime.date.fromisoformat(TODAY) - datetime.timedelta(days=14)).strftime('%Y%m%d'); cm = TODAY[:7].replace('-', '')
    def summ(x): return R.summarize([(r, p) for _, r, p in x])
    REC = {k: dict(season=summ(v), month=summ([z for z in v if z[0][:6] == cm]), last14=summ([z for z in v if z[0] > cut]),
                   months={mm: summ([z for z in v if z[0][:6] == mm]) for mm in sorted({z[0][:6] for z in v})}) for k, v in rows.items()}
    log, warn = state.setdefault('log', []), []
    for rid, s in state['rules'].items():
        v = s['variant']; o = 'strict' if v == 'lowered' else 'lowered'; cur = REC[(rid, v)]; oth = REC.get((rid, o)) or dict(season=R.summarize([]), month=R.summarize([]))
        s['season'] = cur['season']; s['month'] = dict(cur['month'], label=TODAY[:7]); s['last14'] = cur['last14']
        if (rid, o) in REC: s['other'] = dict(variant=o, season=oth['season'])
        else: s.pop('other', None)
        # Nov 14 (B91, Trina A37/A39): rule on/off comes from the hub meta tier status records (tools rebuild_tiers.py); this re-check keeps
        # the every game records only. No rule level switches and no version switching.
        if state.get('policy', {}).get('gate') == 'tiers':
            if s['on'] and mon['n'] >= MONTH_N and mon['u'] < 0 if (mon := cur['month']) else False: warn.append(f"{rid} watch: month {mon['w']}-{mon['l']} {mon['u']:+.2f}u (watch only)")
            continue
        # Trina, Nov 3 2026: no automatic switches while a hold is in place (rule hold or whole-card freeze). Records still update.
        hold = max(s.get('hold_on_until', ''), state.get('freeze_until', ''))
        # Nov 8 2026: a hold or freeze ends on its own date; that day's run applies the policy (main session, Nov 8 run).
        if hold and TODAY < hold:
            if s.get('hold_on_until') and TODAY < s['hold_on_until']: s['on'] = True
            continue
        # NCAAW Option A (Trina, Nov 9 2026): the AP Top 25 three season backtest decides which rules are on, all season.
        # This season's record only warns. policy.gate = 'backtest', policy.backtest_on = the rules that passed.
        pol = state.get('policy', {})
        if pol.get('gate') == 'backtest':
            want = rid in pol.get('backtest_on', []); sea, mon = cur['season'], cur['month']
            if s['on'] != want:
                s['on'] = want; s['switched'] = dict(date=TODAY, to='on' if want else 'off', reason='backtest gate (Top 25, 3 seasons)')
                log.append(dict(date=TODAY, change=f"{rid} {'on' if want else 'off'}: backtest gate (Trina, Nov 9)"))
            if want and sea['n'] >= pol.get('off_min', OFF_N) and (sea['u'] < 0 or (mon['n'] >= pol.get('month_min', MONTH_N) and mon['u'] < 0)):
                warn.append(f"{rid} stays on by the backtest; this season {sea['w']}-{sea['l']} {sea['u']:+.2f}u, month {mon['w']}-{mon['l']} {mon['u']:+.2f}u")
            if not want and sea['n'] >= 5 and sea['u'] > 0 and (mon['n'] < pol.get('month_min', MONTH_N) or mon['u'] > 0):
                warn.append(f"{rid} stays off by the backtest though green this season ({sea['w']}-{sea['l']} {sea['u']:+.2f}u)")
            if s['on'] and cur['last14']['n'] >= 8 and cur['last14']['u'] < 0: warn.append(f"{rid} last 14 days {cur['last14']['w']}-{cur['last14']['l']}, {cur['last14']['u']:+.2f}u")
            continue
        # Season Cards rule status policy (Trina, Nov 9 2026): season to date decides; the month is a watch; two red months in a row
        # switch a rule off after the first full week of the next month. Pick minimum policy.off_min (7 for NCAAW).
        pol = state.get('policy', {}); OFFM, MONM = pol.get('off_min', OFF_N), pol.get('month_min', MONTH_N)
        sea, mon = cur['season'], cur['month']; two = two_red_months(cur.get('months') or {}, TODAY)
        if s['on'] and ((sea['n'] >= OFFM and sea['u'] < 0) or two):
            s['on'] = False; s['auto_off'] = True; s['switched'] = dict(date=TODAY, to='off', season=f"{sea['w']}-{sea['l']}-{sea['p']} {sea['u']:+.2f}u", reason=('two red months ' + two) if two else 'season red')
            log.append(dict(date=TODAY, change=f"{rid} off: season {sea['w']}-{sea['l']} {sea['u']:+.2f}u" + (f", two red months {two}" if two else '')))
        elif not s['on'] and sea['u'] > 0 and not two:
            s['on'] = True; s['auto_off'] = False; s['switched'] = dict(date=TODAY, to='on', season=f"{sea['w']}-{sea['l']}-{sea['p']} {sea['u']:+.2f}u")
            log.append(dict(date=TODAY, change=f"{rid} on (season green): season {sea['w']}-{sea['l']} {sea['u']:+.2f}u"))
        if s['on'] and mon['n'] >= MONM and mon['u'] < 0: warn.append(f"{rid} watch: month {mon['w']}-{mon['l']} {mon['u']:+.2f}u (month is a watch only)")
        if (rid, o) in REC and cur['season']['n'] >= VAR_N and oth['season']['u'] > cur['season']['u'] and oth['month']['n'] >= MONTH_N and oth['month']['u'] > cur['month']['u']:
            s['variant'] = o; log.append(dict(date=TODAY, change=f"{rid} moved to {o}: season {oth['season']['u']:+.2f}u vs {cur['season']['u']:+.2f}u, month {oth['month']['u']:+.2f}u vs {cur['month']['u']:+.2f}u"))
        if s['on'] and cur['last14']['n'] >= 8 and cur['last14']['u'] < 0: warn.append(f"{rid} last 14 days {cur['last14']['w']}-{cur['last14']['l']}, {cur['last14']['u']:+.2f}u")
    state['updated'] = TODAY; state['warnings'] = warn
    state['recheck_note'] = f"{len(G)} games played this season through {TODAY}." if G else 'Runs daily from the first graded slate. Nothing has been played yet.'
    STATE_F.write_text(json.dumps(state, indent=1))
    md = [f"# {('NCAAM' if LG == 'M' else 'NCAAW')} re-check {TODAY}", f"{len(G)} games played this season.", '', '| Rule | Variant | W | L | P | Win % | Units | Last 14 |', '|---|---|---|---|---|---|---|---|']
    for (rid, v), x in REC.items():
        s = x['season']; md.append(f"| {rid} | {v} | {s['w']} | {s['l']} | {s['p']} | {'' if s['pct'] is None else f"{100*s['pct']:.1f}%"} | {s['u']:+.2f} | {x['last14']['u']:+.2f} |")
    md += ['', 'Warnings:'] + [f"- {w}" for w in warn]
    (D/f'recheck_report_{LG}.md').write_text('\n'.join(md))
    print(f"{LG}: {len(G)} games; switches today: {[l for l in log if l['date']==TODAY]}; warnings: {warn}")

if __name__ == '__main__': run()
