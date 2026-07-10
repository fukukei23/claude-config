#!/usr/bin/env python3
"""Gemini モデル陳腐化耐性の健診・運用ツール（層④観測・層⑤能動的健診）.

Usage:
    gemini-models-health.py --invalidate       # ListModelsキャッシュを強制更新
    gemini-models-health.py --report           # statsログ集計（成功率・429・fallback）
    gemini-models-health.py --ping             # 各候補に生存確認（実API・軽量）
    gemini-models-health.py --report --ping    # 両方

層⑤能動的健診: 月1 cron 想定（renew-crons.sh の @cron で管理）。
正典: 30_RESEARCH/llm-models/models/gemini.md（最終確認日を更新案として提示）。
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from lib.api_base import (  # noqa: E402
    _cache_dir,
    _list_models_cached,
    _load_candidates,
)


def _load_key() -> str:
    """Gemini APIキーを2段階で取得（os.environ → ~/.secrets.env パース）."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key
    secrets = Path.home() / ".secrets.env"
    if secrets.exists():
        for line in secrets.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("export ") and "=" in line:
                name, _, val = line[len("export "):].partition("=")
                if name.strip() == "GEMINI_API_KEY":
                    val = val.strip().strip('"').strip("'")
                    if val:
                        return val
    raise RuntimeError("GEMINI_API_KEY not found (env or ~/.secrets.env)")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数をパースする."""
    parser = argparse.ArgumentParser(description="Gemini モデル陳腐化耐性の健診ツール")
    parser.add_argument("--invalidate", action="store_true", help="ListModelsキャッシュを強制更新")
    parser.add_argument("--report", action="store_true", help="statsログの集計レポート")
    parser.add_argument("--ping", action="store_true", help="各候補に生存確認（実API・軽量）")
    return parser.parse_args(argv)


def do_invalidate(api_key: str) -> None:
    """ListModelsキャッシュを強制再取得する（トラブル時の手動更新）."""
    print("[ListModels] キャッシュ強制更新中...")
    models = _list_models_cached(api_key, force=True)
    flash_models = sorted([m for m in models if "flash" in m])
    print(f"  ✅ 取得成功: {len(models)} モデル（Flash系: {flash_models[:6]}）")


def do_report() -> None:
    """~/tmp/api_cache/gemini_stats.jsonl を集計してレポート表示する."""
    stats_path = _cache_dir() / "gemini_stats.jsonl"
    if not stats_path.exists():
        print("[Report] stats ログがありません（まだ API 実行履歴なし）")
        return
    entries = []
    for line in stats_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not entries:
        print("[Report] stats ログは空です")
        return

    by_model: dict[str, Counter] = defaultdict(Counter)
    for e in entries:
        by_model[e.get("model", "?")][e.get("status", "?")] += 1

    print(f"[Report] 全 {len(entries)} 件（{stats_path}）\n")
    print(f"{'モデル':<28} {'attempt':>8} {'ok':>6} {'fail':>6} {'error':>6} {'成功率':>8}")
    print("-" * 70)
    for model, counts in sorted(by_model.items()):
        total = counts["attempt"] or 1
        ok = counts["ok"]
        rate = f"{ok / total * 100:.0f}%" if total else "-"
        print(f"{model:<28} {counts['attempt']:>8} {ok:>6} {counts['fail']:>6} {counts['error']:>6} {rate:>8}")

    fallbacks = [e for e in entries if e.get("fallback_from")]
    if fallbacks:
        print(f"\n⚠️ フォールバック発生: {len(fallbacks)} 件")


def do_ping(api_key: str) -> None:
    """config の全候補（vision/audio/video/text 無料枠）の実在を確認する."""
    print("[Ping] 候補生存確認（ListModels 実在チェック）...")
    try:
        available = _list_models_cached(api_key)
    except Exception as exc:
        print(f"  ❌ ListModels 取得失敗: {exc}")
        return
    for cap in ["vision", "audio", "video", "text"]:
        cands = _load_candidates(cap, paid_ok_limit=False)
        for m in cands:
            mark = "✅" if m in available else "⚠️ 不在"
            print(f"  {cap:<7} {m:<22} {mark}")
    print("\n  ※ 不在候補は config/gemini-models.json から削除を検討（正典: 30_RESEARCH/llm-models/models/gemini.md）")


def main(argv: list[str] | None = None) -> int:
    """エントリポイント."""
    args = parse_args(argv)
    if not any([args.invalidate, args.report, args.ping]):
        print("何らかのモードを指定してください（--invalidate / --report / --ping）")
        return 1

    if args.report:
        do_report()
        print()

    if args.invalidate or args.ping:
        try:
            api_key = _load_key()
        except RuntimeError as exc:
            print(f"❌ {exc}")
            return 1
        if args.invalidate:
            do_invalidate(api_key)
            print()
        if args.ping:
            do_ping(api_key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
