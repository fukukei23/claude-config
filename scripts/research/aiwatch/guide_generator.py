"""guide_generator — source MD生成 + convert.py起動 + HTML sanity check。

ガイド構成(単一ページ・スマホ最優先):
  📈 今週のバズ(TOP・★today順) / 🌱 定着中 / 🆕 新着 / 🗄️ アーカイブ(折畳)
  フッタ: 📊 在庫健全性 + 🤖 今週の評価コスト
"""
import subprocess
from pathlib import Path

from aiwatch.models import EvaluatedRepo

# ai-trending-guide リポジトリのパス(テストで monkeypatch 可)
GUIDE_REPO = Path("/home/yn4416/projects/ai-trending-guide")
SOURCE_FILE = GUIDE_REPO / "source" / "index.md"
CONVERT_SCRIPT = GUIDE_REPO / "convert.py"
MIN_HTML_CHARS = 500
MIN_ENTRIES = 1


def _star_icon(star: int) -> str:
    return "★" * star + "☆" * (5 - star)


def _format_eval_methods(methods) -> str:
    """eval_methods dict を 'llm:25/rule_fallback:5' 形式に整形。"""
    if not methods or not isinstance(methods, dict):
        return "?"
    return "/".join(f"{k}:{v}" for k, v in methods.items())


def _eval_icon(method: str) -> str:
    if method == "llm":
        return "🤖"
    if method == "rule_fallback":
        return "⚙️"
    return "👤"


def render_repo_card(e: EvaluatedRepo, desc_map: dict | None = None) -> str:
    """1リポのカードMDを生成。desc_map に日本語訳があれば優先(Phase2翻訳・summary/detail/plain 3段階)。"""
    r = e.repo
    growth_pct = f"{r.growth_rate * 100:.1f}%" if r.growth_rate > 0 else "N/A"
    total_str = f"{r.stars_total:,}" if r.stars_total >= 0 else "N/A"
    info = (desc_map or {}).get(r.name)
    if isinstance(info, dict):
        summary = info.get("summary") or r.description
        detail = info.get("detail", "")
        plain = info.get("plain", "")
    else:
        summary = info or r.description
        detail = ""
        plain = ""
    card = (
        f"### {_eval_icon(e.eval_method)} [{r.name}]({r.url})\n"
        f"\n{_star_icon(e.fit_star)}  "
        f"**今日★{r.stars_today}** / 累計★{total_str} / 成長率{growth_pct}  "
        f"`{r.tag}`\n"
        f"\n{summary}\n"
    )
    if detail:
        card += f"\n📖 詳説: {detail}\n"
    if plain:
        card += f"\n💡 かみ砕くと: {plain}\n"
    card += f"\n> {e.eval_text}\n"
    return card


def render_source_md(
    evaluated: list[EvaluatedRepo],
    metrics: dict,
    cost: dict,
    week_label: str = "",
    desc_map: dict | None = None,
) -> str:
    """ガイド全体のsource MDを生成。

    evaluated: 評価済みリポ(★降推奨)
    metrics: {active, avg_days, freshness, pending, archived, declined}
    cost: {usd, count, eval_method_breakdown}
    desc_map: {name: japanese_desc}(Phase2翻訳・なければ英語フォールバック)
    """
    # ★降順ソート
    sorted_evals = sorted(evaluated, key=lambda e: e.fit_star, reverse=True)
    buzz = [e for e in sorted_evals if e.repo.stars_today >= 100]
    teijyo = [e for e in sorted_evals if e.repo.tag == "定着"]
    new_entries = [e for e in sorted_evals if e.repo.tag in ("初見", "2週連続")]

    sections: list[str] = [
        f"# 📈 AI Trending Watch{week_label}",
        "",
        "> 毎週自動更新。あなたのClaude Code環境に特化しておすすめを評価。",
        "",
        f"## 📈 今週のバズ(TOP {len(buzz)}件)",
        "",
    ]
    if buzz:
        sections.extend(render_repo_card(e, desc_map) for e in buzz[:10])
    else:
        sections.append("_(今週のバズなし)_")

    sections.extend(["", f"## 🌱 定着中(3週以上・{len(teijyo)}件)", ""])
    sections.extend(render_repo_card(e, desc_map) for e in teijyo[:10])

    sections.extend(["", f"## 🆕 新着({len(new_entries)}件)", ""])
    sections.extend(render_repo_card(e, desc_map) for e in new_entries[:15])

    # フッタ: ダッシュボード + コスト
    sections.extend([
        "",
        "---",
        "",
        "## 📊 在庫健全性",
        "",
        f"- active/pending: **{metrics.get('active', '?')}件**",
        f"- 平均滞在: **{metrics.get('avg_days', '?')}日**",
        f"- プロファイル鮮度: **{metrics.get('freshness', '?')}日**",
        f"- archived: {metrics.get('archived', '?')} / declined: {metrics.get('declined', '?')}",
        "",
        "## 🤖 今週の評価コスト",
        "",
        f"- **${cost.get('usd', 0):.4f}** / {cost.get('count', '?')}件評価",
        f"- 評価方法: {_format_eval_methods(cost.get('eval_methods'))}",
        f"- 週$20キャップ対比: {((cost.get('usd', 0) / 20) * 100):.2f}%",
        "",
    ])

    return "\n".join(sections)


def html_sanity_ok(
    html: str, min_chars: int = MIN_HTML_CHARS, min_entries: int = MIN_ENTRIES
) -> bool:
    """生成HTMLの健全性チェック(空/破損検知)。

    必須: <html>存在 / <body>存在 / 文字数>min / リポカード数≥min(article or ###)
    """
    if not html or len(html) < min_chars:
        return False
    if "<html" not in html.lower() or "<body" not in html.lower():
        return False
    entry_count = html.count("<article") + html.count("<h3") + html.count("<h2")
    return entry_count >= min_entries


def run_convert(guide_repo: Path = GUIDE_REPO, timeout: int = 60) -> tuple[bool, str]:
    """convert.py を起動しHTML生成。戻り値: (成功, メッセージ)。"""
    try:
        result = subprocess.run(
            ["python3", "convert.py"],
            cwd=str(guide_repo),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return True, "convert.py OK"
        return False, f"convert.py exit={result.returncode}: {result.stderr[:200]}"
    except subprocess.TimeoutExpired:
        return False, "convert.py timeout"
    except Exception as exc:
        return False, f"convert.py 例外: {exc}"


def write_source(
    content: str, source_file: Path = SOURCE_FILE
) -> None:
    """source MD をファイル出力。"""
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text(content, encoding="utf-8")
