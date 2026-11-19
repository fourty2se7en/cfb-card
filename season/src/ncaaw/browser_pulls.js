// ===== NCAA cards: browser data pulls (javascript_tool in Claude in Chrome; built-in browser if Chrome is unavailable) =====
// Output truncates near 1,000 chars: store results on window and read 950-char slices, several per browser_batch.
// LG = 'mens-college-basketball' (NCAAM) or 'womens-college-basketball' (NCAAW). Times shown in Phoenix.

// 1. Slate (tab on site.api.espn.com): all Division I games
//   fetch(`https://site.api.espn.com/apis/site/v2/sports/basketball/${LG}/scoreboard?dates=YYYYMMDD&groups=50&limit=500`)
//   per event: id|Phoenix time|away abbr|home abbr|away short|home short|away conf id|home conf id|conferenceCompetition|neutralSite|away AP rank|home AP rank|state(p/i/post)
//   -> data/espn_today_<m|w>.txt (D1 vs D1 games only). Team ids -> data/ids.txt (team guide links).
// 2. Second opening book: ESPN core odds (DraftKings, provider 40) open and current per game
//   https://sports.core.api.espn.com/v2/sports/basketball/leagues/${LG}/events/${id}/competitions/${id}/odds?limit=50
//   Fill o2/c2 (home spread open/now) and t2o/t2c in build.py when posted. On opening day ESPN had no men's odds yet.
//   Keep concurrency at 6 or less: the core odds host blocks bursts for several minutes.
// 3. texas222 (core.texas222.com/wager/Sports.aspx; Trina must already be logged in; never type credentials; never read balances)
//   Menus: 'NCAA BASKETBALL - MEN', 'NCAA BASKETBALL - EXTRA GAMES', 'NCAA BASKETBALL (1H)', "NCAA WOMEN'S BASKETBALL"; click Next at the bottom.
//   No college team totals or player props menu was posted on Nov 2, 2026 (props section of the card stays off until one appears).
//   Slice the page text from 'NCAA BASKETBALL - MEN ~ TIME' (never from the top: the header holds account figures).
//   Rows: menu|t222 time (Pacific)|TEAM|spread price|total price|ml  -> data/t222_<m|w>.txt
// 4. Action Network (actionnetwork.com/ncaab/public-betting and /ncaaw/public-betting; read the visible table, spread view)
//   rows: away|home|away open spread|bets% away|bets% home|money% away|money% home -> data/an_<m|w>.txt
//   (open on AN vs texas222 now = book 1 for the line move rules; tickets% gate SPREAD_MOVE live)
// 5. Ratings: last season final opponent adjusted margin and scoring pace from bt_run.js (RAT[lg+'2025-26']) -> data/ratings_<m|w>_2025-26.txt;
//   this season's games come from season/games_<lg>.txt and blend in by games / (games + 8).
// 6. AP poll: site.api.espn.com/apis/site/v2/sports/basketball/${LG}/rankings -> data/ap_poll.json. NET: first release early December.
// 7. Grading and season data (every run, yesterday's games): ESPN scoreboard finals + core odds open/close
//   -> append one JSON row per game to season/games_<lg>.txt in the bt_build.js row format, then python3 recheck.py <lg> <today>.
// 8. Backtest (one time, Nov 2 2026): bt_build.js then bt_run.js in a site.api.espn.com tab; results -> data/bt_<m|w>.txt.
// 9. (Nov 3, 2026) Efficiency rules need box scores. Every run, append yesterday's D1 games to season/box_<lg>.txt in the bt_build2.js row format:
//    [season, date, home, away, neutral, conf_game, home_pts, away_pts, hFGA, hORB, hTO, hFTA, aFGA, aORB, aTO, aFTA,
//     dk_open_sp, dk_close_sp, dk_open_tot, dk_close_tot, s2_open_sp, s2_close_sp, s2_open_tot, s2_close_tot, med_sp, med_tot]
//    (ESPN summary?event={id} box score + core odds). bt_build2.js has L = mens-college-basketball; set it to womens-college-basketball for NCAAW.
//    Opening total for EARLY_UNDER_OPEN / EARLY_OVER_OPEN live = ESPN core odds DraftKings open total (t2o), else the ESPN board open.
