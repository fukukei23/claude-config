#!/usr/bin/env python3
"""measure-fc-fp.py — check-fail-coverage.sh発火条件の誤検知率を過去transcriptで事前測定.

使い方: python3 measure-fc-fp.py [セッション数=5]
出力: 各セッションの「確定語×検証語共起」検出数と、うちa′4要素を含む割合。
判定: 共起検出のうち4要素充足が3割未満なら発火語の再設計が必要（spec Phase 0.5基準>30%）。
"""
import json, glob, os, sys, re

CONFIRM = ['✅', '完了', '合格', 'PASS']
VERIFY = ['検証', 'テスト', '実測', '確認']


def last_assistant_texts(path: str) -> list:
    """transcriptからassistantテキストのみ抽出する."""
    texts = []
    with open(path) as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('type') == 'assistant':
                for c in d.get('message', {}).get('content', []):
                    if isinstance(c, dict) and c.get('type') == 'text':
                        texts.append(c.get('text', ''))
    return texts


def main(n: int = 5) -> None:
    files = sorted(glob.glob(os.path.expanduser(
        '~/.claude/projects/-home-yn4416/*.jsonl')), key=os.path.getmtime, reverse=True)[:n]
    total_fire, total_ok = 0, 0
    for p in files:
        fires = oks = 0
        for t in last_assistant_texts(p):
            has_c = any(k in t for k in CONFIRM)
            has_v = any(k in t for k in VERIFY)
            if has_c and has_v:
                fires += 1
                # a′4要素の粗い代理検査（引用っぽさ: EXIT= / コードブロック / 閾値 / fail条件）
                if re.search(r'(EXIT=\d|exit code|^```|閾値|fail条件)', t, re.M):
                    oks += 1
        print(f"{os.path.basename(p)[:12]}: 共起検出={fires} 4要素代理充足={oks}")
        total_fire += fires
        total_ok += oks
    if total_fire == 0:
        print("RESULT: 共起0件 — 過去セッションで発火なし（誤検知リスク低）")
        return
    rate = (total_fire - total_ok) / total_fire * 100
    print(f"RESULT: 擬似誤検知率={rate:.0f}% （>30%なら発火語再設計）")


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 5)
