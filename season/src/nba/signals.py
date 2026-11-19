"""Nov 17: no browser in this run, so no Action Network read: splits are neutral (50/50) and no PRO signals. ml_open, sp_open and tot_open are The Odds API opening median (7:13 AM); tot_now the latest read (4:45 PM)."""
AN = {
 'NYK-TOR': dict(ml_open=(-145, 125), bets=50, money=50, sp_open=-3, sp_bets=50, sp_money=50, tot_open=215.5, tot_now='215.5', o_bets=50, o_money=50,
                 sig_ml={}, sig_sp={}, sig_tot={}, n_bets=0),
 'POR-MIN': dict(ml_open=(113, -135), bets=50, money=50, sp_open=2, sp_bets=50, sp_money=50, tot_open=227.5, tot_now='226', o_bets=50, o_money=50,
                 sig_ml={}, sig_sp={}, sig_tot={}, n_bets=0),
 'DET-SAS': dict(ml_open=(310, -400), bets=50, money=50, sp_open=9.5, sp_bets=50, sp_money=50, tot_open=222.5, tot_now='221.5', o_bets=50, o_money=50,
                 sig_ml={}, sig_sp={}, sig_tot={}, n_bets=0),
 'UTA-LAC': dict(ml_open=(200, -239), bets=50, money=50, sp_open=6.5, sp_bets=50, sp_money=50, tot_open=225.5, tot_now='225.5', o_bets=50, o_money=50,
                 sig_ml={}, sig_sp={}, sig_tot={}, n_bets=0),
 'CHA-LAL': dict(ml_open=(250, -305), bets=50, money=50, sp_open=7.5, sp_bets=50, sp_money=50, tot_open=220.5, tot_now='223', o_bets=50, o_money=50,
                 sig_ml={}, sig_sp={}, sig_tot={}, n_bets=0),
}
# Model Projections (info only, not scored)
MODELPROJ = {}
WEIGHTS = {'Sharp Action':2, 'PRO Systems':1, 'Big Money':1}
# 2025-26 final regular season (NBA.com): win %, net rating
_L = dict(ATL=(46,2.2),BOS=(56,8.3),BKN=(20,-10.0),CHA=(44,4.9),CHI=(31,-5.3),CLE=(52,4.1),DAL=(26,-5.2),DEN=(54,5.2),DET=(60,8.4),GSW=(37,-0.5),
 HOU=(52,5.4),IND=(19,-7.8),LAC=(42,1.1),LAL=(53,1.5),MEM=(25,-6.0),MIA=(43,2.1),MIL=(32,-6.1),MIN=(49,3.1),NOP=(26,-4.4),NYK=(53,6.4),
 OKC=(64,11.1),ORL=(45,0.6),PHI=(45,-0.1),PHX=(45,1.4),POR=(42,-0.4),SAC=(22,-9.7),SAS=(62,8.4),TOR=(46,2.9),UTA=(22,-8.2),WAS=(17,-11.8))
LAST = {t: (w/82, n) for t, (w, n) in _L.items()}
# WNBA Finals teams: 2026 regular season (44 games) as 'last season' (stats.wnba.com)
LAST.update({'GSV': (32/44, 9.1), 'ATD': (30/44, 8.4)})


# ------------------------------------------------------------------ NBA card pick rules (approved Oct 29, 2026; lowered thresholds while the sample is small)
# Price limits are Trina's and locked: favorite moneyline no longer than -200, underdog moneyline +100 to +200.
RULES = {
    'FAV_ML': dict(market='Moneyline', label='Favorite moneyline', variants={
        'lowered': dict(lead=2, desc='Favorite -200 to -100 with a signal lead of 2+ on it'),
        'strict':  dict(lead=3, desc='Favorite -200 to -100 with a signal lead of 3+ on it')}),
    'DOG_ML': dict(market='Moneyline', label='Underdog moneyline', variants={
        'lowered': dict(lead=1, need_move=False, desc='Underdog +100 to +200 with the signals on it (lead 1+)'),
        'strict':  dict(lead=1, need_move=True, desc='Underdog +100 to +200 with the signals on it and the line moved toward it against the tickets')}),
    'SPREAD_MOVE': dict(market='Spread', label='Spread line move', variants={
        'lowered': dict(thr=0.5, desc='Spread on the side the line moved toward by 0.5+ at both sources against the ticket majority'),
        'strict':  dict(thr=1.0, desc='Spread on the side the line moved toward by 1+ at both sources against the ticket majority')}),
    'UNDER_DROP': dict(market='Total', label='Under on a dropping total', variants={
        'lowered': dict(min_over=0, desc='Under when the total dropped from the open at both sources'),
        'strict':  dict(min_over=75, desc='Under when the total dropped at both sources with 75%+ of tickets on the over')}),
    'OVER': dict(market='Total', label='Over', variants={
        'lowered': dict(desc='No over rule has a winning record yet: overs are No pick'),
        'strict':  dict(desc='No over rule has a winning record yet: overs are No pick')}),
}
FAV_MIN, FAV_MAX = -200, -100      # locked
DOG_MIN, DOG_MAX = 100, 200        # locked
