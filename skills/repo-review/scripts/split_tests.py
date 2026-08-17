"""テストとソースを分離して LOC を集計する（テストが src ツリーに混在するリポジトリ用）。

使い方: python3 tmp_split_tests.py <REPO> [除外dir ...]
判定: パスに /tests/ を含む or ファイル名が test_*.py / *.test.js / *_test.go
"""
import os
import re
import sys

EXCLUDE_DEFAULT = {
    ".git", "node_modules", "vendor", ".venv", "venv", "dist", "build",
    "__pycache__", "coverage", ".mypy_cache", ".pytest_cache", ".ruff_cache",
}
CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".gs", ".go", ".rs", ".sh", ".rb"}
TEST_NAME = re.compile(r"(^test_.*|.*_test)\.(py|go|rb)$|.*\.test\.(js|ts|tsx)$|.*\.spec\.(js|ts)$")


def is_test(path: str) -> bool:
    """テストファイルか判定する。"""
    norm = path.replace(os.sep, "/")
    if "/tests/" in norm or "/test/" in norm or "/__tests__/" in norm:
        return True
    return bool(TEST_NAME.match(os.path.basename(norm)))


def main() -> None:
    """テスト/ソースの LOC とファイル数を集計して出力する。"""
    root = sys.argv[1]
    exclude = EXCLUDE_DEFAULT | set(sys.argv[2:])
    src_loc = test_loc = src_n = test_n = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude]
        for f in filenames:
            if os.path.splitext(f)[1] not in CODE_EXT:
                continue
            p = os.path.join(dirpath, f)
            try:
                with open(p, "rb") as fh:
                    n = fh.read().count(b"\n") + 1
            except OSError:
                continue
            if is_test(p):
                test_loc += n
                test_n += 1
            else:
                src_loc += n
                src_n += 1
    print(f"  source : {src_loc:>8} LOC / {src_n:>4} files")
    print(f"  tests  : {test_loc:>8} LOC / {test_n:>4} files")
    ratio = test_loc / src_loc if src_loc else 0
    print(f"  test:src = {ratio:.2f} : 1")


if __name__ == "__main__":
    main()
