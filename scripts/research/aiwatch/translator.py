"""translator — MiniMax API でリポ description を日本語1行に翻訳。

Phase2 先取り（description 翻訳のみ・評価の fit_star は引き続き rule 採点）。
MiniMax 失敗/空応答時は英語フォールバック（ガイド生成は継続）。

設計（spec 2026-08-11-ai-repo-watch-b-ssot-design.md #6 フォールバック準拠）:
  - 全リポを1リクエストにまとめて翻訳（コスト削減・一貫性）
  - JSON {"owner/repo": "日本語説明"} で構造化出力
  - usage トークンを返し cost.py で週$20キャップ対象に
"""
import json
import os

from aiwatch.models import RepoStats

MINIMAX_URL = "https://api.minimax.io/anthropic/v1/messages"
MINIMAX_MODEL = "MiniMax-M2.7"


def build_prompt(items: list[tuple[str, str]]) -> str:
    """翻訳プロンプトを構築する。

    items: [(name, english_desc), ...]
    各リポについて summary(1行) / detail(技術者向け詳説) / plain(素人向け平易) の3フィールドを生成。
    """
    body = "\n".join(f"- {name}: {desc}" for name, desc in items)
    return (
        "以下のGitHubリポジトリの英語説明文を基に、各リポについて3つの日本語説明を作成してください。\n"
        "1. summary: 日本語の概要1行（30字程度・英語を日本語に翻訳・要約・英語のまま出力しない）\n"
        "2. detail: 技術者向けの詳しい説明（何ができるか2-3文・技術用語は残してOK）\n"
        "3. plain: 素人向けの平易な説明（日常語・身近な例えを含む2文程度・技術用語は避ける）\n\n"
        "すべての項目を必ず日本語で出力してください。英語のままの出力は禁止です。\n"
        'JSONオブジェクト {"owner/repo": {"summary":"...", "detail":"...", "plain":"..."}} のみを出力してください。\n\n'
        f"{body}"
    )


def parse_translation_json(text: str) -> dict[str, dict]:
    """LLM応答テキストから JSON を抽出して返す（前後の文言/コードブロック許容）。

    戻り値: {name: {"summary":..., "detail":..., "plain":...}}
    旧形式（値が文字列）は summary のみ設定（後方互換）。
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        parsed = json.loads(text[start:end + 1])
        if not isinstance(parsed, dict):
            return {}
    except (json.JSONDecodeError, ValueError):
        return {}
    result: dict[str, dict] = {}
    for k, v in parsed.items():
        if isinstance(v, dict):
            result[str(k)] = {
                "summary": str(v.get("summary", "")),
                "detail": str(v.get("detail", "")),
                "plain": str(v.get("plain", "")),
            }
        elif isinstance(v, str):
            result[str(k)] = {"summary": v, "detail": "", "plain": ""}
    return result


def translate_descriptions(
    repos: list[RepoStats],
    api_key: str | None = None,
    url: str = MINIMAX_URL,
    model: str = MINIMAX_MODEL,
    timeout: int = 60,
    requester=None,
) -> tuple[dict[str, str], dict]:
    """description を日本語翻訳する。

    戻り値: ({name: japanese_desc}, usage_stats)
    usage_stats: {tokens_in, tokens_out, ok}
    失敗時は ({}, {tokens_in:0, tokens_out:0, ok:False}) で英語フォールバック暗示。
    requester はテスト用 mock（requests.post 互換）。
    """
    import requests

    key = api_key or os.environ.get("MINIMAX_API_KEY", "")
    items = [(r.name, r.description) for r in repos if r.description]
    if not items or not key:
        return {}, {"tokens_in": 0, "tokens_out": 0, "ok": False}

    post = requester or requests.post
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": build_prompt(items)}],
    }
    try:
        resp = post(url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return {}, {"tokens_in": 0, "tokens_out": 0, "ok": False}

    text = "".join(
        b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
    )
    usage = data.get("usage", {})
    tokens_in = usage.get("input_tokens", 0)
    tokens_out = usage.get("output_tokens", 0)
    mapping = parse_translation_json(text)
    return mapping, {
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "ok": bool(mapping),
    }
