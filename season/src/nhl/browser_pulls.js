// ===== NHL Card: browser data pulls (run with javascript_tool in Chrome) =====
// Output is capped near 1,500 chars per call: store results on window and print in slices.

// ---- 1. NHL API (open a tab on https://api-web.nhle.com/v1/schedule/YYYY-MM-DD first; same-origin fetches) ----
// Slate:
const s = JSON.parse(document.body.innerText);
window.G = s.gameWeek.find(d => d.date === 'YYYY-MM-DD').games.map(g => ({id: g.id, away: g.awayTeam.abbrev, home: g.homeTeam.abbrev, start: g.startTimeUTC, venue: g.venue?.default}));

// Team game logs + per-game right rail (shots, PP, 1st period):
const j = async u => { for (let i = 0; i < 3; i++) { try { const r = await fetch(u, {cache: 'no-store'}); if (r.ok) return r.json(); } catch (e) {} await new Promise(r => setTimeout(r, 400)); } return null; };
const teams = [...new Set(window.G.flatMap(g => [g.away, g.home]))];
const RR = window.RR = window.RR || {}; const T = window.T = {};
for (const t of teams) {
  const sch = await j(`/v1/club-schedule-season/${t}/now`);
  const gs = sch.games.filter(g => g.gameType === 2 && (g.gameState === 'OFF' || g.gameState === 'FINAL'));
  T[t] = {games: gs.map(g => ({id: g.id, date: g.gameDate, home: g.homeTeam.abbrev === t, opp: g.homeTeam.abbrev === t ? g.awayTeam.abbrev : g.homeTeam.abbrev,
    gf: g.homeTeam.abbrev === t ? g.homeTeam.score : g.awayTeam.score, ga: g.homeTeam.abbrev === t ? g.awayTeam.score : g.homeTeam.score, last: g.gameOutcome?.lastPeriodType}))};
}
const ids = [...new Set(Object.values(T).flatMap(x => x.games.map(g => g.id)))].filter(id => !RR[id]);
for (let i = 0; i < ids.length; i += 8) await Promise.all(ids.slice(i, i + 8).map(async id => { RR[id] = await j(`/v1/gamecenter/${id}/right-rail`); }));
// Aggregate per team (record, home/road, GF/GA, SF/SA, PP, PK, 1P, last game, rest, gf/ga/1P strings) into the
// teams_raw.txt line format:  TEAM rec Hhome Rroad L10 x GFx GAx hHGF/HGA rRGF/RGA SFx SAx PPx% (g/o) PKx% (ga/o) 1Pf/a last:DATE vs|@ OPP gf-ga restN gf[...] ga[...] 1P[...]
// (rest = days between last game and today minus 1; 0 = back-to-back).
// valfn: rr.teamGameStats.find(c => c.category === 'sog'|'powerPlay')[side+'Value']; 1P from rr.linescore.byPeriod[number==1].

// Skaters + goalies (club-stats) and player game logs:
//   /v1/club-stats/{TEAM}/now  -> skaters (top 4 by points + top 3 by shots, gp>=4), goalies
//   /v1/player/{id}/game-log/now -> per game shots, points, goals, assists, powerPlayPoints
// Write skaters_raw.txt lines:  TEAM: Name Ng G-A-P SHsh s2:x s3:x s4:x pX gX aX ppX | ...
// and the GOALIES block:  TEAM Name GS W-L-OT GAA .SV; ...

// Standings now and last season final:
//   /v1/standings/now  -> standings_raw.txt rows (team,conf,div,gp,w,l,ot,pts,ppct,rw,gf,ga,diff,l10,strk,home,road,lgseq,wcseq)
//   /v1/standings/2026-04-16 -> LAST dict in signals.py (2025-26 final points % and goal diff). Update each new season.

// ---- 2. texas222 (core.texas222.com/wager/Sports.aspx; user must already be logged in; never type credentials) ----
const open = async (txt) => { const a = [...document.querySelectorAll('a[data-lg]')].find(e => e.innerText.trim() === txt); if (!a) return 'NO LINK ' + txt; a.click(); await new Promise(r => setTimeout(r, 3500)); return 'ok'; };
for (const t of ['NATIONAL HOCKEY LEAGUE','NHL TEAM TOTALS','NHL (1P)','NHL - 3 WAY LINES (REGULATION TIME ONLY)','NHL: GAME PROPS','NHL: STANLEY CUP WINNER','NHL: EASTERN CONFERENCE WINNER','NHL: WESTERN CONFERENCE WINNER']) await open(t);
window.B = document.body.innerText.replace(/[ \t]+/g, ' ').replace(/\n\s*\n/g, '\n');
// Parse into t222.txt lines: TEAM: puckline price | O/U line price | ML | TT Oline-price Uline+price | 1P pl price, O/U line price, ML | 3W ML | S1 price | draw +price
// and the CUP / WEST / EAST lines in standings_raw.txt. Never read or report the balance/available/pending header.
// texas222 has NO NHL player props (props builder hockey = Finland, KHL, AHL only).

// ---- 3. Action Network (actionnetwork.com/nhl/public-betting and /nhl/sharp-report; user has PRO) ----
// public-betting: rows = time|away|rot|home|rot|open away|open home|best away|best home|bets% a|bets% h|money% a|money% h|diff|#bets
const sel = [...document.querySelectorAll('select')][1];
const setv = async v => { Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(sel, v); sel.dispatchEvent(new Event('change', {bubbles: true})); await new Promise(r => setTimeout(r, 3000)); return [...document.querySelectorAll('table tbody tr')].map(r => r.innerText.replace(/\s*\n\s*/g, ' | ')); };
// await setv('ml'), setv('spread'), setv('total')
// sharp-report: lit (blue) signal buttons per row; 2 buttons per cell = away/home (or over/under on Total)
const grab = () => [...document.querySelectorAll('table tbody tr')].map(tr => { const tds = [...tr.querySelectorAll('td')];
  const teams = tds[0].innerText.split('\n').filter(x => /[A-Za-z]{3,}/.test(x) && !/PM|AM/.test(x));
  const sig = [3,4,5,6].map(i => [...tds[i].querySelectorAll('button')].map(b => { const c = getComputedStyle(b).backgroundColor; return /rgb\((\d+), (\d+), (\d+)/.test(c) && +RegExp.$3 > 180 && +RegExp.$1 < 120 ? 'Y' : '.'; }).join(''));
  return teams.join('/') + ' SA' + sig[0] + ' BM' + sig[1] + ' PS' + sig[2] + ' MP' + sig[3]; });
// Columns: SA Sharp Action, BM Big Money, PS PRO Systems, MP Model Projections. Fill signals.py AN dict.

// ---- 4. Daily Faceoff starting goalies (dailyfaceoff.com/starting-goalies/YYYY-MM-DD) ----
const lines = document.body.innerText.split('\n').map(s => s.trim()).filter(Boolean); const out = [];
for (let i = 0; i < lines.length; i++) { if (/ at /.test(lines[i]) && /\d{4} \| /.test(lines[i+1] || '')) out.push('# ' + lines[i]);
  if (/^(Confirmed|Likely|Expected|Unconfirmed|Projected)$/i.test(lines[i])) out.push(lines[i-1] + ' = ' + lines[i]); }
// Print in slices; fill GAMES in model.py (away goalie, status, home goalie, status).
// Backup (added Nov 2): rotowire.com/hockey/starting-goalies.php (Today's Games). Read it whenever a Daily Faceoff goalie is not Confirmed,
// a game is missing, or Daily Faceoff conflicts with injury news. Use the stronger status of the two sources for the same goalie
// (RotoWire Confirmed = Confirmed; RotoWire Expected = Likely). If the sources name different goalies, prefer the one Confirmed by either;
// if neither is confirmed, keep Daily Faceoff's goalie and add a NOTES line naming both. RotoWire times are Eastern.
//   const t=document.body.innerText; t.slice(t.indexOf('Time'), t.indexOf('Lineup Optimizer'))

// ---- Added Oct 23: full teams_raw aggregation (run after T and RR above; T[t] here is the games array, set TODAY) ----
// const TODAY=new Date('YYYY-MM-DDT12:00:00Z');
// const f2=x=>x.toFixed(2), rec=a=>{let w=0,l=0,o=0;for(const g of a){if(g.gf>g.ga)w++;else if(g.last==='REG')l++;else o++;}return `${w}-${l}-${o}`;};
// const avg=(a,k)=>a.length?a.reduce((s,g)=>s+g[k],0)/a.length:0; window.LINES=[];
// for(const [t,gs] of Object.entries(window.T)){ for(const g of gs){const r=window.RR[g.id];const side=g.home?'home':'away',os=g.home?'away':'home';
//   const v=(c,sd)=>r.teamGameStats.find(x=>x.category===c)[sd+'Value']; g.sf=+v('sog',side); g.sa=+v('sog',os);
//   const pp=v('powerPlay',side).split('/'),pk=v('powerPlay',os).split('/'); g.ppg=+pp[0];g.ppo=+pp[1];g.pkga=+pk[0];g.pko=+pk[1];
//   const p1=r.linescore.byPeriod.find(p=>p.periodDescriptor.number===1); g.p1f=p1[side]; g.p1a=p1[os];}
//  const H=gs.filter(g=>g.home),R=gs.filter(g=>!g.home),L=gs.slice(-10),lg=gs[gs.length-1],sum=k=>gs.reduce((s,g)=>s+g[k],0);
//  const rest=Math.round((TODAY-new Date(lg.date+'T12:00:00Z'))/864e5)-1;
//  LINES.push(`${t} ${rec(gs)} H${rec(H)} R${rec(R)} L10 ${rec(L)} GF${f2(avg(gs,'gf'))} GA${f2(avg(gs,'ga'))} h${f2(avg(H,'gf'))}/${f2(avg(H,'ga'))} r${f2(avg(R,'gf'))}/${f2(avg(R,'ga'))} SF${avg(gs,'sf').toFixed(1)} SA${avg(gs,'sa').toFixed(1)} PP${(100*sum('ppg')/sum('ppo')).toFixed(1)}% (${sum('ppg')}/${sum('ppo')}) PK${(100-100*sum('pkga')/sum('pko')).toFixed(1)}% (${sum('pkga')}/${sum('pko')}) 1P${f2(avg(gs,'p1f'))}/${f2(avg(gs,'p1a'))} last:${lg.date} ${lg.home?'vs':'@'} ${lg.opp} ${lg.gf}-${lg.ga} rest${rest} gf[${gs.map(g=>Math.min(g.gf,9)).join('')}] ga[${gs.map(g=>Math.min(g.ga,9)).join('')}] 1P[${gs.map(g=>g.p1f).join('')}]`); }
// Skater pp field = sum of game-log powerPlayPoints. texas222: after clicking the menu links, click "Next" to load the lines.
// Check injury news in previews: drop injured skaters from skaters_raw and note it in NOTES.

// ---- Added Oct 27: division strength (divs_raw.txt). Run on api-web.nhle.com; loops /v1/score/DATE from opening night to yesterday.
// const st=await (await fetch('/v1/standings/now')).json(); const DIV={}; st.standings.forEach(t=>DIV[t.teamAbbrev.default]=t.divisionName);
// loop dates -> games (gameType 2, OFF/FINAL, dedupe id) -> for cross-division games add W/L/OTL, GF, GA to 'DIV>ALL' and 'DIV>OPPDIV' for both sides.
// Write lines: 'Atlantic>Pacific W L OTL GF GA'. divisions.py turns them into the Division strength signal and the Standings table.

// ===== Daily re-check pulls (start of every card run, before today's pulls). Append every date from the day after the last
// date in review/ng.txt through yesterday to review/ng.txt, sb.txt, ah.txt, sh2.txt and dk.txt. Final games only.
// Export rule: build the text on window, print in ~980 character slices (browser_batch, several slices per call), then print a
// hash and length and check them in python:
//   JS:  [...TXT].reduce((h,c)=>(h*31+c.charCodeAt(0))%1000000007,7)      PY: h=7; for c in s: h=(h*31+ord(c))%1000000007
// 1. NHL API (tab on api-web.nhle.com): /v1/score/YYYY-MM-DD for the game ids, then per game /v1/gamecenter/{id}/boxscore
//    (sog, starter goalie name:shotsAgainst:goalsAgainst) and /right-rail (powerPlay, 1st period).
//    Line: id%100000|MM-DD|away|home|ag|hg|lastPeriodType|asog|hsog|Goalie:sa:ga|Goalie:sa:ga|ppg/ppo away|ppg/ppo home|p1away-p1home
// 2. SBR (tab on sportsbookreview.com): fetch /betting-odds/nhl-hockey/{'',pointspread/,totals/}?date=YYYY-MM-DD, parse __NEXT_DATA__
//    props.pageProps.oddsTables[0].oddsTableModel.gameRows; per market take each book's currentLine (close) and openingLine;
//    drop quotes under 100 or over 5000, drop -110/-110 placeholders when the median is not near even, drop books 8+ no-vig points off the median;
//    medians in DECIMAL odds. Line: MM-DD|AWAY|HOME|mlclose a/h|mlopen a/h|PLsp a/h PLopen-sp a/h|TOTline o/u TOTopen o/u
// 3. Action Network public betting (actionnetwork.com/nhl/public-betting, PRO login): step back with button[aria-label="Previous Date"];
//    on each date set the 2nd select to ml, spread, total (wait ~2.5s each) and confirm every row starts with "Final" (else re-grab that date).
//    Line: MM-DD|Away nickname|Home nickname|open a/h|bets% away|money% away|PL open spread away|PL bets away|PL money away|total open|over bets|over money
// 4. Action Network sharp report (/nhl/sharp-report): same date stepping; for ml, spread, total read lit buttons per row (blue background:
//    rgb B>180 and R<120), columns SA, BM, PS, two buttons each (away/home or over/under). Confirm every row is Final.
//    Line: MM-DD|Away nickname|Home nickname|SAx BMx PSx for ml (6 chars Y/.)|same for spread|same for total
// 5. DraftKings via ESPN (open a tab on sports.core.api.espn.com; same-origin fetches; do not print URLs with query strings):
const am=v=>v&&v.american!=null?v.american:(v&&v.alternateDisplayValue)||'';
async function dkLines(dates /* ['20261029',...] */){
  const L=[];
  for(const ds of dates){
    const sb=await fetch('https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates='+ds).then(r=>r.json());
    await Promise.all(sb.events.map(async e=>{const c=e.competitions[0];const A=c.competitors.find(t=>t.homeAway==='away'),H=c.competitors.find(t=>t.homeAway==='home');
      let o='';const j=await fetch(`https://sports.core.api.espn.com/v2/sports/hockey/leagues/nhl/events/${e.id}/competitions/${e.id}/odds`).then(r=>r.json());
      const x=(j.items||[]).find(i=>i.provider&&i.provider.id==='100')||(j.items||[])[0];
      if(x){const a=x.awayTeamOdds||{},h=x.homeTeamOdds||{};const f=k=>[am((a[k]||{}).moneyLine),am((h[k]||{}).moneyLine),am((a[k]||{}).pointSpread),am((a[k]||{}).spread),am((h[k]||{}).spread),am(((x[k]||{}).total)),am(((x[k]||{}).over)),am(((x[k]||{}).under))].join(',');o=f('open')+'|'+f('close');}
      const st={post:'F',in:'I',pre:'P'}[c.status.type.state]||c.status.type.state;
      L.push([ds.slice(4),A.team.abbreviation,H.team.abbreviation,st,A.score,H.score,o].join('|'));}));
  }
  L.sort(); window.DKT=L.filter(l=>l.split('|')[3]==='F').join('\n'); return {n:L.length, len:DKT.length};
}
//    Line: MMDD|AWAY|HOME|F|ag|hg|open: ml away,ml home,pl spread away,pl away,pl home,total,over,under|close: same (ESPN codes LA, NJ, SJ, TB are mapped in build_data)
// 6. Pick-time second source for TODAY: same odds endpoint, use "current" (x.awayTeamOdds.current / x.current) for today's games ->
//    signals.DK['AWAY-HOME'] = dict(ml=(a, h), pl=(sp_a, price_a, price_h), total=(line, over, under)). It is logged to the inputs collection.
// Then: save the ledger query (all picks) as review/ledger/picks/<doc_id>.json, and run
//   cd review && python3 build_data.py && python3 recheck.py   -> ../rules_state.json, recheck.json, recheck_report.md
