"""multi-llm-review ロジックの Python 関数化（auto-loop から呼出用）。

元: ~/.claude/skills/multi-llm-review/SKILL.md

auto-dev/run-task.sh から呼び出して、レビュアー LLM の出力テキストを
構造化データ（dict）へ正規化する役割を担う。

Phase 2/5 有効化（2026-08-12）:
- run_multi_llm_review() — Gemini + MiniMax の別ベンダー並列レビュー
- backend_kind 必須引数で「どの経路でどのベンダーを呼んだか」を判別
- 判定 3 値（両critical/片側critical+片側silent/両側critical未満）
- ベンダー数 < 2 は即 abort（多様性保証不能）
- API キー値のログ漏洩をマスク
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

SEVERITY_MAP: dict[str, str] = {
    "critical": "critical",
    "high": "high",
    "med": "med",
    "medium": "med",
    "low": "low",
}


def extract_json_from_text(text: str) -> dict[str, Any]:
    """テキスト内の JSON オブジェクトを抽出する。

    戦略: ```json ... ``` フェンス優先 → なければ {...} を greedy match。
    配列/プリミティブは対象外（このプロジェクトのレビュー出力は常にオブジェクト）。

    Raises:
        ValueError: オブジェクトとして解釈できる JSON が text 中に無い場合。
    """
    if not isinstance(text, str):
        raise ValueError("JSON object not found in text")

    # 1. コードフェンス（言語指定あり/なし両対応・非 greedy で最短一致）
    fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if fence_match:
        candidate = fence_match.group(1)
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # 2. greedy {...}（ネスト考慮・最初の { から対応する } まで）
    brace_start = text.find("{")
    if brace_start == -1:
        raise ValueError("JSON object not found in text")

    depth = 0
    end_index = -1
    for i in range(brace_start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end_index = i
                break

    if end_index == -1:
        raise ValueError("JSON object not found in text")

    candidate = text[brace_start : end_index + 1]
    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError("JSON object not found in text") from exc

    if not isinstance(obj, dict):
        raise ValueError("JSON object not found in text")

    return obj


def normalize_severity(severity: str) -> str:
    """severity 表記を critical/high/med/low のいずれかに正規化する。

    未知の値・大文字小文字の揺れ・空文字列はすべて 'low' にフォールバック
    （安全側：誤って高く評価しない）。
    """
    if not severity:
        return "low"
    return SEVERITY_MAP.get(severity.strip().lower(), "low")


def classify_review_item(review: str, objective: str) -> str:
    """レビュー指摘を目的関連性で 3 tier に分類する。

    - direct: objective のキーワードが review 内に直接出現
    - meta:   objective のキーワードは出ないが、何らかの指摘（レビュー作法等）
    - offtopic: 完全無関係（タイポ修正等・極端に短い or objective と被りなし）

    Args:
        review: レビュアーが生成した指摘テキスト。
        objective: 開発タスクの目的（例: 'メールバリデーション関数をRFC準拠にする'）。

    Returns:
        'direct' / 'meta' / 'offtopic' のいずれか。
    """
    obj_keywords = set(_tokenize(objective))
    rev_keywords = set(_tokenize(review))

    if obj_keywords & rev_keywords:
        return "direct"

    # meta: 何かしらの指摘はある（10 文字以上・トークンが1つ以上）
    if len(review) >= 10 and rev_keywords:
        return "meta"

    return "offtopic"


def _tokenize(text: str) -> list[str]:
    """簡易トークナイザ。

    - 漢字 + カタカナ連続スパン内の 2 文字スライディング substring
      （re.findall(r"[一-鿿]{2,}", text) は non-overlapping greedy なので
       "メールバリデーション関数" のように ASCII をまたぐ長い塊を扱えない。
       そこでカタカナ含めたスパンごとに 2 文字部分文字列を抽出する）
    - 英数字 3 文字以上の単語

    仕様書で示された "漢字 2 文字以上 + 英単語 3 文字以上" のセマンティクスを
    「スパン内 2 文字オーバーラップ substring」として実装する。これにより
    「メールバリデーション」と「バリデーション」のように塊の開始位置が
    異なるケースでも、共通する "バリデーション" 等の部分文字列を検出できる。

    注: カタカナ（ァ-ヴー）を含める理由は「メ」「ー」「ル」「バ」「リ」
    等がカタカナであり、漢字スパンだけでは "メールバリデーション" を
    1 つの塊として扱えないため。漢字のみ/カタカナのみ/混在いずれも対応。
    """
    import re
    # 1. 漢字+カタカナ連続スパン（1 文字以上の連続）を全て取得
    cjk_spans = re.findall(r"[一-鿿ァ-ヴー]+", text)
    # 2. 各スパン内の 2 文字スライディング substring
    cjk_subs: list[str] = []
    for span in cjk_spans:
        for i in range(len(span) - 1):
            cjk_subs.append(span[i] + span[i + 1])
    # 3. 英数字 3 文字以上の単語
    ascii_words = re.findall(r"[A-Za-z0-9_]{3,}", text)
    return cjk_subs + ascii_words


# =====================================================================
# Phase 2/5: multi-LLM review（別ベンダー並列レビュー・2026-08-12）
# =====================================================================

# --- dataclass ---


@dataclass
class ReviewItem:
    """個別レビュー指摘（LLM 出力の1件）。"""

    issue: str
    severity: str  # critical/high/med/low（正規化後）
    quote: str
    suggestion: str


@dataclass
class VendorReview:
    """1ベンダーのレビュー結果。"""

    vendor: str  # "gemini" / "minimax"
    backend_kind: str  # "gemini-sdk-rest" / "minimax-anthropic"
    items: list[ReviewItem]
    raw_status: str  # ok/empty/error-429/error-5xx/error-auth/error-exhausted
    model: str = ""
    fallback_used: bool = False
    error_detail: str = ""


@dataclass
class MultiReviewResult:
    """run_multi_llm_review の戻り値。"""

    reviews: list[VendorReview]
    verdict: str  # "ok" / "ng" / "abort"
    abort_reason: str = ""
    by_severity: dict[str, list[dict]] = field(
        default_factory=lambda: {"critical": [], "high": [], "med": [], "low": []}
    )


# --- 定数 ---

MINIMAX_URL = "https://api.minimax.io/anthropic/v1/messages"
MINIMAX_MODELS = ["MiniMax-M3", "MiniMax-M2.7"]
_SENSITIVE_HEADER_NAMES = {"x-api-key", "authorization", "api-key"}
_SECRET_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9]{6})[A-Za-z0-9]*"),
    re.compile(r"(Bearer\s+[A-Za-z0-9]{6})[A-Za-z0-9]*"),
    re.compile(r"(eyJ[A-Za-z0-9]{6})[A-Za-z0-9._-]*"),
]
NO_ISSUE_MARKERS = (
    "no issues",
    "no issues found",
    "見つからなかった",
    "問題ありません",
    "問題なし",
)


# --- APIキー/シークレット ---


def _load_secret(name: str) -> str:
    """環境変数 → ~/.secrets.env の順で APIキー値を取得。

    Returns:
        キー値文字列（未設定時は空文字）。
    """
    val = os.environ.get(name, "")
    if val:
        return val
    secrets = Path.home() / ".secrets.env"
    if secrets.exists():
        for line in secrets.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("export ") and "=" in line:
                k, _, v = line[len("export "):].partition("=")
                if k.strip() == name:
                    return v.strip().strip('"').strip("'")
    return ""


def _mask_str(s: str) -> str:
    """文字列中のシークレットらしき部分をマスク（例外メッセージ漏洩対策）。"""
    for pat in _SECRET_PATTERNS:
        s = pat.sub(r"\1<REDACTED>", s)
    return s


# --- 遅延 import（テスト時の依存爆発回避） ---


def _import_requests_post() -> Callable:
    """requests.post を遅延 import（テスト時は requester mock で回避可）。"""
    import requests

    return requests.post


def _import_gemini_runner() -> tuple[Callable, Callable]:
    """lib.api_base の (run_api_with_fallback, _load_candidates) を遅延 import。"""
    root = Path(__file__).resolve().parents[2]  # claude-config/
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from lib.api_base import _load_candidates, run_api_with_fallback

    return run_api_with_fallback, _load_candidates


# --- プロンプト組み立て ---


def _build_prompt(target: str, objective: str, viewpoint: str) -> str:
    """全レビュアー共通プロンプト（objective 先頭再注入・目的ホールド）。"""
    return (
        f"[当初目的] {objective}\n"
        f"[観点] {viewpoint}\n\n"
        "[対象]\n"
        f"{target}\n\n"
        "[出力形式] JSON配列のみで返答（挨拶・markdownコードブロック不要）:\n"
        '[{"issue": "...", "severity": "critical/high/med/low", '
        '"quote": "対象からのコピペ抜粋", "suggestion": "改善案"}]\n'
        "※ 最大7件。\n"
    )


def _truncate(target: str, max_chars: int = 12000) -> str:
    """コメント・docstring・空行削除で核心のみに圧縮（Gemini MAX_TOKENS対策）。

    Python の ``#`` コメント行・トリプルクォート・空行を削除。
    """
    lines = []
    in_triple = False
    for line in target.splitlines():
        stripped = line.strip()
        if '"""' in stripped or "'''" in stripped:
            in_triple = not in_triple
            continue
        if in_triple:
            continue
        if stripped.startswith("#"):
            continue
        if stripped == "":
            continue
        lines.append(line)
    out = "\n".join(lines)
    return out[:max_chars]


# --- Gemini 呼出（SDK + api_base フォールバック） ---


def _gemini_call_factory(
    prompt_text: str, api_key: str
) -> Callable[[str], Callable[[], str]]:
    """model 名を受け取り generate_content を実行する call() を返す（api_base 用）。

    maxOutputTokens=8000・temperature=0.4 を指定（思考モデル MAX_TOKENS 対策）。
    """

    def factory(model: str):
        def call() -> str:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents=prompt_text,
                config=types.GenerateContentConfig(
                    maxOutputTokens=8000, temperature=0.4
                ),
            )
            text = response.text or ""
            if not text.strip():
                raise RuntimeError(
                    "empty response from Gemini (possible MAX_TOKENS)"
                )
            return text

        return call

    return factory


def _extract_http_status(exc: Exception) -> int | None:
    """例外メッセージから HTTP ステータス(3桁)を抽出。"""
    m = re.search(r"\b([45]\d{2})\b", str(exc))
    return int(m.group(1)) if m else None


def _call_gemini(
    prompt: str, api_key: str, runner: tuple[Callable, Callable] | None = None
) -> tuple[str, str, str, str]:
    """Gemini への1回の呼出。戻り値: (text, model, raw_status, error_detail)。

    runner に (run_api_with_fallback, _load_candidates) を mock 注入可（テスト用）。
    """
    run_fn, load_cands = runner or _import_gemini_runner()
    candidates = load_cands("review", paid_ok_limit=True)
    if not candidates:
        return "", "", "error-exhausted", "review capability 候補なし"
    try:
        model, text = run_fn(
            _gemini_call_factory(prompt, api_key), candidates, api_key
        )
        if text and text.strip():
            return text, model, "ok", ""
        return "", model, "empty", "空応答(MAX_TOKENS?)"
    except Exception as exc:  # noqa: BLE001
        status = _extract_http_status(exc)
        msg = _mask_str(str(exc))
        if status == 401:
            return "", "", "error-auth", msg
        if status == 429:
            return "", "", "error-429", msg
        return "", "", "error-5xx", msg


def _call_gemini_with_retry(
    prompt: str,
    api_key: str,
    runner: tuple[Callable, Callable] | None = None,
    max_retries: int = 2,
) -> tuple[str, str, str, str, bool]:
    """空応答時に truncate → 再送（上限 max_retries）。fallback_used を返す。

    YAGNI凍結の例外: レビュー呼出失敗のリトライ最適化のみ解凍（縮退続行でない）。
    """
    fallback_used = False
    current = prompt
    for _attempt in range(max_retries):
        text, model, status, err = _call_gemini(current, api_key, runner)
        if status == "ok":
            return text, model, status, err, fallback_used
        if status == "empty":
            truncated = _truncate(current)
            if truncated == current:
                break  # これ以上圧縮不可
            current = truncated
            fallback_used = True
            continue
        return text, model, status, err, fallback_used
    return "", "", "empty", "truncate リトライ上限", fallback_used


# --- MiniMax 呼出（直接 requests・Anthropic 互換） ---


def _call_minimax(
    prompt: str,
    api_key: str,
    requester: Callable | None = None,
    timeout: int = 120,
) -> tuple[str, str, str, str]:
    """MiniMax Anthropic 互換へ直接 requests。戻り値: (text, model, raw_status, error_detail)。

    requester に requests.post 互換 callable を mock 注入可（テスト用）。
    候補リスト [M3, M2.7] を順に試行（フォールバック）。
    """
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    post = requester or _import_requests_post()
    last_err = ""
    for model in MINIMAX_MODELS:
        payload = {
            "model": model,
            "max_tokens": 8000,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            resp = post(MINIMAX_URL, headers=headers, json=payload, timeout=timeout)
            status = getattr(resp, "status_code", None)
            if status == 200:
                data = resp.json() if callable(getattr(resp, "json", None)) else {}
                text = ""
                for block in data.get("content", []):
                    if isinstance(block, dict) and block.get("type") == "text":
                        text += block.get("text", "")
                if text.strip():
                    return text, model, "ok", ""
                return "", model, "empty", "空応答"
            if status == 401:
                return "", model, "error-auth", "401"
            if status == 429:
                last_err = f"{model}:429"
                continue
            if status is not None and 500 <= status < 600:
                last_err = f"{model}:{status}"
                continue
            return "", model, f"error-{status}", f"HTTP {status}"
        except TimeoutError:
            last_err = f"{model}:timeout"
            continue
        except Exception as exc:  # noqa: BLE001
            return "", model, "error-5xx", _mask_str(str(exc))
    return "", "", "error-exhausted", last_err or "全モデル失敗"


# --- レビュー結果パース（既存4関数を後処理で再用） ---


def _parse_items(text: str, objective: str) -> list[ReviewItem]:
    """LLM 出力テキスト → ReviewItem リスト（既存 extract/normalize を使用）。

    JSON 配列を直接解析→取れなければオブジェクトの items/reviews キーを試行。
    """
    raw_list: list[Any] = []
    s = text.find("[")
    e = text.rfind("]")
    if s != -1 and e != -1 and e > s:
        try:
            parsed = json.loads(text[s:e + 1])
            if isinstance(parsed, list):
                raw_list = parsed
        except json.JSONDecodeError:
            raw_list = []
    if not raw_list:
        try:
            obj = extract_json_from_text(text)
            if isinstance(obj.get("items"), list):
                raw_list = obj["items"]
            elif isinstance(obj.get("reviews"), list):
                raw_list = obj["reviews"]
        except ValueError:
            raw_list = []
    items: list[ReviewItem] = []
    for it in raw_list:
        if not isinstance(it, dict):
            continue
        if not all(k in it for k in ("issue", "severity")):
            continue
        items.append(
            ReviewItem(
                issue=str(it.get("issue", "")),
                severity=normalize_severity(str(it.get("severity", ""))),
                quote=str(it.get("quote", "")),
                suggestion=str(it.get("suggestion", "")),
            )
        )
    return items


def _is_silent(review: VendorReview) -> bool:
    """silent/空応答判定（判定ポリシー (b) 用）。

    ok 以外の raw_status・0件指摘・"no issues" テンプレを silent 扱い。
    フォールバック発動時（能力差リスク）も silent 扱い（M5対策）。
    """
    if review.raw_status != "ok":
        return True
    if review.fallback_used:
        return True  # フォールバック先は能力差で silent リスク
    if len(review.items) == 0:
        return True
    joined = " ".join(i.issue.lower() for i in review.items)
    if any(marker in joined for marker in NO_ISSUE_MARKERS):
        return True
    return False


def _has_critical(review: VendorReview) -> bool:
    return any(i.severity == "critical" for i in review.items)


def _judge(reviews: list[VendorReview]) -> str:
    """判定 3 値ポリシー（silent agree 握り潰し防止）。

    (a) 両ベンダー critical → ng
    (b) 片側 critical + 片側 silent → ng
    (c) 両側 critical 未満 → ok
    """
    criticals = [r for r in reviews if _has_critical(r)]
    if len(criticals) >= 2:
        return "ng"
    if len(criticals) == 1:
        others = [r for r in reviews if r not in criticals]
        if any(_is_silent(r) for r in others):
            return "ng"
    return "ok"


def _aggregate(reviews: list[VendorReview]) -> dict[str, list[dict]]:
    """指摘を severity 別に集約（task_logger.write_task_log の review_result 形式）。"""
    by: dict[str, list[dict]] = {"critical": [], "high": [], "med": [], "low": []}
    for r in reviews:
        for it in r.items:
            entry = {
                "issue": it.issue,
                "quote": it.quote,
                "suggestion": it.suggestion,
                "vendor": r.vendor,
            }
            if it.severity in by:
                by[it.severity].append(entry)
            else:
                by["low"].append(entry)
    return by


# --- 本体 ---


def run_multi_llm_review(
    target: str,
    objective: str,
    viewpoints: dict[str, str] | None = None,
    gemini_runner: tuple[Callable, Callable] | None = None,
    minimax_requester: Callable | None = None,
) -> MultiReviewResult:
    """別ベンダー LLM に並列独立レビューさせる（目的ホールド・多様性保証）。

    Args:
        target: レビュー対象（plan.md 本文 / git diff）。
        objective: 当初目的（全プロンプト先頭に再注入）。
        viewpoints: {"gemini": "...", "minimax": "..."}。None ならデフォルト観点。
        gemini_runner: テスト用 mock (run_api_with_fallback, _load_candidates)。
        minimax_requester: テスト用 mock (requests.post 互換)。

    Returns:
        MultiReviewResult。verdict は "ok"/"ng"/"abort"。
        ベンダー数 < 2（片系障害含む）は即 abort（多様性保証不能）。
    """
    viewpoints = viewpoints or {
        "gemini": "エッジケース/セキュリティ/リスク",
        "minimax": "設計/可読性/実現性",
    }
    key_g = _load_secret("GEMINI_API_KEY")
    key_m = _load_secret("MINIMAX_API_KEY")

    prompt_g = _build_prompt(target, objective, viewpoints.get("gemini", ""))
    prompt_m = _build_prompt(target, objective, viewpoints.get("minimax", ""))

    text_g, model_g, status_g, err_g, fb_g = _call_gemini_with_retry(
        prompt_g, key_g, gemini_runner
    )
    text_m, model_m, status_m, err_m = _call_minimax(prompt_m, key_m, minimax_requester)

    rv_g = VendorReview(
        vendor="gemini",
        backend_kind="gemini-sdk-rest",
        items=_parse_items(text_g, objective),
        raw_status=status_g,
        model=model_g,
        fallback_used=fb_g,
        error_detail=err_g,
    )
    rv_m = VendorReview(
        vendor="minimax",
        backend_kind="minimax-anthropic",
        items=_parse_items(text_m, objective),
        raw_status=status_m,
        model=model_m,
        error_detail=err_m,
    )
    reviews = [rv_g, rv_m]

    # ベンダー数判定（<2 は即 abort・片系障害含む）
    ok_vendors = {r.vendor for r in reviews if r.raw_status == "ok"}
    if len(ok_vendors) < 2:
        if not ok_vendors:
            reason = "両系障害・pending-retry 相当"
        else:
            reason = "多様性保証不能: ベンダーが1社のみ（片系障害）"
        return MultiReviewResult(reviews=reviews, verdict="abort", abort_reason=reason)

    verdict = _judge(reviews)
    by_sev = _aggregate(reviews)
    return MultiReviewResult(
        reviews=reviews, verdict=verdict, abort_reason="", by_severity=by_sev
    )


# --- CLI エントリ（run-task.sh から呼出・objective はファイルパス経由） ---


def main(argv: list[str] | None = None) -> int:
    """CLI エントリポイント。

    run-task.sh(bash) から ``python3 review_lib.py --target-file ... --objective-file ...``
    で起動。objective はファイルパス経由（シェルクォート破壊回避）。
    """
    import argparse

    parser = argparse.ArgumentParser(description="multi-LLM review (Phase 2/5)")
    parser.add_argument("--target-file", required=True)
    parser.add_argument("--objective-file", required=True)
    parser.add_argument("--viewpoint-gemini", default="エッジケース/セキュリティ/リスク")
    parser.add_argument("--viewpoint-minimax", default="設計/可読性/実現性")
    parser.add_argument("--out", help="結果JSON出力先パス(省略時stdout)")
    args = parser.parse_args(argv)

    target = Path(args.target_file).read_text(encoding="utf-8")
    objective = Path(args.objective_file).read_text(encoding="utf-8").strip()
    viewpoints = {
        "gemini": args.viewpoint_gemini,
        "minimax": args.viewpoint_minimax,
    }
    result = run_multi_llm_review(target, objective, viewpoints)
    payload = {
        "verdict": result.verdict,
        "abort_reason": result.abort_reason,
        "by_severity": result.by_severity,
        "reviews": [
            {
                "vendor": r.vendor,
                "backend_kind": r.backend_kind,
                "raw_status": r.raw_status,
                "model": r.model,
                "fallback_used": r.fallback_used,
                "error_detail": r.error_detail,
                "item_count": len(r.items),
            }
            for r in result.reviews
        ],
    }
    out_text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(out_text, encoding="utf-8")
    else:
        sys.stdout.write(out_text + "\n")
    # verdict: ok=0 / ng=1 / abort=2
    return 0 if result.verdict == "ok" else (1 if result.verdict == "ng" else 2)


if __name__ == "__main__":
    sys.exit(main())