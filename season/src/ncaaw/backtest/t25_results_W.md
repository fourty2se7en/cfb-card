# NCAAW 3 season backtest, AP Top 25 games only (run Nov 9, 2026)

Data: every Division I women's game 2023-24 to 2025-26 rebuilt in Chrome (t25_build.js; 17,906 games, 22,282 box score rows incl. 2022-23 for prior ratings, same count as the Nov 3 build). Ranks = ESPN curatedRank at game time. Odds pulled for games with a ranked team: 2,253 such games, 2,034 with a closing spread and total (552 with both teams ranked). Ratings, rest and form use every D1 game (as the live card's full D1 ratings do); only ranked games are graded. Closing line = ESPN core odds median close (DK and a second book for moves). Opening totals exist mainly in 2023-24.
Runner: t25_run.js (families, MODEL_EDGE, NEUTRAL_UNDER) and t25_run2.js (efficiency rules, EARLY rules graded at the close and at the open). window.T25MODE = 'any' (a ranked team) or 'both'.
Bar (unchanged): positive over three seasons, positive in 2 of 3, and either 3 of 3 or 200+ picks.

Format: three seasons / 2023-24 / 2024-25 / 2025-26 (W-L units)

| Rule | Top 25 games | Bar |
|---|---|---|
| EFF_SPREAD (3+) | 471-386 +42.2u / 169-131 +22.6 / 122-119 -8.1 / 180-136 +27.6 | PASS (2 of 3, 857 picks) |
| EFF_SPREAD (5+, reference) | 259-198 +37.5u / +21.1 / +1.2 / +15.2 | 3 of 3 |
| MODEL_EDGE (3+) | 487-409 +33.7u / +11.9 / +0.7 / +21.1 | PASS (3 of 3) |
| EFF_OVER (3+) | 166-125 +25.9u / +8.8 / +13.2 / +3.9 | PASS (3 of 3) |
| EARLY_OVER_OPEN (graded at close) | 65-34 +25.1u / +17.5 / +3.3 / +4.4 | PASS (3 of 3) |
| EARLY_UNDER_OPEN (graded at close) | 75-57 +11.2u / -5.9 / +14.8 / +2.3 | fails (2 of 3, 132 picks) |
| OVER strict | 94-79 +6.5u / +2.9 / -2.0 / +5.5 | fails (2 of 3, 173 picks) |
| DOG_ML strict | 18-19 +7.1u / +3.4 / +3.6 / none | fails (37 picks) |
| FAV_ML strict | 18-9 +2.8u / +3.3 / +0.7 / -1.2 | fails (27 picks) |
| FAV_ML lowered | 37-29 -4.9u | fails |
| UNDER_DROP lowered | 117-112 -5.6u / -8.9 / -0.6 / +3.9 | fails |
| NEUTRAL_UNDER | 207-192 -3.8u / -15.8 / +13.1 / -1.1 | fails |
| SPREAD_MOVE lowered | 338-378 -70.7u / -50.5 / -7.7 / -12.5 | fails, negative 3 of 3 |
| SPREAD_MOVE strict | 329-362 -62.9u | fails |
| Base: every under | 1003-1030 -118.2u | ranked games lean over |

Both teams ranked (small): EFF_SPREAD 108-79 +19.2u (3 of 3), EFF_OVER 33-16 +14.0u (3 of 3), UNDER_DROP strict 29-18 +8.4u (3 of 3), MODEL_EDGE 92-76 +7.6u, EARLY_UNDER_OPEN 18-8 +8.4u, SPREAD_MOVE -23.8u, NEUTRAL_UNDER -8.8u.

Nothing switched: on and off follow the Season Cards policy (this season's record). Trina decides whether the backtest should change that.
