#!/bin/bash
# WSLのskillsをWindowsデスクトップに自動同期する（Stop hook）
# ~/.claude/skills/ -> C:\Users\yn441\.claude\skills\

WSL_SKILLS="/home/yn4416/.claude/skills"
WIN_SKILLS="/mnt/c/Users/yn441/.claude/skills"

[ -d "$WIN_SKILLS" ] || exit 0

# 追加・更新（WSL側にあってWindows側と異なるもの）
for item in "$WSL_SKILLS"/*/; do
    name=$(basename "$item")
    win_item="$WIN_SKILLS/$name"
    skill_file="$item/SKILL.md"

    if [ ! -d "$win_item" ]; then
        # 新規追加
        cp -r "$item" "$win_item" 2>/dev/null && \
            echo "sync-skills: 追加 $name" || true
    elif [ -f "$skill_file" ] && [ -f "$win_item/SKILL.md" ]; then
        # 既存: SKILL.mdが新しければ上書き
        if [ "$skill_file" -nt "$win_item/SKILL.md" ]; then
            cp -r "$item" "$WIN_SKILLS/" 2>/dev/null && \
                echo "sync-skills: 更新 $name" || true
        fi
    fi
done

# .mdファイル形式のスキル（サブディレクトリでないもの）
for item in "$WSL_SKILLS"/*.md; do
    [ -f "$item" ] || continue
    name=$(basename "$item")
    win_item="$WIN_SKILLS/$name"
    if [ ! -f "$win_item" ] || [ "$item" -nt "$win_item" ]; then
        cp "$item" "$win_item" 2>/dev/null && \
            echo "sync-skills: 同期 $name" || true
    fi
done

exit 0
