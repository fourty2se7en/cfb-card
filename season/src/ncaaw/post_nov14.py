"""Nov 14 post step (early run, about 12:55 AM Phoenix): no NCAAW line posted yet for any AP Top 25 game (The Odds API lists no women's
games for today; ESPN shows no DraftKings line). Writes game docs with picks.side/total {none, analysis} and fixes the old texas222 wording.
Reads ../hub_out, writes ../post2. A second run later today replaces these with the card."""
import json, pathlib
W = pathlib.Path(__file__).parent.parent; O = W/'post2'; O.mkdir(exist_ok=True)
G = json.load(open(W/'hub_out'/'games.json'))
NONE = "No line posted yet when the card ran (12:55 AM Phoenix): The Odds API lists no women's games for today and ESPN shows no DraftKings line, so no rule can fit. The next run today posts picks once a line is out."
AN = {
 '2026-11-14_TAR-TEX': ("No. 6 Texas is 3-0, all at home, winning by 20, 62 and 30 while scoring 89.7 and allowing 52.3 points per game. Tarleton State is 2-1 and lost its only road game by 47. Our efficiency model projects Texas by 33.5.",
                        "Our efficiency model total is 132.9. Texas holds opponents to 52.3 points per game, and Tarleton State's games average 122 total points."),
 '2026-11-14_DEP-ND': ("No. 13 Notre Dame and DePaul meet at a neutral site (Colonial Hall, White Sulphur Springs, WV). Notre Dame has won its two Division I games by 83 and 48, scoring 115.5 points per game; DePaul is 4-0, all at home, winning each by 20 to 32. Our efficiency model projects Notre Dame by 26.5.",
                       "Our efficiency model total is 149.5, the highest of today's Top 25 games. Notre Dame scores 115.5 and DePaul 89.2 points per game; DePaul allows 63.8."),
 '2026-11-14_MINN-KSU': ("No. 18 Minnesota and Kansas State, both unbeaten, meet at a neutral site (Sanford Pentagon, Sioux Falls, SD). Minnesota has won by 20, 8 and 39, scoring 85.0 points per game; Kansas State is 4-0 at home, allowing 47.2 points per game. Our efficiency model projects Minnesota by 11.3.",
                         "Our efficiency model total is 129.3. Kansas State plays slow and allows 47.2 points per game, while Minnesota scores 85.0 and allows 62.7."),
 '2026-11-14_UNC-PENN': ("No. 23 North Carolina is 1-2, with losses by 12 and 45, and plays at Penn (The Palestra), which is 4-0. Penn's Division I wins came by 1, 16 and 19. Our efficiency model still projects North Carolina by 19.7.",
                         "Our efficiency model total is 137.2. North Carolina allows 71.7 points per game after the 45 point loss; Penn allows 59.7."),
 '2026-11-14_NEB-KU': ("No. 25 Nebraska and Kansas, both 3-0, meet at a neutral site (Sanford Pentagon, Sioux Falls, SD). Nebraska has won by 27, 63 and 41 and allows 41.3 points per game; Kansas has won by 18, 25 and 48. Our efficiency model projects Nebraska by 7.0.",
                       "Our efficiency model total is 135.7. Both defenses have been stingy: Nebraska allows 41.3 and Kansas 49.3 points per game."),
}
out = []
for g in G:
    d = g['data']; a = AN[g['id']]
    d['picks'] = {'side': dict(none=NONE, analysis=a[0]), 'total': dict(none=NONE, analysis=a[1])}
    d['notes'] = [n.replace('No line posted at texas222 or DraftKings when the card ran (12:55 AM); Action Network shows no open or splits.',
                            'No line at The Odds API or DraftKings (ESPN) when the card ran (12:55 AM Phoenix). Action Network not read on this early run.') for n in d.get('notes', [])]
    d['notes'].append('Injuries and lineups: no NCAAW injury report posted on ESPN; player box scores for these teams are not in the data feed yet, so no starter changes were found.')
    d['lines'] = dict(book=None, read_at='12:55 AM', note='No line posted yet')
    d['line_history'] = [dict(as_of='2026-11-14 00:55', spread=None, total=None, ml_away=None, ml_home=None, source='The Odds API (no NCAAW events listed); ESPN DraftKings (none)')]
    out.append(g)
json.dump(out, open(O/'games.json', 'w'), indent=1)
for g in out: json.dump(g['data'], open(O/f"g_{g['id']}.json", 'w'))
print(len(out), 'game docs')
