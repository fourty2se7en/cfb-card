// QB usage pull (Nov 9 2026). Paste the window.IDS line printed by `python3 qb_usage.py ids`, then this script, in a site.api.espn.com tab.
// For every finished 2026 game with an FBS team: ESPN summary box score, passing attempts per passer per team. When window.QUfin is true,
// window.QU holds teamId|qb1_by_attempts|share|leader_of_last_game (last = latest game in week order). Read it in 950-character slices.
window.QB = []; window.QUfin = false;
(async () => {
  let i = 0; const ids = window.IDS, pos = {}; ids.forEach((id, k) => pos[id] = k);
  async function J(u) { for (let k = 0; k < 3; k++) { try { const r = await fetch(u); if (r.ok) return await r.json(); } catch (e) {} await new Promise(r => setTimeout(r, 400 * (k + 1))); } return null; }
  await Promise.all(Array.from({length: 6}, async () => { while (i < ids.length) { const id = ids[i++];
    const j = await J('https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event=' + id); const out = [];
    for (const t of (j && j.boxscore && j.boxscore.players) || []) { const p = (t.statistics || []).find(s => s.name == 'passing'); if (!p) continue; const ix = p.labels.indexOf('C/ATT');
      out.push(t.team.id + '~' + (p.athletes || []).map(a => a.athlete.displayName.replace(/[;:~|]/g, '') + ':' + String(a.stats[ix] || '0/0').split('/')[1]).join(';')); }
    window.QB.push(id + '|' + out.join('|')); } }));
  const T = {};
  for (const row of window.QB) { const f = row.split('|'); const gi = pos[f[0]];
    for (const part of f.slice(1)) { const [tid, ps] = part.split('~'); if (!ps) continue; const t = T[tid] || (T[tid] = {att: {}, last: [-1, null]}); let lead = null, lm = -1;
      for (const x of ps.split(';')) { const k = x.lastIndexOf(':'); const n = x.slice(0, k), a = +x.slice(k + 1) || 0; t.att[n] = (t.att[n] || 0) + a; if (a > lm) { lm = a; lead = n; } }
      if (gi > t.last[0]) t.last = [gi, lead]; } }
  window.QU = Object.entries(T).map(([tid, t]) => { const tot = Object.values(t.att).reduce((a, b) => a + b, 0); const [q, a] = Object.entries(t.att).sort((x, y) => y[1] - x[1])[0] || ['', 0];
    return tid + '|' + q + '|' + (tot ? (a / tot).toFixed(2) : '0') + '|' + t.last[1]; }).join('\n');
  window.QUfin = true;
})();
