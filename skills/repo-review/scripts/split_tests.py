"""テストとソースを分離して LOC を集計する（テストが src ツリーに混在するリポジトリ用）。

使い方: python3 split_tests.py <REPO> [除外dir ...（ベース名 or パス指定）]
判定: パスに /tests/ を含む or テスト命名（test_*.py / *_test.go / *.test.tsx / *Test.java 等）
除外・拡張子は _shared.py の単一ソースから import する（critical 2-2・個別定義禁止）。
"""
import os
import re
import sys

from _shared import CODE_EXT, RATIO_EXCLUDED_EXT, prune_dirnames

# test:src 比の対象拡張子（CODE_EXT からドキュメント/マークアップ/設定形式を除いた派生・単一ソース維持）
RATIO_CODE_EXT = set(CODE_EXT) - RATIO_EXCLUDED_EXT

# high 3-1: .spec.tsx / .test.jsx / Test.java 追加
TEST_NAME = re.compile(
    r"(^test_.*|.*_test)\.(py|go|rb)$"
    r"|.*\.test\.(js|ts|tsx|jsx)$"
    r"|.*\.spec\.(js|ts|tsx|jsx)$"
    r"|.*Test\.java$"
)


def is_test(path: str) -> bool:
    """テストファイルか判定する。"""
    norm = path.replace(os.sep, "/")
    if "/tests/" in norm or "/test/" in norm or "/__tests__/" in norm:
        return True
    return bool(TEST_NAME.match(os.path.basename(norm)))


def main() -> None:
    """テスト/ソースの LOC とファイル数を集計して出力する。"""
    root = sys.argv[1]
    exclude = set(sys.argv[2:])
    src_loc = test_loc = src_n = test_n = 0
    for dirpath, dirnames, filenames in os.walk(root):
        prune_dirnames(dirnames, dirpath, root, exclude)
        for f in filenames:
            if os.path.splitext(f)[1] not in RATIO_CODE_EXT:
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
