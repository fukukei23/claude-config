#!/usr/bin/env python3
"""
Claude Code 使用量 日次集計スクリプト
--date YYYY-MM-DD で対象日指定（省略時は昨日）
"""
import json, glob, os, sys, datetime, argparse
from pathlib import Path

# --- パス設定 ---
PROJECTS_JSONL = Path.home() / ".claude/projects"
STATS_DIR = Path.home() / "projects/obsidian-ssot/00_SYSTEM/stats/daily"
SUMMARY_FILE = Path.home() / "projects/obsidian-ssot/00_SYSTEM/stats/summary.md"

DESKTOP_LEVELDB = "/mnt/c/Users/yn441/AppData/Local/Packages/Claude_pzs8sxrjxfjjc/LocalCache/Roaming/Claude/IndexedDB/https_claude.ai_0.indexeddb.leveldb"
DESKTOP_SESSIONS = "/mnt/c/Users/yn441/AppData/Local/Packages/Claude_pzs8sxrjxfjjc/LocalCache/Roaming/Claude/claude-code-sessions"
GIT_REPOS = Path.home() / "projects"
EXCLUDED_REPOS = {"tweetly"}

# --- コスト計算（Sonnet 4.6料金） ---
def calc_cost(in_tok, out_tok, cache_read):
    return (in_tok * 3 + out_tok * 15 + cache_read * 0.3) / 1_000_000

# ==================== A. WSL CLI 集計 ====================
def collect_wsl_cli(target_date: str) -> dict:
    """JSONLファイルからassistantメッセージのusageを集計"""
    day_start = datetime.datetime.strptime(target_date, "%Y-%m-%d")
    day_start_ts = day_start.timestamp()
    day_end_ts = (day_start + datetime.timedelta(days=1)).timestamp()

    sessions = set()
    input_tok = output_tok = cache_read = cache_create = 0

    for jsonl in PROJECTS_JSONL.glob("**/*.jsonl"):
        session_ids = set()
        for line in open(jsonl, encoding="utf-8", errors="ignore"):
            try:
                d = json.loads(line.strip())
            except:
                continue
            if d.get("type") != "assistant":
                continue
            ts = d.get("timestamp", "")
            # ISO -> unix
            try:
                ts_dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except:
                continue
            if not (day_start_ts <= ts_dt.timestamp() < day_end_ts):
                continue
            msg = d.get("message", {})
            u = msg.get("usage", {})
            input_tok += u.get("input_tokens", 0)
            output_tok += u.get("output_tokens", 0)
            cache_read += u.get("cache_read_input_tokens", 0)
            cache_create += u.get("cache_creation_input_tokens", 0)
            if d.get("sessionId"):
                session_ids.add(d["sessionId"])

        sessions.update(session_ids)

    api_calls = input_tok // 1000  # 概算

    return {
        "sessions": len(sessions),
        "api_calls": api_calls,
        "input_tokens": input_tok,
        "output_tokens": output_tok,
        "cache_read_tokens": cache_read,
        "cache_creation_tokens": cache_create,
        "cost_usd_estimate": round(calc_cost(input_tok, output_tok, cache_read), 6)
    }

# ==================== B. デスクトップ集計 ====================
def collect_desktop(target_date: str) -> dict:
    """デスクトップ: LevelDBまたはセッションJSONから集計"""
    day_start = datetime.datetime.strptime(target_date, "%Y-%m-%d")
    day_start_ms = int(day_start.timestamp() * 1000)
    day_end_ms = int((day_start + datetime.timedelta(days=1)).timestamp() * 1000)

    models = {}
    sessions = 0
    input_tok = output_tok = cache_read = None
    token_source = "unavailable"

    # まずセッションJSONでsessions・modelsを集計
    for json_file in glob.glob(f"{DESKTOP_SESSIONS}/**/local_*.json", recursive=True):
        try:
            with open(json_file) as f:
                d = json.load(f)
            created = int(d.get("createdAt", 0))
            if not (day_start_ms <= created < day_end_ms):
                continue
            sessions += 1
            model = d.get("model", "unknown")
            models[model] = models.get(model, 0) + 1
        except Exception:
            pass

    # LevelDB試行（plyvel使用、カスタムコンパレータ必要）
    try:
        import plyvel

        def idb_cmp(a, b):
            if a < b: return -1
            if a > b: return 1
            return 0

        leveldb_copy = "/tmp/claude_leveldb_copy"
        os.makedirs(leveldb_copy, exist_ok=True)

        # ファイルコピー
        for f in glob.glob(f"{DESKTOP_LEVELDB}/*.ldb"):
            shutil.copy(f, leveldb_copy)
        for f in ["CURRENT", "MANIFEST-000001"]:
            p = os.path.join(DESKTOP_LEVELDB, f)
            if os.path.exists(p):
                shutil.copy(p, leveldb_copy)

        db = plyvel.DB(leveldb_copy, create_if_missing=False,
                       comparator=idb_cmp, comparator_name=b'idb_cmp1')

        total_in = total_out = total_cache = 0
        for k, v in db.iterator():
            # usage関連キーをパース（Chromium IndexedDBエンコーディング）
            # この部分は環境により異なるためフォールバック
            pass

        db.close()

        if total_in > 0:
            input_tok = total_in
            output_tok = total_out
            cache_read = total_cache
            token_source = "leveldb"
    except Exception:
        pass  # セッションJSON already collected

    return {
        "sessions": sessions,
        "models": models,
        "input_tokens": input_tok,
        "output_tokens": output_tok,
        "cache_read_tokens": cache_read,
        "cost_usd_estimate": round(calc_cost(input_tok or 0, output_tok or 0, cache_read or 0), 6) if input_tok else None,
        "token_source": token_source
    }

# ==================== C. Git 統計 ====================
def collect_git(target_date: str) -> dict:
    """Gitコミット数・プッシュ数を集計"""
    day_start_str = f"{target_date} 00:00"
    day_end_str = f"{target_date} 23:59"

    repos_active = []
    commits_total = 0

    for repo_dir in sorted(GIT_REPOS.iterdir()):
        if not repo_dir.is_dir():
            continue
        name = repo_dir.name
        if name in EXCLUDED_REPOS or not (repo_dir / ".git").exists():
            continue

        # コミット数
        r = os.popen(f"git -C {repo_dir} log --oneline --after='{day_start_str}' --before='{day_end_str}' 2>/dev/null").read()
        commits = len([l for l in r.strip().split("\n") if l])
        commits_total += commits
        if commits > 0:
            repos_active.append(name)

    return {
        "commits_total": commits_total,
        "repos_active": repos_active,
        "excluded_repos": sorted(EXCLUDED_REPOS)
    }

# ==================== メイン ====================
def main():
    import shutil
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    if args.date:
        target = args.date
    else:
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        target = yesterday.strftime("%Y-%m-%d")

    print(f"📊 集計日: {target}")

    STATS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = STATS_DIR / f"{target}.json"

    result = {
        "date": target,
        "wsl_cli": collect_wsl_cli(target),
        "desktop": collect_desktop(target),
        "git": collect_git(target),
        "collected_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✅ 保存: {out_file}")
    print(f"   WSL CLI sessions={result['wsl_cli']['sessions']} api_calls={result['wsl_cli']['api_calls']}")
    print(f"   Desktop sessions={result['desktop']['sessions']} models={result['desktop']['models']}")
    print(f"   Git commits={result['git']['commits_total']} repos={result['git']['repos_active']}")

if __name__ == "__main__":
    main()