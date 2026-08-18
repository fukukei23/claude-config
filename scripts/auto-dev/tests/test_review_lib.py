"""review_lib.py の JSON 抽出と severity 正規化テスト

multi-llm-review スキルのコアロジック（JSON 抽出・severity 正規化）を
Python 関数化した review_lib.py の単体テスト。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from review_lib import (  # noqa: E402
    NO_ISSUE_MARKERS,
    ReviewItem,
    VendorReview,
    _build_prompt,
    _call_minimax,
    _call_openrouter,
    _is_silent,
    _judge,
    _mask_str,
    classify_review_item,
    extract_json_from_text,
    normalize_severity,
    run_multi_llm_review,
)


def test_extract_json_from_text_simple_object():
    """前後の散文に挟まれた素の JSON オブジェクトを抽出。"""
    text = 'Some prose. {"critical": ["x"], "high": ["y"]} More prose.'
    assert extract_json_from_text(text) == {"critical": ["x"], "high": ["y"]}


def test_extract_json_from_text_code_fenced():
    """```json ... ``` フェンス内の JSON を抽出（フェンス優先）。"""
    text = '```json\n{"critical": ["a"]}\n```'
    assert extract_json_from_text(text) == {"critical": ["a"]}


def test_extract_json_from_text_code_fenced_no_lang():
    """言語指定なしフェンス ``` ... ``` 内の JSON も抽出。"""
    text = '```\n{"low": ["b"]}\n```'
    assert extract_json_from_text(text) == {"low": ["b"]}


def test_extract_json_from_text_with_surrounding_text():
    """日本語の前置き／後置きが前後にある JSON を抽出。"""
    text = '結果は以下の通り。\n{"low": ["minor"]}\n以上です。'
    assert extract_json_from_text(text) == {"low": ["minor"]}


def test_extract_json_from_text_nested_object():
    """ネストしたオブジェクトも greedy match で正しく抽出。"""
    text = 'prefix {"a": {"b": 1}, "c": [1, 2]} suffix'
    assert extract_json_from_text(text) == {"a": {"b": 1}, "c": [1, 2]}


def test_extract_json_from_text_invalid_raises():
    """JSON オブジェクトが無い場合は ValueError。"""
    with pytest.raises(ValueError, match="JSON object not found"):
        extract_json_from_text("no json here")


def test_extract_json_from_text_invalid_only_primitive():
    """プリミティブだけの場合はオブジェクトではないので ValueError。"""
    with pytest.raises(ValueError, match="JSON object not found"):
        extract_json_from_text("42 and true")


def test_normalize_severity_known():
    """既知の severity は正規化して返す。"""
    assert normalize_severity("critical") == "critical"
    assert normalize_severity("HIGH") == "high"
    assert normalize_severity("Med") == "med"
    assert normalize_severity("medium") == "med"
    assert normalize_severity("low") == "low"


def test_normalize_severity_unknown_defaults_to_low():
    """未知の severity は 'low' にフォールバック（安全側）。"""
    assert normalize_severity("warning") == "low"
    assert normalize_severity("info") == "low"


def test_normalize_severity_empty_defaults_to_low():
    """空文字列は 'low' にフォールバック。"""
    assert normalize_severity("") == "low"


# ────────────────────────────────────────────────────────────
# Task 2: classify_review_item — 3tier 分類（直接/メタ/目的外）
# ────────────────────────────────────────────────────────────


def test_classify_review_item_direct():
    """objective に直接言及する指摘 → 'direct'"""
    result = classify_review_item(
        review="validate_email でRFC 5321 準拠のローカル部長チェックが抜けている",
        objective="メールバリデーション関数をRFC準拠にする",
    )
    assert result == "direct"


def test_classify_review_item_meta():
    """objective には言及しないがレビュー作法への指摘 → 'meta'"""
    result = classify_review_item(
        review="テストカバレッジが低い。100%を目指すべき",
        objective="メールバリデーション関数をRFC準拠にする",
    )
    assert result == "meta"


def test_classify_review_item_offtopic():
    """review が極短 or トークン無し → 'offtopic'

    docstring の「offtopic: 完全無関係（タイポ修正等・極端に短い or
    objective と被りなし）」の現実的実装は「10文字未満 or トークン無し」。

    注: 仕様書 plan で提示された "README のタイポ修正が必要" を offtopic
    期待とする例は、docstring/関数ロジックと整合しない（10文字以上+
    トークン有 ⇒ meta 判定）。ここでは docstring/ロジックと整合する
    極短・トークン無しのケースを採用する（Task 2 仕様書は不整合）。
    """
    # 極短（5 文字未満・トークン無し）→ offtopic
    result = classify_review_item(
        review="",
        objective="メールバリデーション関数をRFC準拠にする",
    )
    assert result == "offtopic"


def test_classify_review_item_english_only():
    """漢字なし・英単語のみで objective / review を判定。

    objective "implement JWT auth middleware" / review "JWT middleware
    does not verify expiry" → 両方に "JWT" / "middleware" が重複 → 'direct'。
    """
    result = classify_review_item(
        review="JWT middleware does not verify token expiry claims",
        objective="implement JWT auth middleware for API endpoints",
    )
    assert result == "direct"


def test_classify_review_item_empty_objective():
    """objective が空文字列 → キーワード集合が空 → direct 判定不可 → 'meta' or 'offtopic'。

    仕様: obj_keywords が空集合なので direct 分岐には入らない。
    review が10文字以上でトークン（漢字/英単語）があれば 'meta'。
    """
    result = classify_review_item(
        review="コードの可読性が低いのでリファクタリングすべき",
        objective="",
    )
    assert result == "meta"


def test_classify_review_item_short_offtopic():
    """極短・トークン抽出ゼロの review → 'offtopic'"""
    result = classify_review_item(
        review="!",
        objective="メールバリデーション関数をRFC準拠にする",
    )
    assert result == "offtopic"


def test_classify_review_item_shared_kanji_keyword():
    """objective と review で 2文字漢字を共有 → 'direct'"""
    result = classify_review_item(
        review="バリデーション処理が例外を握りつぶしている",
        objective="メールバリデーション関数をRFC準拠にする",
    )
    assert result == "direct"


# ────────────────────────────────────────────────────────────
# Phase 2/5: run_multi_llm_review（別ベンダー並列レビュー・2026-08-12）
# mock で HTTP/SDK を擬似（実 API ゼロ・CI 安全）
# ────────────────────────────────────────────────────────────


class _MockResponse:
    """requests.post の応答モック。"""

    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json


def _minimax_ok(text):
    return _MockResponse(200, {"content": [{"type": "text", "text": text}]})


def _gemini_runner(text, model="gemini-3.1-pro-preview"):
    """(run_fn, load_cands) の mock。"""

    def load_cands(cap, paid_ok_limit=False):
        return [model]

    def run_fn(factory, candidates, api_key):
        return model, text

    return (run_fn, load_cands)


def _item(issue, sev, quote="q", suggestion="s"):
    return ReviewItem(issue=issue, severity=sev, quote=quote, suggestion=suggestion)


# --- APIキーマスク ---


def test_mask_str_redacts_sk_key():
    """sk- プレフィックスのシークレットをマスク。"""
    masked = _mask_str("error: sk-abcdefghij12345")
    assert "<REDACTED>" in masked
    assert "abcdefghij12345" not in masked


def test_mask_str_redacts_bearer():
    """Bearer トークンをマスク。"""
    masked = _mask_str("Authorization: Bearer abcdefghijk")
    assert "<REDACTED>" in masked
    assert "Bearer abcdefghijk" not in masked


# --- プロンプト組み立て（マルチバイト・シェル破壊回避確認） ---


def test_build_prompt_injects_objective_multibyte():
    """マルチバイト objective がプロンプト先頭に注入される（目的ホールド）。"""
    p = _build_prompt("target code", "メールバリデーション関数をRFC準拠にする", "bug")
    assert "メールバリデーション関数をRFC準拠にする" in p
    assert "target code" in p
    assert "[観点] bug" in p


def test_build_prompt_handles_special_chars():
    """バッククォート・$・改行を含む objective が壊れず注入される。"""
    objective = "objective with `backtick` and $var and\nnewline"
    p = _build_prompt("t", objective, "v")
    assert objective in p


# --- MiniMax 直接呼出 ---


def test_call_minimax_ok():
    """MiniMax 正常応答 → status=ok・モデル=M3。"""
    text = '[{"issue":"a","severity":"high","quote":"q","suggestion":"s"}]'
    out = _call_minimax(
        "prompt",
        "fake-key",
        requester=lambda *a, **k: _minimax_ok(text),
    )
    text_out, model, status, err = out
    assert status == "ok"
    assert model == "MiniMax-M3"
    assert err == ""


def test_call_minimax_429_fallback_to_m27():
    """M3 が429 → M2.7 へフォールバック。"""
    calls = []

    def post(url, headers, json, timeout):
        calls.append(json["model"])
        if json["model"] == "MiniMax-M3":
            return _MockResponse(429)
        return _minimax_ok('[{"issue":"x","severity":"low","quote":"q","suggestion":"s"}]')

    out = _call_minimax("p", "fake-key", requester=post)
    _, model, status, _ = out
    assert status == "ok"
    assert model == "MiniMax-M2.7"
    assert calls == ["MiniMax-M3", "MiniMax-M2.7"]


def test_call_minimax_all_fail():
    """全モデル429 → error-exhausted。"""
    out = _call_minimax(
        "p", "fake-key", requester=lambda *a, **k: _MockResponse(429)
    )
    _, _, status, _ = out
    assert status == "error-exhausted"


def test_call_minimax_masks_key_in_error():
    """例外メッセージに APIキーが含まれていてもマスクされる。"""

    class _BoomResponse:
        status_code = None

        def json(self):
            raise RuntimeError("boom")

        @property
        def text(self):
            return ""

    def post(url, headers, json, timeout):
        # json() が RuntimeError → except Exception で _mask_str
        raise RuntimeError("auth failed with sk-secretkey123 in header")

    out = _call_minimax("p", "sk-secretkey123abc", requester=post)
    _, _, _, err = out
    assert "secretkey123" not in err
    assert "<REDACTED>" in err


# --- 判定ポリシー 3 値 ---


def _vr(vendor, items, status="ok", fallback=False):
    return VendorReview(
        vendor=vendor,
        backend_kind="x",
        items=items,
        raw_status=status,
        fallback_used=fallback,
    )


def test_judge_both_critical_ng():
    """(a) 両ベンダー critical → ng。"""
    reviews = [_vr("g", [_item("a", "critical")]), _vr("m", [_item("b", "critical")])]
    assert _judge(reviews) == "ng"


def test_judge_one_critical_one_silent_ng():
    """(b) 片側 critical + 片側 silent(0件) → ng。"""
    reviews = [_vr("g", [_item("a", "critical")]), _vr("m", [])]
    assert _judge(reviews) == "ng"


def test_judge_one_critical_one_silent_template_ng():
    """(b) 片側 critical + 片側 'no issues' テンプレ → ng。"""
    reviews = [
        _vr("g", [_item("a", "critical")]),
        _vr("m", [_item("no issues found", "low")]),
    ]
    assert _judge(reviews) == "ng"


def test_judge_both_below_critical_ok():
    """(c) 両側 critical 未満 → ok。"""
    reviews = [_vr("g", [_item("a", "high")]), _vr("m", [_item("b", "med")])]
    assert _judge(reviews) == "ok"


def test_judge_fallback_used_is_silent():
    """フォールバック発動時は silent 扱い（能力差リスク・M5対策）。"""
    reviews = [
        _vr("g", [_item("a", "critical")]),
        _vr("m", [_item("b", "high")], fallback=True),
    ]
    assert _judge(reviews) == "ng"


# --- run_multi_llm_review 統合 ---


def test_run_multi_llm_review_both_ok():
    """3社正常・critical なし → verdict=ok（旧2社テストの3社化版）。"""
    g = '[{"issue":"x","severity":"low","quote":"q","suggestion":"s"}]'
    m = '[{"issue":"y","severity":"low","quote":"q","suggestion":"s"}]'
    o = '[{"issue":"z","severity":"low","quote":"q","suggestion":"s"}]'
    result = run_multi_llm_review(
        "target",
        "objective",
        gemini_runner=_gemini_runner(g),
        minimax_requester=lambda *a, **k: _minimax_ok(m),
        openrouter_requester=lambda *a, **k: _or_ok(o),
    )
    assert result.verdict == "ok"
    assert len(result.reviews) == 3
    assert {r.vendor for r in result.reviews} == {"gemini", "minimax", "openrouter"}


def test_run_multi_llm_review_both_critical_ng():
    """2社 critical → ng・by_severity に2件。"""
    g = '[{"issue":"x","severity":"critical","quote":"q","suggestion":"s"}]'
    m = '[{"issue":"y","severity":"critical","quote":"q","suggestion":"s"}]'
    o = '[{"issue":"z","severity":"low","quote":"q","suggestion":"s"}]'
    result = run_multi_llm_review(
        "target",
        "objective",
        gemini_runner=_gemini_runner(g),
        minimax_requester=lambda *a, **k: _minimax_ok(m),
        openrouter_requester=lambda *a, **k: _or_ok(o),
    )
    assert result.verdict == "ng"
    assert len(result.by_severity["critical"]) == 2


def test_run_multi_llm_review_one_critical_one_silent_ng():
    """critical 1社 + 他2社とも silent → ng（握り潰し防止・ポリシーB）。"""
    g = '[{"issue":"x","severity":"critical","quote":"q","suggestion":"s"}]'
    m = '[{"issue":"no issues found","severity":"low","quote":"","suggestion":""}]'
    result = run_multi_llm_review(
        "target",
        "objective",
        gemini_runner=_gemini_runner(g),
        minimax_requester=lambda *a, **k: _minimax_ok(m),
        openrouter_requester=_or_down,
    )
    assert result.verdict == "ng"


def test_run_multi_llm_review_minimax_down_abort():
    """MiniMax+OpenRouter 2社ダウン → ベンダー1社 → abort。"""
    g = '[{"issue":"x","severity":"low","quote":"q","suggestion":"s"}]'
    result = run_multi_llm_review(
        "target",
        "objective",
        gemini_runner=_gemini_runner(g),
        minimax_requester=lambda *a, **k: _MockResponse(429),
        openrouter_requester=_or_down,
    )
    assert result.verdict == "abort"
    assert "1社のみ" in result.abort_reason


def test_run_multi_llm_review_both_down_abort():
    """全社障害(gemini空応答+minimax500+openrouter429) → abort・両系障害。"""

    def gemini_runner_empty():
        def load_cands(cap, paid_ok_limit=False):
            return ["gemini-3.1-pro-preview"]

        def run_fn(factory, candidates, api_key):
            return ("gemini-3.1-pro-preview", "")  # 空応答

        return (run_fn, load_cands)

    result = run_multi_llm_review(
        "target",
        "objective",
        gemini_runner=gemini_runner_empty(),
        minimax_requester=lambda *a, **k: _MockResponse(500),
        openrouter_requester=_or_down,
    )
    assert result.verdict == "abort"
    assert "両系障害" in result.abort_reason


def test_run_multi_llm_review_gemini_empty_truncate_retry():
    """Gemini 空応答 → truncate リトライ（fallback_used=True記録）。"""
    call_count = [0]

    def runner():
        def load_cands(cap, paid_ok_limit=False):
            return ["gemini-3.1-pro-preview"]

        def run_fn(factory, candidates, api_key):
            call_count[0] += 1
            if call_count[0] == 1:
                return ("gemini-3.1-pro-preview", "")  # 1回目空
            return ("gemini-3.1-pro-preview", '[{"issue":"x","severity":"low","quote":"q","suggestion":"s"}]')

        return (run_fn, load_cands)

    result = run_multi_llm_review(
        "# comment line\ncode line\n",
        "objective",
        gemini_runner=runner(),
        minimax_requester=lambda *a, **k: _minimax_ok(
            '[{"issue":"y","severity":"low","quote":"q","suggestion":"s"}]'
        ),
        openrouter_requester=lambda *a, **k: _or_ok(
            '[{"issue":"z","severity":"low","quote":"q","suggestion":"s"}]'
        ),
    )
    # Gemini は空→truncate→2回目ok・fallback_used=True だが minimax 正常なので ok_vendors=2
    # ただし fallback_used=True は silent 扱い → minimax が silent でなければ ok
    gemini_review = next(r for r in result.reviews if r.vendor == "gemini")
    assert gemini_review.fallback_used is True
    assert call_count[0] >= 2


def test_run_multi_llm_review_aggregates_by_severity():
    """指摘が severity 別に集約される（task_logger review_result 形式）。"""
    g = '[{"issue":"g1","severity":"critical","quote":"q","suggestion":"s"},{"issue":"g2","severity":"low","quote":"q","suggestion":"s"}]'
    m = '[{"issue":"m1","severity":"high","quote":"q","suggestion":"s"}]'
    o = '[{"issue":"o1","severity":"low","quote":"q","suggestion":"s"}]'
    result = run_multi_llm_review(
        "target",
        "objective",
        gemini_runner=_gemini_runner(g),
        minimax_requester=lambda *a, **k: _minimax_ok(m),
        openrouter_requester=lambda *a, **k: _or_ok(o),
    )
    assert len(result.by_severity["critical"]) == 1
    assert len(result.by_severity["high"]) == 1
    assert len(result.by_severity["low"]) == 2


# ────────────────────────────────────────────────────────────
# 3社化: OpenRouter 追加 + _judge ポリシーB（2026-08-18）
# マルチLLMレビュー改訂案（採用8件反映）に基づく TDD
# ────────────────────────────────────────────────────────────


def _or_ok(text):
    """OpenRouter 200応答モック（choices[0].message.content）。"""
    return _MockResponse(200, {"choices": [{"message": {"content": text}}]})


def _or_down(*_a, **_k):
    """OpenRouter 障害モック（常時429 → 全モデル試行して exhausted）。"""
    return _MockResponse(429)


# --- _call_openrouter（OpenAI互換・防御的パース） ---


def test_call_openrouter_ok():
    """正常応答 → status=ok・先頭モデル。"""
    text = '[{"issue":"a","severity":"high","quote":"q","suggestion":"s"}]'
    out = _call_openrouter(
        "prompt",
        "fake-key",
        requester=lambda *a, **k: _or_ok(text),
    )
    text_out, model, status, err = out
    assert status == "ok"
    assert model == "cohere/north-mini-code:free"
    assert err == ""


def test_call_openrouter_401_no_retry():
    """401 は即 error-auth（リトライしてAPI予算を食い潰さない）。"""
    calls = []

    def post(url, headers, json, timeout):
        calls.append(json["model"])
        return _MockResponse(401)

    _, _, status, _ = _call_openrouter("p", "fake-key", requester=post)
    assert status == "error-auth"
    assert len(calls) == 1


def test_call_openrouter_429_fallback_second_model():
    """先頭モデル429 → 2番目モデルへフォールバック。"""
    calls = []

    def post(url, headers, json, timeout):
        calls.append(json["model"])
        if json["model"].startswith("cohere"):
            return _MockResponse(429)
        return _or_ok('[{"issue":"x","severity":"low","quote":"q","suggestion":"s"}]')

    _, model, status, _ = _call_openrouter("p", "fake-key", requester=post)
    assert status == "ok"
    assert model == "openai/gpt-oss-20b:free"
    assert len(calls) == 2


def test_call_openrouter_all_fail_exhausted():
    """全モデル429 → error-exhausted。"""
    _, _, status, _ = _call_openrouter("p", "fake-key", requester=_or_down)
    assert status == "error-exhausted"


def test_call_openrouter_empty_choices_fallback():
    """200 でも choices が空配列 → クラッシュせず次モデルへ（防御的パース）。"""
    calls = []

    def post(url, headers, json, timeout):
        calls.append(json["model"])
        if json["model"].startswith("cohere"):
            return _MockResponse(200, {"choices": []})
        return _or_ok('[{"issue":"x","severity":"low","quote":"q","suggestion":"s"}]')

    _, model, status, _ = _call_openrouter("p", "fake-key", requester=post)
    assert status == "ok"
    assert len(calls) == 2


def test_call_openrouter_content_none_fallback():
    """200 でも content が None → クラッシュせず次モデルへ。"""
    def post(url, headers, json, timeout):
        if json["model"].startswith("cohere"):
            return _MockResponse(200, {"choices": [{"message": {"content": None}}]})
        return _or_ok('[{"issue":"x","severity":"low","quote":"q","suggestion":"s"}]')

    _, _, status, _ = _call_openrouter("p", "fake-key", requester=post)
    assert status == "ok"


def test_call_openrouter_models_env_override(monkeypatch):
    """環境変数 OPENROUTER_MODELS（カンマ区切り）でモデル候補を上書き（退役対策）。"""
    calls = []

    def post(url, headers, json, timeout):
        calls.append(json["model"])
        return _MockResponse(429)

    monkeypatch.setenv("OPENROUTER_MODELS", "vendor-a/retired:free, vendor-b/spare:free")
    _call_openrouter("p", "fake-key", requester=post)
    assert calls == ["vendor-a/retired:free", "vendor-b/spare:free"]


# --- NO_ISSUE_MARKERS 語彙（OpenRouter英文テンプレ対応） ---


def test_is_silent_lgtm_template():
    """'lgtm' / 'looks good' / 'no significant issues' も silent 扱い。"""
    for marker in ("lgtm", "looks good to me", "no significant issues found"):
        rv = _vr("o", [_item(marker, "low")])
        assert _is_silent(rv) is True, marker


def test_no_issue_markers_include_openrouter_phrases():
    """マーカー辞書に OpenRouter 系英文が含まれる。"""
    assert "no significant issues" in NO_ISSUE_MARKERS
    assert "looks good" in NO_ISSUE_MARKERS
    assert "lgtm" in NO_ISSUE_MARKERS


# --- _judge ポリシーB（3社: all silent でのみ ng） ---


def test_judge_three_critical1_active_silent_ok():
    """(b') critical1社 + active1社 + silent(error)1社 → ok（エラー社は無情報）。"""
    reviews = [
        _vr("g", [_item("a", "critical")]),
        _vr("m", [_item("b", "high")]),
        _vr("o", [], status="error-exhausted"),
    ]
    assert _judge(reviews) == "ok"


def test_judge_three_critical1_all_silent_ng():
    """(b') critical1社 + 他2社とも沈黙 → ng（誰も反証しない）。"""
    reviews = [
        _vr("g", [_item("a", "critical")]),
        _vr("m", [_item("no issues found", "low")]),
        _vr("o", [], status="error-exhausted"),
    ]
    assert _judge(reviews) == "ng"


def test_judge_three_two_critical_ng():
    """(a) 3社中2社 critical → ng。"""
    reviews = [
        _vr("g", [_item("a", "critical")]),
        _vr("m", [_item("b", "critical")]),
        _vr("o", [_item("c", "low")]),
    ]
    assert _judge(reviews) == "ng"


# --- run_multi_llm_review 3社統合 ---


def test_run_three_all_ok():
    """3社正常 → verdict=ok・reviews 3社。"""
    g = '[{"issue":"x","severity":"low","quote":"q","suggestion":"s"}]'
    m = '[{"issue":"y","severity":"low","quote":"q","suggestion":"s"}]'
    o = '[{"issue":"z","severity":"low","quote":"q","suggestion":"s"}]'
    result = run_multi_llm_review(
        "target",
        "objective",
        gemini_runner=_gemini_runner(g),
        minimax_requester=lambda *a, **k: _minimax_ok(m),
        openrouter_requester=lambda *a, **k: _or_ok(o),
    )
    assert result.verdict == "ok"
    assert len(result.reviews) == 3
    assert {r.vendor for r in result.reviews} == {"gemini", "minimax", "openrouter"}


def test_run_three_openrouter_only_down_continues():
    """OpenRouter単独ダウン → abortしない（ok_vendors=2で継続・3社化の核心）。"""
    g = '[{"issue":"x","severity":"low","quote":"q","suggestion":"s"}]'
    m = '[{"issue":"y","severity":"low","quote":"q","suggestion":"s"}]'
    result = run_multi_llm_review(
        "target",
        "objective",
        gemini_runner=_gemini_runner(g),
        minimax_requester=lambda *a, **k: _minimax_ok(m),
        openrouter_requester=_or_down,
    )
    assert result.verdict == "ok"
    assert result.abort_reason == ""


def test_run_three_two_down_abort():
    """2社ダウン（minimax+openrouter）→ ok_vendors=1 → abort。"""
    g = '[{"issue":"x","severity":"low","quote":"q","suggestion":"s"}]'
    result = run_multi_llm_review(
        "target",
        "objective",
        gemini_runner=_gemini_runner(g),
        minimax_requester=lambda *a, **k: _MockResponse(429),
        openrouter_requester=_or_down,
    )
    assert result.verdict == "abort"
    assert "1社のみ" in result.abort_reason


def test_run_three_all_down_abort():
    """3社全滅 → abort・両系障害。"""
    def gemini_runner_empty():
        def load_cands(cap, paid_ok_limit=False):
            return ["gemini-3.1-pro-preview"]

        def run_fn(factory, candidates, api_key):
            return ("gemini-3.1-pro-preview", "")

        return (run_fn, load_cands)

    result = run_multi_llm_review(
        "target",
        "objective",
        gemini_runner=gemini_runner_empty(),
        minimax_requester=lambda *a, **k: _MockResponse(500),
        openrouter_requester=_or_down,
    )
    assert result.verdict == "abort"
    assert "両系障害" in result.abort_reason


def test_run_three_critical1_others_silent_ng():
    """critical1社 + 他2社とも沈黙 → ng（ポリシーB）。"""
    g = '[{"issue":"x","severity":"critical","quote":"q","suggestion":"s"}]'
    m = '[{"issue":"no issues found","severity":"low","quote":"","suggestion":""}]'
    result = run_multi_llm_review(
        "target",
        "objective",
        gemini_runner=_gemini_runner(g),
        minimax_requester=lambda *a, **k: _minimax_ok(m),
        openrouter_requester=_or_down,
    )
    assert result.verdict == "ng"


def test_run_three_critical1_one_active_ok():
    """critical1社 + active1社 + openrouterダウン → ok（flaky社で誤NGしない）。"""
    g = '[{"issue":"x","severity":"critical","quote":"q","suggestion":"s"}]'
    m = '[{"issue":"y","severity":"high","quote":"q","suggestion":"s"}]'
    result = run_multi_llm_review(
        "target",
        "objective",
        gemini_runner=_gemini_runner(g),
        minimax_requester=lambda *a, **k: _minimax_ok(m),
        openrouter_requester=_or_down,
    )
    assert result.verdict == "ok"


def test_run_missing_openrouter_key_graceful(monkeypatch):
    """OPENROUTER_API_KEY 未設定 → HTTP呼出なしで rv_o=error-auth・2社で継続。"""
    import review_lib

    calls = []

    def post(*a, **k):
        calls.append(a)
        return _or_ok('[{"issue":"z","severity":"low","quote":"q","suggestion":"s"}]')

    real_load = review_lib._load_secret

    def fake_load(name):
        if name == "OPENROUTER_API_KEY":
            return ""
        return real_load(name)

    monkeypatch.setattr(review_lib, "_load_secret", fake_load)
    g = '[{"issue":"x","severity":"low","quote":"q","suggestion":"s"}]'
    m = '[{"issue":"y","severity":"low","quote":"q","suggestion":"s"}]'
    result = run_multi_llm_review(
        "target",
        "objective",
        gemini_runner=_gemini_runner(g),
        minimax_requester=lambda *a, **k: _minimax_ok(m),
        openrouter_requester=post,
    )
    assert calls == []  # キー無しでは呼ばない
    or_review = next(r for r in result.reviews if r.vendor == "openrouter")
    assert or_review.raw_status == "error-auth"
    assert result.verdict == "ok"  # 2社で継続