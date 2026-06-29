#!/bin/bash
# Periodic screenshot monitoring
# Usage: ./monitor-screen.sh [interval_seconds] [output_dir]
# Example: ./monitor-screen.sh 60 /home/yn4416/screenshots

INTERVAL="${1:-60}"
OUTPUT_DIR="${2:-/home/yn4416/screenshots}"
TAKE_SS="/home/yn4416/.claude/scripts/take-screenshot.sh"

mkdir -p "$OUTPUT_DIR"

echo "Starting screen monitor..."
echo "Interval: ${INTERVAL}s"
echo "Output: $OUTPUT_DIR"
echo "Press Ctrl+C to stop"

count=0
while true; do
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    OUTPUT_PATH="$OUTPUT_DIR/screenshot_$TIMESTAMP.png"

    $TAKE_SS "$OUTPUT_PATH" 2>/dev/null

    if [ -f "$OUTPUT_PATH" ]; then
        count=$((count + 1))
        echo "[$count] Saved: $OUTPUT_PATH"
    fi

    sleep "$INTERVAL"
done
