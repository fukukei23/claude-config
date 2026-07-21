"""SSOT体系化 P1: .dir-manifest.json 操作中核モジュール."""
import hashlib
import subprocess
import sys
import unicodedata
from pathlib import Path


# ドット始まりtop-level dir（ツール設定dir）の固定意味（D案・両LLM一致推奨）
# LLM非呼出・べき等・意味は業界標準で自明。未知ドットdirは汎用フォールバック。
DOT_DIR_MEANINGS: dict[str, str] = {
    ".claude": "Claude Code設定",
    ".cursor": "Cursor IDE設定",
    ".devcontainer": "開発コンテナ設定",
    ".github": "GitHub設定(CI/Actions)",
    ".gitlab": "GitLab CI設定",
    ".gradio": "Gradio UI定義",
    ".husky": "Git hooks設定",
    ".nexus": "NexusCore内部状態",
    ".spec": "仕様書ディレクトリ",
    ".vscode": "VS Code設定",
}

_DOT_DIR_GENERIC_PREFIX = "ツール設定ディレクトリ"


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
    """git ls-tree -r -d --name-only でディレクトリ一覧を再帰取得（path昇順）.

    - ``-r``: 再帰（深いパスまで取得）
    - ``-d``: tree（ディレクトリ）のみ・blob=ファイル除外
    - ``--name-only``: パスのみ出力（tab区切りパース不要）
    - ``-c core.quotepath=false``: 日本語パスの octal-escape 抑止

    Args:
        repo_path: 対象 Git リポジトリのパス。

    Returns:
        ディレクトリパスの昇順リスト。空リポジトリ（HEAD無し等）は [] 。
    """
    try:
        out = subprocess.check_output(
            [
                "git", "-c", "core.quotepath=false",
                "ls-tree", "-r", "-d", "--name-only", "HEAD",
            ],
            cwd=str(repo_path),
        )
    except subprocess.CalledProcessError:
        return []
    text = out.decode("utf-8") if isinstance(out, bytes) else out
    return sorted(line for line in text.splitlines() if line.strip())


def list_project_dirs_in_ssot(ssot_root: Path, project: str) -> list[str]:
    """obsidian-ssot 内 ``01_DECISIONS/<project>/`` 配下の top-level dir 一覧を取得.

    ``has_external_repo=false`` のプロジェクト検知用（Task 4・post-commit hook）。
    ``git ls-tree -r -d`` の結果から ``01_DECISIONS/<project>/`` 直下のみ抽出。
    深いパスは top-level(``split('/')[0]``) に集約（ノイズ回避）。

    Args:
        ssot_root: obsidian-ssot リポジトリルートのパス。
        project: ``01_DECISIONS/`` 配下のプロジェクト名（dir名）。

    Returns:
        ``01_DECISIONS/<project>/`` 直下のディレクトリ名の昇順リスト。
        プロジェクトdirが存在しない・git管理外の場合は [] 。
    """
    project_dir = f"01_DECISIONS/{project}"
    try:
        out = subprocess.check_output(
            [
                "git", "-c", "core.quotepath=false",
                "ls-tree", "-r", "-d", "--name-only", "HEAD",
            ],
            cwd=str(ssot_root),
        )
    except subprocess.CalledProcessError:
        return []
    text = out.decode("utf-8") if isinstance(out, bytes) else out
    prefix = f"{project_dir}/"
    tops: set[str] = set()
    for line in text.splitlines():
        if not line.startswith(prefix):
            continue
        rest = line[len(prefix):]
        if not rest:
            continue
        tops.add(rest.split("/")[0])
    return sorted(tops)


def _llm_meaning(repo_path: Path, dir_path: str) -> str:
    """Gemini API でdirの1行meaningを生成（scripts/api/gemini_text.py 経由）.

    Args:
        repo_path: 対象 Git リポジトリのパス（将来の文脈付与用・現状未使用）。
        dir_path: ディレクトリパス文字列。

    Returns:
        生成された意味文字列（stdout・strip 済み）。

    Raises:
        RuntimeError: API呼出が非0 exit または空応答を返した場合。
            呼出側（Task 6）でスキップ判定する契約。
    """
    prompt = f"以下のディレクトリの役割を日本語1行(20字以内)で: {dir_path}"
    gemini_script = Path.home() / ".claude/scripts/api/gemini_text.py"
    result = subprocess.run(
        [sys.executable, str(gemini_script), prompt],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        err = result.stderr.strip() or f"exit {result.returncode}"
        raise RuntimeError(f"gemini_text.py failed: {err}")
    meaning = result.stdout.strip()
    if not meaning:
        raise RuntimeError("gemini_text.py returned empty stdout")
    return meaning


def _resolve_dot_dir_meaning(dir_path: str) -> str | None:
    """ドット始まりtop-level dirの固定意味を返す（非ドットdirは None）.

    Args:
        dir_path: top-level ディレクトリ名。

    Returns:
        固定意味文字列。dir_path が ``.`` 始まりでなければ None。
        既知のドットdir は ``DOT_DIR_MEANINGS``、未知は汎用文言。
    """
    if not dir_path.startswith("."):
        return None
    return DOT_DIR_MEANINGS.get(dir_path, f"{_DOT_DIR_GENERIC_PREFIX}({dir_path})")


def build_manifest_entry(repo_path: Path, dir_path: str) -> dict:
    """1ディレクトリ分のmanifest entryを生成（D案: ドット固定/本体LLM）.

    - ドットdir(``.claude`` 等): 固定意味(DOT_DIR_MEANINGS)・承認不要(pending=False)
    - 本体dir: Gemini API で meaning 生成・人間承認待ち(pending=True)

    Args:
        repo_path: 対象 Git リポジトリのパス。
        dir_path: top-level ディレクトリパス文字列。

    Returns:
        path/meaning/meaning_hash/pending_approval を持つ dict。
        ドットdir は pending_approval=False(固定)・本体dir は True(承認待ち)。
    """
    fixed = _resolve_dot_dir_meaning(dir_path)
    if fixed is not None:
        meaning: str = fixed
        pending = False
    else:
        meaning = _llm_meaning(repo_path, dir_path)
        pending = True
    return {
        "path": dir_path,
        "meaning": meaning,
        "meaning_hash": meaning_hash(meaning),
        "pending_approval": pending,
    }
