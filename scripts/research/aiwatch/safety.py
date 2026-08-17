"""safety — フル自律cronの安全機構(gh認証チェック・HTML sanity・フォールバック判定)。"""
from aiwatch import collector, guide_generator


def ensure_gh_auth() -> tuple[bool, str]:
    """gh CLI API呼出可能か。失敗時は警告メッセージ(処理は継続・★N/Aで)。"""
    if collector.gh_auth_ok():
        return True, "gh認証OK"
    return False, "⚠️ gh API失敗(認証またはレート制限)・累計★はN/Aで継続"


def gh_na_summary(entries: list[dict]) -> str:
    """enrich後の N/A 件数から gh API 実績を要約(事後実測シグナル)。

    事前プローブ(gh_auth_ok)と異なり、実際の★取得結果に基づくため
    プローブ成功≠API成功 の隙間を事後検出できる。
    """
    na = sum(1 for e in entries if e.get("stars_total") == -1)
    total = len(entries)
    status = "gh正常" if na == 0 else "gh API失敗あり(認証または一時障害)"
    return f"{total}件中{na}件N/A={status}"


def verify_pages_html(html: str) -> tuple[bool, str]:
    """Pages公開前のHTML健全性検証。NG時はcommit skip理由を返す。"""
    if guide_generator.html_sanity_ok(html):
        return True, "HTML sanity OK"
    return False, "⚠️ HTML sanity NG・commit skip・前回版維持"


def should_commit(html_ok: bool, dry_run: bool = False) -> tuple[bool, str]:
    """commit実行可否を総合判定。

    dry_run時は常にFalse(Phase1)。
    ポリシー(fail-open・2026-08-17正式決定): gh失敗は★N/Aで処理継続
    かつ commit 可。よって本関数は gh 状態を受け取らない
    (旧 gh_ok 引数は未使用のデッドパラメータだったため削除)。
    HTML失敗のみ commit skip。
    """
    if dry_run:
        return False, "dry-runモード・commit skip"
    if not html_ok:
        return False, "HTML sanity NG・commit skip"
    return True, "commit可"


def fallback_to_rulestars(llm_failed: bool, cap_exceeded: bool) -> bool:
    """MiniMax失敗/キャップ超過時にルール★へフォールバックするか。"""
    return llm_failed or cap_exceeded
