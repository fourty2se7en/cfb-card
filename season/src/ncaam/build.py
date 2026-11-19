"""NCAA card builder (men and women). Usage: python3 build.py M|W YYYY-MM-DD
Reads data/ (texas222 board, ESPN slate, Action Network splits, ratings, backtest results) and src/rules_state_<lg>.json,
writes out/<lg>/index.html and out/<lg>/ledger_today.json. Same look, ledger and Results tab as the NBA card."""
import json, re, sys, html, pathlib, datetime
import rules as R
D = pathlib.Path(__file__).parent; DATA = D.parent/'data'
LG = sys.argv[1] if len(sys.argv) > 1 else 'M'
DATE = sys.argv[2] if len(sys.argv) > 2 else datetime.date.today().isoformat()
dt = datetime.date.fromisoformat(DATE)
DATE_L = dt.strftime('%A, %B ') + str(dt.day) + dt.strftime(', %Y')
NAME = 'NCAAM' if LG == 'M' else 'NCAAW'
FULL = "Men's college basketball" if LG == 'M' else "Women's college basketball"
esc = lambda s: html.escape(str(s), quote=True)
CONF = {'1': 'America East', '2': 'ACC', '3': 'Atlantic 10', '4': 'Big East', '5': 'Big Sky', '6': 'Big South', '7': 'Big Ten', '8': 'Big 12', '9': 'Big West',
        '10': 'CAA', '11': 'Conference USA', '12': 'Ivy League', '13': 'MAAC', '14': 'MAC', '16': 'MEAC', '18': 'Missouri Valley', '19': 'NEC', '20': 'Ohio Valley',
        '21': 'Pac-12', '22': 'Patriot', '23': 'SEC', '24': 'Southern', '25': 'Southland', '26': 'SWAC', '27': 'Sun Belt', '29': 'WCC', '30': 'WAC',
        '44': 'Mountain West', '45': 'Horizon', '46': 'ASUN', '47': 'Big West', '49': 'Summit', '62': 'American'}
STATE = json.loads((D/f'rules_state_{LG}.json').read_text())
# a rule only makes picks on slates on or after the date it went live (no retroactive picks)
LIVE = {k: dict(v, on=v['on'] and v.get('since', '2026-11-02') <= DATE) for k, v in STATE['rules'].items()}

# ---------------- texas222 board
def t222():
    rows = [l.split('|') for l in (DATA/f't222_{LG.lower()}.txt').read_text().strip().splitlines()[1:]]
    rows = [r for r in rows if (LG == 'M' and r[0] in 'MX') or (LG == 'W' and r[0] == 'W')]
    out = []
    for a, h in zip(rows[0::2], rows[1::2]):
        def sp(x):
            m = re.match(r'([+-][\d.]+|PK)\s*([+-]\d+)', x or ''); return ((0.0 if m.group(1) == 'PK' else float(m.group(1))), int(m.group(2))) if m else (None, None)
        def tot(x):
            m = re.match(r'[ou]([\d.]+)([+-]\d+)', x or ''); return (float(m.group(1)), int(m.group(2))) if m else (None, None)
        def ml(r): return int(r[5]) if len(r) > 5 and re.match(r'^[+-]\d+$', r[5]) else None
        sa, sh = sp(a[3] if len(a) > 3 else ''), sp(h[3] if len(h) > 3 else '')
        ta, th = tot(a[4] if len(a) > 4 else ''), tot(h[4] if len(h) > 4 else '')
        out.append(dict(menu=a[0], ttime=a[1], ta=a[2], th=h[2], sp_a=sa[0], spp_a=sa[1], sp_h=sh[0], spp_h=sh[1], tot=ta[0], o_price=ta[1], u_price=th[1], ml_a=ml(a), ml_h=ml(h),
                        posted=sa[0] is not None))
    return out
BOARD = t222()

# ---------------- ESPN slate
def norm(s):
    s = s.upper().replace('&', 'AND').replace('AANDM', 'AM').replace("'", '').replace('.', '').replace('-', ' ').replace('(W)', '')
    s = re.sub(r'\bSTATE\b', 'ST', s); s = re.sub(r'\bSAINT\b', 'ST', s)
    return re.sub(r'\s+', ' ', s).strip()
ALIAS = {'MIAMI FLORIDA': 'MIA', 'MIAMI OHIO': 'M-OH', 'ARKANSAS LITTLE ROCK': 'LR', 'VA COMMONWEALTH': 'VCU', 'MT ST MARYS': 'MSM', 'CHARLOTTE U': 'CLT',
         'UL MONROE': 'ULM', 'UL LAFAYETTE': 'UL', 'ST PETERS': 'SPU', 'UMKC': 'KC', 'THE CITADEL': 'CIT', 'TENNESSEE MARTIN': 'UTM', 'EAST TENN ST': 'ETSU',
         'WISC MILWAUKEE': 'MILW', 'SEATTLE U': 'SEA', 'HAWAII': 'HAW', 'NC ASHEVILLE': 'UNCA', 'LONG ISLAND': 'LIU', 'FLA GULF COAST': 'FGCU', 'CENTRAL FLORIDA': 'UCF',
         'CHARLESTON SOU': 'CHSO', 'USC UPSTATE': 'UPST', 'BOSTON U': 'BU', 'ST THOMAS': 'STMN', 'CENTRAL CONNECTICUT': 'CCSU', 'SE MISSOURI ST': 'SEMO',
         'NORTH CAROLINA CENTRAL': 'NCCU', 'TEXAS AM CORPUS': 'AMCC', 'MD EASTERN SHORE': 'UMES', 'EAST TEXAS AM': 'ETAM', 'FAIRLEIGH DICKINSON': 'FDU',
         'BETHUNE COOKMAN': 'BCU', 'FLORIDA AM': 'FAMU', 'MISSISSIPPI': 'MISS', 'GARDNER WEBB': 'GWEB', 'CONNECTICUT': 'CONN', 'NORTHWESTERN ST': 'NWST',
         'LOYOLA MARYLAND': 'L-MD', 'ST JOHNS': 'SJU', 'ST MARYS CA': 'SMC', 'ST BONAVENTURE': 'SBU', 'GEORGIA SOUTHERN': 'GASO', 'WESTERN KENTUCKY': 'WKU',
         'NC ST': 'NCSU', 'ABILENE CHRISTIAN': 'ACU', 'COASTAL CAROLINA': 'CCU', 'UC DAVIS': 'UCD', 'LONG BEACH ST': 'LBSU', 'UTAH TECH': 'UTU', 'ROBERT MORRIS': 'RMU',
         'EASTERN WASHINGTON': 'EWU', 'EASTERN MICHIGAN': 'EMU', 'EASTERN ILLINOIS': 'EIU', 'WESTERN CAROLINA': 'WCU', 'WESTERN MICHIGAN': 'WMU', 'WESTERN ILLINOIS': 'WIU',
         'CENTRAL MICHIGAN': 'CMU', 'CENTRAL ARKANSAS': 'CARK', 'SOUTHERN INDIANA': 'USI', 'SOUTHERN': 'SOU', 'NORTH DAKOTA': 'UND', 'NORTH ALABAMA': 'UNA',
         'GEORGIA ST': 'GAST', 'BOWLING GREEN': 'BGSU', 'PEPPERDINE': 'PEPP', 'CORNELL': 'COR', 'OAKLAND': 'OAK', 'MICHIGAN': 'MICH', 'MONMOUTH': 'MONM',
         'MASSACHUSETTS': 'MASS', 'TROY': 'TROY', 'JAMES MADISON': 'JMU', 'QUINNIPIAC': 'QUIN', 'MICHIGAN ST': 'MSU', 'ELON': 'ELON', 'COLUMBIA': 'COLU',
         'DARTMOUTH': 'DART', 'MARIST': 'MRST', 'NORTH CAROLINA': 'UNC', 'INDIANA ST': 'INST', 'INDIANA': 'IU', 'YOUNGSTOWN ST': 'YSU', 'BUFFALO': 'BUF',
         'MARSHALL': 'MRSH', 'BALL ST': 'BALL', 'NIAGARA': 'NIA', 'WEST VIRGINIA': 'WVU', 'MEMPHIS': 'MEM', 'IOWA ST': 'ISU', 'AIR FORCE': 'AF', 'WRIGHT ST': 'WRST',
         'OLD DOMINION': 'ODU', 'RIDER': 'RID', 'PITTSBURGH': 'PITT', 'KENT ST': 'KENT', 'LOUISIANA TECH': 'LT', 'SETON HALL': 'HALL', 'CAMPBELL': 'CAM',
         'MOREHEAD ST': 'MORE', 'CANISIUS': 'CAN', 'PENN ST': 'PSU', 'DENVER': 'DEN', 'WISCONSIN': 'WIS', 'BELMONT': 'BEL', 'PURDUE': 'PUR', 'GONZAGA': 'GONZ',
         'TENNESSEE TECH': 'TNTC', 'MISSISSIPPI ST': 'MSST', 'FORDHAM': 'FOR', 'KANSAS': 'KU', 'CREIGHTON': 'CREI', 'VALPARAISO': 'VAL', 'AKRON': 'AKR', 'OHIO': 'OHIO',
         'SOUTH ALABAMA': 'USA', 'LOYOLA CHICAGO': 'LUC', 'LINDENWOOD': 'LIN', 'TCU': 'TCU', 'TOLEDO': 'TOL', 'ARKANSAS ST': 'ARST', 'TULANE': 'TULN', 'WEST GEORGIA': 'WGA',
         'DEPAUL': 'DEP', 'ORAL ROBERTS': 'ORU', 'DAVIDSON': 'DAV', 'WASHINGTON ST': 'WSU', 'OHIO ST': 'OSU', 'BYU': 'BYU', 'UTAH': 'UTAH', 'COLORADO': 'COLO',
         'MINNESOTA': 'MINN', 'CHATTANOOGA': 'UTC', 'LOUISVILLE': 'LOU', 'LA SALLE': 'LAS', 'HOUSTON': 'HOU', 'NEW MEXICO': 'UNM', 'IDAHO ST': 'IDST', 'UTAH ST': 'USU',
         'ARIZONA ST': 'ASU', 'WEBER ST': 'WEB', 'OREGON ST': 'ORST', 'TOWSON': 'TOW', 'SANTA CLARA': 'SCU', 'MONTANA ST': 'MTST', 'COLORADO ST': 'CSU', 'NEVADA': 'NEV',
         'ILLINOIS ST': 'ILST', 'STANFORD': 'STAN', 'UCLA': 'UCLA', 'ARIZONA': 'ARIZ', 'MONTANA': 'MONT', 'OREGON': 'ORE', 'USC': 'USC', 'FLORIDA': 'FLA',
         'ARMY': 'ARMY', 'DUKE': 'DUKE', 'GEORGETOWN': 'GTWN', 'RICHMOND': 'RICH', 'BUCKNELL': 'BUCK', 'MARYLAND': 'MD', 'FLORIDA ATLANTIC': 'FAU', 'VERMONT': 'UVM',
         'IONA': 'IONA', 'LAFAYETTE': 'LAF', 'BUTLER': 'BTLR', 'HOWARD': 'HOW', 'YALE': 'YALE', 'AMERICAN': 'AMER', 'CINCINNATI': 'CIN', 'MAINE': 'ME', 'PROVIDENCE': 'PROV',
         'JACKSON ST': 'JKST', 'TEXAS TECH': 'TTU', 'NJIT': 'NJIT', 'DAYTON': 'DAY', 'BELLARMINE': 'BELL', 'VANDERBILT': 'VAN', 'SOUTH FLORIDA': 'USF', 'STETSON': 'STET',
         'CLEMSON': 'CLEM', 'NAVY': 'NAVY', 'GEORGE WASHINGTON': 'GW', 'EAST CAROLINA': 'ECU', 'NORTHEASTERN': 'NE', 'NEW HAMPSHIRE': 'UNH', 'BROWN': 'BRWN',
         'NEW HAVEN': 'NHVN', 'SYRACUSE': 'SYR', 'PRESBYTERIAN': 'PRES', 'TEMPLE': 'TEM', 'MERCYHURST': 'MERC', 'MARQUETTE': 'MARQ', 'LIPSCOMB': 'LIP', 'GEORGIA': 'UGA',
         'LE MOYNE': 'LEM', 'NEBRASKA': 'NEB', 'TEXAS ST': 'TXST', 'SIENA': 'SIE', 'BRYANT': 'BRY', 'WAKE FOREST': 'WAKE', 'SMU': 'SMU', 'OKLAHOMA': 'OU', 'ILLINOIS': 'ILL',
         'BINGHAMTON': 'BING', 'NORTHWESTERN': 'NU', 'FURMAN': 'FUR', 'LEHIGH': 'LEH', 'ST LOUIS': 'SLU', 'ALCORN ST': 'ALCN', 'FLORIDA ST': 'FSU', 'CHICAGO ST': 'CHST',
         'TEXAS': 'TEX', 'TEXAS SOUTHERN': 'TXSO', 'GRAND CANYON': 'GCU', 'INCARNATE WORD': 'UIW', 'OKLAHOMA ST': 'OKST', 'BAYLOR': 'BAY', 'COLGATE': 'COLG',
         'WASHINGTON': 'WASH', 'RADFORD': 'RAD', 'SAN FRANCISCO': 'SF', 'WICHITA ST': 'WICH', 'KANSAS ST': 'KSU', 'WASHINGTON ST W': 'WSU', 'CALIFORNIA': 'CAL', 'WASHINGTON ST': 'WSU', 'XAVIER': 'XAV', 'WOFFORD': 'WOF', 'TENNESSEE': 'TENN', 'IPFW': 'PFW', 'DUQUESNE': 'DUQ', 'HAMPTON': 'HAMP', 'GEORGIA TECH': 'GT', 'MANHATTAN': 'MAN', 'KENTUCKY': 'UK', 'SAM HOUSTON ST': 'SHSU', 'ALABAMA': 'ALA', 'DREXEL': 'DREX', 'VIRGINIA': 'UVA', 'SOUTH DAKOTA ST': 'SDST', 'CLEVELAND ST': 'CLE', 'MISSOURI': 'MIZ', 'CS FULLERTON': 'CSUF', 'SAN DIEGO ST': 'SDSU', 'NORTHERN ARIZONA': 'NAU', 'UNLV': 'UNLV', 'WAGNER': 'WAG', 'BOSTON COLLEGE': 'BC', 'HOLY CROSS': 'HC', 'RHODE ISLAND': 'URI', 'COPPIN ST': 'COPP', 'VIRGINIA TECH': 'VT', 'STETSON': 'STET', 'SOUTH CAROLINA': 'SC', 'NEW ORLEANS': 'NOLA', 'LSU': 'LSU', 'LIPSCOMB': 'LIP', 'IOWA': 'IOWA', 'ALABAMA ST': 'ALST', 'TEXAS AM': 'TA&M', 'ARKANSAS PINE BLUFF': 'UAPB', 'ARKANSAS': 'ARK', 'NORTH FLORIDA': 'UNF', 'CAL BAPTIST': 'CBU'}
ALIAS.update({'CS NORTHRIDGE': 'CSUN', 'WICHITA ST': 'WICH', 'NORTHERN KENTUCKY': 'NKU', 'SOUTH DAKOTA': 'SDAK', 'NORTH DAKOTA ST': 'NDSU', 'ST MARYS CA': 'SMC', 'MD EASTERN SHORE': 'UMES', 'HIGH POINT': 'HPU', 'LONGWOOD': 'LONG', 'ST JOSEPHS': 'JOES', 'SE LOUISIANA': 'SELA', 'AUBURN': 'AUB', 'QUEENS NC': 'QUC', 'LOYOLA MARYMOUNT': 'LMU'})  # Nov 4
ALIAS.update({'WISC GREEN BAY': 'GB', 'MERCER': 'MER', 'VIRGINIA TECH': 'VT', 'HOFSTRA': 'HOF', 'PRINCETON': 'PRIN', 'NORTHERN ILLINOIS': 'NIU', 'TULSA': 'TLSA', 'VMI': 'VMI', 'JACKSONVILLE ST': 'JXST', 'SOUTH ALABAMA': 'USA', 'PENNSYLVANIA': 'PENN', 'CAL POLY SLO': 'CP', 'ARIZONA': 'ARIZ', 'MCNEESE ST': 'MCN', 'NORTH TEXAS': 'UNT', 'NOTRE DAME': 'ND', 'VERMONT': 'UVM', 'FAIRFIELD': 'FAIR', 'ALBANY NY': 'UALB', 'UMASS LOWELL': 'UML', 'MERRIMACK': 'MRMK', 'MD BALTIMORE CO': 'UMBC', 'MARIST': 'MRST', 'DELAWARE ST': 'DSU', 'MAINE': 'ME', 'SACRED HEART': 'SHU', 'STONEHILL': 'STO', 'FORDHAM': 'FOR', 'JACKSONVILLE': 'JAX', 'FLORIDA': 'FLA', 'EAST TEXAS AM': 'ETAM', 'RICE': 'RICE', 'SOUTHERN MISS': 'USM', 'MICHIGAN': 'MICH', 'CENTRAL FLORIDA': 'UCF', 'NORTHWESTERN': 'NU'})  # Nov 5
ALIAS.update({'AUSTIN PEAY': 'APSU', 'KENNESAW ST': 'KENN', 'NC GREENSBORO': 'UNCG', 'DELAWARE': 'DEL', 'STONY BROOK': 'STBK', 'DETROIT': 'DETM', 'ILLINOIS CHICAGO': 'UIC', 'SOUTHERN ILLINOIS': 'SIU', 'WYOMING': 'WYO', 'NO COLORADO': 'UNCO', 'NEBRASKA OMAHA': 'OMA', 'MIDDLE TENN ST': 'MTSU', 'IDAHO': 'IDHO', 'CALIFORNIA BAPTIST': 'CBU', 'PORTLAND': 'PORT', 'UT ARLINGTON': 'UTA', 'TARLETON ST': 'TAR', 'SAN DIEGO': 'USD', 'WEST FLORIDA': 'UWF', 'FLORIDA INTL': 'FIU', 'ARK PINE BLUFF': 'UAPB', 'SOUTH CAROLINA ST': 'SCST', 'RUTGERS': 'RUTG', 'VILLANOVA': 'VILL', 'GEORGE MASON': 'GMU', 'NICHOLLS ST': 'NICH', 'UAB': 'UAB', 'MISSISSIPPI VALLEY ST': 'MVSU', 'SOUTHERN MISS': 'USM'})  # Nov 6
ALIAS.update({'NORTH CAROLINA AANDT': 'NCAT', 'NC WILMINGTON': 'UNCW', 'SAMFORD': 'SAM', 'CAL SANTA BARBARA': 'UCSB', 'NORTHERN IOWA': 'UNI', 'TEXAS SAN ANTONIO': 'UTSA', 'NEW MEXICO ST': 'NMSU', 'IU INDIANAPOLIS': 'IUIN', 'CAL RIVERSIDE': 'UCR', 'EVANSVILLE': 'EVAN', 'PACIFIC': 'PAC', 'BRADLEY': 'BRAD', 'UTAH VALLEY': 'UVU', 'SAN JOSE ST': 'SJSU', 'CAL IRVINE': 'UCI', 'SACRAMENTO ST': 'SAC', 'PORTLAND ST': 'PRST', 'FRESNO ST': 'FRES', 'UC SAN DIEGO': 'UCSD', 'WINTHROP': 'WIN', 'LAMAR': 'LAM'})  # Nov 7
ALIAS.update({'SIU EDWARDSVILLE': 'SIUE', 'PRAIRIE VIEW AM': 'PV', 'UT RIO GRANDE VALLEY': 'RGV', 'MORGAN ST': 'MORG', 'HOUSTON CHRISTIAN': 'HCU', 'MURRAY ST': 'MUR', 'WESTERN ILLINOIS': 'WIU', 'NIAGARA': 'NIA', 'LIPSCOMB': 'LIP', 'NORTHWESTERN ST': 'NWST'})  # Nov 7 update run
ALIAS.update({'APPALACHIAN ST': 'APP', 'GRAMBLING': 'GRAM', 'ALABAMA AM': 'AAMU'})  # Nov 9
ALIAS.update({'BOISE ST': 'BOIS', 'CS BAKERSFIELD': 'CSUB', 'DRAKE': 'DRKE', 'NORFOLK ST': 'NORF', 'WILLIAM AND MARY': 'W&M', 'UTEP': 'UTEP', 'SACRED HEART': 'SHU', 'BRYANT': 'BRY', 'ALBANY NY': 'UALB'})  # Nov 8
ALIAS.update({'HARVARD': 'HARV', 'EASTERN KENTUCKY': 'EKU', 'GEORGIA TECH': 'GT', 'QUEENS NC': 'QUC', 'PRAIRIE VIEW AANDM': 'PV'})  # Nov 10
ALIAS.update({'COLL OF CHARLESTON': 'COFC', 'TEMPLE': 'TEM', 'PEPPERDINE': 'PEPP', 'SAM HOUSTON': 'SHSU', 'STEPHEN F AUSTIN': 'SFA', 'STEPHEN F. AUSTIN': 'SFA', 'ABILENE CHRISTIAN': 'ACU'})  # Nov 11
def espn():
    p = DATA/f'espn_today_{LG.lower()}.txt'
    rows = [l.split('|') for l in p.read_text().strip().splitlines()[1:]]
    DL = dt.strftime('%a ') + f"{dt.month}/{dt.day}"
    return [dict(id=r[0], day=DL, time=r[1].replace('p', ' PM').replace('a', ' AM').replace(' PM', ':00 PM') if ':' not in r[1] else r[1].replace('p', ' PM').replace('a', ' AM'),
                 away=r[2], home=r[3], an=r[4], hn=r[5], ac=r[6], hc=r[7], cg=r[8] == '1', nu=r[9] == '1', ar=r[10], hr=r[11], state=r[12]) for r in rows]
SLATE = espn()
BYAB = {}
for g in SLATE: BYAB[g['away']] = g; BYAB[g['home']] = g

# ---------------- Action Network splits (spread view): away|home|away open spread|bets a|bets h|money a|money h
AN_ALIAS = {'N.J.I.T.': 'NJIT', 'W. Carolina': 'WCU', "St. Mary's": 'MSM', 'Charleston So': 'CHSO', 'S. Florida': 'USF', 'E. Illinois': 'EIU', 'W. Michigan': 'WMU',
            'GA Southern': 'GASO', 'USC Upstate': 'UPST', 'E. Carolina': 'ECU', 'Ark-Little Rock': 'LR', 'E. Michigan': 'EMU', 'Coastal Car': 'CCU', 'Miami (OH)': 'M-OH',
            'UMASS': 'MASS', 'Long Island': 'LIU', 'St. Thomas': 'STMN', "St. Peter's": 'SPU', 'W. Kentucky': 'WKU', 'Tenn Tech': 'TNTC', 'LA Tech': 'LT', 'NC Central': 'NCCU',
            'G Washington': 'GW', 'C. Michigan': 'CMU', 'Southern Indiana': 'USI', 'SE Missouri': 'SEMO', 'MD-E Shore': 'UMES', 'Fairleigh': 'FDU', 'E TA&M': 'ETAM',
            'Bryant U': 'BRY', 'Southern U': 'SOU', 'TN-Martin': 'UTM', 'UMKC': 'KC', 'Louisiana': 'UL', 'W. Illinois': 'WIU', 'B-Cookman': 'BCU', 'Texas A&M-CC': 'AMCC',
            'Citadel': 'CIT', 'Loyola (IL)': 'LUC', 'S. Alabama': 'USA', 'C. Arkansas': 'CARK', 'Ole Miss': 'MISS', 'Ab Christian': 'ACU', 'LBSU': 'LBSU', 'OK State': 'OKST',
            'NW State': 'NWST', 'E. Washington': 'EWU', 'E Tennessee St': 'ETSU', 'Seattle': 'SEA', 'Hawaii': 'HAW', 'McNeese St': 'MCN', 'Miami (FL)': 'MIA',
            'Loyola (MD)': 'L-MD', 'Central Conn': 'CCSU', "St. John's": 'SJU', 'Youngstown St': 'YSU', 'St. Bonaventure': 'SBU', 'Boston U': 'BU', 'UNC Asheville': 'UNCA',
            'American U': 'AMER', 'UNC': 'UNC', 'Indiana St': 'INST', 'Iowa State': 'ISU', 'Michigan St': 'MSU', 'Wright State': 'WRST', 'Morehead St': 'MORE',
            'Mississippi St': 'MSST', 'Arkansas St': 'ARST', 'Texas St': 'TXST', 'Florida St': 'FSU', 'Alcorn State': 'ALCN', 'Chicago St': 'CHST', 'Utah Tech': 'UTU',
            'Ohio State': 'OSU', 'Washington St': 'WSU', 'Weber State': 'WEB', 'Oregon St': 'ORST', 'Idaho State': 'IDST', 'Utah State': 'USU', 'Montana St': 'MTST',
            'Colorado St': 'CSU', 'Illinois St': 'ILST', "Saint Mary's": 'SMC', 'Arizona St': 'ASU', 'Georgia State': 'GAST', 'Jackson St': 'JKST', 'Kent State': 'KENT',
            'Ball State': 'BALL', 'Saint Louis': 'SLU', 'Grand Canyon': 'GCU', 'Texas Southern': 'TXSO', 'Incarnate Word': 'UIW', 'North Dakota': 'UND', 'North Alabama': 'UNA',
            'UC Davis': 'UCD', 'Robert Morris': 'RMU', 'Santa Clara': 'SCU', 'San Francisco': 'SF', 'Le Moyne': 'LEM', 'New Haven': 'NHVN', 'West Georgia': 'WGA',
            'Florida A&M': 'FAMU', 'La Salle': 'LAS', 'Gardner-Webb': 'GWEB', 'Bowling Green': 'BGSU', 'Old Dominion': 'ODU', 'New Hampshire': 'UNH', 'Air Force': 'AF',
            'Lindenwood': 'LIN', 'Fordham': 'FOR', 'West Virginia': 'WVU', 'Texas Tech': 'TTU', 'Penn State': 'PSU', 'NC State': 'NCSU', 'Seton Hall': 'HALL',
            'Wake Forest': 'WAKE', 'Oral Roberts': 'ORU', 'Oklahoma': 'OU', 'Wisconsin': 'WIS', 'Belmont': 'BEL', 'Creighton': 'CREI', 'Valparaiso': 'VAL', 'Akron': 'AKR',
            'Northwestern': 'NU', 'Binghamton': 'BING', 'Siena': 'SIE', 'Lehigh': 'LEH', 'Davidson': 'DAV', 'Colorado': 'COLO', 'Minnesota': 'MINN', 'Texas': 'TEX',
            'UConn': 'CONN', 'New Mexico': 'UNM', 'Utah': 'UTAH', 'Chattanooga': 'UTC', 'Louisville': 'LOU', 'Houston': 'HOU', 'Baylor': 'BAY', 'Stanford': 'STAN',
            'Radford': 'RAD', 'Colgate': 'COLG', 'Washington': 'WASH', 'Towson': 'TOW', 'Nevada': 'NEV', 'UCLA': 'UCLA', 'Arizona': 'ARIZ', 'Montana': 'MONT', 'Oregon': 'ORE',
            'Milwaukee': 'MILW', 'USC': 'USC', 'UAB': 'UAB', 'Oakland': 'OAK', 'Michigan': 'MICH', 'Florida': 'FLA', 'Pepperdine': 'PEPP', 'Cornell': 'COR', 'Army': 'ARMY',
            'Duke': 'DUKE', 'Georgetown': 'GTWN', 'Monmouth': 'MONM', 'Temple': 'TEM', 'Dayton': 'DAY', 'Maine': 'ME', 'Providence': 'PROV', 'Bellarmine': 'BELL',
            'Vanderbilt': 'VAN', 'Howard': 'HOW', 'Yale': 'YALE', 'Niagara': 'NIA', 'Northeastern': 'NE', 'Rider': 'RID', 'Pittsburgh': 'PITT', 'Richmond': 'RICH',
            'Cincinnati': 'CIN', 'Lafayette': 'LAF', 'Butler': 'BTLR', 'Xavier': 'XAV', 'Syracuse': 'SYR', 'Stetson': 'STET', 'Clemson': 'CLEM', 'Charlotte': 'CLT',
            'Buffalo': 'BUF', 'Marshall': 'MRSH', 'Memphis': 'MEM', 'Bucknell': 'BUCK', 'Maryland': 'MD', 'FGCU': 'FGCU', 'UCF': 'UCF', 'Indiana': 'IU', 'VCU': 'VCU',
            'JMU': 'JMU', 'Dartmouth': 'DART', 'Marist': 'MRST', 'Vermont': 'UVM', 'Iona': 'IONA', 'Elon': 'ELON', 'Columbia': 'COLU', 'Brown': 'BRWN', 'Troy': 'TROY',
            'FAU': 'FAU', 'Quinnipiac': 'QUIN', 'Presbyterian': 'PRES', 'Campbell': 'CAM', 'Canisius': 'CAN', 'Mercyhurst': 'MERC', 'Marquette': 'MARQ', 'Denver': 'DEN',
            'Georgia': 'UGA', 'Navy': 'NAVY', 'Purdue': 'PUR', 'Gonzaga': 'GONZ', 'UL Monroe': 'ULM', 'Lipscomb': 'LIP', 'Toledo': 'TOL', 'Illinois': 'ILL', 'SMU': 'SMU',
            'Kansas': 'KU', 'TCU': 'TCU', 'DePaul': 'DEP', 'Tulane': 'TULN', 'Furman': 'FUR', 'Ohio': 'OHIO', 'Nebraska': 'NEB', 'Mississippi St': 'MSST', 'Iowa St': 'ISU', 'Wofford': 'WOF', 'Tennessee': 'TENN', 'G Tech': 'GT', 'Hampton': 'HAMP', 'Wagner': 'WAG', 'Boston Col': 'BC', 'Manhattan': 'MAN', 'Kentucky': 'UK', 'Holy Cross': 'HC', 'Rhode Island': 'URI', 'Coppin St': 'COPP', 'VA Tech': 'VT', 'Stetson': 'STET', 'S. Carolina': 'SC', 'IPFW': 'PFW', 'Duquesne': 'DUQ', 'Drexel': 'DREX', 'Virginia': 'UVA', 'Sam Houston': 'SHSU', 'Alabama': 'ALA', 'New Orleans': 'NOLA', 'LSU': 'LSU', 'SD State': 'SDST', 'K State': 'KSU', 'Cleveland St': 'CLE', 'Missouri': 'MIZ', 'Lipscomb': 'LIP', 'Iowa': 'IOWA', 'Alabama St': 'ALST', 'Texas A&M': 'TA&M', 'AR-Pine Bluff': 'UAPB', 'Arkansas': 'ARK', 'N. Arizona': 'NAU', 'UNLV': 'UNLV', 'CS Fullerton': 'CSUF', 'San Diego State': 'SDSU', 'North Florida': 'UNF', 'Cal Baptist': 'CBU'}
AN_ALIAS.update({'Butler': 'BTLR', 'Longwood': 'LONG', "Saint Joe's": 'JOES', 'MD-E Shore': 'UMES', 'High Point': 'HPU', 'CS Northridge': 'CSUN', 'Wichita State': 'WICH', 'SE Louisiana': 'SELA', 'Auburn': 'AUB', 'Radford': 'RAD', 'California': 'CAL', 'NDSU': 'NDSU', "Saint Mary's": 'SMC', 'Milwaukee': 'MILW', 'Santa Clara': 'SCU', 'Queens': 'QUC', 'Loyola Marymount': 'LMU', 'Fairleigh': 'FDU'})  # Nov 4
AN_ALIAS.update({'Penn': 'PENN', 'Illinois': 'ILL', 'Cal Poly': 'CP', 'Arizona': 'ARIZ', 'Towson': 'TOW', 'Utah': 'UTAH', 'VMI': 'VMI', 'SMU': 'SMU', 'Le Moyne': 'LEM', 'Creighton': 'CREI', 'Rice': 'RICE', 'N. Illinois': 'NIU', 'Tulsa': 'TLSA', 'Toledo': 'TOL', 'Michigan St': 'MSU', 'West Georgia': 'WGA', 'Loyola (IL)': 'LUC', 'Jax State': 'JXST', 'S. Alabama': 'USA', 'B-Cookman': 'BCU', 'Texas Tech': 'TTU', 'Coastal Car': 'CCU', 'Duke': 'DUKE', 'Gardner-Webb': 'GWEB', 'Texas': 'TEX', 'Jacksonville': 'JAX', 'Florida': 'FLA', 'NW State': 'NWST', 'Mississippi St': 'MSST', 'Bryant U': 'BRY', 'Quinnipiac': 'QUIN', 'UMass Lowell': 'UML', 'Merrimack': 'MRMK', 'Mercyhurst': 'MERC', 'Notre Dame': 'ND', 'Hofstra': 'HOF', 'Princeton': 'PRIN', 'Central Conn': 'CCSU', 'Syracuse': 'SYR', 'Albany': 'UALB', 'Manhattan': 'MAN', 'N.J.I.T.': 'NJIT', 'Iona': 'IONA', 'Delaware St': 'DSU', 'Navy': 'NAVY', 'New Hampshire': 'UNH', 'Rider': 'RID', 'Buffalo': 'BUF', 'Pittsburgh': 'PITT', 'Green Bay': 'GB', 'Cincinnati': 'CIN', 'Mercer': 'MER', 'VA Tech': 'VT', 'Long Island': 'LIU', 'Seton Hall': 'HALL', 'Bellarmine': 'BELL', 'Indiana': 'IU', 'Chattanooga': 'UTC', 'Penn State': 'PSU', 'Wake Forest': 'WAKE', 'Vanderbilt': 'VAN', 'McNeese St': 'MCN', 'North Texas': 'UNT', 'E TA&M': 'ETAM'})  # Nov 5
AN_ALIAS.update({'West Florida': 'UWF', 'FIU': 'FIU', 'SC State': 'SCST', 'Villanova': 'VILL', 'George Mason': 'GMU', 'UNC Greensboro': 'UNCG', 'Austin Peay': 'APSU', 'Kennesaw St': 'KENN', 'Rutgers': 'RUTG', 'Delaware': 'DEL', 'Nicholls St': 'NICH', 'Stony Brook': 'STBK', 'N Kentucky': 'NKU', 'Southern Miss': 'USM', 'Detroit': 'DETM', 'MS Valley St': 'MVSU', 'UIC': 'UIC', 'Wyoming': 'WYO', 'S. Illinois': 'SIU', 'Omaha': 'OMA', 'Idaho': 'IDHO', 'N. Colorado': 'UNCO', 'Middle Tenn': 'MTSU', 'Tarleton St': 'TAR', 'San Diego': 'USD', 'Portland': 'PORT', 'UT-Arlington': 'UTA', 'UMASS': 'MASS', 'Boston Col': 'BC', 'Northeastern': 'NE', 'Virginia': 'UVA'})  # Nov 6
AN_ALIAS.update({'Winthrop': 'WIN', 'NC A&T': 'NCAT', 'UNC Wilmington': 'UNCW', 'Lamar': 'LAM', 'South Dakota': 'SDAK', 'UCSB': 'UCSB', 'Samford': 'SAM', 'IUIN': 'IUIN', 'SIU-Edwardsville': 'SIUE', 'N. Iowa': 'UNI', 'N. Mexico St': 'NMSU', 'UTSA': 'UTSA', 'Prairie View': 'PV', 'UT Grande Valley': 'RGV', 'Morgan State': 'MORG', 'Hou Christian': 'HCU', 'UC Riverside': 'UCR', 'Evansville': 'EVAN', 'Murray State': 'MUR', 'Pacific': 'PAC', 'Bradley': 'BRAD', 'Utah Valley': 'UVU', 'Fresno State': 'FRES', 'UCSD': 'UCSD', 'Portland State': 'PRST', 'Sac State': 'SAC', 'San Jose St': 'SJSU', 'UC Irvine': 'UCI', 'North Dakota': 'UND', 'Toledo': 'TOL', 'Marshall': 'MRSH', 'Lafayette': 'LAF', 'Seattle': 'SEA', 'Weber State': 'WEB', 'Santa Clara': 'SCU'})  # Nov 7
AN_ALIAS.update({'Boise State': 'BOIS', 'Drake': 'DRKE', 'CS Bakersfield': 'CSUB', 'Norfolk State': 'NORF', 'William & Mary': 'W&M', 'UTEP': 'UTEP', 'Sacred Heart': 'SHU', 'Fairfield': 'FAIR', 'Albany': 'UALB', 'Iona': 'IONA', 'St. Thomas': 'STMN', 'Hawaii': 'HAW', 'UT-Arlington': 'UTA', 'California': 'CAL', 'Houston': 'HOU', 'Wichita State': 'WICH', 'USC': 'USC', 'Pittsburgh': 'PITT', 'Penn State': 'PSU', 'Incarnate Word': 'UIW', 'NDSU': 'NDSU', 'Richmond': 'RICH', 'Temple': 'TEM', "Saint Mary's": 'SMC', 'Nevada': 'NEV', "St. Peter's": 'SPU', 'N.J.I.T.': 'NJIT', 'Rider': 'RID', 'Binghamton': 'BING', 'Southern U': 'SOU', 'W. Kentucky': 'WKU', 'Tenn Tech': 'TNTC', 'Idaho State': 'IDST', 'Air Force': 'AF', 'Brown': 'BRWN', 'Lehigh': 'LEH', 'Campbell': 'CAM', 'W. Michigan': 'WMU', 'Merrimack': 'MRMK', 'Butler': 'BTLR', 'Green Bay': 'GB', 'Central Conn': 'CCSU', 'Dartmouth': 'DART', 'Quinnipiac': 'QUIN', 'Vermont': 'UVM', 'SE Missouri': 'SEMO', 'S. Carolina': 'SC', 'Bryant U': 'BRY', 'Marist': 'MRST', 'UMass Lowell': 'UML', 'Manhattan': 'MAN', 'Maine': 'ME', 'New Hampshire': 'UNH', 'Princeton': 'PRIN', 'Siena': 'SIE', 'Arkansas': 'ARK', 'Virginia': 'UVA', "St. John's": 'SJU'})  # Nov 8
AN_ALIAS.update({'Harvard': 'HARV', 'E. Kentucky': 'EKU'})  # Nov 10
AN_ALIAS.update({'Charleston': 'COFC', 'Temple': 'TEM'})  # Nov 11
AN_ALIAS.update({'Southern Utah': 'SUU'})  # Nov 12
AN_ALIAS.update({'Colgate': 'COLG', 'American U': 'AMER', 'Louisville': 'LOU', 'Memphis': 'MEM', 'Niagara': 'NIA', 'Iowa State': 'ISU', 'Nebraska': 'NEB', 'Boston U': 'BU', 'Georgia State': 'GAST', 'Rhode Island': 'URI', 'Washington': 'WASH', 'Utah': 'UTAH', 'Holy Cross': 'HC', 'Michigan': 'MICH', 'La Salle': 'LAS', 'Missouri': 'MIZ', 'Marquette': 'MARQ', 'Baylor': 'BAY', 'Iowa': 'IOWA', 'Saint Louis': 'SLU', 'IPFW': 'PFW', 'E. Illinois': 'EIU', 'Cleveland St': 'CLE', 'Alabama A&M': 'AAMU', 'Chicago St': 'CHST', 'San Diego State': 'SDSU', 'Southern Indiana': 'USI', 'New Haven': 'NHVN', 'Pepperdine': 'PEPP', 'Oregon': 'ORE', 'Canisius': 'CAN', 'Montana St': 'MTST', 'AR-Pine Bluff': 'UAPB', 'Wisconsin': 'WIS', 'Florida A&M': 'FAMU', 'UTEP': 'UTEP', 'Texas St': 'TXST', 'Alabama St': 'ALST', 'Coastal Car': 'CCU', 'William & Mary': 'W&M', 'Charleston': 'COFC'})  # Nov 15
AN = {}
p = DATA/f'an_{LG.lower()}.txt'
if p.exists():
    for l in p.read_text().strip().splitlines():
        f = l.split('|'); a, h = AN_ALIAS.get(f[0], f[0]), AN_ALIAS.get(f[1], f[1])
        num = lambda x: int(x.rstrip('%')) if x and x.rstrip('%').isdigit() else None
        AN[frozenset((a, h))] = dict(a=a, h=h, open_a=float(f[2]) if re.match(r'^[+-]?[\d.]+$', f[2]) else None, ba=num(f[3]), bh=num(f[4]), ma=num(f[5]), mh=num(f[6]))

# ---------------- ratings (last season final, blended with this season by games / (games + 8))
RAT = {}
p = DATA/f'ratings_{LG.lower()}_2025-26.txt'
if p.exists():
    for tok in p.read_text().strip().split(';'):
        t, r, pc = tok.split(',')[:3]
        RAT[t] = (float(r) if r not in ('undefined', '') else None, float(pc) if pc not in ('NaN', '') else None)
import eff as EF
EPRI, EPLG = EF.load_prior(LG)
ECUR, ECLG, ECNT = {}, None, {}
_bp = D/'season'/f'box_{LG}.txt'
if _bp.exists():
    _gs = []
    for _ln in _bp.read_text().strip().splitlines():
        if not _ln.strip(): continue
        _r = json.loads(_ln)
        if _r[8] and _r[12]: _gs.append(dict(h=_r[2], a=_r[3], nu=_r[4] == 1, hs=_r[6], as_=_r[7], poss=(EF.poss(*_r[8:12]) + EF.poss(*_r[12:16]))/2))
    ECUR, ECLG, ECNT = EF.solve(_gs)
LASTG = {}
if _bp.exists():
    for _ln in _bp.read_text().strip().splitlines():
        if not _ln.strip(): continue
        _r = json.loads(_ln)
        for _t in (_r[2], _r[3]): LASTG[_t] = max(LASTG.get(_t, ''), _r[1])
def rest_days(t):
    d = LASTG.get(t)
    if not d or d >= DATE.replace('-', ''): return None
    return (dt - datetime.date(int(d[:4]), int(d[4:6]), int(d[6:]))).days
THIS = {}   # this season to date (team -> (games, rating, pace)), from season/games file; empty on opening day
def rating(t):
    last = RAT.get(t, (None, None)); n, r, pc = THIS.get(t, (0, 0.0, None)); w = n / (n + 8)
    if last[0] is None and not n: return None, None
    lr = last[0] if last[0] is not None else 0.0
    return w * r + (1 - w) * lr, (pc if pc and n else last[1])

# ---------------- ESPN board (core odds, DraftKings first): open and current/closing lines plus live state and scores
def _t(x):
    x = x.strip()
    if x.endswith('PM') or x.endswith('AM'): x = x[:-2] + (':00' if ':' not in x[:-2] else '') + ' ' + x[-2:]
    else: x = x.replace('p', ' PM').replace('a', ' AM')
    return x
EB = {}
p = DATA/'espn_board.txt'
if p.exists():
    for l in p.read_text().strip().splitlines():
        f = l.split('|')
        if f[0] != LG: continue
        nf = lambda x: float(x) if x not in ('', 'null', 'undefined') else None
        ml = lambda x: int(float(x)) if x not in ('', 'null', 'undefined') and abs(float(x)) <= 5000 else None
        EB[f[1]] = dict(id=f[1], time=_t(f[2]), away=f[3], home=f[4], ac=f[5], hc=f[6], cg=f[7] == '1', nu=f[8] == '1', ar=f[9], hr=f[10], state=f[11],
                        as_=int(f[12] or 0), hs=int(f[13] or 0), o=nf(f[14]), c=nf(f[15]), to=nf(f[16]), tc=nf(f[17]), mlh=ml(f[18]), mla=ml(f[19]),
                        book=(f[21] if len(f) > 21 else ''), sph=(ml(f[22]) if len(f) > 22 else None), spa=(ml(f[23]) if len(f) > 23 else None),
                        op=(ml(f[24]) if len(f) > 24 else None), up=(ml(f[25]) if len(f) > 25 else None))
DL = dt.strftime('%a ') + f"{dt.month}/{dt.day}"
# ---------------- The Odds API opening lines (cfb-card repo odds/read.py), second source when the Action Network or DraftKings opener is missing (B5, Nov 10)
def _nm(x):
    x = x.lower().replace('&', 'and').replace("'", '').replace('.', '').replace('-', ' ').replace('ʻ', '')
    x = re.sub(r'\bstate\b', 'st', x); x = re.sub(r'\bsaint\b', 'st', x)
    return re.sub(r'\s+', ' ', x).strip()
OAPI = {}
_op = DATA/'raw'/f"odds_ncaam_{DATE.replace('-', '')}.json"
_tp = DATA/'raw'/f"teaminfo_m_{DATE.replace('-', '')}.txt"
if LG == 'M' and _op.exists() and _tp.exists():
    _ev = list(json.loads(_op.read_text()).values())
    for _l in _tp.read_text().strip().splitlines():
        _gid, _a, _h = _l.split('|')[:3]; _a, _h = _nm(_a.split('^')[0]), _nm(_h.split('^')[0])
        for _x in _ev:
            xa, xh = _nm(_x['away']), _nm(_x['home'])
            def _m(p, q): return p == q or p.startswith(q) or q.startswith(p)
            def _mm(a, h, xa, xh): return _m(a, xa) and _m(h, xh) or (a.split()[-1] == xa.split()[-1] and h.split()[-1] == xh.split()[-1] and (a.split()[0] == xa.split()[0] or h.split()[0] == xh.split()[0]))
            if _mm(_a, _h, xa, xh): OAPI[_gid] = dict(_x.get('open') or {}, flip=False); break
            if _mm(_a, _h, xh, xa): OAPI[_gid] = dict(_x.get('open') or {}, flip=True); break
def odds_open(gid):
    """(home spread open, total open) from The Odds API median open, oriented to the ESPN home team."""
    x = OAPI.get(gid)
    if not x: return None, None
    sp = x.get('spread_home'); sp = (-sp if x['flip'] else sp) if sp is not None else None
    return sp, x.get('total')

def make(g, src, sp, tot, mlh, mla, o1, c1, t1o, t1c, spp_h=-110, spp_a=-110, o_price=-110, u_price=-110, menu=''):
    an = AN.get(frozenset((g['away'], g['home'])))
    tix_a = tix_h = None
    if src == 'texas222' and an and an['open_a'] is not None:
        tix_a = an['ba'] if an['a'] == g['away'] else an['bh']; tix_h = an['bh'] if an['a'] == g['away'] else an['ba']
    e = EB.get(g['id'])
    xo, xto = odds_open(g['id']); open_src = []
    if o1 is None and xo is not None: o1 = xo; open_src.append('spread')
    if (t1o is None and (not e or e.get('to') is None)) and xto is not None: t1o = xto; open_src.append('total')
    rh, ph = rating(g['home']); ra, pa = rating(g['away'])
    proj = (rh - ra + (0 if g['nu'] else R.HCA)) if rh is not None and ra is not None else None
    ptot = (ph + pa) / 2 if ph and pa else None
    etot = emar = None
    if EPRI and (g['home'] in EPRI or g['home'] in ECUR) and (g['away'] in EPRI or g['away'] in ECUR):
        emar, etot, _ph, _pa = EF.project(g['home'], g['away'], g['nu'], EPRI, EPLG, ECUR, ECLG, ECNT); ptot = etot
    rec = dict(g, day=DL, month=dt.month, etot=etot, emar=emar, menu=menu, posted=sp is not None, src=src, sp=sp, tot=tot, mlh=mlh, mla=mla, o1=o1, c1=c1, t1o=t1o, t1c=t1c,
               o2=(e['o'] if e and src == 'texas222' else None), c2=(e['c'] if e and src == 'texas222' else None),
               t2o=(e['to'] if e and src == 'texas222' else None), t2c=(e['tc'] if e and src == 'texas222' else None),
               neutral=g['nu'], tix_away=tix_a, tix_home=tix_h, sp_price_home=spp_h or -110, sp_price_away=spp_a or -110, o_price=o_price or -110, u_price=u_price or -110,
               proj=proj, ptot=ptot, an=an if src == 'texas222' else None, aconf=CONF.get(g['ac'], 'Other'), hconf=CONF.get(g['hc'], 'Other'),
               open_src=('The Odds API ' + ' and '.join(open_src)) if open_src else None, state=(e['state'] if e else g['state']), final=(f"{g['away']} {e['as_']}, {g['home']} {e['hs']}" if e and e['state'] == 'f' else ''), fin=e if e and e['state'] == 'f' else None)
    S = R.signals(rec, dict(proj=proj, rest_h=rest_days(g['home']), rest_a=rest_days(g['away']))); rec['S'] = S
    rec['cands'] = R.candidates(rec, S, LIVE) if rec['posted'] and rec.get('state', 'p') == 'p' else []   # B84: never pick a started game
    return rec

# ---------------- game list = the official ESPN Division I schedule (Trina, Nov 3, 2026). Line for each game:
# texas222 when it posts one; otherwise DraftKings (ESPN core odds); otherwise no line (listed, No pick).
# Nov 2 only: ESPN board lines for games already started (Trina's opening day rule).
T222, unmatched = {}, []
for b in BOARD:
    ka, kh = (b['ta'] if b['ta'] in BYAB else ALIAS.get(norm(b['ta']))), (b['th'] if b['th'] in BYAB else ALIAS.get(norm(b['th'])))  # Nov 12: Odds API files carry ESPN codes
    g = BYAB.get(ka) if ka else None
    if not g or kh not in (g['away'], g['home']): unmatched.append(f"{b['ta']} / {b['th']}"); continue
    T222[g['id']] = (b, g['away'] != ka)
SL = {g['id']: g for g in SLATE}
games = []
for e in sorted(EB.values(), key=lambda x: x['id']):
    g = SL.get(e['id']) or dict(e, an='', hn='')
    g = dict(g, state=e['state'])
    started = e['state'] in ('i', 'f')
    t = T222.get(e['id'])
    if t and t[0]['posted'] and not (DATE == '2026-11-02' and started):
        b, flip = t
        hs = b['sp_a'] if flip else b['sp_h']; ml_h = b['ml_a'] if flip else b['ml_h']; ml_a = b['ml_h'] if flip else b['ml_a']
        spp_h = b['spp_a'] if flip else b['spp_h']; spp_a = b['spp_h'] if flip else b['spp_a']
        an = AN.get(frozenset((g['away'], g['home']))); o1 = None
        if an and an['open_a'] is not None: o1 = -(an['open_a'] if an['a'] == g['away'] else -an['open_a'])
        games.append(make(g, 'texas222', hs, b['tot'], ml_h, ml_a, o1, hs, None, b['tot'], spp_h, spp_a, b['o_price'], b['u_price'], b['menu']))
    elif e['c'] is not None and e['tc'] is not None:
        src = 'ESPN' if DATE == '2026-11-02' else 'DraftKings'
        games.append(make(g, src, e['c'], e['tc'], e['mlh'], e['mla'], e['o'], e['c'], e['to'], e['tc'], e.get('sph') or -110, e.get('spa') or -110, e.get('op') or -110, e.get('up') or -110))
        games[-1]['book'] = e.get('book') or 'DraftKings'   # B84: the board row's real source (Odds API median or ESPN's DraftKings line)
    else:
        games.append(make(g, 'none', None, None, None, None, None, None, None, None))

def grade_now(g, c):
    if not g.get('fin'): return 'pending'
    x = dict(hs=g['fin']['hs'], as_=g['fin']['as_'], sp=g['sp'], tot=g['tot']); r = R.grade(c, x)
    return 'win' if r > 0 else ('loss' if r < 0 else 'push')

# one side pick per game (spread first on a tie, as on the NBA card), one total
def pick_for(rec):
    side = [c for c in rec['cands'] if c['market'] != 'Total']; tot = [c for c in rec['cands'] if c['market'] == 'Total']
    order = {'SPREAD_MOVE_1': 0, 'SPREAD_MOVE_05': 0.5, 'ROAD1DAY_FADE': 1, 'EFF_SPREAD': 2, 'MODEL_EDGE': 3, 'FAV_ML_3': 4, 'FAV_ML_2': 4.5, 'DOG_ML_MOVE': 5, 'DOG_ML_1': 5.5, 'EARLY_UNDER_OPEN': 6, 'EARLY_OVER_OPEN': 7, 'EFF_OVER': 8, 'UNDER_DROP_BAND': 9, 'UNDER_DROP_2': 9.3, 'UNDER_DROP_ANY': 9.6, 'NEUTRAL_UNDER': 10, 'OVER_2': 11, 'OVER_ANY': 11.5}
    side.sort(key=lambda c: (-(STATE['rules'][c['rule']].get('season', {}) or {}).get('u', 0), order.get(c['rule'], 9)))
    tot.sort(key=lambda c: (-(STATE['rules'][c['rule']].get('season', {}) or {}).get('u', 0), order.get(c['rule'], 12)))
    return (side[0] if side else None), (tot[0] if tot else None)
for g in games:
    g['side'], g['total'] = pick_for(g)
    def label(c):
        if not c: return None
        if c['market'] == 'Total': return f"{'Under' if c['side']=='under' else 'Over'} {g['tot']:g}"
        team = g['home'] if c['side'] == 'home' else g['away']
        if c['market'] == 'Moneyline': return f"{team} ML"
        spv = g['sp'] if c['side'] == 'home' else -g['sp']; return f"{team} {spv:+g}"
    g['side_lbl'], g['tot_lbl'] = label(g['side']), label(g['total'])
PICKED = [g for g in games if g['side'] or g['total']]

# ---------------- HTML pieces
def LSRC(g):   # B84 (Nov 14): label the line by its real source
    if g['src'] == 'texas222' or 'Odds API' in str(g.get('book', '')): return 'The Odds API median of books'
    if g['src'] == 'DraftKings': return f"{g.get('book') or 'DraftKings'} (ESPN scoreboard)"
    return 'ESPN board (game started before the card ran)'
def fmt(x): return '·' if x is None else (f'{x:+d}' if isinstance(x, int) else f'{x:+g}')
def pct(x): return '·' if x is None else f'{100*x:.1f}%'
RULENAME = {k: v['name'] for k, v in R.RULES.items()}
def rule_line(rid):
    s = STATE['rules'][rid]; b = s.get('backtest', {})
    return f"{RULENAME[rid]} ({s['variant']}): {'on' if s['on'] else 'off'} · backtest {b.get('w',0)}-{b.get('l',0)}, {b.get('u',0):+.1f}u"

def pick_cell(g, c, lbl):
    if not c: return "<span class='tag t-np'>No pick</span>"
    res = grade_now(g, c) if g.get('fin') else ''
    rt = {'win': "<span class='tag t-a'>Win</span>", 'loss': "<span class='tag t-c'>Loss</span>", 'push': "<span class='tag t-d'>Push</span>"}.get(res, '')
    src = '' if LSRC(g).startswith('The Odds API') else (" <span class='tag t-d'>DraftKings line</span>" if g['src'] == 'DraftKings' else " <span class='tag t-d'>ESPN line</span>")
    return f"<b>{esc(lbl)}</b> {fmt(c['price'])} <span class='tag t-rule'>{esc(RULENAME[c['rule']])}</span>{src} {rt}"

chips = sorted({g['hconf'] for g in games} | {g['aconf'] for g in games})
chip_html = "<div class='chips' id='chips'><button type='button' class='chip on' data-c=''>All</button>" + ''.join(f"<button type='button' class='chip' data-c='{esc(c)}'>{esc(c)}</button>" for c in chips) + "</div>"

def game_row(g):
    a, h = g['away'], g['home']; an = g['an'] or {}
    tip = g['day'] + ' · ' + g['time'] + (' · in progress' if g['state'] == 'i' else (' · final' if g['state'] == 'f' else ''))
    rk = lambda r: f"#{r} " if r else ''
    lines = (f"{h} {fmt(g['sp'])} · total {g['tot']:g} · ML {fmt(g['mla'])} / {fmt(g['mlh'])}" if g['posted'] else 'No line posted yet at The Odds API books or DraftKings')
    proj = f"{h} by {g['proj']:+.1f}".replace('by +', 'by ').replace('by -', 'trails by ') if g['proj'] is not None else 'no rating (no lined games last season)'
    edge = (g['proj'] + g['sp']) if g['proj'] is not None and g['sp'] is not None else None
    an_open = f"{h} {fmt(g['o1'])}" if g['o1'] is not None else '·'
    tix = f"{a} {an.get('ba') if an.get('a')==a else an.get('bh')}% · {h} {an.get('bh') if an.get('a')==a else an.get('ba')}%" if an else '·'
    S = g['S']
    ptot_txt = '·' if not g['ptot'] else (f"{g['ptot']:.1f} (efficiency model)" + (f" · open {g['t2o'] if g.get('t2o') is not None else g.get('t1o')}" if (g.get('t2o') is not None or g.get('t1o') is not None) else '') if g.get('etot') else f"{g['ptot']:.0f} (last season scoring proxy)")
    why = []
    if not g['posted']: why.append('No line yet, so no rule can fire.')
    else:
        live = [r for r, s in STATE['rules'].items() if s['on']]
        why.append('No live rule fits.' if live else 'No rule is live for this card (none passed the backtest).')
    body = (f"<table class='kv'><tbody>"
            f"<tr><td>{ {'texas222': 'Odds API median', 'DraftKings': 'DraftKings', 'none': 'Line'}.get(g['src'], 'ESPN board') }</td><td>{esc(lines)}{ {'texas222': '', 'DraftKings': ' (The Odds API books have not posted this game)', 'none': ''}.get(g['src'], ' (game started before the card ran, or not on texas222)') }</td></tr>"
            f"<tr><td>{'Action Network open' if g['src']=='texas222' else 'DraftKings open'}</td><td>{esc(an_open)}</td></tr>"
            f"<tr><td>Spread tickets</td><td>{esc(tix)}</td></tr>"
            f"<tr><td>Model (last season, opening day)</td><td>{esc(proj)}{'' if edge is None else f' · vs spread {edge:+.1f}'}</td></tr>"
            f"<tr><td>Projected total</td><td>{ptot_txt}</td></tr>"
            f"<tr><td>Signal score</td><td>{esc(a)} {S['sa']} · {esc(h)} {S['sh']} (lead {S['lead']:+d})</td></tr>"
            f"<tr><td>Site</td><td>{'Neutral' if g['neutral'] else 'Home court'} · {'Conference game' if g['cg'] else 'Non-conference'} · {esc(g['aconf'])} vs {esc(g['hconf'])}</td></tr>"
            + (f"<tr><td>Final</td><td>{esc(g['final'])}</td></tr>" if g['final'] else '') + f"<tr><td>Injuries</td><td>LOW: college injury reporting is thin; no confirmed key absences pulled.</td></tr>"
            f"<tr><td>Pick</td><td>{pick_cell(g, g['side'], g['side_lbl'])} {pick_cell(g, g['total'], g['tot_lbl'])} <span class='num'>{esc(' '.join(why)) if not (g['side'] or g['total']) else ''}</span></td></tr>"
            f"</tbody></table>")
    sm = (f"<summary><span class='gm'><b>{esc(rk(g['ar']))}{esc(g['an'] if False else a)}</b> @ <b>{esc(rk(g['hr']))}{esc(h)}</b></span>"
          f"<span class='num'>{esc(tip)}</span><span class='num'>{esc(h+' '+fmt(g['sp'])) if g['posted'] else 'no line'}</span>"
          f"<span class='num'>{'' if not g['posted'] else 'o/u '+format(g['tot'],'g')}</span></summary>")
    return f"<details class='grow' data-c='{esc(g['aconf'])}|{esc(g['hconf'])}'>{sm}{body}</details>"

def _tkey(x):
    x = x.strip().upper().replace('PM', ' PM').replace('AM', ' AM').replace('  ', ' ')
    hm, ap = x.split()[0], x.split()[-1]
    if ':' not in hm: hm += ':00'
    return datetime.datetime.strptime(hm + ' ' + ap, '%I:%M %p')
for _g in games:
    _k = _tkey(_g['time']); _g['time'] = _k.strftime('%-I:%M %p')
all_games = ''.join(game_row(g) for g in sorted(games, key=lambda g: (_tkey(g['time']), g['home'])))

# backtest tables
BT = [l.split('|') for l in (DATA/f'bt_{LG.lower()}.txt').read_text().strip().splitlines()]
def bt_get(test, var, season, month='ALL'):
    for r in BT:
        if r[0] == test and r[1] == var and r[2] == season and r[3] == month: return dict(w=int(r[4]), l=int(r[5]), p=int(r[6]), u=float(r[7]))
    return None
def bt_row(label, x, be=0.5238):
    if not x: return f"<tr><td>{label}</td><td class='num r' colspan='6'>no picks</td></tr>"
    n = x['w'] + x['l']; c = 'pos' if x['u'] > 0 else ('neg' if x['u'] < 0 else '')
    return (f"<tr><td>{label}</td><td class='num r'>{x['w']}</td><td class='num r'>{x['l']}</td><td class='num r'>{x['p']}</td>"
            f"<td class='num r'>{(100*x['w']/n if n else 0):.1f}%</td><td class='num r'>{'·' if be is None else f'{100*be:.1f}%'}</td><td class='num r {c}'>{x['u']:+.1f}u</td></tr>")
TESTS = [('FAV_ML', 'L', 'Favorite ML, lowered (lead 2+)', None), ('FAV_ML', 'S', 'Favorite ML, strict (lead 3+)', None),
         ('DOG_ML', 'L', 'Underdog ML, lowered (lead 1+)', None), ('DOG_ML', 'S', 'Underdog ML, strict (plus line move toward it)', None),
         ('SPREAD_MOVE', 'L', 'Spread line move 0.5+', 0.5238), ('SPREAD_MOVE', 'S', 'Spread line move 1+', 0.5238),
         ('UNDER_DROP', 'L', 'Under, total dropped', 0.5238), ('UNDER_DROP', 'S', 'Under, total dropped 2+', 0.5238),
         ('OVER', 'L', 'Over, total rose', 0.5238), ('OVER', 'S', 'Over, total rose 2+', 0.5238),
         ('BASE_FAV_ML', '', 'Every favorite -200 to -100 (baseline)', None), ('BASE_DOG_ML', '', 'Every underdog +100 to +200 (baseline)', None), ('BASE_UNDER', '', 'Every under (baseline)', 0.5238),
         ('MODEL_EDGE_3', '', 'Model projection beats the spread by 3+', 0.5238),
         ('HOME_ATS_conf', '', 'Home team ATS, conference games', 0.5238), ('HOME_ATS_nonconf', '', 'Home team ATS, non-conference', 0.5238),
         ('UNDER_conf', '', 'Under, conference games', 0.5238), ('UNDER_nonconf', '', 'Under, non-conference', 0.5238),
         ('MIS15_fav', '', 'Nov-Dec non-conf, spread 15+: favorite ATS', 0.5238), ('MIS15_dog', '', 'Nov-Dec non-conf, spread 15+: underdog ATS', 0.5238),
         ('MIS25_dog', '', 'Nov-Dec non-conf, spread 25+: underdog ATS', 0.5238), ('MIS15_under', '', 'Nov-Dec non-conf, spread 15+: under', 0.5238),
         ('NEU_fav', '', 'Neutral site: favorite ATS', 0.5238), ('NEU_under', '', 'Neutral site: under', 0.5238),
         ('HOLI_dog', '', 'Holiday tournaments (Nov-Dec neutral): underdog ATS', 0.5238), ('HOLI_under', '', 'Holiday tournaments: under', 0.5238),
         ('REST2_ATS', '', 'Team with 2+ more days rest ATS', 0.5238), ('ROAD1DAY_fade', '', 'Road team on 1 day rest vs rested home team: home ATS', 0.5238),
         ('ROADTRAV_fade', '', 'Road team traveled, 2 or fewer days rest: home ATS', 0.5238),
         ('UNRK_vs_RK', '', 'Unranked vs ranked: unranked ATS', 0.5238), ('UNRK_HOME_vs_RK', '', 'Unranked home team vs ranked: ATS', 0.5238), ('RKvRK_under', '', 'Ranked vs ranked: under', 0.5238),
         ('PACE_slow_under', '', 'Slow pace tier: under', 0.5238), ('PACE_slow_over', '', 'Slow pace tier: over', 0.5238), ('PACE_mid_under', '', 'Mid pace tier: under', 0.5238),
         ('PACE_mid_over', '', 'Mid pace tier: over', 0.5238), ('PACE_fast_under', '', 'Fast pace tier: under', 0.5238), ('PACE_fast_over', '', 'Fast pace tier: over', 0.5238)]
def verdict(test, var):
    c = bt_get(test, var, 'C'); ss = [bt_get(test, var, s) for s in ('23', '24', '25')]
    pos = sum(1 for x in ss if x and x['u'] > 0)
    return (c and c['u'] > 0 and pos >= 2), pos
def bt_tables():
    hdr = "<thead><tr><th>Test</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Break-even</th><th class='r'>Units</th></tr></thead>"
    out = []
    for test, var, label, be in TESTS:
        ok, pos = verdict(test, var)
        rows = ''.join(bt_row(s, bt_get(test, var, k), be) for s, k in (('2023-24', '23'), ('2024-25', '24'), ('2025-26', '25'), ('Three seasons', 'C')))
        rows += "<tr class='grp'><td colspan='7'>BY MONTH (THREE SEASONS)</td></tr>" + ''.join(bt_row(m, bt_get(test, var, 'C', m), be) for m in ('Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr') if bt_get(test, var, 'C', m))
        tag = "<span class='tag t-rule'>Passes</span>" if ok else "<span class='tag t-np'>Fails</span>"
        out.append(f"<details class='rc'><summary>{esc(label)} {tag} <span class='num'>{pos} of 3 seasons positive</span></summary><div class='scroll'><table class='rt'>{hdr}<tbody>{rows}</tbody></table></div></details>")
    hc = [r for r in BT if r[0].startswith('HOMECONF_') and r[2] == 'C' and r[3] == 'ALL']
    hc.sort(key=lambda r: -float(r[7]))
    hcr = ''.join(bt_row(esc(CONF.get(r[0].split('_')[1], 'Conference ' + r[0].split('_')[1])), dict(w=int(r[4]), l=int(r[5]), p=int(r[6]), u=float(r[7]))) for r in hc)
    out.append(f"<details class='rc'><summary>Home court by conference (home team ATS, conference games, three seasons)</summary><div class='scroll'><table class='rt'>{hdr}<tbody>{hcr}</tbody></table></div></details>")
    return ''.join(out)

WRITEUP = (D/f'backtest_writeup_{LG}.md').read_text() if (D/f'backtest_writeup_{LG}.md').exists() else ''
def md_html(md):
    out, inl = [], False
    for l in md.splitlines():
        if l.startswith('## '): out.append(('</ul>' if inl else '') + f"<h4>{esc(l[3:])}</h4>"); inl = False
        elif l.startswith('- '):
            if not inl: out.append('<ul class=\"nl\">'); inl = True
            out.append(f"<li>{esc(l[2:])}</li>")
        elif l.strip():
            if inl: out.append('</ul>'); inl = False
            out.append(f"<p>{esc(l)}</p>")
    if inl: out.append('</ul>')
    return ''.join(out)

rules_rows = ''.join(f"<tr><td>{esc(RULENAME[r])}</td><td>{esc(s['variant'])}</td><td>{'<span class=\"tag t-rule\">Live</span>' if s['on'] else '<span class=\"tag t-np\">Off</span>'}</td>"
                     f"<td class='num'>{s['backtest']['w']}-{s['backtest']['l']} · {s['backtest']['u']:+.1f}u · {s['backtest']['pos']} of 3</td>"
                     f"<td class='num'>{s.get('season',{}).get('w',0)}-{s.get('season',{}).get('l',0)} · {s.get('season',{}).get('u',0):+.2f}u</td><td class='whyc'>{esc(s.get('note',''))}</td></tr>"
                     for r, s in STATE['rules'].items())

posted = [g for g in games if g['posted']]
pick_rows = ''.join(f"<tr class='pickrow'><td><a class='glink' href='#{g['away'].lower()}-{g['home'].lower()}' data-tab='{g['away'].lower()}-{g['home'].lower()}'>{esc(g['away'])} @ {esc(g['home'])}</a></td><td class='num'>{esc(g['day'])} · {esc(g['time'])}</td>"
                    f"<td>{pick_cell(g, g['side'], g['side_lbl'])}</td><td>{pick_cell(g, g['total'], g['tot_lbl'])}</td></tr>" for g in PICKED)
live_rules = [RULENAME[r] + f" ({s['variant']})" for r, s in STATE['rules'].items() if s['on']]
picks_html = (f"<h3 class='sh'>Tonight's picks</h3>"
              + (f"<div class='scroll'><table><thead><tr><th>Game</th><th>Date · tip (Phoenix)</th><th>Side</th><th>Total</th></tr></thead><tbody>{pick_rows}</tbody></table></div>" if PICKED else
                 f"<div class='card headline'><b>No pick tonight.</b> <span class='num'>{'Live rules: ' + ', '.join(live_rules) + '. None fits a game with an Odds API line.' if live_rules else 'No rule passed the three-season backtest, so every game is No pick until the re-check or your OK turns one on.'}</span></div>"))

# game tabs only for games with a pick
def game_panel(g):
    tid = f"{g['away'].lower()}-{g['home'].lower()}"
    cards = ''
    for c, lbl in ((g['side'], g['side_lbl']), (g['total'], g['tot_lbl'])):
        if not c: cards += "<div class='pick nopick'><div class='lbl'>No pick</div><div class='pt'>No pick</div><div class='why'>No live rule fits this market.</div></div>"; continue
        s = STATE['rules'][c['rule']]; why = g['S']['why_h'] if c['side'] == 'home' else (g['S']['why_a'] if c['side'] == 'away' else [f"total moved {g['S']['M']['t']}"])
        cards += (f"<div class='pick'><div class='lbl'>{esc(c['market'])}</div><div class='pt'>{esc(lbl)} {fmt(c['price'])}</div>"
                  f"<div><span class='tag t-rule'>{esc(RULENAME[c['rule']])}</span><span class='tag t-d'>LOW</span></div>"
                  f"<div class='why'><b>Why:</b> {esc('; '.join(why) or 'rule fit')}. Backtest {s['backtest']['w']}-{s['backtest']['l']}, {s['backtest']['u']:+.1f}u.</div>"
                  f"<div class='why'><b class='ag'>Working against it:</b> injuries unknown (LOW); college ratings on opening day are last season only.</div></div>")
    return (f"<section class='panel' id='panel-{tid}' role='tabpanel' aria-labelledby='tab-{tid}' hidden><div class='top'><h2 class='gh'>{esc(g['away'])} <span class='at'>@</span> {esc(g['home'])}</h2></div>"
            f"<div class='sub'>{esc(g['day'])} · {esc(g['time'])} Phoenix · {esc(g['aconf'])} vs {esc(g['hconf'])}{' · neutral site' if g['neutral'] else ''}</div><div class='picks'>{cards}</div>{game_row(g).replace('<details ', '<details open ')}</section>")
panels = ''.join(game_panel(g) for g in PICKED)

# standings
AP = json.loads((DATA/'ap_poll.json').read_text())[LG] if (DATA/'ap_poll.json').exists() else []
IDS = dict(x.split(':') for x in (DATA/'ids.txt').read_text().strip().split(','))
SPORT = 'mens-college-basketball' if LG == 'M' else 'womens-college-basketball'
GUIDE = {k[1:]: f"https://www.espn.com/{SPORT}/team/_/id/{v}" for k, v in IDS.items() if k[0] == LG}
teams_today = sorted({(g['away'], g['aconf']) for g in games} | {(g['home'], g['hconf']) for g in games}, key=lambda x: (x[1], x[0]))
by_conf = {}
for t, c in teams_today: by_conf.setdefault(c, []).append(t)
conf_html = ''.join(f"<details class='rc'><summary>{esc(c)} <span class='num'>{len(ts)} teams on tonight's board</span></summary><div class='scroll'><table class='rt'><thead><tr><th>Team</th><th class='r'>Conf</th><th class='r'>Overall</th><th class='r'>Rating (last season)</th></tr></thead><tbody>"
                    + ''.join(f"<tr><td>{esc(t)}</td><td class='num r'>0-0</td><td class='num r'>0-0</td><td class='num r'>{'·' if RAT.get(t,(None,))[0] is None else format(RAT[t][0],'+.1f')}</td></tr>" for t in ts) + "</tbody></table></div></details>"
                    for c, ts in sorted(by_conf.items()))
ap_html = ''.join(f"<tr><td class='num'>{r['rank']}</td><td>{esc(r['team'])}</td><td class='num'>{esc(r.get('rec','0-0'))}</td></tr>" for r in AP)
guide_html = ''.join(f"<tr><td>{esc(t)}</td><td>{esc(c)}</td><td>{'<a class=\"glink\" href=\"'+esc(GUIDE[t])+'\" target=\"_blank\" rel=\"noopener\">ESPN team page</a>' if t in GUIDE else '<span class=\"num\">link to come</span>'}</td></tr>" for t, c in teams_today)
standings = (f"<section class='panel' id='panel-standings' role='tabpanel' aria-labelledby='tab-standings' hidden>"
             f"<div class='sub'>Opening night: every team is 0-0. NET rankings are first published in early December; the column fills in then.</div>"
             f"<h3 class='sh'>AP Top 25</h3><div class='scroll'><table class='rt'><thead><tr><th>Rank</th><th>Team</th><th>Record</th></tr></thead><tbody>{ap_html}</tbody></table></div>"
             f"<h3 class='sh'>NET rank</h3><div class='card'><span class='num'>Not published yet (first NET release is in early December).</span></div>"
             f"<h3 class='sh'>Conference standings</h3>{conf_html}"
             f"<h3 class='sh'>Team guide</h3><div class='scroll'><table class='rt'><thead><tr><th>Team</th><th>Conference</th><th>Team page</th></tr></thead><tbody>{guide_html}</tbody></table></div></section>")

results_panel = f"""
<section class='panel' id='panel-results' role='tabpanel' aria-labelledby='tab-results' hidden>
<div class='sub'>Season tracker for every card pick from {DATE_L}: graded from ESPN finals each morning. Units assume 1 unit risked per pick at the Odds API median price shown on the card.</div>
<div id='res-state' class='card'>Loading the pick ledger…</div>
<div id='res-body' hidden>
<div class='tiles' id='res-tiles'></div>
<h3 class='sh'>By rule</h3><div class='scroll'><table class='rt'><thead><tr><th>Rule (card picks)</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-rule'></tbody></table></div>
<h3 class='sh'>By tier</h3><div class='scroll'><table class='rt'><thead><tr><th>Tier</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-tier'></tbody></table></div>
<h3 class='sh'>By market</h3><div class='scroll'><table class='rt'><thead><tr><th>Market</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-mkt'></tbody></table></div>
<h3 class='sh'>By market and tier</h3><div class='scroll'><table class='rt mt'><thead><tr><th>Market · tier</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-mt'></tbody></table></div>
<h3 class='sh'>Filter</h3>
<div class='filters' id='filters'>
<details class='ms' data-f='date'><summary><span class='fl'>Date</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='dow'><summary><span class='fl'>Day of week</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='team'><summary><span class='fl'>Team</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='market'><summary><span class='fl'>Market</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='tier'><summary><span class='fl'>Tier</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='result'><summary><span class='fl'>Result</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<button type='button' id='f-clear'>Clear filters</button>
</div>
<div class='card ftot' id='f-tot'></div>
<details class='rd' id='d-log'><summary>Every pick <span class='num' id='c-log'></span></summary><div class='scroll'><table class='rt log'><thead><tr><th>Date</th><th>Game</th><th>Market</th><th>Pick</th><th class='r'>Price</th><th>Tier</th><th>Final</th><th>Result</th><th class='r'>Units</th></tr></thead><tbody id='res-log'></tbody><tfoot id='res-log-tot'></tfoot></table></div></details>
</div>
<h3 class='sh'>Rule records</h3><div class='scroll'><table class='rt'><thead><tr><th>Rule</th><th>Variant</th><th>Status</th><th>Backtest (3 seasons)</th><th>This season (re-check)</th><th>Note</th></tr></thead><tbody>{rules_rows}</tbody></table></div>
<h3 class='sh'>Re-check: every test, every game played this season</h3><div class='sub'>{esc(STATE.get('recheck_note','Runs daily from the first graded slate. Nothing has been played yet.'))}</div>
<h3 class='sh'>Backtest baseline: 2023-24 to 2025-26</h3><div class='sub'>Every Division I game with an ESPN closing line. Moneylines at the closing consensus, spreads and totals at -110 (break-even 52.4%). Kept separate from this season's re-check. Tap a test to open it.</div>
{bt_tables()}
<h3 class='sh'>Backtest write-up</h3><div class='card'>{md_html(WRITEUP)}</div>
</section>"""

tabs = ("<button class='tab' role='tab' id='tab-slate' aria-controls='panel-slate' data-tab='slate'>Slate</button>"
        "<button class='tab' role='tab' id='tab-standings' aria-controls='panel-standings' data-tab='standings'>Standings<span>AP · conferences</span></button>"
        + ''.join(f"<button class='tab' role='tab' id='tab-{g['away'].lower()}-{g['home'].lower()}' aria-controls='panel-{g['away'].lower()}-{g['home'].lower()}' data-tab='{g['away'].lower()}-{g['home'].lower()}'>{esc(g['away'])} @ {esc(g['home'])}<span>{esc(g['day'])} {esc(g['time'].replace(' PM',''))}</span></button>" for g in PICKED)
        + "<button class='tab' role='tab' id='tab-results' aria-controls='panel-results' data-tab='results'>Results<span>Season tracker</span></button>")
EXTRA_CSS = """
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0 10px}.chip{border-radius:16px;padding:4px 10px;font-size:12px;color:var(--mute)}
.chip.on{background:var(--abg);color:var(--a);border-color:var(--a);font-weight:700}
details.grow{margin:6px 0;padding:8px 12px}details.grow summary{display:flex;flex-wrap:wrap;gap:4px 14px;align-items:baseline;font-weight:400}
details.grow summary .gm{flex:1 1 180px;min-width:0}details.grow .kv td{white-space:normal}details.grow .kv{margin-top:8px}
@media (max-width:640px){table.kv td:first-child{width:auto;min-width:96px}details.grow summary .num{font-size:12px}}
.card h4{margin:14px 0 4px;font-size:14px}
table.kv{table-layout:fixed;width:100%}table.kv td{overflow-wrap:anywhere}table.kv .num,.card .num{white-space:normal}table.kv .tag{white-space:normal}.card p{margin:6px 0;font-size:13.5px}
"""
CSS = (D/'card.css').read_text() + EXTRA_CSS
RESULTS_JS = (D/'results.js').read_text()
unl = f"<div class='sub'>Not on ESPN's Division I slate or not matched: {esc(', '.join(unmatched))}.</div>" if unmatched else ''
page = f"""<title>{NAME} Card</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>{CSS}</style>
<div class='wrap'>
<header class='mast'><div><div class='eyebrow'>{FULL} · {DATE_L}</div><h1>{len(games)} games · {len(posted)} lined</h1></div>
<button id='tt-btn' type='button'>Toggle theme</button></header>
<div class='tabs' role='tablist'>{tabs}</div>
<section class='panel' id='panel-slate' role='tabpanel' aria-labelledby='tab-slate'>
<div class='sub'>Every Division I game on the official schedule. Lines: The Odds API median of books when posted, otherwise DraftKings. Times are Phoenix. Analysis tool, not a betting system.</div>
{picks_html}
<h3 class='sh'>Rules</h3><div class='card'><ul class='nl'>{''.join(f"<li>{esc(rule_line(r))}</li>" for r in STATE['rules'])}</ul></div>
<h3 class='sh'>All games</h3>
{chip_html}
<div id='glist'>{all_games}</div>
{unl}
<div class='card' style='margin-top:12px'><div class='lbl'>How the numbers are built</div><ul class='nl'>
<li>Team strength: opponent-adjusted margin per game from ESPN scores (last season's final number until this season's games count; blend games / (games + 8)), home court 3 points, none at neutral sites.</li>
<li>Rules use only signals that could be backtested: line moves at two books, projection vs spread, rest, home court, form, average margin and bounce-back. Tickets and money (Action Network) are shown but have no college history to test.</li>
<li>Injuries: college reporting is thin, so every game is LOW until key players are confirmed.</li></ul></div>
</section>
{standings}
{panels}
{results_panel}
</div>
<script>
(function(){{
  var tabs=[].slice.call(document.querySelectorAll('.tab'));
  function show(id){{
    if(!document.getElementById('panel-'+id)) id='slate';
    tabs.forEach(function(t){{var on=t.dataset.tab===id; t.setAttribute('aria-selected',on); t.tabIndex=on?0:-1;}});
    [].slice.call(document.querySelectorAll('.panel')).forEach(function(p){{p.hidden = p.id!=='panel-'+id;}});
    var b=document.getElementById('tab-'+id); if(b&&b.scrollIntoView) b.scrollIntoView({{block:'nearest',inline:'center'}});
  }}
  tabs.forEach(function(t,i){{
    t.addEventListener('click',function(){{show(t.dataset.tab); try{{history.replaceState(null,'','#'+t.dataset.tab);}}catch(e){{}} window.scrollTo(0,0);}});
    t.addEventListener('keydown',function(e){{var k=e.key==='ArrowRight'?1:e.key==='ArrowLeft'?-1:0; if(k){{var n=tabs[(i+k+tabs.length)%tabs.length]; n.focus(); n.click();}}}});
  }});
  [].slice.call(document.querySelectorAll('.glink[data-tab]')).forEach(function(a){{a.addEventListener('click',function(e){{e.preventDefault(); show(a.dataset.tab); window.scrollTo(0,0);}});}});
  show((location.hash||'').slice(1)||'slate');
  var chips=[].slice.call(document.querySelectorAll('.chip'));
  chips.forEach(function(c){{c.addEventListener('click',function(){{
    chips.forEach(function(x){{x.classList.toggle('on',x===c);}}); var v=c.dataset.c;
    [].slice.call(document.querySelectorAll('#glist details.grow')).forEach(function(d){{d.hidden = v && d.dataset.c.split('|').indexOf(v)<0;}});
  }});}});
  document.getElementById('tt-btn').addEventListener('click',function(){{
    var r=document.documentElement,cur=r.getAttribute('data-theme');
    var dark=cur?cur==='dark':window.matchMedia('(prefers-color-scheme: dark)').matches;
    r.setAttribute('data-theme',dark?'light':'dark');}});
}})();
</script>
{RESULTS_JS}
"""
out = D.parent/'out'/LG; out.mkdir(parents=True, exist_ok=True)
(out/'index.html').write_text(page)
docs = []
for g in PICKED:
    for kind, c, lbl in (('side', g['side'], g['side_lbl']), ('total', g['total'], g['tot_lbl'])):
        if not c: continue
        docs.append(dict(id=f"{DATE}_{g['away']}-{g['home']}_{kind}", data=dict(date=DATE, game=f"{g['away']} @ {g['home']}", away=g['away'], home=g['home'], time=g['time'], day=g['day'],
                    market=c['market'], pick=lbl, price=int(c['price']), tier='Thin', conflicting=False, projected=None, result=grade_now(g, c), final=g['final'],
                    rule=c['rule'], line_source=LSRC(g), rule_variant=c['variant'], conference=g['hconf'] if g['cg'] else f"{g['aconf']} vs {g['hconf']}")))
(out/'ledger_today.json').write_text(json.dumps(docs, indent=1))
print(f"{NAME}: {len(games)} games joined ({len(posted)} lined), {len(unmatched)} unmatched, {len(PICKED)} with a pick, {len(docs)} ledger docs")
for g in PICKED: print(' ', g['away'], '@', g['home'], g['side_lbl'], g['tot_lbl'])
if unmatched: print('UNMATCHED:', unmatched)
