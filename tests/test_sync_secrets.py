"""config系スクリプトの統合テスト（一時HOME・ダミー値使用・本物のキーは扱わない）.

- sync-secrets-to-settings.sh: .secrets.env → settings.json 同期（冪等性・JSON有効性）
- post-tool-settings-sync.sh: settings.json 変更時のみ example 同期へ中継
- load-secrets.sh: .secrets.env 読み込み件数

実行: cd ~/projects/claude-config && python3 -m pytest tests/test_sync_secrets.py -q
"""

import json
import os
import subprocess
from pathlib import Path


REPO = Path(__file__).parents[1]
SYNC = REPO / "scripts" / "config" / "sync-secrets-to-settings.sh"
POST_TOOL = REPO / "scripts" / "config" / "post-tool-settings-sync.sh"
LOAD = REPO / "scripts" / "config" / "load-secrets.sh"


def run_sh(script: Path, home: Path, env_extra: dict | None = None) -> tuple[int, str]:
    """一時HOME環境でスクリプト実行し (exit_code, stdout) を返す."""
    env = {"HOME": str(home), "PATH": os.environ["PATH"], "TMPDIR": "/tmp"}
    env.update(env_extra or {})
    r = subprocess.run(["bash", str(script)], capture_output=True,
                       timeout=30, env=env)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", errors="replace")


def _make_home(tmp_path: Path, secrets: str | None, settings: dict | None) -> Path:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    if secrets is not None:
        (home / ".secrets.env").write_text(secrets, encoding="utf-8")
    if settings is not None:
        (home / ".claude" / "settings.json").write_text(
            json.dumps(settings, indent=2), encoding="utf-8")
    return home


DUMMY_SECRETS = """export GLM_API_KEY=dummy-glm-key-123
export ANTHROPIC_AUTH_TOKEN=dummy-anthropic-token-456
export BRAVE_API_KEY=dummy-brave-789
export MINIMAX_API_KEY=dummy-minimax-abc
"""

DUMMY_SETTINGS = {
    "env": {
        "ANTHROPIC_AUTH_TOKEN": "OLD-OLD-OLD",
        "ANTHROPIC_BASE_URL": "https://old.example.com",
        "BRAVE_API_KEY": "OLD-BRAVE",
    },
    "mcpServers": {
        "brave-search": {"env": {"BRAVE_API_KEY": "OLD-MCP-BRAVE"}},
        "glm": {"env": {"GLM_API_KEY": "OLD-MCP-GLM"}},
        "minimax": {"env": {"MINIMAX_API_KEY": "OLD-MCP-MMX"}},
    },
}


# ---- sync-secrets-to-settings.sh ----

class TestSyncSecrets:
    def test_secrets不在なら何もせずexit0(self, tmp_path):
        home = _make_home(tmp_path, secrets=None, settings=DUMMY_SETTINGS)
        code, _ = run_sh(SYNC, home)
        assert code == 0
        # settings.json は無変更
        d = json.loads((home / ".claude" / "settings.json").read_text())
        assert d["env"]["ANTHROPIC_AUTH_TOKEN"] == "OLD-OLD-OLD"

    def test_settings不在ならexit1(self, tmp_path):
        home = _make_home(tmp_path, secrets=DUMMY_SECRETS, settings=None)
        code, out = run_sh(SYNC, home)
        assert code == 1
        assert "settings.json不在" in out

    def test_正常系_キーが同期されjson有効性維持(self, tmp_path):
        home = _make_home(tmp_path, secrets=DUMMY_SECRETS, settings=DUMMY_SETTINGS)
        code, out = run_sh(SYNC, home)
        assert code == 0
        d = json.loads((home / ".claude" / "settings.json").read_text())
        assert d["env"]["ANTHROPIC_AUTH_TOKEN"] == "dummy-anthropic-token-456"
        assert d["env"]["BRAVE_API_KEY"] == "dummy-brave-789"
        assert d["mcpServers"]["brave-search"]["env"]["BRAVE_API_KEY"] == "dummy-brave-789"
        assert d["mcpServers"]["glm"]["env"]["GLM_API_KEY"] == "dummy-glm-key-123"
        assert d["mcpServers"]["minimax"]["env"]["MINIMAX_API_KEY"] == "dummy-minimax-abc"

    def test_冪等性_2回目実行でsettings内容が同一(self, tmp_path):
        """同期の冪等性: 2回連続実行しても settings.json の中身は同一."""
        home = _make_home(tmp_path, secrets=DUMMY_SECRETS, settings=DUMMY_SETTINGS)
        run_sh(SYNC, home)
        first = (home / ".claude" / "settings.json").read_text()
        code, _ = run_sh(SYNC, home)
        second = (home / ".claude" / "settings.json").read_text()
        assert code == 0
        assert first == second
        # 2回目は md5 変更なしだが内容同一であれば OK（URL上書き含め安定）

    def test_未定義キーは既存値を維持(self, tmp_path):
        """secrets に無いキー（例: MINIMAX_API_FALLBACK）は既存 settings 値を壊さない."""
        settings = dict(DUMMY_SETTINGS)
        settings["env"]["CUSTOM_KEEP"] = "keep-me"
        home = _make_home(tmp_path, secrets=DUMMY_SECRETS, settings=settings)
        code, _ = run_sh(SYNC, home)
        assert code == 0
        d = json.loads((home / ".claude" / "settings.json").read_text())
        assert d["env"]["CUSTOM_KEEP"] == "keep-me"

    def test_壊れたsettings_jsonならexit1でクラッシュしない(self, tmp_path):
        home = _make_home(tmp_path, secrets=DUMMY_SECRETS, settings={})
        (home / ".claude" / "settings.json").write_text("{broken json!!", encoding="utf-8")
        code, out = run_sh(SYNC, home)
        assert code == 1
        assert "jqパースエラー" in out

    def test_ステータスファイルに結果を書く(self, tmp_path):
        home = _make_home(tmp_path, secrets=DUMMY_SECRETS, settings=DUMMY_SETTINGS)
        run_sh(SYNC, home)
        status = Path("/tmp/claude-startup/secrets-sync.status").read_text()
        assert "Secrets同期" in status


# ---- post-tool-settings-sync.sh ----

class TestPostToolSync:
    def test_未編集パスなら即exit0(self, tmp_path):
        home = _make_home(tmp_path, secrets=None, settings=None)
        code, _ = run_sh(POST_TOOL, home, {"CLAUDE_TOOL_INPUT_FILE_PATH": "/tmp/other.txt"})
        assert code == 0

    def test_空パスなら即exit0(self, tmp_path):
        home = _make_home(tmp_path, secrets=None, settings=None)
        code, _ = run_sh(POST_TOOL, home, {"CLAUDE_TOOL_INPUT_FILE_PATH": ""})
        assert code == 0


# ---- load-secrets.sh ----

class TestLoadSecrets:
    def test_読み込み件数をステータスに書く(self, tmp_path):
        secrets = "export A=1\n# comment\nexport B=2\n\nexport C=3\n"
        home = _make_home(tmp_path, secrets=secrets, settings=None)
        code, _ = run_sh(LOAD, home)
        assert code == 0
        status = Path("/tmp/claude-startup/secrets.status").read_text()
        assert "3件" in status  # コメント・空行を除く3行

    def test_ファイル不在でもexit0(self, tmp_path):
        home = _make_home(tmp_path, secrets=None, settings=None)
        code, _ = run_sh(LOAD, home)
        assert code == 0
