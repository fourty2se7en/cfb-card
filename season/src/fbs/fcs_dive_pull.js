// FBS vs FCS deep dive, browser pull (Nov 9 2026). Run in a site.api.espn.com tab (javascript_tool); the sandbox shell cannot reach ESPN.
// Set TEAMS to the FCS opponents on this week's FBS slate as {"<CFBD school>": <ESPN team id = CFBD id from repo teams.csv>}.
// Fills window.FCSX; read JSON.stringify(window.FCSX) in 950-character slices and save as fcs_espn.json next to fcs_dive.py.
// Per team: who threw in each of the last 3 games (passing leader line from the ESPN summary), rushing and receiving leaders, and the
// starting QB = passing leader of the last game (flag a change when he did not lead the game before). ESPN college injury feeds are
// empty for FCS, so injuries come only from the team's own notes when posted; leave the list empty otherwise.
const TEAMS = {};   // e.g. {"Tennessee Tech": 2635}
window.FCSX = {};
async function J(u) { for (let i = 0; i < 3; i++) { try { const r = await fetch(u); if (r.ok) return await r.json(); } catch (e) {} await new Promise(r => setTimeout(r, 400 * (i + 1))); } return null; }
(async () => {
  for (const [name, id] of Object.entries(TEAMS)) {
    const s = await J(`https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/${id}/schedule`);
    const done = (s && s.events || []).filter(e => e.competitions[0].status.type.completed).slice(-3);
    const games = [];
    for (const e of done) {
      const j = await J(`https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event=${e.id}`);
      const L = (j && j.leaders || []).find(t => String(t.team.id) == String(id));
      const get = k => { const c = L && L.leaders.find(x => x.name == k); const a = c && c.leaders[0]; return a ? `${a.athlete.displayName} ${a.displayValue}` : null; };
      games.push({date: e.date.slice(0, 10), opp: e.competitions[0].competitors.find(c => String(c.team.id) != String(id)).team.shortDisplayName,
                  pass: get('passingYards'), rush: get('rushingYards'), rec: get('receivingYards')});
    }
    const last = games[games.length - 1], prev = games[games.length - 2];
    const qbn = g => g && g.pass ? g.pass.split(' ').slice(0, 2).join(' ') : null;
    window.FCSX[name] = {qb: qbn(last), qb_line: last && last.pass, qb_change: !!(prev && qbn(prev) && qbn(last) && qbn(prev) != qbn(last)),
                         rb: last && last.rush, wr: last && last.rec, last3: games, injuries: []};
  }
  window.FCSX_DONE = true;
})();
