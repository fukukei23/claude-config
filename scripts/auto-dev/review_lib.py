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

3社化（2026-08-18・マルチLLMレビュー改訂案採用8件反映）:
- OpenRouter（free枠）を3社目に追加 — 片系障害を吸収し「3社中2社残れば成立」
- _judge ポリシー(b) を「他の全社が沈黙時のみ ng」へ変更（エラー社は無情報）
- OPENROUTER_MODELS 環境変数でモデル候補を上書き可（free枠退役対策）
- 責務分離: abort=生存条件（最低2社の多様性保証）/ _judge=生存社の中での品質判定
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
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

    vendor: str  # "gemini" / "minimax" / "openrouter"
    backend_kind: str  # "gemini-sdk-rest" / "minimax-anthropic" / "openrouter-chat"
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
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# 選定根拠: multi-llm-review スキルの purpose=code 実績選定（1番目）+
# デザイン系 free 枠（2番目・フォールバック）。free 枠は退役が頻繁なため
# 環境変数 OPENROUTER_MODELS（カンマ区切り）で上書き可能（退役対策）。
OPENROUTER_MODELS = ["cohere/north-mini-code:free", "openai/gpt-oss-20b:free"]
_SENSITIVE_HEADER_NAMES = {"x-api-key", "authorization", "api-key"}
_SECRET_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9]{6})[A-Za-z0-9]*"),
    re.compile(r"(Bearer\s+[A-Za-z0-9]{6})[A-Za-z0-9]*"),
    re.compile(r"(eyJ[A-Za-z0-9]{6})[A-Za-z0-9._-]*"),
]
NO_ISSUE_MARKERS = (
    "no issues",
    "no issues found",
    "no significant issues",  # OpenRouter 系英文テンプレ（3社化・2026-08-18）
    "looks good",  # 同上
    "lgtm",  # 同上
    "見つからなかった",
    "問題ありません",
    "問題なし",
)


# --- APIキー/シークレット ---


def _secrets_env_candidates() -> list[Path]:
    """`.secrets.env` の探索候補（先頭から順に試す）。

    `Path.home()` だけに頼らない理由（2026-08-22 実測）:
        Windows Desktop 版 Claude Code から WSL 上のリポジトリを操作する構成では
        `Path.home()` が `C:\\Users\\<user>` を返し、WSL 側の `~/.secrets.env` に
        到達できない（実測: `.secrets.env 存在 = False` → 3キーとも空 →
        Gemini/MiniMax/OpenRouter が揃って error-auth になり review が abort する）。
        そこで本ファイル自身の位置からも解決する。これは同リポジトリの
        post-commit hook が「$HOME 参照廃止・フック自身のディレクトリで解決」
        （S1修正）としているのと同じ方針。

    Returns:
        重複を除いた候補パスのリスト。
    """
    cands = [Path.home() / ".secrets.env"]
    # <home>/projects/claude-config/scripts/auto-dev/review_lib.py → parents[4] == <home>
    try:
        cands.append(Path(__file__).resolve().parents[4] / ".secrets.env")
    except IndexError:  # 想定外の階層に置かれた場合は候補を増やさないだけ
        pass
    uniq: list[Path] = []
    for c in cands:
        if c not in uniq:
            uniq.append(c)
    return uniq


def _load_secret(name: str) -> str:
    """環境変数 → `.secrets.env`（複数候補）の順で APIキー値を取得。

    Returns:
        キー値文字列（未設定時は空文字）。
    """
    val = os.environ.get(name, "")
    if val:
        return val
    for secrets in _secrets_env_candidates():
        if not secrets.exists():
            continue
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


# --- OpenRouter 呼出（OpenAI互換・free枠・防御的パース） ---


def _openrouter_models() -> list[str]:
    """モデル候補リスト。環境変数 OPENROUTER_MODELS（カンマ区切り）で上書可。

    free 枠は退役が頻発するため、ハードコードを正とせず運用側で
    差し替えられる経路を用意する（マルチLLMレビュー改訂案・採用B）。
    """
    env = os.environ.get("OPENROUTER_MODELS", "")
    if env:
        return [m.strip() for m in env.split(",") if m.strip()]
    return OPENROUTER_MODELS


def _call_openrouter(
    prompt: str,
    api_key: str,
    requester: Callable | None = None,
    timeout: int = 90,
) -> tuple[str, str, str, str]:
    """OpenRouter（OpenAI互換 chat/completions）へ直接 requests。

    戻り値: (text, model, raw_status, error_detail)。
    requester に requests.post 互換 callable を mock 注入可（テスト用）。
    候補リスト（OPENROUTER_MODELS）を順に試行（フォールバック）。

    防御的パース（採用A・M1+G1）: 200 でも choices 空・content None 等
    構造欠損はクラッシュせず次モデルへフォールバック。
    401 は即 error-auth（リトライで予算を食い潰さない・採用M16）。
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    post = requester or _import_requests_post()
    last_err = ""
    for model in _openrouter_models():
        payload = {
            "model": model,
            "max_tokens": 2000,
            # free 枠モデルは思考を content と別の reasoning フィールドへ出力し、
            # 思考が max_tokens を食い尽くして content: null / finish_reason: length で
            # 終わる（2026-08-21 実測: cohere/north-mini-code:free・openai/gpt-oss-20b:free
            # の両方で再現。以前の「思考モデルでないので 8000 不要」は誤った前提だった）。
            # reasoning を無効化すると content が返る（同日実測で確認）。
            # 詳細: 30_RESEARCH/LLMモデル/2026-08-21_思考出力の落とし穴-reasoning-thinkによる本文欠落.md
            "reasoning": {"enabled": False},
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            resp = post(OPENROUTER_URL, headers=headers, json=payload, timeout=timeout)
            status = getattr(resp, "status_code", None)
            if status == 200:
                data = resp.json() if callable(getattr(resp, "json", None)) else {}
                choices = data.get("choices") or [{}]
                content = (choices[0].get("message") or {}).get("content") or ""
                if content.strip():
                    return content, model, "ok", ""
                last_err = f"{model}:空応答(構造欠損含む)"
                continue
            if status == 401 or status == 403:
                return "", model, "error-auth", f"{status}"
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
    """判定 3 値ポリシー（silent agree 握り潰し防止・3社化で(b)を修正）。

    (a) critical が2社以上 → ng
    (b) critical が1社 + **他の全社が沈黙** → ng
        （3社化・ポリシーB・2026-08-18: エラー社は「反証の欠如」でなく
          無情報。1社でも active（指摘あり）なら反証ありとして ok。
          2社構成では others=1社のため any==all で旧挙動と同値）
    (c) それ以外 → ok
    """
    criticals = [r for r in reviews if _has_critical(r)]
    if len(criticals) >= 2:
        return "ng"
    if len(criticals) == 1:
        others = [r for r in reviews if r not in criticals]
        if others and all(_is_silent(r) for r in others):
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


# --- 失敗ログ JSONL 記録（対応案(a)・2026-08-22） ---
# PostToolUse hook（log-mlr-calls.sh）は tool_input.command にドメイン文字列が
# 現れることを判定条件にしているため、python の requests で直接叩く本モジュール
# 経由の呼出は**原理的に捕捉できない**。しかも二重起票を招いた当の失敗
# （2026-08-18・2026-08-21 の OpenRouter 障害）はどちらもこの経路だった。
# よって呼出元（ここ）が自分で1行書き、hook の守備範囲外をカバーする。
# spec: obsidian-ssot/docs/superpowers/specs/2026-08-21-multi-llm-review-failure-log-design.md

# raw_status（ok/empty/error-auth/error-429/error-5xx/error-exhausted/error-<code>）
# → spec §5 の reason enum
_MLR_REASON_MAP = {
    "empty": ("empty_body_keepalive_only", None),
    "error-auth": ("auth_401", 401),
    "error-429": ("rate_limited_429", 429),
    "error-402": ("payment_required_402", 402),
    "error-403": ("auth_401", 403),
    "error-5xx": ("other", None),
    "error-exhausted": ("other", None),
}


_AUTH_ERROR_HINTS = (
    "api key",
    "api_key",
    "apikey",
    "unauthenticated",
    "unauthorized",
    "permission_denied",
    "credential",
    "未設定",
)


def _looks_like_auth_error(detail: str) -> bool:
    """error_detail が認証系の失敗を示すか（大文字小文字を無視）。

    Args:
        detail: VendorReview.error_detail。

    Returns:
        認証系と判断できれば True。
    """
    low = (detail or "").lower()
    return any(h in low for h in _AUTH_ERROR_HINTS)


def build_mlr_log_records(
    result: "MultiReviewResult", round_id: str, topic: str
) -> list[dict]:
    """MultiReviewResult を失敗ログ JSONL のレコード列に変換する（純粋関数）。

    hook が書くのと同一スキーマ（13キー）。auto-loop は自動実行でホスト補記
    （mlr-log.sh annotate）が来ないため、``status`` は最初から ``annotated``。

    Args:
        result: run_multi_llm_review の戻り値。
        round_id: レビュー1回の識別子。auto-loop 由来は ``al-`` prefix。
        topic: 題材（集計キーではなく検索のヒント）。

    Returns:
        レコード（dict）のリスト。ベンダー1社につき1件。
    """
    ts = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
    records: list[dict] = []
    for r in result.reviews:
        if r.raw_status == "ok":
            res, reason, http = "ok", None, None
            findings = len(r.items)
        else:
            res = "fail"
            findings = 0
            reason, http = _MLR_REASON_MAP.get(r.raw_status, ("other", None))
            if http is None and r.raw_status.startswith("error-"):
                # error-<HTTPコード> 形式（_MLR_REASON_MAP に無いコード）
                tail = r.raw_status[len("error-"):]
                if tail.isdigit():
                    http = int(tail)
            if reason == "other" and _looks_like_auth_error(r.error_detail):
                # Gemini は鍵未設定でも SDK 例外が error-5xx に丸められる
                # （error_detail は "No API key was provided..."）。
                # other に埋没させると起票前チェック（reason×model の2軸）で
                # auth_401 として引けず二重起票を防げないため寄せる。
                reason, http = "auth_401", http or 401
        records.append(
            {
                "ts": ts,
                "round_id": round_id,
                "topic": topic,
                "llm": r.vendor,
                "model": r.model or None,
                # 本命モデルで通れば1・フォールバック先で通った/落ちたなら2
                "attempt": 2 if r.fallback_used else 1,
                "result": res,
                "reason": reason,
                "http": http,
                # HTTP層の finish_reason はここまで伝播しないため常に None
                "finish_reason": None,
                "findings": findings,
                "status": "annotated",
                "backlogged": False,
            }
        )
    return records


def _mlr_log_path() -> Path | None:
    """失敗ログ JSONL のパス。``$HOME`` に依存しない（Windows 側は別ホーム）。

    Returns:
        書込可能なパス。決められない場合 None。
    """
    env = os.environ.get("MLR_LOG_FILE")
    if env:
        return Path(env)
    state = os.environ.get("MLR_STATE_DIR")
    if state:
        return Path(state) / "multi-llm-review.jsonl"
    if os.environ.get("PYTEST_CURRENT_TEST"):
        # ★テスト実行中は本番ログへ書かない（明示指定が無い限り）。
        # conftest の fixture だけに頼ると、別ディレクトリからの実行や
        # 新規テストファイルで漏れる。2026-08-22 実測: 既存テストが
        # run_multi_llm_review を14回呼ぶため 1回の pytest で42行が
        # 本番 JSONL に混入し、指標A/Bの分母を壊していた。
        return None
    for base in (Path.home() / ".claude" / "state",
                 Path("/home/yn4416/.claude/state")):
        if base.is_dir():
            return base / "multi-llm-review.jsonl"
    return None


def append_mlr_log(records: list[dict], path: Path | None = None) -> bool:
    """レコードを JSONL へ追記する。**例外を投げない**。

    ログ書込の失敗でレビュー本体（auto-loop）を止めないため、
    あらゆる失敗を False で返す（無言ではなく戻り値で表す）。

    Args:
        records: build_mlr_log_records の戻り値。
        path: 書込先。None なら _mlr_log_path()。

    Returns:
        1行以上書けたら True。
    """
    if not records:
        return False
    target = path or _mlr_log_path()
    if target is None:
        return False
    try:
        with open(target, "a", encoding="utf-8", newline="\n") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def run_multi_llm_review(
    target: str,
    objective: str,
    viewpoints: dict[str, str] | None = None,
    gemini_runner: tuple[Callable, Callable] | None = None,
    minimax_requester: Callable | None = None,
    openrouter_requester: Callable | None = None,
    round_id: str | None = None,
    topic: str = "",
) -> MultiReviewResult:
    """別ベンダー LLM（Gemini + MiniMax + OpenRouter）に独立レビューさせる。

    責務分離（3社化・2026-08-18）:
    - abort 判定 = 生存条件（ok 応答ベンダー >= 2 の多様性保証）
    - _judge 判定 = 生存社の中での品質判定（critical の反証構造）

    Args:
        target: レビュー対象（plan.md 本文 / git diff）。
        objective: 当初目的（全プロンプト先頭に再注入）。
        viewpoints: {"gemini": "...", "minimax": "...", "openrouter": "..."}。
            None ならデフォルト観点。
        gemini_runner: テスト用 mock (run_api_with_fallback, _load_candidates)。
        minimax_requester: テスト用 mock (requests.post 互換)。
        openrouter_requester: テスト用 mock (requests.post 互換)。

    Returns:
        MultiReviewResult。verdict は "ok"/"ng"/"abort"。
        ベンダー数 < 2 は即 abort（多様性保証不能・意図的保守選択として
        閾値 <2 は 3社化後も変更しない）。
        OPENROUTER_API_KEY 未設定時は rv_o=error-auth で 2社縮退継続
        （graceful・採用C）。
    """
    viewpoints = viewpoints or {
        "gemini": "エッジケース/セキュリティ/リスク",
        "minimax": "設計/可読性/実現性",
        "openrouter": "実装の妥当性/網羅性",
    }
    key_g = _load_secret("GEMINI_API_KEY")
    key_m = _load_secret("MINIMAX_API_KEY")
    key_o = _load_secret("OPENROUTER_API_KEY")

    prompt_g = _build_prompt(target, objective, viewpoints.get("gemini", ""))
    prompt_m = _build_prompt(target, objective, viewpoints.get("minimax", ""))
    prompt_o = _build_prompt(target, objective, viewpoints.get("openrouter", ""))

    text_g, model_g, status_g, err_g, fb_g = _call_gemini_with_retry(
        prompt_g, key_g, gemini_runner
    )
    text_m, model_m, status_m, err_m = _call_minimax(prompt_m, key_m, minimax_requester)
    if key_o:
        text_o, model_o, status_o, err_o = _call_openrouter(
            prompt_o, key_o, openrouter_requester
        )
    else:
        # キー未設定 → HTTP呼出なしで error-auth（2社縮退で継続・採用C）
        text_o, model_o, status_o, err_o = "", "", "error-auth", "OPENROUTER_API_KEY 未設定"

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
    rv_o = VendorReview(
        vendor="openrouter",
        backend_kind="openrouter-chat",
        items=_parse_items(text_o, objective),
        raw_status=status_o,
        model=model_o,
        error_detail=err_o,
    )
    reviews = [rv_g, rv_m, rv_o]

    # 失敗ログの round_id（auto-loop 由来を示す al- prefix・hook経由と区別）
    rid = round_id or ("al-" + datetime.now().strftime("%Y%m%d-%H%M%S"))

    # ベンダー数判定（<2 は即 abort・2社以上生き残れば成立）
    ok_vendors = {r.vendor for r in reviews if r.raw_status == "ok"}
    if len(ok_vendors) < 2:
        if not ok_vendors:
            reason = "両系障害・pending-retry 相当"
        else:
            reason = "多様性保証不能: ベンダーが1社のみ（片系障害）"
        aborted = MultiReviewResult(
            reviews=reviews, verdict="abort", abort_reason=reason
        )
        # ★ abort こそ最も記録したいケース。早期 return で取り逃さない
        append_mlr_log(build_mlr_log_records(aborted, rid, topic))
        return aborted

    verdict = _judge(reviews)
    by_sev = _aggregate(reviews)
    result = MultiReviewResult(
        reviews=reviews, verdict=verdict, abort_reason="", by_severity=by_sev
    )
    append_mlr_log(build_mlr_log_records(result, rid, topic))
    return result


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
    parser.add_argument("--viewpoint-openrouter", default="実装の妥当性/網羅性")
    parser.add_argument("--out", help="結果JSON出力先パス(省略時stdout)")
    parser.add_argument(
        "--round-id",
        help="失敗ログの round_id（省略時 al-YYYYMMDD-HHMMSS を自動生成）",
    )
    parser.add_argument(
        "--topic", default="", help="失敗ログの topic（検索のヒント・集計キーではない）"
    )
    args = parser.parse_args(argv)

    target = Path(args.target_file).read_text(encoding="utf-8")
    objective = Path(args.objective_file).read_text(encoding="utf-8").strip()
    viewpoints = {
        "gemini": args.viewpoint_gemini,
        "minimax": args.viewpoint_minimax,
        "openrouter": args.viewpoint_openrouter,
    }
    result = run_multi_llm_review(
        target, objective, viewpoints,
        round_id=args.round_id, topic=args.topic,
    )
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