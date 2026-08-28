#!/usr/bin/env python3
"""paths-json-update.py — active-sessions-paths.json の安全な更新ヘルパー(v3・2026-08-29)

使い方:
  paths-json-update.py <tab_id> <path> [<path>...]   # 宣言path追記(重複回避)
  paths-json-update.py <tab_id> --remove             # タブエントリ削除
  paths-json-update.py <tab_id> --set <path>...      # エントリを置換

設計(revised_proposal_v3_final.md §5,§9):
- rename原子性主体: tmp書込 → os.replace(アトミック)・flockは補助(NFS/コンテナでは
  機能しない既知制限・$HOME配下ローカル配置限定)
- 世代バックアップ: paths.json.bak.<N> を10世代rotate
- 既存entries保持・git pathspec互換の絶対path正規化(~展開+realpath)
"""
import json
import os
import sys
import time

STATE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "state")
PATHS_JSON = os.environ.get("PATHS_JSON_FILE") or os.path.join(
    STATE_DIR, "active-sessions-paths.json")
LOCK_FILE = PATHS_JSON + ".lock"
MAX_BACKUPS = 10


def norm(p: str) -> str:
    return os.path.realpath(os.path.abspath(os.path.expanduser(p)))


def rotate_backup() -> None:
    """既存ファイルを10世代rotate(最古を削除)。"""
    if not os.path.exists(PATHS_JSON):
        return
    for i in range(MAX_BACKUPS - 1, 0, -1):
        src = f"{PATHS_JSON}.bak.{i}"
        dst = f"{PATHS_JSON}.bak.{i + 1}"
        if os.path.exists(src):
            os.replace(src, dst)
    os.replace(PATHS_JSON, f"{PATHS_JSON}.bak.1")


def atomic_write(data: dict) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = f"{PATHS_JSON}.tmp.{os.getpid()}.{int(time.time() * 1000) % 1000000}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, PATHS_JSON)  # rename原子性(主)


def load() -> dict:
    if not os.path.exists(PATHS_JSON):
        return {"entries": {}}
    with open(PATHS_JSON, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    tab = sys.argv[1]
    args = sys.argv[2:]
    if not args:
        print("error: path引数か --remove/--set が必要", file=sys.stderr)
        return 2

    lock_fd = None
    try:
        # 補助ロック(ローカルFS向け・失敗してもrename原子性で壊れない)
        try:
            import fcntl
            lock_fd = open(LOCK_FILE, "w")
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
        except Exception:
            lock_fd = None

        data = load()
        entries = data.setdefault("entries", {})
        if args[0] == "--remove":
            entries.pop(tab, None)
        elif args[0] == "--set":
            entries[tab] = [norm(p) for p in args[1:]]
        else:
            plist = entries.setdefault(tab, [])
            for p in args:
                np = norm(p)
                if np not in plist:
                    plist.append(np)

        rotate_backup()
        atomic_write(data)
        print(f"ok: {tab} -> {entries.get(tab, [])}")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        if lock_fd is not None:
            try:
                lock_fd.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
