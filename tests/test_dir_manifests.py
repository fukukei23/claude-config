"""dir_manifests.py の単体テスト（SSOT体系化 P1 Task 1/2/3）"""
import hashlib
import json
import subprocess
import unicodedata
from pathlib import Path

import pytest

from scripts.obsidian.approve_meaning import approve_manifest
from scripts.obsidian.dir_manifests import (
    _llm_meaning,
    build_manifest_entry,
    list_dirs_via_git,
    list_project_dirs_in_ssot,
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
    """git ls-tree -r -d --name-only の出力をパースしてディレクトリ一覧(昇順)を返す"""
    fake_output = "src/handlers\nsrc/services\n"  # --name-only 形式
    monkeypatch.setattr(
        "subprocess.check_output",
        lambda *a, **k: fake_output.encode(),
    )
    dirs = list_dirs_via_git(tmp_path)
    assert dirs == ["src/handlers", "src/services"]


def test_list_dirs_via_git_returns_empty_on_called_process_error(
    tmp_path, monkeypatch,
):
    """空リポジトリ（CalledProcessError・HEAD無し等）では空リストを返す"""

    def raise_error(*a, **k):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr("subprocess.check_output", raise_error)
    assert list_dirs_via_git(tmp_path) == []


def test_llm_meaning_raises_runtime_error_on_api_failure(monkeypatch):
    """_llm_meaning は非0 exit 時に RuntimeError を送出（呼出側でスキップ判定）"""

    class FakeResult:
        returncode = 1
        stdout = ""
        stderr = "error: invalid api key"

    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: FakeResult(),
    )
    with pytest.raises(RuntimeError, match="gemini_text.py failed"):
        _llm_meaning(Path("/fake"), "src/handlers")


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


def test_build_manifest_entry_uses_fixed_meaning_for_known_dot_dir(monkeypatch):
    """ドットdir(.claude等)は LLM 呼ばず固定意味・pending=False（D案）"""

    def _no_llm(*a, **k):
        raise AssertionError("LLM must not be called for dot dir")

    monkeypatch.setattr("scripts.obsidian.dir_manifests._llm_meaning", _no_llm)
    entry = build_manifest_entry(Path("/fake"), ".claude")
    assert entry["meaning"] == "Claude Code設定"
    assert entry["meaning_hash"] == meaning_hash("Claude Code設定")
    assert entry["pending_approval"] is False


def test_build_manifest_entry_unknown_dot_dir_uses_generic_fallback(monkeypatch):
    """未知ドットdirは汎用文言にフォールバック・pending=False（D案）"""
    monkeypatch.setattr(
        "scripts.obsidian.dir_manifests._llm_meaning",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no llm")),
    )
    entry = build_manifest_entry(Path("/fake"), ".unknown")
    assert entry["meaning"] == "ツール設定ディレクトリ(.unknown)"
    assert entry["pending_approval"] is False


def test_approve_manifest_clears_pending_and_freezes_hash(tmp_path):
    """approve_manifest は pending_approval=False 化・meaning_hash は不変(固定)."""
    manifest_path = tmp_path / ".dir-manifest.json"
    original_hash = meaning_hash("処理")
    manifest_path.write_text(
        json.dumps(
            {
                "project": "x",
                "has_external_repo": False,
                "last_verified": "2026-07-21",
                "directories": [
                    {
                        "path": "src",
                        "meaning": "処理",
                        "meaning_hash": original_hash,
                        "pending_approval": True,
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    approve_manifest(manifest_path, "src")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["directories"][0]["pending_approval"] is False
    # 本hashは固定（不変）・承認で hash 値は変わらない
    assert data["directories"][0]["meaning_hash"] == original_hash


# --- list_project_dirs_in_ssot (Task 4・post-commit hook 検知ロジック) ---


def _init_ssot_repo(tmp_path: Path) -> Path:
    """テスト用の git repo を tmp_path に初期化して返す"""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, check=True,
    )
    return tmp_path


def _commit_dirs(repo_root: Path, paths: list[str], msg: str = "init") -> None:
    """指定ディレクトリを .gitkeep 付きで作成して commit"""
    for rel in paths:
        d = repo_root / rel
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=repo_root, check=True)


def test_list_project_dirs_in_ssot_returns_top_level_only(tmp_path):
    """01_DECISIONS/<project>/ 直下の top-level dir 名のみを返す（深いパスは集約）"""
    repo = _init_ssot_repo(tmp_path)
    _commit_dirs(
        repo,
        [
            "01_DECISIONS/proj1/alpha",
            "01_DECISIONS/proj1/beta",
            "01_DECISIONS/proj1/beta/deep1",  # top-level ではない
            "01_DECISIONS/proj1/gamma/deep2",  # gamma は top-level
        ],
    )
    result = list_project_dirs_in_ssot(repo, "proj1")
    assert result == ["alpha", "beta", "gamma"]


def test_list_project_dirs_in_ssot_empty_when_project_missing(tmp_path):
    """存在しないプロジェクト・git管理外の場合は空リスト"""
    repo = _init_ssot_repo(tmp_path)
    _commit_dirs(repo, ["01_DECISIONS/proj1/alpha"])
    # proj2 は存在しない
    assert list_project_dirs_in_ssot(repo, "proj2") == []


def test_list_project_dirs_in_ssot_isolates_other_projects(tmp_path):
    """別プロジェクトの dir は混入しない（指定 project のみ取得）"""
    repo = _init_ssot_repo(tmp_path)
    _commit_dirs(
        repo,
        [
            "01_DECISIONS/proj1/alpha",
            "01_DECISIONS/proj1/beta",
            "01_DECISIONS/proj2/other1",  # proj2 側
            "01_DECISIONS/proj2/other2",  # proj2 側
        ],
    )
    result = list_project_dirs_in_ssot(repo, "proj1")
    assert result == ["alpha", "beta"]
