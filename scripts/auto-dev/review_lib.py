"""multi-llm-review ロジックの Python 関数化（auto-loop から呼出用）。

元: ~/.claude/skills/multi-llm-review/SKILL.md

auto-dev/run-task.sh から呼び出して、レビュアー LLM の出力テキストを
構造化データ（dict）へ正規化する役割を担う。

Phase 2/5 有効化（2026-08-12）:
- run_multi_llm_review() — Gemini + MiniMax の別ベンダー並列レビュー
- backend_kind 必須引数で「どの経路でどのベンダーを呼んだか」を判別
- 判定 3 値（両critical/片側critical+片側silent/両側critical未満）
- ベンダー数 < 2 は即 abort（多様性保証不能）
- API キー値のログ漏洩をマスク
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

SEVERITY_MAP: dict[str, str] = {
    "critical": "critical",
    "high": "high",
    "med": "med",
    "medium": "med",
    "low": "low",
}


def extract_json_from_text(text: str) -> dict[str, Any]:
    """テキスト内の JSON オブジェクトを抽出する。

    戦略: ```json ... ``` フェンス優先 → なければ {...} を greedy match。
    配列/プリミティブは対象外（このプロジェクトのレビュー出力は常にオブジェクト）。

    Raises:
        ValueError: オブジェクトとして解釈できる JSON が text 中に無い場合。
    """
    if not isinstance(text, str):
        raise ValueError("JSON object not found in text")

    # 1. コードフェンス（言語指定あり/なし両対応・非 greedy で最短一致）
    fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if fence_match:
        candidate = fence_match.group(1)
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # 2. greedy {...}（ネスト考慮・最初の { から対応する } まで）
    brace_start = text.find("{")
    if brace_start == -1:
        raise ValueError("JSON object not found in text")

    depth = 0
    end_index = -1
    for i in range(brace_start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end_index = i
                break

    if end_index == -1:
        raise ValueError("JSON object not found in text")

    candidate = text[brace_start : end_index + 1]
    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError("JSON object not found in text") from exc

    if not isinstance(obj, dict):
        raise ValueError("JSON object not found in text")

    return obj


def normalize_severity(severity: str) -> str:
    """severity 表記を critical/high/med/low のいずれかに正規化する。

    未知の値・大文字小文字の揺れ・空文字列はすべて 'low' にフォールバック
    （安全側：誤って高く評価しない）。
    """
    if not severity:
        return "low"
    return SEVERITY_MAP.get(severity.strip().lower(), "low")


def classify_review_item(review: str, objective: str) -> str:
    """レビュー指摘を目的関連性で 3 tier に分類する。

    - direct: objective のキーワードが review 内に直接出現
    - meta:   objective のキーワードは出ないが、何らかの指摘（レビュー作法等）
    - offtopic: 完全無関係（タイポ修正等・極端に短い or objective と被りなし）

    Args:
        review: レビュアーが生成した指摘テキスト。
        objective: 開発タスクの目的（例: 'メールバリデーション関数をRFC準拠にする'）。

    Returns:
        'direct' / 'meta' / 'offtopic' のいずれか。
    """
    obj_keywords = set(_tokenize(objective))
    rev_keywords = set(_tokenize(review))

    if obj_keywords & rev_keywords:
        return "direct"

    # meta: 何かしらの指摘はある（10 文字以上・トークンが1つ以上）
    if len(review) >= 10 and rev_keywords:
        return "meta"

    return "offtopic"


def _tokenize(text: str) -> list[str]:
    """簡易トークナイザ。

    - 漢字 + カタカナ連続スパン内の 2 文字スライディング substring
      （re.findall(r"[一-鿿]{2,}", text) は non-overlapping greedy なので
       "メールバリデーション関数" のように ASCII をまたぐ長い塊を扱えない。
       そこでカタカナ含めたスパンごとに 2 文字部分文字列を抽出する）
    - 英数字 3 文字以上の単語

    仕様書で示された "漢字 2 文字以上 + 英単語 3 文字以上" のセマンティクスを
    「スパン内 2 文字オーバーラップ substring」として実装する。これにより
    「メールバリデーション」と「バリデーション」のように塊の開始位置が
    異なるケースでも、共通する "バリデーション" 等の部分文字列を検出できる。

    注: カタカナ（ァ-ヴー）を含める理由は「メ」「ー」「ル」「バ」「リ」
    等がカタカナであり、漢字スパンだけでは "メールバリデーション" を
    1 つの塊として扱えないため。漢字のみ/カタカナのみ/混在いずれも対応。
    """
    import re
    # 1. 漢字+カタカナ連続スパン（1 文字以上の連続）を全て取得
    cjk_spans = re.findall(r"[一-鿿ァ-ヴー]+", text)
    # 2. 各スパン内の 2 文字スライディング substring
    cjk_subs: list[str] = []
    for span in cjk_spans:
        for i in range(len(span) - 1):
            cjk_subs.append(span[i] + span[i + 1])
    # 3. 英数字 3 文字以上の単語
    ascii_words = re.findall(r"[A-Za-z0-9_]{3,}", text)
    return cjk_subs + ascii_words