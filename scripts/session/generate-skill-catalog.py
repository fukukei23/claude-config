#!/usr/bin/env python3
"""generate-skill-catalog.py — SKILL_CATALOG.md 自動生成.

SessionStart hook から呼ばれる。廃止旧スクリプト sync-claude-md.sh の
カタログ生成機能のみを切り出し・軽量化・3バグ修正した新スクリプト。

走査対象:
  1. ~/.claude/skills/*/SKILL.md        — 自作スキル
  2. ~/.claude/plugins/cache/<org>/<plugin>/SKILL.md — プラグインスキル（有効/無効）
  3. settings.json の mcpServers        — MCPサーバー

出力: obsidian-ssot/00_SYSTEM/claude-config/SKILL_CATALOG.md
（全体マップ_MOC.md・knowledge-graph.html から参照される内向き完全版）

3バグ修正（旧 sync-claude-md.sh 対比）:
  - PLUGIN_CACHE typo (yn4146 → yn4416)
  - 自作スキル抽出 (*.md → */SKILL.md)
  - MCP除外フィルタ (grep雑 → mcpServers直下キーを正確抽出)
"""
import json
import re
from pathlib import Path
from datetime import datetime

SETTINGS = Path("/home/yn4416/.claude/settings.json")
SKILLS_DIR = Path("/home/yn4416/.claude/skills")
PLUGIN_CACHE = Path("/home/yn4416/.claude/plugins/cache")
OUTPUT = Path("/home/yn4416/projects/obsidian-ssot/00_SYSTEM/claude-config/SKILL_CATALOG.md")

# Plugin/MCP用の日本語説明辞書（SKILL.mdのdescriptionが英語・または取得困難なもの）
# 未登録スキルはSKILL.mdのdescriptionでフォールバック
JA_DESC = {
    # 自作スキル（descriptionがブロックスカラー等で取りにくいものの日本語化）
    "delegate-to-minimax": "要約・変換・テストデータ生成等の大量処理をMiniMaxに自動委譲。翻訳は不可（中国語混入リスク）",
    # superpowers
    "brainstorming": "実装前にユーザー意図・要件・設計を探索。創造的な作業の前に必須",
    "writing-plans": "仕様・要件から多段階実装計画を作成。コードに触る前に計画を書く",
    "executing-plans": "既存の実装計画をレビューチェックポイント付きで実行",
    "systematic-debugging": "バグ・テスト失敗・予期しない動作に遭遇した時の体系的デバッグ手順",
    "test-driven-development": "機能・バグ修正の実装前にテストを先に書くTDDワークフロー",
    "verification-before-completion": "作業完了を宣言する前に検証コマンドを実行し、証拠ベースで成功を確認",
    "using-git-worktrees": "機能開発用の分離されたgit worktreeを作成・管理",
    "requesting-code-review": "タスク完了・機能実装・マージ前のコードレビューを要求",
    "receiving-code-review": "コードレビューフィードバックを受信した時の技術的検証と対応",
    "finishing-a-development-branch": "実装完了・テスト通過後の統合方法（merge/PR/cleanup）をガイド",
    "using-superpowers": "skillの検出・適用ルール。全レスポンスでskillの適用可否を自動判定",
    "dispatching-parallel-agents": "2つ以上の独立タスクを並列サブエージェントで同時実行",
    "subagent-driven-development": "独立タスクを持つ実装計画をサブエージェントで並列実行",
    "writing-skills": "新規skill作成・既存skill編集・デプロイ前の動作確認",
    # その他Plugin
    "claude-automation-recommender": "コードベースを分析し、Claude Code自動化（hooks/skills/plugins/MCP）を推奨",
    "claude-md-improver": "全CLAUDE.mdをスキャンし、品質評価→改善提案→自動修正",
    "skill-creator": "新規skill作成・改善・テスト・ベンチマーク評価のループ実行",
    "access": "Discordチャンネルのアクセス管理（ペアリング承認・許可リスト編集）",
    "configure": "Discordボットのトークン登録・チャンネル設定・ステータス確認",
}

# MCP説明辞書
MCP_DESC = {
    "glm": "GLM-5.2 LLM（メインモデル）",
    "minimax": "MiniMax（大量処理・フォールバック）",
    "brave-search": "Web検索",
    "github": "GitHub操作（PR/Issue/コード検索）",
    "minimax-official": "MiniMax公式（動画・画像・音声・TTS）",
    "minimax-video": "MiniMax動画生成専用",
}


def parse_frontmatter(path: Path) -> dict:
    """SKILL.md の frontmatter を解析（ブロックスカー対応）."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    fm: dict = {}
    lines = m.group(1).split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("name:"):
            fm["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("description:"):
            v = line.split(":", 1)[1].strip()
            if v in (">", "|", "|-", "|+"):
                # ブロックスカラー: 次のインデント行を結合
                desc_parts = []
                i += 1
                while i < len(lines) and lines[i].startswith(" "):
                    desc_parts.append(lines[i].strip())
                    i += 1
                fm["description"] = " ".join(desc_parts)
                continue
            fm["description"] = v
        i += 1
    return fm


def truncate(s: str, n: int = 120) -> str:
    s = (s or "").replace("|", "/").replace("\n", " ").strip()
    return s[:n] + "…" if len(s) > n else s


def main() -> None:
    settings = {}
    if SETTINGS.exists():
        try:
            settings = json.loads(SETTINGS.read_text())
        except (OSError, json.JSONDecodeError):
            pass

    out = [
        "# Skill & Plugin カタログ",
        "",
        "> 自動生成: `generate-skill-catalog.py`（SessionStart hook）",
        f"> 最終更新: {datetime.now():%Y-%m-%d %H:%M}",
        "",
        "## 1. 自作 Skills",
        "",
        "| Skill | 説明 |",
        "|---|---|",
    ]

    # 1. 自作 Skills（*/SKILL.md 走査）
    if SKILLS_DIR.exists():
        for sd in sorted(SKILLS_DIR.iterdir()):
            sf = sd / "SKILL.md"
            if not sf.is_file():
                continue
            fm = parse_frontmatter(sf)
            name = fm.get("name", sd.name)
            desc = JA_DESC.get(name) or fm.get("description", "")
            out.append(f"| `{name}` | {truncate(desc)} |")

    # 2. Plugin Skills（有効）
    out += ["", "## 2. Plugin Skills（有効）", ""]
    enabled = settings.get("enabledPlugins", {})
    if PLUGIN_CACHE.exists():
        for org in sorted(PLUGIN_CACHE.iterdir()):
            if not org.is_dir():
                continue
            for plugin in sorted(org.iterdir()):
                if not plugin.is_dir():
                    continue
                key = f"{plugin.name}@{org.name}"
                if not enabled.get(key):
                    continue
                sfs = list(plugin.rglob("SKILL.md"))
                if not sfs:
                    continue
                out += [f"### `{plugin.name}`", "", "| Skill | 説明 |", "|---|---|"]
                seen = set()
                for sf in sfs:
                    fm = parse_frontmatter(sf)
                    n = fm.get("name")
                    if not n or n in seen:
                        continue
                    seen.add(n)
                    d = JA_DESC.get(n) or fm.get("description", "")
                    out.append(f"| `{n}` | {truncate(d)} |")
                out.append("")

    # 3. MCP Servers（mcpServers 直下キーを正確抽出）
    out += ["## 3. MCP Servers", "", "| サーバー | 用途 |", "|---|---|"]
    for srv in settings.get("mcpServers", {}):
        out.append(f"| `{srv}` | {MCP_DESC.get(srv, '')} |")

    out.append("")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(out), encoding="utf-8")
    print(f"[catalog] {OUTPUT} を更新しました")


if __name__ == "__main__":
    main()
