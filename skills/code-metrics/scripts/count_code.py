#!/usr/bin/env python3
import os
import subprocess

BASE = "/home/yn4416/projects"
REPOS = [
    "NexusCore", "atelier-kyo-manager", "reserve-optimizer", "orchestrix",
    "openclaw-stack", "claude-cost-optimizer", "pw-stealth-enhanced",
    "krotam", "mnp_manager", "tweetly", "contextforge", "ai-ceo-advisor", "sentinel-governance"
]

EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build", ".venv", "venv", ".next"}
APP_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx"}
TEST_PATTERNS = {"test_", "_test", ".test.", ".spec."}

def is_test_file(path):
    fname = os.path.basename(path)
    parts = path.split(os.sep)
    if "tests" in parts or "test" in parts:
        return True
    for p in TEST_PATTERNS:
        if p in fname:
            return True
    return False

def count_lines(filepath):
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except:
        return 0

def scan_repo(repo_path):
    app_lines = 0
    test_lines = 0
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for fname in files:
            ext = os.path.splitext(fname)[1]
            if ext not in APP_EXTS:
                continue
            fpath = os.path.join(root, fname)
            lines = count_lines(fpath)
            if is_test_file(fpath):
                test_lines += lines
            else:
                app_lines += lines
    return app_lines, test_lines

print(f"{'リポジトリ':<30} {'アプリ行数':>12} {'テスト行数':>12}")
print("-" * 56)

total_app = 0
total_test = 0

for repo in REPOS:
    path = os.path.join(BASE, repo)
    if not os.path.isdir(path):
        print(f"{repo:<30} {'(なし)':>12} {'':>12}")
        continue
    app, test = scan_repo(path)
    total_app += app
    total_test += test
    print(f"{repo:<30} {app:>12,} {test:>12,}")

print("-" * 56)
print(f"{'合計':<30} {total_app:>12,} {total_test:>12,}")
print(f"\nアプリ: {total_app/10000:.1f}万行  テスト: {total_test/10000:.1f}万行")
