"""End-of-week re-check for the NFL card's pick rules. Runs after Monday night's game, before Thursday's kickoff
(inside the first "Run NFL Card" after Monday night).
  python3 recheck.py           dry run: every test, the rule records and what would change
  python3 recheck.py --apply   also writes the rule state to signals.json and hist/recheck.json (read by the card's Results tab)

Games: hist/games.csv (weeks 1-7, rebuilt Oct 29) + hist/rebuilt.csv (games missing from snap.csv, rebuilt by hist/build_hist.py:
CAR@GB, Oct 29) + hist/openers2.csv (Action Network and DraftKings openers) + hist/snap.csv (each later game's pre-kickoff read and
its game-day morning line, written by model.py). Wind gaps are filled from snap.csv wx_wind (game-day forecast), then
hist/wx_archive.txt (Open-Meteo observed, weeks 5-8), same as the Nov 7 backtest.
Rules are graded in card order (Trina, Nov 6): side fav_ml, spread, dog_ml, dog_spread; total total_one_sided, over. Each rule's
record is what it gets in that order with every other rule at its current state and this one on, so off rules keep a record.
Switching (Trina, Nov 9 policy, hub meta nfl): season to date decides. A rule switches off when its season units are negative once
it has the league pick minimum (NFL 4 graded picks, one quarter of a 17 game season) and back on when its season units are green
(same minimum). The current month is a watch only (a red month on 5+ picks is reported, never switches). Two completed months in a
row in the red (5+ picks each) switch a rule off after the first full Monday to Sunday week of the next month (first check Dec 14). Finals, closing spreads, totals and their
prices come from nflverse. Moneylines: the cleaned closing median (quotes under 100 or over 5000 dropped, median in decimal odds):
the 8-book Sportsbook Review median for weeks 1-7, nflverse plus DraftKings close after that.
Evaluation (Trina, Oct 30): season to date, one column per month, last 3 weeks as an early warning. A method qualifies at
5+ picks with positive units and a win % above break-even. Scoring, rules and grading come from rules.py, the code the card runs."""
import sys, json, math, copy, datetime as dt, pathlib
import numpy as np, pandas as pd, nflreadpy as nfl
import rules as RU
D = pathlib.Path(__file__).parent; H = D/'hist'
APPLY = '--apply' in sys.argv
RECORDS_ONLY = '--records-only' in sys.argv   # write records and test tables now, switch nothing (used on Oct 30, before the first real re-check)
SIG = RU.load_sig(); RULES = SIG['rules']
sched = nfl.load_schedules([2025, 2026]).to_pandas(); LOG = RU.build_log(sched)
s26 = sched[(sched.season == 2026) & (sched.game_type == 'REG')].copy(); s26['game'] = s26.away_team + '@' + s26.home_team
FIN = {(int(r.week), r.game): r for r in s26[s26.result.notna()].itertuples()}
MW = RU.week_months(sched)

def dk_close():
    out = {}
    p = H/'dk_parts.txt'
    if not p.exists(): return out
    for it in ''.join(p.read_text().split('\n')).split(';'):
        q = it.split(' ')
        while len(q) < 14: q.append('')
        try: out[(int(q[0]), q[1])] = (float(q[8]), float(q[9]))
        except ValueError: pass
    return out
def clean_median(quotes):
    q = [m for m in quotes if m is not None and not pd.isna(m) and 100 <= abs(m) <= 5000]
    if not q: return None
    d = float(np.median([RU.dec(m) for m in q]))
    return round((d-1)*100) if d >= 2 else round(-100/(d-1))

def wx_archive():
    out = {}
    p = H/'wx_archive.txt'
    if not p.exists(): return out
    for it in p.read_text().strip().split(';'):
        q = it.strip().split(' ')
        if len(q) == 5: out[(int(q[0]), q[1])] = (float(q[2]), float(q[3]))
    return out

def games():
    T = pd.read_csv(H/'games.csv')
    if (H/'rebuilt.csv').exists():
        B = pd.read_csv(H/'rebuilt.csv'); T = pd.concat([T, B[~B.set_index(['week', 'game']).index.isin(T.set_index(['week', 'game']).index)]], ignore_index=True)
    T = T.merge(pd.read_csv(H/'openers2.csv'), on=['week', 'game'], how='left')
    if (H/'snap.csv').exists():
        N = pd.read_csv(H/'snap.csv')
        N = N[~N.set_index(['week', 'game']).index.isin(T.set_index(['week', 'game']).index)]
        T = pd.concat([T, N], ignore_index=True)
    DK = dk_close(); WX = wx_archive(); rows = []
    for _, r in T.iterrows():
        f = FIN.get((int(r.week), r.game))
        if f is None: continue
        r = r.copy()
        if pd.isna(r.get('wind')):
            if not pd.isna(r.get('wx_wind')): r['wind'] = r['wx_wind']
            elif (int(r.week), r.game) in WX: r['wind'] = WX[(int(r.week), r.game)][1]
        r['away_score'], r['home_score'] = f.away_score, f.home_score
        r['spread_h'], r['total'] = -f.spread_line, f.total_line
        r['sp_price_a'], r['sp_price_h'], r['over_price'], r['under_price'] = f.away_spread_odds, f.home_spread_odds, f.over_odds, f.under_odds
        if pd.isna(r.get('sbr_ml_a')):
            dka, dkh = DK.get((int(r.week), r.game), (None, None))
            r['ml_a'], r['ml_h'] = clean_median([f.away_moneyline, dka]), clean_median([f.home_moneyline, dkh])
        rows.append(r)
    return pd.DataFrame(rows)

def morning(T):
    """Game-day morning lines: the old card's ledger for weeks 1-7, model.py's first game-day read (m_* columns) after that.
    Spreads and totals grade at -110 at pick time; the moneyline band uses the morning price, graded at the close."""
    lp = H/'ledger_history.csv'   # copy of the retired repo's scripts/ledger_history.csv (weeks 1-7 morning lines)
    L = pd.read_csv(lp if lp.exists() else D.parent/'nfl-card'/'scripts'/'ledger_history.csv'); L['taken'] = pd.to_datetime(L.taken, utc=True)
    s = s26.copy(); s['kick'] = pd.to_datetime(s.gameday + ' ' + s.gametime).dt.tz_localize('America/New_York').dt.tz_convert('UTC')
    K = {(int(r.week), r.game): (r.kick, pd.Timestamp(r.gameday).date()) for r in s.itertuples()}
    T = T.copy(); used = 0
    am = lambda q: -100*q/(1-q) if q >= .5 else 100*(1-q)/q
    for i, r in T.iterrows():
        if not pd.isna(r.get('m_spread_h')):
            T.at[i, 'spread_h'], T.at[i, 'total'] = r.m_spread_h, r.m_total
            T.at[i, 'm_ml_a'], T.at[i, 'm_ml_h'] = r.get('m_ml_a'), r.get('m_ml_h')
        else:
            k = K.get((int(r.week), r.game))
            x = L[(L.week == r.week) & (L.game == r.game) & (L.taken < k[0])] if k else L.iloc[:0]
            if not len(x): continue
            day = x[x.taken.dt.tz_convert('America/Phoenix').dt.date == k[1]]
            pk = (day.sort_values('taken').groupby('market').head(1) if len(day) else x.sort_values('taken').groupby('market').tail(1)).set_index('market')
            if 'Spread' in pk.index: T.at[i, 'spread_h'] = -float(pk.loc['Spread', 'market_num'])
            if 'Total' in pk.index: T.at[i, 'total'] = float(pk.loc['Total', 'market_num'])
            if 'Moneyline' in pk.index:
                p = float(pk.loc['Moneyline', 'market_num'])/100; team = RU.M.canon_team(str(pk.loc['Moneyline', 'pick']).split(' ')[0])
                ph = p if team == r.home else 1 - p; T.at[i, 'm_ml_h'], T.at[i, 'm_ml_a'] = am(ph), am(1 - ph)
        if not pd.isna(T.at[i, 'm_ml_h']): T.at[i, 'band_ml_h'], T.at[i, 'band_ml_a'] = T.at[i, 'm_ml_h'], T.at[i, 'm_ml_a']
        T.at[i, 'sp_price_a'] = T.at[i, 'sp_price_h'] = T.at[i, 'over_price'] = T.at[i, 'under_price'] = -110
        used += 1
    return T, used

def recs(G, rules_, last3):
    r_, _ = RU.rule_records(G, rules_, MW, last3); return r_
def card(G, rules_, rid, last3, version=None):
    return RU.card_order_record(G, rules_, rid, MW, last3, version)
def forced_on(rules_):
    x = copy.deepcopy(rules_)
    for r_ in x['side'] + x['total']: r_['on'] = True
    return x
def with_version(rules_, grp, i, v):
    x = forced_on(rules_); x[grp][i]['version'] = v; return x

if __name__ == '__main__':
    T = games(); weeks = sorted(T.week.unique()); last3 = set(weeks[-3:])
    G = RU.score_all(T, LOG, SIG)
    cur_month = MW[max(weeks)]
    print(f'{len(G)} games played, weeks {min(weeks)}-{max(weeks)}; months {sorted(set(MW[w] for w in weeks), key=list(MW.values()).index)}; last 3 weeks {sorted(last3)}')
    lines = []
    groups = RU.run_tests(G, {w: MW[w] for w in weeks}, last3, out=lambda s_: (print(s_), lines.append(s_)))
    (H/'recheck_report.txt').write_text('\n'.join(lines))
    # rule state: each rule's current version, its other version, and the pick-time (morning line) check
    TM, used = morning(T); GM = RU.score_all(TM, LOG, SIG)
    changes, warns, state = [], [], {}
    POL = RULES.get('policy', {}); OFF_MIN = POL.get('off_min', 4); MONTH_MIN = POL.get('month_min', 5)
    TWO_RED_FROM = POL.get('two_red_months_from', '2026-12-14')
    def two_red(gr):
        # two completed calendar months in a row in the red (5+ picks each); applies only after the first full week of the next month
        if dt.date.today().isoformat() < TWO_RED_FROM: return None
        done = [m for m in sorted(gr['months'], key=list(MW.values()).index) if m != cur_month]
        if len(done) < 2: return None
        a, b = gr['months'][done[-2]], gr['months'][done[-1]]
        if a['n'] >= MONTH_MIN and b['n'] >= MONTH_MIN and a['units'] < 0 and b['units'] < 0: return f"{done[-2]} {RU.rec_text(a)}, {done[-1]} {RU.rec_text(b)}"
        return None
    snap = copy.deepcopy(RULES)   # every rule is judged against the state at the start of the run
    print(f"\n## Rule records in card order (pick-time check on {used} games' morning lines)")
    for grp in ('side', 'total'):
        for i, rule in enumerate(RULES[grp]):
            v = rule['version']; other = 'strict' if v == 'lowered' else 'lowered'
            gr = card(G, snap, rule['id'], last3); go = card(G, snap, rule['id'], last3, other); gm = card(GM, snap, rule['id'], last3)
            s_, so = gr['season'], go['season']
            print(f"{rule['id']:16s} {v:8s} {RU.rec_text(gr):18s} {'Q' if gr['qualifies'] else ' '} | {other} {RU.rec_text(go):18s} | morning {RU.rec_text(gm):18s} | {'on' if rule.get('on', True) else 'OFF'}")
            state[rule['id']] = dict(version=v, current=gr, other_version=other, other=go, morning=gm)
            mc = gr['months'].get(cur_month, {'units': 0, 'n': 0})
            month_red = mc['n'] >= MONTH_MIN and mc['units'] < 0   # watch only (Nov 9 policy)
            tr = two_red(gr)
            if RECORDS_ONLY: pass
            elif rule.get('on', True) and ((s_['n'] >= OFF_MIN and s_['units'] < 0) or tr):
                rule['on'] = False; rule['off_by_recheck'] = True
                changes.append(f"{rule['id']} switched off: season {RU.rec_text(gr)}" + (f", two red months ({tr})" if tr else ''))
            elif not rule.get('on', True) and s_['n'] >= OFF_MIN and s_['units'] > 0 and not tr:
                rule['on'] = True; rule.pop('off_by_recheck', None); changes.append(f"{rule['id']} switched on: season {RU.rec_text(gr)}" + (f", {cur_month} {RU.cell(mc)} (watch)" if mc['n'] else ''))
            if month_red: warns.append(f"Watch: {rule['id']} is red in {cur_month} on {mc['n']} picks ({RU.rec_text(mc)})")
            mo = go['months'].get(cur_month, {'units': 0, 'n': 0})
            would = (s_['n'] >= max(OFF_MIN, POL.get('version_min', 30)) and so['n'] and so['pct'] >= s_['pct'] and so['units'] > s_['units'] and so['units'] > 0 and mo['n'] and mo['units'] > 0)
            if would and RECORDS_ONLY: warns.append(f"{rule['id']} will move {v} -> {other} at the next re-check: {RU.rec_text(go)} vs {RU.rec_text(gr)}")
            if not RECORDS_ONLY and would:
                changes.append(f"{rule['id']} moved {v} -> {other}: {RU.rec_text(gr)} ({s_['pct']*100:.1f}%) -> {RU.rec_text(go)} ({so['pct']*100:.1f}%), {cur_month} {RU.rec_text(mo)}")
                rule['version'] = other
            if not gr['qualifies']: warns.append(f"{rule['id']} does not qualify season to date ({RU.rec_text(gr)})")
            if gr['last3']['n'] and gr['last3']['units'] < 0: warns.append(f"{rule['id']} is negative over the last 3 weeks ({RU.rec_text(gr['last3'])})")
            if not gm['qualifies']: warns.append(f"{rule['id']} fails the pick-time check on morning lines ({RU.rec_text(gm)})")
    final = {r_['id']: card(G, RULES, r_['id'], last3) for r_ in RULES['side'] + RULES['total']}
    final_m = {r_['id']: card(GM, RULES, r_['id'], last3) for r_ in RULES['side'] + RULES['total']}
    print('\n## Changes:', changes or 'none'); print('## Warnings:', warns or 'none')
    def pack(gr): return dict(text=RU.rec_text(gr), W=gr['season']['W'], L=gr['season']['L'], P=gr['season']['P'], units=round(gr['season']['units'], 2),
                              pct=round(gr['season']['pct'], 4) if gr['season']['W'] + gr['season']['L'] else None, be=gr['season']['be'],
                              months={m: RU.cell(x) for m, x in gr['months'].items() if x['n']},
                              month_detail={m: dict(W=x['W'], L=x['L'], P=x['P'], units=round(x['units'], 2)) for m, x in gr['months'].items() if x['n']},
                              last3=RU.cell(gr['last3']), qualifies=gr['qualifies'], warn=gr['warn'])
    records = {}
    for grp in ('side', 'total'):
        for rule in RULES[grp]:
            k = rule['id']; st = state[k]
            records[k] = dict(pack(final[k]), on=bool(rule.get('on', True)), graded='card order', version=rule['version'], morning=RU.rec_text(final_m[k]), morning_q=final_m[k]['qualifies'],
                              other_version=('strict' if rule['version'] == 'lowered' else 'lowered'), other=RU.rec_text(st['other']), through_week=int(max(weeks)))
    for k, v in records.items(): print(f"  {k} ({v['version']}): {v['text']} | {v['months']} | last 3 wk {v['last3']} | morning {v['morning']}")
    if APPLY or RECORDS_ONLY:
        utc = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
        RULES['records'] = records
        RULES['last_recheck'] = dict(utc=utc, games=len(G), through_week=int(max(weeks)), months=sorted(set(MW[w] for w in weeks), key=list(MW.values()).index), last3=sorted(int(w) for w in last3))
        for c in ([] if RECORDS_ONLY else changes): RULES['changelog'].append(dict(date=dt.date.today().isoformat(), change=c))
        RULES['warnings'] = warns
        SIG['rules'] = RULES; (D/'signals.json').write_text(json.dumps(SIG, indent=1))
        def js(o):
            if isinstance(o, dict): return {k: js(v) for k, v in o.items()}
            if isinstance(o, (list, tuple)): return [js(v) for v in o]
            if isinstance(o, float) and math.isnan(o): return None
            if isinstance(o, (np.integer,)): return int(o)
            if isinstance(o, (np.floating,)): return float(o)
            return o
        (H/'recheck.json').write_text(json.dumps(js(dict(utc=utc, through_week=int(max(weeks)), games=len(G), months=RULES['last_recheck']['months'],
                                                        last3=RULES['last_recheck']['last3'], changes=([] if RECORDS_ONLY else changes), warnings=warns, groups=groups)), indent=0))
        print('signals.json and hist/recheck.json updated')

# Player prop rules (Trina, Nov 2): rerun the walk-forward prop backtest on every stored DraftKings line and switch
# prop rules on or off on their season record (props_rules.switch). Runs after the game rules, same --apply flag.
if __name__ == '__main__' and '--no-props' not in sys.argv:
    import props_bt
    print('\n=== Prop rules re-check ===')
    props_bt.recheck(apply=APPLY)
