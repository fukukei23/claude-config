"""apply_crons.py のテスト。"""
import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from apply_crons import parse_definitions, CronDefinition, ParseError

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
