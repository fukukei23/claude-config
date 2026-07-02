#!/usr/bin/env python3
import os, sys, random
from collections import defaultdict

BASE_DIR = "/home/yn4416/projects"

EXCLUDE_DIRS = {
    "mutants", "evaluation", "archive",
    ".venv", "venv", "env", ".env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".tox", "htmlcov",
    "node_modules", "dist", "build", "site-packages",
    ".eggs", "__pypackages__",
}
APP_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx"}
TEST_KEYWORDS = {"test_", "_test", ".test.", ".spec."}

def is_excluded(dirname):
    return dirname in EXCLUDE_DIRS or dirname.startswith(".")

def is_test(path):
    parts = path.split(os.sep)
    if "tests" in parts or "test" in parts:
        return True
    return any(kw in os.path.basename(path) for kw in TEST_KEYWORDS)

def count_lines(f):
    try:
        return sum(1 for _ in open(f, encoding="utf-8", errors="ignore"))
    except:
        return 0

def measure_repo(repo_path):
    dir_stats = defaultdict(lambda: {"app": 0, "test": 0, "app_f": 0, "test_f": 0})
    all_app_files = []
    all_test_files = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if not is_excluded(d)]
        rel = root.replace(repo_path, "").lstrip("/")
        top = rel.split("/")[0] if rel else "(root)"
        for fname in files:
            ext = os.path.splitext(fname)[1]
            if ext not in APP_EXTS:
                continue
            fpath = os.path.join(root, fname)
            lines = count_lines(fpath)
            size = os.path.getsize(fpath)
            if is_test(fpath):
                dir_stats[top]["test"] += lines
                dir_stats[top]["test_f"] += 1
                all_test_files.append((lines, size, fpath))
            else:
                dir_stats[top]["app"] += lines
                dir_stats[top]["app_f"] += 1
                all_app_files.append((lines, size, fpath))
    return dir_stats, all_app_files, all_test_files

repos = sys.argv[1:]
grand_app = grand_test = grand_app_f = grand_test_f = 0
all_app_sample = []
all_test_sample = []
warnings = []

for repo_name in repos:
    repo_path = os.path.join(BASE_DIR, repo_name)
    if not os.path.isdir(repo_path):
        print(f"⚠️  {repo_name}: 見つかりません")
        continue
    dir_stats, app_files, test_files = measure_repo(repo_path)
    app_total = sum(l for l,s,f in app_files)
    test_total = sum(l for l,s,f in test_files)
    app_fcount = len(app_files)
    test_fcount = len(test_files)
    print(f"\n{'='*55}")
    print(f"  {repo_name}")
    print(f"{'='*55}")
    print(f"  アプリ: {app_total:>8,}行 / {app_fcount}ファイル  (平均 {app_total//app_fcount if app_fcount else 0}行/ファイル)")
    print(f"  テスト: {test_total:>8,}行 / {test_fcount}ファイル  (平均 {test_total//test_fcount if test_fcount else 0}行/ファイル)")
    print(f"\n  ─ ディレクトリ別 ─")
    for d, s in sorted(dir_stats.items()):
        if s["app"] + s["test"] > 0:
            print(f"  {d:<22} APP {s['app']:>7,}行({s['app_f']}F)  TEST {s['test']:>7,}行({s['test_f']}F)")
    for lines, size, fpath in sorted(app_files + test_files, reverse=True)[:5]:
        bytes_per_line = size / lines if lines > 0 else 0
        rel = fpath.replace(repo_path, "")
        if lines > 10000:
            warnings.append(f"⚠️  {repo_name}{rel}: {lines:,}行（10,000行超）")
        if bytes_per_line > 200 or bytes_per_line < 5:
            warnings.append(f"⚠️  {repo_name}{rel}: {bytes_per_line:.0f}バイト/行（異常値）")
    grand_app += app_total
    grand_test += test_total
    grand_app_f += app_fcount
    grand_test_f += test_fcount
    all_app_sample.extend(app_files)
    all_test_sample.extend(test_files)

print(f"\n{'='*55}")
print(f"  合計")
print(f"{'='*55}")
print(f"  アプリコード: {grand_app:>8,}行 ({grand_app/10000:.2f}万行) / {grand_app_f}ファイル")
print(f"  テストコード: {grand_test:>8,}行 ({grand_test/10000:.2f}万行) / {grand_test_f}ファイル")

if warnings:
    print(f"\n{'─'*55}")
    print("  【要確認】異常値")
    for w in warnings:
        print(f"  {w}")

print(f"\n{'─'*55}")
print("  【検証 Layer1】ランダムサンプル")
sample_pool = all_app_sample + all_test_sample
if len(sample_pool) >= 3:
    samples = random.sample(sample_pool, 3)
    for lines, size, fpath in samples:
        print(f"\n  📄 {fpath.replace(BASE_DIR, '')} ({lines:,}行)")
        try:
            with open(fpath, encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f):
                    if i >= 5: break
                    print(f"     {i+1}: {line.rstrip()}")
        except:
            print("     (読み取り失敗)")

print(f"\n{'─'*55}")
print("  【検証 Layer2】最大ファイルのバイト整合性")
if all_app_sample:
    largest = max(all_app_sample, key=lambda x: x[0])
    lines, size, fpath = largest
    bpl = size / lines if lines > 0 else 0
    status = "✅ 正常" if 10 <= bpl <= 500 else "⚠️ 要確認"
    print(f"  最大ファイル: {fpath.replace(BASE_DIR, '')} ({lines:,}行, {size:,}バイト)")
    print(f"  1行あたり {bpl:.1f}バイト → {status}")
print()
