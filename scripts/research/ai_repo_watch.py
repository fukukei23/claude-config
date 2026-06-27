"""GitHub Trending を週次スクレイピングし、新規AI関連リポジトリ候補を
pending-ai-repos.json に保存する。評価・導入判定は会話型（人間+Claude）。
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

GITHUB_LINK_RE = re.compile(r"\(https://github\.com/([\w.-]+/[\w.-]+)\)")


def extract_evaluated_repos(markdown_text: str) -> set[str]:
    """評価テーブルのMarkdownリンクURLから owner/repo の集合を抽出する。"""
    return set(GITHUB_LINK_RE.findall(markdown_text))


TRENDING_LIMIT = 25


def parse_trending_html(html: str) -> list[dict]:
    """GitHub Trendingページ(HTML)から上位リポジトリ情報を抽出する。"""
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for article in soup.select("article.Box-row")[:TRENDING_LIMIT]:
        link = article.select_one("h2 a")
        if link is None:
            continue
        repo_path = link.get("href", "").lstrip("/")
        desc_el = article.select_one("p")
        description = desc_el.get_text(strip=True) if desc_el else ""
        stars_today = 0
        for span in article.select("span"):
            text = span.get_text(strip=True)
            m = re.search(r"([\d,]+)\s+stars? today", text)
            if m:
                stars_today = int(m.group(1).replace(",", ""))
                break
        entries.append({
            "name": repo_path,
            "url": f"https://github.com/{repo_path}",
            "description": description,
            "stars_today": stars_today,
        })
    return entries


def filter_new_repos(trending: list[dict], evaluated: set[str]) -> list[dict]:
    """既評価済みリポジトリ(owner/repo)を除外して新規分のみ返す。"""
    return [r for r in trending if r["name"] not in evaluated]


def load_pending_repos(path: Path) -> list[dict]:
    """pending JSONを読み込む。ファイルがなければ空リスト。"""
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_pending_repos(path: Path, new_repos: list[dict], fetched_date: str) -> None:
    """新規分をpending JSONに追記保存する。既存nameは重複追加しない。"""
    existing = load_pending_repos(path)
    existing_names = {r["name"] for r in existing}

    for repo in new_repos:
        if repo["name"] in existing_names:
            continue
        existing.append({**repo, "fetched_date": fetched_date})

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


TRENDING_URL = "https://github.com/trending"
SSOT_EVAL_FILE = Path(
    "/home/yn4416/projects/obsidian-ssot/30_RESEARCH/MCPサーバー/"
    "2026-06-24_GitHub急上昇AIリポジトリ10選評価.md"
)
PENDING_FILE = Path("/home/yn4416/projects/obsidian-ssot/00_SYSTEM/stats/pending-ai-repos.json")
TREND_HISTORY_FILE = Path("/home/yn4416/projects/obsidian-ssot/00_SYSTEM/stats/repo-trend-history.json")
LOG_FILE = Path("/home/yn4416/projects/obsidian-ssot/00_SYSTEM/stats/ai-repo-watch.log")


def fetch_trending_html() -> str:
    """GitHub Trendingページを取得する。"""
    response = requests.get(TRENDING_URL, timeout=15)
    response.raise_for_status()
    return response.text


def _log(message: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{date.today().isoformat()} {message}\n")


def load_trend_history(path: Path) -> dict:
    """観測履歴JSONを読み込む。ファイルがなければ空dict。"""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_trend_history(path: Path, entries: list[dict], observed_date: str) -> dict:
    """観測履歴を更新して保存する。同日内の重複呼び出しではweeks_seenを増やさない。"""
    history = load_trend_history(path)

    for entry in entries:
        name = entry["name"]
        record = history.get(name)
        if record is None:
            history[name] = {
                "first_seen": observed_date,
                "last_seen": observed_date,
                "weeks_seen": 1,
            }
        elif record["last_seen"] != observed_date:
            record["last_seen"] = observed_date
            record["weeks_seen"] += 1

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return history


def tag_for_weeks_seen(weeks_seen: int) -> str:
    """観測週数に応じたタグ文字列を返す。"""
    if weeks_seen <= 1:
        return "初見"
    if weeks_seen == 2:
        return "2週連続"
    return "定着"


def main() -> int:
    try:
        html = fetch_trending_html()
    except Exception as exc:  # noqa: BLE001 - スクレイピング失敗は静かにskip
        _log(f"FETCH_ERROR: {exc}")
        return 0

    trending = parse_trending_html(html)
    today = date.today().isoformat()
    history = save_trend_history(TREND_HISTORY_FILE, trending, observed_date=today)

    evaluated_text = SSOT_EVAL_FILE.read_text(encoding="utf-8") if SSOT_EVAL_FILE.exists() else ""
    evaluated = extract_evaluated_repos(evaluated_text)
    new_repos = filter_new_repos(trending, evaluated)

    for repo in new_repos:
        weeks_seen = history[repo["name"]]["weeks_seen"]
        repo["tag"] = tag_for_weeks_seen(weeks_seen)

    if new_repos:
        save_pending_repos(PENDING_FILE, new_repos, fetched_date=today)
        _log(f"NEW_REPOS: {len(new_repos)}件保存")
    else:
        _log("NEW_REPOS: 0件")

    return 0

if __name__ == "__main__":
    sys.exit(main())
