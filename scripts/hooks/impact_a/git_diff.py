"""impact-a: git diff パーサ + 語彙マッチ・category enum 正規化（spec §4.2）"""
import re
from typing import Final


# category enum（spec §4.2 M3反映・silent mismatch 防止）
VALID_CATEGORIES: Final[frozenset[str]] = frozenset({
    "safety-net-change",
    "data-mutation",
    "schema-change",
    "secret-handling",
    "permission-scope",
    "build-config-change",
})


def parse_unified_zero_diff(diff: str) -> list[str]:
    """`git diff --unified=0` の出力から追加行のみ抽出する。"""
    adds: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            adds.append(line[1:])
    return adds


def match_keywords(lines: list[str], keywords: list[str]) -> list[str]:
    """各行に対し、keywords のいずれかが大文字小文字無視で含まれれば、そのキーワードを返す。"""
    keywords_lower = [k.lower() for k in keywords]
    matches: list[str] = []
    for line in lines:
        line_lower = line.lower()
        for k, k_lower in zip(keywords, keywords_lower):
            if k_lower in line_lower:
                matches.append(k)
    return matches


def normalize_category(cat: str) -> str | None:
    """VALID_CATEGORIES に含まれる場合のみ正規化済み文字列を返す。それ以外は None。"""
    return cat if cat in VALID_CATEGORIES else None
