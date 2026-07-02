#!/bin/bash
BASE=/home/yn4416/projects
REPOS="NexusCore atelier-kyo-manager reserve-optimizer orchestrix claude-cost-optimizer pw-stealth-enhanced krotam mnp_manager tweetly contextforge ai-ceo-advisor sentinel-governance"

TOTAL=0
echo "リポジトリ                      テスト数"
echo "----------------------------------------"
for repo in $REPOS; do
  dir="$BASE/$repo"
  if [ ! -d "$dir" ]; then
    echo "$repo: (なし)"
    continue
  fi
  # pytestがある場合
  if [ -f "$dir/requirements.txt" ] || [ -f "$dir/pyproject.toml" ] || [ -f "$dir/setup.py" ] || find "$dir" -name "test_*.py" -maxdepth 4 | grep -q .; then
    count=$(cd "$dir" && python3 -m pytest --collect-only -q 2>/dev/null | grep -E "^[0-9]+ test" | awk '{print $1}')
    if [ -z "$count" ]; then
      # fallback: grep test functions
      count=$(find "$dir" -name "test_*.py" -o -name "*_test.py" 2>/dev/null | xargs grep -l "def test_" 2>/dev/null | xargs grep -c "def test_" 2>/dev/null | awk -F: '{sum+=$2} END{print sum}')
    fi
  else
    count=0
  fi
  count=${count:-0}
  printf "%-32s %6d\n" "$repo" "$count"
  TOTAL=$((TOTAL + count))
done
echo "----------------------------------------"
printf "%-32s %6d\n" "合計" "$TOTAL"
