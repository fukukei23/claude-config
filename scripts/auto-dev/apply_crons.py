#!/usr/bin/env python3
"""apply-crons — Cron定義↔実体の冪等同期・健康診断。

定義源: ~/bin/renew-crons.sh の # @cron タグ書式
実体: ~/.claude/scheduled_tasks.json
"""
from __future__ import annotations

import glob as _glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass as _dc
from dataclasses import field
from enum import Enum
from pathlib import Path
from typing import Iterable


class ParseError(Exception):
    """定義ファイルの書式エラー。"""


@_dc
class CronDefinition:
    """1件のCron定義。"""
    id: int
    name: str
    schedule: str
    health: str
    prompt: str
    enabled: bool = True


_TAG_RE = re.compile(
    r'^#\s*@cron\s+'
    r'id=(?P<id>\d+)\s+'
    r'name="(?P<name>[^"]*)"\s+'
    r'schedule="(?P<schedule>[^"]*)"\s+'
    r'health="(?P<health>[^"]*)"'
    r'(?:\s+enabled=(?P<enabled>true|false))?'
    r'\s*$'
)

_PROMPT_PREFIX_RE = re.compile(r'^#\s{2,}(.*)$')


def parse_definitions(text: str) -> list[CronDefinition]:
    """renew-crons.sh のテキストをparseし、CronDefinitionリストを返す。

    Args:
        text: renew-crons.sh の全文。

    Returns:
        CronDefinition のリスト（enabled=false含む）。

    Raises:
        ParseError: id重複・schedule5フィールド違反・promptブロックなし。
    """
    lines = text.splitlines()
    defs: list[CronDefinition] = []
    seen_ids: set[int] = set()
    current: CronDefinition | None = None
    prompt_lines: list[str] = []

    def _flush() -> None:
        nonlocal current, prompt_lines
        if current is not None:
            if not prompt_lines:
                raise ParseError(f"id={current.id}: promptブロックがありません")
            current.prompt = "\n".join(prompt_lines)
            defs.append(current)
            current = None
            prompt_lines = []

    for line in lines:
        tag = _TAG_RE.match(line)
        if tag:
            _flush()
            cid = int(tag.group("id"))
            if cid in seen_ids:
                raise ParseError(f"id={cid}: 重複しています")
            seen_ids.add(cid)
            schedule = tag.group("schedule")
            if len(schedule.split()) != 5:
                raise ParseError(f"id={cid}: scheduleは5フィールド({schedule})")
            enabled = tag.group("enabled") != "false"
            current = CronDefinition(
                id=cid,
                name=tag.group("name"),
                schedule=schedule,
                health=tag.group("health"),
                prompt="",
                enabled=enabled,
            )
        elif current is not None:
            pm = _PROMPT_PREFIX_RE.match(line)
            if pm:
                prompt_lines.append(pm.group(1))
            elif line.strip() == "" and prompt_lines:
                _flush()
    _flush()
    return defs


class HealthStatus(Enum):
    OK = "✅"
    STALE = "⚠️"
    UNKNOWN = "❓"


@_dc
class HealthResult:
    status: HealthStatus
    detail: str


def _last_commit_days(repo: str) -> float:
    """repo の最終commit日時を「現在からの経過日数」で返す（失敗時 大きな値）。"""
    path = os.path.expanduser(f"~/projects/{repo}")
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%ct"],
            cwd=path, capture_output=True, text=True, check=True,
        ).stdout.strip()
        age_sec = time.time() - float(out)
        return age_sec / 86400.0
    except Exception:
        return 1e9


def probe_commit(repo: str, max_days: int) -> HealthResult:
    """commit型: repoの最終commitが max_days 日以内ならOK。"""
    days = _last_commit_days(repo)
    if days <= max_days:
        return HealthResult(HealthStatus.OK, f"最終commit {days:.1f}日前")
    return HealthResult(HealthStatus.STALE, f"最終commit {days:.1f}日前（閾値{max_days}日超過）")


def probe_file(pattern: str, max_days: int) -> HealthResult:
    """file型: glob最新ファイルのmtimeが max_days 日以内ならOK。"""
    expanded = os.path.expanduser(pattern)
    files = sorted(_glob.glob(expanded), key=os.path.getmtime, reverse=True)
    if not files:
        return HealthResult(HealthStatus.STALE, f"該当ファイルなし({pattern})")
    age_sec = time.time() - os.path.getmtime(files[0])
    days = age_sec / 86400.0
    if days <= max_days:
        return HealthResult(HealthStatus.OK, f"最新 {os.path.basename(files[0])} ({days:.1f}日前)")
    return HealthResult(HealthStatus.STALE, f"最新 {days:.1f}日前（閾値{max_days}日超過）")


def probe_log(path: str, max_hours: int) -> HealthResult:
    """log型: ファイルmtimeが max_hours 時間以内ならOK。"""
    expanded = os.path.expanduser(path)
    if not os.path.exists(expanded):
        return HealthResult(HealthStatus.STALE, f"ログ不在({path})")
    age_sec = time.time() - os.path.getmtime(expanded)
    hours = age_sec / 3600.0
    if hours <= max_hours:
        return HealthResult(HealthStatus.OK, f"最終更新 {hours:.1f}時間前")
    return HealthResult(HealthStatus.STALE, f"最終更新 {hours:.1f}時間前（閾値{max_hours}h超過）")


def run_health(probe: str) -> HealthResult:
    """health プローブ文字列（type:args:threshold）を判定。"""
    parts = probe.split(":")
    kind = parts[0]
    try:
        if kind == "commit":
            return probe_commit(parts[1], int(parts[2]))
        if kind == "file":
            return probe_file(parts[1], int(parts[2]))
        if kind == "log":
            return probe_log(parts[1], int(parts[2]))
    except (IndexError, ValueError):
        return HealthResult(HealthStatus.UNKNOWN, f"プローブ書式不正({probe})")
    return HealthResult(HealthStatus.UNKNOWN, f"未対応プローブ({kind})")


TASKS_PATH = os.path.expanduser("~/.claude/scheduled_tasks.json")


@_dc
class Action:
    """1件の同期アクション。"""
    kind: str  # "create" | "skip"
    def_id: int
    name: str = ""
    schedule: str = ""
    prompt: str = ""
    reason: str = ""


def load_tasks(path: str = TASKS_PATH) -> list[dict]:
    """scheduled_tasks.json から durable タスクを読込。"""
    try:
        with open(path) as f:
            return [t for t in json.load(f).get("tasks", []) if t.get("durable")]
    except FileNotFoundError:
        return []


def _match(defn: CronDefinition, task: dict) -> bool:
    """同一判定: schedule完全一致 + prompt先頭40字一致。"""
    if defn.schedule != task.get("cron"):
        return False
    return defn.prompt.strip()[:40] == (task.get("prompt") or "")[:40]


def diff(definitions: list[CronDefinition], tasks: list[dict]) -> list[Action]:
    """定義↔実体を突合し、ACTIONリストを返す（create/skipのみ・削除はclean）。"""
    actions: list[Action] = []
    for defn in definitions:
        if not defn.enabled:
            continue
        matched = next((t for t in tasks if _match(defn, t)), None)
        if matched:
            actions.append(Action(kind="skip", def_id=defn.id, name=defn.name, reason="既存同一"))
        else:
            actions.append(Action(kind="create", def_id=defn.id, name=defn.name,
                                  schedule=defn.schedule, prompt=defn.prompt))
    return actions


def format_protocol(actions: list[Action]) -> str:
    """CronCreate協調プロトコル行を生成。"""
    lines = ["=== CRON_APPLY_PROTOCOL_START ==="]
    creates = 0
    skips = 0
    for a in actions:
        if a.kind == "skip":
            lines.append(f'ACTION: skip  id={a.def_id}  reason="{a.reason}"')
            skips += 1
        else:
            lines.append(f'ACTION: create  id={a.def_id}  name="{a.name}"  schedule="{a.schedule}"  durable=true')
            lines.append(f"  PROMPT: {a.prompt.strip()}")
            creates += 1
    lines.append("=== CRON_APPLY_PROTOCOL_END ===")
    lines.append(f"要約: 追加{creates}件・スキップ{skips}件（削除は clean サブコマンドへ）")
    return "\n".join(lines)


class CleanError(Exception):
    """clean操作の安全停止。"""


def run_clean(tasks_path: str, definitions: list[CronDefinition], force: bool = False) -> tuple[int, Path | None]:
    """scheduled_tasks.json のホワイトリスト方式削除。

    定義に一致しない durable エントリを削除。
    戻り値: (削除件数, バックアップファイルPath・削除0件時はNone)。
    """
    tasks_path_obj = Path(tasks_path)
    if not tasks_path_obj.exists():
        raise FileNotFoundError(f"タスクファイル不在: {tasks_path}")
    try:
        with open(tasks_path_obj) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON破損: {tasks_path}: {e}") from e
    tasks = [t for t in data.get("tasks", []) if t.get("durable")]
    enabled = [d for d in definitions if d.enabled]

    keep = []
    remove = []
    for t in tasks:
        if any(_match(d, t) for d in enabled):
            keep.append(t)
        else:
            remove.append(t)

    # 安全閾値: 削除数が有効定義数の半分超なら異常停止
    if enabled and len(remove) > len(enabled) / 2:
        raise CleanError(
            f"削除候補{len(remove)}件が定義{len(enabled)}件の半分超。異常の疑いで停止"
        )

    if not force:
        print(f"削除候補 {len(remove)}件: {[t.get('prompt','')[:30] for t in remove]}")
        ans = input("実行しますか? (y/N): ").strip().lower()
        if ans != "y":
            return 0, None

    backup = tasks_path_obj.with_suffix(f".json.bak.{int(time.time())}")
    shutil.copy2(tasks_path_obj, backup)
    data["tasks"] = keep
    with open(tasks_path_obj, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return len(remove), backup


# ============================================================================
# CLI (Step 1: 追記)
# ============================================================================

AUTO_DEV_DIR = os.path.expanduser("~/projects/claude-config/scripts/auto-dev")
APPLY_LOG = os.path.join(AUTO_DEV_DIR, "cron-apply.log")
HEALTH_LOG = os.path.join(AUTO_DEV_DIR, "cron-health.log")


def _log(path: str, line: str) -> None:
    """ログファイルに時刻付きで追記。"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")
    except OSError as e:
        print(f"WARNING: ログ書き込み失敗 {path}: {e}", file=sys.stderr)


def cmd_check(definitions: list[CronDefinition]) -> int:
    """checkサブコマンド: 突合 + 健康診断 + ログ。"""
    tasks = load_tasks()
    actions = diff(definitions, tasks)
    enabled = [d for d in definitions if d.enabled]
    create_n = sum(1 for a in actions if a.kind == "create")
    ghost_n = len([t for t in tasks if not any(_match(d, t) for d in enabled)])

    print("=== Cron 突合 ===")
    print(f"定義: {len(enabled)}件 / 登録: {len(tasks)}件 / 欠落(create): {create_n} / 不要(ghost): {ghost_n}")
    print()
    print("=== 健康診断 ===")
    warnings = []
    for d in enabled:
        r = run_health(d.health)
        print(f"#{d.id} {d.name:<20} {r.status.value} {r.detail}")
        if r.status == HealthStatus.STALE:
            warnings.append(f"#{d.id} {d.name}")
    print()
    print("=== サマリ ===")
    _log(HEALTH_LOG, f"check 定義{len(enabled)}/登録{len(tasks)}/create{create_n}/ghost{ghost_n} 警告:{','.join(warnings) or 'なし'}")
    if create_n or ghost_n:
        print(f"整合: ⚠️ create{create_n}/ghost{ghost_n}")
        return 1
    if warnings:
        print(f"整合: ✅ / 要対応: {', '.join(warnings)}（別タスク参照）")
        return 0
    print("整合: ✅")
    return 0


def cmd_apply(definitions: list[CronDefinition]) -> int:
    """applyサブコマンド: プロトコル出力 + ログ。"""
    tasks = load_tasks()
    actions = diff(definitions, tasks)
    print(format_protocol(actions))
    creates = sum(1 for a in actions if a.kind == "create")
    skips = sum(1 for a in actions if a.kind == "skip")
    _log(APPLY_LOG, f"apply create={creates} skip={skips}")
    return 0


def main(argv: list[str]) -> int:
    """CLIエントリポイント。"""
    if len(argv) < 2 or argv[1] not in {"check", "diff", "apply", "clean"}:
        print("usage: apply-crons.sh {check|diff|apply|clean} [--force]", file=sys.stderr)
        return 2

    defs_path = os.path.expanduser("~/bin/renew-crons.sh")
    try:
        definitions = parse_definitions(Path(defs_path).read_text())
    except ParseError as e:
        print(f"ParseError: {e}", file=sys.stderr)
        return 2

    sub = argv[1]
    if sub == "check":
        return cmd_check(definitions)
    if sub == "diff":
        tasks = load_tasks()
        for a in diff(definitions, tasks):
            print(f"{a.kind:6} id={a.def_id} {a.name} {a.reason}")
        return 0
    if sub == "apply":
        return cmd_apply(definitions)
    if sub == "clean":
        force = "--force" in argv
        try:
            removed, backup = run_clean(TASKS_PATH, definitions, force=force)
            print(f"削除: {removed}件 / バックアップ: {backup}")
            _log(APPLY_LOG, f"clean removed={removed} backup={backup}")
            return 0
        except CleanError as e:
            print(f"CleanError: {e}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

