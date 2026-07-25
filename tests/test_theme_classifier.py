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
    _classify_file_themes,
    _load_approved_themes,
    run_dry_run,
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


# ============ T2: _map_to_existing（spec§4 マッピング戦略） ============

class TestMapToExisting:
    """推論テーマを既存 approved_themes にマップ（一致/類似→matched / 新規→new）."""

    def test_exact_match(self) -> None:
        approved = ["環境自動化・基本ツール", "セキュリティ"]
        result = _map_to_existing(["セキュリティ"], approved)
        assert result["matched"] == ["セキュリティ"]
        assert result["new"] == []

    def test_new_theme(self) -> None:
        result = _map_to_existing(["全く新しいテーマ"], ["A", "B"])
        assert result["matched"] == []
        assert result["new"] == ["全く新しいテーマ"]

    def test_partial_match_maps_to_existing(self) -> None:
        # proposed="環境自動化" は approved="環境自動化・基本ツール" に包含→既存マップ
        approved = ["環境自動化・基本ツール"]
        result = _map_to_existing(["環境自動化"], approved)
        assert result["matched"] == ["環境自動化・基本ツール"]
        assert result["new"] == []

    def test_mixed_matched_and_new(self) -> None:
        approved = ["環境自動化・基本ツール", "セキュリティ"]
        result = _map_to_existing(["セキュリティ", "新規X"], approved)
        assert result["matched"] == ["セキュリティ"]
        assert result["new"] == ["新規X"]

    def test_empty_proposed_returns_empty(self) -> None:
        result = _map_to_existing([], ["A"])
        assert result["matched"] == []
        assert result["new"] == []

    def test_dedup_matched(self) -> None:
        approved = ["セキュリティ"]
        # 2つの推論が同一既存テーマにマップ→重複しない
        result = _map_to_existing(["セキュリティ", "セキュリティ"], approved)
        assert result["matched"] == ["セキュリティ"]


# ============ T3: compute_adoption_rate（spec§3.1 ゲート≥90%） ============

class TestComputeAdoptionRate:
    """matched 1件以上のファイル比率 = 採用率（Phase0ゲート基準値）."""

    def test_all_matched(self) -> None:
        results = [{"matched": ["A"], "new": []}, {"matched": ["B"], "new": []}]
        assert compute_adoption_rate(results) == 1.0

    def test_none_matched(self) -> None:
        results = [{"matched": [], "new": ["X"]}, {"matched": [], "new": ["Y"]}]
        assert compute_adoption_rate(results) == 0.0

    def test_half(self) -> None:
        results = [{"matched": ["A"], "new": []}, {"matched": [], "new": ["X"]}]
        assert compute_adoption_rate(results) == 0.5

    def test_empty_results(self) -> None:
        assert compute_adoption_rate([]) == 0.0

    def test_empty_matched_counts_as_unadopted(self) -> None:
        # 提案なしファイル（matched/new 共に空）は不採用として分母へ
        results = [{"matched": ["A"], "new": []}, {"matched": [], "new": []}]
        assert compute_adoption_rate(results) == 0.5


# ============ T4: _classify_file_themes（Gemini呼び出し・モック） ============

class TestClassifyFileThemes:
    """ファイル→Gemini分類→マップ。_call_gemini を monkeypatch でモック."""

    def test_matched_theme(self, tmp_path, monkeypatch) -> None:
        f = tmp_path / "2026-07-20_test.md"
        f.write_text("# 決定\nセキュリティ関連の設定変更")
        monkeypatch.setattr(
            "scripts.obsidian.theme_classifier._call_gemini",
            lambda p: '{"themes": ["セキュリティ"], "confidence": 0.9}',
        )
        result = _classify_file_themes(f, ["セキュリティ", "環境自動化"])
        assert result["matched"] == ["セキュリティ"]
        assert result["new"] == []
        assert result["confidence"] == 0.9

    def test_new_theme_flagged(self, tmp_path, monkeypatch) -> None:
        f = tmp_path / "test.md"
        f.write_text("内容")
        monkeypatch.setattr(
            "scripts.obsidian.theme_classifier._call_gemini",
            lambda p: '{"themes": ["全く新しいテーマ"], "confidence": 0.6}',
        )
        result = _classify_file_themes(f, ["A"])
        assert result["matched"] == []
        assert result["new"] == ["全く新しいテーマ"]

    def test_low_confidence_keeps_result_for_review(self, tmp_path, monkeypatch) -> None:
        # confidence < 閾値でも結果は返す（上位で要確認判定・spec§6）
        f = tmp_path / "test.md"
        f.write_text("内容")
        monkeypatch.setattr(
            "scripts.obsidian.theme_classifier._call_gemini",
            lambda p: '{"themes": ["A"], "confidence": 0.3}',
        )
        result = _classify_file_themes(f, ["A"])
        assert result["matched"] == ["A"]
        assert result["confidence"] == 0.3
        assert result["needs_review"] is True


# ============ T5: _load_approved_themes / run_dry_run ============

class TestLoadApprovedThemes:
    """_INDEX.md frontmatter の approved_themes（[A, B] 形式）をリスト化."""

    def test_parse_bracket_list(self, tmp_path) -> None:
        idx = tmp_path / "_INDEX.md"
        idx.write_text("---\nproject: demo\napproved_themes: [A, B, C]\n---\n本文")
        assert _load_approved_themes(idx) == ["A", "B", "C"]

    def test_empty_when_missing(self, tmp_path) -> None:
        idx = tmp_path / "_INDEX.md"
        idx.write_text("---\nproject: demo\n---\n本文")
        assert _load_approved_themes(idx) == []

    def test_no_frontmatter(self, tmp_path) -> None:
        idx = tmp_path / "_INDEX.md"
        idx.write_text("本文のみ")
        assert _load_approved_themes(idx) == []


class TestRunDryRun:
    """dry-run: フォルダ走査→全ファイル分類→採用率集計（承認せず）."""

    def test_collects_adoption_rate(self, tmp_path, monkeypatch) -> None:
        proj = tmp_path / "01_DECISIONS" / "demo"
        proj.mkdir(parents=True)
        (proj / "2026-01-01_a.md").write_text("内容A")
        (proj / "2026-01-02_b.md").write_text("内容B")
        (proj / "_INDEX.md").write_text("---\napproved_themes: [テーマA]\n---\n")
        monkeypatch.setattr(
            "scripts.obsidian.theme_classifier._call_gemini",
            lambda p: '{"themes": ["テーマA"], "confidence": 0.9}',
        )
        result = run_dry_run("demo", ssot_root=tmp_path)
        assert result["total"] == 2
        assert result["adoption_rate"] == 1.0
        assert result["approved"] == ["テーマA"]

    def test_half_adoption(self, tmp_path, monkeypatch) -> None:
        proj = tmp_path / "01_DECISIONS" / "demo"
        proj.mkdir(parents=True)
        (proj / "a.md").write_text("A")
        (proj / "b.md").write_text("B")
        (proj / "_INDEX.md").write_text("---\napproved_themes: [既存]\n---\n")
        responses = iter([
            '{"themes": ["既存"], "confidence": 0.9}',
            '{"themes": ["新規X"], "confidence": 0.6}',
        ])
        monkeypatch.setattr(
            "scripts.obsidian.theme_classifier._call_gemini",
            lambda p: next(responses),
        )
        result = run_dry_run("demo", ssot_root=tmp_path)
        assert result["total"] == 2
        assert result["adoption_rate"] == 0.5

    def test_skips_index_file(self, tmp_path, monkeypatch) -> None:
        proj = tmp_path / "01_DECISIONS" / "demo"
        proj.mkdir(parents=True)
        (proj / "2026-01-01_a.md").write_text("A")
        (proj / "_INDEX.md").write_text("---\napproved_themes: [X]\n---\n")
        monkeypatch.setattr(
            "scripts.obsidian.theme_classifier._call_gemini",
            lambda p: '{"themes": ["X"], "confidence": 0.9}',
        )
        result = run_dry_run("demo", ssot_root=tmp_path)
        # _INDEX.md は分類対象外
        assert result["total"] == 1
