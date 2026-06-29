#!/bin/bash
# tmux 6ペイン復旧スクリプト (3x2グリッド)
# 使い方: bash scripts/tmux-restore-6pane.sh [セッション名]
# デフォルト: ssot

SESSION="${1:-ssot}"

# セッション存在確認
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "エラー: セッション '$SESSION' が存在しません"
  echo "作成するなら: tmux new-session -s $SESSION -d"
  exit 1
fi

PANE_COUNT=$(tmux list-panes -t "$SESSION" -F "#{pane_index}" | wc -l)
echo "現在のペイン数: $PANE_COUNT"

# pane 0以外を削除
echo "ペインを1つにリセット中..."
for i in $(tmux list-panes -t "$SESSION" -F "#{pane_index}" | sort -rn | head -n +2); do
  tmux kill-pane -t "$SESSION:0.$i" 2>/dev/null
done

# 5回分割して6ペインにする
echo "6ペイン作成中..."
for i in $(seq 5); do
  tmux split-window -t "$SESSION:0.0" 2>/dev/null
done

# グリッドレイアウト適用
tmux select-layout -t "$SESSION" tiled

# 監視ペイン設定（pane 3）
echo "監視ペイン設定中..."
tmux send-keys -t "$SESSION:0.3" \
  'watch -n 5 "tmux list-sessions && echo --- && tmux list-panes -a -F \"#{session_name}:#{pane_index} #{pane_width}x#{pane_height} [#{pane_current_command}]\""' \
  Enter

echo "完了: $(tmux list-panes -t "$SESSION" -F "#{pane_index}" | wc -l) ペイン"
tmux list-panes -t "$SESSION" -F "  Pane #{pane_index}: #{pane_width}x#{pane_height} [#{pane_current_command}]"
