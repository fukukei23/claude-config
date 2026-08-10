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


def main(argv: list[str] | None = None) -> int:
    """週次パイプライン(Phase1: dry-run=rule★のみ・MiniMax評価なし)。

    --dry-run: ガイド生成するがcommit/pushしない(Phase1運用モード)。
    """
    import sys as _sys

    args = argv if argv is not None else _sys.argv[1:]
    dry_run = "--dry-run" in args

    # aiwatch ユニット遅延import(テストの分離維持)
    from aiwatch import collector, cost, env_profiler, guide_generator, lifecycle, rule_scorer, safety, translator
    from aiwatch.models import RepoStats

    try:
        today = date.today().isoformat()

        # 1. gh認証チェック(失敗しても★N/Aで継続)
        gh_ok, gh_msg = safety.ensure_gh_auth()
        _log(gh_msg)

        # 2. Trending収集 + gh CLI累計★
        html = collector.fetch_trending_html()
        entries = [collector.enrich_stars(e) for e in collector.parse_trending_html(html)]
        _log(f"TRENDING: {len(entries)}件収集")

        # 3. history更新(既存)
        history = save_trend_history(TREND_HISTORY_FILE, entries, observed_date=today)

        # 4. pending保存(既存・lifecycle用)・tag付与
        evaluated_text = SSOT_EVAL_FILE.read_text(encoding="utf-8") if SSOT_EVAL_FILE.exists() else ""
        evaluated = extract_evaluated_repos(evaluated_text)
        new_repos = filter_new_repos(entries, evaluated)
        for repo in new_repos:
            wh = history.get(repo["name"], {}).get("weeks_seen", 1)
            repo["tag"] = tag_for_weeks_seen(wh)
        if new_repos:
            save_pending_repos(PENDING_FILE, new_repos, fetched_date=today)
        _log(f"NEW_REPOS: {len(new_repos)}件保存(pending総数推移)")

        # 5. 環境プロファイル(月次キャッシュ)
        profile = env_profiler.load_cached_profile(today=today)

        # 6. ルール★採点(全件・Phase1はLLM評価なし)
        repos_stats = [
            RepoStats(
                name=e["name"], url=e["url"], description=e["description"],
                stars_today=e["stars_today"], stars_total=e.get("stars_total", -1),
                growth_rate=e.get("growth_rate", 0.0), tag=e.get("tag", "初見"),
            )
            for e in entries
        ]
        evaluated_repos = rule_scorer.score_repos(repos_stats, profile)

        # 6.5 description日本語翻訳(Phase2先取り・MiniMax直接API・失敗時は英語フォールバック)
        desc_map, trans_stats = translator.translate_descriptions(
            [e.repo for e in evaluated_repos]
        )
        _log(f"TRANSLATE: ok={trans_stats['ok']} {len(desc_map)}件 in={trans_stats['tokens_in']} out={trans_stats['tokens_out']}")

        # 7. lifecycle収束チェック(dry_run_stats)
        conv_ok, steady = lifecycle.convergence_check(
            weekly_inflow=len(entries), archive_after_weeks=4
        )
        _log(f"LIFECYCLE: 収束={'OK' if conv_ok else 'NG'} steady-state~{steady}件")

        # 8. ガイド生成
        loaded = load_pending_repos(PENDING_FILE)
        metrics = {
            "active": len(loaded), "avg_days": 14, "freshness": 0,
            "archived": sum(1 for r in loaded if r.get("tag") == "archived"),
            "declined": sum(1 for r in loaded if r.get("tag") == "declined"),
        }
        cost_rec = cost.record_usage(
            tokens_in=trans_stats["tokens_in"], tokens_out=trans_stats["tokens_out"],
            count=len(evaluated_repos),
            eval_methods={"rule_fallback": len(evaluated_repos)},
            week_label=today,
        )
        md = guide_generator.render_source_md(
            evaluated_repos, metrics, cost_rec, week_label=f" ({today})",
            desc_map=desc_map,
        )
        guide_generator.write_source(md, source_file=guide_generator.SOURCE_FILE)

        # 9. convert.py起動 + HTML sanity
        conv_ok2, conv_msg = guide_generator.run_convert()
        _log(conv_msg)
        html_path = guide_generator.GUIDE_REPO / "docs" / "chapters" / "index.html"
        if not html_path.exists():
            html_path = guide_generator.GUIDE_REPO / "docs" / "index.html"
        html_text = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
        html_ok, html_msg = safety.verify_pages_html(html_text)
        _log(html_msg)

        # 10. commit判定(dry_run時はpushしない)
        do_commit, commit_msg = safety.should_commit(gh_ok, html_ok, dry_run=dry_run)
        _log(f"{commit_msg} (dry_run={dry_run})")
        if do_commit:
            import subprocess
            subprocess.run(
                ["git", "add", "-A"], cwd=str(guide_generator.GUIDE_REPO), check=False
            )
            subprocess.run(
                ["git", "commit", "-m", f"chore: weekly auto-update ({today})"],
                cwd=str(guide_generator.GUIDE_REPO), check=False,
            )
            subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=str(guide_generator.GUIDE_REPO), check=False,
            )
            _log("GUIDE: commit&push完了")

        _log(f"DONE: entries={len(entries)} evaluated={len(evaluated_repos)} commit={do_commit}")
    except Exception as exc:  # noqa: BLE001 - 週次cronは無人実行のため全段で静かにskip
        _log(f"ERROR: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
