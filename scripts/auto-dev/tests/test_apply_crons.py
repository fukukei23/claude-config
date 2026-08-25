"""apply_crons.py のテスト。"""
import json
import subprocess
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from apply_crons import parse_definitions, CronDefinition, ParseError
from apply_crons import probe_commit, probe_file, probe_log, HealthStatus
from apply_crons import diff, Action, load_tasks
from apply_crons import run_clean, CleanError

FIXTURES = Path(__file__).parent / "fixtures"


def _sample_text() -> str:
    return (FIXTURES / "renew-crons-sample.sh").read_text()


def test_parse_tag_format():
    """正常系: # @cron タグ書式を正しくparseする。"""
    defs = parse_definitions(_sample_text())
    ids = {d.id for d in defs}
    assert {1, 5, 8, 9} == ids
    lint = next(d for d in defs if d.id == 1)
    assert lint.name == "Knowledge Lint"
    assert lint.schedule == "3 3 * * 0,2,4"
    assert lint.health == "commit:obsidian-ssot:3"
    assert lint.prompt.strip().startswith("Knowledge Lint: bash")
    assert lint.enabled is True
    melody = next(d for d in defs if d.id == 8)
    assert melody.enabled is False


def test_parse_invalid_format_id_dup():
    """異常系: id重複で ParseError。"""
    text = '''# @cron id=1 name="A" schedule="0 0 * * *" health="commit:r:3"
#   prompt A
# @cron id=1 name="B" schedule="0 0 * * *" health="commit:r:3"
#   prompt B
'''
    with pytest.raises(ParseError, match="id.*重複"):
        parse_definitions(text)


def test_parse_invalid_format_schedule():
    """異常系: scheduleが5フィールドでないと ParseError。"""
    text = '# @cron id=1 name="A" schedule="0 0 *" health="commit:r:3"\n#   prompt A\n'
    with pytest.raises(ParseError, match="schedule"):
        parse_definitions(text)


def test_health_probe_commit_threshold(tmp_path, monkeypatch):
    """commit型: repo最終commit日時で判定（prefix廃止）。閾値以内✅/超過⚠️。"""
    def fake_last_commit_days(repo: str) -> float:
        return 3.0

    monkeypatch.setattr("apply_crons._last_commit_days", fake_last_commit_days)
    fresh = probe_commit("obsidian-ssot", max_days=5)
    stale = probe_commit("obsidian-ssot", max_days=2)
    assert fresh.status == HealthStatus.OK
    assert stale.status == HealthStatus.STALE


def test_health_probe_file(tmp_path):
    """file型: glob最新ファイルの日付で判定。"""
    fresh = tmp_path / "2026-06-28.json"
    fresh.write_text("{}")
    ok = probe_file(str(fresh), max_days=2)
    assert ok.status == HealthStatus.OK
    none = probe_file(str(tmp_path / "none-*.json"), max_days=2)
    assert none.status == HealthStatus.STALE


def test_health_probe_log(tmp_path):
    """log型: ファイルmtimeで判定。"""
    logf = tmp_path / "cron-health.log"
    logf.write_text("line\n")
    ok = probe_log(str(logf), max_hours=30)
    assert ok.status == HealthStatus.OK
    miss = probe_log(str(tmp_path / "missing.log"), max_hours=30)
    assert miss.status == HealthStatus.STALE


def _sample_tasks():
    """fixture: 既存タスク実体のシミュレーション。"""
    return json.loads((FIXTURES / "scheduled-tasks-sample.json").read_text())["tasks"]


def test_skip_existing_same_prompt():
    """定義と実体が一致（schedule+prompt先頭40字）ならskip。"""
    defs = parse_definitions(_sample_text())
    actions = diff(defs, _sample_tasks())
    # id=1/5/9 は実体と同一→skip。id=8 はenabled=false→対象外
    skips = [a for a in actions if a.kind == "skip"]
    assert {a.def_id for a in skips} == {1, 5, 9}


def test_create_when_new():
    """未登録エントリはcreate候補。"""
    defs = [d for d in parse_definitions(_sample_text()) if d.id == 1]
    # 実体を空にすると id=1 はcreate
    actions = diff(defs, [])
    assert len(actions) == 1
    assert actions[0].kind == "create"
    assert actions[0].def_id == 1


def test_idempotent_apply():
    """核心: 同じ入力でdiffを2回計算しても結果は同じ（create候補は安定）。"""
    defs = [d for d in parse_definitions(_sample_text()) if d.id == 1]
    tasks = []
    a1 = diff(defs, tasks)
    a2 = diff(defs, tasks)
    assert [(a.kind, a.def_id) for a in a1] == [(a.kind, a.def_id) for a in a2]
    assert a1[0].kind == "create"


def test_clean_whitelist(tmp_path):
    """clean: ホワイトリスト外のみ削除・バックアップ生成。"""
    tasks = _sample_tasks()
    defs = parse_definitions(_sample_text())
    target = tmp_path / "scheduled_tasks.json"
    target.write_text(json.dumps({"tasks": tasks}))
    removed, backup = run_clean(str(target), defs, force=True)
    # ghost-1 のみ削除される
    assert removed == 1
    assert backup.exists()


def test_clean_safety_threshold(tmp_path):
    """clean: 削除数が定義の半分超なら CleanError で停止。"""
    tasks = [
        {"cron": "0 0 * * *", "prompt": "ゴーストA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "durable": True},
        {"cron": "0 1 * * *", "prompt": "ゴーストB yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy", "durable": True},
    ]
    defs = parse_definitions(_sample_text())  # 有効定義3件→ホワイトリスト一致0→削除2件>定義半分(1)
    target = tmp_path / "scheduled_tasks.json"
    target.write_text(json.dumps({"tasks": tasks}))
    with pytest.raises(CleanError, match="半分超"):
        run_clean(str(target), defs, force=True)


def _cli(args: list[str]) -> int:
    """apply_crons.py をsubprocessで呼び出し・終了コードを返す。"""
    script = str(Path(__file__).parent.parent / "apply_crons.py")
    return subprocess.run(["python3", script] + args, capture_output=True).returncode


def test_cli_no_args_returns_2():
    """引数なしはusage表示・終了コード2。"""
    assert _cli([]) == 2


def test_cli_invalid_subcommand_returns_2():
    """不正サブコマンドは終了コード2。"""
    assert _cli(["unknown"]) == 2


# ============================================================================
# L61（2026-08-25）: ゲート自動再検証 + 発火済みone-shot誤カウント修正
# ============================================================================

_ONE_SHOT_DEFS = '''# @cron id=1 name="定期" schedule="3 3 * * 0,2,4" health="commit:obsidian-ssot:3"
#   定期: bash run.sh
# @cron id=15 name="単発" schedule="0 6 20 8 *" health="file:.claude/state/x:30" one_shot=true
#   単発: echo done
'''


def _recurring_task() -> dict:
    """id=1 定期定義と照合できる実体エントリ。"""
    return {
        "id": "aaaa1111",
        "cron": "3 3 * * 0,2,4",
        "prompt": "定期: bash run.sh\n[cron-id:1]",
        "recurring": True,
    }


def _ghost_task() -> dict:
    """どの定義とも照合不能なゴースト。"""
    return {
        "id": "gggg9999",
        "cron": "0 0 1 1 *",
        "prompt": "ゴースト zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz",
        "recurring": True,
    }


def _setup_reconcile_env(monkeypatch, tmp_path, tasks: list[dict],
                         gate_version: str, cc_version: str) -> None:
    """cmd_reconcile の実ファイル依存を tmp_path へ隔離。"""
    import apply_crons
    tasks_path = tmp_path / "scheduled_tasks.json"
    tasks_path.write_text(json.dumps({"tasks": tasks}, ensure_ascii=False), encoding="utf-8")
    gate_path = tmp_path / ".cron-cc-version"
    if gate_version is not None:
        gate_path.write_text(gate_version + "\n", encoding="utf-8")
    monkeypatch.setattr(apply_crons, "TASKS_PATH", str(tasks_path))
    monkeypatch.setattr(apply_crons, "VERSION_GATE_PATH", str(gate_path))
    monkeypatch.setattr(apply_crons, "STAMP_PATH", str(tmp_path / ".reconcile-stamp"))
    monkeypatch.setattr(apply_crons, "LOCK_PATH", str(tmp_path / ".reconcile.lock"))
    monkeypatch.setattr(apply_crons, "APPLY_LOG", str(tmp_path / "cron-apply.log"))
    monkeypatch.setattr(apply_crons, "_cc_version", lambda: cc_version)


def test_diff_fired_one_shot_is_not_create():
    """修正②: 発火済み(実体に無い)one-shot定義はcreateと数えずskip扱い。"""
    defs = parse_definitions(_ONE_SHOT_DEFS)
    actions = diff(defs, [_recurring_task()])
    kinds = {a.def_id: a.kind for a in actions}
    assert kinds == {1: "skip", 15: "skip"}, "発火済みone-shotがcreateになる誤カウント"


def test_reconcile_done_with_fired_one_shot(monkeypatch, tmp_path, capsys):
    """テスト系統1: one-shot発火済みの状態で reconcile は done（postcheck誤errorしない）。"""
    import apply_crons
    _setup_reconcile_env(monkeypatch, tmp_path, [_recurring_task()],
                         gate_version="2.0.0", cc_version="2.0.0")
    defs = parse_definitions(_ONE_SHOT_DEFS)
    rc = apply_crons.cmd_reconcile(defs)
    out = capsys.readouterr().out
    assert rc == apply_crons.EXIT_OK
    assert "[RESULT]=done" in out
    # one-shotは再登録されない（実体は定期1件のまま）
    after = json.loads((tmp_path / "scheduled_tasks.json").read_text())["tasks"]
    assert len(after) == 1
    assert "[cron-id:15]" not in json.dumps(after)


def test_reconcile_gate_auto_reverify_ok(monkeypatch, tmp_path, capsys):
    """テスト系統2: バージョン乖離+機械検証OK→ゲート自動更新+done。"""
    import apply_crons
    _setup_reconcile_env(monkeypatch, tmp_path, [_recurring_task()],
                         gate_version="1.0.0-old", cc_version="2.0.0-new")
    defs = parse_definitions(_ONE_SHOT_DEFS)
    rc = apply_crons.cmd_reconcile(defs)
    out = capsys.readouterr().out
    assert rc == apply_crons.EXIT_OK
    assert "[RESULT]=done" in out
    # ゲートが新バージョンへ自動更新されている
    gate = (tmp_path / ".cron-cc-version").read_text().strip()
    assert gate == "2.0.0-new"


def test_reconcile_gate_auto_reverify_ng(monkeypatch, tmp_path, capsys):
    """テスト系統3: バージョン乖離+機械検証NG（ghost混入）→error・ゲートは更新しない。"""
    import apply_crons
    _setup_reconcile_env(monkeypatch, tmp_path, [_recurring_task(), _ghost_task()],
                         gate_version="1.0.0-old", cc_version="2.0.0-new")
    defs = parse_definitions(_ONE_SHOT_DEFS)
    rc = apply_crons.cmd_reconcile(defs)
    out = capsys.readouterr().out
    assert rc == apply_crons.EXIT_FAIL
    assert "[RESULT]=error reason=cc-version-changed" in out
    # ゲートは旧バージョンのまま（スキーマ破壊時は停止が正）
    gate = (tmp_path / ".cron-cc-version").read_text().strip()
    assert gate == "1.0.0-old"
