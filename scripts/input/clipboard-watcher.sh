#!/bin/bash
# クリップボード画像を自動保存するバックグラウンドウォッチャー
# Win+Shift+Sでスクショを撮ると自動で保存される

CLIP_DIR="/tmp/clipboard"
CLIP_FILE="$CLIP_DIR/clipboard_latest.png"
mkdir -p "$CLIP_DIR"

# 前回の画像サイズ（変化検知用）
LAST_SIZE=0

echo "クリップボードウォッチャー開始 (PID: $$)"
echo "Win+Shift+S でスクリーンショットを撮ると自動保存されます"
echo "停止: kill $$"

while true; do
    # PowerShellでクリップボード画像を保存（サイズ0で判定）
    /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -Command "
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing
        \$img = [System.Windows.Forms.Clipboard]::GetImage()
        if (\$img -ne \$null) {
            \$winPath = '$(wslpath -w "$CLIP_FILE")'
            \$img.Save(\$winPath, [System.Drawing.Imaging.ImageFormat]::Png)
            Write-Output 'HAS_IMAGE'
        } else {
            Write-Output 'NO_IMAGE'
        }
    " 2>/dev/null | {
        read -r status
        if [ "$status" = "HAS_IMAGE" ]; then
            if [ -f "$CLIP_FILE" ]; then
                SIZE=$(stat -c%s "$CLIP_FILE" 2>/dev/null || echo 0)
                if [ "$SIZE" -ne "$LAST_SIZE" ] && [ "$SIZE" -gt 100 ]; then
                    LAST_SIZE=$SIZE
                    # タイムスタンプ版も保存
                    cp "$CLIP_FILE" "$CLIP_DIR/clipboard_$(date +%Y%m%d_%H%M%S).png"
                    echo "$(date '+%H:%M:%S') クリップボード画像を保存しました ($(($SIZE/1024))KB)"
                fi
            fi
        fi
    }
    sleep 2
done
