# tmux 環境構成ドキュメント

> このファイルは、LLMが変わっても現在のtmux環境を再構築できるよう、
> 構造・意図・手順を全て記述する。操作リファレンスも兼ねる。

---

## 1. 環境の全体像

```
┌─────────────────────────────────────────────────────────────┐
│ tmux server                                                 │
│                                                             │
│  ┌─── Session: ssot（メイン・常時稼働）─────────────────┐   │
│  │  Window: monitor（6ペイン 3列x2行）                 │   │
│  │                                                     │   │
│  │  ┌──────────┬──────────┬──────────┐                │   │
│  │  │ Pane 0   │ Pane 1   │ Pane 2   │                │   │
│  │  │ Claude   │ bash     │ bash     │                │   │
│  │  │ Code     │ (作業用) │ (作業用) │                │   │
│  │  │          │          │          │                │   │
│  │  ├──────────┼──────────┼──────────┤                │   │
│  │  │ Pane 3   │ Pane 4   │ Pane 5   │                │   │
│  │  │ 監視     │ bash     │ bash     │                │   │
│  │  │ (watch)  │ (作業用) │ (作業用) │                │   │
│  │  └──────────┴──────────┴──────────┘                │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─── Session: krokod（サブ・一時作業用）──────────────┐   │
│  │  Window: bash（1ペイン）                            │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 2. 各ペインの役割

| Pane | 役割 | コマンド | 備考 |
|---|---|---|---|
| 0 | Claude Code（メイン対話） | `claude` | 上段左。LLMとのメイン対話窓口 |
| 1 | bash（作業用） | bash | 上段中央。Git操作・ファイル確認等 |
| 2 | bash（作業用） | bash | 上段右。並列作業用 |
| 3 | セッション監視 | `watch -n 5 "tmux ls && tmux list-panes -a"` | 下段左。5秒ごとに全セッション状態を表示 |
| 4 | bash（作業用） | bash | 下段中央。ログ確認・ビルド等 |
| 5 | bash（作業用） | bash | 下段右。並列作業用 |

## 3. 設定ファイル

**場所:** `~/.tmux.conf`
**内容:**
```
set -g mouse on
```
マウス操作のみ有効。最小構成。

**注意:** `tmux source ~/.tmux.conf` を実行するとペインレイアウトがリセットされる場合がある。
設定変更後は `source` ではなく、構成し直すことを想定すること。

## 4. セッション一覧

| セッション名 | 用途 | 作成日 |
|---|---|---|
| `ssot` | メイン作業環境。Claude Code + 作業ペイン + 監視 | 手動作成 |
| `krokod` | サブ。一時的な作業・テスト実行等 | 手動作成 |

## 5. 1から構築する手順（完全再現）

### Step 1: セッション作成
```bash
tmux new-session -s ssot -n monitor -d
tmux new-session -s krokod -d
```

### Step 2: 6ペイン作成
```bash
# ssotに5回分割して6ペインにする
for i in $(seq 5); do tmux split-window -t ssot:0.0; done

# グリッドレイアウト適用
tmux select-layout -t ssot tiled
```

### Step 3: 監視ペイン設定
```bash
tmux send-keys -t ssot:0.3 \
  'watch -n 5 "tmux list-sessions && echo --- && tmux list-panes -a -F \"#{session_name}:#{pane_index} #{pane_width}x#{pane_height} [#{pane_current_command}]\""' \
  Enter
```

### Step 4: Claude Code起動
```bash
tmux send-keys -t ssot:0.0 'claude' Enter
```

### Step 5: 接続
```bash
tmux attach -t ssot
```

## 6. レイアウト崩壊時の即復旧

```bash
# 復旧スクリプト（claude-configリポジトリに保存済み）
bash /home/yn441611/projects/claude-config/scripts/tmux-restore-6pane.sh ssot
```

これ1発で:
1. ペインを1つにリセット（pane 0のClaude Codeは保持）
2. 6ペイン再作成
3. tiledレイアウト適用
4. 監視ペイン自動設定

## 7. 操作リファレンス

### プレフィックス
すべて `Ctrl+b` の後に操作キー

### ペイン
| 操作 | キー |
|---|---|
| 左右分割 | `Ctrl+b %` |
| 上下分割 | `Ctrl+b "` |
| ペイン移動 | `Ctrl+b o` または `Ctrl+b ←↑→↓` |
| 番号で移動 | `Ctrl+b q` → 数字 |
| ペイン閉じる | `Ctrl+b x` または `exit` |
| ズーム切替 | `Ctrl+b z` |
| 入れ替え | `Ctrl+b {` / `Ctrl+b }` |
| レイアウト切替 | `Ctrl+b Space` |
| 横並び均等 | `Ctrl+b Alt+1` |
| 縦並び均等 | `Ctrl+b Alt+2` |

### セッション
| 操作 | キー/コマンド |
|---|---|
| 一覧 | `tmux ls` |
| 作成 | `tmux new -s 名前` |
| 接続 | `tmux attach -t 名前` |
| 切断 | `Ctrl+b d` |
| 切替 | `Ctrl+b s` |
| 名前変更 | `Ctrl+b $` |

### ウィンドウ
| 操作 | キー |
|---|---|
| 新規 | `Ctrl+b c` |
| 切替 | `Ctrl+b 0-9` / `n` / `p` |
| 名前変更 | `Ctrl+b ,` |

## 8. コピペ操作

tmux内でテキストをコピー・ペーストする方法は2通りある。

### 方法A: マウス操作（推奨）
前提: `~/.tmux.conf` に `set -g mouse on` が設定されていること。

| 操作 | やり方 |
|---|---|
| コピー | テキストをドラッグ選択 → 自動でtmuxバッファにコピー |
| ペースト | `Ctrl+b ]` （または右クリック） |
| スクロール | マウスホイール（スクロールモードに入る） |
| スクロール終了 | `q` または `Esc` |

**注意:** 単純にドラッグするとtmuxのコピーになり、ターミナルの選択にならない。
ターミナル本体の選択を使いたい場合は `Shift` を押しながらドラッグ。

### 方法B: キーボード操作
| 操作 | キー |
|---|---|
| コピーモード開始 | `Ctrl+b [` |
| カーソル移動 | `←↑→↓` または `vimキー（hjkl）` |
| 選択開始 | `Space` |
| 選択終了（コピー） | `Enter` |
| ペースト | `Ctrl+b ]` |
| コピーモード終了 | `q` または `Esc` |

### 方法C: システムクリップボード連携（WSL2）
```bash
# tmuxバッファ → Windowsクリップボード
tmux save-buffer - | clip.exe

# Windowsクリップボード → tmuxバッファ
powershell.exe -c "Get-Clipboard" | tmux load-buffer -
```

### コピペ関連のよく使うコマンド
```bash
# コピー履歴一覧（過去にコピーした内容を確認）
tmux list-buffers

# 最新バッファの内容を表示
tmux show-buffer

# バッファ番号を指定してペースト
tmux paste-buffer -b 0

# バッファをファイルに保存
tmux save-buffer ~/clipboard.txt
```

## 9. よく使うコマンド集

### ペイン操作
```bash
# 特定ペインにコマンドを送信
tmux send-keys -t ssot:0.1 'ls -la' Enter

# 特定ペインでコマンドを実行（そのまま表示）
tmux send-keys -t ssot:0.4 'htop' Enter

# 全ペインに同じコマンドを一括送信
tmux list-panes -t ssot -F "#{pane_index}" | \
  xargs -I{} tmux send-keys -t ssot:0.{} 'clear' Enter

# ペインのサイズ変更（CLIから）
tmux resize-pane -t ssot:0.0 -U 5    # 上に5行拡大
tmux resize-pane -t ssot:0.0 -D 5    # 下に5行拡大
tmux resize-pane -t ssot:0.0 -L 10   # 左に10列拡大
tmux resize-pane -t ssot:0.0 -R 10   # 右に10列拡大
```

### セッション管理
```bash
# セッションの生存確認
tmux has-session -t ssot && echo "存在する" || echo "存在しない"

# セッションを完全に終了
tmux kill-session -t krokod

# 全セッション終了（tmux server停止）
tmux kill-server

# セッションのウィンドウ名変更
tmux rename-window -t ssot:0 monitor
```

### テキスト処理
```bash
# ペインの履歴（スクロールバック）を全量取得
tmux capture-pane -t ssot:0.0 -p -S - > ~/pane-log.txt

# ペイン履歴から特定文字列を検索
tmux capture-pane -t ssot:0.0 -p -S - | grep "error"

# ペイン内のテキストをファイルに保存
tmux capture-pane -t ssot:0.0 -p > ~/screenshot.txt
```

### 復旧・保守
```bash
# レイアウトが崩れた時の即直し
tmux select-layout -t ssot tiled

# ペインが多すぎる時の整理
for i in $(tmux list-panes -t ssot -F "#{pane_index}" | sort -rn | head -n +2); do
  tmux kill-pane -t ssot:0.$i
done

# 全ペインの現在のコマンド確認（何が動いてるか）
tmux list-panes -a -F "#{session_name}:#{pane_index} #{pane_current_command}"
```

## 10. 関連ファイル

| ファイル | 場所 | 内容 |
|---|---|---|
| 設定 | `~/.tmux.conf` | `set -g mouse on` のみ |
| 復旧スクリプト | `claude-config/scripts/tmux-restore-6pane.sh` | 1コマンド復旧 |
| このドキュメント | `SSOT/00_SYSTEM/shared-rules/tmux-cheatsheet.md` | 構成仕様・操作リファレンス |
