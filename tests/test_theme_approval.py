"""SSOT体系化 P3-C Phase1: theme_approval（approved_themes + 承認ログ + diff）のテスト."""
from pathlib import Path

from scripts.obsidian.theme_approval import update_approved_themes


def test_update_approved_themes_sets_frontmatter_and_logs(tmp_path: Path) -> None:
    """approved_themes をFMに設定し本文に承認ログ行を追記・差分を返す（§4.4）."""
    idx = tmp_path / "_INDEX.md"
    idx.write_text(
        "---\nproject: ai-music\nstatus: active\nlast_verified: 2026-07-24\n---\n# T\n本文\n",
        encoding="utf-8",
    )
    diff = update_approved_themes(idx, ["hiphop", "cyber-wa"], "2026-07-24")
    text = idx.read_text(encoding="utf-8")
    assert "approved_themes: [hiphop, cyber-wa]" in text
    assert "## テーマ承認ログ" in text
    assert "- 2026-07-24: themes=[hiphop, cyber-wa]" in text
    assert diff  # 空でない（差分表示）


def test_update_approved_themes_preserves_managed_and_unknown_keys(tmp_path: Path) -> None:
    """managed3キーと既存未知キーを保持したまま approved_themes を追加."""
    idx = tmp_path / "_INDEX.md"
    idx.write_text(
        "---\nproject: ai-music\nstatus: active\nlast_verified: 2026-07-24\n"
        "meaning_note: keep-me\n---\n# T\n",
        encoding="utf-8",
    )
    update_approved_themes(idx, ["x"], "2026-07-24")
    text = idx.read_text(encoding="utf-8")
    assert "meaning_note: keep-me" in text
    assert "project: ai-music" in text
    assert "approved_themes: [x]" in text


def test_update_approved_themes_empty_clears(tmp_path: Path) -> None:
    """空リストで approved_themes を [] にする（承認解除）."""
    idx = tmp_path / "_INDEX.md"
    idx.write_text(
        "---\nproject: p\nstatus: active\nlast_verified: 2026-07-24\n"
        "approved_themes: [old]\n---\n# T\n",
        encoding="utf-8",
    )
    update_approved_themes(idx, [], "2026-07-24")
    assert "approved_themes: []" in idx.read_text(encoding="utf-8")


def test_update_approved_themes_appends_second_approval(tmp_path: Path) -> None:
    """2回目承認で承認ログ行が追記される（最新が上・履歴保持）."""
    idx = tmp_path / "_INDEX.md"
    idx.write_text("---\nproject: p\nstatus: active\nlast_verified: 2026-07-24\n---\n# T\n", encoding="utf-8")
    update_approved_themes(idx, ["a"], "2026-07-23")
    update_approved_themes(idx, ["b"], "2026-07-24")
    text = idx.read_text(encoding="utf-8")
    assert "- 2026-07-23: themes=[a]" in text
    assert "- 2026-07-24: themes=[b]" in text


def test_update_approved_themes_no_frontmatter(tmp_path: Path) -> None:
    """FM無しファイル（後方互換）: FM挿入 + 末尾に承認ログセクション."""
    idx = tmp_path / "_INDEX.md"
    idx.write_text("# T\n本文\n", encoding="utf-8")
    diff = update_approved_themes(idx, ["x"], "2026-07-24")
    text = idx.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "approved_themes: [x]" in text
    assert "## テーマ承認ログ" in text
    assert diff
