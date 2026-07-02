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
    prompts = 0
    tool_uses = 0
    models = {}

    for jsonl in PROJECTS_JSONL.glob("**/*.jsonl"):
        session_ids = set()
        for line in open(jsonl, encoding="utf-8", errors="ignore"):
            try:
                d = json.loads(line.strip())
            except:
                continue
            ts = d.get("timestamp", "")
            try:
                ts_dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except:
                continue
            if not (day_start_ts <= ts_dt.timestamp() < day_end_ts):
                continue

            if d.get("sessionId"):
                session_ids.add(d["sessionId"])

            if d.get("type") == "user":
                prompts += 1

            if d.get("type") == "assistant":
                msg = d.get("message", {})
                u = msg.get("usage", {})
                input_tok += u.get("input_tokens", 0)
                output_tok += u.get("output_tokens", 0)
                cache_read += u.get("cache_read_input_tokens", 0)
                cache_create += u.get("cache_creation_input_tokens", 0)
                # モデル別集計
                model = msg.get("model", "unknown")
                models[model] = models.get(model, 0) + 1
                # ツール使用回数
                if msg.get("stop_reason") == "tool_use":
                    tool_uses += 1

        sessions.update(session_ids)

    return {
        "sessions": len(sessions),
        "prompts": prompts,
        "api_calls": sum(models.values()),  # assistant メッセージ総数 = API コール数
        "tool_uses": tool_uses,
        "models": models,
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

    # completedTurns × モデル別係数で概算トークン
    # 係数: 1ターンあたり 平均 input/output token 概算（Desktop版はusage非保持のため推計）
    # claude-sonnet-4-6: 1turn ≈ 3000 in + 800 out
    # claude-haiku-4-5:  1turn ≈ 2000 in + 500 out
    # claude-opus-4-7:  1turn ≈ 4000 in + 1000 out
    MODEL_COEFFICIENTS = {
        "claude-sonnet-4-6": {"input": 3000, "output": 800, "cache_read": 600},
        "claude-haiku-4-5-20251001": {"input": 2000, "output": 500, "cache_read": 300},
        "claude-opus-4-7": {"input": 4000, "output": 1000, "cache_read": 1000},
    }

    total_in = total_out = total_cache = 0
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

            # completedTurns から概算
            turns = d.get("completedTurns") or 0
            if turns > 0:
                coef = MODEL_COEFFICIENTS.get(model, MODEL_COEFFICIENTS["claude-sonnet-4-6"])
                total_in += turns * coef["input"]
                total_out += turns * coef["output"]
                total_cache += turns * coef["cache_read"]
        except Exception:
            pass

    input_tok = total_in if total_in > 0 else None
    output_tok = total_out if total_out > 0 else None
    cache_read = total_cache if total_cache > 0 else None
    token_source = "estimated-from-completedTurns" if input_tok else "unavailable"

    return {
        "sessions": sessions,
        "models": models,
        "input_tokens": input_tok,
        "output_tokens": output_tok,
        "cache_read_tokens": cache_read,
        "cost_usd_estimate": round(calc_cost(input_tok or 0, output_tok or 0, cache_read or 0), 6) if input_tok else None,
        "token_source": token_source,
        "note": "tokens estimated from completedTurns × model coefficients" if input_tok else None
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
    cli = result['wsl_cli']
    dsk = result['desktop']
    git = result['git']
    print(f"   WSL CLI: sessions={cli['sessions']} prompts={cli['prompts']} api_calls={cli['api_calls']} tool_uses={cli['tool_uses']}")
    print(f"   Models: {cli['models']}")
    print(f"   Tokens: in={cli['input_tokens']:,} out={cli['output_tokens']:,} cache_read={cli['cache_read_tokens']:,}")
    print(f"   Cost: ${cli['cost_usd_estimate']:.4f}")
    print(f"   Desktop: sessions={dsk['sessions']} models={dsk['models']}")
    print(f"   Git: commits={git['commits_total']} repos={git['repos_active']}")

if __name__ == "__main__":
    main()