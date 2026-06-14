"""tool_use リクエストのフォールバック先向けサニタイザ。

GLM (minimax API) と minimax (minimax 本社) の anthropic-compatible Messages API は
tool_use / tool_result 形式が微妙に違う:

  - GLM: content 内に {"type": "tool_use", "id": "call_xxx", "name": ..., "input": ...}
        に対し、tool_result は {"type": "tool_result", "tool_use_id": "call_xxx", ...}
  - minimax: id プレフィックスや、tool_result.content が「配列でなければならない」
            など、GLMより厳格な箇所がある

実観測した 400 エラー:
    "invalid params, tool result's tool id(call_76ce548bb4394b49a1e9e881) not found (2013)"

原因: tool_result に渡された tool_use_id が、対応する tool_use ブロックの id と一致しない
      （= IDフォーマット不一致 / 順序が壊れている / message 境界が壊れている）

このモジュールは anthropic Messages API の JSON を受け取り、minimax 互換の形式へ
サニタイズして返す。GLM 向けにはそのまま通す（破壊的変更を避けるため）。
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def sanitize_for_minimax(body: bytes) -> bytes:
    """Messages API リクエストを minimax (minimax-M3) 互換の形式に変換する。

    Args:
        body: anthropic /v1/messages への POST body (JSON bytes)

    Returns:
        sanitized body (JSON bytes)

    Note:
        パースに失敗したら元 body をそのまま返す（安全側）。
    """
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        logger.debug(f"sanitize_for_minimax: non-JSON body, passthrough ({e})")
        return body

    if not isinstance(data, dict):
        return body

    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        return body

    # 1) 各 message の content ブロックを正規化
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        _normalize_message_content(msg)

    # 2) tool_use ↔ tool_result の対応整合性をチェック & 修復
    _reconcile_tool_pairs(messages)

    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def _normalize_message_content(msg: dict[str, Any]) -> None:
    """1つの message の content を minimax 形式に正規化する。"""
    content = msg.get("content")
    if not isinstance(content, list):
        return  # 文字列 content は触らない

    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")

        if btype == "tool_use":
            # GLM は id のみ、minimax は id/tool_call_id どちらでも受け付ける
            # が、tool_result 側の tool_use_id と一致する必要がある
            if "id" in block and "tool_call_id" not in block:
                block["tool_call_id"] = block["id"]

        elif btype == "tool_result":
            # minimax は tool_use_id を必須とする（GLM と同じ名前のはずだが念のため）
            if "tool_use_id" not in block and "tool_call_id" in block:
                block["tool_use_id"] = block["tool_call_id"]
            elif "tool_use_id" not in block and "id" in block:
                block["tool_use_id"] = block["id"]

            # content が文字列の場合、配列にラップ（minimax は配列を要求）
            if isinstance(block.get("content"), str):
                block["content"] = [{"type": "text", "text": block["content"]}]


def _reconcile_tool_pairs(messages: list[dict[str, Any]]) -> None:
    """assistant が出した tool_use id と user の tool_result.tool_use_id が
    きちんと対応しているか確認し、壊れていればログを残す。

    自動修復はしない（破壊的変更リスクが高いため）— ログだけ出して、
    残りは upstream が 400 を返すことで可視化する。
    """
    tool_use_ids: set[str] = set()
    tool_result_ids: set[str] = set()

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                bid = block.get("id") or block.get("tool_call_id")
                if bid:
                    tool_use_ids.add(bid)
            elif block.get("type") == "tool_result":
                bid = block.get("tool_use_id") or block.get("tool_call_id")
                if bid:
                    tool_result_ids.add(bid)

    # 孤立した tool_result（対応する tool_use が無い）を検出
    orphan_results = tool_result_ids - tool_use_ids
    if orphan_results:
        logger.warning(
            f"sanitize_for_minimax: {len(orphan_results)} orphan tool_result(s) "
            f"without matching tool_use: {sorted(orphan_results)[:3]}..."
        )
