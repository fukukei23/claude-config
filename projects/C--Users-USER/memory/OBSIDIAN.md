# Obsidian 構造と使い方

更新日: 2026-02-08

---

## Vault構造

```
C:\SSOT\
├── 00_SYSTEM\          (システム設定・原則)
├── 01_DECISIONS\       (意思決定ログ)
├── 02_CONTEXT\          (背景・コンテキスト)
├── 03_LOGS\            (ログ専用 - Claude会話はここ)
└── .obsidian\           (Obsidian設定)
```

---

## Claude Code 連携ツール

| ツール | パス | ホットキー | 説明 |
|--------|------|-----------|--------|
| スクショ保存 | `C:\Users\USER\.claude\screenshot-to-claude.ahk` | Ctrl + Shift + Z | スクショ→保存→パスをクリップボード |
| Obsidianテンプレート | `C:\Users\USER\.claude\obsidian-helper.ahk` | Ctrl + Alt + N | 会話用テンプレートをクリップボードにコピー |
| Claude会話エクスポート | `C:\Users\USER\.claude\obsidian-exporter.ahk` | Ctrl + Alt + E | JSONLログ→Markdown変換→`03_LOGS/Claude/`へ保存 |

---

## スタートアップ設定（自動起動）

すべてのツールはWindows起動時に自動実行されます：

```
C:\Users\USER\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\
├── obsidian-exporter.ahk - ショートカット.lnk
├── obsidian-helper.lnk
├── screenshot-shortcut.lnk
└── screenshot-to-claude.ahk - ショートカット.lnk
```

---

## Claude会話のワークフロー

1. **会話中**: 必要に応情報をメモ
2. **会話終了時**: Ctrl + Alt + E でエクスポート
3. **Obsidianで確認**: `03_LOGS/Claude/` フォルダをチェック
4. **ノード作成**: Ctrl + Alt + N でテンプレート貼り付け、重要情報を記述

---

## 注意点

- Claude会話ログは `C:\Users\USER\.claude\projects\C--Users-USER\*.jsonl` に保存される
- エクスポートスクリプトは最新のセッションのみ処理
- 画像パスは `C:\Users\USER\.claude_screenshots\` に保存される
