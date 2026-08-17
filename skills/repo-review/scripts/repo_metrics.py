#!/usr/bin/env python3
"""リポジトリ計測スクリプト（言語非依存の骨格 + Python AST 詳細）。

使い方: python3 tmp_repo_metrics.py <REPO_PATH> [追加除外dir ...]
出力: スタック判定 / 拡張子別LOC / ディレクトリ別LOC / Python複雑度 / カバレッジ所在
"""
from __future__ import annotations

import ast
import os
import sys
from collections import Counter
from datetime import datetime

DEFAULT_EXCLUDE = {
    ".git", "node_modules", "vendor", ".venv", "venv", "dist", "build", "target",
    "__pycache__", ".next", "coverage", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "htmlcov", ".gradio", "mutants", "site-packages", ".terraform",
}
CODE_EXT = {
    ".py": "Python", ".js": "JS", ".ts": "TS", ".tsx": "TS", ".jsx": "JS",
    ".gs": "GAS", ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".java": "Java",
    ".sh": "Shell", ".bash": "Shell", ".ps1": "PowerShell", ".sql": "SQL",
    ".md": "Markdown", ".html": "HTML", ".css": "CSS", ".yml": "YAML", ".yaml": "YAML",
}
STACK_MARKERS = {
    "pyproject.toml": "Python(pyproject)", "requirements.txt": "Python(requirements)",
    "package.json": "Node/JS-TS", "go.mod": "Go", "Cargo.toml": "Rust",
    "pom.xml": "Java(maven)", "Gemfile": "Ruby", "composer.json": "PHP",
    "appsscript.json": "Google Apps Script", ".clasp.json": "GAS(clasp)",
    "Dockerfile": "Docker", "docker-compose.yml": "Docker Compose",
}
COVERAGE_FILES = ["coverage.xml", "lcov.info", "coverage.out", ".coverage",
                  "coverage-final.json", "clover.xml"]
BRANCH_NODES = (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.BoolOp,
                ast.IfExp, ast.ExceptHandler, ast.Assert, ast.comprehension)


def walk(root: str, extra_exclude: set[str]):
    """除外ディレクトリを飛ばしてファイルパスを列挙する。"""
    exclude = DEFAULT_EXCLUDE | extra_exclude
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude]
        for f in filenames:
            yield os.path.join(dirpath, f)


def count_lines(path: str) -> int:
    """ファイルの行数を返す（読めなければ0）。"""
    try:
        with open(path, "rb") as fh:
            return fh.read().count(b"\n") + 1
    except OSError:
        return 0


def analyze_python(files: list[str]) -> dict:
    """Python ファイル群の複雑度・関数長・docstring率を集計する。"""
    funcs, nodoc, total = [], 0, 0
    for p in files:
        try:
            tree = ast.parse(open(p, encoding="utf-8", errors="ignore").read())
        except (SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                total += 1
                cc = 1 + sum(1 for x in ast.walk(node) if isinstance(x, BRANCH_NODES))
                length = (node.end_lineno or node.lineno) - node.lineno
                funcs.append((cc, length, f"{p}:{node.lineno} {node.name}"))
                if not ast.get_docstring(node) and not node.name.startswith("_"):
                    nodoc += 1
    funcs.sort(reverse=True)
    return {"total": total, "nodoc": nodoc, "funcs": funcs}


def main() -> None:
    """計測を実行して標準出力にレポートする。"""
    root = sys.argv[1]
    extra = set(sys.argv[2:])
    print(f"### REPO: {root}")

    print("\n--- スタック判定 ---")
    for marker, name in STACK_MARKERS.items():
        if os.path.exists(os.path.join(root, marker)):
            print(f"  {marker:24} -> {name}")

    files = list(walk(root, extra))
    by_ext, by_dir = Counter(), Counter()
    py_files = []
    for p in files:
        ext = os.path.splitext(p)[1].lower()
        if ext not in CODE_EXT:
            continue
        n = count_lines(p)
        by_ext[CODE_EXT[ext]] += n
        rel = os.path.relpath(p, root).replace(os.sep, "/")
        by_dir[rel.split("/")[0] if "/" in rel else "(root)"] += n
        if ext == ".py":
            py_files.append(p)

    print("\n--- 言語別LOC ---")
    for lang, n in by_ext.most_common():
        print(f"  {lang:12} {n:>8}")

    print("\n--- トップレベルdir別LOC(上位15) ---")
    for d, n in by_dir.most_common(15):
        print(f"  {d:28} {n:>8}")

    print("\n--- カバレッジレポートの所在と鮮度 ---")
    found = False
    for p in files:
        if os.path.basename(p) in COVERAGE_FILES:
            mt = datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M")
            print(f"  {os.path.relpath(p, root)}  (更新: {mt})")
            found = True
    if not found:
        print("  なし（カバレッジ未計測 or レポート未コミット）")

    if py_files:
        r = analyze_python(py_files)
        t = r["total"] or 1
        print(f"\n--- Python複雑度 (関数{r['total']}個) ---")
        print(f"  public docstring欠落: {r['nodoc']} ({r['nodoc'] / t * 100:.0f}%)")
        print(f"  CC>10: {sum(1 for f in r['funcs'] if f[0] > 10)}  "
              f"CC>20: {sum(1 for f in r['funcs'] if f[0] > 20)}")
        print("  --- 最も複雑な関数 上位8 ---")
        for cc, ln, s in r["funcs"][:8]:
            print(f"   CC={cc:3} len={ln:3}  {os.path.relpath(s.split(':')[0], root)}"
                  f":{':'.join(s.split(':')[1:])}")


if __name__ == "__main__":
    main()
