"""A57 gap guard (Trina approved Nov 16, 2026; live from the Nov 17 run). NCAAM only.

1. Spread gap guard: any full game spread pick, from any rule (SPREAD_MOVE_*, MODEL_ONLY_SPREAD, NCAAM_SP_CAL, EFF_SPREAD,
   ROAD1DAY_FADE, MODEL_EDGE, ...), whose model gap against the market is MORE than spread_max points
   (|model home margin + home spread| at the line the run reads) is not a card pick: it is a would-be pick (shadow true).
2. Over gap requirement: a full game Over pick, from any rule (OVER_*, EFF_OVER, EARLY_OVER_OPEN, MODEL_ONLY_TOTAL Over, ...),
   needs a model gap of at least over_min points (model total minus market total) to be a card pick; under that it is a would-be pick.
Unders, moneylines and 1st half picks are unchanged. Guarded picks still count toward their tier's status record (A58).
Limits come from hub meta/ncaam policy.gap_guard {spread_max, over_min} when present; defaults 10 and 10.

Use: apply_gap_guard(picks, game[, limits]) for every rule, at the point that decides card vs would-be.
  picks: list of dicts with market ('Spread' | 'Total' | ...) and side ('home'|'away'|'over'|'under'); line optional
         (pick side line; when missing the game's market line is used).
  game:  dict with home_margin (model, home minus away), home_spread (market home line), model_total, total (market total).
         ctx_build(g) makes it from a build.py game row; ctx_doc(d) from a hub game doc.
Each guarded pick gets p['gap_guard'] = {gap, limit, kind, conflict}; the function returns the guarded picks.
"""
import re

DEFAULT = {'spread_max': 10, 'over_min': 10}
_num = lambda s: (lambda m: float(m.group()) if m else None)(re.search(r'[-+]?\d+(\.\d+)?', str(s if s is not None else '')))


def limits(meta=None):
    """Limits from hub meta ncaam (whole doc or its data) policy.gap_guard; defaults when absent."""
    m = (meta or {}); m = m.get('data', m) if isinstance(m, dict) else {}
    gg = ((m.get('policy') or {}).get('gap_guard') or {}) if isinstance(m, dict) else {}
    out = dict(DEFAULT)
    for k in ('spread_max', 'over_min'):
        if gg.get(k) is not None: out[k] = float(gg[k])
    return {k: (int(v) if float(v).is_integer() else v) for k, v in out.items()}


def ctx_build(g):
    """Game context from a build.py game row (emar, sp, etot, tot)."""
    return dict(home_margin=g.get('emar'), home_spread=g.get('sp'), model_total=g.get('etot'), total=g.get('tot'))


def ctx_doc(d):
    """Game context from a hub game doc (model.our_spread 'TEAM -x', model.our_total, lines.spread.home, lines.total.over)."""
    m = d.get('model') or {}; L = d.get('lines') or {}
    A, H = d.get('away'), d.get('home')
    ac = A.get('code') if isinstance(A, dict) else A; hc = H.get('code') if isinstance(H, dict) else H
    hm = None; os_ = m.get('our_spread')
    if os_:
        t = str(os_).rsplit(' ', 1); v = _num(t[-1]); tm = t[0].strip()
        if v is not None: hm = -v if tm == hc else (v if tm == ac else None)
    sh = (L.get('spread') or {}).get('home')
    hs = (0.0 if str(sh).startswith('PK') else _num(str(sh).split()[0])) if sh else None
    to = (L.get('total') or {}).get('over')
    return dict(home_margin=hm, home_spread=hs, model_total=_num(m.get('our_total')), total=_num(str(to).split()[0]) if to else None)


def _f(x):
    return f"{x:.1f}"


def apply_gap_guard(picks, game, lim=None):
    lim = lim or limits(); out = []
    for p in picks:
        mkt, side = p.get('market'), p.get('side'); ln = p.get('line')
        if isinstance(ln, str): ln = 0.0 if ln.startswith('PK') else _num(ln)
        if mkt == 'Spread' and side in ('home', 'away'):
            hm = game.get('home_margin')
            hs = (ln if side == 'home' else -ln) if ln is not None else game.get('home_spread')
            if hm is None or hs is None: continue
            gap = round(abs(hm + hs), 1)
            if gap > lim['spread_max']:
                p['gap_guard'] = dict(kind='spread', gap=gap, limit=lim['spread_max'],
                                      conflict=f"Gap guard: model {_f(gap)} points from the market (limit {lim['spread_max']:g})")
                out.append(p)
        elif mkt == 'Total' and side == 'over':
            mt = game.get('model_total'); tl = ln if ln is not None else game.get('total')
            if mt is None or tl is None: continue
            gap = round(mt - tl, 1)
            if gap < lim['over_min']:
                where = 'above' if gap >= 0 else 'below'
                p['gap_guard'] = dict(kind='over', gap=gap, limit=lim['over_min'],
                                      conflict=f"Over gap guard: model {_f(abs(gap))} points {where} the market (needs {lim['over_min']:g})")
                out.append(p)
    return out


def doc_flag(gg):
    """The flag field written on a pick doc: {gap, limit} plus kind."""
    return dict(gap=gg['gap'], limit=gg['limit'], kind=gg['kind'])
