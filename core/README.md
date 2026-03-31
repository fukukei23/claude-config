# Claude Code Computer Use Scripts

**Claude CodeでWindows画面を操作するスクリプト集**

WSL2環境からWindowsのスクリーンショット、マウス、キーボードを操作できます。

## 特徴

- スクリーンショット自動取得
- マウスクリック自動化
- キーボード入力自動化
- ホットキー操作
- アプリケーション起動
- 定期監視

## セットアップ

### 1. スクリプトをコピー

```bash
mkdir -p ~/.claude/scripts
cp scripts/*.sh scripts/*.ps1 ~/.claude/core/
chmod +x ~/.claude/core/*.sh
```

### 2. 動作確認

```bash
# スクリーンショット撮影
~/.claude/core/take-screenshot.sh

# カーソル位置取得
~/.claude/core/get-cursor.sh
```

## スクリプト一覧

| スクリプト | 機能 | 使用例 |
|-----------|------|--------|
| `take-screenshot.sh` | スクリーンショット撮影 | `take-screenshot.sh /tmp/screen.png` |
| `click.sh` | マウスクリック | `click.sh 100 200 2 left` |
| `type.sh` | 文字入力 | `type.sh "Hello World"` |
| `hotkey.sh` | ホットキー操作 | `hotkey.sh "^(c)"` (Ctrl+C) |
| `start-app.sh` | アプリ起動 | `start-app.sh "notepad.exe"` |
| `get-cursor.sh` | カーソル位置取得 | `get-cursor.sh` |
| `monitor-screen.sh` | 定期スクショ | `monitor-screen.sh 60 /tmp/screens` |

## ホットキー記法

| 記号 | キー |
|------|------|
| `^` | Ctrl |
| `%` | Alt |
| `+` | Shift |
| `~` | Enter |

### 特殊キー

| キー | 記法 |
|------|------|
| Enter | `{ENTER}` または `~` |
| Tab | `{TAB}` |
| Escape | `{ESC}` |
| Backspace | `{BACKSPACE}` |
| Delete | `{DELETE}` |
| 方向キー | `{UP}` `{DOWN}` `{LEFT}` `{RIGHT}` |
| F1-F12 | `{F1}` - `{F12}` |

### 組み合わせ例

```bash
# Ctrl+C（コピー）
hotkey.sh "^(c)"

# Ctrl+V（ペースト）
hotkey.sh "^(v)"

# Alt+F4（閉じる）
hotkey.sh "%{F4}"

# Ctrl+Shift+S（名前を付けて保存）
hotkey.sh "^+(s)"
```

## Claude Codeでの使い方

Claudeに自然言語で指示するだけ：

```
「スクショ撮って」
「(100, 200)をクリックして」
「"Hello"と入力して」
「Ctrl+C押して」
「メモ帳開いて」
```

## 注意事項

- WSL2環境専用です
- Windows側でPowerShellが有効である必要があります
- スクリーンショットはプライマリモニターのみ対応

## ライセンス

MIT

---

**Related**: [tools/obsidian-sync](https://github.com/fukukei23/claude-config/tree/main/tools/obsidian-sync) - Claude Code作業の自動ログ保存
