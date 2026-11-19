// NCAAM backtest dataset v2 (Nov 2, 2026): adds box score possessions for the efficiency model test.
// Runs in a site.api.espn.com tab. Seasons 2022-23 (box only, prior season for 2023-24) to 2025-26 (box + core odds).
// Row: [season, date, home, away, neutral, conf_game, home_pts, away_pts, hFGA, hORB, hTO, hFTA, aFGA, aORB, aTO, aFTA,
//       dk_open_sp, dk_close_sp, dk_open_tot, dk_close_tot, s2_open_sp, s2_close_sp, s2_open_tot, s2_close_tot, med_sp, med_tot]  (home spread)
window.B2 = window.B2 || {rows: [], done: {}, err: 0, prog: ''};
(function () {
  const L = 'mens-college-basketball';
  const SEASONS = {'2022-23': ['20221107', '20230403', false], '2023-24': ['20231106', '20240408', true], '2024-25': ['20241104', '20250407', true], '2025-26': ['20251103', '20260406', true]};
  const num = x => x == null ? null : (typeof x === 'object' ? (x.american != null ? parseFloat(String(x.american).replace('+', '')) : x.value) : parseFloat(x));
  const med = v => { v = v.filter(x => x != null && !isNaN(x)).sort((a, b) => a - b); if (!v.length) return null; const m = v.length >> 1; return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2; };
  const days = (a, b) => { const o = []; let d = new Date(a.slice(0,4)+'-'+a.slice(4,6)+'-'+a.slice(6)+'T12:00:00Z'); const e = new Date(b.slice(0,4)+'-'+b.slice(4,6)+'-'+b.slice(6)+'T12:00:00Z'); while (d <= e) { o.push(d.toISOString().slice(0,10).replace(/-/g,'')); d = new Date(d.getTime()+864e5); } return o; };
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  async function J(u) { for (let i = 0; i < 4; i++) { try { const r = await fetch(u); if (r.ok) return await r.json(); if (r.status === 404) return null; } catch (e) {} await sleep(800 * (i + 1)); } B2.err++; return null; }
  async function pool(ts, n) { let i = 0; await Promise.all(Array.from({length: n}, async () => { while (i < ts.length) { const t = ts[i++]; await t(); await sleep(40); } })); }
  function box(j, abbr) {
    const t = (j && j.boxscore && j.boxscore.teams || []).find(x => x.team.abbreviation === abbr); if (!t) return [null, null, null, null];
    const g = n => { const s = t.statistics.find(z => z.name === n); return s ? s.displayValue : null; };
    const fga = (g('fieldGoalsMade-fieldGoalsAttempted') || '').split('-')[1], fta = (g('freeThrowsMade-freeThrowsAttempted') || '').split('-')[1];
    return [+fga || null, +g('offensiveRebounds') || 0, +(g('totalTurnovers') || g('turnovers')) || 0, +fta || 0];
  }
  async function odds(id) {
    const j = await J(`https://sports.core.api.espn.com/v2/sports/basketball/leagues/${L}/events/${id}/competitions/${id}/odds?limit=50`);
    const it = (j && j.items || []).filter(i => !/live/i.test(i.provider && i.provider.name || '') && i.provider && i.provider.id != '1001');
    if (!it.length) return null;
    const get = i => ({os: num(i.homeTeamOdds && i.homeTeamOdds.open && i.homeTeamOdds.open.pointSpread), cs: num(i.homeTeamOdds && i.homeTeamOdds.close && i.homeTeamOdds.close.pointSpread) ?? (i.spread != null ? +i.spread : null),
      ot: num(i.open && i.open.total), ct: num(i.close && i.close.total) ?? (i.overUnder != null ? +i.overUnder : null)});
    const dk = it.find(i => i.provider.id == '40'); const s2 = ['58', '45', '47', '50', '41', '36'].map(p => it.find(i => i.provider.id == p)).find(Boolean);
    const all = it.map(get), D = dk ? get(dk) : {}, S = s2 ? get(s2) : {};
    return [D.os ?? null, D.cs ?? null, D.ot ?? null, D.ct ?? null, S.os ?? null, S.cs ?? null, S.ot ?? null, S.ct ?? null, med(all.map(x => x.cs)), med(all.map(x => x.ct))];
  }
  window.B2_RUN = async function (conc = 6) {
    for (const [season, [a, b, withOdds]] of Object.entries(SEASONS)) for (const d of days(a, b)) {
      if (B2.done[d]) continue;
      const s = await J(`https://site.api.espn.com/apis/site/v2/sports/basketball/${L}/scoreboard?dates=${d}&groups=50&limit=500`); if (!s) continue;
      const evs = (s.events || []).filter(e => e.status && e.status.type && e.status.type.completed);
      await pool(evs.map(e => async () => {
        const c = e.competitions[0], h = c.competitors.find(x => x.homeAway == 'home'), w = c.competitors.find(x => x.homeAway == 'away');
        if (!h.team.conferenceId || !w.team.conferenceId) return;
        const [j, o] = await Promise.all([J(`https://site.api.espn.com/apis/site/v2/sports/basketball/${L}/summary?event=${e.id}`), withOdds ? odds(e.id) : Promise.resolve(null)]);
        B2.rows.push([season, d, h.team.abbreviation, w.team.abbreviation, c.neutralSite ? 1 : 0, c.conferenceCompetition ? 1 : 0, +h.score, +w.score,
          ...box(j, h.team.abbreviation), ...box(j, w.team.abbreviation), ...(o || Array(10).fill(null))]);
      }), conc);
      B2.done[d] = 1; B2.prog = season + ' ' + d + ' rows ' + B2.rows.length + ' err ' + B2.err;
    }
    B2.prog += ' DONE'; return B2.prog;
  };
})();
