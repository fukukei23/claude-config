"""aiwatch.env_profiler のユニットテスト。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiwatch import env_profiler  # noqa: E402

MCP_SAMPLE = """> **有効サーバー: 4個**
> - brave-search（検索）
> - glm（LLM）
> - minimax（フォールバック）
> - minimax-official（メディア生成）
> - ※ minimax-video / mermaid / context7 は無効化
"""

REPO_INDEX_SAMPLE = """repositories:
  - name: NexusCore
    visibility: public
    status: active
  - name: krotam
    status: archived
  - name: orchestrix
    status: development
"""


def test_extract_mcp_active_and_disabled():
    active, disabled = env_profiler.extract_mcp_from_guide(MCP_SAMPLE)
    assert "brave-search" in active
    assert "minimax-official" in active
    assert len(active) == 4
    assert "mermaid" in disabled
    assert "context7" in disabled


def test_extract_projects_active_only():
    projects = env_profiler.extract_projects_from_repo_index(REPO_INDEX_SAMPLE)
    assert "NexusCore" in projects
    assert "orchestrix" in projects
    assert "krotam" not in projects  # archived除外


def test_build_profile_uses_fake_sources(tmp_path, monkeypatch):
    mcp = tmp_path / "mcp.md"
    mcp.write_text(MCP_SAMPLE)
    idx = tmp_path / "idx.yaml"
    idx.write_text(REPO_INDEX_SAMPLE)
    skills = tmp_path / "skills"
    (skills / "multi-llm-review").mkdir(parents=True)
    (skills / "ssot-record").mkdir(parents=True)

    p = env_profiler.build_profile(
        mcp_guide=mcp, repo_index=idx, skills_dir=skills, today="2026-08-11"
    )
    assert "brave-search" in p.mcp_active
    assert "NexusCore" in p.projects
    assert "review" in p.skill_categories
    assert "record" in p.skill_categories
    assert p.fetched_at == "2026-08-11"
    assert len(p.past_decisions) == 2


def test_load_cached_profile_fresh(tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    cached_data = {
        "mcp_active": ["cached"],
        "mcp_disabled": [],
        "projects": [],
        "skill_categories": [],
        "past_decisions": [],
        "fetched_at": "2026-08-10",  # 1日前=新鮮
    }
    cache.write_text(json.dumps(cached_data), encoding="utf-8")
    # build_profile が呼ばれないようSSOTを空に
    monkeypatch.setattr(env_profiler, "MCP_GUIDE", tmp_path / "missing.md")

    p = env_profiler.load_cached_profile(cache_file=cache, today="2026-08-11")
    assert p.mcp_active == ["cached"]  # キャッシュ再利用


def test_load_cached_profile_stale_rebuilds(tmp_path):
    cache = tmp_path / "cache.json"
    cached_data = {
        "mcp_active": ["stale"],
        "mcp_disabled": [],
        "projects": [],
        "skill_categories": [],
        "past_decisions": [],
        "fetched_at": "2026-01-01",  # 7ヶ月前=陳腐化
    }
    cache.write_text(json.dumps(cached_data), encoding="utf-8")
    mcp = tmp_path / "mcp.md"
    mcp.write_text(MCP_SAMPLE)

    # キャッシュ陳腐化→再抽出(build_profile のデフォルトSSOTを使う=実環境依存)
    # テスト容易化のため build_profile をモック
    import aiwatch.env_profiler as ep

    def fake_build(**kwargs):
        from aiwatch.models import EnvProfile
        return EnvProfile(["rebuilt"], [], [], [], [], "2026-08-11")

    ep.build_profile = fake_build  # type: ignore
    p = ep.load_cached_profile(cache_file=cache, today="2026-08-11")
    assert p.mcp_active == ["rebuilt"]  # 再抽出された
