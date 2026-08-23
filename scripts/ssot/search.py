#!/home/yn4416/.claude/venv/ssot-search/bin/python3
"""
SSOT ハイブリッド検索スクリプト
ripgrep で全文検索 → sentence-transformers で意味的 rerank → 上位表示

Usage:
  python3 search.py <query> [--top N] [--ssot-dir PATH] [--no-coverage] [--log-coverage]
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SSOT_DIR = Path.home() / "projects" / "obsidian-ssot"

# カバレッジ可視化の定数（spec v3・Gemini指摘のマジックナンバー定数化）
MAX_FILES = 80                       # rg_search の第1段フィルタ上限
LOW_EXTRACTION_THRESHOLD = 0.05      # 抽出率5%未満で ⚠️ → 🚨 に強化
NEXT_CANDIDATE_MULTIPLIER = 2        # 次点候補 = top_n × 2 位まで

# 版の自己申告（2026-08-23 追加）
# 本スクリプトは v1（字句検索）。主経路は v2（ベクトル意味検索・ruri-v3-310m + ChromaDB）。
# 出力に版を書かなかったため「v1 を実行して RAG を実測した」と誤認する事故が起きた。
# 呼び出し経路が複数ある以上、正典（SKILL.md）だけでは防げない。実行結果自身に名乗らせる。
VERSION_BANNER = (
    "\n⚙️ これは ssot-search **v1**（字句検索: ripgrep 前置フィルタ + rerank）です。"
    "**ベクトル意味検索(RAG)ではありません**。\n"
    "   語彙が違うと前置フィルタで落ちます。意味検索が要るなら主経路の v2 を使うこと:\n"
    '   cd ~/projects/ssot-search-v2 && .venv/bin/python3 cli.py "<クエリ>" --top 5'
)

LAYER_LABELS = {
    "00_SYSTEM":    "🔧 SYSTEM",
    "01_DECISIONS": "📋 DECISIONS",
    "10_DAILY":     "📅 DAILY",
    "20_PUBLISHING":"📢 PUBLISHING",
    "30_RESEARCH":  "🔬 RESEARCH",
    "40_CAREER":    "💼 CAREER",
    "50_PROJECTS":  "🗂️  PROJECTS",
    "99_ARCHIVE":   "🗃️  ARCHIVE",
}


def _rg_run(pattern: str, ssot_dir: Path) -> list[str]:
    """ripgrep を1パターンで実行しJSON行リストを返す"""
    try:
        result = subprocess.run(
            ["rg", "--ignore-case", "--max-count=3", "--json", "--glob=*.md",
             pattern, str(ssot_dir)],
            capture_output=True, text=True, timeout=30,
        )
        return result.stdout.splitlines()
    except FileNotFoundError:
        print("❌ ripgrep (rg) が見つかりません。`sudo apt install ripgrep` で入れてください。", file=sys.stderr)
        sys.exit(1)


def _tokenize(query: str) -> list[str]:
    """クエリを検索トークンに分割（日本語助詞・スペース・記号で区切る）"""
    import re
    # 助詞・助動詞・記号で分割
    DELIMITERS = r"[\s　のをがはにでもとからまでよりへ、。・]+"
    tokens = re.split(DELIMITERS, query.strip())
    # 英数字混じりの場合はさらにキャメルケースや記号で分割
    expanded = []
    for t in tokens:
        # 英数字と日本語の境界で分割（例: MiniMaxの→MiniMax）
        parts = re.split(r"(?<=[a-zA-Z0-9])(?=[぀-鿿])|(?<=[぀-鿿])(?=[a-zA-Z0-9])", t)
        expanded.extend(parts)
    tokens = [t for t in expanded if len(t) >= 2]
    if not tokens:
        tokens = [query]
    return tokens


def rg_search(query: str, ssot_dir: Path, max_files: int = MAX_FILES) -> list[dict]:
    """ripgrep で全文検索（フレーズ→トークンOR の2段階）、ファイルパスとスニペットを返す"""
    hits: dict[str, dict] = {}

    def _parse_lines(lines: list[str]) -> None:
        for line in lines:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") != "match":
                continue
            path = obj["data"]["path"]["text"]
            text = obj["data"]["lines"]["text"].strip()
            if path not in hits:
                hits[path] = {"path": path, "snippets": []}
            if text not in hits[path]["snippets"]:
                hits[path]["snippets"].append(text)

    # フェーズ1: フレーズ完全一致
    _parse_lines(_rg_run(query, ssot_dir))

    # フェーズ2: ヒットが少なければトークンORで補完
    if len(hits) < max_files:
        tokens = _tokenize(query)
        if len(tokens) > 1 or tokens[0] != query:
            pattern = "|".join(tokens)
            _parse_lines(_rg_run(pattern, ssot_dir))

    return list(hits.values())[:max_files]


def rerank(query: str, hits: list[dict], top_n: int) -> list[dict]:
    """sentence-transformers で意味的 rerank"""
    if not hits:
        return []

    try:
        from sentence_transformers import SentenceTransformer, util
    except ImportError:
        print("⚠️  sentence-transformers 未インストール。キーワード順で返します。", file=sys.stderr)
        return hits[:top_n]

    model = SentenceTransformer("all-MiniLM-L6-v2")

    # 各ファイルの代表テキスト = スニペット + ファイル名
    docs = []
    for h in hits:
        fname = Path(h["path"]).name
        body = " ".join(h["snippets"])
        docs.append(f"{fname} {body}")

    query_emb = model.encode(query, convert_to_tensor=True)
    doc_embs = model.encode(docs, convert_to_tensor=True)
    scores = util.cos_sim(query_emb, doc_embs)[0].tolist()

    ranked = sorted(zip(scores, hits), key=lambda x: x[0], reverse=True)
    return [h for _, h in ranked[:top_n]]


def layer_label(path: str) -> str:
    rel = Path(path).relative_to(SSOT_DIR)
    top = rel.parts[0] if rel.parts else ""
    return LAYER_LABELS.get(top, f"📁 {top}")


def _count_md_files(ssot_dir: Path) -> int:
    """SSOT内の.mdファイル数を返す（.gitignore 準拠・.git除外）"""
    try:
        result = subprocess.run(
            ["rg", "--files", "--glob=*.md", str(ssot_dir)],
            capture_output=True, text=True, timeout=30,
        )
        return len([ln for ln in result.stdout.splitlines() if ln.strip()])
    except FileNotFoundError:
        return 0


def _compute_coverage(total: int, filtered: int, top_n: int, ranked_count: int) -> dict:
    """カバレッジ情報の計算（責務分割: 計算のみ。表示は _render_coverage）

    Args:
        total: SSOT全体の.mdファイル数（母数）
        filtered: rg_search の第1段フィルタ結果件数
        top_n: 表示件数
        ranked_count: rerank が返した件数（top_n×2 要求したが hits 不足の場合は短い）

    Returns:
        カバレッジ情報 dict
    """
    excluded = max(0, total - filtered)
    extraction_rate = (filtered / total) if total > 0 else 0.0
    low_extraction = total > 0 and extraction_rate < LOW_EXTRACTION_THRESHOLD
    next_candidates = max(0, ranked_count - top_n)
    return {
        "total": total,
        "filtered": filtered,
        "excluded": excluded,
        "extraction_rate": extraction_rate,
        "low_extraction": low_extraction,
        "next_candidates": next_candidates,
    }


def _render_coverage(coverage: dict, top_n: int, zero_hit: bool) -> str:
    """カバレッジ情報の表示文字列を生成（責務分割: 表示のみ）

    Args:
        coverage: _compute_coverage の戻り値
        top_n: 表示件数（次点候補の開始位置表示に使用）
        zero_hit: 0ヒットケースか（ヒント表示を切替）

    Returns:
        表示用文字列（複数行）
    """
    total = coverage["total"]
    filtered = coverage["filtered"]
    excluded = coverage["excluded"]
    warn = "🚨" if coverage["low_extraction"] else "⚠️"
    lines = [VERSION_BANNER]

    if zero_hit:
        lines.append(f"\n📊 カバレッジ: SSOT全体 {total:,} .mdファイル中、ripgrep で{filtered}ファイル抽出")
        lines.append("💡 ヒント: クエリを変える（より一般的な語・略語の正式名・英語/日本語の切替）か、別の表現で再検索してください")
    else:
        lines.append(f"\n📊 カバレッジ: SSOT全体 {total:,} .mdファイル中、ripgrep で{filtered}ファイル抽出 → 意味rerankで上位{top_n}件表示")
        nc = coverage["next_candidates"]
        if nc > 0:
            top_end = top_n * NEXT_CANDIDATE_MULTIPLIER
            lines.append(f"📌 次点候補: {top_n + 1}位〜{top_end}位にあと{nc}件（表示を増やすなら --top {top_end}）")
        if excluded > 0:
            lines.append(f"{warn} {excluded:,}ファイルはキーワード非マッチのため未確認（語彙違いの類縁判断が含まれている可能性があります）")

    return "\n".join(lines)


def display(query: str, results: list[dict], coverage: dict | None = None,
            top_n: int = 5, no_coverage: bool = False) -> None:
    """検索結果とカバレッジを表示。coverage=None で従来動作（後方互換）"""
    print(VERSION_BANNER)   # 先頭（`| head` 対策・末尾にも同じものを出す）
    zero_hit = not results
    if zero_hit:
        print(f"🔍 「{query}」に一致するファイルは見つかりませんでした。")
    else:
        print(f"\n🔍 SSOT検索: 「{query}」 — {len(results)}件ヒット\n")
        print("=" * 60)
        for i, h in enumerate(results, 1):
            path = h["path"]
            rel = str(Path(path).relative_to(SSOT_DIR))
            label = layer_label(path)
            print(f"\n{i}. {label}  {rel}")
            for snippet in h["snippets"][:2]:
                print(f"   > {snippet[:120]}")
        print("\n" + "=" * 60)

    # 末尾（`| tail` 対策）。先頭にも出しているのは `| head` 対策（2026-08-23 実測で
    # head -12 だと末尾バナーが見えないことを確認したため両端に出す）。
    if coverage is not None and not no_coverage:
        print(_render_coverage(coverage, top_n, zero_hit))
    else:
        # --no-coverage でも版だけは必ず名乗る（誤認事故の再発防止・2026-08-23）
        print(VERSION_BANNER)


def main():
    global SSOT_DIR
    parser = argparse.ArgumentParser(description="SSOT ハイブリッド検索")
    parser.add_argument("query", nargs="+", help="検索クエリ")
    parser.add_argument("--top", type=int, default=5, help="表示件数（デフォルト: 5）")
    parser.add_argument("--ssot-dir", default=str(SSOT_DIR), help="SSOTディレクトリパス")
    parser.add_argument("--no-coverage", action="store_true",
                        help="カバレッジ表示を抑制（pipe用途）")
    parser.add_argument("--log-coverage", action="store_true",
                        help="カバレッジ3情報をJSONでstderr出力（計測/監査用途）")
    args = parser.parse_args()

    query = " ".join(args.query)
    ssot_dir = Path(args.ssot_dir)
    SSOT_DIR = ssot_dir

    if not ssot_dir.exists():
        print(f"❌ SSOTディレクトリが見つかりません: {ssot_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"🔍 検索中: 「{query}」...", file=sys.stderr)
    total = _count_md_files(ssot_dir)
    hits = rg_search(query, ssot_dir, max_files=MAX_FILES)
    print(f"   ripgrep: {len(hits)}ファイルヒット（全体{total}件中） → 意味的rerankで上位{args.top}件を選出...",
          file=sys.stderr)
    # 次点候補(top_n+1〜top_n×2位)を確保するため top×2 件で rerank
    ranked = rerank(query, hits, top_n=args.top * NEXT_CANDIDATE_MULTIPLIER)
    results = ranked[:args.top]
    coverage = _compute_coverage(total, len(hits), args.top, len(ranked))

    display(query, results, coverage=coverage, top_n=args.top, no_coverage=args.no_coverage)

    if args.log_coverage:
        # 計測/監査用途: 母数・フィルタ結果・除外量 をJSONでstderr出力
        log = {
            "total": coverage["total"],
            "filtered": coverage["filtered"],
            "excluded": coverage["excluded"],
            "extraction_rate": round(coverage["extraction_rate"], 4),
            "low_extraction": coverage["low_extraction"],
        }
        print(json.dumps(log, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
