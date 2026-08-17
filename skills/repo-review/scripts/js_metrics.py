"""JS/GAS 用ファイルレベル計測（ASTパーサ不在時の近似・必ず「近似」と明記して使う）。"""
import os, re, sys
root = sys.argv[1]
EXC = {'node_modules','.git','dist','build','coverage','__pycache__'}
BR = re.compile(r'\b(if|else if|for|while|case|catch|\?\s|&&|\|\|)\b|\?\.')
FN = re.compile(r'\bfunction\s+\w+|\w+\s*[:=]\s*function|\w+\s*=>\s*|\bclass\s+\w+')
rows = []
for dp, dn, fs in os.walk(root):
    dn[:] = [d for d in dn if d not in EXC]
    for f in fs:
        if not f.endswith(('.js', '.ts', '.gs')): continue
        p = os.path.join(dp, f)
        try: txt = open(p, encoding='utf-8', errors='ignore').read()
        except OSError: continue
        loc = txt.count('\n') + 1
        br = len(BR.findall(txt))
        fn = len(FN.findall(txt))
        rows.append((loc, br, fn, os.path.relpath(p, root).replace(os.sep,'/')))
rows.sort(reverse=True)
print(f"JSファイル数: {len(rows)}  総LOC: {sum(r[0] for r in rows)}")
print(f"総関数らしき定義: {sum(r[2] for r in rows)}  総分岐キーワード: {sum(r[1] for r in rows)}")
print("\n--- 最大ファイル 上位12（LOC / 分岐 / 関数定義） ---")
for loc, br, fn, p in rows[:12]:
    dens = br / loc * 100 if loc else 0
    print(f"  {loc:6}行 分岐{br:5} 関数{fn:4} 密度{dens:5.1f}%  {p}")
print("\n--- 分岐密度が高いファイル 上位6（200行以上） ---")
big = [r for r in rows if r[0] >= 200]
big.sort(key=lambda r: r[1]/r[0], reverse=True)
for loc, br, fn, p in big[:6]:
    print(f"  密度{br/loc*100:5.1f}%  {loc:5}行 分岐{br:5}  {p}")
