// ===== NBA season dataset and backtest pulls used Nov 6, 2026 (run with javascript_tool in Chrome) =====
// Output truncates near 1,000 chars per call: store results on window and read 930-char slices, one slice per call.

// ---- A. ESPN finals plus DraftKings open and close (any espn.com tab). One espn_odds.txt row per game.
//      Only keep STATUS_FINAL games. ESPN "close" is the pre-game close even after tip.
const am=x=>x?.american??x?.alternateDisplayValue??'';
const odds=async id=>{const j=await fetch('https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/'+id+'/competitions/'+id+'/odds').then(r=>r.json());return (j.items||[]).find(x=>x.provider?.id=='100')||j.items[0]};
const y=await fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD').then(r=>r.json());const er=[];
for(const e of y.events){const c=e.competitions[0];const h=c.competitors.find(x=>x.homeAway=='home'),a=c.competitors.find(x=>x.homeAway=='away');const i=await odds(e.id);
 const blk=k=>[am(i.homeTeamOdds?.[k]?.pointSpread),am(i.homeTeamOdds?.[k]?.spread),am(i.awayTeamOdds?.[k]?.spread),(i[k]?.total?.american??'').replace(/^[ou]/,''),am(i[k]?.over),am(i[k]?.under),am(i.awayTeamOdds?.[k]?.moneyLine),am(i.homeTeamOdds?.[k]?.moneyLine)].join(',');
 er.push([e.status.type.name,'YYYY-MM-DD',a.team.abbreviation,h.team.abbreviation,a.score,h.score,e.id,'100~'+blk('open')+'~'+blk('close')].join('|'))}
window.ER=er.join('\n');   // drop the leading status field before appending to season/espn_odds.txt

// ---- B. Action Network closing data (actionnetwork.com tab). One an_odds.txt row per game.
//      Must run after the game is final and NOT while it is in progress: once a game tips, book 15 lines and splits turn live.
const AJ=await fetch('https://api.actionnetwork.com/web/v2/scoreboard/publicbetting/nba?bookIds=15,30,68,69,71,75,79,972,1006,1902,1903,2194,2292&date=YYYYMMDD&periods=event').then(r=>r.json());
const fx=x=>x==null?'':''+x;
const blkA=ev=>{if(!ev)return null;const sh=(ev.spread||[]).find(o=>o.side=='home'),sa=(ev.spread||[]).find(o=>o.side=='away'),ov=(ev.total||[]).find(o=>o.side=='over'),un=(ev.total||[]).find(o=>o.side=='under'),ma=(ev.moneyline||[]).find(o=>o.side=='away'),mh=(ev.moneyline||[]).find(o=>o.side=='home');return {sh,sa,ov,un,ma,mh,a:[sh?.value,sh?.odds,sa?.odds,ov?.value,ov?.odds,un?.odds,ma?.odds,mh?.odds]}};
const dec=o=>o>0?1+o/100:1+100/-o;const amr=d=>d>=2?Math.round((d-1)*100):Math.round(-100/(d-1));const med=a=>{a=a.filter(x=>x!=null&&!isNaN(x)).sort((x,y)=>x-y);if(!a.length)return '';const m=a.length>>1;return a.length%2?a[m]:(a[m-1]+a[m])/2};
window.ANR=AJ.games.map(g=>{const A=g.teams.find(t=>t.id==g.away_team_id).abbr,H=g.teams.find(t=>t.id==g.home_team_id).abbr;const m=g.markets||{};const B={};for(const k in m)B[k]=blkA(m[k].event);
 const b15=B['15'];const pct=(o,k)=>o?.bet_info?.[k]?.percent??'';const S=`S${pct(b15?.sh,'tickets')}/${pct(b15?.sh,'money')};M${pct(b15?.mh,'tickets')}/${pct(b15?.mh,'money')};O${pct(b15?.ov,'tickets')}/${pct(b15?.ov,'money')};N${g.num_bets??''}`;
 const ind=Object.keys(B).filter(k=>!['15','30'].includes(k)&&B[k]);const col=i=>ind.map(k=>B[k].a[i]).filter(x=>x!=null);
 const md=[med(col(0)),...[1,2].map(i=>{const c=col(i);return c.length?amr(med(c.map(dec))):''}),med(col(3)),...[4,5].map(i=>{const c=col(i);return c.length?amr(med(c.map(dec))):''}),...[6,7].map(i=>{const c=col(i).filter(x=>Math.abs(x)>=100&&Math.abs(x)<=5000);return c.length?amr(med(c.map(dec))):''})];
 const J=a=>a?a.map(fx).join(','):'';
 return ['YYYY-MM-DD',A,H,g.boxscore?.total_away_points,g.boxscore?.total_home_points,g.status,S,'O~'+J(B['30']?.a),'C15~'+J(b15?.a),'DK~'+J(B['68']?.a),'MED'+ind.length+'~'+md.join(',')].join('|')}).join('\n');
// keep only rows with status "complete"

// ---- C. 1H and Q1 closing lines plus period scores (actionnetwork.com tab) -> season/plines.txt
//      Book 15 (consensus) value, else the median of individual books. Same in-progress caveat as B.
//      2H and Q2 to Q4 markets are in-game lines only, so they are not saved.
const days=['YYYY-MM-DD'];   // or build a date range
const rows=[];
for(const d of days){const j=await fetch('https://api.actionnetwork.com/web/v2/scoreboard/publicbetting/nba?bookIds=15,30,68,69,71,75,79,972,1006,1902,1903,2194,2292&date='+d.replace(/-/g,'')+'&periods=event,firsthalf,firstquarter').then(r=>r.json());
 for(const g of j.games||[]){if(g.status!=='complete')continue;const A=g.teams.find(t=>t.id==g.away_team_id).abbr,H=g.teams.find(t=>t.id==g.home_team_id).abbr;const M=g.markets||{};
  const per=p=>{const pick=b=>{const e=M[b]?.[p];if(!e)return null;const sa=(e.spread||[]).find(o=>o.side=='away'),ov=(e.total||[]).find(o=>o.side=='over');return [sa?.value,ov?.value]};
   const c=pick('15');const ind=Object.keys(M).filter(b=>!['15','30'].includes(b)).map(pick).filter(Boolean);
   const sp=c&&c[0]!=null?c[0]:med(ind.map(x=>x[0]));const tt=c&&c[1]!=null?c[1]:med(ind.map(x=>x[1]));return sp+','+tt};
  const ls=(g.boxscore?.linescore||[]).map(x=>[x.away_points,x.home_points]);const q1=ls[0]||[],q2=ls[1]||[];
  const h1=q1.length&&q2.length?[q1[0]+q2[0],q1[1]+q2[1]]:[];
  rows.push([d.slice(5),A,H,per('firsthalf'),per('firstquarter'),(q1.join(',')||'-')+';'+(h1.join(',')||'-')].join('|'))}}
window.PL=rows.join('\n');
