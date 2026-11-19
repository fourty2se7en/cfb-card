// Rebuilds last season's (2025-26) NCAAW SRS ratings for every Division I team (Nov 7, 2026).
// The old data/ratings_w_2025-26.txt had 36 teams because bt_run.js solved SRS only on games with a posted line.
// This uses every completed D1 vs D1 game (both teams carry an ESPN conferenceId), Nov 3 2025 to Apr 6 2026.
// Same method as bt_run.js solve(): home margin minus 3 (0 at neutral sites), 12 iterations, mean centred at 0.
// Output format matches the old file: TEAM,srs,avg_total_points; ... (recheck.py and build.py read field 2 only).
// Run in Chrome on a site.api.espn.com tab (the sandbox shell cannot reach ESPN). Read window.RW in 950-char slices.
window.WS = {G: [], err: 0, done: 0, prog: ''};
async function J(u, t = 3) { for (let i = 0; i < t; i++) { try { const r = await fetch(u); if (r.ok) return await r.json(); } catch (e) {} await new Promise(r => setTimeout(r, 600 * (i + 1))); } WS.err++; return null; }
const days = []; for (let d = new Date(Date.UTC(2025, 10, 3)); d <= new Date(Date.UTC(2026, 3, 6)); d = new Date(d.getTime() + 864e5)) days.push(d.toISOString().slice(0, 10).replace(/-/g, ''));
(async () => {
  let i = 0;
  await Promise.all(Array.from({length: 6}, async () => { while (i < days.length) { const d = days[i++];
    const s = await J(`https://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/scoreboard?dates=${d}&groups=50&limit=500`); WS.done++;
    for (const e of (s && s.events || [])) { if (!e.status.type.completed) continue; const c = e.competitions[0];
      const h = c.competitors.find(x => x.homeAway == 'home'), w = c.competitors.find(x => x.homeAway == 'away');
      if (!h.team.conferenceId || !w.team.conferenceId) continue;
      WS.G.push([d, h.team.abbreviation, w.team.abbreviation, c.neutralSite ? 1 : 0, +h.score, +w.score, e.id]); } } }));
  const seen = new Set(); const G = WS.G.filter(g => !seen.has(g[6]) && seen.add(g[6]));
  const gs = [], pts = {};
  for (const [d, h, a, nu, hs, as] of G) { const m = hs - as - (nu ? 0 : 3); gs.push([h, a, m], [a, h, -m]); for (const t of [h, a]) (pts[t] = pts[t] || []).push(hs + as); }
  let r = {}; for (const [t] of gs) r[t] = 0;
  for (let it = 0; it < 12; it++) { const s = {}, n = {}; for (const [t, o, m] of gs) { s[t] = (s[t] || 0) + m + (r[o] || 0); n[t] = (n[t] || 0) + 1; }
    for (const t in s) r[t] = s[t] / n[t]; const ks = Object.keys(r), mu = ks.reduce((x, k) => x + r[k], 0) / ks.length; for (const t of ks) r[t] -= mu; }
  window.RW = Object.keys(r).sort().map(t => t + ',' + (+r[t].toFixed(2)) + ',' + Math.round(pts[t].reduce((a, b) => a + b, 0) / pts[t].length)).join(';');
  WS.prog = `DONE ${G.length} games, ${Object.keys(r).length} teams`;   // Nov 7 run: 5625 games, 363 teams
})();
