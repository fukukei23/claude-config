#!/bin/bash
# Claude Code ステータスライン
# stdin JSONからレート制限情報を取得 + 最後に使用したLLMを表示

STATUS_FILE="/tmp/llm-last-used.txt"
INPUT=$(cat)

LLM=""
[ -f "$STATUS_FILE" ] && LLM=$(cat "$STATUS_FILE")

echo "$INPUT" | LLM_STATUS="$LLM" python3 -c "
import sys, json, datetime, os

input_data = sys.stdin.read().strip()
llm = os.environ.get('LLM_STATUS', '')

parts = []
if llm:
    parts.append(llm)

try:
    d = json.loads(input_data) if input_data else {}

    # 5時間レート制限
    rl5 = d.get('rate_limits', {}).get('five_hour', {})
    pct5 = rl5.get('used_percentage', -1)
    if pct5 is not None and pct5 >= 0:
        reset5 = rl5.get('reset_at', '')
        suffix = ''
        if reset5:
            try:
                rt = datetime.datetime.fromisoformat(reset5.replace('Z', '+00:00'))
                now = datetime.datetime.now(datetime.timezone.utc)
                diff = rt - now
                mins = int(diff.total_seconds() / 60)
                if mins > 60:
                    suffix = f' ({mins // 60}h{mins % 60}m)'
                elif mins > 0:
                    suffix = f' ({mins}m)'
            except:
                pass
        parts.append(f'5h: {pct5:.0f}%{suffix}')

    # 7日レート制限
    rl7 = d.get('rate_limits', {}).get('seven_day', {})
    pct7 = rl7.get('used_percentage', -1)
    if pct7 is not None and pct7 >= 0:
        parts.append(f'7d: {pct7:.0f}%')

except:
    pass

if parts:
    print(' | '.join(parts))
elif llm:
    print(llm)
else:
    print('GLM-5.1')
" 2>/dev/null || echo "${LLM:-GLM-5.1}"
