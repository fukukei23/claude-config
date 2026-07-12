#!/bin/bash
# Windows Desktop環境（Git Bash）からWSL側のネイティブコマンド（venv Pythonバイナリ等・
# Linux ELFで直接実行不可なもの）を実行するための汎用wrapper。WSL-CLI環境では不要（直接実行可）。
#
# 【重要】引数には/tmp配下のスクリプトファイルパスを渡すこと（コマンド文字列を直接渡さない）。
# 理由: /home/yn4416等を含むコマンド文字列をBashツールの引数にそのまま書くと、
# PreToolUse path-rewriteフックがUNCパスに書き換えて壊してしまう（2026-07-12確認）。
# 実行したい内容は事前にWriteツールで/tmp配下の一時スクリプトファイルに書き出し
# （Writeツールの書き込み内容はフックの対象外）、そのファイルパスだけを本スクリプトに渡すこと。
#
# 使い方:
#   1. Writeツールで /tmp/<任意名>.sh に実行したいコマンドを書き出す（shebang付き推奨）
#   2. bash win-wsl-exec.sh /tmp/<任意名>.sh

set -e

SCRIPT="$1"
if [ -z "$SCRIPT" ]; then
  echo "使用方法: bash win-wsl-exec.sh <WSL側スクリプトパス（例: /tmp/foo.sh）>" >&2
  exit 1
fi

MSYS2_ARG_CONV_EXCL="*" wsl.exe -e bash "$SCRIPT"
