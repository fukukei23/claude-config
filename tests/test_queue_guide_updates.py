"""queue-guide-updates.sh（Stop・ガイド更新キュー記録）のテスト.

一時gitリポジトリ＋sed差し替えで隔離し、差分→対応章のキュー登録を検証する。

実行: cd ~/projects/claude-config && python3 -m pytest tests/test_queue_guide_updates.py -q
"""

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "session" / "queue-guide-updates.sh"


def _run_in_repo(tmp_path: Path, commits: list[tuple[str, list[str]]],
                 last_commit: str | None, target_dir: str = "scripts/hooks") -> tuple[Path, str, int]:
    """一時git repoを構築してスクリプトの差し替え版を実行.

    commits: [(message, [作成ファイルパス]), ...] — commit順に作成
    last_commit: .last-checked-commit に書くhash（None=書かない）
    returns: (queue_file, stdout, exit_code)
    """
    config = tmp_path / "claude-config"
    config.mkdir()

    def git(*a):
        return subprocess.run(["git", "-C", str(config), *a],
                              capture_output=True, text=True, check=True)
    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    hashes = []
    for msg, files in commits:
        for f in files:
            p = config / f
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"{msg}\n")
        git("add", "-A")
        git("commit", "-q", "-m", msg)
        r = git("rev-parse", "HEAD")
        hashes.append(r.stdout.strip())

    guide = tmp_path / "guide"
    guide.mkdir()
    if last_commit:
        (guide / ".last-checked-commit").write_text(last_commit)

    text = SCRIPT.read_text(encoding="utf-8")
    text = text.replace(
        'GUIDE_DIR="/home/yn4416/projects/claude-code-guide"', f'GUIDE_DIR="{guide}"')
    text = text.replace(
        'CONFIG_DIR="/home/yn4416/projects/claude-config"', f'CONFIG_DIR="{config}"')
    patched = tmp_path / "patched-queue.sh"
    patched.write_text(text, encoding="utf-8")

    r = subprocess.run(["bash", str(patched)], capture_output=True, timeout=30,
                       env={"HOME": str(tmp_path), "PATH": os.environ["PATH"]})
    return (guide / ".update-queue.md",
            (r.stdout + r.stderr).decode("utf-8", errors="replace"), r.returncode)


def test_hooks変更で05hooksがキューに入る(tmp_path):
    queue, _, code = _run_in_repo(
        tmp_path,
        commits=[("base", ["README.md"]),
                 ("hooks changed", ["scripts/hooks/new-hook.sh"])],
        last_commit=None)
    # 初回は LAST_COMMIT 無し → HEAD~1 差分 = hooks変更
    assert code == 0
    text = queue.read_text()
    assert "05-hooks.html" in text


def test_明示的な再実行_新コミットなしは追記なし(tmp_path):
    """1回目実行後（last=HEAD）に新コミット無しで再実行 → 追記なし."""
    queue, _, code = _run_in_repo(
        tmp_path,
        commits=[("base", ["README.md"]),
                 ("mcp changed", ["scripts/mcp/new.py"])],
        last_commit=None)
    assert "04-mcp.html" in queue.read_text()
    before_count = queue.read_text().count("\n")
    # last-checked-commit は1回目で HEAD に更新されている → もう一度実行
    text = SCRIPT.read_text(encoding="utf-8")
    # guide/.last-checked-commit の現在値を使って直接再実行
    config = tmp_path / "claude-config"
    guide = tmp_path / "guide"
    patched = tmp_path / "patched-queue2.sh"
    patched.write_text(text.replace(
        'GUIDE_DIR="/home/yn4416/projects/claude-code-guide"', f'GUIDE_DIR="{guide}"').replace(
        'CONFIG_DIR="/home/yn4416/projects/claude-config"', f'CONFIG_DIR="{config}"'))
    r = subprocess.run(["bash", str(patched)], capture_output=True, timeout=30,
                       env={"HOME": str(tmp_path), "PATH": os.environ["PATH"]})
    assert r.returncode == 0
    after = queue.read_text()
    assert after.count("\n") == before_count  # 追加なし


def test_無関係ファイル変更はキューに入れない(tmp_path):
    queue, _, code = _run_in_repo(
        tmp_path,
        commits=[("base", ["README.md"]),
                 ("docs only", ["docs/note.md"])],
        last_commit=None)
    assert code == 0
    # 対象章に mapping されない変更はキュー登録しない（ファイル自体無し or 該当行なし）
    text = queue.read_text() if queue.exists() else ""
    assert "05-hooks.html" not in text
    assert "03-skills.html" not in text


def test_skills変更で03skillsがキューに入る(tmp_path):
    queue, _, code = _run_in_repo(
        tmp_path,
        commits=[("base", ["README.md"]),
                 ("skill added", ["skills/my-skill/SKILL.md"])],
        last_commit=None)
    assert code == 0
    assert "03-skills.html" in queue.read_text()
