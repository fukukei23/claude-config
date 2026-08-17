"""JS/GAS 用ファイルレベル計測（ASTパーサ不在時の近似・必ず「近似」と明記して使う）。

使い方: python3 js_metrics.py <REPO> [除外dir ...（ベース名 or パス指定）]
前処理でコメント・文字列リテラルを除去してから正規表現を適用する
（high 3-4: コメント内キーワード誤検知で「分岐密度異常高」と偽P1提案されるのを防止）。
除外リストは _shared.py の単一ソースから import（critical 2-2）。
"""
import os
import re
import sys

from _shared import prune_dirnames

BR = re.compile(r'\b(if|else if|for|while|case|catch|\?\s|&&|\|\|)\b|\?\.')
FN = re.compile(r'\bfunction\s+\w+|\w+\s*[:=]\s*function|\w+\s*=>\s*|\bclass\s+\w+')


def strip_comments_strings(src: str) -> str:
    """ブロック/行コメント・文字列リテラルを除去する（正規表現適用前の前処理）。"""
    out = []
    i, n = 0, len(src)
    mode = "code"  # code | line | block | squote | dquote | template
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if mode == "code":
            if c == "/" and nxt == "/":
                mode = "line"
                i += 2
                continue
            if c == "/" and nxt == "*":
                mode = "block"
                i += 2
                continue
            if c == "'":
                mode = "squote"
                i += 1
                continue
            if c == '"':
                mode = "dquote"
                i += 1
                continue
            if c == "`":
                mode = "template"
                i += 1
                continue
            out.append(c)
        elif mode == "line":
            if c == "\n":
                mode = "code"
                out.append(c)
        elif mode == "block":
            if c == "*" and nxt == "/":
                mode = "code"
                i += 2
                continue
        else:  # 文字列内（エスケープは読み飛ばす・改行だけ行数保持で出力）
            if c == "\\":
                i += 2
                continue
            if ((mode == "squote" and c == "'")
                    or (mode == "dquote" and c == '"')
                    or (mode == "template" and c == "`")):
                mode = "code"
            elif c == "\n":
                out.append(c)
        i += 1
    return "".join(out)


def main() -> None:
    """JS/GAS ファイルの近似計測レポートを出力する。"""
    root = sys.argv[1]
    extra = set(sys.argv[2:])
    rows = []
    for dp, dn, fs in os.walk(root):
        prune_dirnames(dn, dp, root, extra)
        for f in fs:
            if not f.endswith(('.js', '.ts', '.gs')):
                continue
            p = os.path.join(dp, f)
            try:
                txt = open(p, encoding='utf-8', errors='ignore').read()
            except OSError:
                continue
            loc = txt.count('\n') + 1
            stripped = strip_comments_strings(txt)
            br = len(BR.findall(stripped))
            fn = len(FN.findall(stripped))
            rows.append((loc, br, fn, os.path.relpath(p, root).replace(os.sep, '/')))
    rows.sort(reverse=True)
    print(f"JSファイル数: {len(rows)}  総LOC: {sum(r[0] for r in rows)}")
    print(f"総関数らしき定義: {sum(r[2] for r in rows)}  総分岐キーワード: {sum(r[1] for r in rows)}")
    print("※ 近似は過大評価傾向（コメント・文字列除去済みでも正規表現ベースのため・"
          "Python の CC と直接比較しない）")
    print("\n--- 最大ファイル 上位12（LOC / 分岐 / 関数定義） ---")
    for loc, br, fn, p in rows[:12]:
        dens = br / loc * 100 if loc else 0
        print(f"  {loc:6}行 分岐{br:5} 関数{fn:4} 密度{dens:5.1f}%  {p}")
    print("\n--- 分岐密度が高いファイル 上位6（200行以上） ---")
    big = [r for r in rows if r[0] >= 200]
    big.sort(key=lambda r: r[1] / r[0], reverse=True)
    for loc, br, fn, p in big[:6]:
        print(f"  密度{br / loc * 100:5.1f}%  {loc:5}行 分岐{br:5}  {p}")


if __name__ == "__main__":
    main()
