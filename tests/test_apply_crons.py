"""apply_crons.py のテスト（③-b: id突合根本対策・cron-id マーカー）.

apply_crons.py は scripts/auto-dev/ 配下（ハイフン含むディレクトリ）のため
通常の import が効かない・importlib で直接ロードする。
"""
import importlib.util
import sys
from pathlib import Path

APPLY_CRONS_PATH = (
    Path(__file__).parent.parent / "scripts" / "auto-dev" / "apply_crons.py"
)
_spec = importlib.util.spec_from_file_location("apply_crons", APPLY_CRONS_PATH)
apply_crons = importlib.util.module_from_spec(_spec)
sys.modules["apply_crons"] = apply_crons
_spec.loader.exec_module(apply_crons)


# ============================================================================
# Task 1: _append_cron_id_marker（冪等・rstrip）
# ============================================================================

def test_append_cron_id_marker_adds_marker():
    """prompt 末尾に [cron-id:N] を付与する"""
    prompt = "renew-crons: bash ~/bin/apply-crons.sh check を実行せよ"
    result = apply_crons._append_cron_id_marker(prompt, 3)
    assert result.rstrip().endswith("[cron-id:3]")


def test_append_cron_id_marker_idempotent():
    """既に末尾マーカー有なら重複付与しない（冪等）"""
    prompt = "renew-crons: bash ~/bin/apply-crons.sh\n[cron-id:3]"
    result = apply_crons._append_cron_id_marker(prompt, 3)
    assert result.count("[cron-id:3]") == 1
    assert result.rstrip().endswith("[cron-id:3]")


def test_append_cron_id_marker_rstrip_no_double_newline():
    """末尾改行付きpromptでも二重改行にならない（rstrip）"""
    prompt = "prompt text\n"
    result = apply_crons._append_cron_id_marker(prompt, 5)
    assert "\n\n" not in result
    assert result.endswith("[cron-id:5]")


# ============================================================================
# Task 2: _extract_cron_id（末尾1行・None・本文無視）
# ============================================================================

def test_extract_cron_id_from_marker():
    """末尾 [cron-id:N] から id を抽出"""
    prompt = "prompt text\n[cron-id:3]"
    assert apply_crons._extract_cron_id(prompt) == 3


def test_extract_cron_id_none_when_no_marker():
    """マーカー無しは None"""
    prompt = "prompt text without marker"
    assert apply_crons._extract_cron_id(prompt) is None


def test_extract_cron_id_ignores_marker_in_body():
    """本文中の [cron-id:N] 風文字列は無視・末尾1行のみ走査"""
    prompt = "[cron-id:99] body text\n[cron-id:3]"
    assert apply_crons._extract_cron_id(prompt) == 3


# ============================================================================
# Task 3: parse_definitions マーカー付与（全エントリ・冪等）
# ============================================================================

_SIMPLE_CRON_TEXT = (
    '# @cron id=2 name="test" schedule="17 1 * * *" health="commit:repo:3"\n'
    "#   test prompt: bash something\n"
)


def test_parse_definitions_appends_marker_to_all_entries():
    """全エントリの prompt 末尾に [cron-id:N] が付与される"""
    defs = apply_crons.parse_definitions(_SIMPLE_CRON_TEXT)
    assert len(defs) == 1
    assert defs[0].prompt.rstrip().endswith("[cron-id:2]")


def test_parse_definitions_marker_single_not_duplicated():
    """parse 結果の prompt にマーカーは1つのみ（重複なし）"""
    defs = apply_crons.parse_definitions(_SIMPLE_CRON_TEXT)
    assert defs[0].prompt.count("[cron-id:2]") == 1


# ============================================================================
# Task 4: _match 3層（両方一致/不一致/片方無legacy/id=8）
# ============================================================================

def _make_defn(cron_id: int, prompt: str, schedule: str = "0 3 * * *"):
    """テスト用 CronDefinition を生成"""
    return apply_crons.CronDefinition(
        id=cron_id, name="t", schedule=schedule, health="x", prompt=prompt
    )


def test_match_both_markers_same_id():
    """両方マーカー有り・id一致 → True（層1）"""
    defn = _make_defn(3, "prompt\n[cron-id:3]")
    task = {"cron": "0 3 * * *", "prompt": "prompt\n[cron-id:3]"}
    assert apply_crons._match(defn, task)


def test_match_both_markers_diff_id():
    """両方マーカー有り・id不一致 → False（層2・create対象）"""
    defn = _make_defn(3, "prompt\n[cron-id:3]")
    task = {"cron": "0 3 * * *", "prompt": "prompt\n[cron-id:5]"}
    assert not apply_crons._match(defn, task)


def test_match_both_markers_same_id_diff_schedule():
    """両方マーカー有り・id一致だがschedule違う → False（schedule変更検知・MiniMax指摘）"""
    defn = _make_defn(3, "prompt\n[cron-id:3]", schedule="0 5 * * *")
    task = {"cron": "0 3 * * *", "prompt": "prompt\n[cron-id:3]"}  # schedule違う
    assert not apply_crons._match(defn, task)


def test_extract_cron_id_whitespace_only_returns_none():
    """空白のみprompt で IndexError 起こさず None（Gemini指摘）"""
    assert apply_crons._extract_cron_id("   \n  \n") is None
    assert apply_crons._extract_cron_id("") is None


def test_match_one_side_no_marker_legacy():
    """片方のみマーカー無し → 従来（schedule+先頭40字）で True（層3・clean誤削除防止）"""
    long_prompt = (
        "renew-crons: bash ~/bin/apply-crons.sh check を実行し"
        "stdout の ACTION 行に従い CronCreate で再登録せよ"
    )  # 50字超・末尾マーカーが先頭40字に入らない（実運用のprompt長さ）
    defn = _make_defn(3, long_prompt + "\n[cron-id:3]")
    task = {"cron": "0 3 * * *", "prompt": long_prompt}  # マーカー無し・先頭40字一致
    assert apply_crons._match(defn, task)


def test_match_legacy_only():
    """両方マーカー無し → 従来通り"""
    defn = _make_defn(3, "prompt text here")
    task = {"cron": "0 3 * * *", "prompt": "prompt text here"}
    assert apply_crons._match(defn, task)


def test_match_id8_with_marker():
    """id=8(enabled=false)でも _match は3層で動く（diff/clean で除外は既存 if not enabled）"""
    defn = apply_crons.CronDefinition(
        id=8, name="melody", schedule="0 0 1 * *", health="x",
        prompt="melody prompt\n[cron-id:8]", enabled=False,
    )
    task = {"cron": "0 0 1 * *", "prompt": "melody prompt\n[cron-id:8]"}
    assert apply_crons._match(defn, task)


# ============================================================================
# Task 2: one_shot 属性（reconcile準備）
# ============================================================================

def test_parse_one_shot_true():
    text = '# @cron id=99 name="tmp" schedule="7 9 20 8 *" health="none" one_shot=true\n#   tmp prompt\n'
    defs = apply_crons.parse_definitions(text)
    assert defs[0].one_shot is True

def test_parse_one_shot_default_false():
    text = '# @cron id=99 name="tmp" schedule="7 9 20 8 *" health="none"\n#   tmp prompt\n'
    defs = apply_crons.parse_definitions(text)
    assert defs[0].one_shot is False


# ============================================================================
# Task 3: [RESULT] シグナルヘルパー
# ============================================================================

def test_result_line_done():
    assert apply_crons.result_line("done") == "[RESULT]=done"

def test_result_line_skip_with_reason():
    assert apply_crons.result_line("skip", reason="stamp") == "[RESULT]=skip reason=stamp"

def test_result_line_error_exit_code():
    assert apply_crons.EXIT_FAIL == 20 and apply_crons.EXIT_OK == 0


# ============================================================================
# Task 4: write_tasks（マージ方式書換え・バックアップ・validate・ロールバック）
# ============================================================================

import json as _json
import os as _os
import tempfile as _tempfile


def _tmp_tasks(entries):
    fd, p = _tempfile.mkstemp(suffix=".json")
    _os.close(fd)
    _json.dump({"tasks": entries}, open(p, "w"))
    return p


def test_write_tasks_backup_and_validate_ok():
    p = _tmp_tasks([{"id": "x1", "prompt": "A", "unknown": {"keep": 1}}])
    out = apply_crons.write_tasks([{"id": "x1", "prompt": "A2", "unknown": {"keep": 1}}], path=p)
    d = _json.load(open(p))
    assert d["tasks"][0]["prompt"] == "A2" and d["tasks"][0]["unknown"] == {"keep": 1}
    assert out == "done" and _os.path.exists(p + ".bak")


def test_write_tasks_invalid_source_rollback():
    p = _tmp_tasks([{"id": "x1", "prompt": "A"}])
    # ソース(json)自体が壊れている状態を作る
    open(p, "w").write("{broken")
    out = apply_crons.write_tasks([{"id": "x1", "prompt": "B"}], path=p)
    assert out == "error" and open(p).read() == "{broken"  # 失敗時は書き込まない


# ============================================================================
# Task 5: desired_entries（自己bootstrap・未知フィールド保持・ゴースト除去）
# ============================================================================

def _defs():
    """実運用と同じくprompt末尾に[cron-id:N]マーカー付きで構築(parse_definitions相当)。"""
    mk = apply_crons._append_cron_id_marker
    return [
        apply_crons.CronDefinition(id=3, name="renew", schedule="0 3 */6 * *",
                                   health="none", prompt=mk("renew-crons: bash ~/bin/apply-crons.sh reconcile", 3)),
        apply_crons.CronDefinition(id=5, name="daily", schedule="5 15 * * *",
                                   health="none", prompt=mk("usage", 5)),
    ]


def test_desired_entries_keeps_unknown_fields_and_drops_ghost():
    current = [
        {"id": "a", "prompt": "usage\n[cron-id:5]", "cron": "5 15 * * *", "extra": "keep-me"},
        {"id": "b", "prompt": "ghost job", "cron": "1 1 1 1 *"},
    ]
    desired = apply_crons.desired_entries(_defs(), current)
    prompts = [e["prompt"] for e in desired]
    assert any("cron-id:3" in p for p in prompts)      # renew自己bootstrap生成
    assert any(e.get("extra") == "keep-me" for e in desired)  # 未知フィールド保持
    assert all("ghost" not in p for p in desired)      # ゴースト除去


def test_self_bootstrap_only_when_missing():
    current = [{"id": "a", "prompt": "renew-crons: bash ~/bin/apply-crons.sh reconcile\n[cron-id:3]", "cron": "0 3 */6 * *", "recurring": True}]
    desired = apply_crons.desired_entries(_defs(), current)
    assert sum(1 for e in desired if "cron-id:3" in e["prompt"]) == 1  # 二重にならない


# ============================================================================
# Task 6: CCバージョン照合ゲート
# ============================================================================

def test_version_gate(tmp_path, monkeypatch):
    gate_file = tmp_path / "v"
    gate_file.write_text("1.0.99")
    monkeypatch.setattr(apply_crons, "VERSION_GATE_PATH", str(gate_file))
    assert apply_crons.version_gate(current="1.0.99") is True   # 一致→通過
    assert apply_crons.version_gate(current="1.1.0") is False   # 乖離→拒否
    assert apply_crons.version_gate(current="1.1.0") is False   # 2回目も拒否(gate不変)
    assert gate_file.read_text() == "1.0.99"


# ============================================================================
# Task 7: reconcile（スタンプ判定・flock・[RESULT]）
# ============================================================================

def test_stamp_should_apply(tmp_path, monkeypatch):
    monkeypatch.setattr(apply_crons, "STAMP_PATH", str(tmp_path / "stamp"))
    apply_crons.write_stamp()  # 今日のcheck緑を記録
    assert apply_crons.stamp_today() is True
    assert apply_crons.should_apply(stamp_ok=True, mismatch=False, force=True) is True   # --force
    assert apply_crons.should_apply(stamp_ok=True, mismatch=False, force=False) is False  # 省略
    assert apply_crons.should_apply(stamp_ok=True, mismatch=True, force=False) is True    # 不一致→常にapply
    assert apply_crons.should_apply(stamp_ok=False, mismatch=False, force=False) is True  # 未記録→apply
