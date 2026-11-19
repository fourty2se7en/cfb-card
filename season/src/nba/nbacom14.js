const q = async (ep, params) => { const r = await fetch('https://stats.nba.com/stats/' + ep + '?' + new URLSearchParams(params), {headers: {'x-nba-stats-origin': 'stats', 'x-nba-stats-token': 'true'}}); return r.json(); };
const rs = j => { const s = j.resultSets ? j.resultSets[0] : j.resultSet; return s.rowSet.map(r => Object.fromEntries(s.headers.map((h, i) => [h, r[i]]))); };
const base = {MeasureType: 'Advanced', PerMode: 'PerGame', SeasonType: 'Regular Season', LeagueID: '00', LastNGames: 0, Month: 0, OpponentTeamID: 0, PaceAdjust: 'N', Period: 0, PlusMinus: 'N', Rank: 'N', TeamID: 0, Conference: '', DateFrom: '', DateTo: '', Division: '', GameScope: '', GameSegment: '', Location: '', Outcome: '', PORound: 0, PlayerExperience: '', PlayerPosition: '', SeasonSegment: '', ShotClockRange: '', StarterBench: '', TwoWay: 0, VsConference: '', VsDivision: ''};
const nz = s => s.normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[.'’]/g,'').replace(/\b(Jr|Sr|II|III|IV)\b/g,'').replace(/\s+/g,' ').trim().toLowerCase();
const GL25 = rs(await q('playergamelogs', {LeagueID:'00', Season:'2025-26', SeasonType:'Regular Season'}));
const GL26 = rs(await q('playergamelogs', {LeagueID:'00', Season:'2026-27', SeasonType:'Regular Season'}));
const ID2AB = {}; for (const g of GL26) ID2AB[g.TEAM_ID] = g.TEAM_ABBREVIATION;
const RT = rs(await q('leaguedashteamstats', {...base, Season:'2026-27', DateTo:'11/13/2026'}));
window.RAT = '11/13/2026|' + RT.map(t => [ID2AB[t.TEAM_ID], t.GP, t.OFF_RATING, t.DEF_RATING, t.PACE].join(',')).join(';');
const OP = rs(await q('leaguedashteamstats', {...base, MeasureType:'Opponent', PerMode:'Per100Possessions', Season:'2026-27'}));
window.OPP = 'OPP 2026-27 ' + OP.map(t => [t.TEAM_NAME.split(' ').pop(), t.GP, t.OPP_REB, t.OPP_AST, t.OPP_FG3M, t.OPP_FG3A].join(',')).join(';');
const by = (L) => { const m = {}; for (const g of L) (m[nz(g.PLAYER_NAME)] ||= []).push(g); for (const k in m) m[k].sort((a,b) => a.GAME_DATE < b.GAME_DATE ? -1 : 1); return m; };
const P25 = by(GL25), P26 = by(GL26);
const SK = {p:'PTS', r:'REB', a:'AST', t:'FG3M'};
const PLS = "".split(';').filter(Boolean).map(x => x.split('|'));
const order = []; const lines = {}; for (const [n, s, l] of PLS) { if (!lines[n]) { lines[n] = []; order.push(n); } lines[n].push([s, +l]); }
const sr = [], sp = [];
const r1 = x => (Math.round(x*10)/10).toFixed(1);
for (const n of order) { const a = P25[nz(n)] || [], b = P26[nz(n)] || [];
  const tn = b.length ? b[b.length-1].TEAM_ABBREVIATION : (a.length ? a[a.length-1].TEAM_ABBREVIATION : '-'); const tl = a.length ? a[a.length-1].TEAM_ABBREVIATION : '-';
  const mpg = a.length ? a.reduce((s,g)=>s+g.MIN,0)/a.length : 0;
  const toks = [], stoks = [];
  for (const [s, l] of lines[n]) { const v = a.map(g => g[SK[s]]); const av = v.length ? v.reduce((x,y)=>x+y,0)/v.length : 0;
    const sd = v.length > 1 ? Math.sqrt(v.reduce((x,y)=>x+(y-av)**2,0)/(v.length-1)) : 0; const ov = v.filter(x => x > l).length;
    toks.push(s + l + ':' + r1(av) + '/' + r1(sd) + '/' + ov + '/' + b.map(g => g[SK[s]]).join('-'));
    const h = a.filter(g => /vs\./.test(g.MATCHUP)).map(g => g[SK[s]]), w = a.filter(g => /@/.test(g.MATCHUP)).map(g => g[SK[s]]);
    const avg = x => x.length ? x.reduce((p,q)=>p+q,0)/x.length : 0;
    stoks.push(s + l + ':h' + r1(avg(h)) + 'x' + h.length + 'a' + r1(avg(w)) + 'x' + w.length); }
  sr.push([n, tn, tl, a.length, r1(mpg), b.map(g => Math.round(g.MIN)).join('-'), toks.join(' ')].join('|'));
  sp.push(n + '|' + stoks.join(' ')); }
window.SRW = sr.join('\n'); window.SPW = sp.join('\n');
// B2B rows
const b2b = (L) => { const byP = {}; for (const g of L) (byP[g.PLAYER_ID] ||= []).push(g); const tdays = {}; for (const g of L) (tdays[g.TEAM_ID] ||= new Set()).add(g.GAME_DATE.slice(0,10));
  const acc = {S:[0,0,0,0,0,0], O:[0,0,0,0,0,0]};
  for (const pid in byP) { const gs = byP[pid]; if (gs.length < 20) continue; const mpg = gs.reduce((s,g)=>s+g.MIN,0)/gs.length; const grp = mpg >= 28 ? 'S' : (mpg >= 15 ? 'O' : null); if (!grp) continue;
    for (const g of gs) { const d = new Date(g.GAME_DATE.slice(0,10)+'T12:00:00Z'); d.setUTCDate(d.getUTCDate()-1); const prev = d.toISOString().slice(0,10); const isb = tdays[g.TEAM_ID].has(prev);
      const o = isb ? 0 : 3; acc[grp][o] += 1; acc[grp][o+1] += g.MIN; acc[grp][o+2] += g.PTS + g.REB + g.AST; } }
  return acc; };
const A1 = b2b(GL25), A2 = b2b(GL26); const B = [];
for (const k of ['S','O']) { const t = A1[k].map((x,i) => x + A2[k][i]); B.push('B2B|' + k + '|' + [t[0], (t[1]/t[0]).toFixed(2), (t[2]/t[1]).toFixed(4), t[3], (t[4]/t[3]).toFixed(2), (t[5]/t[4]).toFixed(4)].join(',')); }
window.B2BW = B.join('\n');
// usage
const OUT = {"BKN": [], "CHI": ["Dailyn Swain", "Tobe Awaka", "Caleb Wilson"], "CLE": ["Evan Mobley", "Sam Merrill", "Nae'Qwan Tomlin"], "DAL": ["Dereck Lively II", "Tarik Biberovic", "Sergio de Larrea"], "DEN": ["Julian Strawther"], "DET": ["Isaiah Joe", "Jalen Duren"], "MEM": ["Quinten Post", "Zach Edey", "Scotty Pippen Jr.", "Richie Saunders"], "MIA": ["Klay Thompson", "Pelle Larsson"], "MIN": ["Anthony Edwards", "Donte DiVincenzo"], "NOP": ["Dejounte Murray", "Bryce McGowens", "Yves Missi", "Trey Murphy III", "Trendon Watford"]};
const U = [];
for (const t in OUT) { const tg = GL26.filter(g => g.TEAM_ABBREVIATION === t); const tot = k => tg.reduce((s,g)=>s+g[k],0); const outs = OUT[t].map(nz);
  const og = tg.filter(g => outs.includes(nz(g.PLAYER_NAME))); const sh = k => (tot(k) ? og.reduce((s,g)=>s+g[k],0)/tot(k) : 0).toFixed(3);
  const names = OUT[t].map(n => { const c = og.filter(g => nz(g.PLAYER_NAME) === nz(n)).length; return c ? n + '(' + c + 'g)' : null; }).filter(Boolean);
  U.push(t + '|' + ['PTS','REB','AST','FG3M'].map(sh).join(',') + '|' + names.join(',')); }
window.USW = U.join('\n');

// lineups: last 5 team games per slate team
const SLATE=["DEN", "NOP", "DAL", "CLE", "DET", "MIA", "BKN", "MEM", "CHI", "MIN"]; const pl={};
for (const g of GL26) { (pl[g.PLAYER_ID] ||= []).push(g); }
const comp=[]; const P36={};
for (const id in pl){ const gs=pl[id]; const m=gs.reduce((s,g)=>s+g.MIN,0); if (m<60) continue; const f=k=>gs.reduce((s,g)=>s+g[k],0)*36/m;
  const fga=gs.reduce((s,g)=>s+g.FGA,0), fgm=gs.reduce((s,g)=>s+g.FGM,0);
  const o={pts:f('PTS'),reb:f('REB'),ast:f('AST'),t3:f('FG3M'),sb:f('STL')+f('BLK'),tov:f('TOV'),fg:fga?fgm/fga:0}; o.c=o.pts+1.2*o.reb+1.5*o.ast+2*o.sb-o.tov; P36[id]=o; comp.push(o); }
const pct=(k,v)=>Math.round(100*comp.filter(o=>o[k]<v).length/comp.length);
const LUW=[];
for (const t of SLATE){ const tg=GL26.filter(g=>g.TEAM_ABBREVIATION===t); const dates=[...new Set(tg.map(g=>g.GAME_DATE.slice(0,10)))].sort().slice(-5);
  const ps={}; for (const g of tg) if (dates.includes(g.GAME_DATE.slice(0,10))) (ps[g.PLAYER_NAME] ||= {id:g.PLAYER_ID,min:0}).min+=g.MIN;
  const rows=Object.entries(ps).map(([n,v])=>[n,Math.round(v.min/dates.length),v.id]).filter(r=>r[1]>=8).sort((a,b)=>b[1]-a[1]).slice(0,11);
  LUW.push(t+'#'+rows.map(([n,m,id])=>{const o=P36[id]; if(!o) return [n,m,'','','',''].join('~');
    const s=(pct('pts',o.pts)>=75?'S':'')+(pct('reb',o.reb)>=75?'R':'')+(pct('ast',o.ast)>=75?'P':'')+(pct('t3',o.t3)>=75?'T':'')+(pct('sb',o.sb)>=75?'D':'');
    const w=(pct('pts',o.pts)<25?'s':'')+(pct('tov',o.tov)>=80?'o':'')+(pct('fg',o.fg)<25?'f':'');
    return [n,m,pct('c',o.c),s,w,''].join('~');}).join(';')); }
window.LUW=LUW.join('\n');

window.ALLN = ['#RAT', window.RAT, '#OPP', window.OPP, '#B2B', window.B2BW, '#USG', window.USW, '#SR', window.SRW, '#SP', window.SPW, '#LU', window.LUW].join('\n');
window.ALLN.length + ' ' + GL25.length + ' ' + GL26.length
