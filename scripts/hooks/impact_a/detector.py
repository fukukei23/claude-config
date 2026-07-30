"""impact-a detector: データ読込→diff解析→マッチ→注入文生成（spec §2.1, §4.1）"""
import re
from pathlib import Path
from typing import Any

from .git_diff import (
    VALID_CATEGORIES,
    match_keywords,
    normalize_category,
    parse_unified_zero_diff,
)
from .parser import (
    parse_antipatterns_md,
    parse_dangerous_ops_yaml,
)


def load_config() -> dict[str, Any]:
    """固定デフォルト（spec は YAML 設定ファイル化しない・YAGNI）"""
    return {
        "edit_extensions": [".py", ".js", ".ts", ".sh", ".yaml", ".yml", ".json"],
        "silent_skip": True,
        "global_antipatterns_path": Path.home() / "projects" / "obsidian-ssot" / "00_SYSTEM" / "impact-antipatterns.md",
        "dangerous_ops_path": Path.home() / "projects" / "obsidian-ssot" / "00_SYSTEM" / "dangerous-ops.yaml",
    }


def detect_from_state(
    diff: str,
    antipatterns: list[dict[str, Any]],
    dangerous_ops: list[dict[str, Any]],
) -> dict[str, Any]:
    """diff と data から検知結果を返す。

    Returns:
        {
            "matched": bool,
            "category": str | None,
            "matched_keywords": list[str],
            "files": list[str],
            "antipattern_id": str | None,
            "dangerous_op_match": str | None,
            "future_scenario_hint": str | None,
            "canonical_source_hint": str | None,
        }
    """
    lines_added = parse_unified_zero_diff(diff)
    files = _extract_files_from_diff(diff)

    # antipatterns と照合
    matched_kws: list[str] = []
    matched_ap: dict[str, Any] | None = None
    for ap in antipatterns:
        kws = ap.get("trigger_keywords", [])
        hits = match_keywords(lines_added, kws)
        if hits:
            matched_kws.extend(hits)
            matched_ap = ap
            break

    # dangerous-ops と照合
    matched_op: dict[str, Any] | None = None
    for op in dangerous_ops:
        for pat in op.get("match_patterns", []):
            for line in lines_added:
                if re.search(pat, line):
                    matched_op = op
                    break
            if matched_op:
                break

    category: str | None = None
    if matched_ap:
        category = normalize_category(matched_ap.get("category", ""))
    if matched_op:
        op_cat = normalize_category(matched_op.get("category", ""))
        if op_cat:
            category = op_cat

    return {
        "matched": bool(matched_ap or matched_op),
        "category": category,
        "matched_keywords": list(dict.fromkeys(matched_kws)),
        "files": files,
        "antipattern_id": matched_ap.get("id") if matched_ap else None,
        "dangerous_op_match": matched_op.get("id") if matched_op else None,
        "future_scenario_hint": matched_ap.get("future_scenario_hint") if matched_ap else None,
        "canonical_source_hint": matched_ap.get("canonical_source_hint") if matched_ap else None,
    }


def build_injection_text(payload: dict[str, Any] | None) -> str:
    """追加Context 注入用 1行TSV（spec §3.5 構造化: 人間可読・軽量3択）

    マッチ判定: payload が非None かつ (matched=True が立っている OR
    category / matched_keywords のいずれかが非空) のいずれかの場合に注入文を返す。
    detect_from_state 経由の正規ルートと、テストからの手動 payload 双方を受けるため。
    """
    if not payload:
        return ""
    if not (
        payload.get("matched")
        or payload.get("category")
        or payload.get("matched_keywords")
    ):
        return ""
    cat = payload.get("category", "?")
    kws = ",".join(payload.get("matched_keywords", []))
    files = ",".join(payload.get("files", []))
    hint = payload.get("future_scenario_hint", "")
    return (
        f"[impact-mode] category={cat} | keywords={kws} | files={files} | "
        f"future_scenario_hint(想起)={hint} | "
        f"行動選択: (1)impactモード手動起動 / (2)ignore_reason記載して無視 / (3)何もせず"
    )


def _extract_files_from_diff(diff: str) -> list[str]:
    """`diff --git a/foo b/foo` 形式、または `+++ b/foo` ヘッダからファイル名を抽出。
    テストフィクスチャ（`--- a/foo` / `+++ b/foo` 形式）と
    本物の git diff 出力（`diff --git ...` 行）双方に対応する。
    """
    files: list[str] = []
    for line in diff.splitlines():
        m = re.match(r"diff --git a/(.+?) b/(.+)", line)
        if m:
            files.append(m.group(2))
            continue
        # unified diff 形式（テストフィクスチャ用）
        m2 = re.match(r"\+\+\+ b/(.+)", line)
        if m2:
            files.append(m2.group(1))
    return list(dict.fromkeys(files))