#!/usr/bin/env python3
"""model_stay_detector.py — transcript末尾の高消費モデル滞在を検出する共有ロジック

spec: obsidian-ssot/docs/superpowers/specs/2026-09-01_glm5.3戻し忘れ検知-design.md §4.1
- HIGH_COST_MODELS はホワイトリスト完全一致（部分文字列マッチ禁止）
- 「flash を含むモデル名」は常に低消費扱い
- 末尾 TAIL_LINES 行のみ走査（全体メモリ読込禁止）
- パース失敗行はスキップ（破損行耐性）
"""
import json
import sys
from collections import deque
from datetime import datetime, timezone

HIGH_COST_MODELS = ["glm-5.3"]  # 将来の glm-5.4 等はこの1行のみ更新
TAIL_LINES = 500


def parse_ts(raw):
    """ISO8601タイムスタンプをdatetime(UTC)へ変換する。失敗時はNone。"""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def is_high_cost(model):
    """高消費モデルかを判定する。ホワイトリスト完全一致+flash除外。"""
    if not isinstance(model, str) or "flash" in model:
        return False
    return model in HIGH_COST_MODELS


def scan_file(path, now=None):
    """1つのtranscriptの末尾連続区間を判定する。該当なしならNone。

    戻り値: {"model": str, "since_min": float|None, "turns": int}
    """
    now = now or datetime.now(timezone.utc)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            tail = deque(f, maxlen=TAIL_LINES)
    except OSError:
        return None
    run_start = None
    run_turns = 0
    run_model = None
    for line in tail:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if entry.get("type") != "assistant" or not isinstance(entry.get("message"), dict):
            continue
        if is_high_cost(entry["message"].get("model")):
            if run_turns == 0:
                run_start = parse_ts(entry.get("timestamp"))
            run_turns += 1
            run_model = entry["message"]["model"]
        else:
            run_start = None
            run_turns = 0
            run_model = None
    if run_turns == 0:
        return None
    since_min = None
    if run_start is not None:
        since_min = (now - run_start).total_seconds() / 60
    return {"model": run_model, "since_min": since_min, "turns": run_turns}


def detect(paths, now=None):
    """複数transcriptの判定結果リスト{transcript, model, since_min, turns}を返す。"""
    out = []
    for p in paths:
        r = scan_file(p, now)
        if r is None:
            continue
        merge = {"transcript": p}
        merge.update(r)
        out.append(merge)
    return out


def main():
    """CLI: python3 module.py <jsonl>... [--now ISO8601] → JSON配列"""
    args = list(sys.argv[1:])
    now = None
    if "--now" in args:
        i = args.index("--now")
        now = parse_ts(args[i + 1])
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        del args[i:i + 2]
    print(json.dumps(detect(args, now), ensure_ascii=False))


if __name__ == "__main__":
    main()
