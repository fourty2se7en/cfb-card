import json,glob,re
NONE={('DET-WAS','side'):"No active rule fits a side: Detroit at -459 is past the -200 limit on the favorite moneyline rule, and the model only spread and moneyline rules lean Detroit in their Solid tier, which is turned off, so they are logged as would-be picks.",
 ('DET-WAS','total'):"The model total rule (blended and calibrated) leans Under 220.5, but its Solid tier is turned off, so it is logged as a would-be pick. The under on a dropping total rule does not fit because the total went up.",
 ('TOR-PHI','side'):"The spread moved toward Toronto against the tickets (line move rule) and the model only rules lean Toronto, but those rules and tiers are turned off, so they are logged as would-be picks."}
for f in glob.glob('final/sports_nba_games__2026-11-12_*.json'):
    g=json.load(open(f)); k=f.split('_')[-1][:-5]
    for s in ('side','total'):
        if (k,s) in NONE and 'none' in g['picks'].get(s,{}): g['picks'][s]['none']=NONE[(k,s)]
    g['lines']['book']='The Odds API median of books (opening read; picks priced at the opener)'; g['lines']['line_source']='The Odds API median of books'
    g['lines']['openers']=re.sub('DraftKings','The Odds API open',g['lines'].get('openers',''))
    json.dump(g,open(f,'w'),indent=1)
for f in glob.glob('final/sports_nba_picks__2026-11-12_*.json')+glob.glob('final/sports_nba_games__2026-11-12_*.json'):
    s=open(f).read(); s2=s.replace('"line_source": "texas222"','"line_source": "The Odds API median of books"').replace('DraftKings via ESPN','The Odds API open vs latest').replace('texas222','The Odds API')
    if s2!=s: open(f,'w').write(s2)
