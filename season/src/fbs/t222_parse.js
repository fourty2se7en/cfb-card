// texas222 board parser (desktop and phone layouts). Rebuilt Nov 7, 2026 from the cfb-card skill note.
// Usage in a texas222 tab after clicking a league in the menu: t222parse('NCAA FOOTBALL - MEN') -> compact string
//   rows "date,time,rot,TEAM,spread,total,ml;" (TEAM without spaces, as model.py parse_t222 expects).
// Desktop layout: innerText lines "time" / "rot" / "TEAM" / spread / total / ml. The date comes from the group header "... - Nov 07".
// Phone layout: each row starts with "#<rot>" and a time ("#327 12:48 PM CENTRAL FLORIDA ..."); strip both before splitting,
//   and read the date from the group header.
// Output is long: store on window.__c and print in 950-character slices (window.__c.slice(i, i + 950)).
function t222parse(heading) {
  const hs = [...document.querySelectorAll('div,span,h1,h2,h3,h4')].filter(e => e.textContent.trim().toUpperCase() === heading.toUpperCase() && !e.closest('li'));
  let c = hs[0]; while (c && c.innerText.length < 400 && c.parentElement) c = c.parentElement;
  const L = (c ? c.innerText : document.body.innerText).split('\n').map(s => s.trim()).filter(Boolean);
  const MON = {JAN:'Jan',FEB:'Feb',MAR:'Mar',APR:'Apr',MAY:'May',JUN:'Jun',JUL:'Jul',AUG:'Aug',SEP:'Sep',OCT:'Oct',NOV:'Nov',DEC:'Dec'};
  const isTime = s => /^\d{1,2}:\d{2}\s*(AM|PM)$/i.test(s);
  const isRot = s => /^\d{3,6}$/.test(s);
  const isPrice = s => /^(PK|pk|[+-]\d|Ov\s*\d|Un\s*\d|o\d|u\d|EV|even)/i.test(s) || /^[+-]\d+$/.test(s);
  let date = '', time = '', out = [], i = 0;
  while (i < L.length) {
    let s = L[i];
    const dm = s.match(/-\s*([A-Za-z]{3})\s*(\d{1,2})\s*$/);
    if (dm && MON[dm[1].toUpperCase()]) { date = MON[dm[1].toUpperCase()] + dm[2].padStart(2, '0'); i++; continue; }
    const ph = s.match(/^#(\d{3,6})\s+(\d{1,2}:\d{2}\s*(?:AM|PM))?\s*(.*)$/i);   // phone layout row
    if (ph) {
      if (ph[2]) time = ph[2].replace(/\s+/g, '');
      let rest = ph[3], f = [];
      // fields after the team: spread, total, ml (may be on the same line or the next lines)
      const m = rest.match(/^(.*?)\s+((?:PK|[+-][\d½.]+)\s*[+-]\d+|$)\s*((?:Ov|Un)\s*[\d½.]+\s*[+-]\d+)?\s*([+-]\d+)?\s*$/i);
      let team = m ? m[1] : rest; if (m) f = [m[2], m[3], m[4]].filter(Boolean);
      let j = i + 1; while (f.length < 3 && j < L.length && isPrice(L[j]) && !L[j].startsWith('#')) f.push(L[j++]);
      out.push([date, time, ph[1], team.replace(/\s+/g, '').toUpperCase(), ...f.map(x => x.replace(/\s+/g, ''))].join(','));
      i = j; continue;
    }
    if (isTime(s)) { time = s.replace(/\s+/g, ''); i++; continue; }
    if (isRot(s) && i + 1 < L.length && !isPrice(L[i + 1])) {
      const rot = s, team = L[i + 1].replace(/\s+/g, '').toUpperCase(); let j = i + 2, f = [];
      while (f.length < 3 && j < L.length && isPrice(L[j])) f.push(L[j++].replace(/\s+/g, ''));
      out.push([date, time, rot, team, ...f].join(','));
      i = j; continue;
    }
    i++;
  }
  return out.join(';');
}
