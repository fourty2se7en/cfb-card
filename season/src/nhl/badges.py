# Team-color abbreviation badges (original design, not team logos)
C = {
 'ANA':('#b9562a','#111111'),'BOS':('#2b2b2b','#fcb514'),'BUF':('#003087','#fcb514'),'CAR':('#cc0000','#111111'),'CBJ':('#002654','#ce1126'),
 'CGY':('#c8102e','#f1be48'),'CHI':('#cf0a2c','#111111'),'COL':('#6f263d','#236192'),'DAL':('#006847','#8f8f8c'),'DET':('#ce1126','#ffffff'),
 'EDM':('#041e42','#ff4c00'),'FLA':('#041e42','#c8102e'),'LAK':('#2b2b2b','#a2aaad'),'MIN':('#154734','#a6192e'),'MTL':('#af1e2d','#192168'),
 'NJD':('#ce1126','#111111'),'NSH':('#041e42','#ffb81c'),'NYI':('#00539b','#f47d30'),'NYR':('#0038a8','#ce1126'),'OTT':('#c8102e','#c2912c'),
 'PHI':('#d65a00','#111111'),'PIT':('#2b2b2b','#fcb514'),'SEA':('#001628','#99d9d9'),'SJS':('#006d75','#ea7200'),'STL':('#002f87','#fcb514'),
 'TBL':('#002868','#ffffff'),'TOR':('#00205b','#ffffff'),'UTA':('#4a7fa8','#090909'),'VAN':('#00205b','#00843d'),'VGK':('#333f42','#b4975a'),
 'WSH':('#041e42','#c8102e'),'WPG':('#041e42','#7b303e'),
}
def badge(t, size=''):
    bg, ac = C[t]
    return f"<span class='tb{(' '+size) if size else ''}' style='--tb:{bg};--ta:{ac}' aria-hidden='true'>{t}</span>"
