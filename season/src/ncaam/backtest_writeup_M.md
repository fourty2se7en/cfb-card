## Bottom line
No rule family passed. All five NBA rule families stay off for the men's card. One college test passed (road team on 1 day rest vs a rested home team) and is live as ROAD1DAY_FADE (approved Nov 2).

## Data used
- 17,267 Division I games with an ESPN closing line: 5,755 in 2023-24, 5,763 in 2024-25, 5,749 in 2025-26.
- Scores, neutral site, conference game flag, AP rank and venue from the ESPN scoreboard (groups=50).
- Lines from ESPN core odds. Closing consensus is the median of every book ESPN lists; moneylines are cleaned (quotes under 100 or over 5000 dropped) and taken as medians in decimal odds.
- Team strength is an opponent adjusted margin built only from games before each date, blended with last season by games / (games + 8). 2023-24 has no prior season, so its early weeks are weaker.

## Data gaps
- Two opening books (DraftKings plus a second book) exist only for 2023-24. 2024-25 has one book with an open; 2025-26 has an open on only 1,257 games. Line move tests use both books when both exist and the single book otherwise.
- Action Network history (tickets %, money %, Sharp Action, Big Money, PRO Systems) could not be pulled for past seasons. The ticket conditions in SPREAD_MOVE and UNDER_DROP could not be tested; they apply live only.
- No historical first half lines, so the first half test could not be run. First half lines are shown on the card for information.
- No historical college injury data.
- Every test is graded at the closing number. Line move rules are hardest to judge this way, because the move is already in the closing price; live picks are made earlier at texas222.
- Pace tier uses season to date points per game (both teams), not possessions.

## Rule families (three seasons, closing prices)
- FAV_ML: lowered 936-700, -95.3u; strict 395-286, -35.3u. Negative every season. Off.
- DOG_ML: lowered 763-1135, -135.4u; strict 300-447, -42.2u. Negative every season. Off.
- SPREAD_MOVE: lowered 3811-3867, -402.5u; strict 3514-3537, -342.5u (49.8%, break-even 52.4%). Off.
- UNDER_DROP: lowered 2320-2199, -89.9u; strict 1218-1147, -39.7u. Positive only in 2025-26. Off.
- OVER: lowered 2454-2356, -125.1u; strict 1314-1272, -77.5u. Off.
- Model edge 3+ vs the spread: 2513-2593, -308.5u. The ratings alone do not beat the close.

## College tests
- Home court by conference: no conference showed a home ATS edge. Best were WAC +3.2u and Big Sky +4.0u on about 250 games each, inside noise.
- Early non-conference mismatches (spread 15+): favorites 848-863, underdogs 863-848, unders 813-899. Nothing to use.
- Conference vs non-conference: home teams 49.1% ATS in conference play, 50.6% outside it; unders 50.3% and 49.4%.
- Neutral sites: favorites 49.7% ATS; unders 52.4% (+0.5u), positive only in 2025-26. Holiday tournaments: underdogs 50.8%, unders 51.3%, both negative.
- Rest and travel: the team with 2+ more days rest 50.4% ATS (-176.6u). Road team that traveled on short rest 50.0%. Road team on 1 day rest vs a home team on 2+ days: 220-178 (55.3%), +22.0u, positive in 2023-24 and 2024-25, negative in 2025-26. Passes the rule test.
- Ranked vs unranked: unranked teams 50.1% ATS; unranked home teams 51.7% (-7.7u).
- Totals by pace tier: no tier beats 52.4% on either side.
- First half lines: not tested (no history).

## Approved Nov 2, 2026
- New rule ROAD1DAY_FADE: when the road team plays on 1 day rest and the home team has 2+ days, take the home team ATS. Backtest 220-178, +22.0u, 2 of 3 seasons positive. Most picks come in March (175-151), so it will rarely fire before conference tournaments.
- ROAD1DAY_FADE is live from Nov 2, 2026. The five rule families stay off; the re-check grades every rule daily.

## Backtest v2 (Nov 3, 2026): efficiency model and early season vs the opener
- Data: 23,015 games with box scores (2022-23 for the prior season, then 2023-24 to 2025-26). Ratings are adjusted offense, defense and tempo from possessions, rebuilt each day from prior games and blended with last season by games / (games + 8). Stricter bar: positive over three seasons and in 2 of 3, plus either all 3 seasons positive or 200+ picks.
- Efficiency model at the close: spread edge 3+ 2347-2413, -279.4u (0 of 3); edge 6+ 609-588, -34.4u. Overs 3+ 1518-1595, -215.0u. Unders 7+ 620-582, -18.4u. Nothing passed.
- Nov and Dec vs the opener: spread edge 3+ 1176-1213, -143.9u; margin model edge 3+ 1209-1127, -27.9u. Over 7+ 89-60, +20.9u (fails, under 200 picks; tracked as EARLY_OVER_OPEN).
- Passed: under when the model total is 4+ below the opener, 911-804 (53.1%), +24.2u, 2 of 3 seasons (2023-24 +7.5u, 2024-25 -5.0u, 2025-26 +21.6u). November -7.8u, December +32.0u.
- Action Network history could not be backtested (past dates are not served); tickets, money and sharp signals are judged live by the re-check.
- Live from Nov 3, 2026: EARLY_UNDER_OPEN (approved by Trina so every rule is tracked from the start of the season). EARLY_OVER_OPEN, EFF_SPREAD and EFF_OVER are tracked by the re-check but off.
