"""path-rewrite.py の置換ロジックに対するテスト"""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "path_rewrite", Path(__file__).parent / "path-rewrite.py"
)
_path_rewrite = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_path_rewrite)
rewrite_command = _path_rewrite.rewrite_command


def test_tilde_projects_prefix_is_rewritten() -> None:
    result = rewrite_command("ls ~/projects/obsidian-ssot")
    assert result == "ls //wsl.localhost/Ubuntu/home/yn4416/projects/obsidian-ssot"


def test_tilde_claude_prefix_is_rewritten() -> None:
    result = rewrite_command("cat ~/.claude/CLAUDE.md")
    assert result == "cat //wsl.localhost/Ubuntu/home/yn4416/.claude/CLAUDE.md"


def test_absolute_home_projects_prefix_is_rewritten() -> None:
    result = rewrite_command("cat /home/yn4416/projects/obsidian-ssot/00_SYSTEM/バックログ.md")
    assert result == "cat //wsl.localhost/Ubuntu/home/yn4416/projects/obsidian-ssot/00_SYSTEM/バックログ.md"


def test_absolute_home_claude_prefix_is_rewritten() -> None:
    result = rewrite_command("cat /home/yn4416/.claude/settings.json")
    assert result == "cat //wsl.localhost/Ubuntu/home/yn4416/.claude/settings.json"


def test_unrelated_tilde_is_not_rewritten() -> None:
    assert rewrite_command("echo ~") is None
    assert rewrite_command("ls ~/Desktop") is None


def test_command_without_tilde_or_home_is_not_rewritten() -> None:
    assert rewrite_command("git status") is None


def test_multiple_prefixes_in_one_command_are_all_rewritten() -> None:
    result = rewrite_command("diff ~/projects/a.md ~/.claude/CLAUDE.md")
    assert result == (
        "diff //wsl.localhost/Ubuntu/home/yn4416/projects/a.md "
        "//wsl.localhost/Ubuntu/home/yn4416/.claude/CLAUDE.md"
    )
