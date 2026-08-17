"""session系Stop/SessionStartスクリプトのテスト（E・handoff系）.

- generate-handoff.sh: Stop毎に ~/.claude/state/handoff.md を生成
- load-handoff.sh: SessionStart時に履歴5件を読み込む
- save-session-log.sh: Stop毎に日記へセッション終了マーカー記録

絶対パス参照のshは一時コピー+sed書換で隔離して検証（実SSOT/実stateを書き換えない）。

実行: cd ~/projects/claude-config && python3 -m pytest tests/test_session_hooks.py -q
"""

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).parents[1]
GEN = REPO / "scripts" / "session" / "generate-handoff.sh"
LOAD = REPO / "scripts" / "session" / "load-handoff.sh"
SAVE = REPO / "scripts" / "session" / "save-session-log.sh"


def run_sh(script: Path, home: Path, cwd: Path | None = None) -> tuple[int, str]:
    env = {"HOME": str(home), "PATH": os.environ["PATH"]}
    r = subprocess.run(["bash", str(script)], capture_output=True,
                       timeout=15, env=env, cwd=str(cwd or home))
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", errors="replace")


def _patched_copy(src: Path, tmp_path: Path, replacements: dict) -> Path:
    """src を replacements で sed 書換した一時コピーを返す."""
    dst = tmp_path / f"patched-{src.name}"
    text = src.read_text(encoding="utf-8")
    for old, new in replacements.items():
        assert old in text, f"{src.name}: 置換元が見つからない: {old}"
        text = text.replace(old, new)
    dst.write_text(text, encoding="utf-8")
    return dst


# ---- generate-handoff.sh ----

class TestGenerateHandoff:
    def test_handoff生成と基本構造(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        code, _ = run_sh(GEN, home)
        out = home / ".claude" / "state" / "handoff.md"
        assert code == 0
        assert out.exists()
        text = out.read_text()
        assert "# セッションハンドオフ" in text
        assert "## 前回のセッション" in text
        assert "## 未解決問題" in text
        assert "## Git状態" in text
        assert "最終更新:" in text

    def test_リポジトリ内ならgit情報が入る(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        code, _ = run_sh(GEN, home, cwd=REPO)
        assert code == 0
        text = (home / ".claude" / "state" / "handoff.md").read_text()
        assert "ブランチ:" in text or "main" in text


# ---- load-handoff.sh ----

class TestLoadHandoff:
    def test_履歴あり_最新5件を読み込む(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        hist = tmp_path / "handoff"
        hist.mkdir()
        for i in range(6):  # 6件作る（読み込まれるのは新しい5件）
            f = hist / f"2026-08-0{i}_100{i}_abcd.md"
            f.write_text(f"# 引き継ぎ{i}\n\n内容{i}\n")
            # mtimeを明示設定（ls -t の同一時刻順序不定を回避）
            subprocess.run(["touch", "-d", f"2026-08-01 10:0{i}:00", str(f)], check=True)
        patched = _patched_copy(LOAD, tmp_path, {
            'HISTORY_DIR="$HOME/projects/obsidian-ssot/00_SYSTEM/handoff"':
            f'HISTORY_DIR="{hist}"',
        })
        env_home = home
        r = subprocess.run(["bash", str(patched)], capture_output=True, timeout=15,
                           env={"HOME": str(env_home), "PATH": os.environ["PATH"]})
        out = r.stdout.decode("utf-8", errors="replace")
        assert "--- Handoff (最新5件) ---" in out
        assert "引き継ぎ5" in out   # 最新側
        assert "引き継ぎ1" in out   # 5件目
        assert "引き継ぎ0" not in out  # 6件目（最古）は読まれない

    def test_履歴空_stateフォールバック(self, tmp_path):
        home = tmp_path / "home"
        (home / ".claude" / "state").mkdir(parents=True)
        state = home / ".claude" / "state" / "handoff.md"
        state.write_text("# フォールバック文書\n")
        patched = _patched_copy(LOAD, tmp_path, {
            'HISTORY_DIR="$HOME/projects/obsidian-ssot/00_SYSTEM/handoff"':
            f'HISTORY_DIR="{tmp_path / "empty"}"',
        })
        r = subprocess.run(["bash", str(patched)], capture_output=True, timeout=15,
                           env={"HOME": str(home), "PATH": os.environ["PATH"]})
        out = r.stdout.decode("utf-8", errors="replace")
        assert "state fallback" in out
        assert "フォールバック文書" in out

    def test_両方なし(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        (home / ".claude").mkdir()
        patched = _patched_copy(LOAD, tmp_path, {
            'HISTORY_DIR="$HOME/projects/obsidian-ssot/00_SYSTEM/handoff"':
            f'HISTORY_DIR="{tmp_path / "empty"}"',
            'STATE_FILE="$HOME/.claude/state/handoff.md"':
            f'STATE_FILE="{tmp_path / "none.md"}"',
        })
        r = subprocess.run(["bash", str(patched)], capture_output=True, timeout=15,
                           env={"HOME": str(home), "PATH": os.environ["PATH"]})
        assert "handoff: なし" in r.stdout.decode()


# ---- save-session-log.sh ----

class TestSaveSessionLog:
    def _patched(self, tmp_path):
        return _patched_copy(SAVE, tmp_path, {
            'SSOT_PATH="/home/yn4416/projects/obsidian-ssot"':
            f'SSOT_PATH="{tmp_path / "ssot"}"',
        })

    def test_日記不存在なら新規作成(self, tmp_path):
        (tmp_path / "home").mkdir()
        code, _ = run_sh(self._patched(tmp_path), tmp_path / "home")
        assert code == 0
        today = subprocess.run(["date", "+%Y-%m-%d"], capture_output=True,
                               text=True).stdout.strip()
        daily = tmp_path / "ssot" / "10_DAILY" / f"{today}.md"
        assert daily.exists()
        assert "セッション終了:" in daily.read_text()

    def test_既存マーカーは1件だけ残る(self, tmp_path):
        patched = self._patched(tmp_path)
        (tmp_path / "home").mkdir()
        today = subprocess.run(["date", "+%Y-%m-%d"], capture_output=True,
                               text=True).stdout.strip()
        daily = tmp_path / "ssot" / "10_DAILY" / f"{today}.md"
        daily.parent.mkdir(parents=True)
        daily.write_text("# 日記\n\n本文\n\n---\nセッション終了: 09:00\n")
        run_sh(patched, tmp_path / "home")
        run_sh(patched, tmp_path / "home")  # 2回実行
        text = daily.read_text()
        assert text.count("セッション終了:") == 1
        assert "本文" in text  # 既存内容は保持
