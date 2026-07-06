"""フェーズ0: タスク prompt から目的文と KPI を抽出する。

プロンプト規約: '[OBJECTIVE] <目的文>' または '[OBJECTIVE] <目的文> [KPI] <KPI文>'

auto-dev/run-task.sh のフェーズ0 から呼び出され、抽出した目的文と KPI を
以降のフェーズ（drift 検知・task_logger）へ渡す責務を担う。
"""
from __future__ import annotations

import re
from typing import Optional

OBJECTIVE_MARKER = re.compile(r"\[OBJECTIVE\]\s*(.+?)(?:\s*\[KPI\]\s*(.+))?$", re.DOTALL)


def extract_objective(prompt: str) -> str:
    """prompt から目的文を抽出する。

    [OBJECTIVE] マーカーがあればマーカー後のテキストを返す。
    無ければ prompt 全体を返す。
    """
    match = OBJECTIVE_MARKER.search(prompt)
    if match:
        return match.group(1).strip()
    return prompt.strip()


def parse_kpi(prompt: str) -> Optional[dict]:
    """prompt から KPI を数値として抽出する。

    Returns:
        dict: {value, unit, direction} または None（KPI が無い/解析不可な場合）
    """
    match = OBJECTIVE_MARKER.search(prompt)
    if not match or not match.group(2):
        # マーカー無しでも KPI 文が含まれるか簡易チェック
        kpi_match = re.search(r"KPI[はは]?\s*(\d+(?:\.\d+)?)\s*(\S+)", prompt)
        if not kpi_match:
            return None
        value = float(kpi_match.group(1))
        unit = kpi_match.group(2)
    else:
        kpi_text = match.group(2)
        kpi_match = re.search(r"(\d+(?:\.\d+)?)\s*(\S+?)(?:以上|超|>=|>|以下|未満|<=|<)?", kpi_text)
        if not kpi_match:
            return None
        value = float(kpi_match.group(1))
        unit = kpi_match.group(2)

    # direction 判定
    direction = "gte"  # デフォルト
    if any(kw in prompt for kw in ["以下", "未満", "<=", "<"]):
        direction = "lte"

    return {"value": value, "unit": unit, "direction": direction}