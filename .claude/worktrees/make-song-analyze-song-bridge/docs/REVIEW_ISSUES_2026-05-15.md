---
name: コードレビュー指摘事項 — Opus × MiniMax (2026-05-15)
date: 2026-05-15
reviewer: Opus 4.7 / MiniMax M2.7
type: issue-backlog
status: open
---

# claude-config — レビュー指摘事項

> 出典: SSOT `40_CAREER/キャリア分析/01_能力評価/2026-05-15_クロスレビュー_Opus×MiniMax.md`
> Anthropic エコシステム内での実装力アピール強化のための修正タスク。優先度順。

---

## 優先度: 🔴 高（採用面接で活きる差別化）

### ISSUE-001: 月 1.5B+ トークン運用の証拠が README に無い
- **症状**: README で「月 1.5B+ トークン処理基盤」と言っているが、その規模を裏付けるダッシュボード / グラフ / 集計スクリプトが見えない
- **対象**: `README.md`, `docs/`
- **推奨対応**:
  - `scheduled-tasks/glm-cost-tracker/` の集計結果をスクリーンショットで貼る
  - `scripts/llm-status.sh` の出力サンプルを README に
  - 月別トークン推移 + コスト推移のチャート（gnuplot で十分）
- **想定工数**: 半日
- **完了条件**: 「本当に大規模運用してるんですね」と面接官に言わせる

### ISSUE-002: MCP サーバーが urllib.request 直書きで非同期化されていない
- **症状**: [`scripts/glm-mcp-server.py`](scripts/glm-mcp-server.py), [`scripts/minimax-mcp-server.py`](scripts/minimax-mcp-server.py) が `urllib.request` 同期実装。1.5B+ トークンスケールで並列性が制約
- **対象**: `scripts/glm-mcp-server.py`, `scripts/minimax-mcp-server.py`
- **推奨対応**:
  - `httpx.AsyncClient` への置き換え（接続プーリング + HTTP/2）
  - MCP サーバー側を asyncio ベースに（既に MCP 公式 SDK が asyncio）
  - ベンチマーク: 並列 10 リクエスト時の P95 レイテンシ比較
- **想定工数**: 1〜2日
- **完了条件**: 「自作 MCP を非同期化して P95 を X% 改善」が言える

---

## 優先度: 🟡 中（運用品質）

### ISSUE-003: フォールバック連鎖が浅い（GLM → MiniMax の 2 段で終了）
- **症状**: [`scripts/claude_fallback.py`](scripts/claude_fallback.py) は primary→secondary の 2 段。MiniMax も死んだら Sonnet 手動許可を待つ
- **対象**: `scripts/claude_fallback.py`, `fallback-config.json`
- **推奨対応**:
  - 3 段目（Sonnet）を「事前許可済みのコスト上限内なら自動」へ
  - `fallback-config.json` に `tertiary_provider` セクション + 日次 USD 上限を追加
  - Sonnet 起動時は別 jsonl ログに分離してコスト可視化
- **想定工数**: 半日

### ISSUE-004: 1.5B トークンとの主張に対しコスト最適化のコードが見えない
- **症状**: バッチ化・キャッシュ・プロンプト圧縮などのコードが scripts/ 配下に見当たらない
- **対象**: 新規 `scripts/prompt-cache.py`, `scripts/batch-processor.py`
- **推奨対応**:
  - 同一プロンプトのレスポンスキャッシュ（diskcache）
  - 短時間内の複数リクエストのバッチング
  - プロンプトテンプレートの差分圧縮
- **想定工数**: 2〜3日（範囲広い）

### ISSUE-005: agents/ ディレクトリに 3 つしかなくスカスカに見える
- **症状**: `code-reviewer.md / decision-recorder.md / tier1-validator.md` の 3 ファイル。実際の運用ノウハウ密度に対し公開分が薄い
- **対象**: `agents/`
- **推奨対応**:
  - 普段使っているサブエージェントのうち、機密性のないものを公開
  - 各エージェントに「いつ呼ばれるか」「期待する出力」を Frontmatter で明示
- **想定工数**: 1日（既存プライベートエージェントの整理）

---

## 優先度: 🟢 低（OSS 化 / 体裁）

### ISSUE-006: Private Repository の表示が README 末尾にのみ
- **対象**: `README.md`
- **推奨**: 公開する場合はサニタイゼーションチェックリストを `docs/PUBLISH_CHECKLIST.md` として整備

### ISSUE-007: ROUTING.md と CLAUDE.md / グローバル CLAUDE.md の整合チェックが自動化されていない
- **症状**: `~/.claude/CLAUDE.md` と repo の CLAUDE.md / ROUTING.md は手動同期
- **対象**: `scripts/`
- **推奨**: `scripts/check-claude-md-sync.sh` を追加して、差分があれば警告

### ISSUE-008: 英語 README が無い
- **対象**: `README.md`
- **推奨**: 公開リポジトリ化する場合は冒頭に英語 abstract

---

## 補足: 採用面接で語るべきストーリー

このリポジトリで強調すべきは:
1. **MCP プロトコルを自作実装している**（[`scripts/glm-mcp-server.py`](scripts/glm-mcp-server.py): 540 行で MCP stdin/stdout を完全実装）
2. **HTTP セマンティクスを完全に理解したフォールバック**（[`scripts/claude_fallback.py:20-39`](scripts/claude_fallback.py): 429/5xx → retryable, 401/403/422 → do_not_fallback）
3. **2 環境（CLI/Desktop）の仕様差を文書化**（[`ROUTING.md`](ROUTING.md): 認証/モデル/コスト構造の差を厳密に定義）
4. **Anthropic エコシステムへの強い文脈知識**（OAuth Pro 固定 / MCP / fallback config の各種ハマりどころ）

逆に質問されたら困る箇所:
- 「1.5B トークンの根拠は？」 → ISSUE-001（証拠ダッシュボード化）
- 「並列性は？」 → ISSUE-002（asyncio 化）
- 「3 段以上のフォールバックは？」 → ISSUE-003
