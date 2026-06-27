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
import subprocess
import time
from dataclasses import dataclass as _dc
from dataclasses import field
from enum import Enum
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

