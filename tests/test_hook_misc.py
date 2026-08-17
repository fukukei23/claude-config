"""未テストフック群（track-tool-usage・notify系・snapshot-init・sync-skills-windows）のテスト.

外部依存（powershell.exe / curl / Discord）はPATHスタブで隔離し、
「組み立ての正しさ・クラッシュしないこと・記録ファイルの契約」を検証する。

実行: cd ~/projects/claude-config && python3 -m pytest tests/test_hook_misc.py -q
"""

import json
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).parents[1]
TRACK = REPO / "scripts" / "hooks" / "track-tool-usage.sh"
NOTIFY_DONE = REPO / "scripts" / "hooks" / "notify-done.sh"
NOTIFY_PS = REPO / "scripts" / "hooks" / "notify.sh"
NOTIFY_DC = REPO / "scripts" / "hooks" / "notify-discord-on-error.sh"
SNAPSHOT = REPO / "scripts" / "hooks" / "guard-settings-snapshot-init.sh"
SYNC_SKILLS = REPO / "scripts" / "session" / "sync-skills-windows.sh"


def run_sh(script: Path, home: Path, stdin: bytes = b"", env_extra: dict | None = None,
           path_prepend: Path | None = None) -> tuple[int, str]:
    env = {"HOME": str(home), "PATH": os.environ["PATH"]}
    env.update(env_extra or {})
    if path_prepend:
        env["PATH"] = f"{path_prepend}:{env['PATH']}"
    r = subprocess.run(["bash", str(script)], input=stdin,
                       capture_output=True, timeout=15, env=env)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", errors="replace")


def _make_stub_dir(tmp_path: Path, name: str, log_lines: list) -> Path:
    """コマンド名 name のスタブ（呼出引数をjsonlに記録）を作り dir を返す."""
    d = tmp_path / "stubs"
    d.mkdir(exist_ok=True)
    stub = d / name
    log = tmp_path / "stub_calls.jsonl"
    stub.write_text(
        "#!/bin/bash\n"
        f"echo \"$@\" | python3 -c \"import sys,json; open('{log}','a').write(json.dumps(sys.stdin.read(), ensure_ascii=False)+chr(10))\"\n"
        "exit 0\n")
    stub.chmod(0o755)
    log_lines.append(log)
    return d


# ---- track-tool-usage.sh ----

class TestTrackToolUsage:
    def test_ヘッダー付きcsvに記録(self, tmp_path):
        stdin = json.dumps({"tool_name": "Bash", "session_id": "s1"}).encode()
        code, _ = run_sh(TRACK, tmp_path, stdin)
        assert code == 0
        import datetime
        today = datetime.date.today().isoformat()
        csv = tmp_path / ".claude" / "logs" / f"tool-usage-{today}.csv"
        text = csv.read_text()
        assert "timestamp,session_id,tool_name,skill_name" in text
        assert ",s1,Bash," in text

    def test_skill発動時はスキル名を記録(self, tmp_path):
        stdin = json.dumps({"tool_name": "Skill", "session_id": "s2",
                            "tool_input": {"skill": "ssot-record"}}).encode()
        code, _ = run_sh(TRACK, tmp_path, stdin)
        assert code == 0
        logs = list((tmp_path / ".claude" / "logs").glob("tool-usage-*.csv"))
        assert "s2,Skill,ssot-record" in logs[0].read_text()

    def test_不正jsonでもexit0(self, tmp_path):
        code, _ = run_sh(TRACK, tmp_path, b"broken")
        assert code == 0

    def test_wt_session時にheartbeat作成(self, tmp_path):
        stdin = json.dumps({"tool_name": "Bash", "session_id": "s"}).encode()
        code, _ = run_sh(TRACK, tmp_path, stdin, {"WT_SESSION": "abcd1234-xxx"})
        assert code == 0
        assert (tmp_path / ".claude" / "state" / "heartbeat" / "abcd").exists()


# ---- notify-done.sh（Stop・完了通知） ----

class TestNotifyDone:
    def test_ベル出力とexit0(self, tmp_path):
        """powershell不在環境でもクラッシュしない・ベルは必ず出す."""
        code, out = run_sh(NOTIFY_DONE, tmp_path)
        assert code == 0
        assert "\a" in out or "\x07" in out


# ---- notify.sh（手動・Windowsトースト） ----

class TestNotify:
    def _patched_notify(self, tmp_path: Path, stubs: Path) -> Path:
        """notify.sh は powershell.exe を絶対パス呼出のため sed 差し替えで隔離."""
        stub_ps = stubs / "powershell.exe"
        text = NOTIFY_PS.read_text(encoding="utf-8")
        text = text.replace(
            "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
            str(stub_ps))
        dst = tmp_path / "patched-notify.sh"
        dst.write_text(text, encoding="utf-8")
        return dst

    def test_powershell呼出の引数契約(self, tmp_path):
        logs = []
        stubs = _make_stub_dir(tmp_path, "powershell.exe", logs)
        patched = self._patched_notify(tmp_path, stubs)
        code, _ = run_sh(patched, tmp_path)
        assert code == 0
        calls = logs[0].read_text()
        assert "-Title" in calls
        assert "承認が必要です" in calls

    def test_引数でtitle_message差し替え(self, tmp_path):
        logs = []
        stubs = _make_stub_dir(tmp_path, "powershell.exe", logs)
        patched = self._patched_notify(tmp_path, stubs)
        r = subprocess.run(["bash", str(patched), "見出しX", "本文Y"],
                           capture_output=True, timeout=15,
                           env={"HOME": str(tmp_path), "PATH": os.environ["PATH"]})
        assert r.returncode == 0
        calls = logs[0].read_text()
        assert "見出しX" in calls and "本文Y" in calls


# ---- notify-discord-on-error.sh（Notification・エラー時Discord通知） ----

class TestNotifyDiscord:
    def test_エラー時curlを呼ぶ(self, tmp_path):
        logs = []
        stubs = _make_stub_dir(tmp_path, "curl", logs)
        stdin = json.dumps({"title": "Error: API failed", "message": "500"}).encode()
        code, _ = run_sh(NOTIFY_DC, tmp_path, stdin,
                         {"DISCORD_CLAUDE_WEBHOOK": "https://discord.example/hook"},
                         path_prepend=stubs)
        assert code == 0
        calls = logs[0].read_text()
        assert "https://discord.example/hook" in calls
        assert "Claude Code Error" in calls

    def test_通常通知はcurlを呼ばない(self, tmp_path):
        logs = []
        stubs = _make_stub_dir(tmp_path, "curl", logs)
        stdin = json.dumps({"title": "Task complete", "message": "done"}).encode()
        run_sh(NOTIFY_DC, tmp_path, stdin,
               {"DISCORD_CLAUDE_WEBHOOK": "https://discord.example/hook"},
               path_prepend=stubs)
        assert not logs[0].exists()

    def test_webhook未設定時は呼ばない(self, tmp_path):
        logs = []
        stubs = _make_stub_dir(tmp_path, "curl", logs)
        stdin = json.dumps({"title": "Error: x", "message": "y"}).encode()
        code, _ = run_sh(NOTIFY_DC, tmp_path, stdin, path_prepend=stubs)
        assert code == 0
        assert not logs[0].exists()


# ---- guard-settings-snapshot-init.sh（SessionStart） ----

class TestSnapshotInit:
    def test_存在ファイルのスナップショット作成(self, tmp_path):
        cfg_dir = tmp_path / "claude"
        cfg_dir.mkdir()
        (cfg_dir / "settings.json").write_text('{"a":1}')
        code, _ = run_sh(SNAPSHOT, tmp_path, env_extra={"CLAUDE_CONFIG_DIR": str(cfg_dir)})
        assert code == 0
        snap = cfg_dir / "state" / "guard-settings-snapshots" / "settings.json.before"
        assert snap.read_text() == '{"a":1}'

    def test_不存在ファイルはスルー(self, tmp_path):
        cfg_dir = tmp_path / "claude"
        cfg_dir.mkdir()
        code, _ = run_sh(SNAPSHOT, tmp_path, env_extra={"CLAUDE_CONFIG_DIR": str(cfg_dir)})
        assert code == 0  # クラッシュしない


# ---- sync-skills-windows.sh（Stop・WSL→Windowsスキル同期） ----

def _patched_sync(tmp_path: Path, wsl_skills: Path, win_skills: Path) -> Path:
    text = SYNC_SKILLS.read_text(encoding="utf-8")
    text = text.replace(
        'WSL_SKILLS="/home/yn4416/.claude/skills"', f'WSL_SKILLS="{wsl_skills}"')
    text = text.replace(
        'WIN_SKILLS="/mnt/c/Users/yn441/.claude/skills"', f'WIN_SKILLS="{win_skills}"')
    dst = tmp_path / "patched-sync-skills.sh"
    dst.write_text(text, encoding="utf-8")
    return dst


class TestSyncSkills:
    def _env(self, tmp_path):
        wsl = tmp_path / "skills"
        win = tmp_path / "win-skills"
        wsl.mkdir()
        win.mkdir(exist_ok=True)
        return wsl, win

    def test_新規スキルを追加(self, tmp_path):
        wsl, win = self._env(tmp_path)
        (wsl / "alpha").mkdir()
        (wsl / "alpha" / "SKILL.md").write_text("---\nname: alpha\n---\n")
        patched = _patched_sync(tmp_path, wsl, win)
        code, out = run_sh(patched, tmp_path)
        assert code == 0
        assert (win / "alpha" / "SKILL.md").exists()

    def test_skill_md欠落は修復(self, tmp_path):
        wsl, win = self._env(tmp_path)
        (wsl / "beta").mkdir()
        (wsl / "beta" / "SKILL.md").write_text("beta body\n")
        (win / "beta").mkdir()  # ディレクトリだけあってSKILL.md無し
        patched = _patched_sync(tmp_path, wsl, win)
        code, _ = run_sh(patched, tmp_path)
        assert code == 0
        assert (win / "beta" / "SKILL.md").exists()

    def test_更新不要なら上書きしない(self, tmp_path):
        wsl, win = self._env(tmp_path)
        (wsl / "gamma").mkdir()
        (wsl / "gamma" / "SKILL.md").write_text("v1\n")
        (win / "gamma").mkdir()
        (win / "gamma" / "SKILL.md").write_text("v1\n")
        patched = _patched_sync(tmp_path, wsl, win)
        code, out = run_sh(patched, tmp_path)
        assert code == 0
        assert "更新 gamma" not in out

    def test_新しければ更新(self, tmp_path):
        wsl, win = self._env(tmp_path)
        (wsl / "delta").mkdir()
        src = wsl / "delta" / "SKILL.md"
        src.write_text("v2\n")
        (win / "delta").mkdir()
        dst = win / "delta" / "SKILL.md"
        dst.write_text("v1-old\n")
        # win側を古くする
        os.utime(dst, (1000000, 1000000))
        patched = _patched_sync(tmp_path, wsl, win)
        code, _ = run_sh(patched, tmp_path)
        assert code == 0
        assert "v2" in dst.read_text()

    def test_win側ディレクトリ自体不在ならexit0(self, tmp_path):
        wsl, _ = self._env(tmp_path)
        patched = _patched_sync(tmp_path, wsl, tmp_path / "no-win")
        code, _ = run_sh(patched, tmp_path)
        assert code == 0
