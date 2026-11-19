// NCAAM backtest v2 tests (Nov 2, 2026). Runs on B2.rows from bt_build2.js.
// Option 2: possession-based adjusted efficiency model (AdjO, AdjD, tempo; opponent and home adjusted; recomputed each day from prior games,
//           last season's final ratings regressed 25% to the mean and blended by games / (games + 8)), graded at the closing consensus.
// Option 3: November and December only, graded at the OPENING line (DraftKings open, else the second book's open), for both the efficiency
//           model and the margin (SRS) model used in the first backtest; plus the efficiency model at the close in the same window.
// Output lines: test|season|month|w|l|p|u   (season C = three seasons; month ALL = whole window).
(function () {
  const I = {se:0,d:1,h:2,a:3,nu:4,cg:5,hs:6,as:7,hfga:8,horb:9,hto:10,hfta:11,afga:12,aorb:13,ato:14,afta:15,dko:16,dkc:17,dkto:18,dktc:19,s2o:20,s2c:21,s2to:22,s2tc:23,sp:24,tot:25};
  const mon = d => ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+d.slice(4,6)-1];
  const R = {};
  function rec(test, se, d, res) { for (const s of [se, 'C']) for (const m of ['ALL', mon(d)]) { const k = [test, s, m].join('|'); const o = R[k] || (R[k] = {w:0,l:0,p:0,u:0}); if (res > 0) { o.w++; o.u += 100/110; } else if (res < 0) { o.l++; o.u -= 1; } else o.p++; } }
  const sgn = x => (x > 0) - (x < 0);
  const HC = 0.014;   // home share of efficiency (about 3 points a game)
  window.B2_ANALYZE = function () {
    for (const k in R) delete R[k];
    const seen = new Set();
    const rows = B2.rows.filter(r => { const k = r[1] + r[2] + r[3]; if (seen.has(k)) return false; seen.add(k); return r[I.hfga] && r[I.afga]; }).sort((x, y) => x[I.d].localeCompare(y[I.d]));
    let prior = {}, priorSRS = {};
    for (const se of ['2022-23', '2023-24', '2024-25', '2025-26']) {
      const G = rows.filter(r => r[I.se] === se); const T = {}; const tm = t => T[t] || (T[t] = []);
      let E = {}, S = {}, lastDay = '', Lg = {o: 102, t: 68};
      function solve() {
        const all = []; for (const t in T) for (const g of T[t]) all.push([t, g]);
        if (!all.length) return;
        let so = 0, sp = 0; for (const [, g] of all) { so += g.pf; sp += g.poss; } Lg = {o: 100 * so / sp, t: sp / all.length};
        const e = {}; for (const t in T) e[t] = {o: Lg.o, d: Lg.o, t: Lg.t};
        for (let it = 0; it < 8; it++) {
          const n = {}; for (const t in T) n[t] = {o: 0, d: 0, t: 0, c: 0};
          for (const [t, g] of all) {
            const op = e[g.opp] || {o: Lg.o, d: Lg.o, t: Lg.t}; const hf = g.loc === 'H' ? 1 + HC : g.loc === 'A' ? 1 - HC : 1;
            const off = 100 * g.pf / g.poss / hf, def = 100 * g.pa / g.poss * hf;
            n[t].o += off * Lg.o / op.d; n[t].d += def * Lg.o / op.o; n[t].t += g.poss * Lg.t / op.t; n[t].c++;
          }
          for (const t in n) if (n[t].c) e[t] = {o: n[t].o / n[t].c, d: n[t].d / n[t].c, t: n[t].t / n[t].c};
        }
        E = e;
        const gs = []; for (const [t, g] of all) gs.push([t, g.opp, g.pf - g.pa - (g.loc === 'H' ? 3 : g.loc === 'A' ? -3 : 0)]);
        let r = {}; for (let it = 0; it < 12; it++) { const s = {}, c = {}; for (const [t, o, m] of gs) { s[t] = (s[t] || 0) + m + (r[o] || 0); c[t] = (c[t] || 0) + 1; } r = {}; for (const t in s) r[t] = s[t] / c[t]; const mu = Object.values(r).reduce((a, b) => a + b, 0) / Object.keys(r).length; for (const t in r) r[t] -= mu; }
        S = r;
      }
      const rate = t => { const n = tm(t).length, w = n / (n + 8); const p = prior[t] ? {o: 0.75 * prior[t].o + 0.25 * Lg.o, d: 0.75 * prior[t].d + 0.25 * Lg.o, t: 0.75 * prior[t].t + 0.25 * Lg.t} : {o: Lg.o - 4, d: Lg.o + 4, t: Lg.t};
        const c = E[t] || p; return {o: w * c.o + (1 - w) * p.o, d: w * c.d + (1 - w) * p.d, t: w * c.t + (1 - w) * p.t}; };
      const srs = t => { const n = tm(t).length, w = n / (n + 8); return w * (S[t] || 0) + (1 - w) * (priorSRS[t] || 0); };
      for (const g of G) {
        const d = g[I.d]; if (d !== lastDay) { solve(); lastDay = d; }
        const h = g[I.h], a = g[I.a], nu = g[I.nu] === 1;
        const possH = g[I.hfga] - g[I.horb] + g[I.hto] + 0.475 * g[I.hfta], possA = g[I.afga] - g[I.aorb] + g[I.ato] + 0.475 * g[I.afta], poss = (possH + possA) / 2;
        if (se !== '2022-23' && g[I.sp] != null) {
          const H = rate(h), A = rate(a), pace = H.t * A.t / Lg.t, hf = nu ? 1 : 1 + HC, af = nu ? 1 : 1 - HC;
          const pH = pace * (H.o * A.d / Lg.o) / 100 * hf, pA = pace * (A.o * H.d / Lg.o) / 100 * af;
          const pm = pH - pA, pt = pH + pA, m = g[I.hs] - g[I.as], tot = g[I.hs] + g[I.as];
          const ats = (spread, side) => side > 0 ? sgn(m + spread) : sgn(-m - spread);
          // option 2: efficiency model at the close
          const e = pm + g[I.sp]; for (const th of [2, 3, 4, 5, 6]) if (Math.abs(e) >= th) rec('EFF_SPREAD_' + th, se, d, ats(g[I.sp], sgn(e)));
          if (g[I.tot] != null) { const et = pt - g[I.tot]; for (const th of [3, 5, 7, 9]) if (Math.abs(et) >= th) rec((et > 0 ? 'EFF_OVER_' : 'EFF_UNDER_') + th, se, d, et > 0 ? sgn(tot - g[I.tot]) : sgn(g[I.tot] - tot)); }
          // option 3: Nov-Dec, graded at the opener
          const early = +d.slice(4, 6) >= 11;
          if (early) {
            for (const th of [2, 3, 4, 5]) if (Math.abs(e) >= th) rec('EARLY_EFF_CLOSE_' + th, se, d, ats(g[I.sp], sgn(e)));
            const os = g[I.dko] != null ? g[I.dko] : g[I.s2o], ot = g[I.dkto] != null ? g[I.dkto] : g[I.s2to];
            if (os != null) {
              const eo = pm + os; for (const th of [2, 3, 4, 5]) if (Math.abs(eo) >= th) rec('EARLY_EFF_OPEN_' + th, se, d, ats(os, sgn(eo)));
              const sm = srs(h) - srs(a) + (nu ? 0 : 3), so = sm + os; for (const th of [3, 5]) if (Math.abs(so) >= th) rec('EARLY_SRS_OPEN_' + th, se, d, ats(os, sgn(so)));
              // closing line value: did the line move toward the model's side? (+1 yes, -1 no, 0 no move)
              if (Math.abs(eo) >= 3 && g[I.sp] != null) rec('EARLY_EFF_OPEN_CLV_3', se, d, sgn(eo) * sgn(os - g[I.sp]));
            }
            if (ot != null) { const et = pt - ot; for (const th of [4, 7]) if (Math.abs(et) >= th) rec((et > 0 ? 'EARLY_EFF_OPEN_OVER_' : 'EARLY_EFF_OPEN_UNDER_') + th, se, d, et > 0 ? sgn(tot - ot) : sgn(ot - tot)); }
          }
        }
        tm(h).push({opp: a, pf: g[I.hs], pa: g[I.as], poss, loc: nu ? 'N' : 'H'}); tm(a).push({opp: h, pf: g[I.as], pa: g[I.hs], poss, loc: nu ? 'N' : 'A'});
      }
      solve(); prior = E; priorSRS = S;
    }
    window.OUT2 = Object.entries(R).map(([k, o]) => k + '|' + o.w + '|' + o.l + '|' + o.p + '|' + o.u.toFixed(1)).sort();
    return OUT2.length;
  };
  window.B2_PASS = function () {
    const m = {}; for (const l of OUT2) { const f = l.split('|'); if (f[2] !== 'ALL') continue; (m[f[0]] = m[f[0]] || {})[f[1]] = {w: +f[3], l: +f[4], u: +f[6]}; }
    return Object.entries(m).map(([k, v]) => { const pos = ['2023-24', '2024-25', '2025-26'].filter(s => v[s] && v[s].u > 0).length; const c = v.C; const n = c.w + c.l;
      const ok = c.u > 0 && pos >= 2 && (pos === 3 || n >= 200); return [k, c.w + '-' + c.l, (100 * c.w / Math.max(1, n)).toFixed(1) + '%', c.u.toFixed(1) + 'u', pos + '/3', ok ? 'PASS' : ''].join(' '); }).join('\n');
  };
})();
