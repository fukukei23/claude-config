"""check-plain-explanation.sh（Stop hook）のテスト.

H層（envフラグ明示オプトアウト）+F層（実user数による機械呼び出し判定）
+dispatch.log（exit経路記録）の改訂案2026-08-18実装と、
既存動作（マーカー検知・短文・ループガード・transcript無し）の回帰を検証する。

合成transcriptのuser content形式は実トランスクリプト
（content: [{"type": "text", "text": ...}]・Stop hook feedbackは先頭プレフィックスで識別）
に準拠させる（2026-08-18 06:38 事故トランスクリプト entry 10/19 の実構造）。

実行: cd ~/projects/claude-config && python3 -m pytest tests/test_check_plain_explanation.py -q
"""

import json
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).parents[1]
SCRIPT = REPO / "scripts" / "session" / "check-plain-explanation.sh"

LONG_TEXT = "A" * 650  # 600字超・マーカーなし
MARKER_TEXT = "B" * 650 + "\n💡 一言でいうと: テスト"


def make_transcript(path: Path, entries: list[tuple[str, str]]) -> Path:
    """合成transcript JSONLを作る。entries = [(type, text), ...]"""
    with open(path, "w", encoding="utf-8") as f:
        for typ, text in entries:
            rec = {
                "type": typ,
                "message": {"content": [{"type": "text", "text": text}]},
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return path


def run_hook(home: Path, transcript: Path | None, session_id: str,
             env_extra: dict | None = None) -> tuple[int, str]:
    """hookを実行し (rc, stdout+stderr) を返す。HOMEはtmpに隔離。"""
    payload = {
        "session_id": session_id,
        "transcript_path": str(transcript) if transcript else "",
    }
    env = {"HOME": str(home), "PATH": os.environ["PATH"]}
    env.update(env_extra or {})
    r = subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(payload).encode(),
        capture_output=True,
        timeout=15,
        env=env,
    )
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", errors="replace")


def guard_dir(home: Path) -> Path:
    return home / ".claude" / "state" / "plain-explanation-guard"


def dispatch_log(home: Path) -> str:
    p = guard_dir(home) / "dispatch.log"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def guard_file_exists(home: Path, session_id: str) -> bool:
    return (guard_dir(home) / f"{session_id}.last").exists()


# ============ H層: envフラグ明示オプトアウト（新機能） ============

def test_env_flag_skips_check(tmp_path):
    """CLAUDE_DISABLE_PLAIN_EXPLANATION_CHECK=1 なら block対象の応答でも即exit 0・guard/差戻しなし"""
    home = tmp_path / "home"
    home.mkdir()
    t = make_transcript(tmp_path / "t.jsonl", [
        ("user", "プロンプト"),
        ("assistant", LONG_TEXT),
    ])
    rc, out = run_hook(home, t, "envtest1",
                       {"CLAUDE_DISABLE_PLAIN_EXPLANATION_CHECK": "1"})
    assert rc == 0
    assert "block" not in out  # 差戻しJSONを出さない
    assert not guard_file_exists(home, "envtest1")  # guard対象外
    assert "exit=env-flag" in dispatch_log(home)  # dispatch.logに記録


def test_env_flag_wins_even_for_dialogue(tmp_path):
    """envフラグは対話形式(user 2個)でも無条件で効く（H層が主防御）"""
    home = tmp_path / "home"
    home.mkdir()
    t = make_transcript(tmp_path / "t.jsonl", [
        ("user", "質問1"),
        ("assistant", LONG_TEXT),
        ("user", "質問2"),
        ("assistant", LONG_TEXT),
    ])
    rc, out = run_hook(home, t, "envtest2",
                       {"CLAUDE_DISABLE_PLAIN_EXPLANATION_CHECK": "1"})
    assert rc == 0
    assert "block" not in out
    assert "exit=env-flag" in dispatch_log(home)


# ============ F層: 実user数による機械呼び出し自動除外（新機能） ============

def test_single_real_user_passes(tmp_path):
    """実user 1個のみ（=claude --print機械呼び出し）は block 対象でも素通り"""
    home = tmp_path / "home"
    home.mkdir()
    t = make_transcript(tmp_path / "t.jsonl", [
        ("user", "JUDGE_PROMPT本文"),
        ("assistant", LONG_TEXT),
    ])
    rc, out = run_hook(home, t, "machinetest1")
    assert rc == 0
    assert "block" not in out
    assert not guard_file_exists(home, "machinetest1")
    assert "exit=machine-fallback" in dispatch_log(home)


def test_feedback_user_not_counted(tmp_path):
    """Stop hook feedback 由来の user entry はカウント除外（差戻し後の再stopでも実user=1なら素通り）"""
    home = tmp_path / "home"
    home.mkdir()
    t = make_transcript(tmp_path / "t.jsonl", [
        ("user", "JUDGE_PROMPT本文"),
        ("assistant", LONG_TEXT),
        ("user", "Stop hook feedback: 平易な解説の併記忘れの可能性: ..."),
        ("assistant", "C" * 300),  # 追加発話（短文）
    ])
    rc, out = run_hook(home, t, "machinetest2")
    assert rc == 0
    assert "block" not in out
    assert "exit=machine-fallback" in dispatch_log(home)


def test_no_user_entries_passes(tmp_path):
    """user entry 0個の異常系 transcript も機械扱いで素通り（fail-safe）"""
    home = tmp_path / "home"
    home.mkdir()
    t = make_transcript(tmp_path / "t.jsonl", [
        ("assistant", LONG_TEXT),
    ])
    rc, out = run_hook(home, t, "machinetest3")
    assert rc == 0
    assert "block" not in out


# ============ 回帰: 対話セッションでは従来どおり差戻し（acceptance criteria a） ============

def test_dialogue_two_users_blocked(tmp_path):
    """実user 2個（対話）は block JSON を出力する（平易解説強制の維持）"""
    home = tmp_path / "home"
    home.mkdir()
    t = make_transcript(tmp_path / "t.jsonl", [
        ("user", "質問1"),
        ("assistant", "かしこまり"),
        ("user", "詳細を教えて"),
        ("assistant", LONG_TEXT),
    ])
    rc, out = run_hook(home, t, "dialogue1")
    assert rc == 0
    assert '"decision": "block"' in out
    assert guard_file_exists(home, "dialogue1")  # guard作成（1回制限用）
    assert "exit=blocked" in dispatch_log(home)


def test_feedback_counted_dialogue_still_blocked(tmp_path):
    """実user 2個 + feedback 1個 の対話は block 維持（feedback除外が対話を誤除外しない）"""
    home = tmp_path / "home"
    home.mkdir()
    t = make_transcript(tmp_path / "t.jsonl", [
        ("user", "質問1"),
        ("assistant", "回答"),
        ("user", "追記質問"),
        ("assistant", LONG_TEXT),
        ("user", "Stop hook feedback: 平易な解説の併記忘れの可能性: ..."),
        ("assistant", LONG_TEXT),
    ])
    rc, out = run_hook(home, t, "dialogue2")
    assert rc == 0
    assert '"decision": "block"' in out


# ============ 回帰: 既存5パターン（2026-08-17実装時のad-hocテスト恒久化） ============

def test_long_with_marker_passes(tmp_path):
    """💡マーカーあり長文 → 通過"""
    home = tmp_path / "home"
    home.mkdir()
    t = make_transcript(tmp_path / "t.jsonl", [
        ("user", "質問1"),
        ("user", "質問2"),
        ("assistant", MARKER_TEXT),
    ])
    rc, out = run_hook(home, t, "marker1")
    assert rc == 0
    assert "block" not in out
    assert "exit=plain-marker" in dispatch_log(home)


def test_short_text_passes(tmp_path):
    """600字未満 → 通過"""
    home = tmp_path / "home"
    home.mkdir()
    t = make_transcript(tmp_path / "t.jsonl", [
        ("user", "質問1"),
        ("user", "質問2"),
        ("assistant", "短い"),
    ])
    rc, out = run_hook(home, t, "short1")
    assert rc == 0
    assert "block" not in out
    assert "exit=short" in dispatch_log(home)


def test_guard_second_invocation_passes(tmp_path):
    """同一メッセージへの2回目 → 通過（ループガード）"""
    home = tmp_path / "home"
    home.mkdir()
    t = make_transcript(tmp_path / "t.jsonl", [
        ("user", "質問1"),
        ("user", "質問2"),
        ("assistant", LONG_TEXT),
    ])
    rc1, out1 = run_hook(home, t, "guard1")
    assert '"decision": "block"' in out1
    rc2, out2 = run_hook(home, t, "guard1")  # 同一session・同一hash
    assert rc2 == 0
    assert "block" not in out2
    assert "exit=guard-pass" in dispatch_log(home)


def test_missing_transcript_passes(tmp_path):
    """transcript_path 不在 → 通過"""
    home = tmp_path / "home"
    home.mkdir()
    rc, out = run_hook(home, None, "notranscript")
    assert rc == 0
    assert "block" not in out
    assert "exit=no-transcript" in dispatch_log(home)
