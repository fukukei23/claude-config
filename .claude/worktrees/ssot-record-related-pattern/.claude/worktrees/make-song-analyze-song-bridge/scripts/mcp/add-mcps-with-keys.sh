#!/bin/bash
# MCPサーバー一括登録スクリプト（APIキーはすべて ~/.secrets.env から読み込み）
# 実行前に source ~/.secrets.env を実行してから使う

set -e

NPX=/home/yn4416/.local/share/fnm/node-versions/v22.22.2/installation/bin/npx

: "${LINEAR_API_KEY:?LINEAR_API_KEY is not set. Add it to ~/.secrets.env}"
: "${SENTRY_AUTH_TOKEN:?SENTRY_AUTH_TOKEN is not set.}"
: "${SUPABASE_ACCESS_TOKEN:?SUPABASE_ACCESS_TOKEN is not set.}"
: "${VERCEL_TOKEN:?VERCEL_TOKEN is not set.}"
: "${STRIPE_SECRET_KEY:?STRIPE_SECRET_KEY is not set.}"

claude mcp add --scope user \
  -e LINEAR_API_KEY="$LINEAR_API_KEY" \
  linear -- "$NPX" -y linear-mcp && echo "linear OK"

claude mcp add --scope user \
  -e SENTRY_AUTH_TOKEN="$SENTRY_AUTH_TOKEN" \
  -e SENTRY_ORG=fukukei \
  sentry -- "$NPX" -y @sentry/mcp-server && echo "sentry OK"

claude mcp add --scope user \
  -e SUPABASE_ACCESS_TOKEN="$SUPABASE_ACCESS_TOKEN" \
  supabase -- "$NPX" -y @supabase/mcp-server-supabase@latest && echo "supabase OK"

claude mcp add --scope user \
  -e VERCEL_TOKEN="$VERCEL_TOKEN" \
  vercel -- "$NPX" -y @vercel/mcp-adapter && echo "vercel OK"

claude mcp add --scope user \
  -e STRIPE_SECRET_KEY="$STRIPE_SECRET_KEY" \
  stripe -- "$NPX" -y @stripe/mcp && echo "stripe OK"
