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
