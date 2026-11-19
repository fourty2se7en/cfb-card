// NCAAW Top 25 backtest dataset (Nov 9, 2026). Runs in a site.api.espn.com tab.
// One pass per date builds both datasets the 3 season backtest uses, women only:
//   BT.rows  (bt_build.js row format): every Division I game with a final, ranks at game time (curatedRank), ESPN core odds
//            ONLY when a team is ranked (other games keep null odds and feed the ratings only, as the live card's full D1 ratings do).
//   B2.rows  (bt_build2.js row format + [hRank, aRank] at the end): box score possessions for every game, odds for ranked games.
// Seasons: 2022-23 box only (prior season for the efficiency ratings), 2023-24 to 2025-26 full.
window.BT = {rows: [], done: {}, err: 0, prog: ''}; window.B2 = {rows: [], done: {}, err: 0, prog: ''};
(function () {
  const L = 'womens-college-basketball';
  const SEASONS = {'2022-23': ['20221107', '20230402', false], '2023-24': ['20231106', '20240407', true], '2024-25': ['20241104', '20250406', true], '2025-26': ['20251103', '20260405', true]};
  const dec = a => a == null || isNaN(a) ? null : (a > 0 ? 1 + a / 100 : 1 + 100 / -a);
  const amer = d => d == null ? null : Math.round(d >= 2 ? (d - 1) * 100 : -100 / (d - 1));
  const med = v => { v = v.filter(x => x != null && !isNaN(x)).sort((a, b) => a - b); if (!v.length) return null; const m = v.length >> 1; return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2; };
  const num = x => x == null ? null : (typeof x === 'object' ? (x.american != null ? parseFloat(String(x.american).replace('+', '')) : x.value) : parseFloat(x));
  const days = (a, b) => { const o = []; let d = new Date(a.slice(0,4)+'-'+a.slice(4,6)+'-'+a.slice(6)+'T12:00:00Z'); const e = new Date(b.slice(0,4)+'-'+b.slice(4,6)+'-'+b.slice(6)+'T12:00:00Z'); while (d <= e) { o.push(d.toISOString().slice(0,10).replace(/-/g,'')); d = new Date(d.getTime()+864e5); } return o; };
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  async function J(u) { for (let i = 0; i < 4; i++) { try { const r = await fetch(u); if (r.ok) return await r.json(); if (r.status === 404) return null; } catch (e) {} await sleep(800 * (i + 1)); } BT.err++; return null; }
  async function pool(ts, n) { let i = 0; await Promise.all(Array.from({length: n}, async () => { while (i < ts.length) { const t = ts[i++]; await t(); await sleep(30); } })); }
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
      ot: num(i.open && i.open.total), ct: num(i.close && i.close.total) ?? (i.overUnder != null ? +i.overUnder : null),
      mh: num(i.homeTeamOdds && i.homeTeamOdds.close && i.homeTeamOdds.close.moneyLine) ?? num(i.homeTeamOdds && i.homeTeamOdds.moneyLine), ma: num(i.awayTeamOdds && i.awayTeamOdds.close && i.awayTeamOdds.close.moneyLine) ?? num(i.awayTeamOdds && i.awayTeamOdds.moneyLine)});
    const dk = it.find(i => i.provider.id == '40'); const s2 = ['58', '45', '47', '50', '41', '36'].map(p => it.find(i => i.provider.id == p)).find(Boolean);
    const all = it.map(get), D = dk ? get(dk) : {}, S = s2 ? get(s2) : {};
    const mlok = x => x != null && Math.abs(x) >= 100 && Math.abs(x) <= 5000;
    return [D.os ?? null, D.cs ?? null, D.ot ?? null, D.ct ?? null, S.os ?? null, S.cs ?? null, S.ot ?? null, S.ct ?? null,
      med(all.map(x => x.cs)), med(all.map(x => x.ct)), amer(med(all.map(x => mlok(x.mh) ? dec(x.mh) : null))), amer(med(all.map(x => mlok(x.ma) ? dec(x.ma) : null))), it.length];
  }
  window.T25_RUN = async function (conc = 6) {
    for (const [season, [a, b, withOdds]] of Object.entries(SEASONS)) for (const d of days(a, b)) {
      if (BT.done[d]) continue;
      const s = await J(`https://site.api.espn.com/apis/site/v2/sports/basketball/${L}/scoreboard?dates=${d}&groups=50&limit=500`); if (!s) continue;
      const evs = (s.events || []).filter(e => e.status && e.status.type && e.status.type.completed);
      await pool(evs.map(e => async () => {
        const c = e.competitions[0], h = c.competitors.find(x => x.homeAway == 'home'), w = c.competitors.find(x => x.homeAway == 'away');
        const rk = x => x.curatedRank && x.curatedRank.current < 99 ? x.curatedRank.current : null;
        const hr = rk(h), ar = rk(w), ranked = hr != null || ar != null;
        const [j, o] = await Promise.all([J(`https://site.api.espn.com/apis/site/v2/sports/basketball/${L}/summary?event=${e.id}`), withOdds && ranked ? odds(e.id) : Promise.resolve(null)]);
        if (h.team.conferenceId && w.team.conferenceId)
          B2.rows.push([season, d, h.team.abbreviation, w.team.abbreviation, c.neutralSite ? 1 : 0, c.conferenceCompetition ? 1 : 0, +h.score, +w.score,
            ...box(j, h.team.abbreviation), ...box(j, w.team.abbreviation), ...(o ? o.slice(0, 10) : Array(10).fill(null)), hr, ar]);
        if (season === '2022-23') return;
        const ls = x => x.linescores && x.linescores[0] ? +x.linescores[0].value + (x.linescores[1] ? +x.linescores[1].value : 0) : null;
        BT.rows.push(['W', season, d, h.team.abbreviation, w.team.abbreviation, h.team.conferenceId || null, w.team.conferenceId || null, c.conferenceCompetition ? 1 : 0, c.neutralSite ? 1 : 0,
          (c.notes && c.notes[0] && c.notes[0].headline) || '', hr, ar, +h.score, +w.score, ls(h), ls(w), null, (c.venue && c.venue.address && c.venue.address.state) || '', ...(o || Array(13).fill(null))]);
      }), conc);
      BT.done[d] = 1; BT.prog = season + ' ' + d + ' bt ' + BT.rows.length + ' b2 ' + B2.rows.length + ' err ' + BT.err;
    }
    BT.prog += ' DONE'; return BT.prog;
  };
})();
