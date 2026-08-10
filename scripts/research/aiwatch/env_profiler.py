"""env_profiler — SSOTからCC環境プロファイルを抽出(月次キャッシュ)。"""
import json
import re
from datetime import date, timedelta
from pathlib import Path

from aiwatch.models import EnvProfile

# SSOT ソース(テストで monkeypatch 可能なモジュール定数)
SSOT_DIR = Path("/home/yn4416/projects/obsidian-ssot")
MCP_GUIDE = SSOT_DIR / "00_SYSTEM" / "MCPツール使い分けガイド.md"
REPO_INDEX = SSOT_DIR / "00_SYSTEM" / "repo-index.yaml"
SKILLS_DIR = Path("/home/yn4416/projects/claude-config") / "skills"
CACHE_FILE = SSOT_DIR / "00_SYSTEM" / "stats" / "env-profile-cache.json"

CACHE_DAYS = 30  # 月次キャッシュ


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def extract_mcp_from_guide(text: str) -> tuple[list[str], list[str]]:
    """MCPガイド本文から(稼働中, 無効化履歴)を抽出。

    稼働中: '- <name>' 形式の箇条書き('※ ... は無効化'行より前)
    無効化: '※ <a> / <b> / ... は無効化' 行
    """
    active: list[str] = []
    disabled: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip("> ").strip()
        m_active = re.match(r"^- ([\w-]+)（", stripped)
        if m_active:
            active.append(m_active.group(1))
            continue
        m_disabled = re.search(r"※\s*(.+?)\s*は無効化", stripped)
        if m_disabled:
            parts = re.split(r"[／/、]", m_disabled.group(1))
            disabled.extend(p.strip() for p in parts if p.strip())
    return active, disabled


def extract_projects_from_repo_index(text: str) -> list[str]:
    """repo-index.yaml からアクティブプロジェクト名(status: active/development)を抽出。"""
    names: list[str] = []
    current: dict = {}
    for line in text.splitlines():
        m_name = re.match(r"^\s*- name:\s*(\S+)", line)
        if m_name:
            if current.get("name") and current.get("status") in ("active", "development"):
                names.append(current["name"])
            current = {"name": m_name.group(1)}
        m_status = re.match(r"^\s*status:\s*(\S+)", line)
        if m_status and current.get("name"):
            current["status"] = m_status.group(1)
    if current.get("name") and current.get("status") in ("active", "development"):
        names.append(current["name"])
    return names


def extract_skill_categories(skills_dir: Path) -> list[str]:
    """skills/ ディレクトリのスキル名から主要カテゴリを推定。"""
    try:
        names = [p.name for p in skills_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]
    except Exception:
        return []
    categories = set()
    keyword_map = {
        "review": ["multi-llm-review", "sentaku", "teian", "code-metrics", "code-simplify"],
        "record": ["ssot-record", "ssot-search", "new-session", "resume-session", "record-new-feature"],
        "music": ["make-song", "sangoku-song", "analyze-song", "reverse-engineer-song", "ai-music"],
        "guide": ["make-guide", "guide-builder", "update-guide", "textbook-guide", "html-guide"],
        "marketing": ["copywriting", "emails", "launch", "seo-audit", "ads", "social"],
    }
    for cat, keys in keyword_map.items():
        if any(k in names for k in keys):
            categories.add(cat)
    return sorted(categories)


def build_profile(
    mcp_guide: Path = MCP_GUIDE,
    repo_index: Path = REPO_INDEX,
    skills_dir: Path = SKILLS_DIR,
    today: str | None = None,
) -> EnvProfile:
    """SSOT読込→EnvProfile構築。"""
    today_str = today or date.today().isoformat()
    active_mcp, disabled_mcp = extract_mcp_from_guide(_read_text(mcp_guide))
    projects = extract_projects_from_repo_index(_read_text(repo_index))
    categories = extract_skill_categories(skills_dir)
    return EnvProfile(
        mcp_active=active_mcp,
        mcp_disabled=disabled_mcp,
        projects=projects,
        skill_categories=categories,
        past_decisions=[
            "MCPは4個に絞る(コンテキスト肥大教訓)",
            "codebase-memory-mcpは無効化(メモリ消費)",
        ],
        fetched_at=today_str,
    )


def load_cached_profile(cache_file: Path = CACHE_FILE, today: str | None = None) -> EnvProfile:
    """キャッシュが30日以内なら再利用・超過または未存在なら再抽出して保存。"""
    today_str = today or date.today().isoformat()
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            fetched = data.get("fetched_at", "")
            if fetched:
                age = date.fromisoformat(today_str) - date.fromisoformat(fetched)
                if age <= timedelta(days=CACHE_DAYS):
                    return EnvProfile(**data)
        except Exception:
            pass
    profile = build_profile(today=today_str)
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            json.dumps(profile.__dict__, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass
    return profile
