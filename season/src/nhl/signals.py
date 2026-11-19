"""Action Network signals, read Nov 15 ~6:55 AM Phoenix (public-betting + sharp-report pages, PRO).
Per game keyed AWAY-HOME. ml: open away/home (AN), bets% away, money% away.
Sharp Action lit on one moneyline in 3 games; totals Sharp Action in 2 games. Big Money on 3 puck lines.
sig_ml / sig_pl / sig_tot: dict signal -> side ('A','H','O','U')."""
AN = {  # Action Network PRO, public betting and sharp report read Nov 15 ~6:55 AM Phoenix (600 to 1,004 tickets per game); tot_now = The Odds API median
 'EDM-PHI': dict(ml_open=(-161, 135), bets=94, money=98, pl_bets=57, pl_money=82, tot_open=5.5, tot_now='6', o_bets=84, o_money=82, sig_ml={}, sig_pl={'Big Money': 'A'}, sig_tot={}),
 'CGY-ANA': dict(ml_open=(105, -125), bets=12, money=21, pl_bets=52, pl_money=53, tot_open=6.5, tot_now='6.5', o_bets=80, o_money=85, sig_ml={}, sig_pl={}, sig_tot={}),
 'FLA-DAL': dict(ml_open=(105, -125), bets=28, money=29, pl_bets=78, pl_money=67, tot_open=5.5, tot_now='6', o_bets=93, o_money=91, sig_ml={'Sharp Action': 'A'}, sig_pl={}, sig_tot={}),
 'NSH-SJS': dict(ml_open=(-135, 115), bets=90, money=62, pl_bets=58, pl_money=89, tot_open=5.5, tot_now='6.5', o_bets=48, o_money=37, sig_ml={'Sharp Action': 'H', 'Big Money': 'H', 'PRO Systems': 'A'}, sig_pl={'Big Money': 'A'}, sig_tot={'Sharp Action': 'O'}),
 'VAN-VGK': dict(ml_open=(230, -286), bets=3, money=4, pl_bets=2, pl_money=39, tot_open=6.5, tot_now='6.5', o_bets=76, o_money=88, sig_ml={'Sharp Action': 'A'}, sig_pl={'Big Money': 'A'}, sig_tot={'Sharp Action': 'U'}),
}
DK = {  # second source: The Odds API median of books, read 6:38 AM Phoenix (no 7:09 opening read yet)
 'EDM-PHI': {'ml': (-150, 126), 'pl': (-1.5, 162, -198), 'total': (6.0, -113, -105)},
 'CGY-ANA': {'ml': (130, -154), 'pl': (1.5, -185, 155), 'total': (6.5, -125, 104)},
 'FLA-DAL': {'ml': (112, -134), 'pl': (1.5, -225, 186), 'total': (6.0, 100, -120)},
 'NSH-SJS': {'ml': (-170, 142), 'pl': (-1.5, 145, -170), 'total': (6.5, -106, -113)},
 'VAN-VGK': {'ml': (320, -420), 'pl': (1.5, 133, -155), 'total': (6.5, -109, -110)},
}
WEIGHTS = {'Sharp Action':2, 'PRO Systems':1, 'Big Money':1}
# 2025-26 final regular season (NHL API standings 2026-04-16): points % and goal differential
LAST = dict(COL=(0.738,99),CAR=(0.689,56),DAL=(0.683,53),BUF=(0.665,47),TBL=(0.646,59),MTL=(0.646,27),MIN=(0.634,32),BOS=(0.610,22),OTT=(0.604,32),
 PIT=(0.598,25),PHI=(0.598,7),WSH=(0.579,19),VGK=(0.579,15),EDM=(0.567,13),UTA=(0.561,28),DET=(0.561,-17),CBJ=(0.561,0),ANA=(0.561,-15),NYI=(0.555,-8),
 LAK=(0.549,-22),NJD=(0.530,-24),STL=(0.524,-27),NSH=(0.524,-22),SJS=(0.524,-41),FLA=(0.512,-25),WPG=(0.500,-29),SEA=(0.482,-37),TOR=(0.476,-46),
 CGY=(0.470,-47),NYR=(0.470,-12),CHI=(0.439,-62),VAN=(0.354,-100))

# ===== Pick rule set (approved by Trina Oct 30, 2026 after the v2 pick-method review of every game Sep 29 to Oct 28).
# One rule set per card. The logic that applies it lives in rules.py, shared by the card and the daily re-check (review/recheck.py).
# Change only on Trina's say-so. Price limits are locked.
RULESET = {
 'approved': '2026-10-30',        # stricter versions count only picks from this date on
 'price': dict(fav_max=-200, dog_min=100, dog_max=200),
 'switch': dict(off_min_picks=20, version_min_picks=30),
 'ML1': dict(market='Moneyline', short='ML rule', versions={
     'base':   dict(lead=2, label='Signal side with a lead of 2+, price within limits'),
     'strict': dict(lead=3, label='Signal side with a lead of 3+, price within limits')}),
 'PL1': dict(market='Puck line', short='PL rule', versions={
     'base':   dict(confirm=False, label='Puck line of the team with Action Network Sharp Action on its moneyline'),
     'strict': dict(confirm=True, label='Sharp Action team puck line, plus money % above ticket % or a reverse line move on that team')}),
 'TOT1': dict(market='Total', short='Total rule', versions={
     'base':   dict(both=False, label='Over in Atlantic vs Pacific games or when the division signal is 2 points'),
     'strict': dict(both=True, label='Over only when it is Atlantic vs Pacific and the division signal is 2 points')}),
 'P1O': dict(market='1st period total', short='1P over rule', versions={   # Nov 12 (Trina): game props
     'base':   dict(line=1.5, label='1st period Over 1.5 when the totals rule (TOT2) takes the Over (season replay at SBR close 123-74 +16.2u)'),
     'strict': dict(line=1.5, label='Same, only when the totals signals lean under by 3+ (stricter)')}),
 'TOT2': dict(market='Total', short='Totals rule', versions={   # Nov 12 (Trina): every game is evaluated for an over or under
     'base':   dict(lead=2, label='Take the other side when the totals signals lean one way by 2+ points (season replay 122-92-3 +21.6u)'),
     'strict': dict(lead=3, label='Take the other side when the totals signals lean one way by 3+ points (season replay 84-67-3 +11.6u)')}),
}
