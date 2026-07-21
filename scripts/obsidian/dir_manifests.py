"""SSOT体系化 P1: .dir-manifest.json 操作中核モジュール."""
import hashlib
import subprocess
import unicodedata
from pathlib import Path


def meaning_hash(meaning: str) -> str:
    """meaning文字列をSHA-256先頭8桁に正規化hash化（NFKC・trim・lower）.

    Args:
        meaning: ハッシュ対象の意味文字列。

    Returns:
        SHA-256 の先頭8桁16進数。
    """
    normalized = unicodedata.normalize("NFKC", meaning).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]


def validate_manifest(manifest: dict) -> None:
    """manifest の基本バリデーション（重複 path・空 meaning）.

    Args:
        manifest: ``.dir-manifest.json`` 相当の dict。

    Raises:
        ValueError: 重複 path または空 meaning が存在する場合。
    """
    directories = manifest.get("directories", [])
    paths = [d["path"] for d in directories]
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate path in directories")
    for d in directories:
        if not d.get("meaning", "").strip():
            raise ValueError(f"empty meaning for path: {d['path']}")


def list_dirs_via_git(repo_path: Path) -> list[str]:
    """git ls-tree でディレクトリ一覧を取得（path昇順）.

    Args:
        repo_path: 対象 Git リポジトリのパス。

    Returns:
        ``git ls-tree HEAD`` の tree エントリパスを昇順ソートしたリスト。
    """
    out = subprocess.check_output(
        ["git", "ls-tree", "HEAD"],
        cwd=str(repo_path),
    )
    text = out.decode("utf-8") if isinstance(out, bytes) else out
    dirs = set()
    for line in text.splitlines():
        if "\t" in line:
            dirs.add(line.split("\t", 1)[1])
    return sorted(dirs)


def _llm_meaning(repo_path: Path, dir_path: str) -> str:
    """Gemini API でdirの1行meaningを生成（scripts/api/gemini.py 経由）.

    Args:
        repo_path: 対象 Git リポジトリのパス（将来的な文脈付与用）。
        dir_path: ディレクトリパス文字列。

    Returns:
        生成された意味文字列（stdout・strip 済み）。
    """
    prompt = f"以下のディレクトリの役割を日本語1行(20字以内)で: {dir_path}"
    gemini_script = Path.home() / ".claude/scripts/api/gemini.py"
    result = subprocess.run(
        ["python3", str(gemini_script), prompt],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout.strip()


def build_manifest_entry(repo_path: Path, dir_path: str) -> dict:
    """1ディレクトリ分のmanifest entryを生成（仮hash・pending）.

    Args:
        repo_path: 対象 Git リポジトリのパス。
        dir_path: ディレクトリパス文字列。

    Returns:
        path/meaning/meaning_hash/pending_approval を持つ dict。
        ``pending_approval`` は人間承認待ちを示す True（Task 3 で False 化）。
    """
    meaning = _llm_meaning(repo_path, dir_path)
    return {
        "path": dir_path,
        "meaning": meaning,
        "meaning_hash": meaning_hash(meaning),
        "pending_approval": True,
    }
