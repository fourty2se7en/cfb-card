"""Builds the rules.py game context from the rebuilt season data (engine.build_all) so the re-check scores games
with exactly the same code as the card."""
import sys, pathlib
R = pathlib.Path(__file__).parent; sys.path.insert(0, str(R.parent)); sys.path.insert(0, str(R))
import rules
from build_data import ok, novig_home, DIVNAME
from engine import LAST, FUT
from score import open_check, tot_open_check

def ctx_from_rebuild(g):
    mla, mlh = g['sb']['mlc']
    if not (ok(mla) and ok(mlh)) or (mla == -110 and mlh == -110 and g['sb']['mlo'][0] is not None and abs(novig_home(*g['sb']['mlo']) - 0.5) > 0.04):
        return None
    an = g['an']; A, H = g['A'], g['H']
    pHo = open_check(g)
    c = dict(a=g['a'], h=g['h'], date=g['date'], mla=mla, mlh=mlh,
             ml_open=None, bets=an['bets'], money=an['money'], o_bets=an['o_bets'], o_money=an['o_money'],
             sig_ml=g['sh_ml'] or {}, sig_tot=g['sh_tot'] or {},
             estH=0.4*g['pH_model'] + 0.6*novig_home(mla, mlh), sv_a=g['svA'], sv_h=g['svH'], loss_a=g['lossA'], loss_h=g['lossH'],
             rest_a=A['rest'], rest_h=H['rest'], home_rec_h=H['home'], road_rec_a=A['road'], strk_a=A['strk'], strk_h=H['strk'],
             l10_a=A['l10'] if A['gp'] else None, l10_h=H['l10'] if H['gp'] else None,
             gd_a=A['diff']/A['gp'] if A['gp'] else None, gd_h=H['diff']/H['gp'] if H['gp'] else None,
             last_a=LAST[g['a']][0], last_h=LAST[g['h']][0], ppct_a=A['ppct'] if A['gp'] else None, ppct_h=H['ppct'] if H['gp'] else None,
             cup_a=FUT[g['a']], cup_h=FUT[g['h']], div_a=DIVNAME[g['div_a']], div_h=DIVNAME[g['div_h']], div_str=g['div'])
    if pHo is not None:
        # rules.score works from an opening price pair; rebuild the pair from the agreed no-vig home probability
        c['ml_open'] = _pair(pHo)
    plc = g['sb']['plc']
    if plc and abs(plc['sp']) == 1.5 and ok(plc['a'][0]) and ok(plc['a'][1]):
        c['pl'] = dict(sp_a=plc['sp'], price_a=plc['a'][0], price_h=plc['a'][1])
    tc = g['sb']['tc']
    if tc and ok(tc['ou'][0]) and ok(tc['ou'][1]):
        c.update(line=tc['line'], tprice=tc['ou'], tot_open=tot_open_check(g), lamT=g['lamT'])
        A5, H5 = A['last5'], H['last5']
        c['last5'] = (sum(A5)+sum(H5))/10 if len(A5) == 5 and len(H5) == 5 else None
    return c

def _pair(pH):
    """No-vig home probability -> a fair (away, home) American price pair with the same no-vig split."""
    def am(p): return -round(100*p/(1-p)) if p > 0.5 else round(100*(1-p)/p)
    return (am(1-pH), am(pH))

def grade(g, pk):
    ag, hg = g['ag'], g['hg']
    if pk['market'] == 'Moneyline':
        return 'W' if ((ag > hg) if pk['side'] == 'A' else (hg > ag)) else 'L'
    if pk['market'] == 'Puck line':
        m = (ag-hg) if pk['side'] == 'A' else (hg-ag)
        return 'W' if m + pk['line'] > 0 else 'L'
    t = ag + hg
    if t == pk['line']: return 'P'
    return 'W' if ((t > pk['line']) == (pk['side'] == 'O')) else 'L'
