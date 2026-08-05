"""SSOT体系化 承認スキーマ自動化 Phase2 最小観測(A‴′): theme_observer のテスト(TDD).

spec: docs/superpowers/specs/2026-07-25-ssot-approval-schema-automation-design.md §7.1
A‴′ = 01_DECISIONSへの新規ファイル追加時だけ dry-run 自動発火 → 通知/ログ。
LLM呼出(run_dry_run)は依存注入でモック置換(_classify_file_themes は呼ばない)。
"""
from __future__ import annotations

import json

from scripts.obsidian.theme_observer import (
    detect_new_decision_files,
    log_observation,
    run_observation,
)


# ============ T1: detect_new_decision_files ============

class TestDetectNewDecisionFiles:
    """git diff --name-only --diff-filter=A の出力から新規 01_DECISIONS ファイルを抽出."""

    def test_single_new_file(self) -> None:
        diff = "01_DECISIONS/claude-code/2026-08-06_test.md"
        assert detect_new_decision_files(diff) == [("claude-code", "2026-08-06_test.md")]

    def test_multiple_files_different_projects(self) -> None:
        diff = "01_DECISIONS/claude-code/a.md\n01_DECISIONS/NexusCore/b.md"
        result = detect_new_decision_files(diff)
        assert ("claude-code", "a.md") in result
        assert ("NexusCore", "b.md") in result
        assert len(result) == 2

    def test_exclude_index_md(self) -> None:
        diff = "01_DECISIONS/claude-code/_INDEX.md\n01_DECISIONS/claude-code/new.md"
        assert detect_new_decision_files(diff) == [("claude-code", "new.md")]

    def test_ignore_non_decision_paths(self) -> None:
        diff = "10_DAILY/2026-08-06.md\n00_SYSTEM/バックログ.md\nREADME.md"
        assert detect_new_decision_files(diff) == []

    def test_empty_input(self) -> None:
        assert detect_new_decision_files("") == []

    def test_strips_whitespace(self) -> None:
        diff = "  01_DECISIONS/claude-code/x.md  \n"
        assert detect_new_decision_files(diff) == [("claude-code", "x.md")]

    def test_only_md_files(self) -> None:
        diff = "01_DECISIONS/claude-code/notes.txt\n01_DECISIONS/claude-code/real.md"
        assert detect_new_decision_files(diff) == [("claude-code", "real.md")]


# ============ T2: run_observation ============

class TestRunObservation:
    """dry-run 発火 → 新規テーマ候補抽出(依存注入でGeminiをモック)."""

    def test_extracts_new_themes(self) -> None:
        def mock_dry(project: str, ssot_root=None) -> dict:
            return {
                "per_file": [
                    {"file": "a.md", "new": ["新テーマ1"], "matched": []},
                    {"file": "b.md", "new": [], "matched": ["既存テーマ"]},
                ],
                "adoption_rate": 0.5,
                "total": 2,
                "approved": [],
            }

        result = run_observation("test-pj", dry_run_fn=mock_dry)
        assert result["new_themes"] == ["新テーマ1"]
        assert result["file_count"] == 2
        assert result["adoption_rate"] == 0.5
        assert result["project"] == "test-pj"
        assert "timestamp" in result

    def test_no_new_themes(self) -> None:
        def mock_dry(project: str, ssot_root=None) -> dict:
            return {
                "per_file": [{"file": "a.md", "new": [], "matched": ["既存"]}],
                "adoption_rate": 1.0,
                "total": 1,
                "approved": ["既存"],
            }

        result = run_observation("pj", dry_run_fn=mock_dry)
        assert result["new_themes"] == []
        assert result["adoption_rate"] == 1.0

    def test_dedup_new_themes(self) -> None:
        def mock_dry(project: str, ssot_root=None) -> dict:
            return {
                "per_file": [
                    {"file": "a.md", "new": ["X", "Y"], "matched": []},
                    {"file": "b.md", "new": ["Y", "Z"], "matched": []},
                ],
                "adoption_rate": 0.0,
                "total": 2,
                "approved": [],
            }

        result = run_observation("pj", dry_run_fn=mock_dry)
        assert result["new_themes"] == ["X", "Y", "Z"]


# ============ T3: log_observation ============

class TestLogObservation:
    """観測ログ(JSON Lines)追記."""

    def test_appends_jsonl(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        log = tmp_path / "obs.jsonl"
        entry1 = {"project": "a", "new_themes": ["x"]}
        entry2 = {"project": "b", "new_themes": []}
        log_observation(log, entry1)
        log_observation(log, entry2)
        lines = log.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == entry1
        assert json.loads(lines[1]) == entry2

    def test_creates_parent_dir(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        log = tmp_path / "subdir" / "obs.jsonl"
        log_observation(log, {"project": "a"})
        assert log.exists()

    def test_unicode_preserved(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        log = tmp_path / "obs.jsonl"
        entry = {"project": "pj", "new_themes": ["日本語テーマ"]}
        log_observation(log, entry)
        content = log.read_text(encoding="utf-8")
        assert "日本語テーマ" in content
