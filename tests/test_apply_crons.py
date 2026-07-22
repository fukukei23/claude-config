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
