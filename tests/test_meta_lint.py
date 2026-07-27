"""test_meta_lint.py — lint設定自体のメタテスト（spec §6.2・変更8）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.obsidian.meta_lint import validate_allowed_config

CONFIG = Path(__file__).parent.parent / "scripts" / "obsidian" / "frontmatter_allowed_keys.yaml"


def test_config_exists():
    assert CONFIG.exists(), f"設定ファイル不在: {CONFIG}"


def test_config_structure():
    import yaml
    d = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert isinstance(d["moc"]["files"], list), "moc.files が list でない"
    assert isinstance(d["moc"]["allowed_keys"], list), "moc.allowed_keys が list でない"
    assert isinstance(d["index"]["allowed_keys"], list), "index.allowed_keys が list でない"


def test_index_pattern_compilable():
    import re
    import yaml
    d = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    re.compile(d["index"]["pattern"])  # 無効パターンなら例外


def test_validate_allowed_config_passes():
    errors = validate_allowed_config()
    assert errors == [], f"lint設定エラー: {errors}"
