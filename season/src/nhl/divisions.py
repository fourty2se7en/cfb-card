"""Division strength from out-of-division results (Trina, Oct 27: weight Atlantic and Central strength; validated daily from data).
Strength = out-of-division points %, regressed with 20 games at .500 because the sample is small early in the season."""
import pathlib, html
D = pathlib.Path(__file__).parent
DIVNAME = {'A':'Atlantic','M':'Metropolitan','C':'Central','P':'Pacific'}
PRIOR_GP = 20
def load():
    R = {}
    for ln in (D/'divs_raw.txt').read_text().splitlines():
        if not ln.strip() or ln.startswith('#'): continue
        k, w, l, o, gf, ga = ln.split()
        d, opp = k.split('>'); w, l, o, gf, ga = map(int, (w, l, o, gf, ga)); gp = w+l+o
        R[(d, opp)] = dict(w=w, l=l, o=o, gp=gp, gf=gf, ga=ga, ppct=(2*w+o)/(2*gp) if gp else 0.5)
    return R
R = load()
def strength(div):
    r = R.get((div, 'ALL'))
    if not r: return 0.5
    return ((2*r['w']+r['o']) + PRIOR_GP) / (2*r['gp'] + 2*PRIOR_GP)
def rec(d, opp='ALL'):
    r = R.get((d, opp)); return f"{r['w']}-{r['l']}-{r['o']}" if r else 'n/a'
def signal(div_a, div_h):
    """Returns (side 'A'/'H' or None, points, gap, note)."""
    A, H = DIVNAME[div_a], DIVNAME[div_h]
    if A == H: return None, 0, 0, ''
    sa, sh = strength(A), strength(H); gap = sa - sh
    pts = 2 if abs(gap) >= 0.10 else (1 if abs(gap) >= 0.05 else 0)
    if not pts: return None, 0, gap, ''
    strong, weak = (A, H) if gap > 0 else (H, A)
    h2h = R.get((strong, weak))
    note = (f"{strong} is {rec(strong)} against other divisions ({strength(strong):.3f} adjusted) vs {weak} {rec(weak)} ({strength(weak):.3f})"
            + (f"; {strong} vs {weak} head to head {rec(strong, weak)}" if h2h else '') + '.')
    return ('A' if gap > 0 else 'H'), pts, gap, note
def panel_html():
    order = sorted(DIVNAME.values(), key=lambda d: -strength(d))
    rows = ''
    for i, d in enumerate(order):
        r = R[(d, 'ALL')]
        cells = ''.join(f"<td class='num r'>{rec(d, o) if o != d else '·'}</td>" for o in order)
        rows += (f"<tr><td class='num'>{i+1}</td><td><b>{d}</b></td><td class='num r'>{rec(d)}</td><td class='num r'>{r['ppct']:.3f}</td>"
                 f"<td class='num r'>{strength(d):.3f}</td><td class='num r'>{r['gf']/r['gp']:.2f}</td><td class='num r'>{r['ga']/r['gp']:.2f}</td>{cells}</tr>")
    heads = ''.join(f"<th class='r'>vs {d[:4]}.</th>" for d in order)
    return (f"<div class='scroll'><table><thead><tr><th>#</th><th>Division</th><th class='r'>Out of div.</th><th class='r'>P%</th><th class='r'>Adjusted</th>"
            f"<th class='r'>GF/G</th><th class='r'>GA/G</th>{heads}</tr></thead><tbody>{rows}</tbody></table></div>"
            "<div class='sub' style='margin-top:8px'>Out-of-division games only (W-L-OTL). Adjusted P% adds 20 games at .500 so small early samples do not swing too far. "
            "In a cross-division game the card adds a <b>Division strength</b> signal: 1 point to the team from the division that is .05+ stronger on adjusted P%, 2 points at .10+. Recomputed every day.</div>")
