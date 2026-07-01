#!/usr/bin/env python3
"""Gemini MCP Server - Google Gemini をレビュー/デバッグ用第2オピニオンとして提供
GLM動作中のCLI(GLM)から呼ばれる「逆MCP」。glm-mcp-server.py 構造踏襲 + Gemini固有制約."""

import json
import sys
import os
import urllib.request
import urllib.error
import time


def _load_key():
    """GEMINI_API_KEY を env → ~/.secrets.env フォールバックで取得."""
    key = os.environ.get('GEMINI_API_KEY', '')
    if key:
        return key
    secrets = os.path.expanduser('~/.secrets.env')
    if os.path.exists(secrets):
        with open(secrets) as f:
            for line in f:
                line = line.strip()
                if line.startswith('export GEMINI_API_KEY='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    return ''
