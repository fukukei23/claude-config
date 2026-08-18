"""daily_triage のガード機構テスト（空応答検知・当日重複防止・Discord省略）。

D'案（2026-07-14）: L3弁証論で flock単独では17分差重複を防げないことが判明し、
当日既生成チェック（idempotency）を主軸・構造検証を中身の形で判定する設計。
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from daily_triage import (  # noqa: E402
    validate_judge_output,
    is_generated_today,
    send_discord,
    MIN_BODY_CHARS,
    REQUIRED_HEADER,
)


# ---------------- validate_judge_output ----------------

_VALID_BODY = f"""## 今日のタスク候補 (2026-07-14)

1. **タスクA** — 理由（repo: hoge）
2. **タスクB** — 理由（repo: fuga）

---
※ 人間の承認後に実行。
"""


def test_validate_valid_body_returns_as_is() -> None:
    """正常応答（ヘッダ+箇条書き+十分な長さ）はそのまま返却される。"""
    assert validate_judge_output(_VALID_BODY) == _VALID_BODY


def test_validate_empty_raises() -> None:
    """空応答は RuntimeError（事故の根本原因）。"""
    try:
        validate_judge_output("")
    except RuntimeError as e:
        assert "短すぎます" in str(e)
    else:
        raise AssertionError("空応答でRuntimeErrorが出ませんでした")


def test_validate_whitespace_only_raises() -> None:
    """空白のみも空応答同等。"""
    try:
        validate_judge_output("   \n  \n")
    except RuntimeError:
        return
    raise AssertionError("空白のみでRuntimeErrorが出ませんでした")


def test_validate_short_but_has_header_raises() -> None:
    """ヘッダだけ・文字数不足は RuntimeError。"""
    try:
        validate_judge_output(REQUIRED_HEADER)
    except RuntimeError as e:
        assert "短すぎます" in str(e)
    else:
        raise AssertionError("短い応答でRuntimeErrorが出ませんでした")


def test_validate_no_header_raises() -> None:
    """必須ヘッダ不在は RuntimeError（中身が壊れた応答を検知）。"""
    body = "1. タスクA\n2. タスクB\n" + "x" * MIN_BODY_CHARS
    try:
        validate_judge_output(body)
    except RuntimeError as e:
        assert "必須ヘッダ不在" in str(e) or REQUIRED_HEADER in str(e)
    else:
        raise AssertionError("ヘッダ不在でRuntimeErrorが出ませんでした")


def test_validate_no_numbered_list_raises() -> None:
    """数字箇条書き不在は RuntimeError。"""
    body = f"{REQUIRED_HEADER} (2026-07-14)\n\n本文のみでリスト無し。" + "x" * MIN_BODY_CHARS
    try:
        validate_judge_output(body)
    except RuntimeError as e:
        assert "箇条書き不在" in str(e)
    else:
        raise AssertionError("箇条書き不在でRuntimeErrorが出ませんでした")


# ---------------- is_generated_today ----------------

def test_generated_today_true(tmp_path: Path) -> None:
    """当日日付の generated_at があれば True（重複実行を検知）。"""
    p = tmp_path / "today-tasks.md"
    p.write_text("<!-- generated_at: 2026-07-14T15:59:46 -->\n## 今日のタスク候補", encoding="utf-8")
    assert is_generated_today(p, "2026-07-14") is True


def test_generated_today_other_day_false(tmp_path: Path) -> None:
    """別日日付なら False（当日分は未生成）。"""
    p = tmp_path / "today-tasks.md"
    p.write_text("<!-- generated_at: 2026-07-13T06:39:00 -->\n本文", encoding="utf-8")
    assert is_generated_today(p, "2026-07-14") is False


def test_generated_today_no_file_false(tmp_path: Path) -> None:
    """ファイル不在なら False。"""
    assert is_generated_today(tmp_path / "absent.md", "2026-07-14") is False


def test_generated_today_no_marker_false(tmp_path: Path) -> None:
    """ファイルは在るが generated_at 行無し（旧形式）なら False。"""
    p = tmp_path / "today-tasks.md"
    p.write_text("本文のみでタイムスタンプ無し", encoding="utf-8")
    assert is_generated_today(p, "2026-07-14") is False


# ---------------- send_discord （省略印） ----------------

class _FakeResp:
    status = 204

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *args: object) -> None:
        pass


def test_send_discord_truncates_with_marker(monkeypatch) -> None:
    """2000字超は切り詰め＋省略印付きで送信される（フォールバック巨大データ対策）。"""
    captured: dict = {}

    def fake_urlopen(req, timeout=30):  # noqa: ANN001
        captured["content"] = json.loads(req.data.decode("utf-8"))["content"]
        captured["len"] = len(captured["content"])
        return _FakeResp()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    long_content = "あ" * 3000
    ok = send_discord(long_content, "https://example.com/webhook")
    assert ok is True
    assert captured["len"] <= 2000
    assert "省略" in captured["content"] or "…" in captured["content"]


def test_send_discord_short_passes_through(monkeypatch) -> None:
    """2000字以下はそのまま（省略印なし）。"""
    captured: dict = {}

    def fake_urlopen(req, timeout=30):  # noqa: ANN001
        captured["content"] = json.loads(req.data.decode("utf-8"))["content"]
        return _FakeResp()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    short = "短いメッセージ"
    assert send_discord(short, "https://example.com/webhook") is True
    assert captured["content"] == short


# ---------------- judge_with_claude: envフラグ + 生応答ログ（2026-08-18改訂案） ----------------
"""改訂案(H主F副+生応答ログ): claude --print呼び出しへのenvフラグ渡しと
validate失敗時の生応答JSONL保存（post-mortem用）を検証する。"""

from types import SimpleNamespace  # noqa: E402
import daily_triage  # noqa: E402


def _fake_completed(stdout: str, returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr="stderR")


def test_judge_env_flag_passed_to_subprocess(monkeypatch, tmp_path) -> None:
    """judge_with_claude は CLAUDE_DISABLE_PLAIN_EXPLANATION_CHECK=1 をenvで渡す（H層）"""
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        captured["cmd"] = cmd
        return _fake_completed(_VALID_BODY)

    monkeypatch.setattr(daily_triage.subprocess, "run", fake_run)
    daily_triage.judge_with_claude("ctx", "2026-08-18", ["repo1"])
    env = captured.get("env")
    assert env is not None, "env引数が渡されていない"
    assert env.get("CLAUDE_DISABLE_PLAIN_EXPLANATION_CHECK") == "1"


def test_judge_failure_saves_raw_response_log(monkeypatch, tmp_path) -> None:
    """validate失敗時: 生応答をJSONLへ1行保存し、RuntimeErrorは継続する"""
    log = tmp_path / "judge-error.jsonl"
    monkeypatch.setattr(daily_triage, "JUDGE_ERROR_LOG", log)

    bad_body = "平易な解説のみの応答" + "X" * 600  # ヘッダなし（今朝の事故と同型）

    def fake_run(cmd, **kwargs):
        return _fake_completed(bad_body)

    monkeypatch.setattr(daily_triage.subprocess, "run", fake_run)
    try:
        daily_triage.judge_with_claude("ctx", "2026-08-18", ["repo1"])
    except RuntimeError:
        pass
    else:
        raise AssertionError("validate失敗でRuntimeErrorが出ませんでした")

    assert log.exists(), "生応答ログが書かれていません"
    lines = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
    rec = lines[0]
    for key in ("ts", "rc", "stdout_len", "prompt_sha256", "validation_error", "stdout"):
        assert key in rec, f"必須キー {key} がありません"
    assert rec["stdout"] == bad_body
    assert "必須ヘッダ不在" in rec["validation_error"]


def test_judge_log_write_failure_does_not_mask(monkeypatch, tmp_path) -> None:
    """ログ書込失敗（権限等）でも validate 由来のRuntimeErrorだけ上がる（クラッシュしない）"""
    unwritable = tmp_path / "blocked" / "judge-error.jsonl"
    unwritable.parent.mkdir()
    unwritable.write_text("")  # 親dirを作ってから…読み取り専用化の代わりにdirをファイルで塞ぐ
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    monkeypatch.setattr(daily_triage, "JUDGE_ERROR_LOG", blocker / "judge-error.jsonl")

    def fake_run(cmd, **kwargs):
        return _fake_completed("破壊された応答" + "Y" * 600)  # ヘッダなし

    monkeypatch.setattr(daily_triage.subprocess, "run", fake_run)
    try:
        daily_triage.judge_with_claude("ctx", "2026-08-18", ["repo1"])
    except RuntimeError as e:
        assert "必須ヘッダ不在" in str(e), "validate由来でない例外に置き換わっています"
    else:
        raise AssertionError("RuntimeErrorが出ませんでした")
