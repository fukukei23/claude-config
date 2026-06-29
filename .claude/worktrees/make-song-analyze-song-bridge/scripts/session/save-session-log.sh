#!/bin/bash
# Claude Code セッション終了時にSSOT日記にタイムスタンプを記録
# スパム防止: 既存マーカーを削除してから最新の1件だけ追加する

SSOT_PATH="/home/yn4416/projects/obsidian-ssot"
TODAY=$(date +%Y-%m-%d)
DAILY_LOG="$SSOT_PATH/10_DAILY/$TODAY.md"
NOW=$(date +%H:%M)

# 日次ログが存在しない場合はヘッダーのみ作成
if [ ! -f "$DAILY_LOG" ]; then
    mkdir -p "$(dirname "$DAILY_LOG")"
    echo "# $TODAY" > "$DAILY_LOG"
fi

# 既存のセッション終了マーカーを全て削除
sed -i '/^セッション終了:/d' "$DAILY_LOG"

# 末尾の --- と空行をクリーンアップ
while true; do
    last_line=$(tail -1 "$DAILY_LOG" 2>/dev/null)
    case "$last_line" in
        ---|"") sed -i '$d' "$DAILY_LOG" ;;
        *) break ;;
    esac
done

# 最新のマーカーを1件だけ追加
echo "" >> "$DAILY_LOG"
echo "---" >> "$DAILY_LOG"
echo "セッション終了: $NOW" >> "$DAILY_LOG"

exit 0
