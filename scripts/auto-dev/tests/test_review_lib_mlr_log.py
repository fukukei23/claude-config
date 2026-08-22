"""review_lib.py の失敗ログ JSONL 記録テスト（対応案(a)・2026-08-22）

auto-loop のレビューは review_lib.py が python の requests で直接APIを叩くため、
PostToolUse hook（log-mlr-calls.sh）では原理的に捕捉できない
（hook は tool_input.command にドメイン文字列が現れることを判定条件にしている）。
しかも二重起票を招いた当の失敗（2026-08-18・2026-08-21）はどちらもこの経路だった。
そこで呼出元が自分で1行書き、hook の守備範囲外をカバーする。

spec: obsidian-ssot/docs/superpowers/specs/2026-08-21-multi-llm-review-failure-log-design.md
"""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from review_lib import (  # noqa: E402
    MultiReviewResult,
    ReviewItem,
    VendorReview,
    append_mlr_log,
    build_mlr_log_records,
    run_multi_llm_review,
)

MLR_REQUIRED_KEYS = [
    "ts", "round_id", "topic", "llm", "model", "attempt", "result",
    "reason", "http", "finish_reason", "findings", "status", "backlogged",
]


def _vr(vendor="openrouter", status="ok", n_items=3, model="m1", fallback=False,
        err=""):
    """テスト用 VendorReview を組み立てる。"""
    items = [
        ReviewItem(severity="high", issue=f"issue{i}", quote="q", suggestion="s")
        for i in range(n_items)
    ]
    return VendorReview(
        vendor=vendor,
        backend_kind=f"{vendor}-kind",
        items=items,
        raw_status=status,
        model=model,
        fallback_used=fallback,
        error_detail=err,
    )


def _result(reviews, verdict="ok", abort_reason=""):
    return MultiReviewResult(reviews=reviews, verdict=verdict,
                             abort_reason=abort_reason)


# --- build_mlr_log_records（純粋関数）---


def test_records_have_full_schema():
    """hook が書くのと同じ13キーが全て揃う（mlr-log.sh --self-test 互換）。"""
    recs = build_mlr_log_records(_result([_vr()]), "al-20260822-090000", "t")
    assert len(recs) == 1
    for k in MLR_REQUIRED_KEYS:
        assert k in recs[0], f"必須キー {k} が無い"


def test_records_ok_case():
    """ok は result=ok / reason=None / findings=指摘件数。"""
    recs = build_mlr_log_records(_result([_vr(status="ok", n_items=7)]), "r1", "t")
    assert recs[0]["result"] == "ok"
    assert recs[0]["reason"] is None
    assert recs[0]["findings"] == 7
    assert recs[0]["llm"] == "openrouter"


def test_records_status_is_annotated():
    """auto-loop は自動実行でホスト補記が来ないため直接 annotated を書く。"""
    recs = build_mlr_log_records(_result([_vr()]), "r1", "t")
    assert recs[0]["status"] == "annotated"
    assert recs[0]["backlogged"] is False


def test_records_carry_round_id_and_topic():
    """round_id / topic が全レコードに入る。"""
    recs = build_mlr_log_records(
        _result([_vr("gemini"), _vr("minimax"), _vr("openrouter")]),
        "al-20260822-091500", "issue-116 plan",
    )
    assert len(recs) == 3
    assert all(r["round_id"] == "al-20260822-091500" for r in recs)
    assert all(r["topic"] == "issue-116 plan" for r in recs)


@pytest.mark.parametrize(
    "status,exp_reason,exp_http",
    [
        ("empty", "empty_body_keepalive_only", None),
        ("error-auth", "auth_401", 401),
        ("error-429", "rate_limited_429", 429),
        ("error-402", "payment_required_402", 402),
        ("error-5xx", "other", None),
        ("error-exhausted", "other", None),
    ],
)
def test_records_status_mapping(status, exp_reason, exp_http):
    """raw_status を spec §5 の reason enum へ写す。"""
    recs = build_mlr_log_records(_result([_vr(status=status, n_items=0)]), "r", "t")
    assert recs[0]["result"] == "fail"
    assert recs[0]["reason"] == exp_reason
    assert recs[0]["http"] == exp_http
    assert recs[0]["findings"] == 0


def test_records_attempt_reflects_fallback():
    """fallback を使ったら attempt=2（本命1機目で通れば1）。"""
    r1 = build_mlr_log_records(_result([_vr(fallback=False)]), "r", "t")[0]
    r2 = build_mlr_log_records(_result([_vr(fallback=True)]), "r", "t")[0]
    assert r1["attempt"] == 1
    assert r2["attempt"] == 2


def test_records_empty_model_becomes_none():
    """model 未取得（全モデル失敗等）は空文字でなく None。"""
    recs = build_mlr_log_records(
        _result([_vr(status="error-exhausted", model="", n_items=0)]), "r", "t")
    assert recs[0]["model"] is None


def test_records_cover_abort_case():
    """★3社全滅(abort)こそ記録したいケース。早期returnで取り逃さないこと。"""
    reviews = [
        _vr("gemini", status="error-5xx", n_items=0),
        _vr("minimax", status="empty", n_items=0),
        _vr("openrouter", status="error-exhausted", n_items=0),
    ]
    recs = build_mlr_log_records(
        _result(reviews, verdict="abort", abort_reason="両系障害"), "r", "t")
    assert len(recs) == 3
    assert all(r["result"] == "fail" for r in recs)


def test_records_auth_error_hidden_in_5xx_is_recovered():
    """★Gemini は鍵未設定でも SDK 例外が error-5xx に丸められる。

    other に埋没させると起票前チェック（reason×model の2軸）で auth_401 として
    引けず、二重起票を防げない（＝機構の目的①が達成できない）。
    """
    recs = build_mlr_log_records(
        _result([_vr("gemini", status="error-5xx", n_items=0,
                     err="No API key was provided. Please pass a valid API key.")]),
        "r", "t")
    assert recs[0]["reason"] == "auth_401"
    assert recs[0]["http"] == 401


def test_records_genuine_5xx_stays_other():
    """本物のサーバエラーは auth_401 に寄せない（過剰補正の禁止）。"""
    recs = build_mlr_log_records(
        _result([_vr("gemini", status="error-5xx", n_items=0,
                     err="503 Service Unavailable: backend overloaded")]),
        "r", "t")
    assert recs[0]["reason"] == "other"
    assert recs[0]["http"] is None


def test_records_ts_is_iso8601():
    recs = build_mlr_log_records(_result([_vr()]), "r", "t")
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", recs[0]["ts"])


def test_records_finish_reason_is_none():
    """HTTP層の finish_reason は review_lib からは取得できないため常に None。"""
    recs = build_mlr_log_records(_result([_vr()]), "r", "t")
    assert recs[0]["finish_reason"] is None


# --- append_mlr_log（副作用・例外を投げない）---


def test_append_writes_one_line_per_record(tmp_path):
    """1レコード1行で追記される（上書きでない）。"""
    p = tmp_path / "multi-llm-review.jsonl"
    recs = build_mlr_log_records(
        _result([_vr("gemini"), _vr("minimax")]), "r1", "t")
    assert append_mlr_log(recs, p) is True
    assert append_mlr_log(
        build_mlr_log_records(_result([_vr()]), "r2", "t"), p) is True
    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 3
    assert [json.loads(ln)["llm"] for ln in lines] == [
        "gemini", "minimax", "openrouter"]


def test_append_writes_valid_utf8(tmp_path):
    """日本語 topic が壊れない（Windows cp932 対策）。"""
    p = tmp_path / "l.jsonl"
    append_mlr_log(build_mlr_log_records(_result([_vr()]), "r", "日本語トピック"), p)
    assert json.loads(
        p.read_text(encoding="utf-8").strip())["topic"] == "日本語トピック"


def test_append_never_raises_on_failure(tmp_path):
    """★書込失敗でも例外を投げない（ログのためにレビュー本体を人質にしない）。"""
    bad = tmp_path / "no_such_dir" / "deep" / "l.jsonl"
    assert append_mlr_log(
        build_mlr_log_records(_result([_vr()]), "r", "t"), bad) is False


def test_append_empty_records_is_noop(tmp_path):
    p = tmp_path / "l.jsonl"
    assert append_mlr_log([], p) is False
    assert not p.exists()


def test_log_path_is_none_under_pytest(monkeypatch):
    """★テスト実行中は本番ログへ書かない（本番データ汚染の防止）。

    2026-08-22 実測: 既存テストが run_multi_llm_review を14回呼ぶため、
    1回の pytest で42行が本番 JSONL に混入し指標A/Bの分母を壊した。
    conftest の fixture だけに頼ると別ディレクトリ実行・新規ファイルで漏れる
    ため、実装側にもガードを置く（二重防御）。
    """
    import review_lib

    monkeypatch.delenv("MLR_LOG_FILE", raising=False)
    monkeypatch.delenv("MLR_STATE_DIR", raising=False)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "dummy::test")
    assert review_lib._mlr_log_path() is None


def test_log_path_respects_explicit_env_even_under_pytest(tmp_path, monkeypatch):
    """明示指定（MLR_LOG_FILE）があればテスト中でもそこへ書く。"""
    import review_lib

    p = tmp_path / "explicit.jsonl"
    monkeypatch.setenv("MLR_LOG_FILE", str(p))
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "dummy::test")
    assert review_lib._mlr_log_path() == p


def test_append_is_noop_when_path_unresolvable(monkeypatch):
    """パスが決められない時は静かに False（例外を投げない）。"""
    import review_lib

    monkeypatch.delenv("MLR_LOG_FILE", raising=False)
    monkeypatch.delenv("MLR_STATE_DIR", raising=False)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "dummy::test")
    recs = build_mlr_log_records(_result([_vr()]), "r", "t")
    assert review_lib.append_mlr_log(recs) is False


# --- run_multi_llm_review 本番経路 ---


class _MockResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._json = payload

    def json(self):
        return self._json


def _gemini_runner(text, model="gemini-3.1-pro-preview"):
    """(run_fn, load_cands) の mock（既存 test_review_lib.py と同形式）。"""

    def load_cands(cap, paid_ok_limit=False):
        return [model]

    def run_fn(factory, candidates, api_key):
        return model, text

    return (run_fn, load_cands)


def _minimax_ok(text):
    return _MockResponse(200, {"content": [{"type": "text", "text": text}]})


def _openrouter_ok(text):
    return _MockResponse(
        200, {"choices": [{"message": {"content": text}, "finish_reason": "stop"}]}
    )


def _all_keys(monkeypatch):
    """3社の鍵を注入する。

    `_load_secret` は環境変数→ファイル位置の順に探すため、実鍵の有無で
    テスト結果が変わるのを防ぐ目的（既存テストと同じ理由・2026-08-21実測）。
    """
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("MINIMAX_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")


_G = '[{"severity":"high","issue":"i","quote":"q","suggestion":"s"}]'


def test_run_review_logs_to_jsonl(tmp_path, monkeypatch):
    """★本番経路: run_multi_llm_review が JSONL に3行書く。"""
    p = tmp_path / "multi-llm-review.jsonl"
    monkeypatch.setenv("MLR_LOG_FILE", str(p))
    _all_keys(monkeypatch)
    result = run_multi_llm_review(
        "target", "objective",
        gemini_runner=_gemini_runner(_G),
        minimax_requester=lambda *a, **k: _minimax_ok(_G),
        openrouter_requester=lambda *a, **k: _openrouter_ok(_G),
        round_id="al-test-1", topic="unit",
    )
    assert result.verdict in ("ok", "ng")
    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 3
    assert {json.loads(ln)["llm"] for ln in lines} == {
        "gemini", "minimax", "openrouter"}
    assert all(json.loads(ln)["round_id"] == "al-test-1" for ln in lines)
    assert all(json.loads(ln)["result"] == "ok" for ln in lines)


def test_run_review_auto_round_id(tmp_path, monkeypatch):
    """round_id 省略時は al- prefix 付きで自動生成（hook経由と区別できる）。"""
    p = tmp_path / "l.jsonl"
    monkeypatch.setenv("MLR_LOG_FILE", str(p))
    _all_keys(monkeypatch)
    run_multi_llm_review(
        "target", "objective",
        gemini_runner=_gemini_runner(_G),
        minimax_requester=lambda *a, **k: _minimax_ok(_G),
        openrouter_requester=lambda *a, **k: _openrouter_ok(_G),
    )
    rid = json.loads(p.read_text(encoding="utf-8").splitlines()[0])["round_id"]
    assert rid.startswith("al-")


def _gemini_auth_fail():
    """鍵不正で SDK が例外を投げる runner（Gemini は error-5xx に丸められる）。"""

    def load_cands(cap, paid_ok_limit=False):
        return ["gemini-3.1-pro-preview"]

    def run_fn(factory, candidates, api_key):
        raise RuntimeError("No API key was provided. Please pass a valid API key.")

    return (run_fn, load_cands)


def _auth_fail(*_a, **_k):
    return _MockResponse(401, {"error": {"code": 401, "message": "unauthorized"}})


def test_run_review_logs_even_on_abort(tmp_path, monkeypatch):
    """★abort（多様性不足で早期return）でも記録が残る。

    3社とも認証失敗を mock で作る（実HTTPを踏まないので `requests` 未導入の
    環境でも動く＝Windows 側 python3 でも緑になる）。
    併せて「Gemini の認証失敗が error-5xx に丸められても auth_401 に寄る」
    補正が本番経路で効いていることも確認する。
    """
    p = tmp_path / "l.jsonl"
    monkeypatch.setenv("MLR_LOG_FILE", str(p))
    _all_keys(monkeypatch)
    result = run_multi_llm_review(
        "target", "objective",
        gemini_runner=_gemini_auth_fail(),
        minimax_requester=_auth_fail,
        openrouter_requester=_auth_fail,
        round_id="al-abort", topic="t",
    )
    assert result.verdict == "abort"
    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 3
    assert all(json.loads(ln)["result"] == "fail" for ln in lines)
    assert all(json.loads(ln)["reason"] == "auth_401" for ln in lines)


def test_run_review_survives_log_failure(tmp_path, monkeypatch):
    """★ログ書込が失敗してもレビュー結果は返る（auto-loopを止めない）。"""
    monkeypatch.setenv("MLR_LOG_FILE", str(tmp_path / "nodir" / "deep" / "l.jsonl"))
    _all_keys(monkeypatch)
    result = run_multi_llm_review(
        "target", "objective",
        gemini_runner=_gemini_runner(_G),
        minimax_requester=lambda *a, **k: _minimax_ok(_G),
        openrouter_requester=lambda *a, **k: _openrouter_ok(_G),
    )
    assert result.verdict in ("ok", "ng")
