// Browser-side validation run 2026-10-29 (see project doc cfb-untested-signals-validated).
// 1) Action Network history: on /ncaaf/public-betting and /ncaaf/sharp-report, loop the week select
//    ('Week 0 / 1', 'Week 2'..'Week 8') and market select (spread, total, ml), waiting for the table to change,
//    grab per row: game slug (a[href*="/ncaaf-game/"]), open, tickets %, money %, and lit sharp buttons (.css-1m5q1hm).
//    Match slugs to CFBD 2026 games (raw.githubusercontent.com/fourty2se7en/cfb-card/<sha>/scripts/data/lines.csv),
//    grade vs consensus close; ML graded by winner at median closing ML, -300..+300.
// 2) QB1 out: ESPN scoreboard (groups=80, seasontype=2, weeks 1-15, 2024-2026) then summary per event;
//    QB1 = team's leader in pass attempts over prior games (2+ games, 60%+ share); out = 0 attempts.
// 3) Weather: Open-Meteo archive hourly wind_speed_10m (mph) and precipitation, max wind and summed rain over
//    kickoff +3h, outdoor venues only, 2017-2025 FBS games with a total, from the repo's backtest cache.
