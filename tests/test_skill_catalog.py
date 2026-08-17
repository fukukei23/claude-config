"""generate-skill-catalog.py（SessionStart・スキルカタログ自動生成）のテスト.

絶対パス定数を一時環境に差し替えて main() を含め検証（実SSOTを書き換えない）。

実行: cd ~/projects/claude-config && python3 -m pytest tests/test_skill_catalog.py -q
"""

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "session" / "generate-skill-catalog.py"

_spec = importlib.util.spec_from_file_location("skill_catalog", SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


# ---- parse_frontmatter ----

class TestParseFrontmatter:
    def test_通常のnameとdescription(self, tmp_path):
        p = tmp_path / "SKILL.md"
        p.write_text("---\nname: myskill\ndescription: 説明文\n---\n# 本体\n")
        fm = mod.parse_frontmatter(p)
        assert fm["name"] == "myskill"
        assert fm["description"] == "説明文"

    def test_ブロックスカラーdescription(self, tmp_path):
        p = tmp_path / "SKILL.md"
        p.write_text("---\nname: bs\ndescription: >\n  一行目。\n  二行目。\n---\n")
        fm = mod.parse_frontmatter(p)
        assert "一行目。" in fm["description"]
        assert "二行目。" in fm["description"]

    def test_frontmatter無しは空dict(self, tmp_path):
        p = tmp_path / "SKILL.md"
        p.write_text("# 本文だけ\n")
        assert mod.parse_frontmatter(p) == {}

    def test_読込失敗は空dict(self, tmp_path):
        assert mod.parse_frontmatter(tmp_path / " absent.md") == {}


# ---- truncate ----

def test_truncate_短い文はそのまま():
    assert mod.truncate("short") == "short"


def test_truncate_長い文は120字で切れて省略記号():
    s = "あ" * 200
    out = mod.truncate(s)
    assert out.startswith("あ" * 120)
    assert out.endswith("…")


def test_truncate_パイプと改行を置換():
    assert "|" not in mod.truncate("a|b\nc")
    assert "\n" not in mod.truncate("a|b\nc")


# ---- main()（一時環境・全パス差し替え） ----

def _setup_env(tmp_path, skills=None, settings=None, plugins=None):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    for name, fm in (skills or {}).items():
        d = skills_dir / name
        d.mkdir()
        (d / "SKILL.md").write_text(f"---\n{fm}\n---\n# {name}\n")
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps(settings or {}))
    cache = tmp_path / "cache"
    cache.mkdir()
    for org, plugin in (plugins or []):
        pdir = cache / org / plugin
        pdir.mkdir(parents=True)
        (pdir / "SKILL.md").write_text(
            f"---\nname: {plugin}-skill\ndescription: plugin desc\n---\n")
    output = tmp_path / "out" / "SKILL_CATALOG.md"
    # モジュール定数を差し替え
    mod.SETTINGS, mod.SKILLS_DIR, mod.PLUGIN_CACHE, mod.OUTPUT = (
        settings_file, skills_dir, cache, output)
    return output


def test_main_自作スキルとmcpセクションを生成(tmp_path, monkeypatch):
    output = _setup_env(
        tmp_path,
        skills={"alpha": "name: alpha\ndescription: アルファ技"},
        settings={"mcpServers": {"glm": {}, "brave-search": {}},
                  "enabledPlugins": {}})
    mod.main()
    text = output.read_text()
    assert "# Skill & Plugin カタログ" in text
    assert "`alpha`" in text and "アルファ技" in text
    assert "## 2. Plugin Skills" in text
    assert "## 3. MCP Servers" in text
    assert "`glm`" in text
    assert "GLM-5.3 LLM" in text  # MCP_DESC 辞書


def test_main_有効プラグインのみ掲載(tmp_path):
    output = _setup_env(
        tmp_path,
        skills={},
        settings={"enabledPlugins": {"plugin-a@org1": True, "plugin-b@org1": False}},
        plugins=[("org1", "plugin-a"), ("org1", "plugin-b")])
    mod.main()
    text = output.read_text()
    assert "plugin-a" in text
    assert "plugin-b" not in text  # 無効プラグインは載らない


def test_main_ja_desc優先(tmp_path):
    """JA_DESC に登録済み名は description より優先."""
    output = _setup_env(
        tmp_path,
        skills={"brainstorming": "name: brainstorming\ndescription: english desc"},
        settings={})
    mod.main()
    text = output.read_text()
    assert "実装前にユーザー意図" in text   # JA_DESC の日本語
    assert "english desc" not in text


def test_main_存在しないパスでもクラッシュしない(tmp_path, monkeypatch):
    mod.SETTINGS = tmp_path / "none.json"
    mod.SKILLS_DIR = tmp_path / "none-skills"
    mod.PLUGIN_CACHE = tmp_path / "none-cache"
    mod.OUTPUT = tmp_path / "o" / "cat.md"
    mod.main()
    assert mod.OUTPUT.exists()
