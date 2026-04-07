# リポジトリ使い分けガイド

**対象読者**: Claude Code Desktop を初めて使う人向け
**版**: 1.0 | 作成: 2026-04-07

---

## 📚 リポジトリ体系図

```
┌─────────────────────────────────────────────────────────┐
│        Claude Code Desktop エコシステム                   │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  🔧 設定・構成                │  📚 プロジェクト管理        │
│  ─────────────────           ─────────────────         │
│  • claude-config             • openclaw-main           │
│  • krokod-setup              • atelier-kyo-manager     │
│  • SSOT（共通KB）            • Reserve-optimizer       │
│                                                           │
│  🛠️  ツール・スクリプト        │  🔐 Handover 文書         │
│  ─────────────────           ─────────────────         │
│  • scripts/                  • handover/               │
│  • tools/                    • LLM_HANDOVER_*.md       │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 主要リポジトリの役割

### 1️⃣ **claude-config** — 設定・ルール集約所

```
📁 fukukei23/claude-config
├── README.md                    ← 概要・セットアップ手順
├── ARCHITECTURE.md              ← システムアーキテクチャ
├── CLAUDE.md                    ← LLM優先ルール
├── ROUTING.md                   ← ルーティング詳細設定
├── TROUBLESHOOTING.md           ← FAQ・トラブル解決
│
├── 📂 agents/                   ← AI 自動化エージェント設定
├── 📂 cache/                    ← キャッシュ・パフォーマンス
├── 📂 core/                     ← コア設定ファイル
├── 📂 docs/                     ← ドキュメント集
├── 📂 lib/                      ← ライブラリ・ユーティリティ
├── 📂 obsidian-logging/         ← Obsidian 連携ログ
├── 📂 plugins/                  ← Claude Code プラグイン設定
├── 📂 projects/                 ← プロジェクト固有設定
├── 📂 scheduled-tasks/          ← 定期タスク定義
├── 📂 scripts/                  ← 自動化スクリプト集
├── 📂 shared-rules/             ← 全プロジェクト共通ルール
├── 📂 tools/                    ← 開発用ツール設定
└── 📂 workflows/                ← CI/CD・自動化フロー
```

#### 🔍 使用シーン

| シーン | ファイル | 何をするか |
|--------|---------|----------|
| LLMのルーティング設定を確認したい | `CLAUDE.md` | MiniMax/GLM/Sonnet優先順位を確認 |
| LLMが遅い・失敗する | `ROUTING.md` | ルーティング詳細やフォールバック設定を確認 |
| トラブル発生時 | `TROUBLESHOOTING.md` | FAQ・よくあるエラーパターン |
| 新しいプロジェクト開始 | `projects/` | プロジェクト別のテンプレート参照 |
| スクリプト自動化 | `scripts/` | 再利用可能なスクリプト探索 |

---

### 2️⃣ **krokod-setup** — WSL2 セットアップ・Fallback リポジトリ

```
📁 fukukei23/krokod-setup
├── README.md                    ← WSL2 側セットアップ
├── FALLBACK.md                  ← フォールバック戦略
├── rules.md                     ← WSL2 専用ルール
├── LLM_HANDOVER_KROKOD_2026-03-22.md ← Krokod 環境の引き継ぎ文書
│
├── 📂 desktop/                  ← Desktop 側の設定テンプレート
│   ├── settings.example.json
│   └── settings.local.example.json
│
└── 📂 scripts/                  ← WSL2 向けスクリプト群
    ├── install.sh
    └── setup.sh
```

#### 🔍 使用シーン

| シーン | ファイル | 何をするか |
|--------|---------|----------|
| Windows が使えない・WSL2 で動かしたい | `README.md` | WSL2 セットアップ手順 |
| Desktop LLM が全て失敗した | `FALLBACK.md` | WSL2 側の Fallback 戦略確認 |
| Desktop/WSL2 設定テンプレートが必要 | `desktop/` | `settings.example.json` をコピー |

---

## 🌐 アクセス方法

### リポジトリ認証（初回のみ）

```bash
# 1. Personal Access Token (PAT) 取得
#    https://github.com/settings/tokens
#    - Scopes: repo (private repo access)
#    - Expiry: 30 days or 90 days 推奨

# 2. Claude Code に登録
#    C:\Users\USER\.claude\settings.local.json に追加:
{
  "env": {
    "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_XXXXXXXXXXXX"
  }
}

# 3. 確認
claude-code --version
# → GitHub認証が成功すれば、以降は自動で private repo にアクセス可能
```

### セッション間の永続化

✅ **Claude Code Desktop では PAT は永続化される**

- 1回設定すれば、再セットアップ不要
- `settings.local.json` は Windows ファイルシステムに保存
- セッション再開時に自動復元

### GitHub から直接クローン

```bash
# 初回（PAT設定済みの場合）
git clone https://github.com/fukukei23/claude-config.git
# → 認証成功

# リポジトリ内の README を読む
cat claude-config/README.md
```

---

## 📋 初心者向けチェックリスト

### ✅ セットアップ時

- [ ] **PAT を取得** → GitHub Settings > Developer Settings > Tokens
- [ ] **settings.local.json に記載** → `C:\Users\USER\.claude\`
- [ ] **動作確認** → `mcp__plugin_github_github__get_me` で認証確認

### ✅ 日常的な使用

- [ ] **LLMルーティング確認** → `CONFIG-STRATEGY.md` を参照
- [ ] **トラブル時** → `claude-config/TROUBLESHOOTING.md` を確認
- [ ] **新プロジェクト開始** → `claude-config/projects/` でテンプレート探索

### ✅ トラブル時

- [ ] **Desktop LLM が遅い** → `ROUTING.md` でフォールバック確認
- [ ] **すべての LLM が失敗** → WSL2 Fallback (`krokod-setup/FALLBACK.md`)
- [ ] **GitHub アクセス 404** → PAT 有効期限・スコープを確認

---

## 🎓 推奨される学習順序

```
1️⃣ 【最初】CONFIG-STRATEGY.md
    └─ MiniMax / GLM / Sonnet の役割を理解

2️⃣ 【次】claude-config/README.md
    └─ リポジトリ全体の概要を把握

3️⃣ 【実務】CLAUDE.md + 各プロジェクトテンプレート
    └─ 実際のプロジェクト設定を参照

4️⃣ 【深掘り】ARCHITECTURE.md + ROUTING.md
    └─ 詳細なルーティング戦略を理解

5️⃣ 【バックアップ】krokod-setup/README.md
    └─ WSL2 環境について認識しておく
```

---

## 🔗 リポジトリマッピング表

| リポジトリ | 主な用途 | 更新頻度 | 必須 |
|-----------|--------|--------|------|
| `claude-config` | 設定・ルール・テンプレート | 高（日々の改善） | ✅ 必須 |
| `krokod-setup` | WSL2 セットアップ・Fallback | 中（環境変更時） | ⚠️ 条件付き |
| 各プロジェクトリポ | 実務コード | 高（開発中） | ✅ 必須 |

---

## ❓ よくある質問

### Q1: 最初に見るべきファイルは？

**A**: `claude-config/README.md` → `CONFIG-STRATEGY.md` → `CLAUDE.md` の順

### Q2: 認証が毎回失敗する場合は？

**A**:
1. PAT の有効期限を確認 → https://github.com/settings/tokens
2. Scopes が "repo" を含むか確認
3. `settings.local.json` の PAT が正しくコピーされているか確認

### Q3: Desktop LLM がすべて遅い・失敗する場合は？

**A**: `krokod-setup/FALLBACK.md` で WSL2 セットアップ検討

### Q4: Claude Code を複数環境で使う場合は？

**A**: `claude-config` を共有、`settings.local.json` は**環境ごとに分ける**

---

## 📞 サポート先

| 問題 | 確認先 |
|-----|-------|
| LLM ルーティング | `CONFIG-STRATEGY.md` + `CLAUDE.md` |
| 設定テンプレート | `claude-config/core/` |
| WSL2 環境 | `krokod-setup/README.md` |
| トラブルシューティング | `claude-config/TROUBLESHOOTING.md` |

---

**最終更新**: 2026-04-07
**責任者**: fukukei23
**バージョン**: 1.0
