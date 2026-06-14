"""Tool-use format sanitizer for GLM→MiniMax conversion."""

import json
import logging

logger = logging.getLogger("glm-rate-proxy")


def sanitize_for_minimax(body: bytes) -> bytes:
    """Convert GLM tool_use format to MiniMax-compatible format.

    GLM format:
    - messages[].content = [{"type": "tool_use", "id": "...", "name": "...", "input": {...}}]

    MiniMax format:
    - Need to convert to tool_calls array in assistant message
    - Or inline tool_use blocks

    This is a NO-OP for now because MiniMax tool_use format is compatible.
    Future work: detect GLM-specific features and convert to MiniMax equivalents.
    """
    # Check if body contains tool_use
    try:
        data = json.loads(body)
        messages = data.get("messages", [])

        has_tool_use = any(
            isinstance(msg, dict)
            and isinstance(msg.get("content"), list)
            and any(isinstance(c, dict) and c.get("type") == "tool_use" for c in msg["content"])
            for msg in messages
        )

        if not has_tool_use:
            # No tool_use to sanitize, return as-is
            return body

        logger.debug("sanitize_for_minimax: tool_use detected but currently no conversion needed")
        return body

    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"sanitize_for_minimax: JSON parse failed ({e}), returning body as-is")
        return body


# For backward compatibility during transition
def sanitize_response(response_body: bytes) -> bytes:
    """Sanitize upstream response body (if needed)."""
    return sanitize_for_minimax(response_body)
