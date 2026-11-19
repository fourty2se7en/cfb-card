// Browser pull used Nov 4 to Nov 7, 2026 for the NCAA cards (run in Chrome on any site.api.espn.com tab; the sandbox shell cannot reach ESPN).
// Fills window.R.Y (yesterday: finals, box stats, ESPN core odds DraftKings open and close) and window.R.T (today: slate plus DraftKings open and now).
// Then window.SY / window.ST hold compact pipe rows; read them in 950-char slices and save as data/raw/y_<YD>.txt and data/raw/t_<TD>.txt.
//   y row: lg|id|home|away|hConf|aConf|confGame|neutral|hRank|aRank|hs|as|h1|a1|venueState|hFGA,hORB,hTO,hFTA,aFGA,aORB,aTO,aFTA|spOpenHome,spCloseHome,totOpen,totClose,mlHome,mlAway
//   t row: espn_board.txt fields 0..25 (lg|id|time|away|home|aConf|hConf|cg|nu|aRank|hRank|state|as|hs|o|c|to|tc|mlh|mla|n|book|sph|spa|op|up) plus |awayTeamId,homeTeamId
//   ST compresses 12 empty odds fields to '~'; expand with l.replace('~', '|'*12). Women's 1H = Q1 + Q2.
// After a game ends ESPN core odds keep one provider; its `current` is the pre-tip close. Opens come from that day's saved board (data/raw/espn_board_<date>.txt) when present.
// Keep concurrency at 6 or less: ESPN core odds blocks bursts.
const YD = '20261106', TD = '20261107';   // set per run
window.R = {Y: [], T: [], err: 0, prog: ''};
const LG = {M: 'mens-college-basketball', W: 'womens-college-basketball'};
async function J(u, t = 3) { for (let i = 0; i < t; i++) { try { const r = await fetch(u); if (r.ok) return await r.json(); } catch (e) {} await new Promise(r => setTimeout(r, 500 * (i + 1))); } R.err++; return null; }
const num = x => x == null ? null : (typeof x === 'object' ? (x.american != null ? parseFloat(String(x.american).replace('+', '')) : x.value) : parseFloat(x));
async function pool(ts, n) { let i = 0; await Promise.all(Array.from({length: n}, async () => { while (i < ts.length) { const t = ts[i++]; await t(); } })); }
async function odds(lg, id) {
  const j = await J(`https://sports.core.api.espn.com/v2/sports/basketball/leagues/${LG[lg]}/events/${id}/competitions/${id}/odds?limit=50`);
  const it = (j && j.items || []).filter(i => i.provider && !/live/i.test(i.provider.name || '') && i.provider.id != '1001');
  const dk = it.find(i => /draftkings/i.test(i.provider.name || '')) || it[0]; if (!dk) return null;
  const H = dk.homeTeamOdds || {}, A = dk.awayTeamOdds || {};
  return {book: dk.provider.name, n: it.length,
    o: num(H.open && H.open.pointSpread), c: num(H.current && H.current.pointSpread) ?? num(H.close && H.close.pointSpread) ?? (dk.spread != null ? +dk.spread : null),
    to: num(dk.open && dk.open.total), tc: num(dk.current && dk.current.total) ?? num(dk.close && dk.close.total) ?? (dk.overUnder != null ? +dk.overUnder : null),
    mlh: num(H.current && H.current.moneyLine) ?? num(H.moneyLine), mla: num(A.current && A.current.moneyLine) ?? num(A.moneyLine),
    sph: num(H.current && H.current.spread) ?? num(H.spreadOdds), spa: num(A.current && A.current.spread) ?? num(A.spreadOdds),
    op: num(dk.current && dk.current.over) ?? num(dk.overOdds), up: num(dk.current && dk.current.under) ?? num(dk.underOdds)};
}
function st(t, name) { const s = (t.statistics || []).find(x => x.name == name); return s ? s.displayValue : null; }
async function box(lg, id) {
  const j = await J(`https://site.api.espn.com/apis/site/v2/sports/basketball/${LG[lg]}/summary?event=${id}`); if (!j || !j.boxscore) return null;
  const out = {}; for (const t of j.boxscore.teams || []) { const fg = st(t, 'fieldGoalsMade-fieldGoalsAttempted'), ft = st(t, 'freeThrowsMade-freeThrowsAttempted');
    out[t.homeAway] = [fg ? +fg.split('-')[1] : null, +(st(t, 'offensiveRebounds') || 0), +(st(t, 'totalTurnovers') || st(t, 'turnovers') || 0), ft ? +ft.split('-')[1] : null]; }
  return out;
}
(async () => {
  for (const lg of ['M', 'W']) {
    const s = await J(`https://site.api.espn.com/apis/site/v2/sports/basketball/${LG[lg]}/scoreboard?dates=${YD}&groups=50&limit=500`);
    const evs = (s && s.events || []);
    await pool(evs.map(e => async () => { const c = e.competitions[0], h = c.competitors.find(x => x.homeAway == 'home'), w = c.competitors.find(x => x.homeAway == 'away');
      const done = e.status.type.completed; const rk = x => x.curatedRank && x.curatedRank.current < 99 ? x.curatedRank.current : null;
      const ls = x => x.linescores && x.linescores[0] ? +x.linescores[0].value + (lg == 'W' && x.linescores[1] ? +x.linescores[1].value : 0) : null;
      const r = {lg, id: e.id, done, st: e.status.type.name, h: h.team.abbreviation, a: w.team.abbreviation, hc: h.team.conferenceId || null, ac: w.team.conferenceId || null,
        cg: c.conferenceCompetition ? 1 : 0, nu: c.neutralSite ? 1 : 0, hr: rk(h), ar: rk(w), hs: +h.score, as: +w.score, h1: ls(h), a1: ls(w), vs: (c.venue && c.venue.address && c.venue.address.state) || ''};
      if (done && r.hc && r.ac) { r.b = await box(lg, e.id); r.od = await odds(lg, e.id); } R.Y.push(r); }), 6);
    R.prog += lg + ' Y ' + evs.length + '; ';
  }
  for (const lg of ['M', 'W']) {
    const s = await J(`https://site.api.espn.com/apis/site/v2/sports/basketball/${LG[lg]}/scoreboard?dates=${TD}&groups=50&limit=500`);
    const evs = (s && s.events || []);
    await pool(evs.map(e => async () => { const c = e.competitions[0], h = c.competitors.find(x => x.homeAway == 'home'), w = c.competitors.find(x => x.homeAway == 'away');
      const rk = x => x.curatedRank && x.curatedRank.current < 99 ? x.curatedRank.current : '';
      const tm = new Date(e.date).toLocaleTimeString('en-US', {timeZone: 'America/Phoenix', hour: 'numeric', minute: '2-digit'});
      const sn = e.status.type.state == 'pre' ? 'p' : (e.status.type.state == 'in' ? 'i' : 'f');
      R.T.push({lg, id: e.id, tm, a: w.team.abbreviation, h: h.team.abbreviation, ac: w.team.conferenceId || '', hc: h.team.conferenceId || '', cg: c.conferenceCompetition ? 1 : 0, nu: c.neutralSite ? 1 : 0,
        ar: rk(w), hr: rk(h), sn, as: +w.score || 0, hs: +h.score || 0, tid: [w.team.id, h.team.id], od: await odds(lg, e.id)}); }), 6);
    R.prog += lg + ' T ' + evs.length + '; ';
  }
  const z = v => v == null || Number.isNaN(v) ? '' : v;
  const o6 = o => o ? [o.o, o.c, o.to, o.tc, o.mlh, o.mla].map(z).join(',') : '';
  window.SY = R.Y.filter(r => r.done && r.hc && r.ac).map(r => [r.lg, r.id, r.h, r.a, z(r.hc), z(r.ac), r.cg, r.nu, z(r.hr), z(r.ar), r.hs, r.as, z(r.h1), z(r.a1), r.vs,
    r.b && r.b.home && r.b.away ? [...r.b.home, ...r.b.away].map(z).join(',') : '', o6(r.od)].join('|')).join('\n');
  window.ST = R.T.filter(r => r.ac && r.hc).map(r => { const o = r.od || {}; return [r.lg, r.id, r.tm.replace(':00', '').replace(' ', ''), r.a, r.h, r.ac, r.hc, r.cg, r.nu, r.ar, r.hr, r.sn, r.as, r.hs,
    z(o.o), z(o.c), z(o.to), z(o.tc), z(o.mlh), z(o.mla), z(o.n), (o.book || '').replace(/ .*/, ''), z(o.sph), z(o.spa), z(o.op), z(o.up), r.tid.join(',')].join('|').replace(/\|{12}/, '~'); }).join('\n');
  R.prog += 'DONE';   // games still in progress are left out of SY: rerun for them later (see HANDOFF)
})();
