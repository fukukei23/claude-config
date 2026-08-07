"""count_unindexed_markers.py の単体テスト（SSOT体系化 P3-C: 未消化マーカー集計）."""
from pathlib import Path

from scripts.obsidian.count_unindexed_markers import (
    MARKER,
    count_unindexed_markers,
)


def _write_index(path: Path, content: str) -> None:
    """テスト用 _INDEX.md を生成."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_count_single_project_multiple_markers(tmp_path):
    """単一PJ: 【要更新】複数 → by_project + total に集計."""
    _write_index(
        tmp_path / "01_DECISIONS" / "proj" / "_INDEX.md",
        f"| file_a.md | タイトルA {MARKER} | — |\n"
        f"| file_b.md | タイトルB {MARKER} | — |\n",
    )
    result = count_unindexed_markers(tmp_path)
    assert result.total == 2
    assert result.by_project == {"proj": 2}


def test_count_multiple_projects_mixed(tmp_path):
    """複数PJ: マーカー有/無混在 → マーカー有PJのみ集計."""
    _write_index(
        tmp_path / "01_DECISIONS" / "has_markers" / "_INDEX.md",
        f"| a.md | title {MARKER} | — |\n",
    )
    _write_index(
        tmp_path / "01_DECISIONS" / "no_markers" / "_INDEX.md",
        "| b.md | 完了タイトル | — |\n",
    )
    result = count_unindexed_markers(tmp_path)
    assert result.total == 1
    assert result.by_project == {"has_markers": 1}
    assert "no_markers" not in result.by_project


def test_count_zero_when_all_digested(tmp_path):
    """全PJ消化済み（マーカー0）→ total=0, by_project={}."""
    _write_index(
        tmp_path / "01_DECISIONS" / "proj" / "_INDEX.md",
        "| a.md | 完了 | — |\n",
    )
    result = count_unindexed_markers(tmp_path)
    assert result.total == 0
    assert result.by_project == {}


def test_count_skips_project_without_index(tmp_path):
    """_INDEX.md 無PJ → 集計から除外（エラーなく）."""
    (tmp_path / "01_DECISIONS" / "no_index").mkdir(parents=True)
    _write_index(
        tmp_path / "01_DECISIONS" / "with_index" / "_INDEX.md",
        f"| a.md | t {MARKER} | — |\n",
    )
    result = count_unindexed_markers(tmp_path)
    assert result.total == 1
    assert result.by_project == {"with_index": 1}


def test_count_generate_decision_indexes_format(tmp_path):
    """generate-decision-indexes の実際の付与形式で正確カウント."""
    # generate-decision-indexes L83 の形式: | `file` | title 【要更新】 | — |
    _write_index(
        tmp_path / "01_DECISIONS" / "proj" / "_INDEX.md",
        "## 新規（要キュレーション）\n\n"
        "| `2026-08-07_hoge.md` | ほげの説明 【要更新】 | — |\n"
        "| `2026-08-07_fuga.md` | ふがの説明 【要更新】 | — |\n",
    )
    result = count_unindexed_markers(tmp_path)
    assert result.total == 2
    assert result.by_project == {"proj": 2}


def test_count_empty_decisions_dir(tmp_path):
    """01_DECISIONS 空フォルダ → total=0, by_project={}."""
    (tmp_path / "01_DECISIONS").mkdir(parents=True)
    result = count_unindexed_markers(tmp_path)
    assert result.total == 0
    assert result.by_project == {}
