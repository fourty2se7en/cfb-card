"""FBS vs FCS deep dive (Trina, Nov 9 2026). The FCS card is retired; FBS vs FCS games stay on the FBS card with a full look at the
FCS opponent, which no other part of the card tracks.

Usage: python3 fcs_dive.py <YYYY-MM-DD from> <YYYY-MM-DD to>   (run after model.py fbs; reads repo/ and hist/, writes fcs_dive.json)
Optional browser pull (fcs_dive_pull.js, ESPN): fcs_espn.json {team: {qb, qb_line, rb, wr, injuries:[...], fcs_rank_note}}.

Output per game (keyed by the CFBD/ESPN game id): notes (one line facts for the game card), deep_dive (structured), against/for items
for the side reasons. Picks: none. The FBS rules were never tested on FBS vs FCS games and 2017-2025 shows no stable edge
(FBS 423-444 against the closing spread), so these games show No pick with the deep dive. Every number comes from the repo data
or the browser pull; a missing value is left out."""
import json, sys, re
from pathlib import Path
import pandas as pd
import numpy as np

D = Path(__file__).parent; R = D / 'repo'
FROM, TO = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else (None, None)
GM = pd.read_csv(R / 'games.csv'); GM['dt'] = pd.to_datetime(GM.startDate, utc=True).dt.tz_convert('America/Phoenix')
G26 = GM[GM.season == 2026]; DONE = G26[G26.homePoints.notna()]
PRIOR = pd.read_csv(R / 'games_prior.csv'); PRIOR = PRIOR[PRIOR.homePoints.notna()]
PR = pd.read_csv(R / 'power_ratings.csv').set_index('team')
RK = pd.read_csv(R / 'rankings.csv') if (R / 'rankings.csv').exists() else pd.DataFrame()
ST = pd.read_csv(R / 'season_stats.csv') if (R / 'season_stats.csv').exists() else pd.DataFrame()
TM = pd.read_csv(R / 'teams.csv').drop_duplicates('school').set_index('school')
H = json.load(open(D / 'hist' / 'fbs_vs_fcs_2017_2025.json'))['rows']
ESPN = json.load(open(D / 'fcs_espn.json')) if (D / 'fcs_espn.json').exists() else {}
LIVE = json.load(open(D / 'live_numbers.json')) if (D / 'live_numbers.json').exists() else {}
SLATE = json.load(open(D / 'slate_fbs.json')) if (D / 'slate_fbs.json').exists() else {'games': []}
SL = {g['id']: g for g in SLATE['games']}


def results(team, df):
    out = []
    for r in df[(df.homeTeam == team) | (df.awayTeam == team)].sort_values('dt' if 'dt' in df else 'startDate').itertuples():
        home = r.homeTeam == team; pf, pa = (r.homePoints, r.awayPoints) if home else (r.awayPoints, r.homePoints)
        opp = r.awayTeam if home else r.homeTeam; ocls = r.awayClassification if home else r.homeClassification
        out.append(dict(date=str(r.startDate)[:10], opp=opp, opp_cls=ocls, site='N' if r.neutralSite else ('H' if home else 'A'),
                        pf=int(pf), pa=int(pa), conf=bool(r.conferenceGame)))
    return out


def rec(rs): w = sum(x['pf'] > x['pa'] for x in rs); return f"{w}-{len(rs) - w}"


def stat(team, k):
    if ST.empty: return None
    v = ST[(ST.team == team) & (ST.stat == k)].value
    return float(v.iloc[0]) if len(v) else None


def per_game(team, k):
    g, v = stat(team, 'games'), stat(team, k)
    return round(v / g, 1) if g and v is not None else None


def poll_rank(team, poll):
    if RK.empty: return None
    x = RK[(RK.season == 2026) & (RK.poll == poll)]
    if x.empty: return None
    x = x[x.week == x.week.max()]; r = x[x.team == team]['rank']
    return (int(r.iloc[0]), int(x.week.max())) if len(r) else None


def band(sp):
    for lo, hi in ((-99, -35), (-35, -28), (-28, -21), (-21, -14), (-14, -7), (-7, 99)):
        if lo <= sp < hi: return lo, hi
    return None


def hist_line(sp):
    b = band(sp); out = []
    if b:
        x = [r for r in H if b[0] <= r[2] < b[1]]; w = sum(r[3] + r[2] > 0 for r in x); l = sum(r[3] + r[2] < 0 for r in x)
        out.append(f"FBS favorites of {abs(b[1]) if b[1] < 0 else 0:g} to {abs(b[0]) if b[0] > -99 else '35+'} points vs FCS, 2017-2025: covered {w}-{l} ({100 * w / max(w + l, 1):.0f}%) at the close.")
    x = [r for r in H if r[1] >= 11]; w = sum(r[3] + r[2] > 0 for r in x); l = sum(r[3] + r[2] < 0 for r in x)
    out.append(f"Week 11+ FBS vs FCS games, 2017-2025: FBS covered {w}-{l} (small sample, not a rule).")
    return out


def dive(g):
    fbs_k = 'h' if g['cls_h'] == 'fbs' else 'a'; fcs_k = 'a' if fbs_k == 'h' else 'h'
    fbs, fcs = g['home' if fbs_k == 'h' else 'away'], g['home' if fcs_k == 'h' else 'away']
    rs = results(fcs, DONE); last = results(fcs, PRIOR)
    vs_fbs = [x for x in rs if x['opp_cls'] == 'fbs']; conf = [x for x in rs if x['conf']]
    pf = round(np.mean([x['pf'] for x in rs]), 1) if rs else None; pa = round(np.mean([x['pa'] for x in rs]), 1) if rs else None
    pr = PR.loc[fcs] if fcs in PR.index else None; pf_ = PR.loc[fbs] if fbs in PR.index else None
    fcs_rank = int(pr['rank']) if pr is not None and pr['rank'] == pr['rank'] else None
    n_fcs = int((PR.division == 'fcs').sum())
    rank_fcs = int((PR[PR.division == 'fcs'].rating > pr.rating).sum() + 1) if pr is not None else None
    poll = poll_rank(fcs, 'FCS Coaches Poll')
    dd = dict(fcs_team=fcs, fbs_team=fbs, conference=(TM.conference[fcs] if fcs in TM.index else None),
              mascot=(TM.mascot[fcs] if fcs in TM.index and isinstance(TM.mascot[fcs], str) else None),
              record=rec(rs) if rs else '0-0', conf_record=rec(conf) if conf else None, last_season=rec(last) if last else None,
              pf_pg=pf, pa_pg=pa, last5=[f"{'W' if x['pf'] > x['pa'] else 'L'} {x['pf']}-{x['pa']} {'vs' if x['site'] != 'A' else 'at'} {x['opp']}" for x in rs[-5:]],
              vs_fbs=[f"{'W' if x['pf'] > x['pa'] else 'L'} {x['pf']}-{x['pa']} {'vs' if x['site'] != 'A' else 'at'} {x['opp']}" for x in vs_fbs],
              rating=(round(float(pr.rating), 1) if pr is not None else None), rating_rank_fcs=(f"{rank_fcs} of {n_fcs} FCS" if rank_fcs else None),
              form=(round(float(pr.form), 1) if pr is not None else None),
              returning_yards_share=(round(float(pr.fcs_ret_yards_share) * 100) if pr is not None and pr.fcs_ret_yards_share == pr.fcs_ret_yards_share else None),
              fcs_poll=(f"#{poll[0]} FCS Coaches Poll (week {poll[1]})" if poll else 'unranked in the FCS Coaches Poll'),
              offense=dict(yards_pg=per_game(fcs, 'totalYards'), pass_pg=per_game(fcs, 'netPassingYards'), rush_pg=per_game(fcs, 'rushingYards'),
                           turnovers_pg=per_game(fcs, 'turnovers'), sacks_allowed_pg=per_game(fcs, 'sacksOpponent')),
              defense=dict(yards_pg=per_game(fcs, 'totalYardsOpponent'), pass_pg=per_game(fcs, 'netPassingYardsOpponent'), rush_pg=per_game(fcs, 'rushingYardsOpponent'),
                           takeaways_pg=per_game(fcs, 'turnoversOpponent'), sacks_pg=per_game(fcs, 'sacks')),
              rating_gap=(round(float(pf_.rating - pr.rating), 1) if pr is not None and pf_ is not None else None))
    # schedule spot for the FBS team: previous and next game
    fg = G26[(G26.homeTeam == fbs) | (G26.awayTeam == fbs)].sort_values('dt'); t0 = pd.Timestamp(g['dt'])
    nxt = fg[fg.dt > t0].head(1); prv = fg[(fg.dt < t0)].tail(1)
    if len(nxt): n = nxt.iloc[0]; dd['fbs_next'] = f"{'vs' if n.homeTeam == fbs else 'at'} {n.awayTeam if n.homeTeam == fbs else n.homeTeam} ({n['dt'].strftime('%b %-d')})"
    if len(prv): p = prv.iloc[0]; dd['fbs_prev'] = f"{'vs' if p.homeTeam == fbs else 'at'} {p.awayTeam if p.homeTeam == fbs else p.homeTeam} ({p['dt'].strftime('%b %-d')})"
    if fcs in ESPN: dd['espn'] = ESPN[fcs]
    sp_fbs = None
    if g.get('spread_h') is not None: sp_fbs = g['spread_h'] if fbs_k == 'h' else -g['spread_h']
    if sp_fbs is not None: dd['history'] = hist_line(sp_fbs)
    notes = [f"FCS opponent deep dive: {fcs}{' ' + dd['mascot'] if dd['mascot'] else ''} ({dd['conference']}), {dd['record']}"
             + (f", {dd['conf_record']} in conference" if dd['conf_record'] else '') + (f"; last season {dd['last_season']}" if dd['last_season'] else '') + f"; {dd['fcs_poll']}."]
    if pf is not None: notes.append(f"{fcs} scores {pf} and allows {pa} per game this season.")
    if dd['rating'] is not None: notes.append(f"Model rating {dd['rating']:+.1f} ({dd['rating_rank_fcs']}); {fbs} rates {dd['rating_gap']:+.1f} points better on a neutral field.")
    if vs_fbs: notes.append(f"{fcs} vs FBS this season: " + '; '.join(dd['vs_fbs']) + '.')
    else: notes.append(f"{fcs} has not played an FBS team this season.")
    if dd['last5']: notes.append('Last 5: ' + '; '.join(dd['last5']) + '.')
    o, d_ = dd['offense'], dd['defense']
    if o['yards_pg'] is not None: notes.append(f"Offense {o['yards_pg']:g} yards per game ({o['pass_pg']:g} pass, {o['rush_pg']:g} rush); defense allows {d_['yards_pg']:g} ({d_['pass_pg']:g} pass, {d_['rush_pg']:g} rush).")
    if dd['returning_yards_share'] is not None: notes.append(f"Returning production: {dd['returning_yards_share']}% of last season's yards.")
    E = dd.get('espn', {})
    if E.get('qb'):
        notes.append(f"QB last game: {E['qb_line'] or E['qb']}" + ('; new passer, a different QB led the game before.' if E.get('qb_change') else '.'))
        prev = [f"{x['opp']} {x['pass']}" for x in (E.get('last3') or [])[:-1] if x.get('pass')]
        if prev: notes.append('Earlier: ' + '; '.join(prev) + '.')
    if E.get('rb') or E.get('wr'): notes.append('Leaders last game: ' + '; '.join(x for x in (E.get('rb'), E.get('wr')) if x) + '.')
    for i in dd.get('espn', {}).get('injuries', []) or []: notes.append(f"Injury: {i}.")
    if dd.get('fbs_next'): notes.append(f"{fbs} schedule spot: last game {dd.get('fbs_prev', 'none')}, next game {dd['fbs_next']}.")
    notes += dd.get('history', [])
    notes.append('No pick: the FBS rules were not tested on FBS vs FCS games, and 2017-2025 shows no stable edge (FBS 423-444 at the close).')
    return dict(notes=notes, deep_dive=dd)


out = {}
for gid, g in SL.items():
    if not g.get('reference_only'): continue
    if FROM and not (FROM <= g['date'] <= TO): continue
    out[str(gid)] = dive(g)
json.dump(out, open(D / 'fcs_dive.json', 'w'), indent=1, default=str)
print(len(out), 'FBS vs FCS games')
for k, v in out.items(): print(k, v['notes'][0])
