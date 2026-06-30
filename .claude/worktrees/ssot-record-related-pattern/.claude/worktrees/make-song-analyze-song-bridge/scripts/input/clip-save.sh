#!/bin/bash
# クリップボードの画像を保存するスクリプト
# 使い方: Win+Shift+S でスクショ → clip-save.sh で保存 → パスが表示される

# 保存先（常に同じパスに上書き）
CLIP_DIR="/tmp/clipboard"
mkdir -p "$CLIP_DIR"

# タイムスタンプ付きファイル名（最新版は常に clipboard_latest.png）
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
WIN_PATH=$(wslpath -w "$CLIP_DIR")

# PowerShellでクリップボード画像を保存
RESULT=$(/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -Command "
Add-Type -AssemblyName System.Windows.Forms
\$img = [System.Windows.Forms.Clipboard]::GetImage()
if (\$img -ne \$null) {
    \$latestPath = '${WIN_PATH}\\clipboard_latest.png'
    \$stampPath = '${WIN_PATH}\\clipboard_${TIMESTAMP}.png'
    \$img.Save(\$latestPath, [System.Drawing.Imaging.ImageFormat]::Png)
    \$img.Save(\$stampPath, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Output 'OK'
} else {
    Write-Output 'NO_IMAGE'
}
" 2>/dev/null)

if [ "$RESULT" = "OK" ]; then
    echo ""
    echo "クリップボード画像を保存しました:"
    echo "  $CLIP_DIR/clipboard_latest.png"
    echo ""
    echo "Claude Codeで以下のように使えます:"
    echo "  この画像を分析して: $CLIP_DIR/clipboard_latest.png"
else
    echo "エラー: クリップボードに画像がありません"
    echo "Win+Shift+S でスクリーンショットを撮ってから再度実行してください"
    exit 1
fi
