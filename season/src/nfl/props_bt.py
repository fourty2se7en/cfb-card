"""Walk-forward prop backtest on every stored prop line (hist/props_lines.csv: DraftKings, weeks 1 on).
For each line the model sees only games before that week (this season) plus all of last season, the same
props_rules.evaluate the live card uses, and the market spread and total for the game script. Graded from nflverse
player stats. A player with no stat line who logged offensive snaps that week (nflverse snap counts) played and is
graded on 0 yards; one with no snaps did not play and is dropped (a push live). Fixed Nov 3: before, every player
with no stat line was dropped, which lost real results (Sam Roush, 37 snaps, 0 yards, under 10.5).
Writes hist/props_bt.csv and prints the record of every category-tier (season, by month, last 3 weeks).
Not modelled here: the live guard that holds back a prop opposing the card's total pick, and the injury report."""
import sys, json, pathlib
import numpy as np, pandas as pd, nflreadpy as nfl
import props_rules as PRR
from rules import week_months, rec_text

D = pathlib.Path(__file__).parent
SEASON = 2026

def run(out=print):
    L = pd.read_csv(D/'hist/props_lines.csv')
    sch = nfl.load_schedules([SEASON]).to_pandas()
    ps = nfl.load_player_stats([SEASON-1, SEASON]).to_pandas().dropna(subset=['player_display_name'])
    ps['_pn'] = ps.player_display_name.map(PRR.pnorm)
    ps = ps[(ps.season == SEASON-1) | ((ps.season == SEASON) & (ps.season_type == 'REG') if 'season_type' in ps else (ps.season == SEASON))]
    sn = nfl.load_snap_counts([SEASON]).to_pandas(); sn['pn'] = sn.player.map(PRR.pnorm)
    PLAYED = {(r.pn, r.team, int(r.week)) for r in sn[sn.offense_snaps.fillna(0) > 0].itertuples()}
    done = sch[sch.home_score.notna()]
    # team points per game before each week (this season)
    rows = []
    for _, g in done.iterrows():
        rows += [(g.week, g.home_team, g.home_score), (g.week, g.away_team, g.away_score)]
    TP = pd.DataFrame(rows, columns=['week', 'team', 'pts'])
    def ppg(t, w):
        x = TP[(TP.team == t) & (TP.week < w)].pts
        return float(x.mean()) if len(x) else 22.0
    G = {(r.week, r.away_team, r.home_team): r for r in sch.itertuples()}
    res = []
    for r in L.itertuples():
        g = G.get((r.week, r.away, r.home))
        if g is None or g.home_score != g.home_score: continue        # unplayed
        nm = PRR.pnorm(r.player)
        best = None; team = None
        for t in (r.away, r.home):                                     # most recent team before this week
            q = ps[(ps._pn == nm) & (ps.team == t) & ((ps.season < SEASON) | (ps.week < r.week))].sort_values(['season', 'week'])
            if len(q):
                lk = tuple(q[['season', 'week']].iloc[-1])
                if best is None or lk > best[0]: best, team = (lk, q), t
        if best is None: continue
        q = best[1]; col = PRR.COL[r.stat]
        cur = q[q.season == SEASON][col].fillna(0).values; prev = q[q.season == SEASON-1][col].fillna(0).values
        allv = q[col].fillna(0).values[-17:]
        spread_h = -float(g.spread_line); total = float(g.total_line); is_h = team == r.home
        imp = total/2 + (-spread_h/2 if is_h else spread_h/2); fav = -(spread_h if is_h else -spread_h)
        e = PRR.evaluate(cur, prev, allv, r.stat, r.line, int(r.po), int(r.pu), imp, ppg(team, r.week), fav)
        act = ps[(ps._pn == nm) & (ps.season == SEASON) & (ps.week == r.week)]
        if len(act): v = float(act[col].fillna(0).sum())
        elif (nm, team, int(r.week)) in PLAYED: v = 0.0               # played, no stat line: 0 yards
        else: continue                                                # did not play
        rr = 0 if v == r.line else (1 if (v > r.line) == (e['side'] == 'Over') else -1)
        res.append(dict(week=r.week, game=f'{r.away} @ {r.home}', player=r.player, team=team, stat=r.stat, line=r.line, side=e['side'],
                        price=e['price'], tier=e['tier'], edge=round(e['edge'], 2), n=e['n'], proj=e['proj'], actual=v, res=rr))
    B = pd.DataFrame(res); B.to_csv(D/'hist/props_bt.csv', index=False)
    MW = week_months(sch); last_w = int(B.week.max()); last3 = {last_w, last_w-1, last_w-2}
    recs = PRR.records(B.to_dict('records'), MW, last3)
    out(f'Prop backtest: {len(B)} graded lines, weeks {int(B.week.min())}-{last_w}, {int(B.tier.notna().sum())} picks (PLAY or LEAN)')
    months = list(dict.fromkeys(MW.values()))
    out('category | tier | season | win% vs BE | ' + ' | '.join(months) + ' | last 3 wks')
    for c in PRR.CATS:
        for t in PRR.TIERS:
            gr = recs[c][t]; s = gr['season']
            pct = f"{100*s['pct']:.1f}% vs {100*s['be']:.1f}%" if s['n'] and s['W']+s['L'] else '-'
            out(f"{c} | {t} | {rec_text(gr)} | {pct} | " + ' | '.join(rec_text(gr['months'][m]) if gr['months'][m]['n'] else '-' for m in months)
                + f" | {rec_text(gr['last3']) if gr['last3']['n'] else '-'}" + (' | QUALIFIES' if gr['qualifies'] else ''))
    return B, recs, MW, last3

if __name__ == '__main__' and '--recheck' not in sys.argv:
    run()

def recheck(apply=False, today=None, out=print):
    """Weekly prop re-check (runs with recheck.py after Monday night's game): rerun the backtest on every stored
    line, then switch rules per props_rules.switch. --apply writes signals.json prop_rules and hist/props_recheck.json."""
    import datetime as dt
    B, recs, MW, last3 = run(out)
    SIG = json.load(open(D/'signals.json'))
    PR = SIG.get('prop_rules') or PRR.default_rules()
    today = today or dt.date.today().isoformat()
    changes = PRR.switch(PR, recs, today)
    PR['records'] = recs; PR['last_recheck'] = today; PR['last3_weeks'] = sorted(last3); PR['n_lines'] = int(len(B))
    out('\nChanges: ' + ('; '.join(changes) if changes else 'none'))
    out('Watch: ' + ('; '.join(f'{k}: {v}' for k, v in PR['flags'].items()) if PR['flags'] else 'none'))
    out('On (shown on the card): ' + ', '.join(f'{c} {t}' for c in PRR.CATS for t in PRR.TIERS if PR['cats'][c][t]['on']))
    if apply:
        SIG['prop_rules'] = PR; json.dump(SIG, open(D/'signals.json', 'w'), indent=1)
        json.dump(dict(records=recs, months=list(dict.fromkeys(MW.values())), last3=sorted(last3), flags=PR['flags'], changes=changes, date=today, n_lines=int(len(B))),
                  open(D/'hist/props_recheck.json', 'w'), indent=1, default=float)
    return PR, changes

if __name__ == '__main__' and '--recheck' in sys.argv:
    recheck(apply='--apply' in sys.argv)
