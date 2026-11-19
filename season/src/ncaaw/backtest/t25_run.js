// NCAA backtest engine. Runs in the browser on BT.rows (from bt_build.js). Writes window.OUT (compact result lines) and window.RAT (final ratings).
// Result line: lg|test|variant|season|month|w|l|p|units   (month 'ALL' = whole season; season 'ALL3' = three seasons)
(function () {
  const I = {lg:0,se:1,d:2,h:3,a:4,hc:5,ac:6,cg:7,nu:8,note:9,hr:10,ar:11,hs:12,as:13,h1:14,a1:15,vs:17,dko:18,dkc:19,dkto:20,dktc:21,s2o:22,s2c:23,s2to:24,s2tc:25,sp:26,tot:27,mlh:28,mla:29};
  const SEAS = ['2023-24','2024-25','2025-26'];
  const HCA = {M: 3.0, W: 3.0};
  const dnum = d => Date.UTC(+d.slice(0,4), +d.slice(4,6)-1, +d.slice(6));
  const mon = d => ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+d.slice(4,6)-1];
  const win = p => p > 0 ? p/100 : 100/(-p);
  const R = {};   // key -> {w,l,p,u}
  function rec(lg, test, v, se, d, res, price) {
    if (!window.CUR_RK) return;
    for (const s of [se, 'ALL3']) for (const m of ['ALL', mon(d)]) {
      const k = [lg,test,v,s,m].join('|'); const o = R[k] || (R[k] = {w:0,l:0,p:0,u:0});
      if (res > 0) { o.w++; o.u += win(price); } else if (res < 0) { o.l++; o.u -= 1; } else o.p++;
    }
  }
  const ats = (margin, spread) => Math.sign(margin + spread);   // margin of the side, its spread
  const median = v => { v = v.slice().sort((a,b)=>a-b); const m = v.length >> 1; return v.length ? (v.length % 2 ? v[m] : (v[m-1]+v[m])/2) : 0; };
  window.RAT = {};
  window.BT_ANALYZE_T25 = function (LGS = ['M', 'W']) {
    for (const k in R) delete R[k];
    const rows = BT.rows.slice().sort((x, y) => x[I.d].localeCompare(y[I.d]));
    for (const lg of LGS) {
      let prevFinal = {};
      for (const se of SEAS) {
        const G = rows.filter(r => r[I.lg] === lg && r[I.se] === se);
        const T = {};   // team -> {g, games:[{d, m, pf, pa, st, loc}]}
        const tm = t => T[t] || (T[t] = {games: []});
        let rating = {}; let lastDay = '';
        // SRS solve on games so far
        function solve(upto) {
          const gs = []; for (const t in T) for (const x of T[t].games) gs.push([t, x.opp, x.m - (x.loc === 'H' ? HCA[lg] : x.loc === 'A' ? -HCA[lg] : 0)]);
          const r = {}; for (const t in T) r[t] = 0;
          for (let it = 0; it < 12; it++) { const s = {}, n = {}; for (const [t, o, m] of gs) { s[t] = (s[t] || 0) + m + (r[o] || 0); n[t] = (n[t] || 0) + 1; }
            for (const t in s) r[t] = s[t] / n[t]; const mu = Object.values(r).reduce((a,b)=>a+b,0) / Math.max(1, Object.keys(r).length); for (const t in r) r[t] -= mu; }
          return r;
        }
        const totals = [];
        for (const g of G) {
          const d = g[I.d]; if (d !== lastDay) { rating = solve(d); lastDay = d; }
          { const rh_ = g[I.hr] != null, ra_ = g[I.ar] != null; window.CUR_RK = (window.T25MODE === 'both' ? (rh_ && ra_) : window.T25MODE === 'none' ? true : (rh_ || ra_)) && g[I.sp] != null && g[I.tot] != null; }
          const h = g[I.h], a = g[I.a], nu = g[I.nu] === 1; tm(h); tm(a);
          const blend = t => { const n = tm(t).games.length, w = n/(n+8); return w*(rating[t] || 0) + (1-w)*(prevFinal[t] || 0); };
          const proj = blend(h) - blend(a) + (nu ? 0 : HCA[lg]);   // home margin
          const sp = g[I.sp], tot = g[I.tot], margin = g[I.hs] - g[I.as], total = g[I.hs] + g[I.as];
          const mv = (o, c) => (o != null && c != null) ? c - o : null;   // home spread change (negative = toward home)
          const m1 = mv(g[I.dko], g[I.dkc]), m2 = mv(g[I.s2o], g[I.s2c]);
          const both = (thr, sign) => (m1 != null && m2 != null) ? (sign*m1 >= thr && sign*m2 >= thr) : (m1 != null ? sign*m1 >= thr : (m2 != null && sign*m2 >= thr));   // two books when both exist, else the one available
          const homeMove = both(0.5, -1), awayMove = both(0.5, 1), homeMove1 = both(1, -1), awayMove1 = both(1, 1);
          const t1 = mv(g[I.dkto], g[I.dktc]), t2 = mv(g[I.s2to], g[I.s2tc]);
          const tA = [t1, t2].filter(x => x != null); const totDrop = tA.length > 0 && tA.every(x => x < 0), totDrop2 = totDrop && tA.every(x => x <= -2);
          const totUp = tA.length > 0 && tA.every(x => x > 0), totUp2 = totUp && tA.every(x => x >= 2);
          const last = t => tm(t).games[tm(t).games.length - 1];
          const rest = t => last(t) ? Math.round((dnum(d) - dnum(last(t).d)) / 864e5) : 99;
          const form = t => { const x = tm(t).games.slice(-5); return x.length ? x.filter(y => y.m > 0).length / x.length : 0.5; };
          const avgm = t => { const x = tm(t).games; return x.length ? x.reduce((s, y) => s + y.m, 0) / x.length : 0; };
          // signal score
          let sh = 0, sa = 0;
          if (homeMove) sh += 2; if (awayMove) sa += 2;
          if (proj + sp >= 1.5) sh++; if (proj + sp <= -1.5) sa++;
          const rh = rest(h), ra = rest(a); if (rh < 99 && ra < 99) { if (rh - ra >= 2) sh++; if (ra - rh >= 2) sa++; }
          if (!nu) sh++;
          if (form(h) - form(a) >= 0.4) sh++; if (form(a) - form(h) >= 0.4) sa++;
          if (avgm(h) - avgm(a) >= 3) sh++; if (avgm(a) - avgm(h) >= 3) sa++;
          if (last(h) && last(h).m <= -10) sh++; if (last(a) && last(a).m <= -10) sa++;
          const lead = sh - sa;   // + = home
          const mlh = g[I.mlh], mla = g[I.mla];
          // ---- rule families ----
          if (mlh != null && mla != null) {
            const fav = mlh < mla ? 'h' : 'a', fp = fav === 'h' ? mlh : mla, dp = fav === 'h' ? mla : mlh;
            const favLead = fav === 'h' ? lead : -lead, favWon = fav === 'h' ? margin > 0 : margin < 0;
            if (fp >= -200 && fp <= -100) {
              if (favLead >= 2) rec(lg, 'FAV_ML', 'lowered', se, d, favWon ? 1 : -1, fp);
              if (favLead >= 3) rec(lg, 'FAV_ML', 'strict', se, d, favWon ? 1 : -1, fp);
              rec(lg, 'BASE_FAV_ML', 'all', se, d, favWon ? 1 : -1, fp);
            }
            if (dp >= 100 && dp <= 200) {
              const dogLead = -favLead, dogMoved = fav === 'h' ? awayMove : homeMove;
              if (dogLead >= 1) rec(lg, 'DOG_ML', 'lowered', se, d, favWon ? -1 : 1, dp);
              if (dogLead >= 1 && dogMoved) rec(lg, 'DOG_ML', 'strict', se, d, favWon ? -1 : 1, dp);
              rec(lg, 'BASE_DOG_ML', 'all', se, d, favWon ? -1 : 1, dp);
            }
          }
          if (homeMove) rec(lg, 'SPREAD_MOVE', 'lowered', se, d, ats(margin, sp), -110);
          if (awayMove) rec(lg, 'SPREAD_MOVE', 'lowered', se, d, ats(-margin, -sp), -110);
          if (homeMove1) rec(lg, 'SPREAD_MOVE', 'strict', se, d, ats(margin, sp), -110);
          if (awayMove1) rec(lg, 'SPREAD_MOVE', 'strict', se, d, ats(-margin, -sp), -110);
          const und = Math.sign(tot - total), ovr = -und;
          if (totDrop) rec(lg, 'UNDER_DROP', 'lowered', se, d, und, -110);
          if (totDrop2) rec(lg, 'UNDER_DROP', 'strict', se, d, und, -110);
          if (totUp) rec(lg, 'OVER', 'lowered', se, d, ovr, -110);
          if (totUp2) rec(lg, 'OVER', 'strict', se, d, ovr, -110);
          rec(lg, 'BASE_UNDER', 'all', se, d, und, -110);
          // projection vs spread (model edge)
          if (Math.abs(proj + sp) >= 3) rec(lg, 'MODEL_EDGE_3', 'all', se, d, proj + sp > 0 ? ats(margin, sp) : ats(-margin, -sp), -110);
          // ---- college tests ----
          const nm = +d.slice(4,6), early = nm >= 11;
          if (!nu && g[I.cg]) rec(lg, 'HOMECONF_' + g[I.hc], 'all', se, d, ats(margin, sp), -110);
          if (!nu) rec(lg, g[I.cg] ? 'HOME_ATS_conf' : 'HOME_ATS_nonconf', 'all', se, d, ats(margin, sp), -110);
          rec(lg, g[I.cg] ? 'UNDER_conf' : 'UNDER_nonconf', 'all', se, d, und, -110);
          if (!g[I.cg] && early && Math.abs(sp) >= 15) {
            const favH = sp < 0; rec(lg, 'MIS15_fav', 'all', se, d, favH ? ats(margin, sp) : ats(-margin, -sp), -110);
            rec(lg, 'MIS15_dog', 'all', se, d, favH ? ats(-margin, -sp) : ats(margin, sp), -110);
            rec(lg, 'MIS15_under', 'all', se, d, und, -110);
            if (Math.abs(sp) >= 25) rec(lg, 'MIS25_dog', 'all', se, d, favH ? ats(-margin, -sp) : ats(margin, sp), -110);
          }
          if (nu) { const favH = sp < 0; rec(lg, 'NEU_fav', 'all', se, d, favH ? ats(margin, sp) : ats(-margin, -sp), -110); rec(lg, 'NEU_under', 'all', se, d, und, -110);
            if (early && !g[I.cg]) { rec(lg, 'HOLI_dog', 'all', se, d, favH ? ats(-margin, -sp) : ats(margin, sp), -110); rec(lg, 'HOLI_under', 'all', se, d, und, -110); } }
          if (rh < 99 && ra < 99) {
            if (rh - ra >= 2) rec(lg, 'REST2_ATS', 'all', se, d, ats(margin, sp), -110);
            if (ra - rh >= 2) rec(lg, 'REST2_ATS', 'all', se, d, ats(-margin, -sp), -110);
            if (ra <= 1 && rh >= 2) rec(lg, 'ROAD1DAY_fade', 'all', se, d, ats(margin, sp), -110);
            const la = last(a), trav = la && la.st && g[I.vs] && la.st !== g[I.vs] && la.loc !== 'H';
            if (trav && !nu && ra <= 2) rec(lg, 'ROADTRAV_fade', 'all', se, d, ats(margin, sp), -110);
          }
          const hr = g[I.hr], ar = g[I.ar];
          if ((hr != null) !== (ar != null)) {
            const rankedH = hr != null; rec(lg, 'UNRK_vs_RK', 'all', se, d, rankedH ? ats(-margin, -sp) : ats(margin, sp), -110);
            if (rankedH === false && !nu) rec(lg, 'UNRK_HOME_vs_RK', 'all', se, d, ats(margin, sp), -110);
          }
          if (hr != null && ar != null) rec(lg, 'RKvRK_under', 'all', se, d, und, -110);
          // pace tier proxy: season-to-date average combined points of both teams' games
          const ap = t => { const x = tm(t).games; return x.length >= 3 ? x.reduce((s, y) => s + y.pf + y.pa, 0) / x.length : null; };
          const ph = ap(h), pa_ = ap(a);
          if (ph != null && pa_ != null) { const pp = (ph + pa_) / 2; totals.push(pp); const med = median(totals.slice(-800));
            const tier = pp < med - 4 ? 'slow' : pp > med + 4 ? 'fast' : 'mid';
            rec(lg, 'PACE_' + tier + '_under', 'all', se, d, und, -110); rec(lg, 'PACE_' + tier + '_over', 'all', se, d, ovr, -110); }
          // first half: share of points (no historical 1H lines)
          // update team logs AFTER the game
          tm(h).games.push({d, m: margin, pf: g[I.hs], pa: g[I.as], opp: a, st: g[I.vs], loc: nu ? 'N' : 'H'});
          tm(a).games.push({d, m: -margin, pf: g[I.as], pa: g[I.hs], opp: h, st: g[I.vs], loc: nu ? 'N' : 'A'});
        }
        rating = solve('end'); const fin = {}; for (const t in T) fin[t] = +(rating[t] || 0).toFixed(2);
        RAT[lg + se] = {rating: fin, pace: Object.fromEntries(Object.entries(T).map(([t, x]) => [t, x.games.reduce((s, y) => s + y.pf + y.pa, 0) / x.games.length])), g: Object.fromEntries(Object.entries(T).map(([t, x]) => [t, x.games.length]))};
        prevFinal = fin;
      }
    }
    window.OUT = Object.entries(R).map(([k, o]) => k + '|' + o.w + '|' + o.l + '|' + o.p + '|' + o.u.toFixed(1));
    return OUT.length + ' lines';
  };
})();
