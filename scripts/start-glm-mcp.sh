#!/bin/bash
set -a
source ~/.claude/secrets.env
set +a
exec python3 -u ~/.claude/scripts/glm-mcp-server.py
