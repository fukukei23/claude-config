"""safety — フル自律cronの安全機構(gh認証チェック・HTML sanity・フォールバック判定)。"""
from aiwatch import collector, guide_generator


def ensure_gh_auth() -> tuple[bool, str]:
    """gh CLI認証有効か。無効時は警告メッセージ(処理は継続・★N/Aで)。"""
    if collector.gh_auth_ok():
        return True, "gh認証OK"
    return False, "⚠️ gh認証切れ・累計★はN/Aで継続(PATフォールバック推奨)"


def verify_pages_html(html: str) -> tuple[bool, str]:
    """Pages公開前のHTML健全性検証。NG時はcommit skip理由を返す。"""
    if guide_generator.html_sanity_ok(html):
        return True, "HTML sanity OK"
    return False, "⚠️ HTML sanity NG・commit skip・前回版維持"


def should_commit(
    gh_ok: bool, html_ok: bool, dry_run: bool = False
) -> tuple[bool, str]:
    """commit実行可否を総合判定。

    dry_run時は常にFalse(Phase1)。
    gh失敗は★N/Aで継続(commit可)・HTML失敗はcommit skip。
    """
    if dry_run:
        return False, "dry-runモード・commit skip"
    if not html_ok:
        return False, "HTML sanity NG・commit skip"
    return True, "commit可"


def fallback_to_rulestars(llm_failed: bool, cap_exceeded: bool) -> bool:
    """MiniMax失敗/キャップ超過時にルール★へフォールバックするか。"""
    return llm_failed or cap_exceeded
