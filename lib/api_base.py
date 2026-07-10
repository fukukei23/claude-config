"""API共通基盤: エラー処理・タイムアウト・JSON出力・キャッシュ保存.

全APIスクリプト（gemini.py, lastfm.py等）がこの基盤を経由して
統一されたJSON形式で結果を返す。
"""
import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable


def make_error_result(error: str) -> dict:
    """例外を統一JSON形式のエラー結果に正規化する.

    Args:
        error: エラーメッセージ文字列

    Returns:
        {"status":"error","summary":null,"full_data":null,"error":<msg>}
    """
    return {
        "status": "error",
        "summary": None,
        "full_data": None,
        "error": error,
    }


def _cache_dir() -> Path:
    """full_dataキャッシュ保存ディレクトリ（~/tmp/api_cache/）を返す."""
    d = Path.home() / "tmp" / "api_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def make_success_result(summary: str, full_data: Any, cache_key: str) -> dict:
    """成功結果を統一JSON形式で生成し、full_dataをキャッシュに保存する.

    Args:
        summary: CCに渡す要約（500トークン以内推奨）
        full_data: Gemini/APIの生レスポンス（キャッシュに保存・CCには渡さない）
        cache_key: キャッシュファイル名の一意キー

    Returns:
        {"status":"ok","summary":<str>,"full_data":<cache_path>,"error":null}
    """
    cache_path = _cache_dir() / f"{cache_key}.json"
    cache_path.write_text(
        json.dumps(full_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "status": "ok",
        "summary": summary,
        "full_data": str(cache_path),
        "error": None,
    }


def run_api(
    call_fn: Any,
    summary_fn: Any,
    cache_key: str,
    timeout: int = 60,
) -> dict:
    """API呼び出しをラップし、例外を捕捉して統一JSONで返す.

    Args:
        call_fn: 引数なし・API呼び出しを行い結果を返す関数
        summary_fn: (result, cache_key)を受け取りmake_success_resultを返す関数
        cache_key: キャッシュファイル名の一意キー
        timeout: タイムアウト秒（現状はドキュメント目的・将来signalで適用）

    Returns:
        成功時はsummary_fnの戻り値、例外時はmake_error_resultの戻り値
    """
    try:
        result = call_fn()
        return summary_fn(result, cache_key)
    except Exception as exc:  # noqa: BLE001 - 共通基盤は全例外を統一形式へ
        return make_error_result(f"{type(exc).__name__}: {exc}")


# =========================================================================
# モデル陳腐化耐性メカニズム（5層）
#   ①設定外部化(_load_config/_load_candidates) ②自動切替(resolve_gemini_model/
#   run_api_with_fallback) ③陳腐化察知(RuntimeError+代替提案) ④観測ログ(_log_stats)
#   ⑤失敗モデル短期キャッシュ(_record_failed_model/_is_recently_failed)
#   レビュー合意: 429=バックオフリトライ(フォールバック対象外)・403/404/5xx=次候補
# =========================================================================

_REPO_ROOT = Path(__file__).resolve().parents[1]
_STATS_PATH = _cache_dir() / "gemini_stats.jsonl"
_FAILED_PATH = _cache_dir() / "failed_models.json"
_GEMINI_MODELS_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _normalize_model_name(name: str) -> str:
    """ListModels の 'models/gemini-x' 表記を generateContent の 'gemini-x' に正規化する.

    Args:
        name: モデル名（ListModels は 'models/' prefix 付き）

    Returns:
        prefix を除去した正規化モデル名
    """
    return name[len("models/"):] if name.startswith("models/") else name


def _models_cache_path(api_key: str) -> Path:
    """APIキーのSHA256ハッシュから ListModels キャッシュパスを生成する."""
    digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]
    return _cache_dir() / f"gemini_models_{digest}.json"


def _list_models_cached(api_key: str, ttl_hours: int = 24, force: bool = False) -> set[str]:
    """SDK 経由で ListModels を取得（24h キャッシュ・force=True でinvalidate）.

    Args:
        api_key: Gemini APIキー
        ttl_hours: キャッシュ有効時間
        force: True ならキャッシュ無視で再取得

    Returns:
        利用可能モデル名の集合（正規化済）
    """
    cache = _models_cache_path(api_key)
    now = time.time()
    if not force and cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if now - data.get("fetched_at", 0) < ttl_hours * 3600:
                return set(data.get("models", []))
        except Exception:
            pass
    from google import genai  # 遅延import（api_base のロード時依存を避ける）

    client = genai.Client(api_key=api_key)
    names = {_normalize_model_name(m.name) for m in client.models.list()}
    cache.write_text(
        json.dumps({"fetched_at": now, "models": sorted(names)}, ensure_ascii=False),
        encoding="utf-8",
    )
    return names


def _list_models_rest(api_key: str) -> set[str]:
    """REST 経由(GET /models)で ListModels を取得（mcp-server.py 用・SDK非依存）.

    Args:
        api_key: Gemini APIキー

    Returns:
        利用可能モデル名の集合（正規化済）
    """
    req = urllib.request.Request(
        f"{_GEMINI_MODELS_BASE}?pageSize=200",
        headers={"x-goog-api-key": api_key},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return {_normalize_model_name(m["name"]) for m in data.get("models", [])}


def _load_config() -> dict:
    """gemini-models.json を複数候補パスから探して読み込む.

    探索順: 環境変数 GEMINI_MODELS_CONFIG → repo内 config/ → ~/.claude/config/

    Returns:
        設定 dict

    Raises:
        RuntimeError: 設定ファイルが見つからない場合
    """
    candidates = [
        os.environ.get("GEMINI_MODELS_CONFIG"),
        str(_REPO_ROOT / "config" / "gemini-models.json"),
        str(Path.home() / ".claude" / "config" / "gemini-models.json"),
    ]
    for p in candidates:
        if p and Path(p).exists():
            return json.loads(Path(p).read_text(encoding="utf-8"))
    raise RuntimeError(
        "gemini-models.json が見つかりません。"
        "config/gemini-models.json（正典: 30_RESEARCH/llm-models/models/gemini.md）を作成してください。"
    )


def _load_candidates(capability: str, paid_ok_limit: bool = False) -> list[str]:
    """capability で候補をフィルタする.

    Args:
        capability: "vision" / "audio" / "video" / "text"
        paid_ok_limit: False なら paid_ok:true の候補を除外（課金事故防止）

    Returns:
        候補モデルIDのリスト（config の並び順を維持＝優先順位）
    """
    cfg = _load_config()
    out: list[str] = []
    for c in cfg.get("candidates", []):
        if capability not in c.get("capabilities", []):
            continue
        if not paid_ok_limit and c.get("paid_ok", False):
            continue
        out.append(c["id"])
    return out


def _is_rate_limit(exc: Exception) -> bool:
    """429（ResourceExhausted）レートリミットエラーか判定する."""
    s = f"{type(exc).__name__} {exc}".lower()
    return any(k in s for k in ["429", "resourceexhausted", "rate limit", "quota"])


def _is_model_persistent_error(exc: Exception) -> bool:
    """403/404/5xx（モデル永続エラー=フォールバック対象）か判定する."""
    s = f"{type(exc).__name__} {exc}".lower()
    return any(
        k in s
        for k in [
            "403", "404", "permissiondenied", "notfound",
            "500", "501", "502", "503", "internalservererror", "deprecated",
        ]
    )


def _record_failed_model(model: str, ttl_minutes: int = 30) -> None:
    """失敗モデルを短期キャッシュに記録する（次回スキップ用）.

    Args:
        model: 失敗したモデル名
        ttl_minutes: キャッシュ有効分数（期限切れエントリは掃除）
    """
    data: dict[str, float] = {}
    if _FAILED_PATH.exists():
        try:
            data = json.loads(_FAILED_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    now = time.time()
    data = {k: v for k, v in data.items() if now - v < ttl_minutes * 60}
    data[model] = now
    _FAILED_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _is_recently_failed(model: str, ttl_minutes: int = 30) -> bool:
    """直近（デフォルト30分以内）で失敗したモデルか判定する."""
    if not _FAILED_PATH.exists():
        return False
    try:
        data = json.loads(_FAILED_PATH.read_text(encoding="utf-8"))
    except Exception:
        return False
    ts = data.get(model)
    return ts is not None and time.time() - ts < ttl_minutes * 60


def _log_stats(
    model: str, status: str, error: str = "", fallback_from: str = ""
) -> None:
    """観測ログ（~/tmp/api_cache/gemini_stats.jsonl）にJSONLで1行追記する.

    Args:
        model: 使用モデル名
        status: "attempt" / "ok" / "fail" / "error"
        error: エラー文字列（先頭200字）
        fallback_from: フォールバック元モデル名
    """
    entry = {
        "ts": time.time(),
        "model": model,
        "status": status,
        "error": error[:200],
        "fallback_from": fallback_from,
    }
    with _STATS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def resolve_gemini_model(
    candidates: list[str],
    api_key: str,
    use_rest: bool = False,
) -> str:
    """候補から実在し直近失敗していない最初のモデルを返す（全滅で陳腐化警告）.

    Args:
        candidates: 候補モデルIDリスト（優先順）
        api_key: Gemini APIキー
        use_rest: True なら REST 版 ListModels（mcp-server.py 用）

    Returns:
        実在する最初のモデル名

    Raises:
        RuntimeError: 全候補が利用不可（陳腐化）の場合。代替候補提案を含む
    """
    available = _list_models_rest(api_key) if use_rest else _list_models_cached(api_key)
    for m in candidates:
        nm = _normalize_model_name(m)
        if nm in available and not _is_recently_failed(nm):
            return nm
    flash_alt = sorted([m for m in available if "flash" in m])[:5]
    raise RuntimeError(
        "⚠️ Geminiモデル陳腐化の可能性: 候補 "
        f"{candidates} がいずれも利用不可（実在しない or 直近失敗）。"
        " config/gemini-models.json と 30_RESEARCH/llm-models/models/gemini.md を更新してください。"
        " 公式: https://ai.google.dev/gemini-api/docs/models "
        f"現在利用可能(Flash系): {flash_alt}"
    )


def run_api_with_fallback(
    call_fn_factory: Callable[[str], Callable[[], str]],
    candidates: list[str],
    api_key: str,
    use_rest: bool = False,
    max_backoff: int = 3,
) -> tuple[str, str]:
    """フォールバック付き API 実行。429=バックオフリトライ・403/404/5xx=次候補。

    Args:
        call_fn_factory: モデル名を受け取り「引数なしで実行し結果テキストを返す callable」を返す関数
        candidates: 候補モデルIDリスト（優先順）
        api_key: Gemini APIキー（ListModels検証用）
        use_rest: True なら REST 版で実在確認
        max_backoff: 429時の最大バックオフ試行回数

    Returns:
        (使用したモデル名, 結果テキスト)

    Raises:
        RuntimeError: 全候補失敗（陳腐化の可能性）
    """
    last_exc: Exception | None = None
    for model in candidates:
        nm = _normalize_model_name(model)
        if _is_recently_failed(nm):
            continue
        _log_stats(nm, "attempt")
        for attempt in range(max_backoff):
            try:
                result = call_fn_factory(nm)()
                _log_stats(nm, "ok")
                return nm, result
            except Exception as exc:
                if _is_rate_limit(exc) and attempt < max_backoff - 1:
                    time.sleep(2 ** attempt)  # 429=バックオフ（フォールバックしない）
                    continue
                if _is_model_persistent_error(exc):
                    _record_failed_model(nm)
                    _log_stats(nm, "fail", error=str(exc))
                    last_exc = exc
                    break  # 次候補へ
                _log_stats(nm, "error", error=str(exc))
                raise  # 予想外エラーは即raise
        else:
            continue
    raise RuntimeError(f"全候補失敗（陳腐化の可能性）。最終エラー: {last_exc}")
