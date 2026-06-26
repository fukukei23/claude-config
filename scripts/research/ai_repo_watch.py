"""GitHub Trending を週次スクレイピングし、新規AI関連リポジトリ候補を
pending-ai-repos.json に保存する。評価・導入判定は会話型（人間+Claude）。
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

GITHUB_LINK_RE = re.compile(r"\(https://github\.com/([\w.-]+/[\w.-]+)\)")


def extract_evaluated_repos(markdown_text: str) -> set[str]:
    """評価テーブルのMarkdownリンクURLから owner/repo の集合を抽出する。"""
    return set(GITHUB_LINK_RE.findall(markdown_text))


def parse_trending_html(html: str) -> list[dict]:
    """GitHub Trendingページ(HTML)から上位リポジトリ情報を抽出する。"""
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for article in soup.select("article.Box-row"):
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
