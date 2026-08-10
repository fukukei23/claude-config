"""collector — GitHub Trending 取得 + gh CLI 累計★取得。"""
import re
import subprocess
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

TRENDING_URL = "https://github.com/trending"
TRENDING_LIMIT = 25
ALLOWED_HOSTS = {"github.com", "www.github.com"}


def _validate_url(url: str) -> None:
    """SSRF防止: httpsスキーム+github.comホストのみ許可。"""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"不正スキーマ: {parsed.scheme}(https必須)")
    if parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"不正ホスト: {parsed.hostname}(github.comのみ許可)")


def fetch_trending_html(url: str = TRENDING_URL, timeout: int = 15) -> str:
    """GitHub Trending ページのHTMLを取得する(SSRF対策済:github.comのみ)。"""
    _validate_url(url)
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def parse_trending_html(html: str, limit: int = TRENDING_LIMIT) -> list[dict]:
    """Trending HTMLから上位リポジトリ情報を抽出する。

    戻り値: [{name, url, description, stars_today}, ...]
    """
    soup = BeautifulSoup(html, "html.parser")
    entries: list[dict] = []
    for article in soup.select("article.Box-row")[:limit]:
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


def _gh_stargazers(name: str, timeout: int = 15) -> int | None:
    """gh CLI で累計★取得。失敗時 None。"""
    try:
        out = subprocess.run(
            ["gh", "api", f"repos/{name}", "--jq", ".stargazers_count"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return int(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None
    except Exception:
        return None


def gh_auth_ok() -> bool:
    """gh CLI 認証有効か。"""
    try:
        return subprocess.run(
            ["gh", "auth", "status"], capture_output=True, timeout=10
        ).returncode == 0
    except Exception:
        return False


def enrich_stars(entry: dict) -> dict:
    """累計★+成長率を付加。gh失敗時 stars_total=-1(N/A)・growth_rate=0.0。"""
    total = _gh_stargazers(entry["name"])
    entry["stars_total"] = total if total is not None else -1
    if total and total > 0:
        entry["growth_rate"] = round(entry["stars_today"] / total, 4)
    else:
        entry["growth_rate"] = 0.0
    return entry
