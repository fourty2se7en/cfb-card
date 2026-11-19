"""NBA teams: official NBA.com team pages, names, guide. Arena names follow sponsors; update when they change."""
ID = {'ATL':37,'BOS':38,'BKN':51,'CHA':66,'CHI':41,'CLE':39,'DAL':42,'DEN':43,'DET':65,'GSW':44,'HOU':45,'IND':54,'LAC':46,'LAL':47,'MEM':63,
'MIA':48,'MIL':49,'MIN':50,'NOP':40,'NYK':52,'OKC':60,'ORL':53,'PHI':55,'PHX':56,'POR':57,'SAC':58,'SAS':59,'TOR':61,'UTA':62,'WAS':64}
SLUG = {'ATL':'hawks','BOS':'celtics','BKN':'nets','CHA':'hornets','CHI':'bulls','CLE':'cavaliers','DAL':'mavericks','DEN':'nuggets','DET':'pistons',
'GSW':'warriors','HOU':'rockets','IND':'pacers','LAC':'clippers','LAL':'lakers','MEM':'grizzlies','MIA':'heat','MIL':'bucks','MIN':'timberwolves',
'NOP':'pelicans','NYK':'knicks','OKC':'thunder','ORL':'magic','PHI':'76ers','PHX':'suns','POR':'blazers','SAC':'kings','SAS':'spurs','TOR':'raptors',
'UTA':'jazz','WAS':'wizards'}
URL = {t: f'https://www.nba.com/team/16106127{ID[t]:02d}/{SLUG[t]}' for t in ID}
FULL = {'ATL':'Atlanta Hawks','BOS':'Boston Celtics','BKN':'Brooklyn Nets','CHA':'Charlotte Hornets','CHI':'Chicago Bulls','CLE':'Cleveland Cavaliers',
'DAL':'Dallas Mavericks','DEN':'Denver Nuggets','DET':'Detroit Pistons','GSW':'Golden State Warriors','HOU':'Houston Rockets','IND':'Indiana Pacers',
'LAC':'LA Clippers','LAL':'Los Angeles Lakers','MEM':'Memphis Grizzlies','MIA':'Miami Heat','MIL':'Milwaukee Bucks','MIN':'Minnesota Timberwolves',
'NOP':'New Orleans Pelicans','NYK':'New York Knicks','OKC':'Oklahoma City Thunder','ORL':'Orlando Magic','PHI':'Philadelphia 76ers','PHX':'Phoenix Suns',
'POR':'Portland Trail Blazers','SAC':'Sacramento Kings','SAS':'San Antonio Spurs','TOR':'Toronto Raptors','UTA':'Utah Jazz','WAS':'Washington Wizards'}
# team: (city/market, nickname, mascot, arena, franchise began, colors)
TEAMS = {
 'BOS':('Boston','Celtics','Lucky the Leprechaun','TD Garden',1946,'Green, white'),
 'BKN':('Brooklyn','Nets','None official','Barclays Center',1967,'Black, white'),
 'NYK':('New York (Manhattan)','Knicks','None official','Madison Square Garden',1946,'Blue, orange'),
 'PHI':('Philadelphia','76ers','Franklin the Dog','Xfinity Mobile Arena',1946,'Blue, red'),
 'TOR':('Toronto','Raptors','The Raptor','Scotiabank Arena',1995,'Red, black'),
 'CHI':('Chicago','Bulls','Benny the Bull','United Center',1966,'Red, black'),
 'CLE':('Cleveland','Cavaliers','Moondog','Rocket Arena',1970,'Wine, gold, navy'),
 'DET':('Detroit','Pistons','Hooper','Little Caesars Arena',1941,'Red, royal blue'),
 'IND':('Indianapolis','Pacers','Boomer','Gainbridge Fieldhouse',1967,'Navy, gold'),
 'MIL':('Milwaukee','Bucks','Bango','Fiserv Forum',1968,'Green, cream'),
 'ATL':('Atlanta','Hawks','Harry the Hawk','State Farm Arena',1946,'Red, volt green'),
 'CHA':('Charlotte','Hornets','Hugo the Hornet','Spectrum Center',1988,'Teal, purple'),
 'MIA':('Miami','Heat','Burnie','Kaseya Center',1988,'Red, black, yellow'),
 'ORL':('Orlando','Magic','Stuff the Magic Dragon','Kia Center',1989,'Blue, black, silver'),
 'WAS':('Washington','Wizards','G-Wiz','Capital One Arena',1961,'Navy, red'),
 'DEN':('Denver','Nuggets','Rocky the Mountain Lion','Ball Arena',1967,'Navy, gold, red'),
 'MIN':('Minneapolis','Timberwolves','Crunch the Wolf','Target Center',1989,'Navy, lake blue, green'),
 'OKC':('Oklahoma City','Thunder','Rumble the Bison','Paycom Center',1967,'Thunder blue, orange'),
 'POR':('Portland','Trail Blazers','Blaze the Trail Cat','Moda Center',1970,'Red, black'),
 'UTA':('Salt Lake City','Jazz','Jazz Bear','Delta Center',1974,'Purple, black, white'),
 'GSW':('San Francisco','Warriors','None official','Chase Center',1946,'Royal blue, gold'),
 'LAC':('Los Angeles (Inglewood)','Clippers','Chuck the Condor','Intuit Dome',1970,'Blue, red, black'),
 'LAL':('Los Angeles','Lakers','None official','Crypto.com Arena',1947,'Purple, gold'),
 'PHX':('Phoenix','Suns','Go the Gorilla','Mortgage Matchup Center',1968,'Purple, orange'),
 'SAC':('Sacramento','Kings','Slamson the Lion','Golden 1 Center',1923,'Purple, silver'),
 'DAL':('Dallas','Mavericks','Champ','American Airlines Center',1980,'Royal blue, navy, silver'),
 'HOU':('Houston','Rockets','Clutch the Bear','Toyota Center',1967,'Red, silver, black'),
 'MEM':('Memphis','Grizzlies','Grizz','FedExForum',1995,'Beale Street blue, navy'),
 'NOP':('New Orleans','Pelicans','Pierre the Pelican','Smoothie King Center',2002,'Navy, gold, red'),
 'SAS':('San Antonio','Spurs','The Coyote','Frost Bank Center',1967,'Black, silver'),
}
CONFDIV = {'E':{'Atlantic':['BOS','BKN','NYK','PHI','TOR'],'Central':['CHI','CLE','DET','IND','MIL'],'Southeast':['ATL','CHA','MIA','ORL','WAS']},
           'W':{'Northwest':['DEN','MIN','OKC','POR','UTA'],'Pacific':['GSW','LAC','LAL','PHX','SAC'],'Southwest':['DAL','HOU','MEM','NOP','SAS']}}

# WNBA teams that appear on the card (WNBA Finals). Keys avoid clashes with NBA abbreviations.
WNBA = {'GSV','ATD'}
URL.update({'GSV':'https://valkyries.wnba.com/','ATD':'https://dream.wnba.com/'})
FULL.update({'GSV':'Golden State Valkyries','ATD':'Atlanta Dream'})
