#!/usr/bin/env python3
"""
NexusCoreのコード行数を徹底的に内訳付きで計測する。
除外対象・含有対象を明示する。
"""
import os
from collections import defaultdict

BASE = "/home/yn4416/projects/NexusCore"

# 除外するディレクトリ名（完全一致）
EXCLUDE_DIRS = {
    "node_modules", ".git", "__pycache__", "dist", "build",
    ".venv", "venv", "env", ".env", ".tox", ".mypy_cache",
    ".pytest_cache", "htmlcov", ".coverage", "site-packages",
    ".eggs", "*.egg-info", "__pypackages__"
}

# 対象拡張子
APP_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx"}
TEST_KEYWORDS = {"test_", "_test", ".test.", ".spec."}

def is_excluded_dir(dirname):
    return dirname in EXCLUDE_DIRS or dirname.startswith(".")

def is_test_path(path):
    parts = path.replace(BASE, "").split(os.sep)
    if "tests" in parts or "test" in parts:
        return True
    fname = os.path.basename(path)
    return any(kw in fname for kw in TEST_KEYWORDS)

def count_lines(filepath):
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except:
        return 0

# ディレクトリ別集計
dir_stats = defaultdict(lambda: {"files": 0, "lines": 0, "type": ""})
app_files = []
test_files = []
excluded_paths = []

for root, dirs, files in os.walk(BASE):
    # 除外チェック
    dirs[:] = [d for d in dirs if not is_excluded_dir(d)]

    rel_root = root.replace(BASE, "").lstrip("/") or "."

    for fname in files:
        ext = os.path.splitext(fname)[1]
        if ext not in APP_EXTS:
            continue
        fpath = os.path.join(root, fname)
        lines = count_lines(fpath)
        is_test = is_test_path(fpath)

        top_dir = rel_root.split("/")[0] if "/" in rel_root else rel_root

        if is_test:
            test_files.append((lines, rel_root, fname))
            dir_stats[f"[TEST] {top_dir}"]["files"] += 1
            dir_stats[f"[TEST] {top_dir}"]["lines"] += lines
        else:
            app_files.append((lines, rel_root, fname))
            dir_stats[f"[APP]  {top_dir}"]["files"] += 1
            dir_stats[f"[APP]  {top_dir}"]["lines"] += lines

total_app = sum(l for l, _, _ in app_files)
total_test = sum(l for l, _, _ in test_files)

print(f"{'='*60}")
print(f"NexusCore コード行数 詳細内訳")
print(f"{'='*60}")
print(f"\n計測対象パス: {BASE}")
print(f"除外ディレクトリ: {', '.join(sorted(EXCLUDE_DIRS))}")
print(f"対象拡張子: {', '.join(sorted(APP_EXTS))}")

print(f"\n{'─'*60}")
print(f"【ディレクトリ別集計】")
print(f"{'─'*60}")
for d, stat in sorted(dir_stats.items()):
    print(f"  {d:<35} {stat['files']:>5}ファイル  {stat['lines']:>8,}行")

print(f"\n{'─'*60}")
print(f"【サマリー】")
print(f"{'─'*60}")
print(f"  アプリコード: {len(app_files):>5}ファイル  {total_app:>8,}行  ({total_app/10000:.1f}万行)")
print(f"  テストコード: {len(test_files):>5}ファイル  {total_test:>8,}行  ({total_test/10000:.1f}万行)")

print(f"\n【アプリコード TOP20 大きいファイル】")
for lines, d, f in sorted(app_files, reverse=True)[:20]:
    print(f"  {lines:>6,}行  {d}/{f}")

print(f"\n【テストコード TOP10 大きいファイル】")
for lines, d, f in sorted(test_files, reverse=True)[:10]:
    print(f"  {lines:>6,}行  {d}/{f}")

# 除外確認
print(f"\n【除外されたディレクトリ確認】")
all_top_dirs = set()
for root, dirs, files in os.walk(BASE):
    rel = root.replace(BASE, "").lstrip("/")
    top = rel.split("/")[0] if rel else "."
    all_top_dirs.add(top)
    break  # 1レベルだけ

import os as _os
top_level = [d for d in _os.listdir(BASE) if _os.path.isdir(_os.path.join(BASE, d))]
excluded_found = [d for d in top_level if is_excluded_dir(d)]
included_found = [d for d in top_level if not is_excluded_dir(d)]
print(f"  トップレベルディレクトリ数: {len(top_level)}")
print(f"  除外済み: {excluded_found}")
print(f"  計測対象: {included_found}")
