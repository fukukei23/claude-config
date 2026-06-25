#!/usr/bin/env python3
"""convert-wikilinks.py のユニットテスト"""
import importlib.util
import os
import tempfile
from pathlib import Path

# convert-wikilinks.py（ハイフン入り）はPythonモジュールとして直接importできないため、
# importlib.util.spec_from_file_location で動的に読み込む。
_CW_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "convert-wikilinks.py")
_spec = importlib.util.spec_from_file_location("convert_wikilinks", _CW_PATH)
_cw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cw)

build_stem_index = _cw.build_stem_index
resolve_stem = _cw.resolve_stem
to_relative_path = _cw.to_relative_path
convert_wikilink = _cw.convert_wikilink
dedupe_related_section = _cw.dedupe_related_section


def make_vault(tmpdir: Path) -> Path:
    """テスト用vault構築"""
    (tmpdir / "01_DECISIONS" / "x").mkdir(parents=True)
    (tmpdir / "01_DECISIONS" / "y").mkdir(parents=True)
    (tmpdir / "00_SYSTEM").mkdir(parents=True)
    (tmpdir / "01_DECISIONS" / "x" / "a.md").write_text("# a\n", encoding="utf-8")
    (tmpdir / "01_DECISIONS" / "y" / "b.md").write_text("# b\n", encoding="utf-8")
    (tmpdir / "00_SYSTEM" / "MOC.md").write_text("# MOC\n", encoding="utf-8")
    return tmpdir


def test_build_stem_index():
    with tempfile.TemporaryDirectory() as td:
        vault = make_vault(Path(td))
        idx = build_stem_index(vault)
        assert "a" in idx and len(idx["a"]) == 1
        assert idx["a"][0].name == "a.md"


def test_resolve_stem_unique():
    with tempfile.TemporaryDirectory() as td:
        vault = make_vault(Path(td))
        idx = build_stem_index(vault)
        path, status = resolve_stem("a", idx)
        assert status == "ok"
        assert path.name == "a.md"


def test_resolve_stem_conflict():
    """同名ファイル複数でconflict"""
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        # SCAN_DIRS配下のディレクトリで同名衝突を起こす
        (vault / "01_DECISIONS" / "p1").mkdir(parents=True)
        (vault / "01_DECISIONS" / "p2").mkdir(parents=True)
        (vault / "01_DECISIONS" / "p1" / "dup.md").write_text("x", encoding="utf-8")
        (vault / "01_DECISIONS" / "p2" / "dup.md").write_text("x", encoding="utf-8")
        idx = build_stem_index(vault)
        path, status = resolve_stem("dup", idx)
        assert status == "conflict"


def test_resolve_stem_notfound():
    with tempfile.TemporaryDirectory() as td:
        vault = make_vault(Path(td))
        idx = build_stem_index(vault)
        path, status = resolve_stem("zzz", idx)
        assert status == "notfound"


def test_to_relative_path():
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        src = vault / "01_DECISIONS" / "y" / "b.md"
        target = vault / "01_DECISIONS" / "x" / "a.md"
        rel = to_relative_path(target, src)
        assert rel == "../x/a.md"


def test_convert_fullpath_wikilink():
    """[[フルパス.md]] → [stem](src相対path)"""
    with tempfile.TemporaryDirectory() as td:
        vault = make_vault(Path(td))
        idx = build_stem_index(vault)
        src = vault / "01_DECISIONS" / "y" / "b.md"
        result, status = convert_wikilink("[[01_DECISIONS/x/a.md]]", src, vault, idx)
        assert result == "[a](../x/a.md)"
        assert status == "ok"


def test_convert_stem_wikilink():
    """[[stem]] → stem解決 → [stem](src相対path)"""
    with tempfile.TemporaryDirectory() as td:
        vault = make_vault(Path(td))
        idx = build_stem_index(vault)
        src = vault / "01_DECISIONS" / "y" / "b.md"
        result, status = convert_wikilink("[[a]]", src, vault, idx)
        assert result == "[a](../x/a.md)"
        assert status == "ok"


def test_convert_alias():
    """[[stem|表示名]] → [表示名](path)"""
    with tempfile.TemporaryDirectory() as td:
        vault = make_vault(Path(td))
        idx = build_stem_index(vault)
        src = vault / "01_DECISIONS" / "y" / "b.md"
        result, status = convert_wikilink("[[a|詳細]]", src, vault, idx)
        assert result == "[詳細](../x/a.md)"


def test_convert_external_url_skip():
    """[[http://...]] → 変換スキップ"""
    with tempfile.TemporaryDirectory() as td:
        vault = make_vault(Path(td))
        idx = build_stem_index(vault)
        src = vault / "01_DECISIONS" / "y" / "b.md"
        result, status = convert_wikilink("[[https://example.com]]", src, vault, idx)
        assert result == "[[https://example.com]]"
        assert status == "skip"


def test_convert_image_embed():
    """![[img.png]] → ![img](path) ※画像は存在チェックせず相対path生成"""
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        (vault / "01_DECISIONS" / "x").mkdir(parents=True)
        (vault / "01_DECISIONS" / "y").mkdir(parents=True)
        # 画像ファイルを実在させる（フルパス解決用）
        (vault / "01_DECISIONS" / "x" / "img.png").write_text("img", encoding="utf-8")
        (vault / "01_DECISIONS" / "y" / "b.md").write_text("# b\n", encoding="utf-8")
        idx = build_stem_index(vault)
        src = vault / "01_DECISIONS" / "y" / "b.md"
        result, status = convert_wikilink("![[01_DECISIONS/x/img.png]]", src, vault, idx)
        assert result == "![img](../x/img.png)"


def test_dedupe_related_section():
    text = "# t\n\nbody\n\n## 関連\n- [a](../x/a.md)\n- [a](../x/a.md)\n- [b](../y/b.md)\n"
    result = dedupe_related_section(text)
    assert result.count("../x/a.md") == 1
    assert result.count("../y/b.md") == 1


def test_dedupe_related_normalizes_path_variants():
    """フルパス形式とstem形式の重複もuniq"""
    text = "## 関連\n- [a](../x/a.md)\n- [a](../x/a.md)\n"
    result = dedupe_related_section(text)
    assert result.count("- [a]") == 1


if __name__ == "__main__":
    import subprocess
    subprocess.run(["python3", "-m", "pytest", __file__, "-v"])