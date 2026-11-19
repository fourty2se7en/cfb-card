import sys
W='/home/claude/season/ncaam/w/data/'; times=set(sys.argv[1].split(','))
L=open(W+'espn_today_m.txt').read().splitlines(); ids=set()
for i,l in enumerate(L):
    f=l.split('|')
    if i and f[1] in times and f[-1]=='p': f[-1]='i'; ids.add(f[0]); L[i]='|'.join(f)
open(W+'espn_today_m.txt','w').write('\n'.join(L)+'\n')
B=open(W+'espn_board.txt').read().splitlines()
for i,l in enumerate(B):
    f=l.split('|')
    if f[1] in ids and f[11]=='p': f[11]='i'; B[i]='|'.join(f)
open(W+'espn_board.txt','w').write('\n'.join(B)+'\n'); print('marked',len(ids))
