"""Goalie saves for the No. 1 tiebreak (most starts, tiebreak most saves; Trina, Nov 14). Nov 15: PHI tie (Vladar 11, Woll 11 starts) broken by saves in their starts,
summed from the NHL API box scores in review/ng.txt (starter shots against minus goals against, through Nov 14): Woll 293, Vladar 262. EDM and CGY from the Nov 14 club-stats read."""
SAVES = {'EDM': {'Levi': 223, 'Jarry': 216, 'Tomkins': 44}, 'CGY': {'Wolf': 238, 'Cooley': 233}, 'PHI': {'Woll': 293, 'Vladar': 262}}
def sv(t, g): return SAVES.get(t, {}).get(g, 0)
