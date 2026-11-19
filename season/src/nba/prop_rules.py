"""Prop rule status (Season Cards policy, Nov 6, 2026). Added to src Nov 8 (was done by hand on Nov 6 and 7).
Each prop Category · Side (stat|side) is graded on every logged prop in the hub ledger (Play and tracking; void and held props skipped).
Season only policy (Trina, Nov 9; code updated Nov 10): season to date decides. Switches off once it has the league pick minimum
(NBA 20) and negative season units; turns back on when season units are green. The current month is a watch only (red on 5+ picks
sets 'watch'; it never switches anything).
Usage: python3 prop_rules.py <ledger dir with the picks *.json> <today YYYY-MM-DD>   (writes prop_rules_state.json, prints switches)"""
import json, sys, glob, pathlib
import pickrules as P
D = pathlib.Path(__file__).parent; ST = D/'prop_rules_state.json'
OFF_N, MONTH_N = 20, 5
MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
def main(led, today):
    old = json.loads(ST.read_text()) if ST.exists() else dict(rules={}, log=[])
    X = [json.loads(pathlib.Path(f).read_text()) for f in glob.glob(str(pathlib.Path(led)/'*.json'))]
    X = [x for x in X if x.get('market') == 'Prop' and x.get('result') in ('win', 'loss', 'push') and x.get('stat') and x.get('side')]
    m = today[:7]; out = dict(updated=today, policy='season only, minimum 20, month watch (Nov 9)', rules={}, log=list(old.get('log', [])))
    for st in ('points', 'rebounds', 'assists', 'threes'):
        for sd in ('over', 'under'):
            k = f'{st}|{sd}'; xs = [x for x in X if x['stat'] == st and x['side'] == sd]
            s = P.summarize([(x['result'], x['price']) for x in xs]); mo = P.summarize([(x['result'], x['price']) for x in xs if x['date'][:7] == m])
            S = dict(w=s['w'], l=s['l'], p=s['p'], u=s['u'], n=s['w']+s['l']+s['p'])
            M = dict(w=mo['w'], l=mo['l'], p=mo['p'], u=mo['u'], n=mo['w']+mo['l']+mo['p'], label=MON[int(m[5:])-1])
            was = old.get('rules', {}).get(k, {}).get('on', True)
            month_bad = M['n'] >= MONTH_N and M['u'] < 0
            if was and S['n'] >= OFF_N and S['u'] < 0: on = False
            elif not was and S['u'] >= 0: on = True
            else: on = was
            if on != was: out['log'].append(f"{today}: {k} switched {'on' if on else 'off'} (season {S['w']}-{S['l']}-{S['p']} {S['u']:+.2f}u; {M['label']} {M['w']}-{M['l']}-{M['p']} {M['u']:+.2f}u)")
            out['rules'][k] = dict(on=on, season=S, month=M, watch=month_bad)
    ST.write_text(json.dumps(out, indent=1))
    for k, v in out['rules'].items(): print(k, 'on' if v['on'] else 'off', v['season'], v['month'])
    print('\n'.join(l for l in out['log'] if l.startswith(today)) or 'no prop rule switches')
if __name__ == '__main__': main(sys.argv[1], sys.argv[2])
