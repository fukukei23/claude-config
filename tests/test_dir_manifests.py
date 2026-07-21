"""dir_manifests.py の単体テスト（SSOT体系化 P1 Task 1/2）"""
import hashlib
import unicodedata
from pathlib import Path

import pytest

from scripts.obsidian.dir_manifests import (
    build_manifest_entry,
    list_dirs_via_git,
    meaning_hash,
    validate_manifest,
)


def test_meaning_hash_is_stable_sha256_8hex():
    """同一下力は常に同一出力（SHA-256 先頭8桁）"""
    # 実測値（SHA-256 先頭8桁・実装後に取得）
    assert meaning_hash("LINE受信イベント処理") == "05a10073"
    # 同一入力は常に同一出力
    assert meaning_hash("test") == meaning_hash("test")


def test_meaning_hash_normalizes_nfkc_trim_lower():
    """全角半角・前後空白・大小文字を NFKC + trim + lower で正規化してから hash"""
    raw = "  ＬＩＮＥ受信  "
    normalized = unicodedata.normalize("NFKC", raw).strip().lower()
    expected = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
    assert meaning_hash(raw) == expected


def test_validate_manifest_rejects_duplicate_paths():
    """重複する path を持つ directories は ValueError"""
    manifest = {
        "project": "x",
        "has_external_repo": False,
        "last_verified": "2026-07-21",
        "directories": [
            {"path": "src", "meaning": "a", "meaning_hash": "h1"},
            {"path": "src", "meaning": "b", "meaning_hash": "h2"},
        ],
    }
    with pytest.raises(ValueError, match="duplicate path"):
        validate_manifest(manifest)


def test_validate_manifest_rejects_empty_meaning():
    """空の meaning は ValueError"""
    manifest = {
        "project": "x",
        "has_external_repo": False,
        "last_verified": "2026-07-21",
        "directories": [{"path": "src", "meaning": "", "meaning_hash": "h"}],
    }
    with pytest.raises(ValueError, match="empty meaning"):
        validate_manifest(manifest)


def test_list_dirs_via_git_parses_ls_tree(tmp_path, monkeypatch):
    """git ls-tree の出力をパースしてディレクトリ一覧(昇順)を返す"""
    fake_output = "tree abc123\tsrc/handlers\ntree def456\tsrc/services\n"
    monkeypatch.setattr(
        "subprocess.check_output",
        lambda *a, **k: fake_output.encode(),
    )
    dirs = list_dirs_via_git(tmp_path)
    assert dirs == ["src/handlers", "src/services"]


def test_build_manifest_entry_marks_pending_with_provisional_hash(monkeypatch):
    """build_manifest_entry は仮hash付与＋pending_approval=True で返す"""
    monkeypatch.setattr(
        "scripts.obsidian.dir_manifests._llm_meaning",
        lambda repo, path: "LINE受信イベント処理",
    )
    entry = build_manifest_entry(Path("/fake"), "src/handlers")
    assert entry["meaning"] == "LINE受信イベント処理"
    assert entry["meaning_hash"] == meaning_hash("LINE受信イベント処理")
    assert entry["pending_approval"] is True
