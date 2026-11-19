// ===== NBA Card: browser data pulls (run with javascript_tool in Chrome) =====
// Output truncates near 1,200 to 1,500 chars per call: store on window and print in slices (one line per call for game logs).

// ---- 1. Slate (ESPN scoreboard JSON; cdn.nba.com returns Access Denied). Open https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD
const s = JSON.parse(document.body.innerText);
s.events.map(e => { const c = e.competitions[0]; const h = c.competitors.find(x => x.homeAway == 'home'), a = c.competitors.find(x => x.homeAway == 'away');
  return [a.team.abbreviation, h.team.abbreviation, new Date(e.date).toLocaleTimeString('en-US', {timeZone: 'America/Phoenix', hour: 'numeric', minute: '2-digit'}), c.venue?.fullName].join('|'); }).join('\n');
// Fill GAMES in model.py. Sportradar home win %: fetch_sports_data (nba, scores) -> SR dict.

// ---- 2. Injuries: https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries (carries official report designations)
const j = JSON.parse(document.body.innerText);
j.injuries.filter(t => /TEAM NAMES/.test(t.displayName)).map(t => t.displayName + ': ' + t.injuries.map(i => i.athlete.displayName + ' ' + i.status + ' (' + (i.details?.type || '') + ')').join('; ')).join('\n');
// Write injuries_raw.txt. If a starter is Out or Doubtful, add INJ_ADJ[team] = (points of margin, note) in model.py (star 4 to 6, starter 2 to 3).

// ---- 3. NBA.com stats (open a tab on https://www.nba.com/stats/teams/advanced, then same-site fetch to stats.nba.com)
const q = async (ep, params) => { const r = await fetch('https://stats.nba.com/stats/' + ep + '?' + new URLSearchParams(params), {headers: {'x-nba-stats-origin': 'stats', 'x-nba-stats-token': 'true'}}); return r.json(); };
const base = {MeasureType: 'Advanced', PerMode: 'PerGame', SeasonType: 'Regular Season', LeagueID: '00', LastNGames: 0, Month: 0, OpponentTeamID: 0, PaceAdjust: 'N', Period: 0, PlusMinus: 'N', Rank: 'N', TeamID: 0,
  Conference: '', DateFrom: '', DateTo: '', Division: '', GameScope: '', GameSegment: '', Location: '', Outcome: '', PORound: 0, PlayerExperience: '', PlayerPosition: '', SeasonSegment: '', ShotClockRange: '', StarterBench: '', TwoWay: 0, VsConference: '', VsDivision: ''};
// leaguedashteamstats {...base, Season:'2025-26'} and '2026-27' -> OFF_RATING, DEF_RATING, NET_RATING, PACE -> teams_raw.txt
// leaguestandingsv3 {LeagueID:'00', Season:'2026-27', SeasonType:'Regular Season'} -> standings_raw.txt rows (team,conf,div,w,l,PlayoffRank,HOME,ROAD,L10,strCurrentStreak,PointsPG,OppPointsPG)
// leaguegamelog {Counter:1000, Direction:'DESC', LeagueID:'00', PlayerOrTeam:'T', Season:'2026-27', SeasonType:'Regular Season', Sorter:'DATE'} -> last game and rest days
// commonteamroster {LeagueID:'00', Season:'2026-27', TeamID} -> who is on each team (set ROSTER in model.py, NEWTEAM in render.py)
// playergamelogs {LeagueID:'00', Season:'2025-26'|'2026-27', SeasonType:'Regular Season'} -> last 20 games per prop player:
//   name|gp|min|P pts|R reb|A ast|T 3pm|team|last date   (players_raw.txt)

// ---- 4. texas222 (core.texas222.com/wager/Sports.aspx; user must already be logged in; never type credentials)
const open = async (txt) => { const a = [...document.querySelectorAll('a[data-lg]')].find(e => e.innerText.trim() === txt); if (!a) return 'NO ' + txt; a.click(); await new Promise(r => setTimeout(r, 3500)); return 'ok'; };
for (const t of ['NBA', 'NBA  GAME(S) TEAM TOTALS', 'NBA (1H)', 'NBA:  PLAYER PROPS', 'NBA: CHAMPIONSHIP WINNER', 'NBA: EASTERN CONFERENCE WINNER', 'NBA: WESTERN CONFERENCE WINNER']) await open(t);
// then click the Next button at the bottom of the menu, wait 3 s, and read:
window.B = document.body.innerText.replace(/[ \t]+/g, ' ').replace(/\n\s*\n/g, '\n');
window.C = window.B.split('\n').map(s => s.trim()).filter(s => !/^#\d+$/.test(s)).join(' ~ ');
window.D = window.C.replace(/ ~ \d{6} ~ /g, ' | ').replace(/ ~ /g, ' ');
// Props: (AWAY VS HOME) Name Stat - Must Play for Action ... Ov X-price ... Un X-price
const p = window.D.slice(window.D.indexOf('NBA: PLAYER PROPS - '));
window.P = [...p.matchAll(/\((\w+) VS (\w+)\) ([^-]+?) - Must Play for Action [A-Z .'\-]+? (?:\d+:\d+ PM )?Ov ([\d½]+)([+-]\d+) [A-Z .'\-]+? Un [\d½]+([+-]\d+)/g)].map(m => `${m[1]}-${m[2]}|${m[3].trim()}|${m[4].replace('½', '.5')}|${m[5]}|${m[6]}`);
// Write t222.txt (spread | total | ML | TT | 1H), props_raw.txt (game|last name|points|rebounds|assists|threes|line|over|under) and CUP/EAST/WEST in standings_raw.txt.
// Never read or report the balance, available or pending figures.

// ---- 5. Action Network (actionnetwork.com/nba/public-betting and /nba/sharp-report; user has PRO)
const sel = [...document.querySelectorAll('select')][1];
const setv = async v => { Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(sel, v); sel.dispatchEvent(new Event('change', {bubbles: true})); await new Promise(r => setTimeout(r, 3000)); return v + ': ' + [...document.querySelectorAll('table tbody tr')].map(r => r.innerText.replace(/\s*\n\s*/g, ' | ')).join('\n'); };
// public-betting rows: time|away|rot|home|rot|open away|open home|best away|price|best home|price|bets% a|bets% h|money% a|money% h|diff|#bets ; await setv('ml'), setv('total') (default spread)
// sharp-report: columns SHARP ACTION, BIG MONEY, PRO SYSTEMS, MODEL PROJ.; lit button = blue background; 2 buttons per cell = away/home (over/under on Total)
const grab = () => [...document.querySelectorAll('table tbody tr')].map(tr => { const tds = [...tr.querySelectorAll('td')]; const teams = tds[0].innerText.split('\n').filter(x => /[A-Za-z]{3,}/.test(x) && !/PM|AM/.test(x));
  const sig = tds.slice(3, 7).map(td => [...td.querySelectorAll('button')].map(b => { const c = getComputedStyle(b).backgroundColor; return /rgb\((\d+), (\d+), (\d+)/.test(c) && +RegExp.$3 > 180 && +RegExp.$1 < 120 ? 'Y' : '.'; }).join(''));
  return teams.join('/') + ' SA' + sig[0] + ' BM' + sig[1] + ' PS' + sig[2] + ' MP' + sig[3]; }).join('\n');
// Fill AN in signals.py (sig_ml, sig_sp, sig_tot). Model projections go in MODELPROJ (info only).

// ---- 6. Grading finals: https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={espnId}
// boxscore.players[team].statistics[0].athletes[] -> stats array in order of .keys (MIN, PTS, FG, 3PT, ..., REB, AST, ...). DNP = push.

// ================= Added Oct 29, 2026: pick rules and daily re-check =================
// ---- 5c. Second opening source for line-move rules (run in an nba.com tab; ESPN core odds = DraftKings). Write dk_raw.txt:
//   header line, then AWAY-HOME|away spread open|away spread now|total open|total now
const M={NY:'NYK',SA:'SAS',UTAH:'UTA',NO:'NOP',GS:'GSW',WSH:'WAS'};const f=t=>M[t]||t;
// const s=await fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD').then(r=>r.json());
// for each event: j=await fetch('https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/'+id+'/competitions/'+id+'/odds').then(r=>r.json());
//   i=j.items[0]; away spread open = -homeTeamOdds.open.pointSpread; now = -homeTeamOdds.current.pointSpread (or -i.spread); total open = i.open.total; now = i.current.total (or i.overUnder)

// ---- 8. Season dataset (re-check), every run for YESTERDAY's games, append one line per game to season/:
//   espn_odds.txt : date|AWAY|HOME|away pts|home pts|event id|100~<DK open: home spread,home sp price,away sp price,total,over,under,ml away,ml home>~<DK close: same>
//                   (ESPN scoreboard for finals; core odds items[0] open/close; ESPN abbreviations are mapped in season_build.py)
//   an_odds.txt   : from an actionnetwork.com tab, api.actionnetwork.com/web/v2/scoreboard/publicbetting/nba?bookIds=15,30,68,69,71,75,79,972,1006,1902,1903,2194,2292&date=YYYYMMDD&periods=event
//                   date|AWAY|HOME|away pts|home pts|status|S<home spread tickets/money>;M<home ml tickets/money>;O<over tickets/money>;N<bets>|O~<book 30 open>|C15~<book 15>|DK~<book 68>|MEDn~<median of individual books>
//                   each block = home spread value,home sp price,away sp price,total,over price,under price,ml away,ml home.
//                   Medians: spread and total plain medians; prices in DECIMAL odds then back to American; moneylines dropped if under 100 or over 5000 before the median.
//   ratings.txt   : nba.com stats leaguedashteamstats Advanced 2026-27 with DateTo=M/D/YYYY (yesterday): M/D/YYYY|TEAM,GP,ORtg,DRtg,Pace;...
// Then: python3 recheck.py <ledger dir> <today>   (writes rules_state.json and recheck_report.md before render.py runs)

// ================= 9. Prop player data (Nov 10): run in an nba.com/stats tab =================
// q(ep, params) and rs(json) helpers as in section 3. GL25/GL26 = playergamelogs for 2025-26 and 2026-27 (all players).
// PLS = 'Name|stat|line;...' from the texas222 prop list (stat p r a t). Names match after nz(): strip accents, periods, apostrophes, Jr/Sr/II/III/IV.
// For each prop player: season_raw row = name|team now|team last season|GP 25|MPG 25|this season minutes by game|stat+line:avg/sd(sample)/games over line/this season values
// splits_raw row = name|stat+line:h{home avg}x{games}a{road avg}x{games} (last season; home = MATCHUP contains 'vs.')
// B2B rows: both seasons, player-seasons with 20+ games, S = 28+ MPG, O = 15 to 28; b2b = team also played the previous day; games, MPG, PRA per minute.
// usage_raw: per slate team, share of 2026-27 team PTS, REB, AST, FG3M by players listed Out (ESPN injuries).
// matchup_raw: leaguedashteamstats MeasureType Opponent, PerMode Per100Possessions, 2026-27: TEAM last word, GP, OPP_REB, OPP_AST, OPP_FG3M, OPP_FG3A.
// ratings.txt: leaguedashteamstats Advanced 2026-27 DateTo yesterday: TEAM,GP,OFF_RATING,DEF_RATING,PACE (team names mapped to codes in Python).
// Join everything in one string and read it in 950 to 980 character slices (several per browser_batch).
