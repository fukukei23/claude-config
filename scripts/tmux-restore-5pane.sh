#!/bin/bash
# tmux 6ペイン復旧 + Claude Code自動起動スクリプト
# 使い方: bash scripts/tmux-restore-5pane.sh [セッション名]
# デフォルト: ssot
# ショートカット: Ctrl+b r
#
# 構成:
# ┌──────────┬──────────┐
# │ Claude 0 │ Claude 1 │
# ├──────────┼──────────┤
# │ Claude 2 │ bash   3 │
# ├──────────┼──────────┤
# │ bash   4 │ 監視   5 │
# └──────────┴──────────┘

SESSION="${1:-ssot}"
CLAUDE="$HOME/.npm-global/bin/claude"
MONITOR_CMD='watch -n 5 "tmux ls && tmux list-panes -a"'

# セッション存在確認（なければ作成）
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "セッション '$SESSION' を新規作成..."
  tmux new-session -s "$SESSION" -d -c "$HOME/vaults/SSOT"
fi

PANE_COUNT=$(tmux list-panes -t "$SESSION" -F "#{pane_index}" | wc -l)
echo "現在のペイン数: $PANE_COUNT"

# pane 0以外を削除
echo "ペインを1つにリセット中..."
for i in $(tmux list-panes -t "$SESSION" -F "#{pane_index}" | sort -rn | head -n +2); do
  tmux kill-pane -t "$SESSION:0.$i" 2>/dev/null
done
sleep 0.5

# 5回分割して6ペインにする
echo "6ペイン作成中..."
for i in $(seq 5); do
  tmux split-window -t "$SESSION:0.0" -c "$HOME/vaults/SSOT" 2>/dev/null
done

sleep 0.3

# グリッドレイアウト適用
tmux select-layout -t "$SESSION" tiled
sleep 0.3

# --- 各ペインにコマンド送信 ---

# Pane 0: Claude Code（メイン）
echo "Pane 0: Claude Code起動中..."
tmux send-keys -t "$SESSION:0.0" "$CLAUDE" Enter
sleep 0.5

# Pane 1: Claude Code
echo "Pane 1: Claude Code起動中..."
tmux send-keys -t "$SESSION:0.1" "$CLAUDE" Enter
sleep 0.5

# Pane 2: Claude Code
echo "Pane 2: Claude Code起動中..."
tmux send-keys -t "$SESSION:0.2" "$CLAUDE" Enter
sleep 0.5

# Pane 3: bash（作業用）— そのまま
echo "Pane 3: bash（作業用）"

# Pane 4: bash（左下）
echo "Pane 4: bash（左下）"

# Pane 5: セッション監視（右下）
echo "Pane 5: セッション監視起動中..."
tmux send-keys -t "$SESSION:0.5" "$MONITOR_CMD" Enter
sleep 0.5

echo ""
echo "完了: $(tmux list-panes -t "$SESSION" -F "#{pane_index}" | wc -l) ペイン"
tmux list-panes -t "$SESSION" -F "  Pane #{pane_index}: #{pane_width}x#{pane_height} [#{pane_current_command}]"
echo ""
echo "Pane 0:   Claude Code（メイン）"
echo "Pane 1:   Claude Code"
echo "Pane 2:   Claude Code"
echo "Pane 3:   bash（作業用）"
echo "Pane 4:   bash（左下）"
echo "Pane 5:   セッション監視（右下）"
