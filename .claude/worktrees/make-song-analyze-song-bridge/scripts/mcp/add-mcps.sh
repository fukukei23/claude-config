#!/bin/bash
NPX=/home/yn4416/.local/share/fnm/node-versions/v22.22.2/installation/bin/npx

claude mcp add --scope user context7 -- "$NPX" -y @upstash/context7-mcp && echo "context7 OK"
claude mcp add --scope user mermaid -- "$NPX" -y mermaid-mcp-server && echo "mermaid OK"
claude mcp add --scope user tavily -- "$NPX" -y tavily-mcp && echo "tavily OK"
claude mcp add --scope user linear -- "$NPX" -y linear-mcp && echo "linear OK"
claude mcp add --scope user sentry -- "$NPX" -y @sentry/mcp-server && echo "sentry OK"
claude mcp add --scope user supabase -- "$NPX" -y @supabase/mcp-server-supabase@latest && echo "supabase OK"
claude mcp add --scope user vercel -- "$NPX" -y @vercel/mcp-adapter && echo "vercel OK"
claude mcp add --scope user stripe -- "$NPX" -y @stripe/mcp && echo "stripe OK"
