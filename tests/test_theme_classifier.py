"""SSOT体系化 承認スキーマ自動化 Phase0: theme_classifier のテスト（TDD）.

spec: docs/superpowers/specs/2026-07-25-ssot-approval-schema-automation-design.md
Phase0 = dry-run検証。本テストは純粋関数（LLM出力パース・マッピング・採用率集計）を扱う。
LLM呼び出し（_classify_file_themes）は別途モックテスト（T4）。
"""
from __future__ import annotations

from scripts.obsidian.theme_classifier import (
    _parse_llm_themes,
    _map_to_existing,
    compute_adoption_rate,
)


# ============ T1: _parse_llm_themes ============

class TestParseLlmThemes:
    """Gemini 出力（JSON or JSONブロック）を {themes, confidence} にパース."""

    def test_plain_json(self) -> None:
        raw = '{"themes": ["環境自動化・基本ツール", "セキュリティ"], "confidence": 0.85}'
        result = _parse_llm_themes(raw)
        assert result["themes"] == ["環境自動化・基本ツール", "セキュリティ"]
        assert result["confidence"] == 0.85

    def test_json_code_block(self) -> None:
        raw = '```json\n{"themes": ["A", "B"], "confidence": 0.7}\n```'
        result = _parse_llm_themes(raw)
        assert result["themes"] == ["A", "B"]
        assert result["confidence"] == 0.7

    def test_json_with_surrounding_text(self) -> None:
        raw = '結果は以下です:\n{"themes": ["X"], "confidence": 0.9}\n以上。'
        result = _parse_llm_themes(raw)
        assert result["themes"] == ["X"]
        assert result["confidence"] == 0.9

    def test_no_confidence_defaults_to_half(self) -> None:
        raw = '{"themes": ["A"]}'
        result = _parse_llm_themes(raw)
        assert result["themes"] == ["A"]
        assert result["confidence"] == 0.5

    def test_empty_returns_empty_zero_confidence(self) -> None:
        result = _parse_llm_themes("")
        assert result["themes"] == []
        assert result["confidence"] == 0.0

    def test_whitespace_trimmed(self) -> None:
        raw = '{"themes": ["  A  ", "B"], "confidence": 0.6}'
        result = _parse_llm_themes(raw)
        assert result["themes"] == ["A", "B"]
