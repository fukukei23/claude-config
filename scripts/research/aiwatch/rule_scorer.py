"""rule_scorer — フォールバック★採点(キーワード+スター+定着度の機械判定)。

MiniMax失敗時のフォールバック兼下位リポの評価。中央値が★2になるよう調整。
"""
from aiwatch.models import EnvProfile, EvaluatedRepo, RepoStats

# ユーザ環境に関連しやすいキーワード(説明文に含まれると★+)
AI_RELEVANT_KEYWORDS = [
    "mcp", "agent", "cli", "rag", "llm", "automation", "workflow",
    "review", "skill", "obsidian", "knowledge", "scrape", "api",
]

# 非AI/環境非関連キーワード(含むと★マイナス)
OFF_TOPIC_KEYWORDS = [
    "jailbreak", "ios ", "android ", "game", "shader", "minecraft",
    "roblox", "fortnite",
]

# 環境プロファイル連携キーワード(profile の mcp_active/projects から派生)
def _profile_keywords(profile: EnvProfile) -> list[str]:
    kws: list[str] = []
    for mcp in profile.mcp_active:
        kws.append(mcp.lower())
    for proj in profile.projects:
        # プロジェクト名を小文字トークン化
        kws.extend(t.lower() for t in proj.replace("-", " ").split())
    return kws


def _count_keyword_hits(description: str, keywords: list[str]) -> int:
    desc_lower = description.lower()
    return sum(1 for k in keywords if k and k in desc_lower)


def score_repo(repo: RepoStats, profile: EnvProfile) -> EvaluatedRepo:
    """ルールベースでfit_star(1-5)・おすすめ文を生成。

    採点:
    - ベース1
    - AI関連キーワード合致 +1(1件以上) / +2(3件以上)
    - 環境プロファイル連携キーワード合致 +1
    - 累計★1万超 +1
    - stars_today 500超(バズ) +1
    - 定着(tag=定着) +1
    - OFF_TOPICキーワード -2
    - 上限5・下限1
    """
    star = 1
    reasons: list[str] = []

    ai_hits = _count_keyword_hits(repo.description, AI_RELEVANT_KEYWORDS)
    if ai_hits >= 3:
        star += 2
        reasons.append(f"AI関連キーワード{ai_hits}件")
    elif ai_hits >= 1:
        star += 1
        reasons.append(f"AI関連キーワード{ai_hits}件")

    profile_kws = _profile_keywords(profile)
    if _count_keyword_hits(repo.description, profile_kws) >= 1:
        star += 1
        reasons.append("環境プロファイル合致")

    if repo.stars_total >= 10000:
        star += 1
        reasons.append(f"累計★{repo.stars_total}")
    if repo.stars_today >= 500:
        star += 1
        reasons.append(f"今日★{repo.stars_today}(バズ)")
    if repo.tag == "定着":
        star += 1
        reasons.append("3週以上定着")

    off_hits = _count_keyword_hits(repo.description, OFF_TOPIC_KEYWORDS)
    if off_hits >= 1:
        star -= 2
        reasons.append(f"環境非関連({off_hits}件)")

    star = max(1, min(5, star))
    reason_text = "・".join(reasons) if reasons else "機械判定(要因弱)"
    eval_text = f"⚙️ルール採点 ★{star}({reason_text})"

    return EvaluatedRepo(repo=repo, fit_star=star, eval_text=eval_text, eval_method="rule_fallback")


def score_repos(repos: list[RepoStats], profile: EnvProfile) -> list[EvaluatedRepo]:
    """全リポを採点。"""
    return [score_repo(r, profile) for r in repos]
