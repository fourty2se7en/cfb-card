"""Daily re-check for the NCAA cards. Usage: python3 recheck.py M|W [today YYYY-MM-DD]
Reads season/games_<lg>.txt (one line per game played this season, same row format as the backtest: bt_build.js),
reruns every rule family (both variants) on every game played, season to date, by month and over the last 14 days,
applies the automatic switches and writes rules_state_<lg>.json and recheck_report_<lg>.md. The backtest stays a separate baseline.
Switches (automatic):
  - a live rule goes off at 20+ season picks with negative units, and back on when its season units turn positive;
  - a rule moves to its other variant only after 30+ picks, when the other variant has more units season to date AND this month (5+ picks).
  - Season Cards policy (Nov 9, 2026, replaces Nov 6): season to date decides. Off at 20+ picks when season is negative; back on when season is
    green. The month is a watch only. Two completed red months in a row (5+ picks each) switch a rule off after the first full week of the next month.
  - UNDER_DROP band variant (Nov 9): drop 4.5 to 6.5 at both books; it never auto-moves to another variant.
Any other rule change is shown to Trina with the numbers and waits for her OK."""
import json, sys, pathlib, datetime
import rules as R
D = pathlib.Path(__file__).parent
LG = sys.argv[1] if len(sys.argv) > 1 else 'M'
TODAY = sys.argv[2] if len(sys.argv) > 2 else datetime.date.today().isoformat()
STATE_F = D/f'rules_state_{LG}.json'
OFF_N, VAR_N, MONTH_N = 7, 30, 5   # Trina Nov 9: pick minimum = 1/4 of a 31 game team season (was 20)
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
    """Trina, Nov 9: two completed calendar months in a row in the red (5+ picks each) switch a rule off, but only once the
    first full week (Monday to Sunday) of the following month is over. months: {'YYYYMM': summary}. Returns 'Oct and Nov' or ''."""
    import datetime as _dt
    t = _dt.date(int(today[:4]), int(today[4:6]) if len(today) == 8 else int(today[5:7]), int(today[-2:]))
    first = t.replace(day=1); mon = first + _dt.timedelta(days=(7 - first.weekday()) % 7); end_week = mon + _dt.timedelta(days=6)
    if t <= end_week: return ''
    def prev(d): return (d.replace(day=1) - _dt.timedelta(days=1)).replace(day=1)
    m1 = prev(first); m2 = prev(m1)
    a, b = months.get(m2.strftime('%Y%m')), months.get(m1.strftime('%Y%m'))
    if a and b and a['n'] >= MONTH_N and b['n'] >= MONTH_N and a['u'] < 0 and b['u'] < 0:
        return f"{m2.strftime('%b')} and {m1.strftime('%b')}"
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
        for rid in R.RULES:
            if R.RULES[rid].get('lg', LG) != LG: continue
            for v in R.RULES[rid]['variants']:
                for c in R.candidates(g, S, {rid: dict(on=True, variant=v)}):
                    rows[(rid, v)].append((g['d'], R.grade(c, g), c['price']))
        m = g['hs'] - g['as_']; d = datetime.date(int(g['d'][:4]), int(g['d'][4:6]), int(g['d'][6:]))
        logs.setdefault(g['h'], []).append((d, m)); logs.setdefault(g['a'], []).append((d, -m)); done.append(g)
    # Efficiency rules from season/box_<LG>.txt (bt_build2.js rows: box scores plus open and close lines).
    # Every rule graded at the closing line, EARLY_* included (Trina, Nov 7, 2026; before that EARLY_* graded at the opener).
    import eff as EF
    bp = D/'season'/f'box_{LG}.txt'
    if bp.exists():
        pri, plg = EF.load_prior(LG); B = sorted([json.loads(x) for x in bp.read_text().strip().splitlines() if x.strip()], key=lambda r: r[1]); done, day, cur = [], '', ({}, None, {})
        sg = lambda x: (x > 0) - (x < 0)
        for r in B:
            if r[1] != day: cur = EF.solve(done); day = r[1]
            if r[2] in pri and r[3] in pri:
                em, et, _, _ = EF.project(r[2], r[3], r[4] == 1, pri, plg, *cur); tot = r[6] + r[7]; m = r[6] - r[7]
                ot = r[18] if r[18] is not None else r[22]; early = int(r[1][4:6]) in (11, 12)
                add = lambda k, res: rows[(k, 'lowered')].append((r[1], res, -110)) if (k, 'lowered') in rows else None
                if early and ot is not None and r[25] is not None and et <= ot - 4: add('EARLY_UNDER_OPEN', sg(r[25] - tot))
                if early and ot is not None and r[25] is not None and et >= ot + 4: add('EARLY_OVER_OPEN', sg(tot - r[25]))
                if r[24] is not None and abs(em + r[24]) >= 3: add('EFF_SPREAD', sg(m + r[24]) if em + r[24] > 0 else sg(-m - r[24]))
                if r[25] is not None and et >= r[25] + 3: add('EFF_OVER', sg(tot - r[25]))
            if r[8] and r[12]: done.append(dict(h=r[2], a=r[3], nu=r[4] == 1, hs=r[6], as_=r[7], poss=(EF.poss(*r[8:12]) + EF.poss(*r[12:16]))/2))
    cut = (datetime.date.fromisoformat(TODAY) - datetime.timedelta(days=14)).strftime('%Y%m%d'); cm = TODAY[:7].replace('-', '')
    def summ(x): return R.summarize([(r, p) for _, r, p in x])
    REC = {k: dict(season=summ(v), month=summ([z for z in v if z[0][:6] == cm]), last14=summ([z for z in v if z[0] > cut]),
                   months={mm: summ([z for z in v if z[0][:6] == mm]) for mm in sorted({z[0][:6] for z in v})}) for k, v in rows.items()}
    log, warn = state.setdefault('log', []), []
    for rid, s in state['rules'].items():
        v = s['variant']; o = 'strict' if v == 'lowered' else 'lowered';   # band (UNDER_DROP, Nov 9) compares with lowered and never auto-moves
        if v == 'band': o = 'lowered'
        cur = REC[(rid, v)]; oth = REC.get((rid, o)) or dict(season=R.summarize([]), month=R.summarize([]))
        s['season'] = cur['season']; s['month'] = cur['month']; s['last14'] = cur['last14']; s['other'] = dict(variant=o, season=oth['season'])
        # Trina, Nov 3 2026: no automatic switches while a hold is in place (rule hold or whole-card freeze). Records still update.
        hold = max(s.get('hold_on_until', ''), state.get('freeze_until', ''))
        if hold and TODAY <= hold:
            if s.get('hold_on_until') and TODAY <= s['hold_on_until']: s['on'] = True
            continue
        # Season Cards rule status policy (Trina, Nov 9, 2026, replaces the Nov 6 month test): season to date decides.
        # Off at 20+ season picks with negative season units. The current month is a watch only. Two completed months in a
        # row in the red (5+ picks each) also turn a rule off, but only after the first full week (Mon to Sun) of the next month.
        # On when season units are green and the two month condition is not active.
        su, mo = cur['season']['u'], cur['month']
        month_bad = mo['n'] >= MONTH_N and mo['u'] < 0
        two_red = two_red_months(cur.get('months') or {}, TODAY)
        rec_txt = f"{cur['season']['w']}-{cur['season']['l']}" + (f"-{cur['season']['p']}" if cur['season']['p'] else '') + f", {su:+.2f}u"
        if s['on'] and ((cur['season']['n'] >= OFF_N and su < 0) or two_red):
            s['on'] = False; s['auto_off'] = True; s['switched'] = dict(date=TODAY, to='off', record=rec_txt + (f", two red months {two_red}" if two_red else ''))
            log.append(dict(date=TODAY, change=f"{rid} off: season {rec_txt}" + (f", two red months {two_red}" if two_red else '')))
        elif not s['on'] and su > 0 and not two_red:
            s['on'] = True; s['auto_off'] = False; s['switched'] = dict(date=TODAY, to='on', record=rec_txt)
            if not s.get('since') or s['since'] < TODAY: s['since'] = TODAY
            log.append(dict(date=TODAY, change=f"{rid} on (season green): season {rec_txt}"))
        if s['on'] and month_bad: warn.append(f"{rid} watch: this month {mo['w']}-{mo['l']}, {mo['u']:+.2f}u (month is a watch only)")
        if v != 'band' and (rid, o) in REC and cur['season']['n'] >= VAR_N and oth['season']['u'] > cur['season']['u'] and oth['month']['n'] >= MONTH_N and oth['month']['u'] > cur['month']['u']:
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
