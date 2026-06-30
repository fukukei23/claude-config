"""tool_use リクエストのフォールバック先向けサニタイザ。

GLM が thinking+tool_use を返した際、会話履歴の再構築で tool_use が欠落し
tool_result だけ残る（orphan）ケースが確認されている（400 エラー: tool id not found）。
thinking ブロックは MiniMax が非対応のため除去する。
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def sanitize_for_minimax(body: bytes) -> bytes:
    """Messages API リクエストを minimax 互換の形式に変換する。"""
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

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        _normalize_message_content(msg)

    _reconcile_tool_pairs(messages)

    # MiniMax は top-level thinking パラメータ非対応
    data.pop("thinking", None)

    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def _normalize_message_content(msg: dict[str, Any]) -> None:
    """1つの message の content を minimax 形式に正規化する。"""
    content = msg.get("content")
    if not isinstance(content, list):
        return

    # assistant メッセージの thinking ブロックを除去（MiniMax 非対応）
    if msg.get("role") == "assistant":
        original_len = len(content)
        content = [b for b in content if not (isinstance(b, dict) and b.get("type") == "thinking")]
        if len(content) != original_len:
            logger.debug(f"_normalize_message_content: stripped {original_len - len(content)} thinking block(s)")
        msg["content"] = content

    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")

        if btype == "tool_use":
            if "id" in block and "tool_call_id" not in block:
                block["tool_call_id"] = block["id"]

        elif btype == "tool_result":
            if "tool_use_id" not in block and "tool_call_id" in block:
                block["tool_use_id"] = block["tool_call_id"]
            elif "tool_use_id" not in block and "id" in block:
                block["tool_use_id"] = block["id"]

            if isinstance(block.get("content"), str):
                block["content"] = [{"type": "text", "text": block["content"]}]


def _reconcile_tool_pairs(messages: list[dict[str, Any]]) -> None:
    """orphan tool_result（対応する tool_use が無い）を除去する。

    孤立 tool_result をそのまま送ると 400 エラー
    "invalid params, tool result's tool id(...) not found (2013)" が発生するため除去。
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

    orphan_results = tool_result_ids - tool_use_ids
    if not orphan_results:
        return

    logger.warning(
        f"sanitize_for_minimax: removing {len(orphan_results)} orphan tool_result(s) "
        f"without matching tool_use: {sorted(orphan_results)[:3]}..."
    )

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        new_content = [
            b for b in content
            if not (
                isinstance(b, dict)
                and b.get("type") == "tool_result"
                and (b.get("tool_use_id") or b.get("tool_call_id")) in orphan_results
            )
        ]
        if len(new_content) != len(content):
            msg["content"] = new_content
