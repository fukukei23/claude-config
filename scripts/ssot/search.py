#!/home/yn4416/.claude/venv/ssot-search/bin/python3
"""
SSOT ハイブリッド検索スクリプト
ripgrep で全文検索 → sentence-transformers で意味的 rerank → 上位表示

Usage:
  python3 search.py <query> [--top N] [--ssot-dir PATH]
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SSOT_DIR = Path.home() / "projects" / "obsidian-ssot"
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


def rg_search(query: str, ssot_dir: Path, max_files: int = 80) -> list[dict]:
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


def display(query: str, results: list[dict]) -> None:
    if not results:
        print(f"🔍 「{query}」に一致するファイルは見つかりませんでした。")
        return

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


def main():
    parser = argparse.ArgumentParser(description="SSOT ハイブリッド検索")
    parser.add_argument("query", nargs="+", help="検索クエリ")
    parser.add_argument("--top", type=int, default=5, help="表示件数（デフォルト: 5）")
    parser.add_argument("--ssot-dir", default=str(SSOT_DIR), help="SSOTディレクトリパス")
    args = parser.parse_args()

    query = " ".join(args.query)
    ssot_dir = Path(args.ssot_dir)

    if not ssot_dir.exists():
        print(f"❌ SSOTディレクトリが見つかりません: {ssot_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"🔍 検索中: 「{query}」...", file=sys.stderr)
    hits = rg_search(query, ssot_dir, max_files=80)
    print(f"   ripgrep: {len(hits)}ファイルヒット → 意味的rerankで上位{args.top}件を選出...", file=sys.stderr)
    results = rerank(query, hits, top_n=args.top)
    display(query, results)


if __name__ == "__main__":
    main()
