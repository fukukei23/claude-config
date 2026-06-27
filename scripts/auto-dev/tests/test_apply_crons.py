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
