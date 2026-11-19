// NCAA backtest dataset builder. Runs in a site.api.espn.com tab (javascript_tool).
// Builds every Division I game (groups=50) with ESPN core odds for 2023-24, 2024-25, 2025-26, men and women.
// Row: [lg, season, date, home, away, hConf, aConf, confGame, neutral, note, hRank, aRank, hs, as, h1h, a1h, hState, venueState,
//       dkOpenSp, dkCloseSp, dkOpenTot, dkCloseTot, s2OpenSp, s2CloseSp, s2OpenTot, s2CloseTot, medSp, medTot, medMLh, medMLa, nBooks]
// Spreads are the HOME spread. Moneylines American. Missing = null.
window.BT = window.BT || {rows: [], done: {}, err: 0, prog: ''};
(function () {
  const LG = {M: 'mens-college-basketball', W: 'womens-college-basketball'};
  const SEASONS = {'2023-24': ['20231106', '20240408'], '2024-25': ['20241104', '20250407'], '2025-26': ['20251103', '20260406']};
  const dec = a => a == null || isNaN(a) ? null : (a > 0 ? 1 + a / 100 : 1 + 100 / -a);
  const amer = d => d == null ? null : Math.round(d >= 2 ? (d - 1) * 100 : -100 / (d - 1));
  const med = v => { v = v.filter(x => x != null && !isNaN(x)).sort((a, b) => a - b); if (!v.length) return null; const m = v.length >> 1; return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2; };
  const num = x => x == null ? null : (typeof x === 'object' ? (x.american != null ? parseFloat(String(x.american).replace('+', '')) : x.value) : parseFloat(x));
  function days(a, b) { const out = []; let d = new Date(a.slice(0, 4) + '-' + a.slice(4, 6) + '-' + a.slice(6) + 'T12:00:00Z'); const e = new Date(b.slice(0, 4) + '-' + b.slice(4, 6) + '-' + b.slice(6) + 'T12:00:00Z'); while (d <= e) { out.push(d.toISOString().slice(0, 10).replace(/-/g, '')); d = new Date(d.getTime() + 864e5); } return out; }
  async function J(u, tries = 3) { for (let i = 0; i < tries; i++) { try { const r = await fetch(u); if (r.ok) return await r.json(); } catch (e) {} await new Promise(r => setTimeout(r, 400 * (i + 1))); } BT.err++; return null; }
  async function odds(lg, id) {
    const j = await J(`https://sports.core.api.espn.com/v2/sports/basketball/leagues/${LG[lg]}/events/${id}/competitions/${id}/odds?limit=50`);
    const it = (j && j.items || []).filter(i => !/live/i.test(i.provider && i.provider.name || '') && i.provider && i.provider.id != '1001');
    if (!it.length) return null;
    const get = i => ({os: num(i.homeTeamOdds && i.homeTeamOdds.open && i.homeTeamOdds.open.pointSpread), cs: num(i.homeTeamOdds && i.homeTeamOdds.close && i.homeTeamOdds.close.pointSpread) ?? (i.spread != null ? +i.spread : null),
      ot: num(i.open && i.open.total), ct: num(i.close && i.close.total) ?? (i.overUnder != null ? +i.overUnder : null),
      mh: num(i.homeTeamOdds && i.homeTeamOdds.close && i.homeTeamOdds.close.moneyLine) ?? num(i.homeTeamOdds && i.homeTeamOdds.moneyLine), ma: num(i.awayTeamOdds && i.awayTeamOdds.close && i.awayTeamOdds.close.moneyLine) ?? num(i.awayTeamOdds && i.awayTeamOdds.moneyLine)});
    const dk = it.find(i => i.provider.id == '40'); const s2 = ['58', '45', '47', '50', '41', '36'].map(p => it.find(i => i.provider.id == p)).find(Boolean);
    const all = it.map(get), D = dk ? get(dk) : {}, S = s2 ? get(s2) : {};
    const mlok = x => x != null && Math.abs(x) >= 100 && Math.abs(x) <= 5000;
    return [D.os ?? null, D.cs ?? null, D.ot ?? null, D.ct ?? null, S.os ?? null, S.cs ?? null, S.ot ?? null, S.ct ?? null,
      med(all.map(x => x.cs)), med(all.map(x => x.ct)), amer(med(all.map(x => mlok(x.mh) ? dec(x.mh) : null))), amer(med(all.map(x => mlok(x.ma) ? dec(x.ma) : null))), it.length];
  }
  async function pool(tasks, n) { let i = 0; await Promise.all(Array.from({length: n}, async () => { while (i < tasks.length) { const t = tasks[i++]; await t(); } })); }
  window.BT_RUN = async function (lgs = ['M', 'W'], conc = 12) {
    for (const lg of lgs) for (const [season, [a, b]] of Object.entries(SEASONS)) for (const d of days(a, b)) {
      const key = lg + d; if (BT.done[key]) continue;
      const s = await J(`https://site.api.espn.com/apis/site/v2/sports/basketball/${LG[lg]}/scoreboard?dates=${d}&groups=50&limit=500`);
      if (!s) continue;
      const evs = (s.events || []).filter(e => e.status && e.status.type && e.status.type.completed);
      const tasks = evs.map(e => async () => {
        const c = e.competitions[0], h = c.competitors.find(x => x.homeAway == 'home'), w = c.competitors.find(x => x.homeAway == 'away');
        const o = await odds(lg, e.id); if (!o) return;
        const ls = x => x.linescores && x.linescores[0] ? +x.linescores[0].value + (lg == 'W' && x.linescores[1] ? +x.linescores[1].value : 0) : null;
        const rk = x => x.curatedRank && x.curatedRank.current < 99 ? x.curatedRank.current : null;
        BT.rows.push([lg, season, d, h.team.abbreviation, w.team.abbreviation, h.team.conferenceId || null, w.team.conferenceId || null, c.conferenceCompetition ? 1 : 0, c.neutralSite ? 1 : 0,
          (c.notes && c.notes[0] && c.notes[0].headline) || '', rk(h), rk(w), +h.score, +w.score, ls(h), ls(w), null, (c.venue && c.venue.address && c.venue.address.state) || '', ...o]);
      });
      await pool(tasks, conc); BT.done[key] = 1; BT.prog = lg + ' ' + season + ' ' + d + ' rows ' + BT.rows.length + ' err ' + BT.err;
    }
    BT.prog += ' DONE'; return BT.prog;
  };
})();
