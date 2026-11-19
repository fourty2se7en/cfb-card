"""Local only: rebuild a minimal ESPN scoreboard.json.gz and rankings.json.gz for ncaaw 2026-11-14 from the browser read (pull/slate_20261114.txt)."""
import json, gzip, os
from datetime import datetime, timedelta
D = '/home/claude/cfb14_ncaaw/season/data/espn/ncaaw/2026-11-14'; os.makedirs(D, exist_ok=True)
VEN = {'401918433': ('Moody Center', 'Austin', 'TX'), '401923183': ('Colonial Hall', 'White Sulphur Springs', 'WV'), '401906983': ('Sanford Pentagon', 'Sioux Falls', 'SD'),
       '401906091': ('The Palestra', 'Philadelphia', 'PA'), '401906965': ('Sanford Pentagon', 'Sioux Falls', 'SD')}
COL = {'TEX': 'af5c37', 'TAR': '000000', 'ND': '062340', 'DEP': '2d649c', 'KSU': '330a57', 'MINN': '5e0a2f', 'PENN': '082A74', 'UNC': '7bafd4', 'KU': '0051ba', 'NEB': 'e31937'}
SHORT = {'TEX': 'Texas', 'TAR': 'Tarleton St', 'ND': 'Notre Dame', 'DEP': 'DePaul', 'KSU': 'Kansas St', 'MINN': 'Minnesota', 'PENN': 'Penn', 'UNC': 'North Carolina', 'KU': 'Kansas', 'NEB': 'Nebraska'}
ev = []
for l in open('/home/claude/season/ncaaw/r1114/pull/slate_20261114.txt'):
    i, hm, a, h, ac, hc, n, ar, hr, arec, hrec, an, hn = l.rstrip('\n').split('|')
    d = datetime(2026, 11, 14 if hm >= '07' else 15, int(hm[:2]), int(hm[3:]))
    def comp(ab, side, conf, rk, rec, name):
        r = rec.split(',') if rec else []
        recs = [dict(type=t, summary=s) for t, s in zip(('total', 'home', 'road'), r)]
        t = dict(abbreviation=ab, displayName=name, shortDisplayName=SHORT.get(ab, name), color=COL.get(ab))
        if conf: t['conferenceId'] = conf
        return dict(homeAway=side, score='0', curatedRank=dict(current=int(rk) if rk else 99), records=recs, team=t)
    c = dict(conferenceCompetition=False, neutralSite=n == '1', status=dict(type=dict(state='pre', completed=False)), odds=[],
             competitors=[comp(h, 'home', hc, hr, hrec, hn), comp(a, 'away', ac, ar, arec, an)])
    if i in VEN: c['venue'] = dict(fullName=VEN[i][0], address=dict(city=VEN[i][1], state=VEN[i][2]))
    ev.append(dict(id=i, date=d.strftime('%Y-%m-%dT%H:%MZ'), competitions=[c]))
json.dump(dict(events=ev), gzip.open(D + '/scoreboard.json.gz', 'wt'))
AP = [(1,'SC','2-0'),(2,'MICH','2-0'),(3,'USC','2-0'),(4,'CONN','2-1'),(5,'DUKE','2-0'),(6,'TEX','2-0'),(7,'LOU','3-0'),(8,'VAN','2-0'),(9,'LSU','2-0'),(10,'IOWA','2-1'),(10,'UCLA','2-0'),(12,'UK','3-0'),(13,'ND','2-0'),(14,'OU','2-0'),(15,'TCU','3-0'),(16,'WASH','2-0'),(17,'OSU','3-0'),(18,'MINN','2-0'),(19,'OKST','2-0'),(19,'MD','1-1'),(21,'MISS','2-0'),(22,'ILL','2-0'),(23,'UNC','0-2'),(24,'WVU','3-0'),(25,'NEB','2-0')]
json.dump(dict(rankings=[dict(name='AP Top 25', occurrence=dict(displayValue='Week 2'), date='2026-11-09T08:00Z', ranks=[dict(current=r, recordSummary=s, team=dict(abbreviation=t)) for r, t, s in AP])]), gzip.open(D + '/rankings.json.gz', 'wt'))
print(len(ev), 'events')
