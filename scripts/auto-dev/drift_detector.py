"""フェーズ6: ズレ検知（v1 はルールベース + KPI 数値評価のみ）。

v2 タスク: Embedding + コサイン類似度の導入（API キー取得後）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class DriftResult:
    drifted: bool
    reason: str
    kpi_value: Optional[float] = None


def detect_drift(
    review_summary: str,
    objective: str,
    kpi: Optional[dict],
) -> DriftResult:
    """ズレ検知 v1（ルールベース + KPI 数値評価）。

    判定ロジック:
    1. KPI が数値で指定されている場合: review_summary から数値抽出 → 達成判定
    2. KPI が無い場合: objective のキーワードが review_summary に含まれているか
    """
    # 1. KPI 数値評価
    if kpi:
        kpi_value = _extract_kpi_value(review_summary, kpi["unit"])
        if kpi_value is not None:
            target = kpi["value"]
            unit = kpi["unit"]
            if kpi["direction"] == "gte":
                drifted = kpi_value < target
                return DriftResult(
                    drifted=drifted,
                    reason=f"KPI未達: 実績 {kpi_value}{unit} < 目標 {target}{unit}"
                    if drifted
                    else f"KPI達成: {kpi_value}{unit}",
                    kpi_value=kpi_value,
                )
            else:  # lte
                drifted = kpi_value > target
                return DriftResult(
                    drifted=drifted,
                    reason=f"KPI超過: 実績 {kpi_value}{unit} > 上限 {target}{unit}"
                    if drifted
                    else f"KPI達成: {kpi_value}{unit}",
                    kpi_value=kpi_value,
                )

    # 2. キーワード含有チェック
    obj_keywords = _tokenize_keywords(objective)
    review_text = review_summary
    missing = [kw for kw in obj_keywords if kw not in review_text]

    if obj_keywords and len(missing) == len(obj_keywords):
        return DriftResult(
            drifted=True,
            reason=f"objective のキーワードが review に含まれない: {obj_keywords}",
        )

    return DriftResult(drifted=False, reason="objective キーワード一致")


def _extract_kpi_value(text: str, unit: str) -> Optional[float]:
    """review_summary テキストから <数値><unit> を抽出する。"""
    pattern = rf"(\d+(?:\.\d+)?)\s*{re.escape(unit)}"
    match = re.search(pattern, text)
    if match:
        return float(match.group(1))
    return None


def _tokenize_keywords(objective: str) -> list[str]:
    """objective から重要なキーワードを抽出（漢字 2 文字以上 + 英単語 3 文字以上）。"""
    kanji = re.findall(r"[一-鿿]{2,}", objective)
    ascii_words = re.findall(r"[A-Za-z0-9_]{3,}", objective)
    return kanji + ascii_words
