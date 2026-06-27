#!/usr/bin/env python3
"""apply-crons — Cron定義↔実体の冪等同期・健康診断。

定義源: ~/bin/renew-crons.sh の # @cron タグ書式
実体: ~/.claude/scheduled_tasks.json
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable


class ParseError(Exception):
    """定義ファイルの書式エラー。"""


@dataclass
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
