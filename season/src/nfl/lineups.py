"""Season Cards lineups, player ratings, unit ratings and prop matchups for NFL game docs (Trina, Nov 11; B34 to B37).
Usage: import lineups as LU; LU.build(team, opp, inj_rows) -> (lineup list, units dict); LU.matchup(stat, side, team, opp)
Starters: the 22 players with the most snaps at their slot over the team's last 3 games (nflverse snap counts):
QB, RB, WR x3, TE, OL x5 on offense; DL x4, LB x2, CB x3, S x2 on defense (nickel, the NFL's most used base).
Ratings 0 to 100: percentile at the position this season from nflverse player stats (per game), minimum 3 games:
QB passing plus rushing EPA per game; RB scrimmage yards per game; WR and TE receiving yards per game; DL and LB pressure
(2 x sacks + QB hits + tackles for loss) per game; CB and S (3 x interceptions + passes defended) per game plus tackles.
OL have no individual stats in nflverse: an OL rating is his snap share percentile blended with his team's pass block and
run block unit ratings (said in the note). Unit ratings are team percentiles of 32 from 2026 play by play:
Pass block = sack rate allowed (low is good), Run block = rushing EPA per play, Pass rush = sack rate, Run D = rushing
EPA allowed per play, Coverage = dropback EPA allowed. Several starters out in one unit lower that unit by the gap between
each starter and his backup, scaled by the unit's size."""
import pandas as pd, numpy as np, nflreadpy as nfl

SEASON = 2026
SC = nfl.load_snap_counts([SEASON]).to_pandas(); SC = SC[SC.game_type == 'REG']
PS = nfl.load_player_stats([SEASON]).to_pandas(); PS = PS[PS.season_type == 'REG'] if 'season_type' in PS else PS
PBP = nfl.load_pbp([SEASON]).to_pandas()
PBP = PBP[(PBP.season_type == 'REG') & PBP.posteam.notna()]

def pct_rank(s, higher_better=True):
    r = s.rank(pct=True); r = r if higher_better else 1 - r + 1 / len(s)
    return (r * 100).clip(1, 99).round().astype(int)

# ---------- team units ----------
db = PBP[(PBP.qb_dropback == 1)]; ru = PBP[(PBP.rush == 1) & (PBP.qb_scramble != 1)]
U = pd.DataFrame({
    'sack_rate_off': db.groupby('posteam').sack.mean(), 'rush_epa_off': ru.groupby('posteam').epa.mean(),
    'sack_rate_def': db.groupby('defteam').sack.mean(), 'rush_epa_def': ru.groupby('defteam').epa.mean(),
    'db_epa_def': db.groupby('defteam').epa.mean(), 'pass_yds_def': db.groupby(['defteam', 'game_id']).yards_gained.sum().groupby('defteam').mean(),
    'rush_yds_def': ru.groupby(['defteam', 'game_id']).yards_gained.sum().groupby('defteam').mean()})
UNIT = pd.DataFrame({'Pass block': pct_rank(U.sack_rate_off, False), 'Run block': pct_rank(U.rush_epa_off), 'Pass rush': pct_rank(U.sack_rate_def),
                     'Run D': pct_rank(U.rush_epa_def, False), 'Coverage': pct_rank(U.db_epa_def, False)})
RANK = {'pass_yds': U.pass_yds_def.rank(method='min').astype(int), 'rush_yds': U.rush_yds_def.rank(method='min').astype(int)}  # 1 = fewest allowed
UNOTE = {'Pass block': lambda t: f"sacks on {U.sack_rate_off[t]*100:.1f}% of dropbacks", 'Run block': lambda t: f"{U.rush_epa_off[t]:+.2f} EPA per rush",
         'Pass rush': lambda t: f"sacks on {U.sack_rate_def[t]*100:.1f}% of opponent dropbacks", 'Run D': lambda t: f"{U.rush_epa_def[t]:+.2f} EPA per rush allowed",
         'Coverage': lambda t: f"{U.db_epa_def[t]:+.2f} EPA per dropback allowed"}

# ---------- player ratings ----------
g = PS.groupby(['player_id', 'player_display_name', 'position']).agg(
    gp=('week', 'nunique'), pepa=('passing_epa', 'sum'), repa=('rushing_epa', 'sum'), ry=('rushing_yards', 'sum'), recy=('receiving_yards', 'sum'),
    sk=('def_sacks', 'sum'), qh=('def_qb_hits', 'sum'), tfl=('def_tackles_for_loss', 'sum'), tk=('def_tackles_solo', 'sum'),
    ints=('def_interceptions', 'sum'), pd_=('def_pass_defended', 'sum')).reset_index()
g = g[g.gp >= 3].copy()
for c in ('pepa', 'repa', 'ry', 'recy', 'sk', 'qh', 'tfl', 'tk', 'ints', 'pd_'): g[c] = g[c].fillna(0) / g.gp
g['score'] = np.nan
grp = {'QB': ['QB'], 'RB': ['RB', 'FB'], 'WR': ['WR'], 'TE': ['TE'], 'DL': ['DE', 'DT', 'NT', 'DL'], 'LB': ['LB', 'ILB', 'OLB', 'MLB'], 'CB': ['CB', 'DB'], 'S': ['S', 'FS', 'SS', 'SAF']}
g['grp'] = g.position.map({p: k for k, v in grp.items() for p in v})
g.loc[g.grp == 'QB', 'score'] = g.pepa + g.repa
g.loc[g.grp == 'RB', 'score'] = g.ry + g.recy
g.loc[g.grp.isin(['WR', 'TE']), 'score'] = g.recy
g.loc[g.grp.isin(['DL', 'LB']), 'score'] = 2 * g.sk + g.qh + g.tfl + (0.15 * g.tk)
g.loc[g.grp.isin(['CB', 'S']), 'score'] = 3 * g.ints + g.pd_ + 0.1 * g.tk
g['rating'] = g.groupby('grp').score.transform(lambda s: pct_rank(s))
RAT = {(r.player_display_name, r.grp): r for r in g.itertuples()}
BYNAME = {}
for r in g.itertuples(): BYNAME.setdefault(r.player_display_name, r)
import re as _re
def _nn(n): return _re.sub(r"[.'`]", '', _re.sub(r'\s+(jr|sr|ii|iii|iv|v)\.?$', '', str(n).strip(), flags=_re.I)).lower()
BYNORM = {}
for r in g.itertuples(): BYNORM.setdefault(_nn(r.player_display_name), r)
def lookup(p, key=None):
    """Player stats row by name: exact (name, group), then exact name, then the name without suffix or periods (Jessie Bates III = Jessie Bates)."""
    r = RAT.get((p, key)) if key else None
    r = r if r is not None else BYNAME.get(p)
    return r if r is not None else BYNORM.get(_nn(p))

def tags(r):
    s, w = [], []
    if r is None: return s, w
    if r.grp == 'QB':
        (s if r.pepa > 3 else w if r.pepa < 0 else s).append(f"{r.pepa:+.1f} passing EPA per game")
        if r.repa > 1: s.append('adds value as a runner')
    elif r.grp == 'RB':
        (s if r.ry >= 60 else w).append(f"{r.ry:.0f} rush yards per game")
        if r.recy >= 20: s.append(f"{r.recy:.0f} receiving yards per game")
    elif r.grp in ('WR', 'TE'):
        (s if r.recy >= 50 else w if r.recy < 25 else s).append(f"{r.recy:.0f} receiving yards per game")
    elif r.grp in ('DL', 'LB'):
        if r.sk >= 0.4: s.append(f"{r.sk:.1f} sacks per game")
        if r.tfl >= 0.5: s.append('makes plays in the backfield')
        if r.sk < 0.15 and r.qh < 0.5: w.append('little pass rush')
    else:
        if r.ints + r.pd_ >= 0.8: s.append('ball skills (picks and breakups)')
        elif r.ints + r.pd_ < 0.3: w.append('few plays on the ball')
    return s, w

SLOTS_O = [('QB', ['QB'], 1), ('RB', ['RB', 'FB'], 1), ('WR', ['WR'], 3), ('TE', ['TE'], 1), ('OL', ['T', 'G', 'C', 'OL', 'OT', 'OG'], 5)]
SLOTS_D = [('DL', ['DE', 'DT', 'NT', 'DL'], 4), ('LB', ['LB', 'ILB', 'OLB', 'MLB'], 2), ('CB', ['CB'], 3), ('S', ['S', 'FS', 'SS', 'SAF'], 2)]

def recent(team):
    gids = SC[SC.team == team].sort_values('week').game_id.unique()[-3:]
    return SC[(SC.team == team) & SC.game_id.isin(gids)]

def rating_of(p, slot, team_hint=None):
    """0 to 100 rating for one player at a lineup slot (OL: snap share among his team's linemen plus that team's block units)."""
    if slot == 'OL':
        t = team_hint
        if t is None:
            z = SC[SC.player == p].sort_values('week'); t = z.team.iloc[-1] if len(z) else None
        if t is None or t not in UNIT.index: return None
        x = recent(t); ol = x[x.position.isin(['T', 'G', 'C', 'OL', 'OT', 'OG'])].groupby('player').offense_pct.mean()
        sp = int(round(ol.rank(pct=True).get(p, 0.5) * 100))
        return int(round(0.4 * sp + 0.3 * UNIT.loc[t, 'Pass block'] + 0.3 * UNIT.loc[t, 'Run block']))
    r = lookup(p, slot)
    if r is None or r.rating != r.rating: return None
    return int(r.rating)

def build(team, qb_override=None, inj=None, moves=None):
    """Returns (lineup rows, units). inj: {player: status} from the official report.
    moves: transactions.json rows for this team (Nov 11): players traded away or put on IR leave the lineup and the next man at
    the slot starts; players acquired with role_now Starts take a starting slot (the lowest rated starter at that slot moves to the bench).
    Each changed row carries 'transaction' and 'replaces'/'replaced_by'."""
    inj = inj or {}; moves = moves or []
    gone = {m['player']: m for m in moves if m['role_now'] == 'Out' and not m.get('already_in_data_arrival')}
    arrive = [m for m in moves if m['move'].startswith('Acquired') and m['role_now'] == 'Starts']
    x = recent(team); x_all = x
    x = x[~x.player.isin(list(gone))]
    out = []; unit_hits = {}; self_moves = {}
    for side, slots, col in (('offense', SLOTS_O, 'offense_pct'), ('defense', SLOTS_D, 'defense_pct')):
        agg = x.groupby(['player', 'position'])[col].mean().reset_index().sort_values(col, ascending=False)
        agg_all = x_all.groupby(['player', 'position'])[col].mean().reset_index().sort_values(col, ascending=False)
        for slot, poss, n in slots:
            base = (list(agg_all[agg_all.position.isin(poss) & (agg_all[col] > 0.2)].player) + [q for q in agg_all[agg_all.position.isin(poss) & (agg_all[col] > 0)].player if q not in list(agg_all[agg_all.position.isin(poss) & (agg_all[col] > 0.2)].player)])[:n]
            lost = [q for q in base if q in gone]
            cand = agg[agg.position.isin(poss) & (agg[col] > 0.2)]
            names = list(cand.player)
            if len(names) < n + 1:   # Nov 11: fill a short slot (or its backup) from the next most used players at the position
                names += [q for q in agg[agg.position.isin(poss) & (agg[col] > 0)].player if q not in names]
            if slot == 'QB' and qb_override: names = [qb_override] + [p for p in names if p != qb_override]
            elif slot == 'QB' and names:
                lw = x[x.position == 'QB'].sort_values('week')
                lw = lw[lw.week == lw.week.max()].sort_values('offense_pct', ascending=False)
                if len(lw): names = [lw.player.iloc[0]] + [p for p in names if p != lw.player.iloc[0]]
            for m in arrive:
                if m['slot'] == slot and m['player'] not in names[:n] and slot != 'QB':
                    cur = names[:n]
                    if len(cur) >= n:
                        rr = [(rating_of(c, slot, team) or 0, c) for c in cur]; low = min(rr)[1]
                        names = [c for c in names if c != low]; names.insert(n - 1, m['player']); names.insert(n, low)
                        self_moves[m['player']] = dict(transaction=f"{m['move']} ({m['date']})", replaces=low)
                    else:
                        names.insert(len(cur), m['player']); self_moves[m['player']] = dict(transaction=f"{m['move']} ({m['date']})")
                    if m['player'] in list(names[n+1:]): pass
            if slot == 'QB' and qb_override and qb_override not in list(x.player):
                for m in moves:
                    if m['player'] == qb_override and m['move'].startswith('Acquired'): self_moves[qb_override] = dict(transaction=f"{m['move']} ({m['date']})")
            starters = names[:n]; bench = names[n:]
            for p in starters:
                key = 'DL' if slot == 'DL' else slot
                r = lookup(p, key)
                share = float(cand[cand.player == p][col].iloc[0]) if p in list(cand.player) else None
                if slot == 'OL':
                    ol = agg[agg.position.isin(poss)]
                    sp = int(round(ol[col].rank(pct=True)[ol.player == p].iloc[0] * 100)) if p in list(ol.player) else 50
                    rating = int(round(0.4 * sp + 0.3 * UNIT.loc[team, 'Pass block'] + 0.3 * UNIT.loc[team, 'Run block']))
                    st, wk = [f"plays {share*100:.0f}% of snaps" if share else 'starter'], []
                    note = 'OL rating from snap share and team block units (no individual OL stats in nflverse)'
                else:
                    rating = int(r.rating) if r is not None else None
                    st, wk = tags(r); note = None if r is not None else 'fewer than 3 games of stats this season'
                status = inj.get(p, 'Active')
                if slot == 'OL' and p not in list(agg.player): rating = rating_of(p, 'OL'); note = 'OL rating from snap share with his previous team and its block units'
                if rating is None and slot != 'OL': rating = rating_of(p, slot)
                row = dict(player=p, pos=slot, role=side, starter=True, status=status, rating=rating, strengths=st, weaknesses=wk, source='nflverse snap counts (last 3 games) and player stats')
                if p in self_moves: row.update(self_moves[p]); row['source'] += '; transactions.json'
                elif lost and p not in base and slot != 'QB':
                    q = lost.pop(0); row['replaces'] = q; row['transaction'] = f"starts for {q} ({gone[q]['move']}, {gone[q]['date']})"; row['source'] += '; transactions.json'
                if note: row['note'] = note
                if status in ('Out', 'Doubtful', 'IR') and bench:
                    bk = bench.pop(0); rb = lookup(bk, slot)
                    row['backup'] = bk; row['backup_rating'] = int(rb.rating) if rb is not None and rb.rating == rb.rating else None
                    unit_hits.setdefault(slot, []).append((p, rating, row['backup_rating']))
                out.append(row)
    units = {k: dict(rating=int(UNIT.loc[team, k]), note=UNOTE[k](team) + ' (percentile of 32)') for k in UNIT.columns}
    for slot, hits in unit_hits.items():
        uk = {'OL': ['Pass block', 'Run block'], 'DL': ['Pass rush', 'Run D'], 'LB': ['Run D'], 'CB': ['Coverage'], 'S': ['Coverage'], 'WR': [], 'TE': ['Run block'], 'RB': [], 'QB': []}[slot]
        size = {'OL': 5, 'DL': 4, 'LB': 2, 'CB': 3, 'S': 2, 'TE': 1}.get(slot, 1)
        drop = sum(max(0, (a or 50) - (b if b is not None else 30)) for _, a, b in hits) / size
        for k in uk:
            units[k]['rating'] = int(max(1, round(units[k]['rating'] - drop)))
            units[k]['note'] += f"; lowered {drop:.0f} for {', '.join(p for p, _, _ in hits)} out"
    return out, units

def matchup(stat, side, team, opp):
    """Opponent matchup for a prop: pass D (yards allowed per game rank, 1 = fewest) for PASS and REC, run D for RUSH."""
    if opp not in RANK['pass_yds'].index: return None
    pr, rr = int(RANK['pass_yds'][opp]), int(RANK['rush_yds'][opp])
    rk = rr if stat == 'RUSH' else pr
    weak = rk >= 23; strong = rk <= 10
    if weak: eff = 'supports Over' if side == 'Over' else 'works against'
    elif strong: eff = 'supports Under' if side == 'Under' else 'works against'
    else: eff = 'neutral'
    yd = U.rush_yds_def[opp] if stat == 'RUSH' else U.pass_yds_def[opp]
    return dict(opp=opp, vs=f"pass D {pr} of 32 · run D {rr} of 32 (yards allowed per game, 1 = fewest)", effect=eff, adj=0,
                detail=f"{opp} allows {yd:.0f} {'rushing' if stat == 'RUSH' else 'passing'} yards per game", source='nflverse play by play 2026',
                note='Shown only: not yet backtested on this season\'s graded props, so it does not change Plays')
